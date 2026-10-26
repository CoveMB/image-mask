"""Independent numerical expectations and reversible native sharpening contracts."""

import json
import math
from contextlib import nullcontext
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_ingest import bind_raster, saved_hashes, saved_raster

from blackmask import operations
from blackmask.project import ProjectError, _json_bytes, digest, read_project, read_revision


def sharpening_settings(amount=0.7, radius=1.0, threshold=0.001, enabled=True):
    return {"enabled": enabled, "amount": amount, "radius_px": radius, "noise_threshold": threshold}


def reference_sharpening(rgb, alpha, support, protection, settings):
    """Full-frame direct convolution, independent of production filters/transfers."""
    encoded = rgb.astype(float) / 65535
    linear = np.empty_like(encoded)
    low = encoded <= 0.04045
    linear[low] = encoded[low] / 12.92
    linear[~low] = ((encoded[~low] + 0.055) / 1.055) ** 2.4
    luminance = sum(linear[:, :, c] * w for c, w in enumerate((0.2126, 0.7152, 0.0722)))
    radius = math.ceil(4 * settings["radius_px"])
    weights = np.array(
        [math.exp(-0.5 * (i / settings["radius_px"]) ** 2) for i in range(-radius, radius + 1)]
    )
    weights /= weights.sum()

    def convolve(value):
        for axis in (0, 1):
            padding = [(radius, radius) if i == axis else (0, 0) for i in range(2)]
            windows = np.lib.stride_tricks.sliding_window_view(
                np.pad(value, padding, mode="symmetric"), len(weights), axis=axis
            )
            value = np.sum(windows * weights, axis=-1)
        return value

    denominator = convolve(alpha.astype(float) / 65535)
    numerator = convolve(luminance * alpha / 65535)
    result = rgb.copy()
    if not settings["enabled"]:
        return result
    height, width = alpha.shape
    for y in range(height):
        for x in range(width):
            original = luminance[y, x]
            if not alpha[y, x] or not support[y, x] or protection[y, x] or original == 0:
                continue
            if denominator[y, x] == 0:
                continue
            detail = original - numerator[y, x] / denominator[y, x]
            adjustment = math.copysign(max(abs(detail) - settings["noise_threshold"], 0), detail)
            adjustment *= settings["amount"] * int(support[y, x]) / 65535
            values = luminance[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2]
            valid = alpha[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2] != 0
            target = min(max(original + adjustment, values[valid].min()), values[valid].max())
            gain = min(target / original, 1 / linear[y, x].max())
            if gain == 1:
                continue
            pixel = linear[y, x] * gain
            result[y, x] = [
                round(65535 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))
                for v in pixel
            ]
    return result


@pytest.mark.parametrize("radius", [0.5, 1, 4, 8])
@pytest.mark.parametrize("threshold", [0, 0.001, 0.02])
def test_independent_alpha_weighted_reference_and_exact_exclusions(radius, threshold):
    from blackmask.sharpening import apply_local_sharpening

    rng = np.random.default_rng(931)
    rgb = rng.integers(0, 65536, (9, 13, 3), dtype=np.uint16)
    rgb[0, :4] = [[0, 0, 0], [1, 200, 3000], [65535, 1000, 33000], [20000] * 3]
    alpha = rng.choice(np.array([0, 1, 32768, 65535], np.uint16), (9, 13))
    support = rng.choice(np.array([0, 17321, 65535], np.uint16), (9, 13))
    protection = rng.random((9, 13)) < 0.2
    protection[3, 3] = True
    alpha[3, 3] = 32768
    support[3, 3] = 65535
    before = [a.copy() for a in (rgb, alpha, support, protection)]
    settings = sharpening_settings(radius=radius, threshold=threshold)
    result = apply_local_sharpening(rgb, alpha, support, protection, settings)
    np.testing.assert_array_equal(result, reference_sharpening(*before, settings))
    excluded = (alpha == 0) | (support == 0) | protection
    np.testing.assert_array_equal(result[excluded], rgb[excluded])
    assert np.any(result != rgb)
    for value, original in zip((rgb, alpha, support, protection), before, strict=True):
        np.testing.assert_array_equal(value, original)


