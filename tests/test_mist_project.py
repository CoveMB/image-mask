import json
import tomllib
from unittest.mock import patch

import numpy as np
import pytest
import tomli_w
from PIL import Image
from test_effects import fixture_project
from test_ingest import bind_raster
from test_matte_operations import run_matte
from test_mist import settings, vapor_settings
from test_operations import edits, request

from blackmask import operations
from blackmask.assets import revision_asset, revision_hashes
from blackmask.export import render_saved_result
from blackmask.project import ProjectError, _json_bytes, digest, read_project, read_revision
from blackmask.repair import scalar16

EMPTY_AREA = {"regions": [], "protection": []}
FEATHERED_AREA = {
    "regions": [
        {
            "id": "detail",
            "role": "support",
            "shape": "rectangle",
            "xyxy": [1, 1, 4, 4],
            "feather_px": 2,
        }
    ],
    "protection": [],
}


def mist_request(project, *, config=None, area=FEATHERED_AREA, disable=False, candidate=True):
    return request(
        project,
        kind="effects",
        scope_xyxy=[0, 0, 6, 4],
        candidate_comparison=candidate,
        mist={"action": "disable"}
        if disable
        else {"action": "apply", "settings": config or settings(6, 4), "clear_area": area},
    )


def test_vapor_round_trip_and_style_switch_preserve_base(tmp_path):
    project, _, base = fixture_project(tmp_path)
    developed_id = base["developed_id"]
    vapor = vapor_settings(6, 4)
    operation = mist_request(project, config=vapor, area=EMPTY_AREA)
    applied = operations.apply_operation(project, operation)
    assert applied["mist"]["algorithm"] == "linear-srgb-vapor-v1"
    assert operations.apply_operation(
        project, mist_request(project, config=vapor, area=EMPTY_AREA)
    )["reused"]
    with pytest.raises(ProjectError, match="[Ss]tale"):
        operations.apply_operation(project, operation)
    disabled = operations.apply_operation(project, mist_request(project, disable=True))
    assert disabled["mist"]["algorithm"] == applied["mist"]["algorithm"]
    assert disabled["mist"]["density_sha256"] == applied["mist"]["density_sha256"]
    np.testing.assert_array_equal(
        render_saved_result(project, disabled["revision"], developed_id),
        render_saved_result(project, base["revision"], developed_id),
    )
    original = operations.apply_operation(project, mist_request(project))
    assert original["mist"]["algorithm"] == "linear-srgb-mist-v1"
    operations.restore_revision(project, applied["revision"])
    state = read_project(project)
    restored = read_revision(project, state["working_revision"], developed_id)
    assert restored["mist"] == applied["mist"]
    assert state["accepted_revision"] == base["revision"]
    base_manifest = read_revision(project, base["revision"], developed_id)
    for name in ("foreground_rgb16.tif", "base_alpha16.png"):
        assert revision_hashes(restored)[name] == revision_hashes(base_manifest)[name]


def test_vapor_rejects_a_mist_algorithm_binding_even_when_disabled(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    applied = operations.apply_operation(
        project, mist_request(project, config=vapor_settings(6, 4, enabled=False))
    )
    path = project / "revisions" / applied["revision"] / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["mist"]["algorithm"] = "linear-srgb-mist-v1"
    path.write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="algorithm"):
        read_revision(project, applied["revision"], applied["developed_id"])


def test_wispy_vapor_can_replace_and_restore_a_legacy_vapor_revision(tmp_path):
    project, _, base = fixture_project(tmp_path)
    config = vapor_settings(6, 4)
    legacy = operations.apply_operation(project, mist_request(project, config=config))
    legacy_pixels = render_saved_result(project, legacy["revision"], base["developed_id"])
    request = mist_request(project, config=dict(config, pattern_version=2))
    updated = operations.apply_operation(project, request)
    assert updated["mist"]["algorithm"] == "linear-srgb-vapor-v2"
    assert updated["mist"]["density_sha256"] != legacy["mist"]["density_sha256"]
    assert updated["mist"]["clear_sha256"] == legacy["mist"]["clear_sha256"]
    assert operations.apply_operation(
        project, mist_request(project, config=dict(config, pattern_version=2))
    )["reused"]
    operations.restore_revision(project, legacy["revision"])
    np.testing.assert_array_equal(
        render_saved_result(project, legacy["revision"], base["developed_id"]), legacy_pixels
    )
    assert read_project(project)["accepted_revision"] == base["revision"]


