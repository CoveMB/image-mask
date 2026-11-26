"""Editable native-space pattern geometry and independent backdrop colour."""

import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

import numpy as np
from PIL import Image

from .assets import inherit_revision_files, revision_asset, revision_hashes
from .exposure import linear_to_rgb16, srgb_to_linear
from .project import ProjectError, _json_bytes, digest, read_revision
from .repair import scalar16

ALGORITHM = "signed-background-pattern-v1"
STYLES = ("waves", "ovals", "mixed")
MAX_SEED = 2**32 - 1
ZERO_WEIGHT = 32768
_WEIGHT_SCALE = 32767
_ROWS = 64
PATTERN_FILES = ("background_pattern/weight16.png", "background_pattern/settings.json")
Tone = Literal["tone1", "tone2"]


class _Placement(TypedDict):
    id: str
    enabled: bool
    center_xy: list[float]
    rotation_degrees: float


class WaveShape(_Placement):
    type: Literal["wave"]
    bend_px: float
    wavelength_px: float
    spacing_px: float
    phase_degrees: float
    band_count: int
    feather_px: float
    first_tone: Tone


class OvalShape(_Placement):
    type: Literal["oval"]
    radii_xy: list[float]
    softness: float
    tone: Tone


PatternShape = WaveShape | OvalShape


class PatternOrigin(TypedDict):
    version: int
    style: str
    seed: int


class PatternSettings(TypedDict):
    enabled: bool
    strength: float
    tones_srgb: list[str]
    reverse: bool
    shapes: list[PatternShape]
    generator: NotRequired[PatternOrigin]


def _number(value: object, minimum: float, maximum: float, name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not minimum <= value <= maximum
    ):
        raise ProjectError(f"Invalid Background pattern {name}")
    return float(value)


def _angle(value: object, name: str) -> float:
    degrees = _number(value, 0, 360, name)
    if degrees == 360:
        raise ProjectError(f"Background pattern {name} must be below 360 degrees")
    return degrees


