"""Independent gain, immutable operands and offline Shadow fade workflows."""

import json
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_effects import fixture_project
from test_ingest import bind_raster, saved_hashes, saved_raster

from blackmask import operations
from blackmask.export import saved_layers
from blackmask.project import ProjectError, _json_bytes, digest, read_project, read_revision


def fade_settings(amount=0.5, preserve=1.0, enabled=True):
    return {"enabled": enabled, "amount": amount, "preserve_highlights": preserve}


def scalar_fade(pixel, support, amount, preserve, reduction=0):
    """Scalar oracle: deliberately independent of production transfer helpers."""
    linear = [
        v / 65535 / 12.92 if v / 65535 <= 0.04045 else ((v / 65535 + 0.055) / 1.055) ** 2.4
        for v in pixel
    ]
    luminance = sum(v * c for v, c in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))
    transition = max(0, min(1, (luminance - 0.10) / 0.65))
    highlight = transition**2 * (3 - 2 * transition)
    gain = 2 ** (
        -6 * amount * support / 65535 * (1 - preserve * highlight) * (1 - reduction / 65535)
    )
    return [
        round(
            65535
            * (
                12.92 * v * gain
                if v * gain <= 0.0031308
                else 1.055 * (v * gain) ** (1 / 2.4) - 0.055
            )
        )
        for v in linear
    ]


@pytest.mark.parametrize("preserve", [0, 0.73])
def test_shadow_reduction_weights_exponent_once_with_exact_protected_endpoints(preserve):
    from blackmask.shadow_fade import apply_shadow_fade

    rgb = np.full((1, 7, 3), 30000, np.uint16)
    alpha = np.array([[65535, 32768, 1, 32768, 0, 32768, 65535]], np.uint16)
    support = np.array([[65535, 65535, 65535, 65535, 65535, 0, 65535]], np.uint16)
    protection = np.array([[False, False, False, True, False, False, False]])
    reduction = np.array([[0, 32768, 65535, 32768, 32768, 32768, 32768]], np.uint16)
    before = [value.copy() for value in (rgb, alpha, support, protection, reduction)]
    result = apply_shadow_fade(
        rgb, alpha, support, protection, fade_settings(0.5, preserve), reduction
    )
    expected = rgb.copy()
    for index in (0, 1, 6):
        expected[0, index] = scalar_fade(
            rgb[0, index], 65535, 0.5, preserve, int(reduction[0, index])
        )
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(result[0, 1], result[0, 6])
    assert np.all(result[0, 1] < rgb[0, 1])
    sensitive = protection & (alpha > 0) & (alpha < 65535) & (support > 0)
    sensitive &= (reduction > 0) & (reduction < 65535)
    assert sensitive.any()
    legacy = np.array(scalar_fade(rgb[0, 1], 65535, 0.5, preserve))
    wrong_interpolation = np.rint(legacy + (rgb[0, 1] - legacy) * (32768 / 65535))
    assert not np.array_equal(result[0, 1], wrong_interpolation)
    assert not np.array_equal(result[0, 1], legacy)
    wrong_double = scalar_fade(
        rgb[0, 1], 65535, 0.5, preserve, 65535 * (1 - (1 - 32768 / 65535) ** 2)
    )
    assert not np.array_equal(result[0, 1], wrong_double)
    for original, value in zip(before, (rgb, alpha, support, protection, reduction), strict=True):
        np.testing.assert_array_equal(value, original)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("bad", [np.zeros((1, 2), float), np.zeros((2, 1), np.uint16)])
def test_shadow_reduction_rejects_bad_registration_even_off(enabled, bad):
    from blackmask.shadow_fade import apply_shadow_fade

    with pytest.raises(ProjectError, match="reduction"):
        apply_shadow_fade(
            np.full((1, 2, 3), 30000, np.uint16),
            np.full((1, 2), 32768, np.uint16),
            np.full((1, 2), 65535, np.uint16),
            np.zeros((1, 2), bool),
            fade_settings(enabled=enabled),
            bad,
        )


def test_shadow_zero_reduction_preserves_legacy_and_off_copies_exactly():
    from blackmask.shadow_fade import apply_shadow_fade

    rgb = (np.arange(18).reshape(2, 3, 3) * 3001).astype(np.uint16)
    alpha = np.full((2, 3), 32768, np.uint16)
    support = np.full_like(alpha, 45001)
    protection = np.zeros_like(alpha, bool)
    for settings in (fade_settings(preserve=0.73), fade_settings(enabled=False), fade_settings(0)):
        legacy = apply_shadow_fade(rgb, alpha, support, protection, settings)
        np.testing.assert_array_equal(
            legacy,
            apply_shadow_fade(rgb, alpha, support, protection, settings, np.zeros_like(alpha)),
        )
        if not settings["enabled"] or settings["amount"] == 0:
            np.testing.assert_array_equal(
                rgb,
                apply_shadow_fade(
                    rgb, alpha, support, protection, settings, np.full_like(alpha, 32768)
                ),
            )


