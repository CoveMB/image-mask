import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_ingest import bind_raster, saved_raster
from test_project import create

from blackmask import operations
from blackmask.project import ProjectError, accept_development, read_project


def opened(tmp_path):
    source, project = create(tmp_path)
    state = read_project(project)
    accept_development(project, state["developed_id"])
    return source, project


def request(project, **extra):
    state = read_project(project)
    return {
        "schema_version": 2,
        "kind": "prepare",
        "developed_id": state["developed_id"],
        "base_revision": state["working_revision"],
        "inputs_digest": operations.draft_digest(project),
        **extra,
    }


def edits(project, regions):
    path = project / "edits.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "developed_id": read_project(project)["developed_id"],
                "actions": [{"action": "upsert", "region": r} for r in regions],
            }
        )
    )
    return "edits.json"


def test_prepare_real_files_snapshots_and_second_parent(tmp_path):
    source, project = opened(tmp_path)
    original = source.read_bytes()
    result = operations.apply_operation(project, request(project))
    assert result["revision"] == "rev-001" and result["parent"] is None
    assert saved_raster(Path(result["trimap_file"])).is_file()
    assert np.all(np.array(Image.open(saved_raster(result["trimap_file"]))) == 128)
    assert result["inputs_digest"] == operations.draft_digest(project)
    assert read_project(project)["accepted_revision"] is None
    revision = Path(result["manifest_file"]).parent
    assert (revision / "request.json").is_file() and (revision / "recipe.toml").is_file()
    second = operations.apply_operation(project, request(project))
    assert second["parent"] == "rev-001" and second["revision"] == "rev-002"
    assert source.read_bytes() == original
    with pytest.raises(ProjectError, match="prepared"):
        operations.accept_revision(project, second["revision"])


