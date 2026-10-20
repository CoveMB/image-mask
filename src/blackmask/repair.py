"""Saved quantized repair arithmetic, independent of model execution/cache."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .guidance import coordinates
from .project import ProjectError, _asset, digest, read_project, read_revision

ORDER = "directional P/C; float64 P*(1-w)+D*w; rint ties-to-even; copy locks"


def scalar16(path: Path) -> np.ndarray:
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


def replay_directory(directory: Path) -> np.ndarray:
    """Merge only reloaded canonical files; caller validates immutable manifest hashes."""
    record = json.loads((directory / "repair/merge.json").read_bytes())
    parent = scalar16(directory / "repair/parent_alpha16.png")
    candidate = scalar16(directory / "repair/candidate_alpha16.png")
    support = scalar16(directory / "repair/support16.png")
    locked = scalar16(directory / "supports/lock_values16.png")
    with Image.open(directory / "supports/protection.png") as image:
        protection = np.array(image) != 0
    with Image.open(directory / "trimap.png") as image:
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
    merged = merge_alpha(parent, candidate, support, protection, locked, record["merge_policy"])
    if np.any(merged[trimap == 0] != 0) or np.any(merged[trimap == 255] != 65535):
        raise ProjectError("Repair known cores failed after merge")
    return merged


def prepared_parent_layers(project: Path, revision: str, master_id: str) -> dict[str, Any]:
    """Follow prepared ancestry and prove unchanged alpha/RGB carry-forward bindings."""
    manifest = read_revision(project, revision, master_id)
    visited = set()
    while manifest.get("kind") == "prepare":
        current = manifest["revision"]
        if current in visited:
            raise ProjectError("Cyclic prepared parent ancestry")
        visited.add(current)
        parent = manifest.get("parent")
        if not isinstance(parent, str):
            raise ProjectError("Prepared repair needs immutable parental revision")
        previous = read_revision(project, parent, master_id)
        if digest(_asset(project, f"revisions/{parent}/manifest.json").read_bytes()) != (
            manifest.get("parent_manifest_sha256")
        ):
            raise ProjectError("Stale prepared parent manifest")
        for name in ("base_alpha16.png", "foreground_rgb16.tif"):
            if (
                name not in previous["files"]
                or manifest["files"].get(name) != previous["files"][name]
            ):
                raise ProjectError("Prepared repair must preserve parental alpha and foreground")
        manifest = previous
    if manifest.get("kind") not in {"matte", "repair", "effects"} or not manifest.get(
        "final_acceptable"
    ):
        raise ProjectError("Repair needs a complete saved parental matte")
    return manifest


def replay_repair(project: Path, revision: str) -> np.ndarray:
    state = read_project(project)
    manifest = read_revision(project, revision, state["master_id"])
    if manifest.get("kind") != "repair":
        raise ProjectError("Replay requires a saved repair revision")
    directory = _asset(project, f"revisions/{revision}")
    record = json.loads((directory / "repair/merge.json").read_bytes())
    parent = manifest["parent"]
    parent_manifest = read_revision(project, parent, state["master_id"])
    if (
        record.get("parent") != parent
        or record.get("master_id") != state["master_id"]
        or record.get("parent_manifest_sha256") != manifest.get("parent_manifest_sha256")
        or record.get("parent_manifest_sha256")
        != digest(_asset(project, f"revisions/{parent}/manifest.json").read_bytes())
        or manifest["files"]["repair/parent_alpha16.png"]
        != parent_manifest["files"].get("base_alpha16.png")
        or manifest["files"]["repair/support16.png"]
        != parent_manifest["files"].get("supports/support16.png")
    ):
        raise ProjectError("Stale repair parent/master/operand bindings")
    prepared_parent_layers(project, parent, state["master_id"])
    merged = replay_directory(directory)
    if not np.array_equal(merged, scalar16(directory / "base_alpha16.png")):
        raise ProjectError("Saved repair replay differs from published alpha")
    return merged
