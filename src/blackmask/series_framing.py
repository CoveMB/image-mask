"""Presentation-only, source-supported fixed-size series composition."""

import json
import math
import os
import stat
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image

from .assets import saved_asset
from .framing import validate_presentation_size
from .project import (
    ProjectError,
    _atomic_json,
    _json_bytes,
    _root,
    _validate_assets,
    check_space,
    digest,
    project_lock,
    read_project,
)
from .spatial_fade import (
    SpatialFadeOperands,
    _blend_background_channel,
    blend_background_float,
    spatial_fade_amount,
)

METADATA_LIMIT = 16384


@dataclass(frozen=True)
class SeriesSettings:
    name: str = "Portrait series"
    output_width_px: int = 4000
    output_height_px: int = 5000
    side_margin_tenths_percent: int = 150
    minimum_vertical_margin_tenths_percent: int = 50

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_series_settings(value: object) -> SeriesSettings:
    names = set(SeriesSettings().to_dict())
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError(
            "Series settings require exactly name, output dimensions and margin fields"
        )
    name = value["name"]
    if not isinstance(name, str) or not 1 <= len(name) <= 80 or not name.strip():
        raise ValueError("Series name must contain 1–80 Unicode characters and not be blank")
    try:
        name.encode("utf-8")
    except UnicodeError as error:
        raise ValueError("Series name must be valid Unicode text") from error
    width, height = value["output_width_px"], value["output_height_px"]
    validate_presentation_size((width, height))
    side, vertical = (
        value["side_margin_tenths_percent"],
        value["minimum_vertical_margin_tenths_percent"],
    )
    if any(type(item) is not int or not 0 <= item <= 450 for item in (side, vertical)):
        raise ValueError("Series margins must be integer tenths of a percent from 0 to 450")
    return SeriesSettings(name, width, height, side, vertical)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate series JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Nonfinite series JSON value")


def _parse_metadata(raw: bytes) -> object:
    if not isinstance(raw, bytes) or len(raw) > METADATA_LIMIT:
        raise ValueError("Series metadata exceeds 16384 bytes")
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Series metadata must be bounded UTF-8 JSON") from error


def parse_series_preset(raw: bytes) -> SeriesSettings:
    value = _parse_metadata(raw)
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "kind",
        *SeriesSettings().to_dict(),
    }:
        raise ValueError("Invalid portable series preset fields")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["kind"] != "series-framing-preset"
    ):
        raise ValueError("Unsupported portable series preset schema/kind")
    return validate_series_settings(
        {key: item for key, item in value.items() if key not in {"schema_version", "kind"}}
    )


def portable_series_preset(settings: SeriesSettings) -> bytes:
    settings = validate_series_settings(settings.to_dict())
    return _json_bytes({"schema_version": 1, "kind": "series-framing-preset", **settings.to_dict()})


def _bounded_file(path: Path) -> bytes:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Series preset symlink aliases are not allowed")
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Series preset must be a regular file")
        raw = stream.read(METADATA_LIMIT + 1)
    if len(raw) > METADATA_LIMIT:
        raise ValueError("Series metadata exceeds 16384 bytes")
    return raw


def read_series_preset_file(path: Path) -> SeriesSettings:
    return parse_series_preset(_bounded_file(path))


@dataclass(frozen=True)
class SeriesLayout:
    subject_bounds_xyxy: tuple[int, int, int, int]
    output_dimensions_wh: tuple[int, int]
    scale: float
    translation_xy: tuple[float, float]
    transformed_subject_bounds_xyxy: tuple[float, float, float, float]
    geometric_margins_lrtb_px: tuple[float, float, float, float]
    fit_reason: Literal["side-margins-matched", "height-limited"]
    source_edge_contact: bool

    def to_dict(self) -> dict[str, object]:
        return json.loads(json.dumps(asdict(self), allow_nan=False))


