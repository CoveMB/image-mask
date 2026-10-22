"""Canonical native-coordinate typed guides, categorical labels and saved-value locks."""

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt

ROLES = {"keep", "remove", "foreground", "background", "unknown", "support", "lock"}


def identifier(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value) is None:
        raise ValueError("Invalid stable identifier")
    return value


def coordinates(value: Any, width: int, height: int, *, box: bool = False) -> list[int]:
    count = 4 if box else 2
    if not isinstance(value, list) or len(value) != count or any(type(v) is not int for v in value):
        raise ValueError("Coordinates must be native integers")
    if box:
        x0, y0, x1, y1 = value
        valid = 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
    else:
        x, y = value
        valid = 0 <= x < width and 0 <= y < height
    if not valid:
        raise ValueError("Coordinates outside native master or empty half-open box")
    return value


def validate_guides(value: Any, developed_id: str, width: int, height: int) -> dict[str, Any]:
    keys = {"schema_version", "developed_id", "width", "height", "regions"}
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 2
        or value["developed_id"] != developed_id
        or type(value["width"]) is not int
        or type(value["height"]) is not int
        or value["width"] != width
        or value["height"] != height
        or not isinstance(value["regions"], list)
    ):
        raise ValueError("Invalid guides schema/master/dimensions")
    seen = set()
    for region in value["regions"]:
        if not isinstance(region, dict):
            raise TypeError("Region must be a typed object")
        stable_id = identifier(region.get("id"))
        if stable_id in seen:
            raise ValueError("Duplicate region ID")
        seen.add(stable_id)
        role, shape = region.get("role"), region.get("shape")
        if role not in ROLES:
            raise ValueError("Unknown guide role")
        expected = {"id", "role", "shape"}
        if shape in {"rectangle", "box"}:
            expected.add("xyxy")
            coordinates(region.get("xyxy"), width, height, box=True)
        elif shape == "point":
            expected.add("xy")
            coordinates(region.get("xy"), width, height)
        elif shape == "stroke":
            expected.update(("points", "radius_px"))
            points = region.get("points")
            if not isinstance(points, list) or not points:
                raise ValueError("Stroke needs native points")
            for point in points:
                coordinates(point, width, height)
            if type(region.get("radius_px")) is not int or not 1 <= region["radius_px"] <= max(
                width, height
            ):
                raise ValueError("Invalid native stroke radius")
        else:
            raise ValueError("Unknown guide shape")
        if role in {"keep", "remove"}:
            expected.add("group_id")
            identifier(region.get("group_id"))
            if shape not in {"point", "box"} or (shape == "box" and role != "keep"):
                raise ValueError("SAM hints use points or a keep box")
        elif shape == "box":
            raise ValueError("Box is a SAM hint; labels use rectangle")
        if role == "support":
            expected.add("feather_px")
            if type(region.get("feather_px")) is not int or not 0 <= region["feather_px"] <= max(
                width, height
            ):
                raise ValueError("Invalid inward feather")
        if role == "lock":
            expected.add("revision")
            revision = region.get("revision")
            if not isinstance(revision, str) or re.fullmatch(r"rev-[0-9]{3,}", revision) is None:
                raise ValueError("Lock needs a saved revision")
        if set(region) != expected:
            raise ValueError("Invalid region keys for role/shape")
    return value


