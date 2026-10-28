"""Independent native backdrop illumination; the unlit base remains the fade target."""

import json
import math
import re
import tomllib
from pathlib import Path
from typing import Any

import numpy as np

from .assets import inherit_revision_files, revision_asset, revision_hashes
from .exposure import linear_to_rgb16, srgb_to_linear
from .project import ProjectError, _json_bytes, digest, read_revision

ALGORITHM = "linear-srgb-background-light-v1"
BACKGROUND_LIGHT_FILES = ("background_light/light_rgb16.tif", "background_light/settings.json")


def _light_shape(shape: tuple[int, int]) -> tuple[int, int]:
    if len(shape) != 2 or any(type(value) is not int or value < 1 for value in shape):
        raise ProjectError("Background light requires positive native height and width")
    return shape


def _number(value: Any, lower: float, upper: float) -> bool:
    return type(value) in {int, float} and lower <= value <= upper and math.isfinite(value)


def validate_background_light(settings: Any, width: int, height: int) -> None:
    """Validate the complete active geometry even when the saved light is disabled."""
    _light_shape((height, width))
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "brightness", "color_srgb", "geometry"}
        or type(settings["enabled"]) is not bool
        or not _number(settings["brightness"], 0, 1)
        or not isinstance(settings["color_srgb"], str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", settings["color_srgb"]) is None
    ):
        raise ProjectError(
            "Background light requires enabled, finite brightness in [0,1], #RRGGBB and geometry"
        )
    geometry = settings["geometry"]
    if not isinstance(geometry, dict) or geometry.get("type") not in ("oval", "directional"):
        raise ProjectError("Background light geometry must be oval or directional")
    fields = {"type", "center_xy", "rotation_degrees"}
    fields |= {"radii_xy", "softness"} if geometry["type"] == "oval" else {"transition_width"}
    if set(geometry) != fields:
        raise ProjectError("Background light geometry has missing or unknown fields")
    center = geometry["center_xy"]
    if (
        not isinstance(center, list)
        or len(center) != 2
        or not _number(center[0], 0, width)
        or not _number(center[1], 0, height)
        or not _number(geometry["rotation_degrees"], 0, 360)
        or geometry["rotation_degrees"] == 360
    ):
        raise ProjectError(
            "Background light centre must lie within the native image and rotation in [0,360)"
        )
    maximum = 2 * max(width, height)
    if geometry["type"] == "oval":
        radii = geometry["radii_xy"]
        if (
            not isinstance(radii, list)
            or len(radii) != 2
            or any(not _number(radius, 0.5, maximum) for radius in radii)
            or not _number(geometry["softness"], 0.05, 1)
        ):
            raise ProjectError(
                "Background light radii must be in [0.5,2D] and softness in [0.05,1]"
            )
    elif not _number(geometry["transition_width"], 0.5, maximum):
        raise ProjectError("Background light transition width must be in [0.5,2D]")


def normalized_background_light(settings: Any, width: int, height: int) -> dict[str, Any]:
    validate_background_light(settings, width, height)
    geometry = {
        name: value.copy() if isinstance(value, list) else value
        for name, value in settings["geometry"].items()
    }
    return {
        "enabled": settings["enabled"],
        "brightness": settings["brightness"],
        "color_srgb": settings["color_srgb"].upper(),
        "geometry": geometry,
    }


