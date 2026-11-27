"""Versioned spatial-light Cloud fields and linear-sRGB compositing."""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from .exposure import linear_to_rgb16, srgb_to_linear
from .guidance import rasterize_regions
from .mist import MAX_SEED, ROWS_PER_CHUNK, _number, _smoothstep, _value_noise, validate_mist_area
from .project import ProjectError

CLOUD_ALGORITHM = "linear-srgb-cloud-v1"
_FULL = 65535
_MAX_PROJECTION_SAMPLES = 100_000_000
_SOURCE_TILE_WH = (2048, 128)


def _ellipse(value: Any, width: int, height: int) -> dict[str, list[float]]:
    if not isinstance(value, dict) or set(value) != {"center_xy", "radii_xy"}:
        raise ProjectError("Cloud ellipse needs a native centre and radii")
    center, radii = value["center_xy"], value["radii_xy"]
    if (
        not isinstance(center, list)
        or len(center) != 2
        or not _number(center[0], 0, width)
        or not _number(center[1], 0, height)
        or not isinstance(radii, list)
        or len(radii) != 2
        or any(not _number(radius, 0.5, max(width, height) * 2) for radius in radii)
    ):
        raise ProjectError("Cloud centre or radii outside native bounds")
    return {
        "center_xy": [float(axis) or 0.0 for axis in center],
        "radii_xy": list(map(float, radii)),
    }


def validate_cloud_settings(value: Any, width: int, height: int) -> dict[str, Any]:
    ranges = {
        "amount": (0.0, 1.0),
        "size": (0.12, 1.0),
        "warp": (0.0, 0.75),
        "light_amount": (0.0, 1.0),
    }
    if (
        min(width, height) <= 0
        or not isinstance(value, dict)
        or set(value) != {"enabled", "tint_srgb", "seed", "center_xy", "radii_xy", *ranges}
        or type(value["enabled"]) is not bool
        or type(value["seed"]) is not int
        or not 0 <= value["seed"] <= MAX_SEED
        or not isinstance(value["tint_srgb"], str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", value["tint_srgb"]) is None
    ):
        raise ProjectError("Cloud needs an enabled flag, uint32 seed and six-digit sRGB colour")
    for name, (minimum, maximum) in ranges.items():
        if not _number(value[name], minimum, maximum):
            raise ProjectError(f"Cloud {name} outside its range")
    ellipse = _ellipse({key: value[key] for key in ("center_xy", "radii_xy")}, width, height)
    return {
        **value,
        **ellipse,
        "tint_srgb": value["tint_srgb"].upper(),
        **{name: float(value[name]) or 0.0 for name in ranges},
    }


def validate_cloud_area(value: Any, developed_id: str, width: int, height: int) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"coverage", "clear", "focus"}
        or not all(isinstance(value[key], list) for key in ("coverage", "clear"))
    ):
        raise ProjectError("Cloud needs coverage, clearance and an optional clear ellipse")
    regions = value["coverage"] + value["clear"]
    point_count = sum(
        len(region["points"])
        for region in regions
        if isinstance(region, dict) and isinstance(region.get("points"), list)
    )
    if len(regions) + (value["focus"] is not None) > 64 or point_count > 8192:
        raise ProjectError("Cloud allows up to 64 combined shapes and 8192 stroke points")
    for key in ("coverage", "clear"):
        validate_mist_area({"regions": value[key], "protection": []}, developed_id, width, height)
    focus = _ellipse(value["focus"], width, height) if value["focus"] is not None else None
    return {**value, "focus": focus}


def cloud_geometry_key(settings: dict[str, Any]) -> tuple[Any, ...]:
    return (
        settings["seed"],
        settings["size"],
        settings["warp"],
        tuple(settings["center_xy"]),
        tuple(settings["radii_xy"]),
    )


def cloud_visible(settings: dict[str, Any] | None) -> bool:
    return bool(settings and settings["enabled"] and settings["amount"])


def _radius(ellipse: dict[str, Any], x: np.ndarray, y: np.ndarray) -> np.ndarray:
    cx, cy = ellipse["center_xy"]
    rx, ry = ellipse["radii_xy"]
    return np.hypot((x - cx) / rx, (y - cy) / ry)


