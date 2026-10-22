"""Native geometric fields and one reversible, background-targeted RGB blend."""

import copy
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from test_ingest import bind_raster, saved_raster

from blackmask.project import ProjectError


def spatial_settings(width=100, height=100):
    return {
        "enabled": True,
        "preserve_highlights": 0.0,
        "oval": {
            "enabled": True,
            "center_xy": [width / 2, height / 2],
            "inner_radii_xy": [width / 4, height / 4],
            "rotation_degrees": 0.0,
            "transition_width": min(width, height) / 4,
            "amount": 0.6,
        },
        "arcs_enabled": False,
        "arcs": [],
    }


def arc_settings(**changes):
    return {
        "id": str(uuid.uuid4()),
        "enabled": True,
        "center_xy": [50.0, 50.0],
        "rotation_degrees": 0.0,
        "half_span": 20.0,
        "bend": 10.0,
        "fade_side": "positive",
        "transition_width": 10.0,
        "end_softness": 5.0,
        "amount": 0.6,
        **changes,
    }


def operands(settings, weight):
    from blackmask.spatial_fade import SpatialFadeOperands

    return SpatialFadeOperands(
        np.asarray(weight, np.uint16),
        np.zeros(np.shape(weight), bool),
        {"enabled": settings["enabled"], "stale": False, "settings": settings},
    )


@pytest.mark.parametrize("rotation", [0, 37, 90, 359])
@pytest.mark.parametrize("radii", [[5, 40], [25, 25]])
def test_ellipse_complete_rays_never_reverse(rotation, radii):
    from blackmask.spatial_fade import elliptical_fade_weight

    oval = dict(
        spatial_settings()["oval"],
        center_xy=[60.5, 60.5],
        inner_radii_xy=radii,
        transition_width=10.0,
        rotation_degrees=rotation,
    )
    distances = np.linspace(0, 100, 2001)
    for angle in np.arange(64) * 2 * np.pi / 64:
        x = 60.5 + np.cos(angle) * distances
        y = 60.5 + np.sin(angle) * distances
        values = elliptical_fade_weight(x, y, oval)
        assert values[0] == 0 and values[-1] == 1
        assert np.all(np.diff(values) >= -1e-14)
        quantized = np.rint(values * 65535).astype(np.int32)
        assert np.all(np.diff(quantized) >= 0)


def test_raster_uses_pixel_centres_and_distinct_rays():
    from blackmask.spatial_fade import elliptical_fade_weight, make_spatial_weight

    settings = spatial_settings(121, 121)
    settings["oval"].update(
        center_xy=[60.5, 60.5],
        inner_radii_xy=[5, 40],
        rotation_degrees=37.0,
        transition_width=10.0,
        amount=1.0,
    )
    # Recorded nearest-pixel path crosses rays; these values need not be monotonic.
    actual = elliptical_fade_weight(
        np.array([59.5, 58.5]), np.array([75.5, 75.5]), settings["oval"]
    )
    np.testing.assert_array_equal(np.rint(actual * 65535), [21227, 14559])
    weight = make_spatial_weight((121, 121), settings)
    theta = np.deg2rad(37)
    for y in range(121):
        for x in range(121):
            dx, dy = x + 0.5 - 60.5, y + 0.5 - 60.5
            u, v = np.cos(theta) * dx + np.sin(theta) * dy, -np.sin(theta) * dx + np.cos(theta) * dy
            rho = np.hypot(u, v)
            if rho == 0:
                expected = 0
            else:
                inner = rho / np.sqrt((u / 5) ** 2 + (v / 40) ** 2)
                outer = rho / np.sqrt((u / 15) ** 2 + (v / 50) ** 2)
                t = np.clip((rho - inner) / (outer - inner), 0, 1)
                expected = round(float(t * t * (3 - 2 * t)) * 65535)
            assert weight[y, x] == expected


@pytest.mark.parametrize("side", ["positive", "negative"])
@pytest.mark.parametrize("bend", [-20, 0, 10, 20])
def test_arc_anchor_plateau_soft_ends_and_direction(side, bend):
    from blackmask.spatial_fade import arc_fade_weight

    arc = arc_settings(center_xy=[0, 0], bend=bend, fade_side=side)
    sign = 1 if side == "positive" else -1
    values = arc_fade_weight(np.zeros(4), bend + sign * np.array([0, 5, 10, 100]), arc)
    np.testing.assert_allclose(values, [0, 0.5, 1, 1], atol=1e-14)
    assert arc_fade_weight(np.array([17.5]), np.array([sign * 100]), arc)[0] == 0.5
    np.testing.assert_array_equal(
        arc_fade_weight(np.array([-20.0, 20.0]), np.array([sign * 100] * 2), arc), [0, 0]
    )
    for u in (-19.9, -17.5, -15, 0, 15, 17.5, 19.9):
        v = sign * np.linspace(-100, 100, 1001)
        field = arc_fade_weight(np.full_like(v, u), v, arc)
        assert np.all(np.diff(field) >= 0)
        assert field[-1] == field[-2]


@pytest.mark.parametrize("rotation", [0, 37, 90, 359])
def test_arc_rotation_and_shortest_span(rotation):
    from blackmask.spatial_fade import arc_fade_weight

    arc = arc_settings(
        half_span=0.5, end_softness=0.5, bend=-0.5, transition_width=0.5, rotation_degrees=rotation
    )
    theta = np.deg2rad(rotation)
    v = np.array([-0.5, -0.25, 0, 100])
    x, y = 50 - np.sin(theta) * v, 50 + np.cos(theta) * v
    np.testing.assert_allclose(arc_fade_weight(x, y, arc), [0, 0.5, 1, 1], atol=1e-12)


def test_empty_arcs_never_disable_oval_and_master_does_not_change_geometry():
    from blackmask.spatial_fade import (
        combined_fade_weight,
        make_spatial_weight,
        spatial_fade_amount,
    )

    settings = spatial_settings(3, 3)
    settings["oval"].update(center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], transition_width=0.5)
    for group in (False, True):
        settings["arcs_enabled"] = group
        assert combined_fade_weight(np.array([2.5]), np.array([2.5]), settings)[0] == 0.6
        weight = make_spatial_weight((3, 3), settings)
        assert weight[2, 2] == 39321
        rgb = np.zeros((3, 3, 3), np.uint16)
        alpha = np.ones((3, 3), np.uint16)
        assert spatial_fade_amount(rgb, alpha, operands(settings, weight))[2, 2] == 0.6
        settings["enabled"] = False
        np.testing.assert_array_equal(make_spatial_weight((3, 3), settings), weight)
        assert not spatial_fade_amount(rgb, alpha, operands(settings, weight)).any()
        settings["enabled"] = True
    settings["oval"]["enabled"] = False
    assert not make_spatial_weight((3, 3), settings).any()


def test_maximum_is_order_duplicate_and_topology_independent():
    from blackmask.spatial_fade import (
        combined_fade_weight,
        make_spatial_weight,
        spatial_fade_amount,
    )

    settings = spatial_settings()
    settings["oval"].update(amount=0.4, inner_radii_xy=[0.5, 0.5], transition_width=0.5)
    arc = arc_settings()
    settings.update(arcs_enabled=True, arcs=[arc])
    x, y = np.array([50.5]), np.array([99.5])
    assert combined_fade_weight(x, y, settings)[0] == 0.6
    duplicate = dict(arc, id=str(uuid.uuid4()))
    settings["arcs"].append(duplicate)
    assert combined_fade_weight(x, y, settings)[0] == 0.6
    weight = make_spatial_weight((100, 100), settings)
    assert weight[99, 50] == 39321
    settings["arcs"].reverse()
    np.testing.assert_array_equal(make_spatial_weight((100, 100), settings), weight)
    settings["arcs"] = []
    assert combined_fade_weight(x, y, settings)[0] == 0.4
    with pytest.raises(ProjectError):
        combined_fade_weight(x, y, settings, shape_id=arc["id"])
    settings["arcs"] = [dict(arc, enabled=False)]
    assert combined_fade_weight(x, y, settings, shape_id=arc["id"])[0] == 0
    for alpha_value in (1, 16384, 65535):
        alpha = np.zeros((100, 100), np.uint16)
        alpha[99, 50] = alpha_value
        q = spatial_fade_amount(
            np.zeros((100, 100, 3), np.uint16), alpha, operands(settings, weight)
        )
        assert q[99, 50] == 0.6
        assert not q[alpha == 0].any()


