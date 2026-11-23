"""Editable Local Texture can be replayed from delivery data and checked on reuse."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from test_export import DEFAULT_MEMBERS, mode_arguments
from test_shadow_fade import fade_request
from test_texture import SETTINGS
from test_texture_project import texture_fixture, texture_request
from test_tone_curve import curve_request

from blackmask import operations
from blackmask.export import (
    export_project,
    read_rgb16,
    render_background,
    render_black,
    saved_layers,
)
from blackmask.framing import frame_result, validate_margins
from blackmask.ingest import write_developed
from blackmask.project import ProjectError, _json_bytes, digest
from blackmask.repair import scalar16
from blackmask.series_framing import (
    compute_series_layout,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)
from blackmask.shadow_fade import apply_shadow_fade
from blackmask.texture import apply_local_texture
from blackmask.tone_curve import apply_local_tone_curve


@pytest.mark.parametrize(
    "mode,enabled", [("native", True), ("add-margins", False), ("match-series", True)]
)
def test_texture_editable_replay_preserves_stage_order_and_alpha(tmp_path, mode, enabled):
    project, _, parent = texture_fixture(tmp_path)
    operations.apply_operation(project, curve_request(project, candidate=True))
    operations.apply_operation(project, texture_request(project))
    if not enabled:
        operations.apply_operation(
            project,
            texture_request(project, settings=SETTINGS | {"enabled": False}, mode="disable"),
        )
    revision = operations.apply_operation(project, fade_request(project, amount=0.3))["revision"]
    _, original_alpha, _ = saved_layers(project, revision, parent["developed_id"])
    options = dict(revision=revision, draft=True, **mode_arguments(mode))
    compact = export_project(project, **options)
    assert {file.name for file in Path(compact["directory"]).iterdir()} == DEFAULT_MEMBERS
    options["variants"] = ("editable",)
    delivery = export_project(project, **options)
    assert export_project(project, **options) == {**delivery, "reused": True}
    primary = Path(delivery["directory"])
    native = tmp_path / "portable-native"
    shutil.copytree(Path(delivery.get("editable_companion", delivery)["directory"]), native)
    presentation = tmp_path / "portable-presentation"
    if mode != "native":
        shutil.copytree(primary, presentation)
    project.rename(tmp_path / "offline-project")
    (tmp_path / "source.tif").rename(tmp_path / "offline-source.tif")

    def operands(prefix):
        settings = json.loads((native / f"{prefix}_settings.json").read_bytes())["settings"]
        return (
            scalar16(native / f"{prefix}_alpha16.png"),
            scalar16(native / f"{prefix}_support16.png"),
            scalar16(native / f"{prefix}_protection16.png") != 0,
            settings,
        )

    def image(stem):
        return read_rgb16(native / f"{stem}_rgb16.tif")

    alpha = scalar16(native / "alpha16.png")
    np.testing.assert_array_equal(alpha, original_alpha)
    np.testing.assert_array_equal(operands("texture")[0], alpha)
    np.testing.assert_array_equal(image("unexposed_foreground"), image("uncurved_foreground"))
    untextured = apply_local_tone_curve(image("uncurved_foreground"), *operands("tone_curve"))
    np.testing.assert_array_equal(untextured, image("untextured_foreground"))
    assert json.loads((native / "texture_area.json").read_bytes())["protection"]
    unfaded = apply_local_texture(untextured, *operands("texture"))
    assert bool(np.any(unfaded != untextured)) is enabled
    np.testing.assert_array_equal(unfaded, image("unfaded_foreground"))
    selected = apply_shadow_fade(unfaded, *operands("shadow_fade"))
    np.testing.assert_array_equal(selected, image("foreground"))
    background = image("background") if (native / "background_rgb16.tif").exists() else None
    flattened = (
        render_background(selected, alpha, background)
        if background is not None
        else render_black(selected, alpha)
    )
    np.testing.assert_array_equal(flattened, image("result"))
    if mode != "native":
        manifest = json.loads((presentation / "manifest.json").read_bytes())
        if mode == "add-margins":
            flattened = frame_result(
                flattened, background, validate_margins(manifest["margins"], (6, 4))
            )
        else:
            layout = compute_series_layout(alpha, validate_series_settings(manifest["settings"]))
            background_settings = json.loads((native / "background_settings.json").read_bytes())
            flattened = render_series(
                selected,
                alpha,
                series_sampling_plan(layout),
                background_settings=background_settings,
            )
        np.testing.assert_array_equal(flattened, read_rgb16(presentation / "result_rgb16.tif"))


def test_texture_export_rejects_rehashed_untextured_pixels_on_native_and_companion_reuse(tmp_path):
    project, _, _ = texture_fixture(tmp_path)
    revision = operations.apply_operation(project, texture_request(project))["revision"]
    options = {"revision": revision, "draft": True, "variants": ("editable",)}
    native = Path(export_project(project, **options)["directory"])
    operand = native / "untextured_foreground_rgb16.tif"
    tampered = read_rgb16(operand)
    tampered[0, 1] = 31000
    operand.unlink()
    write_developed(operand, tampered)
    manifest_file = native / "manifest.json"
    manifest = json.loads(manifest_file.read_bytes())
    manifest["files"][operand.name]["sha256"] = digest(operand.read_bytes())
    manifest_file.write_bytes(_json_bytes(manifest))
    for extra in ({}, mode_arguments("add-margins")):
        with pytest.raises(ProjectError, match="Local texture input pixels"):
            export_project(project, **options, **extra)
    assert list((project / "exports").iterdir()) == [native]
