"""Versioned native Mist field and linear-sRGB Result compositing."""

import json
import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .assets import _checksum, inherit_revision_files, revision_asset, revision_hashes, stage_asset
from .exposure import linear_to_rgb16, srgb_to_linear
from .guidance import rasterize_regions, validate_guides
from .pixel_math import HASH32_MAX, coordinate_hash32
from .project import ProjectError, _json_bytes, digest
from .repair import scalar16

ALGORITHM = "linear-srgb-mist-v1"
VAPOR_ALGORITHM = "linear-srgb-vapor-v1"
WISPY_VAPOR_ALGORITHM = "linear-srgb-vapor-v2"
MAX_REQUEST_BYTES = 2_000_000
MAX_SEED = HASH32_MAX
ROWS_PER_CHUNK = 64
MIST_MEMBERS = {
    "density16.png": "density_sha256",
    "clear16.png": "clear_sha256",
    "settings.json": "settings_sha256",
    "area.json": "area_sha256",
}
PROTECTION_ROLE = "supports/protection.png"


def parse_mist_json(raw: bytes, *, request: bool = False) -> dict[str, Any]:
    if request and len(raw) > MAX_REQUEST_BYTES:
        raise ProjectError(f"Mist request exceeds {MAX_REQUEST_BYTES} bytes")

    def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ProjectError("Duplicate Mist JSON field")
        return result

    def reject_constant(value: str) -> None:
        raise ProjectError(f"Nonfinite Mist JSON value: {value}")

    try:
        value = json.loads(raw, object_pairs_hook=unique_fields, parse_constant=reject_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ProjectError("Invalid Mist JSON") from error
    if not isinstance(value, dict):
        raise ProjectError("Mist JSON must be an object")
    return value


def read_mist_request_bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        return stream.read(MAX_REQUEST_BYTES + 1)


def validate_mist_request(value: Any, developed_id: str, width: int, height: int) -> dict[str, Any]:
    if isinstance(value, dict):
        if set(value) == {"action"} and value["action"] == "disable":
            return value
        if set(value) == {"action", "settings", "clear_area"} and value["action"] == "apply":
            return {
                "action": "apply",
                "settings": validate_mist_settings(value["settings"], width, height),
                "clear_area": validate_mist_area(value["clear_area"], developed_id, width, height),
            }
    raise ProjectError(
        "Mist requires Apply with complete settings and Clear mist area or Disable alone"
    )


def _number(value: Any, minimum: float, maximum: float) -> bool:
    return type(value) in (int, float) and minimum <= value <= maximum and math.isfinite(value)


def validate_mist_settings(value: Any, width: int, height: int) -> dict[str, Any]:
    """Return canonical settings, including geometry retained while Mist is OFF."""
    if type(width) is not int or type(height) is not int or min(width, height) < 1:
        raise ProjectError("Mist needs positive native dimensions")
    vapor = isinstance(value, dict) and value.get("style") == "vapor"
    ranges: dict[str, tuple[float, float]] = {"density": (0, 1)}
    if not vapor:
        ranges.update(wisp_size=(0.04, 0.60), stretch=(1, 5))
    ranges["rotation_degrees"] = (0, 360)
    geometry = {"style", "focus_xy"} if vapor else {"coverage"}
    if vapor and "pattern_version" in value:
        geometry.add("pattern_version")
        if type(value["pattern_version"]) is not int or value["pattern_version"] != 2:
            raise ProjectError("Vapor pattern_version must be the integer 2 when present")
    if (
        not isinstance(value, dict)
        or set(value) != {"enabled", "tint_srgb", "seed", *geometry, *ranges}
        or type(value["enabled"]) is not bool
        or not isinstance(value["tint_srgb"], str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", value["tint_srgb"]) is None
        or type(value["seed"]) is not int
        or not 0 <= value["seed"] <= MAX_SEED
    ):
        raise ProjectError("Invalid Mist settings fields, enabled flag, tint or seed")
    for name, (minimum, maximum) in ranges.items():
        if not _number(value[name], minimum, maximum) or (
            name == "rotation_degrees" and value[name] == maximum
        ):
            raise ProjectError(f"Mist {name} outside its range")
    normalized = {
        "enabled": value["enabled"],
        "tint_srgb": value["tint_srgb"].upper(),
        "seed": value["seed"],
        **{name: float(value[name]) or 0.0 for name in ranges},
    }
    if vapor:
        focus = value["focus_xy"]
        if (
            not isinstance(focus, list)
            or len(focus) != 2
            or not _number(focus[0], 0, width)
            or not _number(focus[1], 0, height)
        ):
            raise ProjectError("Vapor focus outside native bounds")
        if "pattern_version" in value:
            normalized["pattern_version"] = value["pattern_version"]
        return dict(normalized, style="vapor", focus_xy=[float(axis) or 0.0 for axis in focus])
    coverage = value["coverage"]
    if not isinstance(coverage, dict) or set(coverage) != {"center_xy", "radii_xy", "softness"}:
        raise ProjectError("Invalid Mist coverage settings")
    center, radii = coverage["center_xy"], coverage["radii_xy"]
    if (
        not isinstance(center, list)
        or len(center) != 2
        or not _number(center[0], 0, width)
        or not _number(center[1], 0, height)
        or not isinstance(radii, list)
        or len(radii) != 2
        or any(not _number(radius, 0.5, 2 * max(width, height)) for radius in radii)
        or not _number(coverage["softness"], 0.05, 1)
    ):
        raise ProjectError("Mist coverage centre, radii or softness outside native bounds")
    return {
        **normalized,
        "coverage": {
            "center_xy": [float(axis) or 0.0 for axis in center],
            "radii_xy": [float(axis) for axis in radii],
            "softness": float(coverage["softness"]),
        },
    }


def mist_algorithm(settings: dict[str, Any]) -> str:
    if settings.get("style") != "vapor":
        return ALGORITHM
    return WISPY_VAPOR_ALGORITHM if settings.get("pattern_version") == 2 else VAPOR_ALGORITHM


def _smoothstep(value: np.ndarray) -> np.ndarray:
    return value * value * (3 - 2 * value)


def _quintic(value: np.ndarray) -> np.ndarray:
    return value**3 * (value * (value * 6 - 15) + 10)


def _lattice(x: np.ndarray, y: np.ndarray, seed: int, octave: int) -> np.ndarray:
    # V1 hashes signed cells modulo 2**32. Keep unsigned arithmetic explicit.
    salt = seed ^ (((octave + 1) * 0xC2B2AE3D) & MAX_SEED)
    return coordinate_hash32(x, y, salt).astype(np.float64) / MAX_SEED


def _value_noise(x: np.ndarray, y: np.ndarray, seed: int, octave: int) -> np.ndarray:
    floor_x, floor_y = np.floor(x), np.floor(y)
    wx, wy = _quintic(x - floor_x), _quintic(y - floor_y)
    ix, iy = floor_x.astype(np.int64).astype(np.uint32), floor_y.astype(np.int64).astype(np.uint32)
    next_x = np.add(ix, np.uint32(1), dtype=np.uint32)
    next_y = np.add(iy, np.uint32(1), dtype=np.uint32)
    top = _lattice(ix, iy, seed, octave) * (1 - wx) + _lattice(next_x, iy, seed, octave) * wx
    bottom = (
        _lattice(ix, next_y, seed, octave) * (1 - wx) + _lattice(next_x, next_y, seed, octave) * wx
    )
    return top * (1 - wy) + bottom * wy


def _noise_gain(wavelength: float, footprint_px: float) -> float:
    taper = max(0.0, min(1.0, (wavelength / footprint_px - 2) / 2))
    return taper * taper * (3 - 2 * taper)


def _wisp_opacity(
    u: np.ndarray, v: np.ndarray, wavelength_px: float, seed: int, footprint_px: float
) -> np.ndarray:
    field = np.zeros(u.shape, dtype=np.float64)
    for octave, weight in enumerate((4, 2, 1)):
        wavelength = wavelength_px / 2**octave
        gain = _noise_gain(wavelength, footprint_px)
        field += weight * (
            0.5 + gain * (_value_noise(u / wavelength, v / wavelength, seed, octave) - 0.5)
        )
    return _smoothstep(np.clip((field / 7 - 0.30) / 0.55, 0, 1))


def _vapor_opacity(
    u: np.ndarray, v: np.ndarray, short_axis: int, seed: int, footprint_px: float
) -> np.ndarray:
    """Shape a low diagonal bank with a thin secondary plume and a clear focus."""
    bank_radius = np.hypot((u + 0.65 * v - 0.50) / 0.39, (v - 0.10) / 0.69)
    bank = _smoothstep(np.clip((1 - bank_radius) / 0.60, 0, 1))
    plume_radius = np.hypot((u + 0.34) / 0.53, (v - 0.04) / 0.58)
    plume = _smoothstep(np.clip((1 - plume_radius) / 0.80, 0, 1))
    texture = np.full(u.shape, 0.5, dtype=np.float64)
    for octave, (along, across, weight) in enumerate(((0.55, 0.30, 0.7), (0.26, 0.15, 0.3))):
        gain = _noise_gain(across * short_axis, footprint_px)
        if gain:
            texture += weight * gain * (_value_noise(u / along, v / across, seed, octave) - 0.5)
    focus = _smoothstep(np.clip((np.hypot(u, v) - 0.12) / 0.17, 0, 1))
    return (0.98 * bank + 0.39 * plume * (1 - bank)) * (0.75 + 0.25 * texture) * focus


def _wispy_vapor_opacity(
    dx: np.ndarray,
    dy: np.ndarray,
    bearing: float,
    short_axis: int,
    seed: int,
    footprint_px: float,
) -> np.ndarray:
    """Offset the bank from the focus and run fine wisps across its bearing."""
    bank_x = dx - 0.24 * short_axis * math.cos(bearing)
    bank_y = dy - 0.24 * short_axis * math.sin(bearing)
    angle = bearing - math.radians(95)
    u = math.cos(angle) * bank_x + math.sin(angle) * bank_y
    v = -math.sin(angle) * bank_x + math.cos(angle) * bank_y
    radius = np.hypot(u / (0.83 * short_axis), v / (0.765 * short_axis))
    bank = _smoothstep(np.clip((1 - radius) / 0.72, 0, 1))
    wisps = _wisp_opacity(u / 3.4, v, max(16, 0.25 * short_axis), seed, footprint_px)
    focus = _smoothstep(np.clip((np.hypot(dx, dy) / short_axis - 0.12) / 0.157, 0, 1))
    return bank * wisps * focus


def sample_mist_density(
    settings: dict[str, Any],
    native_size_wh: tuple[int, int],
    x: np.ndarray,
    y: np.ndarray,
    footprint_px: float = 1,
) -> np.ndarray:
    """Sample density16 at broadcastable native pixel-edge coordinates."""
    x, y = np.broadcast_arrays(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64))
    if settings["density"] == 0:
        return np.zeros(x.shape, dtype=np.uint16)
    vapor = settings.get("style") == "vapor"
    center = settings["focus_xy"] if vapor else settings["coverage"]["center_xy"]
    angle = math.radians(settings["rotation_degrees"])
    dx, dy = x - center[0], y - center[1]
    short_axis = min(native_size_wh)
    if vapor and settings.get("pattern_version") == 2:
        opacity = _wispy_vapor_opacity(dx, dy, angle, short_axis, settings["seed"], footprint_px)
        return np.rint(65535 * settings["density"] * opacity).astype(np.uint16)
    u = math.cos(angle) * dx + math.sin(angle) * dy
    v = -math.sin(angle) * dx + math.cos(angle) * dy
    if vapor:
        opacity = _vapor_opacity(
            u / short_axis, v / short_axis, short_axis, settings["seed"], footprint_px
        )
        return np.rint(65535 * settings["density"] * opacity).astype(np.uint16)
    coverage = settings["coverage"]
    radius = np.hypot(u / coverage["radii_xy"][0], v / coverage["radii_xy"][1])
    envelope = _smoothstep(np.clip((1 - radius) / coverage["softness"], 0, 1))
    u /= settings["stretch"]
    base_wavelength = max(16, settings["wisp_size"] * short_axis)
    opacity = _wisp_opacity(u, v, base_wavelength, settings["seed"], footprint_px)
    return np.rint(65535 * settings["density"] * envelope * opacity).astype(np.uint16)


def make_mist_density(settings: dict[str, Any], native_size_wh: tuple[int, int]) -> np.ndarray:
    width, height = native_size_wh
    density = np.empty((height, width), dtype=np.uint16)
    x = np.arange(width, dtype=np.float64)[None, :] + 0.5
    for start in range(0, height, ROWS_PER_CHUNK):
        stop = min(start + ROWS_PER_CHUNK, height)
        y = np.arange(start, stop, dtype=np.float64)[:, None] + 0.5
        density[start:stop] = sample_mist_density(settings, native_size_wh, x, y)
    return density


def validate_mist_area(value: Any, developed_id: str, width: int, height: int) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"regions", "protection"}
        or not isinstance(value["regions"], list)
        or value["protection"] != []
    ):
        raise ProjectError("Clear mist needs support regions and an empty protection list")
    if len(value["regions"]) > 64:
        raise ProjectError("Clear mist allows at most 64 shapes")
    points = 0
    for region in value["regions"]:
        if (
            not isinstance(region, dict)
            or region.get("role") != "support"
            or region.get("shape") not in ("stroke", "rectangle")
        ):
            raise ProjectError("Clear mist supports only strokes and rectangles")
        if region["shape"] == "stroke" and isinstance(region.get("points"), list):
            points += len(region["points"])
            if points > 8192:
                raise ProjectError("Clear mist allows at most 8192 stroke points")
    try:
        validate_guides(
            _clear_guides(value, developed_id, width, height), developed_id, width, height
        )
    except (TypeError, ValueError) as error:
        raise ProjectError(f"Invalid Clear mist area: {error}") from error
    return value