def test_protection_and_highlights_are_explicit_exceptions():
    from blackmask.spatial_fade import spatial_fade_amount

    settings = spatial_settings()
    settings["preserve_highlights"] = 1.0
    saved = operands(settings, [[39321, 39321, 39321]])
    saved.protection[0, 1] = True
    rgb = np.array([[[65535] * 3, [10000] * 3, [10000] * 3]], np.uint16)
    alpha = np.array([[65535, 16384, 1]], np.uint16)
    np.testing.assert_array_equal(spatial_fade_amount(rgb, alpha, saved), [[0, 0, 0.6]])
    settings["preserve_highlights"] = 0.0
    np.testing.assert_array_equal(spatial_fade_amount(rgb, alpha, saved), [[0.6, 0, 0.6]])


def test_linear_blend_has_exact_endpoints_and_can_brighten_black():
    from blackmask.spatial_fade import blend_background_float

    foreground = np.array([[[12345, 23456, 34567], [11111, 22222, 33333], [0, 0, 0]]], np.uint16)
    background = np.array([[[4608, 1792, 2048]] * 3], np.uint16)
    original = foreground.copy()
    result = blend_background_float(foreground, background, np.array([[0, 1, 0.5]]))
    np.testing.assert_array_equal(result[0, 0], foreground[0, 0])
    np.testing.assert_array_equal(result[0, 1], background[0, 1])
    # The two dimmer target channels stay in the linear branch after halving.
    assert np.all(result[0, 2] > 0)
    np.testing.assert_allclose(result[0, 2], [2547.3897027449, 896, 1024], atol=1e-6)
    np.testing.assert_array_equal(foreground, original)
    for bad in (np.array([[np.nan] * 3]), np.ones((2, 3)), np.array([[0, -0.1, 1]])):
        with pytest.raises(ProjectError):
            blend_background_float(foreground, background, bad)


def test_shared_colour_helpers_preserve_quantizing_wrapper_and_highlight_thresholds():
    from blackmask.exposure import highlight_weight, linear_to_rgb16, linear_to_srgb

    linear = np.array([[0, 0.0031308, 0.1], [0.425, 0.75, 1]])
    np.testing.assert_array_equal(
        np.rint(linear_to_srgb(linear) * 65535).astype(np.uint16), linear_to_rgb16(linear)
    )
    np.testing.assert_allclose(
        highlight_weight(np.repeat(np.array([0, 0.1, 0.425, 0.75, 1])[:, None], 3, axis=1)),
        [0, 0, 0.5, 1, 1],
        atol=1e-15,
    )


def test_strict_settings_and_bounded_shape_count():
    from blackmask.spatial_fade import validate_spatial_fade

    settings = spatial_settings()
    validate_spatial_fade(settings, 100, 100)
    settings["arcs"] = [arc_settings() for _ in range(32)]
    validate_spatial_fade(settings, 100, 100)
    invalid = []
    invalid.append(dict(settings, arcs=settings["arcs"] + [arc_settings()]))
    invalid.append(dict(settings, arcs=[settings["arcs"][0]] * 2))
    invalid.append(dict(settings, extra=True))
    invalid.append(dict(settings, enabled=1))
    invalid.append(dict(settings, preserve_highlights=True))
    for field, value in (
        ("id", "../escape"),
        ("id", str(uuid.uuid1())),
        ("enabled", 1),
        ("half_span", 0),
        ("bend", 21),
        ("transition_width", float("nan")),
        ("rotation_degrees", 360),
        ("center_xy", [101, 50]),
        ("amount", float("inf")),
        ("end_softness", 21),
        ("fade_side", "up"),
        ("amount", True),
    ):
        bad = copy.deepcopy(settings)
        bad["arcs"] = [dict(arc_settings(enabled=False), **{field: value})]
        invalid.append(bad)
    for bad in invalid:
        with pytest.raises(ProjectError):
            validate_spatial_fade(bad, 100, 100)


def test_shape_topology_does_not_weaken_tip():
    from blackmask.spatial_fade import make_spatial_weight, spatial_fade_amount

    settings = spatial_settings()
    settings["oval"].update(inner_radii_xy=[1, 1], transition_width=1.0)
    weight = make_spatial_weight((100, 100), settings)
    rgb = np.full((100, 100, 3), 12000, np.uint16)
    for value in (1, 16384, 65535):
        for topology in ("thin", "broad", "branches"):
            alpha = np.zeros((100, 100), np.uint16)
            if topology == "thin":
                alpha[:, 50] = value
            elif topology == "broad":
                alpha[:] = value
            else:
                alpha[:, 50] = value
                alpha[::3] = value
            q = spatial_fade_amount(rgb, alpha, operands(settings, weight))
            assert q[99, 50] == 0.6


def test_crossing_opposing_fields_are_continuous_maxima_and_crop_registered():
    from blackmask.spatial_fade import combined_fade_weight, make_spatial_weight

    settings = spatial_settings(128, 96)
    settings["oval"].update(amount=0.4, rotation_degrees=37.0)
    settings["arcs_enabled"] = True
    settings["arcs"] = [
        arc_settings(bend=0),
        arc_settings(rotation_degrees=90),
        arc_settings(fade_side="negative"),
    ]
    x = np.linspace(25, 75, 10001)
    y = np.full_like(x, 55)
    combined = combined_fade_weight(x, y, settings)
    selected = [
        combined_fade_weight(x, y, settings, shape_id=identity)
        for identity in ["oval", *[arc["id"] for arc in settings["arcs"]]]
    ]
    np.testing.assert_array_equal(combined, np.maximum.reduce(selected))
    assert np.all((combined >= 0) & (combined <= 0.6))
    assert np.max(np.abs(np.diff(combined))) < 0.002
    weight = make_spatial_weight((96, 128), settings)
    xx, yy = np.meshgrid(np.arange(42, 71) + 0.5, np.arange(60, 80) + 0.5)
    np.testing.assert_array_equal(
        np.rint(combined_fade_weight(xx, yy, settings) * 65535), weight[60:80, 42:71]
    )


@pytest.mark.parametrize("configuration", ["oval", "arcs", "both"])
def test_multi_head_branching_protection_soft_ends_and_series(configuration):
    from test_series_framing import series_settings

    from blackmask.background import make_background
    from blackmask.export import render_background
    from blackmask.series_framing import compute_series_layout, render_series, series_sampling_plan
    from blackmask.spatial_fade import make_spatial_weight, spatial_fade_amount

    y, x = np.mgrid[:96, :128]
    alpha = np.zeros((96, 128), np.uint16)
    heads = (
        ((x - 35) ** 2 + (y - 30) ** 2 < 100)
        | ((x - 90) ** 2 + (y - 25) ** 2 < 100)
        | ((x - 65) ** 2 + (y - 60) ** 2 < 64)
    )
    stems = (
        (np.abs(x - (35 + (y - 30) * 0.5)) < 1.5)
        | (np.abs(x - (90 - (y - 25) * 0.35)) < 1.5)
        | ((x == 115) & (y >= 60))
    )
    alpha[stems] = 26214
    alpha[heads] = 65535
    protected = (x - 35) ** 2 + (y - 30) ** 2 < 144
    alpha[protected & stems & ~heads] = 26214
    foreground = np.full((96, 128, 3), [38000, 32000, 27000], np.uint16)
    original = foreground.copy(), alpha.copy()
    settings = spatial_settings(128, 96)
    settings["oval"].update(
        enabled=configuration != "arcs",
        center_xy=[64, 60],
        inner_radii_xy=[20, 12],
        transition_width=30,
        rotation_degrees=37,
        amount=0.4,
    )
    settings["arcs_enabled"] = configuration != "oval"
    settings["arcs"] = [
        arc_settings(
            center_xy=[64, 48],
            half_span=60,
            bend=10,
            transition_width=18,
            end_softness=20,
            amount=0.8,
        ),
        arc_settings(
            center_xy=[70, 48],
            half_span=50,
            bend=-10,
            transition_width=18,
            end_softness=15,
            fade_side="negative",
            amount=0.7,
        ),
    ]
    saved = operands(settings, make_spatial_weight(alpha.shape, settings))
    unprotected_q = spatial_fade_amount(foreground, alpha, saved)
    assert np.any(unprotected_q[protected & (alpha > 0)] > 0)
    saved.protection[protected] = True
    q = spatial_fade_amount(foreground, alpha, saved)
    assert not q[protected].any()
    assert np.any((alpha[protected] > 0) & (alpha[protected] < 65535))
    if configuration != "oval":
        # The lateral soft end still touches an unintended adjacent stem.
        assert 0 < q[80, 115] < settings["arcs"][0]["amount"]
    background_settings = {"color_srgb": "#45202B", "variation": 0.55}
    background = make_background(alpha.shape, background_settings)
    baseline = render_background(foreground, alpha, background)
    actual = render_background(
        foreground, alpha, background, spatial_fade=saved, fade_background16=background
    )
    np.testing.assert_array_equal(actual[protected], baseline[protected])
    sampling = series_sampling_plan(
        compute_series_layout(alpha, series_settings(output_width_px=83, output_height_px=117))
    )
    rgba = render_series(
        foreground,
        alpha,
        sampling,
        spatial_fade=saved,
        background_settings=background_settings,
        transparent=True,
    )
    off = render_series(foreground, alpha, sampling, transparent=True)
    np.testing.assert_array_equal(rgba[..., 3], off[..., 3])
    assert not rgba[rgba[..., 3] == 0, :3].any()
    np.testing.assert_array_equal(foreground, original[0])
    np.testing.assert_array_equal(alpha, original[1])


