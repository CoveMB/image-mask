"""Independent native backdrop and composition contracts using synthetic pixels."""

import json
import math
import tomllib

import numpy as np
import pytest
import tomli_w


@pytest.mark.parametrize(
    "shape,display,settings",
    [
        ((11, 17), (7, 5), {"color_srgb": "#315579", "variation": 0.55}),
        ((1, 17), (7, 1), {"color_srgb": "#315579", "variation": 0}),
        ((17, 1), (1, 7), {"color_srgb": "#000000", "variation": 0.55}),
    ],
)
def test_sampled_background_matches_full_grid_without_full_output_allocation(
    monkeypatch, shape, display, settings
):
    from blackmask.background import make_background, sample_background

    full = make_background(shape, settings)
    x = (2 * np.arange(display[0]) + 1) * shape[1] // (2 * display[0])
    y = (2 * np.arange(display[1]) + 1) * shape[0] // (2 * display[1])
    original = np.empty

    def bounded_empty(size, *args, **kwargs):
        assert size != (*shape, 3)
        return original(size, *args, **kwargs)

    monkeypatch.setattr(np, "empty", bounded_empty)
    np.testing.assert_array_equal(sample_background(shape, settings, display), full[np.ix_(y, x)])


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        {"color_srgb": "#123456", "variation": True},
        {"color_srgb": "#12345g", "variation": 0},
        {"color_srgb": "123456", "variation": 0},
        {"color_srgb": "#123456", "variation": -0.1},
        {"color_srgb": "#123456", "variation": 1.1},
        {"color_srgb": "#123456", "variation": float("nan")},
        {"color_srgb": "#123456", "variation": float("inf")},
        {"color_srgb": "#123456", "variation": 0, "enabled": True},
    ],
)
def test_invalid_background_settings(settings):
    from blackmask.background import validate_background

    with pytest.raises(ValueError):
        validate_background(settings)


def test_background_uniform_black_and_singleton():
    from blackmask.background import make_background

    for shape in [(1, 1), (1, 7), (5, 1), (3, 7)]:
        uniform = make_background(shape, {"color_srgb": "#120708", "variation": 0})
        np.testing.assert_array_equal(uniform, np.broadcast_to([4626, 1799, 2056], (*shape, 3)))
        assert uniform.dtype == np.uint16
        for strength in [0, 0.55, 1]:
            assert not make_background(
                shape, {"color_srgb": "#000000", "variation": strength}
            ).any()
    np.testing.assert_array_equal(
        make_background((1, 1), {"color_srgb": "#120708", "variation": 1}), [[[4626, 1799, 2056]]]
    )


def scalar_background(height, width, color, variation):
    values = []
    for j in range(height):
        for i in range(width):
            x, y = i / (width - 1) if width > 1 else 0, j / (height - 1) if height > 1 else 0
            values.append(
                0.48 * math.cos(2 * math.pi * (0.58 * x - 0.72 * y) + 1.2)
                + 0.30 * math.sin(2 * math.pi * (1.12 * x + 0.33 * y) - 0.7)
                + 0.22 * math.cos(2 * math.pi * (0.24 * x + 1.23 * y) + 0.5)
            )
    mean = math.fsum(values) / len(values)
    maximum = max(abs(v - mean) for v in values)
    result = []
    for value in values:
        gain = 2 ** (variation * ((value - mean) / maximum if maximum else 0))
        pixel = []
        for channel in color:
            c = channel / 255
            linear = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            linear = min(1, linear * gain)
            encoded = 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
            pixel.append(round(encoded * 65535))
        result.append(pixel)
    return np.array(result, dtype=np.uint16).reshape(height, width, 3)


@pytest.mark.parametrize("shape", [(3, 7), (1, 7), (5, 1), (1, 1)])
def test_background_independent_native_scalar_oracle(shape):
    from blackmask.background import make_background

    settings = {"color_srgb": "#ac3708", "variation": 0.55}
    actual = make_background(shape, settings)
    np.testing.assert_array_equal(actual, scalar_background(*shape, [172, 55, 8], 0.55))
    np.testing.assert_array_equal(actual, make_background(shape, settings))
    assert settings == {"color_srgb": "#ac3708", "variation": 0.55}


