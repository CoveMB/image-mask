"""Native oval/arc geometry and one linear-sRGB blend toward the selected background."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np

from .exposure import highlight_weight, linear_to_srgb, srgb_to_linear
from .project import ProjectError, digest
from .repair import scalar16

SPATIAL_FADE_FILES = ("weight16.png", "protection16.png", "alpha16.png", "settings.json")
SPATIAL_FADE_ALGORITHM = "linear-srgb-oval-arcs-background-fade-v1"


def _number(value: Any, lower: float, upper: float, *, upper_open: bool = False) -> bool:
    return (
        type(value) in {int, float}
        and lower <= value
        and (value < upper if upper_open else value <= upper)
        and np.isfinite(value)
    )


def validate_spatial_fade(settings: Any, width: int, height: int) -> None:
    """Validate inactive shapes too; never clamp or discard authored settings."""
    if any(type(value) is not int or value <= 0 for value in (width, height)):
        raise ProjectError("Spatial fade requires positive native image dimensions")
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "preserve_highlights", "oval", "arcs_enabled", "arcs"}
        or type(settings["enabled"]) is not bool
        or type(settings["arcs_enabled"]) is not bool
        or not _number(settings["preserve_highlights"], 0, 1)
        or not isinstance(settings["arcs"], list)
        or len(settings["arcs"]) > 32
    ):
        raise ProjectError("Invalid spatial fade settings, switches or arc count (maximum 32)")
    common = {"enabled", "center_xy", "rotation_degrees", "transition_width", "amount"}
    oval = settings["oval"]
    if not isinstance(oval, dict) or set(oval) != common | {"inner_radii_xy"}:
        raise ProjectError("Invalid spatial fade oval fields")
    limit = 2 * max(width, height)
    ids: set[str] = set()
    for index, shape in enumerate([oval, *settings["arcs"]]):
        if index != 0:
            if not isinstance(shape, dict) or set(shape) != common | {
                "id",
                "half_span",
                "bend",
                "fade_side",
                "end_softness",
            }:
                raise ProjectError("Invalid spatial fade arc fields")
            stable_id = shape["id"]
            try:
                parsed = UUID(stable_id) if isinstance(stable_id, str) else None
            except ValueError:
                parsed = None
            if (
                parsed is None
                or parsed.version != 4
                or str(parsed) != stable_id
                or stable_id in ids
            ):
                raise ProjectError("Spatial fade arc IDs must be unique lowercase UUID-v4 values")
            ids.add(stable_id)
            if (
                not _number(shape["half_span"], 0.5, limit)
                or not _number(shape["bend"], -shape["half_span"], shape["half_span"])
                or not _number(shape["end_softness"], 0.5, shape["half_span"])
                or shape["fade_side"] not in ("positive", "negative")
            ):
                raise ProjectError("Invalid spatial fade arc span, bend, soft ends or direction")
        else:
            radii = shape["inner_radii_xy"]
            if (
                not isinstance(radii, list)
                or len(radii) != 2
                or any(not _number(value, 0.5, limit) for value in radii)
            ):
                raise ProjectError("Invalid spatial fade inner oval radii")
        centre = shape["center_xy"]
        if (
            type(shape["enabled"]) is not bool
            or not isinstance(centre, list)
            or len(centre) != 2
            or not _number(centre[0], 0, width)
            or not _number(centre[1], 0, height)
            or not _number(shape["rotation_degrees"], 0, 360, upper_open=True)
            or not _number(shape["transition_width"], 0.5, limit)
            or not _number(shape["amount"], 0, 1)
        ):
            raise ProjectError("Invalid spatial fade shape geometry, strength or switch")


def _smoothstep(value: np.ndarray) -> np.ndarray:
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def _local_coordinates(
    x: np.ndarray, y: np.ndarray, shape: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray]:
    if (
        not isinstance(x, np.ndarray)
        or not isinstance(y, np.ndarray)
        or x.shape != y.shape
        or x.dtype.kind not in "iuf"
        or y.dtype.kind not in "iuf"
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
    ):
        raise ProjectError("Spatial fade samples require aligned finite native coordinates")
    theta = np.deg2rad(shape["rotation_degrees"])
    dx = x.astype(np.float64) - shape["center_xy"][0]
    dy = y.astype(np.float64) - shape["center_xy"][1]
    return np.cos(theta) * dx + np.sin(theta) * dy, -np.sin(theta) * dx + np.cos(theta) * dy


def elliptical_fade_weight(x: np.ndarray, y: np.ndarray, oval: dict[str, Any]) -> np.ndarray:
    """Evaluate exact continuous rays; transition expands each ellipse semi-axis."""
    u, v = _local_coordinates(x, y, oval)
    rho = np.hypot(u, v)
    unit_u = np.divide(u, rho, out=np.zeros_like(u), where=rho != 0)
    unit_v = np.divide(v, rho, out=np.zeros_like(v), where=rho != 0)
    a, b = oval["inner_radii_xy"]
    d = oval["transition_width"]
    inner_inverse = np.hypot(unit_u / a, unit_v / b)
    outer_inverse = np.hypot(unit_u / (a + d), unit_v / (b + d))
    inner = np.divide(1, inner_inverse, out=np.zeros_like(rho), where=rho != 0)
    outer = np.divide(1, outer_inverse, out=np.ones_like(rho), where=rho != 0)
    result = _smoothstep((rho - inner) / (outer - inner))
    return np.where(rho == 0, 0, result)


def arc_fade_weight(x: np.ndarray, y: np.ndarray, arc: dict[str, Any]) -> np.ndarray:
    """A one-sided parabolic boundary with lateral softness and a permanent plateau."""
    u, v = _local_coordinates(x, y, arc)
    span = arc["half_span"]
    boundary = arc["bend"] * (1 - (u / span) ** 2)
    distance = v - boundary
    if arc["fade_side"] == "negative":
        distance = -distance
    lateral = 1 - _smoothstep((np.abs(u) - (span - arc["end_softness"])) / arc["end_softness"])
    return np.where(np.abs(u) < span, lateral * _smoothstep(distance / arc["transition_width"]), 0)


def combined_fade_weight(
    x: np.ndarray,
    y: np.ndarray,
    settings: dict[str, Any],
    *,
    shape_id: str | None = None,
) -> np.ndarray:
    """Reduce each enabled, strength-weighted shape once; master OFF is applied in q."""
    shapes = [("oval", settings["oval"], True)] + [
        (arc["id"], arc, settings["arcs_enabled"]) for arc in settings["arcs"]
    ]
    if shape_id is not None and not any(identity == shape_id for identity, _, _ in shapes):
        raise ProjectError("Unknown spatial fade shape ID in this saved revision")
    # Check coordinates even when no shape contributes.
    _local_coordinates(x, y, settings["oval"])
    result = np.zeros(x.shape, np.float64)
    for identity, shape, group_enabled in shapes:
        if shape_id is not None and identity != shape_id:
            continue
        if not group_enabled or not shape["enabled"] or shape["amount"] == 0:
            continue
        evaluator = elliptical_fade_weight if identity == "oval" else arc_fade_weight
        np.maximum(result, shape["amount"] * evaluator(x, y, shape), out=result)
    return result


def make_spatial_weight(shape: tuple[int, int], settings: dict[str, Any]) -> np.ndarray:
    """Bound transient geometry to 64 rows and quantize the maximum only once."""
    height, width = shape
    validate_spatial_fade(settings, width, height)
    result = np.empty(shape, np.uint16)
    for start in range(0, height, 64):
        stop = min(start + 64, height)
        x, y = np.meshgrid(
            np.arange(width, dtype=np.float64) + 0.5, np.arange(start, stop, dtype=np.float64) + 0.5
        )
        result[start:stop] = np.rint(combined_fade_weight(x, y, settings) * 65535).astype(np.uint16)
    return result


@dataclass(frozen=True)
class SpatialFadeOperands:
    weight16: np.ndarray
    protection: np.ndarray
    record: dict[str, Any]


def spatial_fade_amount(
    foreground: np.ndarray, alpha16: np.ndarray, operands: SpatialFadeOperands
) -> np.ndarray:
    """Alpha gates eligibility only; saved explicit protection always wins."""
    if (
        foreground.dtype != np.uint16
        or foreground.ndim != 3
        or foreground.shape[2] != 3
        or alpha16.dtype != np.uint16
        or alpha16.shape != foreground.shape[:2]
        or operands.weight16.dtype != np.uint16
        or operands.weight16.shape != alpha16.shape
        or operands.protection.dtype != np.bool_
        or operands.protection.shape != alpha16.shape
    ):
        raise ProjectError("Spatial fade requires aligned RGB16/A16/W16 and boolean protection")
    result = np.zeros(alpha16.shape, np.float64)
    if not operands.record["enabled"] or operands.record["stale"]:
        return result
    preserve = operands.record["settings"]["preserve_highlights"]
    for start in range(0, alpha16.shape[0], 64):
        rows = slice(start, start + 64)
        eligible = (
            (alpha16[rows] != 0) & ~operands.protection[rows] & (operands.weight16[rows] != 0)
        )
        weight = operands.weight16[rows][eligible].astype(np.float64) / 65535
        if preserve and eligible.any():
            weight *= 1 - preserve * highlight_weight(
                srgb_to_linear(foreground[rows][eligible].astype(np.float64) / 65535)
            )
        result[rows][eligible] = weight
    return result


def blend_background_float(
    foreground: np.ndarray, background16: np.ndarray, amount: np.ndarray
) -> np.ndarray:
    """Blend encoded RGB in linear light, keeping exact q=0 and q=1 endpoints."""
    if (
        foreground.ndim != 3
        or foreground.shape[2] != 3
        or foreground.dtype.kind not in "iuf"
        or background16.dtype != np.uint16
        or background16.shape != foreground.shape
        or amount.shape != foreground.shape[:2]
        or amount.dtype.kind not in "iuf"
        or not np.isfinite(foreground).all()
        or not np.isfinite(amount).all()
        or np.any((foreground < 0) | (foreground > 65535))
        or np.any((amount < 0) | (amount > 1))
    ):
        raise ProjectError(
            "Spatial background blend requires aligned finite RGB16-range samples and q in [0,1]"
        )
    return np.stack(
        [
            _blend_background_channel(foreground[..., channel], background16[..., channel], amount)
            for channel in range(3)
        ],
        axis=-1,
    )


def _blend_background_channel(
    foreground: np.ndarray, background16: np.ndarray, amount: np.ndarray
) -> np.ndarray:
    """Canonical pointwise blend for validated native RGB or sampled series channels."""
    result = foreground.astype(np.float64)
    partial = (amount > 0) & (amount < 1)
    q = amount[partial]
    result[partial] = (
        linear_to_srgb(
            (1 - q) * srgb_to_linear(foreground[partial].astype(np.float64) / 65535)
            + q * srgb_to_linear(background16[partial].astype(np.float64) / 65535)
        )
        * 65535
    )
    result[amount == 1] = background16[amount == 1]
    return result


def validate_spatial_bindings(project: Path, directory: Path, manifest: dict[str, Any]) -> None:
    """Check inventory before cache lookup so unbound or symlinked files cannot hide."""
    from .assets import revision_hashes

    saved = directory / "effects/spatial-fade"
    listed = {
        name for name in revision_hashes(manifest) if name.startswith("effects/spatial-fade/")
    }
    if "spatial_fade" not in manifest:
        if saved.exists() or saved.is_symlink() or listed:
            raise ProjectError("Unbound saved spatial fade operands")
        return
    required = {f"effects/spatial-fade/{name}" for name in SPATIAL_FADE_FILES}
    if listed != required or "base_alpha16.png" not in revision_hashes(manifest):
        raise ProjectError("Incomplete or extra bound spatial fade operands")
    try:
        if (
            saved.is_symlink()
            or {path.name for path in saved.iterdir()}
            != {
                Path(name).name
                for name in manifest.get("files", {})
                if name.startswith("effects/spatial-fade/")
            }
            or any(path.is_symlink() or not path.is_file() for path in saved.iterdir())
        ):
            raise ProjectError("Invalid saved spatial fade inventory")
    except OSError as error:
        raise ProjectError("Missing saved spatial fade operands") from error
    spatial = manifest["spatial_fade"]
    if (
        isinstance(spatial, dict)
        and spatial.get("enabled")
        and manifest.get("shading", {}).get("enabled")
    ):
        raise ProjectError("Inward shading and spatial fade cannot both be enabled")


def read_spatial_fade(
    project: Path, directory: Path, manifest: dict[str, Any], alpha: np.ndarray
) -> SpatialFadeOperands | None:
    """Read immutable operands, including OFF records; project cache owns geometric replay."""
    from .assets import revision_asset

    validate_spatial_bindings(project, directory, manifest)
    if "spatial_fade" not in manifest:
        return None
    record = manifest["spatial_fade"]
    keys = {
        "schema_version",
        "enabled",
        "settings",
        "stale",
        "source_id",
        "algorithm",
        "alpha_sha256",
        "weight_sha256",
        "protection_sha256",
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
        or record["source_id"] != manifest["developed_id"]
        or record["algorithm"] != SPATIAL_FADE_ALGORITHM
        or alpha.dtype != np.uint16
        or alpha.ndim != 2
    ):
        raise ProjectError("Invalid saved spatial fade identity/schema/status")
    height, width = alpha.shape
    validate_spatial_fade(record["settings"], width, height)
    from .guidance import coordinates

    if (
        record["enabled"] != record["settings"]["enabled"]
        or coordinates(record["scope_xyxy"], width, height, box=True) != [0, 0, width, height]
        or record["enabled"]
        and manifest.get("shading", {}).get("enabled")
    ):
        raise ProjectError("Inconsistent saved spatial fade settings, scope or exclusive mode")
    try:
        if (
            json.loads(
                revision_asset(
                    project, directory, manifest, "effects/spatial-fade/settings.json"
                ).read_bytes()
            )
            != record
        ):
            raise ProjectError("Inconsistent saved spatial fade settings record")
        arrays = []
        for name, key in (
            ("weight16.png", "weight_sha256"),
            ("protection16.png", "protection_sha256"),
            ("alpha16.png", "alpha_sha256"),
        ):
            path = revision_asset(project, directory, manifest, "effects/spatial-fade/" + name)
            if path.is_symlink() or digest(path.read_bytes()) != record[key]:
                raise ProjectError("Saved spatial fade dependency hash mismatch")
            value = scalar16(path)
            if value.shape != alpha.shape:
                raise ProjectError("Saved spatial fade dimensions differ from master")
            arrays.append(value)
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectError("Missing or invalid saved spatial fade operands") from error
    weight, protection, dependency = arrays
    if not np.isin(protection, [0, 65535]).all() or record["stale"] != bool(
        record["enabled"] and not np.array_equal(dependency, alpha)
    ):
        raise ProjectError("Invalid saved spatial fade protection/dependency status")
    return SpatialFadeOperands(weight, protection != 0, record)
