"""Native tiling and one quantization boundary, independent of model execution."""

import hashlib
import json
import os
import tempfile
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .models import run_device_stage

TILE_SIZE = 1024
OVERLAP = 256
STRIDE = TILE_SIZE - OVERLAP


def tile_origins(length: int) -> list[int]:
    if type(length) is not int or length < 1:
        raise ValueError("Native dimension must be positive")
    if length <= TILE_SIZE:
        return [0]
    origins = list(range(0, length - TILE_SIZE + 1, STRIDE))
    if origins[-1] != length - TILE_SIZE:
        origins.append(length - TILE_SIZE)
    return origins


def _axis_weights(length: int, origin: int, total: int) -> np.ndarray:
    weights = np.ones(length, dtype=np.float64)
    ramp_length = min(OVERLAP, length)
    ramp = np.sin((np.arange(ramp_length) + 0.5) / OVERLAP * np.pi / 2) ** 2
    if origin > 0:
        weights[:ramp_length] *= ramp
    if origin + length < total:
        weights[-ramp_length:] *= ramp[::-1]
    return weights


def _complete_cache_identity(identity: dict[str, Any] | None) -> bool:
    required = {
        "master_id",
        "model",
        "revision",
        "hashes",
        "packages",
        "preprocessing",
        "dtype",
        "attention",
    }
    if not isinstance(identity, dict) or not required <= identity.keys():
        return False
    hashes, packages = identity["hashes"], identity["packages"]
    return (
        all(
            isinstance(identity[name], str) and identity[name]
            for name in required - {"hashes", "packages"}
        )
        and isinstance(hashes, dict)
        and {"config.json", "preprocessor_config.json", "model.safetensors"} <= hashes.keys()
        and all(isinstance(value, str) and len(value) == 64 for value in hashes.values())
        and isinstance(packages, dict)
        and {"torch", "torchvision", "transformers", "safetensors", "numpy", "Pillow"}
        <= packages.keys()
        and all(isinstance(value, str) and value for value in packages.values())
    )


def _cache_generation(cache: Path, backend: str) -> str:
    from .project import _atomic_json, check_space

    if cache.resolve() != cache.absolute():
        raise ValueError("Unsafe matte cache path")
    cache.mkdir(parents=True, exist_ok=True)
    marker = cache / "backend.json"
    try:
        if marker.is_symlink():
            raise ValueError("Unsafe matte backend marker")
        record = json.loads(marker.read_bytes())
        if (
            set(record) == {"backend", "generation"}
            and record["backend"] == backend
            and isinstance(record["generation"], str)
            and len(record["generation"]) == 32
        ):
            return record["generation"]
    except (OSError, ValueError, TypeError):
        pass
    check_space(cache, 1024**2)
    generation = uuid.uuid4().hex
    _atomic_json(marker, {"backend": backend, "generation": generation})
    return generation


