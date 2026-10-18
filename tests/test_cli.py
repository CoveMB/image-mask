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
    assert report["models"] == "not installed or evaluated in I01"
    assert report["libraw"]


def test_cli_failure_is_actionable(tmp_path):
    result = run("open", "--project", tmp_path / "missing")
    assert result.returncode != 0
    assert "incomplete" in result.stderr or "missing" in result.stderr
    assert "Traceback" not in result.stderr
