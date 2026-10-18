"""Synthetic color-cleanup arithmetic and saved-operation contracts; no photo preference claims."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_ingest import srgb_profile, tiff
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
    accept_development(project, read_project(project)["master_id"])
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
    base, alpha, _ = saved_layers(project, _parent["revision"], read_project(project)["master_id"])
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("No model")):
        result = operations.apply_operation(project, effect_request(project))
        rgb, actual_alpha, manifest = saved_layers(
            project, result["revision"], read_project(project)["master_id"]
        )
        assert manifest["kind"] == "effects"
        assert np.any(rgb != _source)
        np.testing.assert_array_equal(actual_alpha, alpha)
        directory = project / "revisions" / result["revision"]
        np.testing.assert_array_equal(tifffile.imread(directory / "corrected_rgb16.tif"), rgb)
        np.testing.assert_array_equal(tifffile.imread(directory / "foreground_rgb16.tif"), base)
        again = operations.apply_operation(
            project, effect_request(project, candidate_comparison=True)
        )
        np.testing.assert_array_equal(
            saved_layers(project, again["revision"], read_project(project)["master_id"])[0], rgb
        )
        disabled = operations.apply_operation(project, effect_request(project, enabled=False))
        np.testing.assert_array_equal(
            saved_layers(project, disabled["revision"], read_project(project)["master_id"])[0],
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
    operations.apply_operation(project, effect_request(project))
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, old)


def test_cleanup_repair_stale_block_scoped_rebuild_and_exact_locks(tmp_path):
    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair

    from blackmask.review import review_project

    project, _source, _parent = fixture_project(tmp_path)
    accepted = export_project(project)
    accepted_bytes = {p.name: p.read_bytes() for p in Path(accepted["directory"]).iterdir()}
    first = operations.apply_operation(project, effect_request(project))
    operations.accept_revision(project, first["revision"])
    old_rgb, old_alpha, _ = saved_layers(
        project, first["revision"], read_project(project)["master_id"]
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
        project, repaired["revision"], read_project(project)["master_id"]
    )
    assert manifest["color_cleanup"]["stale"] is True
    assert np.any(alpha != old_alpha)
    np.testing.assert_array_equal(alpha[1, 2], old_alpha[1, 2])
    for name in ("review", "review-before"):
        review = json.loads(
            (project / "revisions" / repaired["revision"] / name / "manifest.json").read_bytes()
        )
        assert "cleanup OFF" in review["label"]
    reviewed = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
    assert "cleanup_stale" in reviewed["stale_labels"]
    with pytest.raises(ProjectError, match="Stale.*cleanup"):
        operations.accept_revision(project, repaired["revision"])
    with pytest.raises(ProjectError, match="Stale.*cleanup"):
        export_project(project, revision=repaired["revision"], draft=True)
    rebuilt = operations.apply_operation(
        project, effect_request(project, scope=[1, 1, 4, 3], candidate_comparison=True)
    )
    new_rgb, new_alpha, manifest = saved_layers(
        project, rebuilt["revision"], read_project(project)["master_id"]
    )
    assert manifest["color_cleanup"]["stale"] is False
    outside = np.ones(alpha.shape, bool)
    outside[1:3, 1:4] = False
    assert np.any((old_alpha[outside] > 0) & (old_alpha[outside] < 65535))
    np.testing.assert_array_equal(new_rgb[outside], old_rgb[outside])
    np.testing.assert_array_equal(new_rgb[1, 2], old_rgb[1, 2])
    np.testing.assert_array_equal(new_alpha, alpha)
    operations.accept_revision(project, rebuilt["revision"])
    exported = export_project(project)
    np.testing.assert_array_equal(
        tifffile.imread(Path(exported["directory"]) / "black_rgb16.tif"),
        np.rint(new_rgb.astype(np.float64) * (alpha.astype(np.float64) / 65535)[..., None]).astype(
            np.uint16
        ),
    )
    for name, data in accepted_bytes.items():
        assert (Path(accepted["directory"]) / name).read_bytes() == data
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
        identity = {k: state[k] for k in ("master_id", "inputs_digest", "authoring_digest")}
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
    saved_layers(project, revision, read_project(project)["master_id"])
    operations.restore_revision(project, revision)
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

    reviewed = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
    assert "draft_changed" not in reviewed["stale_labels"]
    operations.accept_revision(project, result["revision"])
    original_recipe = (project / "recipe.toml").read_bytes()
    operations.restore_revision(project, result["parent"], replace_drafts=True)
    operations.restore_revision(project, result["revision"], replace_drafts=True)
    assert (project / "recipe.toml").read_bytes() == original_recipe
    assert read_project(project)["accepted_revision"] == result["revision"]


def test_corrected_profile_validation_and_dependency_identity(tmp_path):
    from blackmask.project import digest

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, effect_request(project))
    directory = project / "revisions" / result["revision"]
    rgb = tifffile.imread(directory / "corrected_rgb16.tif")
    tifffile.imwrite(directory / "corrected_rgb16.tif", rgb, photometric="rgb", metadata=None)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["files"]["corrected_rgb16.tif"] = digest(
        (directory / "corrected_rgb16.tif").read_bytes()
    )
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="profile"):
        saved_layers(project, result["revision"], read_project(project)["master_id"])


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
    rgb, _, _ = saved_layers(project, result["revision"], read_project(project)["master_id"])
    np.testing.assert_array_equal(rgb, source)


def test_review_manifest_identifies_selected_corrected_rgb_and_actual_strength(tmp_path):
    from blackmask.review import review_project

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, effect_request(project))
    record = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
    assert record["assets"]["foreground_rgb16"].endswith("/corrected_rgb16.tif")
    saved = json.loads(
        (project / "revisions" / result["revision"] / "review/manifest.json").read_bytes()
    )
    assert saved["color_cleanup"]["strength"] == 0.35
    assert "cleanup ON" in saved["label"]


@pytest.mark.parametrize("repairing", [False, True])
def test_same_alpha_rgb_lock_survives_inherited_cleanup_and_export(tmp_path, repairing):
    from test_repair_operations import repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    earlier = operations.apply_operation(project, effect_request(project, strength=0.35))
    operations.accept_revision(project, earlier["revision"])
    newer = operations.apply_operation(project, effect_request(project, strength=0.75))
    operations.accept_revision(project, newer["revision"])
    before_rgb, before_alpha, _ = saved_layers(
        project, newer["revision"], read_project(project)["master_id"]
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
        project, result["revision"], read_project(project)["master_id"]
    )
    np.testing.assert_array_equal(alpha, before_alpha)
    assert manifest["color_cleanup"]["stale"] is False
    np.testing.assert_array_equal(rgb[1, 2], expected)
    unchanged = np.ones(alpha.shape, bool)
    unchanged[1, 2] = False
    np.testing.assert_array_equal(rgb[unchanged], before_rgb[unchanged])
    operations.accept_revision(project, result["revision"])
    exported = export_project(project)
    np.testing.assert_array_equal(
        tifffile.imread(Path(exported["directory"]) / "black_rgb16.tif")[1, 2], [5890, 8390, 10890]
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
        project, parent["revision"], read_project(project)["master_id"]
    )
    assert alpha[1, 2] == 16384
    np.testing.assert_array_equal(before_rgb[1, 2], [23559, 33559, 43559])
    outside = np.ones(alpha.shape, bool)
    outside[:, 3:5] = False
    for _ in range(2):
        result = operations.apply_operation(
            project, effect_request(project, scope=[3, 0, 5, 4], candidate_comparison=True)
        )
        rgb, _, _ = saved_layers(project, result["revision"], read_project(project)["master_id"])
        np.testing.assert_array_equal(rgb[outside], before_rgb[outside])
        operations.accept_revision(project, result["revision"])
        exported = export_project(project)
        np.testing.assert_array_equal(
            tifffile.imread(Path(exported["directory"]) / "black_rgb16.tif")[1, 2],
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
        saved_layers(project, first["revision"], read_project(project)["master_id"])[1],
        saved_layers(project, result["revision"], read_project(project)["master_id"])[1],
    )
    for panel in ("black", "gray", "white"):
        before = np.array(Image.open(directory / f"review-before/crop-000-{panel}_RGB8_VIEW.png"))
        after = np.array(Image.open(directory / f"review/crop-000-{panel}_RGB8_VIEW.png"))
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
    rgb, _, _ = saved_layers(project, cleanup["revision"], read_project(project)["master_id"])
    expected = saved_layers(project, earlier["revision"], read_project(project)["master_id"])[0][
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
    accepted = export_project(project)
    accepted_bytes = {p.name: p.read_bytes() for p in Path(accepted["directory"]).iterdir()}
    master_bytes = (project / "masters" / f"{read_project(project)['master_id']}.tif").read_bytes()
    parent_rgb, parent_alpha, _ = saved_layers(
        project, first["revision"], read_project(project)["master_id"]
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
        project, repaired["revision"], read_project(project)["master_id"]
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
        tifffile.imread(directory / "corrected_rgb16.tif")[outside], parent_rgb[outside]
    )
    np.testing.assert_array_equal(
        tifffile.imread(directory / "foreground_rgb16.tif")[1, 1], [23559, 33559, 43559]
    )
    assert read_project(project)["accepted_revision"] == first["revision"]
    assert (
        project / "masters" / f"{read_project(project)['master_id']}.tif"
    ).read_bytes() == master_bytes
    assert manifest["color_cleanup"]["stale"] is change_alpha
    if change_alpha:
        # Both panels are honestly labelled base layers, including the explicit saved lock.
        for panel_name, base_revision in (
            ("review-before", prepared["revision"]),
            ("review", repaired["revision"]),
        ):
            record = json.loads((directory / panel_name / "manifest.json").read_bytes())
            assert "cleanup OFF on both sides" in record["label"]
            base_rgb = tifffile.imread(
                project / "revisions" / base_revision / "foreground_rgb16.tif"
            )
            base_alpha = np.array(
                Image.open(project / "revisions" / base_revision / "base_alpha16.png")
            )
            actual = np.array(Image.open(directory / panel_name / "crop-000-black_RGB8_VIEW.png"))
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
    exported = export_project(project)
    np.testing.assert_array_equal(
        tifffile.imread(Path(exported["directory"]) / "black_rgb16.tif")[1, 1], [5890, 8390, 10890]
    )
    for name, data in accepted_bytes.items():
        assert (Path(accepted["directory"]) / name).read_bytes() == data


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


def test_shading_saved_operation_independent_cleanup_global_opacity_and_export(tmp_path):
    from blackmask.export import render_black
    from blackmask.repair import scalar16

    project, source, _parent = fixture_project(tmp_path)
    cleaned = operations.apply_operation(project, effect_request(project))
    rgb, alpha, cleanup_manifest = saved_layers(
        project, cleaned["revision"], read_project(project)["master_id"]
    )
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("No model")):
        shaded = operations.apply_operation(project, shading_request(project))
        foreground, actual_alpha, manifest = saved_layers(
            project, shaded["revision"], read_project(project)["master_id"]
        )
        np.testing.assert_array_equal(foreground, rgb)
        np.testing.assert_array_equal(actual_alpha, alpha)
        assert manifest["color_cleanup"] == cleanup_manifest["color_cleanup"]
        weight = scalar16(project / "revisions" / shaded["revision"] / "shadow_weight16.png")
        assert np.any(weight) and weight[2, 3] == 0
        operations.accept_revision(project, shaded["revision"])
        exported = Path(export_project(project)["directory"])
        np.testing.assert_array_equal(
            tifffile.imread(exported / "black_rgb16.tif"), render_black(rgb, alpha, weight, 0.12)
        )
        np.testing.assert_array_equal(scalar16(exported / "shadow_weight16.png"), weight)
        np.testing.assert_array_equal(tifffile.imread(exported / "foreground_rgb16.tif"), rgb)
        assert "baked shading" in (exported / "README.txt").read_text()
        with patch(
            "blackmask.effects.make_shadow_weight",
            side_effect=AssertionError("Opacity must reuse W"),
        ):
            changed = operations.apply_operation(
                project, shading_request(project, opacity=0.24, opacity_only=True)
            )
        directory = project / "revisions" / changed["revision"]
        np.testing.assert_array_equal(scalar16(directory / "shadow_weight16.png"), weight)
        assert (
            json.loads((directory / "effects/shading/settings.json").read_bytes())[
                "operation_scope"
            ]
            == "global opacity only"
        )
        disabled = operations.apply_operation(project, shading_request(project, enabled=False))
        assert (
            saved_layers(project, disabled["revision"], read_project(project)["master_id"])[2][
                "color_cleanup"
            ]
            == cleanup_manifest["color_cleanup"]
        )
    assert read_project(project)["accepted_revision"] == shaded["revision"]
    np.testing.assert_array_equal(
        tifffile.imread(project / "masters" / (read_project(project)["master_id"] + ".tif")), source
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
    accepted = Path(export_project(project)["directory"])
    original = {p.name: p.read_bytes() for p in accepted.iterdir()}
    old_weight = scalar16(project / "revisions" / first["revision"] / "shadow_weight16.png")
    old_corrected = tifffile.imread(
        project / "revisions" / first["revision"] / "corrected_rgb16.tif"
    )
    old_alpha = saved_layers(project, first["revision"], read_project(project)["master_id"])[1]
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
    manifest = saved_layers(project, repair["revision"], read_project(project)["master_id"])[2]
    assert manifest["color_cleanup"]["stale"] and manifest["shading"]["stale"]
    for name in ("review", "review-before"):
        label = json.loads(
            (project / "revisions" / repair["revision"] / name / "manifest.json").read_bytes()
        )["label"]
        assert "cleanup OFF" in label and "shading OFF" in label
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
        with Image.open(
            project
            / "revisions"
            / repair["revision"]
            / review_name
            / "crop-000-black_RGB8_VIEW.png"
        ) as image:
            np.testing.assert_array_equal(np.array(image), expected_view)
    from blackmask.repair import replay_repair

    np.testing.assert_array_equal(replay_repair(project, repair["revision"]), expected_alpha)
    label = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
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
        export_project(project, revision=rebuilt_cleanup["revision"], draft=True)
    partial_support = np.zeros((4, 6), dtype=np.uint16)
    partial_support[1, 1] = 65535
    partial = operations.apply_operation(project, shading_request(project, support=partial_support))
    assert partial["shading"]["stale"]
    scope_support = np.zeros((4, 6), dtype=np.uint16)
    scope_support[1:3, 1:4] = 65535
    rebuilt = operations.apply_operation(project, shading_request(project, support=scope_support))
    assert not rebuilt["shading"]["stale"] and not rebuilt["color_cleanup"]["stale"]
    directory = project / "revisions" / rebuilt["revision"]
    weight = scalar16(directory / "shadow_weight16.png")
    outside = scope_support == 0
    assert old_weight[outside].any() and np.any(old_corrected[outside] != source[outside])
    np.testing.assert_array_equal(weight[outside], old_weight[outside])
    assert weight[2, 3] == 0 and weight[1, 2] == 0
    np.testing.assert_array_equal(scalar16(directory / "base_alpha16.png"), expected_alpha)
    np.testing.assert_array_equal(expected_alpha[outside], old_alpha[outside])
    final_rgb = tifffile.imread(directory / "corrected_rgb16.tif")
    np.testing.assert_array_equal(final_rgb[1, 2], old_corrected[1, 2])
    np.testing.assert_array_equal(final_rgb[0, 4], old_corrected[0, 4])
    np.testing.assert_array_equal(
        tifffile.imread(directory / "corrected_rgb16.tif")[outside], old_corrected[outside]
    )
    operations.accept_revision(project, rebuilt["revision"])
    # New process uses only saved layers, no model/cache setup or original capture lookup.
    result = subprocess.run(
        [sys.executable, "-m", "blackmask", "export", str(project)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    exported = Path(json.loads(result.stdout)["directory"])
    rgb, alpha, _ = saved_layers(project, rebuilt["revision"], read_project(project)["master_id"])
    expected = np.rint(
        rgb.astype(np.float64)
        * (alpha.astype(np.float64) / 65535)[..., None]
        * (1 - 0.12 * weight.astype(np.float64) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(tifffile.imread(exported / "black_rgb16.tif"), expected)
    for name, data in original.items():
        assert (accepted / name).read_bytes() == data


def test_viewer_shading_same_native_crop_comparisons_and_independent_disable(tmp_path):
    import io

    from blackmask.export import render_black
    from blackmask.repair import scalar16
    from blackmask.viewer import ReviewServer

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, shading_request(project))
    rgb, alpha, _ = saved_layers(project, result["revision"], read_project(project)["master_id"])
    weight = scalar16(project / "revisions" / result["revision"] / "shadow_weight16.png")
    server = ReviewServer(project)
    try:
        state = server.snapshot()
        current = next(r for r in state["revisions"] if r["revision"] == result["revision"])
        assert current["shading"]["settings"]["width_px"] == 3
        for opacity in (0, 0.12, 0.24):
            data = server.image(f"/image/black/{result['revision']}/1,0,5,4/p{opacity}")
            with Image.open(io.BytesIO(data)) as image:
                expected = np.rint(
                    render_black(rgb, alpha, weight, opacity).astype(np.float64) / 257
                ).astype(np.uint8)[:, 1:5]
                np.testing.assert_array_equal(np.array(image), expected)
        identity = {k: state[k] for k in ("master_id", "inputs_digest", "authoring_digest")}
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
        identity = {k: state[k] for k in ("master_id", "inputs_digest", "authoring_digest")}
        prefix = "revisions/" + matte["revision"]
        with Image.open(project / prefix / "supports/protection.png") as image:
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
        weight = scalar16(project / "revisions" / result["revision"] / "shadow_weight16.png")
        assert weight.any() and weight[1, 4] == 0
        protection = scalar16(
            project / "revisions" / result["revision"] / "effects/shading/protection16.png"
        )
        assert protection[1, 4] == 65535
    finally:
        server.server_close()