def native_matte(
    pixels: np.ndarray,
    trimap: np.ndarray,
    predict: Callable[[np.ndarray, np.ndarray, str], tuple[np.ndarray, dict[str, Any]]],
    device: str,
    *,
    auto_mps: bool = False,
    cache_dir: Path | None = None,
    cache_identity: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Retry the entire stage on device switch; never mix tile predictions across devices."""
    if (
        pixels.dtype != np.uint8
        or pixels.ndim != 3
        or pixels.shape[2] != 3
        or trimap.dtype != np.uint8
        or trimap.shape != pixels.shape[:2]
        or not np.isin(trimap, [0, 128, 255]).all()
    ):
        raise ValueError("Matting requires aligned RGB8 and categorical trimap")
    height, width = trimap.shape
    ys, xs = tile_origins(height), tile_origins(width)

    def stage(selected: str) -> tuple[np.ndarray, dict[str, Any]]:
        generation = (
            _cache_generation(cache_dir, selected)
            if cache_dir is not None and _complete_cache_identity(cache_identity)
            else None
        )
        accumulated = np.zeros(trimap.shape, dtype=np.float64)
        total_weight = np.zeros(trimap.shape, dtype=np.float64)
        records = []
        inferred = 0
        reused = 0
        for y in ys:
            for x in xs:
                h, w = min(TILE_SIZE, height - y), min(TILE_SIZE, width - x)
                guide = trimap[y : y + h, x : x + w]
                if np.any(guide == 128):
                    rgb = pixels[y : y + h, x : x + w]
                    key = hashlib.sha256(
                        json.dumps(
                            {
                                "identity": cache_identity,
                                "backend": selected,
                                "crop": [x, y, x + w, y + h],
                                "tile_size": TILE_SIZE,
                                "overlap": OVERLAP,
                                "version": 2,
                                "generation": generation,
                            },
                            sort_keys=True,
                        ).encode()
                        + rgb.tobytes()
                        + guide.tobytes()
                    ).hexdigest()
                    entry = (
                        cache_dir / f"{key}.npz"
                        if cache_dir is not None and generation is not None
                        else None
                    )
                    cached = None
                    if entry is not None and entry.is_file() and not entry.is_symlink():
                        try:
                            with np.load(entry, allow_pickle=False) as data:
                                candidate = data["alpha"]
                                metadata = json.loads(str(data["metadata"]))
                                expected = str(data["sha256"])
                                if (
                                    candidate.dtype in (np.dtype("float32"), np.dtype("float64"))
                                    and isinstance(metadata, dict)
                                    and str(data["key"]) == key
                                    and candidate.shape == guide.shape
                                    and np.isfinite(candidate).all()
                                    and hashlib.sha256(
                                        candidate.tobytes()
                                        + json.dumps(metadata, sort_keys=True).encode()
                                    ).hexdigest()
                                    == expected
                                ):
                                    cached = candidate.copy()
                        except (
                            OSError,
                            ValueError,
                            TypeError,
                            KeyError,
                            EOFError,
                            zipfile.BadZipFile,
                        ):
                            pass  # Rebuildable invalid cache is a miss, never an accepted dependency.
                    if cached is not None:
                        prediction = cached
                        metadata = dict(metadata, cache_reused=True)
                        reused += 1
                    else:
                        prediction, metadata = predict(rgb, guide, selected)
                        inferred += 1
                        if prediction.shape != guide.shape or not np.isfinite(prediction).all():
                            raise FloatingPointError("Non-finite or invalid native tile prediction")
                        if entry is not None:
                            from .project import check_space

                            if cache_dir is None or cache_dir.resolve() != cache_dir.absolute():
                                raise ValueError("Unsafe matte cache path")
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            check_space(cache_dir, prediction.nbytes * 2 + 1024**2)
                            descriptor, temporary = tempfile.mkstemp(prefix=".tile-", dir=cache_dir)
                            serialized = json.dumps(metadata, sort_keys=True)
                            checksum = hashlib.sha256(
                                prediction.tobytes() + serialized.encode()
                            ).hexdigest()
                            with os.fdopen(descriptor, "wb") as stream:
                                np.savez(
                                    stream,
                                    alpha=prediction,
                                    metadata=serialized,
                                    sha256=checksum,
                                    key=key,
                                )
                                stream.flush()
                                os.fsync(stream.fileno())
                            if not entry.exists():
                                os.link(temporary, entry, follow_symlinks=False)
                            # Invalid existing entries and verified temporaries retained; no destructive cleanup.
                else:
                    prediction, metadata = guide.astype(np.float64) / 255, {"bypassed": True}
                if prediction.shape != guide.shape or not np.isfinite(prediction).all():
                    raise FloatingPointError("Non-finite or invalid native tile prediction")
                prediction = np.clip(prediction, 0, 1)
                weight = _axis_weights(h, y, height)[:, None] * _axis_weights(w, x, width)[None, :]
                accumulated[y : y + h, x : x + w] += prediction * weight
                total_weight[y : y + h, x : x + w] += weight
                records.append({"crop_xyxy": [x, y, x + w, y + h], **metadata})
        if not np.isfinite(accumulated).all() or not np.all(total_weight > 0):
            raise FloatingPointError("Invalid matte coverage or accumulation")
        alpha = np.clip(accumulated / total_weight, 0, 1)
        alpha[trimap == 0] = 0
        alpha[trimap == 255] = 1
        return np.rint(alpha * 65535).astype(np.uint16), {
            "tile_size_px": TILE_SIZE,
            "overlap_px": OVERLAP,
            "stride_px": STRIDE,
            "origins_x": xs,
            "origins_y": ys,
            "tiles": records,
            "inferred_tiles": inferred,
            "reused_tiles": reused,
            "minimum_weight": float(total_weight.min()),
            "quantization": "once float64 ties-to-even",
        }

    (alpha, record), selected, fallback = run_device_stage(stage, device, auto_mps=auto_mps)
    return alpha, dict(record, device=selected, fallback=fallback)