def compute_series_layout(alpha16: np.ndarray, settings: SeriesSettings) -> SeriesLayout:
    settings = validate_series_settings(settings.to_dict())
    if (
        not isinstance(alpha16, np.ndarray)
        or alpha16.dtype != np.uint16
        or alpha16.ndim != 2
        or min(alpha16.shape) < 1
    ):
        raise ValueError("Series layout requires a nonempty scalar uint16 mask")
    height, width = alpha16.shape
    x0, y0, x1, y1 = width, height, 0, 0
    for start in range(0, height, 64):
        positive = alpha16[start : start + 64] != 0
        columns = np.flatnonzero(positive.any(axis=0))
        rows = np.flatnonzero(positive.any(axis=1))
        if len(columns):
            x0, x1 = min(x0, int(columns[0])), max(x1, int(columns[-1]) + 1)
            y0, y1 = min(y0, start + int(rows[0])), max(y1, start + int(rows[-1]) + 1)
    if x1 == 0:
        raise ValueError(
            "Series framing needs positive alpha; review the native mask before framing"
        )
    output_width, output_height = settings.output_width_px, settings.output_height_px
    width_scale = (
        output_width * (1000 - 2 * settings.side_margin_tenths_percent) / (1000 * (x1 - x0))
    )
    height_scale = (
        output_height
        * (1000 - 2 * settings.minimum_vertical_margin_tenths_percent)
        / (1000 * (y1 - y0))
    )
    scale = min(width_scale, height_scale)
    left, top = (output_width - scale * (x1 - x0)) / 2, (output_height - scale * (y1 - y0)) / 2
    tx, ty = left - scale * x0, top - scale * y0
    if not all(math.isfinite(value) for value in (scale, tx, ty)) or scale <= 0:
        raise ValueError("Invalid series layout transform")
    return SeriesLayout(
        (x0, y0, x1, y1),
        (output_width, output_height),
        scale,
        (tx, ty),
        (left, top, output_width - left, output_height - top),
        (left, left, top, top),
        "height-limited" if height_scale < width_scale else "side-margins-matched",
        x0 == 0 or y0 == 0 or x1 == width or y1 == height,
    )


@dataclass(frozen=True)
class SamplingAxis:
    core_length: int
    output_start: int
    output_length: int
    ideal_start: float
    spacing: float
    padding_origin: int
    padded_extent: int
    box: tuple[float, float]
    maximum_output_phase_error: float
    coefficient_bytes: int


@dataclass(frozen=True)
class SeriesSamplingPlan:
    layout: SeriesLayout
    display_dimensions_wh: tuple[int, int]
    x: SamplingAxis
    y: SamplingAxis
    horizontal_first: bool
    identity: bool

    def to_dict(self) -> dict[str, object]:
        return json.loads(json.dumps(asdict(self), allow_nan=False))


def _sampling_axis(
    start: int, stop: int, scale: float, translation: float, extent: int, full_scale: float
) -> SamplingAxis:
    if (
        not all(math.isfinite(value) for value in (scale, translation, full_scale))
        or scale <= 0
        or start < 0
        or stop <= start
    ):
        raise ValueError("Invalid series sampling geometry")
    radius = 3 * max(1, scale)
    output_start = max(0, math.floor(scale * start + translation - radius))
    output_stop = min(extent, math.ceil(scale * stop + translation + radius))
    length = output_stop - output_start
    if length < 1:
        raise ValueError("Series sampling support does not intersect the output")
    ideal_start = (output_start - translation) / scale - start
    ideal_stop = (output_stop - translation) / scale - start
    support = 3 * max(1, 1 / scale)
    origin = math.floor(min(0, ideal_start - support)) - 1
    end = math.ceil(max(stop - start, ideal_stop + support)) + 1
    padded = end - origin
    if padded >= 2**31:
        raise ValueError("Series sampling exceeds Pillow integer bounds")
    box = (ideal_start - origin, ideal_stop - origin)
    first, last = (float(np.float32(value)) for value in box)
    spacing = float(np.float32(last - first)) / length
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError("Series sampling source box lost its extent")
    effective_support = 3 * max(1, spacing)
    if (
        first + 0.5 * spacing - effective_support < 0
        or first + (length - 0.5) * spacing + effective_support > padded
    ):
        # The extra whole transparent sample protects float-box rounding too.
        raise ValueError("Series sampling lacks complete transparent filter support")
    kernel = 2 * math.ceil(effective_support) + 1
    coefficients = 8 * length * (kernel + 1)
    if kernel > (2**31 - 1) // 8 or 8 * length * kernel > 2**31 - 1:
        raise ValueError("Series coefficient allocation exceeds Pillow integer bounds")
    error = (
        max(
            abs(first + (i + 0.5) * spacing + origin - (ideal_start + (i + 0.5) / scale))
            for i in (0, length - 1)
        )
        * full_scale
    )
    if error > 1 / 64:
        raise ValueError("Series sampling exceeds 1/64 output-pixel phase error")
    return SamplingAxis(
        stop - start,
        output_start,
        length,
        ideal_start,
        1 / scale,
        origin,
        padded,
        box,
        error,
        coefficients,
    )


