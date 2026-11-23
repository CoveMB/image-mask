"""Saved quantized repair arithmetic, independent of model execution/cache."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

from .assets import revision_asset, revision_hashes, saved_asset
from .guidance import coordinates, rasterize_regions
from .matte import TILE_SIZE
from .project import ProjectError, digest, read_project, read_revision

ORDER = "directional P/C; float64 P*(1-w)+D*w; rint ties-to-even; copy locks"
EDGE_SUPPORT_ALGORITHM = "inward-smoothstep-3px-v1"
EDGE_DETAIL_ALGORITHM = "source-detail-v1"
_EDGE_FEATHER_PX = 3
_EDGE_CONTEXT_PX = 64


def scalar16(path: Path | BinaryIO) -> np.ndarray:
    with Image.open(path) as image:
        if image.format != "PNG" or image.mode not in {"I;16", "I;16B", "I;16L"}:
            raise ProjectError("Repair operand must be grayscale16 PNG")
        return np.array(image, dtype=np.uint16)


def _change_required_cores(parent: np.ndarray, trimap: np.ndarray) -> np.ndarray:
    return ((trimap == 255) & (parent != 65535)) | ((trimap == 0) & (parent != 0))


def validate_merge(
    parent: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    locked: np.ndarray,
    trimap: np.ndarray,
    policy: str,
) -> None:
    if policy not in {"replace", "increase-only", "decrease-only"}:
        raise ProjectError("Invalid repair merge policy")
    if parent.ndim != 2 or any(
        values.dtype != np.uint16 or values.shape != parent.shape
        for values in (parent, support, locked)
    ):
        raise ProjectError("Repair operands require aligned uint16 samples")
    if protection.dtype != np.bool_ or protection.shape != parent.shape:
        raise ProjectError("Invalid repair protection")
    if trimap.shape != parent.shape or not np.isin(trimap, [0, 128, 255]).all():
        raise ProjectError("Invalid repair trimap")
    if np.any(_change_required_cores(parent, trimap) & (support != 65535)):
        raise ProjectError("Change-required core needs full support")
    if (policy == "increase-only" and np.any((trimap == 0) & (parent != 0))) or (
        policy == "decrease-only" and np.any((trimap == 255) & (parent != 65535))
    ):
        raise ProjectError("Directional policy incompatible with known core")
    if np.any(
        protection & (((trimap == 0) & (locked != 0)) | ((trimap == 255) & (locked != 65535)))
    ):
        raise ProjectError("Known core conflicts with saved lock")
    if np.any(protection & (support == 0) & (locked != parent)):
        raise ProjectError("Saved lock differs from parent outside repair support")


def merge_alpha(
    parent: np.ndarray,
    candidate: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    locked: np.ndarray,
    policy: str,
) -> np.ndarray:
    validate_merge(parent, support, protection, locked, np.full(parent.shape, 128), policy)
    if candidate.dtype != np.uint16 or candidate.shape != parent.shape:
        raise ProjectError("Candidate requires aligned quantized uint16 samples")
    desired = (
        candidate
        if policy == "replace"
        else np.maximum(parent, candidate)
        if policy == "increase-only"
        else np.minimum(parent, candidate)
    )
    weight = support.astype(np.float64) / 65535
    merged = np.rint(
        parent.astype(np.float64) * (1 - weight) + desired.astype(np.float64) * weight
    ).astype(np.uint16)
    merged[support == 0] = parent[support == 0]
    merged[protection] = locked[protection]
    return merged


def validate_support(
    support: np.ndarray,
    shape: tuple[int, int],
    context: list[int],
    scope: list[int],
) -> None:
    if support.shape != shape or support.dtype != np.uint16:
        raise ProjectError("Repair support must be full-master grayscale16")
    x0, y0, x1, y1 = context
    sx0, sy0, sx1, sy1 = scope
    allowed = np.zeros(shape, dtype=bool)
    left, top, right, bottom = max(x0, sx0), max(y0, sy0), min(x1, sx1), min(y1, sy1)
    if left < right and top < bottom:
        allowed[top:bottom, left:right] = True
    if not np.any(support) or np.any((support != 0) & ~allowed):
        raise ProjectError("Repair support exceeds explicit scope/context or is empty")


@dataclass(frozen=True)
class EdgeRepairPlan:
    context: list[int]
    scope: list[int]
    support: np.ndarray
    mode: str
    background_gaps: np.ndarray | None = None
    protected_tips: np.ndarray | None = None


def _edge_mark_bounds(region: Any, crop: list[int], *, allow_point: bool = False) -> list[int]:
    if not isinstance(region, dict):
        raise ProjectError("Invalid edge refinement shape")
    left, top, right, bottom = crop
    shape = region.get("shape")
    if shape == "rectangle" and set(region) == {"shape", "xyxy"}:
        x0, y0, x1, y1 = coordinates(region["xyxy"], right, bottom, box=True)
        if left <= x0 and top <= y0:
            return [x0, y0, x1, y1]
    elif allow_point and shape == "point" and set(region) == {"shape", "xy"}:
        x, y = coordinates(region["xy"], right, bottom)
        if left <= x and top <= y:
            return [x, y, x + 1, y + 1]
    elif shape == "stroke" and set(region) == {"shape", "points", "radius_px"}:
        points = region["points"]
        radius = region["radius_px"]
        if not isinstance(points, list) or not 1 <= len(points) <= 1024:
            raise ProjectError("Use a shorter native edge stroke")
        if type(radius) is not int or not 1 <= radius <= 64:
            raise ProjectError("Edge brush radius must be 1–64 native pixels")
        xs, ys = zip(*(coordinates(point, right, bottom) for point in points), strict=True)
        if left <= min(xs) and top <= min(ys):
            return [min(xs) - radius, min(ys) - radius, max(xs) + radius + 1, max(ys) + radius + 1]
    else:
        raise ProjectError("Invalid edge refinement shape fields")
    raise ProjectError("Edge marks must fit the displayed native crop")


def _local_edge_guides(
    marks: list, crop: list[int], context: list[int], developed_id: str, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = context
    regions = []
    for index, mark in enumerate(marks):
        if not isinstance(mark, dict) or mark.get("role") not in ("background", "protect"):
            raise ProjectError("Invalid local edge guide role")
        region = {key: value for key, value in mark.items() if key != "role"}
        left, top, right, bottom = _edge_mark_bounds(region, crop, allow_point=True)
        if not (
            x0 <= max(0, left)
            and y0 <= max(0, top)
            and min(width, right) <= x1
            and min(height, bottom) <= y1
        ):
            raise ProjectError("Local guides must fit inside the writable edge area")
        if region["shape"] == "rectangle":
            region["xyxy"] = [left - x0, top - y0, right - x0, bottom - y0]
        elif region["shape"] == "point":
            region["xy"] = [left - x0, top - y0]
        else:
            region["points"] = [[x - x0, y - y0] for x, y in region["points"]]
        region.update(id=f"local-edge-{index}", role="background")
        if mark["role"] == "protect":
            region.update(role="support", feather_px=0)
        regions.append(region)
    local = rasterize_regions(
        {
            "schema_version": 2,
            "developed_id": developed_id,
            "width": x1 - x0,
            "height": y1 - y0,
            "regions": regions,
        }
    )
    return local.trimap == 0, local.support16 != 0


def edge_support(
    area: Any,
    developed_id: str,
    protection: np.ndarray,
    parent: np.ndarray,
    trimap: np.ndarray,
    *,
    feathered: bool = True,
    refinement: Any = None,
) -> EdgeRepairPlan:
    """Derive native read bounds and quantized write weights from the reviewed geometry."""
    height, width = protection.shape
    mode, marks = "standard", []
    if refinement is not None:
        if not isinstance(refinement, dict) or set(refinement) != {"mode", "guides"}:
            raise ProjectError("Invalid edge refinement options")
        mode, marks = refinement["mode"], refinement["guides"]
        if mode not in ("standard", "stronger"):
            raise ProjectError("Invalid edge refinement mode")
        if not isinstance(marks, list) or len(marks) > 16:
            raise ProjectError("Use up to 16 local edge guides")
        if marks and mode != "stronger":
            raise ProjectError("Local edge guides require Stronger")
    if not isinstance(area, dict) or set(area) != {"crop_xyxy", "regions"}:
        raise ProjectError("Invalid edge refinement area")
    crop = coordinates(area["crop_xyxy"], width, height, box=True)
    left, top, right, bottom = crop
    if not isinstance(area["regions"], list) or not 1 <= len(area["regions"]) <= 16:
        raise ProjectError("Edge refinement requires 1–16 strokes or rectangles")
    bounds = [_edge_mark_bounds(region, crop) for region in area["regions"]]
    guides = {
        "schema_version": 2,
        "developed_id": developed_id,
        "width": width,
        "height": height,
        "regions": [
            dict(region, id=f"edge-{index}", role="support", feather_px=0)
            for index, region in enumerate(area["regions"])
        ],
    }
    x0 = max(left, min(box[0] for box in bounds))
    y0 = max(top, min(box[1] for box in bounds))
    x1 = min(right, max(box[2] for box in bounds))
    y1 = min(bottom, max(box[3] for box in bounds))
    scope = [x0, y0, x1, y1]
    context = [
        max(0, x0 - _EDGE_CONTEXT_PX),
        max(0, y0 - _EDGE_CONTEXT_PX),
        min(width, x1 + _EDGE_CONTEXT_PX),
        min(height, y1 + _EDGE_CONTEXT_PX),
    ]
    if context[2] - context[0] > TILE_SIZE or context[3] - context[1] > TILE_SIZE:
        raise ProjectError("Use a smaller edge area so its native context fits one matting tile")
    support = rasterize_regions(guides, scope_xyxy=scope).support16
    support[protection] = 0
    background_gaps = protected_tips = None
    if marks:
        cx0, cy0, cx1, cy1 = context
        local_window = np.s_[cy0:cy1, cx0:cx1]
        background_gaps, protected_tips = _local_edge_guides(
            marks, crop, context, developed_id, width, height
        )
        local_support = support[local_window]
        if np.any((background_gaps | protected_tips) & (local_support == 0)):
            raise ProjectError(
                "Local guides must fit inside the writable edge area and avoid saved locks"
            )
        if np.any(background_gaps & protected_tips):
            raise ProjectError("Background gap overlaps tip protection")
        if np.any(background_gaps & (trimap[local_window] == 255)):
            raise ProjectError("Background gap overlaps confirmed foreground")
        local_support[protected_tips] = 0
    if feathered:
        window = np.s_[y0:y1, x0:x1]
        writable = support[window] != 0
        distance = distance_transform_edt(np.pad(writable, 1))[1:-1, 1:-1]
        # Start the ramp half a pixel from the nearest exterior sample center.
        fraction = np.clip((distance - 0.5) / _EDGE_FEATHER_PX, 0, 1)
        weight = fraction**2 * (3 - 2 * fraction)
        weight[writable & _change_required_cores(parent[window], trimap[window])] = 1
        support[window] = np.rint(weight * 65535).astype(np.uint16)
    validate_support(support, protection.shape, context, scope)
    return EdgeRepairPlan(context, scope, support, mode, background_gaps, protected_tips)


def replay_directory(project: Path, directory: Path, manifest: dict[str, Any]) -> np.ndarray:
    """Merge only reloaded canonical files; caller validates immutable manifest hashes."""
    record = json.loads((directory / "repair/merge.json").read_bytes())
    parent = scalar16(revision_asset(project, directory, manifest, "repair/parent_alpha16.png"))
    candidate = scalar16(
        revision_asset(project, directory, manifest, "repair/candidate_alpha16.png")
    )
    support = scalar16(revision_asset(project, directory, manifest, "repair/support16.png"))
    locked = scalar16(revision_asset(project, directory, manifest, "supports/lock_values16.png"))
    with Image.open(
        revision_asset(project, directory, manifest, "supports/protection.png")
    ) as image:
        protection = np.array(image) != 0
    with Image.open(revision_asset(project, directory, manifest, "trimap.png")) as image:
        trimap = np.array(image)
    height, width = parent.shape
    context = coordinates(record["context_xyxy"], width, height, box=True)
    scope = coordinates(record["scope_xyxy"], width, height, box=True)
    x0, y0, x1, y1 = context
    if record.get("operation_order") != ORDER or record.get("crop_mapping") != {
        "origin_xy": [x0, y0],
        "dimensions_wh": [x1 - x0, y1 - y0],
        "native_scale": 1,
        "half_open": True,
    }:
        raise ProjectError("Invalid repair crop mapping/order")
    validate_support(support, parent.shape, context, scope)
    validate_merge(parent, support, protection, locked, trimap, record["merge_policy"])
    if "edge_area" in record:
        feathered = "edge_support_algorithm" in record
        if feathered and record["edge_support_algorithm"] != EDGE_SUPPORT_ALGORITHM:
            raise ProjectError("Unknown saved edge support algorithm")
        refinement = record.get("edge_refinement")
        if "edge_refinement" in record:
            request = json.loads((directory / "request.json").read_bytes())
            if (
                not isinstance(refinement, dict)
                or not feathered
                or not isinstance(request, dict)
                or request.get("edge_refinement") != refinement
                or request.get("edge_area") != record["edge_area"]
            ):
                raise ProjectError("Saved edge refinement differs from its request")
        plan = edge_support(
            record["edge_area"],
            record["developed_id"],
            protection,
            parent,
            trimap,
            feathered=feathered,
            refinement=refinement,
        )
        if (
            plan.context != context
            or plan.scope != scope
            or not np.array_equal(support, plan.support)
        ):
            raise ProjectError("Saved edge repair support differs from its authored footprint")
        if record.get("edge_candidate_algorithm") != (
            EDGE_DETAIL_ALGORITHM if plan.mode == "stronger" else None
        ):
            raise ProjectError("Unknown saved edge candidate algorithm for its mode")
        if plan.background_gaps is not None and np.any(
            candidate[y0:y1, x0:x1][plan.background_gaps]
        ):
            raise ProjectError("Saved edge candidate contradicts its background gap guides")
    merged = merge_alpha(parent, candidate, support, protection, locked, record["merge_policy"])
    if np.any(merged[trimap == 0] != 0) or np.any(merged[trimap == 255] != 65535):
        raise ProjectError("Repair known cores failed after merge")
    return merged


def prepared_parent_layers(project: Path, revision: str, developed_id: str) -> dict[str, Any]:
    """Follow prepared ancestry and prove unchanged alpha/RGB carry-forward bindings."""
    manifest = read_revision(project, revision, developed_id)
    visited = set()
    while manifest.get("kind") == "prepare":
        current = manifest["revision"]
        if current in visited:
            raise ProjectError("Cyclic prepared parent ancestry")
        visited.add(current)
        parent = manifest.get("parent")
        if not isinstance(parent, str):
            raise ProjectError("Prepared repair needs immutable parental revision")
        previous = read_revision(project, parent, developed_id)
        if digest(saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes()) != (
            manifest.get("parent_manifest_sha256")
        ):
            raise ProjectError("Stale prepared parent manifest")
        for name in ("base_alpha16.png", "foreground_rgb16.tif"):
            if (
                name not in revision_hashes(previous)
                or revision_hashes(manifest).get(name) != revision_hashes(previous)[name]
            ):
                raise ProjectError("Prepared repair must preserve parental alpha and foreground")
        if manifest.get("spatial_fade") != previous.get("spatial_fade") or any(
            manifest["files"].get(name) != previous["files"].get(name)
            for name in previous["files"]
            if name.startswith("effects/spatial-fade/")
        ):
            raise ProjectError("Prepared repair must preserve parental spatial fade operands")
        manifest = previous
    if manifest.get("kind") not in {"matte", "repair", "effects"} or not manifest.get(
        "final_acceptable"
    ):
        raise ProjectError("Repair needs a complete saved parental matte")
    return manifest


def replay_repair(project: Path, revision: str) -> np.ndarray:
    state = read_project(project)
    manifest = read_revision(project, revision, state["developed_id"])
    if manifest.get("kind") != "repair":
        raise ProjectError("Replay requires a saved repair revision")
    directory = saved_asset(project, f"revisions/{revision}")
    record = json.loads((directory / "repair/merge.json").read_bytes())
    parent = manifest["parent"]
    parent_manifest = read_revision(project, parent, state["developed_id"])
    parent_hashes = revision_hashes(parent_manifest)
    hashes = revision_hashes(manifest)
    if (
        record.get("parent") != parent
        or record.get("developed_id") != state["developed_id"]
        or record.get("parent_manifest_sha256") != manifest.get("parent_manifest_sha256")
        or record.get("parent_manifest_sha256")
        != digest(saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes())
        or hashes["repair/parent_alpha16.png"] != parent_hashes.get("base_alpha16.png")
    ):
        raise ProjectError("Stale repair parent/master/operand bindings")
    if "edge_area" in record:
        if any(
            hashes.get(name) != parent_hashes.get(name)
            for name in (
                "trimap.png",
                "supports/protection.png",
                "supports/lock_values16.png",
                "foreground_rgb16.tif",
            )
        ):
            raise ProjectError("Edge repair must inherit its parent trimap, locks and RGB16")
    elif hashes["repair/support16.png"] != parent_hashes.get("supports/support16.png"):
        raise ProjectError("Stale repair parent/master/operand bindings")
    prepared_parent_layers(project, parent, state["developed_id"])
    merged = replay_directory(project, directory, manifest)
    if not np.array_equal(
        merged, scalar16(revision_asset(project, directory, manifest, "base_alpha16.png"))
    ):
        raise ProjectError("Saved repair replay differs from published alpha")
    return merged