@pytest.mark.parametrize(
    "path,value",
    [
        (("oval", "inner_radii_xy"), [0.49, 1]),
        (("oval", "inner_radii_xy"), [201, 1]),
        (("oval", "center_xy"), [0, -0.1]),
        (("oval", "rotation_degrees"), -0.1),
        (("oval", "transition_width"), 0.49),
        (("oval", "amount"), 1.01),
        (("oval", "enabled"), 0),
        (("preserve_highlights",), float("nan")),
        (("arcs_enabled",), 1),
    ],
)
def test_all_shapes_are_strict_even_when_disabled(path, value):
    from blackmask.spatial_fade import validate_spatial_fade

    settings = spatial_settings()
    settings["enabled"] = settings["oval"]["enabled"] = False
    target = settings
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ProjectError):
        validate_spatial_fade(settings, 100, 100)


def spatial_request(project, settings=None, *, candidate=False, **fields):
    from test_operations import request

    return request(
        project,
        kind="effects",
        scope_xyxy=[0, 0, 6, 4],
        candidate_comparison=candidate,
        spatial_fade=spatial_settings(6, 4) if settings is None else settings,
        **fields,
    )


@pytest.mark.parametrize("mode", ["oval", "off", "empty", "arcs"])
def test_spatial_equivalent_submission_reuses_current_native_result(tmp_path, mode):
    """Missing spatial identity/recipe handling must not publish a redundant revision."""
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.project import read_project

    project, _, parent = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    if mode == "off":
        settings["enabled"] = False
    if mode == "empty":
        settings["oval"]["enabled"] = False
    if mode == "arcs":
        settings["arcs_enabled"] = True
        settings["arcs"] = [arc_settings(center_xy=[3, 2], half_span=2, bend=0.5, end_softness=0.5)]
    first = operations.apply_operation(project, spatial_request(project, settings, candidate=True))
    before = {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    repeated = spatial_request(project, copy.deepcopy(settings), candidate=True)
    with patch(
        "blackmask.operations.VitMatteSession", side_effect=AssertionError("model on reuse")
    ):
        second = operations.apply_operation(project, repeated)
    assert second["reused"] is True
    assert second["revision"] == first["revision"]
    assert second["parent"] == first["parent"]
    assert read_project(project)["accepted_revision"] == parent["revision"]
    assert before == {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("amount", [0.0, 0.6])
def test_spatial_reuse_uses_protection_bytes_and_validated_nested_numbers(tmp_path, amount):
    """Locator spelling/numeric encoding may reuse, but changed safety bytes need history."""
    from PIL import Image
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.assets import revision_asset
    from blackmask.project import read_project, read_revision
    from blackmask.repair import scalar16
    from blackmask.spatial_fade import read_spatial_fade

    project, _, _ = fixture_project(tmp_path)
    protection = np.zeros((4, 6), dtype=np.uint16)
    protection[1, 2] = 65535
    Image.fromarray(protection).save(project / "protection-a.png")
    settings = spatial_settings(6, 4)
    settings["oval"]["amount"] = amount
    settings["oval"]["center_xy"] = [3, 2]
    first = operations.apply_operation(
        project,
        spatial_request(
            project, settings, candidate=True, spatial_fade_protection_file="protection-a.png"
        ),
    )
    (project / "protection-b.png").write_bytes((project / "protection-a.png").read_bytes())
    equivalent = copy.deepcopy(settings)
    equivalent["oval"]["center_xy"] = [3.0, 2.0]
    second = operations.apply_operation(
        project,
        spatial_request(
            project, equivalent, candidate=True, spatial_fade_protection_file="protection-b.png"
        ),
    )
    assert second["reused"] is True and second["revision"] == first["revision"]
    protection[2, 3] = 65535
    Image.fromarray(protection).save(project / "protection-b.png")
    changed = operations.apply_operation(
        project,
        spatial_request(
            project, equivalent, candidate=True, spatial_fade_protection_file="protection-b.png"
        ),
    )
    assert changed["reused"] is False and changed["revision"] != first["revision"]
    manifest = read_revision(project, changed["revision"], read_project(project)["developed_id"])
    directory = project / "revisions" / changed["revision"]
    alpha = scalar16(revision_asset(project, directory, manifest, "base_alpha16.png"))
    saved = read_spatial_fade(project, directory, manifest, alpha)
    assert saved is not None and saved.protection[1, 2] and saved.protection[2, 3]


@pytest.mark.parametrize("cold", [False, True])
def test_spatial_reuse_keeps_cold_integrity_validation_without_effect_generation(tmp_path, cold):
    """Reuse cannot bypass cold geometry validation or rerun effects generation."""
    from test_effects import fixture_project

    from blackmask import operations, spatial_fade
    from blackmask import project as project_module

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, spatial_request(project, candidate=True))
    if cold:
        project_module._validate_spatial_fade_semantics.cache_clear()
    before = {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    with (
        patch(
            "blackmask.spatial_fade.make_spatial_weight", wraps=spatial_fade.make_spatial_weight
        ) as validation,
        patch(
            "blackmask.effects.make_spatial_weight",
            side_effect=AssertionError("new output W on reuse"),
        ),
        patch("blackmask.operations.VitMatteSession", side_effect=AssertionError("model on reuse")),
    ):
        repeated = operations.apply_operation(project, spatial_request(project, candidate=True))
    assert repeated["reused"] and repeated["revision"] == first["revision"]
    assert validation.call_count == (1 if cold else 0)
    assert before == {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "binding", ["record", "weight16.png", "protection16.png", "alpha16.png", "settings.json"]
)
def test_inherited_spatial_output_binding_must_match_before_background_reuse(tmp_path, binding):
    """A stale saved output proof must miss even when native operands still validate."""
    from test_background import background_request
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.project import digest, read_project

    project, _, parent = fixture_project(tmp_path)
    operations.apply_operation(project, spatial_request(project, candidate=True))
    first = operations.apply_operation(project, background_request(project))
    repeated = operations.apply_operation(project, background_request(project))
    assert repeated["reused"] and repeated["revision"] == first["revision"]
    directory = project / "revisions" / first["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    result = json.loads((directory / "result.json").read_bytes())
    for proof in (manifest["effects_reuse"], result["effects_reuse"]):
        if binding == "record":
            proof["spatial_fade"]["record"]["candidate_comparison"] = False
        else:
            proof["spatial_fade"]["files"]["effects/spatial-fade/" + binding] = "0" * 64
    (directory / "result.json").write_text(json.dumps(result))
    manifest["files"]["result.json"] = digest((directory / "result.json").read_bytes())
    (directory / "manifest.json").write_text(json.dumps(manifest))
    changed = operations.apply_operation(project, background_request(project))
    assert not changed["reused"] and changed["revision"] != first["revision"]
    assert changed["spatial_fade"] == first["spatial_fade"]
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_spatial_reuse_rechecks_actual_protection_bytes_before_return(tmp_path, monkeypatch):
    """A proven hit cannot hide a referenced protection file changed before return."""
    from PIL import Image
    from test_effects import fixture_project

    from blackmask import effects, operations

    project, _, _ = fixture_project(tmp_path)
    protection = np.zeros((4, 6), dtype=np.uint16)
    protection[1, 2] = 65535
    target = project / "spatial-protection.png"
    Image.fromarray(protection).save(target)
    operations.apply_operation(
        project, spatial_request(project, candidate=True, spatial_fade_protection_file=target.name)
    )
    before = (project / "state.json").read_bytes()
    original = effects._reused_effects_result

    def change_protection(*arguments):
        result = original(*arguments)
        assert result is not None
        target.write_bytes(target.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(effects, "_reused_effects_result", change_protection)
    with pytest.raises(ProjectError, match="Stale spatial fade protection"):
        operations.apply_operation(
            project,
            spatial_request(project, candidate=True, spatial_fade_protection_file=target.name),
        )
    assert (project / "state.json").read_bytes() == before
    assert target.read_bytes().endswith(b"\n")


@pytest.mark.parametrize("failure", [RuntimeError, MemoryError, KeyboardInterrupt])
def test_spatial_generation_failure_preserves_captured_request_and_native_state(tmp_path, failure):
    """New spatial geometry must not run before its exact recovery inputs are captured."""
    import hashlib

    from PIL import Image
    from test_effects import fixture_project

    from blackmask import operations

    project, _, parent = fixture_project(tmp_path)
    protection = np.zeros((4, 6), dtype=np.uint16)
    protection[1, 2] = 65535
    protection_path = project / "spatial-protection.png"
    Image.fromarray(protection).save(protection_path)
    operation = spatial_request(
        project, candidate=True, spatial_fade_protection_file=protection_path.name
    )
    request_file = project / "spatial-request.json"
    request_bytes = (json.dumps(operation, indent=2) + "\n").encode()
    request_file.write_bytes(request_bytes)
    root_inputs = {
        name: (project / name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    before = {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    revisions_before = sorted(path.name for path in (project / "revisions").iterdir())
    with (
        patch(
            "blackmask.effects.make_spatial_weight", side_effect=failure("spatial generation fault")
        ),
        pytest.raises(failure, match="spatial generation fault"),
    ):
        operations.apply_operation(project, operation, request_file=request_file)
    stages = list((project / "revisions").glob(".effects-*"))
    assert len(stages) == 1, "A failed spatial computation must retain its diagnostic stage"
    stage = stages[0]
    assert (stage / "request.json").read_bytes() == request_bytes
    for name, captured in root_inputs.items():
        assert (stage / "inputs" / name).read_bytes() == captured
    proof = json.loads((stage / "inputs/effects.json").read_bytes())
    protection_hash = hashlib.sha256(protection_path.read_bytes()).hexdigest()
    assert proof["request"]["spatial_fade"] == operation["spatial_fade"]
    assert proof["request"]["spatial_fade_protection_file"] == {"sha256": protection_hash}
    assert proof["inputs"]["request_files"]["spatial_fade_protection_file"] == protection_hash
    for name in ("source", "guides"):
        assert proof["inputs"][name] == hashlib.sha256(root_inputs[name + ".json"]).hexdigest()
    for name, captured in before.items():
        assert (project / name).read_bytes() == captured
    assert (
        json.loads((project / "state.json").read_bytes())["accepted_revision"] == parent["revision"]
    )
    assert (
        sorted(path.name for path in (project / "revisions").iterdir() if path != stage)
        == revisions_before
    )
    assert not (stage / "manifest.json").exists()
    assert not (stage / "result.json").exists()


def test_spatial_operation_replaces_mode_without_baking_source_or_losing_settings(tmp_path):
    import tomllib

    from test_effects import fixture_project, shading_request
    from test_shadow_fade import fade_request

    from blackmask import operations
    from blackmask.effects import saved_shading, saved_spatial_fade
    from blackmask.export import saved_layers
    from blackmask.project import read_project
    from blackmask.spatial_fade import read_spatial_fade

    project, _, parent = fixture_project(tmp_path)
    operations.apply_operation(project, fade_request(project, amount=0.38))
    old = operations.apply_operation(project, shading_request(project, opacity=0.75))
    master = read_project(project)["developed_id"]
    before_rgb, before_alpha, before = saved_layers(project, old["revision"], master)
    original_source = (project / "source.json").read_bytes()
    settings = spatial_settings(6, 4)
    settings.update(
        arcs_enabled=True,
        arcs=[
            arc_settings(
                center_xy=[3, 2], half_span=2, bend=0.5, transition_width=1, end_softness=0.5
            )
        ],
    )
    result = operations.apply_operation(project, spatial_request(project, settings, candidate=True))
    rgb, alpha, manifest = saved_layers(project, result["revision"], master)
    np.testing.assert_array_equal(rgb, before_rgb)
    np.testing.assert_array_equal(alpha, before_alpha)
    assert (project / "source.json").read_bytes() == original_source
    assert manifest["shadow_fade"] == before["shadow_fade"]
    assert manifest["background"] == before["background"]
    assert not manifest["shading"]["enabled"]
    assert manifest["shading"]["settings"] == dict(before["shading"]["settings"], enabled=False)
    for name in (
        "shadow_weight16.png",
        "effects/shading/protection16.png",
        "effects/shading/support16.png",
    ):
        assert manifest["assets"][name] == before["assets"][name]
    assert saved_shading(project, result["revision"], alpha, manifest) == (None, 0.0)
    saved = read_spatial_fade(project, project / "revisions" / result["revision"], manifest, alpha)
    assert saved.record["settings"] == settings
    assert saved.protection[2, 3]
    assert tomllib.loads((project / "recipe.toml").read_text())["spatial_fade"] == settings
    disabled_settings = dict(settings, enabled=False)
    disabled = operations.apply_operation(project, spatial_request(project, disabled_settings))
    _, _, off_manifest = saved_layers(project, disabled["revision"], master)
    assert not off_manifest["shading"]["enabled"]
    assert saved_spatial_fade(project, disabled["revision"], alpha, off_manifest) is None
    assert off_manifest["spatial_fade"]["settings"] == disabled_settings
    enabled = operations.apply_operation(
        project, spatial_request(project, settings, candidate=True)
    )
    old_only = shading_request(project, opacity_only=True)
    with pytest.raises(ProjectError, match="opacity|explicit|mode"):
        operations.apply_operation(project, old_only)
    restored = operations.apply_operation(project, shading_request(project))
    assert not restored["spatial_fade"]["enabled"] and restored["shading"]["enabled"]
    assert restored["spatial_fade"]["settings"]["arcs"] == settings["arcs"]
    assert read_project(project)["accepted_revision"] == parent["revision"]
    assert enabled["spatial_fade"]["enabled"]


@pytest.mark.parametrize("strength,shapes", [(0, True), (0.6, True), (0, False)])
def test_spatial_accepted_base_gate_including_zero_and_disable_recovery(tmp_path, strength, shapes):
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.project import read_project

    project, _, parent = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    settings["oval"].update(enabled=shapes, amount=strength)
    first = operations.apply_operation(project, spatial_request(project, settings))
    before = (project / "state.json").read_bytes()
    directories = set((project / "revisions").iterdir())
    with pytest.raises(ProjectError, match="accepted.*base|candidate"):
        operations.apply_operation(project, spatial_request(project, settings))
    assert (project / "state.json").read_bytes() == before
    assert set((project / "revisions").iterdir()) == directories
    operations.apply_operation(project, spatial_request(project, settings, candidate=True))
    disabled = operations.apply_operation(
        project, spatial_request(project, dict(settings, enabled=False))
    )
    assert not disabled["spatial_fade"]["enabled"]
    assert first["spatial_fade"]["enabled"]
    assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize("encoding", [8, 16])
def test_spatial_protection_is_categorical_additive_and_survives_shape_replacement(
    tmp_path, encoding
):
    from PIL import Image
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.export import saved_layers
    from blackmask.project import read_project
    from blackmask.spatial_fade import make_spatial_weight, read_spatial_fade

    project, _, _ = fixture_project(tmp_path)
    explicit = np.zeros((4, 6), np.uint8 if encoding == 8 else np.uint16)
    explicit[1, 3] = 255 if encoding == 8 else 65535
    Image.fromarray(explicit).save(project / "spatial-protection.png")
    settings = spatial_settings(6, 4)
    settings["oval"]["enabled"] = False
    settings.update(
        arcs_enabled=True,
        arcs=[
            arc_settings(
                center_xy=[3, 1], half_span=2, bend=0, transition_width=0.5, end_softness=0.5
            )
        ],
    )
    first = operations.apply_operation(
        project,
        spatial_request(project, settings, spatial_fade_protection_file="spatial-protection.png"),
    )
    master = read_project(project)["developed_id"]
    _, alpha, manifest = saved_layers(project, first["revision"], master)
    saved = read_spatial_fade(project, project / "revisions" / first["revision"], manifest, alpha)
    assert 0 < alpha[1, 3] < 65535 and saved.protection[1, 3]
    assert saved.weight16.any()
    prior_weight = saved.weight16.copy()
    for change in ("move", "lower", "disable", "remove"):
        updated = copy.deepcopy(settings)
        updated["enabled"] = False
        if change == "move":
            updated["arcs"][0]["center_xy"] = [0, 4]
        elif change == "lower":
            updated["arcs"][0]["amount"] = 0.1
        elif change == "disable":
            updated["arcs"][0]["enabled"] = False
        else:
            updated["arcs"] = []
        result = operations.apply_operation(project, spatial_request(project, updated))
        _, alpha, manifest = saved_layers(project, result["revision"], master)
        saved = read_spatial_fade(
            project, project / "revisions" / result["revision"], manifest, alpha
        )
        np.testing.assert_array_equal(saved.weight16, make_spatial_weight(alpha.shape, updated))
        assert np.any(saved.weight16 != prior_weight)
        assert saved.protection[1, 3]
    explicit[:] = 0
    explicit[2, 2] = 255 if encoding == 8 else 65535
    Image.fromarray(explicit).save(project / "spatial-protection.png")
    result = operations.apply_operation(
        project,
        spatial_request(
            project, settings, candidate=True, spatial_fade_protection_file="spatial-protection.png"
        ),
    )
    _, alpha, manifest = saved_layers(project, result["revision"], master)
    saved = read_spatial_fade(project, project / "revisions" / result["revision"], manifest, alpha)
    assert saved.protection[1, 3] and saved.protection[2, 2]


@pytest.mark.parametrize(
    "extra",
    [
        {"support_file": "x.png"},
        {"shading": {"enabled": False, "opacity": 0}},
        {"opacity_only": True},
        {"spatial_fade_amount_only": True},
        {"scope_xyxy": [1, 0, 6, 4]},
    ],
)
def test_spatial_invalid_operations_preserve_state(tmp_path, extra):
    from test_effects import fixture_project

    from blackmask import operations

    project, _, _ = fixture_project(tmp_path)
    operation = spatial_request(project)
    operation.update(extra)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.apply_operation(project, operation)
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("asset", ["weight16.png", "alpha16.png", "settings.json", "extra.json"])
@pytest.mark.parametrize("enabled", [False, True])
def test_spatial_saved_operands_are_validated_even_off_and_after_cache_warmup(
    tmp_path, asset, enabled
):
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.assets import revision_asset
    from blackmask.project import _validation_scope, read_project, read_revision

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(
        project, spatial_request(project, dict(spatial_settings(6, 4), enabled=enabled))
    )
    master = read_project(project)["developed_id"]
    directory = project / "revisions" / result["revision"]
    logical_name = f"effects/spatial-fade/{asset}"
    with _validation_scope():
        manifest = read_revision(project, result["revision"], master)
        if asset.endswith(".png"):
            assert logical_name in manifest["assets"]
            target = revision_asset(project, directory, manifest, logical_name)
            assert target.is_file()
            expected_error = "^Stale shared asset hash mismatch or changed while reading$"
        else:
            target = directory / logical_name
            if asset == "settings.json":
                assert target.is_file()
                expected_error = "^Saved revision hash mismatch:"
            else:
                assert not target.exists()
                expected_error = "^Invalid saved spatial fade inventory$"
        target.write_bytes(b"tampered")
        with pytest.raises(ProjectError, match=expected_error):
            read_revision(project, result["revision"], master)


@pytest.mark.parametrize("change_alpha,repairing", [(False, False), (True, False), (True, True)])
def test_spatial_prepare_matte_repair_stale_locks_and_replay(tmp_path, change_alpha, repairing):
    from test_effects import fixture_project
    from test_exposure import rectangle
    from test_matte_operations import StubSession, approve, run_matte
    from test_operations import edits, request
    from test_repair_operations import repair_request, run_repair

    from blackmask import operations
    from blackmask.export import saved_layers
    from blackmask.project import read_project
    from blackmask.repair import replay_repair
    from blackmask.spatial_fade import read_spatial_fade

    project, _, _ = fixture_project(tmp_path)
    first = operations.apply_operation(project, spatial_request(project))
    master = read_project(project)["developed_id"]
    before_rgb, before_alpha, _ = saved_layers(project, first["revision"], master)
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
    prepared_manifest = json.loads(
        (project / "revisions" / prepared["revision"] / "manifest.json").read_bytes()
    )
    assert prepared_manifest["spatial_fade"] == first["spatial_fade"]
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
            run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 5, 3]))
            if repairing
            else run_matte(project)
        )
    rgb, alpha, manifest = saved_layers(project, result["revision"], master)
    assert manifest["spatial_fade"]["stale"] is change_alpha
    assert alpha[1, 3] == before_alpha[1, 3]
    np.testing.assert_array_equal(rgb[1, 3], before_rgb[1, 3])
    saved = read_spatial_fade(project, project / "revisions" / result["revision"], manifest, alpha)
    assert saved.protection[1, 3]
    if repairing:
        np.testing.assert_array_equal(replay_repair(project, result["revision"]), alpha)
    if change_alpha:
        with pytest.raises(ProjectError, match="Stale|stale"):
            operations.accept_revision(project, result["revision"])
        disabled = operations.apply_operation(
            project, spatial_request(project, dict(spatial_settings(6, 4), enabled=False))
        )
        assert not disabled["spatial_fade"]["stale"]
        operations.accept_revision(project, disabled["revision"])


def test_spatial_rehashed_geometry_tamper_is_rejected_with_master_off(tmp_path):
    from PIL import Image
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.project import _json_bytes, digest, read_revision

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(
        project, spatial_request(project, dict(spatial_settings(6, 4), enabled=False))
    )
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    Image.fromarray(np.zeros((4, 6), np.uint16)).save(
        directory / "effects/spatial-fade/weight16.png"
    )
    manifest["spatial_fade"]["weight_sha256"] = digest(
        (directory / "effects/spatial-fade/weight16.png").read_bytes()
    )
    (directory / "effects/spatial-fade/settings.json").write_bytes(
        _json_bytes(manifest["spatial_fade"])
    )
    for name in ("weight16.png", "settings.json"):
        relative = f"effects/spatial-fade/{name}"
        bind_raster(project, directory, manifest, relative)
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="geometry"):
        read_revision(project, result["revision"], result["developed_id"])


def test_spatial_aliased_oval_cannot_be_accepted_as_an_arc():
    from blackmask.spatial_fade import validate_spatial_fade

    settings = spatial_settings()
    settings["arcs"] = [settings["oval"]]
    with pytest.raises(ProjectError):
        validate_spatial_fade(settings, 100, 100)


@pytest.mark.parametrize("after_rename", [False, True])
def test_spatial_interrupted_publication_reports_visible_revision_and_preserves_recovery(
    tmp_path, after_rename
):
    from test_effects import fixture_project

    from blackmask import export, operations
    from blackmask.project import read_project, read_revision

    project, _, parent = fixture_project(tmp_path)
    operation = spatial_request(project)
    original_sync = export._sync_directory
    before = (project / "state.json").read_bytes()

    def interrupted(path):
        if path == project / "revisions":
            raise OSError("Synthetic post-rename sync failure")
        return original_sync(path)

    if after_rename:
        with (
            patch.object(export, "_sync_directory", interrupted),
            pytest.raises(ProjectError, match="uncertain|unconfirmed") as error,
        ):
            operations.apply_operation(project, operation)
        visible = max((project / "revisions").glob("rev-*"))
        assert str(visible) in str(error.value)
        read_revision(project, visible.name, parent["developed_id"])
        operations.restore_revision(project, visible.name)
        assert read_project(project)["working_revision"] == visible.name
    else:
        with (
            patch.object(
                export, "_publish_new_directory", side_effect=OSError("Synthetic before rename")
            ),
            pytest.raises((ProjectError, OSError)),
        ):
            operations.apply_operation(project, operation)
        assert (project / "state.json").read_bytes() == before
        assert max((project / "revisions").glob("rev-*")).name == parent["revision"]
        assert list((project / "revisions").glob(".effects-*"))
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_spatial_recipe_round_trip_and_legacy_absence():
    import tomllib

    import tomli_w

    from blackmask.recipe import Recipe

    legacy = Recipe("master")
    assert "spatial_fade" not in legacy.to_dict()
    settings = spatial_settings(6, 4)
    settings.update(
        enabled=False,
        arcs_enabled=False,
        arcs=[
            arc_settings(
                center_xy=[3, 2],
                half_span=2,
                bend=-1,
                transition_width=0.5,
                end_softness=0.5,
                enabled=False,
            )
        ],
    )
    authored = Recipe("master", spatial_fade=settings)
    restored = Recipe.from_dict(
        tomllib.loads(tomli_w.dumps(authored.to_dict())), "master", dimensions_wh=(6, 4)
    )
    assert restored.to_dict() == authored.to_dict()
    with pytest.raises(ProjectError):
        Recipe.from_dict(dict(legacy.to_dict(), spatial_fade=None), "master", dimensions_wh=(6, 4))


def test_spatial_dual_enabled_saved_state_rejected_even_in_effects_off_comparison(tmp_path):
    from test_effects import fixture_project, shading_request

    from blackmask import operations
    from blackmask.export import saved_layers
    from blackmask.project import _json_bytes

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, shading_request(project))
    result = operations.apply_operation(project, spatial_request(project, candidate=True))
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["shading"]["enabled"] = manifest["shading"]["settings"]["enabled"] = True
    relative = "effects/shading/settings.json"
    (directory / relative).write_bytes(_json_bytes(manifest["shading"]))
    bind_raster(project, directory, manifest, relative)
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="both|exclusive"):
        saved_layers(project, result["revision"], result["developed_id"], effects_off=True)


