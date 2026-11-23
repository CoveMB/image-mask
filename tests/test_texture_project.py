"""Apply, inherit and recover Local Texture on a synthetic saved project."""

import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from test_effects import fixture_project
from test_exposure import rectangle
from test_matte_operations import StubSession, approve
from test_operations import edits, request
from test_repair_operations import repair_request, run_repair
from test_texture import SETTINGS, gray16

from blackmask import operations
from blackmask.export import export_project, saved_layers
from blackmask.project import (
    ProjectError,
    _json_bytes,
    _validation_scope,
    digest,
    read_project,
    read_revision,
)


def texture_fixture(tmp_path):
    rgb = gray16(np.array([0.14, 0.14, 0.156, 0.176, 0.165, 0.145]), height=4)
    return fixture_project(tmp_path, rgb)


def texture_request(project, *, settings=None, candidate=True, mode="replace", scope=(0, 0, 6, 4)):
    fields = {"local_texture": SETTINGS.copy() if settings is None else settings}
    if mode == "replace":
        fields["texture_area"] = {
            "regions": [rectangle("texture", [1, 0, 6, 4])],
            "protection": [rectangle("bright", [2, 1, 3, 2])],
        }
    elif mode == "saved":
        fields["texture_settings_only"] = True
    return request(
        project, kind="effects", scope_xyxy=list(scope), candidate_comparison=candidate, **fields
    )


def test_texture_cli_apply_settings_off_and_reuse(tmp_path, monkeypatch, capsys):
    from blackmask.cli import main

    project, _, parent = texture_fixture(tmp_path)
    master = parent["developed_id"]
    base, alpha, _ = saved_layers(project, parent["revision"], master)
    original_recipe = (project / "recipe.toml").read_bytes()
    assert "local_texture" not in tomllib.loads(original_recipe.decode())
    path = tmp_path / "texture.json"
    initial = texture_request(project, candidate=False, settings=SETTINGS | {"scale_px": 4.0})
    path.write_text(
        json.dumps(initial).replace('"strength": 0.5', '"strength": 1, "strength": 0.5')
    )
    monkeypatch.setattr("sys.argv", ["blackmask", "run", str(project), "--request", str(path)])
    assert main() != 0
    assert "Duplicate" in capsys.readouterr().err
    assert read_project(project)["working_revision"] == parent["revision"]
    path.write_text(json.dumps(initial))
    assert main() == 0
    selected = json.loads(capsys.readouterr().out)["revision"]
    rgb, actual_alpha, first = saved_layers(project, selected, master)
    assert np.any(rgb[0, 1:] != base[0, 1:])
    np.testing.assert_array_equal(rgb[1, 2], base[1, 2])
    np.testing.assert_array_equal(actual_alpha, alpha)
    np.testing.assert_array_equal(
        saved_layers(project, selected, master, texture_off=True)[0], base
    )
    assert first["local_texture"]["settings"] == SETTINGS
    assert tomllib.loads((project / "recipe.toml").read_text())["local_texture"] == SETTINGS

    with pytest.raises(ProjectError, match="candidate comparison"):
        operations.apply_operation(project, texture_request(project, candidate=False, mode="saved"))
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(
            project, texture_request(project, mode="saved", scope=(2, 0, 6, 4))
        )
    equivalent_size = operations.apply_operation(project, texture_request(project, mode="saved"))
    np.testing.assert_array_equal(
        saved_layers(project, equivalent_size["revision"], master)[0], rgb
    )
    stronger = SETTINGS | {"strength": 0.85}
    updated = operations.apply_operation(
        project, texture_request(project, settings=stronger, mode="saved")
    )
    again = operations.apply_operation(
        project, texture_request(project, settings=stronger, mode="saved")
    )
    assert again["reused"] and again["revision"] == updated["revision"]
    for key in ("area_sha256", "support_sha256", "protection_sha256", "alpha_sha256"):
        assert updated["local_texture"][key] == first["local_texture"][key]
    disabled = operations.apply_operation(
        project, texture_request(project, settings=stronger | {"enabled": False}, mode="disable")
    )
    assert not disabled["local_texture"]["enabled"]
    assert (
        project / "revisions" / parent["revision"] / "recipe.toml"
    ).read_bytes() == original_recipe
    np.testing.assert_array_equal(saved_layers(project, disabled["revision"], master)[0], base)


