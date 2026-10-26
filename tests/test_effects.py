"""Synthetic color-cleanup arithmetic and saved-operation contracts; no photo preference claims."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_ingest import bind_raster, native_review_directories, saved_raster, srgb_profile, tiff
from test_matte_operations import approve, run_matte
from test_operations import edits, request

from blackmask import operations
from blackmask.export import export_project, saved_layers
from blackmask.project import ProjectError, accept_development, create_project, read_project


def fixture_project(tmp_path):
    source = np.full((4, 6, 3), [20000, 30000, 40000], dtype=np.uint16)
    source[:, 0] = [10000, 20000, 30000]
    project = tmp_path / "project"
    create_project(tiff(tmp_path / "source.tif", source, profile=srgb_profile()), project, {})
    accept_development(project, read_project(project)["developed_id"])
    name = edits(
        project,
        [
            {"id": "empty", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 4]},
            {"id": "solid", "role": "foreground", "shape": "rectangle", "xyxy": [5, 0, 6, 4]},
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    parent = run_matte(project)
    operations.accept_revision(project, parent["revision"])
    return project, source, parent


def effect_request(project, *, enabled=True, strength=0.35, scope=None, support=None, **extra):
    shape = (4, 6)
    if scope is None:
        scope = [1, 0, 5, 4]
    if support is None:
        support = np.zeros(shape, dtype=np.uint16)
        x0, y0, x1, y1 = scope
        support[y0:y1, x0:x1] = 65535
    Image.fromarray(support).save(project / "cleanup-support.png")
    return request(
        project,
        kind="effects",
        scope_xyxy=scope,
        color_cleanup={"enabled": enabled, "strength": strength},
        support_file="cleanup-support.png",
        candidate_comparison=extra.pop("candidate_comparison", False),
        **extra,
    )


def test_cleanup_independent_inverse_mixture_preserves_all_excluded_samples():
    from blackmask.effects import make_corrected_rgb

    source = np.full((1, 6, 3), 30000, dtype=np.uint16)
    source[0, 0] = 10000
    alpha = np.array([[0, 21845, 65535, 21845, 21845, 21845]], dtype=np.uint16)
    support = np.array([[65535, 65535, 65535, 65535, 0, 32768]], dtype=np.uint16)
    protection = np.array([[False, False, False, True, False, False]])
    result = make_corrected_rgb(
        source,
        alpha,
        support,
        {"enabled": True, "strength": 0.75},
        known_empty=alpha == 0,
        protection=protection,
    )
    # amount=.75*(1-1/3)=.5; (30000-.5*10000)/.5=50000.
    assert np.all(result[0, 1] == 50000)
    # Half support uses exact stored 32768/65535, not a nominal .5.
    assert np.all(result[0, 5] == 36667)
    np.testing.assert_array_equal(result[0, [0, 2, 3, 4]], source[0, [0, 2, 3, 4]])
    for settings in ({"enabled": False, "strength": 0.75}, {"enabled": True, "strength": 0.0}):
        np.testing.assert_array_equal(
            make_corrected_rgb(
                source, alpha, support, settings, known_empty=alpha == 0, protection=protection
            ),
            source,
        )


def test_public_effects_saved_precision_no_compounding_and_disable(tmp_path):
    project, _source, _parent = fixture_project(tmp_path)
    base, alpha, _ = saved_layers(
        project, _parent["revision"], read_project(project)["developed_id"]
    )
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("No model")):
        result = operations.apply_operation(project, effect_request(project))
        rgb, actual_alpha, manifest = saved_layers(
            project, result["revision"], read_project(project)["developed_id"]
        )
        assert manifest["kind"] == "effects"
        assert np.any(rgb != _source)
        np.testing.assert_array_equal(actual_alpha, alpha)
        directory = project / "revisions" / result["revision"]
        np.testing.assert_array_equal(
            tifffile.imread(saved_raster(directory / "corrected_rgb16.tif")), rgb
        )
        np.testing.assert_array_equal(
            tifffile.imread(saved_raster(directory / "foreground_rgb16.tif")), base
        )
        again = operations.apply_operation(
            project, effect_request(project, candidate_comparison=True)
        )
        np.testing.assert_array_equal(
            saved_layers(project, again["revision"], read_project(project)["developed_id"])[0], rgb
        )
        disabled = operations.apply_operation(project, effect_request(project, enabled=False))
        np.testing.assert_array_equal(
            saved_layers(project, disabled["revision"], read_project(project)["developed_id"])[0],
            _source,
        )
    assert read_project(project)["accepted_revision"] == _parent["revision"]


def test_effect_requires_accepted_base_or_explicit_candidate_and_rejects_stale(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, effect_request(project))
    old = effect_request(project)
    with pytest.raises(ProjectError, match="accepted.*base|candidate"):
        operations.apply_operation(project, old)
    operations.accept_revision(project, result["revision"])
    repeated = operations.apply_operation(project, effect_request(project))
    assert repeated["reused"] and repeated["revision"] == result["revision"]
    changed = operations.apply_operation(project, effect_request(project, strength=0.5))
    assert changed["reused"] is False and changed["revision"] != result["revision"]
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, old)


def test_cleanup_repair_stale_block_scoped_rebuild_and_exact_locks(tmp_path):
    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair

    from blackmask.review import review_project

    project, _source, _parent = fixture_project(tmp_path)
    accepted = export_project(project, variants=("black", "transparent", "editable"))
    accepted_bytes = {p.name: p.read_bytes() for p in Path(accepted["directory"]).iterdir()}
    first = operations.apply_operation(project, effect_request(project))
    operations.accept_revision(project, first["revision"])
    old_rgb, old_alpha, _ = saved_layers(
        project, first["revision"], read_project(project)["developed_id"]
    )
    lock = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": first["revision"],
            }
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=lock))
    approve(project, prepared)
    prepared = repair_guides(project, [1, 1, 4, 3])
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        repaired = run_repair(
            project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3])
        )
    _rgb, alpha, manifest = saved_layers(
        project, repaired["revision"], read_project(project)["developed_id"]
    )
    assert manifest["color_cleanup"]["stale"] is True
    assert read_project(project)["latest_result_revision"] == first["revision"]
    assert np.any(alpha != old_alpha)
    np.testing.assert_array_equal(alpha[1, 2], old_alpha[1, 2])
    for name in ("review", "review-before"):
        review = json.loads(
            (project / "revisions" / repaired["revision"] / name / "manifest.json").read_bytes()
        )
        assert "cleanup OFF" in review["label"]
    reviewed = json.loads(saved_raster(Path(review_project(project)["manifest_file"])).read_bytes())
    assert "cleanup_stale" in reviewed["stale_labels"]
    assert reviewed["settings"]["color_cleanup"] == {"enabled": True, "strength": 0.35}
    assert reviewed["effects"]["color_cleanup"]["stale"] is True
    assert (
        reviewed["assets"]["foreground_rgb16"] == manifest["assets"]["foreground_rgb16.tif"]["path"]
    )
    with pytest.raises(ProjectError, match="Stale.*cleanup"):
        operations.accept_revision(project, repaired["revision"])
    with pytest.raises(ProjectError, match="Stale.*cleanup"):
        export_project(
            project,
            revision=repaired["revision"],
            draft=True,
            variants=("black", "transparent", "editable"),
        )
    rebuilt = operations.apply_operation(
        project, effect_request(project, scope=[1, 1, 4, 3], candidate_comparison=True)
    )
    new_rgb, new_alpha, manifest = saved_layers(
        project, rebuilt["revision"], read_project(project)["developed_id"]
    )
    assert manifest["color_cleanup"]["stale"] is False
    assert read_project(project)["latest_result_revision"] == rebuilt["revision"]
    outside = np.ones(alpha.shape, bool)
    outside[1:3, 1:4] = False
    assert np.any((old_alpha[outside] > 0) & (old_alpha[outside] < 65535))
    np.testing.assert_array_equal(new_rgb[outside], old_rgb[outside])
    np.testing.assert_array_equal(new_rgb[1, 2], old_rgb[1, 2])
    np.testing.assert_array_equal(new_alpha, alpha)
    operations.accept_revision(project, rebuilt["revision"])
    exported = export_project(project, variants=("black", "transparent", "editable"))
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(Path(exported["directory"]) / "black_rgb16.tif")),
        np.rint(new_rgb.astype(np.float64) * (alpha.astype(np.float64) / 65535)[..., None]).astype(
            np.uint16
        ),
    )
    for name, data in accepted_bytes.items():
        assert (saved_raster(Path(accepted["directory"]) / name)).read_bytes() == data
    operations.restore_revision(project, first["revision"], replace_drafts=True)
    assert read_project(project)["accepted_revision"] == rebuilt["revision"]


def test_partial_rebuild_keeps_remaining_alpha_dependencies_stale(tmp_path):
    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, effect_request(project))
    prepared = repair_guides(project, [1, 1, 4, 3])
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3]))
    rebuilt = operations.apply_operation(
        project, effect_request(project, scope=[1, 1, 2, 2], candidate_comparison=True)
    )
    assert rebuilt["color_cleanup"]["stale"] is True
    disabled = operations.apply_operation(project, effect_request(project, enabled=False))
    assert disabled["color_cleanup"]["enabled"] is False
    operations.accept_revision(project, disabled["revision"])
    export_project(project)


def test_viewer_and_cli_share_effects_and_saved_comparison_mode(tmp_path):
    import subprocess
    import sys

    from blackmask.viewer import ReviewServer

    project, _source, _parent = fixture_project(tmp_path)
    operation = effect_request(project)
    filename = project / "effects-request.json"
    filename.write_text(json.dumps(operation))
    completed = subprocess.run(
        [sys.executable, "-m", "blackmask", "run", str(project), "--request", str(filename)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    server = ReviewServer(project)
    try:
        state = server.snapshot()
        current = next(r for r in state["revisions"] if r["revision"] == result["revision"])
        assert current["color_cleanup"]["enabled"] is True
        path = f"/image/black/{result['revision']}/0,0,6,4"
        assert server.image(path) != server.image(path + "/base")
        identity = {k: state[k] for k in ("developed_id", "inputs_digest", "authoring_digest")}
        identity.update(
            base_revision=state["working_revision"],
            action="effects",
            scope_xyxy=[1, 0, 5, 4],
            support_file="cleanup-support.png",
            color_cleanup={"enabled": False, "strength": 0.35},
            candidate_comparison=False,
        )
        disabled = server.execute(identity)
        assert disabled["color_cleanup"]["enabled"] is False
    finally:
        server.server_close()


@pytest.mark.parametrize(
    "field,value", [("strength", float("nan")), ("strength", 1.1), ("enabled", 1)]
)
def test_invalid_cleanup_settings_preserve_state(tmp_path, field, value):
    project, _, _ = fixture_project(tmp_path)
    operation = effect_request(project)
    operation["color_cleanup"][field] = value
    before = (project / "state.json").read_bytes()
    with pytest.raises((ProjectError, ValueError)):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("shading", [False, True])
def test_interrupted_effect_pointer_retains_complete_assets_and_explicit_restore(tmp_path, shading):
    project, _, _parent = fixture_project(tmp_path)
    operation = shading_request(project) if shading else effect_request(project)
    original = operations._atomic_json
    from blackmask import effects

    def interrupted(path, *args, **kwargs):
        if path.name == "state.json":
            raise OSError("Synthetic interrupted pointer")
        return original(path, *args, **kwargs)

    with (
        patch.object(effects, "_atomic_json", interrupted),
        pytest.raises(OSError, match="interrupted"),
    ):
        operations.apply_operation(project, operation)
    assert read_project(project)["working_revision"] == _parent["revision"]
    assert read_project(project)["accepted_revision"] == _parent["revision"]
    revision = max((project / "revisions").glob("rev-*")).name
    saved_layers(project, revision, read_project(project)["developed_id"])
    operations.restore_revision(project, revision, replace_drafts=True)
    assert read_project(project)["working_revision"] == revision
    assert read_project(project)["accepted_revision"] == _parent["revision"]


def test_cleanup_support_mutation_before_publish_rejects_state_change(tmp_path):
    project, _, _parent = fixture_project(tmp_path)
    operation = effect_request(project)
    from blackmask import effects

    original = effects.make_corrected_rgb

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        Image.fromarray(np.zeros((4, 6), np.uint16)).save(project / "cleanup-support.png")
        return result

    with (
        patch.object(effects, "make_corrected_rgb", changing),
        pytest.raises(ProjectError, match="Stale"),
    ):
        operations.apply_operation(project, operation)
    assert read_project(project)["working_revision"] == _parent["revision"]


def test_effects_consumes_editable_recipe_settings_without_override(tmp_path):
    import tomllib

    import tomli_w

    project, _, _ = fixture_project(tmp_path)
    value = tomllib.loads((project / "recipe.toml").read_text())
    value["color_cleanup"] = {"enabled": True, "strength": 0.5}
    (project / "recipe.toml").write_text(tomli_w.dumps(value))
    operation = effect_request(project)
    operation.pop("color_cleanup")
    result = operations.apply_operation(project, operation)
    assert result["color_cleanup"]["strength"] == 0.5
    assert result["color_cleanup"]["enabled"] is True
    from blackmask.review import review_project

    reviewed = json.loads(saved_raster(Path(review_project(project)["manifest_file"])).read_bytes())
    assert "draft_changed" not in reviewed["stale_labels"]
    operations.accept_revision(project, result["revision"])
    original_recipe = (project / "recipe.toml").read_bytes()
    operations.restore_revision(project, result["parent"], replace_drafts=True)
    operations.restore_revision(project, result["revision"], replace_drafts=True)
    assert (project / "recipe.toml").read_bytes() == original_recipe
    assert read_project(project)["accepted_revision"] == result["revision"]


def test_corrected_profile_validation_and_dependency_identity(tmp_path):

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, effect_request(project))
    directory = project / "revisions" / result["revision"]
    rgb = tifffile.imread(saved_raster(directory / "corrected_rgb16.tif"))
    tifffile.imwrite(directory / "corrected_rgb16.tif", rgb, photometric="rgb", metadata=None)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    bind_raster(project, directory, manifest, "corrected_rgb16.tif")
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="profile"):
        saved_layers(project, result["revision"], read_project(project)["developed_id"])


def test_effect_cli_respects_actual_writer_lock(tmp_path):
    import subprocess
    import sys

    from blackmask.project import project_lock

    project, _, _ = fixture_project(tmp_path)
    filename = project / "effects-request.json"
    filename.write_text(json.dumps(effect_request(project)))
    before = (project / "state.json").read_bytes()
    with project_lock(project):
        result = subprocess.run(
            [sys.executable, "-m", "blackmask", "run", str(project), "--request", str(filename)],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    assert result.returncode != 0
    assert "busy" in result.stderr.lower()
    assert (project / "state.json").read_bytes() == before


def test_explicit_disable_works_with_empty_current_guide_support(tmp_path):
    project, source, _ = fixture_project(tmp_path)
    operations.apply_operation(project, effect_request(project))
    result = operations.apply_operation(
        project, effect_request(project, enabled=False, support=np.zeros((4, 6), np.uint16))
    )
    rgb, _, _ = saved_layers(project, result["revision"], read_project(project)["developed_id"])
    np.testing.assert_array_equal(rgb, source)


@pytest.mark.parametrize("enabled,strength", [(True, 0.7), (False, 0.6), (True, 0.0)])
@pytest.mark.parametrize("inherited", [False, True])
def test_review_manifest_reports_effective_cleanup_and_preserves_consumed_recipe(
    tmp_path, enabled, strength, inherited
):
    import tomllib

    from blackmask.operations import draft_digest
    from blackmask.review import review_project

    project, _, _ = fixture_project(tmp_path)
    recipe_bytes = (project / "recipe.toml").read_bytes()
    original_digest = draft_digest(project)
    assert tomllib.loads(recipe_bytes.decode())["color_cleanup"]["enabled"] is False
    result = operations.apply_operation(
        project, effect_request(project, enabled=enabled, strength=strength)
    )
    effective_recipe_bytes = (project / "recipe.toml").read_bytes()
    assert (
        project / "revisions" / result["revision"] / "inputs/recipe.toml"
    ).read_bytes() == recipe_bytes
    effective_digest = draft_digest(project)
    saved_review = json.loads(
        (project / "revisions" / result["revision"] / "review/manifest.json").read_bytes()
    )
    assert saved_review["color_cleanup"]["strength"] == strength
    assert ("cleanup ON" if enabled and strength != 0 else "cleanup OFF") in saved_review["label"]
    if inherited:
        prepared = operations.apply_operation(project, request(project))
        approve(project, prepared)
        result = run_matte(project)
    directory = project / "revisions" / result["revision"]
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    record = json.loads(saved_raster(Path(review_project(project)["manifest_file"])).read_bytes())
    effective = enabled and strength != 0
    assert record["settings"]["color_cleanup"] == {"enabled": effective, "strength": strength}
    assert record["effects"]["color_cleanup"]["enabled"] is effective
    assert record["effects"]["color_cleanup"]["stale"] is False
    assert "cleanup_stale" not in record["stale_labels"]
    foreground = "corrected_rgb16.tif" if effective else "foreground_rgb16.tif"
    assert record["assets"]["foreground_rgb16"] == manifest["assets"][foreground]["path"]
    assert record["revision_inputs_digest"] == manifest["draft_digest"] == effective_digest
    assert draft_digest(project) == effective_digest
    assert manifest["inputs_digest"] == (effective_digest if inherited else original_digest)
    assert (project / "recipe.toml").read_bytes() == effective_recipe_bytes
    assert (directory / "recipe.toml").read_bytes() == effective_recipe_bytes
    assert (directory / "manifest.json").read_bytes() == manifest_bytes


@pytest.mark.parametrize("strength", [None, True, -0.1, 1.1])
def test_review_rejects_invalid_saved_cleanup_strength(tmp_path, strength):
    from blackmask.review import review_project

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, effect_request(project))
    manifest_file = project / "revisions" / result["revision"] / "manifest.json"
    manifest = json.loads(saved_raster(manifest_file).read_bytes())
    manifest["color_cleanup"]["strength"] = strength
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="Cleanup requires"):
        review_project(project)
    assert not (saved_raster(project / "reviews" / result["revision"])).exists()


@pytest.mark.parametrize("repairing", [False, True])
def test_same_alpha_rgb_lock_survives_inherited_cleanup_and_export(tmp_path, repairing):
    from test_repair_operations import repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    earlier = operations.apply_operation(project, effect_request(project, strength=0.35))
    operations.accept_revision(project, earlier["revision"])
    newer = operations.apply_operation(project, effect_request(project, strength=0.75))
    operations.accept_revision(project, newer["revision"])
    before_rgb, before_alpha, _ = saved_layers(
        project, newer["revision"], read_project(project)["developed_id"]
    )
    expected = np.array([23559, 33559, 43559], np.uint16)
    assert not np.array_equal(before_rgb[1, 2], expected)
    name = edits(
        project,
        [
            {
                "id": "partial-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": earlier["revision"],
            },
            {
                "id": "repair-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 1, 4, 3],
                "feather_px": 0,
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    result = (
        run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3]))
        if repairing
        else run_matte(project)
    )
    rgb, alpha, manifest = saved_layers(
        project, result["revision"], read_project(project)["developed_id"]
    )
    np.testing.assert_array_equal(alpha, before_alpha)
    assert manifest["color_cleanup"]["stale"] is False
    np.testing.assert_array_equal(rgb[1, 2], expected)
    unchanged = np.ones(alpha.shape, bool)
    unchanged[1, 2] = False
    np.testing.assert_array_equal(rgb[unchanged], before_rgb[unchanged])
    operations.accept_revision(project, result["revision"])
    exported = export_project(project, variants=("black", "transparent", "editable"))
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(Path(exported["directory"]) / "black_rgb16.tif"))[1, 2],
        [5890, 8390, 10890],
    )


def test_first_and_reenabled_cleanup_preserve_outside_support_rgb_lock(tmp_path):
    project, _, base = fixture_project(tmp_path)
    effect = operations.apply_operation(project, effect_request(project))
    operations.restore_revision(project, base["revision"], replace_drafts=True)
    name = edits(
        project,
        [
            {
                "id": "partial-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": effect["revision"],
            }
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    parent = run_matte(project)
    operations.accept_revision(project, parent["revision"])
    before_rgb, alpha, _ = saved_layers(
        project, parent["revision"], read_project(project)["developed_id"]
    )
    assert alpha[1, 2] == 16384
    np.testing.assert_array_equal(before_rgb[1, 2], [23559, 33559, 43559])
    outside = np.ones(alpha.shape, bool)
    outside[:, 3:5] = False
    for _ in range(2):
        result = operations.apply_operation(
            project, effect_request(project, scope=[3, 0, 5, 4], candidate_comparison=True)
        )
        rgb, _, _ = saved_layers(project, result["revision"], read_project(project)["developed_id"])
        np.testing.assert_array_equal(rgb[outside], before_rgb[outside])
        operations.accept_revision(project, result["revision"])
        exported = export_project(project, variants=("black", "transparent", "editable"))
        np.testing.assert_array_equal(
            tifffile.imread(saved_raster(Path(exported["directory"]) / "black_rgb16.tif"))[1, 2],
            [5890, 8390, 10890],
        )
        operations.apply_operation(project, effect_request(project, enabled=False))


def test_noop_alpha_repair_compares_matching_enabled_cleanup(tmp_path):
    from test_repair_operations import repair_guides, repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, effect_request(project))
    prepared = repair_guides(project, [1, 1, 4, 3])
    result = run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3]))
    directory = project / "revisions" / result["revision"]
    np.testing.assert_array_equal(
        saved_layers(project, first["revision"], read_project(project)["developed_id"])[1],
        saved_layers(project, result["revision"], read_project(project)["developed_id"])[1],
    )
    native = native_review_directories(project, result["revision"])
    for panel in ("black", "gray", "white"):
        before = np.array(Image.open(native["review-before"] / f"crop-000-{panel}_RGB8_VIEW.png"))
        after = np.array(Image.open(native["review"] / f"crop-000-{panel}_RGB8_VIEW.png"))
        np.testing.assert_array_equal(before, after)
    for name in ("review-before", "review"):
        record = json.loads((directory / name / "manifest.json").read_bytes())
        assert "cleanup ON" in record["label"]


@pytest.mark.parametrize("change", ["guides", "matting", "groups"])
def test_effect_recipe_snapshot_does_not_accept_unprepared_mask_changes(tmp_path, change):
    import tomllib

    import tomli_w

    project, _, _ = fixture_project(tmp_path)
    if change == "guides":
        guides = json.loads((project / "guides.json").read_bytes())
        guides["regions"].append(
            {"id": "unprepared", "role": "background", "shape": "rectangle", "xyxy": [2, 1, 3, 2]}
        )
        (project / "guides.json").write_text(json.dumps(guides))
    else:
        recipe = tomllib.loads((project / "recipe.toml").read_text())
        if change == "matting":
            recipe["matting"]["device"] = "cpu"
        else:
            recipe["groups"] = [{"id": "new", "keep": True, "material_policy": "unknown_interior"}]
        (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="Changed guidance/base recipe.*prepare"):
        operations.apply_operation(project, effect_request(project))
    assert (project / "state.json").read_bytes() == before


def test_cleanup_keeps_legacy_saved_prepared_layer_rgb_locks_compatible(tmp_path):
    project, _, base = fixture_project(tmp_path)
    earlier = operations.apply_operation(project, effect_request(project))
    inherited = operations.apply_operation(project, request(project))
    operations.restore_revision(project, base["revision"], replace_drafts=True)
    name = edits(
        project,
        [
            {
                "id": "prepared-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": inherited["revision"],
            }
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    result = run_matte(project)
    operations.accept_revision(project, result["revision"])
    cleanup = operations.apply_operation(project, effect_request(project))
    rgb, _, _ = saved_layers(project, cleanup["revision"], read_project(project)["developed_id"])
    expected = saved_layers(project, earlier["revision"], read_project(project)["developed_id"])[0][
        1, 2
    ]
    np.testing.assert_array_equal(rgb[1, 2], expected)


@pytest.mark.parametrize("change_alpha", [False, True])
def test_current_appearance_rgb_lock_outside_repair_support_preserves_saved_layers(
    tmp_path, change_alpha
):
    from test_matte_operations import StubSession
    from test_repair_operations import repair_request, run_repair

    from blackmask.repair import replay_repair

    project, _source, _base = fixture_project(tmp_path)
    first = operations.apply_operation(project, effect_request(project))
    operations.accept_revision(project, first["revision"])
    accepted = export_project(project, variants=("black", "transparent", "editable"))
    accepted_bytes = {p.name: p.read_bytes() for p in Path(accepted["directory"]).iterdir()}
    master_bytes = (
        saved_raster(project / "assets/developed" / f"{read_project(project)['developed_id']}.tif")
    ).read_bytes()
    parent_rgb, parent_alpha, _ = saved_layers(
        project, first["revision"], read_project(project)["developed_id"]
    )
    name = edits(
        project,
        [
            {
                "id": "outside-current-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 1, 2, 2],
                "revision": first["revision"],
            },
            {
                "id": "repair-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [3, 1, 5, 3],
                "feather_px": 0,
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (
            np.full(guide.shape, 0.75 if change_alpha else 0.25),
            {},
        ),
    ):
        repaired = run_repair(
            project, repair_request(project, prepared, [0, 0, 6, 4], [3, 1, 5, 3])
        )
    directory = project / "revisions" / repaired["revision"]
    rgb, alpha, manifest = saved_layers(
        project, repaired["revision"], read_project(project)["developed_id"]
    )
    np.testing.assert_array_equal(replay_repair(project, repaired["revision"]), alpha)
    np.testing.assert_array_equal(rgb[1, 1], parent_rgb[1, 1])
    if not change_alpha:
        unchanged = np.ones(alpha.shape, bool)
        unchanged[1:3, 3:5] = False
        np.testing.assert_array_equal(rgb[unchanged], parent_rgb[unchanged])
    outside = np.ones(alpha.shape, bool)
    outside[1:3, 3:5] = False
    np.testing.assert_array_equal(alpha[outside], parent_alpha[outside])
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(directory / "corrected_rgb16.tif"))[outside],
        parent_rgb[outside],
    )
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(directory / "foreground_rgb16.tif"))[1, 1],
        [23559, 33559, 43559],
    )
    assert read_project(project)["accepted_revision"] == first["revision"]
    assert (
        saved_raster(project / "assets/developed" / f"{read_project(project)['developed_id']}.tif")
    ).read_bytes() == master_bytes
    assert manifest["color_cleanup"]["stale"] is change_alpha
    if change_alpha:
        native = native_review_directories(project, repaired["revision"])
        # Both panels are honestly labelled base layers, including the explicit saved lock.
        for panel_name, base_revision in (
            ("review-before", prepared["revision"]),
            ("review", repaired["revision"]),
        ):
            record = json.loads((directory / panel_name / "manifest.json").read_bytes())
            assert "cleanup OFF on both sides" in record["label"]
            base_rgb = tifffile.imread(
                saved_raster(project / "revisions" / base_revision / "foreground_rgb16.tif")
            )
            base_alpha = np.array(
                Image.open(saved_raster(project / "revisions" / base_revision / "base_alpha16.png"))
            )
            actual = np.array(Image.open(native[panel_name] / "crop-000-black_RGB8_VIEW.png"))
            expected = np.rint(
                np.rint(
                    base_rgb.astype(np.float64) * (base_alpha.astype(np.float64) / 65535)[..., None]
                )
                / 257
            ).astype(np.uint8)
            np.testing.assert_array_equal(actual, expected)
        repaired = operations.apply_operation(
            project, effect_request(project, scope=[3, 1, 5, 3], candidate_comparison=True)
        )
    operations.accept_revision(project, repaired["revision"])
    exported = export_project(project, variants=("black", "transparent", "editable"))
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(Path(exported["directory"]) / "black_rgb16.tif"))[1, 1],
        [5890, 8390, 10890],
    )
    for name, data in accepted_bytes.items():
        assert (saved_raster(Path(accepted["directory"]) / name)).read_bytes() == data


def test_different_historical_rgb_lock_outside_support_still_rejects(tmp_path):
    from test_repair_operations import repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    earlier = operations.apply_operation(project, effect_request(project, strength=0.35))
    operations.accept_revision(project, earlier["revision"])
    newer = operations.apply_operation(project, effect_request(project, strength=0.75))
    operations.accept_revision(project, newer["revision"])
    name = edits(
        project,
        [
            {
                "id": "outside-historical-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 1, 2, 2],
                "revision": earlier["revision"],
            },
            {
                "id": "repair-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [3, 1, 5, 3],
                "feather_px": 0,
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="Saved RGB lock differs.*outside repair support"):
        run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [3, 1, 5, 3]))
    assert (project / "state.json").read_bytes() == before


def test_shading_exact_single_round_renderer_and_straight_preview():
    from blackmask.export import render_black, view_rgba

    foreground = np.array([[[65535] * 3, [65535] * 3, [5, 7, 1], [1] * 3]], dtype=np.uint16)
    alpha = np.array([[32768, 32768, 65535, 40000]], dtype=np.uint16)
    weight = np.full(alpha.shape, 65535, dtype=np.uint16)
    np.testing.assert_array_equal(
        render_black(foreground, alpha, weight, 0), render_black(foreground, alpha)
    )
    actual = render_black(foreground, alpha, weight, 0.25)
    assert actual[0, 0, 0] == 24576
    # Rounding shaded F=0.75 to 1 before alpha would incorrectly produce 1.
    assert actual[0, 3, 0] == 0
    np.testing.assert_array_equal(render_black(foreground, alpha, weight, 0.5)[0, 2], [2, 4, 0])
    rgba = view_rgba(foreground, alpha, weight, 0.25)
    assert rgba[0, 0, 0] == 191 and rgba[0, 0, 3] == 128


def test_shadow_weight_unbaked_protection_band_and_thin_features():
    from blackmask.effects import make_shadow_weight

    source = np.full((80, 100, 3), 24000, dtype=np.uint16)
    alpha = np.zeros((80, 100), dtype=np.uint16)
    alpha[5:75, 5:85] = 65535
    alpha[35:37, 85:98] = 65535
    alpha[4, 20:40] = 20000
    support = np.full(alpha.shape, 65535, dtype=np.uint16)
    support[:, :10] = 0
    protection = np.zeros(alpha.shape, dtype=bool)
    protection[68:75, 20:30] = True
    settings = {"enabled": True, "opacity": 0.12, "width_px": 10.0, "direction_degrees": 90.0}
    weight = make_shadow_weight(source, alpha, support, settings, protection=protection)
    assert weight.dtype == np.uint16 and np.any(weight > 0)
    assert np.all(weight[protection] == 0) and np.all(weight[support == 0] == 0)
    assert np.all(weight[alpha == 0] == 0) and np.all(weight[25:55, 25:65] == 0)
    np.testing.assert_array_equal(
        weight,
        make_shadow_weight(
            source, alpha, support, dict(settings, opacity=0.24), protection=protection
        ),
    )
    assert weight[36, 96] < weight[73, 50]


def shading_request(project, *, opacity=0.12, enabled=True, opacity_only=False, support=None):
    operation = effect_request(project, candidate_comparison=True, support=support)
    operation.pop("color_cleanup")
    operation["shading"] = {
        "enabled": enabled,
        "opacity": opacity,
        "width_px": 3.0,
        "direction_degrees": 90.0,
    }
    if opacity_only:
        operation["opacity_only"] = True
    else:
        protection = np.zeros((4, 6), dtype=np.uint16)
        protection[2, 3] = 65535
        Image.fromarray(protection).save(project / "shading-protection.png")
        operation["shading_protection_file"] = "shading-protection.png"
    return operation


@pytest.mark.parametrize("prior_shading", [True, False])
def test_geometry_omitting_shading_disable_reuses_effective_saved_settings(tmp_path, prior_shading):
    import tomllib
    from contextlib import ExitStack

    import tomli_w

    from blackmask import effects, models, review

    project, _, _ = fixture_project(tmp_path)
    if prior_shading:
        operations.apply_operation(project, shading_request(project))
    operation = shading_request(project, enabled=False, opacity=0)
    operation["shading"] = {"enabled": False, "opacity": 0}
    first = operations.apply_operation(project, operation)
    directory = project / "revisions" / first["revision"]
    assert json.loads((directory / "request.json").read_bytes()) == operation
    operations.accept_revision(project, first["revision"])
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["local_exposure"]["ev"] = 1.1
    (project / "recipe.toml").write_bytes(tomli_w.dumps(recipe).encode())
    repeated = dict(
        operation, base_revision=first["revision"], inputs_digest=operations.draft_digest(project)
    )
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    with ExitStack() as guards:
        for owner, name in (
            (effects, "make_corrected_rgb"),
            (effects, "make_shadow_weight"),
            (review, "write_revision_overview"),
            (operations, "VitMatteSession"),
            (models, "SamSession"),
        ):
            guards.enter_context(
                patch.object(
                    owner, name, side_effect=AssertionError("generation on identical disable")
                )
            )
        second = operations.apply_operation(project, repeated)
    assert second["reused"] is True and second["revision"] == first["revision"]
    assert second["parent"] == first["parent"]
    assert second["manifest_file"] == first["manifest_file"]
    assert second["status"] == read_project(project)["status"] == "accepted"
    assert before == {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    expected = {"enabled": False, "opacity": 0}
    if prior_shading:
        expected.update(width_px=3.0, direction_degrees=90.0)
    assert first["shading"]["settings"] == expected
    assert second["effects_reuse"]["request"]["shading"] == expected
    assert (
        json.loads((directory / "inputs/effects.json").read_bytes())["request"]["shading"]
        == expected
    )


def test_disabled_shading_changed_geometry_creates_meaningful_result(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, shading_request(project))
    disabled_request = shading_request(project, enabled=False, opacity=0)
    disabled_request["shading"] = {"enabled": False, "opacity": 0}
    disabled = operations.apply_operation(project, disabled_request)
    previous_rgb, previous_alpha, _ = saved_layers(
        project, disabled["revision"], read_project(project)["developed_id"]
    )
    changed_request = shading_request(project, enabled=False, opacity=0)
    changed_request["shading"]["width_px"] = 7
    changed = operations.apply_operation(project, changed_request)
    assert changed["reused"] is False and changed["revision"] != disabled["revision"]
    assert changed["shading"]["settings"]["width_px"] == 7
    rgb, alpha, _ = saved_layers(
        project, changed["revision"], read_project(project)["developed_id"]
    )
    np.testing.assert_array_equal(rgb, previous_rgb)
    np.testing.assert_array_equal(alpha, previous_alpha)
    repeat = shading_request(project, enabled=False, opacity=0)
    repeat["shading"] = {"enabled": False, "opacity": 0}
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    reused = operations.apply_operation(project, repeat)
    assert reused["reused"] and reused["revision"] == changed["revision"]
    assert reused["shading"]["settings"]["width_px"] == 7
    assert before == {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize(
    "malformed", ["missing-direction", "zero-width", "invalid-direction", "opacity-only"]
)
def test_shading_disable_reuse_keeps_geometry_validation(tmp_path, malformed):
    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, shading_request(project))
    disabled = shading_request(project, enabled=False, opacity=0)
    disabled["shading"] = {"enabled": False, "opacity": 0}
    operations.apply_operation(project, disabled)
    operation = shading_request(project, enabled=False, opacity=0)
    if malformed == "missing-direction":
        operation["shading"].pop("direction_degrees")
    elif malformed == "zero-width":
        operation["shading"]["width_px"] = 0
    elif malformed == "invalid-direction":
        operation["shading"]["direction_degrees"] = 360
    else:
        operation["shading"] = {"enabled": False, "opacity": 0}
        operation["opacity_only"] = True
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    with pytest.raises(
        ProjectError, match="shading settings|positive width|cannot change geometry"
    ):
        operations.apply_operation(project, operation)
    assert before == {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize(
    "mode",
    [
        "cleanup",
        "cleanup-off",
        "shading",
        "opacity",
        "shading-off",
        "exposure",
        "exposure-amount",
        "exposure-off",
        "fade",
        "fade-amount",
        "fade-off",
        "background",
    ],
)
def test_identical_effects_request_reuses_current_after_identity_checks(tmp_path, mode):
    """Unconditional revision publication/generation must fail this contract."""
    from contextlib import ExitStack

    from test_background import background_request
    from test_exposure import exposure_request
    from test_shadow_fade import fade_request

    from blackmask import background, effects

    project, _, _ = fixture_project(tmp_path)
    if mode == "opacity":
        operations.apply_operation(project, shading_request(project))
    if mode == "exposure-amount":
        operations.apply_operation(project, exposure_request(project))
    if mode == "fade-amount":
        operations.apply_operation(project, fade_request(project))
    if mode.startswith("cleanup"):
        operation = effect_request(
            project, enabled=mode != "cleanup-off", candidate_comparison=True
        )
    elif mode in {"shading", "opacity", "shading-off"}:
        operation = shading_request(
            project, opacity=0.24, opacity_only=mode == "opacity", enabled=mode != "shading-off"
        )
    elif mode.startswith("exposure"):
        operation = exposure_request(
            project, ev=0.75, amount_only=mode == "exposure-amount", enabled=mode != "exposure-off"
        )
    elif mode.startswith("fade"):
        operation = fade_request(
            project, amount=0.3, amount_only=mode == "fade-amount", enabled=mode != "fade-off"
        )
    else:
        operation = background_request(project)
    first = operations.apply_operation(project, operation)
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    repeated = dict(
        operation, base_revision=first["revision"], inputs_digest=operations.draft_digest(project)
    )
    with ExitStack() as guards:
        for owner, name in (
            (effects, "make_corrected_rgb"),
            (effects, "make_shadow_weight"),
            (effects, "write_revision_overview"),
            (background, "make_background"),
        ):
            # The overview import is function-local in the baseline.
            if name == "write_revision_overview":
                from blackmask import review

                owner = review
            guards.enter_context(
                patch.object(owner, name, side_effect=AssertionError("generation on reuse"))
            )
        guards.enter_context(
            patch(
                "blackmask.operations.VitMatteSession", side_effect=AssertionError("model on reuse")
            )
        )
        second = operations.apply_operation(project, repeated)
    assert second["reused"] is True
    assert second["revision"] == first["revision"]
    assert second["parent"] == first["parent"]
    assert second["manifest_file"] == first["manifest_file"]
    assert second["revision_inputs_digest"] == first["revision_inputs_digest"]
    assert before == {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, operation)


def test_reuse_preserves_pending_drafts_and_accepted_status(tmp_path):
    import tomllib

    import tomli_w

    project, _, _ = fixture_project(tmp_path)
    operation = shading_request(project)
    first = operations.apply_operation(project, operation)
    operations.accept_revision(project, first["revision"])
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["notes"] = "Keep this pending note"
    recipe["local_exposure"] = {"enabled": True, "ev": 1.25}
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    before = {
        name: (project / name).read_bytes() for name in ("recipe.toml", "guides.json", "state.json")
    }
    result = operations.apply_operation(
        project,
        dict(
            operation,
            base_revision=first["revision"],
            inputs_digest=operations.draft_digest(project),
        ),
    )
    assert result["reused"] is True and result["status"] == "accepted"
    assert result["inputs_digest"] != result["revision_inputs_digest"]
    assert before == {name: (project / name).read_bytes() for name in before}
    with pytest.raises(ProjectError, match="Stale final acceptance"):
        operations.accept_revision(project, first["revision"])


@pytest.mark.parametrize(
    "changed", ["scope", "support", "candidate", "execution", "package", "unknown"]
)
def test_effect_reuse_requires_current_operands_and_provenance(tmp_path, changed, monkeypatch):
    from blackmask import effects

    project, _, _ = fixture_project(tmp_path)
    operation = effect_request(project, candidate_comparison=True)
    first = operations.apply_operation(project, operation)
    operations.accept_revision(project, first["revision"])
    repeated = dict(
        operation, base_revision=first["revision"], inputs_digest=operations.draft_digest(project)
    )
    if changed == "scope":
        repeated["scope_xyxy"] = [0, 0, 5, 4]
    elif changed == "support":
        support = np.zeros((4, 6), dtype=np.uint16)
        support[:, 1:5] = 32768
        Image.fromarray(support).save(project / "cleanup-support.png")
    elif changed == "candidate":
        repeated["candidate_comparison"] = False
    elif changed == "execution":
        monkeypatch.setattr(effects, "EFFECTS_EXECUTION_VERSION", "different-version")
    elif changed == "package":
        original = effects.version
        monkeypatch.setattr(
            effects,
            "version",
            lambda name: "different-package" if name == "numpy" else original(name),
        )
    else:
        monkeypatch.setattr(effects, "_effects_execution_identity", lambda: None)
    result = operations.apply_operation(project, repeated)
    assert result["reused"] is False and result["revision"] != first["revision"]
    assert read_project(project)["accepted_revision"] == first["revision"]


def test_metadata_only_revision_preserves_pixels_and_new_protection(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    operation = shading_request(project)
    first = operations.apply_operation(project, operation)
    state = read_project(project)
    _, alpha, before = saved_layers(project, first["revision"], state["developed_id"])
    protection = np.zeros((4, 6), dtype=np.uint16)
    protection[2, 3] = 65535
    protection[0, 5] = 65535  # Outside the write support: unchanged pixels, changed safety input.
    assert np.any((alpha > 0) & (alpha < 65535))
    Image.fromarray(protection).save(project / "shading-protection.png")
    result = operations.apply_operation(
        project,
        dict(
            operation,
            base_revision=first["revision"],
            inputs_digest=operations.draft_digest(project),
        ),
    )
    _, _, after = saved_layers(project, result["revision"], state["developed_id"])
    assert result["revision"] != first["revision"] and result["reused"] is False
    assert before["assets"] == after["assets"]
    assert before["effects_reuse"] != after["effects_reuse"]


@pytest.mark.parametrize(
    "changed", ["state.json", "recipe.toml", "source.json", "cleanup-support.png", "request"]
)
def test_reuse_rechecks_captured_inputs_before_return(tmp_path, changed, monkeypatch):
    from blackmask import effects

    project, _, _ = fixture_project(tmp_path)
    operation = effect_request(project, candidate_comparison=True)
    first = operations.apply_operation(project, operation)
    repeated = dict(
        operation, base_revision=first["revision"], inputs_digest=operations.draft_digest(project)
    )
    request_file = project / "repeat.json"
    request_file.write_text(json.dumps(repeated))
    target = request_file if changed == "request" else project / changed
    original = effects._reused_effects_result
    before_state = (project / "state.json").read_bytes()

    def mutate(*arguments):
        result = original(*arguments)
        assert result is not None
        target.write_bytes(target.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(effects, "_reused_effects_result", mutate)
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, repeated, request_file=request_file)
    if changed != "state.json":
        assert (project / "state.json").read_bytes() == before_state
    assert target.read_bytes().endswith(b"\n")


def test_failed_submission_does_not_publish_result_and_keeps_captured_inputs(tmp_path):
    import hashlib

    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    operation = effect_request(project, candidate_comparison=True)
    with (
        patch(
            "blackmask.effects.make_corrected_rgb", side_effect=RuntimeError("computation fault")
        ),
        pytest.raises(RuntimeError, match="computation fault"),
    ):
        operations.apply_operation(project, operation)
    (stage,) = (project / "revisions").glob(".effects-*")
    assert json.loads((stage / "request.json").read_bytes()) == operation
    assert (stage / "inputs/state.json").read_bytes() == before
    assert (
        json.loads((stage / "inputs/effects.json").read_bytes())["inputs"]["request_files"][
            "support_file"
        ]
        == hashlib.sha256((project / "cleanup-support.png").read_bytes()).hexdigest()
    )
    assert (project / "state.json").read_bytes() == before
    assert not (stage / "manifest.json").exists()


def test_equivalent_input_locator_reuses_actual_bytes(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    operation = effect_request(project, candidate_comparison=True)
    first = operations.apply_operation(project, operation)
    (project / "same-support.png").write_bytes((project / "cleanup-support.png").read_bytes())
    result = operations.apply_operation(
        project,
        dict(
            operation,
            support_file="same-support.png",
            base_revision=first["revision"],
            inputs_digest=operations.draft_digest(project),
        ),
    )
    assert result["reused"] is True and result["revision"] == first["revision"]


@pytest.mark.parametrize(
    "evidence",
    [
        "absent",
        "unknown",
        "boolean-schema",
        "legacy-execution",
        "legacy-execution-v2",
        "result-mismatch",
        "wrong-request",
        "wrong-shading-geometry",
        "wrong-algorithm",
    ],
)
def test_unproven_saved_effects_evidence_computes_normally(tmp_path, evidence):
    from blackmask.project import digest

    project, _, _ = fixture_project(tmp_path)
    operation = shading_request(project)
    first = operations.apply_operation(project, operation)
    directory = project / "revisions" / first["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    result = json.loads((directory / "result.json").read_bytes())
    if evidence == "absent":
        manifest.pop("effects_reuse")
        result.pop("effects_reuse")
    elif evidence == "unknown":
        manifest["effects_reuse"]["schema_version"] = 99
        result["effects_reuse"]["schema_version"] = 99
    elif evidence == "boolean-schema":
        manifest["effects_reuse"]["schema_version"] = True
        result["effects_reuse"]["schema_version"] = True
    elif evidence in {"legacy-execution", "legacy-execution-v2"}:
        old_version = (
            "validated-effects-v2" if evidence == "legacy-execution-v2" else "validated-effects-v1"
        )
        manifest["effects_reuse"]["execution"]["version"] = old_version
        result["effects_reuse"]["execution"]["version"] = old_version
    elif evidence == "result-mismatch":
        result["effects_reuse"]["schema_version"] = 99
    elif evidence in {"wrong-request", "wrong-shading-geometry"}:
        saved = json.loads((directory / "request.json").read_bytes())
        if evidence == "wrong-request":
            saved["base_revision"] = first["revision"]
        else:
            saved["shading"]["width_px"] = 9
        (directory / "request.json").write_text(json.dumps(saved))
        manifest["files"]["request.json"] = digest((directory / "request.json").read_bytes())
    else:
        manifest["shading"]["algorithm"] = "unknown-algorithm"
    (directory / "result.json").write_text(json.dumps(result))
    manifest["files"]["result.json"] = digest((directory / "result.json").read_bytes())
    (directory / "manifest.json").write_text(json.dumps(manifest))
    original = (directory / "manifest.json").read_bytes()
    completed = operations.apply_operation(project, shading_request(project))
    assert completed["reused"] is False and completed["revision"] != first["revision"]
    assert (directory / "manifest.json").read_bytes() == original


def test_equivalent_effects_cli_and_actual_viewer_protocol(tmp_path):
    import subprocess
    import sys
    import time

    from test_viewer import http, running

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, shading_request(project))
    operation = shading_request(project)
    filename = project / "repeat-request.json"
    filename.write_text(json.dumps(operation))
    before = (project / "state.json").read_bytes()
    bound_cli = 'import sys;from pathlib import Path;from blackmask import cli;assert Path(cli.__file__).is_relative_to(Path.cwd()/"src");sys.exit(cli.main())'
    completed = subprocess.run(
        [sys.executable, "-B", "-c", bound_cli, "run", str(project), "--request", str(filename)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    returned = json.loads(completed.stdout)
    assert returned["reused"] and returned["revision"] == first["revision"]
    with running(project) as server:
        payload = dict(
            operation, action="effects", authoring_digest=server.snapshot()["authoring_digest"]
        )
        payload.pop("schema_version")
        payload.pop("kind")
        assert (
            http(server, "/api/action", "POST", payload, Origin="https://attacker.invalid")[0]
            == 403
        )
        assert http(server, "/api/action", "POST", payload)[0] == 202
        for _ in range(200):
            current = server.snapshot()["action"]
            if not current["running"]:
                break
            time.sleep(0.01)
        assert not current["running"] and not current["error"], current
        assert current["result"]["reused"] and current["result"]["revision"] == first["revision"]
        with pytest.raises(ProjectError, match="Stale viewer"):
            server.execute(dict(payload, inputs_digest="0" * 64))
    assert (project / "state.json").read_bytes() == before


def test_equivalent_effects_still_requires_actual_process_writer_lock(tmp_path):
    import subprocess
    import sys

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, shading_request(project))
    operation = shading_request(project)
    program = 'import sys;from pathlib import Path;from blackmask.project import project_lock\nwith project_lock(Path(sys.argv[1])):\n print("locked",flush=True)\n sys.stdin.read(1)'
    child = subprocess.Popen(
        [sys.executable, "-B", "-c", program, str(project)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(ProjectError, match="busy"):
            operations.apply_operation(project, operation)
    finally:
        _, errors = child.communicate("x", timeout=10)
        assert child.returncode == 0, errors
    repeated = operations.apply_operation(project, operation)
    assert repeated["reused"] and repeated["revision"] == first["revision"]


@pytest.mark.parametrize(
    "changed",
    ["guides", "backend", "source", "alpha", "support", "permission", "symlink", "identity"],
)
def test_equivalent_effects_cannot_bypass_current_input_validation(tmp_path, changed):
    import tomllib

    import tomli_w

    project, _, _ = fixture_project(tmp_path)
    operation = shading_request(project)
    first = operations.apply_operation(project, operation)
    before = (project / "state.json").read_bytes()
    repeated = dict(operation, base_revision=first["revision"])
    if changed == "guides":
        guides = json.loads((project / "guides.json").read_bytes())
        guides["regions"][0]["xyxy"] = [0, 0, 1, 3]
        (project / "guides.json").write_text(json.dumps(guides))
    elif changed == "backend":
        recipe = tomllib.loads((project / "recipe.toml").read_text())
        recipe["matting"]["device"] = "mps"
        (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    elif changed == "source":
        path = project / "assets/developed" / (read_project(project)["developed_id"] + ".tif")
        path.write_bytes(path.read_bytes() + b"changed source identity")
    elif changed == "alpha":
        manifest = json.loads(
            (project / "revisions" / first["revision"] / "manifest.json").read_bytes()
        )
        path = project / manifest["assets"]["base_alpha16.png"]["path"]
        Image.fromarray(np.zeros((4, 6), dtype=np.uint16)).save(path)
    elif changed == "support":
        Image.fromarray(np.zeros((2, 2), dtype=np.uint16)).save(project / "cleanup-support.png")
    elif changed == "permission":
        repeated["candidate_comparison"] = False
    elif changed == "symlink":
        (project / "input-alias.png").symlink_to(project / "cleanup-support.png")
        repeated["support_file"] = "input-alias.png"
    else:
        repeated["developed_id"] = "f" * 64
    repeated["inputs_digest"] = operations.draft_digest(project)
    with (
        patch(
            "blackmask.effects.make_shadow_weight",
            side_effect=AssertionError("generation before validation"),
        ),
        pytest.raises(ProjectError),
    ):
        operations.apply_operation(project, repeated)
    assert (project / "state.json").read_bytes() == before


def test_shading_saved_operation_independent_cleanup_global_opacity_and_export(tmp_path):
    from blackmask.export import render_black
    from blackmask.repair import scalar16

    project, source, _parent = fixture_project(tmp_path)
    cleaned = operations.apply_operation(project, effect_request(project))
    rgb, alpha, cleanup_manifest = saved_layers(
        project, cleaned["revision"], read_project(project)["developed_id"]
    )
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("No model")):
        shaded = operations.apply_operation(project, shading_request(project))
        foreground, actual_alpha, manifest = saved_layers(
            project, shaded["revision"], read_project(project)["developed_id"]
        )
        np.testing.assert_array_equal(foreground, rgb)
        np.testing.assert_array_equal(actual_alpha, alpha)
        assert manifest["color_cleanup"] == cleanup_manifest["color_cleanup"]
        weight = scalar16(
            saved_raster(project / "revisions" / shaded["revision"] / "shadow_weight16.png")
        )
        assert np.any(weight) and weight[2, 3] == 0
        operations.accept_revision(project, shaded["revision"])
        exported = Path(
            export_project(project, variants=("black", "transparent", "editable"))["directory"]
        )
        np.testing.assert_array_equal(
            tifffile.imread(saved_raster(exported / "black_rgb16.tif")),
            render_black(rgb, alpha, weight, 0.12),
        )
        np.testing.assert_array_equal(
            scalar16(saved_raster(exported / "shadow_weight16.png")), weight
        )
        np.testing.assert_array_equal(
            tifffile.imread(saved_raster(exported / "foreground_rgb16.tif")), rgb
        )
        assert "baked shading" in (exported / "README.txt").read_text()
        with patch(
            "blackmask.effects.make_shadow_weight",
            side_effect=AssertionError("Opacity must reuse W"),
        ):
            changed = operations.apply_operation(
                project, shading_request(project, opacity=0.24, opacity_only=True)
            )
        directory = project / "revisions" / changed["revision"]
        np.testing.assert_array_equal(
            scalar16(saved_raster(directory / "shadow_weight16.png")), weight
        )
        assert (
            json.loads((directory / "effects/shading/settings.json").read_bytes())[
                "operation_scope"
            ]
            == "global opacity only"
        )
        disabled = operations.apply_operation(project, shading_request(project, enabled=False))
        assert (
            saved_layers(project, disabled["revision"], read_project(project)["developed_id"])[2][
                "color_cleanup"
            ]
            == cleanup_manifest["color_cleanup"]
        )
    assert read_project(project)["accepted_revision"] == shaded["revision"]
    np.testing.assert_array_equal(
        tifffile.imread(
            saved_raster(
                project / "assets/developed" / (read_project(project)["developed_id"] + ".tif")
            )
        ),
        source,
    )


def test_both_effects_repair_independent_stale_rebuild_and_fresh_export(tmp_path):
    import subprocess
    import sys

    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair

    from blackmask.repair import scalar16
    from blackmask.review import review_project

    project, source, _parent = fixture_project(tmp_path)
    operations.apply_operation(project, effect_request(project))
    first = operations.apply_operation(project, shading_request(project))
    operations.accept_revision(project, first["revision"])
    accepted = Path(
        export_project(project, variants=("black", "transparent", "editable"))["directory"]
    )
    original = {p.name: p.read_bytes() for p in accepted.iterdir()}
    old_weight = scalar16(
        saved_raster(project / "revisions" / first["revision"] / "shadow_weight16.png")
    )
    old_corrected = tifffile.imread(
        saved_raster(project / "revisions" / first["revision"] / "corrected_rgb16.tif")
    )
    old_alpha = saved_layers(project, first["revision"], read_project(project)["developed_id"])[1]
    lock_file = edits(
        project,
        [
            {
                "id": "inside-partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": first["revision"],
            },
            {
                "id": "outside-partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [4, 0, 5, 1],
                "revision": first["revision"],
            },
        ],
    )
    prepared_locks = operations.apply_operation(
        project, request(project, guide_edits_file=lock_file)
    )
    approve(project, prepared_locks)
    prepared = repair_guides(project, [1, 1, 4, 3])
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        repair = run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3]))
    manifest = saved_layers(project, repair["revision"], read_project(project)["developed_id"])[2]
    assert manifest["color_cleanup"]["stale"] and manifest["shading"]["stale"]
    for name in ("review", "review-before"):
        label = json.loads(
            (project / "revisions" / repair["revision"] / name / "manifest.json").read_bytes()
        )["label"]
        assert "cleanup OFF" in label and "shading OFF" in label
    native = native_review_directories(project, repair["revision"])
    # Independently derive BASE pixels on both sides; no production renderer reused.
    expected_alpha = old_alpha.copy()
    expected_alpha[1:3, 1:4] = 49151
    expected_alpha[1, 2] = old_alpha[1, 2]
    expected_after_rgb = source.copy()
    expected_after_rgb[1, 2] = old_corrected[1, 2]
    expected_after_rgb[0, 4] = old_corrected[0, 4]
    assert 0 < old_alpha[1, 2] < 65535 and 0 < old_alpha[0, 4] < 65535
    assert np.any(old_corrected[1, 2] != source[1, 2])
    for review_name, expected_rgb, expected_a in (
        ("review-before", source, old_alpha),
        ("review", expected_after_rgb, expected_alpha),
    ):
        expected_black16 = np.rint(
            expected_rgb.astype(np.float64) * (expected_a.astype(np.float64) / 65535)[..., None]
        ).astype(np.uint16)
        expected_view = np.rint(expected_black16.astype(np.float64) / 257).astype(np.uint8)
        with Image.open(native[review_name] / "crop-000-black_RGB8_VIEW.png") as image:
            np.testing.assert_array_equal(np.array(image), expected_view)
    from blackmask.repair import replay_repair

    np.testing.assert_array_equal(replay_repair(project, repair["revision"]), expected_alpha)
    label = json.loads(saved_raster(Path(review_project(project)["manifest_file"])).read_bytes())
    assert {"cleanup_stale", "shading_stale"} <= set(label["stale_labels"])
    with pytest.raises(ProjectError, match="Stale"):
        operations.accept_revision(project, repair["revision"])
    rebuilt_cleanup = operations.apply_operation(
        project, effect_request(project, scope=[1, 1, 4, 3], candidate_comparison=True)
    )
    assert not rebuilt_cleanup["color_cleanup"]["stale"] and rebuilt_cleanup["shading"]["stale"]
    with pytest.raises(ProjectError, match="Stale"):
        operations.accept_revision(project, rebuilt_cleanup["revision"])
    with pytest.raises(ProjectError, match="Stale"):
        export_project(
            project,
            revision=rebuilt_cleanup["revision"],
            draft=True,
            variants=("black", "transparent", "editable"),
        )
    partial_support = np.zeros((4, 6), dtype=np.uint16)
    partial_support[1, 1] = 65535
    partial = operations.apply_operation(project, shading_request(project, support=partial_support))
    assert partial["shading"]["stale"]
    scope_support = np.zeros((4, 6), dtype=np.uint16)
    scope_support[1:3, 1:4] = 65535
    rebuilt = operations.apply_operation(project, shading_request(project, support=scope_support))
    assert not rebuilt["shading"]["stale"] and not rebuilt["color_cleanup"]["stale"]
    directory = project / "revisions" / rebuilt["revision"]
    weight = scalar16(saved_raster(directory / "shadow_weight16.png"))
    outside = scope_support == 0
    assert old_weight[outside].any() and np.any(old_corrected[outside] != source[outside])
    np.testing.assert_array_equal(weight[outside], old_weight[outside])
    assert weight[2, 3] == 0 and weight[1, 2] == 0
    np.testing.assert_array_equal(
        scalar16(saved_raster(directory / "base_alpha16.png")), expected_alpha
    )
    np.testing.assert_array_equal(expected_alpha[outside], old_alpha[outside])
    final_rgb = tifffile.imread(saved_raster(directory / "corrected_rgb16.tif"))
    np.testing.assert_array_equal(final_rgb[1, 2], old_corrected[1, 2])
    np.testing.assert_array_equal(final_rgb[0, 4], old_corrected[0, 4])
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(directory / "corrected_rgb16.tif"))[outside],
        old_corrected[outside],
    )
    operations.accept_revision(project, rebuilt["revision"])
    # New process uses only saved layers, no model/cache setup or original capture lookup.
    result = subprocess.run(
        [sys.executable, "-m", "blackmask", "export", str(project), "--variant", "black"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    exported = Path(json.loads(result.stdout)["directory"])
    rgb, alpha, _ = saved_layers(
        project, rebuilt["revision"], read_project(project)["developed_id"]
    )
    expected = np.rint(
        rgb.astype(np.float64)
        * (alpha.astype(np.float64) / 65535)[..., None]
        * (1 - 0.12 * weight.astype(np.float64) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "black_rgb16.tif")), expected
    )
    for name, data in original.items():
        assert (saved_raster(accepted / name)).read_bytes() == data


def test_viewer_shading_same_native_crop_comparisons_and_independent_disable(tmp_path):
    import io

    from blackmask.export import render_black
    from blackmask.repair import scalar16
    from blackmask.viewer import ReviewServer

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, shading_request(project))
    rgb, alpha, _ = saved_layers(project, result["revision"], read_project(project)["developed_id"])
    weight = scalar16(
        saved_raster(project / "revisions" / result["revision"] / "shadow_weight16.png")
    )
    server = ReviewServer(project)
    try:
        state = server.snapshot()
        current = next(r for r in state["revisions"] if r["revision"] == result["revision"])
        assert current["shading"]["settings"]["width_px"] == 3
        for opacity in (0, 0.12, 0.24):
            data = server.image(f"/image/black/{result['revision']}/1,0,5,4/p{opacity}")
            with Image.open(saved_raster(io.BytesIO(data))) as image:
                expected = np.rint(
                    render_black(rgb, alpha, weight, opacity).astype(np.float64) / 257
                ).astype(np.uint8)[:, 1:5]
                np.testing.assert_array_equal(np.array(image), expected)
        identity = {k: state[k] for k in ("developed_id", "inputs_digest", "authoring_digest")}
        operation = shading_request(project, enabled=False)
        operation.pop("schema_version")
        operation.pop("kind")
        operation.update(identity, action="effects")
        assert server.execute(operation)["shading"]["enabled"] is False
    finally:
        server.server_close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("width_px", 0),
        ("width_px", 1000),
        ("direction_degrees", 360),
        ("direction_degrees", True),
        ("opacity", float("nan")),
        ("opacity", 2),
        ("enabled", 1),
    ],
)
def test_invalid_shading_preserves_state(tmp_path, field, value):
    project, _, _ = fixture_project(tmp_path)
    operation = shading_request(project)
    operation["shading"][field] = value
    before = (project / "state.json").read_bytes()
    with pytest.raises((ProjectError, ValueError)):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


def test_shading_protection_mutation_before_publish_preserves_state(tmp_path):
    from blackmask import effects

    project, _, _ = fixture_project(tmp_path)
    operation = shading_request(project)
    before = (project / "state.json").read_bytes()
    original = effects.make_shadow_weight

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        Image.fromarray(np.zeros((4, 6), dtype=np.uint16)).save(project / "shading-protection.png")
        return result

    with (
        patch.object(effects, "make_shadow_weight", changing),
        pytest.raises(ProjectError, match="Stale shading protection"),
    ):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


def test_first_shading_uses_offline_authored_guides_without_external_mask(tmp_path):
    from blackmask.repair import scalar16
    from blackmask.viewer import ReviewServer

    project, _, parent = fixture_project(tmp_path)
    guide_file = edits(
        project,
        [
            {
                "id": "protect-detail",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [4, 1, 5, 2],
                "revision": parent["revision"],
            },
            {
                "id": "shading-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [1, 0, 5, 4],
                "feather_px": 0,
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=guide_file))
    approve(project, prepared)
    matte = run_matte(project)
    server = ReviewServer(project)
    try:
        state = server.snapshot()
        identity = {k: state[k] for k in ("developed_id", "inputs_digest", "authoring_digest")}
        prefix = "revisions/" + matte["revision"]
        with Image.open(saved_raster(project / prefix / "supports/protection.png")) as image:
            assert image.mode == "L" and np.array(image)[1, 4] == 255
        result = server.execute(
            dict(
                identity,
                action="effects",
                base_revision=matte["revision"],
                scope_xyxy=[1, 0, 5, 4],
                support_file=prefix + "/supports/support16.png",
                shading_protection_file=prefix + "/supports/protection.png",
                candidate_comparison=True,
                shading={
                    "enabled": True,
                    "opacity": 0.12,
                    "width_px": 3.0,
                    "direction_degrees": 90.0,
                },
            )
        )
        weight = scalar16(
            saved_raster(project / "revisions" / result["revision"] / "shadow_weight16.png")
        )
        assert weight.any() and weight[1, 4] == 0
        protection = scalar16(
            saved_raster(
                project / "revisions" / result["revision"] / "effects/shading/protection16.png"
            )
        )
        assert protection[1, 4] == 65535
    finally:
        server.server_close()