def test_composite_single_round_alpha_and_foreground_only_shading():
    from blackmask.export import render_background, render_black

    foreground = np.array([[[65535] * 3, [65535] * 3, [5, 7, 9], [12345] * 3]], dtype=np.uint16)
    alpha = np.array([[32768, 0, 65535, 65535]], dtype=np.uint16)
    backdrop = np.full(foreground.shape, 10000, dtype=np.uint16)
    weight = np.full(alpha.shape, 65535, dtype=np.uint16)
    originals = [x.copy() for x in (foreground, alpha, backdrop, weight)]
    assert render_background(foreground, alpha, backdrop)[0, 0, 0] == 37768
    assert render_background(foreground, alpha, backdrop, weight, 0.25)[0, 0, 0] == 29576
    result = render_background(foreground, alpha, backdrop, weight, 0.5)
    np.testing.assert_array_equal(result[0, 1], [10000] * 3)
    np.testing.assert_array_equal(result[0, 2], [2, 4, 4])
    np.testing.assert_array_equal(
        result[alpha == 65535], render_black(foreground, alpha, weight, 0.5)[alpha == 65535]
    )
    for value, original in zip((foreground, alpha, backdrop, weight), originals, strict=True):
        np.testing.assert_array_equal(value, original)
    rng = np.random.default_rng(17)
    foreground = rng.integers(0, 65536, (5, 9, 3), dtype=np.uint16)
    alpha = rng.integers(0, 65536, (5, 9), dtype=np.uint16)
    weight = rng.integers(0, 65536, (5, 9), dtype=np.uint16)
    np.testing.assert_array_equal(
        render_background(foreground, alpha, np.zeros_like(foreground), weight, 0.73),
        render_black(foreground, alpha, weight, 0.73),
    )


def background_request(project, color="#120708", variation=0.55, **extra):
    from test_operations import request

    return request(
        project,
        kind="effects",
        scope_xyxy=[0, 0, 6, 4],
        background={"color_srgb": color, "variation": variation},
        candidate_comparison=True,
        **extra,
    )


def legacy_project(tmp_path):
    from test_ingest import srgb_profile, tiff
    from test_matte_operations import approve, run_matte
    from test_operations import edits, request

    from blackmask import operations
    from blackmask.project import accept_development, create_project, read_project

    project = tmp_path / "project"
    create_project(
        tiff(
            tmp_path / "source.tif",
            np.full((4, 6, 3), 30000, dtype=np.uint16),
            profile=srgb_profile(),
        ),
        project,
        {},
    )
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe.pop("background", None)
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))
    accept_development(project, read_project(project)["master_id"])
    name = edits(
        project,
        [
            {"id": "empty", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 4]},
            {"id": "solid", "role": "foreground", "shape": "rectangle", "xyxy": [5, 0, 6, 4]},
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, prepared)
    result = run_matte(project)
    operations.accept_revision(project, result["revision"])
    return project, result


def test_new_defaults_native_prepare_and_exact_inheritance(tmp_path):
    from test_effects import effect_request, fixture_project

    from blackmask import operations
    from blackmask.background import read_background
    from blackmask.project import read_project, read_revision

    project, _, parent = fixture_project(tmp_path)
    state = read_project(project)
    assert tomllib.loads((project / "recipe.toml").read_text())["background"] == {
        "color_srgb": "#120708",
        "variation": 0.55,
    }
    manifest = read_revision(project, parent["revision"], state["master_id"])
    assert manifest["background"]["settings"] == {"color_srgb": "#120708", "variation": 0.55}
    original = read_background(project / "revisions" / parent["revision"], manifest)
    result = operations.apply_operation(project, effect_request(project))
    inherited = read_revision(project, result["revision"], state["master_id"])
    assert inherited["background"] == manifest["background"]
    np.testing.assert_array_equal(
        read_background(project / "revisions" / result["revision"], inherited), original
    )


