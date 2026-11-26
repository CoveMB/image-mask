import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_background import legacy_project
from test_background_light import light_settings, scalar_decode, scalar_encode
from test_background_pattern import contour, pattern_settings, wave
from test_background_pattern_project import pattern_request
from test_export import mode_arguments
from test_series_framing import scalar_background_blend
from test_spatial_fade import delivered_spatial, operands, spatial_request, spatial_settings
from test_spatial_fade_target import lit_project

from blackmask import operations
from blackmask.background_pattern import make_background_pattern
from blackmask.export import export_project, read_rgb16, render_saved_result
from blackmask.framing import frame_result, validate_margins
from blackmask.project import ProjectError, _json_bytes, digest, read_revision
from blackmask.repair import scalar16
from blackmask.review import render_presentation_preview
from blackmask.series_framing import (
    compute_series_layout,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)
from blackmask.spatial_fade import spatial_fade_amount


def delivery(project, revision, mode):
    return export_project(
        project,
        revision=revision,
        draft=True,
        variants=("black", "transparent", "editable"),
        **mode_arguments(mode),
    )


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
def test_editable_pattern_delivers_native_backdrop_and_unchanged_diagnostics(tmp_path, mode):
    project, _, _, lit, _ = lit_project(tmp_path)
    saved = operations.apply_operation(project, pattern_request(project))
    off = delivery(project, lit["revision"], mode)
    on = delivery(project, saved["revision"], mode)
    assert delivery(project, saved["revision"], mode)["reused"]
    output = Path(on["directory"])
    detached = tmp_path / "detached-native"
    shutil.copytree(on.get("editable_companion", on)["directory"], detached)
    record = json.loads((detached / "manifest.json").read_bytes())
    pattern = record["background_pattern"]
    for filename, role in (
        ("background_pattern_weight16.png", "weight_sha256"),
        ("background_pattern_settings.json", "settings_sha256"),
    ):
        assert digest((detached / filename).read_bytes()) == pattern[role]
        if mode != "native":
            framed = json.loads((output / "manifest.json").read_bytes())
            assert framed["editable_companion"]["files_sha256"][filename] == pattern[role]
    for name in ("black_rgb16.tif", "transparent_RGBA8_VIEW.png"):
        assert (output / name).read_bytes() == (Path(off["directory"]) / name).read_bytes()

    alpha = scalar16(detached / "alpha16.png")
    before = render_saved_result(project, lit["revision"], lit["developed_id"])
    weights = (scalar16(detached / "background_pattern_weight16.png").astype(float) - 32768) / 32767
    assert np.all(weights == 1)
    assert np.any(alpha == 0) and np.any(alpha == 65535) and np.any((alpha > 0) & (alpha < 65535))
    base = read_rgb16(detached / "background_rgb16.tif")
    light = read_rgb16(detached / "background_light_rgb16.tif")
    rgb16 = read_rgb16(detached / "result_rgb16.tif")
    unrounded_lit = np.vectorize(scalar_decode)(base / 65535) + np.vectorize(scalar_decode)(
        light / 65535
    )
    lit16 = np.vectorize(scalar_encode)(np.minimum(unrounded_lit, 1.0))
    lit16[~np.any(light, axis=2)] = base[~np.any(light, axis=2)]
    b2 = np.full_like(base, 8224)
    foreground = read_rgb16(detached / "foreground_rgb16.tif")
    fade = delivered_spatial(detached, record["spatial_fade"])
    amount = spatial_fade_amount(foreground, alpha, fade)
    assert np.any(amount > 0)
    subject = np.vectorize(scalar_background_blend)(foreground, lit16, amount[..., None])
    coverage = alpha[..., None] / 65535
    expected = np.rint(subject * coverage + b2 * (1 - coverage))
    np.testing.assert_array_equal(rgb16, expected)
    np.testing.assert_array_equal(rgb16[alpha == 65535], before[alpha == 65535])
    np.testing.assert_array_equal(rgb16[alpha == 0], b2[alpha == 0])
    if mode == "add-margins":
        expected_frame = frame_result(rgb16, b2, validate_margins(framed["margins"], (6, 4)))
        np.testing.assert_array_equal(read_rgb16(output / "result_rgb16.tif"), expected_frame)
    if mode != "native":
        arguments = mode_arguments(mode)
        presentation = {"mode": mode}
        if mode == "add-margins":
            presentation["margins"] = arguments["framing"]
        else:
            presentation["settings"] = arguments["series"]
        revision, master = saved["revision"], saved["developed_id"]
        preview, _ = render_presentation_preview(
            project, revision, master, read_revision(project, revision, master), presentation
        )
        with Image.open(output / "result_RGB8_VIEW.png") as pixels:
            np.testing.assert_array_equal(preview, np.asarray(pixels))


