import json
import tomllib

import numpy as np
import pytest
from test_background import background_request, legacy_project
from test_background_light import light_request
from test_background_pattern import oval, pattern_settings
from test_effects import fixture_project
from test_matte_operations import run_matte
from test_operations import request
from test_spatial_fade import operands, spatial_settings
from test_spatial_fade_target import lit_project

from blackmask import effects, operations
from blackmask.assets import revision_asset, revision_hashes
from blackmask.export import render_background, render_saved_result, saved_layers
from blackmask.project import ProjectError, read_project, read_revision


def pattern_request(project, settings=None, **changes):
    return request(
        project,
        **{
            "kind": "effects",
            "scope_xyxy": [0, 0, 6, 4],
            "candidate_comparison": True,
            "background_pattern": settings if settings is not None else target_settings(),
            **changes,
        },
    )


def target_settings(**changes):
    return pattern_settings(
        **{"shapes": [oval(center_xy=[3, 2], radii_xy=[12, 12], tone="tone2")], **changes}
    )


def test_legacy_black_result_accepts_pattern_without_adding_a_base(tmp_path):
    project, base = legacy_project(tmp_path)
    master = base["developed_id"]
    recipe = project / "recipe.toml"
    original = recipe.read_bytes()
    before = render_saved_result(project, base["revision"], master)
    assert recipe.read_bytes() == original
    saved = operations.apply_operation(project, pattern_request(project))
    _, alpha, manifest = saved_layers(project, saved["revision"], master)
    assert "background" not in manifest
    after = render_saved_result(project, saved["revision"], master)
    assert np.any(alpha == 0) and np.any(alpha == 65535)
    assert np.all(before[alpha == 0] == 0) and np.all(after[alpha == 0] == 8224)
    np.testing.assert_array_equal(after[alpha == 65535], before[alpha == 65535])


def test_saved_pattern_never_enters_lit_fade_target(tmp_path):
    project, accepted, _, lit, light = lit_project(tmp_path)
    revision, master = lit["revision"], lit["developed_id"]
    baseline = render_saved_result(project, revision, master)
    _, alpha, previous = saved_layers(project, revision, master)
    assert np.any(alpha == 65535) and np.any(alpha == 0)

    saved = operations.apply_operation(project, pattern_request(project))
    result = render_saved_result(project, saved["revision"], master)
    np.testing.assert_array_equal(result[alpha == 65535], baseline[alpha == 65535])
    assert np.any(result[alpha == 0] != baseline[alpha == 0])
    assert np.all(result[alpha == 0] == 8224)
    assert (
        revision_hashes(read_revision(project, saved["revision"], master))["base_alpha16.png"]
        == (revision_hashes(previous)["base_alpha16.png"])
    )
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    unlit = operations.apply_operation(project, light_request(project, dict(light, enabled=False)))
    assert np.all(render_saved_result(project, unlit["revision"], master)[alpha == 0] == 8224)


def test_pattern_override_preserves_lit_target_and_partial_protection():
    alpha = np.array([[32768, 65535]], np.uint16)
    foreground = np.full((1, 2, 3), 30000, dtype=np.uint16)
    unpatterned = np.full_like(foreground, 4000)
    shown = np.full_like(foreground, 8224)
    fade = operands(
        dict(spatial_settings(2, 1), target="lit"), np.full(alpha.shape, 65535, np.uint16)
    )
    fade.protection[0, 0] = True
    result = render_background(
        foreground, alpha, unpatterned, spatial_fade=fade, display_background16=shown
    )
    np.testing.assert_array_equal(result[0, :, 0], [19112, 4000])


def test_pattern_inheritance_restore_and_field_reuse(tmp_path):
    project, _, accepted = fixture_project(tmp_path)
    master = accepted["developed_id"]
    saved_bytes = (project / "recipe.toml").read_bytes()
    read_project(project)
    assert (project / "recipe.toml").read_bytes() == saved_bytes
    settings = target_settings(generator={"version": 1, "style": "mixed", "seed": 7})
    settings["shapes"][0]["center_xy"] = [2.125, 2]
    generated = operations.apply_operation(project, pattern_request(project, settings))
    revision = generated["revision"]
    assert (
        operations.apply_operation(project, pattern_request(project, settings))["revision"]
        == revision
    )
    record = read_revision(project, revision, master)["background_pattern"]
    disabled = dict(settings, enabled=False, tones_srgb=["#010203", "#152020"])
    operations.apply_operation(project, pattern_request(project, disabled))
    operations.apply_operation(project, background_request(project, "#020203", 0.6))
    operations.apply_operation(project, request(project))
    rematte = run_matte(project)
    inherited = read_revision(project, rematte["revision"], master)["background_pattern"]
    assert inherited["weight_sha256"] == record["weight_sha256"]
    assert inherited["settings"] == disabled
    operations.restore_revision(project, revision, replace_drafts=True)
    assert tomllib.loads((project / "recipe.toml").read_text())["background_pattern"] == settings
    assert read_project(project)["accepted_revision"] == accepted["revision"]


def test_pattern_rejects_stale_tampered_and_partial_writes(tmp_path, monkeypatch):
    from blackmask.project import _validation_scope

    project, _, accepted = fixture_project(tmp_path)
    original_state = (project / "state.json").read_bytes()
    original_guides = (project / "guides.json").read_bytes()
    for invalid in (
        {"developed_id": "1" * 64},
        {"base_revision": "rev-001"},
        {"scope_xyxy": [0, 0, 1, 1]},
        {"background": {"color_srgb": "#000000", "variation": 0}},
    ):
        with pytest.raises(ProjectError):
            operations.apply_operation(project, pattern_request(project, **invalid))

    write = effects._atomic_json

    def fail_at_pointer(path, *args, **kwargs):
        if path.name == "state.json":
            raise OSError("interrupted")
        return write(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(effects, "_atomic_json", fail_at_pointer)
        with pytest.raises((OSError, ProjectError), match="interrupt|durability"):
            operations.apply_operation(project, pattern_request(project))
    assert (project / "state.json").read_bytes() == original_state
    assert (project / "guides.json").read_bytes() == original_guides

    path = max((project / "revisions").glob("rev-*"))
    master = accepted["developed_id"]
    operations.restore_revision(project, path.name, replace_drafts=True)
    with pytest.raises(ProjectError, match="candidate comparison"):
        operations.apply_operation(project, pattern_request(project, candidate_comparison=False))
    with _validation_scope():
        raw = json.loads((path / "manifest.json").read_bytes())
        read_revision(project, path.name, master)
        operand = revision_asset(project, path, raw, "background_pattern/weight16.png")
        operand.write_bytes(operand.read_bytes() + b"changed")
        with pytest.raises(ProjectError, match="hash|Hash"):
            read_revision(project, path.name, master)