def test_legacy_absence_roundtrip_opt_in_restore_and_unapplied_draft(tmp_path):
    from test_effects import effect_request

    from blackmask import operations
    from blackmask.project import ProjectError, read_project, read_revision
    from blackmask.recipe import Recipe

    project, parent = legacy_project(tmp_path)
    before = (project / "recipe.toml").read_bytes()
    recipe = tomllib.loads(before.decode())
    master = read_project(project)["master_id"]
    assert "background" not in Recipe.from_dict(recipe, master).to_dict()
    result = operations.apply_operation(project, effect_request(project))
    assert "background" not in read_revision(project, result["revision"], master)
    assert (project / "recipe.toml").read_bytes() == before
    accepted = read_project(project)["accepted_revision"]
    applied = operations.apply_operation(project, background_request(project, "#ab3708", 0))
    assert applied["background"]["settings"] == {"color_srgb": "#AB3708", "variation": 0}
    assert read_project(project)["accepted_revision"] == accepted
    operations.restore_revision(project, parent["revision"])
    assert "background" not in tomllib.loads((project / "recipe.toml").read_text())
    operations.restore_revision(project, applied["revision"])
    assert (
        tomllib.loads((project / "recipe.toml").read_text())["background"]
        == applied["background"]["settings"]
    )
    changed = tomllib.loads((project / "recipe.toml").read_text())
    changed["background"]["variation"] = 0.3
    (project / "recipe.toml").write_text(tomli_w.dumps(changed))
    before_state = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="[Bb]ackground"):
        operations.apply_operation(project, effect_request(project, candidate_comparison=True))
    assert (project / "state.json").read_bytes() == before_state


@pytest.mark.parametrize(
    "extra",
    [
        {"shading": {"enabled": False, "opacity": 0}},
        {"opacity_only": True},
        {"support_file": "missing"},
        {"shadow_fade_amount_only": True},
    ],
)
def test_background_exclusive_and_full_scope(tmp_path, extra):
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.project import ProjectError

    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError):
        operations.apply_operation(project, background_request(project, **extra))
    op = background_request(project)
    op["scope_xyxy"] = [1, 0, 5, 4]
    with pytest.raises(ProjectError, match="scope"):
        operations.apply_operation(project, op)
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "unbound",
        "missing",
        "hash",
        "algorithm",
        "identity",
        "settings",
        "uniform",
        "profile",
        "dtype",
        "dimensions",
        "recipe",
    ],
)
def test_background_current_and_warm_asset_validation(tmp_path, mutation):
    import tifffile
    from test_effects import fixture_project

    from blackmask import operations
    from blackmask.ingest import write_master
    from blackmask.project import (
        ProjectError,
        _validation_scope,
        digest,
        read_project,
        read_revision,
    )

    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, background_request(project, variation=0))
    directory = project / "revisions" / result["revision"]
    master = read_project(project)["master_id"]
    with _validation_scope():
        manifest = read_revision(project, result["revision"], master)
        if mutation == "unbound":
            (directory / "background/extra.json").write_text("{}")
        elif mutation == "missing":
            (directory / "background/settings.json").rename(directory / "retained-settings.json")
        elif mutation == "hash":
            (directory / "background/settings.json").write_text("{}")
        else:
            record = manifest["background"]
            if mutation == "algorithm":
                record["algorithm"] = "unknown"
            if mutation == "identity":
                record["master_id"] = "0" * 64
            if mutation == "settings":
                record["settings"]["variation"] = True
                (directory / "background/settings.json").write_text(json.dumps(record["settings"]))
            raster = directory / "background/background_rgb16.tif"
            if mutation == "uniform":
                write_master(raster, np.zeros((4, 6, 3), dtype=np.uint16))
            if mutation == "profile":
                tifffile.imwrite(raster, np.zeros((4, 6, 3), dtype=np.uint16))
            if mutation == "dimensions":
                write_master(raster, np.zeros((2, 6, 3), dtype=np.uint16))
            if mutation == "dtype":
                tifffile.imwrite(raster, np.zeros((4, 6, 3), dtype=np.uint8))
            if mutation == "recipe":
                recipe = tomllib.loads((directory / "recipe.toml").read_text())
                recipe["background"]["variation"] = 0.2
                (directory / "recipe.toml").write_text(tomli_w.dumps(recipe))
                manifest["files"]["recipe.toml"] = digest((directory / "recipe.toml").read_bytes())
            for name, key in [
                ("background/background_rgb16.tif", "background_sha256"),
                ("background/settings.json", "settings_sha256"),
            ]:
                manifest["files"][name] = digest((directory / name).read_bytes())
                record[key] = manifest["files"][name]
            (directory / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ProjectError):
            read_revision(project, result["revision"], master)


