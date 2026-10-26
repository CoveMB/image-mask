"""Preparation transaction: immutable snapshots, role validation and sole state publication."""

import hashlib
import json
import os
import re
import stat
import tempfile
import tomllib
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import tomli_w
from PIL import Image

from .assets import (
    collect_stage_assets,
    inherit_revision_files,
    revision_asset,
    revision_hashes,
    saved_asset,
    stage_asset,
)
from .guidance import (
    build_trimap_proposal,
    coordinates,
    edit_guides,
    rasterize_regions,
    validate_guides,
)
from .library import StorageConfig, validate_library_project
from .models import SamSession, VitMatteSession
from .project import (
    ProjectError,
    _atomic_bytes,
    _atomic_json,
    _directory,
    _json_bytes,
    _publish_new_directory,
    _root,
    _sync_directory,
    _validate_assets,
    _validate_revision_directory,
    check_space,
    digest,
    load_developed,
    project_lock,
    project_writer_busy,
    read_project,
    read_revision,
    record_generated_result,
)
from .recipe import Recipe


def _result_preview(
    project: Path, result: dict[str, Any], config: StorageConfig | None, *, generated: bool = False
) -> dict[str, Any]:
    from .previews import _refresh_result_preview_locked, result_preview_status

    # Native state already committed. Context/publication failures belong to the
    # derivative status, while the entrypoint's preflight still guards native work.
    preview = result_preview_status(project, config)
    if preview["status"] == "not_applicable":
        return result
    if (
        generated
        and config is not None
        and result.get("revision") == preview["latest_result_revision"]
    ):
        preview = _refresh_result_preview_locked(project, config)
    return dict(result, preview=preview, preview_pending=preview["status"] == "pending")


def draft_digest(project: Path) -> str:
    return digest(
        saved_asset(project, "recipe.toml").read_bytes()
        + b"\0"
        + saved_asset(project, "guides.json").read_bytes()
    )


def _input_file(project: Path, name: Any) -> Path:
    if (
        not isinstance(name, str)
        or not name
        or Path(name).is_absolute()
        or ".." in Path(name).parts
    ):
        raise ProjectError("Referenced input must be a relative project file")
    return saved_asset(project, name)


def _alpha(project: Path, revision: str, developed_id: str, shape: tuple[int, int]) -> np.ndarray:
    manifest = read_revision(project, revision, developed_id)
    if "base_alpha16.png" not in revision_hashes(manifest):
        raise ProjectError("Lock/parent needs saved revision alpha16; prepare alone has no alpha")
    with Image.open(saved_asset(project, f"revisions/{revision}/base_alpha16.png")) as image:
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
            developed_id=recipe.developed_id,
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
    project: Path, revision: str, developed_id: str, inputs_digest: str
) -> dict[str, Any]:
    """Explicit human confirmation of the exact current authoritative prepared trimap."""
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        _reject_pending_guidance(project)
        manifest = read_revision(project, revision, state["developed_id"])
        if (
            developed_id != state["developed_id"]
            or revision != state["working_revision"]
            or inputs_digest != draft_digest(project)
            or inputs_digest != manifest.get("draft_digest")
        ):
            raise ProjectError("Stale trimap review identity, revision or draft digest")
        if manifest.get("kind") != "prepare":
            raise ProjectError("Trimap review requires current prepared revision")
        record = {
            "schema_version": 2,
            "revision": revision,
            "developed_id": developed_id,
            "inputs_digest": inputs_digest,
            "manifest_sha256": digest(
                saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
            ),
            "trimap_sha256": revision_hashes(manifest)["trimap.png"],
            "confirmation": "explicit human trimap review",
        }
        before = saved_asset(project, "state.json").read_bytes()

        def recheck():
            if (
                before != saved_asset(project, "state.json").read_bytes()
                or draft_digest(project) != inputs_digest
                or digest(saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes())
                != record["manifest_sha256"]
            ):
                raise ProjectError("Stale trimap review inputs")
            read_revision(project, revision, developed_id)
            load_developed(project, developed_id)

        check_space(project, 1024**2)
        approvals = saved_asset(project, "approvals")
        approvals.mkdir(exist_ok=True)
        path = saved_asset(project, f"approvals/{revision}-trimap.json")
        recheck()
        if path.exists():
            if json.loads(path.read_bytes()) != record:
                raise ProjectError("Existing trimap approval differs; preserved")
        else:
            _atomic_json(path, record, replace_existing=False, validate_before_replace=recheck)
        return record


def accept_revision(
    project: Path, revision: str, *, storage_config: StorageConfig | None = None
) -> dict[str, Any]:
    project = _root(project)
    bundle = validate_library_project(project, storage_config)
    with project_lock(project):
        state = read_project(project)
        _reject_pending_guidance(project)
        manifest = read_revision(project, revision, state["developed_id"])
        if (
            manifest.get("kind") not in {"matte", "repair", "effects"}
            or manifest.get("final_acceptable") is not True
        ):
            raise ProjectError(
                "A prepared revision cannot be accepted as a final photo; matte and review required"
            )
        from .export import saved_layers

        saved_layers(project, revision, state["developed_id"])
        from .effects import effects_stale

        if effects_stale(manifest):
            raise ProjectError(
                "Stale enabled cleanup/shading/local exposure/Shadow fade: scoped rebuild or explicit disable required before acceptance"
            )
        captured = draft_digest(project)
        if revision != state["working_revision"] or captured != manifest["draft_digest"]:
            raise ProjectError("Stale final acceptance; current complete reviewed matte required")
        before = saved_asset(project, "state.json").read_bytes()
        manifest_bytes = saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()

        def recheck():
            if (
                before != saved_asset(project, "state.json").read_bytes()
                or captured != draft_digest(project)
                or manifest_bytes
                != saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
            ):
                raise ProjectError("Stale final acceptance inputs")
            saved_layers(project, revision, state["developed_id"])

        check_space(project, 1024**2)
        if bundle is not None:
            from .previews import _demote_result_preview_locked

            assert storage_config is not None
            _demote_result_preview_locked(project, storage_config)
            recheck()
        state.update(accepted_revision=revision, status="accepted")
        _atomic_json(saved_asset(project, "state.json"), state, validate_before_replace=recheck)
        if bundle is not None:
            from .previews import _refresh_result_preview_locked

            assert storage_config is not None
            preview = _refresh_result_preview_locked(project, storage_config)
            return dict(state, preview=preview, preview_pending=preview["status"] == "pending")
        return state


def apply_operation(
    project: Path,
    operation: dict[str, Any],
    *,
    model_cache: Path | None = None,
    request_file: Path | None = None,
    expected_revision_manifest_sha256: str | None = None,
    storage_config: StorageConfig | None = None,
) -> dict[str, Any]:
    """Validate a prepare request, process snapshots, return actual identities and review paths."""
    project = _root(project)
    validate_library_project(project, storage_config)
    with project_lock(project):
        try:
            if expected_revision_manifest_sha256 is not None:
                if (
                    not isinstance(expected_revision_manifest_sha256, str)
                    or re.fullmatch(r"[a-f0-9]{64}", expected_revision_manifest_sha256) is None
                ):
                    raise ProjectError("Invalid expected raw revision manifest identity")
                state = read_project(project)
                parent = state["working_revision"]
                if (
                    not parent
                    or digest(
                        saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes()
                    )
                    != expected_revision_manifest_sha256
                ):
                    raise ProjectError("Stale raw revision manifest; reload the selected result")
            if isinstance(operation, dict) and operation.get("kind") in {"matte", "repair"}:
                return _result_preview(
                    project,
                    _run_matte(project, operation, model_cache, request_file),
                    storage_config,
                    generated=True,
                )
            if isinstance(operation, dict) and operation.get("kind") == "effects":
                from .effects import run_effects

                return _result_preview(
                    project,
                    run_effects(project, operation, request_file),
                    storage_config,
                    generated=True,
                )
            return _result_preview(
                project, _prepare(project, operation, model_cache, request_file), storage_config
            )
        except (ValueError, KeyError, TypeError) as error:
            if isinstance(error, ProjectError):
                raise
            raise ProjectError(f"Invalid operation: {error}") from error


