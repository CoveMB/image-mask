"""Independent reduction geometry and protected native fade arithmetic."""

import copy
import json
from unittest.mock import patch

import numpy as np
import pytest

from blackmask.project import ProjectError
from blackmask.spatial_fade import SpatialFadeOperands, spatial_fade_amount


def rectangle(identity="region", amount=1.0, *, box=None, feather=0):
    return {
        "shape": {
            "id": identity,
            "role": "support",
            "shape": "rectangle",
            "xyxy": box or [0, 0, 8, 8],
            "feather_px": feather,
        },
        "amount": amount,
    }


def area(*regions):
    return {"schema_version": 1, "regions": list(regions)}


def spatial_operands(reduction, *, enabled=True, preserve=0.0):
    return SpatialFadeOperands(
        np.full((1, 5), 39321, np.uint16),
        np.array([[False, False, False, True, True]]),
        {"enabled": enabled, "stale": False, "settings": {"preserve_highlights": preserve}},
        reduction,
    )


def test_spatial_reduction_applies_once_without_alpha_attenuation_or_lost_protection():
    alpha = np.array([[65535, 1, 32768, 65535, 32768]], np.uint16)
    reduction = np.array([[0, 65535, 32768, 65535, 32768]], np.uint16)
    foreground = np.full((1, 5, 3), 30000, np.uint16)
    operands = spatial_operands(reduction)
    before = foreground.copy(), alpha.copy(), operands.weight16.copy()
    partial = 0.6 * (1 - 32768 / 65535)
    actual = spatial_fade_amount(foreground, alpha, operands)
    np.testing.assert_allclose(actual, [[0.6, 0, partial, 0, 0]], atol=1e-14, rtol=0)
    sensitive = operands.protection & (alpha > 0) & (alpha < 65535)
    sensitive &= (operands.weight16 > 0) & (reduction < 65535)
    assert sensitive.any()
    control = SpatialFadeOperands(
        operands.weight16, np.zeros((1, 5), bool), operands.record, reduction
    )
    assert spatial_fade_amount(foreground, alpha, control)[0, 4] == partial
    for saved, current in zip(before, (foreground, alpha, operands.weight16), strict=True):
        np.testing.assert_array_equal(saved, current)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("bad", [np.zeros((1, 5), float), np.zeros((1, 4), np.uint16)])
def test_invalid_reduction_rejects_even_with_effect_disabled(enabled, bad):
    with pytest.raises(ProjectError, match="reduction"):
        spatial_fade_amount(
            np.full((1, 5, 3), 30000, np.uint16),
            np.full((1, 5), 32768, np.uint16),
            spatial_operands(bad, enabled=enabled),
        )


def test_zero_reduction_keeps_legacy_arithmetic_with_highlights():
    foreground = np.arange(15, dtype=np.uint16).reshape(1, 5, 3) * 4000
    alpha = np.array([[65535, 1, 32768, 65535, 32768]], np.uint16)
    legacy = spatial_operands(None, preserve=0.73)
    zero = spatial_operands(np.zeros((1, 5), np.uint16), preserve=0.73)
    np.testing.assert_array_equal(
        spatial_fade_amount(foreground, alpha, legacy), spatial_fade_amount(foreground, alpha, zero)
    )


def test_partial_reduction_multiplies_independent_highlight_preservation_once():
    foreground = np.full((1, 5, 3), 50000, np.uint16)
    alpha = np.full((1, 5), 32768, np.uint16)
    reduction = np.full((1, 5), 32768, np.uint16)
    linear = ((50000 / 65535 + 0.055) / 1.055) ** 2.4
    transition = (linear - 0.1) / 0.65
    highlight = transition * transition * (3 - 2 * transition)
    expected = 0.6 * (1 - 0.73 * highlight) * (1 - 32768 / 65535)
    result = spatial_fade_amount(foreground, alpha, spatial_operands(reduction, preserve=0.73))
    np.testing.assert_allclose(result, [[expected, expected, expected, 0, 0]], atol=1e-15)


