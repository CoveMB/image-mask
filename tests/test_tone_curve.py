"""Local tone curve precision and saved-project behavior using synthetic pixels."""

import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tomli_w
from PIL import Image
from test_effects import fixture_project
from test_exposure import exposure_request, rectangle
from test_matte_operations import StubSession, approve, run_matte
from test_operations import edits, request
from test_repair_operations import repair_request, run_repair
from test_shadow_fade import fade_request

from blackmask import operations
from blackmask.assets import revision_hashes, saved_asset
from blackmask.export import export_project, saved_layers
from blackmask.project import ProjectError, _json_bytes, digest, read_project, read_revision

POINTS = [[800, 550], [3200, 3800], [7000, 7000]]


def test_curve_rgb16_reference_and_exact_exclusions():
    from blackmask.tone_curve import apply_local_tone_curve

    neutral = [16000, 36000, 60000, 36000, 36000, 36000, 36000, 36000, 0]
    rgb = np.repeat(np.array([neutral], dtype=np.uint16)[..., None], 3, axis=2)
    alpha = np.array([[65535, 65535, 65535, 18000, 65535, 0, 65535, 65535, 65535]], np.uint16)
    support = np.array([[65535, 65535, 65535, 32768, 32768, 65535, 0, 65535, 65535]], np.uint16)
    protection = np.zeros(alpha.shape, dtype=bool)
    protection[0, 7] = True
    original_rgb, original_alpha = rgb.tobytes(), alpha.tobytes()
    result = apply_local_tone_curve(
        rgb, alpha, support, protection, {"enabled": True, "points": POINTS}
    )
    expected = [13166, 38391, 60000, 37220, 37220, 36000, 36000, 36000, 0]
    np.testing.assert_array_equal(result, np.repeat(np.array([expected])[..., None], 3, axis=2))
    assert result.dtype == np.uint16 and not np.shares_memory(result, rgb)
    for settings in (
        {"enabled": False, "points": POINTS},
        {"enabled": True, "points": []},
        {"enabled": True, "points": [[800, 800], [2000, 2000]]},
    ):
        identity = apply_local_tone_curve(rgb, alpha, support, protection, settings)
        np.testing.assert_array_equal(identity, rgb)
        assert not np.shares_memory(identity, rgb)
    assert rgb.tobytes() == original_rgb and alpha.tobytes() == original_alpha


def test_curve_gamut_cap_precedes_feather():
    from blackmask.tone_curve import apply_local_tone_curve

    rgb = np.array([[[62000, 34000, 8000], [62000, 34000, 8000]]], np.uint16)
    alpha = np.full((1, 2), 65535, np.uint16)
    support = np.array([[65535, 32768]], np.uint16)
    result = apply_local_tone_curve(
        rgb,
        alpha,
        support,
        np.zeros((1, 2), bool),
        {"enabled": True, "points": [[2000, 4000], [6000, 8500]]},
    )
    np.testing.assert_array_equal(result, [[[65535, 36026, 8625], [63800, 35032, 8318]]])


def test_curve_rejects_invalid_settings_or_operands():
    from blackmask.tone_curve import apply_local_tone_curve, validate_local_tone_curve

    for points in (
        [[3000, 3000], [2000, 5000]],
        [[3000, 3000], [3000, 5000]],
        [[3000, 3000], [5000, 3000]],
        [[900, 900], [1200, 800]],
        [[0, 5000]],
        [[5000, 10000]],
        [[-1, 2000]],
        [[value, value] for value in range(1, 8)],
        [[True, 500]],
        [[500.5, 900]],
        [[500, float("nan")]],
        [[float("inf"), 900]],
        [[2000]],
        [(5, 5)],
        None,
    ):
        with pytest.raises(ProjectError):
            validate_local_tone_curve({"enabled": False, "points": points})
    for settings in ({}, {"enabled": 1, "points": []}, {"enabled": True, "points": [], "x": 0}):
        with pytest.raises(ProjectError):
            validate_local_tone_curve(settings)

    rgb = np.zeros((2, 3, 3), dtype=np.uint16)
    alpha = np.zeros((2, 3), dtype=np.uint16)
    protection = np.zeros((2, 3), dtype=bool)
    for operands in (
        (rgb.astype(np.uint8), alpha, alpha, protection),
        (rgb[..., 0], alpha, alpha, protection),
        (rgb[..., :2], alpha, alpha, protection),
        (rgb, alpha.astype(np.uint8), alpha, protection),
        (rgb, alpha.T, alpha, protection),
        (rgb, alpha, alpha.astype(np.uint8), protection),
        (rgb, alpha, alpha.T, protection),
        (rgb, alpha, alpha, protection.astype(np.uint16)),
        (rgb, alpha, alpha, protection.T),
    ):
        with pytest.raises(ProjectError):
            apply_local_tone_curve(*operands, {"enabled": False, "points": []})


