import importlib
from unittest.mock import patch

import numpy as np
import pytest


def engine():
    return importlib.import_module("blackmask.matte")


@pytest.mark.parametrize(
    "length,expected",
    [(17, [0]), (1024, [0]), (1025, [0, 1]), (1793, [0, 768, 769]), (2049, [0, 768, 1025])],
)
def test_native_boundary_origins(length, expected):
    assert engine().tile_origins(length) == expected


def test_native_merge_known_bypass_clamp_and_positive_weights():
    matte = engine()
    pixels = np.zeros((1031, 1793, 3), dtype=np.uint8)
    trimap = np.full(pixels.shape[:2], 128, dtype=np.uint8)
    trimap[:2] = 0
    trimap[-2:] = 255
    calls = []

    def predict(rgb, guide, device):
        calls.append((rgb.shape, device))
        return np.full(guide.shape, 0.25), {"device": device}

    alpha, record = matte.native_matte(pixels, trimap, predict, "cpu")
    assert np.all(alpha[:2] == 0) and np.all(alpha[-2:] == 65535)
    assert np.all(alpha[2:-2] == 16384)
    assert record["minimum_weight"] > 0 and len(calls) == 6
    assert all(shape == (1024, 1024, 3) for shape, _ in calls)
    known = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    result, record = matte.native_matte(
        np.zeros((2, 2, 3), dtype=np.uint8),
        known,
        lambda *args: pytest.fail("known tile inference"),
        "cpu",
    )
    np.testing.assert_array_equal(result, known.astype(np.uint16) * 257)
    assert record["inferred_tiles"] == 0


def test_nonfinite_rejected_and_auto_restarts_entire_geometry():
    matte = engine()
    rgb = np.zeros((19, 1025, 3), dtype=np.uint8)
    guide = np.full((19, 1025), 128, dtype=np.uint8)
    with pytest.raises(ValueError, match="finite|failed"):
        matte.native_matte(rgb, guide, lambda *args: (np.full(args[1].shape, np.nan), {}), "cpu")
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        if device == "mps" and calls.count("mps") == 2:
            raise RuntimeError("injected backend failure")
        return np.full(guide.shape, 0.9 if device == "mps" else 0.25), {}

    alpha, record = matte.native_matte(rgb, guide, predict, "auto", auto_mps=True)
    assert calls == ["mps", "mps", "cpu", "cpu"]
    assert np.all(alpha == 16384) and record["device"] == "cpu"
    assert "injected" in record["fallback"]


def test_scalar_render_exact_independent_sentinels_and_straight_view():
    export = importlib.import_module("blackmask.export")
    foreground = np.array(
        [[[65535, 5, 7], [12345, 257, 65535], [65535, 65535, 65535]]], dtype=np.uint16
    )
    alpha = np.array([[32768, 0, 65535]], dtype=np.uint16)
    actual = export.render_black(foreground, alpha)
    np.testing.assert_array_equal(
        actual, np.array([[[32768, 3, 4], [0, 0, 0], [65535, 65535, 65535]]], dtype=np.uint16)
    )
    rgba = export.view_rgba(foreground, alpha)
    assert rgba[0, 0, 0] == 255 and rgba[0, 1, 0] == 48
    assert rgba[0, 0, 3] == 128 and rgba[0, 1, 3] == 0


def test_tile_cache_hash_validation_and_device_separation(tmp_path):
    matte = engine()
    rgb = np.zeros((17, 1025, 3), dtype=np.uint8)
    guide = np.full(rgb.shape[:2], 128, dtype=np.uint8)
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        return np.full(guide.shape, 0.4), {"device": device}

    first, _ = matte.native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity={"master": "a", "pins": "b"}
    )
    second, record = matte.native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity={"master": "a", "pins": "b"}
    )
    assert calls == ["cpu", "cpu"] and record["reused_tiles"] == 2
    np.testing.assert_array_equal(first, second)
    next(tmp_path.glob("*.npz")).write_bytes(b"corrupt")
    matte.native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity={"master": "a", "pins": "b"}
    )
    assert len(calls) == 3
    matte.native_matte(
        rgb, guide, predict, "mps", cache_dir=tmp_path, cache_identity={"master": "a", "pins": "b"}
    )
    assert calls[-2:] == ["mps", "mps"]


def test_vitmatte_missing_assets_no_network(tmp_path):
    from blackmask import models

    with (
        patch("urllib.request.urlopen", side_effect=AssertionError("hidden download")),
        pytest.raises(ValueError, match="missing|setup|hash"),
    ):
        models.VitMatteSession(tmp_path)