def sample_cloud_density(
    settings: dict[str, Any], size_wh: tuple[int, int], x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    wavelength = min(size_wh) * settings["size"]
    cx, cy = settings["center_xy"]
    u, v = (x - cx) / wavelength, (y - cy) / wavelength
    seed, warp = settings["seed"], settings["warp"]
    layer_x = u + warp * (2 * _value_noise(u * 0.55, v * 0.55, seed, 0) - 1)
    layer_y = v + warp * (2 * _value_noise(u * 0.55, v * 0.55, seed, 1) - 1)
    field = (
        0.72 * _value_noise(layer_x, layer_y, seed, 2)
        + 0.21 * _value_noise(layer_x * 2.3, layer_y * 2.3, seed, 3)
        + 0.07 * _value_noise(layer_x * 5, layer_y * 5, seed, 4)
    )
    mass = _smoothstep(np.clip((field - 0.18) / 0.64, 0, 1))
    envelope = _smoothstep(np.clip((1 - _radius(settings, x, y)) / 0.69, 0, 1))
    return np.rint(65535 * mass * envelope).astype(np.uint16)


def sample_cloud_light(
    settings: dict[str, Any], size_wh: tuple[int, int], x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    wavelength = min(size_wh) * settings["size"]
    cx, cy = settings["center_xy"]
    u, v = (x - cx) / wavelength, (y - cy) / wavelength
    seed = settings["seed"]
    field = (
        0.70 * _value_noise(u * 2.8, v * 2.8, seed, 5)
        + 0.23 * _value_noise(u * 5.7, v * 5.7, seed, 6)
        + 0.07 * _value_noise(u * 11.1, v * 11.1, seed, 7)
    )
    return np.rint(65535 * _smoothstep(np.clip((field - 0.2) / 0.58, 0, 1))).astype(np.uint16)


def _native_field(
    settings: dict[str, Any],
    size_wh: tuple[int, int],
    sample: Callable[[dict[str, Any], tuple[int, int], np.ndarray, np.ndarray], np.ndarray],
) -> np.ndarray:
    width, height = size_wh
    field = np.empty((height, width), dtype=np.uint16)
    x = np.arange(width, dtype=np.float64)[None, :] + 0.5
    for start in range(0, height, ROWS_PER_CHUNK):
        stop = min(start + ROWS_PER_CHUNK, height)
        y = np.arange(start, stop, dtype=np.float64)[:, None] + 0.5
        field[start:stop] = sample(settings, size_wh, x, y)
    return field


def _support16(
    regions: list[dict[str, Any]], size: tuple[int, int], developed_id: str = ""
) -> np.ndarray:
    width, height = size
    # Support geometry is source-bound by the owning revision, independently of rasterization.
    return rasterize_regions(
        {
            "schema_version": 2,
            "developed_id": developed_id,
            "width": width,
            "height": height,
            "regions": regions,
        }
    ).support16


def make_cloud_fields(
    settings: dict[str, Any],
    area: dict[str, Any],
    developed_id: str,
    native_size_wh: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    density = _native_field(settings, native_size_wh, sample_cloud_density)
    if area["coverage"]:
        coverage = _support16(area["coverage"], native_size_wh, developed_id)
        for start in range(0, density.shape[0], ROWS_PER_CHUNK):
            rows = slice(start, start + ROWS_PER_CHUNK)
            density[rows] = _with_coverage(density[rows], coverage[rows])
    return density, _native_field(settings, native_size_wh, sample_cloud_light)


def _with_coverage(density: np.ndarray, coverage: np.ndarray) -> np.ndarray:
    return np.rint(density.astype(np.float64) * coverage / _FULL).astype(np.uint16)


def make_cloud_clear(area: dict[str, Any], developed_id: str, protection: np.ndarray) -> np.ndarray:
    height, width = protection.shape
    clear = (
        _support16(area["clear"], (width, height), developed_id)
        if area["clear"]
        else np.zeros((height, width), dtype=np.uint16)
    )
    clear[protection] = _FULL
    focus = area["focus"]
    if focus is not None:
        x = np.arange(width, dtype=np.float64)[None, :] + 0.5
        for start in range(0, height, ROWS_PER_CHUNK):
            stop = min(start + ROWS_PER_CHUNK, height)
            y = np.arange(start, stop, dtype=np.float64)[:, None] + 0.5
            envelope = _smoothstep(np.clip((1 - _radius(focus, x, y)) / 0.55, 0, 1))
            np.maximum(
                clear[start:stop],
                np.rint(_FULL * envelope).astype(np.uint16),
                out=clear[start:stop],
            )
    return clear


@dataclass(frozen=True)
class CloudOperands:
    density16: np.ndarray
    light16: np.ndarray
    clear16: np.ndarray
    settings: dict[str, Any]
    area: dict[str, Any]
    native_size_wh: tuple[int, int]
    origin_xy: tuple[int, int] = (0, 0)

    def __post_init__(self) -> None:
        shape = self.density16.shape
        if (
            len(shape) != 2
            or min(shape) <= 0
            or any(
                plane.shape != shape or plane.dtype != np.uint16
                for plane in (self.density16, self.light16, self.clear16)
            )
            or min(self.origin_xy) < 0
            or self.origin_xy[0] + shape[1] > self.native_size_wh[0]
            or self.origin_xy[1] + shape[0] > self.native_size_wh[1]
        ):
            raise ProjectError("Cloud maps must be aligned native scalar16")

    def crop(self, x0: int, y0: int, x1: int, y1: int) -> "CloudOperands":
        ox, oy = self.origin_xy
        if not (0 <= x0 < x1 <= self.clear16.shape[1] and 0 <= y0 < y1 <= self.clear16.shape[0]):
            raise ProjectError("Cloud crop outside the available native map")
        crop = (slice(y0, y1), slice(x0, x1))
        return replace(
            self,
            density16=self.density16[crop],
            light16=self.light16[crop],
            clear16=self.clear16[crop],
            origin_xy=(ox + x0, oy + y0),
        )


def cloud_resource_bytes(
    width: int, height: int, *, rebuild_clear: bool = False, rebuild_coverage: bool = False
) -> int:
    # Retained scalar16 maps, row-at-a-time optics, and guide rasterization when requested.
    return (10 + (72 if rebuild_clear or rebuild_coverage else 0)) * width * height + (
        260 * width * min(ROWS_PER_CHUNK, height)
    )


def cloud_projection_bytes(width: int, height: int) -> int:
    tile_width, tile_height = _SOURCE_TILE_WH
    return tile_width * tile_height * 260 + 256 * width * min(ROWS_PER_CHUNK, height)


def _tint_linear(settings: dict[str, Any]) -> np.ndarray:
    return srgb_to_linear(np.array(list(bytes.fromhex(settings["tint_srgb"][1:]))) / 255)


def blend_cloud_into_result(result: np.ndarray, cloud: CloudOperands) -> np.ndarray:
    """Composite on owned RGB16, preserving inactive pixels without conversion."""
    if not cloud_visible(cloud.settings):
        return result
    if result.dtype != np.uint16 or result.shape != (*cloud.clear16.shape, 3):
        raise ProjectError("Cloud needs an aligned RGB16 Result")
    tint = _tint_linear(cloud.settings)
    amount, shade = cloud.settings["amount"], cloud.settings["light_amount"]
    for start in range(0, result.shape[0], ROWS_PER_CHUNK):
        rows = slice(start, start + ROWS_PER_CHUNK)
        density, light, clear = cloud.density16[rows], cloud.light16[rows], cloud.clear16[rows]
        active = (density > 0) & (clear < _FULL)
        if active.any():
            opacity = (
                amount * density[active].astype(np.float64) * (_FULL - clear[active]) / _FULL**2
            )[:, None]
            multiplier = (1 - shade) + shade * light[active].astype(np.float64) / _FULL
            incoming = srgb_to_linear(result[rows][active].astype(np.float64) / _FULL)
            result[rows][active] = linear_to_rgb16(
                (1 - opacity) * incoming + opacity * (multiplier[:, None] * tint)
            )
    return result


@dataclass(frozen=True)
class ProjectedCloudPlane:
    opacity: np.ndarray
    light_rgb: np.ndarray


def _sum_axis(values: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Integrate unit-width cells over each half-open interval along the last axis."""
    integral = np.pad(np.cumsum(values, axis=-1, dtype=np.float64), ((0, 0), (1, 0)))

    def at(position: np.ndarray) -> np.ndarray:
        index = np.floor(position).astype(np.intp)
        return integral[:, index] + (position - index) * (
            integral[:, np.minimum(index + 1, values.shape[-1])] - integral[:, index]
        )

    return at(upper) - at(lower)


def _box_sums(
    values: np.ndarray,
    x_lower: np.ndarray,
    x_upper: np.ndarray,
    y_lower: np.ndarray,
    y_upper: np.ndarray,
) -> np.ndarray:
    return _sum_axis(_sum_axis(values, x_lower, x_upper).T, y_lower, y_upper).T


def _any_full_clear(
    clear16: np.ndarray, support: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
) -> np.ndarray:
    x_low, y_low, x_high, y_high = support
    height, width = clear16.shape
    x_low, x_high = np.clip(x_low, 0, width), np.clip(x_high, 0, width)
    protected = np.zeros((len(y_low), len(x_low)), dtype=bool)
    prefix = np.zeros(width + 1, dtype=np.intp)
    previous = None
    for row, (top, bottom) in enumerate(
        zip(y_low.clip(0, height), y_high.clip(0, height), strict=True)
    ):
        if top >= bottom:
            continue
        if (top, bottom) != previous:
            np.cumsum(np.any(clear16[top:bottom] == _FULL, axis=0), out=prefix[1:])
            previous = top, bottom
        protected[row] = prefix[x_high] > prefix[x_low]
    return protected


def cloud_projection_bounds(
    settings: dict[str, Any],
    native_wh: tuple[int, int],
    x: np.ndarray,
    y: np.ndarray,
    footprint_xy: tuple[float, float],
) -> tuple[int, int, int, int]:
    """Bound density work to the saved raster and the analytic ellipse."""
    width, height = native_wh
    cx, cy = settings["center_xy"]
    rx, ry = settings["radii_xy"]
    footprint_x, footprint_y = footprint_xy
    left = max(math.floor(x[0] - footprint_x / 2), min(0, math.floor(cx - rx)))
    right = min(math.ceil(x[-1] + footprint_x / 2), max(width, math.ceil(cx + rx)))
    top = max(math.floor(y[0] - footprint_y / 2), min(0, math.floor(cy - ry)))
    bottom = min(math.ceil(y[-1] + footprint_y / 2), max(height, math.ceil(cy + ry)))
    if max(0, right - left) * max(0, bottom - top) > _MAX_PROJECTION_SAMPLES:
        raise ProjectError(
            "Cloud projection exceeds 100 million source samples; use a less extreme frame"
        )
    return left, top, right, bottom


def _edge_clamped_support(
    lower: np.ndarray, upper: np.ndarray, extent: int
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.floor(lower).clip(0, extent - 1).astype(np.intp),
        (np.ceil(upper) - 1).clip(0, extent - 1).astype(np.intp) + 1,
    )


class CloudProjector:
    """Filter one saved native field and its analytic exterior for a delivery canvas."""

    def __init__(self, cloud: CloudOperands) -> None:
        width, height = cloud.native_size_wh
        if cloud.origin_xy != (0, 0) or cloud.clear16.shape != (height, width):
            raise ProjectError("Framed Cloud requires complete native maps")
        self.cloud = cloud
        self.tint = _tint_linear(cloud.settings)
        self.coverage16: np.ndarray | None = None

    def _samples(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        cloud = self.cloud
        width, height = cloud.native_size_wh
        inside_x, inside_y = (0 <= x) & (x < width), (0 <= y) & (y < height)
        clipped_x, clipped_y = x.clip(0, width - 1), y.clip(0, height - 1)
        nearest = np.ix_(clipped_y, clipped_x)
        density, light, clear = (
            cloud.density16[nearest],
            cloud.light16[nearest],
            cloud.clear16[nearest],
        )
        rows, columns = np.nonzero(~(inside_y[:, None] & inside_x))
        if rows.size:
            mapped_x, mapped_y = x[columns] + 0.5, y[rows] + 0.5
            exterior_density = sample_cloud_density(
                cloud.settings, cloud.native_size_wh, mapped_x, mapped_y
            )
            if cloud.area["coverage"]:
                if self.coverage16 is None:
                    self.coverage16 = _support16(cloud.area["coverage"], cloud.native_size_wh)
                exterior_density = _with_coverage(
                    exterior_density, self.coverage16[clipped_y[rows], clipped_x[columns]]
                )
            density[rows, columns] = exterior_density
            light[rows, columns] = sample_cloud_light(
                cloud.settings, cloud.native_size_wh, mapped_x, mapped_y
            )
        return density, light, clear

    def project(
        self,
        x: np.ndarray,
        y: np.ndarray,
        footprint_xy: tuple[float, float],
        *,
        subject_support_xyxy: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None,
    ) -> ProjectedCloudPlane:
        if any(
            coordinates.ndim != 1
            or not coordinates.size
            or not np.isfinite(coordinates).all()
            or np.any(np.diff(coordinates) <= 0)
            for coordinates in (x, y)
        ) or any(not np.isfinite(span) or span < 1 for span in footprint_xy):
            raise ProjectError("Cloud needs increasing finite sample axes and positive footprints")
        opacity = np.zeros((len(y), len(x)), dtype=np.float64)
        light = np.zeros_like(opacity)
        if not cloud_visible(self.cloud.settings):
            return ProjectedCloudPlane(opacity, light[..., None] * self.tint)
        width, height = footprint_xy
        x_lower, x_upper = x - width / 2, x + width / 2
        y_lower, y_upper = y - height / 2, y + height / 2
        x_start, y_start, x_stop, y_stop = cloud_projection_bounds(
            self.cloud.settings, self.cloud.native_size_wh, x, y, footprint_xy
        )
        native_width, native_height = self.cloud.native_size_wh
        x_low, x_high = _edge_clamped_support(x_lower, x_upper, native_width)
        y_low, y_high = _edge_clamped_support(y_lower, y_upper, native_height)
        # Clearance extends from the native edge even where exterior density is zero.
        protected = _any_full_clear(self.cloud.clear16, (x_low, y_low, x_high, y_high))
        if subject_support_xyxy is not None:
            protected |= _any_full_clear(self.cloud.clear16, subject_support_xyxy)
        amount, shade = self.cloud.settings["amount"], self.cloud.settings["light_amount"]
        # Tile the source footprint as well as the destination so strong reductions
        # never allocate a large temporary for all actual native/extended samples.
        tile_width, tile_height = _SOURCE_TILE_WH
        for top in range(y_start, y_stop, tile_height):
            bottom = min(top + tile_height, y_stop)
            yr = slice(y_upper.searchsorted(top, side="right"), y_lower.searchsorted(bottom))
            if yr.start == yr.stop:
                continue
            yl, yh = (
                (y_lower[yr] - top).clip(0, bottom - top),
                (y_upper[yr] - top).clip(0, bottom - top),
            )
            for left in range(x_start, x_stop, tile_width):
                right = min(left + tile_width, x_stop)
                xr = slice(x_upper.searchsorted(left, side="right"), x_lower.searchsorted(right))
                if xr.start == xr.stop:
                    continue
                xl, xh = (
                    (x_lower[xr] - left).clip(0, right - left),
                    (x_upper[xr] - left).clip(0, right - left),
                )
                density, field_light, clear = self._samples(
                    np.arange(left, right), np.arange(top, bottom)
                )
                alpha = amount * density.astype(np.float64) * (_FULL - clear) / _FULL**2
                opacity[yr, xr] += _box_sums(alpha, xl, xh, yl, yh)
                light[yr, xr] += _box_sums(
                    alpha * ((1 - shade) + shade * field_light.astype(np.float64) / _FULL),
                    xl,
                    xh,
                    yl,
                    yh,
                )
        opacity = np.where(protected, 0, np.clip(opacity / (width * height), 0, 1))
        light = np.where(protected, 0, np.clip(light / (width * height), 0, opacity))
        return ProjectedCloudPlane(opacity, light[..., None] * self.tint)

    def blend(
        self,
        result: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
        footprint_xy: tuple[float, float] = (1, 1),
        *,
        subject_support_xyxy: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None,
    ) -> np.ndarray:
        """Composite the projected field in owned output rows using bounded scratch."""
        if not cloud_visible(self.cloud.settings):
            return result
        for start in range(0, len(y), ROWS_PER_CHUNK):
            rows = slice(start, start + ROWS_PER_CHUNK)
            support = None
            if subject_support_xyxy is not None:
                low_x, low_y, high_x, high_y = subject_support_xyxy
                support = (low_x, low_y[rows], high_x, high_y[rows])
            plane = self.project(x, y[rows], footprint_xy, subject_support_xyxy=support)
            active = plane.opacity > 0
            if active.any():
                pixels = result[rows]
                incoming = srgb_to_linear(pixels[active].astype(np.float64) / _FULL)
                pixels[active] = linear_to_rgb16(
                    (1 - plane.opacity[active][:, None]) * incoming + plane.light_rgb[active]
                )
        return result
