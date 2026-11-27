import json
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tomli_w
from test_background_pattern_project import pattern_request, target_settings
from test_effects import fixture_project
from test_matte_operations import StubSession, run_matte
from test_mist_project import mist_request
from test_operations import edits, request
from test_repair_operations import repair_guides, repair_request
from test_resume import recovery_id

from blackmask import operations
from blackmask.assets import revision_asset
from blackmask.export import render_saved_result
from blackmask.project import ProjectError, _json_bytes, read_project, read_revision
from blackmask.repair import scalar16

EMPTY_AREA = {"coverage": [], "clear": [], "focus": None}


def cloud_settings(**changes):
    return {
        "enabled": True,
        "amount": 0.72,
        "tint_srgb": "#282828",
        "light_amount": 0.64,
        "seed": 12,
        "size": 0.32,
        "warp": 0.48,
        "center_xy": [3.18, 2.6],
        "radii_xy": [8.7, 5.0],
        **changes,
    }


def cloud_request(project, *, config=None, area=EMPTY_AREA, disable=False, candidate=True):
    return request(
        project,
        kind="effects",
        scope_xyxy=[0, 0, 6, 4],
        candidate_comparison=candidate,
        cloud={"action": "disable"}
        if disable
        else {"action": "apply", "settings": config or cloud_settings(), "area": area},
    )


def test_apply_and_disable_keep_an_editable_cloud_without_changing_acceptance(tmp_path):
    project, _, base = fixture_project(tmp_path)
    capture = (tmp_path / "source.tif").read_bytes()
    base_revision, developed_id = base["revision"], base["developed_id"]
    base_manifest = read_revision(project, base_revision, developed_id)
    base_result = render_saved_result(project, base_revision, developed_id)
    assert base_manifest["schema_version"] == 2
    assert operations.apply_operation(project, cloud_request(project, disable=True))["reused"]

    recipe = project / "recipe.toml"
    pending_cleanup = {"enabled": True, "strength": 0.13}
    recipe.write_text(
        tomli_w.dumps(dict(tomllib.loads(recipe.read_text()), color_cleanup=pending_cleanup))
    )
    config = cloud_settings(tint_srgb="#3a495b")
    applied = operations.apply_operation(
        project, cloud_request(project, candidate=False, config=config)
    )
    current = read_revision(project, applied["revision"], developed_id)
    assert current["schema_version"] == 3
    assert current["cloud"]["algorithm"] == "linear-srgb-cloud-v1"
    assert tomllib.loads(recipe.read_text())["color_cleanup"] == pending_cleanup
    for role in ("base_alpha16.png", "foreground_rgb16.tif"):
        assert current["assets"][role] == base_manifest["assets"][role]
    assert np.any(render_saved_result(project, applied["revision"], developed_id) != base_result)
    assert operations.apply_operation(project, cloud_request(project, config=config))["reused"]

    disabled = operations.apply_operation(project, cloud_request(project, disable=True))
    disabled_manifest = read_revision(project, disabled["revision"], developed_id)
    assert disabled_manifest["schema_version"] == 3
    assert disabled_manifest["cloud"]["settings"] == dict(
        current["cloud"]["settings"], enabled=False
    )
    for field in ("density_sha256", "light_sha256", "clear_sha256", "area_sha256"):
        assert disabled_manifest["cloud"][field] == current["cloud"][field]
    np.testing.assert_array_equal(
        render_saved_result(project, disabled["revision"], developed_id), base_result
    )
    assert operations.apply_operation(project, cloud_request(project, disable=True))["reused"]
    operations.restore_revision(project, applied["revision"], replace_drafts=True)
    assert read_project(project)["working_revision"] == applied["revision"]
    assert read_project(project)["accepted_revision"] == base_revision
    assert tomllib.loads(recipe.read_text())["cloud"]["tint_srgb"] == "#3A495B"
    assert (tmp_path / "source.tif").read_bytes() == capture