@pytest.mark.parametrize("identity", ["off", "zero", "alpha", "support", "protect", "constant"])
def test_exact_identity(identity):
    from blackmask.sharpening import apply_local_sharpening

    rgb = np.random.default_rng(5).integers(0, 65536, (5, 7, 3), dtype=np.uint16)
    alpha = np.full((5, 7), 32768, np.uint16)
    support = np.full_like(alpha, 65535)
    protect = np.zeros(alpha.shape, bool)
    settings = sharpening_settings(threshold=0)
    if identity == "off":
        settings["enabled"] = False
    if identity == "zero":
        settings["amount"] = 0
    if identity == "alpha":
        alpha[:] = 0
    if identity == "support":
        support[:] = 0
    if identity == "protect":
        protect[:] = True
    if identity == "constant":
        rgb[:] = [1401, 33000, 65535]
    np.testing.assert_array_equal(
        apply_local_sharpening(rgb, alpha, support, protect, settings), rgb
    )


@pytest.mark.parametrize("radius", [0.5, 1, 4, 8])
def test_fine_broad_detail_noise_guard_and_sharp_step(radius):
    from blackmask.sharpening import apply_local_sharpening

    x = np.arange(81)
    # Captured soft lines plus broad texture, with both dark and bright detail.
    levels = 27000 + 9000 * np.exp(-(((x - 20) / 2) ** 2)) - 8000 * np.exp(-(((x - 40) / 6) ** 2))
    rgb = np.repeat(np.rint(levels)[None, :, None], 3, axis=2).astype(np.uint16)
    alpha = np.full(rgb.shape[:2], 65535, np.uint16)
    protection = np.zeros(alpha.shape, bool)
    result = apply_local_sharpening(
        rgb, alpha, alpha, protection, sharpening_settings(radius=radius, threshold=0)
    )
    assert int(result[0, 19, 0]) - int(result[0, 18, 0]) > int(rgb[0, 19, 0]) - int(rgb[0, 18, 0])
    assert result.min() >= rgb.min() and result.max() <= rgb.max()
    noise = (30000 + np.random.default_rng(8).integers(-50, 51, rgb.shape)).astype(np.uint16)
    np.testing.assert_array_equal(
        apply_local_sharpening(
            noise, alpha, alpha, protection, sharpening_settings(radius=radius, threshold=0.02)
        ),
        noise,
    )
    rgb[:, :40] = 10000
    rgb[:, 40:] = 50000
    np.testing.assert_array_equal(
        apply_local_sharpening(
            rgb, alpha, alpha, protection, sharpening_settings(radius=radius, threshold=0)
        ),
        rgb,
    )


@pytest.mark.parametrize("radius", [0.5, 8])
def test_strips_match_full_reference_with_corners_seams_and_blocks(radius):
    from blackmask.sharpening import apply_local_sharpening

    y, x = np.indices((269, 17))
    levels = 16000 + y * 83 + x * 317 + (x // 4 % 2) * 1100 + (y // 8 % 2) * 700
    rgb = np.repeat(levels[:, :, None], 3, axis=2).astype(np.uint16)
    alpha = np.where((x + y) % 13 == 0, 0, 32768).astype(np.uint16)
    support = np.full_like(alpha, 65535)
    protect = y % 59 == 0
    settings = sharpening_settings(radius=radius, threshold=0)
    result = apply_local_sharpening(rgb, alpha, support, protect, settings)
    expected = reference_sharpening(rgb, alpha, support, protect, settings)
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(result[120:135, 3:12], expected[120:135, 3:12])


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        sharpening_settings(amount=True),
        sharpening_settings(enabled=1),
        sharpening_settings(amount=-0.1),
        sharpening_settings(amount=1.01),
        sharpening_settings(radius=0.49),
        sharpening_settings(radius=8.01),
        sharpening_settings(radius=True),
        sharpening_settings(threshold=-0.01),
        sharpening_settings(threshold=0.021),
        sharpening_settings(threshold=float("nan")),
        sharpening_settings(radius=float("inf")),
        dict(sharpening_settings(), extra=1),
    ],
)
def test_invalid_settings(settings):
    from blackmask.sharpening import validate_local_sharpening

    with pytest.raises(ProjectError):
        validate_local_sharpening(settings)