def test_edits_applied_once_and_subsequent_prepare_inherits(tmp_path):
    _, project = opened(tmp_path)
    region = {"id": "fg", "role": "foreground", "shape": "rectangle", "xyxy": [0, 0, 1, 1]}
    filename = edits(project, [region])
    result = operations.apply_operation(project, request(project, guide_edits_file=filename))
    trimap = np.array(Image.open(saved_raster(result["trimap_file"])))
    assert trimap[0, 0] == 255 and trimap[1, 2] == 128
    assert json.loads((project / "guides.json").read_text())["regions"] == [region]
    second = operations.apply_operation(project, request(project))
    np.testing.assert_array_equal(np.array(Image.open(saved_raster(second["trimap_file"]))), trimap)
    manifest = json.loads(Path(result["manifest_file"]).read_text())
    assert "edits.json" in manifest["external_inputs"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("developed_id", "0" * 64),
        ("base_revision", "rev-999"),
        ("inputs_digest", "0" * 64),
        ("kind", "shell"),
        ("scope_xyxy", [0, 0, 100, 100]),
        ("unexpected", 1),
    ],
)
def test_invalid_requests_preserve_state(tmp_path, field, value):
    _, project = opened(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.apply_operation(project, request(project, **{field: value}))
    assert (project / "state.json").read_bytes() == before


def test_saved_lock_requires_existing_alpha(tmp_path):
    _, project = create(tmp_path)
    filename = edits(
        project,
        [
            {
                "id": "lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [0, 0, 2, 2],
                "revision": "rev-001",
            }
        ],
    )
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="saved|revision|alpha"):
        operations.apply_operation(project, request(project, guide_edits_file=filename))
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("legacy_status", [None, "review_needed"])
def test_masking_without_development_approval_preserves_source_appearance(tmp_path, legacy_status):
    import hashlib

    import tifffile

    from blackmask.project import load_developed

    source, project = create(tmp_path)
    state = read_project(project)
    if legacy_status is not None:
        state["status"] = legacy_status
        (project / "state.json").write_text(json.dumps(state))
        original_state = (project / "state.json").read_bytes()
        assert read_project(project)["development_approved"] is False
        assert (project / "state.json").read_bytes() == original_state
    master_path = project / "assets/developed" / f"{state['developed_id']}.tif"
    original_source = hashlib.sha256(source.read_bytes()).hexdigest()
    original_master = hashlib.sha256(saved_raster(master_path).read_bytes()).hexdigest()
    master, _ = load_developed(project, state["developed_id"])
    filename = edits(
        project,
        [
            {"id": "flower", "role": "foreground", "shape": "rectangle", "xyxy": [0, 0, 1, 2]},
            {"id": "empty", "role": "background", "shape": "rectangle", "xyxy": [1, 0, 3, 2]},
        ],
    )
    operations.apply_operation(project, request(project, guide_edits_file=filename))
    matte = operations.apply_operation(project, request(project, kind="matte"))
    revision = project / "revisions" / matte["revision"]
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(revision / "foreground_rgb16.tif")), master
    )
    np.testing.assert_array_equal(
        np.array(Image.open(saved_raster(revision / "base_alpha16.png"))),
        np.array([[65535, 0, 0], [65535, 0, 0]], dtype=np.uint16),
    )
    assert read_project(project)["accepted_revision"] is None
    assert not (revision / "trimap_approval.json").exists()
    assert not (project / "approvals").exists()
    effect = operations.apply_operation(
        project,
        request(
            project,
            kind="effects",
            scope_xyxy=[0, 0, 3, 2],
            background={"color_srgb": "#151515", "variation": 0.55},
            candidate_comparison=True,
        ),
    )
    effect_revision = project / "revisions" / effect["revision"]
    assert not (effect_revision / "trimap_approval.json").exists()
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(effect_revision / "foreground_rgb16.tif")), master
    )
    np.testing.assert_array_equal(
        np.array(Image.open(saved_raster(effect_revision / "base_alpha16.png"))),
        np.array(Image.open(saved_raster(revision / "base_alpha16.png"))),
    )
    operations.accept_revision(project, effect["revision"])
    final = read_project(project)
    assert final["accepted_revision"] == effect["revision"]
    assert final["development_approved"] is False
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_source
    assert hashlib.sha256(saved_raster(master_path).read_bytes()).hexdigest() == original_master


def test_low_space_and_publish_failure_preserve_pointer(tmp_path):
    _, project = opened(tmp_path)
    operation = request(project)
    before = (project / "state.json").read_bytes()
    with (
        patch("blackmask.project.shutil.disk_usage", return_value=type("Disk", (), {"free": 1})()),
        pytest.raises(ProjectError, match="space"),
    ):
        operations.apply_operation(project, operation)
    with (
        patch("blackmask.operations._atomic_json", side_effect=OSError("injected")),
        pytest.raises(OSError),
    ):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before
    assert read_project(project)["working_revision"] is None


def test_edits_cannot_read_outside_or_follow_symlink(tmp_path):
    _, project = opened(tmp_path)
    (tmp_path / "outside.json").write_text("{}")
    (project / "alias.json").symlink_to(tmp_path / "outside.json")
    for filename in ["../outside.json", "alias.json", "/etc/passwd"]:
        with pytest.raises(ProjectError):
            operations.apply_operation(project, request(project, guide_edits_file=filename))


def test_guidance_conflict_rejected_before_model_boundary(tmp_path):
    _, project = opened(tmp_path)
    filename = edits(
        project,
        [
            {"id": role, "role": role, "shape": "rectangle", "xyxy": [0, 0, 2, 2]}
            for role in ["foreground", "background"]
        ],
    )
    with (
        patch(
            "blackmask.operations.select_candidates",
            side_effect=AssertionError("inference should not run"),
        ),
        pytest.raises(ProjectError, match="foreground.*background"),
    ):
        operations.apply_operation(project, request(project, guide_edits_file=filename))