def edit_guides(guides: dict[str, Any], edits: Any) -> dict[str, Any]:
    if (
        not isinstance(edits, dict)
        or set(edits) != {"schema_version", "developed_id", "actions"}
        or type(edits["schema_version"]) is not int
        or edits["schema_version"] != 2
        or edits["developed_id"] != guides["developed_id"]
        or not isinstance(edits["actions"], list)
    ):
        raise ValueError("Invalid typed guide edits")
    regions = {r["id"]: r for r in guides["regions"]}
    seen = set()
    for action in edits["actions"]:
        if not isinstance(action, dict):
            raise TypeError("Guide action must be an object")
        if action.get("action") == "upsert" and set(action) == {"action", "region"}:
            region = action["region"]
            if not isinstance(region, dict):
                raise ValueError("Invalid region")
            stable_id = identifier(region.get("id"))
            # A lock binding cannot be silently moved; remove it explicitly first.
            old = regions.get(stable_id)
            if old and old["role"] == "lock" and old != region:
                raise ValueError(
                    "Remove existing lock explicitly before changing its binding/region"
                )
            regions[stable_id] = region
        elif action.get("action") == "remove" and set(action) == {"action", "id"}:
            stable_id = identifier(action["id"])
            if stable_id not in regions:
                raise ValueError("Cannot remove missing guide")
            del regions[stable_id]
        else:
            raise ValueError("Unknown typed guide action")
        if stable_id in seen:
            raise ValueError("Duplicate guide action ID; use separate recorded operations")
        seen.add(stable_id)
    result = dict(guides, regions=list(regions.values()))
    return validate_guides(result, guides["developed_id"], guides["width"], guides["height"])


def _region_mask(region: dict[str, Any], width: int, height: int) -> NDArray[np.bool_]:
    mask = np.zeros((height, width), dtype=bool)
    if region["shape"] in {"rectangle", "box"}:
        x0, y0, x1, y1 = region["xyxy"]
        mask[y0:y1, x0:x1] = True
    elif region["shape"] == "point":
        x, y = region["xy"]
        mask[y, x] = True
    else:
        radius = region["radius_px"]
        points = region["points"]
        pairs = pairwise(points) if len(points) > 1 else [(points[0], points[0])]
        for (ax, ay), (bx, by) in pairs:
            x0, x1 = max(0, min(ax, bx) - radius), min(width, max(ax, bx) + radius + 1)
            y0, y1 = max(0, min(ay, by) - radius), min(height, max(ay, by) + radius + 1)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            length2 = (bx - ax) ** 2 + (by - ay) ** 2
            fraction = (
                np.clip(((xx - ax) * (bx - ax) + (yy - ay) * (by - ay)) / length2, 0, 1)
                if length2
                else 0
            )
            distance2 = (xx - (ax + fraction * (bx - ax))) ** 2 + (
                yy - (ay + fraction * (by - ay))
            ) ** 2
            mask[y0:y1, x0:x1] |= distance2 <= radius**2
    return mask


@dataclass(frozen=True)
class RasterizedGuides:
    trimap: NDArray[np.uint8]
    support16: NDArray[np.uint16]
    protection: NDArray[np.bool_]
    lock_values16: NDArray[np.uint16]


