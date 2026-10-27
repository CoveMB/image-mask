"""Independent light-field and selected-A contracts; synthetic pixels only."""

import copy
import json
import math
import tomllib

import numpy as np
import pytest
import tomli_w
from test_ingest import saved_raster


def light_settings(width=6, height=4, *, kind="oval", enabled=True, **changes):
    geometry = {
        "type": kind,
        "center_xy": [(width - 1) / 2, (height - 1) / 2],
        "rotation_degrees": 0.0,
    }
    if kind == "oval":
        geometry.update(radii_xy=[max(0.5, width * 0.35), max(0.5, height * 0.35)], softness=1.0)
    else:
        geometry["transition_width"] = max(width, height)
    return {
        "enabled": enabled,
        "brightness": 0.1,
        "color_srgb": "#FFFFFF",
        "geometry": geometry,
        **changes,
    }


def scalar_decode(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def scalar_encode(value):
    value = min(1, max(0, value))
    return round(
        65535 * (12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055)
    )


def scalar_light(settings, x, y):
    geometry = settings["geometry"]
    angle = math.radians(geometry["rotation_degrees"])
    dx, dy = x - geometry["center_xy"][0], y - geometry["center_xy"][1]
    u = math.cos(angle) * dx + math.sin(angle) * dy
    v = -math.sin(angle) * dx + math.cos(angle) * dy
    if geometry["type"] == "oval":
        radius = math.hypot(u / geometry["radii_xy"][0], v / geometry["radii_xy"][1])
        t = min(1, max(0, (1 - radius) / geometry["softness"]))
        weight = t * t * (3 - 2 * t)
    else:
        t = min(1, max(0, u / geometry["transition_width"] + 0.5))
        weight = 1 - t * t * (3 - 2 * t)
    peak = scalar_decode(settings["brightness"])
    return [
        scalar_encode(
            scalar_decode(int(settings["color_srgb"][i : i + 2], 16) / 255) * peak * weight
        )
        for i in (1, 3, 5)
    ]


@pytest.mark.parametrize("kind", ["oval", "directional"])
@pytest.mark.parametrize("shape", [(1, 1), (1, 7), (9, 1), (70, 11)])
@pytest.mark.parametrize("angle", [0, 37, 90, 359])
def test_native_light_matches_independent_scalar_centres(kind, shape, angle):
    from blackmask.background_light import make_background_light

    height, width = shape
    settings = light_settings(width, height, kind=kind, color_srgb="#91d3ef", brightness=0.125)
    settings["geometry"]["rotation_degrees"] = angle
    expected = np.array(
        [[scalar_light(settings, x, y) for x in range(width)] for y in range(height)], np.uint16
    )
    actual = make_background_light(shape, settings)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == np.uint16
    np.testing.assert_array_equal(
        make_background_light(shape, dict(settings, enabled=False)), expected
    )


@pytest.mark.parametrize("kind", ["oval", "directional"])
def test_light_sampling_extends_native_geometry_and_uses_bounded_rows(monkeypatch, kind):
    from blackmask import background_light

    settings = light_settings(11, 131, kind=kind)
    x, y = np.meshgrid(np.array([-30.5, 0, 5.5, 100]), np.array([-12, 0.25, 77, 170]))
    expected = np.array(
        [
            [scalar_light(settings, i, j) for i, j in zip(xx, yy, strict=True)]
            for xx, yy in zip(x, y, strict=True)
        ],
        np.uint16,
    )
    np.testing.assert_array_equal(
        background_light.sample_background_light((131, 11), settings, x, y), expected
    )
    sampler = background_light.sample_background_light
    calls = []

    def bounded(shape, settings, x, y):
        assert x.shape == y.shape and x.shape[0] <= 64
        calls.append(x.shape[0])
        return sampler(shape, settings, x, y)

    monkeypatch.setattr(background_light, "sample_background_light", bounded)
    actual = background_light.make_background_light((131, 11), settings)
    assert calls == [64, 64, 3]
    assert actual.shape == (131, 11, 3)


def test_oval_plateau_and_directional_monotonic_reverse():
    from blackmask.background_light import sample_background_light

    settings = light_settings(20, 10, brightness=1)
    settings["geometry"].update(center_xy=[10, 5], radii_xy=[8, 4], softness=0.5)
    xs = np.array([10, 14, 16, 18, 19])
    actual = sample_background_light((10, 20), settings, xs, np.full(xs.shape, 5))
    np.testing.assert_array_equal(actual[:, 0], [65535, 65535, scalar_encode(0.5), 0, 0])
    settings = light_settings(20, 10, kind="directional", brightness=1)
    settings["geometry"].update(center_xy=[10, 5], transition_width=8)
    xs = np.linspace(-10, 30, 81)
    light = sample_background_light((10, 20), settings, xs, np.full(xs.shape, 5))
    assert np.all(np.diff(light[:, 0].astype(int)) <= 0)
    assert light[0, 0] == 65535 and light[-1, 0] == 0
    settings["geometry"]["rotation_degrees"] = 180
    reverse = sample_background_light((10, 20), settings, xs, np.full(xs.shape, 5))
    np.testing.assert_array_equal(reverse, light[::-1])


@pytest.mark.parametrize("kind", ["oval", "directional"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", 1),
        ("brightness", True),
        ("brightness", -0.1),
        ("brightness", 1.01),
        ("brightness", float("nan")),
        ("brightness", float("inf")),
        ("color_srgb", "#gg0000"),
        ("color_srgb", "123456"),
        ("unknown", 0),
    ],
)
def test_invalid_settings_rejected_even_off(kind, field, value):
    from blackmask.background_light import validate_background_light

    settings = light_settings(kind=kind, enabled=False)
    settings[field] = value
    with pytest.raises(ValueError):
        validate_background_light(settings, 6, 4)


@pytest.mark.parametrize("kind", ["oval", "directional"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("center_xy", [-0.1, 0]),
        ("center_xy", [6.01, 0]),
        ("center_xy", [0, 4.01]),
        ("center_xy", [True, 0]),
        ("center_xy", [0]),
        ("rotation_degrees", 360),
        ("rotation_degrees", -1),
        ("rotation_degrees", float("nan")),
        ("unknown", 1),
    ],
)
def test_invalid_geometry_rejected_even_off(kind, field, value):
    from blackmask.background_light import validate_background_light

    settings = light_settings(kind=kind, enabled=False)
    settings["geometry"][field] = value
    with pytest.raises(ValueError):
        validate_background_light(settings, 6, 4)


@pytest.mark.parametrize(
    "kind,field,value",
    [
        ("oval", "radii_xy", [0.49, 1]),
        ("oval", "radii_xy", [1, 12.01]),
        ("oval", "radii_xy", [1, False]),
        ("oval", "softness", 0.049),
        ("oval", "softness", 1.001),
        ("oval", "softness", True),
        ("directional", "transition_width", 0.49),
        ("directional", "transition_width", 12.01),
        ("directional", "transition_width", float("inf")),
        ("directional", "transition_width", True),
    ],
)
def test_shape_specific_bounds(kind, field, value):
    from blackmask.background_light import validate_background_light

    settings = light_settings(kind=kind)
    settings["geometry"][field] = value
    with pytest.raises(ValueError):
        validate_background_light(settings, 6, 4)


def test_normalization_retains_fraction_and_owns_nested_geometry():
    from blackmask.background_light import normalized_background_light

    settings = light_settings(brightness=0.125, color_srgb="#aBcDeF")
    before = copy.deepcopy(settings)
    actual = normalized_background_light(settings, 6, 4)
    assert actual["color_srgb"] == "#ABCDEF" and actual["brightness"] == 0.125
    actual["geometry"]["center_xy"][0] = 0
    assert settings == before


@pytest.mark.parametrize("changes", [{"brightness": 0}, {"color_srgb": "#000000"}])
def test_zero_fields_and_disabled_combination_are_exact_identity(changes):
    from blackmask.background_light import combine_background_light, make_background_light

    base = np.arange(72, dtype=np.uint16).reshape(4, 6, 3) * 911
    before = base.copy()
    light = make_background_light((4, 6), light_settings(**changes))
    assert not light.any()
    np.testing.assert_array_equal(combine_background_light(base, light, enabled=True), base)
    np.testing.assert_array_equal(
        combine_background_light(base, np.full_like(base, 30000), enabled=False), base
    )
    np.testing.assert_array_equal(base, before)


def test_linear_combination_saturates_and_preserves_zero_pixels_without_mutation():
    from blackmask.background_light import combine_background_light

    base = np.array([[[123, 32768, 65535], [60000, 10000, 20000], [0, 0, 0]]], np.uint16)
    light = np.array([[[0, 0, 0], [50000, 30000, 20000], [12345, 32768, 65535]]], np.uint16)
    expected = np.array(
        [
            [
                [
                    scalar_encode(scalar_decode(int(b) / 65535) + scalar_decode(int(l) / 65535))
                    for b, l in zip(bb, ll, strict=True)
                ]
                for bb, ll in zip(base[0], light[0], strict=True)
            ]
        ],
        np.uint16,
    )
    before = base.copy(), light.copy()
    actual = combine_background_light(base, light, enabled=True)
    np.testing.assert_array_equal(actual, expected)
    assert actual[0, 1, 0] == 65535
    np.testing.assert_array_equal(actual[0, 0], base[0, 0])
    np.testing.assert_array_equal(base, before[0])
    np.testing.assert_array_equal(light, before[1])


def test_selected_unlit_target_and_single_alpha_preserve_opaque_pixels():
    from test_spatial_fade import operands, spatial_settings

    from blackmask.background_light import combine_background_light
    from blackmask.export import render_background

    alpha = np.array([[0, 1, 16384, 32768, 65534, 65535]], np.uint16)
    foreground = np.full((1, 6, 3), [31000, 42000, 53000], np.uint16)
    base = np.full_like(foreground, [1000, 3000, 5000])
    light = np.full_like(foreground, [12000, 16000, 22000])
    displayed = combine_background_light(base, light, enabled=True)
    spatial = operands(spatial_settings(6, 1), np.full(alpha.shape, 65535, np.uint16))
    spatial.protection[0, 3] = True
    actual = render_background(
        foreground, alpha, displayed, spatial_fade=spatial, fade_background16=base
    )
    off = render_background(foreground, alpha, base, spatial_fade=spatial, fade_background16=base)
    expected = np.empty_like(actual)
    for x in range(6):
        for channel in range(3):
            selected = (
                int(foreground[0, x, channel])
                if spatial.protection[0, x]
                else int(base[0, x, channel])
            )
            a = int(alpha[0, x]) / 65535
            expected[0, x, channel] = round(selected * a + int(displayed[0, x, channel]) * (1 - a))
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual[0, -1], off[0, -1])
    wrong_target = render_background(
        foreground, alpha, displayed, spatial_fade=spatial, fade_background16=displayed
    )
    assert np.any(wrong_target != expected)
    wrong_double_alpha = np.rint(
        off.astype(float)
        + (displayed.astype(float) - base) * (1 - alpha.astype(float)[..., None] / 65535) ** 2
    )
    assert np.any(wrong_double_alpha[:, 2:4] != expected[:, 2:4])


