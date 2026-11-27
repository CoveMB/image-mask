"""Detached Cloud replay, diagnostics and framing with a saved matte."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_cloud import AREA, settings
from test_effects import fixture_project
from test_export import mode_arguments
from test_matte_operations import approve, run_matte
from test_operations import edits, request

from blackmask import operations
from blackmask.cloud import CloudOperands, blend_cloud_into_result, make_cloud_clear
from blackmask.export import export_project, read_rgb16, render_background, render_saved_result
from blackmask.framing import frame_result, validate_margins
from blackmask.project import digest
from blackmask.repair import scalar16
from blackmask.series_framing import (
    compute_series_layout,
    render_series,
    series_sampling_plan,
    validate_series_settings,
)


def _apply_cloud(project, tint, area=AREA):
    return operations.apply_operation(
        project,
        request(
            project,
            kind="effects",
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            cloud={"action": "apply", "settings": settings(tint_srgb=tint), "area": area},
        ),
    )


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("tint", ["#000000", "#282828", "#59738A"])
def test_detached_cloud_replay_and_diagnostics(tmp_path, mode, tint):
    project, _, base = fixture_project(tmp_path)
    config = {
        **AREA,
        "coverage": [
            {
                "id": "bank",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 0, 6, 4],
                "feather_px": 2,
            }
        ],
    }
    applied = _apply_cloud(project, tint, config)
    options = {"variants": ("black", "transparent", "editable"), **mode_arguments(mode)}
    baseline = export_project(project, **options)
    options.update(revision=applied["revision"], draft=True)
    delivered = export_project(project, **options)
    assert export_project(project, **options)["reused"]
    native = tmp_path / "detached-native"
    primary = native if mode == "native" else tmp_path / "detached-frame"
    shutil.copytree(Path(delivered.get("editable_companion", delivered)["directory"]), native)
    if mode != "native":
        shutil.copytree(Path(delivered["directory"]), primary)
    for name in ("black_rgb16.tif", "transparent_RGBA8_VIEW.png"):
        assert (primary / name).read_bytes() == (Path(baseline["directory"]) / name).read_bytes()
    with_cloud = render_saved_result(project, applied["revision"], applied["developed_id"])
    assert np.any(
        with_cloud != render_saved_result(project, base["revision"], base["developed_id"])
    )
    project.rename(tmp_path / "unavailable-project")
    (tmp_path / "source.tif").rename(tmp_path / "unavailable-source.tif")

    record = json.loads((primary / "manifest.json").read_bytes())
    companion = json.loads((native / "manifest.json").read_bytes())
    assert record["cloud"] == companion["cloud"] == applied["cloud"]
    assert record["export_version"] == record["encoding"]["version"] == "requested-result-v10"
    for filename, role in (
        ("cloud_density16.png", "density_sha256"),
        ("cloud_light16.png", "light_sha256"),
        ("cloud_clear16.png", "clear_sha256"),
        ("cloud_area.json", "area_sha256"),
        ("cloud_settings.json", "settings_sha256"),
        ("cloud_hard_protection.png", "protection_sha256"),
    ):
        assert digest((native / filename).read_bytes()) == record["cloud"][role]
        if mode != "native":
            assert record["editable_companion"]["files_sha256"][filename] == record["cloud"][role]

    foreground = read_rgb16(native / "foreground_rgb16.tif")
    alpha = scalar16(native / "alpha16.png")
    cloud = CloudOperands(
        scalar16(native / "cloud_density16.png"),
        scalar16(native / "cloud_light16.png"),
        scalar16(native / "cloud_clear16.png"),
        json.loads((native / "cloud_settings.json").read_bytes()),
        json.loads((native / "cloud_area.json").read_bytes()),
        (6, 4),
    )
    assert cloud.settings["tint_srgb"] == tint
    backdrop = read_rgb16(native / "background_rgb16.tif")
    with patch(
        "blackmask.cloud.sample_cloud_density",
        side_effect=AssertionError("native regenerated density"),
    ):
        rebuilt = blend_cloud_into_result(render_background(foreground, alpha, backdrop), cloud)
    np.testing.assert_array_equal(rebuilt, read_rgb16(native / "result_rgb16.tif"))
    np.testing.assert_array_equal(rebuilt, with_cloud)
    if mode == "add-margins":
        rebuilt = frame_result(
            rebuilt, backdrop, validate_margins(record["margins"], (6, 4)), cloud=cloud
        )
        x0, y0, x1, y1 = record["source_rect_xyxy"]
        np.testing.assert_array_equal(rebuilt[y0:y1, x0:x1], with_cloud)
    elif mode == "match-series":
        layout = compute_series_layout(alpha, validate_series_settings(record["settings"]))
        backdrop_settings = json.loads((native / "background_settings.json").read_bytes())
        rebuilt = render_series(
            foreground,
            alpha,
            series_sampling_plan(layout),
            background_settings=backdrop_settings,
            cloud=cloud,
        )
    np.testing.assert_array_equal(rebuilt, read_rgb16(primary / "result_rgb16.tif"))


def test_detached_hard_protection_recovers_lock_hidden_by_authored_clear(tmp_path):
    project, _, base = fixture_project(tmp_path)
    guides = edits(
        project,
        [
            {
                "id": "lock-partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 1, 2, 2],
                "revision": base["revision"],
            }
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=guides))
    approve(project, prepared)
    run_matte(project)
    covered = {
        **AREA,
        "clear": [
            {
                "id": "detail",
                "shape": "rectangle",
                "role": "support",
                "xyxy": [1, 1, 3, 2],
                "feather_px": 0,
            }
        ],
    }
    applied = _apply_cloud(project, "#1A2B3C", covered)
    outcome = export_project(
        project, variants=("editable",), revision=applied["revision"], draft=True
    )
    output = Path(outcome["directory"])
    record = json.loads((output / "manifest.json").read_bytes())
    alpha = scalar16(output / "alpha16.png")
    assert 0 < alpha[1, 1] < 65535
    assert record["files"]["cloud_hard_protection.png"]["precision_bits"] == 8
    with Image.open(output / "cloud_hard_protection.png") as image:
        assert image.mode == "L"
        protection = np.array(image) != 0
    clear = scalar16(output / "cloud_clear16.png")
    regenerated = make_cloud_clear(AREA, applied["developed_id"], protection)
    assert clear[1, 1] == clear[1, 2] == regenerated[1, 1] == 65535
    assert regenerated[1, 2] == 0