def test_apply_repeat_disable_and_pending_cleanup_preserve_accepted_pixels(tmp_path):
    project, _, parent = fixture_project(tmp_path)
    developed_id, base_revision = parent["developed_id"], parent["revision"]
    capture = (tmp_path / "source.tif").read_bytes()
    recipe = project / "recipe.toml"
    base_recipe = tomllib.loads(recipe.read_text())
    original_files = set(project.rglob("*"))
    assert "mist" not in read_revision(project, base_revision, developed_id)
    assert set(project.rglob("*")) == original_files
    base = render_saved_result(project, base_revision, developed_id)
    assert (
        operations.apply_operation(project, mist_request(project, disable=True))["revision"]
        == base_revision
    )
    pending_cleanup = {"enabled": True, "strength": 0.13}
    recipe.write_text(tomli_w.dumps(dict(base_recipe, color_cleanup=pending_cleanup)))
    applied = operations.apply_operation(project, mist_request(project, candidate=False))
    result = render_saved_result(project, applied["revision"], developed_id)
    assert np.any(result[:, 0] != base[:, 0])  # Background-only, next to the partial alpha.
    assert np.any(result[:, 5] != base[:, 5])  # Opaque subject.
    np.testing.assert_array_equal(result[2, 2], base[2, 2])
    saved = read_revision(project, applied["revision"], developed_id)
    previous = read_revision(project, base_revision, developed_id)
    for role in ("base_alpha16.png", "foreground_rgb16.tif"):
        assert saved["assets"][role] == previous["assets"][role]
    assert tomllib.loads(recipe.read_text())["color_cleanup"] == pending_cleanup
    with pytest.raises(ProjectError, match="candidate"):
        operations.apply_operation(project, mist_request(project, candidate=False))
    assert operations.apply_operation(project, mist_request(project))["reused"]
    disabled = operations.apply_operation(project, mist_request(project, disable=True))
    assert disabled["mist"]["settings"] == dict(applied["mist"]["settings"], enabled=False)
    for role in ("area_sha256", "density_sha256", "clear_sha256"):
        assert applied["mist"][role] == disabled["mist"][role]
    np.testing.assert_array_equal(
        render_saved_result(project, disabled["revision"], developed_id), base
    )
    assert operations.apply_operation(project, mist_request(project, disable=True))["reused"]
    assert read_project(project)["accepted_revision"] == base_revision
    assert (tmp_path / "source.tif").read_bytes() == capture


def test_prepare_keeps_unapplied_recipe_and_rebuilds_mist_after_lock_changes(tmp_path):
    project, _, parent = fixture_project(tmp_path)
    developed_id = parent["developed_id"]
    applied = operations.apply_operation(project, mist_request(project, area=EMPTY_AREA))
    recipe = project / "recipe.toml"
    raw_draft = tomli_w.dumps(
        dict(tomllib.loads(recipe.read_text()), mist=settings(6, 4, seed=439))
    )
    recipe.write_text(raw_draft)
    lock = {
        "id": "partial",
        "role": "lock",
        "shape": "rectangle",
        "xyxy": [2, 0, 3, 1],
        "revision": parent["revision"],
    }
    prepared = operations.apply_operation(
        project, request(project, guide_edits_file=edits(project, [lock]))
    )
    directory = project / "revisions" / prepared["revision"]
    manifest = read_revision(project, prepared["revision"], developed_id)
    assert (directory / "recipe.toml").read_text() == raw_draft
    assert manifest["mist"]["settings"] == applied["mist"]["settings"]
    assert manifest["mist"]["density_sha256"] == applied["mist"]["density_sha256"]
    assert manifest["mist"]["clear_sha256"] != applied["mist"]["clear_sha256"]
    assert scalar16(revision_asset(project, directory, manifest, "mist/clear16.png"))[0, 2] == 65535
    completed = run_matte(project)
    assert completed["mist"] == manifest["mist"]
    assert read_project(project)["accepted_revision"] == parent["revision"]
    remove = project / "remove-lock.json"
    remove.write_bytes(
        _json_bytes(
            {
                "schema_version": 2,
                "developed_id": developed_id,
                "actions": [{"action": "remove", "id": "partial"}],
            }
        )
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=remove.name))
    without_lock = read_revision(project, prepared["revision"], developed_id)
    assert without_lock["mist"]["clear_sha256"] == applied["mist"]["clear_sha256"]
    operations.restore_revision(project, completed["revision"], replace_drafts=True)
    assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize("tampering", ["rehashed_clear", "stray", "missing"])