def light_request(project, settings=None, **extra):
    from test_operations import request

    return request(
        project,
        kind="effects",
        scope_xyxy=[0, 0, 6, 4],
        candidate_comparison=True,
        background_light=light_settings() if settings is None else settings,
        **extra,
    )


@pytest.mark.parametrize("kind", ["oval", "directional"])
@pytest.mark.parametrize("enabled", [True, False])
def test_saved_light_preserves_foreground_assets_and_effective_recipe(tmp_path, kind, enabled):
    from test_effects import fixture_project
    from test_ingest import saved_hashes

    from blackmask import operations
    from blackmask.background_light import read_background_light
    from blackmask.project import read_project, read_revision
    from blackmask.recipe import Recipe

    project, _, accepted = fixture_project(tmp_path)
    master = read_project(project)["developed_id"]
    before = read_revision(project, accepted["revision"], master)
    settings = light_settings(kind=kind, enabled=enabled, brightness=0.125, color_srgb="#aBcDeF")
    result = operations.apply_operation(project, light_request(project, settings))
    manifest = read_revision(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    pixels = read_background_light(project, directory, manifest)
    expected = np.array(
        [[scalar_light(settings, x, y) for x in range(6)] for y in range(4)], np.uint16
    )
    np.testing.assert_array_equal(pixels, expected)
    assert pixels.any(), "OFF must retain recoverable nonzero pixels"
    for name, checksum in saved_hashes(before).items():
        if name.endswith((".png", ".tif")):
            assert saved_hashes(manifest)[name] == checksum
    normalized = dict(settings, color_srgb="#ABCDEF")
    assert manifest["background_light"]["settings"] == normalized
    assert "background_light/light_rgb16.tif" in manifest["assets"]
    assert "background_light/settings.json" in manifest["files"]
    assert tomllib.loads((directory / "recipe.toml").read_text())["background_light"] == normalized
    document = tomllib.loads((project / "recipe.toml").read_text())
    assert Recipe.from_dict(document, master, dimensions_wh=(6, 4)).background_light == normalized
    assert read_project(project)["accepted_revision"] == accepted["revision"]


def test_enabled_only_light_inherits_exact_field_and_repeated_off_reuses(tmp_path, monkeypatch):
    from test_effects import fixture_project
    from test_ingest import saved_raster

    from blackmask import background_light, operations
    from blackmask.project import read_project

    project, _, accepted = fixture_project(tmp_path)
    settings = light_settings()
    first = operations.apply_operation(project, light_request(project, settings))
    first_directory = project / "revisions" / first["revision"]
    original = saved_raster(first_directory / "background_light/light_rgb16.tif").read_bytes()
    draft = tomllib.loads((project / "recipe.toml").read_text())
    draft["background"]["variation"] = 0.123
    (project / "recipe.toml").write_text(tomli_w.dumps(draft))

    def forbidden(*args, **kwargs):
        raise AssertionError("Enabled-only transitions must inherit encoded pixels")

    monkeypatch.setattr(background_light, "make_background_light", forbidden)
    disabled = operations.apply_operation(
        project, light_request(project, dict(settings, enabled=False))
    )
    assert (
        saved_raster(
            project / "revisions" / disabled["revision"] / "background_light/light_rgb16.tif"
        ).read_bytes()
        == original
    )
    assert tomllib.loads((project / "recipe.toml").read_text())["background"]["variation"] == 0.123
    before = (project / "state.json").read_bytes(), (project / "recipe.toml").read_bytes()
    repeated = operations.apply_operation(
        project, light_request(project, dict(settings, enabled=False))
    )
    assert repeated["reused"] and repeated["revision"] == disabled["revision"]
    assert before == ((project / "state.json").read_bytes(), (project / "recipe.toml").read_bytes())
    assert read_project(project)["accepted_revision"] == accepted["revision"]


def test_changed_off_apply_replaces_field_and_base_apply_preserves_pending_light(tmp_path):
    from test_background import background_request
    from test_effects import fixture_project
    from test_ingest import saved_raster

    from blackmask import operations
    from blackmask.project import read_project, read_revision

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, light_request(project))
    original = saved_raster(
        project / "revisions" / first["revision"] / "background_light/light_rgb16.tif"
    ).read_bytes()
    settings = light_settings(enabled=False, brightness=0.3, kind="directional")
    changed = operations.apply_operation(project, light_request(project, settings))
    current = saved_raster(
        project / "revisions" / changed["revision"] / "background_light/light_rgb16.tif"
    ).read_bytes()
    assert original != current
    draft = tomllib.loads((project / "recipe.toml").read_text())
    draft["background_light"]["geometry"]["center_xy"][0] = 0.125
    (project / "recipe.toml").write_text(tomli_w.dumps(draft))
    base = operations.apply_operation(project, background_request(project, "#123456", 0.2))
    manifest = read_revision(project, base["revision"], read_project(project)["developed_id"])
    assert manifest["background_light"]["settings"] == settings
    assert (
        saved_raster(
            project / "revisions" / base["revision"] / "background_light/light_rgb16.tif"
        ).read_bytes()
        == current
    )
    assert (
        tomllib.loads((project / "recipe.toml").read_text())["background_light"]
        == draft["background_light"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unbound",
        "missing",
        "hash",
        "algorithm",
        "identity",
        "settings",
        "zero",
        "profile",
        "dtype",
        "dimensions",
        "recipe",
        "extra_record",
    ],
)
def test_off_light_validation_rejects_tampering_even_in_warm_scope(tmp_path, mutation):
    import tifffile
    from test_effects import fixture_project
    from test_ingest import bind_raster, saved_hashes

    from blackmask import operations
    from blackmask.ingest import write_developed
    from blackmask.project import (
        ProjectError,
        _validation_scope,
        digest,
        read_project,
        read_revision,
    )

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(
        project, light_request(project, light_settings(enabled=False, brightness=0))
    )
    directory = project / "revisions" / result["revision"]
    master = read_project(project)["developed_id"]
    with _validation_scope():
        manifest = read_revision(project, result["revision"], master)
        if mutation == "unbound":
            (directory / "background_light/extra.json").write_text("{}")
        elif mutation == "missing":
            (directory / "background_light/settings.json").rename(
                directory / "retained-settings.json"
            )
        elif mutation == "hash":
            (directory / "background_light/settings.json").write_text("{}")
        else:
            record = manifest["background_light"]
            if mutation == "algorithm":
                record["algorithm"] = "unknown"
            elif mutation == "identity":
                record["developed_id"] = "0" * 64
            elif mutation == "extra_record":
                record["unknown"] = 1
            elif mutation == "settings":
                record["settings"]["geometry"]["rotation_degrees"] = True
                (directory / "background_light/settings.json").write_text(
                    json.dumps(record["settings"])
                )
            raster = directory / "background_light/light_rgb16.tif"
            if mutation == "zero":
                write_developed(raster, np.full((4, 6, 3), 1000, np.uint16))
            elif mutation == "profile":
                tifffile.imwrite(raster, np.zeros((4, 6, 3), np.uint16))
            elif mutation == "dimensions":
                write_developed(raster, np.zeros((2, 6, 3), np.uint16))
            elif mutation == "dtype":
                tifffile.imwrite(raster, np.zeros((4, 6, 3), np.uint8))
            elif mutation == "recipe":
                recipe = tomllib.loads((directory / "recipe.toml").read_text())
                recipe["background_light"]["brightness"] = 0.2
                (directory / "recipe.toml").write_text(tomli_w.dumps(recipe))
                manifest["files"]["recipe.toml"] = digest((directory / "recipe.toml").read_bytes())
            for name, key in [
                ("background_light/light_rgb16.tif", "light_sha256"),
                ("background_light/settings.json", "settings_sha256"),
            ]:
                bind_raster(project, directory, manifest, name)
                record[key] = saved_hashes(manifest)[name]
            (directory / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ProjectError):
            read_revision(project, result["revision"], master)