def _clear_guides(
    area: dict[str, Any], developed_id: str, width: int, height: int
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "developed_id": developed_id,
        "width": width,
        "height": height,
        "regions": area["regions"],
    }


def make_mist_clear(area: dict[str, Any], developed_id: str, protection: np.ndarray) -> np.ndarray:
    height, width = protection.shape
    validate_mist_area(area, developed_id, width, height)
    clear = (
        rasterize_regions(_clear_guides(area, developed_id, width, height)).support16
        if area["regions"]
        else np.zeros(protection.shape, dtype=np.uint16)
    )
    clear[protection] = 65535
    return clear


def mist_has_pixels(density16: np.ndarray, clear16: np.ndarray, settings: dict[str, Any]) -> bool:
    return bool(
        settings["enabled"]
        and settings["density"]
        and any(
            np.any(
                (density16[start : start + ROWS_PER_CHUNK] > 0)
                & (clear16[start : start + ROWS_PER_CHUNK] < 65535)
            )
            for start in range(0, density16.shape[0], ROWS_PER_CHUNK)
        )
    )


def blend_mist_into_result(
    result16: np.ndarray,
    density16: np.ndarray,
    clear16: np.ndarray,
    settings: dict[str, Any],
) -> np.ndarray:
    """Composite once in place on an owned Result; leave bypassed pixels untouched."""
    if not settings["enabled"] or not settings["density"]:
        return result16
    tint = srgb_to_linear(
        np.array([int(settings["tint_srgb"][i : i + 2], 16) for i in (1, 3, 5)]) / 255
    )
    for start in range(0, result16.shape[0], ROWS_PER_CHUNK):
        rows = slice(start, start + ROWS_PER_CHUNK)
        density, clear = density16[rows], clear16[rows]
        active = (density > 0) & (clear < 65535)
        if active.any():
            out = result16[rows]
            opacity = density[active].astype(np.float64) * (65535 - clear[active]) / 65535**2
            linear = srgb_to_linear(out[active].astype(np.float64) / 65535)
            out[active] = linear_to_rgb16(linear + opacity[:, None] * (tint - linear))
    return result16