def test_shadow_reduction_saved_lifecycle_retains_spatial_and_inherited_operands(tmp_path):
    from test_fade_reduction import area, rectangle, reduction_request
    from test_spatial_fade import spatial_request

    from blackmask.assets import revision_asset, revision_hashes
    from blackmask.export import saved_layers
    from blackmask.fade_reduction import read_fade_reduction
    from blackmask.repair import scalar16

    project, _, accepted = fixture_project(tmp_path)
    operations.apply_operation(project, spatial_request(project))
    spatial = operations.apply_operation(project, reduction_request(project))
    legacy = operations.apply_operation(project, fade_request(project, preserve=0))
    master = legacy["developed_id"]
    before = read_revision(project, legacy["revision"], master)
    before_files = revision_hashes(before)
    assert before["shadow_fade"]["schema_version"] == 2
    document = area(rectangle(amount=0.5, box=[0, 0, 6, 4]))
    reduced = operations.apply_operation(
        project, reduction_request(project, document, target="shadow_fade")
    )
    selected = read_revision(project, reduced["revision"], master)
    record = selected["shadow_fade"]
    assert record["schema_version"] == 3 and record["enabled"]
    assert record["settings"] == before["shadow_fade"]["settings"]
    directory = project / "revisions" / reduced["revision"]
    alpha = scalar16(revision_asset(project, directory, selected, "base_alpha16.png"))
    np.testing.assert_array_equal(
        read_fade_reduction(project, directory, selected, "shadow_fade", alpha),
        np.full((4, 6), 32768, np.uint16),
    )
    for name, checksum in before_files.items():
        if name in {"foreground_rgb16.tif", "base_alpha16.png", "guides.json"} or name.startswith(
            ("supports/", "effects/spatial-fade/")
        ):
            assert revision_hashes(selected)[name] == checksum
    assert selected["spatial_fade"] == before["spatial_fade"] == spatial["spatial_fade"]
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    reduced_pixels = saved_layers(project, reduced["revision"], master)[0]
    original_pixels = saved_layers(project, legacy["revision"], master)[0]
    assert np.any(reduced_pixels > original_pixels)
    np.testing.assert_array_equal(
        saved_layers(project, reduced["revision"], master, shadow_reduction_off=True)[0],
        original_pixels,
    )
    reused = operations.apply_operation(
        project, reduction_request(project, document, target="shadow_fade")
    )
    assert reused["reused"] and reused["revision"] == reduced["revision"]
    changed = operations.apply_operation(
        project,
        reduction_request(
            project, area(rectangle(amount=0.75, box=[0, 0, 6, 4])), target="shadow_fade"
        ),
    )
    assert not changed["reused"]
    settings_changed = operations.apply_operation(
        project, fade_request(project, amount=0.25, amount_only=True)
    )
    disabled = operations.apply_operation(project, fade_request(project, enabled=False))
    from blackmask.export import export_project

    delivered = Path(
        export_project(project, revision=disabled["revision"], draft=True, variants=("editable",))[
            "directory"
        ]
    )
    assert json.loads((delivered / "shadow_fade_reduction.json").read_bytes())["regions"]
    np.testing.assert_array_equal(
        scalar16(delivered / "shadow_fade_reduction16.png"), np.full((4, 6), 49151, np.uint16)
    )
    assert (
        json.loads((delivered / "manifest.json").read_bytes())["shadow_fade"]["reduction_sha256"]
        == changed["shadow_fade"]["reduction_sha256"]
    )
    rebuilt = operations.apply_operation(project, fade_request(project, amount=0.6, preserve=0))
    for result in (settings_changed, disabled, rebuilt):
        inherited = read_revision(project, result["revision"], master)["shadow_fade"]
        assert inherited["schema_version"] == 3
        for key in ("reduction_sha256", "reduction_area_sha256", "reduction_algorithm"):
            assert inherited[key] == changed["shadow_fade"][key]
    cleared = operations.apply_operation(
        project, reduction_request(project, area(), target="shadow_fade")
    )
    clear_manifest = read_revision(project, cleared["revision"], master)
    assert clear_manifest["shadow_fade"]["schema_version"] == 3
    assert not read_fade_reduction(
        project, project / "revisions" / cleared["revision"], clear_manifest, "shadow_fade", alpha
    ).any()
    assert read_revision(project, legacy["revision"], master) == before
    assert read_project(project)["accepted_revision"] == accepted["revision"]


def test_shadow_reduction_reuse_binds_current_saved_settings_and_operands(tmp_path):
    from test_fade_reduction import area, rectangle, reduction_request

    from blackmask.fade_reduction import rasterize_fade_reduction

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, fade_request(project))
    result = operations.apply_operation(project, reduction_request(project, target="shadow_fade"))
    directory = project / "revisions" / result["revision"]
    manifest = read_revision(project, result["revision"], result["developed_id"])
    changed_area = area(rectangle(amount=0.75, box=[0, 0, 6, 4]))
    folder = directory / "effects/shadow-fade"
    (folder / "reduction.json").write_bytes(_json_bytes(changed_area))
    Image.fromarray(rasterize_fade_reduction(changed_area, result["developed_id"], 6, 4)).save(
        folder / "reduction16.png"
    )
    for name, key in (
        ("reduction.json", "reduction_area_sha256"),
        ("reduction16.png", "reduction_sha256"),
    ):
        manifest["shadow_fade"][key] = digest((folder / name).read_bytes())
        bind_raster(project, directory, manifest, "effects/shadow-fade/" + name)
    (folder / "settings.json").write_bytes(_json_bytes(manifest["shadow_fade"]))
    bind_raster(project, directory, manifest, "effects/shadow-fade/settings.json")
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    read_revision(project, result["revision"], result["developed_id"])
    repeated = operations.apply_operation(project, reduction_request(project, target="shadow_fade"))
    assert not repeated["reused"]
    assert repeated["shadow_fade"]["reduction_sha256"] == result["shadow_fade"]["reduction_sha256"]