def curve_request(
    project,
    *,
    points=POINTS,
    enabled=True,
    settings_only=False,
    candidate=False,
    area=None,
    scope=(0, 0, 6, 4),
    **extra,
):
    fields = {
        "local_tone_curve": {"enabled": enabled, "points": points},
        "scope_xyxy": list(scope),
        "candidate_comparison": candidate,
    }
    if settings_only:
        fields["tone_curve_settings_only"] = True
    elif enabled and "support_file" not in extra:
        fields["tone_curve_area"] = (
            area
            if area is not None
            else {
                "regions": [rectangle("tone", [1, 0, 6, 4])],
                "protection": [rectangle("reflection", [2, 1, 3, 2])],
            }
        )
    return request(project, kind="effects", **fields, **extra)


def scalar_curve_request(project, **extra):
    support = np.zeros((4, 6), np.uint16)
    support[:, 4] = 65535
    protection = np.zeros((4, 6), np.uint8)
    protection[1, 4] = 255
    Image.fromarray(support).save(project / "curve-support.png")
    Image.fromarray(protection).save(project / "curve-protect.png")
    return curve_request(
        project,
        support_file="curve-support.png",
        tone_curve_protection_file="curve-protect.png",
        **extra,
    )


def test_curve_effect_replaces_area_and_reuses_current_operands(tmp_path, monkeypatch, capsys):
    from test_spatial_fade import spatial_settings

    from blackmask.cli import main
    from blackmask.recipe import Recipe

    rgb = np.full((4, 6, 3), 36000, np.uint16)
    project, _, parent = fixture_project(tmp_path, rgb)
    master = parent["developed_id"]
    recipe_path = project / "recipe.toml"
    recipe = tomllib.loads(recipe_path.read_text())
    assert "local_tone_curve" not in recipe
    parsed = Recipe.from_dict(recipe, master)
    base, alpha, _ = saved_layers(project, parent["revision"], master)
    recipe["notes"] = "pending unrelated work"
    recipe["local_exposure"] = {"enabled": True, "ev": 1.25}
    recipe["spatial_fade"] = spatial_settings(6, 4)
    recipe_bytes = (tomli_w.dumps(recipe) + "\n# retain exact consumed bytes\n").encode()
    recipe_path.write_bytes(recipe_bytes)
    operation = curve_request(project)
    request_path = project / "curve-request.json"
    request_path.write_text(json.dumps(operation, indent=4) + "\n")
    monkeypatch.setattr(
        "sys.argv", ["blackmask", "run", str(project), "--request", str(request_path)]
    )
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert parsed.local_tone_curve == {"enabled": False, "points": []}
    directory = project / "revisions" / result["revision"]
    selected, actual_alpha, first = saved_layers(project, result["revision"], master)
    assert selected[0, 1].tolist() == [38391] * 3
    np.testing.assert_array_equal(selected[1, 2], base[1, 2])
    np.testing.assert_array_equal(actual_alpha, alpha)
    assert (directory / "inputs/recipe.toml").read_bytes() == recipe_bytes
    assert (directory / "request.json").read_bytes() == request_path.read_bytes()
    assert tomllib.loads(recipe_path.read_text()) == dict(
        recipe, local_tone_curve=operation["local_tone_curve"]
    )
    assert (
        tomllib.loads((directory / "recipe.toml").read_text())["local_exposure"]["enabled"] is False
    )
    original_files = revision_hashes(first)

    updated = operations.apply_operation(
        project, curve_request(project, points=[[5000, 2500]], settings_only=True, candidate=True)
    )
    second = read_revision(project, updated["revision"], master)
    for name in ("support_sha256", "protection_sha256", "alpha_sha256", "area_sha256"):
        assert second["local_tone_curve"][name] == first["local_tone_curve"][name]
    assert original_files == revision_hashes(read_revision(project, result["revision"], master))

    replaced = operations.apply_operation(project, scalar_curve_request(project, candidate=True))
    selected, _, revised = saved_layers(project, replaced["revision"], master)
    np.testing.assert_array_equal(selected[:, :4], base[:, :4])
    np.testing.assert_array_equal(selected[1, 4], base[1, 4])
    assert selected[0, 4].tolist() == [38391] * 3
    assert revised["local_tone_curve"]["area_sha256"] is None
    before = recipe_path.read_bytes()
    repeated = operations.apply_operation(project, scalar_curve_request(project, candidate=True))
    assert repeated["reused"] and repeated["revision"] == replaced["revision"]
    assert recipe_path.read_bytes() == before


