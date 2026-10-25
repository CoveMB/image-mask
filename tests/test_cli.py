import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_ingest import saved_raster, tiff

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


def test_cache_cli_inspect_confirmation_and_busy_writer(tmp_path):
    from test_cache_management import inventory, predictions
    from test_project import create

    from blackmask.project import project_lock

    _, project = create(tmp_path)
    predictions(project)
    before = inventory(project)
    inspected = run("cache", "inspect", project)
    assert inspected.returncode == 0, inspected.stderr
    report = json.loads(inspected.stdout)
    assert report["candidates"] and report["writer_busy"] is False
    assert inventory(project) == before
    assert run("cache", "clear", project).returncode == 2
    stale = run("cache", "clear", project, "--confirm", "0" * 64)
    assert stale.returncode == 1 and "Stale" in stale.stderr
    with project_lock(project):
        busy = run("cache", "inspect", project)
        assert busy.returncode == 0 and json.loads(busy.stdout)["writer_busy"] is True
        refused = run("cache", "clear", project, "--confirm", report["candidate_digest"])
        assert refused.returncode == 1 and "busy" in refused.stderr
    assert inventory(project) == before
    cleared = run("cache", "clear", project, "--confirm", report["candidate_digest"])
    assert cleared.returncode == 0, cleared.stderr
    result = json.loads(cleared.stdout)
    assert result["status"] == "cleared"
    assert result["removed"] == [entry["path"] for entry in report["candidates"]]
    assert inventory(project) == {
        name: value for name, value in before.items() if name not in result["removed"]
    }


def test_cache_cli_forwards_imported_storage_context(tmp_path):
    from test_cache_management import predictions
    from test_library import configuration

    from blackmask import library

    config_file, destination = configuration(tmp_path)
    config = library.load_storage_config(config_file)
    library.ensure_library(config)
    source = tiff(destination / "Inbox/capture.tif", profile=srgb_profile())
    project = library.import_photo(config, source, subject="synthetic", development={})
    predictions(project)
    inspected = run("cache", "inspect", project)
    assert inspected.returncode == 0, inspected.stderr
    report = json.loads(inspected.stdout)
    refused = run("cache", "clear", project, "--confirm", report["candidate_digest"])
    assert refused.returncode == 1 and "--config" in refused.stderr
    cleared = run(
        "--config", config_file, "cache", "clear", project, "--confirm", report["candidate_digest"]
    )
    assert cleared.returncode == 0, cleared.stderr
    assert json.loads(cleared.stdout)["removed"]