def series_sampling_plan(
    layout: SeriesLayout, *, display_dimensions_wh: tuple[int, int] | None = None
) -> SeriesSamplingPlan:
    width, height = validate_presentation_size(layout.output_dimensions_wh)
    display = (
        layout.output_dimensions_wh
        if display_dimensions_wh is None
        else validate_presentation_size(display_dimensions_wh)
    )
    if display_dimensions_wh is not None and max(display) > 1600:
        raise ValueError("Series preview long edge must not exceed 1600")
    x0, y0, x1, y1 = layout.subject_bounds_xyxy
    tx, ty = layout.translation_xy
    x = _sampling_axis(
        x0, x1, layout.scale * display[0] / width, tx * display[0] / width, display[0], layout.scale
    )
    y = _sampling_axis(
        y0,
        y1,
        layout.scale * display[1] / height,
        ty * display[1] / height,
        display[1],
        layout.scale,
    )
    horizontal_first = x.output_length * y.core_length <= y.output_length * x.core_length
    intermediate = (
        x.output_length * y.core_length if horizontal_first else y.output_length * x.core_length
    )
    if intermediate > sys.maxsize // 4:
        raise ValueError("Series sampling intermediate exceeds allocation bounds")
    identity = (
        display == layout.output_dimensions_wh
        and layout.scale == 1
        and tx.is_integer()
        and ty.is_integer()
    )
    return SeriesSamplingPlan(layout, display, x, y, horizontal_first, identity)


def estimate_series_resources(
    sampling: SeriesSamplingPlan,
    *,
    retained_native_bytes: int,
    transparent: bool,
    spatial_fade_pixels: int = 0,
    native_export_peak_bytes: int = 0,
) -> dict[str, int]:
    if (
        type(retained_native_bytes) is not int
        or retained_native_bytes < 0
        or type(transparent) is not bool
        or type(spatial_fade_pixels) is not int
        or spatial_fade_pixels < 0
        or type(native_export_peak_bytes) is not int
        or native_export_peak_bytes < 0
    ):
        raise ValueError("Invalid series resource inputs")
    x, y = sampling.x, sampling.y
    first, second = (x, y) if sampling.horizontal_first else (y, x)
    strip = min(64, max(first.output_length, second.core_length))
    intermediate = first.output_length * second.core_length
    scratch = max(
        12 * (first.padded_extent + first.output_length) * min(64, second.core_length)
        + 64 * first.core_length * min(64, second.core_length),
        12 * (second.padded_extent + second.output_length) * min(64, first.output_length),
    )
    coefficients = max(first.coefficient_bytes, second.coefficient_bytes) + 64 * strip
    width, height = sampling.display_dimensions_wh
    values = {
        "retained_native_bytes": retained_native_bytes,
        "output_rgb16_bytes": 6 * width * height,
        "output_rgba8_bytes": 4 * width * height if transparent else 0,
        "filtered_alpha_bytes": 4 * x.output_length * y.output_length,
        "scalar_intermediate_bytes": 4 * intermediate,
        "strip_transfer_and_native_scratch_bytes": scratch,
        "coefficient_bytes": coefficients,
        "row_and_allocator_headroom_bytes": 2 * 1024**2 + 64 * 256 * max(width, height),
    }
    if spatial_fade_pixels:
        values.update(
            native_spatial_amount_bytes=8 * spatial_fade_pixels,
            filtered_spatial_amount_bytes=4 * x.output_length * y.output_length,
            spatial_blend_tile_bytes=64 * max(width, height) * 128,
            spatial_transparent_rgba_bytes=4 * width * height if transparent else 0,
        )
    series_peak = sum(value for key, value in values.items() if key != "output_rgba8_bytes")
    if native_export_peak_bytes:
        values["native_export_peak_bytes"] = native_export_peak_bytes
    values["estimated_peak_bytes"] = max(series_peak, native_export_peak_bytes)
    if values["estimated_peak_bytes"] > sys.maxsize:
        raise ValueError("Series sampling resource estimate exceeds allocation bounds")
    return values


