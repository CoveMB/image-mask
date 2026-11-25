"""The opt-in Result target preserves native masks, diagnostics and editable replay."""

import io
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_background import background_request
from test_background_light import light_request, light_settings
from test_effects import fixture_project
from test_export import mode_arguments
from test_fade_reduction import area, rectangle, reduction_request
from test_mist_project import mist_request
from test_series_framing import scalar_background_blend
from test_spatial_fade import delivered_spatial, operands, spatial_request, spatial_settings
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask import operations
from blackmask.background_light import combine_background_light
from blackmask.export import export_project, read_rgb16, render_background, render_saved_result
from blackmask.framing import frame_result, validate_margins
from blackmask.mist import MistOperands, blend_mist_into_result
from blackmask.project import ProjectError, _json_bytes, digest, read_project
from blackmask.repair import scalar16
from blackmask.series_framing import (
    compute_series_layout,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)
from blackmask.spatial_fade import validate_spatial_fade


def test_native_lit_target_converges_exactly_and_preserves_protected_contribution():
    alpha = np.array([[0, 1, 32768, 32768, 44444, 65535]], np.uint16)
    foreground = np.full((1, 6, 3), [31000, 42000, 53000], np.uint16)
    base = np.full_like(foreground, [1000, 3000, 5000])
    displayed = combine_background_light(
        base, np.arange(18, dtype=np.uint16).reshape(1, 6, 3) * 1400, enabled=True
    )
    weight = np.full(alpha.shape, 65535, np.uint16)
    weight[0, 4] = 32768
    spatial = operands(dict(spatial_settings(6, 1), target="lit"), weight)
    spatial.protection[0, 3] = True
    actual = render_background(
        foreground, alpha, displayed, spatial_fade=spatial, fade_background16=base
    )
    expected = displayed.copy()
    for x, amount in ((3, 0.0), (4, 32768 / 65535)):
        a = int(alpha[0, x]) / 65535
        for channel in range(3):
            f, b = int(foreground[0, x, channel]), int(displayed[0, x, channel])
            expected[0, x, channel] = round(a * scalar_background_blend(f, b, amount) + (1 - a) * b)
    assert np.any(displayed != base)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("target", ["base", None, ["lit"]])
def test_invalid_explicit_target_is_rejected_even_with_fade_off(target):
    with pytest.raises(ProjectError, match="Spatial fade target"):
        validate_spatial_fade(dict(spatial_settings(6, 4), enabled=False, target=target), 6, 4)


def lit_project(tmp_path):
    ramp = np.arange(24, dtype=np.uint16).reshape(4, 6, 1)
    project, _, accepted = fixture_project(
        tmp_path, ramp * 400 + np.array([36000, 22000, 4000], np.uint16)
    )
    operations.apply_operation(project, background_request(project, "#312520", 0.6))
    light = light_settings(brightness=0.45, color_srgb="#96A6CB")
    operations.apply_operation(project, light_request(project, light))
    settings = spatial_settings(6, 4)
    settings["oval"].update(center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], amount=1.0)
    base = operations.apply_operation(project, spatial_request(project, settings, candidate=True))
    lit = operations.apply_operation(
        project, spatial_request(project, dict(settings, target="lit"), candidate=True)
    )
    return project, accepted, base, lit, light