def _prepare(
    project: Path, operation: dict[str, Any], model_cache: Path | None, request_file: Path | None
) -> dict[str, Any]:
    required = {"schema_version", "kind", "base_revision", "developed_id", "inputs_digest"}
    optional = {"guide_edits_file", "scope_xyxy", "reason", "assisted_review"}
    if (
        not isinstance(operation, dict)
        or not required <= set(operation)
        or set(operation) - required - optional
        or type(operation["schema_version"]) is not int
        or operation["schema_version"] != 2
        or operation["kind"] != "prepare"
        or ("reason" in operation and not isinstance(operation["reason"], str))
    ):
        raise ProjectError("Only typed schema-2 prepare operations are implemented")
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
        operation["developed_id"] != state["developed_id"]
        or operation["base_revision"] != state["working_revision"]
    ):
        raise ProjectError("Stale master, base revision or draft inputs_digest")
    snapshots = {
        name: saved_asset(project, name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    captured_digest = digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
    if (
        operation["inputs_digest"] != captured_digest
        or json.loads(snapshots["state.json"]) != state
    ):
        raise ProjectError("Stale draft digest or state changed before snapshot capture")
    pixels, metadata = load_developed(project, state["developed_id"])
    height, width = pixels.shape[:2]
    scope = coordinates(operation.get("scope_xyxy", [0, 0, width, height]), width, height, box=True)
    recipe = Recipe.from_dict(
        tomllib.loads(snapshots["recipe.toml"].decode()),
        state["developed_id"],
        max_margin_px=max(width, height),
        dimensions_wh=(width, height),
    )
    guides = validate_guides(
        json.loads(snapshots["guides.json"]), state["developed_id"], width, height
    )
    external: dict[str, bytes] = {}
    if "guide_edits_file" in operation:
        name = operation["guide_edits_file"]
        external[name] = _input_file(project, name).read_bytes()
        guides = edit_guides(guides, json.loads(external[name]))
    parent = state["working_revision"]
    parent_manifest = read_revision(project, parent, state["developed_id"]) if parent else None
    if parent_manifest:
        parent_guides = json.loads(
            saved_asset(project, f"revisions/{parent}/guides.json").read_bytes()
        )
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
        _alpha(project, parent, state["developed_id"], shape)
        if parent_manifest and "base_alpha16.png" in revision_hashes(parent_manifest)
        else None
    )
    lock_revisions = {r["revision"] for r in guides["regions"] if r["role"] == "lock"}
    saved_alpha = {
        rev: _alpha(project, rev, state["developed_id"], shape) for rev in lock_revisions
    }
    lock_manifest_hashes = {
        rev: digest(saved_asset(project, f"revisions/{rev}/manifest.json").read_bytes())
        for rev in lock_revisions
    }
    raster = rasterize_regions(
        guides, scope_xyxy=scope, saved_alpha=saved_alpha, parent_alpha=parent_alpha
    )
    check_space(project, pixels.nbytes * (9 if recipe.background is not None else 8) + 1024**2)
    revisions = saved_asset(project, "revisions")
    revisions.mkdir(exist_ok=True)
    existing = [
        int(p.name[4:]) for p in revisions.iterdir() if re.fullmatch(r"rev-[0-9]{3,}", p.name)
    ]
    revision = f"rev-{max(existing, default=0) + 1:03d}"
    stage = Path(tempfile.mkdtemp(prefix=".prepare-", dir=revisions))
    assets: dict[str, Any] = {}
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
            if name in revision_hashes(parent_manifest):
                inherit_revision_files(project, parent, stage, assets, (name,))
    from .effects import (
        inherit_cleanup,
        inherit_exposure,
        inherit_local_sharpening,
        inherit_shading,
        inherit_shadow_fade,
        inherit_spatial_fade,
    )

    cleanup = (
        inherit_cleanup(project, parent, stage, state["developed_id"], assets=assets)
        if parent
        else None
    )
    shading = (
        inherit_shading(project, parent, stage, state["developed_id"], assets=assets)
        if parent
        else None
    )
    exposure = (
        inherit_exposure(project, parent, stage, state["developed_id"], assets=assets)
        if parent
        else None
    )
    fade = (
        inherit_shadow_fade(project, parent, stage, state["developed_id"], assets=assets)
        if parent
        else None
    )
    sharpening = (
        inherit_local_sharpening(project, parent, stage, state["developed_id"], assets=assets)
        if parent
        else None
    )
    spatial = (
        inherit_spatial_fade(project, parent, stage, state["developed_id"], assets=assets)
        if parent
        else None
    )
    from .background import inherit_background

    background = inherit_background(
        project,
        parent,
        stage,
        state["developed_id"],
        (height, width),
        recipe.background,
        assets=assets,
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
                "developed_id": state["developed_id"],
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
    from .review import write_preparation_overview

    write_preparation_overview(stage, pixels, developed_id=state["developed_id"], revision=revision)
    collect_stage_assets(project, stage, assets)
    files = {
        str(path.relative_to(stage)): digest(path.read_bytes())
        for path in stage.rglob("*")
        if path.is_file()
    }
    new_guides = _json_bytes(guides) if external else snapshots["guides.json"]
    new_digest = digest(snapshots["recipe.toml"] + b"\0" + new_guides)
    manifest = {
        "schema_version": 2,
        "revision": revision,
        "parent": parent,
        "developed_id": state["developed_id"],
        "kind": "prepare",
        "complete": True,
        "final_acceptable": False,
        "inputs_digest": operation["inputs_digest"],
        "draft_digest": new_digest,
        "scope_xyxy": scope,
        "files": files,
        "assets": assets,
        "candidates": candidate_records,
        "proposal": proposal_record,
        "external_inputs": {
            name: {"sha256": digest(data), "snapshot": f"inputs/external-{i}.json"}
            for i, (name, data) in enumerate(external.items())
        },
        "parent_manifest_sha256": digest(
            saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes()
        )
        if parent
        else None,
        "source_precision_bits": metadata["source_precision_bits"],
        "proxy_precision_bits": 8,
        "trimap_review": "optional human review; selection membership does not prove opacity",
        **({"color_cleanup": cleanup} if cleanup is not None else {}),
        **({"shading": shading} if shading is not None else {}),
        **({"local_exposure": exposure} if exposure is not None else {}),
        **({"shadow_fade": fade} if fade is not None else {}),
        **({"local_sharpening": sharpening} if sharpening is not None else {}),
        **({"spatial_fade": spatial} if spatial is not None else {}),
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
            if saved_asset(project, name).read_bytes() != data:
                raise ProjectError(f"Stale input changed during prepare: {name}")
        for name, data in external.items():
            if _input_file(project, name).read_bytes() != data:
                raise ProjectError(f"Stale external input changed: {name}")

    check_inputs()
    load_developed(project, state["developed_id"])
    if parent:
        current_parent = read_revision(project, parent, state["developed_id"])
        if (
            digest(saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes())
            != manifest["parent_manifest_sha256"]
            or current_parent != parent_manifest
        ):
            raise ProjectError("Stale parent changed during prepare")
    for saved in lock_revisions:
        read_revision(project, saved, state["developed_id"])
        if (
            digest(saved_asset(project, f"revisions/{saved}/manifest.json").read_bytes())
            != lock_manifest_hashes[saved]
        ):
            raise ProjectError("Stale saved lock dependency changed during prepare")
    destination = revisions / revision
    if destination.exists():
        raise ProjectError("Revision publication collision; preserved")
    _publish_new_directory(stage, destination)
    _sync_directory(revisions)
    read_revision(project, revision, state["developed_id"])
    # Draft publication may precede a failed pointer write; accepted state remains exact and recoverable.
    if external:
        _atomic_json(
            saved_asset(project, "guides.json"), guides, validate_before_replace=check_inputs
        )
        publication_inputs["guides.json"] = new_guides
    state.update(working_revision=revision, status="review_needed")
    _atomic_json(saved_asset(project, "state.json"), state, validate_before_replace=check_inputs)
    return {
        "revision": revision,
        "parent": parent,
        "developed_id": state["developed_id"],
        "inputs_digest": new_digest,
        "status": "review_needed",
        "final_acceptable": False,
        "manifest_file": str(destination / "manifest.json"),
        "trimap_file": str(revision_asset(project, destination, manifest, "trimap.png")),
        "support_file": str(
            revision_asset(project, destination, manifest, "supports/support16.png")
        ),
        "protection_file": str(
            revision_asset(project, destination, manifest, "supports/protection.png")
        ),
        "source_proxy_file": str(
            revision_asset(project, destination, manifest, "source_proxy8.png")
        ),
        "trimap_proposal_file": str(
            revision_asset(project, destination, manifest, "trimap_proposal.png")
        )
        if proposal_record
        else None,
        "proposal_boundary_file": str(
            revision_asset(project, destination, manifest, "proposal_boundary.png")
        )
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
    requests = saved_asset(project, "requests")
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
            "schema_version": 2,
            "operation_sha256": digest(
                saved_asset(project, f"requests/{directory.name}/operation.json").read_bytes()
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
    for path in saved_asset(project, "requests").glob("matte-*/operation.json"):
        data = saved_asset(project, str(path.relative_to(project))).read_bytes()
        if cycle_id.encode() not in data:
            continue
        operation = json.loads(data)
        if operation.get("assisted_review", {}).get("cycle_id") == cycle_id:
            checksums.add(digest(_json_bytes(operation)))
    return checksums


def _read_matte_snapshot(
    project: Path, directory: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    manifest = json.loads(
        saved_asset(project, f"requests/{directory.name}/manifest.json").read_bytes()
    )
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 2
        or not isinstance(manifest.get("inputs"), dict)
        or set(manifest.get("inputs", {}))
        != {"state.json", "source.json", "recipe.toml", "guides.json"}
        or not isinstance(manifest.get("dependencies"), dict)
        or not manifest["dependencies"]
        or digest(saved_asset(project, f"requests/{directory.name}/operation.json").read_bytes())
        != manifest.get("operation_sha256")
    ):
        raise ProjectError("Invalid recovery snapshot; restart from current reviewed inputs")
    operation = json.loads(
        saved_asset(project, f"requests/{directory.name}/operation.json").read_bytes()
    )
    if not isinstance(operation, dict):
        raise ProjectError("Invalid recovery operation object")
    snapshots = {}
    for name, checksum in manifest["inputs"].items():
        saved = saved_asset(project, f"requests/{directory.name}/inputs/{name}").read_bytes()
        if digest(saved) != checksum:
            raise ProjectError(
                "Recovery snapshot hash mismatch; restart from current reviewed inputs"
            )
        snapshots[name] = saved
    return operation, manifest, snapshots


def _verify_matte_request(
    project: Path, directory: Path, *, completed_revision: str | None = None
) -> dict[str, Any]:
    operation, manifest, snapshots = _read_matte_snapshot(project, directory)
    for name, saved in snapshots.items():
        if name == "state.json" and completed_revision is not None:
            continue
        if saved_asset(project, name).read_bytes() != saved:
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
    if state["developed_id"] != operation["developed_id"] or (
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
    project: Path,
    operation_id: str,
    *,
    model_cache: Path | None = None,
    source: Path | None = None,
    storage_config: StorageConfig | None = None,
) -> dict[str, Any]:
    """Resume the same snapshotted matte/repair under the canonical writer lock."""
    project = _root(project)
    validate_library_project(project, storage_config)
    if not isinstance(operation_id, str) or re.fullmatch(r"matte-[a-z0-9_]+", operation_id) is None:
        raise ProjectError("Invalid recovery operation identity")
    with project_lock(project):
        directory = saved_asset(project, f"requests/{operation_id}")
        with _recovery_record_errors():
            if source is not None:
                record = json.loads(saved_asset(project, "source.json").read_bytes())
                if digest(source.read_bytes()) != record["source_sha256"]:
                    raise ProjectError("Moved source hash differs from recorded capture")
            completion = directory / "completion.json"
            has_completion = completion.is_file()
        if has_completion:
            with _recovery_record_errors():
                completed = json.loads(
                    saved_asset(project, f"requests/{directory.name}/completion.json").read_bytes()
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
                destination = saved_asset(project, f"revisions/{revision}")
                stage_name = completed["stage"]
                if (
                    not isinstance(stage_name, str)
                    or re.fullmatch(r"\.matte-[a-z0-9_]+", stage_name) is None
                ):
                    raise ProjectError("Invalid recovery stage")
                retained = (
                    destination
                    if destination.exists()
                    else saved_asset(project, f"revisions/{stage_name}")
                )
                manifest = _validate_revision_directory(
                    project, revision, operation["developed_id"], f"revisions/{retained.name}"
                )
                if (
                    digest((retained / "manifest.json").read_bytes())
                    != completed["manifest_sha256"]
                    or manifest["parent"] != operation["base_revision"]
                    or manifest["inputs_digest"] != operation["inputs_digest"]
                    or manifest["draft_digest"]
                    != digest(
                        (retained / "recipe.toml").read_bytes()
                        + b"\0"
                        + (retained / "guides.json").read_bytes()
                    )
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
                        project, revision, operation["developed_id"], f"revisions/{retained.name}"
                    )

            check_space(project, 1024**2)
            recheck()
            if retained != destination:
                _publish_new_directory(retained, destination)
                retained = destination
                _sync_directory(destination.parent)
            if not already_current:
                record_generated_result(state, revision, manifest)
                _atomic_json(
                    saved_asset(project, "state.json"), state, validate_before_replace=recheck
                )
            _atomic_json(
                directory / "progress.json",
                {"status": "review_needed", "phase": "complete", "revision": revision},
            )
            return _result_preview(
                project,
                dict(
                    result,
                    inputs_digest=draft_digest(project),
                    revision_inputs_digest=manifest["draft_digest"],
                    operation_id=operation_id,
                    resumed_completed_stage=True,
                ),
                storage_config,
                generated=True,
            )
        with _recovery_record_errors():
            operation = _verify_matte_request(project, directory)
            manifest = json.loads(
                saved_asset(project, f"requests/{directory.name}/manifest.json").read_bytes()
            )
            request_file = Path(manifest["request_file"]) if manifest["request_file"] else None
        return _result_preview(
            project,
            _run_matte(
                project,
                operation,
                model_cache,
                request_file,
                directory,
            ),
            storage_config,
            generated=True,
        )


def operation_status(
    project: Path, *, storage_config: StorageConfig | None = None
) -> dict[str, Any]:
    """Read saved pointers and recovery records without waiting for a writer."""
    project = _root(project)
    state = read_project(project, validate_drafts=False)
    busy = project_writer_busy(project)
    records: list[dict[str, Any]] = []
    for path in sorted(saved_asset(project, "requests").glob("matte-*/manifest.json")):
        directory = saved_asset(project, str(path.parent.relative_to(project)))
        try:
            progress = json.loads(
                saved_asset(project, f"requests/{directory.name}/progress.json").read_bytes()
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
                    saved_asset(project, f"requests/{directory.name}/completion.json").read_bytes()
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
    from .previews import result_preview_status

    preview = result_preview_status(project, storage_config)
    return dict(
        state,
        writer_busy=busy,
        operations=records,
        preview=preview,
        preview_pending=preview["status"] == "pending",
    )


def reopen_project_status(project: Path, *, storage_config: StorageConfig) -> dict[str, Any]:
    """Refresh an idle configured gallery and report actual state without waiting."""
    validate_library_project(project, storage_config)
    from .previews import refresh_result_preview

    preview: dict[str, Any] | None = None
    try:
        preview = refresh_result_preview(project, storage_config)
    except ProjectError as error:
        # project_lock preserves the precise flock contention as its cause.
        if not isinstance(error.__cause__, BlockingIOError):
            raise
    status = operation_status(project, storage_config=storage_config)
    # Visible files cannot establish durability after a failed publication sync.
    if preview is not None and preview["status"] == "pending":
        return dict(status, preview=preview, preview_pending=True)
    return status


def _matte(
    project: Path,
    operation: dict[str, Any],
    model_cache: Path | None,
    request_file: Path | None,
    recovery: list[Path],
) -> dict[str, Any]:
    import tifffile

    from .ingest import write_developed
    from .matte import native_matte
    from .repair import (
        ORDER,
        prepared_parent_layers,
        replay_directory,
        scalar16,
        validate_merge,
        validate_support,
    )
    from .review import write_revision_overview

    repairing = operation["kind"] == "repair"
    required = {"schema_version", "kind", "base_revision", "developed_id", "inputs_digest"}
    optional = {"reason"}
    if repairing:
        required |= {"context_xyxy", "scope_xyxy", "support_file"}
        optional |= {"merge_policy", "assisted_review"}
    if (
        set(operation) - required - optional
        or not required <= set(operation)
        or type(operation["schema_version"]) is not int
        or operation["schema_version"] != 2
        or ("reason" in operation and not isinstance(operation["reason"], str))
    ):
        raise ProjectError("Invalid typed schema-2 matte operation; prepare guide changes first")
    operation = json.loads(_json_bytes(operation))
    request_bytes = request_file.read_bytes() if request_file else None
    if request_bytes is not None and json.loads(request_bytes) != operation:
        raise ProjectError("Stale request before matte snapshot")
    state = read_project(project)
    _reject_pending_guidance(project)
    parent = state["working_revision"]
    if not parent:
        raise ProjectError("Matte requires a prepared trimap")
    if (
        operation["developed_id"] != state["developed_id"]
        or operation["base_revision"] != parent
        or operation["inputs_digest"] != draft_digest(project)
    ):
        raise ProjectError("Stale matte master, revision or inputs_digest")
    manifest = read_revision(project, parent, state["developed_id"])
    if manifest.get("kind") != "prepare":
        raise ProjectError("Prepare the trimap before each matte rerun")
    if manifest["draft_digest"] != operation["inputs_digest"]:
        raise ProjectError("Stale prepared draft; prepare changed guides/settings")
    approval_path = saved_asset(project, f"approvals/{parent}-trimap.json")
    approval_bytes = approval_path.read_bytes() if approval_path.is_file() else None
    parent_bytes = saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes()
    if approval_bytes is not None:
        approval = json.loads(approval_bytes)
        if not isinstance(approval, dict):
            raise ProjectError("Invalid trimap approval record")
        if (
            approval.get("revision") != parent
            or approval.get("developed_id") != state["developed_id"]
            or approval.get("inputs_digest") != operation["inputs_digest"]
            or approval.get("manifest_sha256") != digest(parent_bytes)
            or approval.get("trimap_sha256") != revision_hashes(manifest)["trimap.png"]
        ):
            raise ProjectError("Stale trimap approval assets")
    snapshots = {
        name: saved_asset(project, name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    if (
        json.loads(snapshots["state.json"]) != state
        or digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
        != operation["inputs_digest"]
    ):
        raise ProjectError("Stale matte snapshot")
    pixels, _ = load_developed(project, state["developed_id"])
    height, width = pixels.shape[:2]
    recipe = Recipe.from_dict(
        tomllib.loads(snapshots["recipe.toml"].decode()),
        state["developed_id"],
        max_margin_px=max(width, height),
        dimensions_wh=(width, height),
    )
    guides = json.loads(saved_asset(project, f"revisions/{parent}/guides.json").read_bytes())
    saved = {
        r["revision"]: _alpha(project, r["revision"], state["developed_id"], (height, width))
        for r in guides["regions"]
        if r["role"] == "lock"
    }
    lock_hashes = {
        rev: digest(saved_asset(project, f"revisions/{rev}/manifest.json").read_bytes())
        for rev in saved
    }
    raster = rasterize_regions(guides, scope_xyxy=manifest["scope_xyxy"], saved_alpha=saved)
    with Image.open(saved_asset(project, f"revisions/{parent}/trimap.png")) as image:
        trimap = np.array(image)
    if not np.array_equal(trimap, raster.trimap):
        raise ProjectError("Prepared trimap differs from saved typed guides")
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
        expected_support = saved_asset(project, f"revisions/{parent}/supports/support16.png")
        support_path = (
            expected_support
            if operation["support_file"] == str(expected_support)
            else _input_file(project, operation["support_file"])
        )
        if support_path != expected_support:
            raise ProjectError("Repair must consume returned immutable prepared support")
        support_bytes = support_path.read_bytes()
        support = scalar16(support_path)
        parent_alpha = _alpha(project, parent, state["developed_id"], (height, width))
        validate_support(support, (height, width), context, scope)
        if not np.array_equal(support, raster.support16):
            raise ProjectError("Saved support differs from prepared guides")
        validate_merge(
            parent_alpha, support, raster.protection, raster.lock_values16, trimap, policy
        )
        prepared_parent_layers(project, parent, state["developed_id"])
        ancestor = parent
        while ancestor:
            ancestor_manifest = read_revision(project, ancestor, state["developed_id"])
            ancestor_hashes[ancestor] = digest(
                saved_asset(project, f"revisions/{ancestor}/manifest.json").read_bytes()
            )
            if ancestor_manifest.get("kind") != "prepare":
                break
            ancestor = ancestor_manifest["parent"]
    check_space(project, pixels.nbytes * (42 if recipe.background is not None else 40) + 1024**2)
    foreground = pixels.copy()
    if repairing:
        foreground = tifffile.imread(
            saved_asset(project, f"revisions/{parent}/foreground_rgb16.tif")
        )
        if foreground.shape != pixels.shape or foreground.dtype != np.uint16:
            raise ProjectError("Invalid repair parent foreground RGB16")
    applicable_parent_foreground = foreground
    if repairing and any(
        manifest.get(name, {}).get("enabled")
        for name in ("color_cleanup", "local_sharpening", "local_exposure", "shadow_fade")
    ):
        from .effects import saved_effect_lock_layers

        # The write boundary preserves the saved selected appearance, which may
        # differ from the base master RGB before this explicit lock is bound.
        applicable_parent_foreground, _, _ = saved_effect_lock_layers(
            project, parent, state["developed_id"]
        )
    rgb_protection = np.zeros((height, width), dtype=bool)
    for region in guides["regions"]:
        if region["role"] != "lock":
            continue
        rev = region["revision"]
        locked_manifest = read_revision(project, rev, state["developed_id"])
        name = (
            "foreground_rgb16.tif"
            if "foreground_rgb16.tif" in revision_hashes(locked_manifest)
            else "corrected_rgb16.tif"
            if "corrected_rgb16.tif" in revision_hashes(locked_manifest)
            else None
        )
        if name:
            values = tifffile.imread(saved_asset(project, f"revisions/{rev}/{name}"))
            if any(
                locked_manifest.get(name, {}).get("enabled")
                for name in ("color_cleanup", "local_sharpening", "local_exposure", "shadow_fade")
            ):
                from .effects import saved_effect_lock_layers

                values, _, _ = saved_effect_lock_layers(project, rev, state["developed_id"])
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
        dependencies = (
            {f"approvals/{parent}-trimap.json": digest(approval_bytes)}
            if approval_bytes is not None
            else {}
        )
        if "assisted_review" in operation:
            review_name = operation["assisted_review"]["review_manifest_file"]
            review_path = _input_file(project, review_name)
            dependencies[review_name] = digest(review_path.read_bytes())
            for name, checksum in json.loads(review_path.read_bytes())["view_files"].items():
                dependencies[str(Path(review_name).parent / name)] = checksum
        for saved_revision in {parent, *lock_hashes, *ancestor_hashes}:
            saved_manifest = read_revision(project, saved_revision, state["developed_id"])
            dependencies[f"revisions/{saved_revision}/manifest.json"] = digest(
                saved_asset(project, f"revisions/{saved_revision}/manifest.json").read_bytes()
            )
            dependencies.update(
                {
                    str(
                        saved_asset(project, f"revisions/{saved_revision}/{name}").relative_to(
                            project
                        )
                    ): checksum
                    for name, checksum in revision_hashes(saved_manifest).items()
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
        cache_dir=saved_asset(project, "cache/matte"),
        cache_identity={
            "developed_id": state["developed_id"],
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
    revisions = saved_asset(project, "revisions")
    existing = [
        int(p.name[4:]) for p in revisions.iterdir() if re.fullmatch(r"rev-[0-9]{3,}", p.name)
    ]
    revision = f"rev-{max(existing, default=0) + 1:03d}"
    stage = Path(tempfile.mkdtemp(prefix=".matte-", dir=revisions))
    assets: dict[str, Any] = {}
    for name in (
        "recipe.toml",
        "trimap.png",
        "supports/support16.png",
        "supports/protection.png",
        "supports/lock_values16.png",
    ):
        inherit_revision_files(project, parent, stage, assets, (name,))
    # Keep the validated editable bytes used by the completed effective digest;
    # preparation may have normalized equivalent JSON for rasterization.
    (stage / "guides.json").write_bytes(snapshots["guides.json"])
    (stage / "request.json").write_bytes(
        request_bytes if request_bytes is not None else _json_bytes(operation)
    )
    if approval_bytes is not None:
        (stage / "trimap_approval.json").write_bytes(approval_bytes)
    (stage / "inputs").mkdir()
    for name, data in snapshots.items():
        (stage / "inputs" / name).write_bytes(data)
    if repairing:
        (stage / "repair").mkdir()
        assets["repair/parent_alpha16.png"] = dict(manifest["assets"]["base_alpha16.png"])
        Image.fromarray(candidate).save(stage / "repair/candidate_alpha16.png")
        if support_bytes is None:
            raise ProjectError("Missing repair support snapshot")
        assets["repair/support16.png"] = dict(manifest["assets"]["supports/support16.png"])
        (stage / "repair/merge.json").write_bytes(
            _json_bytes(
                {
                    "parent": parent,
                    "parent_manifest_sha256": digest(parent_bytes),
                    "developed_id": state["developed_id"],
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
        alpha = replay_directory(project, stage, {"assets": assets})
    Image.fromarray(alpha).save(stage / "base_alpha16.png")
    write_developed(stage / "foreground_rgb16.tif", foreground)
    with Image.open(stage_asset(project, stage, assets, "base_alpha16.png")) as image:
        if image.mode not in {"I;16", "I;16L", "I;16B"} or not np.array_equal(
            np.array(image), alpha
        ):
            raise ProjectError("Alpha16 round trip failed")
    if not np.array_equal(
        tifffile.imread(stage_asset(project, stage, assets, "foreground_rgb16.tif")), foreground
    ):
        raise ProjectError("Foreground RGB16 round trip failed")
    from .effects import (
        effects_stale,
        inherit_cleanup,
        inherit_exposure,
        inherit_local_sharpening,
        inherit_shading,
        inherit_shadow_fade,
        inherit_spatial_fade,
        saved_spatial_fade,
    )

    cleanup = inherit_cleanup(
        project,
        parent,
        stage,
        state["developed_id"],
        alpha,
        foreground,
        rgb_protection,
        assets=assets,
    )
    shading = inherit_shading(project, parent, stage, state["developed_id"], alpha, assets=assets)
    exposure = inherit_exposure(
        project, parent, stage, state["developed_id"], alpha, rgb_protection, assets=assets
    )
    fade = inherit_shadow_fade(
        project, parent, stage, state["developed_id"], alpha, rgb_protection, assets=assets
    )
    sharpening = inherit_local_sharpening(
        project, parent, stage, state["developed_id"], alpha, rgb_protection, assets=assets
    )
    spatial = inherit_spatial_fade(
        project, parent, stage, state["developed_id"], alpha, rgb_protection, assets=assets
    )
    from .background import inherit_background

    background = inherit_background(
        project,
        parent,
        stage,
        state["developed_id"],
        (height, width),
        recipe.background,
        assets=assets,
    )
    # Preparation snapshots requested drafts. A completed matte applies those
    # guides/matting settings but only inherits the previously generated effects.
    effective_recipe = tomllib.loads(snapshots["recipe.toml"].decode())
    defaults = Recipe(state["developed_id"]).to_dict()
    for name, inherited in (
        ("color_cleanup", cleanup),
        ("shading", shading),
        ("local_sharpening", sharpening),
        ("local_exposure", exposure),
        ("shadow_fade", fade),
        ("spatial_fade", spatial),
        ("background", background),
    ):
        if inherited is not None:
            effective_recipe[name] = (
                {"enabled": inherited["enabled"], "strength": inherited["strength"]}
                if name == "color_cleanup"
                else dict(inherited["settings"])
            )
        elif name in effective_recipe:
            if name in defaults:
                effective_recipe[name] = defaults[name]
            else:
                effective_recipe.pop(name)
    effective_recipe_bytes = (
        snapshots["recipe.toml"]
        if effective_recipe == tomllib.loads(snapshots["recipe.toml"].decode())
        else tomli_w.dumps(effective_recipe).encode()
    )
    (stage / "recipe.toml").write_bytes(effective_recipe_bytes)
    revision_inputs_digest = digest(effective_recipe_bytes + b"\0" + snapshots["guides.json"])
    stale_effects = effects_stale(
        {
            "color_cleanup": cleanup or {},
            "shading": shading or {},
            "local_sharpening": sharpening or {},
            "local_exposure": exposure or {},
            "shadow_fade": fade or {},
            "spatial_fade": spatial or {},
        }
    )
    review_weight = (
        scalar16(stage_asset(project, stage, assets, "shadow_weight16.png"))
        if shading and shading["enabled"] and not stale_effects
        else None
    )
    review_opacity = shading["opacity"] if shading and review_weight is not None else 0.0
    review_foreground = foreground
    if cleanup and cleanup["enabled"] and not stale_effects:
        review_foreground = tifffile.imread(
            stage_asset(project, stage, assets, "corrected_rgb16.tif")
        )
    from .sharpening import selected_local_sharpening

    review_foreground = selected_local_sharpening(
        project,
        stage,
        review_foreground,
        alpha,
        {
            "developed_id": state["developed_id"],
            "assets": assets,
            **({"local_sharpening": sharpening} if sharpening else {}),
        },
        sharpening_off=stale_effects,
    )
    from .exposure import selected_exposure

    review_foreground, clipping = selected_exposure(
        project,
        stage,
        review_foreground,
        alpha,
        {
            "developed_id": state["developed_id"],
            "assets": assets,
            **({"local_exposure": exposure} if exposure else {}),
        },
        exposure_off=stale_effects,
    )
    from .shadow_fade import selected_shadow_fade

    review_foreground = selected_shadow_fade(
        project,
        stage,
        review_foreground,
        alpha,
        {
            "developed_id": state["developed_id"],
            "assets": assets,
            **({"shadow_fade": fade} if fade else {}),
        },
        shadow_fade_off=stale_effects,
    )
    from .export import read_rgb16

    background_pixels = (
        read_rgb16(stage_asset(project, stage, assets, "background/background_rgb16.tif"))
        if background is not None and not stale_effects
        else None
    )
    from .spatial_fade import SpatialFadeOperands

    spatial_operands = (
        SpatialFadeOperands(
            scalar16(stage_asset(project, stage, assets, "effects/spatial-fade/weight16.png")),
            scalar16(stage_asset(project, stage, assets, "effects/spatial-fade/protection16.png"))
            != 0,
            spatial,
        )
        if spatial is not None and spatial["enabled"] and not stale_effects
        else None
    )
    fade_target = (
        background_pixels
        if background_pixels is not None
        else np.zeros_like(review_foreground)
        if spatial_operands is not None
        else None
    )
    write_revision_overview(
        stage / "review",
        pixels,
        review_foreground,
        alpha,
        background16=background_pixels,
        spatial_fade=spatial_operands,
        fade_background16=fade_target,
        developed_id=state["developed_id"],
        revision=revision,
        crops=[context] if repairing else None,
        weight16=review_weight,
        opacity=review_opacity,
    )
    if repairing:
        if parent_alpha is None:
            raise ProjectError("Missing repair parent review alpha")
        before_foreground = tifffile.imread(
            saved_asset(project, f"revisions/{parent}/foreground_rgb16.tif")
        )
        if cleanup and cleanup["enabled"] and not stale_effects:
            from .export import read_rgb16

            # Prepared guides contain the requested new locks; the before panel
            # depicts the actual inherited appearance before those locks apply.
            before_foreground = read_rgb16(
                saved_asset(project, f"revisions/{parent}/corrected_rgb16.tif")
            )
        if (sharpening or exposure or fade) and not stale_effects:
            from .effects import saved_effect_lock_layers

            before_foreground, _, _ = saved_effect_lock_layers(
                project, parent, state["developed_id"]
            )
        write_revision_overview(
            stage / "review-before",
            pixels,
            before_foreground,
            parent_alpha,
            background16=background_pixels,
            spatial_fade=saved_spatial_fade(
                project, parent, parent_alpha, manifest, effects_off=stale_effects
            ),
            fade_background16=fade_target,
            developed_id=state["developed_id"],
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
    if sharpening:
        for review_name in ("review", "review-before") if repairing else ("review",):
            path = stage / review_name / "manifest.json"
            record = json.loads(path.read_bytes())
            record["local_sharpening"] = sharpening
            record["label"] += (
                "; Local sharpening OFF; BASE comparison"
                if stale_effects
                else f"; Local sharpening {'ON' if sharpening['enabled'] else 'OFF'}"
            )
            path.write_bytes(_json_bytes(record))
    if spatial:
        for review_name in ("review", "review-before") if repairing else ("review",):
            path = stage / review_name / "manifest.json"
            record = json.loads(path.read_bytes())
            record["spatial_fade"] = (
                manifest["spatial_fade"] if review_name == "review-before" else spatial
            )
            record["label"] += (
                "; spatial fade stale; BASE comparison"
                if stale_effects
                else "; Fade into background ON"
                if spatial["enabled"]
                else "; Fade into background OFF"
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
        "developed_id": state["developed_id"],
        "inputs_digest": operation["inputs_digest"],
        "kind": "repair" if repairing else "matte",
        "status": "review_needed",
        "final_acceptable": True,
        "model": model_record,
        **({"color_cleanup": cleanup} if cleanup is not None else {}),
        **({"shading": shading} if shading is not None else {}),
        **({"local_exposure": exposure} if exposure is not None else {}),
        **({"shadow_fade": fade} if fade is not None else {}),
        **({"local_sharpening": sharpening} if sharpening is not None else {}),
        **({"spatial_fade": spatial} if spatial is not None else {}),
        **({"background": background} if background is not None else {}),
    }
    (stage / "result.json").write_bytes(_json_bytes(result))
    collect_stage_assets(project, stage, assets)
    files = {
        str(p.relative_to(stage)): digest(p.read_bytes()) for p in stage.rglob("*") if p.is_file()
    }
    new_manifest = {
        "schema_version": 2,
        **result,
        "complete": True,
        "draft_digest": revision_inputs_digest,
        "files": files,
        "assets": assets,
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
            read_revision(project, ancestor, state["developed_id"])
            if (
                digest(saved_asset(project, f"revisions/{ancestor}/manifest.json").read_bytes())
                != expected
            ):
                raise ProjectError("Stale repair ancestral operands")
        for name, data in snapshots.items():
            if saved_asset(project, name).read_bytes() != data:
                raise ProjectError(f"Stale input changed during matte: {name}")
        if request_file is not None and request_file.read_bytes() != request_bytes:
            raise ProjectError("Stale matte request file")
        if (
            approval_bytes is not None and approval_path.read_bytes() != approval_bytes
        ) or saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes() != parent_bytes:
            raise ProjectError("Stale prepared assets/approval")
        read_revision(project, parent, state["developed_id"])
        load_developed(project, state["developed_id"])
        for rev, expected in lock_hashes.items():
            read_revision(project, rev, state["developed_id"])
            if (
                digest(saved_asset(project, f"revisions/{rev}/manifest.json").read_bytes())
                != expected
            ):
                raise ProjectError("Stale saved lock values")

    _verify_matte_request(project, recovery[0])
    recheck()
    destination = revisions / revision
    if destination.exists():
        raise ProjectError("Revision collision; preserved")
    _publish_new_directory(stage, destination)
    _sync_directory(revisions)
    read_revision(project, revision, state["developed_id"])
    record_generated_result(state, revision, new_manifest)
    _atomic_json(saved_asset(project, "state.json"), state, validate_before_replace=recheck)
    return dict(
        result,
        inputs_digest=draft_digest(project),
        revision_inputs_digest=revision_inputs_digest,
        manifest_file=str(destination / "manifest.json"),
        review_manifest_file=str(destination / "review/manifest.json"),
    )


def restore_revision(
    project: Path,
    revision: str,
    *,
    replace_drafts: bool = False,
    expected_identity: dict[str, Any] | None = None,
    storage_config: StorageConfig | None = None,
) -> dict[str, Any]:
    """Select saved working inputs; acceptance is never reassigned."""
    project = _root(project)
    validate_library_project(project, storage_config)
    with project_lock(project):
        state = read_project(project, validate_drafts=not replace_drafts)
        if expected_identity is not None and (
            expected_identity.get("developed_id") != state["developed_id"]
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
        target = read_revision(project, revision, state["developed_id"])
        if target.get("kind") not in {"prepare", "matte", "repair", "effects"}:
            raise ProjectError("Unsupported saved revision for restore")
        current = state["working_revision"]
        expected_draft_digest = target["draft_digest"]
        if current is not None:
            current_manifest = read_revision(project, current, state["developed_id"])
            expected_draft_digest = current_manifest["draft_digest"]
        if not replace_drafts and draft_digest(project) != expected_draft_digest:
            raise ProjectError(
                "Unsaved draft edits; preserve them or explicitly use --replace-drafts"
            )
        snapshots = {
            name: saved_asset(project, name).read_bytes()
            for name in ("state.json", "source.json", "recipe.toml", "guides.json")
        }
        pending_path = saved_asset(project, "viewer-draft.json")
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
            saved_asset(project, f"revisions/{current}/manifest.json").read_bytes()
            if current
            else None
        )
        if current_bytes is not None and json.loads(current_bytes) != current_manifest:
            raise ProjectError("Stale working revision before restore snapshot")
        target_bytes = saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        recipe = saved_asset(project, f"revisions/{revision}/recipe.toml").read_bytes()
        guides = saved_asset(project, f"revisions/{revision}/guides.json").read_bytes()
        if json.loads(target_bytes) != target:
            raise ProjectError("Stale restore target before snapshot")
        if digest(recipe + b"\0" + guides) != target["draft_digest"]:
            # Earlier prepare/matte revisions normalize guides but retain the exact
            # effective editable draft in their hashed input snapshots.
            if not {"inputs/recipe.toml", "inputs/guides.json"} <= set(target["files"]):
                raise ProjectError("Invalid saved restore draft digest")
            recipe = saved_asset(project, f"revisions/{revision}/inputs/recipe.toml").read_bytes()
            guides = saved_asset(project, f"revisions/{revision}/inputs/guides.json").read_bytes()
            if digest(recipe + b"\0" + guides) != target["draft_digest"]:
                raise ProjectError("Invalid saved restore draft digest")
        pixels, _ = _validate_assets(project, state, validate_drafts=not replace_drafts)
        Recipe.from_dict(
            tomllib.loads(recipe.decode()),
            state["developed_id"],
            max_margin_px=max(pixels.shape[:2]),
            dimensions_wh=(pixels.shape[1], pixels.shape[0]),
        )
        validate_guides(json.loads(guides), state["developed_id"], pixels.shape[1], pixels.shape[0])
        check_space(
            project, sum(map(len, snapshots.values())) * 3 + len(recipe) + len(guides) + 1024**2
        )
        recovery = saved_asset(project, "recovery")
        recovery.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix="restore-", dir=recovery))
        for name, data in snapshots.items():
            (stage / name).write_bytes(data)
        (stage / "request.json").write_bytes(
            _json_bytes(
                {
                    "revision": revision,
                    "developed_id": state["developed_id"],
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
                if saved_asset(project, name).read_bytes() != data:
                    raise ProjectError(f"Stale input changed during restore: {name}")
            if (
                saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
                != target_bytes
            ):
                raise ProjectError("Stale restore target")
            if current:
                read_revision(project, current, state["developed_id"])
                if (
                    saved_asset(project, f"revisions/{current}/manifest.json").read_bytes()
                    != current_bytes
                ):
                    raise ProjectError("Stale working revision during restore")
            read_revision(project, revision, state["developed_id"])
            _validate_assets(project, state, validate_drafts=not replace_drafts)

        # Files are atomic individually; recovery retains all original bytes on interruption.
        for name, data in (("recipe.toml", recipe), ("guides.json", guides)):
            _atomic_bytes(saved_asset(project, name), data, validate_before_replace=recheck)
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
        _atomic_json(saved_asset(project, "state.json"), state, validate_before_replace=recheck)
        return _result_preview(
            project,
            dict(state, inputs_digest=target["draft_digest"], recovery_directory=str(stage)),
            storage_config,
        )


def _check_draft_identity(project: Path, identity: dict[str, Any]) -> dict[str, Any]:
    state = read_project(project)
    if (
        identity.get("developed_id") != state["developed_id"]
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
            name: saved_asset(project, name).read_bytes()
            for name in ("recipe.toml", "guides.json", "state.json")
        }
        captured_authoring = guidance_draft_digest(project)

        def recheck() -> None:
            read_project(project)
            if (
                any(
                    saved_asset(project, name).read_bytes() != data
                    for name, data in snapshots.items()
                )
                or guidance_draft_digest(project) != captured_authoring
            ):
                raise ProjectError("Stale drafts changed during authoring save")

        guides = json.loads(snapshots["guides.json"])
        edits = {"schema_version": 2, "developed_id": state["developed_id"], "actions": actions}
        edited = edit_guides(guides, edits)
        for region in edited["regions"]:
            if region["role"] == "lock":
                _alpha(
                    project,
                    region["revision"],
                    state["developed_id"],
                    (guides["height"], guides["width"]),
                )
        recipe = tomllib.loads(snapshots["recipe.toml"].decode())
        recipe["groups"] = groups
        Recipe.from_dict(
            recipe,
            state["developed_id"],
            max_margin_px=max(guides["width"], guides["height"]),
            dimensions_wh=(guides["width"], guides["height"]),
        )
        check_space(project, len(_json_bytes(edits)) * 3 + 1024**2)
        # Retain exact prior recipe and every typed edit file for interruption/recovery.
        directory = saved_asset(project, "requests")
        directory.mkdir(exist_ok=True)
        name = f"requests/viewer-{uuid.uuid4().hex}.json"
        record = dict(edits, groups=groups, previous_recipe=snapshots["recipe.toml"].decode())
        _atomic_json(saved_asset(project, name), record, replace_existing=False)
        edits_name = f"requests/viewer-edits-{uuid.uuid4().hex}.json"
        _atomic_json(saved_asset(project, edits_name), edits, replace_existing=False)
        new_recipe = tomli_w.dumps(recipe).encode()
        _atomic_bytes(
            saved_asset(project, "recipe.toml"), new_recipe, validate_before_replace=recheck
        )
        snapshots["recipe.toml"] = new_recipe
        pending = {
            "developed_id": state["developed_id"],
            "base_revision": state["working_revision"],
            "inputs_digest": digest(new_recipe + b"\0" + snapshots["guides.json"]),
            "record_file": name,
            "guide_edits_file": edits_name,
            "actions": actions,
        }
        _atomic_json(
            saved_asset(project, "viewer-draft.json"), pending, validate_before_replace=recheck
        )
        return pending


def prepare_guidance_draft(
    project: Path, identity: dict[str, Any], scope: list[int], *, model_cache: Path | None = None
) -> dict[str, Any]:
    """Consume current pending typed edits once through the canonical preparation owner."""
    project = _root(project)
    with project_lock(project):
        state = _check_draft_identity(project, identity)
        operation = {
            "schema_version": 2,
            "kind": "prepare",
            "developed_id": state["developed_id"],
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
        path = saved_asset(project, "viewer-draft.json")
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
                "schema_version": 2,
                "developed_id": pending["developed_id"],
                "actions": pending["actions"],
            }
            or record["actions"] != pending["actions"]
        ):
            raise ProjectError("Saved authoring snapshot differs from pending typed edits")
        state = read_project(project, validate_drafts=False)
        consumed = any(
            pending["guide_edits_file"]
            in read_revision(project, p.name, state["developed_id"]).get("external_inputs", {})
            for p in saved_asset(project, "revisions").glob("rev-*")
            if re.fullmatch(r"rev-[0-9]{3,}", p.name)
        )
        current = (
            not consumed
            and not pending.get("superseded_by_restore", False)
            and pending["developed_id"] == state["developed_id"]
            and pending["base_revision"] == state["working_revision"]
            and pending["inputs_digest"] == draft_digest(project)
        )
        return dict(pending, current=current, consumed=consumed, groups=record["groups"])
    except ProjectError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ProjectError(f"Invalid saved authoring record: {error}") from error


def guidance_draft_digest(project: Path) -> str:
    path = saved_asset(project, "viewer-draft.json")
    return digest(path.read_bytes() if path.exists() else b"")


def _reject_pending_guidance(project: Path) -> None:
    pending = pending_guidance(project)
    if pending and pending["current"] and pending["actions"]:
        raise ProjectError("Saved pending guidance requires preparation first")


def _cache_context_fingerprint(project: Path) -> str:
    """Bind retained state and directory membership without reading raster bodies again."""
    from .matte import _cache_file_identity

    records: dict[str, Any] = {}

    def visit(path: Path) -> None:
        value = path.lstat()
        name = str(path.relative_to(project))
        if stat.S_ISDIR(value.st_mode):
            records[name] = {"device": value.st_dev, "inode": value.st_ino, "mode": value.st_mode}
            with _directory(path) as descriptor:
                children = sorted(os.listdir(descriptor))
            for child in children:
                visit(path / child)
        elif stat.S_ISREG(value.st_mode):
            record: dict[str, Any] = {"identity": _cache_file_identity(value)}
            if path.suffix in {".json", ".toml", ".sha256"}:
                with _directory(path.parent) as parent:
                    descriptor = os.open(
                        path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
                    )
                    with os.fdopen(descriptor, "rb") as stream:
                        if _cache_file_identity(os.fstat(stream.fileno())) != record["identity"]:
                            raise ProjectError(f"Retained processing context changed: {name}")
                        record["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
                        if _cache_file_identity(os.fstat(stream.fileno())) != record["identity"]:
                            raise ProjectError(f"Retained processing context changed: {name}")
            records[name] = record
        else:
            raise ProjectError(f"Unsafe retained processing context: {name}")

    # Cache and lock membership change during clearing; neither is permanent context.
    for name in (
        "state.json",
        "source.json",
        "recipe.toml",
        "guides.json",
        "viewer-draft.json",
        "assets",
        "revisions",
        "requests",
        "recovery",
        "approvals",
        "exports",
        "framing.json",
        "series-framing.json",
    ):
        path = project / name
        if os.path.lexists(path):
            visit(path)
    return digest(_json_bytes(records))


def _processing_dependency(project: Path, name: str) -> Path:
    if not isinstance(name, str) or not Path(name).parts or Path(name).parts[0] == "cache":
        raise ProjectError("Processing cache cannot be a permanent dependency")
    path = _input_file(project, name)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ProjectError(f"Invalid permanent dependency: {name}")
    return path


def _completed_processing_request(project: Path, directory: Path, developed_id: str) -> None:
    """Completion is saved history, independent of later drafts and original request paths."""
    allowed = {"operation.json", "manifest.json", "inputs", "completion.json", "progress.json"}
    if any(
        path.name not in allowed and not re.fullmatch(r"\.state-[a-z0-9_]+\.tmp", path.name)
        for path in directory.iterdir()
    ):
        raise ProjectError(f"Unrecognized processing recovery record: {directory.name}")
    if any(
        path.name not in {"state.json", "source.json", "recipe.toml", "guides.json"}
        and not re.fullmatch(r"\.state-[a-z0-9_]+\.tmp", path.name)
        for path in (directory / "inputs").iterdir()
    ):
        raise ProjectError(f"Unrecognized processing input snapshot: {directory.name}")
    operation, manifest, snapshots = _read_matte_snapshot(project, directory)
    completed = json.loads((directory / "completion.json").read_bytes())
    progress = json.loads((directory / "progress.json").read_bytes())
    revision = completed["revision"]
    retained = read_revision(project, revision, developed_id)
    saved_state = json.loads(snapshots["state.json"])
    saved_source = json.loads(snapshots["source.json"])
    if (
        not isinstance(saved_state, dict)
        or not isinstance(saved_source, dict)
        or operation.get("kind") not in {"matte", "repair"}
        or type(operation.get("schema_version")) is not int
        or operation["schema_version"] != 2
        or operation.get("developed_id") != developed_id
        or saved_state.get("developed_id") != developed_id
        or saved_source.get("developed_id") != developed_id
        or saved_state.get("working_revision") != operation.get("base_revision")
        or digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
        != operation.get("inputs_digest")
        or retained.get("kind") != operation["kind"]
        or retained.get("parent") != operation.get("base_revision")
        or retained.get("inputs_digest") != operation.get("inputs_digest")
        or digest((project / "revisions" / revision / "manifest.json").read_bytes())
        != completed["manifest_sha256"]
        or json.loads((project / "revisions" / revision / "request.json").read_bytes()) != operation
        or not isinstance(completed.get("stage"), str)
        or re.fullmatch(r"\.matte-[a-z0-9_]+", completed["stage"]) is None
        or progress != {"status": "review_needed", "phase": "complete", "revision": revision}
    ):
        raise ProjectError(f"Unresolved or contradictory processing completion: {directory.name}")
    for name, checksum in manifest["dependencies"].items():
        if digest(_processing_dependency(project, name).read_bytes()) != checksum:
            raise ProjectError(f"Retained processing dependency hash mismatch: {name}")


def _cache_restore_backups(project: Path, developed_id: str) -> list[dict[str, Any]]:
    """Validate captured backup shape; never claim that a restore completed."""
    pointers: list[dict[str, Any]] = []
    recovery = project / "recovery"
    if not recovery.exists():
        return pointers
    for directory in sorted(recovery.iterdir()):
        if not directory.is_dir() or re.fullmatch(r"restore-[a-z0-9_]+", directory.name) is None:
            raise ProjectError(
                "Unknown recovery capture; preserve and inspect before clearing cache"
            )
        names = {path.name for path in directory.iterdir()}
        required = {"state.json", "source.json", "recipe.toml", "guides.json", "request.json"}
        if not required <= names or names - required - {"viewer-draft.json"}:
            raise ProjectError(f"Incomplete recovery capture: {directory.name}")
        target = json.loads((directory / "request.json").read_bytes())
        if (
            set(target) != {"revision", "developed_id", "replace_drafts", "target_manifest_sha256"}
            or type(target["replace_drafts"]) is not bool
            or target["developed_id"] != developed_id
        ):
            raise ProjectError("Invalid restore backup target")
        read_revision(project, target["revision"], developed_id)
        if (
            digest((project / "revisions" / target["revision"] / "manifest.json").read_bytes())
            != target["target_manifest_sha256"]
        ):
            raise ProjectError("Restore backup target manifest changed")
        for name in ("state.json", "source.json"):
            saved = json.loads((directory / name).read_bytes())
            if not isinstance(saved, dict) or saved.get("developed_id") != developed_id:
                raise ProjectError("Restore backup source identity differs")
        if "viewer-draft.json" in names:
            try:
                pointer = json.loads((directory / "viewer-draft.json").read_bytes())
                if isinstance(pointer, dict):
                    pointers.append(pointer)
            except ValueError:
                pass  # Opaque invalid prior bytes are deliberately retained by explicit restore.
    return pointers


def _cache_authoring_history(
    project: Path,
    state: dict[str, Any],
    revisions: dict[str, dict[str, Any]],
    backups: list[dict[str, Any]],
    entries: list[Path],
) -> None:
    """Resolve consumed edits or proven supersession, one author per edit batch."""
    metadata = json.loads((project / "source.json").read_bytes())["metadata"]
    width, height = metadata["width"], metadata["height"]
    developed_id = state["developed_id"]
    pointers = list(backups)
    current_path = project / "viewer-draft.json"
    current = json.loads(current_path.read_bytes()) if current_path.exists() else None
    if current is not None:
        if not isinstance(current, dict):
            raise ProjectError("Invalid saved authoring pointer")
        if current != {"superseded_by_restore": True, "unreadable": True}:
            if "superseded_by_restore" in current and (
                current["superseded_by_restore"] is not True
                or {key: value for key, value in current.items() if key != "superseded_by_restore"}
                not in backups
            ):
                raise ProjectError("Unproven authoring supersession")
            pointers.append(current)
    edits: dict[str, dict[str, Any]] = {}
    authors: dict[str, dict[str, Any]] = {}
    for path in entries:
        name = str(path.relative_to(project))
        value = json.loads(path.read_bytes())
        if re.fullmatch(r"viewer-edits-[a-f0-9]{32}\.json", path.name):
            if not isinstance(value, dict) or set(value) != {
                "schema_version",
                "developed_id",
                "actions",
            }:
                raise ProjectError("Invalid retained typed viewer edits")
            if not isinstance(value["actions"], list):
                raise ProjectError("Invalid retained viewer actions")
            # A removal's old region may no longer be current. Seed only those IDs so
            # canonical typed validation checks every action, including remove fields.
            removed_regions = [
                {"id": action.get("id"), "role": "unknown", "shape": "point", "xy": [0, 0]}
                for action in value["actions"]
                if isinstance(action, dict) and action.get("action") == "remove"
            ]
            edit_guides(
                {
                    "schema_version": 2,
                    "developed_id": developed_id,
                    "width": width,
                    "height": height,
                    "regions": removed_regions,
                },
                value,
            )
            edits[name] = value
        else:
            if not isinstance(value, dict) or set(value) != {
                "schema_version",
                "developed_id",
                "actions",
                "groups",
                "previous_recipe",
            }:
                raise ProjectError("Invalid retained viewer authoring record")
            recipe = tomllib.loads(value["previous_recipe"])
            recipe["groups"] = value["groups"]
            Recipe.from_dict(
                recipe,
                developed_id,
                max_margin_px=max(width, height),
                dimensions_wh=(width, height),
            )
            authors[name] = value
    resolved: set[str] = set()
    unbound: list[list[str]] = []
    for name, value in edits.items():
        if value["developed_id"] != developed_id:
            raise ProjectError("Retained authoring master differs")
        checksum = digest((project / name).read_bytes())
        consumed = False
        for revision, manifest in revisions.items():
            binding = manifest.get("external_inputs", {}).get(name)
            if binding is not None:
                if (
                    not isinstance(binding, dict)
                    or binding.get("sha256") != checksum
                    or digest(
                        _processing_dependency(
                            project, f"revisions/{revision}/{binding['snapshot']}"
                        ).read_bytes()
                    )
                    != checksum
                ):
                    raise ProjectError("Consumed viewer edit binding differs")
                consumed = True
        own_pointers = [pointer for pointer in pointers if pointer.get("guide_edits_file") == name]
        # Restore captures its backup before replacing any draft. Only a published
        # supersession pointer (possibly captured by a later restore) proves retirement.
        retired = any(
            pointer.get("superseded_by_restore") is True
            and {key: item for key, item in pointer.items() if key != "superseded_by_restore"}
            in backups
            for pointer in own_pointers
        )
        if (
            current is not None
            and current.get("guide_edits_file") == name
            and current.get("superseded_by_restore") is not True
        ):
            retired = False
        if not consumed and not retired:
            raise ProjectError(
                "Unresolved viewer authoring; prepare or explicitly restore before clearing"
            )
        matching = [
            author_name
            for author_name, author in authors.items()
            if {key: author[key] for key in ("schema_version", "developed_id", "actions")} == value
        ]
        if not matching:
            raise ProjectError("Viewer edits have no matching retained authoring record")
        for pointer in own_pointers:
            if (
                pointer.get("record_file") not in matching
                or pointer.get("actions") != value["actions"]
                or pointer.get("developed_id") != developed_id
                or re.fullmatch(r"[a-f0-9]{64}", str(pointer.get("inputs_digest"))) is None
                or (
                    pointer.get("base_revision") is not None
                    and pointer["base_revision"] not in revisions
                )
            ):
                raise ProjectError("Invalid retained authoring pointer binding")
        bound = {pointer["record_file"] for pointer in own_pointers}
        if len(bound) > 1 or bound & resolved:
            raise ProjectError("Conflicting retained authoring pointer bindings")
        if bound:
            resolved.update(bound)
        else:
            unbound.append(matching)
    # Reserve exact pointer associations before accounting for consumed historical
    # batches with identical actions. One completed batch cannot resolve two authors.
    for matching in unbound:
        remaining = set(matching) - resolved
        if not remaining:
            raise ProjectError("Viewer edit batches outnumber retained authoring records")
        resolved.add(min(remaining))
    if set(authors) != resolved or any(
        pointer.get("guide_edits_file") not in edits
        for pointer in pointers
        if pointer != {"superseded_by_restore": True, "unreadable": True}
    ):
        raise ProjectError("Unrecognized retained viewer authoring history")


def _validate_cache_context(project: Path) -> None:
    state = read_project(project)
    revisions = {}
    for directory in (
        sorted((project / "revisions").iterdir()) if (project / "revisions").exists() else ()
    ):
        if directory.name.startswith("."):
            continue  # Preserved diagnostic stages never stand in for completion.
        revisions[directory.name] = read_revision(project, directory.name, state["developed_id"])
        external = revisions[directory.name].get("external_inputs", {})
        if not isinstance(external, dict):
            raise ProjectError("Invalid permanent external input table")
        for name, binding in external.items():
            if not isinstance(name, str) or Path(name).parts[:1] == ("cache",):
                raise ProjectError("Invalid permanent external input reference")
            if not isinstance(binding, dict) or set(binding) != {"sha256", "snapshot"}:
                raise ProjectError("Invalid permanent external input binding")
            snapshot = _processing_dependency(
                project, f"revisions/{directory.name}/{binding['snapshot']}"
            )
            if digest(snapshot.read_bytes()) != binding["sha256"]:
                raise ProjectError("Permanent external input snapshot differs")
    backups = _cache_restore_backups(project, state["developed_id"])
    authors = []
    requests = project / "requests"
    if requests.exists():
        for entry in sorted(requests.iterdir()):
            if re.fullmatch(r"\.state-[a-z0-9_]+\.tmp", entry.name):
                continue  # Existing initial publication aliases and failed state diagnostics.
            if re.fullmatch(r"matte-[a-z0-9_]+", entry.name) and entry.is_dir():
                _completed_processing_request(project, entry, state["developed_id"])
            elif re.fullmatch(r"review-[a-f0-9]{32}", entry.name) and entry.is_dir():
                from .review import _cycle_record

                record = _cycle_record(project, entry.name)
                allowed = {"head.sha256", *(path.name for path in entry.glob("*.json"))}
                if (
                    record["phase"] != "stopped"
                    or record["developed_id"] != state["developed_id"]
                    or any(
                        path.name not in allowed
                        and not re.fullmatch(r"\.state-[a-z0-9_]+\.tmp", path.name)
                        for path in entry.iterdir()
                    )
                ):
                    raise ProjectError("Unresolved or unrecognized assisted review history")
            elif (
                re.fullmatch(r"viewer-(?:edits-)?[a-f0-9]{32}\.json", entry.name)
                and entry.is_file()
            ):
                authors.append(entry)
            else:
                raise ProjectError(f"Unrecognized processing request: {entry.name}")
    if authors or (project / "viewer-draft.json").exists() or backups:
        _cache_authoring_history(project, state, revisions, backups, authors)
    exports = project / "exports"
    if exports.exists():
        for directory in exports.iterdir():
            if directory.name.startswith("."):
                continue
            if not directory.is_dir():
                raise ProjectError("Unrecognized permanent delivery")
            record = json.loads((directory / "manifest.json").read_bytes())
            revision = record["revision"]
            manifest = revisions[revision]
            expected = {
                f"assets/developed/{state['developed_id']}.tif": json.loads(
                    (project / "source.json").read_bytes()
                )["developed_file_sha256"],
                **{
                    reference["path"]: reference["sha256"]
                    for reference in manifest["assets"].values()
                },
            }
            if (
                record.get("native_assets") != expected
                or record.get("developed_id") != state["developed_id"]
                or record.get("revision_manifest_sha256")
                != digest((project / "revisions" / revision / "manifest.json").read_bytes())
            ):
                raise ProjectError("Invalid permanent delivery native asset references")
            from .export import _delivery_members, _validate_delivery

            request_record = {
                key: value
                for key, value in record.items()
                if key not in {"files", "editable_companion"}
            }
            _validate_delivery(
                directory,
                request_record,
                _delivery_members(request_record, manifest),
                companion_binding=record.get("editable_companion"),
            )


def _cache_prediction(descriptor: int, name: str) -> dict[str, Any]:
    from .matte import _cache_file_identity, _read_tile_prediction

    observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
    if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise ProjectError("Nonregular or multiply linked prediction is protected")
    opened = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    with os.fdopen(opened, "rb") as stream:
        identity = _cache_file_identity(observed)
        if _cache_file_identity(os.fstat(stream.fileno())) != identity:
            raise ProjectError("Cache prediction changed during opening")
        _read_tile_prediction(stream, name[:-4])
        stream.seek(0)
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if (
            _cache_file_identity(os.fstat(stream.fileno())) != identity
            or _cache_file_identity(os.stat(name, dir_fd=descriptor, follow_symlinks=False))
            != identity
        ):
            raise ProjectError("Cache prediction changed during inspection")
    return {
        "path": f"cache/matte/{name}",
        "sha256": checksum,
        "logical_bytes": observed.st_size,
        "identity": identity,
    }


def _processing_cache_snapshot(project: Path) -> tuple[dict[str, Any], str]:
    candidates, protected, blockers = [], [], []
    context = ""
    directories = []
    try:
        context = _cache_context_fingerprint(project)
        _validate_cache_context(project)
        if _cache_context_fingerprint(project) != context:
            raise ProjectError("Processing context changed during inspection")
    except (OSError, ValueError, KeyError, TypeError) as error:
        blockers.append(f"Processing context blocks clearing: {error}")
    cache = project / "cache/matte"
    if os.path.lexists(project / "cache"):
        try:
            with _directory(project / "cache") as parent:
                value = os.fstat(parent)
                directories.append((value.st_dev, value.st_ino, value.st_mode))
                if os.path.lexists(cache):
                    with _directory(cache) as descriptor:
                        value = os.fstat(descriptor)
                        directories.append((value.st_dev, value.st_ino, value.st_mode))
                        for name in sorted(os.listdir(descriptor)):
                            observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                            try:
                                if re.fullmatch(r"[a-f0-9]{64}\.npz", name) is None:
                                    raise ProjectError(
                                        "Unrecognized cache entry or retained diagnostic"
                                    )
                                candidates.append(_cache_prediction(descriptor, name))
                            except (
                                OSError,
                                ValueError,
                                KeyError,
                                TypeError,
                                EOFError,
                                zipfile.BadZipFile,
                            ) as error:
                                protected.append(
                                    {
                                        "path": f"cache/matte/{name}",
                                        "logical_bytes": observed.st_size,
                                        "reason": str(error),
                                    }
                                )
                        with _directory(cache) as current:
                            current_stat = os.fstat(current)
                            if (
                                current_stat.st_dev,
                                current_stat.st_ino,
                                current_stat.st_mode,
                            ) != directories[-1]:
                                raise ProjectError("Cache directory changed during inspection")
        except (OSError, ValueError) as error:
            blockers.append(f"Unsafe cache directory: {error}")
    try:
        if context and _cache_context_fingerprint(project) != context:
            blockers.append("Processing context changed while enumerating predictions")
    except (OSError, ValueError) as error:
        blockers.append(f"Processing context changed: {error}")
    return {
        "candidates": candidates,
        "protected": protected,
        "blockers": blockers,
        "candidate_logical_bytes": sum(entry["logical_bytes"] for entry in candidates),
        "candidate_digest": digest(
            _json_bytes({"candidates": candidates, "context": context, "directories": directories})
        ),
    }, context


def inspect_processing_cache(project: Path) -> dict[str, Any]:
    """Read eligible single-link predictions and blockers without any project write."""
    project = _root(project)
    report, _ = _processing_cache_snapshot(project)
    try:
        report["writer_busy"] = project_writer_busy(project)
    except (OSError, ProjectError) as error:
        report["writer_busy"] = None
        report["blockers"].append(f"Cannot inspect writer lock: {error}")
    return report


def _recheck_cache_context(project: Path, expected: str) -> None:
    if _cache_context_fingerprint(project) != expected:
        raise ProjectError(
            "Processing context changed; inspect requests, recovery and permanent references"
        )


def clear_processing_cache(
    project: Path, expected_digest: str, *, storage_config: StorageConfig | None = None
) -> dict[str, Any]:
    """Clear only the exact confirmed expendable set under the canonical writer lock."""
    project = _root(project)
    validate_library_project(project, storage_config)
    if (
        not isinstance(expected_digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", expected_digest) is None
    ):
        raise ProjectError("Cache clear requires the exact inspected confirmation digest")
    with project_lock(project):
        report, context = _processing_cache_snapshot(project)
        if report["blockers"]:
            raise ProjectError("; ".join(report["blockers"]))
        if report["candidate_digest"] != expected_digest:
            raise ProjectError("Stale cache confirmation digest; inspect again before clearing")
        result: dict[str, Any] = {
            "status": "cleared",
            "removed": [],
            "removed_logical_bytes": 0,
            "failures": [],
            "durability_uncertain": False,
            "candidate_digest": expected_digest,
        }
        if not report["candidates"]:
            return result
        cache = project / "cache/matte"
        with _directory(cache) as descriptor:
            held = os.fstat(descriptor)
            for entry in report["candidates"]:
                try:
                    _recheck_cache_context(project, context)
                    with _directory(cache) as current:
                        observed = os.fstat(current)
                        if (observed.st_dev, observed.st_ino) != (held.st_dev, held.st_ino):
                            raise ProjectError(
                                "Cache directory changed; retained directory preserved"
                            )
                    name = Path(entry["path"]).name
                    if _cache_prediction(descriptor, name) != entry:
                        raise ProjectError("Cache prediction changed; remaining entries preserved")
                    os.unlink(name, dir_fd=descriptor)
                    result["removed"].append(entry["path"])
                    result["removed_logical_bytes"] += entry["logical_bytes"]
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    EOFError,
                    zipfile.BadZipFile,
                ) as error:
                    result["status"] = "partial"
                    result["failures"].append({"path": entry["path"], "error": str(error)})
                    break
            if result["removed"]:
                try:
                    os.fsync(descriptor)
                except OSError as error:
                    result["status"] = "partial"
                    result["durability_uncertain"] = True
                    result["failures"].append(
                        {"path": "cache/matte", "error": f"Directory durability uncertain: {error}"}
                    )
        return result