def test_cloud_appearance_changes_reuse_maps_and_normalize_tint(tmp_path):
    project, _, base = fixture_project(tmp_path)
    developed_id = base["developed_id"]
    black = cloud_settings(tint_srgb="#000000")
    first = operations.apply_operation(project, cloud_request(project, config=black))
    black_result = render_saved_result(project, first["revision"], developed_id)
    with (
        patch(
            "blackmask.cloud_store.make_cloud_fields",
            side_effect=AssertionError("fields regenerated"),
        ),
        patch(
            "blackmask.cloud_store.make_cloud_clear",
            side_effect=AssertionError("clearance regenerated"),
        ),
    ):
        charcoal = operations.apply_operation(project, cloud_request(project))
        custom = operations.apply_operation(
            project,
            cloud_request(
                project, config=cloud_settings(tint_srgb="#1a2B3c", amount=0.9, light_amount=0.2)
            ),
        )
        equivalent = operations.apply_operation(
            project,
            cloud_request(
                project, config=cloud_settings(tint_srgb="#1A2B3C", amount=0.9, light_amount=0.2)
            ),
        )
        again = operations.apply_operation(project, cloud_request(project, config=black))

    for revision in (charcoal, custom, again):
        for hash_field in ("density_sha256", "light_sha256", "clear_sha256", "area_sha256"):
            assert revision["cloud"][hash_field] == first["cloud"][hash_field]
    assert custom["cloud"]["settings"]["tint_srgb"] == "#1A2B3C"
    assert custom["revision"] != charcoal["revision"]
    assert equivalent["revision"] == custom["revision"]
    assert equivalent["reused"]
    assert np.any(render_saved_result(project, charcoal["revision"], developed_id) != black_result)
    np.testing.assert_array_equal(
        render_saved_result(project, again["revision"], developed_id), black_result
    )


def test_invisible_cloud_colours_have_distinct_execution_identities(tmp_path):
    project, _, base = fixture_project(tmp_path)
    developed_id = base["developed_id"]
    dark = operations.apply_operation(
        project, cloud_request(project, config=cloud_settings(amount=0, tint_srgb="#000000"))
    )
    light = operations.apply_operation(
        project, cloud_request(project, config=cloud_settings(amount=0, tint_srgb="#FFFFFF"))
    )
    assert dark["revision"] != light["revision"]
    assert dark["effects_reuse"]["request"] != light["effects_reuse"]["request"]
    np.testing.assert_array_equal(
        render_saved_result(project, dark["revision"], developed_id),
        render_saved_result(project, light["revision"], developed_id),
    )


def test_prepare_rebuilds_only_cloud_clearance_and_matte_inherits_it(tmp_path):
    project, _, base = fixture_project(tmp_path)
    developed_id = base["developed_id"]
    applied = operations.apply_operation(project, cloud_request(project))
    recipe = project / "recipe.toml"
    pending = tomli_w.dumps(dict(tomllib.loads(recipe.read_text()), cloud=cloud_settings(seed=439)))
    recipe.write_text(pending)
    lock = {
        "id": "partial",
        "role": "lock",
        "shape": "rectangle",
        "xyxy": [2, 0, 3, 1],
        "revision": base["revision"],
    }
    with patch(
        "blackmask.cloud_store.make_cloud_fields", side_effect=AssertionError("fields regenerated")
    ):
        prepared = operations.apply_operation(
            project, request(project, guide_edits_file=edits(project, [lock]))
        )
        directory = project / "revisions" / prepared["revision"]
        manifest = read_revision(project, prepared["revision"], developed_id)
        assert manifest["schema_version"] == 3
        assert (directory / "recipe.toml").read_text() == pending
        for field in ("settings", "density_sha256", "light_sha256", "area_sha256"):
            assert manifest["cloud"][field] == applied["cloud"][field]
        assert manifest["cloud"]["clear_sha256"] != applied["cloud"]["clear_sha256"]
        assert (
            scalar16(revision_asset(project, directory, manifest, "cloud/clear16.png"))[0, 2]
            == 65535
        )
        completed = run_matte(project)
    assert completed["cloud"] == manifest["cloud"]
    assert read_revision(project, completed["revision"], developed_id)["schema_version"] == 3
    assert recipe.read_text() == pending
    assert read_project(project)["accepted_revision"] == base["revision"]