def test_disabled_mist_rejects_bad_inventory_or_clear_map_even_in_read_scope(tmp_path, tampering):
    from blackmask.project import _validation_scope

    project, _, parent = fixture_project(tmp_path)
    operations.apply_operation(project, mist_request(project, area=EMPTY_AREA))
    lock = {
        "id": "partial",
        "role": "lock",
        "shape": "rectangle",
        "xyxy": [2, 0, 3, 1],
        "revision": parent["revision"],
    }
    operations.apply_operation(project, request(project, guide_edits_file=edits(project, [lock])))
    run_matte(project)
    disabled = operations.apply_operation(project, mist_request(project, disable=True))
    directory = project / "revisions" / disabled["revision"]
    manifest_file = directory / "manifest.json"
    revision, developed_id = disabled["revision"], disabled["developed_id"]
    with _validation_scope():
        manifest = read_revision(project, revision, developed_id)
        if tampering == "stray":
            (directory / "mist/unknown.json").write_text("{}")
        elif tampering == "missing":
            (directory / "mist/area.json").unlink()
        else:
            path = directory / "mist/clear16.png"
            Image.fromarray(np.zeros((4, 6), np.uint16)).save(path)
            checksum = digest(path.read_bytes())
            bind_raster(project, directory, manifest, "mist/clear16.png")
            manifest["mist"]["clear_sha256"] = checksum
            manifest_file.write_bytes(_json_bytes(manifest))
            assert revision_hashes(manifest)["mist/clear16.png"] == checksum
        with pytest.raises(ProjectError, match="[Mm]ist"):
            read_revision(project, revision, developed_id)