def test_shadow_fade_identity_and_exact_exclusions():
    from blackmask.shadow_fade import apply_shadow_fade

    rgb = np.array([[[19337, 31111, 47003]] * 6], np.uint16)
    alpha = np.array([[65535, 32768, 0, 32768, 65535, 32768]], np.uint16)
    support = np.array([[65535, 65535, 65535, 65535, 0, 32768]], np.uint16)
    protection = np.array([[False, False, False, True, False, False]])
    originals = [v.copy() for v in (rgb, alpha, support, protection)]
    result = apply_shadow_fade(rgb, alpha, support, protection, fade_settings(preserve=0))
    assert np.all(result[0, 0] < rgb[0, 0])
    np.testing.assert_array_equal(result[0, 0], result[0, 1])
    assert np.all((result[0, 5] > result[0, 0]) & (result[0, 5] < rgb[0, 5]))
    np.testing.assert_array_equal(result[0, [2, 3, 4]], rgb[0, [2, 3, 4]])
    for settings in (fade_settings(enabled=False), fade_settings(amount=0)):
        np.testing.assert_array_equal(
            apply_shadow_fade(rgb, alpha, support, protection, settings), rgb
        )
    for actual, before in zip((rgb, alpha, support, protection), originals, strict=True):
        np.testing.assert_array_equal(actual, before)


def test_shadow_fade_independent_gain_and_highlight_transition():
    from blackmask.shadow_fade import apply_shadow_fade

    pixels = [
        [65535] * 3,
        [65535] * 3,
        [200, 2650, 2651],
        [3000, 1000, 4000],
        [22883] * 3,
        [22885] * 3,
        [40001] * 3,
        [57724] * 3,
        [57726] * 3,
        [60000] * 3,
        [65535, 7001, 12345],
    ]
    rgb = np.array([pixels], np.uint16)
    alpha = np.full(rgb.shape[:2], 65535, np.uint16)
    alpha[0, 1] = 32768
    protection = np.zeros(alpha.shape, bool)
    sentinel = apply_shadow_fade(
        rgb, alpha, np.full_like(alpha, 65535), protection, fade_settings(1 / 6, 0)
    )
    np.testing.assert_array_equal(sentinel[0, :2], [[48192] * 3] * 2)
    previous = rgb
    for amount in (0.1, 0.38, 0.4, 1):
        result = apply_shadow_fade(rgb, alpha, alpha, protection, fade_settings(amount, 0.7))
        expected = [
            [
                scalar_fade(pixel, int(support), amount, 0.7)
                for pixel, support in zip(rgb[0], alpha[0], strict=True)
            ]
        ]
        np.testing.assert_array_equal(result, expected)
        assert np.all(result <= previous)
        previous = result
    preserved = apply_shadow_fade(rgb, alpha, alpha, protection, fade_settings(1, 1))
    np.testing.assert_array_equal(preserved[0, [0, 1, 9]], rgb[0, [0, 1, 9]])
    assert np.max(np.abs(preserved[0, 4].astype(int) - preserved[0, 5])) < 4
    assert np.max(np.abs(preserved[0, 7].astype(int) - preserved[0, 8])) < 4


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        fade_settings(True),
        fade_settings(-0.1),
        fade_settings(1.1),
        fade_settings(float("nan")),
        fade_settings(0.2, float("inf")),
        fade_settings(0.2, True),
        fade_settings(0.2, 2**100),
        dict(fade_settings(), extra=0),
        fade_settings(enabled=1),
    ],
)
def test_shadow_fade_invalid_settings(settings):
    from blackmask.shadow_fade import validate_shadow_fade

    with pytest.raises(ProjectError):
        validate_shadow_fade(settings)


def test_shadow_fade_invalid_registration():
    from blackmask.shadow_fade import apply_shadow_fade

    rgb = np.ones((2, 3, 3), np.uint16)
    alpha = np.ones((2, 3), np.uint16)
    protection = np.zeros(alpha.shape, bool)
    for values in (
        (rgb.astype(float), alpha, alpha, protection),
        (rgb, alpha[:1], alpha, protection),
        (rgb, alpha, alpha.astype(float), protection),
        (rgb, alpha, alpha, alpha),
    ):
        with pytest.raises(ProjectError):
            apply_shadow_fade(*values, fade_settings())


def fade_request(
    project, *, amount=0.5, preserve=1.0, enabled=True, amount_only=False, area=None, **extra
):
    from test_exposure import rectangle
    from test_operations import request

    fields = {
        "shadow_fade": fade_settings(amount, preserve, enabled),
        "scope_xyxy": [0, 0, 6, 4],
        "candidate_comparison": True,
    }
    if amount_only:
        fields["shadow_fade_amount_only"] = True
    elif enabled:
        fields["shadow_fade_area"] = (
            area
            if area is not None
            else {
                "regions": [rectangle("fade", [1, 0, 6, 4])],
                "protection": [rectangle("protected", [2, 1, 3, 2])],
            }
        )
    fields.update(extra)
    return request(project, kind="effects", **fields)


