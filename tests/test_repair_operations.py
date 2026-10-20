"""Synthetic recorded repair workflow; fixture approvals are not photographic evidence."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from test_ingest import srgb_profile, tiff
from test_matte_operations import StubSession, approve, run_matte
from test_operations import edits, request

from blackmask import operations
from blackmask.project import accept_development, create_project, read_project


def parent_project(tmp_path):
    source = tiff(
        tmp_path / "source.tif", np.full((4, 5, 3), 12345, dtype=np.uint16), profile=srgb_profile()
    )
    project = tmp_path / "project"
    create_project(source, project, {})
    accept_development(project, read_project(project)["master_id"])
    prepared = operations.apply_operation(project, request(project))
    approve(project, prepared)
    parent = run_matte(project)
    operations.accept_revision(project, parent["revision"])
    return source, project, parent


def repair_guides(project, rectangle):
    filename = edits(
        project,
        [
            {
                "id": "repair-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": rectangle,
                "feather_px": 0,
            }
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    approve(project, prepared)
    return prepared


def repair_request(project, prepared, context, scope, *, relative=False):
    support = prepared["support_file"]
    if relative:
        support = str(Path(support).relative_to(project))
    return request(
        project,
        kind="repair",
        context_xyxy=context,
        scope_xyxy=scope,
        support_file=support,
        reason="Synthetic fixture source-guided test correction",
    )


def run_repair(project, operation):
    with patch("blackmask.operations.VitMatteSession", StubSession):
        return operations.apply_operation(project, operation, model_cache=Path("unused"))


def test_public_returned_absolute_support_path_and_exact_outside(tmp_path):
    source, project, parent = parent_project(tmp_path)
    original = source.read_bytes()
    prepared = repair_guides(project, [1, 1, 4, 3])
    assert Path(prepared["support_file"]).is_absolute()
    with (
        patch.object(StubSession, "identity", {"fixture": "repair"}),
        patch.object(
            StubSession,
            "predict",
            side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
        ),
    ):
        result = run_repair(project, repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 4, 3]))
    with Image.open(project / "revisions" / result["revision"] / "base_alpha16.png") as image:
        alpha = np.array(image)
    assert np.all(alpha[1:3, 1:4] == 49151)
    outside = np.ones((4, 5), dtype=bool)
    outside[1:3, 1:4] = False
    assert outside.any() and (~outside).any()
    assert np.all(alpha[outside] == 16384)
    assert source.read_bytes() == original
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_moved_native_context_invalidates_identical_crop_bytes(tmp_path):
    from test_matte import cache_identity

    _, project, _ = parent_project(tmp_path)
    calls = []

    def prediction(rgb, guide, device):
        calls.append((rgb.copy(), guide.copy()))
        return np.full(guide.shape, 0.75), {}

    identity = cache_identity()
    identity.pop("master_id")
    with (
        patch.object(StubSession, "identity", identity),
        patch.object(StubSession, "predict", side_effect=prediction),
    ):
        first = repair_guides(project, [1, 1, 2, 2])
        run_repair(
            project, repair_request(project, first, [0, 0, 3, 2], [1, 1, 2, 2], relative=True)
        )
        second = repair_guides(project, [2, 1, 3, 2])
        run_repair(
            project, repair_request(project, second, [1, 0, 4, 2], [2, 1, 3, 2], relative=True)
        )
    assert len(calls) == 2
    np.testing.assert_array_equal(calls[0][0], calls[1][0])
    np.testing.assert_array_equal(calls[0][1], calls[1][1])


import os
import subprocess
import sys

import pytest
import tifffile

from blackmask.project import ProjectError, digest, project_lock


def alpha_at(project, revision):
    with Image.open(project / "revisions" / revision / "base_alpha16.png") as image:
        return np.array(image)


@pytest.mark.parametrize(
    "policy,level,expected",
    [
        ("replace", 0.75, 49151),
        ("increase-only", 0.1, 16384),
        ("decrease-only", 0.75, 16384),
        ("increase-only", 0.75, 49151),
        ("decrease-only", 0.1, 6554),
    ],
)
def test_repair_roundtrip_replay_full_rerun_locks_and_restore(tmp_path, policy, level, expected):
    from blackmask.ingest import write_master
    from blackmask.repair import replay_repair

    source, project, parent = parent_project(tmp_path)
    capture = source.read_bytes()
    directory = project / "revisions" / parent["revision"]
    foreground = tifffile.imread(directory / "foreground_rgb16.tif")
    foreground[1, 2] = [1111, 2222, 3333]
    # Explicit synthetic saved RGB fixture, never photographic acceptance evidence.
    write_master(directory / "foreground_rgb16.tif", foreground)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["files"]["foreground_rgb16.tif"] = digest(
        (directory / "foreground_rgb16.tif").read_bytes()
    )
    (directory / "manifest.json").write_text(json.dumps(manifest))
    filename = edits(
        project,
        [
            {
                "id": "repair-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 1, 4, 3],
                "feather_px": 2,
            },
            {
                "id": "partial-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": parent["revision"],
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    assert np.array_equal(
        alpha_at(project, prepared["revision"]), alpha_at(project, parent["revision"])
    )
    np.testing.assert_array_equal(
        tifffile.imread(Path(prepared["manifest_file"]).parent / "foreground_rgb16.tif"), foreground
    )
    with pytest.raises(ProjectError, match="prepared"):
        operations.accept_revision(project, prepared["revision"])
    approve(project, prepared)
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 4, 3])
    operation["merge_policy"] = policy
    with (
        patch.object(StubSession, "identity", {"fixture": policy}),
        patch.object(
            StubSession,
            "predict",
            side_effect=lambda rgb, guide, device: (np.full(guide.shape, level), {}),
        ),
    ):
        result = run_repair(project, operation)
    saved = Path(result["manifest_file"]).parent
    alpha = alpha_at(project, result["revision"])
    prior = alpha_at(project, parent["revision"])
    with Image.open(saved / "repair/support16.png") as image:
        support = np.array(image)
    assert np.any(support == 0) and np.any((support > 0) & (support < 65535))
    assert np.all(alpha[support == 0] == prior[support == 0])
    assert alpha[1, 2] == prior[1, 2] == 16384
    # Independent scalar formula at a non-protected, genuinely feathered sample.
    weight = int(support[2, 1]) / 65535
    assert alpha[2, 1] == round(16384 * (1 - weight) + expected * weight)
    np.testing.assert_array_equal(tifffile.imread(saved / "foreground_rgb16.tif"), foreground)
    np.testing.assert_array_equal(replay_repair(project, result["revision"]), alpha)
    empty = tmp_path / "empty-cache"
    empty.mkdir()
    code = """
