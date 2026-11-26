"""Deterministic pixel-grid math for saved effects and composed RGB8 views."""

import numpy as np

HASH32_MAX = 2**32 - 1
BACKDROP_DITHER_PNG_SUFFIX = "+backdrop-coordinate-dither-v1"
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
