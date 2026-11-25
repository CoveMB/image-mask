import json
import shutil
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_background_light import scalar_decode, scalar_encode
from test_effects import fixture_project
from test_export import mode_arguments
from test_mist import _scalar_density, settings
from test_mist_project import FEATHERED_AREA, mist_request

from blackmask import operations
from blackmask.export import export_project, read_rgb16, render_background
from blackmask.framing import frame_result, framing_preview, validate_margins
from blackmask.mist import MistOperands, blend_mist_into_result, make_mist_density
from blackmask.project import ProjectError, _json_bytes, digest
from blackmask.repair import scalar16
from blackmask.series_framing import (
    SeriesSettings,
    compute_series_layout,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)


@pytest.mark.parametrize(
    ("mode", "switch"),
    [
        ("native", "on"),
        ("add-margins", "on"),
        ("match-series", "on"),
        ("add-margins", "off"),
        ("match-series", "zero"),
    ],
)
def test_editable_mist_replays_without_original_project_and_keeps_variants(tmp_path, mode, switch):
    ramp = np.arange(24, dtype=np.uint16).reshape(4, 6, 1)
    project, _, base = fixture_project(
        tmp_path, ramp * 400 + np.array([36000, 22000, 4000], np.uint16)
    )
    area = {
        "regions": FEATHERED_AREA["regions"]
        + [
            {
                "id": "edge",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [0, 0, 1, 4],
                "feather_px": 0,
            }
        ],
        "protection": [],
    }
    config = settings(6, 4, density=0 if switch == "zero" else 0.75, tint_srgb="#8c9192")
    applied = operations.apply_operation(project, mist_request(project, area=area, config=config))
    if switch == "off":
        applied = operations.apply_operation(project, mist_request(project, disable=True))
    options = {"variants": ("black", "transparent", "editable"), **mode_arguments(mode)}
    base_delivery = export_project(project, **options)
    assert export_project(project, **options)["reused"]
    assert (
        json.loads(Path(base_delivery["manifest_file"]).read_bytes())["export_version"]
        == "requested-result-v5"
    )
    options.update(revision=applied["revision"], draft=True)
    delivered = export_project(project, **options)
    assert export_project(project, **options)["reused"]
    native = tmp_path / "detached-native"
    shutil.copytree(Path(delivered.get("editable_companion", delivered)["directory"]), native)
    presentation = native if mode == "native" else tmp_path / "detached-frame"
    if mode != "native":
        shutil.copytree(Path(delivered["directory"]), presentation)
    for name in ("black_rgb16.tif", "transparent_RGBA8_VIEW.png"):
        assert (presentation / name).read_bytes() == (
            Path(base_delivery["directory"]) / name
        ).read_bytes()
    accepted = json.loads((project / "state.json").read_bytes())["accepted_revision"]
    assert accepted == base["revision"]
    project.rename(tmp_path / "unavailable-project")
    (tmp_path / "source.tif").rename(tmp_path / "unavailable-source.tif")

    record = json.loads((presentation / "manifest.json").read_bytes())
    native_record = json.loads((native / "manifest.json").read_bytes())
    assert record["mist"] == native_record["mist"] == applied["mist"]
    assert record["export_version"] == record["encoding"]["version"] == "requested-result-v6"
    for name in ("area", "settings", "density", "clear"):
        filename = f"mist_{name}.json" if name in ("area", "settings") else f"mist_{name}16.png"
        assert digest((native / filename).read_bytes()) == record["mist"][name + "_sha256"]
        if mode != "native":
            assert (
                record["editable_companion"]["files_sha256"][filename]
                == record["mist"][name + "_sha256"]
            )
    assert json.loads((native / "mist_area.json").read_bytes()) == area
    foreground = read_rgb16(native / "foreground_rgb16.tif")
    alpha = scalar16(native / "alpha16.png")
    assert np.any((alpha > 0) & (alpha < 65535))
    mist = MistOperands(
        scalar16(native / "mist_density16.png"),
        scalar16(native / "mist_clear16.png"),
        json.loads((native / "mist_settings.json").read_bytes()),
    )
    backdrop = read_rgb16(native / "background_rgb16.tif")
    flattened = render_background(foreground, alpha, backdrop)
    with patch(
        "blackmask.mist.sample_mist_density",
        side_effect=AssertionError("native replay regenerated density"),
    ):
        reconstructed = blend_mist_into_result(
            flattened.copy(), mist.density16, mist.clear16, mist.settings
        )
    assert bool(np.any(reconstructed != flattened)) is (switch == "on")
    np.testing.assert_array_equal(reconstructed, read_rgb16(native / "result_rgb16.tif"))
    if mode == "add-margins":
        reconstructed = frame_result(
            reconstructed, backdrop, validate_margins(record["margins"], (6, 4)), mist=mist
        )
    if mode == "match-series":
        layout = compute_series_layout(alpha, validate_series_settings(record["settings"]))
        background_settings = json.loads((native / "background_settings.json").read_bytes())
        reconstructed = render_series(
            foreground,
            alpha,
            series_sampling_plan(layout),
            background_settings=background_settings,
            mist=mist,
        )
    np.testing.assert_array_equal(reconstructed, read_rgb16(presentation / "result_rgb16.tif"))