def test_invalid_registration():
    from blackmask.sharpening import apply_local_sharpening

    rgb = np.zeros((2, 3, 3), np.uint16)
    alpha = np.ones((2, 3), np.uint16)
    protect = np.zeros(alpha.shape, bool)
    for operands in (
        (rgb.astype(float), alpha, alpha, protect),
        (rgb, alpha[:1], alpha, protect),
        (rgb, alpha, alpha.astype(float), protect),
        (rgb, alpha, alpha, alpha),
    ):
        with pytest.raises(ProjectError):
            apply_local_sharpening(*operands, sharpening_settings())


def sharpening_project(tmp_path):
    from test_ingest import srgb_profile, tiff
    from test_matte_operations import approve, run_matte
    from test_operations import edits, request

    from blackmask import operations
    from blackmask.project import accept_development, create_project, read_project

    levels = np.array([10000, 22000, 28000, 32000, 37000, 50000], np.uint16)
    source = np.repeat(levels[None, :, None], 4, axis=0)
    source = np.concatenate([source, source // 2, source // 3], axis=2)
    project = tmp_path / "project"
    create_project(tiff(tmp_path / "source.tif", source, profile=srgb_profile()), project, {})
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
    parent = run_matte(project)
    operations.accept_revision(project, parent["revision"])
    return project, source, parent


def sharpening_request(
    project,
    *,
    amount=0.7,
    radius=1,
    threshold=0.001,
    enabled=True,
    amount_only=False,
    area=None,
    **extra,
):
    from test_exposure import rectangle
    from test_operations import request

    fields = {
        "local_sharpening": sharpening_settings(amount, radius, threshold, enabled),
        "scope_xyxy": [0, 0, 6, 4],
        "candidate_comparison": True,
    }
    if amount_only:
        fields["sharpening_amount_only"] = True
    elif enabled:
        fields["sharpening_area"] = (
            area
            if area is not None
            else {
                "regions": [rectangle("detail", [1, 0, 6, 4])],
                "protection": [rectangle("protected", [2, 1, 3, 2])],
            }
        )
    fields.update(extra)
    return request(project, kind="effects", **fields)


def test_saved_sharpening_replacement_amount_reset_reuse_and_pending_recipe(tmp_path):
    import tomllib

    import tomli_w
    from test_exposure import rectangle
    from test_ingest import saved_raster

    from blackmask import operations
    from blackmask.export import saved_layers
    from blackmask.project import read_project
    from blackmask.repair import scalar16

    project, _, parent = sharpening_project(tmp_path)
    master = read_project(project)["developed_id"]
    base, alpha, _ = saved_layers(project, parent["revision"], master)
    recipe_path = project / "recipe.toml"
    recipe = tomllib.loads(recipe_path.read_text())
    recipe["local_exposure"] = {"enabled": True, "ev": 1.5}
    recipe_path.write_text(tomli_w.dumps(recipe))
    first = operations.apply_operation(project, sharpening_request(project))
    assert tomllib.loads(recipe_path.read_text())["local_exposure"] == recipe["local_exposure"]
    directory = project / "revisions" / first["revision"] / "effects/sharpening"
    support = scalar16(saved_raster(directory / "support16.png"))
    protect = scalar16(saved_raster(directory / "protection16.png")) != 0
    rgb = saved_layers(project, first["revision"], master)[0]
    assert np.any(rgb != base)
    np.testing.assert_array_equal(
        rgb, reference_sharpening(base, alpha, support, protect, sharpening_settings())
    )
    repeated = operations.apply_operation(project, sharpening_request(project))
    assert repeated["reused"] and repeated["revision"] == first["revision"]
    for amount in (0.2, 1, 0):
        result = operations.apply_operation(
            project, sharpening_request(project, amount=amount, amount_only=True)
        )
        rgb, actual_alpha, _ = saved_layers(project, result["revision"], master)
        np.testing.assert_array_equal(
            rgb, reference_sharpening(base, alpha, support, protect, sharpening_settings(amount))
        )
        np.testing.assert_array_equal(actual_alpha, alpha)
        np.testing.assert_array_equal(
            saved_layers(project, result["revision"], master, sharpening_off=True)[0], base
        )
    area = {"regions": [rectangle("new", [4, 0, 5, 4])], "protection": []}
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(
            project, sharpening_request(project, area=area, scope_xyxy=[4, 0, 5, 4])
        )
    result = operations.apply_operation(project, sharpening_request(project, area=area))
    rgb = saved_layers(project, result["revision"], master)[0]
    np.testing.assert_array_equal(rgb[:, :4], base[:, :4])
    assert np.any(rgb[:, 4] != base[:, 4])
    disabled = operations.apply_operation(project, sharpening_request(project, enabled=False))
    np.testing.assert_array_equal(saved_layers(project, disabled["revision"], master)[0], base)
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_absent_optional_recipe_and_saved_layers_are_not_rewritten(tmp_path):
    import tomllib

    import tomli_w

    from blackmask.export import saved_layers
    from blackmask.project import read_project
    from blackmask.recipe import Recipe

    project, _, parent = sharpening_project(tmp_path)
    path = project / "recipe.toml"
    value = tomllib.loads(path.read_text())
    value.pop("local_sharpening", None)
    path.write_text(tomli_w.dumps(value))
    before = path.read_bytes()
    master = read_project(project)["developed_id"]
    parsed = Recipe.from_dict(value, master)
    assert parsed.local_sharpening == sharpening_settings(0, 1, 0.001, False)
    rgb = saved_layers(project, parent["revision"], master)[0]
    np.testing.assert_array_equal(
        saved_layers(project, parent["revision"], master, sharpening_off=True)[0], rgb
    )
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "fields",
    [
        {"sharpening_amount_only": True},
        {"sharpening_amount_only": 1},
        {"sharpening_area": {"regions": [], "protection": []}},
        {"sharpening_protection_file": "missing.png"},
        {"local_exposure": {"enabled": False, "ev": 0}},
        {"color_cleanup": {"enabled": False, "strength": 0}},
        {"shading": {"enabled": False, "opacity": 0}},
        {"unsupported": True},
    ],
)
def test_invalid_sharpening_requests_preserve_state(tmp_path, fields):

    from blackmask.operations import apply_operation

    project, _, _ = sharpening_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        apply_operation(project, sharpening_request(project, **fields))
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 1),
        ("enabled", 1),
        ("developed_id", "foreign"),
        ("algorithm", "unknown"),
        ("stale", True),
        ("unsupported", True),
        ("settings", sharpening_settings(True)),
    ],
)
def test_saved_disabled_sharpening_semantics_reject_rehashed_corruption(tmp_path, field, value):
    project, _, _ = sharpening_project(tmp_path)
    result = operations.apply_operation(project, sharpening_request(project, enabled=False))
    master = read_project(project)["developed_id"]
    read_revision(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    record = manifest["local_sharpening"]
    record[field] = value
    settings = directory / "effects/sharpening/settings.json"
    saved_raster(settings).write_bytes(_json_bytes(record))
    manifest["files"]["effects/sharpening/settings.json"] = digest(
        saved_raster(settings).read_bytes()
    )
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError):
        read_revision(project, result["revision"], master)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize(
    "field,alias",
    [
        ("settings.enabled", None),
        ("enabled", None),
        ("stale", 0),
        ("candidate_comparison", 1),
        ("schema_version", 2.0),
        ("settings.amount", True),
        ("settings.amount", False),
        ("settings.radius_px", True),
        ("settings.noise_threshold", False),
        ("scope_xyxy", [False, 0, 6, 4]),
    ],
)
def test_saved_sharpening_file_only_type_alias_rejected_without_export_changes(
    tmp_path, enabled, warm, field, alias
):
    from test_framing import hashes

    from blackmask.export import export_project
    from blackmask.project import _validate_local_sharpening_semantics, _validation_scope

    project, _, parent = sharpening_project(tmp_path)
    result = operations.apply_operation(
        project,
        sharpening_request(
            project,
            enabled=enabled,
            amount=int(alias) if field == "settings.amount" else 1,
            radius=1,
            threshold=0,
        ),
    )
    state = read_project(project)
    assert state["accepted_revision"] == parent["revision"]
    assert state["working_revision"] == result["revision"]
    export_project(project, revision=result["revision"], draft=True, variants=("editable",))
    before_state = (project / "state.json").read_bytes()
    exports = project / "exports"
    before_files = hashes(exports)
    before_namespace = sorted(str(path.relative_to(exports)) for path in exports.rglob("*"))
    assert before_files and before_namespace
    directory = project / "revisions" / result["revision"]
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    valid_record = _json_bytes(manifest["local_sharpening"])
    settings_path = saved_raster(directory / "effects/sharpening/settings.json")
    actual = json.loads(settings_path.read_bytes())
    container = actual["settings"] if field.startswith("settings.") else actual
    name = field.split(".")[-1]
    replacement = int(enabled) if alias is None else alias
    assert container[name] == replacement  # The original Python-equality defect.
    container[name] = replacement
    if not warm:
        _validate_local_sharpening_semantics.cache_clear()
    with _validation_scope() if warm else nullcontext():
        if warm:
            read_revision(project, result["revision"], state["developed_id"])
        settings_path.write_bytes(_json_bytes(actual))
        manifest["files"]["effects/sharpening/settings.json"] = digest(settings_path.read_bytes())
        manifest_path.write_bytes(_json_bytes(manifest))
        assert _json_bytes(manifest["local_sharpening"]) == valid_record
        assert _json_bytes(actual) != valid_record
        with pytest.raises(ProjectError, match="saved Local sharpening settings"):
            read_revision(project, result["revision"], state["developed_id"])
        with pytest.raises(ProjectError, match="saved Local sharpening settings"):
            export_project(project, revision=result["revision"], draft=True, variants=("editable",))
    assert (project / "state.json").read_bytes() == before_state
    assert hashes(exports) == before_files
    assert sorted(str(path.relative_to(exports)) for path in exports.rglob("*")) == before_namespace