def test_saved_fade_independent_noncompounding_replacement_and_reset(tmp_path):
    from test_effects import effect_request, fixture_project
    from test_exposure import exposure_request, rectangle

    from blackmask import operations
    from blackmask.export import saved_layers
    from blackmask.project import read_project
    from blackmask.repair import scalar16

    project, _, _ = fixture_project(tmp_path)
    exposed = operations.apply_operation(project, exposure_request(project, ev=2))
    master = read_project(project)["developed_id"]
    base, alpha, _ = saved_layers(project, exposed["revision"], master)
    first = operations.apply_operation(project, fade_request(project))
    directory = project / "revisions" / first["revision"] / "effects/shadow-fade"
    support = scalar16(saved_raster(directory / "support16.png"))
    protection = scalar16(saved_raster(directory / "protection16.png")) != 0
    accepted = read_project(project)["accepted_revision"]
    for amount, preserve in ((0.5, 1), (1, 0), (0.25, 0.5), (0, 1)):
        result = operations.apply_operation(
            project, fade_request(project, amount=amount, preserve=preserve, amount_only=True)
        )
        rgb, actual_alpha, manifest = saved_layers(project, result["revision"], master)
        expected = base.copy()
        for y, x in zip(*np.where((support != 0) & (alpha != 0) & ~protection), strict=True):
            expected[y, x] = scalar_fade(base[y, x], int(support[y, x]), amount, preserve)
        np.testing.assert_array_equal(rgb, expected)
        np.testing.assert_array_equal(actual_alpha, alpha)
        np.testing.assert_array_equal(
            saved_layers(project, result["revision"], master, shadow_fade_off=True)[0], base
        )
        assert manifest["local_exposure"] == exposed["local_exposure"]
        assert (
            project / "revisions" / result["revision"] / "effects/shadow-fade/area.json"
        ).read_bytes() == (directory / "area.json").read_bytes()
    area_b = {"regions": [rectangle("b", [4, 0, 5, 4])], "protection": []}
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(
            project, fade_request(project, area=area_b, scope_xyxy=[4, 0, 5, 4])
        )
    assert (project / "state.json").read_bytes() == before
    replaced = operations.apply_operation(project, fade_request(project, area=area_b, preserve=0))
    rgb = saved_layers(project, replaced["revision"], master)[0]
    np.testing.assert_array_equal(rgb[:, :4], base[:, :4])
    assert np.any(rgb[:, 4] != base[:, 4])
    disabled = operations.apply_operation(project, fade_request(project, enabled=False, amount=0))
    np.testing.assert_array_equal(saved_layers(project, disabled["revision"], master)[0], base)
    rebuilt = operations.apply_operation(
        project, effect_request(project, strength=0.5, candidate_comparison=True)
    )
    assert rebuilt["shadow_fade"] == disabled["shadow_fade"]
    assert read_project(project)["accepted_revision"] == accepted


@pytest.mark.parametrize(
    "fields",
    [
        {"shadow_fade_amount_only": True},
        {"shadow_fade_amount_only": 1},
        {"shadow_fade_area": {"regions": [], "protection": []}},
        {"shadow_fade_protection_file": "missing.png"},
        {"local_exposure": {"enabled": False, "ev": 0}},
        {"color_cleanup": {"enabled": False, "strength": 0}},
        {"shading": {"enabled": False, "opacity": 0}},
        {"unsupported": True},
    ],
)
def test_invalid_fade_requests_preserve_state(tmp_path, fields):
    from test_effects import fixture_project

    from blackmask.operations import apply_operation

    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        apply_operation(project, fade_request(project, **fields))
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("exposure", [False, True])
@pytest.mark.parametrize("fade", [False, True])
def test_legacy_optional_sections_load_independently_without_rewrite(tmp_path, exposure, fade):
    import tomllib

    import tomli_w
    from test_effects import fixture_project

    from blackmask.project import read_project, read_revision
    from blackmask.recipe import Recipe

    project, _, parent = fixture_project(tmp_path)
    path = project / "recipe.toml"
    recipe = tomllib.loads(path.read_text())
    if not exposure:
        recipe.pop("local_exposure", None)
    if fade:
        recipe["shadow_fade"] = fade_settings(enabled=False, amount=0)
    else:
        recipe.pop("shadow_fade", None)
    path.write_text(tomli_w.dumps(recipe))
    before = saved_raster(path).read_bytes()
    master = read_project(project)["developed_id"]
    parsed = Recipe.from_dict(recipe, master)
    assert parsed.shadow_fade == fade_settings(enabled=False, amount=0)
    assert parsed.local_exposure == {"enabled": False, "ev": 0}
    read_revision(project, parent["revision"], master)
    assert saved_raster(path).read_bytes() == before