@pytest.mark.parametrize(
    "member", ["mist_settings.json", "mist_area.json", "mist_density16.png", "mist_clear16.png"]
)
def test_disabled_mist_operand_cannot_be_rehashed_into_framed_companion(tmp_path, member):
    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, mist_request(project))
    disabled = operations.apply_operation(project, mist_request(project, disable=True))
    options = {
        "revision": disabled["revision"],
        "draft": True,
        "variants": ("editable",),
        **mode_arguments("add-margins"),
    }
    result = export_project(project, **options)
    native = Path(result["editable_companion"]["directory"])
    path = native / member
    if member.endswith(".png"):
        Image.fromarray(np.zeros((4, 6), np.uint16)).save(path)
    else:
        path.write_bytes(b"{}\n")
    table = native / "manifest.json"
    manifest = json.loads(table.read_bytes())
    manifest["files"][member].update(sha256=digest(path.read_bytes()), bytes=path.stat().st_size)
    table.write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="Mist operand binding"):
        export_project(project, **options)


def test_margin_extension_has_exact_native_rectangle_clear_border_and_matching_preview():
    native_size = (20, 16)
    config = settings(*native_size, tint_srgb="#ffffff")
    native = np.full((16, 20, 3), [2500, 4000, 6000], np.uint16)
    backdrop = np.full_like(native, 1234)
    clear = np.zeros(native.shape[:2], np.uint16)
    clear[:, 0] = 65535
    mist = MistOperands(make_mist_density(config, native_size), clear, config)
    margins = validate_margins(
        {"left_px": 4, "right_px": 5, "top_px": 3, "bottom_px": 2}, native_size
    )
    padded = frame_result(native, backdrop, margins, mist=mist)
    np.testing.assert_array_equal(padded[3:19, 4:24], native)
    np.testing.assert_array_equal(padded[:, :4], 1234)
    density = _scalar_density(config, native_size, 20.5, 6.5)
    assert density > 0
    expected = scalar_encode(
        scalar_decode(1234 / 65535) + density / 65535 * (1 - scalar_decode(1234 / 65535))
    )
    np.testing.assert_array_equal(padded[9, 24], expected)
    preview, geometry = framing_preview(native, backdrop, margins, max_edge=11, mist=mist)
    dw, dh = geometry["display_dimensions_wh"]
    xs = (2 * np.arange(dw) + 1) * padded.shape[1] // (2 * dw)
    ys = (2 * np.arange(dh) + 1) * padded.shape[0] // (2 * dh)
    np.testing.assert_array_equal(
        preview, np.rint(padded[np.ix_(ys, xs)].astype(float) / 257).astype(np.uint8)
    )