def test_saved_lit_target_native_comparisons_and_restore(tmp_path):
    project, accepted, base, lit, light = lit_project(tmp_path)
    assert lit["spatial_fade"]["settings"]["target"] == "lit"
    reduced = operations.apply_operation(
        project,
        reduction_request(project, area(rectangle(box=[2, 1, 3, 2]))),
    )
    assert reduced["spatial_fade"]["settings"]["target"] == "lit"
    with_mist = operations.apply_operation(project, mist_request(project))
    light_off = operations.apply_operation(
        project, light_request(project, dict(light, enabled=False))
    )
    master = accepted["developed_id"]
    lit_result = render_saved_result(project, lit["revision"], master)
    assert np.any(lit_result != render_saved_result(project, base["revision"], master))
    assert np.any(lit_result != render_saved_result(project, reduced["revision"], master))
    operations.restore_revision(project, with_mist["revision"])
    assert read_project(project)["accepted_revision"] == accepted["revision"]

    with running(project) as server:
        saved = next(
            row
            for row in server.snapshot()["revisions"]
            if row["revision"] == with_mist["revision"]
        )
        assert saved["spatial_fade"]["settings"]["target"] == "lit"

        def pixels(revision, panel="result", suffix=""):
            status, png, _ = http(server, f"/image/{panel}/{revision}/0,0,6,4{suffix}")
            assert status == 200
            with Image.open(io.BytesIO(png)) as image:
                return np.array(image)

        def expected(revision):
            return np.rint(render_saved_result(project, revision, master) / 257).astype(np.uint8)

        current = with_mist["revision"]
        np.testing.assert_array_equal(pixels(current), expected(current))
        np.testing.assert_array_equal(
            pixels(current, suffix="/mist-off"), expected(reduced["revision"])
        )
        np.testing.assert_array_equal(
            pixels(current, suffix="/background-light-off"), expected(light_off["revision"])
        )
        for panel in ("black", "gray", "white", "alpha"):
            np.testing.assert_array_equal(
                pixels(lit["revision"], panel), pixels(base["revision"], panel)
            )


@pytest.mark.parametrize("with_mist", [False, True])
def test_lit_delivery_replays_all_modes_and_binds_saved_operands(tmp_path, with_mist):
    project, accepted, base, lit, light = lit_project(tmp_path)
    if with_mist:
        lit_revision = lit["revision"]
        operations.restore_revision(project, base["revision"])
        base = operations.apply_operation(project, mist_request(project))
        operations.restore_revision(project, lit_revision)
        lit = operations.apply_operation(project, mist_request(project))
    options = {"variants": ("black", "transparent", "editable"), "draft": True}
    detached = tmp_path / "detached"
    detached.mkdir()
    deliveries = {}
    for mode in ("native", "add-margins", "match-series"):
        args = mode_arguments(mode)
        legacy = export_project(project, revision=base["revision"], **options, **args)
        delivery = export_project(project, revision=lit["revision"], **options, **args)
        deliveries[mode] = delivery
        assert export_project(project, revision=lit["revision"], **options, **args)["reused"]
        source = Path(delivery["directory"])
        shutil.copytree(source, detached / mode)
        for name in ("black_rgb16.tif", "transparent_RGBA8_VIEW.png"):
            assert (source / name).read_bytes() == (Path(legacy["directory"]) / name).read_bytes()
    native = detached / "native"
    record = json.loads((native / "manifest.json").read_bytes())
    assert record["export_version"] == record["encoding"]["version"] == "requested-result-v7"
    native_members = (
        "spatial_fade_settings.json",
        "background_rgb16.tif",
        "background_settings.json",
        "background_light_rgb16.tif",
        "background_light_settings.json",
    )
    native_directory = Path(deliveries["native"]["directory"])
    margin_companion = Path(deliveries["add-margins"]["editable_companion"]["directory"])
    tamper_cases = [(native_directory, name, {}) for name in native_members]
    tamper_cases.append(
        (margin_companion, "spatial_fade_settings.json", mode_arguments("add-margins"))
    )
    for directory, name, args in tamper_cases:
        manifest_path = directory / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        path = directory / name
        saved = path.read_bytes()
        # Self-consistent member metadata must not authorize a substitute from another edit.
        substitute = (
            b"{}" if path.suffix == ".json" else (native / "foreground_rgb16.tif").read_bytes()
        )
        try:
            path.write_bytes(substitute)
            modified = json.loads(manifest_bytes)
            modified["files"][name].update(sha256=digest(substitute), bytes=len(substitute))
            manifest_path.write_bytes(_json_bytes(modified))
            with pytest.raises(ProjectError, match="Lit backdrop operand binding mismatch"):
                export_project(project, revision=lit["revision"], **options, **args)
        finally:
            path.write_bytes(saved)
            manifest_path.write_bytes(manifest_bytes)
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    project.rename(tmp_path / "unavailable-project")
    (tmp_path / "source.tif").rename(tmp_path / "unavailable-source.tif")

    foreground = read_rgb16(native / "foreground_rgb16.tif")
    alpha = scalar16(native / "alpha16.png")
    spatial_record = json.loads((native / "spatial_fade_settings.json").read_bytes())
    assert spatial_record == record["spatial_fade"]
    spatial = delivered_spatial(native, spatial_record)
    b0 = read_rgb16(native / "background_rgb16.tif")
    b1 = combine_background_light(
        b0, read_rgb16(native / "background_light_rgb16.tif"), enabled=True
    )
    replayed = render_background(foreground, alpha, b1, spatial_fade=spatial, fade_background16=b0)
    mist = None
    if with_mist:
        mist = MistOperands(
            scalar16(native / "mist_density16.png"),
            scalar16(native / "mist_clear16.png"),
            json.loads((native / "mist_settings.json").read_bytes()),
        )
        pre_mist = replayed.copy()
        blend_mist_into_result(replayed, mist.density16, mist.clear16, mist.settings)
        assert np.any(pre_mist != replayed)
    np.testing.assert_array_equal(replayed, read_rgb16(native / "result_rgb16.tif"))
    margins = detached / "add-margins"
    margins_record = json.loads((margins / "manifest.json").read_bytes())
    assert margins_record["spatial_fade"] == spatial_record
    np.testing.assert_array_equal(
        frame_result(
            replayed,
            b1,
            validate_margins(margins_record["margins"], (6, 4)),
            mist=mist,
        ),
        read_rgb16(margins / "result_rgb16.tif"),
    )
    series = detached / "match-series"
    series_record = json.loads((series / "manifest.json").read_bytes())
    assert series_record["spatial_fade"] == spatial_record
    assert light == json.loads((native / "background_light_settings.json").read_bytes())
    np.testing.assert_array_equal(
        render_series(
            foreground,
            alpha,
            series_sampling_plan(
                compute_series_layout(alpha, validate_series_settings(series_record["settings"]))
            ),
            spatial_fade=spatial,
            background_settings=json.loads((native / "background_settings.json").read_bytes()),
            background_light_settings=light,
            mist=mist,
        ),
        read_rgb16(series / "result_rgb16.tif"),
    )