@pytest.mark.parametrize("change_alpha", [False, True])
@pytest.mark.parametrize("repairing", [False, True])
@pytest.mark.parametrize("reduction", [False, True])
def test_fade_prepare_matte_repair_partial_rgb_locks_and_stale(
    tmp_path, change_alpha, repairing, reduction
):
    from unittest.mock import patch

    from test_effects import fixture_project
    from test_exposure import exposure_request, rectangle
    from test_matte_operations import StubSession, approve, run_matte
    from test_operations import edits, request
    from test_repair_operations import repair_request, run_repair

    from blackmask import operations
    from blackmask.export import export_project, saved_layers
    from blackmask.project import read_project

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, exposure_request(project, ev=2))
    first = operations.apply_operation(project, fade_request(project, preserve=0))
    from test_fade_reduction import reduction_request

    if reduction:
        first = operations.apply_operation(
            project, reduction_request(project, target="shadow_fade")
        )
    master = read_project(project)["developed_id"]
    before_rgb, before_alpha, _ = saved_layers(project, first["revision"], master)
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
    if reduction:
        prepared_record = read_revision(project, prepared["revision"], master)["shadow_fade"]
        assert prepared_record["schema_version"] == 3
        assert prepared_record["reduction_sha256"] == first["shadow_fade"]["reduction_sha256"]
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
    assert manifest["shadow_fade"]["stale"] is change_alpha
    if reduction:
        assert manifest["shadow_fade"]["schema_version"] == 3
        assert (
            manifest["shadow_fade"]["reduction_sha256"] == first["shadow_fade"]["reduction_sha256"]
        )
    np.testing.assert_array_equal(rgb[1, 3], before_rgb[1, 3])
    assert alpha[1, 3] == before_alpha[1, 3]
    if change_alpha:
        with pytest.raises(ProjectError, match="Stale"):
            export_project(project, revision=result["revision"], draft=True)
        with pytest.raises(ProjectError, match="Stale"):
            operations.apply_operation(project, fade_request(project, amount_only=True))
        disabled = operations.apply_operation(
            project, fade_request(project, enabled=False, amount=0)
        )
        assert disabled["local_exposure"]["stale"]
        assert not disabled["shadow_fade"]["stale"]
        with pytest.raises(ProjectError, match="current saved.*alpha"):
            operations.apply_operation(project, reduction_request(project, target="shadow_fade"))
    else:
        np.testing.assert_array_equal(rgb, before_rgb)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 1),
        ("enabled", 1),
        ("developed_id", "foreign"),
        ("algorithm", "unknown"),
        ("stale", True),
        ("unsupported", True),
        ("settings", fade_settings(True)),
    ],
)
def test_saved_disabled_fade_semantics_reject_rehashed_corruption(tmp_path, field, value):
    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, fade_request(project, enabled=False))
    master = read_project(project)["developed_id"]
    read_revision(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    record = manifest["shadow_fade"]
    record[field] = value
    settings = directory / "effects/shadow-fade/settings.json"
    saved_raster(settings).write_bytes(_json_bytes(record))
    manifest["files"]["effects/shadow-fade/settings.json"] = digest(
        saved_raster(settings).read_bytes()
    )
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError):
        read_revision(project, result["revision"], master)


@pytest.mark.parametrize(
    "asset",
    [
        "base_alpha16.png",
        "effects/shadow-fade/support16.png",
        "effects/shadow-fade/protection16.png",
        "effects/shadow-fade/alpha16.png",
        "effects/shadow-fade/settings.json",
        "effects/shadow-fade/area.json",
    ],
)
@pytest.mark.parametrize("request_local", [False, True])
def test_warm_fade_validation_rehashes_assets(tmp_path, asset, request_local):
    from blackmask.project import _validation_scope

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, fade_request(project))
    master = read_project(project)["developed_id"]
    with _validation_scope() if request_local else nullcontext():
        read_revision(project, result["revision"], master)
        path = project / "revisions" / result["revision"] / asset
        saved_raster(path).write_bytes(saved_raster(path).read_bytes() + b" ")
        with pytest.raises(ProjectError, match="hash mismatch"):
            read_revision(project, result["revision"], master)


def scalar_request(project):
    Image.fromarray(np.full((4, 6), 65535, np.uint16)).save(project / "area.png")
    Image.fromarray(np.zeros((4, 6), np.uint8)).save(project / "protect.png")
    operation = fade_request(project)
    operation.pop("shadow_fade_area")
    operation.update(support_file="area.png", shadow_fade_protection_file="protect.png")
    return operation


@pytest.mark.parametrize("enabled", [False, True])
def test_warm_fade_rejects_unbound_area_and_rehashed_geometry(tmp_path, enabled):
    from blackmask.project import _validation_scope
    from blackmask.repair import scalar16

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, scalar_request(project))
    if not enabled:
        result = operations.apply_operation(project, fade_request(project, enabled=False))
    master = read_project(project)["developed_id"]
    directory = project / "revisions" / result["revision"]
    with _validation_scope():
        read_revision(project, result["revision"], master)
        (directory / "effects/shadow-fade/area.json").write_text("{}")
        with pytest.raises(ProjectError, match="Unbound"):
            read_revision(project, result["revision"], master)
    # A distinct authored revision tests semantic cache renewal after all hashes change.
    other = tmp_path / "other"
    other.mkdir()
    project, _, _ = fixture_project(other)
    result = operations.apply_operation(project, fade_request(project))
    master = read_project(project)["developed_id"]
    read_revision(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    name = "effects/shadow-fade/support16.png"
    support = scalar16(saved_raster(directory / name))
    support[0, 1] = 0
    Image.fromarray(support).save(directory / name)
    bind_raster(project, directory, manifest, name)
    manifest["shadow_fade"]["support_sha256"] = saved_hashes(manifest)[name]
    settings = directory / "effects/shadow-fade/settings.json"
    saved_raster(settings).write_bytes(_json_bytes(manifest["shadow_fade"]))
    manifest["files"]["effects/shadow-fade/settings.json"] = digest(
        saved_raster(settings).read_bytes()
    )
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="area differs"):
        read_revision(project, result["revision"], master)


