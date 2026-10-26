"""Portable sharpening deliveries reconstructed in an actual offline child."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import PIL._imaging
import pytest
from test_background import background_request
from test_effects import effect_request, shading_request
from test_export import mode_arguments
from test_exposure import exposure_request
from test_shadow_fade import fade_request
from test_sharpening import sharpening_project, sharpening_request
from test_spatial_fade import spatial_request

from blackmask import operations
from blackmask.export import export_project

REPLAY = r"""
import json, sys
from pathlib import Path
from unittest.mock import patch
import numpy as np, tifffile, PIL._imaging
from PIL import Image
from blackmask.sharpening import apply_local_sharpening
from blackmask.exposure import apply_exposure
from blackmask.shadow_fade import apply_shadow_fade
from blackmask.spatial_fade import SpatialFadeOperands
from blackmask.export import render_background, render_black
from blackmask.framing import frame_result, validate_margins
from blackmask.series_framing import (render_series, compute_series_layout,
                                    series_sampling_plan, validate_series_settings)
from blackmask.repair import scalar16
root, output = map(Path, sys.argv[1:3])
assert PIL._imaging.__file__ == sys.argv[3]
def settings(prefix):
    return json.loads((root / (prefix + '_settings.json')).read_text())['settings']
def operands(prefix):
    return (scalar16(root/(prefix+'_alpha16.png')), scalar16(root/(prefix+'_support16.png')),
            scalar16(root/(prefix+'_protection16.png')) != 0, settings(prefix))
with patch('socket.socket', side_effect=AssertionError('offline')), patch('blackmask.project.load_developed', side_effect=AssertionError('no project')):
    alpha = scalar16(root/'alpha16.png')
    rgb = apply_local_sharpening(tifffile.imread(root/'unsharpened_foreground_rgb16.tif'),
                                *operands('sharpening'))
    np.testing.assert_array_equal(rgb, tifffile.imread(root/'unexposed_foreground_rgb16.tif'))
    if (root/'exposure_settings.json').exists():
        rgb = apply_exposure(rgb, *operands('exposure'))[0]
    if (root/'shadow_fade_settings.json').exists():
        np.testing.assert_array_equal(rgb, tifffile.imread(root/'unfaded_foreground_rgb16.tif'))
        rgb = apply_shadow_fade(rgb, *operands('shadow_fade'))
    np.testing.assert_array_equal(rgb, tifffile.imread(root/'foreground_rgb16.tif'))
    background = tifffile.imread(root/'background_rgb16.tif') if (root/'background_rgb16.tif').exists() else None
    weight = scalar16(root/'shadow_weight16.png') if (root/'shadow_weight16.png').exists() else None
    shading = json.loads((root/'shading_settings.json').read_text()) if (root/'shading_settings.json').exists() else {}
    opacity = shading.get('opacity', 0) if shading.get('enabled') else 0
    spatial = None
    if (root/'spatial_fade_settings.json').exists():
        record = json.loads((root/'spatial_fade_settings.json').read_text())
        if record['enabled']:
            spatial = SpatialFadeOperands(scalar16(root/'spatial_fade_weight16.png'),
                      scalar16(root/'spatial_fade_protection16.png') != 0, record)
    target = background if background is not None else np.zeros_like(rgb) if spatial else None
    native = render_background(rgb, alpha, background, weight, opacity, spatial_fade=spatial,
                               fade_background16=target) if background is not None else render_black(
                               rgb, alpha, weight, opacity, spatial_fade=spatial, fade_background16=target)
    np.testing.assert_array_equal(native, tifffile.imread(root/'result_rgb16.tif'))
    record = json.loads((output/'manifest.json').read_text())
    if record['mode'] == 'add-margins':
        native = frame_result(native, background, validate_margins(record['margins'], (6,4)))
    elif record['mode'] == 'match-series':
        plan = series_sampling_plan(compute_series_layout(alpha, validate_series_settings(record['settings'])))
        native = render_series(rgb, alpha, plan, weight16=weight, opacity=opacity,
                               spatial_fade=spatial,
                               background_settings=json.loads((root/'background_settings.json').read_text()) if background is not None else None)
    np.testing.assert_array_equal(native, tifffile.imread(output/'result_rgb16.tif'))
    with Image.open(output/'result_RGB8_VIEW.png') as image:
        np.testing.assert_array_equal(np.array(image), np.rint(native.astype(float)/257).astype(np.uint8))
print('exported-only replay exact; actual Pillow core verified')
"""


@pytest.mark.parametrize("mode", ["native", "add-margins", "match-series"])
@pytest.mark.parametrize("appearance", ["off", "shading", "spatial"])
def test_editable_export_and_native_companion_replay_without_project(tmp_path, mode, appearance):
    project, _, _ = sharpening_project(tmp_path)
    operations.apply_operation(project, effect_request(project, candidate_comparison=True))
    result = operations.apply_operation(project, sharpening_request(project))
    if appearance != "off":
        operations.apply_operation(project, exposure_request(project, ev=0.3))
        operations.apply_operation(project, fade_request(project, amount=0.2, preserve=0.4))
        operations.apply_operation(project, background_request(project))
        result = operations.apply_operation(
            project,
            shading_request(project)
            if appearance == "shading"
            else spatial_request(project, candidate=True),
        )
    exported = export_project(
        project,
        revision=result["revision"],
        draft=True,
        variants=("editable", "black", "transparent"),
        **mode_arguments(mode),
    )
    primary = Path(exported["directory"])
    native = Path(exported.get("editable_companion", {}).get("directory", str(primary)))
    required = {
        "unsharpened_foreground_rgb16.tif",
        "unexposed_foreground_rgb16.tif",
        "sharpening_support16.png",
        "sharpening_protection16.png",
        "sharpening_alpha16.png",
        "sharpening_settings.json",
        "sharpening_area.json",
    }
    assert required <= {path.name for path in native.iterdir()}
    record = json.loads((native / "manifest.json").read_text())
    assert record["local_sharpening"]["enabled"]
    assert "DRAFT" in (native / "README.txt").read_text()
    portable = tmp_path / "portable-native"
    delivery = tmp_path / "portable-delivery"
    shutil.copytree(native, portable)
    shutil.copytree(primary, delivery)
    project.rename(tmp_path / "unavailable-project")
    (tmp_path / "source.tif").rename(tmp_path / "unavailable-source.tif")
    completed = subprocess.run(
        [sys.executable, "-B", "-c", REPLAY, str(portable), str(delivery), PIL._imaging.__file__],
        cwd=portable,
        env=dict(
            os.environ,
            PYTHONPATH=str(Path("src").resolve()),
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "exported-only replay exact" in completed.stdout
