"""Only test-owned synthetic disposable predictions are removed by these cases."""

import json
import os
import stat
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from test_matte import cache_identity
from test_matte_operations import prepared, run_matte
from test_operations import request
from test_project import create

from blackmask import operations
from blackmask.matte import native_matte
from blackmask.project import ProjectError, read_project


def predictions(project, count=2):
    cache = project / "cache/matte"
    for index in range(count):
        pixels = np.full((3, 4, 3), index, dtype=np.uint8)
        native_matte(
            pixels,
            np.full((3, 4), 128, dtype=np.uint8),
            lambda *args: (np.full((3, 4), 0.25), {}),
            "cpu",
            cache_dir=cache,
            cache_identity=cache_identity(),
        )
    return sorted(cache.glob("*.npz"))


def inventory(project):
    return {
        str(path.relative_to(project)): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in project.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def test_clear_mixed_compression_removes_only_supported_predictions(tmp_path):
    import io
    import zipfile

    _, project = create(tmp_path)
    entries = predictions(project, count=4)
    for entry, method in zip(entries, (0, 8, 12, 14)):
        output = io.BytesIO()
        with (
            zipfile.ZipFile(entry) as source,
            zipfile.ZipFile(output, "w", compression=method) as target,
        ):
            for name in source.namelist():
                target.writestr(name, source.read(name))
        entry.write_bytes(output.getvalue())
    diagnostic = project / "cache/matte/.tile-retained-diagnostic"
    diagnostic.write_bytes(b"preserved diagnostic")
    outside = tmp_path / "outside-sentinel"
    outside.write_bytes(b"outside project")
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    eligible = {str(entry.relative_to(project)) for entry in entries[:2]}
    protected = {str(entry.relative_to(project)) for entry in entries[2:]}
    assert {item["path"] for item in report["candidates"]} == eligible
    assert protected <= {item["path"] for item in report["protected"]}
    assert not report["blockers"]
    cleared = operations.clear_processing_cache(project, report["candidate_digest"])
    assert set(cleared["removed"]) == eligible
    assert inventory(project) == {
        name: value for name, value in before.items() if name not in eligible
    }
    assert outside.read_bytes() == b"outside project"


def terminal_authoring(project, viewer, cycle):
    from test_assisted_review import cycle_request, start

    from blackmask import review

    matte = run_matte(project)
    pending = None
    if viewer != "none":
        pending = operations.save_guidance_draft(
            project,
            request(project),
            [],
            [
                {
                    "action": "upsert",
                    "region": {
                        "id": "viewer",
                        "role": "background",
                        "shape": "point",
                        "xy": [2, 1],
                    },
                }
            ],
        )
        if viewer == "consumed":
            prepared_result = operations.prepare_guidance_draft(
                project, request(project), [0, 0, 3, 2]
            )
            assert operations.pending_guidance(project)["consumed"] is True
            manifest = json.loads(
                (project / "revisions" / prepared_result["revision"] / "manifest.json").read_bytes()
            )
            assert pending["guide_edits_file"] in manifest["external_inputs"]
            run_matte(project)
        else:
            previous = (project / "viewer-draft.json").read_bytes()
            restored = operations.restore_revision(project, matte["revision"], replace_drafts=True)
            assert (
                Path(restored["recovery_directory"]) / "viewer-draft.json"
            ).read_bytes() == previous
            status = operations.pending_guidance(project)
            assert status["consumed"] is False and status["current"] is False
            assert status["superseded_by_restore"] is True
    stopped = None
    if cycle:
        started = start(project)
        stopped = review.review_cycle(
            project,
            cycle_request(
                project, "stop", cycle_id=started["cycle_id"], reason="Synthetic explicit stop"
            ),
        )
        assert review._cycle_record(project, stopped["cycle_id"])["phase"] == "stopped"
    return pending, stopped


@pytest.mark.parametrize(
    "viewer,cycle",
    [
        ("consumed", False),
        ("consumed", True),
        ("restored", False),
        ("restored", True),
        ("none", True),
    ],
)
def test_clear_terminal_authoring_histories_preserves_records(tmp_path, viewer, cycle):
    _, project, _ = prepared(tmp_path)
    terminal_authoring(project, viewer, cycle)
    predictions(project)
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"] == []
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    assert result["status"] == "cleared"
    assert inventory(project) == {
        name: data for name, data in before.items() if name not in result["removed"]
    }
    if viewer != "none":
        status = operations.pending_guidance(project)
        assert status["consumed"] is (viewer == "consumed")
        assert status["current"] is False


@pytest.mark.parametrize(
    "damage", ["pending", "ready", "record", "binding", "supersession", "terminal", "anchor"]
)
def test_clear_unresolved_or_tampered_authoring_refuses(tmp_path, damage):
    from test_assisted_review import start

    _, project, _ = prepared(tmp_path)
    pending, stopped = terminal_authoring(
        project, "restored" if damage == "supersession" else "consumed", True
    )
    if damage == "pending":
        operations.save_guidance_draft(
            project,
            request(project),
            [],
            [
                {
                    "action": "upsert",
                    "region": {"id": "later", "role": "unknown", "shape": "point", "xy": [1, 1]},
                }
            ],
        )
    elif damage == "ready":
        start(project)
    elif damage == "record":
        (project / pending["record_file"]).write_text("{}")
    elif damage == "binding":
        for path in (project / "revisions").glob("rev-*/manifest.json"):
            value = json.loads(path.read_bytes())
            if pending["guide_edits_file"] in value.get("external_inputs", {}):
                value["external_inputs"][pending["guide_edits_file"]] = "0" * 64
                path.write_text(json.dumps(value))
    elif damage == "supersession":
        pointer = json.loads((project / "viewer-draft.json").read_bytes())
        pointer["superseded_by_restore"] = "yes"
        (project / "viewer-draft.json").write_text(json.dumps(pointer))
    elif damage == "terminal":
        path = max((project / "requests" / stopped["cycle_id"]).glob("*.json"))
        path.write_text("{}")
    else:
        (project / "requests" / stopped["cycle_id"] / "head.sha256").rename(
            project / "retained-anchor"
        )
    predictions(project)
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(project) == before


def test_restore_backup_before_publication_does_not_retire_pending_authoring(tmp_path, monkeypatch):
    _, project, _ = prepared(tmp_path)
    matte = run_matte(project)
    actions = [
        {
            "action": "upsert",
            "region": {"id": "pending", "role": "background", "shape": "point", "xy": [2, 1]},
        }
    ]
    operations.save_guidance_draft(project, request(project), [], actions)
    pointer = (project / "viewer-draft.json").read_bytes()
    atomic_bytes = operations._atomic_bytes

    def interrupt_before_draft(path, data, **kwargs):
        if path == project / "recipe.toml":
            raise OSError("injected before first restore replacement")
        return atomic_bytes(path, data, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(operations, "_atomic_bytes", interrupt_before_draft)
        with pytest.raises(OSError, match="first restore replacement"):
            operations.restore_revision(project, matte["revision"], replace_drafts=True)
    backups = list((project / "recovery").glob("restore-*/viewer-draft.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == pointer
    pending = operations.pending_guidance(project)
    assert pending["current"] is True and pending["consumed"] is False
    assert pending["actions"] == actions
    predictions(project)
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(project) == before


@pytest.mark.parametrize("interrupted", [True, False])
def test_repeated_actions_require_distinct_completed_authoring(tmp_path, monkeypatch, interrupted):
    _, project, _ = prepared(tmp_path)
    first, _ = terminal_authoring(project, "consumed", False)
    record = json.loads((project / first["record_file"]).read_bytes())
    previous_records = set((project / "requests").glob("viewer-*.json"))
    atomic_json = operations._atomic_json

    def interrupt_edits(path, value, **kwargs):
        if path.name.startswith("viewer-edits-"):
            raise OSError("injected before repeated edits publication")
        return atomic_json(path, value, **kwargs)

    if interrupted:
        with monkeypatch.context() as scoped:
            scoped.setattr(operations, "_atomic_json", interrupt_edits)
            with pytest.raises(OSError, match="repeated edits publication"):
                operations.save_guidance_draft(
                    project, request(project), record["groups"], record["actions"]
                )
        added = set((project / "requests").glob("viewer-*.json")) - previous_records
        assert len(added) == 1 and not next(iter(added)).name.startswith("viewer-edits-")
        assert operations.pending_guidance(project)["consumed"] is True
    else:
        second = operations.save_guidance_draft(
            project, request(project), record["groups"], record["actions"]
        )
        assert second["record_file"] != first["record_file"]
        operations.prepare_guidance_draft(project, request(project), [0, 0, 3, 2])
        assert operations.pending_guidance(project)["consumed"] is True
    predictions(project)
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"]
    if interrupted:
        assert report["blockers"]
        with pytest.raises(ProjectError):
            operations.clear_processing_cache(project, report["candidate_digest"])
        assert inventory(project) == before
    else:
        assert report["blockers"] == []
        result = operations.clear_processing_cache(project, report["candidate_digest"])
        assert result["removed"]
        assert inventory(project) == {
            name: data for name, data in before.items() if name not in result["removed"]
        }


def test_inspection_without_cache_or_lock_is_read_only(tmp_path):
    _, project = create(tmp_path)
    lock = project / ".writer.lock"
    if lock.exists():
        lock.rename(project / "retained-writer-lock")
    before = inventory(project)
    first = operations.inspect_processing_cache(project)
    assert first == operations.inspect_processing_cache(project)
    assert first["candidates"] == [] and first["blockers"] == []
    assert not lock.exists() and not (project / "cache").exists()
    assert inventory(project) == before


def test_clear_exact_candidates_preserves_unknowns_and_multiple_links(tmp_path):
    _, project = create(tmp_path)
    entries = predictions(project, 3)
    os.link(entries[0], entries[0].parent / ".tile-old")
    (entries[0].parent / "unknown.npz").write_bytes(b"preserve unknown")
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["blockers"] == []
    names = [str(p.relative_to(project)) for p in entries[1:]]
    assert [entry["path"] for entry in report["candidates"]] == names
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    assert result["status"] == "cleared" and result["removed"] == names
    assert result["removed_logical_bytes"] == sum(len(before[name][0]) for name in names)
    assert inventory(project) == {
        name: value for name, value in before.items() if name not in names
    }


@pytest.mark.parametrize("change", ["wrong", "link", "replace", "draft"])
def test_stale_confirmation_removes_nothing(tmp_path, change):
    _, project = create(tmp_path)
    entries = predictions(project)
    report = operations.inspect_processing_cache(project)
    if change == "link":
        os.link(entries[0], tmp_path / "outside-link")
    elif change == "replace":
        original = entries[0].read_bytes()
        entries[0].rename(entries[0].with_suffix(".retained"))
        entries[0].write_bytes(original)
    elif change == "draft":
        with (project / "recipe.toml").open("a") as stream:
            stream.write("\n# later draft\n")
    before = inventory(project)
    with pytest.raises(ProjectError, match="[Ss]tale|[Cc]onfirm|[Dd]igest"):
        operations.clear_processing_cache(
            project, "0" * 64 if change == "wrong" else report["candidate_digest"]
        )
    assert inventory(project) == before


@pytest.mark.parametrize("failure", ["unlink", "sync"])
def test_partial_clear_reports_only_actual_unlinks(tmp_path, monkeypatch, failure):
    _, project = create(tmp_path)
    entries = predictions(project)
    report = operations.inspect_processing_cache(project)
    before = inventory(project)
    unlink = os.unlink
    removed = []

    def remove(path, **kwargs):
        if failure == "unlink" and removed:
            raise OSError("injected second unlink")
        unlink(path, **kwargs)
        removed.append(path)

    monkeypatch.setattr(os, "unlink", remove)
    if failure == "sync":
        monkeypatch.setattr(
            os, "fsync", lambda *args: (_ for _ in ()).throw(OSError("injected sync"))
        )
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    expected = [
        str(path.relative_to(project)) for path in (entries[:1] if failure == "unlink" else entries)
    ]
    assert result["status"] == "partial" and result["failures"]
    assert result["removed"] == expected
    assert result["removed_logical_bytes"] == sum(len(before[name][0]) for name in expected)
    assert result["durability_uncertain"] is (failure == "sync")
    assert inventory(project) == {
        name: data for name, data in before.items() if name not in expected
    }


def test_completed_old_processing_and_restore_allow_clear(tmp_path):
    _, project, initial = prepared(tmp_path)
    completed = run_matte(project)
    operations.apply_operation(project, request(project))
    with (project / "recipe.toml").open("a") as stream:
        stream.write("\n# valid later draft\n")
    operations.restore_revision(project, initial["revision"], replace_drafts=True)
    predictions(project)
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["blockers"] == [] and report["candidates"]
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    assert result["status"] == "cleared"
    assert inventory(project) == {
        name: data for name, data in before.items() if name not in result["removed"]
    }
    assert (project / "requests" / completed["operation_id"] / "completion.json").exists()


def test_external_request_unavailable_then_clear_and_native_recompute(tmp_path, monkeypatch):
    from PIL import Image
    from test_ingest import saved_raster
    from test_matte_operations import StubSession

    _, project, initial = prepared(tmp_path)
    operation = request(project, kind="matte")
    external = tmp_path / "external-request.json"
    external.write_text(json.dumps(operation))
    calls = []

    class CountingPrediction(StubSession):
        identity: ClassVar[dict] = {
            name: value for name, value in cache_identity().items() if name != "developed_id"
        }

        def predict(self, pixels, trimap, device):
            calls.append(tuple(trimap.shape))
            return super().predict(pixels, trimap, device)

    monkeypatch.setattr(operations, "VitMatteSession", CountingPrediction)
    first = operations.apply_operation(
        project, operation, model_cache=tmp_path / "absent-models", request_file=external
    )
    assert len(calls) == 1
    original_request = external.read_bytes()
    retained_external = tmp_path / "retained-external-request.json"
    external.rename(retained_external)
    assert not external.exists() and retained_external.read_bytes() == original_request
    manifest = json.loads(
        (project / "requests" / first["operation_id"] / "manifest.json").read_bytes()
    )
    assert manifest["request_file"] == str(external)
    operations.restore_revision(project, initial["revision"], replace_drafts=True)
    before = inventory(project)
    inspected = operations.inspect_processing_cache(project)
    assert inspected["candidates"] and inspected["blockers"] == []
    old_keys = [entry["path"] for entry in inspected["candidates"]]
    cleared = operations.clear_processing_cache(project, inspected["candidate_digest"])
    assert cleared["status"] == "cleared" and cleared["removed"] == old_keys
    assert inventory(project) == {
        name: value for name, value in before.items() if name not in old_keys
    }
    assert all(not (project / name).exists() for name in old_keys)
    second = operations.apply_operation(
        project, request(project, kind="matte"), model_cache=tmp_path / "absent-models"
    )
    assert len(calls) == 2 and second["revision"] != first["revision"]
    after = operations.inspect_processing_cache(project)
    assert after["blockers"] == []
    assert [entry["path"] for entry in after["candidates"]] == old_keys
    with Image.open(
        saved_raster(project / "revisions" / second["revision"] / "base_alpha16.png")
    ) as image:
        alpha = np.array(image)
    assert alpha.dtype == np.uint16
    assert alpha[0, 0] == 65535 and alpha[1, 2] == 0 and alpha[0, 1] == 16384
    assert retained_external.read_bytes() == original_request


def test_noncurrent_asset_reference_blocks_cold_and_warm_clear(tmp_path):
    from test_cli import run

    _, project, old = prepared(tmp_path)
    current = operations.apply_operation(project, request(project))
    assert old["revision"] == "rev-001" and current["revision"] == "rev-002"
    assert not (project / "requests").exists()
    entries = predictions(project)
    assert operations.inspect_processing_cache(project)["blockers"] == []
    old_manifest = project / "revisions" / old["revision"] / "manifest.json"
    manifest = json.loads(old_manifest.read_bytes())
    assert manifest["assets"]
    next(iter(manifest["assets"].values()))["path"] = str(entries[0].relative_to(project))
    old_manifest.write_text(json.dumps(manifest))
    assert read_project(project)["working_revision"] == current["revision"]
    before = inventory(project)
    cold = run("cache", "inspect", project)
    assert cold.returncode == 0, cold.stderr
    assert json.loads(cold.stdout)["blockers"]
    warm = operations.inspect_processing_cache(project)
    assert warm["candidates"] and warm["blockers"]
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(project, warm["candidate_digest"])
    assert inventory(project) == before


@pytest.mark.parametrize(
    "changed", ["progress", "completion", "snapshot", "unknown", "recovery", "historical_asset"]
)
def test_uncertain_history_blocks_with_nonempty_candidates(tmp_path, changed):
    _, project, initial = prepared(tmp_path)
    completed = run_matte(project)
    entries = predictions(project)
    directory = project / "requests" / completed["operation_id"]
    if changed in {"progress", "completion"}:
        (directory / f"{changed}.json").write_text("{}")
    elif changed == "snapshot":
        (directory / "inputs/state.json").write_text("{}")
    elif changed == "unknown":
        (project / "requests/unknown.json").write_text("{}")
    elif changed == "recovery":
        (project / "recovery/restore-incomplete").mkdir(parents=True)
    else:
        path = project / "revisions" / initial["revision"] / "manifest.json"
        value = json.loads(path.read_bytes())
        assert value["assets"]
        next(iter(value["assets"].values()))["path"] = str(entries[0].relative_to(project))
        path.write_text(json.dumps(value))
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(project) == before


@pytest.mark.parametrize("change", ["request", "recovery", "permanent", "none"])
def test_clear_late_context_change_reports_partial_result(tmp_path, monkeypatch, change):
    _, project, initial = prepared(tmp_path)
    run_matte(project)
    entries = predictions(project)
    report = operations.inspect_processing_cache(project)
    assert report["blockers"] == [] and len(report["candidates"]) == 2
    first_size = entries[0].stat().st_size
    second = (entries[1].read_bytes(), entries[1].stat().st_ino)
    unlink = os.unlink
    calls = []

    def remove(path, **kwargs):
        unlink(path, **kwargs)
        calls.append(path)
        if len(calls) != 1:
            return
        if change == "request":
            saved = {
                name: (project / name).read_bytes()
                for name in ("state.json", "source.json", "recipe.toml", "guides.json")
            }
            parent = project / "revisions" / initial["revision"] / "manifest.json"
            operations._save_matte_request(
                project,
                request(project, kind="matte"),
                saved,
                {str(parent.relative_to(project)): operations.digest(parent.read_bytes())},
                None,
                None,
            )
        elif change == "recovery":
            (project / "recovery/restore-interrupted").mkdir(parents=True)
        elif change == "permanent":
            path = project / "revisions" / initial["revision"] / "manifest.json"
            value = json.loads(path.read_bytes())
            assert value["assets"]
            next(iter(value["assets"].values()))["path"] = str(entries[1].relative_to(project))
            path.write_text(json.dumps(value))

    monkeypatch.setattr(os, "unlink", remove)
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    if change == "none":
        assert result["status"] == "cleared" and len(result["removed"]) == 2
    else:
        assert result["status"] == "partial"
        assert result["removed"] == [str(entries[0].relative_to(project))]
        assert result["removed_logical_bytes"] == first_size
        assert (entries[1].read_bytes(), entries[1].stat().st_ino) == second
        assert result["failures"]


@pytest.mark.parametrize("context", ["missing", "wrong", "matching"])
def test_imported_clear_requires_matching_public_storage_context(tmp_path, context):
    from test_ingest import ramp, tiff

    from blackmask import library

    config = library.StorageConfig(tmp_path / "library")
    library.ensure_library(config)
    original = config.destination / "Inbox/synthetic.tif"
    from blackmask.ingest import srgb_profile

    tiff(original, ramp(), profile=srgb_profile())
    project = library.import_photo(config, original, subject="synthetic", development={})
    predictions(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and not report["blockers"]
    wrong = library.StorageConfig(tmp_path / "other-library")
    library.ensure_library(wrong)
    before = inventory(tmp_path)
    if context == "matching":
        result = operations.clear_processing_cache(
            project, report["candidate_digest"], storage_config=config
        )
        assert result["status"] == "cleared" and result["removed"]
    else:
        with pytest.raises(ProjectError, match="config|configured"):
            operations.clear_processing_cache(
                project,
                report["candidate_digest"],
                storage_config=None if context == "missing" else wrong,
            )
        assert inventory(tmp_path) == before


@pytest.mark.parametrize("component", ["cache", "matte", "prediction"])
def test_cache_symlinks_never_follow_or_remove_targets(tmp_path, component):
    _, project = create(tmp_path)
    entries = predictions(project)
    path = {"cache": project / "cache", "matte": project / "cache/matte", "prediction": entries[0]}[
        component
    ]
    retained = tmp_path / "outside-preserved"
    path.rename(retained)
    path.symlink_to(retained, target_is_directory=component != "prediction")
    before = inventory(tmp_path)
    report = operations.inspect_processing_cache(project)
    if component == "prediction":
        assert str(path.relative_to(project)) in [entry["path"] for entry in report["protected"]]
        assert str(path.relative_to(project)) not in [
            entry["path"] for entry in report["candidates"]
        ]
    else:
        assert report["blockers"]
        with pytest.raises(ProjectError):
            operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(tmp_path) == before


def test_cache_directory_replacement_invalidates_confirmation(tmp_path):
    _, project = create(tmp_path)
    entries = predictions(project)
    report = operations.inspect_processing_cache(project)
    cache = project / "cache/matte"
    retained = project / "cache/retained-directory"
    cache.rename(retained)
    cache.mkdir()
    for path in entries:
        (retained / path.name).rename(cache / path.name)
    before = inventory(project)
    with pytest.raises(ProjectError, match="[Ss]tale|[Cc]hanged"):
        operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(project) == before


def test_late_external_link_blocks_before_first_unlink(tmp_path, monkeypatch):
    _, project = create(tmp_path)
    entries = predictions(project)
    report = operations.inspect_processing_cache(project)
    recheck = operations._recheck_cache_context
    calls = []

    def change(project, expected):
        recheck(project, expected)
        if not calls:
            os.link(entries[0], tmp_path / "external-link")
        calls.append(True)

    monkeypatch.setattr(operations, "_recheck_cache_context", change)
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    assert result["status"] == "partial" and result["removed"] == []
    assert entries[0].stat().st_nlink == 2 and entries[1].exists()


def test_unknown_nested_processing_record_blocks_clear(tmp_path):
    _, project, _ = prepared(tmp_path)
    completed = run_matte(project)
    predictions(project)
    (project / "requests" / completed["operation_id"] / "unrecognized.json").write_text("{}")
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(project, report["candidate_digest"])


def test_cache_confirmation_binds_presentation_snapshots(tmp_path):
    from blackmask.framing import save_framing_preset

    _, project = create(tmp_path)
    predictions(project)
    report = operations.inspect_processing_cache(project)
    state = read_project(project)
    save_framing_preset(
        project,
        {"top_px": 1, "right_px": 2, "bottom_px": 3, "left_px": 4},
        expected_developed_id=state["developed_id"],
        expected_digest=None,
    )
    before = inventory(project)
    with pytest.raises(ProjectError, match="[Ss]tale"):
        operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(project) == before


@pytest.mark.parametrize("record", ["operation", "state", "external_inputs"])
def test_malformed_retained_record_types_report_blockers(tmp_path, record):
    _, project, prepared_result = prepared(tmp_path)
    completed = run_matte(project)
    predictions(project)
    directory = project / "requests" / completed["operation_id"]
    if record == "external_inputs":
        path = project / "revisions" / prepared_result["revision"] / "manifest.json"
        value = json.loads(path.read_bytes())
        value["external_inputs"] = []
        path.write_text(json.dumps(value))
    else:
        name = "operation.json" if record == "operation" else "inputs/state.json"
        (directory / name).write_text("[]")
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        if record == "operation":
            manifest["operation_sha256"] = operations.digest(b"[]")
        else:
            manifest["inputs"]["state.json"] = operations.digest(b"[]")
        manifest_path.write_text(json.dumps(manifest))
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(project, report["candidate_digest"])
    assert inventory(project) == before


def test_late_directory_swap_preserves_remaining_predictions(tmp_path, monkeypatch):
    _, project = create(tmp_path)
    entries = predictions(project)
    report = operations.inspect_processing_cache(project)
    remaining = entries[1].read_bytes()
    cache = entries[0].parent
    retained = project / "cache/retained"
    unlink = os.unlink
    moved = []

    def remove(path, **kwargs):
        unlink(path, **kwargs)
        if not moved:
            cache.rename(retained)
            cache.mkdir()
            (cache / entries[1].name).write_bytes(b"arriving directory owner")
            moved.append(True)

    monkeypatch.setattr(os, "unlink", remove)
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    assert result["status"] == "partial"
    assert result["removed"] == [str(entries[0].relative_to(project))]
    assert (retained / entries[1].name).read_bytes() == remaining
    assert (cache / entries[1].name).read_bytes() == b"arriving directory owner"


@pytest.mark.parametrize("boundary", ["request", "draft", "state"])
def test_restore_capture_interruption_is_preserved_and_classified(tmp_path, monkeypatch, boundary):
    _, project, initial = prepared(tmp_path)
    completed = run_matte(project)
    predictions(project)
    write = Path.write_bytes
    atomic = operations._atomic_bytes
    publish = operations._atomic_json

    def fail_capture(path, value):
        if path.name == "request.json" and path.parent.name.startswith("restore-"):
            raise OSError("incomplete restore capture")
        return write(path, value)

    def fail_draft(path, value, **kwargs):
        if path == project / "recipe.toml":
            raise OSError("complete backup before draft replacement")
        return atomic(path, value, **kwargs)

    def fail_state(path, value, **kwargs):
        if path == project / "state.json":
            raise OSError("complete backup after draft replacement")
        return publish(path, value, **kwargs)

    with monkeypatch.context() as changes:
        if boundary == "request":
            changes.setattr(Path, "write_bytes", fail_capture)
        elif boundary == "draft":
            changes.setattr(operations, "_atomic_bytes", fail_draft)
        else:
            changes.setattr(operations, "_atomic_json", fail_state)
        with pytest.raises(OSError):
            operations.restore_revision(project, initial["revision"], replace_drafts=True)
    assert read_project(project)["working_revision"] == completed["revision"]
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"]
    if boundary == "request":
        assert report["blockers"]
        with pytest.raises(ProjectError):
            operations.clear_processing_cache(project, report["candidate_digest"])
        assert inventory(project) == before
    else:
        assert not report["blockers"]
        result = operations.clear_processing_cache(project, report["candidate_digest"])
        assert result["status"] == "cleared"
        assert inventory(project) == {
            name: value for name, value in before.items() if name not in result["removed"]
        }


@pytest.mark.parametrize("invalid", ["key", "checksum", "dtype", "shape", "nan", "metadata"])
def test_invalid_named_predictions_are_protected(tmp_path, invalid):
    import hashlib

    _, project = create(tmp_path)
    entry = predictions(project, 1)[0]
    alpha = np.full((3, 4), 0.25)
    if invalid == "dtype":
        alpha = alpha.astype(np.int64)
    elif invalid == "shape":
        alpha = alpha.reshape(12)
    elif invalid == "nan":
        alpha[0, 0] = np.nan
    metadata = "[]" if invalid == "metadata" else "{}"
    checksum = hashlib.sha256(alpha.tobytes() + metadata.encode()).hexdigest()
    np.savez(
        entry,
        alpha=alpha,
        metadata=metadata,
        key="0" * 64 if invalid == "key" else entry.stem,
        sha256="0" * 64 if invalid == "checksum" else checksum,
    )
    before = inventory(project)
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] == [] and report["protected"]
    result = operations.clear_processing_cache(project, report["candidate_digest"])
    assert result["removed"] == [] and inventory(project) == before