def test_page_target_only_edit_is_pending_and_late_completion_preserves_newer_edit():
    run_page(
        r"""
await ready();
const target = $('spatialTarget');
assert.equal(target.value, 'base');
target.value = 'lit'; target.onchange();
assert.match($('spatialDraftStatus').textContent, /Unapplied fade/);
assert.equal(posts.length, 0);
await $('spatialApply').onclick();
const sent = posts.at(-1);
assert.equal(sent.spatial_fade.target, 'lit');
target.value = 'base'; target.onchange();
const current = {...servedState.revisions[0], revision:'rev-002',
  revision_manifest_sha256:'b'.repeat(64), spatial_fade:{settings:sent.spatial_fade}};
servedState.revisions.push(current);
servedState.working_revision = 'rev-002';
servedState.action = {name:'effects', running:false, error:null, result:{
  revision:'rev-002', parent:'rev-001', spatial_fade:current.spatial_fade}};
actionWasRunning = true;
await refresh();
assert.equal(target.value, 'base');
assert.match($('spatialDraftStatus').textContent, /Stale unapplied/);
await $('spatialApply').onclick();
assert.equal(posts.length, 1);
await $('spatialCancel').onclick();
assert.equal(target.value, 'lit');
target.value = 'base'; target.onchange();
await $('spatialDisable').onclick();
assert.equal(posts.at(-1).spatial_fade.target, 'lit');
assert.equal(posts.at(-1).spatial_fade.enabled, false);
"""
    )
