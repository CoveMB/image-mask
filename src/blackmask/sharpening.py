"""Bounded alpha-aware sharpening of captured linear luminance; no inference."""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter

from .assets import revision_asset
from .exposure import linear_to_rgb16, rasterize_effect_area, srgb_to_linear
from .project import ProjectError, _json_bytes, digest
from .repair import scalar16


def validate_local_sharpening(settings: Any) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "amount", "radius_px", "noise_threshold"}
        or type(settings.get("enabled")) is not bool
        or any(
            type(settings[name]) not in {int, float}
            or not lower <= settings[name] <= upper
            or not np.isfinite(settings[name])
            for name, lower, upper in (
                ("amount", 0, 1),
                ("radius_px", 0.5, 8),
                ("noise_threshold", 0, 0.02),
            )
        )
    ):
        raise ProjectError(
            "Local sharpening requires enabled boolean, finite amount [0,1], "
            "radius_px [0.5,8] and noise_threshold [0,0.02]"
        )


def apply_local_sharpening(
    foreground: np.ndarray,
    alpha: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    settings: dict[str, Any],
) -> np.ndarray:
    """Filter full-width strips with native halos; copy every excluded sample exactly.

    Alpha weights neighbourhood evidence, never write strength. A shared RGB gain
    preserves linear chromaticity and limits gamut without channel-wise clipping.
    """
    validate_local_sharpening(settings)
    if (
        foreground.dtype != np.uint16
        or foreground.ndim != 3
        or foreground.shape[2] != 3
        or alpha.dtype != np.uint16
        or alpha.shape != foreground.shape[:2]
        or support.dtype != np.uint16
        or support.shape != alpha.shape
        or protection.dtype != np.bool_
        or protection.shape != alpha.shape
    ):
        raise ProjectError(
            "Local sharpening requires aligned RGB16/A16/support16 and boolean protection"
        )
    result = foreground.copy()
    if not settings["enabled"] or settings["amount"] == 0:
        return result
    height, width = alpha.shape
    halo = math.ceil(4 * settings["radius_px"])
    # Bound scratch buffers in rows; full-width context avoids column seams.
    strip_rows = max(1, min(128, 262144 // max(1, width)))
    for top in range(0, height, strip_rows):
        bottom = min(height, top + strip_rows)
        eligible = (alpha[top:bottom] != 0) & (support[top:bottom] != 0) & ~protection[top:bottom]
        if not eligible.any():
            continue
        start, stop = max(0, top - halo), min(height, bottom + halo)
        core = slice(top - start, bottom - start)
        linear = srgb_to_linear(foreground[start:stop].astype(np.float64) / 65535)
        luminance = linear[:, :, 0] * 0.2126 + linear[:, :, 1] * 0.7152 + linear[:, :, 2] * 0.0722
        weights = alpha[start:stop].astype(np.float64) / 65535
        denominator = gaussian_filter(
            weights, settings["radius_px"], radius=halo, mode="reflect", output=np.float64
        )[core]
        numerator = gaussian_filter(
            luminance * weights,
            settings["radius_px"],
            radius=halo,
            mode="reflect",
            output=np.float64,
        )[core]
        original = luminance[core]
        mean = np.divide(numerator, denominator, out=original.copy(), where=denominator != 0)
        detail = original - mean
        detail = np.sign(detail) * np.maximum(np.abs(detail) - settings["noise_threshold"], 0)
        candidate = original + detail * settings["amount"] * support[top:bottom] / 65535
        minimum = minimum_filter(np.where(weights != 0, luminance, np.inf), size=3, mode="reflect")[
            core
        ]
        maximum = maximum_filter(
            np.where(weights != 0, luminance, -np.inf), size=3, mode="reflect"
        )[core]
        candidate = np.minimum(np.maximum(candidate, minimum), maximum)
        changed = eligible & (denominator != 0) & (original > 0) & (candidate != original)
        if not changed.any():
            continue
        pixels = linear[core][changed]
        gain = np.minimum(candidate[changed] / original[changed], 1 / pixels.max(axis=1))
        values = foreground[top:bottom][changed].copy()
        adjusted = gain != 1
        values[adjusted] = linear_to_rgb16(pixels[adjusted] * gain[adjusted, None])
        result[top:bottom][changed] = values
    return result


SHARPENING_FILES = ("support16.png", "protection16.png", "alpha16.png", "settings.json")


def read_local_sharpening(
    project: Path, directory: Path, manifest: dict[str, Any], alpha: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None:
    """Validate immutable operands even when disabled; absence is the legacy OFF state."""
    if "local_sharpening" not in manifest:
        return None
    record = manifest["local_sharpening"]
    keys = {
        "schema_version",
        "enabled",
        "settings",
        "stale",
        "developed_id",
        "algorithm",
        "alpha_sha256",
        "support_sha256",
        "protection_sha256",
        "area_sha256",
        "candidate_comparison",
        "scope_xyxy",
    }
    if (
        not isinstance(record, dict)
        or set(record) != keys
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 2
        or type(record["enabled"]) is not bool
        or type(record["stale"]) is not bool
        or type(record["candidate_comparison"]) is not bool
        or record["developed_id"] != manifest["developed_id"]
        or record["algorithm"] != "linear-srgb-local-sharpening-v1"
    ):
        raise ProjectError("Invalid saved Local sharpening identity/schema/status")
    validate_local_sharpening(record["settings"])
    if record["enabled"] != record["settings"]["enabled"]:
        raise ProjectError("Inconsistent saved Local sharpening settings")
    from .guidance import coordinates

    height, width = alpha.shape
    coordinates(record["scope_xyxy"], width, height, box=True)
    saved = directory / "effects/sharpening"
    try:
        saved_record = _json_bytes(
            json.loads(
                revision_asset(
                    project, directory, manifest, "effects/sharpening/settings.json"
                ).read_bytes()
            )
        )
    except (TypeError, ValueError) as error:
        raise ProjectError("Invalid saved Local sharpening settings record") from error
    # Python equality treats Boolean values as numeric aliases; JSON preserves their types.
    if saved_record != _json_bytes(record):
        raise ProjectError("Inconsistent saved Local sharpening settings record")
    arrays = []
    for name, key in (
        ("support16.png", "support_sha256"),
        ("protection16.png", "protection_sha256"),
        ("alpha16.png", "alpha_sha256"),
    ):
        path = revision_asset(project, directory, manifest, "effects/sharpening/" + name)
        if digest(path.read_bytes()) != record[key]:
            raise ProjectError("Saved Local sharpening dependency hash mismatch")
        value = scalar16(path)
        if value.shape != alpha.shape:
            raise ProjectError("Saved Local sharpening dimensions differ from master")
        arrays.append(value)
    support, protection, dependency = arrays
    if not np.isin(protection, [0, 65535]).all() or record["stale"] != bool(
        record["enabled"] and not np.array_equal(dependency, alpha)
    ):
        raise ProjectError("Invalid saved Local sharpening protection/dependency status")
    if record["area_sha256"] is not None:
        path = revision_asset(project, directory, manifest, "effects/sharpening/area.json")
        if digest(path.read_bytes()) != record["area_sha256"]:
            raise ProjectError("Saved Local sharpening authored area hash mismatch")
        authored_support, authored_protection = rasterize_effect_area(
            json.loads(path.read_bytes()), manifest["developed_id"], width, height
        )
        if not np.array_equal(authored_support, support) or np.any(
            authored_protection & (protection == 0)
        ):
            raise ProjectError("Saved Local sharpening area differs from registered operands")
    elif (saved / "area.json").exists():
        raise ProjectError("Unbound saved Local sharpening authored area")
    return support, protection != 0, record


def selected_local_sharpening(
    project: Path,
    directory: Path,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    sharpening_off: bool = False,
) -> np.ndarray:
    saved = read_local_sharpening(project, directory, manifest, alpha)
    if saved is None:
        return foreground
    support, protection, record = saved
    settings = dict(record["settings"])
    if sharpening_off or record["stale"]:
        settings["enabled"] = False
    return apply_local_sharpening(foreground, alpha, support, protection, settings)