def test_curve_rejects_stale_or_corrupt_inputs_without_pointer_changes(tmp_path):
    from blackmask import effects, review
    from blackmask.project import _validation_scope

    project, _, parent = fixture_project(tmp_path)
    state_path = project / "state.json"
    before = state_path.read_bytes()
    with pytest.raises(ProjectError, match="saved"):
        operations.apply_operation(project, curve_request(project, enabled=False))
    operation = scalar_curve_request(project)
    support = project / "curve-support.png"
    Image.fromarray(np.zeros((2, 2), dtype=np.uint16)).save(support)
    with pytest.raises(ProjectError, match="align|dimensions"):
        operations.apply_operation(project, operation)
    operation = scalar_curve_request(project)
    original_overview = review.write_revision_overview

    def change_support(*args, **kwargs):
        result = original_overview(*args, **kwargs)
        support.write_bytes(support.read_bytes() + b"changed")
        return result

    with (
        patch.object(review, "write_revision_overview", change_support),
        pytest.raises(ProjectError, match="Stale"),
    ):
        operations.apply_operation(project, operation)
    assert state_path.read_bytes() == before

    operation = scalar_curve_request(project)
    with (
        patch.object(effects, "_atomic_json", side_effect=OSError("pointer interrupted")),
        pytest.raises((OSError, ProjectError), match="interrupt|unconfirmed"),
    ):
        operations.apply_operation(project, operation)
    assert state_path.read_bytes() == before
    master = parent["developed_id"]
    retained = [
        path.name
        for path in (project / "revisions").glob("rev-*")
        if path.name > parent["revision"]
    ]
    (recovered,) = retained
    operations.restore_revision(project, recovered, replace_drafts=True)
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(
            project,
            curve_request(
                project,
                candidate=True,
                area={"regions": [rectangle("other", [1, 0, 2, 4])], "protection": []},
                scope=(1, 0, 2, 4),
            ),
        )
    disabled = operations.apply_operation(project, curve_request(project, enabled=False))
    revision = disabled["revision"]
    directory = project / "revisions" / revision
    settings_name = "effects/tone-curve/settings.json"
    settings_path = directory / settings_name
    manifest_path = directory / "manifest.json"
    manifest_before = manifest_path.read_bytes()
    settings_before = settings_path.read_bytes()
    before = state_path.read_bytes()
    with _validation_scope():
        read_revision(project, revision, master)
        area_path = directory / "effects/tone-curve/area.json"
        area_path.write_text("{}")
        with pytest.raises(ProjectError, match="Unbound"):
            read_revision(project, revision, master)
        area_path.unlink()
        manifest = json.loads(manifest_before)
        bad = dict(manifest["local_tone_curve"], stale=0)
        settings_path.write_bytes(_json_bytes(bad))
        manifest["files"][settings_name] = digest(settings_path.read_bytes())
        manifest_path.write_bytes(_json_bytes(manifest))
        with pytest.raises(ProjectError, match="settings"):
            read_revision(project, revision, master)
        settings_path.write_bytes(settings_before)
        manifest_path.write_bytes(manifest_before)
        assert read_revision(project, revision, master)["local_tone_curve"]["enabled"] is False
    assert state_path.read_bytes() == before
    assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize("repairing,change_alpha", [(False, False), (True, False), (True, True)])
