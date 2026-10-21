import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
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


def test_series_cli_saved_only_replay_and_exclusive_modes(tmp_path):
    from test_effects import fixture_project

    from blackmask.series_framing import SeriesSettings, portable_series_preset

    project, _, _ = fixture_project(tmp_path)
    preset = tmp_path / "series.json"
    preset.write_bytes(
        portable_series_preset(SeriesSettings(output_width_px=40, output_height_px=50))
    )
    first = run("export", project, "--series-preset", preset, "--framed-transparent")
    assert first.returncode == 0, first.stderr
    output = json.loads(first.stdout)
    assert output["output_dimensions_wh"] == [40, 50]
    (tmp_path / "source.tif").rename(tmp_path / "retained-original.tif")
    preset.write_bytes(preset.read_bytes() + b"\n")
    replay = run("export", project, "--series-preset", preset, "--framed-transparent")
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == output
    conflict = run("export", project, "--series-preset", preset, "--margins", 0, 0, 0, 0)
    assert conflict.returncode == 2
    assert not (project / "series-framing.json").exists()


def test_framed_cli_saved_only_replay_variants_draft_and_busy_lock(tmp_path, monkeypatch):
    import hashlib

    import numpy as np
    import tifffile
    from test_effects import fixture_project, shading_request

    from blackmask import operations
    from blackmask.project import project_lock

    for name in ("BLACKMASK_SAM_CACHE", "BLACKMASK_VITMATTE_CACHE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    native = run("export", project)
    assert native.returncode == 0, native.stderr
    native_directory = Path(json.loads(native.stdout)["directory"])
    native_bytes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in native_directory.iterdir()
    }
    first = run("export", project, "--margins", 2, 1, 3, 0, "--framed-transparent")
    assert first.returncode == 0, first.stderr
    result = json.loads(first.stdout)
    assert result["output_dimensions_wh"] == [9, 7]
    assert result["source_rect_xyxy"] == [2, 3, 8, 7]
    directory = Path(result["directory"])
    pixels = tifffile.imread(directory / "result_rgb16.tif")
    np.testing.assert_array_equal(
        pixels[3:7, 2:8], tifffile.imread(native_directory / "result_rgb16.tif")
    )
    original_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()
    }
    # The original capture is unavailable at its recorded path in the next process.
    (tmp_path / "source.tif").rename(tmp_path / "retained-original.tif")
    replay = run("export", project, "--margins", 2, 1, 3, 0, "--framed-transparent")
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == result
    assert original_hashes == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()
    }
    assert before == (project / "state.json").read_bytes()
    assert native_bytes == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in native_directory.iterdir()
    }
    for args in (
        ("--framed-transparent",),
        ("--margins", -1, 0, 0, 0),
        ("--margins", 32768, 0, 0, 0),
        ("--margins", 1.5, 0, 0, 0),
    ):
        failed = run("export", project, *args)
        assert failed.returncode != 0 and failed.stderr
    with project_lock(project):
        busy = run("export", project, "--margins", 0, 0, 0, 0)
    assert busy.returncode != 0 and "busy" in busy.stderr.lower()
    draft = operations.apply_operation(project, shading_request(project))
    failed = run("export", project, "--revision", draft["revision"], "--margins", 0, 0, 0, 0)
    assert failed.returncode != 0 and "--draft" in failed.stderr
    delivered = run(
        "export", project, "--revision", draft["revision"], "--draft", "--margins", 0, 0, 0, 0
    )
    assert delivered.returncode == 0, delivered.stderr
    record = json.loads(Path(json.loads(delivered.stdout)["manifest_file"]).read_bytes())
    assert record["draft"] is True and record["label"].startswith("DRAFT")


def test_fresh_cli_create_reopen_doctor_accept(tmp_path):
    source = tiff(tmp_path / "source.bin", profile=srgb_profile())
    project = tmp_path / "project"
    opened = run("open", "--headless", source, "--project", project)
    assert opened.returncode == 0, opened.stderr
    state = json.loads(opened.stdout)
    assert state["development_approved"] is False
    assert run("open", "--headless", "--project", project).returncode == 0
    assert (
        run("accept", project, "--development", "--master-id", state["master_id"]).returncode == 0
    )
    reopened = json.loads(run("open", "--headless", "--project", project).stdout)
    assert reopened["development_approved"] is True
    doctor = run("doctor", "--project", project)
    assert doctor.returncode == 0, doctor.stderr
    report = json.loads(doctor.stdout)
    assert report["native_arm64_python312"] is True
    assert report["auto_device"] == "cpu"
    assert report["libraw"]


def test_cli_failure_is_actionable(tmp_path):
    result = run("open", "--headless", "--project", tmp_path / "missing")
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
        [sys.executable, "-m", "blackmask", "open", "--headless", "--project", str(project)],
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


def test_open_defaults_to_viewer_and_explicit_headless_preserves_json(
    tmp_path, monkeypatch, capsys
):
    from test_project import create

    from blackmask import cli, viewer

    _, project = create(tmp_path)
    calls = []
    monkeypatch.setattr(viewer, "open_viewer", lambda *args: calls.append(args))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "blackmask",
            "open",
            "--project",
            str(project),
            "--model-cache",
            "vit-cache",
            "--sam-cache",
            "sam-cache",
        ],
    )
    assert cli.main() == 0
    assert calls == [(project, Path("vit-cache"), Path("sam-cache"))]
    monkeypatch.setattr(sys, "argv", ["blackmask", "open", "--headless", "--project", str(project)])
    assert cli.main() == 0
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["development_approved"] is False


@pytest.mark.parametrize("model,label", [("sam", "SAM"), ("vitmatte", "ViTMatte")])
def test_doctor_missing_cache_hint_names_selected_model(tmp_path, model, label):
    completed = run("doctor", "--project", tmp_path, "--model", model)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["models"] == f"pass --model-cache to verify pinned {label} assets"