@dataclass(frozen=True)
class MistOperands:
    density16: np.ndarray
    clear16: np.ndarray
    settings: dict[str, Any]

    def crop(self, x0: int, y0: int, x1: int, y1: int) -> "MistOperands":
        region = np.s_[y0:y1, x0:x1]
        return MistOperands(self.density16[region], self.clear16[region], self.settings)


def separate_result_panel(has_background: bool, mist: MistOperands | None) -> bool:
    return has_background or (
        mist is not None and mist_has_pixels(mist.density16, mist.clear16, mist.settings)
    )


def read_mist_area(project: Path, directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    raw = revision_asset(project, directory, manifest, "mist/area.json").read_bytes()
    if digest(raw) != manifest["mist"]["area_sha256"]:
        raise ProjectError("Saved Clear mist area hash changed")
    return parse_mist_json(raw)


def validate_mist_bindings(directory: Path, manifest: dict[str, Any]) -> None:
    """Check the closed namespace before either revision cache can return."""
    expected_rasters = {"mist/density16.png", "mist/clear16.png"} if "mist" in manifest else set()
    expected_text = {"mist/settings.json", "mist/area.json"} if "mist" in manifest else set()
    namespace = directory / "mist"
    local = set()
    if namespace.exists() or namespace.is_symlink():
        if not expected_text or namespace.is_symlink() or not namespace.is_dir():
            raise ProjectError("Invalid saved Mist namespace")
        for path in namespace.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ProjectError("Invalid saved Mist member")
            local.add(f"mist/{path.name}")
    if (
        local != expected_text
        or {name for name in manifest["files"] if name == "mist" or name.startswith("mist/")}
        != expected_text
        or {name for name in manifest["assets"] if name == "mist" or name.startswith("mist/")}
        != expected_rasters
    ):
        raise ProjectError("Missing, unknown or unbound Mist operands")


def validate_mist_revision(
    project: Path, directory: Path, manifest: dict[str, Any], size: tuple[int, int] | None = None
) -> None:
    if "mist" not in manifest and manifest.get("kind") == "prepare":
        return
    recipe = tomllib.loads((directory / "recipe.toml").read_text())
    if "mist" not in manifest:
        if "mist" in recipe:
            raise ProjectError("Unbound saved Mist recipe settings")
        return
    record = manifest["mist"]
    assert size is not None
    width, height = size
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
            "protection_sha256",
            *MIST_MEMBERS.values(),
        }
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["developed_id"] != manifest["developed_id"]
        or type(record["width"]) is not int
        or type(record["height"]) is not int
        or (record["width"], record["height"]) != size
    ):
        raise ProjectError("Invalid saved Mist identity, schema, algorithm or native dimensions")
    hashes = revision_hashes(manifest)
    if record["protection_sha256"] != hashes.get(PROTECTION_ROLE) or any(
        record[field] != hashes[f"mist/{name}"] for name, field in MIST_MEMBERS.items()
    ):
        raise ProjectError("Mist operand or hard protection hash differs from revision binding")
    settings = validate_mist_settings(record["settings"], width, height)
    if record["algorithm"] != mist_algorithm(settings):
        raise ProjectError("Saved Mist algorithm differs from settings")
    saved_settings = revision_asset(project, directory, manifest, "mist/settings.json").read_bytes()
    if _json_bytes(settings) != saved_settings or _json_bytes(record["settings"]) != saved_settings:
        raise ProjectError("Invalid canonical saved Mist settings")
    if (
        manifest.get("kind") != "prepare"
        and validate_mist_settings(recipe.get("mist"), width, height) != settings
    ):
        raise ProjectError("Mist effective recipe and saved settings differ")
    area_path = revision_asset(project, directory, manifest, "mist/area.json")
    area_bytes = area_path.read_bytes()
    area = validate_mist_area(parse_mist_json(area_bytes), manifest["developed_id"], width, height)
    if area_bytes != _json_bytes(area):
        raise ProjectError("Invalid canonical saved Clear mist area")
    if (
        not settings["density"]
        and scalar16(revision_asset(project, directory, manifest, "mist/density16.png")).any()
    ):
        raise ProjectError("Nonzero saved Mist density raster with zero density")
    clear = scalar16(revision_asset(project, directory, manifest, "mist/clear16.png"))
    with Image.open(revision_asset(project, directory, manifest, PROTECTION_ROLE)) as raster:
        for y0 in range(0, height, ROWS_PER_CHUNK):
            y1 = min(y0 + ROWS_PER_CHUNK, height)
            if np.any((np.asarray(raster.crop((0, y0, width, y1))) != 0) & (clear[y0:y1] != 65535)):
                raise ProjectError("Saved Clear mist raster omits hard protection")