import json,sys
from pathlib import Path
import numpy as np
from blackmask import models
calls=[]
def forbidden(*args,**kwargs):
    calls.append(1)
    raise AssertionError("model forbidden during replay")
models.VitMatteSession.__init__=forbidden
models.SamSession.__init__=forbidden
from blackmask.repair import replay_repair
alpha=replay_repair(Path(sys.argv[1]),sys.argv[2])
np.save(sys.argv[3],alpha)
print(json.dumps({"model_calls":len(calls),"exact":True}))
"""
    env = dict(
        os.environ,
        BLACKMASK_VITMATTE_CACHE=str(empty),
        BLACKMASK_SAM_CACHE=str(empty),
        HF_HUB_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    replayed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(project),
            result["revision"],
            str(tmp_path / "replay.npy"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert replayed.returncode == 0, replayed.stderr
    assert json.loads(replayed.stdout) == {"model_calls": 0, "exact": True}
    np.testing.assert_array_equal(np.load(tmp_path / "replay.npy"), alpha)
    assert list(empty.iterdir()) == []
    # Later complete matte rerun respects same saved partial alpha/RGB lock.
    again = operations.apply_operation(project, request(project))
    approve(project, again)
    with (
        patch.object(StubSession, "identity", {"fixture": "full-rerun"}),
        patch.object(
            StubSession,
            "predict",
            side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.9), {}),
        ),
    ):
        full = run_matte(project)
    assert alpha_at(project, full["revision"])[1, 2] == 16384
    np.testing.assert_array_equal(
        tifffile.imread(Path(full["manifest_file"]).parent / "foreground_rgb16.tif")[1, 2],
        [1111, 2222, 3333],
    )
    restored = operations.restore_revision(project, result["revision"])
    assert restored["working_revision"] == result["revision"]
    assert restored["accepted_revision"] == parent["revision"]
    assert source.read_bytes() == capture


@pytest.mark.parametrize(
    "field,value",
    [
        ("master_id", "0" * 64),
        ("base_revision", "rev-999"),
        ("inputs_digest", "0" * 64),
        ("context_xyxy", [0, 0, 0, 2]),
        ("scope_xyxy", [0, 0, 1, 1]),
        ("support_file", "/private/tmp/unrelated.png"),
        ("guide_edits_file", "edits.json"),
        ("merge_policy", "arbitrary"),
        ("reason", ""),
    ],
)
def test_repair_invalid_inputs_rejected_before_models(tmp_path, field, value):
    _, project, parent = parent_project(tmp_path)
    prepared = repair_guides(project, [1, 1, 3, 3])
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3])
    operation[field] = value
    state = (project / "state.json").read_bytes()
    with (
        patch(
            "blackmask.operations.VitMatteSession",
            side_effect=AssertionError("model must not load"),
        ),
        pytest.raises(ProjectError),
    ):
        operations.apply_operation(project, operation, model_cache=Path("unused"))
    assert (project / "state.json").read_bytes() == state
    assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize("failure", ["low-disk", "draft-edit", "pointer", "publication"])
def test_repair_failure_preserves_accepted_export_source_and_newer_draft(tmp_path, failure):
    from blackmask.export import export_project

    source, project, parent = parent_project(tmp_path)
    exported = export_project(project)
    export_path = Path(exported["directory"]) / "black_rgb16.tif"
    accepted_bytes = export_path.read_bytes()
    source_bytes = source.read_bytes()
    prepared = repair_guides(project, [1, 1, 3, 3])
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3])
    before = (project / "state.json").read_bytes()

    def prediction(rgb, guide, device):
        if failure == "draft-edit":
            with (project / "recipe.toml").open("a") as stream:
                stream.write("\n# newer external text\n")
        return np.full(guide.shape, 0.8), {}

    target = {
        "low-disk": "blackmask.project.shutil.disk_usage",
        "pointer": "blackmask.operations._atomic_json",
        "publication": "blackmask.operations._publish_new_directory",
    }.get(failure)
    with (
        patch.object(StubSession, "identity", {"fixture": failure}),
        patch.object(StubSession, "predict", side_effect=prediction),
    ):
        if target:
            arguments = (
                {"return_value": type("Disk", (), {"free": 1})()}
                if failure == "low-disk"
                else {"side_effect": OSError(failure)}
            )
            with patch(target, **arguments), pytest.raises((ProjectError, OSError)):
                run_repair(project, operation)
        else:
            with pytest.raises(ProjectError, match="Stale"):
                run_repair(project, operation)
    assert (project / "state.json").read_bytes() == before
    assert export_path.read_bytes() == accepted_bytes
    assert source.read_bytes() == source_bytes
    assert read_project(project)["accepted_revision"] == parent["revision"]
    if failure == "draft-edit":
        assert "newer external text" in (project / "recipe.toml").read_text()


def test_restore_unsaved_text_recovery_and_interrupted_pointer(tmp_path):
    _, project, parent = parent_project(tmp_path)
    repair_guides(project, [1, 1, 3, 3])
    with (project / "recipe.toml").open("a") as stream:
        stream.write("\n# preserve my unsaved text\n")
    before = {
        name: (project / name).read_bytes() for name in ("recipe.toml", "guides.json", "state.json")
    }
    with pytest.raises(ProjectError, match="Unsaved"):
        operations.restore_revision(project, parent["revision"])
    assert all((project / name).read_bytes() == data for name, data in before.items())
    with (
        patch("blackmask.operations._atomic_json", side_effect=OSError("pointer fault")),
        pytest.raises(OSError),
    ):
        operations.restore_revision(project, parent["revision"], replace_drafts=True)
    assert (project / "state.json").read_bytes() == before["state.json"]
    recovery = list((project / "recovery").iterdir())
    assert len(recovery) == 1
    assert all((recovery[0] / name).read_bytes() == data for name, data in before.items())
    restored = operations.restore_revision(project, parent["revision"], replace_drafts=True)
    assert restored["accepted_revision"] == parent["revision"]
    assert restored["working_revision"] == parent["revision"]


def test_real_cli_writers_share_os_lock_and_reads_remain_responsive(tmp_path):
    _, project, parent = parent_project(tmp_path)
    prepared = repair_guides(project, [1, 1, 3, 3])
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3])
    path = project / "request.json"
    path.write_text(json.dumps(operation))
    before = (project / "state.json").read_bytes()
    with project_lock(project):
        for args in (
            ["restore", str(project), "--revision", parent["revision"]],
            ["accept", str(project), "--revision", parent["revision"]],
            ["run", str(project), "--request", str(path)],
        ):
            child = subprocess.run(
                [sys.executable, "-m", "blackmask", *args],
                check=False,
                capture_output=True,
                text=True,
            )
            assert child.returncode == 1 and "busy" in child.stderr, child.stderr
        child = subprocess.run(
            [sys.executable, "-m", "blackmask", "open", "--headless", "--project", str(project)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert child.returncode == 0, child.stderr
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize(
    "policy,role", [("increase-only", "background"), ("decrease-only", "foreground")]
)
def test_incompatible_known_core_policy_fails_before_inference(tmp_path, policy, role):
    _, project, _ = parent_project(tmp_path)
    filename = edits(
        project,
        [
            {
                "id": "support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 1, 3, 3],
                "feather_px": 0,
            },
            {"id": "core", "role": role, "shape": "rectangle", "xyxy": [1, 1, 2, 2]},
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    approve(project, prepared)
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3])
    operation["merge_policy"] = policy
    with (
        patch(
            "blackmask.operations.VitMatteSession", side_effect=AssertionError("model forbidden")
        ),
        pytest.raises(ProjectError, match="Directional"),
    ):
        operations.apply_operation(project, operation, model_cache=Path("unused"))


def test_feathered_change_required_core_rejected_during_prepare(tmp_path):
    _, project, _ = parent_project(tmp_path)
    filename = edits(
        project,
        [
            {
                "id": "support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 1, 3, 3],
                "feather_px": 3,
            },
            {"id": "core", "role": "background", "shape": "rectangle", "xyxy": [1, 1, 2, 2]},
        ],
    )
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="full support"):
        operations.apply_operation(project, request(project, guide_edits_file=filename))
    assert (project / "state.json").read_bytes() == before


def test_replace_rechecks_nonempty_known_cores_and_native_review_mapping(tmp_path):
    _, project, _ = parent_project(tmp_path)
    filename = edits(
        project,
        [
            {
                "id": "support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 1, 4, 3],
                "feather_px": 0,
            },
            {"id": "fg", "role": "foreground", "shape": "rectangle", "xyxy": [1, 1, 2, 2]},
            {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [3, 2, 4, 3]},
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    approve(project, prepared)
    context = [1, 0, 5, 4]
    with (
        patch.object(StubSession, "identity", {"fixture": "known-cores"}),
        patch.object(
            StubSession,
            "predict",
            side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.4), {}),
        ),
    ):
        result = run_repair(project, repair_request(project, prepared, context, [1, 1, 4, 3]))
    alpha = alpha_at(project, result["revision"])
    assert alpha[1, 1] == 65535 and alpha[2, 3] == 0
    directory = Path(result["manifest_file"]).parent
    for name in ("review", "review-before"):
        record = json.loads((directory / name / "manifest.json").read_bytes())
        assert record["crops"][0]["crop_xyxy"] == context
        assert record["crops"][0]["native_origin_xy"] == [1, 0]
        assert record["crops"][0]["displayed_dimensions_wh"] == [4, 4]


@pytest.mark.parametrize("change", ["mapping", "parent", "order"])
def test_replay_rejects_invalid_bound_mapping_parent_and_order(tmp_path, change):
    from blackmask.repair import replay_repair

    _, project, _ = parent_project(tmp_path)
    prepared = repair_guides(project, [1, 1, 3, 3])
    result = run_repair(project, repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3]))
    directory = Path(result["manifest_file"]).parent
    path = directory / "repair/merge.json"
    record = json.loads(path.read_bytes())
    if change == "mapping":
        record["crop_mapping"]["origin_xy"] = [1, 0]
    elif change == "parent":
        record["parent"] = "rev-999"
    else:
        record["operation_order"] = "different ordering"
    path.write_text(json.dumps(record))
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["files"]["repair/merge.json"] = digest(path.read_bytes())
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="mapping|bindings"):
        replay_repair(project, result["revision"])


def test_alias_support_rejected_and_late_ancestor_edit_never_publishes(tmp_path):
    _, project, parent = parent_project(tmp_path)
    prepared = repair_guides(project, [1, 1, 3, 3])
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3])
    alias = project / "support-alias.png"
    alias.symlink_to(prepared["support_file"])
    with pytest.raises(ProjectError, match="symlink"):
        run_repair(project, dict(operation, support_file="support-alias.png"))
    state = (project / "state.json").read_bytes()
    ancestor = project / "revisions" / parent["revision"] / "manifest.json"
    prior = ancestor.read_bytes()

    def late_edit(rgb, guide, device):
        record = json.loads(prior)
        record["fixture_late_edit"] = True
        ancestor.write_text(json.dumps(record))
        return np.full(guide.shape, 0.8), {}

    with (
        patch.object(StubSession, "identity", {"fixture": "late-ancestor"}),
        patch.object(StubSession, "predict", side_effect=late_edit),
        pytest.raises(ProjectError, match="Stale"),
    ):
        run_repair(project, operation)
    assert (project / "state.json").read_bytes() == state


def test_actual_killed_repair_writer_retains_accepted_files_and_releases_lock(tmp_path):
    source, project, parent = parent_project(tmp_path)
    prepared = repair_guides(project, [1, 1, 3, 3])
    operation = repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3])
    before = (project / "state.json").read_bytes()
    capture = source.read_bytes()
    alpha = (project / "revisions" / parent["revision"] / "base_alpha16.png").read_bytes()
    marker = tmp_path / "inference-entered"
    code = """