def rasterize_regions(
    guides: dict[str, Any],
    *,
    scope_xyxy: list[int] | None = None,
    saved_alpha: dict[str, NDArray[np.uint16]] | None = None,
    parent_alpha: NDArray[np.uint16] | None = None,
    proposed_foreground: NDArray[np.bool_] | None = None,
    proposed_unknown: NDArray[np.bool_] | None = None,
) -> RasterizedGuides:
    width, height = guides["width"], guides["height"]
    validate_guides(guides, guides["developed_id"], width, height)
    shape = (height, width)
    masks = {
        role: np.zeros(shape, dtype=bool)
        for role in ("foreground", "background", "unknown", "lock")
    }
    support = np.zeros(shape, dtype=np.uint16)
    lock_values = np.zeros(shape, dtype=np.uint16)
    saved_alpha = saved_alpha or {}
    scope = np.zeros(shape, dtype=bool)
    x0, y0, x1, y1 = coordinates(scope_xyxy or [0, 0, width, height], width, height, box=True)
    scope[y0:y1, x0:x1] = True
    for region in guides["regions"]:
        role = region["role"]
        if role in {"keep", "remove"}:
            continue
        mask = _region_mask(region, width, height)
        if role == "support":
            mask &= scope
            feather = region["feather_px"]
            weight = (
                np.minimum(distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1] / feather, 1)
                if feather
                else mask
            )
            support = np.maximum(support, np.rint(weight * 65535).astype(np.uint16))
        elif role == "lock":
            values = saved_alpha.get(region["revision"])
            if values is None or values.shape != shape or values.dtype != np.uint16:
                raise ValueError("Lock needs same-master saved revision alpha16")
            if np.any(mask & masks["lock"] & (lock_values != values)):
                raise ValueError("Conflicting saved lock values")
            lock_values[mask] = values[mask]
            masks["lock"] |= mask
        else:
            masks[role] |= mask
    # Suggestions share categorical/conflict guards; derived uncertainty preserves typed cores.
    for proposed in (proposed_foreground, proposed_unknown):
        if proposed is not None and (proposed.shape != shape or proposed.dtype != np.bool_):
            raise ValueError("Invalid native proposal mask")
    if proposed_unknown is not None:
        masks["unknown"] |= proposed_unknown & ~(masks["foreground"] | masks["background"])
    if proposed_foreground is not None:
        masks["foreground"] |= proposed_foreground
    foreground, background, unknown, protection = (
        masks[r] for r in ("foreground", "background", "unknown", "lock")
    )
    if np.any(foreground & background):
        raise ValueError("Contradictory foreground/background assertions")
    if np.any(
        protection & ((foreground & (lock_values != 65535)) | (background & (lock_values != 0)))
    ):
        raise ValueError("Confirmed core conflicts with saved lock values")
    # Unknown corridors win over single known assertions, never over a contradictory pair.
    trimap = np.full(shape, 128, dtype=np.uint8)
    trimap[foreground & ~unknown] = 255
    trimap[background & ~unknown] = 0
    if parent_alpha is not None:
        if parent_alpha.shape != shape or parent_alpha.dtype != np.uint16:
            raise ValueError("Invalid parent alpha16")
        needs_change = ((trimap == 255) & (parent_alpha != 65535)) | (
            (trimap == 0) & (parent_alpha != 0)
        )
        if np.any(needs_change & (support != 65535)):
            raise ValueError("Change-required core needs full support inside write scope")
    return RasterizedGuides(trimap, support, protection, lock_values)


def build_trimap_proposal(
    guides: dict[str, Any],
    groups: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    scope_xyxy: list[int] | None = None,
    saved_alpha: dict[str, NDArray[np.uint16]] | None = None,
    parent_alpha: NDArray[np.uint16] | None = None,
) -> tuple[RasterizedGuides, NDArray[np.bool_]]:
    """Unreviewed native morphology suggestion; never replaces confirmed trimap or alpha."""
    shape = (guides["height"], guides["width"])
    foreground = np.zeros(shape, dtype=bool)
    boundary = np.zeros(shape, dtype=bool)
    for group in groups:
        if not group["keep"] or group.get("selected_candidate") is None:
            continue
        selected = [
            candidate
            for candidate in candidates
            if candidate["group_id"] == group["id"] and candidate["selected"]
        ]
        if len(selected) != 1:
            raise ValueError("Morphology needs exactly one actual selected native candidate")
        mask = selected[0]["mask"]
        if mask.shape != shape or mask.dtype != np.bool_:
            raise ValueError("Invalid selected native candidate mask")
        morphology = group.get("morphology")
        if morphology is None:
            if group["material_policy"] == "unknown_interior":
                boundary |= mask
            continue
        erosion, dilation = morphology["foreground_erosion_px"], morphology["unknown_dilation_px"]
        if any(
            type(margin) is not int or not 0 <= margin <= max(shape)
            for margin in (erosion, dilation)
        ):
            raise ValueError("Morphology margins must be native integers within master size")
        core = np.zeros(shape, dtype=bool)
        expanded = np.zeros(shape, dtype=bool)
        if np.any(mask):
            expanded = distance_transform_edt(~mask) <= dilation
            if group["material_policy"] == "opaque_core":
                core = distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1] > erosion
        foreground |= core
        boundary |= expanded & ~core
    return rasterize_regions(
        guides,
        scope_xyxy=scope_xyxy,
        saved_alpha=saved_alpha,
        parent_alpha=parent_alpha,
        proposed_foreground=foreground,
        proposed_unknown=boundary,
    ), boundary
