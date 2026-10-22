"""Resolve a three-channel DNG's recorded white point without guessing daylight.

Only primary-profile, single/dual/triple-illuminant RGB DNG metadata is supported.
The caller retains ownership of RAW recognition, development and orientation.

Robertson isotemperature data below is from Colour v0.4.6, BSD-3-Clause:
https://github.com/colour-science/colour/blob/v0.4.6/colour/temperature/robertson1968.py
Copyright 2013 Colour Developers

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import io
import struct
from typing import Any

import numpy as np
import numpy.typing as npt
import tifffile

FloatArray = npt.NDArray[np.float64]

# Reciprocal megakelvin, CIE 1960 u/v, isotherm slope. Includes the published
# 325-mired correction (u=0.24792); no Colour package is imported or required.
_ROBERTSON_LINES = np.array(
    [
        (0, 0.18006, 0.26352, -0.24341),
        (10, 0.18066, 0.26589, -0.25479),
        (20, 0.18133, 0.26846, -0.26876),
        (30, 0.18208, 0.27119, -0.28539),
        (40, 0.18293, 0.27407, -0.30470),
        (50, 0.18388, 0.27709, -0.32675),
        (60, 0.18494, 0.28021, -0.35156),
        (70, 0.18611, 0.28342, -0.37915),
        (80, 0.18740, 0.28668, -0.40955),
        (90, 0.18880, 0.28997, -0.44278),
        (100, 0.19032, 0.29326, -0.47888),
        (125, 0.19462, 0.30141, -0.58204),
        (150, 0.19962, 0.30921, -0.70471),
        (175, 0.20525, 0.31647, -0.84901),
        (200, 0.21142, 0.32312, -1.0182),
        (225, 0.21807, 0.32909, -1.2168),
        (250, 0.22511, 0.33439, -1.4512),
        (275, 0.23247, 0.33904, -1.7298),
        (300, 0.24010, 0.34308, -2.0637),
        (325, 0.24792, 0.34655, -2.4681),
        (350, 0.25591, 0.34951, -2.9641),
        (375, 0.26400, 0.35200, -3.5814),
        (400, 0.27218, 0.35407, -4.3633),
        (425, 0.28039, 0.35577, -5.3762),
        (450, 0.28863, 0.35714, -6.7262),
        (475, 0.29685, 0.35823, -8.5955),
        (500, 0.30505, 0.35907, -11.324),
        (525, 0.31320, 0.35968, -15.628),
        (550, 0.32129, 0.36011, -23.325),
        (575, 0.32931, 0.36038, -40.770),
        (600, 0.33724, 0.36051, -116.45),
    ],
    dtype=np.float64,
)


def _temperature_tint(white_xy: FloatArray) -> tuple[float, float]:
    """Robertson coordinates select a blend, never a replacement white point."""
    x, y = white_xy
    denominator = 1.5 - x + 6 * y
    u, v = 2 * x / denominator, 3 * y / denominator
    mired, line_u, line_v, slope = _ROBERTSON_LINES.T
    distances = ((v - line_v) - slope * (u - line_u)) / np.hypot(1, slope)
    crossings = np.flatnonzero(distances[1:] <= 0)
    index = int(crossings[0] + 1) if crossings.size else len(mired) - 1
    distance = max(-float(distances[index]), 0.0)
    weight = distance / (float(distances[index - 1]) + distance) if index > 1 else 0.0
    temperature = float(1e6 / (weight * mired[index - 1] + (1 - weight) * mired[index]))
    lengths = np.hypot(1, slope[index - 1 : index + 1])
    directions = np.column_stack((1 / lengths, slope[index - 1 : index + 1] / lengths))
    direction = weight * directions[0] + (1 - weight) * directions[1]
    direction /= np.linalg.norm(direction)
    origin = weight * _ROBERTSON_LINES[index - 1, 1:3] + (1 - weight) * _ROBERTSON_LINES[index, 1:3]
    tint = float(-3000 * ((np.array([u, v]) - origin) @ direction))
    return temperature, tint


def _illuminant_code(tags: tifffile.TiffTags, code: int) -> int:
    tag = tags.get(code)
    if tag is None or tag.dtype != 3 or tag.count != 1:
        raise ValueError("DNG white balance requires calibration illuminants")
    return int(tag.value)


def _illuminant_white_xy(tags: tifffile.TiffTags, code: int, byteorder: str) -> FloatArray:
    illuminant = _illuminant_code(tags, code)
    white_points = {
        1: (0.3324, 0.3474),
        2: (0.37208, 0.37529),
        3: (0.4476, 0.4074),
        4: (0.3324, 0.3474),
        9: (0.3324, 0.3474),
        10: (0.3127, 0.3290),
        11: (0.2990, 0.3149),
        12: (0.31310, 0.33727),
        13: (0.34588, 0.35875),
        14: (0.37417, 0.37281),
        15: (0.40910, 0.39430),
        16: (0.44018, 0.40329),
        17: (0.4476, 0.4074),
        18: (0.348483, 0.351747),
        19: (0.310061, 0.316150),
        20: (0.3324, 0.3474),
        21: (0.3127, 0.3290),
        22: (0.2990, 0.3149),
        23: (0.3457, 0.3585),
    }
    if illuminant in white_points:
        return np.array(white_points[illuminant])
    if illuminant != 255:
        raise ValueError("DNG white balance has an unsupported calibration illuminant")
    data_code = {50778: 52533, 50779: 52534, 52529: 52535}[code]
    tag = tags.get(data_code)
    if tag is None or tag.dtype != 7 or tag.count != 18 or not isinstance(tag.value, bytes):
        raise ValueError(
            "DNG white balance requires custom illuminant xy data (spectral data unsupported)"
        )
    kind, numerator_x, denominator_x, numerator_y, denominator_y = struct.unpack(
        byteorder + "HIIII", tag.value
    )
    if kind != 0 or denominator_x == 0 or denominator_y == 0:
        raise ValueError("DNG white balance has unsupported or invalid custom illuminant data")
    white = np.array([numerator_x / denominator_x, numerator_y / denominator_y])
    if (white <= 0).any() or white.sum() >= 1:
        raise ValueError("DNG white balance has invalid custom illuminant chromaticity")
    return white


def _illuminant_temperature(
    tags: tifffile.TiffTags, code: int, byteorder: str
) -> tuple[int, float]:
    illuminant = _illuminant_code(tags, code)
    temperatures = {
        1: 5500,
        2: 4150,
        3: 2850,
        4: 5500,
        9: 5500,
        10: 6500,
        11: 7500,
        12: 6400,
        13: 5050,
        14: 4150,
        15: 3525,
        16: 2925,
        17: 2850,
        18: 5500,
        19: 6500,
        20: 5500,
        21: 6500,
        22: 7500,
        23: 5000,
        24: 3200,
    }
    if illuminant == 255:
        temperature, _ = _temperature_tint(_illuminant_white_xy(tags, code, byteorder))
        return illuminant, temperature
    if illuminant not in temperatures:
        raise ValueError("DNG white balance requires recognized calibration illuminants")
    return illuminant, float(temperatures[illuminant])


def _triple_weights(white_xy: FloatArray, lights: list[FloatArray]) -> FloatArray:
    """DNG 1.6 distance, smoothing and suppression in scaled temperature/tint."""
    positions = np.array([_temperature_tint(white) for white in [white_xy, *lights]])
    positions[:, 0] = np.minimum(1500 / positions[:, 0], 1)
    positions[:, 1] /= 200
    squared_distances = np.sum((positions[1:] - positions[0]) ** 2, axis=1)
    weights = 1 / (squared_distances + 1e-8)
    weights /= weights.sum()
    weights = weights * weights * (3 - 2 * weights)
    weights = np.clip((weights - 0.02) / 0.98, 0, 1)
    weights /= weights.sum()
    return weights


def _rationals(
    tags: tifffile.TiffTags, code: int, count: int, default: FloatArray | None = None
) -> FloatArray:
    tag = tags.get(code)
    if tag is None:
        if default is not None:
            return default
        raise ValueError(f"DNG white balance requires {tifffile.TIFF.TAGS[code]}")
    if tag.count != count or tag.dtype not in {5, 10}:
        raise ValueError(f"DNG white balance has malformed {tag.name}")
    values = np.asarray(tag.value, dtype=np.float64)
    if values.shape != (2 * count,) or not np.isfinite(values).all():
        raise ValueError(f"DNG white balance has malformed {tag.name}")
    if (values[1::2] == 0).any():
        raise ValueError(f"DNG white balance has zero denominator in {tag.name}")
    return values[::2] / values[1::2]


def _matrix(tags: tifffile.TiffTags, code: int, *, optional: bool = False) -> FloatArray:
    values = _rationals(tags, code, 9, np.eye(3).ravel() if optional else None).reshape(3, 3)
    if np.linalg.matrix_rank(values) != 3:
        raise ValueError(f"DNG white balance has singular {tifffile.TIFF.TAGS[code]}")
    return values


def _text(tags: tifffile.TiffTags, code: int) -> str:
    tag = tags.get(code)
    if tag is None:
        return ""
    if tag.dtype not in {1, 2} or tag.count > 4096:
        raise ValueError(f"DNG white balance has malformed {tag.name}")
    value = tag.value
    if isinstance(value, bytes):
        try:
            value = value.rstrip(b"\0").decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"DNG white balance has malformed {tag.name}") from error
    if not isinstance(value, str) or "\0" in value:
        raise ValueError(f"DNG white balance has malformed {tag.name}")
    return value


def _color_matrix(tags: tifffile.TiffTags, code: int) -> FloatArray:
    matrix = _matrix(tags, code)
    # DNG SDK profile normalization: comparable D50 scales before interpolation.
    d50 = np.array([0.3457 / 0.3585, 1.0, (1 - 0.3457 - 0.3585) / 0.3585])
    maximum = float(np.max(matrix @ d50))
    if maximum <= 0:
        raise ValueError("DNG white balance has no positive D50 profile response")
    if not 0.99 <= maximum <= 1.01:
        matrix = matrix / maximum
    matrix = np.floor(matrix * 10000 + 0.5) / 10000
    if np.linalg.matrix_rank(matrix) != 3:
        raise ValueError("DNG white balance has degenerate normalized color matrix")
    return matrix


def dng_as_shot_white_balance(data: bytes) -> dict[str, Any] | None:
    """Return explicit RGBG multipliers/provenance, or None without this DNG tag.

    Invalid, ambiguous and unsupported tagged inputs fail before RAW processing.
    CameraCalibration applies only to a profile with the matching signature.
    """
    if data[:4] not in {b"II*\x00", b"MM\x00*"}:
        return None
    try:
        with tifffile.TiffFile(io.BytesIO(data)) as image:
            page = image.pages[0]
            if not isinstance(page, tifffile.TiffPage):
                raise TypeError("DNG white balance requires a supported primary IFD")
            tags = page.tags
            if 50706 not in tags or 50729 not in tags:
                return None
            consumed_codes = {
                50706,
                50721,
                50722,
                50723,
                50724,
                50727,
                50728,
                50729,
                50778,
                50779,
                50879,
                50931,
                50932,
                50934,
                50936,
                52529,
                52530,
                52531,
                52533,
                52534,
                52535,
            }
            seen = set()
            for tag in tags.values():
                if tag.code in consumed_codes:
                    if tag.code in seen:
                        raise ValueError(f"DNG white balance has duplicate {tag.name}")
                    seen.add(tag.code)
            if tags[50706].dtype != 1 or tags[50706].count != 4 or tags[50706].value[:1] != b"\x01":
                raise ValueError("DNG white balance requires supported DNG version 1")
            if 50728 in tags:
                raise ValueError("DNG white balance has both AsShotNeutral and AsShotWhiteXY")
            if 52531 in tags and 50722 not in tags:
                raise ValueError("DNG white balance has a third color matrix without a second")
            if 50879 in tags and tags[50879].value != 0:
                raise ValueError("DNG white balance requires a scene-referred color profile")
            as_shot_profile = _text(tags, 50934)
            if as_shot_profile and as_shot_profile != _text(tags, 50936):
                raise ValueError("DNG white balance supports only the primary profile")
            white_xy = _rationals(tags, 50729, 2)
            x, y = white_xy
            if x <= 0 or y <= 0 or x + y >= 1:
                raise ValueError("DNG white balance has an invalid AsShotWhiteXY chromaticity")
            analog_balance = _rationals(tags, 50727, 3, np.ones(3))
            if (analog_balance <= 0).any():
                raise ValueError("DNG white balance requires positive AnalogBalance")
            matching_calibration = _text(tags, 50931) == _text(tags, 50932)
            color_codes = (
                [50721] + ([50722] if 50722 in tags else []) + ([52531] if 52531 in tags else [])
            )
            weights = np.ones(1)
            interpolation: dict[str, Any] = {}
            if len(color_codes) == 3:
                light_codes = [50778, 50779, 52529]
                lights = [_illuminant_white_xy(tags, code, image.byteorder) for code in light_codes]
                if any(np.array_equal(lights[i], lights[j]) for i in range(3) for j in range(i)):
                    raise ValueError("DNG white balance has duplicate calibration white points")
                weights = _triple_weights(white_xy, lights)
                interpolation = {
                    "calibration_illuminants": [
                        _illuminant_code(tags, code) for code in light_codes
                    ],
                }
            elif len(color_codes) == 2:
                illuminant1, temperature1 = _illuminant_temperature(tags, 50778, image.byteorder)
                illuminant2, temperature2 = _illuminant_temperature(tags, 50779, image.byteorder)
                if temperature1 == temperature2:
                    raise ValueError(
                        "DNG white balance has indistinguishable calibration illuminants"
                    )
                temperature, _ = _temperature_tint(white_xy)
                weight = float(
                    np.clip(
                        (1 / temperature - 1 / temperature2)
                        / (1 / temperature1 - 1 / temperature2),
                        0,
                        1,
                    )
                )
                weights = np.array([weight, 1 - weight])
                interpolation = {
                    "temperature_kelvin": temperature,
                    "calibration_illuminants": [illuminant1, illuminant2],
                }
            color_matrix = np.zeros((3, 3))
            for weight, color_code, calibration_code in zip(
                weights, color_codes, (50723, 50724, 52530)
            ):
                calibration = _matrix(tags, calibration_code, optional=True)
                if not matching_calibration:
                    calibration = np.eye(3)
                # Each calibration is combined with its own matrix before blending.
                color_matrix += (
                    weight * np.diag(analog_balance) @ calibration @ _color_matrix(tags, color_code)
                )
            neutral = color_matrix @ np.array([x / y, 1.0, (1 - x - y) / y])
            if not np.isfinite(neutral).all() or (neutral <= 0).any():
                raise ValueError("DNG white balance has a non-positive camera neutral")
            multipliers = neutral[1] / neutral
            if not np.isfinite(multipliers).all() or np.max(multipliers) > np.finfo(np.float32).max:
                raise ValueError("DNG white balance multipliers exceed the RAW reader range")
            return {
                "source": "DNG AsShotWhiteXY",
                "algorithm": "dng-as-shot-white-xy-v1",
                "white_xy": white_xy.tolist(),
                "multipliers": [float(multipliers[0]), 1.0, float(multipliers[2]), 1.0],
                "matching_calibration": matching_calibration,
                "calibration_weights": weights.tolist(),
                **interpolation,
            }
    except (
        tifffile.TiffFileError,
        IndexError,
        KeyError,
        TypeError,
        np.linalg.LinAlgError,
    ) as error:
        raise ValueError("DNG white balance metadata cannot be interpreted safely") from error