@pytest.mark.parametrize(
    "extra",
    [
        {"background": {"color_srgb": "#000000", "variation": 0}},
        {"shading": {"enabled": False, "opacity": 0}},
        {"support_file": "missing"},
    ],
)
def test_light_operation_is_exclusive_and_full_scope(tmp_path, extra):
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.project import ProjectError

    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.apply_operation(project, light_request(project, **extra))
    operation = light_request(project)
    operation["scope_xyxy"] = [1, 0, 5, 4]
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


def test_same_source_repair_inherits_light_without_regeneration_or_staleness(tmp_path, monkeypatch):
    from unittest.mock import patch

    from test_effects import fixture_project
    from test_ingest import saved_raster
    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair

    from blackmask import background_light, operations
    from blackmask.export import saved_layers
    from blackmask.project import read_project, read_revision

    project, _, accepted = fixture_project(tmp_path)
    applied = operations.apply_operation(project, light_request(project))
    master = read_project(project)["developed_id"]
    before = read_revision(project, applied["revision"], master)
    light_bytes = saved_raster(
        project / "revisions" / applied["revision"] / "background_light/light_rgb16.tif"
    ).read_bytes()
    old_alpha = saved_layers(project, applied["revision"], master)[1]

    def forbidden(*args, **kwargs):
        raise AssertionError("Inherited native light must never regenerate")

    monkeypatch.setattr(background_light, "make_background_light", forbidden)
    prepared = repair_guides(project, [2, 0, 4, 4])
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        result = run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [2, 0, 4, 4]))
    manifest = read_revision(project, result["revision"], master)
    assert manifest["background_light"] == before["background_light"]
    assert "stale" not in manifest["background_light"]
    assert (
        saved_raster(
            project / "revisions" / result["revision"] / "background_light/light_rgb16.tif"
        ).read_bytes()
        == light_bytes
    )
    assert np.any(saved_layers(project, result["revision"], master)[1] != old_alpha)
    assert read_project(project)["accepted_revision"] == accepted["revision"]


