"""Preparation transaction: immutable snapshots, role validation and sole state publication."""

import json
import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .guidance import (
    build_trimap_proposal,
    coordinates,
    edit_guides,
    rasterize_regions,
    validate_guides,
)
from .models import SamSession, VitMatteSession
from .project import (
    ProjectError,
    _asset,
    _atomic_json,
    _json_bytes,
    _publish_new_directory,
    _root,
    _sync_directory,
    check_space,
    digest,
    load_master,
    project_lock,
    read_project,
    read_revision,
)
from .recipe import Recipe


def draft_digest(project: Path) -> str:
    return digest(
        _asset(project, "recipe.toml").read_bytes()
        + b"\0"
        + _asset(project, "guides.json").read_bytes()
    )


def _input_file(project: Path, name: Any) -> Path:
    if (
        not isinstance(name, str)
        or not name
        or Path(name).is_absolute()
        or ".." in Path(name).parts
    ):
        raise ProjectError("Referenced input must be a relative project file")
    return _asset(project, name)


def _alpha(project: Path, revision: str, master_id: str, shape: tuple[int, int]) -> np.ndarray:
    manifest = read_revision(project, revision, master_id)
    if "base_alpha16.png" not in manifest["files"]:
        raise ProjectError("Lock/parent needs saved revision alpha16; prepare alone has no alpha")
    with Image.open(_asset(project, f"revisions/{revision}/base_alpha16.png")) as image:
        if image.format != "PNG" or image.mode not in {"I;16", "I;16B", "I;16L"}:
            raise ProjectError("Saved alpha must be grayscale16 PNG")
        values = np.array(image, dtype=np.uint16)
    if values.shape != shape:
        raise ProjectError("Saved alpha dimensions differ from master")
    return values


def select_candidates(
    pixels: np.ndarray, recipe: Recipe, guides: dict[str, Any], cache: Path | None
) -> list[dict[str, Any]]:
    """Named native candidate membership masks; never opacity assertions."""
    group_ids = {group["id"] for group in recipe.groups}
    hints = [r for r in guides["regions"] if r["role"] in {"keep", "remove"}]
    if any(h["group_id"] not in group_ids for h in hints):
        raise ProjectError("SAM hint references undeclared group")
    session = None
    results = []
    for group in recipe.groups:
        own = [h for h in hints if h["group_id"] == group["id"]]
        if not own:
            if group.get("selected_candidate") is not None:
                raise ProjectError("Selected candidate needs recorded SAM prompts")
            continue
        boxes = [h["xyxy"] for h in own if h["shape"] == "box"]
        if len(boxes) > 1:
            raise ProjectError("Use one SAM box per named group")
        points = [h["xy"] for h in own if h["shape"] == "point"]
        labels = [1 if h["role"] == "keep" else 0 for h in own if h["shape"] == "point"]
        if session is None:
            if cache is None:
                raise ProjectError(
                    "SAM hints require explicit --model-cache or BLACKMASK_SAM_CACHE; no downloads"
                )
            session = SamSession(cache)
        prediction = session.select(
            pixels,
            points,
            labels,
            boxes[0] if boxes else None,
            recipe.device,
            master_id=recipe.master_id,
        )
        for index, mask in enumerate(prediction.masks):
            results.append(
                {
                    "id": f"{group['id']}-{index}",
                    "group_id": group["id"],
                    "index": index,
                    "selected": group.get("selected_candidate") == index,
                    "keep": group["keep"],
                    "material_policy": group["material_policy"],
                    "score": float(prediction.scores[index]),
                    "mask": mask,
                    "model": prediction.metadata,
                }
            )
    return results