def test_reduction_geometry_maximum_order_duplicates_and_empty():
    from blackmask.fade_reduction import rasterize_fade_reduction

    regions = [rectangle("low", 0.25), rectangle("high", 0.75)]
    for ordered in (regions, regions[::-1], [*regions, rectangle("duplicate", 0.75)]):
        np.testing.assert_array_equal(
            rasterize_fade_reduction(area(*ordered), "master", 8, 8),
            np.full((8, 8), 49151, np.uint16),
        )
    np.testing.assert_array_equal(
        rasterize_fade_reduction(area(), "master", 8, 8), np.zeros((8, 8), np.uint16)
    )


def test_inward_feather_quantizes_support_before_single_reduction_quantization():
    from blackmask.fade_reduction import rasterize_fade_reduction

    result = rasterize_fade_reduction(area(rectangle(amount=0.5, feather=4)), "master", 8, 8)
    np.testing.assert_array_equal(result[3], [8192, 16384, 24576, 32768, 32768, 24576, 16384, 8192])
    narrow = rectangle(box=[3, 0, 4, 8], feather=4)
    result = rasterize_fade_reduction(area(narrow), "master", 8, 8)
    assert result.max() == 16384
    assert not result[:, :3].any() and not result[:, 4:].any()


@pytest.mark.parametrize("amount", [True, -0.1, 1.01, float("nan"), float("inf"), "0.5"])
def test_reduction_rejects_invalid_amount_before_allocation(amount):
    from blackmask.fade_reduction import rasterize_fade_reduction

    with (
        patch("numpy.zeros", side_effect=AssertionError("allocated before validation")),
        pytest.raises((ProjectError, ValueError), match="reduction"),
    ):
        rasterize_fade_reduction(area(rectangle(amount=amount)), "master", 8, 8)


@pytest.mark.parametrize("kind", ["duplicate", "extra", "point", "outside", "regions", "points"])
def test_reduction_rejects_invalid_geometry_and_total_limits_before_allocation(kind):
    from blackmask.fade_reduction import rasterize_fade_reduction

    document = area(rectangle())
    if kind == "duplicate":
        document["regions"].append(copy.deepcopy(document["regions"][0]))
    elif kind == "extra":
        document["extra"] = 1
    elif kind == "point":
        document["regions"][0]["shape"] = {
            "id": "point",
            "role": "support",
            "shape": "point",
            "xy": [1, 1],
            "feather_px": 0,
        }
    elif kind == "outside":
        document["regions"][0]["shape"]["xyxy"] = [0, 0, 9, 8]
    elif kind == "regions":
        document = area(*(rectangle(f"r{i}") for i in range(129)))
    else:
        document = area(
            *(
                {
                    "shape": {
                        "id": f"stroke{i}",
                        "role": "support",
                        "shape": "stroke",
                        "points": [[1, 1]] * count,
                        "radius_px": 1,
                        "feather_px": 0,
                    },
                    "amount": 1,
                }
                for i, count in enumerate((4096, 4097))
            )
        )
    with (
        patch("numpy.zeros", side_effect=AssertionError("allocated before validation")),
        pytest.raises((ProjectError, ValueError)),
    ):
        rasterize_fade_reduction(document, "master", 8, 8)


def reduction_request(project, document=None, **changes):
    from test_operations import request

    return request(
        project,
        kind="effects",
        scope_xyxy=changes.pop("scope_xyxy", [0, 0, 6, 4]),
        candidate_comparison=True,
        fade_reduction={
            "target": "spatial_fade",
            "area": document
            if document is not None
            else area(rectangle(amount=0.5, box=[0, 0, 6, 4])),
        },
        **changes,
    )