def test_curve_inherits_partial_rgb_lock_and_requires_alpha_rebuild(
    tmp_path, repairing, change_alpha
):
    from blackmask.effects import saved_effect_lock_layers
    from blackmask.review import review_project

    source = np.full((4, 6, 3), 36000, np.uint16)
    project, _, parent = fixture_project(tmp_path, source)
    curved = operations.apply_operation(project, curve_request(project))
    operations.accept_revision(project, curved["revision"])
    master = parent["developed_id"]
    frozen = export_project(project)
    selected, before_alpha, before = saved_layers(project, curved["revision"], master)
    assert selected[1, 3].tolist() == [38391] * 3
    assert 0 < before_alpha[1, 3] < 65535
    filename = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [3, 1, 4, 2],
                "revision": curved["revision"],
            },
            rectangle("repair", [1, 1, 2, 3]),
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    prepared_rgb, prepared_alpha, _ = saved_effect_lock_layers(
        project, prepared["revision"], master
    )
    np.testing.assert_array_equal(prepared_rgb, selected)
    np.testing.assert_array_equal(prepared_alpha, before_alpha)
    approve(project, prepared)
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (
            np.full(guide.shape, 0.75 if change_alpha else 0.25),
            {},
        ),
    ):
        result = (
            run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 2, 3]))
            if repairing
            else run_matte(project)
        )
    rgb, alpha, manifest = saved_layers(project, result["revision"], master)
    assert alpha[1, 3] == before_alpha[1, 3]
    np.testing.assert_array_equal(rgb[1, 3], selected[1, 3])
    assert manifest["local_tone_curve"]["stale"] is change_alpha
    if not change_alpha:
        np.testing.assert_array_equal(rgb, selected)
        return
    assert alpha[1, 1] != before_alpha[1, 1]
    refreshed = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
    assert "BASE" in refreshed["label"] and "local_tone_curve_stale" in refreshed["stale_labels"]
    state = read_project(project)
    assert state["latest_result_revision"] == state["accepted_revision"] == curved["revision"]
    with pytest.raises(ProjectError, match="Stale.*tone curve"):
        export_project(project, revision=result["revision"], draft=True)
    with pytest.raises(ProjectError, match="Stale.*tone curve"):
        operations.accept_revision(project, result["revision"])
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(
            project, curve_request(project, settings_only=True, candidate=True)
        )
    assert read_project(project) == state
    assert export_project(project)["directory"] == frozen["directory"]
    disabled = operations.apply_operation(project, curve_request(project, enabled=False))
    assert (
        disabled["local_tone_curve"]["alpha_sha256"] == before["local_tone_curve"]["alpha_sha256"]
    )
    assert disabled["local_tone_curve"]["stale"] is False
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(
            project, curve_request(project, settings_only=True, candidate=True)
        )
    rebuilt = operations.apply_operation(project, curve_request(project, candidate=True))
    assert not rebuilt["local_tone_curve"]["stale"]
    assert rebuilt["local_tone_curve"]["alpha_sha256"] != before["local_tone_curve"]["alpha_sha256"]
    np.testing.assert_array_equal(
        saved_layers(project, rebuilt["revision"], master)[0][1, 3], selected[1, 3]
    )


def test_curve_pipeline_and_pre_exposure_clipping(tmp_path):
    from blackmask.exposure import apply_exposure
    from blackmask.review import review_project
    from blackmask.shadow_fade import apply_shadow_fade, read_shadow_fade
    from blackmask.tone_curve import apply_local_tone_curve, read_local_tone_curve

    source = np.full((4, 6, 3), 30000, np.uint16)
    source[0, 1] = 52428
    project, _, parent = fixture_project(tmp_path, source)
    exposure = {"regions": [rectangle("exposure", [1, 0, 3, 1])], "protection": []}
    operations.apply_operation(project, exposure_request(project, area=exposure, ev=1))
    operations.apply_operation(
        project, curve_request(project, points=[[6000, 3500]], candidate=True)
    )
    result = operations.apply_operation(project, fade_request(project, amount=0.5, preserve=0))
    master = parent["developed_id"]
    rgb, alpha, manifest = saved_layers(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    published = json.loads(
        saved_asset(project, f"revisions/{result['revision']}/review/manifest.json").read_bytes()
    )
    refreshed = json.loads(Path(review_project(project)["manifest_file"]).read_bytes())
    expected = {"clipped_pixels": 1, "eligible_pixels": 2}
    assert (
        published["local_exposure_clipping"]
        == refreshed["effects"]["local_exposure"]["clipping"]
        == expected
    )
    support, protection, curve = read_local_tone_curve(project, directory, manifest, alpha)
    fade_support, fade_protection, fade = read_shadow_fade(project, directory, manifest, alpha)
    exposed = saved_layers(
        project, result["revision"], master, tone_curve_off=True, shadow_fade_off=True
    )[0]
    curved = apply_local_tone_curve(exposed, alpha, support, protection, curve["settings"])
    assert exposed[0, 1].tolist() == [65535] * 3
    assert np.any(curved[0, 2] != exposed[0, 2])
    wrong_order = apply_local_tone_curve(source, alpha, support, protection, curve["settings"])
    wrong_exposure_support = np.zeros(alpha.shape, np.uint16)
    wrong_exposure_support[0, 1:3] = 65535
    assert (
        apply_exposure(
            wrong_order,
            alpha,
            wrong_exposure_support,
            np.zeros(alpha.shape, bool),
            {"enabled": True, "ev": 1},
        )[1]["clipped_pixels"]
        == 0
    )
    faded = apply_shadow_fade(curved, alpha, fade_support, fade_protection, fade["settings"])
    np.testing.assert_array_equal(rgb, faded)
    np.testing.assert_array_equal(
        saved_layers(project, result["revision"], master, tone_curve_off=True)[0],
        apply_shadow_fade(exposed, alpha, fade_support, fade_protection, fade["settings"]),
    )
