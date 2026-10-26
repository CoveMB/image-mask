"""Saved project contracts: shared operands, effective settings and publication history."""

import hashlib
import json
import tomllib
from unittest.mock import patch

import numpy as np
import pytest
import tomli_w
from test_effects import effect_request, fixture_project, shading_request
from test_ingest import saved_raster

from blackmask import operations
from blackmask.project import ProjectError, read_project


def manifest_for(project, revision):
    return json.loads((project / "revisions" / revision / "manifest.json").read_bytes())


def test_new_project_uses_developed_schema_and_preserves_identity_math(tmp_path):
    project, source, _ = fixture_project(tmp_path)
    state = read_project(project)
    assert state["schema_version"] == 2
    assert "master_id" not in state
    record = json.loads((project / "source.json").read_bytes())
    import tifffile

    pixels = tifffile.imread(
        saved_raster(project / "assets/developed" / (state["developed_id"] + ".tif"))
    )
    metadata_bytes = (
        json.dumps(record["metadata"], sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    assert (
        hashlib.sha256(metadata_bytes + pixels.astype("<u2").tobytes()).hexdigest()
        == state["developed_id"]
    )
    assert not (project / "masters").exists()
    assert np.any(source % 257)


def test_schema_one_refuses_without_creating_lock_or_changing_any_bytes(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    path = project / "state.json"
    state = json.loads(saved_raster(path).read_bytes())
    state["schema_version"] = 1
    path.write_text(json.dumps(state))
    (project / ".writer.lock").unlink()
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    for action in (lambda: read_project(project), lambda: operations.apply_operation(project, {})):
        with pytest.raises(ProjectError, match="schema|format"):
            action()
    assert {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    } == before


def test_opacity_only_adds_no_raster_assets_and_revisions_are_lightweight(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, shading_request(project, opacity=0.12))
    first_manifest = manifest_for(project, first["revision"])
    assert "base_alpha16.png" in first_manifest["assets"]
    before = {
        str(p.relative_to(project)): p.read_bytes()
        for p in (project / "assets").rglob("*")
        if p.is_file()
    }
    request = shading_request(project, opacity=0.24, opacity_only=True)
    with patch(
        "blackmask.effects.make_shadow_weight",
        side_effect=AssertionError("unexpected W generation"),
    ):
        second = operations.apply_operation(project, request)
    after = {
        str(p.relative_to(project)): p.read_bytes()
        for p in (project / "assets").rglob("*")
        if p.is_file()
    }
    assert after == before
    second_manifest = manifest_for(project, second["revision"])
    for name in ("foreground_rgb16.tif", "base_alpha16.png", "shadow_weight16.png"):
        assert first_manifest["assets"][name] == second_manifest["assets"][name]
    images = [
        p
        for p in (project / "revisions").glob("rev-*/**/*")
        if p.suffix.lower() in {".png", ".tif", ".jpg"}
    ]
    assert images and all(p.name == "preview.jpg" for p in images)


@pytest.mark.parametrize(
    "applied", ["color_cleanup", "shading", "local_exposure", "shadow_fade", "background"]
)
def test_effective_recipe_applies_override_preserves_consumed_and_unrelated_draft(
    tmp_path, applied
):
    project, _, _ = fixture_project(tmp_path)
    recipe_path = project / "recipe.toml"
    current = tomllib.loads(recipe_path.read_text())
    current["notes"] = "pending note, not applied by this effect"
    unrelated = "color_cleanup" if applied != "color_cleanup" else "shading"
    current[unrelated] = (
        {"enabled": False, "strength": 0.731}
        if unrelated == "color_cleanup"
        else {"enabled": False, "opacity": 0.219}
    )
    recipe_path.write_text(tomli_w.dumps(current))
    consumed = saved_raster(recipe_path).read_bytes()
    from test_background import background_request
    from test_exposure import exposure_request
    from test_shadow_fade import fade_request

    request = {
        "color_cleanup": lambda: effect_request(project, strength=0.61),
        "shading": lambda: shading_request(project, opacity=0.12),
        "local_exposure": lambda: exposure_request(project, ev=0.7),
        "shadow_fade": lambda: fade_request(project, amount=0.32),
        "background": lambda: background_request(project, color="#324456"),
    }[applied]()
    result = operations.apply_operation(project, request)
    directory = project / "revisions" / result["revision"]
    effective = tomllib.loads((directory / "recipe.toml").read_text())
    assert effective[applied] == request[applied]
    assert effective[unrelated] != current[unrelated]
    assert effective["notes"] != current["notes"]
    assert (directory / "inputs/recipe.toml").read_bytes() == consumed
    assert tomllib.loads(recipe_path.read_text())[unrelated] == current[unrelated]
    assert result["inputs_digest"] == operations.draft_digest(project)
    assert (
        operations.draft_digest(project)
        != manifest_for(project, result["revision"])["draft_digest"]
    )
    with pytest.raises(ProjectError, match="Stale final acceptance"):
        operations.accept_revision(project, result["revision"])
    operations.restore_revision(project, result["revision"], replace_drafts=True)
    assert tomllib.loads(recipe_path.read_text()) == effective


def test_latest_generated_survives_restore_accept_and_export(tmp_path):
    project, _, first = fixture_project(tmp_path)
    assert read_project(project).get("latest_result_revision") == first["revision"]
    second = operations.apply_operation(project, effect_request(project, strength=0.61))
    assert read_project(project)["latest_result_revision"] == second["revision"]
    operations.restore_revision(project, first["revision"], replace_drafts=True)
    operations.accept_revision(project, first["revision"])
    from blackmask.export import export_project

    export_project(project)
    assert read_project(project)["latest_result_revision"] == second["revision"]


def test_developed_foreground_reuses_the_single_developed_object(tmp_path):
    project, _, result = fixture_project(tmp_path)
    record = json.loads((project / "source.json").read_bytes())
    manifest = manifest_for(project, result["revision"])
    expected = {
        "path": f"assets/developed/{record['developed_id']}.tif",
        "sha256": record["developed_file_sha256"],
    }
    assert manifest["assets"]["foreground_rgb16.tif"] == expected
    duplicate = project / "assets" / (record["developed_file_sha256"] + ".tif")
    assert not duplicate.exists()


@pytest.mark.parametrize("record", ["source.json", "revision"])
def test_project_bound_record_versions_are_strict(tmp_path, record):
    project, _, result = fixture_project(tmp_path)
    path = (
        project / record
        if record != "revision"
        else project / "revisions" / result["revision"] / "manifest.json"
    )
    data = json.loads(path.read_bytes())
    data["schema_version"] = 1
    path.write_text(json.dumps(data))
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    with pytest.raises(ProjectError, match="schema|version|manifest|identity"):
        read_project(project)
    assert {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    } == before


@pytest.mark.parametrize(
    "reference", [None, {}, {"path": []}, {"path": "assets/a.png", "sha256": 5}]
)
def test_malformed_asset_bindings_are_actionable_project_errors(tmp_path, reference):
    project, _, result = fixture_project(tmp_path)
    directory = project / "revisions" / result["revision"]
    manifest = manifest_for(project, result["revision"])
    manifest["assets"]["base_alpha16.png"] = reference
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="asset|raster|binding"):
        read_project(project)


def test_published_revision_cannot_use_a_local_raster_fallback(tmp_path):
    from blackmask.project import digest

    project, _, result = fixture_project(tmp_path)
    directory = project / "revisions" / result["revision"]
    manifest = manifest_for(project, result["revision"])
    reference = manifest["assets"].pop("base_alpha16.png")
    local = directory / "base_alpha16.png"
    local.write_bytes((project / reference["path"]).read_bytes())
    manifest["files"]["base_alpha16.png"] = digest(local.read_bytes())
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="shared|raster"):
        read_project(project)


def test_state_directory_sync_failure_reports_observed_pointers_and_uncertainty(tmp_path):
    from blackmask import project as module

    project, _, first = fixture_project(tmp_path)
    original = module._sync_directory
    target = f"rev-{int(first['revision'][4:]) + 1:03d}"

    def failed_sync(path):
        if (
            path == project
            and json.loads((project / "state.json").read_bytes())["working_revision"] == target
        ):
            raise OSError("synthetic directory sync failure")
        return original(path)

    with (
        patch.object(module, "_sync_directory", side_effect=failed_sync),
        pytest.raises(ProjectError, match="durability.*uncertain.*observed") as caught,
    ):
        operations.apply_operation(project, effect_request(project, strength=0.61))
    state = read_project(project)
    assert state["working_revision"] == state["latest_result_revision"] == target
    assert state["accepted_revision"] == first["revision"]
    assert target in str(caught.value) and first["revision"] in str(caught.value)


def test_missing_shared_asset_map_is_an_actionable_project_error(tmp_path):
    from test_background import legacy_project

    project, result = legacy_project(tmp_path)
    directory = project / "revisions" / result["revision"]
    manifest = manifest_for(project, result["revision"])
    del manifest["assets"]
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="manifest|asset"):
        read_project(project)