def saved_reduction(project, revision):
    from blackmask.assets import revision_asset
    from blackmask.project import read_project, read_revision
    from blackmask.repair import scalar16
    from blackmask.spatial_fade import read_spatial_fade

    manifest = read_revision(project, revision, read_project(project)["developed_id"])
    directory = project / "revisions" / revision
    alpha = scalar16(revision_asset(project, directory, manifest, "base_alpha16.png"))
    return manifest, read_spatial_fade(project, directory, manifest, alpha)


def test_reduction_saved_lifecycle_preserves_native_inputs_and_reuses_only_same_edit(tmp_path):
    from test_effects import fixture_project
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask import operations
    from blackmask.assets import revision_hashes
    from blackmask.project import read_project

    project, _, accepted = fixture_project(tmp_path)
    legacy = operations.apply_operation(project, spatial_request(project))
    before, old = saved_reduction(project, legacy["revision"])
    assert old.record["schema_version"] == 1 and old.reduction16 is None
    first = operations.apply_operation(project, reduction_request(project))
    manifest, saved = saved_reduction(project, first["revision"])
    assert saved.record["schema_version"] == 2
    np.testing.assert_array_equal(saved.reduction16, np.full((4, 6), 32768, np.uint16))
    for name, checksum in revision_hashes(before).items():
        if name in {"base_alpha16.png", "foreground_rgb16.tif", "guides.json"} or name.startswith(
            "supports/"
        ):
            assert revision_hashes(manifest)[name] == checksum
    np.testing.assert_array_equal(saved.weight16, old.weight16)
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    again = operations.apply_operation(project, reduction_request(project))
    assert again["reused"] and again["revision"] == first["revision"]
    changed_area = area(rectangle(amount=0.75, box=[0, 0, 6, 4]))
    changed = operations.apply_operation(project, reduction_request(project, changed_area))
    assert not changed["reused"] and changed["revision"] != first["revision"]
    settings = spatial_settings(6, 4)
    settings["enabled"] = False
    disabled = operations.apply_operation(
        project, spatial_request(project, settings, candidate=True)
    )
    _, saved_off = saved_reduction(project, disabled["revision"])
    assert saved_off.record["schema_version"] == 2 and not saved_off.record["enabled"]
    assert (
        saved_off.record["reduction_sha256"]
        == saved_reduction(project, changed["revision"])[1].record["reduction_sha256"]
    )
    from pathlib import Path

    from blackmask.export import export_project

    delivered = Path(
        export_project(project, revision=disabled["revision"], draft=True, variants=("editable",))[
            "directory"
        ]
    )
    assert json.loads((delivered / "spatial_fade_reduction.json").read_bytes()) == changed_area
    assert (delivered / "spatial_fade_reduction16.png").is_file()
    cleared = operations.apply_operation(project, reduction_request(project, area()))
    _, empty = saved_reduction(project, cleared["revision"])
    assert empty.record["schema_version"] == 2 and not empty.record["enabled"]
    assert not empty.reduction16.any()
    assert saved_reduction(project, legacy["revision"])[0] == before


