"""Versioned procedural proposals using the same shapes as manual authoring."""

import re
from hashlib import sha256

from .background_pattern import MAX_SEED, STYLES, OvalShape, PatternShape, WaveShape
from .project import ProjectError

_STYLE_SHAPES = {
    "waves": ("lower-wave", "side-wave"),
    "ovals": ("upper-oval", "side-oval"),
    "mixed": ("lower-wave", "side-wave", "upper-oval"),
}
_PLACEMENTS = {
    "lower-wave": ((0.40, 0.58), (0.77, 0.87), (-12, 16)),
    "side-wave": ((0.12, 0.24), (0.43, 0.59), (68, 104)),
    "upper-oval": ((0.60, 0.80), (0.15, 0.32), (-30, 25)),
    "side-oval": ((0.14, 0.30), (0.48, 0.77), (-40, 35)),
}


def default_pattern_seed(developed_id: str, style: str) -> int:
    if (
        not isinstance(developed_id, str)
        or re.fullmatch(r"[0-9a-f]{64}", developed_id) is None
        or style not in STYLES
    ):
        raise ProjectError("Invalid Background pattern source identity or style")
    payload = b"image-mask/background-pattern/v1\0" + bytes.fromhex(developed_id) + b"\0"
    return int.from_bytes(sha256(payload + style.encode("ascii")).digest()[:4], "big")


def _draw(attribute_key: str, bounds: tuple[float, float]) -> float:
    bits = int.from_bytes(sha256(attribute_key.encode("ascii")).digest()[:8], "big") >> 11
    low, high = bounds
    return low + (high - low) * (bits / 2**53)


def generate_background_pattern(
    style: str, seed: int, width: int, height: int
) -> list[PatternShape]:
    if (
        style not in STYLES
        or type(seed) is not int
        or not 0 <= seed <= MAX_SEED
        or type(width) is not int
        or type(height) is not int
        or min(width, height) < 1
    ):
        raise ProjectError("Invalid Background pattern generation style, seed or dimensions")
    short = min(width, height)
    shapes: list[PatternShape] = []
    for identifier in _STYLE_SHAPES[style]:
        key = f"background-pattern-v1/{seed}/{style}/{identifier}/"
        x, y, angle = _PLACEMENTS[identifier]
        center = [_draw(key + "center_x", x) * width, _draw(key + "center_y", y) * height]
        rotation = _draw(key + "rotation", angle) % 360
        if identifier.endswith("-wave"):
            lower = identifier == "lower-wave"
            spacing = max(
                0.5, _draw(key + "spacing", (0.085, 0.16) if lower else (0.10, 0.20)) * short
            )
            wave: WaveShape = {
                "id": identifier,
                "type": "wave",
                "enabled": True,
                "center_xy": center,
                "rotation_degrees": rotation,
                "bend_px": _draw(key + "bend", (0.035, 0.11) if lower else (0.025, 0.075)) * short,
                "wavelength_px": max(
                    0.5, _draw(key + "wavelength", (0.65, 1.25) if lower else (0.75, 1.40)) * short
                ),
                "spacing_px": spacing,
                "phase_degrees": _draw(key + "phase", (0, 360)),
                "band_count": 3 if lower else 2,
                "feather_px": max(
                    0.5, _draw(key + "feather", (0.22, 0.45) if lower else (0.30, 0.56)) * spacing
                ),
                "first_tone": "tone2" if lower else "tone1",
            }
            shapes.append(wave)
        else:
            upper = identifier == "upper-oval"
            oval: OvalShape = {
                "id": identifier,
                "type": "oval",
                "enabled": True,
                "center_xy": center,
                "rotation_degrees": rotation,
                "radii_xy": [
                    max(
                        0.5,
                        _draw(key + "radius_x", (0.19, 0.35) if upper else (0.12, 0.27)) * width,
                    ),
                    max(
                        0.5,
                        _draw(key + "radius_y", (0.20, 0.38) if upper else (0.16, 0.33)) * height,
                    ),
                ],
                "softness": _draw(key + "softness", (0.70, 1) if upper else (0.75, 1)),
                "tone": "tone1" if upper else "tone2",
            }
            shapes.append(oval)
    return shapes
