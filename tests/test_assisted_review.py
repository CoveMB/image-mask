"""Synthetic public-operation cycles; no live assistant or photographic acceptance."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_ingest import saved_raster
from test_matte_operations import StubSession, approve, prepared, run_matte
from test_operations import edits, request

from blackmask import operations, review
from blackmask.export import export_project
from blackmask.project import ProjectError, read_project


def baseline(tmp_path):
    source, project, prepared_result = prepared(tmp_path)
    approve(project, prepared_result)
    result = run_matte(project)
    operations.accept_revision(project, result["revision"])
    exported = export_project(project)
    return source, project, result, Path(exported["directory"])


def cycle_request(project, action, **fields):
    return {
        "schema_version": 2,
        "action": action,
        "developed_id": read_project(project)["developed_id"],
        "base_revision": read_project(project)["working_revision"],
        "inputs_digest": operations.draft_digest(project),
        **fields,
    }


def start(project):
    return review.review_cycle(
        project, cycle_request(project, "start", user_request="Review the synthetic gap")
    )


@pytest.mark.parametrize(
    "damage", ["overview", "scale", "origin", "dimensions", "missing-view", "wrong-png"]
)
def test_rehashed_reduced_review_cannot_authorize_native_edits(tmp_path, damage):
    from blackmask.project import _json_bytes, digest

    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    path = project / envelope["review_manifest_file"]
    record = json.loads(path.read_bytes())
    if damage == "overview":
        record["overview"] = True
    elif damage == "scale":
        record["crops"][0]["scale_xy"] = [2, 2]
    elif damage == "origin":
        record["crops"][0]["native_origin_xy"] = [1, 0]
    elif damage == "dimensions":
        record["crops"][0]["displayed_dimensions_wh"] = [1, 1]
    elif damage == "missing-view":
        del record["crops"][0]["files"]["source_RGB8_VIEW"]
    else:
        name = record["crops"][0]["files"]["source_RGB8_VIEW"]
        Image.new("RGB", (1, 1)).save(path.parent / name)
        record["view_files"][name] = digest((path.parent / name).read_bytes())
    raw_revision = (project / "revisions" / record["revision"] / "manifest.json").read_bytes()
    key = digest(_json_bytes({"review": record, "manifest": digest(raw_revision)}))
    destination = path.parent.parent / key
    path.parent.rename(destination)
    (destination / "manifest.json").write_bytes(_json_bytes(record))
    envelope["review_manifest_file"] = str((destination / "manifest.json").relative_to(project))
    state = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="native|Native"):
        review.validate_assisted(project, request(project, assisted_review=envelope))
    assert (project / "state.json").read_bytes() == state


def proposal(project, cycle, defect_id="gap"):
    current = review.review_project(project, crops=[[0, 0, 3, 2]])
    return {
        "cycle_id": cycle["cycle_id"],
        "review_manifest_file": str(Path(current["manifest_file"]).relative_to(project)),
        "defect": {
            "id": defect_id,
            "classification": "alpha",
            "location_xyxy": [1, 0, 2, 1],
            "source_evidence": "Synthetic source pixel is explicitly selected as empty by the fixture",
            "likely_cause": "Fixture alpha differs from the selected categorical background",
            "uncertainty": "Synthetic contract only; no photographic judgement",
            "source_resolved": True,
        },
    }


def prepare_repair(project, envelope, *, background=True):
    filename = edits(
        project,
        [
            {
                "id": "change",
                "role": "background" if background else "foreground",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 1],
            },
            {
                "id": "scope",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 1],
                "feather_px": 0,
            },
            {
                "id": "protected",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 1, 2, 2],
                "revision": "rev-002",
            },
        ],
    )
    result = operations.apply_operation(
        project, request(project, guide_edits_file=filename, assisted_review=envelope)
    )
    approve(project, result)
    operation = request(
        project,
        kind="repair",
        reason="Synthetic source-visible gap",
        context_xyxy=[0, 0, 3, 2],
        scope_xyxy=[1, 0, 2, 1],
        support_file=result["support_file"],
        assisted_review=envelope,
    )
    return operation


def repair(project, operation):
    with patch("blackmask.operations.VitMatteSession", StubSession):
        return operations.apply_operation(
            project, operation, model_cache=Path("unused-explicit-test-cache")
        )


def assess(project, cycle, outcome="improved"):
    return review.review_cycle(
        project,
        cycle_request(
            project,
            "assess",
            cycle_id=cycle["cycle_id"],
            outcome=outcome,
            comparison="Matching synthetic source/before/after crops inspected; no human photographic acceptance",
        ),
    )


def test_shared_two_attempt_budget_and_preservation_reopen(tmp_path):
    source, project, original, exported = baseline(tmp_path)
    capture = source.read_bytes()
    accepted = {p.name: p.read_bytes() for p in exported.iterdir() if p.is_file()}
    original_alpha = np.array(
        Image.open(saved_raster(project / "revisions" / original["revision"] / "base_alpha16.png"))
    )
    cycle = start(project)
    for index in range(2):
        envelope = proposal(project, cycle, defect_id=f"gap-{index}")
        operation = prepare_repair(project, envelope, background=index == 0)
        result = repair(project, operation)
        with pytest.raises(ProjectError, match="assessment|pending"):
            operations.apply_operation(project, request(project, assisted_review=envelope))
        cycle = assess(project, cycle)
        assert cycle["attempts"] == index + 1
        alpha = np.array(
            Image.open(
                saved_raster(project / "revisions" / result["revision"] / "base_alpha16.png")
            )
        )
        assert alpha[1, 1] == original_alpha[1, 1] == 16384
        assert alpha[0, 0] == original_alpha[0, 0] and alpha[1, 2] == original_alpha[1, 2]
    assert cycle["stop_reason"] == "attempt_budget_exhausted"
    assert cycle["best_revision"] == result["revision"] and cycle["status"] == "review_needed"
    with pytest.raises(ProjectError, match="stopped|budget"):
        operations.apply_operation(project, request(project, assisted_review=envelope))
    saved = review.review_cycle(
        project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
    )
    assert saved == cycle
    assert len(list((project / "requests" / cycle["cycle_id"]).glob("*.json"))) == 5
    assert read_project(project)["accepted_revision"] == original["revision"]
    assert read_project(project)["status"] == "review_needed"
    assert source.read_bytes() == capture
    assert {p.name: p.read_bytes() for p in exported.iterdir() if p.is_file()} == accepted
    revision = project / "revisions" / result["revision"]
    assert json.loads((revision / "request.json").read_bytes()) == operation
    assert json.loads((revision / "result.json").read_bytes())["revision"] == result["revision"]


@pytest.mark.parametrize(
    "outcome",
    ["no_progress", "regression", "ambiguous", "missing_source_evidence", "user_decision"],
)
def test_early_stop_retains_best_without_acceptance(tmp_path, outcome):
    _, project, original, _ = baseline(tmp_path)
    cycle = start(project)
    result = repair(project, prepare_repair(project, proposal(project, cycle)))
    cycle = assess(project, cycle, outcome)
    assert cycle["attempts"] == 1 and cycle["stop_reason"] == outcome
    assert cycle["best_revision"] == original["revision"]
    assert read_project(project)["working_revision"] == result["revision"]
    assert read_project(project)["accepted_revision"] == original["revision"]
    # A distinct explicit request is a distinct budget, never an implicit restart.
    new = start(project)
    assert new["cycle_id"] != cycle["cycle_id"] and new["attempts"] == 0


def test_unchanged_alpha_forces_no_progress(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    repair(project, prepare_repair(project, envelope))
    cycle = assess(project, cycle)
    envelope = proposal(project, start(project))
    operation = prepare_repair(project, envelope)
    repair(project, operation)
    cycle = assess(project, {"cycle_id": envelope["cycle_id"]})
    assert cycle["stop_reason"] == "no_progress" and cycle["attempts"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("classification", "color"),
        ("classification", "shading"),
        ("classification", "user_decision"),
        ("classification", "execute"),
        ("source_resolved", False),
        ("source_evidence", ""),
        ("location_xyxy", [0, 0, 4, 2]),
    ],
)
def test_invalid_proposal_does_not_run_or_change_state(tmp_path, field, value):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    envelope["defect"][field] = value
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.apply_operation(project, request(project, assisted_review=envelope))
    assert (project / "state.json").read_bytes() == before
    assert (
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )["attempts"]
        == 0
    )


def test_review_manifest_has_current_identity_paths_settings_and_stale_labels(tmp_path):
    _, project, original, _ = baseline(tmp_path)
    first = review.review_project(project, crops=[[1, 0, 3, 2]])
    manifest = json.loads(saved_raster(Path(first["manifest_file"])).read_bytes())
    assert manifest["inputs_digest"] == operations.draft_digest(project)
    assert manifest["working_revision"] == original["revision"]
    assert manifest["qa"]["structural_checks"] == "passed"
    assert manifest["settings"]["matting"]["device"] == "auto"
    assert manifest["effects"]["available"] is True
    assert manifest["effects"]["color_cleanup"]["enabled"] is False
    assert manifest["stale_labels"] == []
    for name in ("source_rgb16", "foreground_rgb16", "alpha16"):
        assert (saved_raster(project / manifest["assets"][name])).is_file()
    with (project / "recipe.toml").open("a") as stream:
        stream.write("\n# external draft edit\n")
    second = review.review_project(project, crops=[[1, 0, 3, 2]])
    stale = json.loads(saved_raster(Path(second["manifest_file"])).read_bytes())
    assert second != first and "draft_changed" in stale["stale_labels"]


def test_failed_attempt_resumes_once_and_stopped_cycle_cannot_resume_completed(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    operation = prepare_repair(project, proposal(project, cycle))
    with (
        patch("blackmask.operations.VitMatteSession", StubSession),
        patch.object(StubSession, "predict", side_effect=RuntimeError("controlled interruption")),
        pytest.raises(ProjectError, match="controlled interruption"),
    ):
        repair(project, operation)
    saved = review.review_cycle(
        project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
    )
    assert saved["attempts"] == 1 and saved["phase"] == "awaiting_assessment"
    statuses = operations.operation_status(project)
    operation_id = next(
        r["operation_id"] for r in statuses["operations"] if r["status"] == "failed"
    )
    with patch("blackmask.operations.VitMatteSession", StubSession):
        result = operations.resume_operation(
            project, operation_id, model_cache=Path("unused-explicit-test-cache")
        )
    assert (
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )["attempts"]
        == 1
    )
    review.review_cycle(
        project,
        cycle_request(project, "stop", cycle_id=cycle["cycle_id"], reason="User requested stop"),
    )
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="stopped"):
        operations.resume_operation(project, result["operation_id"], model_cache=Path("unused"))
    assert (project / "state.json").read_bytes() == before


def test_assisted_lock_removal_and_conflicting_core_rejected(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    operation = prepare_repair(project, envelope)
    repair(project, operation)
    cycle = assess(project, cycle)
    envelope = proposal(project, cycle)
    before = (project / "state.json").read_bytes()
    filename = edits(
        project,
        [{"id": "conflict", "role": "background", "shape": "rectangle", "xyxy": [1, 1, 2, 2]}],
    )
    with pytest.raises(ProjectError, match="lock"):
        operations.apply_operation(
            project, request(project, guide_edits_file=filename, assisted_review=envelope)
        )
    (project / filename).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "developed_id": read_project(project)["developed_id"],
                "actions": [{"action": "remove", "id": "protected"}],
            }
        )
    )
    with pytest.raises(ProjectError, match="lock"):
        operations.apply_operation(
            project, request(project, guide_edits_file=filename, assisted_review=envelope)
        )
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("corrupt", ["draft", "manifest", "crop"])
def test_stale_or_changed_review_assets_fail_without_attempt(tmp_path, corrupt):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    operation = request(project, assisted_review=envelope)
    if corrupt == "draft":
        with (project / "recipe.toml").open("a") as stream:
            stream.write("\n# newer draft\n")
    else:
        manifest = project / envelope["review_manifest_file"]
        if corrupt == "manifest":
            data = json.loads(saved_raster(manifest).read_bytes())
            data["crops"][0]["native_origin_xy"] = [999, 999]
            manifest.write_text(json.dumps(data))
        else:
            saved_raster(next(manifest.parent.glob("crop-*.png"))).write_bytes(
                b"changed reviewed pixels"
            )
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="Stale|stale|changed|Invalid"):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before
    assert (
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )["attempts"]
        == 0
    )


def test_cycle_cli_round_trip_and_actual_competing_process(tmp_path):
    import os
    import subprocess
    import sys

    from blackmask.project import project_lock

    _, project, _, _ = baseline(tmp_path)
    cycle_file = project / "cycle-start.json"
    cycle_file.write_text(
        json.dumps(cycle_request(project, "start", user_request="Explicit synthetic CLI cycle"))
    )
    command = [
        sys.executable,
        "-m",
        "blackmask",
        "review",
        str(project),
        "--cycle-request",
        str(cycle_file),
    ]
    environment = dict(os.environ, PYTHONPATH=str(Path("src").absolute()))
    with project_lock(project):
        loser = subprocess.run(
            command, capture_output=True, text=True, env=environment, check=False
        )
    assert loser.returncode == 1 and "busy" in loser.stderr.lower()
    winner = subprocess.run(command, capture_output=True, text=True, env=environment, check=False)
    assert winner.returncode == 0, winner.stderr
    cycle = json.loads(winner.stdout)
    cycle_file.write_text(
        json.dumps({"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]})
    )
    reopened = subprocess.run(command, capture_output=True, text=True, env=environment, check=False)
    assert reopened.returncode == 0 and json.loads(reopened.stdout) == cycle


def test_unknown_off_image_reapplied_and_stale_repairs_fail_before_attempt(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    operation = prepare_repair(project, proposal(project, cycle))
    before = (project / "state.json").read_bytes()
    for update in [
        {"kind": "effects"},
        {"context_xyxy": [0, 0, 4, 2]},
        {"inputs_digest": "0" * 64},
        {"guide_edits_file": "edits.json"},
        {"support_file": "edits.json"},
    ]:
        with pytest.raises(ProjectError):
            repair(project, dict(operation, **update))
    assert (project / "state.json").read_bytes() == before
    assert (
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )["attempts"]
        == 0
    )


def test_absolute_native_review_rejected_before_repair_reservation(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    operation = prepare_repair(project, proposal(project, cycle))
    envelope = operation["assisted_review"]
    absolute = str(project / envelope["review_manifest_file"])
    assert Path(absolute).is_absolute() and Path(absolute).is_file()
    status_request = {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
    before_cycle = review.review_cycle(project, status_request)
    before_files = {
        str(path.relative_to(project)): (path.read_bytes(), path.stat().st_mode)
        for path in project.rglob("*")
        if path.is_file()
    }
    invalid = dict(operation, assisted_review=dict(envelope, review_manifest_file=absolute))
    with pytest.raises(ProjectError, match="relative project file"):
        repair(project, invalid)
    # Includes attempts/phase/history, requests/recovery and all saved state/assets.
    assert review.review_cycle(project, status_request) == before_cycle
    assert {
        str(path.relative_to(project)): (path.read_bytes(), path.stat().st_mode)
        for path in project.rglob("*")
        if path.is_file()
    } == before_files
    repaired = repair(project, operation)
    after_cycle = review.review_cycle(project, status_request)
    assert after_cycle["attempts"] == 1 and after_cycle["phase"] == "awaiting_assessment"
    assert read_project(project)["working_revision"] == repaired["revision"]


def test_consumed_viewer_draft_allows_manual_to_assisted_continuation(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    operations.save_guidance_draft(
        project,
        request(project),
        [],
        [
            {
                "action": "upsert",
                "region": {"id": "viewer-bg", "role": "background", "shape": "point", "xy": [2, 1]},
            }
        ],
    )
    prepared_result = operations.prepare_guidance_draft(project, request(project), [0, 0, 3, 2])
    assert operations.pending_guidance(project)["consumed"] is True
    approve(project, prepared_result)
    run_matte(project)
    cycle = start(project)
    envelope = proposal(project, cycle)
    manifest = json.loads((saved_raster(project / envelope["review_manifest_file"])).read_bytes())
    assert manifest["stale_labels"] == []
    result = operations.apply_operation(project, request(project, assisted_review=envelope))
    assert result["status"] == "review_needed"


@pytest.mark.parametrize("event", ["reserve", "assess", "stop"])
def test_altered_terminal_event_rejects_status_new_attempt_and_resume(tmp_path, event):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    result = repair(project, prepare_repair(project, envelope))
    if event == "assess":
        assess(project, cycle, "regression")
    elif event == "stop":
        review.review_cycle(
            project,
            cycle_request(project, "stop", cycle_id=cycle["cycle_id"], reason="Explicit stop"),
        )
    directory = project / "requests" / cycle["cycle_id"]
    last = max(directory.glob("*.json"))
    saved_raster(last.with_suffix(".preserved")).write_bytes(saved_raster(last).read_bytes())
    record = json.loads(saved_raster(last).read_bytes())
    record["phase"] = "ready"
    last.write_text(json.dumps(record))
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="history|event|integrity"):
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )
    with pytest.raises(ProjectError, match="history|event|integrity"):
        operations.apply_operation(project, request(project, assisted_review=envelope))
    with pytest.raises(ProjectError, match="history|event|integrity"):
        operations.resume_operation(project, result["operation_id"], model_cache=Path("unused"))
    assert (project / "state.json").read_bytes() == before


def test_truncated_reserved_history_rejected_by_retained_recovery(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    operation = prepare_repair(project, envelope)
    with (
        patch.object(StubSession, "predict", side_effect=RuntimeError("controlled failure")),
        pytest.raises(ProjectError),
    ):
        repair(project, operation)
    directory = project / "requests" / cycle["cycle_id"]
    last = max(directory.glob("*.json"))
    saved_raster(last).rename(last.with_suffix(".retained-reservation"))
    before = (project / "state.json").read_bytes()
    for action in [
        lambda: review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        ),
        lambda: operations.apply_operation(project, request(project, assisted_review=envelope)),
    ]:
        with pytest.raises(ProjectError, match="history|reservation"):
            action()
    assert (project / "state.json").read_bytes() == before


def test_renamed_contradictory_stop_event_rejected(tmp_path):
    from blackmask.project import _json_bytes, digest

    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    review.review_cycle(
        project, cycle_request(project, "stop", cycle_id=cycle["cycle_id"], reason="Explicit stop")
    )
    directory = project / "requests" / cycle["cycle_id"]
    last = max(directory.glob("*.json"))
    record = json.loads(saved_raster(last).read_bytes())
    record["phase"] = "ready"
    saved_raster(last).rename(last.with_suffix(".retained-stop"))
    data = _json_bytes(record)
    (saved_raster(directory / f"001-{digest(data)}.json")).write_bytes(data)
    with pytest.raises(ProjectError, match="history|event|transition"):
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )


@pytest.mark.parametrize("terminal", ["stop", "regression"])
def test_lost_terminal_disposition_rejects_status_and_completed_resume(tmp_path, terminal):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    result = repair(project, prepare_repair(project, proposal(project, cycle)))
    if terminal == "stop":
        review.review_cycle(
            project,
            cycle_request(project, "stop", cycle_id=cycle["cycle_id"], reason="Explicit stop"),
        )
    else:
        assess(project, cycle, "regression")
    directory = project / "requests" / cycle["cycle_id"]
    last = max(directory.glob("*.json"))
    saved_raster(last).rename(last.with_suffix(".retained-terminal"))
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="history|anchor|integrity"):
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )
    with pytest.raises(ProjectError, match="history|anchor|integrity"):
        operations.resume_operation(project, result["operation_id"], model_cache=Path("unused"))
    assert (project / "state.json").read_bytes() == before


def test_failed_integrity_anchor_publication_preserves_history_and_fails_closed(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    directory = project / "requests" / cycle["cycle_id"]
    anchor = directory / "head.sha256"
    original_anchor = saved_raster(anchor).read_bytes()
    original_state = (project / "state.json").read_bytes()
    with (
        patch(
            "blackmask.review._atomic_bytes",
            side_effect=OSError("controlled anchor replacement failure"),
        ),
        pytest.raises(OSError, match="anchor"),
    ):
        review.review_cycle(
            project,
            cycle_request(project, "stop", cycle_id=cycle["cycle_id"], reason="Explicit stop"),
        )
    assert saved_raster(anchor).read_bytes() == original_anchor
    assert len(list(directory.glob("*.json"))) == 2
    with pytest.raises(ProjectError, match="history|anchor|integrity"):
        review.review_cycle(
            project, {"schema_version": 2, "action": "status", "cycle_id": cycle["cycle_id"]}
        )
    assert (project / "state.json").read_bytes() == original_state


def test_integrity_anchor_loss_during_repair_stops_publication(tmp_path):
    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    operation = prepare_repair(project, proposal(project, cycle))
    before = (project / "state.json").read_bytes()
    anchor = project / "requests" / cycle["cycle_id"] / "head.sha256"

    def remove_anchor(rgb, trimap, device):
        saved_raster(anchor).rename(anchor.with_suffix(".retained-anchor"))
        return np.full(trimap.shape, 0.25), {"fixture": "synthetic-anchor-loss"}

    with (
        patch.object(StubSession, "predict", side_effect=remove_anchor),
        pytest.raises(ProjectError, match="history|anchor|integrity"),
    ):
        repair(project, operation)
    assert (project / "state.json").read_bytes() == before
