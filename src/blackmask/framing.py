"""Exact presentation padding; all source coordinates remain native."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .assets import saved_asset
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


@dataclass(frozen=True)
class Margins:
    left_px: int
    right_px: int
    top_px: int
    bottom_px: int

    def to_dict(self) -> dict[str, int]:
        return {
            "left_px": self.left_px,
            "right_px": self.right_px,
            "top_px": self.top_px,
            "bottom_px": self.bottom_px,
        }


def validate_presentation_size(size: tuple[int, int]) -> tuple[int, int]:
    """Bound presentation geometry before allocating a delivery canvas."""
    if (
        type(size) is not tuple
        or len(size) != 2
        or any(type(item) is not int or item <= 0 for item in size)
    ):
        raise ValueError("Presentation dimensions must be positive integer width and height")
    width, height = size
    if width > 32768 or height > 32768 or width * height > 100_000_000:
        raise ValueError("Framed output exceeds 32768 pixels per axis or 100000000 pixels")
    return size


def validate_margins(value: object, source_size: tuple[int, int]) -> Margins:
    """Validate strict JSON integers and bound the canvas before allocating it."""
    names = {"left_px", "right_px", "top_px", "bottom_px"}
    if (
        not isinstance(value, dict)
        or set(value) != names
        or any(type(item) is not int or item < 0 for item in value.values())
    ):
        raise ValueError("Margins require exactly four nonnegative integer pixel counts")
    if (
        type(source_size) is not tuple
        or len(source_size) != 2
        or any(type(item) is not int or item <= 0 for item in source_size)
    ):
        raise ValueError("Source dimensions must be positive integer width and height")
    width = source_size[0] + value["left_px"] + value["right_px"]
    height = source_size[1] + value["top_px"] + value["bottom_px"]
    validate_presentation_size((width, height))
    return Margins(**value)


def framed_geometry(
    source_size: tuple[int, int], margins: Margins
) -> tuple[int, int, tuple[int, int, int, int]]:
    if not isinstance(margins, Margins):
        raise TypeError("Expected validated Margins")
    settings = validate_margins(margins.to_dict(), source_size)
    width, height = source_size
    return (
        settings.left_px + width + settings.right_px,
        settings.top_px + height + settings.bottom_px,
        (settings.left_px, settings.top_px, settings.left_px + width, settings.top_px + height),
    )


def frame_result(
    native_rgb16: np.ndarray, background_rgb16: np.ndarray | None, margins: Margins
) -> np.ndarray:
    """Copy the completed native render; extend only the saved backdrop outwards."""
    if (
        not isinstance(native_rgb16, np.ndarray)
        or native_rgb16.dtype != np.uint16
        or native_rgb16.ndim != 3
        or native_rgb16.shape[2] != 3
    ):
        raise ValueError("Framing requires a native RGB16 raster")
    width, height, (x0, y0, x1, y1) = framed_geometry(
        (native_rgb16.shape[1], native_rgb16.shape[0]), margins
    )
    if background_rgb16 is not None and (
        not isinstance(background_rgb16, np.ndarray)
        or background_rgb16.dtype != np.uint16
        or background_rgb16.shape != native_rgb16.shape
    ):
        raise ValueError("Framing requires an aligned saved RGB16 backdrop")
    result = np.empty((height, width, 3), dtype=np.uint16)
    if background_rgb16 is None:
        result.fill(0)
    else:
        # Broadcasting edge strips avoids a second expanded backdrop allocation.
        result[:y0, x0:x1] = background_rgb16[0]
        result[y1:, x0:x1] = background_rgb16[-1]
        result[y0:y1, :x0] = background_rgb16[:, :1]
        result[y0:y1, x1:] = background_rgb16[:, -1:]
        result[:y0, :x0] = background_rgb16[0, 0]
        result[:y0, x1:] = background_rgb16[0, -1]
        result[y1:, :x0] = background_rgb16[-1, 0]
        result[y1:, x1:] = background_rgb16[-1, -1]
    result[y0:y1, x0:x1] = native_rgb16
    return result


def frame_transparent(native_rgba8: np.ndarray, margins: Margins) -> np.ndarray:
    """Preserve the canonical straight RGBA8 view and put zero RGBA outside it."""
    if (
        not isinstance(native_rgba8, np.ndarray)
        or native_rgba8.dtype != np.uint8
        or native_rgba8.ndim != 3
        or native_rgba8.shape[2] != 4
    ):
        raise ValueError("Transparent framing requires a native RGBA8 raster")
    width, height, (x0, y0, x1, y1) = framed_geometry(
        (native_rgba8.shape[1], native_rgba8.shape[0]), margins
    )
    result = np.zeros((height, width, 4), dtype=np.uint8)
    result[y0:y1, x0:x1] = native_rgba8
    return result


def framing_preview(
    native_rgb16: np.ndarray,
    background_rgb16: np.ndarray | None,
    margins: Margins,
    *,
    max_edge: int = 1600,
) -> tuple[np.ndarray, dict[str, object]]:
    """Sample the virtual presentation canvas using only bounded display-row scratch."""
    if type(max_edge) is not int or not 1 <= max_edge <= 1600:
        raise ValueError("Preview maximum edge must be an integer from 1 to 1600")
    if (
        not isinstance(native_rgb16, np.ndarray)
        or native_rgb16.dtype != np.uint16
        or native_rgb16.ndim != 3
        or native_rgb16.shape[2] != 3
    ):
        raise ValueError("Framing preview requires native RGB16")
    source_height, source_width = native_rgb16.shape[:2]
    width, height, rectangle = framed_geometry((source_width, source_height), margins)
    if background_rgb16 is not None and (
        not isinstance(background_rgb16, np.ndarray)
        or background_rgb16.dtype != np.uint16
        or background_rgb16.shape != native_rgb16.shape
    ):
        raise ValueError("Framing preview requires an aligned saved RGB16 backdrop")
    longest = max(width, height)
    display_width = max(1, width * min(max_edge, longest) // longest)
    display_height = max(1, height * min(max_edge, longest) // longest)
    x0, y0, _, _ = rectangle
    source_x = (2 * np.arange(display_width) + 1) * width // (2 * display_width) - x0
    inside_x = (source_x >= 0) & (source_x < source_width)
    clipped_x = np.clip(source_x, 0, source_width - 1)
    pixels = np.empty((display_height, display_width, 3), dtype=np.uint8)
    for row_index in range(display_height):
        source_y = (2 * row_index + 1) * height // (2 * display_height) - y0
        row = (
            np.zeros((display_width, 3), dtype=np.uint16)
            if background_rgb16 is None
            else background_rgb16[min(max(source_y, 0), source_height - 1), clipped_x].copy()
        )
        if 0 <= source_y < source_height:
            row[inside_x] = native_rgb16[source_y, source_x[inside_x]]
        pixels[row_index] = np.rint(row.astype(np.float64) / 257).astype(np.uint8)
    return pixels, {
        "source_dimensions_wh": [source_width, source_height],
        "output_dimensions_wh": [width, height],
        "display_dimensions_wh": [display_width, display_height],
        "source_rect_xyxy": list(rectangle),
    }


def read_framing_preset(
    project: Path, developed_id: str, source_size: tuple[int, int]
) -> tuple[Margins, str | None]:
    """Read optional source-bound presentation metadata without changing native state."""
    path = saved_asset(_root(project), "framing.json")
    try:
        with path.open("rb") as stream:
            raw = stream.read(16385)
    except FileNotFoundError:
        return validate_margins(Margins(0, 0, 0, 0).to_dict(), source_size), None
    try:
        if len(raw) > 16384:
            raise ValueError("Preset exceeds 16 KiB metadata bound")
        value = json.loads(raw)
        if (
            not isinstance(value, dict)
            or set(value) != {"schema_version", "developed_id", "source_dimensions_wh", "margins"}
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 2
            or value["developed_id"] != developed_id
            or not isinstance(value["source_dimensions_wh"], list)
            or any(type(item) is not int for item in value["source_dimensions_wh"])
            or value["source_dimensions_wh"] != list(source_size)
        ):
            raise ValueError("Wrong framing schema, source identity or dimensions")
        return validate_margins(value["margins"], source_size), digest(raw)
    except (ValueError, TypeError, KeyError) as error:
        raise ProjectError(
            f"Invalid framing.json; preserve file for explicit recovery: {error}"
        ) from error


class FramingSaveUncertain(ProjectError):
    """A failed publication whose visible preset must be reloaded before another save."""

    def __init__(self, visible: dict[str, object]):
        self.visible = {**visible, "framing_reload_required": True}
        super().__init__(
            "Framing save durability unconfirmed; visible framing.json may have changed. "
            "Keep your edits and Reload saved margins before saving again."
        )


def save_framing_preset(
    project: Path,
    value: dict[str, object],
    *,
    expected_digest: str | None,
    expected_developed_id: str,
) -> dict[str, object]:
    """Source-bound raw-byte CAS using the shared project writer and publication helpers."""
    if expected_digest is not None and (
        not isinstance(expected_digest, str)
        or re.fullmatch("[a-f0-9]{64}", expected_digest) is None
    ):
        raise ProjectError("Expected framing digest must be SHA-256 or null for an absent preset")
    project = _root(project)
    with project_lock(project):
        source_bytes = saved_asset(project, "source.json").read_bytes()
        state = read_project(project, validate_drafts=False)
        if state["developed_id"] != expected_developed_id:
            raise ProjectError("Stale framing source identity; reload current project")
        source, _ = _validate_assets(project, state, validate_drafts=False)
        source_size = (source.shape[1], source.shape[0])
        del source
        settings = validate_margins(value, source_size)
        previous, previous_digest = read_framing_preset(project, expected_developed_id, source_size)
        if previous_digest != expected_digest:
            raise ProjectError("Stale framing preset; Reload saved margins before saving")
        if previous_digest is not None and previous == settings:
            return {"framing": settings.to_dict(), "framing_digest": previous_digest}
        envelope = {
            "schema_version": 2,
            "developed_id": expected_developed_id,
            "source_dimensions_wh": list(source_size),
            "margins": settings.to_dict(),
        }

        def unchanged() -> None:
            if saved_asset(project, "source.json").read_bytes() != source_bytes:
                raise ProjectError("Stale framing source before publication")
            if (
                read_framing_preset(project, expected_developed_id, source_size)[1]
                != previous_digest
            ):
                raise ProjectError("Stale framing preset before publication")

        check_space(project, 1024**2)
        try:
            _atomic_json(
                saved_asset(project, "framing.json"), envelope, validate_before_replace=unchanged
            )
        except (OSError, ValueError) as error:
            try:
                visible, visible_digest = read_framing_preset(
                    project, expected_developed_id, source_size
                )
            except (ProjectError, OSError):
                observed: dict[str, object] = {"framing": None, "framing_digest": None}
            else:
                if visible_digest == previous_digest:
                    raise ProjectError(
                        f"Framing save failed; saved preset unchanged: {error}"
                    ) from error
                observed = {"framing": visible.to_dict(), "framing_digest": visible_digest}
            raise FramingSaveUncertain(observed) from error
        return {"framing": settings.to_dict(), "framing_digest": digest(_json_bytes(envelope))}