@pytest.mark.parametrize("change_alpha", [False, True])
def test_texture_repair_preserves_partial_lock_and_reports_alpha_rebind(tmp_path, change_alpha):
    from blackmask.effects import saved_effect_lock_layers
    from blackmask.review import review_project

    project, _, parent = texture_fixture(tmp_path)
    master = parent["developed_id"]
    textured = operations.apply_operation(project, texture_request(project))
    operations.accept_revision(project, textured["revision"])
    selected, before_alpha, before = saved_layers(project, textured["revision"], master)
    locked = (1, 3)
    assert 0 < before_alpha[locked] < 65535
    assert np.any(selected[locked] != saved_layers(project, parent["revision"], master)[0][locked])
    filename = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [3, 1, 4, 2],
                "revision": textured["revision"],
            },
            rectangle("repair", [1, 1, 2, 3]),
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    np.testing.assert_array_equal(
        saved_effect_lock_layers(project, prepared["revision"], master)[0], selected
    )
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
            project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 2, 3])
        )
    rgb, alpha, manifest = saved_layers(project, repaired["revision"], master)
    assert alpha[locked] == before_alpha[locked]
    np.testing.assert_array_equal(rgb[locked], selected[locked])
    assert manifest["local_texture"]["stale"] is change_alpha
    if not change_alpha:
        np.testing.assert_array_equal(alpha, before_alpha)
        assert np.any(rgb[0, 2:5] != selected[0, 2:5])
        return

    review = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
    assert "BASE" in review["label"] and "local_texture_stale" in review["stale_labels"]
    with pytest.raises(ProjectError, match="Stale.*texture"):
        export_project(project, revision=repaired["revision"], draft=True)
    with pytest.raises(ProjectError, match="Stale.*texture"):
        operations.accept_revision(project, repaired["revision"])
    assert export_project(project)["revision"] == textured["revision"]
    disabled = operations.apply_operation(
        project, texture_request(project, settings=SETTINGS | {"enabled": False}, mode="disable")
    )
    assert disabled["local_texture"]["alpha_sha256"] == before["local_texture"]["alpha_sha256"]
    with pytest.raises(ProjectError, match="Stale.*alpha"):
        operations.apply_operation(project, texture_request(project, mode="saved"))
    rebuilt = operations.apply_operation(project, texture_request(project))
    assert rebuilt["local_texture"]["alpha_sha256"] != before["local_texture"]["alpha_sha256"]
    np.testing.assert_array_equal(
        saved_layers(project, rebuilt["revision"], master)[0][locked], selected[locked]
    )
    assert (
        read_revision(project, textured["revision"], master)["local_texture"]
        == before["local_texture"]
    )


def test_texture_warm_validation_reuses_geometry_but_rechecks_operand_bytes(tmp_path):
    from blackmask import texture

    project, _, parent = texture_fixture(tmp_path)
    revision = operations.apply_operation(project, texture_request(project))["revision"]
    with patch.object(
        texture, "rasterize_effect_area", wraps=texture.rasterize_effect_area
    ) as rasterize:
        with _validation_scope():
            read_revision(project, revision, parent["developed_id"])
        calls = rasterize.call_count
        with _validation_scope():
            read_revision(project, revision, parent["developed_id"])
        assert rasterize.call_count == calls
        area = project / "revisions" / revision / "effects/texture/area.json"
        area.write_bytes(area.read_bytes() + b" ")
        with _validation_scope(), pytest.raises(ProjectError, match="hash mismatch"):
            read_revision(project, revision, parent["developed_id"])


def test_texture_keeps_the_submitted_manifest_identity_through_capture(tmp_path, monkeypatch):
    from blackmask import effects
    from blackmask.assets import store_asset
    from blackmask.ingest import write_developed

    project, _, parent = texture_fixture(tmp_path)
    revision = parent["revision"]
    manifest_path = project / "revisions" / revision / "manifest.json"
    original = manifest_path.read_bytes()
    replacement_rgb, _, _ = saved_layers(project, revision, parent["developed_id"])
    replacement_rgb[:, 0] = 50000
    replacement = tmp_path / "replacement.tif"
    write_developed(replacement, replacement_rgb)
    revised = json.loads(original)
    revised["assets"]["foreground_rgb16.tif"] = store_asset(project, replacement)
    state, recipe = ((project / name).read_bytes() for name in ("state.json", "recipe.toml"))
    published = set((project / "revisions").glob("rev-*"))

    run_effects = effects.run_effects

    def swap_parent_then_run(*args, **kwargs):
        manifest_path.write_bytes(_json_bytes(revised))
        return run_effects(*args, **kwargs)

    monkeypatch.setattr(effects, "run_effects", swap_parent_then_run)
    with pytest.raises(ProjectError, match="Stale raw revision manifest"):
        operations.apply_operation(
            project, texture_request(project), expected_revision_manifest_sha256=digest(original)
        )
    assert (project / "state.json").read_bytes() == state
    assert (project / "recipe.toml").read_bytes() == recipe
    assert set((project / "revisions").glob("rev-*")) == published


def test_texture_rechecks_pending_guidance_before_publication(tmp_path, monkeypatch):
    from blackmask import review

    project, _, _ = texture_fixture(tmp_path)
    region = {"id": "pending", "role": "unknown", "shape": "point", "xy": [1, 1]}
    operations.save_guidance_draft(
        project, request(project), [], [{"action": "upsert", "region": region}]
    )
    pointer = project / "viewer-draft.json"
    retained = tmp_path / "retained-viewer-draft.json"
    pointer.rename(retained)
    state, recipe = ((project / name).read_bytes() for name in ("state.json", "recipe.toml"))
    published = set((project / "revisions").glob("rev-*"))
    write_overview = review.write_revision_overview

    def write_overview_then_restore_draft(*args, **kwargs):
        result = write_overview(*args, **kwargs)
        retained.rename(pointer)
        assert operations.pending_guidance(project)["current"]
        return result

    monkeypatch.setattr(review, "write_revision_overview", write_overview_then_restore_draft)
    with pytest.raises(ProjectError, match="Stale viewer authoring identity"):
        operations.apply_operation(
            project,
            texture_request(project),
            expected_authoring_digest=operations.guidance_draft_digest(project),
        )
    assert (project / "state.json").read_bytes() == state
    assert (project / "recipe.toml").read_bytes() == recipe
    assert operations.pending_guidance(project)["current"]
    assert set((project / "revisions").glob("rev-*")) == published