def accept_trimap(
    project: Path, revision: str, master_id: str, inputs_digest: str
) -> dict[str, Any]:
    """Explicit human confirmation of the exact current authoritative prepared trimap."""
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        manifest = read_revision(project, revision, state["master_id"])
        if (
            master_id != state["master_id"]
            or revision != state["working_revision"]
            or inputs_digest != draft_digest(project)
            or inputs_digest != manifest.get("draft_digest")
        ):
            raise ProjectError("Stale trimap review identity, revision or draft digest")
        if manifest.get("kind") != "prepare" or not state["development_approved"]:
            raise ProjectError(
                "Trimap review requires current prepared revision and development approval"
            )
        record = {
            "schema_version": 1,
            "revision": revision,
            "master_id": master_id,
            "inputs_digest": inputs_digest,
            "manifest_sha256": digest(
                _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
            ),
            "trimap_sha256": manifest["files"]["trimap.png"],
            "confirmation": "explicit human trimap review",
        }
        before = _asset(project, "state.json").read_bytes()

        def recheck():
            if (
                before != _asset(project, "state.json").read_bytes()
                or draft_digest(project) != inputs_digest
                or digest(_asset(project, f"revisions/{revision}/manifest.json").read_bytes())
                != record["manifest_sha256"]
            ):
                raise ProjectError("Stale trimap review inputs")
            read_revision(project, revision, master_id)
            load_master(project, master_id)

        check_space(project, 1024**2)
        approvals = _asset(project, "approvals")
        approvals.mkdir(exist_ok=True)
        path = _asset(project, f"approvals/{revision}-trimap.json")
        recheck()
        if path.exists():
            if json.loads(path.read_bytes()) != record:
                raise ProjectError("Existing trimap approval differs; preserved")
        else:
            _atomic_json(path, record, replace_existing=False, validate_before_replace=recheck)
        return record


def accept_revision(project: Path, revision: str) -> dict[str, Any]:
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        manifest = read_revision(project, revision, state["master_id"])
        if manifest.get("kind") != "matte" or manifest.get("final_acceptable") is not True:
            raise ProjectError(
                "A prepared revision cannot be accepted as a final photo; matte and review required"
            )
        from .export import saved_layers

        saved_layers(project, revision, state["master_id"])
        captured = draft_digest(project)
        if (
            revision != state["working_revision"]
            or captured != manifest["draft_digest"]
            or not state["development_approved"]
        ):
            raise ProjectError("Stale final acceptance; current complete reviewed matte required")
        before = _asset(project, "state.json").read_bytes()
        manifest_bytes = _asset(project, f"revisions/{revision}/manifest.json").read_bytes()

        def recheck():
            if (
                before != _asset(project, "state.json").read_bytes()
                or captured != draft_digest(project)
                or manifest_bytes
                != _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
            ):
                raise ProjectError("Stale final acceptance inputs")
            saved_layers(project, revision, state["master_id"])

        check_space(project, 1024**2)
        state.update(accepted_revision=revision, status="accepted")
        _atomic_json(_asset(project, "state.json"), state, validate_before_replace=recheck)
        return state


def apply_operation(
    project: Path,
    operation: dict[str, Any],
    *,
    model_cache: Path | None = None,
    request_file: Path | None = None,
) -> dict[str, Any]:
    """Validate a prepare request, process snapshots, return actual identities and review paths."""
    project = _root(project)
    with project_lock(project):
        try:
            if isinstance(operation, dict) and operation.get("kind") == "matte":
                return _matte(project, operation, model_cache, request_file)
            return _prepare(project, operation, model_cache, request_file)
        except (ValueError, KeyError, TypeError) as error:
            if isinstance(error, ProjectError):
                raise
            raise ProjectError(f"Invalid operation: {error}") from error