def _resize_rows(core: np.ndarray, axis: SamplingAxis) -> np.ndarray:
    padded = np.zeros((core.shape[0], axis.padded_extent), np.float32)
    offset = -axis.padding_origin
    padded[:, offset : offset + axis.core_length] = core
    image = Image.fromarray(padded)
    del padded
    resized = None
    try:
        resized = image.resize(
            (axis.output_length, core.shape[0]),
            Image.Resampling.LANCZOS,
            box=(axis.box[0], 0, axis.box[1], core.shape[0]),
            reducing_gap=None,
        )
        return np.array(resized, dtype=np.float32)
    finally:
        image.close()
        if resized is not None:
            resized.close()


def _plane_tiles(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    sampling: SeriesSamplingPlan,
    plane: int,
    weight16: np.ndarray | None,
    opacity: float,
    spatial_amount: np.ndarray | None = None,
) -> Iterator[tuple[slice, slice, np.ndarray]]:
    from .export import _foreground_contribution

    x0, y0, x1, y1 = sampling.layout.subject_bounds_xyxy
    foreground_core = foreground[y0:y1, x0:x1]
    alpha_core = alpha16[y0:y1, x0:x1]
    weight_core = None if weight16 is None else weight16[y0:y1, x0:x1]
    amount_core = None if spatial_amount is None else spatial_amount[y0:y1, x0:x1]
    if not sampling.horizontal_first:
        foreground_core = foreground_core.transpose(1, 0, 2)
        alpha_core = alpha_core.T
        weight_core = None if weight_core is None else weight_core.T
        amount_core = None if amount_core is None else amount_core.T
    first, second = (
        (sampling.x, sampling.y) if sampling.horizontal_first else (sampling.y, sampling.x)
    )
    intermediate = np.empty((second.core_length, first.output_length), np.float32)
    try:
        for start in range(0, second.core_length, 64):
            rows = slice(start, min(start + 64, second.core_length))
            if plane == -1:
                source = alpha_core[rows].astype(np.float64) / 65535
            elif plane == -2:
                if amount_core is None:
                    raise ValueError("Series amount sampling requires the combined native q field")
                source = alpha_core[rows].astype(np.float64) / 65535 * amount_core[rows]
            else:
                contribution = _foreground_contribution(
                    foreground_core[rows],
                    alpha_core[rows],
                    None if weight_core is None else weight_core[rows],
                    opacity,
                )
                source = contribution[..., plane]
            intermediate[rows] = _resize_rows(source, first)
            del source
            if plane >= 0:
                del contribution
        for start in range(0, first.output_length, 64):
            columns = slice(start, min(start + 64, first.output_length))
            tile = _resize_rows(intermediate[:, columns].T, second).T
            if sampling.horizontal_first:
                yield slice(0, second.output_length), columns, tile
            else:
                yield columns, slice(0, second.output_length), tile.T
    finally:
        del intermediate