def test_mist_rejects_mixed_and_malformed_requests_and_checks_disk_before_staging(tmp_path):
    project, _, parent = fixture_project(tmp_path)
    operation = mist_request(project)
    original = set((project / "revisions").iterdir())
    with pytest.raises(ProjectError, match="exclusive"):
        operations.apply_operation(
            project, dict(operation, color_cleanup={"enabled": False, "strength": 0})
        )
    request_path = tmp_path / "request.json"
    request_path.write_bytes(_json_bytes(operation).replace(b'"seed":1', b'"seed":2,"seed":1'))
    with pytest.raises(ProjectError, match="Duplicate"):
        operations.apply_operation(project, operation, request_file=request_path)
    request_path.write_bytes(b" " * 2_000_000 + _json_bytes(operation))
    with pytest.raises(ProjectError, match="2000000"):
        operations.apply_operation(project, operation, request_file=request_path)
    with (
        patch("blackmask.effects.check_space", side_effect=ProjectError("Insufficient space")),
        pytest.raises(ProjectError, match="Insufficient space"),
    ):
        operations.apply_operation(project, operation)
    assert set((project / "revisions").iterdir()) == original
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_mist_visible_publication_on_state_failure_is_explicitly_restorable(tmp_path):
    project, _, parent = fixture_project(tmp_path)
    state_before = (project / "state.json").read_bytes()
    with (
        patch("blackmask.effects._atomic_json", side_effect=OSError("synthetic state failure")),
        pytest.raises(
            ProjectError, match="Mist publication durability unconfirmed.*synthetic state failure"
        ),
    ):
        operations.apply_operation(project, mist_request(project))
    assert (project / "state.json").read_bytes() == state_before
    visible = max((project / "revisions").glob("rev-*")).name
    assert (
        visible != parent["revision"]
        and read_revision(project, visible, parent["developed_id"])["mist"]
    )
    operations.restore_revision(project, visible, replace_drafts=True)
    state = read_project(project)
    assert state["working_revision"] == visible and state["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize("failure", ["stale-request", "state-directory-sync"])
def test_mist_visible_publication_reports_the_original_diagnosis(tmp_path, monkeypatch, failure):
    from blackmask import effects
    from blackmask import project as project_module

    project, _, parent = fixture_project(tmp_path)
    state_path = project / "state.json"
    state_before = state_path.read_bytes()
    operation = mist_request(project)
    request_path = tmp_path / "request.json"
    request_bytes = _json_bytes(operation)
    request_path.write_bytes(request_bytes)

    if failure == "stale-request":

        def invalidate_request_before_state_write(path, value, **options):
            assert path == state_path
            request_path.write_bytes(request_bytes + b"\n")
            project_module._atomic_json(path, value, **options)

        monkeypatch.setattr(effects, "_atomic_json", invalidate_request_before_state_write)
        diagnosis = "Stale effects support/request/parent"
    else:
        sync_directory = project_module._sync_directory

        def fail_after_state_replace(directory):
            if directory == project and state_path.read_bytes() != state_before:
                raise OSError("synthetic state directory sync failure")
            sync_directory(directory)

        monkeypatch.setattr(project_module, "_sync_directory", fail_after_state_replace)
        diagnosis = "State replacement occurred; directory durability is uncertain; observed"

    with pytest.raises(ProjectError, match=diagnosis) as captured:
        operations.apply_operation(project, operation, request_file=request_path)
    visible = max((project / "revisions").glob("rev-*")).name
    assert visible != parent["revision"]
    assert read_revision(project, visible, parent["developed_id"])["mist"]
    assert f"visible revision {project / 'revisions' / visible}" in str(captured.value)
    assert "Reload project status" in str(captured.value)
    state = read_project(project)
    assert state["accepted_revision"] == parent["revision"]
    if failure == "stale-request":
        assert state_path.read_bytes() == state_before
        assert "durability unconfirmed" not in str(captured.value)
    else:
        assert state["working_revision"] == visible
        assert f'"working_revision": "{visible}"' in str(captured.value)


def test_alpha_only_repair_and_completed_resume_keep_mist_operand_identities(tmp_path):
    from pathlib import Path

    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request
    from test_resume import recovery_id

    project, _, parent = fixture_project(tmp_path)
    applied = operations.apply_operation(project, mist_request(project))
    prepared = repair_guides(project, [1, 1, 5, 3])
    operation = repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 5, 3])

    class ChangedAlpha(StubSession):
        def predict(self, rgb, trimap, device):
            return np.full(trimap.shape, 0.625), {"fixture": "changed-alpha", "device": device}

    with (
        patch("blackmask.operations.VitMatteSession", ChangedAlpha),
        patch("blackmask.operations._publish_new_directory", side_effect=OSError("interrupted")),
        pytest.raises(OSError, match="interrupted"),
    ):
        operations.apply_operation(project, operation, model_cache=Path("unused"))
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("model replay")):
        resumed = operations.resume_operation(project, recovery_id(project))
    directory = project / "revisions" / resumed["revision"]
    manifest = read_revision(project, resumed["revision"], parent["developed_id"])
    alpha = scalar16(revision_asset(project, directory, manifest, "base_alpha16.png"))
    assert alpha[2, 2] == 40959 and alpha[0, 2] == 16384
    assert manifest["mist"] == applied["mist"]
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_native_mist_success_reports_gallery_pending_separately_from_acceptance(tmp_path):
    from test_previews import generate, jpeg, managed

    _, config, project = managed(tmp_path)
    base = generate(project, config)
    operations.accept_revision(project, base["revision"], storage_config=config)
    accepted_jpeg = jpeg(config, project).read_bytes()
    with patch(
        "blackmask.previews._encode_preview", side_effect=OSError("synthetic gallery failure")
    ):
        applied = operations.apply_operation(project, mist_request(project), storage_config=config)
    assert applied["preview_pending"] is True
    assert "synthetic gallery failure" in applied["preview"]["error"]
    state = read_project(project)
    assert state["working_revision"] == applied["revision"] != state["accepted_revision"]
    assert state["accepted_revision"] == base["revision"]
    assert jpeg(config, project).read_bytes() == accepted_jpeg