@pytest.mark.parametrize("configuration", ["oval", "arcs", "both"])
def test_spatial_native_render_converges_to_target_with_unchanged_partial_alpha(configuration):
    from blackmask.export import render_background, render_black, view_rgba
    from blackmask.review import review_panels

    settings = spatial_settings(6, 4)
    settings["oval"]["enabled"] = configuration != "arcs"
    settings["arcs_enabled"] = configuration != "oval"
    settings["arcs"] = [
        arc_settings(center_xy=[3, 2], half_span=2, bend=0, transition_width=1, end_softness=0.5)
    ]
    foreground = np.full((4, 6, 3), [0, 10000, 20000], np.uint16)
    alpha = np.tile(np.array([0, 1, 16384, 32768, 65535, 65535], np.uint16), (4, 1))
    background = np.full_like(foreground, [4608, 1792, 2048])
    saved = operands(settings, np.full((4, 6), 65535, np.uint16))
    saved.protection[1, 3] = True
    original_alpha = alpha.copy()
    expected = background.copy()
    expected[1, 3] = np.rint(
        foreground[1, 3] * (int(alpha[1, 3]) / 65535)
        + background[1, 3] * (1 - int(alpha[1, 3]) / 65535)
    )
    actual = render_background(
        foreground, alpha, background, spatial_fade=saved, fade_background16=background
    )
    np.testing.assert_array_equal(actual, expected)
    black = render_black(foreground, alpha, spatial_fade=saved, fade_background16=background)
    assert np.any(black[..., 0] > 0)
    rgba = view_rgba(foreground, alpha, spatial_fade=saved, fade_background16=background)
    np.testing.assert_array_equal(rgba[..., 3], np.rint(alpha / 257).astype(np.uint8))
    np.testing.assert_array_equal(rgba[0, 3, :3], np.rint(background[0, 3] / 257).astype(np.uint8))
    panels = review_panels(
        foreground,
        foreground,
        alpha,
        background16=background,
        spatial_fade=saved,
        fade_background16=background,
    )
    np.testing.assert_array_equal(panels["result"], np.rint(actual / 257).astype(np.uint8))
    gray = np.full_like(background, 32768)
    gray_expected = render_background(
        foreground, alpha, gray, spatial_fade=saved, fade_background16=background
    )
    np.testing.assert_array_equal(panels["gray"], np.rint(gray_expected / 257).astype(np.uint8))
    np.testing.assert_array_equal(alpha, original_alpha)
    with pytest.raises((ProjectError, ValueError), match="target|background"):
        render_black(foreground, alpha, spatial_fade=saved)
    with pytest.raises((ProjectError, ValueError), match="shading|exclusive"):
        render_black(
            foreground,
            alpha,
            np.ones_like(alpha),
            0.5,
            spatial_fade=saved,
            fade_background16=background,
        )