def render_series(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    sampling: SeriesSamplingPlan,
    *,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    background_settings: dict[str, Any] | None = None,
    transparent: bool = False,
    spatial_fade: SpatialFadeOperands | None = None,
) -> np.ndarray:
    from .background import LEGACY_BACKGROUND, make_background, sample_background
    from .export import _foreground_contribution

    if (
        type(transparent) is not bool
        or not isinstance(foreground, np.ndarray)
        or foreground.dtype != np.uint16
        or foreground.ndim != 3
        or foreground.shape[2] != 3
        or alpha16.dtype != np.uint16
        or alpha16.shape != foreground.shape[:2]
    ):
        raise ValueError("Series rendering requires aligned saved RGB16 and alpha16")
    if weight16 is not None and (weight16.dtype != np.uint16 or weight16.shape != alpha16.shape):
        raise ValueError("Series shading requires aligned W16")
    if sampling != series_sampling_plan(
        sampling.layout,
        display_dimensions_wh=None
        if sampling.display_dimensions_wh == sampling.layout.output_dimensions_wh
        else sampling.display_dimensions_wh,
    ):
        raise ValueError("Invalid series sampling plan")
    if (
        compute_series_layout(alpha16, SeriesSettings()).subject_bounds_xyxy
        != sampling.layout.subject_bounds_xyxy
    ):
        raise ValueError("Series sampling mask bounds are stale")
    _foreground_contribution(
        foreground[:1, :1], alpha16[:1, :1], None if weight16 is None else weight16[:1, :1], opacity
    )
    active_spatial = (
        spatial_fade is not None
        and spatial_fade.record["enabled"]
        and not spatial_fade.record["stale"]
    )
    if active_spatial and opacity != 0:
        raise ValueError("Spatial fade and inward shading are mutually exclusive")
    estimate_series_resources(
        sampling,
        retained_native_bytes=foreground.nbytes
        + alpha16.nbytes
        + (0 if weight16 is None else weight16.nbytes)
        + (
            spatial_fade.weight16.nbytes + spatial_fade.protection.nbytes
            if active_spatial and spatial_fade is not None
            else 0
        ),
        transparent=transparent,
        **({"spatial_fade_pixels": alpha16.size} if active_spatial else {}),
    )
    native_amount = (
        spatial_fade_amount(foreground, alpha16, spatial_fade)
        if active_spatial and spatial_fade is not None
        else None
    )
    if native_amount is not None and not native_amount.any():
        native_amount = None
    width, height = sampling.display_dimensions_wh
    settings = LEGACY_BACKGROUND if background_settings is None else background_settings
    if transparent:
        result = np.zeros((height, width, 4), np.uint8)
    elif sampling.display_dimensions_wh == sampling.layout.output_dimensions_wh:
        result = make_background((height, width), settings)
    else:
        output_width, output_height = sampling.layout.output_dimensions_wh
        result = sample_background((output_height, output_width), settings, (width, height))
    target = None
    if native_amount is not None:
        if not transparent:
            target = result
        elif sampling.display_dimensions_wh == sampling.layout.output_dimensions_wh:
            target = make_background((height, width), settings)
        else:
            output_width, output_height = sampling.layout.output_dimensions_wh
            target = sample_background((output_height, output_width), settings, (width, height))
    x, y = sampling.x, sampling.y
    x0, y0, x1, y1 = sampling.layout.subject_bounds_xyxy
    if sampling.identity:
        tx, ty = (int(value) for value in sampling.layout.translation_xy)
        for start in range(y0, y1, 64):
            stop = min(start + 64, y1)
            rows, columns = slice(start + ty, stop + ty), slice(x0 + tx, x1 + tx)
            alpha = alpha16[start:stop, x0:x1].astype(np.float64) / 65535
            contribution = _foreground_contribution(
                foreground[start:stop, x0:x1],
                alpha16[start:stop, x0:x1],
                None if weight16 is None else weight16[start:stop, x0:x1],
                opacity,
            )
            if native_amount is not None and target is not None:
                contribution = (
                    blend_background_float(
                        foreground[start:stop, x0:x1],
                        target[rows, columns],
                        native_amount[start:stop, x0:x1],
                    )
                    * alpha[..., None]
                )
            if transparent:
                result[rows, columns, 3] = np.rint(alpha * 255).astype(np.uint8)
                np.divide(
                    contribution, alpha[..., None], out=contribution, where=alpha[..., None] > 0
                )
                result[rows, columns, :3] = np.rint(contribution / 257).astype(np.uint8)
                region = result[rows, columns]
                region[region[..., 3] == 0, :3] = 0
            else:
                result[rows, columns] = np.rint(
                    contribution + result[rows, columns].astype(np.float64) * (1 - alpha[..., None])
                ).astype(np.uint16)
        return result
    alpha = np.empty((y.output_length, x.output_length), np.float32)
    for rows, columns, tile in _plane_tiles(foreground, alpha16, sampling, -1, weight16, opacity):
        if not np.isfinite(tile).all():
            raise ValueError("Nonfinite series alpha samples")
        alpha[rows, columns] = np.clip(tile, 0, 1)
    filtered_amount = None
    if native_amount is not None:
        filtered_amount = np.empty_like(alpha)
        for rows, columns, tile in _plane_tiles(
            foreground, alpha16, sampling, -2, weight16, opacity, native_amount
        ):
            if not np.isfinite(tile).all():
                raise ValueError("Nonfinite series spatial amount samples")
            filtered_amount[rows, columns] = np.clip(tile, 0, alpha[rows, columns])
        native_amount = None
    if transparent:
        for start in range(0, y.output_length, 64):
            stop = min(start + 64, y.output_length)
            result[
                y.output_start + start : y.output_start + stop,
                x.output_start : x.output_start + x.output_length,
                3,
            ] = np.rint(alpha[start:stop].astype(np.float64) * 255).astype(np.uint8)
    for channel in range(3):
        for rows, columns, tile in _plane_tiles(
            foreground, alpha16, sampling, channel, weight16, opacity
        ):
            if not np.isfinite(tile).all():
                raise ValueError("Nonfinite series colour samples")
            bounded_alpha = alpha[rows, columns].astype(np.float64)
            contribution = np.clip(tile.astype(np.float64), 0, 65535 * bounded_alpha)
            target_rows = slice(rows.start + y.output_start, rows.stop + y.output_start)
            target_columns = slice(columns.start + x.output_start, columns.stop + x.output_start)
            if filtered_amount is not None and target is not None:
                ratio = np.divide(
                    filtered_amount[rows, columns].astype(np.float64),
                    bounded_alpha,
                    out=np.zeros_like(bounded_alpha),
                    where=bounded_alpha > 0,
                )
                straight = np.divide(
                    contribution,
                    bounded_alpha,
                    out=np.zeros_like(contribution),
                    where=bounded_alpha > 0,
                )
                faded = _blend_background_channel(
                    straight, target[target_rows, target_columns, channel], ratio
                )
                if transparent:
                    result[target_rows, target_columns, channel] = np.rint(faded / 257).astype(
                        np.uint8
                    )
                    continue
                else:
                    changed = ratio != 0
                    contribution[changed] = faded[changed] * bounded_alpha[changed]
            if transparent:
                np.divide(contribution, bounded_alpha, out=contribution, where=bounded_alpha > 0)
                result[target_rows, target_columns, channel] = np.rint(contribution / 257).astype(
                    np.uint8
                )
            else:
                backdrop = result[target_rows, target_columns, channel].astype(np.float64)
                result[target_rows, target_columns, channel] = np.rint(
                    contribution + backdrop * (1 - bounded_alpha)
                ).astype(np.uint16)
    if transparent:
        for start in range(0, height, 64):
            rgba_rows = result[start : start + 64]
            rgba_rows[rgba_rows[..., 3] == 0, :3] = 0
    return result