def test_background_combined_noncompounding_and_repair_staleness(tmp_path):
    from test_effects import effect_request, fixture_project, shading_request
    from test_exposure import exposure_request
    from test_operations import request
    from test_shadow_fade import fade_request

    from blackmask import operations
    from blackmask.background import read_background
    from blackmask.export import export_project, saved_layers
    from blackmask.project import ProjectError, read_project, read_revision

    project, source, _ = fixture_project(tmp_path)
    operations.apply_operation(project, effect_request(project))
    operations.apply_operation(project, shading_request(project))
    operations.apply_operation(project, exposure_request(project, ev=1))
    parent = operations.apply_operation(project, fade_request(project))
    master = read_project(project)["master_id"]
    foreground, alpha, manifest = saved_layers(project, parent["revision"], master)
    old_dir = project / "revisions" / parent["revision"]
    old_files = {
        name: (old_dir / name).read_bytes()
        for name in manifest["files"]
        if name.startswith("effects/")
        or name
        in {
            "foreground_rgb16.tif",
            "base_alpha16.png",
            "corrected_rgb16.tif",
            "shadow_weight16.png",
        }
    }
    clipping = json.loads((old_dir / "review/manifest.json").read_bytes())[
        "local_exposure_clipping"
    ]
    import io

    from PIL import Image

    from blackmask.effects import saved_shading
    from blackmask.viewer import ReviewServer

    with ReviewServer(project) as server:
        for mode in ["shadow-fade-off", "exposure-off", "base"]:
            rgb, a, m = saved_layers(
                project,
                parent["revision"],
                master,
                effects_off=mode == "base",
                exposure_off=mode == "exposure-off",
                shadow_fade_off=mode == "shadow-fade-off",
            )
            w, p = saved_shading(project, parent["revision"], a, m, effects_off=mode == "base")
            b = np.zeros_like(rgb) if mode == "base" else read_background(old_dir, m)
            expected = np.rint(scalar_composite(rgb, a, b, w, p).astype(float) / 257).astype(
                np.uint8
            )
            actual = np.array(
                Image.open(
                    io.BytesIO(server.image(f"/image/result/{parent['revision']}/0,0,6,4/{mode}"))
                )
            )
            np.testing.assert_array_equal(actual, expected)
    for color, variation in [("#120708", 0.55), ("#000000", 1), ("#120708", 0.55)]:
        result = operations.apply_operation(project, background_request(project, color, variation))
        rgb, actual_alpha, saved = saved_layers(project, result["revision"], master)
        np.testing.assert_array_equal(rgb, foreground)
        np.testing.assert_array_equal(actual_alpha, alpha)
        directory = project / "revisions" / result["revision"]
        for name, data in old_files.items():
            assert (directory / name).read_bytes() == data
        for name in ["color_cleanup", "shading", "local_exposure", "shadow_fade"]:
            assert saved[name] == manifest[name]
        assert (
            json.loads((directory / "review/manifest.json").read_bytes())["local_exposure_clipping"]
            == clipping
        )
    raster = read_background(directory, saved)
    support = np.zeros(alpha.shape, dtype=np.uint16)
    support[:, 2:4] = 65535
    from PIL import Image

    Image.fromarray(support).save(project / "support.png")
    from unittest.mock import patch

    from test_exposure import rectangle
    from test_matte_operations import StubSession, approve
    from test_operations import edits
    from test_repair_operations import repair_request, run_repair

    prepared = operations.apply_operation(
        project,
        request(project, guide_edits_file=edits(project, [rectangle("repair", [2, 0, 4, 4])])),
    )
    approve(project, prepared)
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        repaired = run_repair(
            project, repair_request(project, prepared, [0, 0, 6, 4], [2, 0, 4, 4])
        )
    repaired_manifest = read_revision(project, repaired["revision"], master)
    np.testing.assert_array_equal(
        read_background(project / "revisions" / repaired["revision"], repaired_manifest), raster
    )
    assert repaired_manifest["shadow_fade"]["stale"]
    background_only = operations.apply_operation(project, background_request(project, "#123456", 0))
    with pytest.raises(ProjectError, match="Stale"):
        export_project(project, revision=background_only["revision"], draft=True)
    with pytest.raises(ProjectError, match="[Ss]tale"):
        operations.accept_revision(project, background_only["revision"])
    from blackmask.project import load_master

    np.testing.assert_array_equal(load_master(project, master)[0], source)