def test_spatial_zero_legacy_and_crop_paths_preserve_exact_pixels():
    from blackmask.export import render_background, render_black, view_rgba
    from blackmask.spatial_fade import SpatialFadeOperands

    rng = np.random.default_rng(123)
    rgb = rng.integers(0, 65536, (8, 12, 3), np.uint16)
    alpha = rng.integers(0, 65536, (8, 12), np.uint16)
    background = rng.integers(0, 65536, rgb.shape, np.uint16)
    saved = operands(spatial_settings(12, 8), np.zeros(alpha.shape, np.uint16))
    for renderer, arguments in (
        (render_black, (rgb, alpha)),
        (render_background, (rgb, alpha, background)),
        (view_rgba, (rgb, alpha)),
    ):
        np.testing.assert_array_equal(
            renderer(*arguments),
            renderer(*arguments, spatial_fade=saved, fade_background16=background),
        )
    saved.weight16[:] = rng.integers(0, 65536, alpha.shape, np.uint16)
    full = render_background(
        rgb, alpha, background, spatial_fade=saved, fade_background16=background
    )
    rows, columns = slice(2, 7), slice(3, 11)
    cropped = SpatialFadeOperands(
        saved.weight16[rows, columns], saved.protection[rows, columns], saved.record
    )
    np.testing.assert_array_equal(
        full[rows, columns],
        render_background(
            rgb[rows, columns],
            alpha[rows, columns],
            background[rows, columns],
            spatial_fade=cropped,
            fade_background16=background[rows, columns],
        ),
    )


