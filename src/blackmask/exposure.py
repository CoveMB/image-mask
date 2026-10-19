"""Independent native selection and linear-sRGB local exposure; no inference."""

import json
from pathlib import Path
from typing import Any

import numpy as np

from .guidance import rasterize_regions, validate_guides
from .project import ProjectError, digest
from .repair import scalar16


def validate_exposure(settings: Any) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "ev"}
        or type(settings.get("enabled")) is not bool
        or type(settings.get("ev")) not in {int, float}
        or not -3 <= settings["ev"] <= 3
        or not np.isfinite(settings["ev"])
    ):
        raise ProjectError("Local exposure requires enabled boolean and finite EV in [-3,3]")


def apply_exposure(
    foreground: np.ndarray,
    alpha: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    settings: dict[str, Any],
) -> tuple[np.ndarray, dict[str, int]]:
    """Gain uses area alone, never alpha; excluded RGB stays bit-exact."""
    validate_exposure(settings)
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
            "Local exposure requires aligned RGB16/A16/support16 and boolean protection"
        )
    eligible = (support != 0) & (alpha != 0) & ~protection
    counts = {"clipped_pixels": 0, "eligible_pixels": int(eligible.sum())}
    result = foreground.copy()
    if not settings["enabled"] or settings["ev"] == 0 or not eligible.any():
        return result, counts
    encoded = foreground[eligible].astype(np.float64) / 65535
    linear = np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)
    linear *= np.exp2(settings["ev"] * support[eligible].astype(np.float64) / 65535)[:, None]
    counts["clipped_pixels"] = int(np.any(linear > 1, axis=1).sum())
    linear = np.clip(linear, 0, 1)
    encoded = np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - 0.055)
    result[eligible] = np.rint(np.clip(encoded, 0, 1) * 65535).astype(np.uint16)
    return result, counts


def rasterize_exposure_area(
    area: dict[str, Any], master_id: str, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    """Reuse canonical native geometry without changing any matting guides."""
    if (
        not isinstance(area, dict)
        or set(area) != {"regions", "protection"}
        or any(not isinstance(area[name], list) for name in ("regions", "protection"))
    ):
        raise ProjectError("Exposure area requires regions and protection lists")
    guides = {
        "schema_version": 1,
        "master_id": master_id,
        "width": width,
        "height": height,
        "regions": area["regions"] + area["protection"],
    }
    validate_guides(guides, master_id, width, height)
    if any(region["role"] != "support" for region in guides["regions"]) or any(
        region["feather_px"] != 0 for region in area["protection"]
    ):
        raise ProjectError("Exposure uses support shapes; protection must have zero feather")
    support = rasterize_regions(dict(guides, regions=area["regions"])).support16
    protection = rasterize_regions(dict(guides, regions=area["protection"])).support16 != 0
    return support, protection


EXPOSURE_FILES = ("support16.png", "protection16.png", "alpha16.png", "settings.json")


def read_exposure(
    directory: Path, manifest: dict[str, Any], alpha: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None:
    """Validate immutable operands even when disabled; absence is the legacy OFF state."""
    record = manifest.get("local_exposure")
    if record is None:
        return None
    keys = {
        "schema_version",
        "enabled",
        "settings",
        "stale",
        "source_id",
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
        or record["schema_version"] != 1
        or type(record["enabled"]) is not bool
        or type(record["stale"]) is not bool
        or type(record["candidate_comparison"]) is not bool
        or record["source_id"] != manifest["master_id"]
        or record["algorithm"] != "linear-srgb-local-exposure-v1"
    ):
        raise ProjectError("Invalid saved local exposure identity/schema/status")
    validate_exposure(record["settings"])
    if record["enabled"] != record["settings"]["enabled"]:
        raise ProjectError("Inconsistent saved local exposure settings")
    from .guidance import coordinates

    height, width = alpha.shape
    coordinates(record["scope_xyxy"], width, height, box=True)
    saved = directory / "effects/exposure"
    if json.loads((saved / "settings.json").read_bytes()) != record:
        raise ProjectError("Inconsistent saved local exposure settings record")
    arrays = []
    for name, key in (
        ("support16.png", "support_sha256"),
        ("protection16.png", "protection_sha256"),
        ("alpha16.png", "alpha_sha256"),
    ):
        path = saved / name
        if digest(path.read_bytes()) != record[key]:
            raise ProjectError("Saved local exposure dependency hash mismatch")
        value = scalar16(path)
        if value.shape != alpha.shape:
            raise ProjectError("Saved local exposure dimensions differ from master")
        arrays.append(value)
    support, protection, dependency = arrays
    if not np.isin(protection, [0, 65535]).all() or record["stale"] != bool(
        record["enabled"] and not np.array_equal(dependency, alpha)
    ):
        raise ProjectError("Invalid saved local exposure protection/dependency status")
    if record["area_sha256"] is not None:
        path = saved / "area.json"
        if digest(path.read_bytes()) != record["area_sha256"]:
            raise ProjectError("Saved local exposure authored area hash mismatch")
        authored_support, authored_protection = rasterize_exposure_area(
            json.loads(path.read_bytes()), manifest["master_id"], width, height
        )
        if not np.array_equal(authored_support, support) or np.any(
            authored_protection & (protection == 0)
        ):
            raise ProjectError("Saved local exposure area differs from registered operands")
    elif (saved / "area.json").exists():
        raise ProjectError("Unbound saved local exposure authored area")
    return support, protection != 0, record


def selected_exposure(
    directory: Path,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    exposure_off: bool = False,
) -> tuple[np.ndarray, dict[str, int]]:
    saved = read_exposure(directory, manifest, alpha)
    if saved is None:
        return foreground, {"clipped_pixels": 0, "eligible_pixels": 0}
    support, protection, record = saved
    settings = dict(record["settings"])
    if exposure_off or record["stale"]:
        settings["enabled"] = False
    return apply_exposure(foreground, alpha, support, protection, settings)