@pytest.mark.integration
def test_real_cpu_vitmatte_native_pad_unpad_normalization():
    import os
    from pathlib import Path

    from blackmask import models

    cache = os.environ.get("BLACKMASK_VITMATTE_CACHE")
    if not cache:
        pytest.skip("Set BLACKMASK_VITMATTE_CACHE to explicitly installed pinned assets")
    session = models.VitMatteSession(Path(cache))
    rgb = np.zeros((65, 97, 3), dtype=np.uint8)
    rgb[10:50, 20:70] = [200, 100, 50]
    guide = np.full((65, 97), 128, dtype=np.uint8)
    guide[:3] = 0
    guide[-3:] = 255
    alpha, record = session.predict(rgb, guide, "cpu")
    assert alpha.shape == (65, 97) and np.isfinite(alpha).all()
    assert record["pixel_values_shape"] == [1, 4, 96, 128]
    assert record["output_shape"] == [1, 1, 96, 128]
    assert record["padding_ltrb"] == [0, 0, 31, 31]
    assert (
        record["dtype"] == "float32"
        and record["device"] == "cpu"
        and record["attention"] == "eager"
    )
    assert record["corner_tensor"] == [-1.0, -1.0, -1.0, 0.0]
    assert record["normalization"]["mean"] == [0.5, 0.5, 0.5]
    assert np.isclose(record["unknown_tensor"], 128 / 255)


def test_existing_empty_output_directory_is_never_replaced(tmp_path):
    from blackmask.project import ProjectError, _publish_new_directory

    source = tmp_path / "stage"
    source.mkdir()
    (source / "complete").write_text("saved")
    destination = tmp_path / "already-owned"
    destination.mkdir()
    with pytest.raises(ProjectError, match="collision|exists"):
        _publish_new_directory(source, destination)
    assert source.is_dir() and destination.is_dir() and not list(destination.iterdir())


def test_spatial_tile_registration_and_independent_sine_blend_sentinels():
    import math

    matte = engine()
    width, height = 1793, 7
    x = np.arange(width)
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = x % 256
    rgb[..., 1] = x // 256
    rgb[..., 2] = np.arange(height)[:, None]
    trimap = np.full((height, width), 128, dtype=np.uint8)
    seen = []

    def predict(crop, guide, device):
        origin = int(crop[0, 0, 0]) + 256 * int(crop[0, 0, 1])
        seen.append(origin)
        np.testing.assert_array_equal(crop, rgb[:, origin : origin + 1024])
        local_x = np.arange(1024)[None, :]
        row = np.arange(height)[:, None]
        return 0.2 + 0.0005 * local_x + 0.01 * row, {}

    alpha, record = matte.native_matte(rgb, trimap, predict, "cpu")
    assert seen == [0, 768, 769] and record["minimum_weight"] > 0
    for sample_x in [0, 100, 768, 769, 800, 900, 1000, 1023, 1024, 1200, 1536, 1700, 1791, 1792]:
        for sample_y in [0, 3, 6]:
            # Independent scalar cases for these three hand-derived tile bounds.
            operands = []
            if sample_x < 1024:
                weight = (
                    1.0
                    if sample_x < 768
                    else math.sin((1023 - sample_x + 0.5) / 256 * math.pi / 2) ** 2
                )
                operands.append((weight, 0.2 + 0.0005 * sample_x + 0.01 * sample_y))
            if 768 <= sample_x < 1792:
                local = sample_x - 768
                weight = 1.0
                if local < 256:
                    weight *= math.sin((local + 0.5) / 256 * math.pi / 2) ** 2
                if local >= 768:
                    weight *= math.sin((1023 - local + 0.5) / 256 * math.pi / 2) ** 2
                operands.append((weight, 0.2 + 0.0005 * local + 0.01 * sample_y))
            if sample_x >= 769:
                local = sample_x - 769
                weight = 1.0 if local >= 256 else math.sin((local + 0.5) / 256 * math.pi / 2) ** 2
                operands.append((weight, 0.2 + 0.0005 * local + 0.01 * sample_y))
            expected = round(sum(w * v for w, v in operands) / sum(w for w, _ in operands) * 65535)
            assert alpha[sample_y, sample_x] == expected, (sample_x, sample_y)


def test_finite_extremes_clamp_before_single_alpha16_quantization():
    rgb = np.zeros((1, 3, 3), dtype=np.uint8)
    guide = np.full((1, 3), 128, dtype=np.uint8)
    alpha, _ = engine().native_matte(
        rgb, guide, lambda *args: (np.array([[-0.25, 0.4, 1.25]]), {}), "cpu"
    )
    np.testing.assert_array_equal(alpha, [[0, 26214, 65535]])