@pytest.mark.parametrize(
    "filename",
    [
        "source.json",
        "recipe.toml",
        "guides.json",
        "request.json",
        "area.png",
        "protect.png",
        "parent",
    ],
)
@pytest.mark.parametrize("at_pointer", [False, True])
def test_fade_input_snapshot_races_preserve_pointers(tmp_path, filename, at_pointer):
    from blackmask import effects, review

    project, _, parent = fixture_project(tmp_path)
    operation = scalar_request(project)
    operation_path = project / "request.json"
    saved_raster(operation_path).write_bytes(_json_bytes(operation))
    before = (project / "state.json").read_bytes()
    path = project / (
        f"revisions/{parent['revision']}/manifest.json" if filename == "parent" else filename
    )

    def change():
        saved_raster(path).write_bytes(saved_raster(path).read_bytes() + b" ")

    if at_pointer:
        original = effects._atomic_json

        def changing(target, value, **kwargs):
            if target.name == "state.json":
                change()
            return original(target, value, **kwargs)

        owner, name = effects, "_atomic_json"
    else:
        original = review.write_revision_overview

        def changing(*args, **kwargs):
            result = original(*args, **kwargs)
            change()
            return result

        owner, name = review, "write_revision_overview"
    with patch.object(owner, name, changing), pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, operation, request_file=operation_path)
    assert (project / "state.json").read_bytes() == before