def test_repair_resume_reuses_cloud_fields_with_changed_alpha(tmp_path):
    project, _, base = fixture_project(tmp_path)
    applied = operations.apply_operation(project, cloud_request(project))
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
    manifest = read_revision(project, resumed["revision"], base["developed_id"])
    alpha = scalar16(revision_asset(project, directory, manifest, "base_alpha16.png"))
    assert alpha[2, 2] == 40959 and alpha[0, 2] == 16384
    assert manifest["schema_version"] == 3
    assert manifest["cloud"] == applied["cloud"] == resumed["cloud"]
    assert read_project(project)["accepted_revision"] == base["revision"]


def test_cloud_and_other_effects_inherit_each_others_immutable_operands(tmp_path):
    project, _, base = fixture_project(tmp_path)
    mist = operations.apply_operation(project, mist_request(project))
    pattern = operations.apply_operation(project, pattern_request(project))
    cloud = operations.apply_operation(project, cloud_request(project))
    assert (
        cloud["mist"] == mist["mist"]
        and cloud["background_pattern"] == pattern["background_pattern"]
    )
    changed_pattern = operations.apply_operation(
        project, pattern_request(project, target_settings(strength=0.23))
    )
    assert changed_pattern["cloud"] == cloud["cloud"]
    assert changed_pattern["mist"] == mist["mist"]
    cloud_off = operations.apply_operation(project, cloud_request(project, disable=True))
    assert cloud_off["mist"] == mist["mist"]
    assert cloud_off["background_pattern"] == changed_pattern["background_pattern"]
    assert cloud_off["cloud"]["density_sha256"] == cloud["cloud"]["density_sha256"]
    assert read_project(project)["accepted_revision"] == base["revision"]


def test_cloud_before_and_after_visibility_failures_preserve_accepted_work(tmp_path):
    project, _, base = fixture_project(tmp_path)
    operation = cloud_request(project)
    state_before = (project / "state.json").read_bytes()
    original = set((project / "revisions").iterdir())
    with (
        patch("blackmask.effects.check_space", side_effect=ProjectError("synthetic low disk")),
        pytest.raises(ProjectError, match="synthetic low disk"),
    ):
        operations.apply_operation(project, operation)
    assert set((project / "revisions").iterdir()) == original
    assert (project / "state.json").read_bytes() == state_before

    with (
        patch("blackmask.effects._atomic_json", side_effect=OSError("synthetic state failure")),
        pytest.raises(
            ProjectError, match="Cloud publication.*visible revision.*synthetic state failure"
        ),
    ):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == state_before
    visible = max((project / "revisions").glob("rev-*")).name
    assert visible != base["revision"]
    assert read_revision(project, visible, base["developed_id"])["cloud"]["settings"]["enabled"]
    operations.restore_revision(project, visible, replace_drafts=True)
    state = read_project(project)
    assert state["working_revision"] == visible and state["accepted_revision"] == base["revision"]


@pytest.mark.parametrize(
    "tampering",
    [
        "old_schema",
        "unknown_schema",
        "no_record",
        "bad_dimensions",
        "map_binding",
        "bad_off_tint",
        "extra",
        "missing",
        "symlink",
    ],
)
def test_cloud_namespace_is_validated_when_disabled(tmp_path, tampering):
    project, _, _ = fixture_project(tmp_path)
    applied = operations.apply_operation(project, cloud_request(project))
    disabled = operations.apply_operation(project, cloud_request(project, disable=True))
    directory = project / "revisions" / disabled["revision"]
    revision, developed_id = disabled["revision"], disabled["developed_id"]
    manifest = read_revision(project, revision, developed_id)
    if tampering == "old_schema":
        manifest["schema_version"] = 2
    elif tampering == "unknown_schema":
        manifest["schema_version"] = 4
    elif tampering == "no_record":
        del manifest["cloud"]
    elif tampering == "bad_dimensions":
        manifest["cloud"]["width"] += 1
    elif tampering == "map_binding":
        manifest["cloud"]["density_sha256"] = manifest["cloud"]["light_sha256"]
    elif tampering == "bad_off_tint":
        manifest["cloud"]["settings"]["tint_srgb"] = "charcoal"
    elif tampering == "extra":
        (directory / "cloud/extra.json").write_text("{}")
    elif tampering == "missing":
        (directory / "cloud/area.json").unlink()
    else:
        (directory / "cloud/area.json").unlink()
        (directory / "cloud/area.json").symlink_to(
            project / "revisions" / applied["revision"] / "cloud/area.json"
        )
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError):
        read_revision(project, revision, developed_id)