@pytest.mark.parametrize("existing", [True, False])
def test_prepare_cannot_apply_or_introduce_pending_light_before_model_work(
    tmp_path, monkeypatch, existing
):
    from test_effects import fixture_project
    from test_operations import request

    from blackmask import operations
    from blackmask.project import ProjectError

    project, _, _ = fixture_project(tmp_path)
    if existing:
        operations.apply_operation(project, light_request(project))
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["background_light"] = light_settings(brightness=0.4)
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    before = (project / "state.json").read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Reject pending light before any candidate/model processing")

    monkeypatch.setattr(operations, "select_candidates", forbidden)
    with pytest.raises(ProjectError, match="explicit Apply Background light"):
        operations.apply_operation(project, request(project))
    assert (project / "state.json").read_bytes() == before


def test_saved_native_result_uses_authoritative_light_without_generator(tmp_path, monkeypatch):
    from test_effects import fixture_project
    from test_ingest import bind_raster, saved_hashes

    from blackmask import background_light, operations
    from blackmask.background import read_background
    from blackmask.export import render_saved_result, saved_layers
    from blackmask.ingest import write_developed
    from blackmask.project import read_project, read_revision

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, light_request(project))
    directory = project / "revisions" / result["revision"]
    master = read_project(project)["developed_id"]
    foreground, alpha, manifest = saved_layers(project, result["revision"], master)
    custom = np.full_like(foreground, [10000, 20000, 30000])
    write_developed(directory / "background_light/light_rgb16.tif", custom)
    bind_raster(project, directory, manifest, "background_light/light_rgb16.tif")
    manifest["background_light"]["light_sha256"] = saved_hashes(manifest)[
        "background_light/light_rgb16.tif"
    ]
    (directory / "manifest.json").write_text(json.dumps(manifest))
    base = read_background(project, directory, manifest)
    expected = np.empty_like(foreground)
    for y in range(4):
        for x in range(6):
            a = int(alpha[y, x]) / 65535
            for channel in range(3):
                displayed = scalar_encode(
                    scalar_decode(int(base[y, x, channel]) / 65535)
                    + scalar_decode(int(custom[y, x, channel]) / 65535)
                )
                expected[y, x, channel] = round(
                    int(foreground[y, x, channel]) * a + displayed * (1 - a)
                )

    def forbidden(*args, **kwargs):
        raise AssertionError("Native reads must use saved pixels, not analytic generation")

    monkeypatch.setattr(background_light, "make_background_light", forbidden)
    monkeypatch.setattr(background_light, "sample_background_light", forbidden)
    read_revision(project, result["revision"], master)
    np.testing.assert_array_equal(
        render_saved_result(project, result["revision"], master), expected
    )


def scalar_light_composition(foreground, alpha, base, light, weight, protection):
    """Independent unrounded P and encoded displayed backdrop for preservation checks."""
    contribution = np.zeros(foreground.shape, float)
    displayed = np.empty_like(base)
    for y in range(len(alpha)):
        for x in range(alpha.shape[1]):
            a = int(alpha[y, x]) / 65535
            q = 0 if protection[y, x] or not a else int(weight[y, x]) / 65535
            for channel in range(3):
                f, b, l = (int(pixels[y, x, channel]) for pixels in (foreground, base, light))
                linear = scalar_decode(f / 65535) * (1 - q) + scalar_decode(b / 65535) * q
                selected = (
                    f
                    if q == 0
                    else b
                    if q == 1
                    else 65535
                    * (
                        12.92 * linear
                        if linear <= 0.0031308
                        else 1.055 * linear ** (1 / 2.4) - 0.055
                    )
                )
                contribution[y, x, channel] = selected * a
                displayed[y, x, channel] = scalar_encode(
                    scalar_decode(b / 65535) + scalar_decode(l / 65535)
                )
    return contribution, displayed


