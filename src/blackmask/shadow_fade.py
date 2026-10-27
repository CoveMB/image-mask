"""Reversible linear-sRGB subject fading from immutable foreground operands."""

import json
from pathlib import Path
from typing import Any

import numpy as np

from .assets import revision_asset
from .exposure import highlight_weight, linear_to_rgb16, rasterize_effect_area, srgb_to_linear
from .fade_reduction import read_fade_reduction
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
    reduction16: np.ndarray | None = None,
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
    if reduction16 is not None and (
        not isinstance(reduction16, np.ndarray)
        or reduction16.dtype != np.uint16
        or reduction16.shape != alpha.shape
    ):
        raise ProjectError("Shadow fade reduction requires aligned uint16 samples")
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
    if reduction16 is not None and reduction16.any():
        weight *= 1 - reduction16[eligible].astype(np.float64) / 65535
    changed = weight != 0
    values = foreground[eligible].copy()
    values[changed] = linear_to_rgb16(
        linear[changed] * np.exp2(-6 * settings["amount"] * weight[changed])[:, None]
    )
    result[eligible] = values
    return result


SHADOW_FADE_FILES = ("support16.png", "protection16.png", "alpha16.png", "settings.json")


def shadow_fade_files(record: dict[str, Any]) -> tuple[str, ...]:
    """Select the exact inventory of the immutable saved record."""
    if (
        not isinstance(record, dict)
        or type(record.get("schema_version")) is not int
        or record["schema_version"] not in (2, 3)
    ):
        raise ProjectError("Invalid saved Shadow fade identity/schema/status")
    files: tuple[str, ...] = SHADOW_FADE_FILES
    if record.get("area_sha256") is not None:
        files += ("area.json",)
    if record["schema_version"] == 3:
        files += ("reduction16.png", "reduction.json")
    return files


def validate_shadow_fade_bindings(project: Path, directory: Path, manifest: dict[str, Any]) -> None:
    """Reject unbound and extra operands before any cached semantic validation."""
    from .assets import revision_hashes

    prefix = "effects/shadow-fade/"
    saved = directory / prefix
    listed = {name for name in revision_hashes(manifest) if name.startswith(prefix)}
    if "shadow_fade" not in manifest:
        if saved.exists() or saved.is_symlink() or listed:
            raise ProjectError("Unbound saved Shadow fade operands")
        return
    required = {prefix + name for name in shadow_fade_files(manifest["shadow_fade"])}
    if listed != required or "base_alpha16.png" not in revision_hashes(manifest):
        raise ProjectError("Incomplete Shadow fade assets or extra bound operands")
    try:
        if (
            saved.is_symlink()
            or {path.name for path in saved.iterdir()}
            != {Path(name).name for name in manifest.get("files", {}) if name.startswith(prefix)}
            or any(path.is_symlink() or not path.is_file() for path in saved.iterdir())
        ):
            raise ProjectError("Invalid saved Shadow fade inventory")
    except OSError as error:
        raise ProjectError("Missing saved Shadow fade operands") from error


def read_shadow_fade(
    project: Path, directory: Path, manifest: dict[str, Any], alpha: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None:
    """Validate immutable operands even when disabled; absence is the legacy OFF state."""
    if "shadow_fade" not in manifest:
        return None
    record = manifest["shadow_fade"]
    shadow_fade_files(record)
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
    if record.get("schema_version") == 3:
        keys |= {"reduction_sha256", "reduction_area_sha256", "reduction_algorithm"}
    if (
        not isinstance(record, dict)
        or set(record) != keys
        or type(record["schema_version"]) is not int
        or record["schema_version"] not in (2, 3)
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
    read_fade_reduction(project, directory, manifest, "shadow_fade", alpha)
    return support, protection != 0, record


def selected_shadow_fade(
    project: Path,
    directory: Path,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    shadow_fade_off: bool = False,
    shadow_reduction_off: bool = False,
) -> np.ndarray:
    saved = read_shadow_fade(project, directory, manifest, alpha)
    if saved is None:
        return foreground
    support, protection, record = saved
    settings = dict(record["settings"])
    if shadow_fade_off or record["stale"]:
        settings["enabled"] = False
    reduction = (
        None
        if shadow_reduction_off
        else read_fade_reduction(project, directory, manifest, "shadow_fade", alpha)
    )
    return apply_shadow_fade(foreground, alpha, support, protection, settings, reduction)
