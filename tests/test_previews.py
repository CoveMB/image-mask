"""Synthetic native gallery, acceptance and filesystem preservation contracts."""

import hashlib
import inspect
import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_effects import shading_request
from test_ingest import tiff
from test_library import configuration, inventory
from test_matte_operations import StubSession
from test_operations import edits, request

from blackmask import library, operations
from blackmask.ingest import srgb_profile
from blackmask.project import ProjectError, read_project


def configured(function, *args, config, **kwargs):
    # The initial causal RED exercises the predecessor's real entrypoints too.
    if "storage_config" in inspect.signature(function).parameters:
        kwargs["storage_config"] = config
    return function(*args, **kwargs)


def managed(tmp_path, subject="pattern"):
    config_path, destination = configuration(tmp_path)
    config = library.load_storage_config(config_path)
    library.ensure_library(config)
    pixels = np.full((4, 6, 3), [20001, 30002, 40003], dtype=np.uint16)
    source = tiff(destination / "Inbox/CAMERA.tif", pixels, profile=srgb_profile())
    source.with_suffix(".xmp").write_bytes(b"preserved sidecar")
    project = library.import_photo(
        config, source, subject=subject, development={}, sidecars=(source.with_suffix(".xmp"),)
    )
    name = edits(
        project,
        [
            {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 4]},
            {"id": "fg", "role": "foreground", "shape": "rectangle", "xyxy": [5, 0, 6, 4]},
        ],
    )
    configured(
        operations.apply_operation, project, request(project, guide_edits_file=name), config=config
    )
    return config_path, config, project


def generate(project, config):
    with patch.object(operations, "VitMatteSession", StubSession):
        return configured(
            operations.apply_operation,
            project,
            request(project, kind="matte"),
            config=config,
            model_cache=Path("unused-synthetic"),
        )


def jpeg(config, project):
    return config.destination / "Results Preview" / (project.parent.name + ".jpg")


def marker(path):
    with Image.open(path, formats=["JPEG"]) as image:
        image.load()
        assert image.info["icc_profile"] == srgb_profile()
        assert not image.getexif() and "xmp" not in image.info
        return json.loads(image.info["comment"])