@pytest.mark.parametrize("enabled", [False, True])
def test_saved_sharpening_settings_formatting_is_semantically_unchanged(tmp_path, enabled):
    from pathlib import Path

    from blackmask.export import export_project

    project, _, _ = sharpening_project(tmp_path)
    result = operations.apply_operation(project, sharpening_request(project, enabled=enabled))
    state = read_project(project)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    settings_path = saved_raster(directory / "effects/sharpening/settings.json")
    record = json.loads(settings_path.read_bytes())
    settings_path.write_text(json.dumps(dict(reversed(list(record.items()))), indent=2))
    manifest["files"]["effects/sharpening/settings.json"] = digest(settings_path.read_bytes())
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    assert (
        read_revision(project, result["revision"], state["developed_id"])["local_sharpening"]
        == record
    )
    exported = export_project(
        project, revision=result["revision"], draft=True, variants=("editable",)
    )
    assert (
        json.loads((Path(exported["directory"]) / "sharpening_settings.json").read_bytes())
        == record
    )
    assert read_project(project) == state


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_saved_sharpening_nonfinite_actual_settings_raise_project_error(tmp_path, value):
    project, _, _ = sharpening_project(tmp_path)
    result = operations.apply_operation(project, sharpening_request(project))
    state = read_project(project)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    settings_path = saved_raster(directory / "effects/sharpening/settings.json")
    record = json.loads(settings_path.read_bytes())
    record["settings"]["amount"] = value
    settings_path.write_text(json.dumps(record))
    manifest["files"]["effects/sharpening/settings.json"] = digest(settings_path.read_bytes())
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    with pytest.raises(ProjectError, match="saved Local sharpening settings"):
        read_revision(project, result["revision"], state["developed_id"])


