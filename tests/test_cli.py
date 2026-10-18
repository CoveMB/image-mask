import json
import os
import subprocess
import sys
from pathlib import Path

from test_ingest import tiff

from blackmask.ingest import srgb_profile


def run(*arguments):
    return subprocess.run(
        [sys.executable, "-m", "blackmask", *map(str, arguments)],
        env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_fresh_cli_create_reopen_doctor_accept(tmp_path):
    source = tiff(tmp_path / "source.bin", profile=srgb_profile())
    project = tmp_path / "project"
    opened = run("open", source, "--project", project)
    assert opened.returncode == 0, opened.stderr
    state = json.loads(opened.stdout)
    assert state["development_approved"] is False
    assert run("open", "--project", project).returncode == 0
    assert (
        run("accept", project, "--development", "--master-id", state["master_id"]).returncode == 0
    )
    reopened = json.loads(run("open", "--project", project).stdout)
    assert reopened["development_approved"] is True
    doctor = run("doctor", "--project", project)
    assert doctor.returncode == 0, doctor.stderr
    report = json.loads(doctor.stdout)
    assert report["native_arm64_python312"] is True
    assert report["auto_device"] == "cpu"
    assert report["libraw"]


def test_cli_failure_is_actionable(tmp_path):
    result = run("open", "--project", tmp_path / "missing")
    assert result.returncode != 0
    assert "incomplete" in result.stderr or "missing" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_prepare_returns_paths_and_rejects_final_acceptance(tmp_path):
    from test_project import create

    from blackmask.operations import draft_digest
    from blackmask.project import accept_development, read_project

    _, project = create(tmp_path)
    state = read_project(project)
    accept_development(project, state["master_id"])
    request = project / "prepare.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "prepare",
                "master_id": state["master_id"],
                "base_revision": None,
                "inputs_digest": draft_digest(project),
            }
        )
    )
    completed = subprocess.run(
        [sys.executable, "-m", "blackmask", "run", str(project), "--request", str(request)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert Path(result["trimap_file"]).is_file() and result["revision"] == "rev-001"
    reopened = subprocess.run(
        [sys.executable, "-m", "blackmask", "open", "--project", str(project)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert (
        reopened.returncode == 0
        and json.loads(reopened.stdout)["inputs_digest"] == result["inputs_digest"]
    )
    rejected = subprocess.run(
        [sys.executable, "-m", "blackmask", "accept", str(project), "--revision", "rev-001"],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert rejected.returncode == 1 and "prepared" in rejected.stderr


def test_cli_recorded_known_only_journey_and_explicit_review_controls(tmp_path):
    from test_matte_operations import prepared
    from test_operations import edits, request

    from blackmask.operations import apply_operation

    _, project, _ = prepared(tmp_path)
    name = edits(
        project,
        [
            {"id": "allbg", "role": "background", "shape": "rectangle", "xyxy": [1, 0, 3, 1]},
            {"id": "lower", "role": "foreground", "shape": "rectangle", "xyxy": [0, 1, 2, 2]},
        ],
    )
    result = apply_operation(project, request(project, guide_edits_file=name))
    approved = run(
        "accept",
        project,
        "--trimap",
        "--revision",
        result["revision"],
        "--master-id",
        result["master_id"],
        "--inputs-digest",
        result["inputs_digest"],
    )
    assert approved.returncode == 0, approved.stderr
    operation = request(project, kind="matte")
    filename = project / "matte.json"
    filename.write_text(json.dumps(operation))
    completed = run("run", project, "--request", filename)
    assert completed.returncode == 0, completed.stderr
    candidate = json.loads(completed.stdout)
    reviewed = run("review", project, "--revision", candidate["revision"])
    assert reviewed.returncode == 0, reviewed.stderr
    final = run("accept", project, "--revision", candidate["revision"])
    assert final.returncode == 0, final.stderr
    exported = run("export", project)
    assert exported.returncode == 0, exported.stderr
    assert Path(json.loads(exported.stdout)["directory"]).is_dir()
