"""Source-supported local exposure math, saved state and offline controls."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_effects import effect_request, fixture_project, shading_request
from test_matte_operations import approve, run_matte
from test_operations import edits, request

from blackmask import operations
from blackmask.export import export_project, saved_layers
from blackmask.project import ProjectError, read_project, read_revision


def test_exposure_preserves_alpha_and_excluded_rgb():
    from blackmask.exposure import apply_exposure

    foreground = np.full((1, 6, 3), 20000, np.uint16)
    alpha = np.array([[65535, 21845, 0, 21845, 65535, 21845]], np.uint16)
    support = np.array([[65535, 65535, 65535, 65535, 0, 32768]], np.uint16)
    protection = np.array([[False, False, False, True, False, False]])
    inputs = [a.copy() for a in (foreground, alpha, support, protection)]
    result, counts = apply_exposure(
        foreground, alpha, support, protection, {"enabled": True, "ev": 1}
    )
    assert np.all(result[0, 0] > foreground[0, 0])
    np.testing.assert_array_equal(result[0, 0], result[0, 1])  # Alpha never scales gain.
    assert np.all((result[0, 5] > foreground[0, 5]) & (result[0, 5] < result[0, 0]))
    np.testing.assert_array_equal(result[0, [2, 3, 4]], foreground[0, [2, 3, 4]])
    for actual, before in zip((foreground, alpha, support, protection), inputs, strict=True):
        np.testing.assert_array_equal(actual, before)
    assert counts == {"clipped_pixels": 0, "eligible_pixels": 3}


def test_ev_math_identity_and_clipping():
    from blackmask.exposure import apply_exposure

    rgb = np.array([[[0, 1000, 32768], [65535, 60000, 40000]]], np.uint16)
    alpha = np.full((1, 2), 65535, np.uint16)
    protection = np.zeros((1, 2), bool)
    for ev in (-3, -1, 1, 3):
        result, counts = apply_exposure(rgb, alpha, alpha, protection, {"enabled": True, "ev": ev})
        expected = []
        clipped = 0
        for pixel in rgb[0]:
            linear = [
                v / 65535 / 12.92 if v / 65535 <= 0.04045 else ((v / 65535 + 0.055) / 1.055) ** 2.4
                for v in pixel
            ]
            exposed = [v * 2**ev for v in linear]
            clipped += any(v > 1 for v in exposed)
            expected.append(
                [
                    round(
                        65535
                        * (
                            12.92 * min(v, 1)
                            if min(v, 1) <= 0.0031308
                            else 1.055 * min(v, 1) ** (1 / 2.4) - 0.055
                        )
                    )
                    for v in exposed
                ]
            )
        np.testing.assert_array_equal(result[0], expected)
        assert counts == {"clipped_pixels": clipped, "eligible_pixels": 2}
    for settings in ({"enabled": True, "ev": 0}, {"enabled": False, "ev": 3}):
        result, counts = apply_exposure(rgb, alpha, alpha, protection, settings)
        np.testing.assert_array_equal(result, rgb)
        assert counts["clipped_pixels"] == 0


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        {"enabled": 1, "ev": 1},
        {"enabled": True, "ev": True},
        {"enabled": True, "ev": float("nan")},
        {"enabled": True, "ev": float("inf")},
        {"enabled": True, "ev": -3.1},
        {"enabled": True, "ev": 3.1},
        {"enabled": True, "ev": 2**100},
        {"enabled": True, "ev": 1, "extra": 0},
    ],
)
def test_exposure_rejects_invalid_settings(settings):
    from blackmask.exposure import validate_exposure

    with pytest.raises(ProjectError):
        validate_exposure(settings)


def test_exposure_rejects_invalid_registration():
    from blackmask.exposure import apply_exposure

    rgb = np.ones((2, 3, 3), np.uint16)
    alpha = np.ones((2, 3), np.uint16)
    protection = np.zeros((2, 3), bool)
    for inputs in (
        (rgb.astype(np.uint8), alpha, alpha, protection),
        (rgb, alpha[:, :2], alpha, protection),
        (rgb, alpha, alpha.astype(float), protection),
        (rgb, alpha, alpha, protection.astype(np.uint16)),
    ):
        with pytest.raises(ProjectError):
            apply_exposure(*inputs, {"enabled": True, "ev": 1})


def rectangle(identifier, box, feather=0):
    return {
        "id": identifier,
        "role": "support",
        "shape": "rectangle",
        "xyxy": box,
        "feather_px": feather,
    }


def test_area_uses_native_geometry_and_feather():
    from blackmask.exposure import rasterize_exposure_area

    area = {
        "regions": [rectangle("area", [2, 1, 8, 7], 3)],
        "protection": [rectangle("protected", [4, 3, 6, 5])],
    }
    support, protection = rasterize_exposure_area(area, "master", 10, 8)
    assert support.shape == (8, 10) and support.dtype == np.uint16
    assert support[1, 2] == 21845 and support[3, 4] == 65535
    assert not support[:, :2].any() and not support[:1].any()
    assert protection.sum() == 4 and protection[3, 4]
    for invalid in (
        {"regions": area["regions"]},
        dict(area, protection=[rectangle("p", [1, 1, 3, 3], 1)]),
        dict(area, regions=[rectangle("a", [-1, 0, 2, 2])]),
        dict(area, regions=[dict(rectangle("a", [0, 0, 2, 2]), role="unknown")]),
    ):
        with pytest.raises((ProjectError, ValueError)):
            rasterize_exposure_area(invalid, "master", 10, 8)


def exposure_request(project, *, ev=1, enabled=True, amount_only=False, area=None, **extra):
    fields = {
        "local_exposure": {"enabled": enabled, "ev": ev},
        "scope_xyxy": [0, 0, 6, 4],
        "candidate_comparison": True,
    }
    if amount_only:
        fields["exposure_amount_only"] = True
    elif enabled:
        fields["exposure_area"] = (
            area
            if area is not None
            else {
                "regions": [rectangle("area", [1, 0, 6, 4])],
                "protection": [rectangle("protect", [2, 1, 3, 2])],
            }
        )
    fields.update(extra)
    return request(project, kind="effects", **fields)


def test_saved_exposure_noncompounding_disable_compare_and_export(tmp_path):
    from blackmask.exposure import apply_exposure
    from blackmask.repair import scalar16
    from blackmask.review import review_project

    project, source, parent = fixture_project(tmp_path)
    base, alpha, _ = saved_layers(project, parent["revision"], read_project(project)["master_id"])
    accepted = read_project(project)["accepted_revision"]
    with patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("No model")):
        first = operations.apply_operation(project, exposure_request(project))
        rgb, actual_alpha, manifest = saved_layers(
            project, first["revision"], read_project(project)["master_id"]
        )
        directory = project / "revisions" / first["revision"] / "effects/exposure"
        support = scalar16(directory / "support16.png")
        protection = scalar16(directory / "protection16.png") != 0
        expected, counts = apply_exposure(
            base, alpha, support, protection, {"enabled": True, "ev": 1}
        )
        np.testing.assert_array_equal(rgb, expected)
        np.testing.assert_array_equal(actual_alpha, alpha)
        assert np.any(rgb != base) and np.array_equal(rgb[1, 2], base[1, 2])
        assert manifest["local_exposure"]["enabled"]
        for ev in (1, 0.5, 0, -1):
            changed = operations.apply_operation(
                project, exposure_request(project, ev=ev, amount_only=True)
            )
            expected, _ = apply_exposure(
                base, alpha, support, protection, {"enabled": True, "ev": ev}
            )
            np.testing.assert_array_equal(
                saved_layers(project, changed["revision"], read_project(project)["master_id"])[0],
                expected,
            )
        off_rgb = saved_layers(
            project, first["revision"], read_project(project)["master_id"], exposure_off=True
        )[0]
        np.testing.assert_array_equal(off_rgb, base)
        exported = Path(
            export_project(project, revision=first["revision"], draft=True)["directory"]
        )
        np.testing.assert_array_equal(tifffile.imread(exported / "foreground_rgb16.tif"), rgb)
        np.testing.assert_array_equal(
            tifffile.imread(exported / "unexposed_foreground_rgb16.tif"), base
        )
        assert (exported / "exposure_support16.png").is_file()
        assert (exported / "exposure_protection16.png").is_file()
        assert json.loads((exported / "manifest.json").read_bytes())["local_exposure"]["enabled"]
        reviewed = json.loads(
            Path(review_project(project, revision=first["revision"])["manifest_file"]).read_bytes()
        )
        assert reviewed["effects"]["local_exposure"]["clipping"] == counts
        disabled = operations.apply_operation(
            project, exposure_request(project, enabled=False, ev=0)
        )
        np.testing.assert_array_equal(
            saved_layers(project, disabled["revision"], read_project(project)["master_id"])[0], base
        )
        assert (
            project / "revisions" / disabled["revision"] / "effects/exposure/area.json"
        ).read_bytes() == (directory / "area.json").read_bytes()
        operations.restore_revision(project, first["revision"], replace_drafts=True)
        np.testing.assert_array_equal(
            saved_layers(project, first["revision"], read_project(project)["master_id"])[0], rgb
        )
    np.testing.assert_array_equal(source, base)
    assert read_project(project)["accepted_revision"] == accepted


def test_exposure_only_comparison_retains_cleanup_and_shading(tmp_path):
    from blackmask.effects import saved_shading

    project, _, _ = fixture_project(tmp_path)
    cleanup = operations.apply_operation(project, effect_request(project))
    shaded = operations.apply_operation(project, shading_request(project))
    base, alpha, before = saved_layers(
        project, shaded["revision"], read_project(project)["master_id"]
    )
    result = operations.apply_operation(project, exposure_request(project))
    rgb, _, manifest = saved_layers(
        project, result["revision"], read_project(project)["master_id"], exposure_off=True
    )
    np.testing.assert_array_equal(rgb, base)
    assert manifest["color_cleanup"] == before["color_cleanup"]
    assert manifest["shading"] == before["shading"]
    weight, opacity = saved_shading(project, result["revision"], alpha, manifest)
    assert weight is not None and opacity == 0.12
    rebuilt = operations.apply_operation(
        project, effect_request(project, strength=0.5, candidate_comparison=True)
    )
    assert rebuilt["local_exposure"]["settings"] == result["local_exposure"]["settings"]
    unexposed = saved_layers(
        project, rebuilt["revision"], read_project(project)["master_id"], exposure_off=True
    )[0]
    actual = saved_layers(project, rebuilt["revision"], read_project(project)["master_id"])[0]
    assert np.any(actual != unexposed)
    assert cleanup["color_cleanup"]["enabled"]


def test_area_replacement_requires_union_scope_and_restores_old_area(tmp_path):
    project, _, parent = fixture_project(tmp_path)
    area_a = {"regions": [rectangle("a", [1, 0, 2, 4])], "protection": []}
    area_b = {"regions": [rectangle("b", [4, 0, 5, 4])], "protection": []}
    operations.apply_operation(project, exposure_request(project, area=area_a))
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(
            project, exposure_request(project, area=area_b, scope_xyxy=[4, 0, 5, 4])
        )
    assert (project / "state.json").read_bytes() == before
    result = operations.apply_operation(project, exposure_request(project, area=area_b))
    rgb = saved_layers(project, result["revision"], read_project(project)["master_id"])[0]
    base = saved_layers(project, parent["revision"], read_project(project)["master_id"])[0]
    np.testing.assert_array_equal(rgb[:, 1], base[:, 1])
    assert np.any(rgb[:, 4] != base[:, 4])


@pytest.mark.parametrize(
    "fields",
    [
        {"exposure_amount_only": True},
        {"exposure_amount_only": 1},
        {"exposure_area": {"regions": [], "protection": []}},
        {"exposure_protection_file": "missing.png"},
        {"color_cleanup": {"enabled": False, "strength": 0.35}},
        {"shading": {"enabled": False, "opacity": 0}},
        {"unsupported": True},
    ],
)
def test_invalid_exposure_requests_preserve_state(tmp_path, fields):
    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.apply_operation(project, exposure_request(project, **fields))
    assert (project / "state.json").read_bytes() == before


def test_scalar_exposure_inputs_recheck_before_publication(tmp_path):
    from blackmask import review

    project, _, _ = fixture_project(tmp_path)
    support = np.full((4, 6), 65535, np.uint16)
    Image.fromarray(support).save(project / "area.png")
    Image.fromarray(np.zeros_like(support)).save(project / "protect.png")
    operation = exposure_request(project)
    operation.pop("exposure_area")
    operation.update(support_file="area.png", exposure_protection_file="protect.png")
    original = review.write_review
    before = (project / "state.json").read_bytes()

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        Image.fromarray(np.zeros_like(support)).save(project / "area.png")
        return result

    with patch.object(review, "write_review", changing), pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


def test_legacy_recipe_missing_exposure_loads_without_rewrite(tmp_path):
    import tomllib

    import tomli_w

    from blackmask.recipe import Recipe

    project, _, parent = fixture_project(tmp_path)
    path = project / "recipe.toml"
    recipe = tomllib.loads(path.read_text())
    recipe.pop("local_exposure", None)
    path.write_text(tomli_w.dumps(recipe))
    before = path.read_bytes()
    assert Recipe.from_dict(recipe, read_project(project)["master_id"]).local_exposure == {
        "enabled": False,
        "ev": 0,
    }
    assert path.read_bytes() == before
    assert "local_exposure" not in read_revision(
        project, parent["revision"], read_project(project)["master_id"]
    )


@pytest.mark.parametrize("change_alpha", [False, True])
@pytest.mark.parametrize("repairing", [False, True])
def test_exposure_inherits_through_partial_alpha_lock_and_matte_or_repair(
    tmp_path, change_alpha, repairing
):
    from test_matte_operations import StubSession
    from test_repair_operations import repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, exposure_request(project))
    before_rgb, before_alpha, _ = saved_layers(
        project, first["revision"], read_project(project)["master_id"]
    )
    assert 0 < before_alpha[1, 3] < 65535
    name = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [3, 1, 4, 2],
                "revision": first["revision"],
            },
            rectangle("repair", [1, 1, 5, 3]),
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
        repaired = (
            run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 5, 3]))
            if repairing
            else run_matte(project)
        )
    rgb, alpha, manifest = saved_layers(
        project, repaired["revision"], read_project(project)["master_id"]
    )
    assert manifest["local_exposure"]["stale"] is change_alpha
    np.testing.assert_array_equal(rgb[1, 3], before_rgb[1, 3])
    assert alpha[1, 3] == before_alpha[1, 3]
    if change_alpha:
        with pytest.raises(ProjectError, match="Stale"):
            export_project(project, revision=repaired["revision"], draft=True)
        with pytest.raises(ProjectError, match="Stale"):
            operations.apply_operation(project, exposure_request(project, amount_only=True))
        disabled = operations.apply_operation(
            project, exposure_request(project, enabled=False, ev=0)
        )
        assert not disabled["local_exposure"]["enabled"]
    else:
        np.testing.assert_array_equal(rgb, before_rgb)


def test_viewer_exposure_roundtrip_compare_security_and_stale_identity(tmp_path):
    import io
    import time

    from test_viewer import http, running

    project, _, _ = fixture_project(tmp_path)
    guides = (project / "guides.json").read_bytes()
    with running(project) as server:
        state = server.snapshot()
        operation = exposure_request(project)
        operation.pop("schema_version")
        operation.pop("kind")
        operation.update(action="effects", authoring_digest=state["authoring_digest"])
        assert (
            http(server, "/api/action", "POST", operation, Origin="https://attacker.invalid")[0]
            == 403
        )
        assert http(server, "/api/action", "POST", dict(operation, unknown=1))[0] == 400
        assert http(server, "/api/action", "POST", operation)[0] == 202
        for _ in range(200):
            current = server.snapshot()
            if not current["action"]["running"]:
                break
            time.sleep(0.01)
        assert not current["action"]["error"], current["action"]
        revision = current["working_revision"]
        record = next(r for r in current["revisions"] if r["revision"] == revision)
        assert record["exposure_area"] == operation["exposure_area"]
        assert record["local_exposure"]["clipping"]["eligible_pixels"] > 0
        image = np.array(
            Image.open(io.BytesIO(server.image(f"/image/black/{revision}/0,0,6,4/exposure-off")))
        )
        from blackmask.export import render_black

        rgb, alpha, _ = saved_layers(project, revision, current["master_id"], exposure_off=True)
        np.testing.assert_array_equal(
            image, np.rint(render_black(rgb, alpha) / 257).astype(np.uint8)
        )
        with pytest.raises(ProjectError, match="Stale"):
            server.execute(operation)
        assert http(server, "/image/black/" + revision + "/0,0,6,4/exposure-off")[0] == 200
    assert (project / "guides.json").read_bytes() == guides


def test_scalar_area_roundtrip_and_saved_disabled_validation(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    support = np.zeros((4, 6), np.uint16)
    support[:, 2:5] = 32768
    protection = np.zeros((4, 6), np.uint8)
    protection[1, 3] = 255
    Image.fromarray(support).save(project / "support.png")
    Image.fromarray(protection).save(project / "protected.png")
    operation = exposure_request(project)
    operation.pop("exposure_area")
    operation.update(support_file="support.png", exposure_protection_file="protected.png")
    result = operations.apply_operation(project, operation)
    assert result["local_exposure"]["area_sha256"] is None
    disabled = operations.apply_operation(project, exposure_request(project, enabled=False))
    directory = project / "revisions" / disabled["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    record = manifest["local_exposure"]
    record["settings"]["ev"] = True
    from blackmask.project import _json_bytes, digest

    settings = directory / "effects/exposure/settings.json"
    settings.write_bytes(_json_bytes(record))
    manifest["files"]["effects/exposure/settings.json"] = digest(settings.read_bytes())
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="EV"):
        read_revision(project, disabled["revision"], read_project(project)["master_id"])


@pytest.mark.parametrize(
    "filename", ["source.json", "recipe.toml", "guides.json", "request.json", "protected.png"]
)
def test_changed_exposure_inputs_abort_before_publication(tmp_path, filename):
    from blackmask import review

    project, _, _ = fixture_project(tmp_path)
    operation = exposure_request(project)
    if filename == "protected.png":
        operation.pop("exposure_area")
        Image.fromarray(np.full((4, 6), 65535, np.uint16)).save(project / "support.png")
        Image.fromarray(np.zeros((4, 6), np.uint16)).save(project / "protected.png")
        operation.update(support_file="support.png", exposure_protection_file="protected.png")
    operation_path = project / "request.json"
    operation_path.write_text(json.dumps(operation))
    before = (project / "state.json").read_bytes()
    original = review.write_review

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        path = project / filename
        path.write_bytes(path.read_bytes() + b" ")
        return result

    with patch.object(review, "write_review", changing), pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, operation, request_file=operation_path)
    assert (project / "state.json").read_bytes() == before


def test_interrupted_exposure_publication_retains_complete_revision_and_restore(tmp_path):
    from blackmask import effects

    project, _, parent = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    original = effects._atomic_json

    def interrupted(path, value, **kwargs):
        if path.name == "state.json":
            raise OSError("synthetic interrupted pointer")
        return original(path, value, **kwargs)

    with (
        patch.object(effects, "_atomic_json", interrupted),
        pytest.raises(OSError, match="interrupted"),
    ):
        operations.apply_operation(project, exposure_request(project))
    assert (project / "state.json").read_bytes() == before
    result = read_revision(project, "rev-003", read_project(project)["master_id"])
    assert result["local_exposure"]["enabled"]
    operations.restore_revision(project, "rev-003", replace_drafts=True)
    assert read_project(project)["working_revision"] == "rev-003"
    assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("enabled", 1),
        ("source_id", "foreign"),
        ("algorithm", "unknown"),
        ("stale", True),
        ("unsupported", True),
    ],
)
def test_saved_exposure_rejects_inconsistent_or_unsupported_record(tmp_path, field, value):
    from blackmask.project import _json_bytes, digest

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, exposure_request(project))
    master_id = read_project(project)["master_id"]
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["local_exposure"][field] = value
    settings = directory / "effects/exposure/settings.json"
    settings.write_bytes(_json_bytes(manifest["local_exposure"]))
    manifest["files"]["effects/exposure/settings.json"] = digest(settings.read_bytes())
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError):
        read_revision(project, result["revision"], master_id)