def _pair(value: object, minimum: float, maximums: tuple[int, int], name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ProjectError(f"Background pattern {name} requires two coordinates")
    return [_number(item, minimum, maximum, name) for item, maximum in zip(value, maximums)]


def _tone(value: object) -> Tone:
    if value == "tone1":
        return "tone1"
    if value == "tone2":
        return "tone2"
    raise ProjectError("Background pattern shape requires Tone 1 or Tone 2")


def _shape(value: object, width: int, height: int) -> PatternShape:
    if not isinstance(value, dict) or not isinstance(value.get("id"), str):
        raise ProjectError("Invalid Background pattern shape")
    common = {"id", "type", "enabled", "center_xy", "rotation_degrees"}
    wave = {
        "bend_px",
        "wavelength_px",
        "spacing_px",
        "phase_degrees",
        "band_count",
        "feather_px",
        "first_tone",
    }
    oval = {"radii_xy", "softness", "tone"}
    kind = value.get("type")
    if (
        (kind != "wave" and kind != "oval")
        or set(value) != common | (wave if kind == "wave" else oval)
        or type(value["enabled"]) is not bool
        or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", value["id"]) is None
    ):
        raise ProjectError("Invalid Background pattern shape fields or ID")
    limit = 2 * max(width, height)
    placement: _Placement = {
        "id": value["id"],
        "enabled": value["enabled"],
        "center_xy": _pair(value["center_xy"], 0, (width, height), "centre"),
        "rotation_degrees": _angle(value["rotation_degrees"], "rotation"),
    }
    if kind == "oval":
        return {
            **placement,
            "type": "oval",
            "radii_xy": _pair(value["radii_xy"], 0.5, (limit, limit), "radii"),
            "softness": _number(value["softness"], 0.05, 1, "softness"),
            "tone": _tone(value["tone"]),
        }
    count = value["band_count"]
    if type(count) is not int or not 1 <= count <= 4:
        raise ProjectError("Background pattern requires one to four wave bands")
    spacing = _number(value["spacing_px"], 0.5, limit, "spacing")
    return {
        **placement,
        "type": "wave",
        "bend_px": _number(value["bend_px"], 0, limit, "bend"),
        "wavelength_px": _number(value["wavelength_px"], 0.5, limit, "wavelength"),
        "spacing_px": spacing,
        "phase_degrees": _angle(value["phase_degrees"], "phase"),
        "band_count": count,
        "feather_px": _number(value["feather_px"], 0.5, spacing, "feather"),
        "first_tone": _tone(value["first_tone"]),
    }


def normalize_background_pattern(settings: object, width: int, height: int) -> PatternSettings:
    """Validate and own editable values, including disabled shapes."""
    required = {"enabled", "strength", "tones_srgb", "reverse", "shapes"}
    if (
        type(width) is not int
        or type(height) is not int
        or min(width, height) < 1
        or not isinstance(settings, dict)
        or set(settings) - {"generator"} != required
        or type(settings["enabled"]) is not bool
        or type(settings["reverse"]) is not bool
    ):
        raise ProjectError("Invalid Background pattern settings or native dimensions")
    tones, shapes = settings["tones_srgb"], settings["shapes"]
    if (
        not isinstance(tones, list)
        or len(tones) != 2
        or any(
            not isinstance(tone, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", tone) is None
            for tone in tones
        )
    ):
        raise ProjectError("Background pattern requires two #RRGGBB tones")
    if not isinstance(shapes, list) or len(shapes) > 8:
        raise ProjectError("Background pattern supports up to eight shapes")
    layout = [_shape(shape, width, height) for shape in shapes]
    if len({shape["id"] for shape in layout}) != len(layout):
        raise ProjectError("Background pattern shape IDs must be unique")
    if settings["enabled"] and not any(shape["enabled"] for shape in layout):
        raise ProjectError("Enable at least one shape before applying Background pattern")
    normalized: PatternSettings = {
        "enabled": settings["enabled"],
        "strength": _number(settings["strength"], 0, 1, "strength"),
        "tones_srgb": [tone.upper() for tone in tones],
        "reverse": settings["reverse"],
        "shapes": layout,
    }
    if "generator" in settings:
        origin = settings["generator"]
        if (
            not isinstance(origin, dict)
            or set(origin) != {"version", "style", "seed"}
            or type(origin["version"]) is not int
            or origin["version"] != 1
            or origin["style"] not in STYLES
            or type(origin["seed"]) is not int
            or not 0 <= origin["seed"] <= MAX_SEED
        ):
            raise ProjectError("Invalid Background pattern generator origin")
        normalized["generator"] = {"version": 1, "style": origin["style"], "seed": origin["seed"]}
    return normalized


def _smooth(position: np.ndarray) -> np.ndarray:
    fraction = np.clip(position, 0, 1)
    return fraction * fraction * (3 - 2 * fraction)


def _sample(shapes: list[PatternShape], x: np.ndarray, y: np.ndarray) -> np.ndarray:
    signed = np.zeros_like(x, dtype=np.float64)
    for shape in shapes:
        if not shape["enabled"]:
            continue
        radians = math.radians(shape["rotation_degrees"])
        cosine, sine = math.cos(radians), math.sin(radians)
        dx, dy = x - shape["center_xy"][0], y - shape["center_xy"][1]
        along, across = cosine * dx + sine * dy, -sine * dx + cosine * dy
        if shape["type"] == "oval":
            radius_x, radius_y = shape["radii_xy"]
            distance = np.hypot(along / radius_x, across / radius_y)
            sign = -1 if shape["tone"] == "tone1" else 1
            signed += sign * _smooth((1 - distance) / shape["softness"])
            continue
        cycle = along / shape["wavelength_px"] + shape["phase_degrees"] / 360
        warped = across - shape["bend_px"] * np.sin(math.tau * cycle)
        spacing, count, feather = shape["spacing_px"], shape["band_count"], shape["feather_px"]
        sign = -1 if shape["first_tone"] == "tone1" else 1
        for band in range(count):
            lower = (band - count / 2) * spacing
            signed += sign * (
                _smooth((warped - lower) / feather + 0.5)
                - _smooth((warped - lower - spacing) / feather + 0.5)
            )
            sign = -sign
    return np.rint(ZERO_WEIGHT + _WEIGHT_SCALE * np.clip(signed, -1, 1)).astype(np.uint16)


def sample_background_pattern(
    settings: PatternSettings, native_wh: tuple[int, int], x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    normalized = normalize_background_pattern(settings, *native_wh)
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ProjectError("Background pattern requires matching finite sample coordinates")
    return _sample(normalized["shapes"], x, y)


def make_background_pattern(
    settings: PatternSettings,
    native_wh: tuple[int, int],
    *,
    crop_xyxy: list[int] | None = None,
) -> np.ndarray:
    normalized = normalize_background_pattern(settings, *native_wh)
    width, height = native_wh
    if crop_xyxy is None:
        x0, y0, x1, y1 = 0, 0, width, height
    else:
        from .guidance import coordinates

        x0, y0, x1, y1 = coordinates(crop_xyxy, width, height, box=True)
    result = np.empty((y1 - y0, x1 - x0), dtype=np.uint16)
    columns = np.arange(x0, x1, dtype=np.float64)[None, :]
    for start in range(y0, y1, _ROWS):
        stop = min(start + _ROWS, y1)
        rows = np.arange(start, stop, dtype=np.float64)[:, None]
        x, y = np.broadcast_arrays(columns, rows)
        result[start - y0 : stop - y0] = _sample(normalized["shapes"], x, y)
    return result


def pattern_visible(settings: PatternSettings | None) -> bool:
    return settings is not None and settings["enabled"] and settings["strength"] > 0


def combine_background_pattern(
    background16: np.ndarray, weight16: np.ndarray, settings: PatternSettings
) -> np.ndarray:
    """Mix only the displayed backdrop, preserving exact identity off the field."""
    if (
        background16.dtype != np.uint16
        or background16.ndim != 3
        or background16.shape[-1] != 3
        or weight16.dtype != np.uint16
        or weight16.shape != background16.shape[:2]
        or weight16.min(initial=1) == 0
    ):
        raise ProjectError("Background pattern requires matching RGB16 and valid signed scalar16")
    if not pattern_visible(settings):
        return background16
    palette = srgb_to_linear(
        np.array([list(bytes.fromhex(tone[1:])) for tone in settings["tones_srgb"]]) / 255
    )
    result = background16.copy()
    for start in range(0, weight16.shape[0], _ROWS):
        rows = slice(start, start + _ROWS)
        field = weight16[rows]
        active = field != ZERO_WEIGHT
        if not active.any():
            continue
        signed = (field[active].astype(np.float64) - ZERO_WEIGHT) / _WEIGHT_SCALE
        if settings["reverse"]:
            signed = -signed
        amount = np.abs(signed)[:, None] * settings["strength"]
        base = srgb_to_linear(background16[rows][active].astype(np.float64) / 65535)
        target = palette[(signed > 0).astype(np.intp)]
        result[rows][active] = linear_to_rgb16(base + amount * (target - base))
    return result


@dataclass(frozen=True)
class PatternOperands:
    settings: PatternSettings
    weight16: np.ndarray

    def crop(self, x0: int, y0: int, x1: int, y1: int) -> "PatternOperands":
        return PatternOperands(self.settings, self.weight16[y0:y1, x0:x1])


def pattern_resource_bytes(width: int, height: int) -> int:
    # Include the field, new displayed backdrop, optional legacy black base and row work.
    return 16 * width * height + min(height, _ROWS) * width * 192


def display_background(
    background16: np.ndarray | None, pattern: PatternOperands | None
) -> np.ndarray | None:
    """Return a display-only override, never a subject fade operand."""
    if pattern is None or not pattern_visible(pattern.settings):
        return None
    if background16 is None:
        background16 = np.zeros((*pattern.weight16.shape, 3), dtype=np.uint16)
    return combine_background_pattern(background16, pattern.weight16, pattern.settings)


def validate_background_pattern_bindings(directory: Path, manifest: dict[str, Any]) -> None:
    prefix = "background_pattern/"
    present = "background_pattern" in manifest
    bound = {name for name in revision_hashes(manifest) if name.startswith(prefix)}
    expected = set(PATTERN_FILES) if present else set()
    folder = directory / prefix
    if (
        bound != expected
        or folder.is_symlink()
        or (
            present
            and (
                not folder.is_dir() or {path.name for path in folder.iterdir()} != {"settings.json"}
            )
        )
        or (not present and folder.exists())
    ):
        raise ProjectError("Missing, unknown or unbound Background pattern operands")
    if present:
        settings = folder / "settings.json"
        if not settings.is_file() or settings.is_symlink():
            raise ProjectError("Invalid Background pattern settings asset")


def read_background_pattern(
    project: Path, directory: Path, manifest: dict[str, Any]
) -> PatternOperands | None:
    validate_background_pattern_bindings(directory, manifest)
    recipe = tomllib.loads((directory / "recipe.toml").read_text())
    if "background_pattern" not in manifest:
        if "background_pattern" in recipe:
            raise ProjectError("Unbound Background pattern recipe settings")
        return None
    record = manifest["background_pattern"]
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
            "weight_sha256",
            "settings_sha256",
        }
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["algorithm"] != ALGORITHM
        or record["developed_id"] != manifest["developed_id"]
    ):
        raise ProjectError("Invalid saved Background pattern identity or algorithm")
    width, height = record["width"], record["height"]
    settings = normalize_background_pattern(record["settings"], width, height)
    encoded = _json_bytes(dict(settings))
    hashes = revision_hashes(manifest)
    settings_path = revision_asset(project, directory, manifest, PATTERN_FILES[1])
    if (
        _json_bytes(record["settings"]) != encoded
        or normalize_background_pattern(recipe.get("background_pattern"), width, height) != settings
        or settings_path.read_bytes() != encoded
        or hashes[PATTERN_FILES[1]] != record["settings_sha256"]
        or digest(encoded) != record["settings_sha256"]
        or hashes[PATTERN_FILES[0]] != record["weight_sha256"]
    ):
        raise ProjectError("Background pattern settings or operand hashes differ")
    field = scalar16(revision_asset(project, directory, manifest, PATTERN_FILES[0]))
    if field.shape != (height, width) or field.min(initial=1) == 0:
        raise ProjectError("Invalid Background pattern weight dimensions or codes")
    return PatternOperands(settings, field)


def stage_background_pattern(
    project: Path,
    parent: str | None,
    stage: Path,
    developed_id: str,
    native_wh: tuple[int, int],
    assets: dict[str, Any],
    settings: PatternSettings | None = None,
) -> dict[str, Any] | None:
    """Inherit validated saved operands or apply exactly one explicit replacement."""
    previous = (
        read_revision(project, parent, developed_id).get("background_pattern") if parent else None
    )
    if settings is None:
        if previous is not None and parent is not None:
            inherit_revision_files(project, parent, stage, assets, PATTERN_FILES)
        return previous
    weight = stage / PATTERN_FILES[0]
    weight.parent.mkdir(exist_ok=True)
    if (
        previous is not None
        and parent is not None
        and previous["settings"]["shapes"] == settings["shapes"]
    ):
        inherit_revision_files(project, parent, stage, assets, (PATTERN_FILES[0],))
        checksum = previous["weight_sha256"]
    else:
        Image.fromarray(make_background_pattern(settings, native_wh)).save(weight)
        checksum = digest(weight.read_bytes())
    encoded = _json_bytes(dict(settings))
    (stage / PATTERN_FILES[1]).write_bytes(encoded)
    return {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "developed_id": developed_id,
        "width": native_wh[0],
        "height": native_wh[1],
        "settings": dict(settings),
        "weight_sha256": checksum,
        "settings_sha256": digest(encoded),
    }


def saved_pattern(
    project: Path, directory: Path, manifest: dict[str, Any], *, off: bool = False
) -> PatternOperands | None:
    if off or "background_pattern" not in manifest:
        return None
    return read_background_pattern(project, directory, manifest)