def test_fade_low_disk_busy_writer_and_pointer_failure_recovery(tmp_path):
    import subprocess
    import sys

    from blackmask import effects

    project, _, parent = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with (
        patch.object(effects, "check_space", side_effect=ProjectError("Low disk")),
        pytest.raises(ProjectError, match="Low disk"),
    ):
        operations.apply_operation(project, fade_request(project))
    command = [
        sys.executable,
        "-B",
        "-c",
        "from blackmask.project import project_lock; from pathlib import Path; import sys; lock=project_lock(Path(sys.argv[1])); lock.__enter__(); print('locked',flush=True); sys.stdin.readline()",
        str(project),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(ProjectError, match="busy"):
            operations.apply_operation(project, fade_request(project))
    finally:
        process.communicate("done\n", timeout=10)
    assert process.returncode == 0
    with (
        patch.object(effects, "_atomic_json", side_effect=OSError("interrupted pointer")),
        pytest.raises(OSError, match="interrupted"),
    ):
        operations.apply_operation(project, fade_request(project))
    assert (project / "state.json").read_bytes() == before
    master = read_project(project)["developed_id"]
    orphan = read_revision(project, "rev-003", master)
    assert orphan["shadow_fade"]["enabled"]
    operations.restore_revision(project, "rev-003", replace_drafts=True)
    assert read_project(project)["working_revision"] == "rev-003"
    assert read_project(project)["accepted_revision"] == parent["revision"]


def white_project(tmp_path):
    from test_ingest import srgb_profile, tiff
    from test_matte_operations import approve, run_matte
    from test_operations import edits, request

    from blackmask.project import accept_development, create_project

    rgb = np.full((4, 6, 3), [20001, 30001, 40001], np.uint16)
    rgb[0, 5] = 65535
    project = tmp_path / "project"
    create_project(tiff(tmp_path / "source.tif", rgb, profile=srgb_profile()), project, {})
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
    return project, run_matte(project)


def test_shadow_fade_preserves_upstream_exposure_clipping_counts(tmp_path):
    from test_exposure import exposure_request, rectangle

    from blackmask.review import review_project
    from blackmask.viewer import ReviewServer

    project, _ = white_project(tmp_path)
    area = {"regions": [rectangle("white", [5, 0, 6, 1])], "protection": []}
    operations.apply_operation(project, exposure_request(project, ev=2, area=area))
    expected = {"clipped_pixels": 1, "eligible_pixels": 1}
    for amount, preserve, enabled in ((0, 1, False), (1, 0, True), (0.5, 0, True)):
        result = operations.apply_operation(
            project,
            fade_request(project, amount=amount, preserve=preserve, enabled=enabled, area=area),
        )
        directory = project / "revisions" / result["revision"]
        assert (
            json.loads((directory / "review/manifest.json").read_bytes())["local_exposure_clipping"]
            == expected
        )
        refreshed = json.loads(
            saved_raster(
                Path(review_project(project, revision=result["revision"])["manifest_file"])
            ).read_bytes()
        )
        assert refreshed["effects"]["local_exposure"]["clipping"] == expected
        server = ReviewServer(project)
        try:
            for _ in range(2):
                row = next(
                    r for r in server.snapshot()["revisions"] if r["revision"] == result["revision"]
                )
                assert row["local_exposure"]["clipping"] == expected
        finally:
            server.server_close()
        if enabled:
            rgb = saved_layers(project, result["revision"], read_project(project)["developed_id"])[
                0
            ]
            np.testing.assert_array_equal(
                rgb[0, 5], scalar_fade([65535] * 3, 65535, amount, preserve)
            )


def test_fade_export_distinct_layers_exact_replay_and_fresh_process(tmp_path):
    import os
    import subprocess
    import sys

    from test_exposure import exposure_request

    from blackmask.export import export_project, render_black
    from blackmask.repair import scalar16

    project, _, _ = fixture_project(tmp_path)
    exposed = operations.apply_operation(project, exposure_request(project, ev=2))
    master = read_project(project)["developed_id"]
    unfaded = saved_layers(project, exposed["revision"], master)[0]
    cleanup_only = saved_layers(project, exposed["revision"], master, exposure_off=True)[0]
    result = operations.apply_operation(project, fade_request(project, amount=1 / 6, preserve=0))
    selected, alpha, _manifest = saved_layers(project, result["revision"], master)
    exported = Path(
        export_project(
            project,
            revision=result["revision"],
            draft=True,
            variants=("black", "transparent", "editable"),
        )["directory"]
    )
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "foreground_rgb16.tif")), selected
    )
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "unfaded_foreground_rgb16.tif")), unfaded
    )
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "unexposed_foreground_rgb16.tif")), cleanup_only
    )
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "base_foreground_rgb16.tif")), cleanup_only
    )
    support = scalar16(saved_raster(exported / "shadow_fade_support16.png"))
    protection = scalar16(saved_raster(exported / "shadow_fade_protection16.png")) != 0
    expected = unfaded.copy()
    for y, x in zip(*np.where((support != 0) & (alpha != 0) & ~protection), strict=True):
        expected[y, x] = scalar_fade(unfaded[y, x], int(support[y, x]), 1 / 6, 0)
    np.testing.assert_array_equal(selected, expected)
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "black_rgb16.tif")),
        np.rint(expected.astype(float) * (alpha.astype(float) / 65535)[..., None]).astype(
            np.uint16
        ),
    )
    assert render_black(
        np.array([[[48192] * 3]], np.uint16), np.array([[32768]], np.uint16)
    ).tolist() == [[[24096] * 3]]
    # Original path unavailable, inference/network forbidden in a new interpreter.
    (saved_raster(tmp_path / "source.tif")).rename(tmp_path / "unavailable.tif")
    program = """import socket, sys, json
from pathlib import Path
from unittest.mock import patch
import numpy as np, tifffile
from blackmask.export import saved_layers, export_project
from blackmask.project import read_project
from blackmask.shadow_fade import apply_shadow_fade
from blackmask.repair import scalar16
project, exported = map(Path, sys.argv[1:3]); revision=sys.argv[3]
with patch('socket.socket', side_effect=AssertionError('offline')), patch('blackmask.models.VitMatteSession', side_effect=AssertionError('no inference')):
    master=read_project(project)['developed_id']
    selected, alpha, _=saved_layers(project, revision, master)
    settings=json.loads((exported/'shadow_fade_settings.json').read_bytes())['settings']
    replay=apply_shadow_fade(tifffile.imread(exported/'unfaded_foreground_rgb16.tif'), scalar16(exported/'shadow_fade_alpha16.png'), scalar16(exported/'shadow_fade_support16.png'), scalar16(exported/'shadow_fade_protection16.png') != 0, settings)
    np.testing.assert_array_equal(replay, selected)
    assert export_project(project, revision=revision, draft=True, variants=('black','transparent','editable'))['directory'] == str(exported)
print('saved-only replay and export exact')
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", program, str(project), str(exported), result["revision"]],
        env=dict(os.environ, PYTHONPATH=str(Path("src").resolve())),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "saved-only replay and export exact" in completed.stdout
    (exported / "README.txt").write_text("different output")
    with pytest.raises(ProjectError, match="collision"):
        export_project(
            project,
            revision=result["revision"],
            draft=True,
            variants=("black", "transparent", "editable"),
        )


def test_viewer_does_not_report_completion_with_pre_action_state(tmp_path):
    from blackmask.viewer import ReviewServer

    project, _, parent = fixture_project(tmp_path)
    server = ReviewServer(project)
    server.action = {"running": True, "error": None, "result": None}
    original = operations.operation_status

    def finish_between_reads(*args, **kwargs):
        old = original(*args, **kwargs)
        result = operations.apply_operation(project, fade_request(project))
        server.action.update(running=False, result=result)
        return old

    try:
        with patch.object(operations, "operation_status", finish_between_reads):
            state = server.snapshot()
        assert state["action"]["running"] or state["working_revision"] != parent["revision"]
    finally:
        server.server_close()


def test_viewer_fade_endpoint_compare_security_and_warm_metadata(tmp_path):
    import io
    import time

    from test_exposure import exposure_request
    from test_viewer import http, running

    from blackmask import shadow_fade
    from blackmask.export import render_black

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, exposure_request(project, ev=2))
    before = (project / "state.json").read_bytes()
    with running(project) as server:
        state = server.snapshot()
        operation = fade_request(project, preserve=0)
        operation.pop("schema_version")
        operation.pop("kind")
        operation.update(action="effects", authoring_digest=state["authoring_digest"])
        assert (
            http(server, "/api/action", "POST", operation, Origin="https://attacker.invalid")[0]
            == 403
        )
        assert http(server, "/api/action", "POST", dict(operation, unknown=1))[0] == 400
        assert http(
            server,
            "/api/action",
            "POST",
            dict(operation, shadow_fade_protection_file="../other.png"),
        )[0] in (202, 400)
        for _ in range(200):
            if not server.snapshot()["action"]["running"]:
                break
            time.sleep(0.01)
        assert (project / "state.json").read_bytes() == before
        assert http(server, "/api/action", "POST", operation)[0] == 202
        for _ in range(200):
            current = server.snapshot()
            if not current["action"]["running"]:
                break
            time.sleep(0.01)
        assert not current["action"]["running"] and not current["action"]["error"], current[
            "action"
        ]
        revision = current["working_revision"]
        row = next(r for r in current["revisions"] if r["revision"] == revision)
        assert row["shadow_fade_area"] == operation["shadow_fade_area"]
        assert row["shadow_fade"]["enabled"]
        with patch.object(
            shadow_fade, "scalar16", side_effect=AssertionError("warm poll decoded fade masks")
        ):
            assert server.snapshot() == current
        for mode in ("shadow-fade-off", "exposure-off", "base"):
            path = f"/image/black/{revision}/0,0,6,4/{mode}"
            pixels = np.array(Image.open(saved_raster(io.BytesIO(server.image(path)))))
            rgb, alpha, _ = saved_layers(
                project,
                revision,
                current["developed_id"],
                shadow_fade_off=mode == "shadow-fade-off",
                exposure_off=mode == "exposure-off",
                effects_off=mode == "base",
            )
            np.testing.assert_array_equal(
                pixels, np.rint(render_black(rgb, alpha) / 257).astype(np.uint8)
            )
        assert (
            http(server, f"/image/black/{revision}/0,0,6,4/shadow-fade-off/exposure-off")[0] == 404
        )
        with pytest.raises(ProjectError, match="Stale"):
            server.execute(operation)


def test_fade_explicit_disable_without_saved_area_and_prepared_alpha_binding(tmp_path):
    from test_operations import request

    project, _, _ = fixture_project(tmp_path)
    disabled = operations.apply_operation(
        project, fade_request(project, enabled=False, amount=0, amount_only=True)
    )
    assert not disabled["shadow_fade"]["enabled"]
    prepared = operations.apply_operation(project, request(project))
    master = read_project(project)["developed_id"]
    directory = project / "revisions" / prepared["revision"]
    manifest = read_revision(project, prepared["revision"], master)
    del manifest["assets"]["base_alpha16.png"]
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="Incomplete Shadow fade"):
        read_revision(project, prepared["revision"], master)


def test_fade_recomputes_after_upstream_changes_and_comparisons_retain_other_effects(tmp_path):
    from test_effects import effect_request, shading_request
    from test_exposure import exposure_request

    from blackmask.effects import saved_shading
    from blackmask.export import export_project
    from blackmask.repair import scalar16

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, effect_request(project))
    operations.apply_operation(project, shading_request(project))
    operations.apply_operation(project, exposure_request(project, ev=2))
    first = operations.apply_operation(project, fade_request(project, amount=0.4, preserve=0.6))
    master = read_project(project)["developed_id"]
    for update in (exposure_request(project, ev=1, amount_only=True),):
        result = operations.apply_operation(project, update)
    result = operations.apply_operation(
        project, effect_request(project, strength=0.5, candidate_comparison=True)
    )
    assert result["shadow_fade"] == first["shadow_fade"]
    directory = project / "revisions" / result["revision"] / "effects/shadow-fade"
    support = scalar16(saved_raster(directory / "support16.png"))
    protection = scalar16(saved_raster(directory / "protection16.png")) != 0
    rgb, alpha, manifest = saved_layers(project, result["revision"], master)
    for exposure_off in (False, True):
        upstream = saved_layers(
            project, result["revision"], master, shadow_fade_off=True, exposure_off=exposure_off
        )[0]
        actual = saved_layers(project, result["revision"], master, exposure_off=exposure_off)[0]
        expected = upstream.copy()
        for y, x in zip(*np.where((support != 0) & (alpha != 0) & ~protection), strict=True):
            expected[y, x] = scalar_fade(upstream[y, x], int(support[y, x]), 0.4, 0.6)
        np.testing.assert_array_equal(actual, expected)
        assert np.any(actual != upstream)
    weight, opacity = saved_shading(project, result["revision"], alpha, manifest)
    assert weight is not None and opacity == 0.12
    exported = Path(
        export_project(
            project,
            revision=result["revision"],
            draft=True,
            variants=("black", "transparent", "editable"),
        )["directory"]
    )
    independent_black = np.rint(
        rgb.astype(float)
        * (alpha.astype(float) / 65535)[..., None]
        * (1 - 0.12 * weight.astype(float) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(exported / "black_rgb16.tif")), independent_black
    )


@pytest.mark.parametrize("different_rgb", [False, True])
def test_fade_same_alpha_rgb_lock_outside_repair_support(tmp_path, different_rgb):
    from test_exposure import rectangle
    from test_matte_operations import approve
    from test_operations import edits, request
    from test_repair_operations import repair_request, run_repair

    project, _, parent = fixture_project(tmp_path)
    faded = operations.apply_operation(project, fade_request(project, preserve=0))
    master = read_project(project)["developed_id"]
    selected = saved_layers(project, faded["revision"], master)[0]
    lock_revision = parent["revision"] if different_rgb else faded["revision"]
    name = edits(
        project,
        [
            {
                "id": "rgb",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [3, 1, 4, 2],
                "revision": lock_revision,
            },
            rectangle("repair", [1, 1, 2, 3]),
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    operation = repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 2, 3])
    before = (project / "state.json").read_bytes()
    if different_rgb:
        with pytest.raises(ProjectError, match="RGB lock differs"):
            run_repair(project, operation)
        assert (project / "state.json").read_bytes() == before
    else:
        result = run_repair(project, operation)
        np.testing.assert_array_equal(
            saved_layers(project, result["revision"], master)[0][1, 3], selected[1, 3]
        )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("request_local", [False, True])
def test_present_null_fade_record_rejected_cold_and_warm(tmp_path, enabled, request_local):
    from blackmask.project import _validation_scope

    project, _, parent = fixture_project(tmp_path)
    master = read_project(project)["developed_id"]
    # Legacy absence remains valid; present null must never take that path.
    assert "shadow_fade" not in read_revision(project, parent["revision"], master)
    result = operations.apply_operation(project, fade_request(project, enabled=enabled))
    directory = project / "revisions" / result["revision"]
    with _validation_scope() if request_local else nullcontext():
        manifest = read_revision(project, result["revision"], master)
        manifest["shadow_fade"] = None
        (directory / "manifest.json").write_bytes(_json_bytes(manifest))
        for _ in range(2):
            with pytest.raises(ProjectError, match="Shadow fade identity/schema/status"):
                read_revision(project, result["revision"], master)