def sample_background_light(
    shape: tuple[int, int], settings: dict[str, Any], x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    """Evaluate native integer-centre geometry, including coordinates outside the image."""
    height, width = _light_shape(shape)
    validate_background_light(settings, width, height)
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ProjectError("Background light sample coordinates must be equally shaped and finite")
    color = np.array([int(settings["color_srgb"][i : i + 2], 16) for i in (1, 3, 5)]) / 255
    if settings["brightness"] == 0 or not color.any():
        return np.zeros((*x.shape, 3), np.uint16)
    geometry = settings["geometry"]
    angle = math.radians(geometry["rotation_degrees"])
    dx, dy = x - geometry["center_xy"][0], y - geometry["center_xy"][1]
    u = math.cos(angle) * dx + math.sin(angle) * dy
    if geometry["type"] == "oval":
        v = -math.sin(angle) * dx + math.cos(angle) * dy
        radius = np.hypot(u / geometry["radii_xy"][0], v / geometry["radii_xy"][1])
        position = np.clip((1 - radius) / geometry["softness"], 0, 1)
    else:
        position = np.clip(u / geometry["transition_width"] + 0.5, 0, 1)
    weight = position * position * (3 - 2 * position)
    if geometry["type"] == "directional":
        weight = 1 - weight
    peak = srgb_to_linear(np.asarray(settings["brightness"], dtype=np.float64))
    return linear_to_rgb16(srgb_to_linear(color) * peak * weight[..., None])


def make_background_light(shape: tuple[int, int], settings: dict[str, Any]) -> np.ndarray:
    """Generate recoverable light regardless of enabled state with at most 64-row fields."""
    height, width = _light_shape(shape)
    validate_background_light(settings, width, height)
    result = np.empty((height, width, 3), np.uint16)
    columns = np.arange(width, dtype=np.float64)[None, :]
    for start in range(0, height, 64):
        rows = np.arange(start, min(start + 64, height), dtype=np.float64)[:, None]
        x, y = np.broadcast_arrays(columns, rows)
        result[start : start + 64] = sample_background_light(shape, settings, x, y)
    return result


def validate_background_light_bindings(
    project: Path, directory: Path, manifest: dict[str, Any]
) -> None:
    """Check optional inventory before either revision-validation cache can return."""
    bound = {name for name in revision_hashes(manifest) if name.startswith("background_light/")}
    expected = set(BACKGROUND_LIGHT_FILES) if "background_light" in manifest else set()
    saved = directory / "background_light"
    local = set()
    if saved.exists() or saved.is_symlink():
        if saved.is_symlink() or not saved.is_dir():
            raise ProjectError("Invalid saved background light directory")
        for path in saved.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ProjectError("Invalid saved background light asset")
            local.add("background_light/" + path.name)
    if directory.name.startswith((".prepare-", ".matte-", ".effects-")):
        bound |= local
    elif local != (expected & set(manifest.get("files", {}))):
        raise ProjectError("Missing, unknown or unbound background light assets")
    if bound != expected:
        raise ProjectError("Missing, unknown or unbound background light assets")


def read_background_light(
    project: Path, directory: Path, manifest: dict[str, Any]
) -> np.ndarray | None:
    """Validate OFF operands too; saved native pixels are authoritative, never regenerated."""
    from .export import read_rgb16

    validate_background_light_bindings(project, directory, manifest)
    recipe = tomllib.loads((directory / "recipe.toml").read_text())
    if "background_light" not in manifest:
        if "background_light" in recipe:
            raise ProjectError("Unbound background light recipe settings")
        return None
    record = manifest["background_light"]
    if (
        not isinstance(record, dict)
        or set(record)
        != {
            "schema_version",
            "algorithm",
            "developed_id",
            "width",
            "height",
            "settings",
            "light_sha256",
            "settings_sha256",
        }
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["algorithm"] != ALGORITHM
        or record["developed_id"] != manifest["developed_id"]
        or any(type(record[name]) is not int or record[name] < 1 for name in ("width", "height"))
    ):
        raise ProjectError("Invalid saved background light identity/schema/algorithm")
    width, height = record["width"], record["height"]
    settings = normalized_background_light(record["settings"], width, height)
    if (
        settings != record["settings"]
        or normalized_background_light(recipe.get("background_light"), width, height) != settings
    ):
        raise ProjectError("Background light recipe and saved settings differ")
    for name, key in zip(BACKGROUND_LIGHT_FILES, ("light_sha256", "settings_sha256"), strict=True):
        if (
            revision_hashes(manifest)[name] != record[key]
            or digest(revision_asset(project, directory, manifest, name).read_bytes())
            != record[key]
        ):
            raise ProjectError("Saved background light hash mismatch")
    saved_settings = json.loads(
        revision_asset(project, directory, manifest, BACKGROUND_LIGHT_FILES[1]).read_bytes()
    )
    if (
        normalized_background_light(saved_settings, width, height) != settings
        or saved_settings != settings
    ):
        raise ProjectError("Saved background light settings differ")
    pixels = read_rgb16(revision_asset(project, directory, manifest, BACKGROUND_LIGHT_FILES[0]))
    if pixels.shape != (height, width, 3):
        raise ProjectError("Saved background light dimensions differ")
    if (settings["brightness"] == 0 or settings["color_srgb"] == "#000000") and pixels.any():
        raise ProjectError("Saved zero background light pixels differ from settings")
    return pixels


def _save_light_record(
    stage: Path,
    developed_id: str,
    shape: tuple[int, int],
    settings: dict[str, Any],
    light_sha256: str,
) -> dict[str, Any]:
    (stage / "background_light").mkdir(exist_ok=True)
    encoded = _json_bytes(settings)
    (stage / BACKGROUND_LIGHT_FILES[1]).write_bytes(encoded)
    return {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "developed_id": developed_id,
        "width": shape[1],
        "height": shape[0],
        "settings": settings,
        "light_sha256": light_sha256,
        "settings_sha256": digest(encoded),
    }


def save_background_light(
    stage: Path, developed_id: str, shape: tuple[int, int], settings: dict[str, Any]
) -> dict[str, Any]:
    from .ingest import write_developed

    height, width = _light_shape(shape)
    settings = normalized_background_light(settings, width, height)
    pixels = make_background_light(shape, settings)
    (stage / "background_light").mkdir(exist_ok=True)
    path = stage / BACKGROUND_LIGHT_FILES[0]
    write_developed(path, pixels)
    return _save_light_record(stage, developed_id, shape, settings, digest(path.read_bytes()))


def apply_background_light(
    project: Path,
    parent: str,
    stage: Path,
    developed_id: str,
    shape: tuple[int, int],
    settings: dict[str, Any],
    *,
    assets: dict[str, Any],
) -> dict[str, Any]:
    """An enabled-only Apply inherits encoded pixels; other explicit changes regenerate."""
    settings = normalized_background_light(settings, shape[1], shape[0])
    previous = read_revision(project, parent, developed_id).get("background_light")
    if previous is not None and all(
        settings[key] == previous["settings"][key]
        for key in ("brightness", "color_srgb", "geometry")
    ):
        inherit_revision_files(project, parent, stage, assets, (BACKGROUND_LIGHT_FILES[0],))
        return _save_light_record(stage, developed_id, shape, settings, previous["light_sha256"])
    return save_background_light(stage, developed_id, shape, settings)


def inherit_background_light(
    project: Path,
    parent: str | None,
    stage: Path,
    developed_id: str,
    shape: tuple[int, int],
    settings: dict[str, Any] | None,
    *,
    assets: dict[str, Any],
) -> dict[str, Any] | None:
    """Preparation and matte inheritance cannot introduce or apply a pending light draft."""
    height, width = _light_shape(shape)
    manifest = read_revision(project, parent, developed_id) if parent is not None else {}
    record = manifest.get("background_light")
    expected = record["settings"] if record is not None else None
    current = normalized_background_light(settings, width, height) if settings is not None else None
    if current != expected:
        raise ProjectError(
            "Changed background light draft requires explicit Apply Background light"
        )
    if record is not None and parent is not None:
        if record["developed_id"] != developed_id or (record["height"], record["width"]) != shape:
            raise ProjectError("Inherited background light source/dimensions differ")
        (stage / "background_light").mkdir(exist_ok=True)
        inherit_revision_files(project, parent, stage, assets, BACKGROUND_LIGHT_FILES)
    return record


def read_active_background_light(
    project: Path, directory: Path, manifest: dict[str, Any]
) -> np.ndarray | None:
    """Read validated saved light, returning no field when disabled or entirely zero."""
    light = read_background_light(project, directory, manifest)
    if light is None or not manifest["background_light"]["settings"]["enabled"] or not light.any():
        return None
    return light


def saved_backgrounds(
    project: Path, directory: Path, manifest: dict[str, Any], *, light_off: bool = False
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Return independent unlit/displayed backdrops without deciding foreground staleness."""
    from .background import read_background

    base = read_background(project, directory, manifest)
    light = read_active_background_light(project, directory, manifest)
    if light is None or light_off:
        return base, base
    if base is None:
        base = np.zeros_like(light)
    return base, combine_background_light(base, light, enabled=True)


def combine_background_light(
    background16: np.ndarray, light16: np.ndarray, *, enabled: bool
) -> np.ndarray:
    """Add decoded light only to the displayed backdrop; never alter the base operand."""
    if (
        type(enabled) is not bool
        or background16.dtype != np.uint16
        or light16.dtype != np.uint16
        or background16.ndim != 3
        or background16.shape[-1] != 3
        or light16.shape != background16.shape
    ):
        raise ProjectError(
            "Background light combination requires matching RGB16 arrays and boolean enabled"
        )
    if not enabled or not light16.any():
        return background16
    result = background16.copy()
    for start in range(0, len(result), 64):
        base, light = background16[start : start + 64], light16[start : start + 64]
        active = np.any(light != 0, axis=-1)
        combined = linear_to_rgb16(
            srgb_to_linear(base.astype(np.float64) / 65535)
            + srgb_to_linear(light.astype(np.float64) / 65535)
        )
        result[start : start + 64][active] = combined[active]
    return result