def saved_mist(
    project: Path, directory: Path, manifest: dict[str, Any], *, effects_off: bool = False
) -> MistOperands | None:
    """Read the active maps of a validated saved revision."""
    if effects_off or "mist" not in manifest:
        return None
    settings = manifest["mist"]["settings"]
    if not settings["enabled"] or not settings["density"]:
        return None
    return MistOperands(
        scalar16(revision_asset(project, directory, manifest, "mist/density16.png")),
        scalar16(revision_asset(project, directory, manifest, "mist/clear16.png")),
        settings,
    )


def stage_mist(
    project: Path,
    parent: str | None,
    stage: Path,
    assets: dict[str, Any],
    manifest: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Stage an explicit replacement or retain the saved settings and density."""
    record = manifest.get("mist")
    replacement = request is not None and request["action"] == "apply"
    if record is None and not replacement:
        return None
    protection_path = stage_asset(project, stage, assets, PROTECTION_ROLE)
    protection_hash = (
        assets[PROTECTION_ROLE]["sha256"]
        if PROTECTION_ROLE in assets
        else _checksum(protection_path)
    )
    if replacement:
        assert request is not None
        settings, area = request["settings"], request["clear_area"]
        with Image.open(protection_path) as image:
            width, height = image.size
        developed_id = manifest["developed_id"]
        (stage / "mist").mkdir()
        density_path = stage / "mist/density16.png"
        Image.fromarray(make_mist_density(settings, (width, height))).save(density_path)
        encoded_area = _json_bytes(area)
        (stage / "mist/area.json").write_bytes(encoded_area)
        record = {
            "schema_version": 1,
            "algorithm": mist_algorithm(settings),
            "developed_id": developed_id,
            "width": width,
            "height": height,
            "density_sha256": _checksum(density_path),
            "area_sha256": digest(encoded_area),
        }
    else:
        assert parent is not None and record is not None
        settings = (
            record["settings"] if request is None else dict(record["settings"], enabled=False)
        )
        developed_id = record["developed_id"]
        inherit_revision_files(
            project, parent, stage, assets, ("mist/density16.png", "mist/area.json")
        )
    if not replacement and record["protection_sha256"] == protection_hash:
        assert parent is not None
        inherit_revision_files(project, parent, stage, assets, ("mist/clear16.png",))
        clear_hash = record["clear_sha256"]
    else:
        area = parse_mist_json((stage / "mist/area.json").read_bytes())
        with Image.open(protection_path) as image:
            protection = np.asarray(image) != 0
        clear_path = stage / "mist/clear16.png"
        Image.fromarray(make_mist_clear(area, developed_id, protection)).save(clear_path)
        clear_hash = _checksum(clear_path)
    encoded_settings = _json_bytes(settings)
    (stage / "mist/settings.json").write_bytes(encoded_settings)
    return dict(
        record,
        settings=settings,
        settings_sha256=digest(encoded_settings),
        clear_sha256=clear_hash,
        protection_sha256=protection_hash,
    )


def mist_resource_bytes(width: int, height: int, *, rebuild_clear: bool = False) -> int:
    # Two scalar maps, row-local color/noise scratch and the maximum live
    # native EDT/brush buffers for one shape (authored shapes run in sequence).
    return (
        width * height * (4 + (112 if rebuild_clear else 0))
        + min(height, ROWS_PER_CHUNK) * width * 256
    )
