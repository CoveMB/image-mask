"""Bounded band-pass contrast on captured, straight RGB16 foreground."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, maximum_filter

from .assets import inherit_revision_files, revision_asset, stage_asset
from .exposure import highlight_weight, linear_to_rgb16, rasterize_effect_area, srgb_to_linear
from .guidance import coordinates
from .project import ProjectError, _json_bytes, digest
from .repair import scalar16

TEXTURE_ALGORITHM = "linear-srgb-local-texture-v1"
TEXTURE_PREFIX = "effects/texture/"
TEXTURE_RASTERS = {
    "support16.png": "support_sha256",
    "protection16.png": "protection_sha256",
    "alpha16.png": "alpha_sha256",
}
TEXTURE_TEXT = ("area.json", "settings.json")
TEXTURE_DEFAULTS = {
    "enabled": False,
    "strength": 0.0,
    "scale_px": 4.0,
    "grain_guard": 0.0005,
    "preserve_highlights": 1.0,
}


def validate_local_texture(settings: object) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != TEXTURE_DEFAULTS.keys()
        or type(settings["enabled"]) is not bool
        or any(
            type(settings[name]) not in (int, float) or not low <= settings[name] <= high
            for name, low, high in (
                ("strength", 0, 1),
                ("scale_px", 2, 16),
                ("grain_guard", 0, 0.02),
                ("preserve_highlights", 0, 1),
            )
        )
    ):
        raise ProjectError(
            "Local texture requires enabled boolean, strength [0,1], scale_px [2,16], "
            "grain_guard [0,0.02] and preserve_highlights [0,1]"
        )


def _alpha_mean(luminance: np.ndarray, alpha: np.ndarray, sigma: float, core: slice) -> np.ndarray:
    radius = math.ceil(4 * sigma)
    denominator = gaussian_filter(alpha, sigma, radius=radius, mode="reflect")[core]
    numerator = gaussian_filter(luminance * alpha, sigma, radius=radius, mode="reflect")[core]
    return np.divide(numerator, denominator, out=luminance[core].copy(), where=denominator > 0)


def _edge_taper(luminance: np.ndarray, alpha: np.ndarray, radius: int, core: slice) -> np.ndarray:
    # Two-pixel axial differences distinguish sharp transitions from faint bands.
    # A near-transparent outlier must not turn off detail in its whole neighborhood.
    scores = np.zeros_like(luminance)
    for padding, (first, second) in (
        (((1, 1), (0, 0)), (np.s_[:-2, :], np.s_[2:, :])),
        (((0, 0), (1, 1)), (np.s_[:, :-2], np.s_[:, 2:])),
    ):
        values = np.pad(luminance, padding, mode="symmetric")
        coverage = np.pad(alpha, padding, mode="symmetric")
        contrast = np.abs(values[first] - values[second]) / np.maximum(
            values[first] + values[second], 0.05
        )
        confidence = np.minimum(1, 4 * np.minimum(coverage[first], coverage[second]))
        np.maximum(scores, contrast * confidence, out=scores)
    nearby = maximum_filter(scores, size=2 * radius + 1, mode="reflect")[core]
    transition = np.clip((nearby - 0.08) / 0.10, 0, 1)
    return 1 - transition * transition * (3 - 2 * transition)


def apply_local_texture(
    foreground: np.ndarray,
    alpha: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    settings: dict[str, Any],
) -> np.ndarray:
    """Change eligible RGB only. Alpha supplies context, never write strength."""
    validate_local_texture(settings)
    if (
        not all(isinstance(array, np.ndarray) for array in (foreground, alpha, support, protection))
        or foreground.dtype != np.uint16
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
            "Local texture requires aligned RGB16/A16/support16 and boolean protection"
        )

    result = foreground.copy()
    if not settings["enabled"] or settings["strength"] == 0:
        return result
    height, width = alpha.shape
    scale = settings["scale_px"]
    radius = math.ceil(4 * scale)
    halo = radius + 1  # The edge maximum also reads a one-pixel difference halo.
    black_limit, white_limit = srgb_to_linear(np.array([1, 65534], np.float64) / 65535)
    strip_rows = max(1, min(128, 262144 // max(1, width)))
    for top in range(0, height, strip_rows):
        bottom = min(height, top + strip_rows)
        rows = slice(top, bottom)
        eligible = (alpha[rows] != 0) & (support[rows] != 0) & ~protection[rows]
        if not eligible.any():
            continue
        start, stop = max(0, top - halo), min(height, bottom + halo)
        core = slice(top - start, bottom - start)
        linear = srgb_to_linear(foreground[start:stop].astype(np.float64) / 65535)
        luminance = linear[..., 0] * 0.2126 + linear[..., 1] * 0.7152 + linear[..., 2] * 0.0722
        coverage = alpha[start:stop].astype(np.float64) / 65535
        band = _alpha_mean(luminance, coverage, scale / 2, core) - _alpha_mean(
            luminance, coverage, scale, core
        )
        band = np.sign(band) * np.maximum(np.abs(band) - settings["grain_guard"], 0)
        changed = eligible & (luminance[core] > 0) & (band != 0)
        if not changed.any():
            continue
        pixels = linear[core][changed]
        edge = _edge_taper(luminance, coverage, radius, core)[changed]
        highlights = 1 - settings["preserve_highlights"] * highlight_weight(pixels)
        gain = (
            1 + settings["strength"] * band[changed] * edge * highlights / luminance[core][changed]
        )
        # Positive gains respect the brightest channel, including already saturated samples.
        # Negative gains leave every positive channel at or above the first nonzero code.
        lower = black_limit / np.min(np.where(pixels > 0, pixels, np.inf), axis=1)
        upper = np.maximum(1, white_limit / pixels.max(axis=1))
        gain = 1 + (support[rows][changed] / 65535) * (np.clip(gain, lower, upper) - 1)
        varies = gain != 1
        vertical, horizontal = np.nonzero(changed)
        result[rows][vertical[varies], horizontal[varies]] = linear_to_rgb16(
            pixels[varies] * gain[varies, None]
        )
    return result


def parse_texture_json(raw: bytes) -> Any:
    """Keep duplicate fields or nonfinite constants from disappearing at a raw boundary."""

    def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ProjectError("Duplicate Local texture JSON field")
        return result

    def reject_constant(value: str) -> None:
        raise ProjectError("Nonfinite Local texture JSON value")

    try:
        return json.loads(raw, object_pairs_hook=unique_fields, parse_constant=reject_constant)
    except (UnicodeError, RecursionError) as error:
        raise ProjectError("Invalid Local texture JSON") from error


def check_texture_scope(support: np.ndarray, scope: list[int]) -> None:
    x0, y0, x1, y1 = scope
    if any(
        section.any()
        for section in (support[:y0], support[y1:], support[y0:y1, :x0], support[y0:y1, x1:])
    ):
        raise ProjectError("Local texture scope must contain previous and replacement support")


@dataclass(frozen=True)
class TextureOperands:
    support: np.ndarray
    protection: np.ndarray
    dependency: np.ndarray
    record: dict[str, Any]


def read_local_texture(
    project: Path,
    directory: Path,
    manifest: dict[str, Any],
    alpha: np.ndarray,
    *,
    verify_geometry: bool = True,
) -> TextureOperands | None:
    if "local_texture" not in manifest:
        return None
    record = manifest["local_texture"]
    if (
        not isinstance(record, dict)
        or set(record)
        != {
            "schema_version",
            "enabled",
            "settings",
            "stale",
            "developed_id",
            "algorithm",
            "scope_xyxy",
            "candidate_comparison",
            "area_sha256",
            *TEXTURE_RASTERS.values(),
        }
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 2
        or record["algorithm"] != TEXTURE_ALGORITHM
        or record["developed_id"] != manifest["developed_id"]
        or any(
            type(record[key]) is not bool for key in ("enabled", "stale", "candidate_comparison")
        )
    ):
        raise ProjectError("Invalid saved Local texture identity/schema/status")
    validate_local_texture(record["settings"])
    height, width = alpha.shape
    scope = coordinates(record["scope_xyxy"], width, height, box=True)

    def operand(name: str) -> Path:
        return revision_asset(project, directory, manifest, TEXTURE_PREFIX + name)

    if record["enabled"] != record["settings"]["enabled"] or _json_bytes(
        parse_texture_json(operand("settings.json").read_bytes())
    ) != _json_bytes(record):
        raise ProjectError("Inconsistent saved Local texture settings")
    area_bytes = operand("area.json").read_bytes()
    if digest(area_bytes) != record["area_sha256"]:
        raise ProjectError("Saved Local texture area hash mismatch")
    rasters = []
    for name, key in TEXTURE_RASTERS.items():
        path = operand(name)
        if digest(path.read_bytes()) != record[key]:
            raise ProjectError("Saved Local texture operand hash mismatch")
        raster = scalar16(path)
        if raster.shape != alpha.shape:
            raise ProjectError("Saved Local texture raster differs from master dimensions")
        rasters.append(raster)
    support, protection16, dependency = rasters
    if np.any((protection16 != 0) & (protection16 != 65535)) or record["stale"] != (
        record["enabled"] and not np.array_equal(dependency, alpha)
    ):
        raise ProjectError("Invalid saved Local texture protection/dependency status")
    protection = protection16 != 0
    check_texture_scope(support, scope)
    if verify_geometry:
        authored_support, authored_protection = rasterize_effect_area(
            parse_texture_json(area_bytes), manifest["developed_id"], width, height
        )
        if not np.array_equal(authored_support, support) or np.any(
            authored_protection & ~protection
        ):
            raise ProjectError("Saved Local texture area differs from registered operands")
    return TextureOperands(support, protection, dependency, record)


def inherit_local_texture(
    project: Path,
    parent: str,
    stage: Path,
    manifest: dict[str, Any],
    assets: dict[str, Any],
    *,
    alpha: np.ndarray | None = None,
    rgb_protection: np.ndarray | None = None,
) -> dict[str, Any] | None:
    previous = manifest.get("local_texture")
    if previous is None:
        return None
    record = dict(previous)
    inherit_revision_files(
        project,
        parent,
        stage,
        assets,
        [TEXTURE_PREFIX + name for name in (*TEXTURE_RASTERS, *TEXTURE_TEXT)],
    )
    if alpha is not None:
        dependency = scalar16(stage_asset(project, stage, assets, TEXTURE_PREFIX + "alpha16.png"))
        record["stale"] = bool(record["enabled"] and not np.array_equal(dependency, alpha))
    if rgb_protection is not None and rgb_protection.any():
        name = TEXTURE_PREFIX + "protection16.png"
        protection = scalar16(stage_asset(project, stage, assets, name))
        if np.any(protection[rgb_protection] == 0):
            protection[rgb_protection] = 65535
            Image.fromarray(protection).save(stage / name)
            record["protection_sha256"] = digest((stage / name).read_bytes())
    if record != previous:
        (stage / TEXTURE_PREFIX / "settings.json").write_bytes(_json_bytes(record))
    return record