def test_cloud_rejects_mixed_partial_and_duplicate_requests_before_staging(tmp_path):
    project, _, base = fixture_project(tmp_path)
    operation = cloud_request(project)
    original = set((project / "revisions").iterdir())
    with pytest.raises(ProjectError, match="exclusive"):
        operations.apply_operation(project, dict(operation, mist={"action": "disable"}))
    with pytest.raises(ProjectError, match="native"):
        operations.apply_operation(project, dict(operation, scope_xyxy=[0, 0, 5, 4]))
    path = project / "cloud-request.json"
    path.write_text(
        json.dumps(operation).replace('"amount": 0.72', '"amount": 0.72, "amount": 0.8')
    )
    with pytest.raises(ProjectError, match="[Dd]uplicate"):
        operations.apply_operation(project, operation, request_file=path)
    path.write_bytes(_json_bytes(operation) + b" " * 2_000_000)
    with pytest.raises(ProjectError, match="2000000"):
        operations.apply_operation(project, operation, request_file=path)
    assert set((project / "revisions").iterdir()) == original
    assert read_project(project)["working_revision"] == base["revision"]


def test_cloud_request_enforces_combined_area_budgets():
    from blackmask.cloud_store import validate_cloud_request

    developed_id = "a" * 64
    shape = {"role": "support", "shape": "rectangle", "xyxy": [0, 0, 1, 1], "feather_px": 0}
    strokes = {
        "role": "support",
        "shape": "stroke",
        "points": [[1, 1]] * 4096,
        "radius_px": 1,
        "feather_px": 1,
    }
    config = cloud_settings()
    for area in (
        dict(
            EMPTY_AREA,
            coverage=[dict(shape, id=f"a{i}") for i in range(32)],
            clear=[dict(shape, id=f"b{i}") for i in range(32)],
        ),
        dict(EMPTY_AREA, coverage=[dict(strokes, id="a")], clear=[dict(strokes, id="b")]),
    ):
        operation = {"action": "apply", "settings": config, "area": area}
        assert validate_cloud_request(operation, developed_id, 6, 4)["area"] == area
        enlarged = dict(area, clear=[*area["clear"], dict(area["clear"][0], id="over")])
        with pytest.raises(ProjectError, match="64 combined shapes and 8192 stroke points"):
            validate_cloud_request(dict(operation, area=enlarged), developed_id, 6, 4)


def test_cli_runs_only_a_closed_cloud_request(tmp_path, monkeypatch, capsys):
    from blackmask.cli import main

    project, _, base = fixture_project(tmp_path)
    operation = cloud_request(project)
    path = tmp_path / "cloud.json"
    monkeypatch.setattr(sys, "argv", ["blackmask", "run", str(project), "--request", str(path)])
    path.write_text(
        json.dumps(operation).replace('"amount": 0.72', '"amount": 0.72, "amount": 0.8')
    )
    assert main() != 0
    assert "Duplicate Cloud JSON field" in capsys.readouterr().err
    assert read_project(project)["working_revision"] == base["revision"]

    path.write_bytes(_json_bytes(operation))
    assert main() == 0
    applied = json.loads(capsys.readouterr().out)
    manifest = read_revision(project, applied["revision"], base["developed_id"])
    assert manifest["schema_version"] == 3
    assert manifest["cloud"]["settings"]["tint_srgb"] == "#282828"