@pytest.mark.parametrize(
    "consumer",
    [
        "result",
        "background-light-off",
        "exposure-off",
        "shadow-fade-off",
        "sharpening-off",
        "base",
        "black",
        "gray",
        "white",
        "source",
        "alpha",
        "review",
        "export",
        "margins",
    ],
)
def test_native_consumers_keep_unlit_spatial_target_and_independent_light(tmp_path, consumer):
    import io
    from pathlib import Path

    import tifffile
    from PIL import Image
    from test_effects import fixture_project
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask import operations
    from blackmask.background import read_background
    from blackmask.effects import saved_spatial_fade
    from blackmask.export import export_project, saved_layers
    from blackmask.project import read_project
    from blackmask.review import review_project
    from blackmask.viewer import ReviewServer

    project, source, _ = fixture_project(tmp_path)
    protection = np.zeros((4, 6), np.uint16)
    protection[1, 3] = 65535
    Image.fromarray(protection).save(project / "protected.png")
    settings = spatial_settings(6, 4)
    settings["oval"].update(center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], transition_width=0.5)
    operations.apply_operation(
        project, spatial_request(project, settings, spatial_fade_protection_file="protected.png")
    )
    light = light_settings(kind="directional", brightness=0.45, color_srgb="#91D3EF")
    applied = operations.apply_operation(project, light_request(project, light))
    revision = applied["revision"]
    master = read_project(project)["developed_id"]
    foreground, alpha, manifest = saved_layers(project, revision, master)
    base = read_background(project, project / "revisions" / revision, manifest)
    light_pixels = np.array(
        [[scalar_light(light, x, y) for x in range(6)] for y in range(4)], np.uint16
    )
    spatial = saved_spatial_fade(project, revision, alpha, manifest)
    assert spatial.weight16[alpha == 65535].any()
    assert ((alpha > 0) & (alpha < 65535) & spatial.protection).any()
    contribution, displayed = scalar_light_composition(
        foreground, alpha, base, light_pixels, spatial.weight16, spatial.protection
    )
    factor = alpha.astype(float)[..., None] / 65535
    expected = np.rint(contribution + displayed * (1 - factor)).astype(np.uint16)
    if consumer in {"export", "margins"}:
        framing = (
            {"left_px": 1, "right_px": 2, "top_px": 2, "bottom_px": 1}
            if consumer == "margins"
            else None
        )
        exported = export_project(
            project,
            revision=revision,
            draft=True,
            framing=framing,
            variants=("editable", "black", "transparent"),
        )
        directory = Path(exported["directory"])
        wanted = expected
        if framing is not None:
            wanted = np.pad(displayed, ((2, 1), (1, 2), (0, 0)), mode="edge")
            wanted[2:6, 1:7] = expected
        np.testing.assert_array_equal(tifffile.imread(directory / "result_rgb16.tif"), wanted)
        native = (
            Path(exported["editable_companion"]["directory"]) if framing is not None else directory
        )
        np.testing.assert_array_equal(tifffile.imread(native / "background_rgb16.tif"), base)
        np.testing.assert_array_equal(
            tifffile.imread(native / "background_light_rgb16.tif"), light_pixels
        )
        assert json.loads((native / "background_light_settings.json").read_bytes()) == light
        assert (
            json.loads((directory / "manifest.json").read_bytes())["background_light"]
            == manifest["background_light"]
        )
        if framing is None:
            np.testing.assert_array_equal(
                tifffile.imread(directory / "black_rgb16.tif"),
                np.rint(contribution).astype(np.uint16),
            )
            rgba = np.array(Image.open(directory / "transparent_RGBA8_VIEW.png"))
            # Native straight RGBA retains hidden RGB; only series zeroes rounded-zero alpha.
            straight = np.divide(
                contribution, factor, out=foreground.astype(float).copy(), where=factor > 0
            )
            wanted_rgb = np.rint(straight / 257).astype(np.uint8)
            np.testing.assert_array_equal(rgba[..., :3], wanted_rgb)
        return
    if consumer == "review":
        reviewed = review_project(project, crops=[[2, 1, 6, 4]])
        directory = Path(reviewed["manifest_file"]).parent
        actual = np.array(Image.open(directory / "crop-000-result_RGB8_VIEW.png"))
        wanted = np.rint(expected[1:4, 2:6].astype(float) / 257).astype(np.uint8)
    else:
        panel = consumer if consumer in {"black", "gray", "white", "source", "alpha"} else "result"
        suffix = "" if consumer == panel else "/" + consumer
        identity = master if consumer == "source" else revision
        with ReviewServer(project) as server:
            actual = np.array(
                Image.open(io.BytesIO(server.image(f"/image/{panel}/{identity}/2,1,6,4{suffix}")))
            )
        if consumer == "source":
            wanted = np.rint(source.astype(float) / 257).astype(np.uint8)
        elif consumer == "alpha":
            wanted = np.repeat(
                np.rint(alpha.astype(float) / 257).astype(np.uint8)[..., None], 3, axis=-1
            )
        elif consumer == "base":
            wanted = np.rint(np.rint(foreground.astype(float) * factor) / 257).astype(np.uint8)
        elif consumer in {"gray", "white"}:
            wanted = np.rint(
                (contribution + (32768 if consumer == "gray" else 65535) * (1 - factor)) / 257
            ).astype(np.uint8)
        else:
            composite = (
                np.rint(contribution).astype(np.uint16)
                if consumer == "black"
                else np.rint(contribution + base * (1 - factor)).astype(np.uint16)
                if consumer == "background-light-off"
                else expected
            )
            wanted = np.rint(composite.astype(float) / 257).astype(np.uint8)
        wanted = wanted[1:4, 2:6]
    np.testing.assert_array_equal(actual, wanted)