@pytest.mark.parametrize("effect", ["color_cleanup", "shading", "local_exposure", "shadow_fade"])
@pytest.mark.parametrize("generation", ["matte", "repair", "completed_resume"])
@pytest.mark.parametrize("noncanonical_guides", [False, True])
def test_completed_matte_recipe_records_inherited_effects_and_preserves_pending_draft(
    tmp_path, effect, generation, noncanonical_guides
):
    from test_background import background_request
    from test_exposure import exposure_request
    from test_matte_operations import approve, run_matte
    from test_operations import request
    from test_repair_operations import repair_guides, repair_request, run_repair
    from test_resume import interrupted

    from blackmask.project import digest

    project, _, _ = fixture_project(tmp_path)
    from test_shadow_fade import fade_request

    applied = operations.apply_operation(
        project,
        {
            "color_cleanup": lambda: effect_request(project, strength=0.61),
            "shading": lambda: shading_request(project, opacity=0.12),
            "local_exposure": lambda: exposure_request(project, ev=0.7),
            "shadow_fade": lambda: fade_request(project, amount=0.32),
        }[effect](),
    )
    operations.accept_revision(project, applied["revision"])
    recipe_path = project / "recipe.toml"
    actual = tomllib.loads(recipe_path.read_text())[effect]
    pending = tomllib.loads(recipe_path.read_text())
    key = {
        "color_cleanup": "strength",
        "shading": "opacity",
        "local_exposure": "ev",
        "shadow_fade": "amount",
    }[effect]
    pending[effect][key] += 0.1
    recipe_path.write_text(tomli_w.dumps(pending))
    if noncanonical_guides:
        if generation == "repair":
            repair_guides(project, [1, 1, 5, 3])
        guides_path = project / "guides.json"
        guides_path.write_text(json.dumps(json.loads(guides_path.read_bytes()), indent=4) + "\n\n")
    if generation == "repair":
        if noncanonical_guides:
            prepared = operations.apply_operation(project, request(project))
            approve(project, prepared)
        else:
            prepared = repair_guides(project, [1, 1, 5, 3])
        result = run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 5, 3]))
    else:
        prepared = operations.apply_operation(project, request(project))
        approve(project, prepared)
        if generation == "completed_resume":
            operation_id = interrupted(project, "_publish_new_directory")
            with patch(
                "blackmask.operations.VitMatteSession",
                side_effect=AssertionError("No model during completed resume"),
            ):
                result = operations.resume_operation(project, operation_id)
        else:
            result = run_matte(project)
    directory = project / "revisions" / result["revision"]
    effective = tomllib.loads((directory / "recipe.toml").read_text())
    assert effective[effect] == actual
    assert (directory / "guides.json").read_bytes() == (
        directory / "inputs/guides.json"
    ).read_bytes()
    assert tomllib.loads((directory / "inputs/recipe.toml").read_text())[effect] == pending[effect]
    assert tomllib.loads(recipe_path.read_text())[effect] == pending[effect]
    effective_digest = digest(
        (directory / "recipe.toml").read_bytes() + b"\0" + (directory / "guides.json").read_bytes()
    )
    assert manifest_for(project, result["revision"])["draft_digest"] == effective_digest
    assert result["revision_inputs_digest"] == effective_digest != result["inputs_digest"]
    with pytest.raises(ProjectError, match="Stale final acceptance"):
        operations.accept_revision(project, result["revision"])
    followup = operations.apply_operation(project, background_request(project, color="#324456"))
    assert (
        tomllib.loads((project / "revisions" / followup["revision"] / "recipe.toml").read_text())[
            effect
        ]
        == actual
    )
    assert tomllib.loads(recipe_path.read_text())[effect] == pending[effect]
    operations.restore_revision(project, result["revision"], replace_drafts=True)
    assert tomllib.loads(recipe_path.read_text()) == effective


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("invalid", ["symlink", "traversal", "wrong_role"])
def test_shared_operand_confinement_and_role_rejection_preserve_project(tmp_path, warm, invalid):
    from blackmask import assets
    from blackmask import project as module

    project, _, result = fixture_project(tmp_path)
    for cached in (
        assets._validate_role,
        module._validate_background_semantics,
        module._validate_exposure_semantics,
        module._validate_shadow_fade_semantics,
    ):
        cached.cache_clear()
    if warm:
        read_project(project)
    manifest = manifest_for(project, result["revision"])
    reference = manifest["assets"]["base_alpha16.png"]
    if invalid == "symlink":
        path = project / reference["path"]
        retained = tmp_path / "retained-alpha.png"
        path.rename(retained)
        path.symlink_to(retained)
    elif invalid == "traversal":
        reference["path"] = "assets/../" + reference["path"]
    else:
        manifest["assets"]["base_alpha16.png"] = dict(manifest["assets"]["trimap.png"])
    (project / "revisions" / result["revision"] / "manifest.json").write_text(json.dumps(manifest))
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    with pytest.raises(ProjectError, match="symlink|binding|role|precision"):
        read_project(project)
    assert {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    } == before
    if invalid == "symlink":
        assert path.is_symlink() and path.read_bytes() == retained.read_bytes()