def test_series_unit_translation_uses_saved_native_maps_inside_capture():
    alpha = np.zeros((14, 18), np.uint16)
    alpha[2:12, 3:15] = 32768
    foreground = np.full((*alpha.shape, 3), 26000, np.uint16)
    layout = compute_series_layout(alpha, SeriesSettings("Identity", 20, 16, 200, 0))
    assert layout.scale == 1 and layout.translation_xy == (1, 1)
    plan = series_sampling_plan(layout)
    config = settings(18, 14, tint_srgb="#ffffff")
    density = np.zeros_like(alpha)
    density[8, 8] = 32768
    clear = np.zeros_like(alpha)
    baseline = render_series(foreground, alpha, plan)
    actual = render_series(foreground, alpha, plan, mist=MistOperands(density, clear, config))
    expected = baseline.copy()
    native_rgb = expected[1:15, 1:19]
    blend_mist_into_result(native_rgb, density, clear, config)
    np.testing.assert_array_equal(actual[1:15, 1:19], native_rgb)
    assert np.any(actual[9, 9] != baseline[9, 9])
    assert _scalar_density(config, (18, 14), -0.5, 6.5) > 0
    assert np.any(actual[7, 0] != baseline[7, 0])


@pytest.mark.parametrize("display", [None, (7, 6)])
def test_minified_series_projects_clearance_beyond_nearest_and_uses_full_pixel_centres(display):
    size = (100, 100)
    alpha = np.full((100, 100), 17500, np.uint16)
    foreground = np.full((100, 100, 3), [16000, 27000, 55000], np.uint16)
    plan = series_sampling_plan(
        compute_series_layout(alpha, SeriesSettings("Small", 12, 11, 0, 0)),
        display_dimensions_wh=display,
    )
    config = settings(*size, tint_srgb="#ffffff", density=1, seed=501)
    clear = np.zeros_like(alpha)
    clear[50, 50] = 65535
    density = make_mist_density(config, size)
    baseline = render_series(foreground, alpha, plan)
    unprotected = render_series(
        foreground, alpha, plan, mist=MistOperands(density, np.zeros_like(clear), config)
    )
    protected = render_series(foreground, alpha, plan, mist=MistOperands(density, clear, config))
    width, height = plan.display_dimensions_wh
    scale = plan.layout.scale
    tx, ty = plan.layout.translation_xy
    footprint = max(1, 12 / (width * scale), 11 / (height * scale))
    witness = 0
    for j in range(height):
        for i in range(width):
            x = (((2 * i + 1) * 12 // (2 * width)) + 0.5 - tx) / scale
            y = (((2 * j + 1) * 11 // (2 * height)) + 0.5 - ty) / scale
            density_value = _scalar_density(config, size, x, y, footprint)
            expected = []
            for channel in baseline[j, i]:
                linear = scalar_decode(int(channel) / 65535)
                expected.append(scalar_encode(linear + density_value / 65535 * (1 - linear)))
            assert unprotected[j, i].tolist() == expected
            spacing_x = 12 / (width * scale)
            spacing_y = 11 / (height * scale)
            center_x = ((i + 0.5) * 12 / width - tx) / scale
            center_y = ((j + 0.5) * 11 / height - ty) / scale
            if (
                abs(center_x - 50.5) < 3 * spacing_x - 0.1
                and abs(center_y - 50.5) < 3 * spacing_y - 0.1
                and max(abs(x - 50.5), abs(y - 50.5)) > 2
                and density_value
            ):
                np.testing.assert_array_equal(protected[j, i], baseline[j, i])
                witness += 1
    assert witness and np.any(protected != unprotected) and np.any(protected != baseline)


def test_mist_oversized_delivery_is_rejected_before_creating_stage(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, mist_request(project))
    with pytest.raises(ValueError, match="32768"):
        export_project(
            project,
            revision=result["revision"],
            draft=True,
            framing={"left_px": 32768, "right_px": 0, "top_px": 0, "bottom_px": 0},
        )
    assert not (project / "exports").exists()
