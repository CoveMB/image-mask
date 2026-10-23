import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tomli_w
from test_ingest import ramp, tiff

from blackmask.ingest import srgb_profile
from blackmask.project import (
    ProjectError,
    accept_development,
    create_project,
    load_developed,
    project_lock,
    read_project,
)


def create(tmp_path):
    source = tiff(tmp_path / "capture.tif", profile=srgb_profile())
    project = tmp_path / "project"
    create_project(source, project, {})
    return source, project


def test_create_reopen_and_explicit_identity_approval(tmp_path):
    source, project = create(tmp_path)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    state = read_project(project)
    assert state["development_approved"] is False
    assert state["status"] == "ready"
    assert state["working_revision"] is None and state["accepted_revision"] is None
    assert state["latest_result_revision"] is None
    pixels, metadata = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["source_sha256"] == original
    accept_development(project, state["developed_id"])
    assert read_project(project)["development_approved"] is True
    assert read_project(project)["accepted_revision"] is None
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    with pytest.raises(ProjectError, match="identity"):
        accept_development(project, "0" * 64)


def test_identity_binds_development_not_just_dimensions(tmp_path):
    source, project = create(tmp_path)
    other = tmp_path / "other"
    create_project(source, other, {"assume_srgb": True})
    assert read_project(project)["developed_id"] != read_project(other)["developed_id"]


@pytest.mark.parametrize("status", [[], {}, "accepted"])
def test_invalid_initial_status_is_rejected_without_rewriting_state(tmp_path, status):
    _, project = create(tmp_path)
    state_path = project / "state.json"
    state = json.loads(state_path.read_text())
    state["status"] = status
    state_path.write_text(json.dumps(state))
    before = state_path.read_bytes()
    with pytest.raises(ProjectError, match="Invalid project state"):
        read_project(project)
    assert state_path.read_bytes() == before


def test_source_output_alias_and_symlink_refused(tmp_path):
    source = tiff(tmp_path / "source.tif", profile=srgb_profile())
    with pytest.raises(ProjectError):
        create_project(source, source, {})
    directory = tmp_path / "container"
    directory.mkdir()
    nested = tiff(directory / "capture.tif", profile=srgb_profile())
    with pytest.raises(ProjectError):
        create_project(nested, directory, {})
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(ProjectError):
        create_project(source, alias, {})
    assert nested.exists()


def test_existing_project_never_overwritten(tmp_path):
    source, project = create(tmp_path)
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    with pytest.raises(ProjectError):
        create_project(source, project, {})
    assert before == {
        p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }


def test_tampered_master_and_draft_rejected(tmp_path):
    _, project = create(tmp_path)
    state = read_project(project)
    recipe = project / "recipe.toml"
    import tomllib

    data = tomllib.loads(recipe.read_text())
    data["unexpected"] = True
    recipe.write_text(tomli_w.dumps(data))
    with pytest.raises(ProjectError, match="recipe|unknown"):
        accept_development(project, state["developed_id"])
    del data["unexpected"]
    data["shading"]["enabled"] = "false"
    recipe.write_text(tomli_w.dumps(data))
    with pytest.raises(ProjectError):
        read_project(project)
    data["shading"]["enabled"] = False
    recipe.write_text(tomli_w.dumps(data))
    master = project / "assets/developed" / (state["developed_id"] + ".tif")
    master.write_bytes(b"corrupt")
    with pytest.raises(ProjectError, match="master|hash"):
        load_developed(project, state["developed_id"])
    assert json.loads((project / "state.json").read_text())["development_approved"] is False