def test_cache_cli_real_lock_handshake_and_partial_exit(tmp_path):
    from test_cache_management import inventory, predictions
    from test_project import create

    _, project = create(tmp_path)
    entries = predictions(project)
    report = json.loads(run("cache", "inspect", project).stdout)
    before = inventory(project)
    holder_program = """import sys
from pathlib import Path
from blackmask.project import project_lock
with project_lock(Path(sys.argv[1])):
    print('locked',flush=True)
    sys.stdin.readline()
"""
    with subprocess.Popen(
        [sys.executable, "-B", "-c", holder_program, str(project)],
        env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as holder:
        try:
            assert holder.stdout.readline().strip() == "locked"
            inspected = run("cache", "inspect", project)
            assert inspected.returncode == 0 and json.loads(inspected.stdout)["writer_busy"] is True
            refused = run("cache", "clear", project, "--confirm", report["candidate_digest"])
            assert refused.returncode == 1 and "busy" in refused.stderr
            assert inventory(project) == before
        finally:
            holder.stdin.write("release\n")
            holder.stdin.flush()
            assert holder.wait(timeout=20) == 0
    partial_program = """import os,sys
from blackmask.cli import main
original=os.unlink
removed=[]
def unlink(path,**kwargs):
    if removed: raise OSError('injected second unlink')
    original(path,**kwargs)
    removed.append(path)
os.unlink=unlink
sys.argv=['blackmask','cache','clear',sys.argv[1],'--confirm',sys.argv[2]]
raise SystemExit(main())
"""
    partial = subprocess.run(
        [sys.executable, "-B", "-c", partial_program, str(project), report["candidate_digest"]],
        env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert partial.returncode == 1, partial.stderr
    result = json.loads(partial.stdout)
    assert result["status"] == "partial"
    assert result["removed"] == [str(entries[0].relative_to(project))]
    assert result["removed_logical_bytes"] == len(before[result["removed"][0]][0])
    assert entries[1].read_bytes() == before[str(entries[1].relative_to(project))][0]


def test_requested_delivery_cli_variants_and_presentation_editable(tmp_path):
    from test_effects import fixture_project

    project, _, _ = fixture_project(tmp_path)
    result = run("export", project, "--variant", "editable")
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert (Path(output["directory"]) / "alpha16.png").is_file()
    assert not (Path(output["directory"]) / "transparent_RGBA8_VIEW.png").exists()
    framed = run("export", project, "--margins", 0, 0, 0, 0, "--variant", "editable")
    assert framed.returncode == 0, framed.stderr
    pair = json.loads(framed.stdout)
    assert pair["editable_companion"]["directory"] == output["directory"]
    assert not (Path(pair["directory"]) / "alpha16.png").exists()


def test_series_cli_saved_only_replay_and_exclusive_modes(tmp_path):
    from test_effects import fixture_project

    from blackmask.series_framing import SeriesSettings, portable_series_preset

    project, _, _ = fixture_project(tmp_path)
    preset = tmp_path / "series.json"
    saved_raster(preset).write_bytes(
        portable_series_preset(SeriesSettings(output_width_px=40, output_height_px=50))
    )
    first = run("export", project, "--series-preset", preset, "--framed-transparent")
    assert first.returncode == 0, first.stderr
    output = json.loads(first.stdout)
    assert output["output_dimensions_wh"] == [40, 50]
    (saved_raster(tmp_path / "source.tif")).rename(tmp_path / "retained-original.tif")
    saved_raster(preset).write_bytes(saved_raster(preset).read_bytes() + b"\n")
    replay = run("export", project, "--series-preset", preset, "--framed-transparent")
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == {**output, "reused": True}
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
        path.name: hashlib.sha256(saved_raster(path).read_bytes()).hexdigest()
        for path in native_directory.iterdir()
    }
    first = run("export", project, "--margins", 2, 1, 3, 0, "--framed-transparent")
    assert first.returncode == 0, first.stderr
    result = json.loads(first.stdout)
    assert result["output_dimensions_wh"] == [9, 7]
    assert result["source_rect_xyxy"] == [2, 3, 8, 7]
    directory = Path(result["directory"])
    pixels = tifffile.imread(saved_raster(directory / "result_rgb16.tif"))
    np.testing.assert_array_equal(
        pixels[3:7, 2:8], tifffile.imread(saved_raster(native_directory / "result_rgb16.tif"))
    )
    original_hashes = {
        path.name: hashlib.sha256(saved_raster(path).read_bytes()).hexdigest()
        for path in directory.iterdir()
    }
    # The original capture is unavailable at its recorded path in the next process.
    (saved_raster(tmp_path / "source.tif")).rename(tmp_path / "retained-original.tif")
    replay = run("export", project, "--margins", 2, 1, 3, 0, "--framed-transparent")
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == {**result, "reused": True}
    assert original_hashes == {
        path.name: hashlib.sha256(saved_raster(path).read_bytes()).hexdigest()
        for path in directory.iterdir()
    }
    assert before == (project / "state.json").read_bytes()
    assert native_bytes == {
        path.name: hashlib.sha256(saved_raster(path).read_bytes()).hexdigest()
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
    record = json.loads(
        saved_raster(Path(json.loads(delivered.stdout)["manifest_file"])).read_bytes()
    )
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
        run("accept", project, "--development", "--developed-id", state["developed_id"]).returncode
        == 0
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
    accept_development(project, state["developed_id"])
    request = project / "prepare.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "prepare",
                "developed_id": state["developed_id"],
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
    assert saved_raster(Path(result["trimap_file"])).is_file() and result["revision"] == "rev-001"
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
        "--developed-id",
        result["developed_id"],
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

    def opened_window(*args, storage_config=None):
        assert storage_config is None
        calls.append(args)

    monkeypatch.setattr(viewer, "open_viewer", opened_window)
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


def test_comparison_cli_explicit_retention_presentation_reuse_and_missing_native(tmp_path):
    from test_effects import fixture_project
    from test_framing import margins

    from blackmask.project import digest, read_project

    project, _, revision = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    crops_file = tmp_path / "crops.json"
    crops_file.write_text("[[1,0,6,4]]")
    plain = run("review", project, "--crops", crops_file)
    assert plain.returncode == 0, plain.stderr
    assert "manifest_file" in json.loads(plain.stdout)
    presentation = tmp_path / "presentation.json"
    presentation.write_text(
        json.dumps(
            {
                "mode": "add-margins",
                "revision": revision["revision"],
                "developed_id": read_project(project)["developed_id"],
                "revision_manifest_sha256": digest(
                    (project / "revisions" / revision["revision"] / "manifest.json").read_bytes()
                ),
                "margins": margins(),
            }
        )
    )
    arguments = (
        "review",
        project,
        "--comparison",
        "--retain-native",
        "--presentation",
        presentation,
        "--crops",
        crops_file,
    )
    first = run(*arguments)
    assert first.returncode == 0, first.stderr
    output = json.loads(first.stdout)
    assert (
        json.loads(Path(output["comparison_manifest_file"]).read_bytes())["presentation"]["mode"]
        == "add-margins"
    )
    replay = run(*arguments)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == {**output, "reused": True}
    native = Path(output["native_manifest_file"]).parent
    native.rename(tmp_path / "preserved-native")
    failed = run(*arguments)
    assert failed.returncode == 1
    assert (
        str(native) in failed.stderr
        and output["comparison_manifest_file"].rsplit("/", 1)[0] in failed.stderr
    )
    assert not native.exists()
    assert run("review", project, "--retain-native").returncode == 1
    assert (project / "state.json").read_bytes() == before