def test_generated_native_result_publishes_one_named_jpeg(tmp_path):
    _, config, project = managed(tmp_path)
    original = (project.parent / "original/CAMERA.tif").read_bytes()
    result = generate(project, config)
    path = jpeg(config, project)
    assert path.is_file(), "complete native generation must publish its gallery JPEG"
    assert list(path.parent.glob("*.jpg")) == [path]
    assert marker(path)["revision"] == result["revision"]
    assert marker(path)["status"] == "Draft"
    assert result["preview_pending"] is False
    assert (
        json.loads((project / "preview.json").read_bytes())["jpeg_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert (project.parent / "original/CAMERA.tif").read_bytes() == original


@pytest.mark.parametrize("extra", [1, 4])
def test_new_import_reserves_jpg_capacity_before_any_mutation(tmp_path, extra):
    config_path, destination = configuration(tmp_path)
    config = library.load_storage_config(config_path)
    library.ensure_library(config)
    source = tiff(destination / "Inbox/CAMERA.tif", profile=srgb_profile())
    limit = os.pathconf(destination / "Results Preview", "PC_NAME_MAX")
    before = inventory(destination)
    with pytest.raises(ProjectError, match="preview|Preview"):
        library.import_photo(config, source, subject="x" * (limit - 4 - 22 + extra), development={})
    assert inventory(destination) == before
    assert not (destination / ".import.lock").exists()


def test_accept_older_keeps_latest_but_demotes_its_footer(tmp_path):
    _, config, project = managed(tmp_path)
    first = generate(project, config)
    configured(operations.accept_revision, project, first["revision"], config=config)
    second = configured(
        operations.apply_operation, project, shading_request(project), config=config
    )
    configured(operations.accept_revision, project, second["revision"], config=config)
    assert marker(jpeg(config, project))["status"] == "Accepted"
    configured(
        operations.restore_revision, project, first["revision"], config=config, replace_drafts=True
    )
    assert marker(jpeg(config, project))["status"] == "Accepted"
    configured(operations.accept_revision, project, first["revision"], config=config)
    state = read_project(project)
    assert state["latest_result_revision"] == second["revision"]
    assert state["accepted_revision"] == first["revision"]
    assert marker(jpeg(config, project))["revision"] == second["revision"]
    assert marker(jpeg(config, project))["status"] == "Draft"


def test_preview_status_and_intact_repair_do_not_write_or_render(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    generate(project, config)
    before = inventory(config.destination)
    with patch.object(previews, "_render_latest", side_effect=AssertionError("unexpected render")):
        assert previews.result_preview_status(project, config)["status"] == "current"
        assert previews.refresh_result_preview(project, config)["status"] == "current"
    assert inventory(config.destination) == before


def test_missing_receipt_repairs_owned_jpeg_without_state_changes(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    generate(project, config)
    receipt = project / "preview.json"
    receipt.rename(project / "retained-receipt.json")
    before = (project / "state.json").read_bytes()
    assert previews.result_preview_status(project, config)["status"] == "pending"
    assert previews.refresh_result_preview(project, config)["status"] == "current"
    assert (project / "state.json").read_bytes() == before


def test_unknown_gallery_collision_preserves_native_completed_result(tmp_path):
    _, config, project = managed(tmp_path)
    path = jpeg(config, project)
    path.write_bytes(b"foreign collision")
    result = generate(project, config)
    assert result["preview_pending"] is True
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert path.read_bytes() == b"foreign collision"
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        configured(operations.accept_revision, project, result["revision"], config=config)
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize(
    "shape,photo_size",
    [
        ((2000, 3200), (1600, 1000)),
        ((3200, 2000), (1000, 1600)),
        ((80, 120), (120, 80)),
        ((9, 1), (1, 9)),
    ],
)
def test_jpeg_photo_rectangle_size_and_external_footer(tmp_path, shape, photo_size):
    from blackmask import previews

    pixels = np.full((*shape, 3), [12345, 23456, 34567], dtype=np.uint16)
    record = {"revision": "rev-001", "status": "Draft"}
    data, layout = previews._encode_preview(pixels, record)
    import io

    with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
        image.load()
        x0, y0, x1, y1 = layout["photo_rectangle_xyxy"]
        assert (x1 - x0, y1 - y0) == photo_size
        assert y1 < image.height and y0 == 0
        assert image.width >= 360 and image.width <= 1600
        assert np.any(np.all(np.array(image)[y1:] > 200, axis=2)), "visible footer glyphs"
        assert image.info["icc_profile"] == srgb_profile()
        assert not image.getexif()


@pytest.mark.parametrize("phase", ["demotion", "promotion"])
@pytest.mark.parametrize("point", ["write", "flush", "file-sync", "rename", "parent-sync"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_acceptance_jpeg_failure_boundaries_preserve_truth(tmp_path, phase, point, when):
    import stat

    from blackmask import previews

    _, config, project = managed(tmp_path)
    first = generate(project, config)
    configured(operations.accept_revision, project, first["revision"], config=config)
    second = configured(
        operations.apply_operation, project, shading_request(project), config=config
    )
    configured(operations.accept_revision, project, second["revision"], config=config)
    configured(
        operations.restore_revision, project, first["revision"], config=config, replace_drafts=True
    )
    prior = (project / "state.json").read_bytes()
    real_publish, real_open, real_sync, real_rename = (
        previews._publish_gallery_bytes,
        os.fdopen,
        os.fsync,
        os.replace,
    )
    active, calls, triggered = None, 0, False

    def fault(selected, function, *args, **kwargs):
        nonlocal triggered
        if active != phase or selected != point or triggered:
            return function(*args, **kwargs)
        triggered = True
        if when == "after":
            function(*args, **kwargs)
        raise OSError(f"{phase}/{point}/{when}")

    def publishing(*args, **kwargs):
        nonlocal active, calls
        calls += 1
        active = "demotion" if calls == 1 else "promotion"
        try:
            return real_publish(*args, **kwargs)
        finally:
            active = None

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def write(self, value):
            return fault("write", self.stream.write, value)

        def flush(self):
            return fault("flush", self.stream.flush)

    def opening(*args, **kwargs):
        stream = real_open(*args, **kwargs)
        return Stream(stream) if active and args[1] == "wb" else stream

    def syncing(descriptor):
        selected = "parent-sync" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file-sync"
        return fault(selected, real_sync, descriptor)

    def renaming(*args, **kwargs):
        return fault("rename", real_rename, *args, **kwargs)

    with (
        patch.object(previews, "_publish_gallery_bytes", side_effect=publishing),
        patch.object(os, "fdopen", side_effect=opening),
        patch.object(os, "fsync", side_effect=syncing),
        patch.object(os, "replace", side_effect=renaming),
    ):
        if phase == "demotion":
            with pytest.raises(ProjectError, match="demotion"):
                operations.accept_revision(project, first["revision"], storage_config=config)
        else:
            result = operations.accept_revision(project, first["revision"], storage_config=config)
            assert result["preview_pending"]
    assert triggered, "failure must hit the intended real filesystem boundary"
    state = read_project(project)
    displayed = marker(jpeg(config, project))
    if phase == "demotion":
        assert (project / "state.json").read_bytes() == prior
    else:
        assert state["accepted_revision"] == first["revision"]
        assert displayed["status"] == "Draft"
    assert displayed["status"] != "Accepted" or displayed["revision"] == state["accepted_revision"]
    assert previews.refresh_result_preview(project, config)["status"] == "current"


@pytest.mark.parametrize("when", ["before", "after", "parent-sync"])
def test_acceptance_state_failure_uses_actual_reread_and_no_promotion(tmp_path, when):
    from blackmask import previews
    from blackmask import project as storage

    _, config, project = managed(tmp_path)
    first = generate(project, config)
    second = configured(
        operations.apply_operation, project, shading_request(project), config=config
    )
    configured(operations.accept_revision, project, second["revision"], config=config)
    configured(
        operations.restore_revision, project, first["revision"], config=config, replace_drafts=True
    )
    real_write, real_sync = operations._atomic_json, storage._sync_directory
    active = False

    def writing(path, value, **kwargs):
        nonlocal active
        if path.name != "state.json":
            return real_write(path, value, **kwargs)
        if when == "before":
            raise OSError("state before replace")
        active = True
        try:
            real_write(path, value, **kwargs)
        finally:
            active = False
        raise OSError("state error after completed replacement")

    def syncing(path):
        if active and path == project and when == "parent-sync":
            raise OSError("state parent sync")
        return real_sync(path)

    with (
        patch.object(operations, "_atomic_json", side_effect=writing),
        patch.object(storage, "_sync_directory", side_effect=syncing),
        pytest.raises((OSError, ProjectError)),
    ):
        operations.accept_revision(project, first["revision"], storage_config=config)
    state = read_project(project)
    assert state["accepted_revision"] == (
        second["revision"] if when == "before" else first["revision"]
    )
    assert marker(jpeg(config, project))["status"] == "Draft"
    assert previews.result_preview_status(project, config)["status"] == "pending"


def test_receipt_failure_after_generation_is_pending_and_native_complete(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    with patch.object(previews, "_atomic_json", side_effect=OSError("receipt failed")):
        result = generate(project, config)
    assert result["preview_pending"]
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert previews.refresh_result_preview(project, config)["status"] == "current"


@pytest.mark.parametrize("multibyte", [False, True])
@pytest.mark.parametrize("extra", [0, 1])
def test_exact_name_capacity_uses_filesystem_bytes(tmp_path, multibyte, extra):
    _, destination = configuration(tmp_path)
    config = library.StorageConfig(destination)
    library.ensure_library(config)
    source = tiff(destination / "Inbox/CAMERA.tif", profile=srgb_profile())
    limit = os.pathconf(destination / "Results Preview", "PC_NAME_MAX")
    ending = "éé" if multibyte else "xxxx"
    assert len(os.fsencode(ending)) == 4
    subject = "x" * (limit - 4 - 22 - 4 + extra) + ending
    before = inventory(destination)
    if extra:
        with pytest.raises(ProjectError, match="preview"):
            library.import_photo(config, source, subject=subject, development={})
        assert inventory(destination) == before
    else:
        project = library.import_photo(config, source, subject=subject, development={})
        assert len(os.fsencode(project.parent.name + ".jpg")) == limit
        assert project.parent.name.endswith(subject)


def test_actual_gallery_parent_limit_is_not_inbox_limit(tmp_path):
    _, destination = configuration(tmp_path)
    config = library.StorageConfig(destination)
    library.ensure_library(config)
    source = tiff(destination / "Inbox/CAMERA.tif", profile=srgb_profile())
    real_limit = library._component_limit
    before = inventory(destination)
    with (
        patch.object(
            library,
            "_component_limit",
            side_effect=lambda p: 80 if p.name == "Results Preview" else real_limit(p),
        ),
        pytest.raises(library.ResultPreviewNameTooLong),
    ):
        library.import_photo(config, source, subject="x" * 60, development={})
    assert inventory(destination) == before


def test_existing_overlong_native_project_is_usable_but_acceptance_stays_unchanged(tmp_path):
    from blackmask import previews

    # Model the previously valid name, without changing any saved schema or identity.
    with patch.object(library, "_check_result_preview_capacity"):
        _, config, project = managed(tmp_path, subject="x" * 233)
    result = generate(project, config)
    assert result["preview_pending"]
    assert result["preview"]["reason"] == "name_too_long"
    before = inventory(config.destination)
    assert previews.refresh_result_preview(project, config)["reason"] == "name_too_long"
    assert operations.operation_status(project, storage_config=config)["preview_pending"]
    with pytest.raises(ProjectError, match="demotion.*preview name"):
        operations.accept_revision(project, result["revision"], storage_config=config)
    assert inventory(config.destination) == before
    assert read_project(project)["accepted_revision"] is None
    duplicate = config.destination / "Inbox/OTHER.tif"
    duplicate.write_bytes((project.parent / "original/CAMERA.tif").read_bytes())
    assert library.import_photo(config, duplicate, subject="short", development={}) == project
    assert duplicate.exists()


def test_missing_wrong_config_and_stale_repair_preserve_saved_work(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    before = inventory(config.destination)
    with pytest.raises(ProjectError, match="config"):
        operations.apply_operation(project, request(project))
    with pytest.raises(ProjectError, match="configured library"):
        operations.apply_operation(
            project, request(project), storage_config=library.StorageConfig(tmp_path / "wrong")
        )
    assert inventory(config.destination) == before
    result = generate(project, config)
    old = {
        "developed_id": result["developed_id"],
        "base_revision": None,
        "inputs_digest": "wrong",
        "authoring_digest": "wrong",
    }
    before = inventory(config.destination)
    with pytest.raises(ProjectError, match="Stale"):
        previews.refresh_result_preview(project, config, expected_identity=old)
    assert inventory(config.destination) == before


@pytest.mark.parametrize("kind", ["symlink", "directory", "fifo", "hardlink"])
def test_gallery_leaf_conflicts_are_preserved_without_false_native_failure(tmp_path, kind):
    _, config, project = managed(tmp_path)
    path = jpeg(config, project)
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside sentinel")
    if kind == "symlink":
        path.symlink_to(outside)
    elif kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        os.link(outside, path)
    before = path.lstat()
    result = generate(project, config)
    assert result["preview_pending"]
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert (path.lstat().st_ino, path.lstat().st_mode) == (before.st_ino, before.st_mode)
    assert outside.read_bytes() == b"outside sentinel"


def test_first_publication_race_cannot_overwrite_arriving_file(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    real = previews._exclusive_rename

    def arriving(source, destination, **kwargs):
        descriptor = os.open(
            str(destination),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=kwargs["destination_directory"],
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"arriving sentinel")
        return real(source, destination, **kwargs)

    with patch.object(previews, "_exclusive_rename", side_effect=arriving):
        result = generate(project, config)
    assert result["preview_pending"]
    assert jpeg(config, project).read_bytes() == b"arriving sentinel"


def test_forged_accepted_receipt_cannot_change_draft_image_or_state(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    result = generate(project, config)
    receipt = json.loads((project / "preview.json").read_bytes())
    receipt["status"] = "Accepted"
    (project / "preview.json").write_text(json.dumps(receipt))
    assert previews.result_preview_status(project, config)["status"] == "pending"
    assert previews.refresh_result_preview(project, config)["status"] == "current"
    assert marker(jpeg(config, project))["status"] == "Draft"
    assert read_project(project)["accepted_revision"] is None
    assert read_project(project)["latest_result_revision"] == result["revision"]


def test_cli_reopen_repair_and_http_keep_actual_gallery_state(tmp_path):
    import threading

    from test_library import command
    from test_viewer import http, perform

    from blackmask.viewer import ReviewServer

    config_path, config, project = managed(tmp_path)
    result = generate(project, config)
    (project / "preview.json").rename(project / "retained-receipt.json")
    before = inventory(config.destination)
    status = command("--config", config_path, "status", project)
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["preview_pending"]
    assert inventory(config.destination) == before
    repaired = command("--config", config_path, "preview", "repair", project)
    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(repaired.stdout)["status"] == "current"
    with ReviewServer(project, storage_config=config) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assert (
                http(server, "/api/action", "POST", {}, Origin="https://foreign.example")[0] == 403
            )
            (project / "preview.json").rename(project / "retained-http-receipt.json")
            before = inventory(config.destination)
            state = json.loads(http(server)[1])
            assert state["preview_pending"]
            assert inventory(config.destination) == before
            response = perform(server, "preview-repair")
            assert response["status"] == "current"
            assert read_project(project)["latest_result_revision"] == result["revision"]
        finally:
            server.shutdown()
            thread.join(3)


def test_cli_repair_and_accept_report_existing_overlong_constraint(tmp_path):
    from test_library import command

    with patch.object(library, "_check_result_preview_capacity"):
        config_path, config, project = managed(tmp_path, subject="x" * 233)
    result = generate(project, config)
    before = inventory(config.destination)
    status = command("--config", config_path, "status", project)
    assert status.returncode == 0
    assert json.loads(status.stdout)["preview"]["reason"] == "name_too_long"
    repair = command("--config", config_path, "preview", "repair", project)
    assert repair.returncode == 1
    assert json.loads(repair.stdout)["reason"] == "name_too_long"
    accepted = command("--config", config_path, "accept", project, "--revision", result["revision"])
    assert accepted.returncode == 1 and "demotion" in accepted.stderr
    assert inventory(config.destination) == before


def test_real_process_lock_blocks_repair_and_accept_without_blocking_reads(tmp_path):
    import subprocess
    import sys

    from test_library import SOURCE_ROOT, command

    config_path, config, project = managed(tmp_path)
    result = generate(project, config)
    code = "from blackmask.project import project_lock; from pathlib import Path; import sys;\nwith project_lock(Path(sys.argv[1])):\n print('locked',flush=True)\n sys.stdin.readline()\n"
    worker = subprocess.Popen(
        [sys.executable, "-B", "-c", code, str(project)],
        env=dict(os.environ, PYTHONPATH=str(SOURCE_ROOT)),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert worker.stdout.readline().strip() == "locked"
        before = inventory(config.destination)
        status = command("--config", config_path, "status", project)
        assert status.returncode == 0 and json.loads(status.stdout)["writer_busy"]
        repaired = command("--config", config_path, "preview", "repair", project)
        assert repaired.returncode == 1 and "busy" in repaired.stderr
        accepted = command(
            "--config", config_path, "accept", project, "--revision", result["revision"]
        )
        assert accepted.returncode == 1 and "busy" in accepted.stderr
        assert inventory(config.destination) == before
    finally:
        output, error = worker.communicate("release\n", timeout=10)
        assert worker.returncode == 0, (output, error)


def test_completed_resume_repairs_without_models_or_new_revision(tmp_path):
    from test_resume import recovery_id

    _, config, project = managed(tmp_path)
    result = generate(project, config)
    operation_id = recovery_id(project)
    jpeg(config, project).rename(project / "retained-gallery.jpg")
    before = (project / "state.json").read_bytes(), inventory(project / "revisions")
    with patch.object(operations, "VitMatteSession", side_effect=AssertionError("model")):
        resumed = operations.resume_operation(project, operation_id, storage_config=config)
    assert resumed["resumed_completed_stage"] and resumed["revision"] == result["revision"]
    assert resumed["preview"]["status"] == "current"
    assert before == ((project / "state.json").read_bytes(), inventory(project / "revisions"))


def test_gallery_ignores_drafts_prepare_restore_and_native_framed_series_exports(tmp_path):
    import tomllib

    import tomli_w

    from blackmask.export import export_project
    from blackmask.framing import Margins, save_framing_preset
    from blackmask.series_framing import SeriesSettings

    _, config, project = managed(tmp_path)
    first = generate(project, config)
    operations.accept_revision(project, first["revision"], storage_config=config)
    path = jpeg(config, project)

    def snapshot():
        return path.read_bytes(), path.stat().st_mtime_ns, (project / "preview.json").read_bytes()

    before = snapshot()
    recipe_path = project / "recipe.toml"
    original = recipe_path.read_bytes()
    recipe = tomllib.loads(recipe_path.read_text())
    recipe["shading"]["opacity"] = 0.42
    recipe_path.write_text(tomli_w.dumps(recipe))
    assert snapshot() == before
    recipe_path.write_bytes(original)
    operations.apply_operation(project, request(project), storage_config=config)
    assert snapshot() == before
    operations.restore_revision(
        project, first["revision"], replace_drafts=True, storage_config=config
    )
    assert snapshot() == before
    save_framing_preset(
        project,
        {"left_px": 2, "right_px": 3, "top_px": 1, "bottom_px": 0},
        expected_digest=None,
        expected_developed_id=read_project(project)["developed_id"],
    )
    for settings in (
        {},
        {"framing": Margins(0, 0, 0, 0).to_dict()},
        {"framing": Margins(2, 3, 1, 0).to_dict()},
        {"series": SeriesSettings("Test", 120, 100, 100, 100).to_dict()},
    ):
        export_project(project, **settings)
        assert snapshot() == before
    assert read_project(project)["latest_result_revision"] == first["revision"]


@pytest.mark.parametrize("failure", ["encode", "rename-before", "rename-after", "receipt"])
def test_native_effect_completion_survives_preview_failure(tmp_path, failure):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    first = generate(project, config)
    operations.accept_revision(project, first["revision"], storage_config=config)
    original_state = read_project(project)
    immutable = inventory(project / "assets"), inventory(project / "revisions")
    real_replace = os.replace
    triggered = False

    def replace(start, end, **kwargs):
        nonlocal triggered
        if str(end).endswith(".jpg"):
            triggered = True
            if failure == "rename-after":
                real_replace(start, end, **kwargs)
            raise OSError("injected JPEG rename")
        return real_replace(start, end, **kwargs)

    target = {"encode": "_encode_preview", "receipt": "_atomic_json"}.get(failure)
    with (
        patch.object(previews, target, side_effect=OSError(failure))
        if target
        else patch("os.replace", side_effect=replace)
    ):
        result = operations.apply_operation(
            project, shading_request(project), storage_config=config
        )
    if failure.startswith("rename"):
        assert triggered
    assert result["preview_pending"] is True
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert read_project(project)["accepted_revision"] == original_state["accepted_revision"]
    assert immutable[0].items() <= inventory(project / "assets").items()
    assert immutable[1].items() <= inventory(project / "revisions").items()
    assert previews.refresh_result_preview(project, config)["status"] == "current"


def test_renderer_matches_independent_native_scalar_composite(tmp_path):
    from test_background import scalar_composite

    from blackmask import previews
    from blackmask.background import read_background
    from blackmask.effects import saved_shading
    from blackmask.export import saved_layers

    _, config, project = managed(tmp_path)
    generate(project, config)
    operations.apply_operation(project, shading_request(project), storage_config=config)
    state = read_project(project)
    foreground, alpha, manifest = saved_layers(
        project, state["latest_result_revision"], state["developed_id"]
    )
    weight, opacity = saved_shading(project, state["latest_result_revision"], alpha, manifest)
    assert np.any(foreground % 257) and np.any((alpha > 0) & (alpha < 65535))
    background = read_background(
        project, project / "revisions" / state["latest_result_revision"], manifest
    )
    expected = scalar_composite(
        foreground,
        alpha,
        np.zeros_like(foreground) if background is None else background,
        weight,
        opacity,
    )
    np.testing.assert_array_equal(previews._render_latest(project, state), expected)


@pytest.mark.parametrize("umask", [0o077, 0o777])
def test_new_gallery_files_are_private_and_readable_under_umask(tmp_path, umask):
    import stat

    from blackmask import previews

    _, config, project = managed(tmp_path)
    generate(project, config)
    (config.destination / "Results Preview").rename(config.destination / "retained-empty-gallery")
    prior = os.umask(umask)
    try:
        result = previews.refresh_result_preview(project, config)
    finally:
        os.umask(prior)
    assert result["status"] == "current"
    assert stat.S_IMODE(jpeg(config, project).stat().st_mode) == 0o600
    assert stat.S_IMODE(jpeg(config, project).parent.stat().st_mode) == 0o700


def test_raw_inputs_changed_during_render_cannot_publish_old_buffer(tmp_path):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    generate(project, config)
    (project / "preview.json").rename(project / "retained-receipt.json")
    original = jpeg(config, project).read_bytes()
    renderer = previews._render_latest

    def changed(*args):
        pixels = renderer(*args)
        state_path = project / "state.json"
        state_path.write_bytes(state_path.read_bytes() + b"\n")
        return pixels

    with patch.object(previews, "_render_latest", side_effect=changed):
        status = previews.refresh_result_preview(project, config)
    assert status["status"] == "pending" and "Stale" in status["error"]
    assert jpeg(config, project).read_bytes() == original


def test_real_paused_preview_writer_blocks_new_generation_then_retry_uses_latest(tmp_path):
    import subprocess
    import sys

    from test_library import SOURCE_ROOT

    config_path, config, project = managed(tmp_path)
    first = generate(project, config)
    (project / "preview.json").rename(project / "retained-receipt.json")
    code = """
import sys
from pathlib import Path
from blackmask import previews,library
real = previews._publish_gallery_bytes
def paused(*args, **kwargs):
    print('ready',flush=True)
    sys.stdin.readline()
    return real(*args, **kwargs)
previews._publish_gallery_bytes = paused
result=previews.refresh_result_preview(Path(sys.argv[1]),library.load_storage_config(Path(sys.argv[2])))
assert result['status']=='current',result
"""
    worker = subprocess.Popen(
        [sys.executable, "-B", "-c", code, str(project), str(config_path)],
        env=dict(os.environ, PYTHONPATH=str(SOURCE_ROOT)),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert worker.stdout.readline().strip() == "ready"
        with pytest.raises(ProjectError, match="busy"):
            operations.apply_operation(project, shading_request(project), storage_config=config)
        assert read_project(project)["latest_result_revision"] == first["revision"]
    finally:
        output, error = worker.communicate("release\n", timeout=15)
        assert worker.returncode == 0, (output, error)
    second = operations.apply_operation(project, shading_request(project), storage_config=config)
    assert marker(jpeg(config, project))["revision"] == second["revision"]
    assert second["revision"] != first["revision"]


def test_failed_and_stale_enabled_native_results_do_not_replace_gallery(tmp_path):
    _, config, project = managed(tmp_path)
    generate(project, config)
    shaded = operations.apply_operation(project, shading_request(project), storage_config=config)
    operations.accept_revision(project, shaded["revision"], storage_config=config)
    path = jpeg(config, project)
    before = path.read_bytes(), path.stat().st_mtime_ns, (project / "preview.json").read_bytes()
    operations.apply_operation(project, request(project), storage_config=config)
    with (
        patch.object(
            operations, "VitMatteSession", side_effect=ProjectError("injected model failure")
        ),
        pytest.raises(ProjectError, match="injected model failure"),
    ):
        operations.apply_operation(
            project,
            request(project, kind="matte"),
            storage_config=config,
            model_cache=Path("unused"),
        )
    with (
        patch.object(operations, "VitMatteSession", StubSession),
        patch.object(
            StubSession,
            "predict",
            side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
        ),
    ):
        result = operations.apply_operation(
            project,
            request(project, kind="matte"),
            storage_config=config,
            model_cache=Path("unused"),
        )
    assert read_project(project)["working_revision"] == result["revision"]
    assert read_project(project)["latest_result_revision"] == shaded["revision"]
    assert before == (
        path.read_bytes(),
        path.stat().st_mtime_ns,
        (project / "preview.json").read_bytes(),
    )


def test_gallery_context_failure_after_native_commit_returns_pending(tmp_path):
    _, config, project = managed(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"outside sentinel")
    before = inventory(outside)
    real = operations._run_matte

    def changed(*args, **kwargs):
        result = real(*args, **kwargs)
        gallery = config.destination / "Results Preview"
        gallery.rename(config.destination / "retained-gallery")
        gallery.symlink_to(outside, target_is_directory=True)
        return result

    with patch.object(operations, "_run_matte", side_effect=changed):
        result = generate(project, config)
    assert result["preview_pending"]
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert "Unsafe" in result["preview"]["error"]
    assert inventory(outside) == before


@pytest.mark.parametrize("older", [False, True])
def test_acceptance_receipt_failure_preserves_actual_pointer_and_truth(tmp_path, older):
    from blackmask import previews

    _, config, project = managed(tmp_path)
    first = generate(project, config)
    if older:
        second = operations.apply_operation(
            project, shading_request(project), storage_config=config
        )
        operations.accept_revision(project, second["revision"], storage_config=config)
        operations.restore_revision(
            project, first["revision"], replace_drafts=True, storage_config=config
        )
    with patch.object(previews, "_atomic_json", side_effect=OSError("injected receipt failure")):
        result = operations.accept_revision(project, first["revision"], storage_config=config)
    assert result["preview_pending"]
    state = read_project(project)
    assert state["accepted_revision"] == first["revision"]
    displayed = marker(jpeg(config, project))
    assert displayed["status"] != "Accepted" or displayed["revision"] == state["accepted_revision"]
    assert previews.refresh_result_preview(project, config)["status"] == "current"


def test_oversized_foreign_jpeg_header_is_pending_without_decode_or_native_failure(tmp_path):
    import io

    from blackmask import previews

    _, config, project = managed(tmp_path)
    output = io.BytesIO()
    Image.new("RGB", (1, 1)).save(output, format="JPEG")
    malformed = bytearray(output.getvalue())
    start = malformed.index(b"\xff\xc0")
    malformed[start + 5 : start + 9] = b"\xff\xff\xff\xff"
    path = jpeg(config, project)
    path.write_bytes(malformed)
    with patch.object(previews, "_render_latest", side_effect=AssertionError("foreign JPEG")):
        result = generate(project, config)
        status = previews.result_preview_status(project, config)
    assert result["preview_pending"] and status["status"] == "pending"
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert "collision preserved" in status["error"]
    assert path.read_bytes() == malformed