def read_series_settings(
    project: Path, developed_id: str, source_size: tuple[int, int]
) -> tuple[SeriesSettings, str | None]:
    """Read an optional source-bound snapshot without modifying the project."""
    path = saved_asset(_root(project), "series-framing.json")
    try:
        raw = _bounded_file(path)
    except FileNotFoundError:
        return SeriesSettings(), None
    try:
        value = _parse_metadata(raw)
        if (
            not isinstance(value, dict)
            or set(value) != {"schema_version", "developed_id", "source_dimensions_wh", "settings"}
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 2
            or value["developed_id"] != developed_id
            or not isinstance(value["source_dimensions_wh"], list)
            or any(type(item) is not int for item in value["source_dimensions_wh"])
            or value["source_dimensions_wh"] != list(source_size)
        ):
            raise ValueError("Wrong series schema, source identity or dimensions")
        return validate_series_settings(value["settings"]), digest(raw)
    except (ValueError, TypeError, KeyError) as error:
        raise ProjectError(
            f"Invalid series-framing.json; preserve it for explicit recovery: {error}"
        ) from error


class SeriesSaveUncertain(ProjectError):
    """Visible settings must be reloaded after uncertain post-replace durability."""

    def __init__(self, visible: dict[str, object]):
        self.visible = {**visible, "series_reload_required": True}
        super().__init__(
            "Series save durability unconfirmed; visible series-framing.json may have changed. Keep edits and Reload saved series settings before saving again."
        )