@pytest.mark.parametrize(
    "asset",
    [
        "base_alpha16.png",
        "effects/sharpening/support16.png",
        "effects/sharpening/protection16.png",
        "effects/sharpening/alpha16.png",
        "effects/sharpening/settings.json",
        "effects/sharpening/area.json",
    ],
)
@pytest.mark.parametrize("request_local", [False, True])
def test_warm_sharpening_validation_rehashes_assets(tmp_path, asset, request_local):
    from blackmask.project import _validation_scope

    project, _, _ = sharpening_project(tmp_path)
    result = operations.apply_operation(project, sharpening_request(project))
    master = read_project(project)["developed_id"]
    with _validation_scope() if request_local else nullcontext():
        read_revision(project, result["revision"], master)
        path = project / "revisions" / result["revision"] / asset
        saved_raster(path).write_bytes(saved_raster(path).read_bytes() + b" ")
        with pytest.raises(ProjectError, match="hash mismatch"):
            read_revision(project, result["revision"], master)


@pytest.mark.parametrize("change_alpha", [False, True])
@pytest.mark.parametrize("repairing", [False, True])
def test_sharpening_prepare_matte_repair_partial_rgb_locks_and_stale(
    tmp_path, change_alpha, repairing
):
    from unittest.mock import patch

    from test_exposure import exposure_request, rectangle
    from test_matte_operations import StubSession, approve, run_matte
    from test_operations import edits, request
    from test_repair_operations import repair_request, run_repair

    from blackmask import operations
    from blackmask.export import export_project, saved_layers
    from blackmask.project import read_project

    project, _, _ = sharpening_project(tmp_path)
    operations.apply_operation(project, exposure_request(project, ev=2))
    first = operations.apply_operation(project, sharpening_request(project))
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
    assert manifest["local_sharpening"]["stale"] is change_alpha
    np.testing.assert_array_equal(rgb[1, 3], before_rgb[1, 3])
    assert alpha[1, 3] == before_alpha[1, 3]
    if change_alpha:
        with pytest.raises(ProjectError, match="Stale"):
            export_project(project, revision=result["revision"], draft=True)
        with pytest.raises(ProjectError, match="Stale"):
            operations.accept_revision(project, result["revision"])
        with pytest.raises(ProjectError, match="Stale"):
            operations.apply_operation(project, sharpening_request(project, amount_only=True))
        disabled = operations.apply_operation(
            project, sharpening_request(project, enabled=False, amount=0)
        )
        assert disabled["local_exposure"]["stale"]
        assert not disabled["local_sharpening"]["stale"]
    else:
        # A new selected-RGB lock changes the filter's neighbourhood input.
        # Replay the reviewed formula; whole-frame pointwise-effect identity
        # does not apply to a nonlocal kernel after its input changes.
        from blackmask.repair import scalar16

        directory = project / "revisions" / result["revision"]
        base = saved_layers(
            project,
            result["revision"],
            master,
            sharpening_off=True,
            exposure_off=True,
            shadow_fade_off=True,
        )[0]
        support = scalar16(saved_raster(directory / "effects/sharpening/support16.png"))
        protection = scalar16(saved_raster(directory / "effects/sharpening/protection16.png")) != 0
        expected = reference_sharpening(base, alpha, support, protection, sharpening_settings())
        exposure_support = scalar16(saved_raster(directory / "effects/exposure/support16.png"))
        exposure_protection = (
            scalar16(saved_raster(directory / "effects/exposure/protection16.png")) != 0
        )
        for y, x in zip(
            *np.where((alpha != 0) & (exposure_support != 0) & ~exposure_protection), strict=True
        ):
            gain = 2 ** (2 * int(exposure_support[y, x]) / 65535)
            values = [
                v / 65535 / 12.92 if v / 65535 <= 0.04045 else ((v / 65535 + 0.055) / 1.055) ** 2.4
                for v in expected[y, x]
            ]
            values = [min(1, value * gain) for value in values]
            expected[y, x] = [
                round(65535 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))
                for v in values
            ]
        np.testing.assert_array_equal(rgb, expected)