def test_completed_matte_does_not_activate_effects_without_generated_records(tmp_path):
    from test_exposure import exposure_request
    from test_matte_operations import approve, run_matte
    from test_operations import request
    from test_shadow_fade import fade_request

    project, _, _ = fixture_project(tmp_path)
    path = project / "recipe.toml"
    pending = tomllib.loads(path.read_text())
    for name, operation in (
        ("color_cleanup", effect_request(project, strength=0.61)),
        ("shading", shading_request(project, opacity=0.12)),
        ("local_exposure", exposure_request(project, ev=0.7)),
        ("shadow_fade", fade_request(project, amount=0.32)),
    ):
        pending[name] = operation[name]
    path.write_text(tomli_w.dumps(pending))
    prepared = operations.apply_operation(project, request(project))
    approve(project, prepared)
    result = run_matte(project)
    directory = project / "revisions" / result["revision"]
    effective = tomllib.loads((directory / "recipe.toml").read_text())
    manifest = manifest_for(project, result["revision"])
    for name in ("color_cleanup", "shading", "local_exposure", "shadow_fade"):
        assert name not in manifest and effective[name]["enabled"] is False
        assert tomllib.loads(path.read_text())[name] == pending[name]
    assert result["revision_inputs_digest"] != result["inputs_digest"]
    with pytest.raises(ProjectError, match="Stale final acceptance"):
        operations.accept_revision(project, result["revision"])