@pytest.mark.parametrize("kind", ["oval", "directional"])
@pytest.mark.parametrize(
    "shape,output,display,margin",
    [
        ((3, 4), (4, 3), None, 0),
        ((3, 4), (40, 30), None, 0),
        ((3, 4), (40, 30), (9, 7), 0),
        ((3, 4), (17, 19), (11, 9), 150),
        ((1, 7), (13, 15), None, 150),
        ((8, 1), (15, 13), (7, 9), 150),
    ],
)
def test_series_light_uses_native_half_centres_and_unlit_target(
    kind, shape, output, display, margin
):
    from test_background import scalar_background
    from test_series_framing import scalar_background_blend, scalar_sample
    from test_spatial_fade import operands, spatial_settings

    from blackmask.series_framing import (
        SeriesSettings,
        compute_series_layout,
        render_series,
        series_sampling_plan,
    )

    alpha = np.full(shape, 32768, np.uint16)
    alpha.flat[0], alpha.flat[-1] = 1, 65535
    foreground = (np.arange(alpha.size * 3).reshape((*shape, 3)) * 293 + 17001).astype(np.uint16)
    spatial = operands(spatial_settings(shape[1], shape[0]), np.full(shape, 49151, np.uint16))
    spatial.protection.flat[1] = True
    sampling = series_sampling_plan(
        compute_series_layout(
            alpha,
            SeriesSettings(
                output_width_px=output[0],
                output_height_px=output[1],
                side_margin_tenths_percent=margin,
                minimum_vertical_margin_tenths_percent=0,
            ),
        ),
        display_dimensions_wh=display,
    )
    light = light_settings(shape[1], shape[0], kind=kind, brightness=0.55, color_srgb="#91D3EF")
    light["geometry"]["rotation_degrees"] = 37
    background = {"color_srgb": "#45202B", "variation": 0.8}
    width, height = sampling.display_dimensions_wh
    indices_x = (2 * np.arange(width) + 1) * output[0] // (2 * width)
    indices_y = (2 * np.arange(height) + 1) * output[1] // (2 * height)
    base = scalar_background(output[1], output[0], [69, 32, 43], 0.8)[np.ix_(indices_y, indices_x)]
    scale = sampling.layout.scale
    tx, ty = sampling.layout.translation_xy
    light_pixels = np.array(
        [
            [
                scalar_light(
                    light, (int(x) + 0.5 - tx) / scale - 0.5, (int(y) + 0.5 - ty) / scale - 0.5
                )
                for x in indices_x
            ]
            for y in indices_y
        ],
        np.uint16,
    )
    displayed = np.empty_like(base)
    for y in range(height):
        for x in range(width):
            for channel in range(3):
                displayed[y, x, channel] = scalar_encode(
                    scalar_decode(int(base[y, x, channel]) / 65535)
                    + scalar_decode(int(light_pixels[y, x, channel]) / 65535)
                )
    expected = displayed.copy()
    wrong_target = displayed.copy()
    native_alpha = alpha.astype(float) / 65535
    native_q = spatial.weight16.astype(float) / 65535
    native_q[spatial.protection] = 0
    if sampling.identity:
        a, sampled_q = native_alpha, native_alpha * native_q
    else:
        a = np.clip(scalar_sample(native_alpha, sampling, effective=True), 0, 1)
        sampled_q = np.clip(scalar_sample(native_alpha * native_q, sampling, effective=True), 0, a)
    ratio = np.divide(sampled_q, a, out=np.zeros_like(a), where=a > 0)
    for channel in range(3):
        p = (
            native_alpha * foreground[..., channel]
            if sampling.identity
            else scalar_sample(native_alpha * foreground[..., channel], sampling, effective=True)
        )
        p = np.clip(p, 0, 65535 * a)
        straight = np.divide(p, a, out=np.zeros_like(p), where=a > 0)
        for y in range(a.shape[0]):
            for x in range(a.shape[1]):
                oy, ox = sampling.y.output_start + y, sampling.x.output_start + x
                b, lit = int(base[oy, ox, channel]), int(displayed[oy, ox, channel])
                for target, result in ((b, expected), (lit, wrong_target)):
                    faded = scalar_background_blend(straight[y, x], target, ratio[y, x])
                    contribution = p[y, x] if ratio[y, x] == 0 else faded * a[y, x]
                    result[oy, ox, channel] = round(contribution + lit * (1 - a[y, x]))
    assert np.any(expected != wrong_target), (
        "The fixture must distinguish B1 accidentally becoming the fade target"
    )
    if scale == 10:
        assert abs(((0 - tx) / scale - ((0.5 - tx) / scale - 0.5)) * scale) == pytest.approx(4.5)
        wrong_centres = np.array(
            [
                [
                    scalar_light(light, (int(x) - tx) / scale, (int(y) - ty) / scale)
                    for x in indices_x
                ]
                for y in indices_y
            ],
            np.uint16,
        )
        assert np.any(light_pixels != wrong_centres)
    actual = render_series(
        foreground,
        alpha,
        sampling,
        spatial_fade=spatial,
        background_settings=background,
        background_light_settings=light,
    )
    np.testing.assert_allclose(
        actual.astype(int), expected.astype(int), atol=0 if sampling.identity else 2, rtol=0
    )
    for diagnostic in ({"black_background": True}, {"transparent": True}):
        baseline = render_series(
            foreground,
            alpha,
            sampling,
            spatial_fade=spatial,
            background_settings=background,
            **diagnostic,
        )
        np.testing.assert_array_equal(
            render_series(
                foreground,
                alpha,
                sampling,
                spatial_fade=spatial,
                background_settings=background,
                background_light_settings=light,
                **diagnostic,
            ),
            baseline,
        )


def test_series_resource_estimate_accounts_for_light_base_and_bounded_scratch():
    from blackmask.series_framing import (
        SeriesSettings,
        compute_series_layout,
        estimate_series_resources,
        series_sampling_plan,
    )

    sampling = series_sampling_plan(
        compute_series_layout(
            np.full((4, 6), 65535, np.uint16),
            SeriesSettings(output_width_px=90, output_height_px=130),
        )
    )
    base = estimate_series_resources(sampling, retained_native_bytes=192, transparent=False)
    lit = estimate_series_resources(
        sampling, retained_native_bytes=192, transparent=False, background_light=True
    )
    assert lit["background_light_base_rgb16_bytes"] == 90 * 130 * 6
    assert lit["background_light_strip_bytes"] >= 90 * 64 * 128
    assert (
        lit["estimated_peak_bytes"] >= base["estimated_peak_bytes"] + 90 * 130 * 6 + 90 * 64 * 128
    )
    # Export admission covers Result together with diagnostic alternatives.
    for alternatives in ({"transparent": True}, {"transparent": False, "black_background": True}):
        combined = estimate_series_resources(
            sampling, retained_native_bytes=192, background_light=True, **alternatives
        )
        assert (
            combined["background_light_base_rgb16_bytes"]
            == lit["background_light_base_rgb16_bytes"]
        )
        assert combined["background_light_strip_bytes"] == lit["background_light_strip_bytes"]


@pytest.mark.parametrize("kind", ["oval", "directional"])
@pytest.mark.parametrize("consumer", ["export", "preview"])
def test_series_delivery_and_preview_extend_saved_light_on_output_canvas(tmp_path, kind, consumer):
    from pathlib import Path

    import tifffile
    from test_background import scalar_background
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.export import export_project, saved_layers
    from blackmask.project import read_project
    from blackmask.review import render_presentation_preview
    from blackmask.series_framing import SeriesSettings, compute_series_layout, series_sampling_plan

    project, _, _ = fixture_project(tmp_path)
    light = light_settings(kind=kind, brightness=0.75)
    light["geometry"]["rotation_degrees"] = 37
    applied = operations.apply_operation(project, light_request(project, light))
    revision = applied["revision"]
    master = read_project(project)["developed_id"]
    _, alpha, manifest = saved_layers(project, revision, master)
    settings = SeriesSettings(output_width_px=17, output_height_px=39)
    layout = compute_series_layout(alpha, settings)
    assert series_sampling_plan(layout).y.output_start > 0
    base = scalar_background(39, 17, [18, 7, 8], 0.55)
    tx, ty = layout.translation_xy
    expected_empty = np.empty_like(base)
    for y in range(39):
        for x in range(17):
            pixels = scalar_light(
                light, (x + 0.5 - tx) / layout.scale - 0.5, (y + 0.5 - ty) / layout.scale - 0.5
            )
            for channel in range(3):
                expected_empty[y, x, channel] = scalar_encode(
                    scalar_decode(int(base[y, x, channel]) / 65535)
                    + scalar_decode(pixels[channel] / 65535)
                )
    # The top row lies outside the resampled subject and still receives analytic light.
    if consumer == "export":
        result = export_project(
            project,
            revision=revision,
            draft=True,
            series=settings.to_dict(),
            variants=("editable",),
        )
        directory = Path(result["directory"])
        actual = tifffile.imread(directory / "result_rgb16.tif")
        record = json.loads((directory / "manifest.json").read_bytes())
        assert record["background_light_transform"]["scale"] == layout.scale
        assert record["background_light_transform"]["translation_xy"] == list(layout.translation_xy)
        companion = Path(result["editable_companion"]["directory"])
        assert (companion / "background_light_rgb16.tif").read_bytes() == saved_raster(
            project / "revisions" / revision / "background_light/light_rgb16.tif"
        ).read_bytes()
        np.testing.assert_array_equal(actual[0], expected_empty[0])
    else:
        actual, metadata = render_presentation_preview(
            project,
            revision,
            master,
            manifest,
            {"mode": "match-series", "settings": settings.to_dict()},
        )
        assert metadata["output_dimensions_wh"] == [17, 39]
        np.testing.assert_array_equal(
            actual[0], np.rint(expected_empty[0].astype(float) / 257).astype(np.uint8)
        )