def test_sharpening_recomputes_cleanup_then_exposure_and_fade(tmp_path):
    from test_effects import effect_request
    from test_exposure import exposure_request
    from test_ingest import saved_raster
    from test_shadow_fade import fade_request

    from blackmask.export import saved_layers
    from blackmask.repair import scalar16

    project, _, parent = sharpening_project(tmp_path)
    master = read_project(project)["developed_id"]
    operations.apply_operation(project, sharpening_request(project))
    for strength in (0.2, 0.7):
        cleaned = operations.apply_operation(
            project, effect_request(project, strength=strength, candidate_comparison=True)
        )
        base, alpha, _ = saved_layers(project, cleaned["revision"], master, sharpening_off=True)
        folder = project / "revisions" / cleaned["revision"] / "effects/sharpening"
        support = scalar16(saved_raster(folder / "support16.png"))
        protection = scalar16(saved_raster(folder / "protection16.png")) != 0
        expected = reference_sharpening(base, alpha, support, protection, sharpening_settings())
        np.testing.assert_array_equal(
            saved_layers(project, cleaned["revision"], master)[0], expected
        )
    operations.apply_operation(project, exposure_request(project, ev=0.4))
    faded = operations.apply_operation(project, fade_request(project, amount=0.2, preserve=0))
    off = saved_layers(project, faded["revision"], master, sharpening_off=True)[0]
    selected = saved_layers(project, faded["revision"], master)[0]
    assert np.any(off != selected)
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_sharpening_native_review_and_managed_gallery(tmp_path):
    from pathlib import Path

    from test_ingest import srgb_profile, tiff
    from test_library import configuration
    from test_operations import edits, request
    from test_previews import generate, jpeg, marker

    from blackmask import library, previews
    from blackmask.background import read_background
    from blackmask.export import saved_layers
    from blackmask.review import review_project

    config_path, destination = configuration(tmp_path)
    config = library.load_storage_config(config_path)
    library.ensure_library(config)
    pixels = np.broadcast_to(
        np.array([10000, 22000, 28000, 32000, 37000, 50000], np.uint16)[None, :, None],
        (4, 6, 3),
    ).copy()
    source = tiff(destination / "Inbox/CAMERA.tif", pixels, profile=srgb_profile())
    project = library.import_photo(config, source, subject="detail", development={})
    name = edits(
        project,
        [
            {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 4]},
            {"id": "fg", "role": "foreground", "shape": "rectangle", "xyxy": [5, 0, 6, 4]},
        ],
    )
    operations.apply_operation(
        project, request(project, guide_edits_file=name), storage_config=config
    )
    parent = generate(project, config)
    operations.accept_revision(project, parent["revision"], storage_config=config)
    result = operations.apply_operation(project, sharpening_request(project), storage_config=config)
    state = read_project(project)
    selected, alpha, manifest = saved_layers(project, result["revision"], state["developed_id"])
    assert np.any(selected != pixels)
    background = read_background(project, project / "revisions" / result["revision"], manifest)
    weight = (alpha.astype(np.float64) / 65535)[..., None]
    expected = np.rint(selected * weight + background * (1 - weight)).astype(np.uint16)
    np.testing.assert_array_equal(previews._render_latest(project, state), expected)
    assert marker(jpeg(config, project))["revision"] == result["revision"]
    assert state["accepted_revision"] == parent["revision"]
    reviewed = review_project(project, crops=[[1, 0, 5, 4]], storage_config=config)
    record = json.loads(Path(reviewed["manifest_file"]).read_bytes())
    assert record["effects"]["local_sharpening"] == manifest["local_sharpening"]
    assert record["settings"]["local_sharpening"] == sharpening_settings()
    assert read_project(project)["accepted_revision"] == parent["revision"]