@pytest.mark.parametrize("mode", ["add-margins", "match-series"])
def test_v2_pattern_delivery_matches_preview_and_keeps_opaque_lit_fade(tmp_path, mode):
    project, _, _, lit, _ = lit_project(tmp_path)
    settings = pattern_settings(
        irregularity=0.68,
        shapes=[
            contour(center_xy=[1.5, 2], radii_xy=[5, 4]),
            wave(center_xy=[3, 2], rotation_degrees=20, bend_px=0.8),
        ],
    )
    saved = operations.apply_operation(project, pattern_request(project, settings))
    revision, master = saved["revision"], saved["developed_id"]
    manifest = read_revision(project, revision, master)
    record = manifest["background_pattern"]
    assert record["algorithm"] == "signed-background-pattern-v2"
    output = delivery(project, revision, mode)
    folder = Path(output["directory"])
    native = Path(output["editable_companion"]["directory"])
    for member, role in (
        ("background_pattern_weight16.png", "weight_sha256"),
        ("background_pattern_settings.json", "settings_sha256"),
    ):
        assert digest((native / member).read_bytes()) == record[role]
    np.testing.assert_array_equal(
        scalar16(native / "background_pattern_weight16.png"),
        make_background_pattern(settings, (6, 4)),
    )
    result = read_rgb16(native / "result_rgb16.tif")
    np.testing.assert_array_equal(result, render_saved_result(project, revision, master))
    alpha = scalar16(native / "alpha16.png")
    off = render_saved_result(project, lit["revision"], master)
    assert np.any(alpha == 65535) and np.any(alpha == 0)
    np.testing.assert_array_equal(result[alpha == 65535], off[alpha == 65535])
    assert np.any(result[alpha == 0] != off[alpha == 0])
    arguments = mode_arguments(mode)
    presentation = (
        {"mode": mode, "margins": arguments["framing"]}
        if mode == "add-margins"
        else {"mode": mode, "settings": arguments["series"]}
    )
    preview, _ = render_presentation_preview(project, revision, master, manifest, presentation)
    with Image.open(folder / "result_RGB8_VIEW.png") as actual:
        np.testing.assert_array_equal(preview, np.asarray(actual))
    base_folder = Path(delivery(project, lit["revision"], mode)["directory"])
    for member in ("black_rgb16.tif", "transparent_RGBA8_VIEW.png"):
        assert (folder / member).read_bytes() == (base_folder / member).read_bytes()


def test_series_samples_pattern_outside_native_and_bypass_is_exact():
    alpha = np.zeros((9, 9), np.uint16)
    alpha[:8, :6] = 65535
    rgb = np.full((9, 9, 3), 25000, np.uint16)
    series = dict(
        mode_arguments("match-series")["series"],
        output_width_px=10,
        output_height_px=28,
        side_margin_tenths_percent=200,
        minimum_vertical_margin_tenths_percent=0,
    )
    layout = compute_series_layout(alpha, validate_series_settings(series))
    sampling = series_sampling_plan(layout)
    settings = {
        "enabled": True,
        "strength": 1.0,
        "tones_srgb": ["#111111", "#202020"],
        "reverse": False,
        "shapes": [
            {
                "id": "wide",
                "type": "oval",
                "enabled": True,
                "center_xy": [3, 2],
                "rotation_degrees": 0,
                "radii_xy": [18, 18],
                "softness": 0.05,
                "tone": "tone2",
            }
        ],
    }
    assert sampling.identity and sampling.layout.translation_xy == (2, 10)
    fade = operands(
        dict(spatial_settings(9, 9), target="lit"), np.full(alpha.shape, 65535, np.uint16)
    )
    appearance = {
        "background_light_settings": light_settings(brightness=0.45),
        "spatial_fade": fade,
    }
    with_pattern = render_series(
        rgb, alpha, sampling, background_pattern_settings=settings, **appearance
    )
    assert np.all(with_pattern[0, 0] == 8224)
    before = render_series(rgb, alpha, sampling, **appearance)
    subject = np.s_[10:18, 2:8]
    assert np.any(before[subject] != 25000)
    np.testing.assert_array_equal(with_pattern[subject], before[subject])
    compact = series_sampling_plan(layout, display_dimensions_wh=(5, 14))
    backdrop = np.empty((14, 5), bool)
    preview = render_series(
        rgb,
        alpha,
        compact,
        background_pattern_settings=settings,
        backdrop_only=backdrop,
        **appearance,
    )
    assert backdrop[0, 0]
    assert np.all(preview[0, 0] == 8224)
    for bypass in ("black_background", "transparent"):
        np.testing.assert_array_equal(
            render_series(
                rgb,
                alpha,
                sampling,
                background_pattern_settings=settings,
                **appearance,
                **{bypass: True},
            ),
            render_series(rgb, alpha, sampling, **appearance, **{bypass: True}),
        )


def test_pattern_delivery_rejects_rehashed_member(tmp_path):
    project, _, _, _, _ = lit_project(tmp_path)
    saved = operations.apply_operation(project, pattern_request(project))
    delivered = delivery(project, saved["revision"], "match-series")
    native = Path(delivered["editable_companion"]["directory"])
    member = "background_pattern_settings.json"
    path = native / member
    path.write_bytes(path.read_bytes().replace(b"#202020", b"#202021"))
    manifest = native / "manifest.json"
    record = json.loads(manifest.read_bytes())
    record["files"][member]["sha256"] = digest(path.read_bytes())
    manifest.write_bytes(_json_bytes(record))
    with pytest.raises(ProjectError, match="collision"):
        delivery(project, saved["revision"], "match-series")


def test_margins_pattern_preview_keeps_legacy_black_fade_target(tmp_path):
    project, _ = legacy_project(tmp_path)
    fade = spatial_settings(6, 4)
    fade["oval"].update(center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], amount=1.0)
    operations.apply_operation(project, spatial_request(project, fade))
    saved = operations.apply_operation(project, pattern_request(project))
    revision, master = saved["revision"], saved["developed_id"]
    manifest = read_revision(project, revision, master)
    assert "background" not in manifest
    preview, _ = render_presentation_preview(
        project,
        revision,
        master,
        manifest,
        {"mode": "add-margins", "margins": mode_arguments("add-margins")["framing"]},
    )
    output = Path(delivery(project, revision, "add-margins")["directory"])
    with Image.open(output / "result_RGB8_VIEW.png") as pixels:
        np.testing.assert_array_equal(preview, np.asarray(pixels))