def delivered_spatial(directory, record):
    from blackmask.repair import scalar16
    from blackmask.spatial_fade import SpatialFadeOperands

    return SpatialFadeOperands(
        scalar16(directory / "spatial_fade_weight16.png"),
        scalar16(directory / "spatial_fade_protection16.png") != 0,
        record,
    )


@pytest.mark.parametrize("delivery", ["native", "margins", "series"])
def test_spatial_switch_back_exports_declare_and_replay_active_shading(tmp_path, delivery):
    import shutil

    import tifffile
    from test_effects import fixture_project, shading_request

    from blackmask import operations
    from blackmask.export import export_project
    from blackmask.framing import frame_result, validate_margins
    from blackmask.repair import scalar16
    from blackmask.series_framing import (
        SeriesSettings,
        compute_series_layout,
        render_series,
        series_sampling_plan,
        validate_series_settings,
    )

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, spatial_request(project))
    result = operations.apply_operation(project, shading_request(project, opacity=0.75))
    margins = {"left_px": 1, "right_px": 2, "top_px": 1, "bottom_px": 0}
    options = {}
    if delivery == "margins":
        options["framing"] = margins
    elif delivery == "series":
        options["series"] = SeriesSettings(output_width_px=17, output_height_px=19).to_dict()
    response = export_project(project, revision=result["revision"], draft=True, **options)
    native_path = Path(response.get("editable_companion", response)["directory"])
    portable = tmp_path / "portable"
    portable.mkdir()
    native = Path(shutil.copytree(native_path, portable / native_path.name))
    frame = None
    if delivery != "native":
        frame_path = Path(response["directory"])
        frame = Path(shutil.copytree(frame_path, portable / frame_path.name))
    project.rename(tmp_path / "original-project-unavailable")
    manifest = json.loads((native / "manifest.json").read_bytes())
    assert not manifest["spatial_fade"]["enabled"] and manifest["shading"]["enabled"]
    foreground = tifffile.imread(native / "foreground_rgb16.tif").astype(np.float64)
    alpha16 = scalar16(native / "alpha16.png")
    alpha = alpha16.astype(np.float64) / 65535
    weight = scalar16(native / "shadow_weight16.png")
    assert np.any((weight > 0) & (alpha16 > 0) & (alpha16 < 65535))
    background = tifffile.imread(native / "background_rgb16.tif")
    # Follow the formula actually delivered to the recipient; never execute prose.
    formula = manifest["result_compositing"]
    assert formula in (native / "README.txt").read_text()
    factor = (
        1 - manifest["shading"]["opacity"] * weight.astype(np.float64) / 65535
        if "F*A*H" in formula
        else np.ones(alpha.shape)  # The spatial formula at saved q=0 omits H.
    )
    replay = np.rint(
        foreground * alpha[..., None] * factor[..., None] + background * (1 - alpha[..., None])
    ).astype(np.uint16)
    np.testing.assert_array_equal(replay, tifffile.imread(native / "result_rgb16.tif"))
    if frame is not None:
        compact = json.loads((frame / "manifest.json").read_bytes())
        if delivery == "margins":
            framed = frame_result(replay, background, validate_margins(margins, (6, 4)))
        else:
            sampling = series_sampling_plan(
                compute_series_layout(alpha16, validate_series_settings(compact["settings"]))
            )
            framed = render_series(
                foreground.astype(np.uint16),
                alpha16,
                sampling,
                weight16=weight,
                opacity=manifest["shading"]["opacity"],
                spatial_fade=delivered_spatial(native, manifest["spatial_fade"]),
                background_settings=manifest["background"]["settings"],
            )
        np.testing.assert_array_equal(framed, tifffile.imread(frame / "result_rgb16.tif"))