def test_saved_nonuniform_background_replays_without_generation(tmp_path, monkeypatch):
    from test_effects import fixture_project

    from blackmask import background
    from blackmask.ingest import write_master
    from blackmask.project import digest, read_project, read_revision

    project, _, result = fixture_project(tmp_path)
    master = read_project(project)["master_id"]
    directory = project / "revisions" / result["revision"]
    manifest = read_revision(project, result["revision"], master)
    raster = np.arange(72, dtype=np.uint16).reshape(4, 6, 3) * 131
    write_master(directory / "background/background_rgb16.tif", raster)
    checksum = digest((directory / "background/background_rgb16.tif").read_bytes())
    manifest["files"]["background/background_rgb16.tif"] = checksum
    manifest["background"]["background_sha256"] = checksum
    (directory / "manifest.json").write_text(json.dumps(manifest))

    def forbidden(*args):
        raise AssertionError("saved background regenerated")

    monkeypatch.setattr(background, "make_background", forbidden)
    manifest = read_revision(project, result["revision"], master)
    np.testing.assert_array_equal(background.read_background(directory, manifest), raster)


def test_background_busy_low_space_and_interrupted_state_restore(tmp_path, monkeypatch):
    from test_effects import fixture_project

    from blackmask import effects, operations
    from blackmask.project import ProjectError, project_lock, read_project

    project, _, parent = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    recipe = (project / "recipe.toml").read_bytes()
    with project_lock(project), pytest.raises(ProjectError, match="[Bb]usy|writer"):
        operations.apply_operation(project, background_request(project))

    def low_space(*args):
        raise ProjectError("Insufficient space")

    with monkeypatch.context() as m:
        m.setattr(effects, "check_space", low_space)
        with pytest.raises(ProjectError, match="space"):
            operations.apply_operation(project, background_request(project))
    assert (project / "state.json").read_bytes() == before
    original = effects._atomic_json

    def interrupt(path, *args, **kwargs):
        if path.name == "state.json":
            raise OSError("synthetic pointer interruption")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(effects, "_atomic_json", interrupt)
    with pytest.raises(OSError, match="interruption"):
        operations.apply_operation(project, background_request(project, "#AB1234", 0.3))
    assert (project / "state.json").read_bytes() == before
    assert (project / "recipe.toml").read_bytes() != recipe
    orphan = max((project / "revisions").glob("rev-*"))
    assert orphan.name != read_project(project)["working_revision"]
    operations.restore_revision(project, orphan.name, replace_drafts=True)
    state = read_project(project)
    assert state["working_revision"] == orphan.name
    assert state["accepted_revision"] == parent["revision"]
    assert tomllib.loads((project / "recipe.toml").read_text())["background"] == {
        "color_srgb": "#AB1234",
        "variation": 0.3,
    }


@pytest.mark.parametrize("point", ["publication", "recipe"])
def test_background_race_preserves_newer_draft_and_accepted_pointer(tmp_path, monkeypatch, point):
    from test_effects import fixture_project

    import blackmask.export as exports
    from blackmask import effects, operations
    from blackmask.project import ProjectError

    project, _, _ = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    changed = (project / "recipe.toml").read_bytes() + b"\n# newer editable draft\n"
    if point == "publication":
        original = exports.publish_artifacts

        def publish(*args):
            original(*args)
            (project / "recipe.toml").write_bytes(changed)

        monkeypatch.setattr(exports, "publish_artifacts", publish)
    else:
        original = effects._atomic_bytes

        def atomic(path, data, **kwargs):
            (project / "recipe.toml").write_bytes(changed)
            return original(path, data, **kwargs)

        monkeypatch.setattr(effects, "_atomic_bytes", atomic)
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(project, background_request(project))
    assert (project / "recipe.toml").read_bytes() == changed
    assert (project / "state.json").read_bytes() == before