import json,sys,time
from pathlib import Path
import numpy as np
from blackmask import operations
class Session:
    identity={"fixture":"killed-repair"}
    def __init__(self,cache): pass
    def predict(self,rgb,guide,device):
        Path(sys.argv[3]).write_text("entered")
        time.sleep(60)
        return np.full(guide.shape,0.7),{}
operations.VitMatteSession=Session
operations.apply_operation(Path(sys.argv[1]),json.loads(sys.argv[2]),model_cache=Path("unused"))
"""
    import time

    child = subprocess.Popen(
        [sys.executable, "-c", code, str(project), json.dumps(operation), str(marker)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), "repair child never entered inference"
        child.kill()
        _, stderr = child.communicate(timeout=5)
        assert child.returncode == -9, stderr
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    assert (project / "state.json").read_bytes() == before
    assert source.read_bytes() == capture
    assert (project / "revisions" / parent["revision"] / "base_alpha16.png").read_bytes() == alpha
    with project_lock(project):
        assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize(
    "filename,bad_bytes",
    [
        ("recipe.toml", b"not valid = ["),
        ("guides.json", b"{broken"),
    ],
)
def test_explicit_restore_recovers_malformed_drafts_without_weakening_reads(
    tmp_path, filename, bad_bytes
):
    source, project, parent = parent_project(tmp_path)
    repair_guides(project, [1, 1, 3, 3])
    (project / filename).write_bytes(bad_bytes)
    capture = source.read_bytes()
    state_bytes = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        read_project(project)
    with pytest.raises(ProjectError):
        operations.restore_revision(project, parent["revision"])
    assert (project / filename).read_bytes() == bad_bytes
    assert (project / "state.json").read_bytes() == state_bytes
    result = operations.restore_revision(project, parent["revision"], replace_drafts=True)
    recovery = Path(result["recovery_directory"])
    assert (recovery / filename).read_bytes() == bad_bytes
    assert (recovery / "state.json").read_bytes() == state_bytes
    assert result["working_revision"] == result["accepted_revision"] == parent["revision"]
    assert read_project(project)["accepted_revision"] == parent["revision"]
    assert source.read_bytes() == capture


@pytest.mark.parametrize("invalid", ["master", "state", "source"])
def test_explicit_restore_still_rejects_invalid_immutable_assets(tmp_path, invalid):
    source, project, parent = parent_project(tmp_path)
    state = read_project(project)
    capture = source.read_bytes()
    (project / "recipe.toml").write_bytes(b"broken = [")
    if invalid == "master":
        (project / "masters" / (state["master_id"] + ".tif")).write_bytes(b"invalid master")
    elif invalid == "state":
        broken = dict(state, status="invalid status")
        (project / "state.json").write_text(json.dumps(broken))
    else:
        broken = json.loads((project / "source.json").read_bytes())
        broken["master_id"] = "0" * 64
        (project / "source.json").write_text(json.dumps(broken))
    state_bytes = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.restore_revision(project, parent["revision"], replace_drafts=True)
    assert (project / "state.json").read_bytes() == state_bytes
    assert (project / "recipe.toml").read_bytes() == b"broken = ["
    assert source.read_bytes() == capture
    assert not (project / "recovery").exists()


def test_explicit_malformed_restore_preserves_late_text_and_acceptance(tmp_path):
    source, project, parent = parent_project(tmp_path)
    repair_guides(project, [1, 1, 3, 3])
    (project / "guides.json").write_bytes(b"{broken")
    before = (project / "state.json").read_bytes()
    capture = source.read_bytes()
    original = operations._atomic_bytes

    def intervening_text(path, data, **kwargs):
        (project / "guides.json").write_bytes(b"{newer external edit")
        return original(path, data, **kwargs)

    with (
        patch("blackmask.operations._atomic_bytes", side_effect=intervening_text),
        pytest.raises(ProjectError, match="Stale"),
    ):
        operations.restore_revision(project, parent["revision"], replace_drafts=True)
    assert (project / "guides.json").read_bytes() == b"{newer external edit"
    assert (project / "state.json").read_bytes() == before
    assert source.read_bytes() == capture
    records = list((project / "recovery").iterdir())
    assert len(records) == 1
    assert (records[0] / "guides.json").read_bytes() == b"{broken"


def test_default_repair_review_retains_saved_asymmetric_crops_and_explicit_override(tmp_path):
    from blackmask.review import review_project

    _, project, _ = parent_project(tmp_path)
    prepared = repair_guides(project, [1, 1, 3, 3])
    context = [1, 0, 5, 4]
    result = run_repair(project, repair_request(project, prepared, context, [1, 1, 3, 3]))
    reviewed = review_project(project, revision=result["revision"])
    record = json.loads(Path(reviewed["manifest_file"]).read_bytes())
    assert [crop["crop_xyxy"] for crop in record["crops"]] == [context]
    overridden = review_project(project, revision=result["revision"], crops=[[0, 0, 2, 2]])
    override = json.loads(Path(overridden["manifest_file"]).read_bytes())
    assert [crop["crop_xyxy"] for crop in override["crops"]] == [[0, 0, 2, 2]]


@pytest.mark.parametrize("kind", ["prepare", "matte", "repair"])
def test_restore_noncanonical_valid_guide_text_from_immutable_input_snapshot(tmp_path, kind):
    _, project, _ = parent_project(tmp_path)
    guides = json.loads((project / "guides.json").read_bytes())
    guides["regions"].append(
        {
            "id": "support",
            "role": "support",
            "shape": "rectangle",
            "xyxy": [1, 1, 3, 3],
            "feather_px": 0,
        }
    )
    original = (json.dumps(guides, indent=4, sort_keys=True) + "\n\n").encode()
    (project / "guides.json").write_bytes(original)
    prepared = operations.apply_operation(project, request(project))
    approve(project, prepared)
    if kind == "prepare":
        target = prepared
    elif kind == "matte":
        target = run_matte(project)
    else:
        target = run_repair(project, repair_request(project, prepared, [0, 0, 5, 4], [1, 1, 3, 3]))
    assert (project / "guides.json").read_bytes() == original
    # Existing saved revisions may store normalized guides but hash original draft bytes.
    directory = Path(target["manifest_file"]).parent
    assert (directory / "guides.json").read_bytes() != original
    result = operations.restore_revision(project, target["revision"])
    assert result["working_revision"] == target["revision"]
    assert (project / "guides.json").read_bytes() == original
    assert operations.draft_digest(project) == result["inputs_digest"]


def test_restore_rechecks_unsaved_default_text_during_snapshot(tmp_path):
    _, project, parent = parent_project(tmp_path)
    repair_guides(project, [1, 1, 3, 3])
    before = (project / "state.json").read_bytes()
    actual_digest = operations.draft_digest

    def edit_after_digest(root):
        captured = actual_digest(root)
        with (root / "recipe.toml").open("a") as stream:
            stream.write("\n# newly saved external text\n")
        return captured

    with (
        patch("blackmask.operations.draft_digest", side_effect=edit_after_digest),
        pytest.raises(ProjectError, match="Unsaved|Stale"),
    ):
        operations.restore_revision(project, parent["revision"])
    assert "newly saved external text" in (project / "recipe.toml").read_text()
    assert (project / "state.json").read_bytes() == before


def orphan_preparation(tmp_path):
    from test_operations import opened

    source, project = opened(tmp_path)
    filename = edits(
        project,
        [
            {
                "id": "support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [0, 0, 2, 1],
                "feather_px": 0,
            }
        ],
    )
    atomic_json = operations._atomic_json

    def fail_working_pointer(path, value, **kwargs):
        if path.name == "state.json":
            raise OSError("injected initial preparation pointer failure")
        return atomic_json(path, value, **kwargs)

    with (
        patch("blackmask.operations._atomic_json", side_effect=fail_working_pointer),
        pytest.raises(OSError, match="pointer failure"),
    ):
        operations.apply_operation(project, request(project, guide_edits_file=filename))
    state = read_project(project)
    assert state["working_revision"] is None and state["accepted_revision"] is None
    revisions = [path for path in (project / "revisions").iterdir() if path.name.startswith("rev-")]
    assert len(revisions) == 1
    return source, project, revisions[0].name


@pytest.mark.parametrize("filename", ["recipe.toml", "guides.json"])
def test_restore_orphan_rejects_unsaved_drafts_without_explicit_replacement(tmp_path, filename):
    source, project, revision = orphan_preparation(tmp_path)
    capture = source.read_bytes()
    path = project / filename
    path.write_bytes(
        path.read_bytes() + (b"\n# unsaved recipe text\n" if filename == "recipe.toml" else b"\n\n")
    )
    before = {
        name: (project / name).read_bytes() for name in ("recipe.toml", "guides.json", "state.json")
    }
    with pytest.raises(ProjectError, match="Unsaved|replace-drafts"):
        operations.restore_revision(project, revision)
    assert all((project / name).read_bytes() == value for name, value in before.items())
    assert not (project / "recovery").exists()
    result = operations.restore_revision(project, revision, replace_drafts=True)
    assert result["working_revision"] == revision and result["accepted_revision"] is None
    recovery = Path(result["recovery_directory"])
    assert all((recovery / name).read_bytes() == value for name, value in before.items())
    assert operations.draft_digest(project) == result["inputs_digest"]
    assert source.read_bytes() == capture


def test_restore_orphan_with_matching_drafts_needs_no_replacement_flag(tmp_path):
    source, project, revision = orphan_preparation(tmp_path)
    capture = source.read_bytes()
    before = {name: (project / name).read_bytes() for name in ("recipe.toml", "guides.json")}
    result = operations.restore_revision(project, revision)
    assert result["working_revision"] == revision and result["accepted_revision"] is None
    assert all((project / name).read_bytes() == value for name, value in before.items())
    assert source.read_bytes() == capture


def test_restore_orphan_binds_default_check_to_captured_draft_bytes(tmp_path):
    source, project, revision = orphan_preparation(tmp_path)
    capture = source.read_bytes()
    state = (project / "state.json").read_bytes()
    original = operations.draft_digest

    def edit_after_initial_check(root):
        captured = original(root)
        with (root / "recipe.toml").open("a") as stream:
            stream.write("\n# intervening unsaved text\n")
        return captured

    with (
        patch("blackmask.operations.draft_digest", side_effect=edit_after_initial_check),
        pytest.raises(ProjectError, match="Unsaved|Stale"),
    ):
        operations.restore_revision(project, revision)
    assert "intervening unsaved text" in (project / "recipe.toml").read_text()
    assert (project / "state.json").read_bytes() == state
    assert source.read_bytes() == capture
    assert not (project / "recovery").exists()