def test_reduction_requires_existing_effect_and_union_scope_without_publication(tmp_path):
    from test_effects import fixture_project
    from test_spatial_fade import spatial_request

    from blackmask import operations
    from blackmask.project import read_project

    project, _, _ = fixture_project(tmp_path)
    before = read_project(project)
    with pytest.raises(ProjectError, match="saved.*spatial|saved.*fade"):
        operations.apply_operation(project, reduction_request(project))
    assert read_project(project) == before
    operations.apply_operation(project, spatial_request(project))
    operations.apply_operation(project, reduction_request(project))
    before = read_project(project)
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(
            project, reduction_request(project, area(), scope_xyxy=[1, 0, 6, 4])
        )
    assert read_project(project) == before


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("tamper", ["geometry", "missing", "extra", "future", "raster"])
def test_reduction_saved_validation_rejects_tampering_after_warm_read(tmp_path, enabled, tamper):
    from PIL import Image
    from test_effects import fixture_project
    from test_ingest import bind_raster
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask import operations
    from blackmask.project import _json_bytes, digest, read_revision

    project, _, _ = fixture_project(tmp_path)
    settings = dict(spatial_settings(6, 4), enabled=enabled)
    operations.apply_operation(project, spatial_request(project, settings))
    result = operations.apply_operation(project, reduction_request(project))
    manifest, _ = saved_reduction(project, result["revision"])
    directory = project / "revisions" / result["revision"]
    folder = directory / "effects/spatial-fade"
    if tamper == "extra":
        (folder / "unexpected.json").write_text("{}")
    elif tamper == "missing":
        (folder / "reduction.json").unlink()
    else:
        if tamper == "geometry":
            document = area(rectangle(amount=0.75, box=[0, 0, 6, 4]))
            (folder / "reduction.json").write_bytes(_json_bytes(document))
            manifest["spatial_fade"]["reduction_area_sha256"] = digest(
                (folder / "reduction.json").read_bytes()
            )
            bind_raster(project, directory, manifest, "effects/spatial-fade/reduction.json")
        elif tamper == "raster":
            Image.fromarray(np.zeros((4, 6), np.uint16)).save(folder / "reduction16.png")
            manifest["spatial_fade"]["reduction_sha256"] = digest(
                (folder / "reduction16.png").read_bytes()
            )
            bind_raster(project, directory, manifest, "effects/spatial-fade/reduction16.png")
        else:
            manifest["spatial_fade"]["schema_version"] = 99
        (folder / "settings.json").write_bytes(_json_bytes(manifest["spatial_fade"]))
        bind_raster(project, directory, manifest, "effects/spatial-fade/settings.json")
        (directory / "manifest.json").write_bytes(_json_bytes(manifest))
    for _ in range(2):
        with pytest.raises(ProjectError):
            read_revision(project, result["revision"], result["developed_id"])


def test_reduction_limits_accept_boundary_and_bound_total_points():
    from blackmask.fade_reduction import rasterize_fade_reduction

    shapes = [rectangle(f"r{i}", amount=0.25, box=[0, 0, 2, 2]) for i in range(127)]
    shapes.append(
        {
            "amount": 0.75,
            "shape": {
                "id": "stroke",
                "shape": "stroke",
                "role": "support",
                "points": [[0, 0]] * 8192,
                "radius_px": 1,
                "feather_px": 0,
            },
        }
    )
    np.testing.assert_array_equal(
        rasterize_fade_reduction(area(*shapes), "master", 2, 2), [[49151, 49151], [49151, 16384]]
    )


@pytest.mark.parametrize("failure", ["space", "publication"])
def test_reduction_failed_save_preserves_existing_revision_and_accepted_bytes(tmp_path, failure):
    from test_cache_management import inventory
    from test_effects import fixture_project
    from test_spatial_fade import spatial_request

    from blackmask import operations

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, spatial_request(project))
    before = inventory(project)
    target = (
        "blackmask.effects.check_space"
        if failure == "space"
        else "blackmask.export._publish_new_directory"
    )
    with (
        patch(target, side_effect=OSError("synthetic bounded failure")),
        pytest.raises(OSError, match="synthetic"),
    ):
        operations.apply_operation(project, reduction_request(project))
    after = inventory(project)
    assert all(after[name] == value for name, value in before.items())
    if failure == "publication":
        assert list((project / "revisions").glob(".effects-*"))


def test_full_reduction_generated_overview_matches_preserved_unfaded_input(tmp_path):
    from test_effects import fixture_project
    from test_spatial_fade import spatial_request

    from blackmask import operations

    project, _, parent = fixture_project(tmp_path)
    before = (project / "revisions" / parent["revision"] / "preview.jpg").read_bytes()
    operations.apply_operation(project, spatial_request(project))
    result = operations.apply_operation(
        project, reduction_request(project, area(rectangle(amount=1, box=[0, 0, 6, 4])))
    )
    # No labels enter the image: identical panel pixels must encode identically.
    assert (project / "revisions" / result["revision"] / "preview.jpg").read_bytes() == before