def test_spatial_native_export_reconstructs_from_actual_delivered_layers(tmp_path):
    import tifffile
    from PIL import Image
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.export import export_project, render_background, saved_layers, view_rgba
    from blackmask.project import digest
    from blackmask.repair import scalar16

    project, source, _ = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    settings["oval"].update(
        center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], transition_width=0.5, amount=1
    )
    result = operations.apply_operation(project, spatial_request(project, settings))
    foreground, alpha, _ = saved_layers(project, result["revision"], result["developed_id"])
    exported = Path(export_project(project, revision=result["revision"], draft=True)["directory"])
    manifest = json.loads((exported / "manifest.json").read_bytes())
    saved = delivered_spatial(exported, manifest["spatial_fade"])
    np.testing.assert_array_equal(tifffile.imread(exported / "foreground_rgb16.tif"), foreground)
    np.testing.assert_array_equal(tifffile.imread(exported / "source_rgb16.tif"), source)
    np.testing.assert_array_equal(scalar16(exported / "alpha16.png"), alpha)
    background = tifffile.imread(exported / "background_rgb16.tif")
    np.testing.assert_array_equal(
        render_background(
            foreground, alpha, background, spatial_fade=saved, fade_background16=background
        ),
        tifffile.imread(exported / "result_rgb16.tif"),
    )
    with Image.open(exported / "transparent_RGBA8_VIEW.png") as image:
        np.testing.assert_array_equal(
            np.array(image),
            view_rgba(foreground, alpha, spatial_fade=saved, fade_background16=background),
        )
    for name in ("weight16.png", "protection16.png", "alpha16.png", "settings.json"):
        member = "spatial_fade_" + name
        assert manifest["files"][member] == digest((exported / member).read_bytes())
    assert manifest["spatial_fade"]["settings"] == settings


@pytest.mark.parametrize("enabled,strength", [(True, 0.6), (False, 0.6), (True, 0)])
@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("series", [False, True])
def test_spatial_framed_pair_delivers_portable_native_companion(
    tmp_path, enabled, strength, transparent, series
):
    import shutil

    import tifffile
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.export import export_project, render_background
    from blackmask.framing import frame_result, validate_margins
    from blackmask.project import digest
    from blackmask.repair import scalar16
    from blackmask.series_framing import SeriesSettings

    project, _, _ = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    settings["enabled"] = enabled
    settings["oval"]["amount"] = strength
    result = operations.apply_operation(project, spatial_request(project, settings))
    margins = {"left_px": 1, "right_px": 2, "top_px": 3, "bottom_px": 1}
    options = {"series": SeriesSettings().to_dict()} if series else {"framing": margins}
    # Keep series canvas small; active series pixel replay is Task 4's contract.
    if series:
        options["series"].update(output_width_px=16, output_height_px=16)
    response = export_project(
        project, revision=result["revision"], draft=True, framed_transparent=transparent, **options
    )
    frame = Path(response["directory"])
    native = Path(response["editable_companion"]["directory"])
    expected_names = {"result_rgb16.tif", "result_RGB8_VIEW.png", "README.txt", "manifest.json"}
    if transparent:
        expected_names.add("transparent_RGBA8_VIEW.png")
    assert {p.name for p in frame.iterdir()} == expected_names
    assert native.name == result["revision"] + "-DRAFT"
    frame_manifest = json.loads((frame / "manifest.json").read_bytes())
    native_manifest = json.loads((native / "manifest.json").read_bytes())
    binding = frame_manifest["editable_companion"]
    assert set(binding) == {"directory_name", "manifest_sha256", "files_sha256"}
    assert binding["directory_name"] == native.name
    assert binding["manifest_sha256"] == digest((native / "manifest.json").read_bytes())
    assert binding["manifest_sha256"] == response["editable_companion"]["manifest_sha256"]
    assert binding["files_sha256"] == {
        p.name: digest(p.read_bytes()) for p in native.iterdir() if p.name != "manifest.json"
    }
    assert frame_manifest["revision_manifest_sha256"] == native_manifest["revision_manifest_sha256"]
    assert native_manifest["spatial_fade"]["settings"] == settings
    assert native.name in (frame / "README.txt").read_text()
    assert (
        str(project)
        not in (frame / "README.txt").read_text() + (frame / "manifest.json").read_text()
    )
    isolated = tmp_path / "portable"
    isolated.mkdir()
    copied_native = Path(shutil.copytree(native, isolated / native.name))
    copied_frame = Path(shutil.copytree(frame, isolated / frame.name))
    project.rename(tmp_path / "original-project-unavailable")
    # The renderer receives only copied files; no project path participates in replay.
    with patch(
        "blackmask.project.read_project", side_effect=AssertionError("Original project unavailable")
    ):
        foreground = tifffile.imread(copied_native / "foreground_rgb16.tif")
        alpha = scalar16(copied_native / "alpha16.png")
        background = tifffile.imread(copied_native / "background_rgb16.tif")
        saved = delivered_spatial(copied_native, native_manifest["spatial_fade"])
        replay = render_background(
            foreground, alpha, background, spatial_fade=saved, fade_background16=background
        )
        np.testing.assert_array_equal(replay, tifffile.imread(copied_native / "result_rgb16.tif"))
        if not series:
            np.testing.assert_array_equal(
                frame_result(replay, background, validate_margins(margins, (6, 4))),
                tifffile.imread(copied_frame / "result_rgb16.tif"),
            )