@pytest.mark.parametrize("target", ["guides.json", "recipe.toml", "state.json", "edits.json"])
def test_mid_run_text_edit_stops_publication_without_clobber(tmp_path, target):
    _, project = opened(tmp_path)
    filename = edits(project, [])
    before = (project / "state.json").read_bytes()
    changed = b"external editor changed draft"

    def interfere(*args):
        (saved_raster(project / target)).write_bytes(changed)
        return []

    with (
        patch("blackmask.operations.select_candidates", side_effect=interfere),
        pytest.raises(ProjectError, match="Stale|stale"),
    ):
        operations.apply_operation(project, request(project, guide_edits_file=filename))
    assert (saved_raster(project / target)).read_bytes() == changed
    if target != "state.json":
        assert (project / "state.json").read_bytes() == before


def saved_alpha_fixture(project, values):
    # Synthetic downstream boundary: attach a saved uint16 alpha to a complete prepared fixture.
    # This is not matting or final acceptance evidence.

    result = operations.apply_operation(project, request(project))
    directory = Path(result["manifest_file"]).parent
    Image.fromarray(values).save(directory / "base_alpha16.png")
    manifest = json.loads((directory / "manifest.json").read_text())
    bind_raster(project, directory, manifest, "base_alpha16.png")
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return result


def test_preparing_partial_lock_carries_alpha_exact_and_explicit_removal(tmp_path):
    _, project = opened(tmp_path)
    values = np.array([[0, 12345, 65535], [17, 33333, 60000]], dtype=np.uint16)
    first = saved_alpha_fixture(project, values)
    lock = {
        "id": "wing",
        "role": "lock",
        "shape": "rectangle",
        "xyxy": [1, 0, 2, 2],
        "revision": first["revision"],
    }
    filename = edits(project, [lock])
    result = operations.apply_operation(project, request(project, guide_edits_file=filename))
    directory = Path(result["manifest_file"]).parent
    np.testing.assert_array_equal(
        np.array(Image.open(saved_raster(directory / "base_alpha16.png"))), values
    )
    lock_values = np.array(Image.open(saved_raster(directory / "supports/lock_values16.png")))
    assert lock_values[0, 1] == 12345 and lock_values[1, 1] == 33333
    # Root text cannot silently remove a persistent lock without a recorded remove action.
    guides = json.loads((project / "guides.json").read_text())
    guides["regions"] = []
    (project / "guides.json").write_text(json.dumps(guides))
    with pytest.raises(ProjectError, match="remove action"):
        operations.apply_operation(project, request(project))
    guides["regions"] = [lock]
    (project / "guides.json").write_text(json.dumps(guides))
    (project / filename).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "developed_id": first["developed_id"],
                "actions": [{"action": "remove", "id": "wing"}],
            }
        )
    )
    removed = operations.apply_operation(project, request(project, guide_edits_file=filename))
    assert not np.any(np.array(Image.open(saved_raster(removed["protection_file"]))))


def test_midrun_saved_lock_manifest_and_values_change_rejected(tmp_path):

    _, project = opened(tmp_path)
    values = np.array([[0, 12345, 65535], [17, 33333, 60000]], dtype=np.uint16)
    first = saved_alpha_fixture(project, values)
    filename = edits(
        project,
        [
            {
                "id": "lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 2],
                "revision": first["revision"],
            }
        ],
    )
    directory = Path(first["manifest_file"]).parent
    # Make first a non-parent lock dependency so parent recheck alone cannot protect it.
    operations.apply_operation(project, request(project))
    before = (project / "state.json").read_bytes()

    def interfere(*args):
        Image.fromarray(np.zeros_like(values)).save(directory / "base_alpha16.png")
        manifest = json.loads((directory / "manifest.json").read_text())
        bind_raster(project, directory, manifest, "base_alpha16.png")
        (directory / "manifest.json").write_text(json.dumps(manifest))
        return []

    with (
        patch("blackmask.operations.select_candidates", side_effect=interfere),
        pytest.raises(ProjectError, match="Stale|stale"),
    ):
        operations.apply_operation(project, request(project, guide_edits_file=filename))
    assert (project / "state.json").read_bytes() == before