def _prepare(
    project: Path, operation: dict[str, Any], model_cache: Path | None, request_file: Path | None
) -> dict[str, Any]:
    required = {"schema_version", "kind", "base_revision", "master_id", "inputs_digest"}
    optional = {"guide_edits_file", "scope_xyxy", "reason"}
    if (
        not isinstance(operation, dict)
        or not required <= set(operation)
        or set(operation) - required - optional
        or type(operation["schema_version"]) is not int
        or operation["schema_version"] != 1
        or operation["kind"] != "prepare"
        or ("reason" in operation and not isinstance(operation["reason"], str))
    ):
        raise ProjectError("Only typed schema-1 prepare operations are implemented")
    # Copy caller-owned request so mutation in another thread cannot change the snapshot.
    operation = json.loads(_json_bytes(operation))
    request_bytes = request_file.read_bytes() if request_file is not None else None
    if request_bytes is not None and json.loads(request_bytes) != operation:
        raise ProjectError("Stale request file changed before snapshot")
    state = read_project(project)
    if not state["development_approved"]:
        raise ProjectError("Explicit human development approval required before preparation")
    if (
        operation["master_id"] != state["master_id"]
        or operation["base_revision"] != state["working_revision"]
    ):
        raise ProjectError("Stale master, base revision or draft inputs_digest")
    snapshots = {
        name: _asset(project, name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    captured_digest = digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
    if (
        operation["inputs_digest"] != captured_digest
        or json.loads(snapshots["state.json"]) != state
    ):
        raise ProjectError("Stale draft digest or state changed before snapshot capture")
    pixels, metadata = load_master(project, state["master_id"])
    height, width = pixels.shape[:2]
    scope = coordinates(operation.get("scope_xyxy", [0, 0, width, height]), width, height, box=True)
    recipe = Recipe.from_dict(
        tomllib.loads(snapshots["recipe.toml"].decode()),
        state["master_id"],
        max_margin_px=max(width, height),
    )
    guides = validate_guides(
        json.loads(snapshots["guides.json"]), state["master_id"], width, height
    )
    external: dict[str, bytes] = {}
    if "guide_edits_file" in operation:
        name = operation["guide_edits_file"]
        external[name] = _input_file(project, name).read_bytes()
        guides = edit_guides(guides, json.loads(external[name]))
    parent = state["working_revision"]
    parent_manifest = read_revision(project, parent, state["master_id"]) if parent else None
    if parent_manifest:
        parent_guides = json.loads(_asset(project, f"revisions/{parent}/guides.json").read_bytes())
        effective = {r["id"]: r for r in guides["regions"]}
        actions = json.loads(external[operation["guide_edits_file"]])["actions"] if external else []
        removed = {a["id"] for a in actions if a["action"] == "remove"}
        for region in parent_guides["regions"]:
            if (
                region["role"] == "lock"
                and effective.get(region["id"]) != region
                and region["id"] not in removed
            ):
                raise ProjectError(
                    "Removing/changing saved lock requires explicit recorded remove action"
                )
    shape = (height, width)
    parent_alpha = (
        _alpha(project, parent, state["master_id"], shape)
        if parent_manifest and "base_alpha16.png" in parent_manifest["files"]
        else None
    )
    lock_revisions = {r["revision"] for r in guides["regions"] if r["role"] == "lock"}
    saved_alpha = {rev: _alpha(project, rev, state["master_id"], shape) for rev in lock_revisions}
    lock_manifest_hashes = {
        rev: digest(_asset(project, f"revisions/{rev}/manifest.json").read_bytes())
        for rev in lock_revisions
    }
    raster = rasterize_regions(
        guides, scope_xyxy=scope, saved_alpha=saved_alpha, parent_alpha=parent_alpha
    )
    check_space(project, pixels.nbytes * 8 + 1024**2)
    revisions = _asset(project, "revisions")
    revisions.mkdir(exist_ok=True)
    existing = [
        int(p.name[4:]) for p in revisions.iterdir() if re.fullmatch(r"rev-[0-9]{3,}", p.name)
    ]
    revision = f"rev-{max(existing, default=0) + 1:03d}"
    stage = Path(tempfile.mkdtemp(prefix=".prepare-", dir=revisions))
    (stage / "supports").mkdir()
    (stage / "inputs").mkdir()
    (stage / "recipe.toml").write_bytes(snapshots["recipe.toml"])
    (stage / "guides.json").write_bytes(_json_bytes(guides))
    (stage / "request.json").write_bytes(
        request_bytes if request_bytes is not None else _json_bytes(operation)
    )
    for name, data in snapshots.items():
        (stage / "inputs" / name).write_bytes(data)
    for index, (name, data) in enumerate(external.items()):
        (stage / "inputs" / f"external-{index}.json").write_bytes(data)
    Image.fromarray(raster.trimap).save(stage / "trimap.png")
    Image.fromarray(raster.support16).save(stage / "supports/support16.png")
    Image.fromarray(raster.protection.astype(np.uint8) * 255).save(
        stage / "supports/protection.png"
    )
    Image.fromarray(raster.lock_values16).save(stage / "supports/lock_values16.png")
    if parent_manifest:
        for name in ("base_alpha16.png", "corrected_rgb16.tif"):
            if name in parent_manifest["files"]:
                (stage / name).write_bytes(
                    _asset(project, f"revisions/{parent}/{name}").read_bytes()
                )
    # RGB8 is a separately labelled proxy. It never becomes a precision output owner.
    proxy = np.rint(pixels.astype(np.float64) / 257).astype(np.uint8)
    cache = model_cache or (
        Path(os.environ["BLACKMASK_SAM_CACHE"]) if "BLACKMASK_SAM_CACHE" in os.environ else None
    )
    candidates = select_candidates(proxy, recipe, guides, cache)
    proposal_groups = [group for group in recipe.groups if "morphology" in group]
    proposal_record = None
    if proposal_groups:
        proposal_raster, boundary = build_trimap_proposal(
            guides,
            recipe.groups,
            candidates,
            scope_xyxy=scope,
            saved_alpha=saved_alpha,
            parent_alpha=parent_alpha,
        )
        Image.fromarray(proposal_raster.trimap).save(stage / "trimap_proposal.png")
        Image.fromarray(boundary.astype(np.uint8) * 255).save(stage / "proposal_boundary.png")
        for name, proposed_expected in (
            ("trimap_proposal.png", proposal_raster.trimap),
            ("proposal_boundary.png", boundary.astype(np.uint8) * 255),
        ):
            with Image.open(stage / name) as image:
                if not np.array_equal(np.array(image), proposed_expected):
                    raise ProjectError("Morphology proposal round trip failed")
        proposal_record = {
            "review_status": "unreviewed",
            "trimap_file": "trimap_proposal.png",
            "boundary_file": "proposal_boundary.png",
            "groups": [
                {
                    "group_id": group["id"],
                    "candidate_id": f"{group['id']}-{group['selected_candidate']}",
                    "morphology": group["morphology"],
                }
                for group in proposal_groups
            ],
        }
    candidate_records = []
    membership = np.zeros(shape, dtype=bool)
    for candidate in candidates:
        mask = candidate.pop("mask")
        if mask.shape != shape or mask.dtype != np.bool_:
            raise ProjectError("Candidate native dimensions/type invalid")
        name = f"candidates/{candidate['id']}.png"
        (stage / "candidates").mkdir(exist_ok=True)
        Image.fromarray(mask.astype(np.uint8) * 255).save(stage / name)
        if candidate["selected"] and candidate["keep"]:
            membership |= mask
        candidate_records.append(dict(candidate, mask_file=name))
    Image.fromarray(membership.astype(np.uint8) * 255).save(stage / "selected_membership.png")
    Image.fromarray(proxy).save(stage / "source_proxy8.png")
    for name, expected in (
        ("trimap.png", raster.trimap),
        ("supports/support16.png", raster.support16),
        ("supports/protection.png", raster.protection.astype(np.uint8) * 255),
        ("supports/lock_values16.png", raster.lock_values16),
    ):
        with Image.open(stage / name) as image:
            if not np.array_equal(np.array(image), expected):
                raise ProjectError("Prepared asset round trip failed")
    (stage / "result.json").write_bytes(
        _json_bytes(
            {
                "revision": revision,
                "parent": parent,
                "master_id": state["master_id"],
                "kind": "prepare",
                "status": "review_needed",
                "final_acceptable": False,
                "trimap_file": "trimap.png",
                "support_file": "supports/support16.png",
                "protection_file": "supports/protection.png",
                "candidates": candidate_records,
                "proposal": proposal_record,
            }
        )
    )
    files = {
        str(path.relative_to(stage)): digest(path.read_bytes())
        for path in stage.rglob("*")
        if path.is_file()
    }
    new_guides = _json_bytes(guides) if external else snapshots["guides.json"]
    new_digest = digest(snapshots["recipe.toml"] + b"\0" + new_guides)
    manifest = {
        "schema_version": 1,
        "revision": revision,
        "parent": parent,
        "master_id": state["master_id"],
        "kind": "prepare",
        "complete": True,
        "final_acceptable": False,
        "inputs_digest": operation["inputs_digest"],
        "draft_digest": new_digest,
        "scope_xyxy": scope,
        "files": files,
        "candidates": candidate_records,
        "proposal": proposal_record,
        "external_inputs": {
            name: {"sha256": digest(data), "snapshot": f"inputs/external-{i}.json"}
            for i, (name, data) in enumerate(external.items())
        },
        "parent_manifest_sha256": digest(
            _asset(project, f"revisions/{parent}/manifest.json").read_bytes()
        )
        if parent
        else None,
        "source_precision_bits": metadata["source_precision_bits"],
        "proxy_precision_bits": 8,
        "trimap_review": "human review required; selection membership does not prove opacity",
    }
    (stage / "manifest.json").write_bytes(_json_bytes(manifest))
    for path in stage.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted((p for p in stage.rglob("*") if p.is_dir()), reverse=True):
        _sync_directory(path)
    _sync_directory(stage)
    # Publication checks bind to the consumed snapshot, then the explicitly published draft.
    publication_inputs = dict(snapshots)

    def check_inputs() -> None:
        if request_file is not None and request_file.read_bytes() != request_bytes:
            raise ProjectError("Stale request file changed during prepare")
        for name, data in publication_inputs.items():
            if _asset(project, name).read_bytes() != data:
                raise ProjectError(f"Stale input changed during prepare: {name}")
        for name, data in external.items():
            if _input_file(project, name).read_bytes() != data:
                raise ProjectError(f"Stale external input changed: {name}")

    check_inputs()
    load_master(project, state["master_id"])
    if parent:
        current_parent = read_revision(project, parent, state["master_id"])
        if (
            digest(_asset(project, f"revisions/{parent}/manifest.json").read_bytes())
            != manifest["parent_manifest_sha256"]
            or current_parent != parent_manifest
        ):
            raise ProjectError("Stale parent changed during prepare")
    for saved in lock_revisions:
        read_revision(project, saved, state["master_id"])
        if (
            digest(_asset(project, f"revisions/{saved}/manifest.json").read_bytes())
            != lock_manifest_hashes[saved]
        ):
            raise ProjectError("Stale saved lock dependency changed during prepare")
    destination = revisions / revision
    if destination.exists():
        raise ProjectError("Revision publication collision; preserved")
    _publish_new_directory(stage, destination)
    _sync_directory(revisions)
    read_revision(project, revision, state["master_id"])
    # Draft publication may precede a failed pointer write; accepted state remains exact and recoverable.
    if external:
        _atomic_json(_asset(project, "guides.json"), guides, validate_before_replace=check_inputs)
        publication_inputs["guides.json"] = new_guides
    state.update(working_revision=revision, status="review_needed")
    _atomic_json(_asset(project, "state.json"), state, validate_before_replace=check_inputs)
    return {
        "revision": revision,
        "parent": parent,
        "master_id": state["master_id"],
        "inputs_digest": new_digest,
        "status": "review_needed",
        "final_acceptable": False,
        "manifest_file": str(destination / "manifest.json"),
        "trimap_file": str(destination / "trimap.png"),
        "support_file": str(destination / "supports/support16.png"),
        "protection_file": str(destination / "supports/protection.png"),
        "source_proxy_file": str(destination / "source_proxy8.png"),
        "trimap_proposal_file": str(destination / "trimap_proposal.png")
        if proposal_record
        else None,
        "proposal_boundary_file": str(destination / "proposal_boundary.png")
        if proposal_record
        else None,
        "candidates": candidate_records,
        "proposal": proposal_record,
    }


def _matte(
    project: Path, operation: dict[str, Any], model_cache: Path | None, request_file: Path | None
) -> dict[str, Any]:
    import tifffile

    from .ingest import write_master
    from .matte import native_matte
    from .review import write_review

    required = {"schema_version", "kind", "base_revision", "master_id", "inputs_digest"}
    if (
        set(operation) - required - {"reason"}
        or not required <= set(operation)
        or type(operation["schema_version"]) is not int
        or operation["schema_version"] != 1
        or ("reason" in operation and not isinstance(operation["reason"], str))
    ):
        raise ProjectError("Invalid typed schema-1 matte operation; prepare guide changes first")
    operation = json.loads(_json_bytes(operation))
    request_bytes = request_file.read_bytes() if request_file else None
    if request_bytes is not None and json.loads(request_bytes) != operation:
        raise ProjectError("Stale request before matte snapshot")
    state = read_project(project)
    parent = state["working_revision"]
    if not state["development_approved"] or not parent:
        raise ProjectError("Matte requires approved development and human-reviewed prepared trimap")
    if (
        operation["master_id"] != state["master_id"]
        or operation["base_revision"] != parent
        or operation["inputs_digest"] != draft_digest(project)
    ):
        raise ProjectError("Stale matte master, revision or inputs_digest")
    manifest = read_revision(project, parent, state["master_id"])
    if manifest.get("kind") != "prepare":
        raise ProjectError("Prepare and explicitly review the trimap before each matte rerun")
    if manifest["draft_digest"] != operation["inputs_digest"]:
        raise ProjectError("Stale prepared draft; prepare and review changed guides/settings")
    approval_path = _asset(project, f"approvals/{parent}-trimap.json")
    if not approval_path.is_file():
        raise ProjectError("Explicit human trimap review required before native matte")
    approval_bytes = approval_path.read_bytes()
    approval = json.loads(approval_bytes)
    if not isinstance(approval, dict):
        raise ProjectError("Invalid trimap approval record")
    parent_bytes = _asset(project, f"revisions/{parent}/manifest.json").read_bytes()
    if (
        approval.get("revision") != parent
        or approval.get("master_id") != state["master_id"]
        or approval.get("inputs_digest") != operation["inputs_digest"]
        or approval.get("manifest_sha256") != digest(parent_bytes)
        or approval.get("trimap_sha256") != manifest["files"]["trimap.png"]
    ):
        raise ProjectError("Stale trimap approval assets")
    snapshots = {
        name: _asset(project, name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    if (
        json.loads(snapshots["state.json"]) != state
        or digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
        != operation["inputs_digest"]
    ):
        raise ProjectError("Stale matte snapshot")
    pixels, _ = load_master(project, state["master_id"])
    height, width = pixels.shape[:2]
    recipe = Recipe.from_dict(
        tomllib.loads(snapshots["recipe.toml"].decode()),
        state["master_id"],
        max_margin_px=max(width, height),
    )
    guides = json.loads(_asset(project, f"revisions/{parent}/guides.json").read_bytes())
    saved = {
        r["revision"]: _alpha(project, r["revision"], state["master_id"], (height, width))
        for r in guides["regions"]
        if r["role"] == "lock"
    }
    lock_hashes = {
        rev: digest(_asset(project, f"revisions/{rev}/manifest.json").read_bytes()) for rev in saved
    }
    raster = rasterize_regions(guides, scope_xyxy=manifest["scope_xyxy"], saved_alpha=saved)
    with Image.open(_asset(project, f"revisions/{parent}/trimap.png")) as image:
        trimap = np.array(image)
    if not np.array_equal(trimap, raster.trimap):
        raise ProjectError("Prepared trimap differs from confirmed typed guides")
    check_space(project, pixels.nbytes * 40 + 1024**2)
    foreground = pixels.copy()
    rgb_protection = np.zeros((height, width), dtype=bool)
    for region in guides["regions"]:
        if region["role"] != "lock":
            continue
        rev = region["revision"]
        locked_manifest = read_revision(project, rev, state["master_id"])
        name = (
            "foreground_rgb16.tif"
            if "foreground_rgb16.tif" in locked_manifest["files"]
            else "corrected_rgb16.tif"
            if "corrected_rgb16.tif" in locked_manifest["files"]
            else None
        )
        if name:
            values = tifffile.imread(_asset(project, f"revisions/{rev}/{name}"))
            if values.shape != pixels.shape or values.dtype != np.uint16:
                raise ProjectError("Invalid saved foreground lock RGB16")
            own = dict(guides, regions=[region])
            mask = rasterize_regions(
                own, scope_xyxy=manifest["scope_xyxy"], saved_alpha=saved
            ).protection
            if np.any(mask & rgb_protection & np.any(foreground != values, axis=2)):
                raise ProjectError("Conflicting saved foreground RGB lock values")
            foreground[mask] = values[mask]
            rgb_protection |= mask
    cache = model_cache or (
        Path(os.environ["BLACKMASK_VITMATTE_CACHE"])
        if "BLACKMASK_VITMATTE_CACHE" in os.environ
        else None
    )
    if np.any(trimap == 128) and cache is None:
        raise ProjectError(
            "Unknown pixels require explicit local ViTMatte model cache; no downloads"
        )
    session = VitMatteSession(cache) if np.any(trimap == 128) and cache else None

    def predict(rgb, guide, device):
        if session is None:
            raise ProjectError("ViTMatte session missing")
        return session.predict(rgb, guide, device)

    alpha, model_record = native_matte(
        np.rint(pixels.astype(np.float64) / 257).astype(np.uint8),
        trimap,
        predict,
        recipe.device,
        cache_dir=_asset(project, "cache/matte"),
        cache_identity={"master_id": state["master_id"], **session.identity} if session else None,
    )
    alpha[raster.protection] = raster.lock_values16[raster.protection]
    if np.any(alpha[trimap == 0] != 0) or np.any(alpha[trimap == 255] != 65535):
        raise ProjectError("Locked alpha contradicts known cores after matte")
    revisions = _asset(project, "revisions")
    existing = [
        int(p.name[4:]) for p in revisions.iterdir() if re.fullmatch(r"rev-[0-9]{3,}", p.name)
    ]
    revision = f"rev-{max(existing, default=0) + 1:03d}"
    stage = Path(tempfile.mkdtemp(prefix=".matte-", dir=revisions))
    for name in (
        "recipe.toml",
        "guides.json",
        "trimap.png",
        "supports/support16.png",
        "supports/protection.png",
        "supports/lock_values16.png",
    ):
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_asset(project, f"revisions/{parent}/{name}").read_bytes())
    (stage / "request.json").write_bytes(
        request_bytes if request_bytes is not None else _json_bytes(operation)
    )
    (stage / "trimap_approval.json").write_bytes(approval_bytes)
    (stage / "inputs").mkdir()
    for name, data in snapshots.items():
        (stage / "inputs" / name).write_bytes(data)
    Image.fromarray(alpha).save(stage / "base_alpha16.png")
    write_master(stage / "foreground_rgb16.tif", foreground)
    with Image.open(stage / "base_alpha16.png") as image:
        if image.mode not in {"I;16", "I;16L", "I;16B"} or not np.array_equal(
            np.array(image), alpha
        ):
            raise ProjectError("Alpha16 round trip failed")
    if not np.array_equal(tifffile.imread(stage / "foreground_rgb16.tif"), foreground):
        raise ProjectError("Foreground RGB16 round trip failed")
    write_review(
        stage / "review", pixels, foreground, alpha, master_id=state["master_id"], revision=revision
    )
    (stage / "qa.json").write_bytes(
        _json_bytes(
            {
                "structural_checks": "passed",
                "foreground_core_samples": int(np.count_nonzero(trimap == 255)),
                "background_core_samples": int(np.count_nonzero(trimap == 0)),
                "locked_samples": int(raster.protection.sum()),
                "human_photographic_review": "pending",
            }
        )
    )
    result = {
        "revision": revision,
        "parent": parent,
        "master_id": state["master_id"],
        "inputs_digest": operation["inputs_digest"],
        "kind": "matte",
        "status": "review_needed",
        "final_acceptable": True,
        "model": model_record,
    }
    (stage / "result.json").write_bytes(_json_bytes(result))
    files = {
        str(p.relative_to(stage)): digest(p.read_bytes()) for p in stage.rglob("*") if p.is_file()
    }
    new_manifest = {
        "schema_version": 1,
        **result,
        "complete": True,
        "draft_digest": operation["inputs_digest"],
        "files": files,
        "parent_manifest_sha256": digest(parent_bytes),
        "scope_xyxy": [0, 0, width, height],
        "foreground_asset": "foreground_rgb16.tif",
        "output_precision_bits": 16,
        "model_view_precision_bits": 8,
        "compositing": "encoded-sRGB float64 ties-to-even; alpha once",
    }
    (stage / "manifest.json").write_bytes(_json_bytes(new_manifest))
    for path in stage.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted((p for p in stage.rglob("*") if p.is_dir()), reverse=True):
        _sync_directory(path)
    _sync_directory(stage)

    def recheck():
        for name, data in snapshots.items():
            if _asset(project, name).read_bytes() != data:
                raise ProjectError(f"Stale input changed during matte: {name}")
        if request_file is not None and request_file.read_bytes() != request_bytes:
            raise ProjectError("Stale matte request file")
        if (
            approval_path.read_bytes() != approval_bytes
            or _asset(project, f"revisions/{parent}/manifest.json").read_bytes() != parent_bytes
        ):
            raise ProjectError("Stale prepared assets/approval")
        read_revision(project, parent, state["master_id"])
        load_master(project, state["master_id"])
        for rev, expected in lock_hashes.items():
            read_revision(project, rev, state["master_id"])
            if digest(_asset(project, f"revisions/{rev}/manifest.json").read_bytes()) != expected:
                raise ProjectError("Stale saved lock values")

    recheck()
    destination = revisions / revision
    if destination.exists():
        raise ProjectError("Revision collision; preserved")
    _publish_new_directory(stage, destination)
    _sync_directory(revisions)
    read_revision(project, revision, state["master_id"])
    state.update(working_revision=revision, status="review_needed")
    _atomic_json(_asset(project, "state.json"), state, validate_before_replace=recheck)
    return dict(
        result,
        manifest_file=str(destination / "manifest.json"),
        review_manifest_file=str(destination / "review/manifest.json"),
    )