def save_series_settings(
    project: Path,
    value: dict[str, object],
    *,
    expected_digest: str | None,
    expected_developed_id: str,
) -> dict[str, object]:
    """Explicit source-bound raw-byte CAS under the canonical project writer lock."""
    if expected_digest is not None and (
        not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise ProjectError("Expected series digest must be SHA-256 or null for an absent preset")
    settings = validate_series_settings(value)
    project = _root(project)
    with project_lock(project):
        source_bytes = saved_asset(project, "source.json").read_bytes()
        state = read_project(project, validate_drafts=False)
        if state["developed_id"] != expected_developed_id:
            raise ProjectError("Stale series source identity; reload the photo")
        source, _ = _validate_assets(project, state, validate_drafts=False)
        source_size = (source.shape[1], source.shape[0])
        del source
        previous, previous_digest = read_series_settings(
            project, expected_developed_id, source_size
        )
        if previous_digest != expected_digest:
            raise ProjectError("Stale series settings; Reload saved series settings before saving")
        if previous_digest is not None and previous == settings:
            return {"series_settings": settings.to_dict(), "series_digest": previous_digest}
        envelope = {
            "schema_version": 2,
            "developed_id": expected_developed_id,
            "source_dimensions_wh": list(source_size),
            "settings": settings.to_dict(),
        }

        def unchanged() -> None:
            if saved_asset(project, "source.json").read_bytes() != source_bytes:
                raise ProjectError("Stale series source before publication")
            if (
                read_project(project, validate_drafts=False)["developed_id"]
                != expected_developed_id
            ):
                raise ProjectError("Stale series master before publication")
            if (
                read_series_settings(project, expected_developed_id, source_size)[1]
                != previous_digest
            ):
                raise ProjectError("Stale series settings before publication")

        check_space(project, 1024**2)
        try:
            _atomic_json(
                saved_asset(project, "series-framing.json"),
                envelope,
                validate_before_replace=unchanged,
            )
        except (OSError, ValueError) as error:
            try:
                visible, visible_digest = read_series_settings(
                    project, expected_developed_id, source_size
                )
            except (ProjectError, OSError):
                observed: dict[str, object] = {"series_settings": None, "series_digest": None}
            else:
                if visible_digest == previous_digest:
                    raise ProjectError(
                        f"Series save failed; saved settings unchanged: {error}"
                    ) from error
                observed = {"series_settings": visible.to_dict(), "series_digest": visible_digest}
            raise SeriesSaveUncertain(observed) from error
        return {
            "series_settings": settings.to_dict(),
            "series_digest": digest(_json_bytes(envelope)),
        }