@pytest.mark.parametrize("failure", ["native-sync", "frame-render", "frame-sync"])
def test_spatial_pair_failures_keep_outputs_and_identical_retry_completes(tmp_path, failure):
    from test_effects import fixture_project

    from blackmask import export, operations

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, spatial_request(project))
    options = {
        "revision": result["revision"],
        "draft": True,
        "framing": {"left_px": 1, "right_px": 1, "top_px": 1, "bottom_px": 1},
    }
    native = project / "exports" / (result["revision"] + "-DRAFT")
    original_sync = export._sync_directory
    count = 0

    def fail_sync(path):
        nonlocal count
        if path == project / "exports":
            count += 1
            if count == (1 if failure == "native-sync" else 2):
                raise OSError("Synthetic paired sync interruption")
        return original_sync(path)

    if failure == "frame-render":
        context = patch(
            "blackmask.framing.frame_result",
            side_effect=OSError("Synthetic frame render interruption"),
        )
    else:
        context = patch.object(export, "_sync_directory", fail_sync)
    with context, pytest.raises(ProjectError) as error:
        export.export_project(project, **options)
    assert native.is_dir() and str(native) in str(error.value)
    before = {p.name: p.read_bytes() for p in native.iterdir()}
    response = export.export_project(project, **options)
    assert response["editable_companion"]["directory"] == str(native)
    assert {p.name: p.read_bytes() for p in native.iterdir()} == before
    assert Path(response["directory"]).is_dir()


@pytest.mark.parametrize("failure", [None, "sync", "cleanup"])
def test_spatial_companion_reuse_discards_only_current_durable_duplicate(tmp_path, failure):
    from test_effects import fixture_project

    from blackmask import export, operations

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, spatial_request(project))
    options = {
        "revision": result["revision"],
        "draft": True,
        "framing": {"left_px": 1, "right_px": 1, "top_px": 1, "bottom_px": 1},
    }
    first = export.export_project(project, **options)
    native = Path(first["editable_companion"]["directory"])
    expected = {p.name: p.read_bytes() for p in native.iterdir()}
    exports = project / "exports"
    retained = exports / ".export-retained-failed-evidence"
    retained.mkdir()
    (retained / "evidence.txt").write_bytes(b"earlier failure: preserve")
    if failure is not None:
        original_sync = export._sync_directory

        def fail_parent_sync(path):
            if path == exports:
                raise OSError("retry parent sync failed")
            return original_sync(path)

        context = (
            patch.object(export, "_sync_directory", side_effect=fail_parent_sync)
            if failure == "sync"
            else patch.object(
                export.shutil, "rmtree", side_effect=OSError("duplicate cleanup failed")
            )
        )
        with context, pytest.raises(ProjectError):
            export.export_project(project, **options)
    preserved = {
        p: {f.name: f.read_bytes() for f in p.iterdir()} for p in exports.glob(".export-*")
    }
    assert retained in preserved
    if failure is not None:
        assert len(preserved) >= 2
    for left in (1, 1, 2):
        options["framing"]["left_px"] = left
        response = export.export_project(project, **options)
        assert response["editable_companion"]["directory"] == str(native)
        assert {p.name: p.read_bytes() for p in native.iterdir()} == expected
        assert set(exports.glob(".export-*")) == set(preserved)
        for path, files in preserved.items():
            assert {p.name: p.read_bytes() for p in path.iterdir()} == files


@pytest.mark.parametrize("tamper", ["modify", "missing", "extra", "symlink"])
def test_spatial_companion_reuse_rejects_tampering_without_overwrite(tmp_path, tamper):
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.export import export_project

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, spatial_request(project))
    options = {
        "revision": result["revision"],
        "draft": True,
        "framing": {"left_px": 1, "right_px": 1, "top_px": 1, "bottom_px": 1},
    }
    first = export_project(project, **options)
    native = Path(first["editable_companion"]["directory"])
    target = native / "README.txt"
    if tamper == "modify":
        target.write_bytes(b"changed")
    elif tamper == "missing":
        target.rename(native / "renamed.txt")
    elif tamper == "extra":
        (native / "extra").mkdir()
    else:
        target.rename(native / "original.txt")
        target.symlink_to(native / "original.txt")
    with pytest.raises(ProjectError, match="collision|differing|unexpected"):
        export_project(project, **options)
    assert Path(first["directory"]).is_dir()


def test_spatial_saved_reviews_use_canonical_colour_and_new_background_retains_geometry(tmp_path):
    import tifffile
    from PIL import Image
    from test_background import background_request
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.effects import saved_spatial_fade
    from blackmask.export import render_background, saved_layers
    from blackmask.review import review_project

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, spatial_request(project))
    rgb, alpha, before = saved_layers(project, result["revision"], result["developed_id"])
    saved = saved_spatial_fade(project, result["revision"], alpha, before)
    background = tifffile.imread(
        saved_raster(project / "revisions" / result["revision"] / "background/background_rgb16.tif")
    )
    expected = render_background(
        rgb, alpha, background, spatial_fade=saved, fade_background16=background
    )
    generated = project / "revisions" / result["revision"] / "review"
    overview = json.loads((generated / "manifest.json").read_bytes())
    assert overview["overview"] is True
    assert all(set(crop["files"]) == {"overview"} for crop in overview["crops"])
    assert not list(generated.glob("*.png"))
    reviewed = Path(review_project(project)["manifest_file"])
    record = json.loads(reviewed.read_bytes())
    assert record["effects"]["spatial_fade"] == before["spatial_fade"]
    assert record["assets"]["spatial_fade"].endswith("effects/spatial-fade/settings.json")
    with Image.open(reviewed.parent / "crop-000-result_RGB8_VIEW.png") as image:
        np.testing.assert_array_equal(np.array(image), np.rint(expected / 257).astype(np.uint8))
    changed = operations.apply_operation(project, background_request(project, "#552233", 0.2))
    new_rgb, new_alpha, after = saved_layers(project, changed["revision"], result["developed_id"])
    assert after["spatial_fade"] == before["spatial_fade"]
    for name, checksum in before["files"].items():
        if name.startswith("effects/spatial-fade/"):
            assert after["files"][name] == checksum
    for name, reference in before["assets"].items():
        if name.startswith("effects/spatial-fade/"):
            assert after["assets"][name] == reference
    np.testing.assert_array_equal(new_rgb, rgb)
    np.testing.assert_array_equal(new_alpha, alpha)
    assert after["background"] != before["background"]


def test_spatial_pair_admission_precedes_both_publications_and_native_arrays_are_shared(tmp_path):
    from test_effects import fixture_project

    from blackmask import export, operations

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, spatial_request(project))
    options = {
        "revision": result["revision"],
        "draft": True,
        "framing": {"left_px": 1, "right_px": 1, "top_px": 1, "bottom_px": 1},
    }
    with (
        patch.object(export, "check_space", side_effect=ProjectError("Insufficient paired space")),
        pytest.raises(ProjectError, match="space"),
    ):
        export.export_project(project, **options)
    assert not (project / "exports").exists()
    real_layers, real_native = export.saved_layers, export._export_native_locked
    consumed = []

    def layers(*args, **kwargs):
        values = real_layers(*args, **kwargs)
        consumed.append(values[:2])
        return values

    def native(*args, **kwargs):
        assert kwargs["foreground"] is consumed[0][0]
        assert kwargs["alpha"] is consumed[0][1]
        return real_native(*args, **kwargs)

    with (
        patch.object(export, "saved_layers", layers),
        patch.object(export, "_export_native_locked", native),
    ):
        first = export.export_project(project, **options)
    assert len(consumed) == 1
    native_directory = Path(first["editable_companion"]["directory"])
    original = {p.name: p.read_bytes() for p in native_directory.iterdir()}
    options["framing"]["left_px"] = 2
    second = export.export_project(project, **options)
    assert second["editable_companion"] == first["editable_companion"]
    assert second["directory"] != first["directory"]
    assert {p.name: p.read_bytes() for p in native_directory.iterdir()} == original


def test_spatial_operation_retains_shared_schema2_operands(tmp_path):
    from test_effects import fixture_project
    from test_operations import request

    from blackmask import operations
    from blackmask.project import read_project, read_revision

    project, _, parent = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    result = operations.apply_operation(
        project,
        request(
            project,
            kind="effects",
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            spatial_fade=settings,
        ),
    )
    manifest = read_revision(project, result["revision"], read_project(project)["developed_id"])
    roles = {
        "effects/spatial-fade/weight16.png",
        "effects/spatial-fade/protection16.png",
        "effects/spatial-fade/alpha16.png",
    }
    assert roles <= set(manifest["assets"])
    assert not roles & set(manifest["files"])
    assert all(not (project / "revisions" / result["revision"] / name).exists() for name in roles)
    assert read_project(project)["latest_result_revision"] == result["revision"]
    assert read_project(project)["accepted_revision"] == parent["revision"]
