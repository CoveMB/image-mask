"""Interrupted operation contracts; synthetic approvals are test controls only."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from test_matte_operations import StubSession, approve, prepared, run_matte
from test_operations import request

from blackmask import operations
from blackmask.project import ProjectError, read_project


def recovery_id(project):
    return max(
        (project / "requests").glob("matte-*/manifest.json"), key=lambda p: p.stat().st_mtime_ns
    ).parent.name


def interrupted(project, boundary="inference"):
    target = "blackmask.operations.VitMatteSession.predict"
    if boundary == "inference":
        with (
            patch("blackmask.operations.VitMatteSession", StubSession),
            patch.object(StubSession, "predict", side_effect=RuntimeError("interrupted")),
            pytest.raises(ProjectError, match="interrupted"),
        ):
            operations.apply_operation(
                project, request(project, kind="matte"), model_cache=Path("unused")
            )
    else:
        target = (
            "blackmask.review.write_review"
            if boundary == "write_review"
            else "blackmask.operations." + boundary
        )
        original = operations._atomic_json

        def fail_pointer(path, value, **kwargs):
            if path.name == "state.json":
                raise OSError("interrupted")
            return original(path, value, **kwargs)

        failure = fail_pointer if boundary == "_atomic_json" else OSError("interrupted")
        with (
            patch("blackmask.operations.VitMatteSession", StubSession),
            patch(target, side_effect=failure),
            pytest.raises(OSError, match="interrupted"),
        ):
            operations.apply_operation(
                project, request(project, kind="matte"), model_cache=Path("unused")
            )
    return recovery_id(project)


@pytest.mark.parametrize(
    "boundary", ["inference", "write_review", "_publish_new_directory", "_atomic_json"]
)
@pytest.mark.parametrize("trimap_confirmed", [False, True])
def test_resume_preserves_accepted_export_and_finishes_review(tmp_path, boundary, trimap_confirmed):
    from blackmask.export import export_project

    _, project, initial = prepared(tmp_path)
    approve(project, initial)
    accepted = run_matte(project)
    operations.accept_revision(project, accepted["revision"])
    exported = Path(export_project(project)["directory"])
    saved_export = {p.name: p.read_bytes() for p in exported.iterdir() if p.is_file()}
    preparation = operations.apply_operation(project, request(project))
    if trimap_confirmed:
        approve(project, preparation)
    state_before = (project / "state.json").read_bytes()
    operation_id = interrupted(project, boundary)
    assert (project / "state.json").read_bytes() == state_before
    status = operations.operation_status(project)
    assert any(
        item["operation_id"] == operation_id and item["status"] == "failed"
        for item in status["operations"]
    )
    with patch("blackmask.operations.VitMatteSession", StubSession):
        result = operations.resume_operation(project, operation_id, model_cache=Path("unused"))
    assert result["status"] == "review_needed"
    assert (
        project / "revisions" / result["revision"] / "trimap_approval.json"
    ).exists() is trimap_confirmed
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    assert {p.name: p.read_bytes() for p in exported.iterdir() if p.is_file()} == saved_export
    assert operations.resume_operation(project, operation_id)["revision"] == result["revision"]


@pytest.mark.parametrize("changed", ["recipe.toml", "guides.json", "snapshot", "support"])
def test_resume_rejects_paused_edits_without_overwriting(tmp_path, changed):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project)
    if changed == "snapshot":
        path = project / "requests" / operation_id / "inputs/recipe.toml"
    elif changed == "support":
        path = project / "revisions" / result["revision"] / "supports/support16.png"
    else:
        path = project / changed
    path.write_bytes(path.read_bytes() + b" ")
    retained = path.read_bytes()
    state = (project / "state.json").read_bytes()
    with pytest.raises((ProjectError, ValueError), match="Stale|stale|hash|snapshot|Invalid"):
        operations.resume_operation(project, operation_id, model_cache=Path("unused"))
    assert path.read_bytes() == retained and (project / "state.json").read_bytes() == state


def test_moved_source_must_match_hash(tmp_path):
    source, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project)
    moved = tmp_path / "moved.tif"
    moved.write_bytes(b"wrong")
    with pytest.raises(ProjectError, match="source|Source"):
        operations.resume_operation(project, operation_id, source=moved, model_cache=Path("unused"))
    moved.write_bytes(source.read_bytes())
    with patch("blackmask.operations.VitMatteSession", StubSession):
        assert (
            operations.resume_operation(
                project, operation_id, source=moved, model_cache=Path("unused")
            )["status"]
            == "review_needed"
        )


def test_unknown_cache_dependencies_are_misses(tmp_path):
    from blackmask.matte import native_matte

    rgb = np.zeros((3, 7, 3), dtype=np.uint8)
    trimap = np.full((3, 7), 128, dtype=np.uint8)
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        return np.full(guide.shape, 0.25), {}

    for _ in range(2):
        native_matte(
            rgb, trimap, predict, "cpu", cache_dir=tmp_path, cache_identity={"master_id": "unknown"}
        )
    assert calls == ["cpu", "cpu"]


def test_interrupt_tiles_reuses_only_completed_and_backend_switch_restarts_all(tmp_path):
    from test_matte import cache_identity

    from blackmask.matte import native_matte

    rgb = np.zeros((7, 1025, 3), dtype=np.uint8)
    guide = np.full(rgb.shape[:2], 128, dtype=np.uint8)
    calls = []

    def predict(rgb, trimap, device):
        calls.append(device)
        if len(calls) == 2:
            raise RuntimeError("interrupted tile")
        return np.full(trimap.shape, 0.25), {"device": device}

    with pytest.raises(ValueError, match="interrupted tile"):
        native_matte(
            rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
        )
    alpha, record = native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    assert calls == ["cpu", "cpu", "cpu"] and record["reused_tiles"] == 1
    assert np.all(alpha == 16384)
    native_matte(rgb, guide, predict, "mps", cache_dir=tmp_path, cache_identity=cache_identity())
    native_matte(rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity())
    assert calls == ["cpu", "cpu", "cpu", "mps", "mps", "cpu", "cpu"]


@pytest.mark.parametrize(
    "changed",
    [
        "master_id",
        "revision",
        "hashes",
        "packages",
        "dtype",
        "preprocessing",
        "attention",
        "context_xyxy",
    ],
)
def test_complete_cache_identity_changes_invalidate(tmp_path, changed):
    from test_matte import cache_identity

    from blackmask.matte import native_matte

    rgb = np.zeros((3, 7, 3), dtype=np.uint8)
    guide = np.full(rgb.shape[:2], 128, dtype=np.uint8)
    identity = cache_identity()
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        return np.full(guide.shape, 0.25), {}

    native_matte(rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=identity)
    _, warm = native_matte(rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=identity)
    assert warm["reused_tiles"] == 1 and calls == ["cpu"]
    if changed == "hashes":
        identity["hashes"]["config.json"] = "f" * 64
    elif changed == "packages":
        identity["packages"]["torch"] = "changed-test-version"
    elif changed == "master_id":
        identity[changed] = "f" * 64
    elif changed == "revision":
        identity[changed] = "f" * 40
    elif changed == "context_xyxy":
        identity[changed] = [1, 0, 8, 3]
    else:
        identity[changed] = "changed"
    native_matte(rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=identity)
    assert calls == ["cpu", "cpu"]


def test_completed_stage_resume_does_not_construct_models(tmp_path):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project, "_publish_new_directory")
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("repeat model")):
        resumed = operations.resume_operation(project, operation_id)
    assert resumed["resumed_completed_stage"] is True


def test_resume_low_space_and_midrun_edit_preserve_state(tmp_path):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project)
    state = (project / "state.json").read_bytes()
    with (
        patch(
            "blackmask.operations.check_space", side_effect=ProjectError("Insufficient free space")
        ),
        pytest.raises(ProjectError, match="space"),
    ):
        operations.resume_operation(project, operation_id, model_cache=Path("unused"))
    retained = (project / "guides.json").read_bytes() + b" "

    class EditingSession(StubSession):
        def predict(self, rgb, guide, device):
            (project / "guides.json").write_bytes(retained)
            return super().predict(rgb, guide, device)

    with (
        patch("blackmask.operations.VitMatteSession", EditingSession),
        pytest.raises(ProjectError, match="Stale"),
    ):
        operations.resume_operation(project, operation_id, model_cache=Path("unused"))
    assert (project / "state.json").read_bytes() == state
    assert (project / "guides.json").read_bytes() == retained


def test_fresh_cli_resume_and_status_under_real_writer_contention(tmp_path):
    import subprocess
    import sys

    _, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project, "_publish_new_directory")
    worker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from blackmask.project import project_lock; import sys; \nwith project_lock(Path(sys.argv[1])): print('locked', flush=True); sys.stdin.readline()",
            str(project),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert worker.stdout.readline().strip() == "locked"
        status = subprocess.run(
            [sys.executable, "-m", "blackmask", "status", str(project)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert status.returncode == 0 and json.loads(status.stdout)["writer_busy"] is True
        busy = subprocess.run(
            [
                sys.executable,
                "-m",
                "blackmask",
                "resume",
                str(project),
                "--operation",
                operation_id,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert busy.returncode == 1 and "busy" in busy.stderr
    finally:
        worker.communicate("release\n", timeout=15)
    assert worker.returncode == 0
    resumed = subprocess.run(
        [sys.executable, "-m", "blackmask", "resume", str(project), "--operation", operation_id],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert resumed.returncode == 0 and json.loads(resumed.stdout)["resumed_completed_stage"]


@pytest.mark.parametrize(
    "missing",
    ["config.json", "preprocessor_config.json", "model.safetensors", "torch", "numpy", "Pillow"],
)
def test_incomplete_nested_cache_dependencies_miss(tmp_path, missing):
    from test_matte import cache_identity

    from blackmask.matte import native_matte

    identity = cache_identity()
    identity["hashes" if missing.endswith(("json", "safetensors")) else "packages"].pop(missing)
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        return np.full(guide.shape, 0.25), {}

    for _ in range(2):
        native_matte(
            np.zeros((3, 7, 3), dtype=np.uint8),
            np.full((3, 7), 128, dtype=np.uint8),
            predict,
            "cpu",
            cache_dir=tmp_path,
            cache_identity=identity,
        )
    assert calls == ["cpu", "cpu"]


def test_scoped_repair_completed_stage_recovery_preserves_outside_and_acceptance(tmp_path):
    from test_repair_operations import alpha_at, parent_project, repair_guides, repair_request

    from blackmask.repair import replay_repair

    source, project, parent = parent_project(tmp_path)
    original = source.read_bytes()
    prepared_result = repair_guides(project, [1, 1, 4, 3])
    operation = repair_request(project, prepared_result, [0, 0, 5, 4], [1, 1, 4, 3])
    with (
        patch("blackmask.operations.VitMatteSession", StubSession),
        patch("blackmask.operations._publish_new_directory", side_effect=OSError("interrupted")),
        pytest.raises(OSError, match="interrupted"),
    ):
        operations.apply_operation(project, operation, model_cache=Path("unused"))
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("model replay")):
        resumed = operations.resume_operation(project, recovery_id(project))
    alpha = alpha_at(project, resumed["revision"])
    np.testing.assert_array_equal(alpha, replay_repair(project, resumed["revision"]))
    outside = np.ones((4, 5), dtype=bool)
    outside[1:3, 1:4] = False
    np.testing.assert_array_equal(alpha[outside], alpha_at(project, parent["revision"])[outside])
    assert (
        source.read_bytes() == original
        and read_project(project)["accepted_revision"] == parent["revision"]
    )


@pytest.mark.parametrize("broken", ["manifest.json", "operation.json", "completion.json"])
def test_malformed_recovery_records_fail_actionably(tmp_path, broken):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project, "_publish_new_directory")
    (project / "requests" / operation_id / broken).write_text('{"bad": true}')
    with pytest.raises(ProjectError, match="Invalid|snapshot|recovery|Recovery"):
        operations.resume_operation(project, operation_id)


@pytest.mark.parametrize("repairing", [False, True])
def test_request_edit_between_capture_and_record_rejects_completed_resume(tmp_path, repairing):
    if repairing:
        from test_repair_operations import parent_project, repair_guides, repair_request

        _, project, _ = parent_project(tmp_path)
        prepared_result = repair_guides(project, [1, 1, 4, 3])
        operation = repair_request(project, prepared_result, [0, 0, 5, 4], [1, 1, 4, 3])
        changed = dict(operation, scope_xyxy=[1, 1, 3, 3])
    else:
        _, project, prepared_result = prepared(tmp_path)
        approve(project, prepared_result)
        operation = request(project, kind="matte")
        changed = dict(operation, inputs_digest="0" * 64)
    path = project / "request.json"
    path.write_text(json.dumps(operation))
    state = (project / "state.json").read_bytes()
    original = operations._save_matte_request

    def editing_save(*args, **kwargs):
        path.write_text(json.dumps(changed))
        return original(*args, **kwargs)

    with (
        patch("blackmask.operations.VitMatteSession", StubSession),
        patch("blackmask.operations._save_matte_request", editing_save),
        pytest.raises(ProjectError, match="Stale"),
    ):
        operations.apply_operation(
            project, operation, model_cache=Path("unused"), request_file=path
        )
    operation_id = recovery_id(project)
    assert (project / "requests" / operation_id / "completion.json").is_file()
    with pytest.raises(ProjectError, match="Stale"):
        operations.resume_operation(project, operation_id)
    assert (project / "state.json").read_bytes() == state
    assert json.loads(path.read_bytes()) == changed


@pytest.mark.parametrize("repairing", [False, True])
@pytest.mark.parametrize(
    "boundary,error_type",
    [
        ("rerun", OSError),
        ("rerun", ValueError),
        ("rerun", KeyError),
        ("rerun", TypeError),
        ("rerun", ProjectError),
        ("publication", OSError),
        ("sync", OSError),
        ("pointer", OSError),
    ],
)
def test_valid_resume_failure_preserves_cause_acceptance_and_retry(
    tmp_path, repairing, boundary, error_type
):
    from test_repair_operations import parent_project, repair_guides, repair_request

    from blackmask.export import export_project

    source, project, accepted = parent_project(tmp_path)
    original_source = source.read_bytes()
    export = Path(export_project(project)["directory"])
    accepted_files = {p.name: p.read_bytes() for p in export.iterdir() if p.is_file()}
    if repairing:
        prepared_result = repair_guides(project, [1, 1, 4, 3])
        operation = repair_request(project, prepared_result, [0, 0, 5, 4], [1, 1, 4, 3])
    else:
        prepared_result = operations.apply_operation(project, request(project))
        approve(project, prepared_result)
        operation = request(project, kind="matte")
    initial_boundary = (
        "blackmask.review.write_review"
        if boundary == "rerun"
        else "blackmask.operations._publish_new_directory"
    )
    with (
        patch("blackmask.operations.VitMatteSession", StubSession),
        patch(initial_boundary, side_effect=OSError("initial interruption")),
        pytest.raises(OSError, match="initial interruption"),
    ):
        operations.apply_operation(project, operation, model_cache=Path("unused"))
    operation_id = recovery_id(project)
    saved_state = (project / "state.json").read_bytes()
    error = error_type("temporary storage failure")
    original_json = operations._atomic_json

    def fail_pointer(path, value, **kwargs):
        if path.name == "state.json":
            raise error
        return original_json(path, value, **kwargs)

    target = {
        "rerun": "blackmask.review.write_review",
        "publication": "blackmask.operations._publish_new_directory",
        "sync": "blackmask.operations._sync_directory",
        "pointer": "blackmask.operations._atomic_json",
    }[boundary]
    with (
        patch("blackmask.operations.VitMatteSession", StubSession),
        patch(target, side_effect=fail_pointer if boundary == "pointer" else error),
        pytest.raises(error_type) as caught,
    ):
        operations.resume_operation(project, operation_id, model_cache=Path("unused"))
    assert caught.value is error
    assert (project / "state.json").read_bytes() == saved_state
    assert source.read_bytes() == original_source
    assert {p.name: p.read_bytes() for p in export.iterdir() if p.is_file()} == accepted_files
    with patch("blackmask.operations.VitMatteSession", StubSession):
        resumed = operations.resume_operation(project, operation_id, model_cache=Path("unused"))
    assert resumed["status"] == "review_needed"
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    assert export_project(project)["directory"] == str(export)
    assert {p.name: p.read_bytes() for p in export.iterdir() if p.is_file()} == accepted_files


@pytest.mark.parametrize("broken", ["json", "missing", "type"])
def test_unreadable_recovery_record_stays_actionable(tmp_path, broken):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    operation_id = interrupted(project, "_publish_new_directory")
    directory = project / "requests" / operation_id
    if broken == "json":
        (directory / "manifest.json").write_text("{")
    elif broken == "missing":
        (directory / "operation.json").rename(directory / "operation-retained.json")
    else:
        (directory / "completion.json").write_text("null")
    with pytest.raises(ProjectError, match="Invalid recovery record") as caught:
        operations.resume_operation(project, operation_id)
    assert caught.value.__cause__ is not None
