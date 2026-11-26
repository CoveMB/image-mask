"""Deterministic pixel-grid math for saved effects and composed RGB8 views."""

import math

import numpy as np
from PIL import Image
from scipy.ndimage import maximum_filter1d

HASH32_MAX = 2**32 - 1
BACKDROP_DITHER_PNG_SUFFIX = "+backdrop-coordinate-dither-v1"
BACKDROP_JPEG_QUALITY = 98
_DISPLAY_SALT = 0x13C14BD0
_ROWS_PER_CHUNK = 64


def coordinate_hash32(x: np.ndarray, y: np.ndarray, salt: int) -> np.ndarray:
    """Mix broadcastable unsigned coordinates with unsigned wraparound."""
    bits = np.bitwise_xor(
        np.multiply(x, np.uint32(0x9E3779B1), dtype=np.uint32),
        np.multiply(y, np.uint32(0x85EBCA77), dtype=np.uint32),
    )
    bits ^= np.uint32(salt)
    bits = np.multiply(bits ^ (bits >> np.uint32(16)), np.uint32(0x7FEB352D), dtype=np.uint32)
    bits = np.multiply(bits ^ (bits >> np.uint32(15)), np.uint32(0x846CA68B), dtype=np.uint32)
    return bits ^ (bits >> np.uint32(16))


def result_rgb8(
    rgb16: np.ndarray,
    *,
    backdrop_only: np.ndarray | None = None,
    origin_xy: tuple[int, int] = (0, 0),
) -> np.ndarray:
    """Quantize composed RGB, dithering only selected pure-backdrop samples."""
    if rgb16.dtype != np.uint16 or rgb16.ndim != 3 or rgb16.shape[2] != 3:
        raise ValueError("Result conversion requires RGB16")
    if backdrop_only is not None and (
        backdrop_only.dtype != np.bool_ or backdrop_only.shape != rgb16.shape[:2]
    ):
        raise ValueError("Backdrop selection must be an aligned boolean plane")
    result = np.empty(rgb16.shape, np.uint8)
    origin_x, origin_y = origin_xy
    for start in range(0, rgb16.shape[0], _ROWS_PER_CHUNK):
        stop = start + _ROWS_PER_CHUNK
        rows = rgb16[start:stop]
        converted = np.rint(rows.astype(np.float64) / 257).astype(np.uint8)
        if backdrop_only is not None:
            local_y, local_x = np.nonzero(backdrop_only[start:stop])
            if local_x.size:
                x = (local_x + origin_x).astype(np.uint32)
                y = (local_y + origin_y + start).astype(np.uint32)
                thresholds = coordinate_hash32(x, y, _DISPLAY_SALT) / HASH32_MAX
                lower, remainder = np.divmod(rows[local_y, local_x], 257)
                converted[local_y, local_x] = lower + (thresholds[:, None] < remainder / 257)
        result[start:stop] = converted
    return result


def dither_resized_backdrop(
    rgb16: np.ndarray,
    alpha16: np.ndarray,
    resized_rgb8: np.ndarray,
    *,
    origin_xy: tuple[int, int] = (0, 0),
) -> np.ndarray:
    """Keep the existing thumbnail colors wherever the Lanczos footprint sees a subject."""
    if (
        alpha16.dtype != np.uint16
        or alpha16.shape != rgb16.shape[:2]
        or resized_rgb8.dtype != np.uint8
        or resized_rgb8.ndim != 3
        or resized_rgb8.shape[2] != 3
    ):
        raise ValueError("Backdrop preview requires aligned native alpha16 and RGB8 output")
    height, width = resized_rgb8.shape[:2]
    if rgb16.shape == resized_rgb8.shape:
        return result_rgb8(rgb16, backdrop_only=alpha16 == 0, origin_xy=origin_xy)

    native_height, native_width = alpha16.shape
    coverage = alpha16 != 0
    if coverage.any():
        # Lanczos has radius 3. Inspect the entire filter footprint using
        # categorical coverage so negative lobes cannot cancel a subject pixel.
        for axis, native, reduced in ((0, native_height, height), (1, native_width, width)):
            if native != reduced:
                radius = math.ceil(3 * max(1, native / reduced) + 0.5)
                maximum_filter1d(coverage, size=2 * radius + 1, axis=axis, output=coverage)
    rows = (2 * np.arange(height) + 1) * native_height // (2 * height)
    columns = (2 * np.arange(width) + 1) * native_width // (2 * width)
    backdrop = ~coverage[np.ix_(rows, columns)]
    if not backdrop.any():
        return resized_rgb8

    reduced16 = np.empty_like(resized_rgb8, dtype=np.uint16)
    for channel in range(3):
        with (
            Image.fromarray(rgb16[..., channel].astype(np.float32)) as plane,
            plane.resize((width, height), Image.Resampling.LANCZOS) as reduced,
        ):
            reduced16[..., channel] = np.rint(np.clip(np.asarray(reduced), 0, 65535))
    pixels = result_rgb8(reduced16, backdrop_only=backdrop)
    pixels[~backdrop] = resized_rgb8[~backdrop]
    return pixels
