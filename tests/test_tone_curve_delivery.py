"""Native and presentation deliveries replay from portable operands."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import tifffile
from test_effects import fixture_project, shading_request
from test_export import mode_arguments
from test_exposure import exposure_request
from test_shadow_fade import fade_request
from test_sharpening import sharpening_project, sharpening_request
from test_tone_curve import POINTS, curve_request

from blackmask import operations
from blackmask.export import export_project, render_background, render_black
from blackmask.exposure import apply_exposure
from blackmask.framing import frame_result, validate_margins
from blackmask.project import digest
from blackmask.repair import scalar16
from blackmask.series_framing import (
    compute_series_layout,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)
from blackmask.shadow_fade import apply_shadow_fade
from blackmask.sharpening import apply_local_sharpening
from blackmask.tone_curve import apply_local_tone_curve


def hashes(directory):
    return {path.name: digest(path.read_bytes()) for path in directory.iterdir()}


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("enabled", [True, False])
def test_curve_editable_delivery_replays_rgb16(tmp_path, mode, enabled):
    project, _, _ = sharpening_project(tmp_path)
    if mode == "add-margins":
        operations.apply_operation(project, sharpening_request(project))
        operations.apply_operation(project, exposure_request(project, ev=0.5))
    operations.apply_operation(
        project, curve_request(project, points=[[3000, 6000]], candidate=True)
    )
    if not enabled:
        operations.apply_operation(
            project, curve_request(project, points=[[3000, 6000]], enabled=False)
        )
    result = operations.apply_operation(project, fade_request(project, amount=0.3, preserve=0.3))
    if mode == "add-margins":
        result = operations.apply_operation(project, shading_request(project))
    arguments = {"revision": result["revision"], "draft": True, **mode_arguments(mode)}
    compact = export_project(project, **arguments)
    assert {path.name for path in Path(compact["directory"]).iterdir()} == {
        "manifest.json",
        "README.txt",
        "recipe.toml",
        "result_rgb16.tif",
        "result_RGB8_VIEW.png",
    }
    arguments["variants"] = ("editable", "black", "transparent")
    exported = export_project(project, **arguments)
    primary = Path(exported["directory"])
    native = Path(exported.get("editable_companion", {}).get("directory", str(primary)))
    before = {primary: hashes(primary), native: hashes(native)}
    assert export_project(project, **arguments) == {**exported, "reused": True}
    assert all(hashes(path) == expected for path, expected in before.items())
    portable = tmp_path / "portable-native"
    presentation = tmp_path / "portable-presentation"
    shutil.copytree(native, portable)
    shutil.copytree(primary, presentation)
    project.rename(tmp_path / "unavailable-project")
    (tmp_path / "source.tif").rename(tmp_path / "unavailable-source.tif")

    def recorded(name):
        return json.loads((portable / name).read_bytes())

    def operands(prefix):
        return (
            scalar16(portable / f"{prefix}_alpha16.png"),
            scalar16(portable / f"{prefix}_support16.png"),
            scalar16(portable / f"{prefix}_protection16.png") != 0,
            recorded(f"{prefix}_settings.json")["settings"],
        )

    def rgb(name):
        return tifffile.imread(portable / f"{name}_rgb16.tif")

    alpha = scalar16(portable / "alpha16.png")
    unexposed = rgb("unexposed_foreground")
    if mode == "add-margins":
        unsharpened = rgb("unsharpened_foreground")
        np.testing.assert_array_equal(unsharpened, rgb("base_foreground"))
        np.testing.assert_array_equal(
            apply_local_sharpening(unsharpened, *operands("sharpening")), unexposed
        )
        uncurved = apply_exposure(unexposed, *operands("exposure"))[0]
    else:
        uncurved = unexposed
        np.testing.assert_array_equal(unexposed, rgb("base_foreground"))
    np.testing.assert_array_equal(uncurved, rgb("uncurved_foreground"))
    assert recorded("tone_curve_area.json")["regions"]
    curve = recorded("tone_curve_settings.json")
    assert curve["enabled"] is enabled
    assert recorded("manifest.json")["local_tone_curve"] == curve
    unfaded = apply_local_tone_curve(uncurved, *operands("tone_curve"))
    assert np.any(unfaded != uncurved) == enabled
    np.testing.assert_array_equal(unfaded, rgb("unfaded_foreground"))
    selected = apply_shadow_fade(unfaded, *operands("shadow_fade"))
    np.testing.assert_array_equal(selected, rgb("foreground"))
    shading = recorded("shading_settings.json") if mode == "add-margins" else {}
    weight = scalar16(portable / "shadow_weight16.png") if shading else None
    opacity = shading["opacity"] if shading.get("enabled") else 0
    background = rgb("background") if (portable / "background_rgb16.tif").exists() else None
    flattened = (
        render_background(selected, alpha, background, weight, opacity)
        if background is not None
        else render_black(selected, alpha, weight, opacity)
    )
    np.testing.assert_array_equal(flattened, rgb("result"))
    delivery = json.loads((presentation / "manifest.json").read_bytes())
    assert delivery["effects"]["local_tone_curve"] == {
        "enabled": enabled,
        "record_sha256": digest((portable / "tone_curve_settings.json").read_bytes()),
    }
    if mode == "add-margins":
        flattened = frame_result(
            flattened, background, validate_margins(delivery["margins"], (6, 4))
        )
    elif mode == "match-series":
        settings = validate_series_settings(delivery["settings"])
        sampling = series_sampling_plan(compute_series_layout(alpha, settings))
        flattened = render_series(
            selected,
            alpha,
            sampling,
            weight16=weight,
            opacity=opacity,
            background_settings=recorded("background_settings.json")
            if background is not None
            else None,
        )
    np.testing.assert_array_equal(flattened, tifffile.imread(presentation / "result_rgb16.tif"))


def test_curve_free_delivery_retains_frozen_identity(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    variants = ("editable", "black", "transparent")
    delivery = export_project(project, variants=variants)
    directory = Path(delivery["directory"])
    frozen = hashes(directory)
    assert set(frozen) == {
        "manifest.json",
        "README.txt",
        "recipe.toml",
        "result_rgb16.tif",
        "result_RGB8_VIEW.png",
        "background_rgb16.tif",
        "background_settings.json",
        "black_rgb16.tif",
        "black_RGB8_VIEW.png",
        "transparent_RGBA8_VIEW.png",
        "foreground_rgb16.tif",
        "source_rgb16.tif",
        "alpha16.png",
    }
    # Native notes from 0bf8ed5 are independent of the execution runtime and source locator.
    assert (
        frozen["README.txt"] == "c9ae141e21a2a3ac3942c94f744f84a81b40f212a89cd2f2571aa0772e137a25"
    )
    record = json.loads((directory / "manifest.json").read_bytes())
    assert record["export_version"] == "requested-result-v5"
    assert "local_tone_curve" not in record["effects"]
    assert directory.name == "rev-002-native-" + record["identity_sha256"]
    operations.apply_operation(project, curve_request(project, points=POINTS))
    assert export_project(project, variants=variants) == {**delivery, "reused": True}
    assert hashes(directory) == frozen
