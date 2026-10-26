"""Reversible linear-sRGB subject fading from immutable foreground operands."""

import json
from pathlib import Path
from typing import Any

import numpy as np

from .assets import revision_asset
from .exposure import highlight_weight, linear_to_rgb16, rasterize_effect_area, srgb_to_linear
from .project import ProjectError, digest
from .repair import scalar16


def validate_shadow_fade(settings: Any) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "amount", "preserve_highlights"}
        or type(settings.get("enabled")) is not bool
        or any(
            type(settings[name]) not in {int, float}
            or not 0 <= settings[name] <= 1
            or not np.isfinite(settings[name])
            for name in ("amount", "preserve_highlights")
        )
    ):
        raise ProjectError(
            "Shadow fade requires enabled boolean and finite amount/preserve highlights in [0,1]"
        )


def apply_shadow_fade(
    foreground: np.ndarray,
    alpha: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    settings: dict[str, Any],
) -> np.ndarray:
    """Alpha gates eligibility only; excluded and zero-weight RGB are copied exactly."""
    validate_shadow_fade(settings)
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
            "Shadow fade requires aligned RGB16/A16/support16 and boolean protection"
        )
    result = foreground.copy()
    eligible = (alpha != 0) & (support != 0) & ~protection
    if not settings["enabled"] or settings["amount"] == 0 or not eligible.any():
        return result
    linear = srgb_to_linear(foreground[eligible].astype(np.float64) / 65535)
    highlights = highlight_weight(linear)
    weight = (
        support[eligible].astype(np.float64)
        / 65535
        * (1 - settings["preserve_highlights"] * highlights)
    )
    changed = weight != 0
    values = foreground[eligible].copy()
    values[changed] = linear_to_rgb16(
        linear[changed] * np.exp2(-6 * settings["amount"] * weight[changed])[:, None]
    )
    result[eligible] = values
    return result


SHADOW_FADE_FILES = ("support16.png", "protection16.png", "alpha16.png", "settings.json")


def read_shadow_fade(
    project: Path, directory: Path, manifest: dict[str, Any], alpha: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None:
    """Validate immutable operands even when disabled; absence is the legacy OFF state."""
    if "shadow_fade" not in manifest:
        return None
    record = manifest["shadow_fade"]
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
        or record["algorithm"] != "linear-srgb-shadow-fade-v1"
    ):
        raise ProjectError("Invalid saved Shadow fade identity/schema/status")
    validate_shadow_fade(record["settings"])
    if record["enabled"] != record["settings"]["enabled"]:
        raise ProjectError("Inconsistent saved Shadow fade settings")
    from .guidance import coordinates

    height, width = alpha.shape
    coordinates(record["scope_xyxy"], width, height, box=True)
    saved = directory / "effects/shadow-fade"
    if (
        json.loads(
            revision_asset(
                project, directory, manifest, "effects/shadow-fade/settings.json"
            ).read_bytes()
        )
        != record
    ):
        raise ProjectError("Inconsistent saved Shadow fade settings record")
    arrays = []
    for name, key in (
        ("support16.png", "support_sha256"),
        ("protection16.png", "protection_sha256"),
        ("alpha16.png", "alpha_sha256"),
    ):
        path = revision_asset(project, directory, manifest, "effects/shadow-fade/" + name)
        if digest(path.read_bytes()) != record[key]:
            raise ProjectError("Saved Shadow fade dependency hash mismatch")
        value = scalar16(path)
        if value.shape != alpha.shape:
            raise ProjectError("Saved Shadow fade dimensions differ from master")
        arrays.append(value)
    support, protection, dependency = arrays
    if not np.isin(protection, [0, 65535]).all() or record["stale"] != bool(
        record["enabled"] and not np.array_equal(dependency, alpha)
    ):
        raise ProjectError("Invalid saved Shadow fade protection/dependency status")
    if record["area_sha256"] is not None:
        path = revision_asset(project, directory, manifest, "effects/shadow-fade/area.json")
        if digest(path.read_bytes()) != record["area_sha256"]:
            raise ProjectError("Saved Shadow fade authored area hash mismatch")
        authored_support, authored_protection = rasterize_effect_area(
            json.loads(path.read_bytes()), manifest["developed_id"], width, height
        )
        if not np.array_equal(authored_support, support) or np.any(
            authored_protection & (protection == 0)
        ):
            raise ProjectError("Saved Shadow fade area differs from registered operands")
    elif (saved / "area.json").exists():
        raise ProjectError("Unbound saved Shadow fade authored area")
    return support, protection != 0, record


def selected_shadow_fade(
    project: Path,
    directory: Path,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    shadow_fade_off: bool = False,
) -> np.ndarray:
    saved = read_shadow_fade(project, directory, manifest, alpha)
    if saved is None:
        return foreground
    support, protection, record = saved
    settings = dict(record["settings"])
    if shadow_fade_off or record["stale"]:
        settings["enabled"] = False
    return apply_shadow_fade(foreground, alpha, support, protection, settings)
