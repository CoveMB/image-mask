from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from blackmask import models


def test_missing_or_corrupt_model_fails_without_network(tmp_path):
    with (
        patch("urllib.request.urlopen", side_effect=AssertionError("hidden download")),
        pytest.raises(ValueError, match="setup|missing|hash"),
    ):
        models.SamSession(tmp_path)


def test_explicit_mps_failure_visible_and_auto_retries_same_geometry():
    pixels = np.zeros((13, 17, 3), dtype=np.uint8)
    calls = []

    def stage(device):
        calls.append((device, pixels.shape))
        if device == "mps":
            raise RuntimeError("unsupported")
        return "cpu-result"

    with pytest.raises(ValueError, match="MPS|mps"):
        models.run_device_stage(stage, "mps", auto_mps=True)
    assert calls == [("mps", (13, 17, 3))]
    calls.clear()
    result, device, fallback = models.run_device_stage(stage, "auto", auto_mps=True)
    assert result == "cpu-result" and device == "cpu" and fallback == "unsupported"
    assert calls == [("mps", (13, 17, 3)), ("cpu", (13, 17, 3))]


@pytest.mark.integration
def test_real_cpu_sam_geometry_normalization_and_native_candidates():
    import os

    cache = os.environ.get("BLACKMASK_SAM_CACHE")
    if not cache:
        pytest.skip("Set BLACKMASK_SAM_CACHE to explicitly installed pinned assets")
    session = models.SamSession(Path(cache))
    pixels = np.zeros((65, 97, 3), dtype=np.uint8)
    pixels[10:50, 20:70] = [200, 100, 50]
    result = session.select(pixels, [[40, 30]], [1], None, "cpu", master_id="a" * 64)
    assert result.masks.shape == (3, 65, 97) and result.masks.dtype == np.bool_
    assert np.isfinite(result.scores).all()
    record = result.metadata
    assert record["pixel_values_shape"] == [1, 3, 1024, 1024]
    assert record["dtype"] == "float32" and record["device"] == "cpu"
    assert np.allclose(record["input_points_tensor"][0][0][0], [422.268036, 472.615387], atol=1e-4)
    assert record["attention"] == "eager"
    assert record["normalization"]["mean"] == [0.485, 0.456, 0.406]
    assert record["normalization"]["std"] == [0.229, 0.224, 0.225]
    assert np.allclose(
        record["corner_tensor"], [-0.485 / 0.229, -0.456 / 0.224, -0.406 / 0.225], atol=1e-5
    )
    second = session.select(pixels, [[45, 32]], [1], [20, 10, 70, 50], "cpu", master_id="a" * 64)
    assert second.metadata["embedding_reused"] is True
    assert second.masks.shape == (3, 65, 97)

    changed = session.select(pixels, [[45, 32]], [1], None, "cpu", master_id="b" * 64)
    assert changed.metadata["embedding_reused"] is False


@pytest.mark.integration
def test_existing_vitmatte_setup_reuse_has_no_network():
    import os

    cache = os.environ.get("BLACKMASK_VITMATTE_CACHE")
    if not cache:
        pytest.skip("Set explicitly installed ViTMatte cache")
    with patch("urllib.request.urlopen", side_effect=AssertionError("unexpected download")):
        assert models.setup_vitmatte(Path(cache)) == models.VITMATTE_FILES