def test_background_light_real_http_apply_off_snapshot_and_stale_manifest(tmp_path):
    from test_effects import fixture_project
    from test_viewer import http, running

    project, _, _ = fixture_project(tmp_path)
    with running(project) as server:
        snapshot = server.snapshot()
        current = next(
            row for row in snapshot["revisions"] if row["revision"] == snapshot["working_revision"]
        )
        data = {key: snapshot[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(
            action="effects",
            base_revision=snapshot["working_revision"],
            revision_manifest_sha256=current["revision_manifest_sha256"],
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            background_light=light_settings(brightness=0.12345),
        )
        for enabled in (True, False):
            data["background_light"]["enabled"] = enabled
            assert http(server, "/api/action", "POST", data)[0] == 202
            assert server.action_lock.acquire(timeout=10)
            server.action_lock.release()
            assert server.action["error"] is None
            snapshot = server.snapshot()
            current = next(
                row
                for row in snapshot["revisions"]
                if row["revision"] == snapshot["working_revision"]
            )
            assert current["background_light"]["settings"] == data["background_light"]
            for key in ("developed_id", "inputs_digest", "authoring_digest"):
                data[key] = snapshot[key]
            data["base_revision"] = snapshot["working_revision"]
            data["revision_manifest_sha256"] = current["revision_manifest_sha256"]
        before = (project / "state.json").read_bytes()
        data["revision_manifest_sha256"] = "0" * 64
        assert http(server, "/api/action", "POST", data)[0] == 202
        assert server.action_lock.acquire(timeout=10)
        server.action_lock.release()
        assert "Stale" in server.action["error"]
        assert (project / "state.json").read_bytes() == before
        del data["revision_manifest_sha256"]
        assert http(server, "/api/action", "POST", data)[0] == 400


@pytest.mark.parametrize("field", ["background_light", "brightness", "center_xy"])
def test_background_light_http_rejects_duplicate_keys_before_start(tmp_path, field):
    from http.client import HTTPConnection

    from test_effects import fixture_project
    from test_viewer import running

    project, _, _ = fixture_project(tmp_path)
    with running(project) as server:
        snapshot = server.snapshot()
        current = next(
            row for row in snapshot["revisions"] if row["revision"] == snapshot["working_revision"]
        )
        data = {key: snapshot[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(
            action="effects",
            base_revision=snapshot["working_revision"],
            revision_manifest_sha256=current["revision_manifest_sha256"],
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            background_light=light_settings(),
        )
        raw = json.dumps(data).replace('"' + field + '":', '"' + field + '":null,"' + field + '":')
        before = dict(server.action)
        connection = HTTPConnection(*server.server_address, timeout=5)
        connection.request(
            "POST",
            "/api/action",
            raw,
            {
                "Host": server.host,
                "Origin": server.origin,
                "Content-Type": "application/json",
                "X-Blackmask-Token": server.token,
            },
        )
        response = connection.getresponse()
        status, body = response.status, response.read()
        connection.close()
        assert status == 400 and b"Duplicate" in body
        assert server.action == before


def test_light_writer_failures_orphan_restore_and_legacy_absence_preserve_acceptance(
    tmp_path, monkeypatch
):
    from test_effects import fixture_project

    from blackmask import effects, operations
    from blackmask.project import ProjectError, project_lock, read_project, read_revision

    project, _, parent = fixture_project(tmp_path)
    master = read_project(project)["developed_id"]
    assert "background_light" not in read_revision(project, parent["revision"], master)
    before = (project / "state.json").read_bytes()
    recipe = (project / "recipe.toml").read_bytes()
    with project_lock(project), pytest.raises(ProjectError, match="[Bb]usy|writer"):
        operations.apply_operation(project, light_request(project))
    with monkeypatch.context() as scoped:

        def no_space(*args):
            raise ProjectError("Insufficient space")

        scoped.setattr(effects, "check_space", no_space)
        with pytest.raises(ProjectError, match="space"):
            operations.apply_operation(project, light_request(project))
    assert (project / "state.json").read_bytes() == before
    assert (project / "recipe.toml").read_bytes() == recipe
    original = effects._atomic_json

    def interrupt(path, *args, **kwargs):
        if path.name == "state.json":
            raise OSError("synthetic state-last interruption")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(effects, "_atomic_json", interrupt)
        with pytest.raises(OSError, match="state-last"):
            operations.apply_operation(
                project, light_request(project, light_settings(enabled=False))
            )
    assert (project / "state.json").read_bytes() == before
    orphan = max((project / "revisions").glob("rev-*"))
    assert orphan.name != parent["revision"]
    record = read_revision(project, orphan.name, master)["background_light"]
    assert not record["settings"]["enabled"]
    operations.restore_revision(project, orphan.name, replace_drafts=True)
    assert read_project(project)["working_revision"] == orphan.name
    assert read_project(project)["accepted_revision"] == parent["revision"]
    operations.restore_revision(project, parent["revision"])
    assert "background_light" not in tomllib.loads((project / "recipe.toml").read_text())
    operations.restore_revision(project, orphan.name)
    assert (
        tomllib.loads((project / "recipe.toml").read_text())["background_light"]
        == record["settings"]
    )


def test_light_http_manifest_is_rechecked_inside_writer_lock(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from test_effects import fixture_project
    from test_viewer import http, running

    from blackmask import operations

    project, _, parent = fixture_project(tmp_path)
    path = project / "revisions" / parent["revision"] / "manifest.json"
    before = (project / "state.json").read_bytes()
    original = operations.project_lock
    with running(project) as server:
        snapshot = server.snapshot()
        row = next(
            item
            for item in snapshot["revisions"]
            if item["revision"] == snapshot["working_revision"]
        )
        data = {key: snapshot[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(
            action="effects",
            base_revision=snapshot["working_revision"],
            revision_manifest_sha256=row["revision_manifest_sha256"],
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            background_light=light_settings(),
        )

        @contextmanager
        def changed_under_lock(project_path):
            with original(project_path):
                path.write_bytes(path.read_bytes() + b"\n")
                yield

        with monkeypatch.context() as scoped:
            scoped.setattr(operations, "project_lock", changed_under_lock)
            assert http(server, "/api/action", "POST", data)[0] == 202
            assert server.action_lock.acquire(timeout=10)
            server.action_lock.release()
            assert "Stale raw revision manifest" in server.action["error"]
        assert (project / "state.json").read_bytes() == before
        assert max((project / "revisions").glob("rev-*")).name == parent["revision"]


@pytest.mark.parametrize("effect", ["cleanup", "shading", "exposure", "shadow", "sharpening"])
def test_light_keeps_upstream_effect_operands_and_pending_root_settings(tmp_path, effect):
    from test_effects import effect_request, fixture_project, shading_request
    from test_exposure import exposure_request
    from test_shadow_fade import fade_request
    from test_sharpening import sharpening_request

    from blackmask import operations
    from blackmask.assets import revision_hashes
    from blackmask.export import saved_layers
    from blackmask.project import read_project

    project, _, accepted = fixture_project(tmp_path)
    request = {
        "cleanup": effect_request,
        "shading": shading_request,
        "exposure": exposure_request,
        "shadow": fade_request,
        "sharpening": sharpening_request,
    }[effect]
    previous = operations.apply_operation(project, request(project))
    master = read_project(project)["developed_id"]
    foreground, alpha, manifest = saved_layers(project, previous["revision"], master)
    draft = tomllib.loads((project / "recipe.toml").read_text())
    draft["background"] = {"color_srgb": "#123456", "variation": 0.12345}
    # Native guidance is unchanged; these independent unapplied controls must survive.
    draft["local_exposure"] = {"enabled": True, "ev": 0.3}
    (project / "recipe.toml").write_text(tomli_w.dumps(draft))
    result = operations.apply_operation(project, light_request(project))
    actual, current_alpha, current = saved_layers(project, result["revision"], master)
    np.testing.assert_array_equal(actual, foreground)
    np.testing.assert_array_equal(current_alpha, alpha)
    for name, checksum in revision_hashes(manifest).items():
        # The write-only request support is provenance of that cleanup operation;
        # cumulative saved support and all replay operands must be inherited.
        if (
            name.endswith((".png", ".tif"))
            and not name.startswith("review/")
            and name != "effects/write_support16.png"
        ):
            assert revision_hashes(current)[name] == checksum
    for section in (
        "color_cleanup",
        "shading",
        "local_exposure",
        "shadow_fade",
        "local_sharpening",
    ):
        assert current.get(section) == manifest.get(section)
    root = tomllib.loads((project / "recipe.toml").read_text())
    assert root["background"] == draft["background"]
    assert root["local_exposure"] == draft["local_exposure"]
    assert read_project(project)["accepted_revision"] == accepted["revision"]


def test_light_gallery_and_historical_appearance_reference_use_saved_pixels(tmp_path):
    import base64
    import io

    from PIL import Image
    from test_appearance_recipes import saved_recipe
    from test_background import scalar_background
    from test_library import inventory
    from test_previews import generate, jpeg, managed, marker

    from blackmask import operations, previews
    from blackmask.export import saved_layers
    from blackmask.project import read_project

    _, config, project = managed(tmp_path)
    accepted = generate(project, config)
    operations.accept_revision(project, accepted["revision"], storage_config=config)
    light = light_settings(kind="directional", brightness=0.375)
    applied = operations.apply_operation(
        project, light_request(project, light), storage_config=config
    )
    state = read_project(project)
    foreground, alpha, _ = saved_layers(project, applied["revision"], state["developed_id"])
    base = scalar_background(4, 6, [18, 7, 8], 0.55)
    field = np.array([[scalar_light(light, x, y) for x in range(6)] for y in range(4)], np.uint16)
    contribution, displayed = scalar_light_composition(
        foreground, alpha, base, field, np.zeros_like(alpha), np.zeros_like(alpha, bool)
    )
    expected = np.rint(
        contribution + displayed * (1 - alpha.astype(float)[..., None] / 65535)
    ).astype(np.uint16)
    np.testing.assert_array_equal(previews._render_latest(project, state), expected)
    assert not applied["preview_pending"]
    assert marker(jpeg(config, project))["revision"] == applied["revision"]
    operations.apply_operation(
        project, light_request(project, dict(light, enabled=False)), storage_config=config
    )
    before = inventory(project)
    document = json.loads(
        saved_recipe(project, applied["revision"], ["background"], reference=True)
    )
    assert set(document["sections"]) == {"background"}
    with Image.open(io.BytesIO(base64.b64decode(document["reference"]["png_base64"]))) as image:
        np.testing.assert_array_equal(
            np.array(image), np.rint(expected.astype(float) / 257).astype(np.uint8)
        )
    assert inventory(project) == before


def test_genuine_v4_notes_and_members_remain_compatible():
    from pathlib import Path

    from blackmask.export import _delivery_members, _delivery_notes

    captured = json.loads(Path("tests/fixtures/background-light-v4.json").read_bytes())
    assert captured["producer_head"] == "8238f6f710c559f41e95831a2c013e882976f197"
    for delivery in captured["deliveries"]:
        record = delivery["request_record"]
        assert record["export_version"] == "requested-result-v4"
        assert _delivery_notes(record) == delivery["notes"].encode()
        assert set(_delivery_members(record, delivery["revision_manifest"])) | {
            "manifest.json"
        } == set(delivery["members"])


@pytest.mark.parametrize("enabled", [None, False, True])
def test_native_light_delivery_members_are_independently_bounded(tmp_path, enabled):
    from pathlib import Path

    from test_effects import fixture_project

    from blackmask.export import export_project
    from blackmask.operations import apply_operation

    project, _, parent = fixture_project(tmp_path)
    revision = parent["revision"]
    if enabled is not None:
        revision = apply_operation(
            project, light_request(project, light_settings(enabled=enabled))
        )["revision"]
    compact = Path(export_project(project, revision=revision, draft=True)["directory"])
    basic = {
        "result_rgb16.tif",
        "result_RGB8_VIEW.png",
        "recipe.toml",
        "manifest.json",
        "README.txt",
    }
    assert {path.name for path in compact.iterdir()} == basic
    editable = Path(
        export_project(project, revision=revision, draft=True, variants=("editable",))["directory"]
    )
    expected = basic | {
        "foreground_rgb16.tif",
        "alpha16.png",
        "source_rgb16.tif",
        "background_rgb16.tif",
        "background_settings.json",
    }
    if enabled is not None:
        expected |= {"background_light_rgb16.tif", "background_light_settings.json"}
    assert {path.name for path in editable.iterdir()} == expected
    assert all(path.is_file() and not path.is_symlink() for path in editable.iterdir())