def scalar_sharpening_request(project):
    Image.fromarray(np.full((4, 6), 65535, np.uint16)).save(project / "area.png")
    Image.fromarray(np.zeros((4, 6), np.uint8)).save(project / "protect.png")
    operation = sharpening_request(project)
    operation.pop("sharpening_area")
    operation.update(support_file="area.png", sharpening_protection_file="protect.png")
    return operation


def test_sharpening_reuse_avoids_filtering_and_cache_inspection_validates_operands(
    tmp_path, monkeypatch
):
    from blackmask import sharpening

    project, _, _ = sharpening_project(tmp_path)
    result = operations.apply_operation(project, scalar_sharpening_request(project))

    def forbidden(*args, **kwargs):
        raise AssertionError("equivalent request must reuse validated result")

    monkeypatch.setattr(sharpening, "gaussian_filter", forbidden)
    repeated = operations.apply_operation(project, scalar_sharpening_request(project))
    assert repeated["reused"] and repeated["revision"] == result["revision"]
    assert operations.inspect_processing_cache(project)["blockers"] == []
    (project / "revisions" / result["revision"] / "effects/sharpening/area.json").write_text("{}")
    assert operations.inspect_processing_cache(project)["blockers"]


@pytest.mark.parametrize("enabled", [False, True])
def test_warm_sharpening_rejects_unbound_area_and_rehashed_geometry(tmp_path, enabled):
    from blackmask.project import _validation_scope
    from blackmask.repair import scalar16

    project, _, _ = sharpening_project(tmp_path)
    result = operations.apply_operation(project, scalar_sharpening_request(project))
    if not enabled:
        result = operations.apply_operation(project, sharpening_request(project, enabled=False))
    master = read_project(project)["developed_id"]
    directory = project / "revisions" / result["revision"]
    with _validation_scope():
        read_revision(project, result["revision"], master)
        (directory / "effects/sharpening/area.json").write_text("{}")
        with pytest.raises(ProjectError, match="Unbound"):
            read_revision(project, result["revision"], master)
    # A distinct authored revision tests semantic cache renewal after all hashes change.
    other = tmp_path / "other"
    other.mkdir()
    project, _, _ = sharpening_project(other)
    result = operations.apply_operation(project, sharpening_request(project))
    master = read_project(project)["developed_id"]
    read_revision(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    name = "effects/sharpening/support16.png"
    support = scalar16(saved_raster(directory / name))
    support[0, 1] = 0
    Image.fromarray(support).save(directory / name)
    bind_raster(project, directory, manifest, name)
    manifest["local_sharpening"]["support_sha256"] = saved_hashes(manifest)[name]
    settings = directory / "effects/sharpening/settings.json"
    saved_raster(settings).write_bytes(_json_bytes(manifest["local_sharpening"]))
    manifest["files"]["effects/sharpening/settings.json"] = digest(
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
def test_sharpening_input_snapshot_races_preserve_pointers(tmp_path, filename, at_pointer):
    from blackmask import effects, review

    project, _, parent = sharpening_project(tmp_path)
    operation = scalar_sharpening_request(project)
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


def test_sharpening_low_disk_busy_writer_and_pointer_failure_recovery(tmp_path):
    import subprocess
    import sys

    from blackmask import effects

    project, _, parent = sharpening_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with (
        patch.object(effects, "check_space", side_effect=ProjectError("Low disk")),
        pytest.raises(ProjectError, match="Low disk"),
    ):
        operations.apply_operation(project, sharpening_request(project))
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
            operations.apply_operation(project, sharpening_request(project))
    finally:
        process.communicate("done\n", timeout=10)
    assert process.returncode == 0
    with (
        patch.object(effects, "_atomic_json", side_effect=OSError("interrupted pointer")),
        pytest.raises(OSError, match="interrupted"),
    ):
        operations.apply_operation(project, sharpening_request(project))
    assert (project / "state.json").read_bytes() == before
    master = read_project(project)["developed_id"]
    orphan = read_revision(project, "rev-003", master)
    assert orphan["local_sharpening"]["enabled"]
    operations.restore_revision(project, "rev-003", replace_drafts=True)
    assert read_project(project)["working_revision"] == "rev-003"
    assert read_project(project)["accepted_revision"] == parent["revision"]
