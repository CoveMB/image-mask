"""Preparation transaction: immutable snapshots, role validation and sole state publication."""

import json
import os
import re
import tempfile
import tomllib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import tomli_w
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
    _atomic_bytes,
    _atomic_json,
    _json_bytes,
    _publish_new_directory,
    _root,
    _sync_directory,
    _validate_assets,
    _validate_revision_directory,
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
        _reject_pending_guidance(project)
        manifest = read_revision(project, revision, state["master_id"])
        if (
            master_id != state["master_id"]
            or revision != state["working_revision"]
            or inputs_digest != draft_digest(project)
            or inputs_digest != manifest.get("draft_digest")
        ):
            raise ProjectError("Stale trimap review identity, revision or draft digest")
        if manifest.get("kind") != "prepare":
            raise ProjectError("Trimap review requires current prepared revision")
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
        _reject_pending_guidance(project)
        manifest = read_revision(project, revision, state["master_id"])
        if (
            manifest.get("kind") not in {"matte", "repair", "effects"}
            or manifest.get("final_acceptable") is not True
        ):
            raise ProjectError(
                "A prepared revision cannot be accepted as a final photo; matte and review required"
            )
        from .export import saved_layers

        saved_layers(project, revision, state["master_id"])
        from .effects import effects_stale

        if effects_stale(manifest):
            raise ProjectError(
                "Stale enabled cleanup/shading/local exposure/Shadow fade: scoped rebuild or explicit disable required before acceptance"
            )
        captured = draft_digest(project)
        if revision != state["working_revision"] or captured != manifest["draft_digest"]:
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
            if isinstance(operation, dict) and operation.get("kind") in {"matte", "repair"}:
                return _run_matte(project, operation, model_cache, request_file)
            if isinstance(operation, dict) and operation.get("kind") == "effects":
                from .effects import run_effects

                return run_effects(project, operation, request_file)
            return _prepare(project, operation, model_cache, request_file)
        except (ValueError, KeyError, TypeError) as error:
            if isinstance(error, ProjectError):
                raise
            raise ProjectError(f"Invalid operation: {error}") from error


