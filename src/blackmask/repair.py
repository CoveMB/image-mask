"""Saved quantized repair arithmetic, independent of model execution/cache."""

import json
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np
from PIL import Image

from .assets import revision_asset, revision_hashes, saved_asset
from .guidance import coordinates, rasterize_regions, validate_guides
from .matte import TILE_SIZE
from .project import ProjectError, digest, read_project, read_revision

ORDER = "directional P/C; float64 P*(1-w)+D*w; rint ties-to-even; copy locks"


def scalar16(path: Path | BinaryIO) -> np.ndarray:
    with Image.open(path) as image:
        if image.format != "PNG" or image.mode not in {"I;16", "I;16B", "I;16L"}:
            raise ProjectError("Repair operand must be grayscale16 PNG")
        return np.array(image, dtype=np.uint16)


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
    needs_change = ((trimap == 255) & (parent != 65535)) | ((trimap == 0) & (parent != 0))
    if np.any(needs_change & (support != 65535)):
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


def edge_support(
    area: Any, developed_id: str, protection: np.ndarray
) -> tuple[list[int], list[int], np.ndarray]:
    """Derive one bounded write footprint and its read context from reviewed geometry."""
    height, width = protection.shape
    if not isinstance(area, dict) or set(area) != {"crop_xyxy", "regions"}:
        raise ProjectError("Invalid edge refinement area")
    left, top, right, bottom = coordinates(area["crop_xyxy"], width, height, box=True)
    if not isinstance(area["regions"], list) or not 1 <= len(area["regions"]) <= 16:
        raise ProjectError("Edge refinement requires 1–16 strokes or rectangles")
    regions = []
    for index, region in enumerate(area["regions"]):
        if not isinstance(region, dict):
            raise ProjectError("Invalid edge refinement shape")
        shape = region.get("shape")
        if shape == "stroke" and set(region) == {"shape", "points", "radius_px"}:
            if not isinstance(region["points"], list) or not 1 <= len(region["points"]) <= 1024:
                raise ProjectError("Use a shorter native edge stroke")
            if type(region["radius_px"]) is not int or not 1 <= region["radius_px"] <= 64:
                raise ProjectError("Edge brush radius must be 1–64 native pixels")
        elif shape != "rectangle" or set(region) != {"shape", "xyxy"}:
            raise ProjectError("Invalid edge refinement shape fields")
        regions.append(dict(region, id=f"edge-{index}", role="support", feather_px=0))
    guides = validate_guides(
        {
            "schema_version": 2,
            "developed_id": developed_id,
            "width": width,
            "height": height,
            "regions": regions,
        },
        developed_id,
        width,
        height,
    )
    bounds = []
    for region in regions:
        if region["shape"] == "rectangle":
            x0, y0, x1, y1 = region["xyxy"]
            if not (left <= x0 < x1 <= right and top <= y0 < y1 <= bottom):
                raise ProjectError("Edge rectangle must fit the displayed native crop")
            bounds.append([x0, y0, x1, y1])
        else:
            xs, ys = zip(*region["points"], strict=True)
            if not (left <= min(xs) <= max(xs) < right and top <= min(ys) <= max(ys) < bottom):
                raise ProjectError(
                    "Edge stroke must start and end within the displayed native crop"
                )
            radius = region["radius_px"]
            bounds.append(
                [min(xs) - radius, min(ys) - radius, max(xs) + radius + 1, max(ys) + radius + 1]
            )
    x0 = max(left, min(box[0] for box in bounds))
    y0 = max(top, min(box[1] for box in bounds))
    x1 = min(right, max(box[2] for box in bounds))
    y1 = min(bottom, max(box[3] for box in bounds))
    scope = [x0, y0, x1, y1]
    padding = 64
    context = [
        max(0, x0 - padding),
        max(0, y0 - padding),
        min(width, x1 + padding),
        min(height, y1 + padding),
    ]
    if context[2] - context[0] > TILE_SIZE or context[3] - context[1] > TILE_SIZE:
        raise ProjectError("Use a smaller edge area so its native context fits one matting tile")
    support = rasterize_regions(guides, scope_xyxy=scope).support16
    support[protection] = 0
    validate_support(support, protection.shape, context, scope)
    return context, scope, support


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
    if "edge_area" in record:
        edge_context, edge_scope, edge = edge_support(
            record["edge_area"], record["developed_id"], protection
        )
        if edge_context != context or edge_scope != scope or not np.array_equal(support, edge):
            raise ProjectError("Saved edge repair support differs from its authored footprint")
    validate_merge(parent, support, protection, locked, trimap, record["merge_policy"])
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