def test_unapplied_background_blocks_prepare_before_model(tmp_path, monkeypatch):
    from test_effects import fixture_project
    from test_operations import request

    from blackmask import operations
    from blackmask.project import ProjectError

    project, _, _ = fixture_project(tmp_path)
    recipe = tomllib.loads((project / "recipe.toml").read_text())
    recipe["background"]["variation"] = 0.1
    (project / "recipe.toml").write_text(tomli_w.dumps(recipe))

    def forbidden(*args):
        raise AssertionError("Model invoked for unapplied background")

    monkeypatch.setattr(operations, "select_candidates", forbidden)
    with pytest.raises(ProjectError, match="background"):
        operations.apply_operation(project, request(project))


def scalar_composite(foreground, alpha, backdrop, weight=None, opacity=0):
    result = np.empty_like(foreground)
    for y in range(alpha.shape[0]):
        for x in range(alpha.shape[1]):
            a = int(alpha[y, x]) / 65535
            h = 1 - opacity * int(weight[y, x]) / 65535 if weight is not None else 1
            for c in range(3):
                result[y, x, c] = round(
                    int(foreground[y, x, c]) * a * h + int(backdrop[y, x, c]) * (1 - a)
                )
    return result


def test_result_native_crop_review_viewer_export_and_saved_only_replay(tmp_path):
    import io
    import subprocess
    import sys

    import tifffile
    from PIL import Image
    from test_effects import fixture_project, shading_request

    from blackmask import operations
    from blackmask.background import read_background
    from blackmask.effects import saved_shading
    from blackmask.export import export_project, saved_layers
    from blackmask.project import read_project
    from blackmask.review import review_panels, review_project
    from blackmask.viewer import ReviewServer

    project, source, _ = fixture_project(tmp_path)
    operations.apply_operation(project, shading_request(project))
    result = operations.apply_operation(project, background_request(project))
    master = read_project(project)["master_id"]
    foreground, alpha, manifest = saved_layers(project, result["revision"], master)
    directory = project / "revisions" / result["revision"]
    backdrop = read_background(directory, manifest)
    weight, opacity = saved_shading(project, result["revision"], alpha, manifest)
    expected = scalar_composite(foreground, alpha, backdrop, weight, opacity)
    app = ReviewServer(project)
    for crop in [[0, 0, 6, 4], [2, 1, 6, 4], [5, 3, 6, 4], [0, 0, 1, 4]]:
        x0, y0, x1, y1 = crop
        wanted = np.rint(expected[y0:y1, x0:x1].astype(float) / 257).astype(np.uint8)
        panel = review_panels(
            source[y0:y1, x0:x1],
            foreground[y0:y1, x0:x1],
            alpha[y0:y1, x0:x1],
            weight[y0:y1, x0:x1],
            opacity,
            background16=backdrop[y0:y1, x0:x1],
        )["result"]
        np.testing.assert_array_equal(panel, wanted)
        pixels = np.array(
            Image.open(
                io.BytesIO(
                    app.image(f"/image/result/{result['revision']}/" + ",".join(map(str, crop)))
                )
            )
        )
        np.testing.assert_array_equal(pixels, wanted)
    app.server_close()
    reviewed = review_project(project, crops=[[2, 1, 6, 4]])
    assets = __import__("pathlib").Path(reviewed["manifest_file"]).parent
    np.testing.assert_array_equal(
        np.array(Image.open(assets / "crop-000-result_RGB8_VIEW.png")),
        np.rint(expected[1:4, 2:6].astype(float) / 257).astype(np.uint8),
    )
    exported = export_project(project, revision=result["revision"], draft=True)
    output = __import__("pathlib").Path(exported["directory"])
    np.testing.assert_array_equal(tifffile.imread(output / "result_rgb16.tif"), expected)
    np.testing.assert_array_equal(tifffile.imread(output / "background_rgb16.tif"), backdrop)
    np.testing.assert_array_equal(
        tifffile.imread(output / "black_rgb16.tif"),
        scalar_composite(foreground, alpha, np.zeros_like(backdrop), weight, opacity),
    )
    np.testing.assert_array_equal(tifffile.imread(output / "foreground_rgb16.tif"), foreground)
    rgba = np.array(Image.open(output / "transparent_RGBA8_VIEW.png"))
    np.testing.assert_array_equal(rgba[..., 3], np.rint(alpha.astype(float) / 257).astype(np.uint8))
    assert (
        json.loads((output / "background_settings.json").read_bytes())
        == manifest["background"]["settings"]
    )
    assert export_project(project, revision=result["revision"], draft=True) == exported
    code = """import sys, pathlib, numpy as np, tifffile
from PIL import Image
p=pathlib.Path(sys.argv[1])
f=tifffile.imread(p/'foreground_rgb16.tif').astype(np.float64)
a=np.array(Image.open(p/'alpha16.png')).astype(np.float64)/65535
w=np.array(Image.open(p/'shadow_weight16.png')).astype(np.float64)/65535
import json
h=1-json.loads((p/'shading_settings.json').read_bytes())['opacity']*w
b=tifffile.imread(p/'background_rgb16.tif').astype(np.float64)
assert np.array_equal(np.rint(f*a[...,None]*h[...,None]+b*(1-a[...,None])).astype(np.uint16),tifffile.imread(p/'result_rgb16.tif'))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    (output / "result_rgb16.tif").write_bytes(b"preserved collision")
    from blackmask.project import ProjectError

    with pytest.raises(ProjectError, match="collision"):
        export_project(project, revision=result["revision"], draft=True)
    assert (output / "result_rgb16.tif").read_bytes() == b"preserved collision"


def test_legacy_export_file_set_and_identical_reuse(tmp_path):
    from pathlib import Path

    from blackmask.export import export_project

    project, _ = legacy_project(tmp_path)
    before = (project / "recipe.toml").read_bytes()
    result = export_project(project)
    output = Path(result["directory"])
    assert {p.name for p in output.iterdir()} == {
        "black_rgb16.tif",
        "alpha16.png",
        "black_RGB8_VIEW.png",
        "transparent_RGBA8_VIEW.png",
        "foreground_rgb16.tif",
        "source_rgb16.tif",
        "recipe.toml",
        "manifest.json",
        "README.txt",
    }
    manifest = (output / "manifest.json").read_bytes()
    assert "background" not in json.loads(manifest)
    assert export_project(project) == result
    assert (output / "manifest.json").read_bytes() == manifest
    assert (project / "recipe.toml").read_bytes() == before


def test_background_viewer_endpoint_identity_security_and_warm_poll(tmp_path, monkeypatch):
    import time

    from test_effects import fixture_project
    from test_viewer import http, running

    from blackmask import background
    from blackmask.project import ProjectError

    project, _, _ = fixture_project(tmp_path)
    with running(project) as server:
        state = server.snapshot()
        assert state["revisions"][-1]["background"]["settings"] == {
            "color_srgb": "#120708",
            "variation": 0.55,
        }
        op = background_request(project, "#000000", 0.55)
        op.pop("schema_version")
        op.pop("kind")
        op.update(action="effects", authoring_digest=state["authoring_digest"])
        assert http(server, "/api/action", "POST", op, Origin="https://attacker.invalid")[0] == 403
        assert http(server, "/api/action", "POST", op, **{"X-Blackmask-Token": "wrong"})[0] == 403
        assert http(server, "/api/action", "POST", dict(op, unknown=1))[0] == 400
        assert http(server, "/api/action", "POST", op)[0] == 202
        for _ in range(200):
            current = server.snapshot()
            if not current["action"]["running"]:
                break
            time.sleep(0.01)
        assert not current["action"]["running"] and not current["action"]["error"], current[
            "action"
        ]
        assert current["working_revision"] != state["working_revision"]
        assert current["revisions"][-1]["background"]["settings"] == {
            "color_srgb": "#000000",
            "variation": 0.55,
        }

        def forbidden(*args):
            raise AssertionError("warm status generated/decoded background")

        with monkeypatch.context() as m:
            m.setattr(background, "make_background", forbidden)
            m.setattr(background, "read_background", forbidden)
            assert server.snapshot() == current
        with pytest.raises(ProjectError, match="Stale"):
            server.execute(op)
        assert (
            http(server, f"/image/result/{current['working_revision']}/0,0,6,4/base/exposure-off")[
                0
            ]
            == 404
        )