def test_request_file_mutation_rejected_and_original_bytes_snapshotted(tmp_path):
    _, project = opened(tmp_path)
    operation = request(project)
    path = project / "request.json"
    path.write_text(json.dumps(operation, indent=4))

    def interfere(*args):
        path.write_text("{}")
        return []

    with (
        patch("blackmask.operations.select_candidates", side_effect=interfere),
        pytest.raises(ProjectError, match="Stale request"),
    ):
        operations.apply_operation(project, operation, request_file=path)
    assert read_project(project)["working_revision"] is None
    path.write_text(json.dumps(operation, indent=4))
    result = operations.apply_operation(project, operation, request_file=path)
    directory = Path(result["manifest_file"]).parent
    assert (directory / "request.json").read_bytes() == saved_raster(path).read_bytes()
    assert (directory / "result.json").is_file()


def test_real_process_busy_and_killed_prepare_preserves_working_state(tmp_path):
    import os
    import subprocess
    import sys

    _, project = opened(tmp_path)
    first = operations.apply_operation(project, request(project))
    before = (project / "state.json").read_bytes()
    operation = request(project)
    code = """import sys,json
from pathlib import Path
from blackmask import operations
def pause(*args):
    print('model-boundary',flush=True)
    sys.stdin.readline()
    return []
operations.select_candidates=pause
operations.apply_operation(Path(sys.argv[1]),json.loads(sys.argv[2]))
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(project), json.dumps(operation)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
    )
    try:
        assert process.stdout.readline().strip() == "model-boundary"
        assert read_project(project)["working_revision"] == first["revision"]
        with pytest.raises(ProjectError, match="busy"):
            operations.apply_operation(project, operation)
        process.kill()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert process.returncode < 0 and (project / "state.json").read_bytes() == before
    second = operations.apply_operation(project, operation)
    assert second["parent"] == first["revision"]


def test_selected_group_candidates_are_membership_only(tmp_path):
    import tomllib

    import tomli_w

    from blackmask.models import Candidates

    _, project = opened(tmp_path)
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["groups"] = [
        {"id": "wing", "keep": True, "material_policy": "unknown_interior", "selected_candidate": 1}
    ]
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    filename = edits(
        project,
        [{"id": "hint", "role": "keep", "shape": "point", "xy": [1, 1], "group_id": "wing"}],
    )
    masks = np.array(
        [[[0, 0, 0], [0, 0, 0]], [[0, 1, 0], [0, 1, 0]], [[1, 1, 1], [1, 1, 1]]], dtype=bool
    )
    # Expensive inference boundary alone is stubbed; saving, selection and trimap are real.
    prediction = Candidates(
        masks, np.array([0.1, 0.2, 0.3], dtype=np.float32), {"evidence": "stub-only"}
    )
    with patch("blackmask.operations.SamSession") as session:
        session.return_value.select.return_value = prediction
        result = operations.apply_operation(
            project,
            request(project, guide_edits_file=filename),
            model_cache=Path("unused-stub-cache"),
        )
    assert [c["id"] for c in result["candidates"]] == ["wing-0", "wing-1", "wing-2"]
    directory = Path(result["manifest_file"]).parent
    assert np.all(np.array(Image.open(saved_raster(result["trimap_file"]))) == 128)
    np.testing.assert_array_equal(
        np.array(Image.open(saved_raster(directory / "selected_membership.png"))), masks[1] * 255
    )


def test_corrupt_prepared_revision_is_not_reused(tmp_path):
    _, project = opened(tmp_path)
    first = operations.apply_operation(project, request(project))
    saved_raster(Path(first["trimap_file"])).write_bytes(b"broken")
    with pytest.raises(ProjectError, match="hash"):
        read_project(project)


@pytest.mark.parametrize("target", ["guides.json", "state.json"])
def test_identity_check_binds_actual_captured_bytes(tmp_path, target):
    from blackmask import operations as module

    _, project = opened(tmp_path)
    operation = request(project)
    before = (project / "state.json").read_bytes()
    if target == "guides.json":
        changed = json.loads((saved_raster(project / target)).read_bytes())
        changed["regions"] = [{"id": "late", "role": "background", "shape": "point", "xy": [0, 0]}]
    else:
        changed = json.loads(before)
        changed.update(development_approved=False, status="review_needed")
    changed_bytes = json.dumps(changed).encode()
    original = module.saved_asset
    state_reads = 0

    def change_at_capture(root, name):
        nonlocal state_reads
        if root == project and name == "state.json":
            state_reads += 1
            if state_reads == 1:
                (saved_raster(project / target)).write_bytes(changed_bytes)
        return original(root, name)

    with (
        patch("blackmask.operations.saved_asset", side_effect=change_at_capture),
        pytest.raises(ProjectError, match="Stale|stale"),
    ):
        operations.apply_operation(project, operation)
    assert (saved_raster(project / target)).read_bytes() == changed_bytes
    if target != "state.json":
        assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("target", ["guides.json", "recipe.toml", "state.json", "edits.json"])
def test_edit_during_final_revision_validation_preserved(tmp_path, target):
    _, project = opened(tmp_path)
    filename = edits(project, [{"id": "fg", "role": "foreground", "shape": "point", "xy": [0, 0]}])
    operation = request(project, guide_edits_file=filename)
    before = (project / "state.json").read_bytes()
    changed = b"editor saved late boundary bytes"
    original = operations.read_revision

    def change_after_validation(root, revision, developed_id):
        manifest = original(root, revision, developed_id)
        if revision == "rev-001":
            (saved_raster(project / target)).write_bytes(changed)
        return manifest

    with (
        patch("blackmask.operations.read_revision", side_effect=change_after_validation),
        pytest.raises(ProjectError, match="Stale|stale"),
    ):
        operations.apply_operation(project, operation)
    assert (saved_raster(project / target)).read_bytes() == changed
    if target != "state.json":
        assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("replacement", ["guides.json", "state.json"])
def test_edit_at_atomic_replacement_boundary_preserved(tmp_path, replacement):
    _, project = opened(tmp_path)
    filename = edits(project, [{"id": "fg", "role": "foreground", "shape": "point", "xy": [0, 0]}])
    operation = request(project, guide_edits_file=filename)
    before = (project / "state.json").read_bytes()
    changed = b"newer guide bytes saved while atomic replacement is preparing"
    original = operations._atomic_json

    def editor_save(path, value, **kwargs):
        if path.name == replacement:
            (project / "guides.json").write_bytes(changed)
        return original(path, value, **kwargs)

    with (
        patch("blackmask.operations._atomic_json", side_effect=editor_save),
        pytest.raises(ProjectError, match="Stale|stale"),
    ):
        operations.apply_operation(project, operation)
    assert (project / "guides.json").read_bytes() == changed
    assert (project / "state.json").read_bytes() == before


def test_prepare_saves_opt_in_selected_native_proposal_without_forcing_trimap(tmp_path):
    import tomllib

    import tomli_w

    from blackmask.models import Candidates

    _, project = opened(tmp_path)
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["groups"] = [
        {
            "id": "body",
            "keep": True,
            "material_policy": "opaque_core",
            "selected_candidate": 1,
            "morphology": {"foreground_erosion_px": 0, "unknown_dilation_px": 0},
        }
    ]
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    filename = edits(
        project,
        [{"id": "hint", "role": "keep", "shape": "point", "xy": [1, 1], "group_id": "body"}],
    )
    masks = np.array(
        [[[0, 0, 0], [0, 0, 0]], [[0, 1, 0], [0, 1, 0]], [[1, 1, 1], [1, 1, 1]]], dtype=bool
    )
    prediction = Candidates(
        masks, np.array([0.1, 0.2, 0.3], dtype=np.float32), {"evidence": "stub-only"}
    )
    with patch("blackmask.operations.SamSession") as session:
        session.return_value.select.return_value = prediction
        result = operations.apply_operation(
            project,
            request(project, guide_edits_file=filename),
            model_cache=Path("unused-stub-cache"),
        )
    directory = Path(result["manifest_file"]).parent
    assert np.all(np.array(Image.open(saved_raster(result["trimap_file"]))) == 128)
    expected = np.array([[128, 255, 128], [128, 255, 128]], dtype=np.uint8)
    np.testing.assert_array_equal(
        np.array(Image.open(saved_raster(result["trimap_proposal_file"]))), expected
    )
    saved = tomllib.loads((directory / "recipe.toml").read_text())
    assert saved["groups"][0]["morphology"] == {
        "foreground_erosion_px": 0,
        "unknown_dilation_px": 0,
    }
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["proposal"]["review_status"] == "unreviewed"
    assert manifest["proposal"]["groups"][0]["candidate_id"] == "body-1"
    assert (
        result["final_acceptable"] is False and read_project(project)["accepted_revision"] is None
    )


@pytest.mark.parametrize(
    "morphology",
    [
        {"foreground_erosion_px": True, "unknown_dilation_px": 1},
        {"foreground_erosion_px": -1, "unknown_dilation_px": 1},
        {"foreground_erosion_px": 1},
        {"foreground_erosion_px": 1, "unknown_dilation_px": 1, "unexpected": 1},
    ],
)
def test_invalid_morphology_settings_reject_without_state_change(tmp_path, morphology):
    import tomllib

    import tomli_w

    _, project = opened(tmp_path)
    operation = request(project)
    before = (project / "state.json").read_bytes()
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["groups"] = [
        {
            "id": "body",
            "keep": True,
            "material_policy": "opaque_core",
            "selected_candidate": 1,
            "morphology": morphology,
        }
    ]
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    with pytest.raises(ProjectError, match="morphology"):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


def test_proposal_partial_lock_failure_preserves_saved_alpha_and_state(tmp_path):
    import tomllib

    import tomli_w

    from blackmask.models import Candidates

    _, project = opened(tmp_path)
    values = np.array([[0, 12345, 65535], [17, 33333, 60000]], dtype=np.uint16)
    first = saved_alpha_fixture(project, values)
    directory = Path(first["manifest_file"]).parent
    before_alpha = (saved_raster(directory / "base_alpha16.png")).read_bytes()
    before_state = (project / "state.json").read_bytes()
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["groups"] = [
        {
            "id": "body",
            "keep": True,
            "material_policy": "opaque_core",
            "selected_candidate": 1,
            "morphology": {"foreground_erosion_px": 0, "unknown_dilation_px": 0},
        }
    ]
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    filename = edits(
        project,
        [
            {"id": "hint", "role": "keep", "shape": "point", "xy": [1, 1], "group_id": "body"},
            {
                "id": "lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 2],
                "revision": first["revision"],
            },
        ],
    )
    masks = np.zeros((3, 2, 3), dtype=bool)
    masks[1, :, 1] = True
    prediction = Candidates(
        masks, np.array([0.1, 0.2, 0.3], dtype=np.float32), {"evidence": "stub-only"}
    )
    with patch("blackmask.operations.SamSession") as session:
        session.return_value.select.return_value = prediction
        with pytest.raises(ProjectError, match="lock"):
            operations.apply_operation(
                project,
                request(project, guide_edits_file=filename),
                model_cache=Path("unused-stub-cache"),
            )
    assert (saved_raster(directory / "base_alpha16.png")).read_bytes() == before_alpha
    assert (project / "state.json").read_bytes() == before_state