def _prepare(
    project: Path, operation: dict[str, Any], model_cache: Path | None, request_file: Path | None
) -> dict[str, Any]:
    required = {"schema_version", "kind", "base_revision", "master_id", "inputs_digest"}
    optional = {"guide_edits_file", "scope_xyxy", "reason", "assisted_review"}
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
    assisted_inputs = {}
    if "assisted_review" in operation:
        from .review import validate_assisted

        validate_assisted(project, operation)
        review_name = operation["assisted_review"]["review_manifest_file"]
        review_bytes = _input_file(project, review_name).read_bytes()
        assisted_inputs[review_name] = digest(review_bytes)
        assisted_inputs.update(
            {
                str(Path(review_name).parent / name): checksum
                for name, checksum in json.loads(review_bytes)["view_files"].items()
            }
        )
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
                and (region["id"] not in removed or "assisted_review" in operation)
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
    check_space(project, pixels.nbytes * (9 if recipe.background is not None else 8) + 1024**2)
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
        for name in ("base_alpha16.png", "foreground_rgb16.tif", "corrected_rgb16.tif"):
            if name in parent_manifest["files"]:
                (stage / name).write_bytes(
                    _asset(project, f"revisions/{parent}/{name}").read_bytes()
                )
    from .effects import inherit_cleanup, inherit_exposure, inherit_shading, inherit_shadow_fade

    cleanup = inherit_cleanup(project, parent, stage, state["master_id"]) if parent else None
    shading = inherit_shading(project, parent, stage, state["master_id"]) if parent else None
    exposure = inherit_exposure(project, parent, stage, state["master_id"]) if parent else None
    fade = inherit_shadow_fade(project, parent, stage, state["master_id"]) if parent else None
    from .background import inherit_background

    background = inherit_background(
        project, parent, stage, state["master_id"], (height, width), recipe.background
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
        **({"color_cleanup": cleanup} if cleanup is not None else {}),
        **({"shading": shading} if shading is not None else {}),
        **({"local_exposure": exposure} if exposure is not None else {}),
        **({"shadow_fade": fade} if fade is not None else {}),
        **({"background": background} if background is not None else {}),
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
        for name, checksum in assisted_inputs.items():
            if digest(_input_file(project, name).read_bytes()) != checksum:
                raise ProjectError("Stale inspected review assets during preparation")
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


def _save_matte_request(
    project: Path,
    operation: dict[str, Any],
    snapshots: dict[str, bytes],
    dependencies: dict[str, str],
    request_file: Path | None,
    request_bytes: bytes | None,
) -> Path:
    requests = _asset(project, "requests")
    requests.mkdir(exist_ok=True)
    check_space(project, sum(map(len, snapshots.values())) * 3 + 1024**2)
    directory = Path(tempfile.mkdtemp(prefix="matte-", dir=requests))
    (directory / "inputs").mkdir()
    for name, data in snapshots.items():
        _atomic_bytes(directory / "inputs" / name, data, replace_existing=False)
    _atomic_json(directory / "operation.json", operation, replace_existing=False)
    _atomic_json(
        directory / "manifest.json",
        {
            "schema_version": 1,
            "operation_sha256": digest(
                _asset(project, f"requests/{directory.name}/operation.json").read_bytes()
            ),
            "inputs": {name: digest(data) for name, data in snapshots.items()},
            "dependencies": dependencies,
            "request_file": str(request_file.absolute()) if request_file else None,
            "request_sha256": digest(request_bytes) if request_bytes is not None else None,
        },
        replace_existing=False,
    )
    _sync_directory(directory)
    return directory


def retained_assisted_requests(project: Path, cycle_id: str) -> set[str]:
    """Reconcile cycle reservations against existing immutable recovery request snapshots."""
    checksums = set()
    for path in _asset(project, "requests").glob("matte-*/operation.json"):
        data = _asset(project, str(path.relative_to(project))).read_bytes()
        if cycle_id.encode() not in data:
            continue
        operation = json.loads(data)
        if operation.get("assisted_review", {}).get("cycle_id") == cycle_id:
            checksums.add(digest(_json_bytes(operation)))
    return checksums


def _verify_matte_request(
    project: Path, directory: Path, *, completed_revision: str | None = None
) -> dict[str, Any]:
    manifest = json.loads(_asset(project, f"requests/{directory.name}/manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or set(manifest.get("inputs", {}))
        != {"state.json", "source.json", "recipe.toml", "guides.json"}
        or not isinstance(manifest.get("dependencies"), dict)
        or not manifest["dependencies"]
        or digest(_asset(project, f"requests/{directory.name}/operation.json").read_bytes())
        != manifest.get("operation_sha256")
    ):
        raise ProjectError("Invalid recovery snapshot; restart from current reviewed inputs")
    operation = json.loads(
        _asset(project, f"requests/{directory.name}/operation.json").read_bytes()
    )
    for name, checksum in manifest["inputs"].items():
        saved = _asset(project, f"requests/{directory.name}/inputs/{name}").read_bytes()
        if digest(saved) != checksum:
            raise ProjectError(
                "Recovery snapshot hash mismatch; restart from current reviewed inputs"
            )
        if name == "state.json" and completed_revision is not None:
            continue
        if _asset(project, name).read_bytes() != saved:
            raise ProjectError(f"Stale recovery input {name}; restart from current reviewed inputs")
    for name, checksum in manifest["dependencies"].items():
        if digest(_input_file(project, name).read_bytes()) != checksum:
            raise ProjectError(
                f"Stale recovery dependency hash: {name}; restart from current reviewed inputs"
            )
    if manifest["request_file"] is not None:
        path = Path(manifest["request_file"])
        if (
            not path.is_file()
            or path.is_symlink()
            or digest(path.read_bytes()) != manifest["request_sha256"]
        ):
            raise ProjectError("Stale original request; restart with current reviewed inputs")
    state = read_project(project)
    if state["master_id"] != operation["master_id"] or (
        completed_revision is None and state["working_revision"] != operation["base_revision"]
    ):
        raise ProjectError("Stale recovery master/parent; restart from current reviewed inputs")
    return operation


def _run_matte(
    project: Path,
    operation: dict[str, Any],
    model_cache: Path | None,
    request_file: Path | None,
    directory: Path | None = None,
) -> dict[str, Any]:
    recovery: list[Path] = [] if directory is None else [directory]
    try:
        result = _matte(project, operation, model_cache, request_file, recovery)
        _atomic_json(
            recovery[0] / "progress.json",
            {
                "status": "review_needed",
                "phase": "complete",
                "revision": result["revision"],
            },
        )
        return dict(result, operation_id=recovery[0].name)
    except BaseException as error:
        if recovery:
            try:
                _atomic_json(
                    recovery[0] / "progress.json",
                    {
                        "status": "failed",
                        "phase": "interrupted",
                        "error": str(error),
                    },
                )
            except (OSError, ProjectError):
                pass  # Preserve the original failure; previous progress remains inspectable.
        raise


@contextmanager
def _recovery_record_errors() -> Iterator[None]:
    """Convert saved-record failures without relabelling retryable processing errors."""
    try:
        yield
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ProjectError):
            raise
        raise ProjectError(
            f"Invalid recovery record: {error}; restart from current reviewed inputs"
        ) from error


def resume_operation(
    project: Path, operation_id: str, *, model_cache: Path | None = None, source: Path | None = None
) -> dict[str, Any]:
    """Resume the same snapshotted matte/repair under the canonical writer lock."""
    project = _root(project)
    if not isinstance(operation_id, str) or re.fullmatch(r"matte-[a-z0-9_]+", operation_id) is None:
        raise ProjectError("Invalid recovery operation identity")
    with project_lock(project):
        directory = _asset(project, f"requests/{operation_id}")
        with _recovery_record_errors():
            if source is not None:
                record = json.loads(_asset(project, "source.json").read_bytes())
                if digest(source.read_bytes()) != record["source_sha256"]:
                    raise ProjectError("Moved source hash differs from recorded capture")
            completion = directory / "completion.json"
            has_completion = completion.is_file()
        if has_completion:
            with _recovery_record_errors():
                completed = json.loads(
                    _asset(project, f"requests/{directory.name}/completion.json").read_bytes()
                )
                revision = completed["revision"]
                if (
                    not isinstance(revision, str)
                    or re.fullmatch(r"rev-[0-9]{3,}", revision) is None
                ):
                    raise ProjectError("Invalid recovery completion revision")
                state = read_project(project)
                already_current = state["working_revision"] == revision
                operation = _verify_matte_request(
                    project, directory, completed_revision=revision if already_current else None
                )
                if "assisted_review" in operation:
                    from .review import validate_assisted

                    validate_assisted(project, operation, resuming=True)
                destination = _asset(project, f"revisions/{revision}")
                stage_name = completed["stage"]
                if (
                    not isinstance(stage_name, str)
                    or re.fullmatch(r"\.matte-[a-z0-9_]+", stage_name) is None
                ):
                    raise ProjectError("Invalid recovery stage")
                retained = (
                    destination
                    if destination.exists()
                    else _asset(project, f"revisions/{stage_name}")
                )
                manifest = _validate_revision_directory(
                    project, revision, operation["master_id"], f"revisions/{retained.name}"
                )
                if (
                    digest((retained / "manifest.json").read_bytes())
                    != completed["manifest_sha256"]
                    or manifest["parent"] != operation["base_revision"]
                    or manifest["draft_digest"] != operation["inputs_digest"]
                ):
                    raise ProjectError(
                        "Invalid completed recovery manifest; restart from current inputs"
                    )

                result = dict(json.loads((retained / "result.json").read_bytes()))

            def recheck():
                with _recovery_record_errors():
                    if "assisted_review" in operation:
                        validate_assisted(project, operation, resuming=True)
                    _verify_matte_request(
                        project, directory, completed_revision=revision if already_current else None
                    )
                    _validate_revision_directory(
                        project, revision, operation["master_id"], f"revisions/{retained.name}"
                    )

            check_space(project, 1024**2)
            recheck()
            if retained != destination:
                _publish_new_directory(retained, destination)
                retained = destination
                _sync_directory(destination.parent)
            if not already_current:
                state.update(working_revision=revision, status="review_needed")
                _atomic_json(_asset(project, "state.json"), state, validate_before_replace=recheck)
            _atomic_json(
                directory / "progress.json",
                {"status": "review_needed", "phase": "complete", "revision": revision},
            )
            return dict(result, operation_id=operation_id, resumed_completed_stage=True)
        with _recovery_record_errors():
            operation = _verify_matte_request(project, directory)
            manifest = json.loads(
                _asset(project, f"requests/{directory.name}/manifest.json").read_bytes()
            )
            request_file = Path(manifest["request_file"]) if manifest["request_file"] else None
        return _run_matte(
            project,
            operation,
            model_cache,
            request_file,
            directory,
        )


def operation_status(project: Path) -> dict[str, Any]:
    """Read saved pointers and recovery records without waiting for a writer."""
    project = _root(project)
    state = read_project(project, validate_drafts=False)
    busy = False
    try:
        with project_lock(project):
            pass
    except ProjectError as error:
        if "busy" not in str(error):
            raise
        busy = True
    records: list[dict[str, Any]] = []
    for path in sorted(_asset(project, "requests").glob("matte-*/manifest.json")):
        directory = _asset(project, str(path.parent.relative_to(project)))
        try:
            progress = json.loads(
                _asset(project, f"requests/{directory.name}/progress.json").read_bytes()
            )
            status = progress["status"]
            if status == "running" and not busy:
                status = "failed"
                progress["error"] = (
                    "Writer interrupted; resume verified work or restart from current inputs"
                )
            completion = directory / "completion.json"
            revision = (
                json.loads(
                    _asset(project, f"requests/{directory.name}/completion.json").read_bytes()
                )["revision"]
                if completion.is_file()
                else None
            )
            _verify_matte_request(
                project,
                directory,
                completed_revision=revision if revision == state["working_revision"] else None,
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            status, progress = (
                "stale",
                {
                    "error": str(error),
                    "recovery": "Restart from current reviewed inputs; retained artifacts are preserved",
                },
            )
        records.append(dict(progress, operation_id=directory.name, status=status))
    return dict(state, writer_busy=busy, operations=records)


def _matte(
    project: Path,
    operation: dict[str, Any],
    model_cache: Path | None,
    request_file: Path | None,
    recovery: list[Path],
) -> dict[str, Any]:
    import tifffile

    from .ingest import write_master
    from .matte import native_matte
    from .repair import (
        ORDER,
        prepared_parent_layers,
        replay_directory,
        scalar16,
        validate_merge,
        validate_support,
    )
    from .review import write_review

    repairing = operation["kind"] == "repair"
    required = {"schema_version", "kind", "base_revision", "master_id", "inputs_digest"}
    optional = {"reason"}
    if repairing:
        required |= {"context_xyxy", "scope_xyxy", "support_file"}
        optional |= {"merge_policy", "assisted_review"}
    if (
        set(operation) - required - optional
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
    _reject_pending_guidance(project)
    parent = state["working_revision"]
    if not parent:
        raise ProjectError("Matte requires a human-reviewed prepared trimap")
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
    context = [0, 0, width, height]
    scope = context
    policy = operation.get("merge_policy", "replace")
    support_path = None
    support_bytes = None
    parent_alpha = None
    ancestor_hashes: dict[str, str] = {}
    if repairing:
        context = coordinates(operation["context_xyxy"], width, height, box=True)
        scope = coordinates(operation["scope_xyxy"], width, height, box=True)
        if not isinstance(operation.get("reason"), str) or not operation["reason"].strip():
            raise ProjectError("Repair requires source-supported requested change/rationale")
        expected_support = _asset(project, f"revisions/{parent}/supports/support16.png")
        support_path = (
            expected_support
            if operation["support_file"] == str(expected_support)
            else _input_file(project, operation["support_file"])
        )
        if support_path != expected_support:
            raise ProjectError("Repair must consume returned immutable prepared support")
        support_bytes = support_path.read_bytes()
        support = scalar16(support_path)
        parent_alpha = _alpha(project, parent, state["master_id"], (height, width))
        validate_support(support, (height, width), context, scope)
        if not np.array_equal(support, raster.support16):
            raise ProjectError("Saved support differs from prepared guides")
        validate_merge(
            parent_alpha, support, raster.protection, raster.lock_values16, trimap, policy
        )
        prepared_parent_layers(project, parent, state["master_id"])
        ancestor = parent
        while ancestor:
            ancestor_manifest = read_revision(project, ancestor, state["master_id"])
            ancestor_hashes[ancestor] = digest(
                _asset(project, f"revisions/{ancestor}/manifest.json").read_bytes()
            )
            if ancestor_manifest.get("kind") != "prepare":
                break
            ancestor = ancestor_manifest["parent"]
    check_space(project, pixels.nbytes * (42 if recipe.background is not None else 40) + 1024**2)
    foreground = pixels.copy()
    if repairing:
        foreground = tifffile.imread(_asset(project, f"revisions/{parent}/foreground_rgb16.tif"))
        if foreground.shape != pixels.shape or foreground.dtype != np.uint16:
            raise ProjectError("Invalid repair parent foreground RGB16")
    applicable_parent_foreground = foreground
    if repairing and any(
        manifest.get(name, {}).get("enabled")
        for name in ("color_cleanup", "local_exposure", "shadow_fade")
    ):
        from .effects import saved_effect_lock_layers

        # The write boundary preserves the saved selected appearance, which may
        # differ from the base master RGB before this explicit lock is bound.
        applicable_parent_foreground, _, _ = saved_effect_lock_layers(
            project, parent, state["master_id"]
        )
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
            if any(
                locked_manifest.get(name, {}).get("enabled")
                for name in ("color_cleanup", "local_exposure", "shadow_fade")
            ):
                from .effects import saved_effect_lock_layers

                values, _, _ = saved_effect_lock_layers(project, rev, state["master_id"])
            if values.shape != pixels.shape or values.dtype != np.uint16:
                raise ProjectError("Invalid saved foreground lock RGB16")
            own = dict(guides, regions=[region])
            mask = rasterize_regions(
                own, scope_xyxy=manifest["scope_xyxy"], saved_alpha=saved
            ).protection
            if np.any(mask & rgb_protection & np.any(foreground != values, axis=2)):
                raise ProjectError("Conflicting saved foreground RGB lock values")
            if repairing and np.any(
                mask & (support == 0) & np.any(applicable_parent_foreground != values, axis=2)
            ):
                raise ProjectError("Saved RGB lock differs from parent outside repair support")
            foreground[mask] = values[mask]
            rgb_protection |= mask
    cache = model_cache or (
        Path(os.environ["BLACKMASK_VITMATTE_CACHE"])
        if "BLACKMASK_VITMATTE_CACHE" in os.environ
        else None
    )
    x0, y0, x1, y1 = context
    local_trimap = trimap[y0:y1, x0:x1]
    if np.any(local_trimap == 128) and cache is None:
        raise ProjectError(
            "Unknown pixels require explicit local ViTMatte model cache; no downloads"
        )
    from .review import reserve_assisted

    reserve_assisted(project, operation, resuming=bool(recovery))
    if not recovery:
        dependencies = {f"approvals/{parent}-trimap.json": digest(approval_bytes)}
        if "assisted_review" in operation:
            review_name = operation["assisted_review"]["review_manifest_file"]
            review_path = _input_file(project, review_name)
            dependencies[review_name] = digest(review_path.read_bytes())
            for name, checksum in json.loads(review_path.read_bytes())["view_files"].items():
                dependencies[str(Path(review_name).parent / name)] = checksum
        for saved_revision in {parent, *lock_hashes, *ancestor_hashes}:
            saved_manifest = read_revision(project, saved_revision, state["master_id"])
            dependencies[f"revisions/{saved_revision}/manifest.json"] = digest(
                _asset(project, f"revisions/{saved_revision}/manifest.json").read_bytes()
            )
            dependencies.update(
                {
                    f"revisions/{saved_revision}/{name}": checksum
                    for name, checksum in saved_manifest["files"].items()
                }
            )
        recovery.append(
            _save_matte_request(
                project, operation, snapshots, dependencies, request_file, request_bytes
            )
        )
    _atomic_json(recovery[0] / "progress.json", {"status": "running", "phase": "tiles"})
    session = VitMatteSession(cache) if np.any(local_trimap == 128) and cache else None

    def predict(rgb, guide, device):
        if session is None:
            raise ProjectError("ViTMatte session missing")
        return session.predict(rgb, guide, device)

    alpha, model_record = native_matte(
        np.rint(pixels[y0:y1, x0:x1].astype(np.float64) / 257).astype(np.uint8),
        local_trimap,
        predict,
        recipe.device,
        cache_dir=_asset(project, "cache/matte"),
        cache_identity={
            "master_id": state["master_id"],
            **session.identity,
            **({"context_xyxy": context} if repairing else {}),
        }
        if session
        else None,
    )
    if repairing:
        if parent_alpha is None:
            raise ProjectError("Missing repair parent alpha")
        candidate = parent_alpha.copy()
        candidate[y0:y1, x0:x1] = alpha
    else:
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
    if repairing:
        (stage / "repair").mkdir()
        (stage / "repair/parent_alpha16.png").write_bytes(
            _asset(project, f"revisions/{parent}/base_alpha16.png").read_bytes()
        )
        Image.fromarray(candidate).save(stage / "repair/candidate_alpha16.png")
        if support_bytes is None:
            raise ProjectError("Missing repair support snapshot")
        (stage / "repair/support16.png").write_bytes(support_bytes)
        (stage / "repair/merge.json").write_bytes(
            _json_bytes(
                {
                    "parent": parent,
                    "parent_manifest_sha256": digest(parent_bytes),
                    "master_id": state["master_id"],
                    "context_xyxy": context,
                    "scope_xyxy": scope,
                    "crop_mapping": {
                        "origin_xy": [x0, y0],
                        "dimensions_wh": [x1 - x0, y1 - y0],
                        "native_scale": 1,
                        "half_open": True,
                    },
                    "operation_order": ORDER,
                    "merge_policy": policy,
                    "rationale": operation["reason"],
                }
            )
        )
        alpha = replay_directory(stage)
    Image.fromarray(alpha).save(stage / "base_alpha16.png")
    write_master(stage / "foreground_rgb16.tif", foreground)
    with Image.open(stage / "base_alpha16.png") as image:
        if image.mode not in {"I;16", "I;16L", "I;16B"} or not np.array_equal(
            np.array(image), alpha
        ):
            raise ProjectError("Alpha16 round trip failed")
    if not np.array_equal(tifffile.imread(stage / "foreground_rgb16.tif"), foreground):
        raise ProjectError("Foreground RGB16 round trip failed")
    from .effects import (
        effects_stale,
        inherit_cleanup,
        inherit_exposure,
        inherit_shading,
        inherit_shadow_fade,
    )

    cleanup = inherit_cleanup(
        project, parent, stage, state["master_id"], alpha, foreground, rgb_protection
    )
    shading = inherit_shading(project, parent, stage, state["master_id"], alpha)
    exposure = inherit_exposure(project, parent, stage, state["master_id"], alpha, rgb_protection)
    fade = inherit_shadow_fade(project, parent, stage, state["master_id"], alpha, rgb_protection)
    from .background import inherit_background

    background = inherit_background(
        project, parent, stage, state["master_id"], (height, width), recipe.background
    )
    stale_effects = effects_stale(
        {
            "color_cleanup": cleanup or {},
            "shading": shading or {},
            "local_exposure": exposure or {},
            "shadow_fade": fade or {},
        }
    )
    review_weight = (
        scalar16(stage / "shadow_weight16.png")
        if shading and shading["enabled"] and not stale_effects
        else None
    )
    review_opacity = shading["opacity"] if shading and review_weight is not None else 0.0
    review_foreground = foreground
    if cleanup and cleanup["enabled"] and not stale_effects:
        review_foreground = tifffile.imread(stage / "corrected_rgb16.tif")
    from .exposure import selected_exposure

    review_foreground, clipping = selected_exposure(
        stage,
        review_foreground,
        alpha,
        {"master_id": state["master_id"], **({"local_exposure": exposure} if exposure else {})},
        exposure_off=stale_effects,
    )
    from .shadow_fade import selected_shadow_fade

    review_foreground = selected_shadow_fade(
        stage,
        review_foreground,
        alpha,
        {"master_id": state["master_id"], **({"shadow_fade": fade} if fade else {})},
        shadow_fade_off=stale_effects,
    )
    from .export import read_rgb16

    background_pixels = (
        read_rgb16(stage / "background/background_rgb16.tif")
        if background is not None and not stale_effects
        else None
    )
    write_review(
        stage / "review",
        pixels,
        review_foreground,
        alpha,
        background16=background_pixels,
        master_id=state["master_id"],
        revision=revision,
        crops=[context] if repairing else None,
        weight16=review_weight,
        opacity=review_opacity,
    )
    if repairing:
        if parent_alpha is None:
            raise ProjectError("Missing repair parent review alpha")
        before_foreground = tifffile.imread(
            _asset(project, f"revisions/{parent}/foreground_rgb16.tif")
        )
        if cleanup and cleanup["enabled"] and not stale_effects:
            from .export import read_rgb16

            # Prepared guides contain the requested new locks; the before panel
            # depicts the actual inherited appearance before those locks apply.
            before_foreground = read_rgb16(
                _asset(project, f"revisions/{parent}/corrected_rgb16.tif")
            )
        if (exposure or fade) and not stale_effects:
            from .effects import saved_effect_lock_layers

            before_foreground, _, _ = saved_effect_lock_layers(project, parent, state["master_id"])
        write_review(
            stage / "review-before",
            pixels,
            before_foreground,
            parent_alpha,
            background16=background_pixels,
            master_id=state["master_id"],
            revision=parent,
            crops=[context],
            weight16=review_weight,
            opacity=review_opacity,
        )
    if cleanup:
        for review_name in ("review", "review-before") if repairing else ("review",):
            path = stage / review_name / "manifest.json"
            record = json.loads(path.read_bytes())
            record["color_cleanup"] = cleanup
            record["label"] += (
                "; BASE-to-BASE comparison: cleanup OFF on both sides; stale enabled cleanup needs scoped rebuild or explicit disable"
                if stale_effects
                else f"; cleanup ON, latest scoped strength {cleanup['strength']}"
                if cleanup["enabled"]
                else "; cleanup OFF"
            )
            path.write_bytes(_json_bytes(record))
    if shading:
        for review_name in ("review", "review-before") if repairing else ("review",):
            path = stage / review_name / "manifest.json"
            record = json.loads(path.read_bytes())
            record["shading"] = shading
            record["label"] += (
                "; BASE-to-BASE comparison: cleanup OFF; shading OFF on both sides; stale enabled effects need scoped rebuild or explicit disable"
                if stale_effects
                else f"; shading ON; baked shading p={review_opacity}"
                if shading["enabled"]
                else "; shading OFF"
            )
            path.write_bytes(_json_bytes(record))
    if exposure:
        for review_name in ("review", "review-before") if repairing else ("review",):
            path = stage / review_name / "manifest.json"
            record = json.loads(path.read_bytes())
            record["local_exposure"] = exposure
            record["local_exposure_clipping"] = clipping
            record["label"] += (
                "; local exposure OFF; BASE comparison, rebuild or disable stale effects"
                if stale_effects
                else f"; local exposure {'ON' if exposure['enabled'] else 'OFF'}"
            )
            path.write_bytes(_json_bytes(record))
    if fade:
        for review_name in ("review", "review-before") if repairing else ("review",):
            path = stage / review_name / "manifest.json"
            record = json.loads(path.read_bytes())
            record["shadow_fade"] = fade
            record["label"] += (
                "; Shadow fade OFF; BASE comparison"
                if stale_effects
                else f"; Shadow fade {'ON' if fade['enabled'] else 'OFF'}"
            )
            path.write_bytes(_json_bytes(record))
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
        "kind": "repair" if repairing else "matte",
        "status": "review_needed",
        "final_acceptable": True,
        "model": model_record,
        **({"color_cleanup": cleanup} if cleanup is not None else {}),
        **({"shading": shading} if shading is not None else {}),
        **({"local_exposure": exposure} if exposure is not None else {}),
        **({"shadow_fade": fade} if fade is not None else {}),
        **({"background": background} if background is not None else {}),
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
        "scope_xyxy": scope,
        "context_xyxy": context,
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
    _atomic_json(
        recovery[0] / "completion.json",
        {
            "revision": revision,
            "stage": stage.name,
            "manifest_sha256": digest((stage / "manifest.json").read_bytes()),
        },
    )

    def recheck():
        if "assisted_review" in operation:
            from .review import validate_assisted

            validate_assisted(project, operation, resuming=True)
        if support_path is not None and support_path.read_bytes() != support_bytes:
            raise ProjectError("Stale repair support")
        for ancestor, expected in ancestor_hashes.items():
            read_revision(project, ancestor, state["master_id"])
            if (
                digest(_asset(project, f"revisions/{ancestor}/manifest.json").read_bytes())
                != expected
            ):
                raise ProjectError("Stale repair ancestral operands")
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

    _verify_matte_request(project, recovery[0])
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


def restore_revision(
    project: Path,
    revision: str,
    *,
    replace_drafts: bool = False,
    expected_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select saved working inputs; acceptance is never reassigned."""
    project = _root(project)
    with project_lock(project):
        state = read_project(project, validate_drafts=not replace_drafts)
        if expected_identity is not None and (
            expected_identity.get("master_id") != state["master_id"]
            or expected_identity.get("base_revision") != state["working_revision"]
            or expected_identity.get("inputs_digest") != draft_digest(project)
            or (
                "authoring_digest" in expected_identity
                and expected_identity["authoring_digest"] != guidance_draft_digest(project)
            )
        ):
            raise ProjectError("Stale restore viewer identity")
        pending_invalid = False
        try:
            pending = pending_guidance(project)
        except ProjectError:
            if not replace_drafts:
                raise
            pending, pending_invalid = None, True
        if pending and pending["current"] and pending["actions"] and not replace_drafts:
            raise ProjectError(
                "Saved pending authoring needs explicit draft replacement for restore"
            )
        target = read_revision(project, revision, state["master_id"])
        if target.get("kind") not in {"prepare", "matte", "repair", "effects"}:
            raise ProjectError("Unsupported saved revision for restore")
        current = state["working_revision"]
        expected_draft_digest = target["draft_digest"]
        if current is not None:
            current_manifest = read_revision(project, current, state["master_id"])
            expected_draft_digest = current_manifest["draft_digest"]
        if not replace_drafts and draft_digest(project) != expected_draft_digest:
            raise ProjectError(
                "Unsaved draft edits; preserve them or explicitly use --replace-drafts"
            )
        snapshots = {
            name: _asset(project, name).read_bytes()
            for name in ("state.json", "source.json", "recipe.toml", "guides.json")
        }
        pending_path = _asset(project, "viewer-draft.json")
        if pending_path.exists():
            snapshots["viewer-draft.json"] = pending_path.read_bytes()
        if json.loads(snapshots["state.json"]) != state:
            raise ProjectError("Stale restore state before snapshot")
        if (
            not replace_drafts
            and digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
            != expected_draft_digest
        ):
            raise ProjectError("Unsaved draft edits captured during restore")
        current_bytes = (
            _asset(project, f"revisions/{current}/manifest.json").read_bytes() if current else None
        )
        if current_bytes is not None and json.loads(current_bytes) != current_manifest:
            raise ProjectError("Stale working revision before restore snapshot")
        target_bytes = _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        recipe = _asset(project, f"revisions/{revision}/recipe.toml").read_bytes()
        guides = _asset(project, f"revisions/{revision}/guides.json").read_bytes()
        if json.loads(target_bytes) != target:
            raise ProjectError("Stale restore target before snapshot")
        if digest(recipe + b"\0" + guides) != target["draft_digest"]:
            # Earlier prepare/matte revisions normalize guides but retain the exact
            # effective editable draft in their hashed input snapshots.
            if not {"inputs/recipe.toml", "inputs/guides.json"} <= set(target["files"]):
                raise ProjectError("Invalid saved restore draft digest")
            recipe = _asset(project, f"revisions/{revision}/inputs/recipe.toml").read_bytes()
            guides = _asset(project, f"revisions/{revision}/inputs/guides.json").read_bytes()
            if digest(recipe + b"\0" + guides) != target["draft_digest"]:
                raise ProjectError("Invalid saved restore draft digest")
        pixels, _ = _validate_assets(project, state, validate_drafts=not replace_drafts)
        Recipe.from_dict(
            tomllib.loads(recipe.decode()), state["master_id"], max_margin_px=max(pixels.shape[:2])
        )
        validate_guides(json.loads(guides), state["master_id"], pixels.shape[1], pixels.shape[0])
        check_space(
            project, sum(map(len, snapshots.values())) * 3 + len(recipe) + len(guides) + 1024**2
        )
        recovery = _asset(project, "recovery")
        recovery.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix="restore-", dir=recovery))
        for name, data in snapshots.items():
            (stage / name).write_bytes(data)
        (stage / "request.json").write_bytes(
            _json_bytes(
                {
                    "revision": revision,
                    "master_id": state["master_id"],
                    "replace_drafts": replace_drafts,
                    "target_manifest_sha256": digest(target_bytes),
                }
            )
        )
        for path in stage.iterdir():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        _sync_directory(stage)
        _sync_directory(recovery)
        publication_inputs = dict(snapshots)

        def recheck():
            for name, data in publication_inputs.items():
                if _asset(project, name).read_bytes() != data:
                    raise ProjectError(f"Stale input changed during restore: {name}")
            if _asset(project, f"revisions/{revision}/manifest.json").read_bytes() != target_bytes:
                raise ProjectError("Stale restore target")
            if current:
                read_revision(project, current, state["master_id"])
                if (
                    _asset(project, f"revisions/{current}/manifest.json").read_bytes()
                    != current_bytes
                ):
                    raise ProjectError("Stale working revision during restore")
            read_revision(project, revision, state["master_id"])
            _validate_assets(project, state, validate_drafts=not replace_drafts)

        # Files are atomic individually; recovery retains all original bytes on interruption.
        for name, data in (("recipe.toml", recipe), ("guides.json", guides)):
            _atomic_bytes(_asset(project, name), data, validate_before_replace=recheck)
            publication_inputs[name] = data
        if "viewer-draft.json" in snapshots:
            retired = (
                {"superseded_by_restore": True, "unreadable": True}
                if pending_invalid or pending is None
                else dict(json.loads(snapshots["viewer-draft.json"]), superseded_by_restore=True)
            )
            _atomic_json(pending_path, retired, validate_before_replace=recheck)
            publication_inputs["viewer-draft.json"] = _json_bytes(retired)
        state.update(
            working_revision=revision,
            status=("accepted" if state["accepted_revision"] == revision else "review_needed"),
        )
        _atomic_json(_asset(project, "state.json"), state, validate_before_replace=recheck)
        return dict(state, inputs_digest=target["draft_digest"], recovery_directory=str(stage))


def _check_draft_identity(project: Path, identity: dict[str, Any]) -> dict[str, Any]:
    state = read_project(project)
    if (
        identity.get("master_id") != state["master_id"]
        or identity.get("base_revision") != state["working_revision"]
        or identity.get("inputs_digest") != draft_digest(project)
        or (
            "authoring_digest" in identity
            and identity["authoring_digest"] != guidance_draft_digest(project)
        )
    ):
        raise ProjectError("Stale master, revision or draft inputs_digest; reload before editing")
    return state


def save_guidance_draft(
    project: Path, identity: dict[str, Any], groups: Any, actions: Any
) -> dict[str, Any]:
    """Save typed pending edits, never silently replace/remove a persistent lock."""
    project = _root(project)
    with project_lock(project):
        state = _check_draft_identity(project, identity)
        snapshots = {
            name: _asset(project, name).read_bytes()
            for name in ("recipe.toml", "guides.json", "state.json")
        }
        captured_authoring = guidance_draft_digest(project)

        def recheck() -> None:
            read_project(project)
            if (
                any(_asset(project, name).read_bytes() != data for name, data in snapshots.items())
                or guidance_draft_digest(project) != captured_authoring
            ):
                raise ProjectError("Stale drafts changed during authoring save")

        guides = json.loads(snapshots["guides.json"])
        edits = {"schema_version": 1, "master_id": state["master_id"], "actions": actions}
        edited = edit_guides(guides, edits)
        for region in edited["regions"]:
            if region["role"] == "lock":
                _alpha(
                    project,
                    region["revision"],
                    state["master_id"],
                    (guides["height"], guides["width"]),
                )
        recipe = tomllib.loads(snapshots["recipe.toml"].decode())
        recipe["groups"] = groups
        Recipe.from_dict(
            recipe, state["master_id"], max_margin_px=max(guides["width"], guides["height"])
        )
        check_space(project, len(_json_bytes(edits)) * 3 + 1024**2)
        # Retain exact prior recipe and every typed edit file for interruption/recovery.
        directory = _asset(project, "requests")
        directory.mkdir(exist_ok=True)
        name = f"requests/viewer-{uuid.uuid4().hex}.json"
        record = dict(edits, groups=groups, previous_recipe=snapshots["recipe.toml"].decode())
        _atomic_json(_asset(project, name), record, replace_existing=False)
        edits_name = f"requests/viewer-edits-{uuid.uuid4().hex}.json"
        _atomic_json(_asset(project, edits_name), edits, replace_existing=False)
        new_recipe = tomli_w.dumps(recipe).encode()
        _atomic_bytes(_asset(project, "recipe.toml"), new_recipe, validate_before_replace=recheck)
        snapshots["recipe.toml"] = new_recipe
        pending = {
            "master_id": state["master_id"],
            "base_revision": state["working_revision"],
            "inputs_digest": digest(new_recipe + b"\0" + snapshots["guides.json"]),
            "record_file": name,
            "guide_edits_file": edits_name,
            "actions": actions,
        }
        _atomic_json(_asset(project, "viewer-draft.json"), pending, validate_before_replace=recheck)
        return pending


def prepare_guidance_draft(
    project: Path, identity: dict[str, Any], scope: list[int], *, model_cache: Path | None = None
) -> dict[str, Any]:
    """Consume current pending typed edits once through the canonical preparation owner."""
    project = _root(project)
    with project_lock(project):
        state = _check_draft_identity(project, identity)
        operation = {
            "schema_version": 1,
            "kind": "prepare",
            "master_id": state["master_id"],
            "base_revision": state["working_revision"],
            "inputs_digest": draft_digest(project),
            "scope_xyxy": scope,
        }
        pending = pending_guidance(project)
        if pending is not None and pending["current"]:
            operation["guide_edits_file"] = pending["guide_edits_file"]
        return _prepare(project, operation, model_cache, None)


def pending_guidance(project: Path) -> dict[str, Any] | None:
    """A restored identity must never reapply a previously consumed edit batch."""
    try:
        path = _asset(project, "viewer-draft.json")
        if not path.exists():
            return None
        pending = json.loads(path.read_bytes())
        if pending == {"superseded_by_restore": True, "unreadable": True}:
            return None
        if (
            not isinstance(pending, dict)
            or re.fullmatch(r"requests/viewer-[a-f0-9]{32}\.json", str(pending.get("record_file")))
            is None
            or re.fullmatch(
                r"requests/viewer-edits-[a-f0-9]{32}\.json", str(pending.get("guide_edits_file"))
            )
            is None
        ):
            raise ProjectError("Invalid saved authoring record identity")
        edits = json.loads(_input_file(project, pending["guide_edits_file"]).read_bytes())
        record = json.loads(_input_file(project, pending["record_file"]).read_bytes())
        if (
            edits
            != {
                "schema_version": 1,
                "master_id": pending["master_id"],
                "actions": pending["actions"],
            }
            or record["actions"] != pending["actions"]
        ):
            raise ProjectError("Saved authoring snapshot differs from pending typed edits")
        state = read_project(project, validate_drafts=False)
        consumed = any(
            pending["guide_edits_file"]
            in read_revision(project, p.name, state["master_id"]).get("external_inputs", {})
            for p in _asset(project, "revisions").glob("rev-*")
            if re.fullmatch(r"rev-[0-9]{3,}", p.name)
        )
        current = (
            not consumed
            and not pending.get("superseded_by_restore", False)
            and pending["master_id"] == state["master_id"]
            and pending["base_revision"] == state["working_revision"]
            and pending["inputs_digest"] == draft_digest(project)
        )
        return dict(pending, current=current, consumed=consumed, groups=record["groups"])
    except ProjectError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ProjectError(f"Invalid saved authoring record: {error}") from error


def guidance_draft_digest(project: Path) -> str:
    path = _asset(project, "viewer-draft.json")
    return digest(path.read_bytes() if path.exists() else b"")


def _reject_pending_guidance(project: Path) -> None:
    pending = pending_guidance(project)
    if pending and pending["current"] and pending["actions"]:
        raise ProjectError("Saved pending guidance requires prepare and trimap review first")