def test_managed_symlink_cannot_write_external_state(tmp_path):
    _, project = create(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes((project / "state.json").read_bytes())
    (project / "state.json").unlink()
    (project / "state.json").symlink_to(outside)
    before = outside.read_bytes()
    with pytest.raises(ProjectError):
        read_project(project)
    assert outside.read_bytes() == before


def test_low_disk_prevents_assets(tmp_path):
    source = tiff(tmp_path / "source.tif", profile=srgb_profile())
    project = tmp_path / "project"
    with (
        patch("blackmask.project.shutil.disk_usage", return_value=type("Disk", (), {"free": 1})()),
        pytest.raises(ProjectError, match="space|reserve"),
    ):
        create_project(source, project, {})
    assert not (project / "state.json").exists()
    assert not (project / "assets/developed").exists()


def test_initial_publication_failure_and_recovery(tmp_path):
    source = tiff(tmp_path / "source.tif", profile=srgb_profile())
    project = tmp_path / "project"
    original = os.link

    def fail_state(source, destination, **kwargs):
        if Path(destination).name == "state.json":
            raise OSError("injected publication failure")
        return original(source, destination, **kwargs)

    with (
        patch("blackmask.project.os.link", side_effect=fail_state),
        pytest.raises(OSError, match="injected"),
    ):
        create_project(source, project, {})
    with pytest.raises(ProjectError, match="incomplete"):
        read_project(project)
    create_project(source, tmp_path / "recovered", {})
    np.testing.assert_array_equal(
        load_developed(
            tmp_path / "recovered", read_project(tmp_path / "recovered")["developed_id"]
        )[0],
        ramp(),
    )


def test_approval_failure_preserves_exact_state(tmp_path):
    _, project = create(tmp_path)
    state = read_project(project)
    before = (project / "state.json").read_bytes()
    with (
        patch("blackmask.project.os.replace", side_effect=OSError("injected atomic failure")),
        pytest.raises(OSError),
    ):
        accept_development(project, state["developed_id"])
    assert (project / "state.json").read_bytes() == before
    assert read_project(project)["development_approved"] is False


def test_real_process_lock_busy_and_reads_responsive(tmp_path):
    _, project = create(tmp_path)
    code = "from pathlib import Path; from blackmask.project import project_lock; import sys;\nwith project_lock(Path(sys.argv[1])): print('locked',flush=True); sys.stdin.readline()"
    environment = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(project)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        assert read_project(project)["development_approved"] is False
        with pytest.raises(ProjectError, match="busy"):
            accept_development(project, read_project(project)["developed_id"])
        with pytest.raises(ProjectError, match="busy"), project_lock(project):
            pass
    finally:
        process.communicate("release\n", timeout=10)
    assert process.returncode == 0
    accept_development(project, read_project(project)["developed_id"])


def test_source_mutation_during_ingest_never_publishes(tmp_path):
    from blackmask import project as module

    source = tiff(tmp_path / "source.tif", profile=srgb_profile())
    project = tmp_path / "project"
    original = module.decode_source

    def mutate(data, settings):
        result = original(data, settings)
        source.write_bytes(b"changed outside application")
        return result

    with (
        patch("blackmask.project.decode_source", side_effect=mutate),
        pytest.raises(ProjectError, match="source|stale"),
    ):
        create_project(source, project, {})
    assert not (project / "state.json").exists()


def test_real_process_interruption_never_publishes_incomplete_state(tmp_path):
    source = tiff(tmp_path / "capture.tif", profile=srgb_profile())
    before = source.read_bytes()
    project = tmp_path / "interrupted"
    code = """import os,sys
from pathlib import Path
from blackmask.project import create_project
original = os.link
def pause(source, destination, **kwargs):
    original(source, destination, **kwargs)
    print('published-asset', flush=True)
    sys.stdin.readline()
os.link = pause
create_project(Path(sys.argv[1]), Path(sys.argv[2]), {})
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(source), str(project)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
    )
    try:
        assert process.stdout.readline().strip() == "published-asset"
        process.kill()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert process.returncode < 0
    assert source.read_bytes() == before
    assert not (project / "state.json").exists()
    with pytest.raises(ProjectError, match="incomplete"):
        read_project(project)
    with pytest.raises(ProjectError, match="incomplete"):
        create_project(source, project, {})
    # OS releases a killed writer's lock; no stale lock deletion is required.
    with project_lock(project):
        pass


def test_approval_low_disk_preserves_state(tmp_path):
    _, project = create(tmp_path)
    before = (project / "state.json").read_bytes()
    developed_id = read_project(project)["developed_id"]
    with (
        patch("blackmask.project.shutil.disk_usage", return_value=type("Disk", (), {"free": 1})()),
        pytest.raises(ProjectError, match="space"),
    ):
        accept_development(project, developed_id)
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_wb_rejects_camera_then_creates_daylight_project(tmp_path, invalid):
    from test_ingest import FakeRaw

    from blackmask.ingest import IngestError

    source = tmp_path / "capture.raw"
    source.write_bytes(b"synthetic RAW boundary")
    raw = FakeRaw()
    raw.camera_whitebalance = [invalid, 1, 1.5, 0]
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        with pytest.raises(IngestError, match="white balance"):
            create_project(source, tmp_path / "camera", {})
        project = create_project(source, tmp_path / "daylight", {"white_balance": "daylight"})
    state = read_project(project)
    pixels, metadata = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["camera_whitebalance"][0] is None
    assert metadata["camera_whitebalance_valid"] is False
    assert metadata["development"]["white_balance"] == "daylight"
    assert state["development_approved"] is False


@pytest.mark.parametrize(
    "name", ["recipe.toml", "guides.json", "source.json", "README.md", "state.json"]
)
def test_initial_publication_never_replaces_arriving_file(tmp_path, name):
    from blackmask import project as module

    source = tiff(tmp_path / "capture.tif", profile=srgb_profile())
    project = tmp_path / "project"
    original = module.decode_source
    sentinel = b"USER FILE CREATED DURING DECODE\n"

    def collide(data, settings):
        result = original(data, settings)
        (project / name).write_bytes(sentinel)
        return result

    with (
        patch("blackmask.project.decode_source", side_effect=collide),
        pytest.raises(ProjectError, match="collision|incomplete"),
    ):
        create_project(source, project, {})
    assert (project / name).read_bytes() == sentinel
    if name != "state.json":
        assert not (project / "state.json").exists()
    with pytest.raises(ProjectError):
        read_project(project)


def test_tiff_raw_preview_creates_identity_bound_full_precision_master(tmp_path):
    import io

    from PIL import Image
    from test_ingest import FakeRaw

    buffer = io.BytesIO()
    Image.new("RGB", (7, 4), (10, 20, 30)).save(buffer, format="TIFF")
    source = tmp_path / "misnamed.jpg"
    source.write_bytes(buffer.getvalue())
    original = source.read_bytes()
    raw = FakeRaw()
    raw.camera_whitebalance = [2, 1, 1.5, 0]
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        project = create_project(source, tmp_path / "project", {})
    state = read_project(project)
    pixels, metadata = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["format"] == "RAW"
    assert metadata["source_precision_bits"] is None
    assert metadata["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert state["development_approved"] is False
    assert source.read_bytes() == original


def test_gain_map_jpeg_rejection_never_publishes_project_assets(tmp_path):
    from test_ingest import multi_image_jpeg

    from blackmask.ingest import IngestError

    source = tmp_path / "capture.png"
    original = multi_image_jpeg(gain_map=True)
    source.write_bytes(original)
    project = tmp_path / "project"
    with pytest.raises(IngestError, match="Multi-image JPEG"):
        create_project(source, project, {"assume_srgb": True})
    assert source.read_bytes() == original
    assert not (project / "state.json").exists()
    assert not (project / "assets/developed").exists()
