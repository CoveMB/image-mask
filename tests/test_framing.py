"""Independent geometry/pixel and saved-export contracts; synthetic fixtures only."""

import hashlib
import importlib
import json
import subprocess
import sys
import weakref
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_background import legacy_project, scalar_composite
from test_effects import fixture_project, shading_request
from test_ingest import saved_hashes, saved_raster

from blackmask import operations
from blackmask.export import export_project, saved_layers
from blackmask.project import ProjectError, read_project


def margins(left=1, right=2, top=1, bottom=0):
    return {"left_px": left, "right_px": right, "top_px": top, "bottom_px": bottom}


def test_preview_samples_literal_background_without_expanded_allocation(monkeypatch):
    from blackmask import framing

    native = np.array([[[0, 257, 65535], [514, 771, 1028]]], np.uint16)
    backdrop = np.array([[[2570, 5140, 7710], [10280, 12850, 15420]]], np.uint16)
    settings = framing.Margins(1, 2, 1, 0)
    pixels, geometry = framing.framing_preview(native, backdrop, settings)
    assert pixels.tolist() == [
        [[10, 20, 30], [10, 20, 30], [40, 50, 60], [40, 50, 60], [40, 50, 60]],
        [[10, 20, 30], [0, 1, 255], [2, 3, 4], [40, 50, 60], [40, 50, 60]],
    ]
    assert geometry == {
        "source_dimensions_wh": [2, 1],
        "output_dimensions_wh": [5, 2],
        "display_dimensions_wh": [5, 2],
        "source_rect_xyxy": [1, 1, 3, 2],
    }
    real_empty = np.empty
    allocations = []

    def bounded_empty(shape, *args, **kwargs):
        allocations.append(shape)
        assert np.prod(shape) <= 1600 * 1600 * 3
        return real_empty(shape, *args, **kwargs)

    monkeypatch.setattr(framing.np, "empty", bounded_empty)
    pixels, geometry = framing.framing_preview(native, backdrop, framing.Margins(9998, 0, 9999, 0))
    assert pixels.shape == (1600, 1600, 3)
    assert geometry["output_dimensions_wh"] == [10000, 10000]
    assert allocations
    for bound in (0, True, 1601, 1.5):
        with pytest.raises(ValueError):
            framing.framing_preview(native, backdrop, settings, max_edge=bound)


def test_reduced_preview_has_literal_pixel_centre_samples():
    from blackmask import framing

    native = (
        np.array(
            [[[1, 2, 3], [4, 5, 6], [7, 8, 9]], [[10, 11, 12], [13, 14, 15], [16, 17, 18]]],
            dtype=np.uint16,
        )
        * 257
    )
    backdrop = (
        np.array(
            [
                [[21, 22, 23], [24, 25, 26], [27, 28, 29]],
                [[31, 32, 33], [34, 35, 36], [37, 38, 39]],
            ],
            dtype=np.uint16,
        )
        * 257
    )
    pixels, geometry = framing.framing_preview(
        native, backdrop, framing.Margins(2, 1, 1, 2), max_edge=4
    )
    # The 6×5 canvas is reduced to 4×3. Display pixel centres land in canvas
    # columns 0, 2, 3, 5 and rows 0, 2, 4. The middle row samples two native
    # pixels; all other samples come from the nearest saved-backdrop edges.
    assert pixels.tolist() == [
        [[21, 22, 23], [21, 22, 23], [24, 25, 26], [27, 28, 29]],
        [[31, 32, 33], [10, 11, 12], [13, 14, 15], [37, 38, 39]],
        [[31, 32, 33], [31, 32, 33], [34, 35, 36], [37, 38, 39]],
    ]
    assert geometry == {
        "source_dimensions_wh": [3, 2],
        "output_dimensions_wh": [6, 5],
        "display_dimensions_wh": [4, 3],
        "source_rect_xyxy": [2, 1, 5, 3],
    }


def test_preset_absence_save_cas_and_native_bytes_preserved(tmp_path):
    from blackmask.framing import read_framing_preset, save_framing_preset

    project, _, _ = fixture_project(tmp_path)
    state = read_project(project)
    before = hashes(project)
    zero, expected = read_framing_preset(project, state["developed_id"], (6, 4))
    assert zero.to_dict() == margins(0, 0, 0, 0) and expected is None
    assert hashes(project) == before
    saved = save_framing_preset(
        project, margins(), expected_digest=None, expected_developed_id=state["developed_id"]
    )
    assert saved["framing"] == margins()
    assert (
        saved["framing_digest"]
        == hashlib.sha256((project / "framing.json").read_bytes()).hexdigest()
    )
    assert {
        name: value for name, value in hashes(project).items() if name != "framing.json"
    } == before
    with pytest.raises(ProjectError, match="Stale"):
        save_framing_preset(
            project, margins(9), expected_digest=None, expected_developed_id=state["developed_id"]
        )
    assert read_framing_preset(project, state["developed_id"], (6, 4))[0].to_dict() == margins()


@pytest.mark.parametrize("phase", ["temporary", "file-sync", "before", "after"])
def test_preset_write_failure_reports_actual_visibility(tmp_path, monkeypatch, phase):
    from blackmask import framing
    from blackmask import project as project_module

    project, _, _ = fixture_project(tmp_path)
    developed_id = read_project(project)["developed_id"]
    saved = framing.save_framing_preset(
        project, margins(), expected_digest=None, expected_developed_id=developed_id
    )
    old = (project / "framing.json").read_bytes()
    before = hashes(project)

    def fail(*args, **kwargs):
        raise OSError("synthetic sync failure")

    owner, name = {
        "temporary": (project_module.tempfile, "mkstemp"),
        "file-sync": (project_module.os, "fsync"),
        "before": (project_module.os, "replace"),
        "after": (project_module, "_sync_directory"),
    }[phase]
    monkeypatch.setattr(owner, name, fail)
    with pytest.raises(ProjectError) as caught:
        framing.save_framing_preset(
            project,
            margins(5),
            expected_digest=saved["framing_digest"],
            expected_developed_id=developed_id,
        )
    if phase != "after":
        assert (project / "framing.json").read_bytes() == old
        assert "unchanged" in str(caught.value)
    else:
        assert isinstance(caught.value, framing.FramingSaveUncertain)
        assert caught.value.visible["framing"] == margins(5)
        assert caught.value.visible["framing_reload_required"] is True
        assert (
            caught.value.visible["framing_digest"]
            == hashlib.sha256((project / "framing.json").read_bytes()).hexdigest()
        )
    for name, value in before.items():
        if name != "framing.json":
            assert hashes(project)[name] == value


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "boolean",
        "source",
        "dimensions",
        "margin",
        "extra",
        "broken",
        "oversized",
        "symlink",
    ],
)
def test_invalid_presets_are_preserved_and_native_state_remains_readable(tmp_path, change):
    from blackmask.framing import read_framing_preset, save_framing_preset

    project, _, _ = fixture_project(tmp_path)
    developed_id = read_project(project)["developed_id"]
    value = {
        "schema_version": 2,
        "developed_id": developed_id,
        "source_dimensions_wh": [6, 4],
        "margins": margins(),
    }
    if change == "schema":
        value["schema_version"] = 1
    if change == "boolean":
        value["schema_version"] = True
    if change == "source":
        value["developed_id"] = "foreign"
    if change == "dimensions":
        value["source_dimensions_wh"] = [6, True]
    if change == "margin":
        value["margins"] = margins(1.5)
    if change == "extra":
        value["extra"] = 0
    raw = (
        b"{broken"
        if change == "broken"
        else b" " * 16385
        if change == "oversized"
        else json.dumps(value).encode()
    )
    path = project / "framing.json"
    if change == "symlink":
        target = tmp_path / "external-preset.json"
        saved_raster(target).write_bytes(raw)
        path.symlink_to(target)
    else:
        saved_raster(path).write_bytes(raw)
    before = hashes(project)
    with pytest.raises(ProjectError):
        read_framing_preset(project, developed_id, (6, 4))
    with pytest.raises(ProjectError):
        save_framing_preset(
            project, margins(), expected_digest=None, expected_developed_id=developed_id
        )
    assert read_project(project)["developed_id"] == developed_id
    assert hashes(project) == before and saved_raster(path).read_bytes() == raw


def test_preset_real_process_lock_and_raw_digest_cas(tmp_path):
    from blackmask.framing import read_framing_preset, save_framing_preset

    project, _, _ = fixture_project(tmp_path)
    developed_id = read_project(project)["developed_id"]
    program = r"""
import json, sys
from pathlib import Path
from blackmask import framing
from blackmask.project import ProjectError
project, developed_id, mode, expected = sys.argv[1:]
if mode == 'hold':
    original = framing._atomic_json
    def held(*args, **kwargs):
        print('locked', flush=True)
        assert sys.stdin.readline().strip() == 'continue'
        return original(*args, **kwargs)
    framing._atomic_json = held
try:
    result = framing.save_framing_preset(Path(project),
        dict(left_px=2,right_px=3,top_px=4,bottom_px=5),
        expected_digest=json.loads(expected), expected_developed_id=developed_id)
except ProjectError as error:
    print(json.dumps({'error': str(error)}), flush=True)
else:
    print(json.dumps(result), flush=True)
"""
    command = [sys.executable, "-c", program, str(project), developed_id]
    first = subprocess.Popen(
        command + ["hold", "null"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert first.stdout.readline().strip() == "locked"
        second = subprocess.run(
            command + ["save", "null"], capture_output=True, text=True, timeout=10, check=False
        )
        assert second.returncode == 0 and "busy" in json.loads(second.stdout)["error"].lower()
        output, error = first.communicate("continue\n", timeout=10)
        assert first.returncode == 0, error
        assert json.loads(output)["framing"] == margins(2, 3, 4, 5)
        stale = subprocess.run(
            command + ["save", "null"], capture_output=True, text=True, timeout=10, check=False
        )
        assert stale.returncode == 0 and "Stale" in json.loads(stale.stdout)["error"]
    finally:
        if first.poll() is None:
            first.kill()
            first.communicate()
    saved, expected = read_framing_preset(project, developed_id, (6, 4))
    path = project / "framing.json"
    original = saved_raster(path).read_bytes()
    saved_raster(path).write_bytes(original + b"\n")
    with pytest.raises(ProjectError, match="Stale"):
        save_framing_preset(
            project, saved.to_dict(), expected_digest=expected, expected_developed_id=developed_id
        )
    actual = hashlib.sha256(saved_raster(path).read_bytes()).hexdigest()
    assert (
        save_framing_preset(
            project, saved.to_dict(), expected_digest=actual, expected_developed_id=developed_id
        )["framing_digest"]
        == actual
    )
    assert saved_raster(path).read_bytes() == original + b"\n"


def hashes(directory):
    return {
        str(path.relative_to(directory)): hashlib.sha256(
            saved_raster(path).read_bytes()
        ).hexdigest()
        for path in directory.rglob("*")
        if saved_raster(path).is_file()
    }


def test_literal_native_result_and_only_saved_backdrop_edges():
    from blackmask.framing import frame_result, framed_geometry, validate_margins

    native = np.array([[[1, 258, 65534], [19, 1001, 32768]]], np.uint16)
    backdrop = np.array([[[11, 12, 13], [21, 22, 23]]], np.uint16)
    settings = validate_margins(margins(), (2, 1))
    assert settings.to_dict() == margins()
    assert framed_geometry((2, 1), settings) == (5, 2, (1, 1, 3, 2))
    expected = np.array(
        [
            [[11, 12, 13], [11, 12, 13], [21, 22, 23], [21, 22, 23], [21, 22, 23]],
            [[11, 12, 13], [1, 258, 65534], [19, 1001, 32768], [21, 22, 23], [21, 22, 23]],
        ],
        np.uint16,
    )
    np.testing.assert_array_equal(frame_result(native, backdrop, settings), expected)
    black = frame_result(native, None, settings)
    np.testing.assert_array_equal(black[1, 1:3], native[0])
    assert not black[0].any() and not black[1, [0, 3, 4]].any()
    assert native[0, 0].tolist() == [1, 258, 65534]
    assert backdrop[0, 0].tolist() == [11, 12, 13]


@pytest.mark.parametrize("shape", [(1, 1), (1, 7), (5, 1), (3, 7)])
@pytest.mark.parametrize("values", [margins(0, 0, 0, 0), margins(2, 1, 3, 4)])
def test_geometry_and_straight_transparency_are_exact(shape, values):
    from blackmask.framing import frame_transparent, framed_geometry, validate_margins

    native = np.arange(np.prod(shape) * 4, dtype=np.uint8).reshape(*shape, 4)
    settings = validate_margins(values, (shape[1], shape[0]))
    width, height, (x0, y0, x1, y1) = framed_geometry((shape[1], shape[0]), settings)
    actual = frame_transparent(native, settings)
    expected = np.zeros((height, width, 4), np.uint8)
    expected[y0:y1, x0:x1] = native
    np.testing.assert_array_equal(actual, expected)
    assert not np.shares_memory(actual, native)


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [],
        dict(margins(), other=0),
        {"left_px": 0},
        *[
            margins(left=value)
            for value in (-1, True, 1.0, "1", np.int64(1), None, float("nan"), float("inf"), 2**100)
        ],
    ],
)
def test_strict_margin_inputs(value):
    from blackmask.framing import validate_margins

    with pytest.raises(ValueError):
        validate_margins(value, (3, 2))


@pytest.mark.parametrize(
    "size", [(0, 1), (-1, 2), (True, 1), (1.0, 1), (32769, 1), (10001, 10000), (1,), [1, 1]]
)
def test_source_and_output_bounds_before_expanded_allocation(size):
    from blackmask.framing import validate_margins

    with pytest.raises(ValueError):
        validate_margins(margins(0, 0, 0, 0), size)


def test_limits_and_direct_margin_instances_are_revalidated(monkeypatch):
    from blackmask import framing

    assert framing.framed_geometry((32768, 1), framing.Margins(0, 0, 0, 0))[:2] == (32768, 1)
    assert framing.framed_geometry((10000, 10000), framing.Margins(0, 0, 0, 0))[:2] == (
        10000,
        10000,
    )
    native = np.zeros((1, 1, 3), np.uint16)
    rgba = np.zeros((1, 1, 4), np.uint8)
    with patch("blackmask.framing.np.empty", side_effect=AssertionError("expanded allocation")):
        for settings in (
            framing.Margins(True, 0, 0, 0),
            framing.Margins(-1, 0, 0, 0),
            framing.Margins(32768, 0, 0, 0),
            framing.Margins(10000, 0, 10000, 0),
        ):
            with pytest.raises(ValueError):
                framing.frame_result(native, None, settings)
            with pytest.raises(ValueError):
                framing.frame_transparent(rgba, settings)


@pytest.mark.parametrize(
    "bad",
    [np.zeros((1, 2, 3), np.uint8), np.zeros((1, 2), np.uint16), np.zeros((0, 2, 3), np.uint16)],
)
def test_invalid_rasters_rejected(bad):
    from blackmask.framing import Margins, frame_result, frame_transparent

    with pytest.raises(ValueError):
        frame_result(bad, None, Margins(0, 0, 0, 0))
    with pytest.raises(ValueError):
        frame_transparent(bad, Margins(0, 0, 0, 0))
    with pytest.raises(ValueError):
        frame_result(np.zeros((1, 1, 3), np.uint16), bad, Margins(0, 0, 0, 0))


def protected_project(tmp_path):
    from test_matte_operations import StubSession, approve, run_matte
    from test_operations import edits, request

    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, trimap, device: (
            np.full(trimap.shape, 0.5),
            {"fixture": "synthetic-test-only"},
        ),
    ):
        project, source, parent = fixture_project(tmp_path)
    guides = edits(
        project,
        [
            {
                "id": "partial-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 2],
                "revision": parent["revision"],
            },
            {
                "id": "opaque-lock",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [5, 1, 6, 2],
                "revision": parent["revision"],
            },
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=guides))
    approve(project, prepared)

    def prediction(rgb, trimap, device):
        values = np.full(trimap.shape, 0.5)
        values[0, 1] = 1 / 65535
        return values, {"fixture": "synthetic-test-only"}

    with patch.object(StubSession, "predict", side_effect=prediction):
        run_matte(project)
    result = operations.apply_operation(project, shading_request(project, opacity=0.37))
    operations.accept_revision(project, result["revision"])
    return project, source, result


def test_saved_framed_exports_scalar_pixels_protection_and_compact_manifest(tmp_path):
    from blackmask.background import read_background
    from blackmask.effects import saved_shading
    from blackmask.ingest import srgb_profile

    project, _, selected = protected_project(tmp_path)
    state = read_project(project)
    foreground, alpha, manifest = saved_layers(project, selected["revision"], state["developed_id"])
    directory = project / "revisions" / selected["revision"]
    with Image.open(saved_raster(directory / "supports/protection.png")) as image:
        protection = np.array(image) != 0
    assert protection[1, 2] and alpha[1, 2] == 32768
    assert protection[1, 5] and alpha[1, 5] == 65535
    assert {0, 1, 32768, 65535} <= set(alpha.ravel())
    backdrop = read_background(project, directory, manifest)
    weight, opacity = saved_shading(project, selected["revision"], alpha, manifest)
    assert weight.any() and opacity != 0 and np.any(foreground % 257)
    native = scalar_composite(foreground, alpha, backdrop, weight, opacity)
    expected = np.empty((7, 9, 3), np.uint16)
    for y in range(7):
        for x in range(9):
            expected[y, x] = (
                native[y - 2, x - 1]
                if 2 <= y < 6 and 1 <= x < 7
                else backdrop[min(3, max(0, y - 2)), min(5, max(0, x - 1))]
            )
    before = hashes(project / "revisions"), (project / "state.json").read_bytes()
    output = export_project(project, framing=margins(1, 2, 2, 1), framed_transparent=True)
    delivery = Path(output["directory"])
    assert {path.name for path in delivery.iterdir()} == {
        "result_rgb16.tif",
        "result_RGB8_VIEW.png",
        "transparent_RGBA8_VIEW.png",
        "README.txt",
        "manifest.json",
    }
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(delivery / "result_rgb16.tif")), expected
    )
    with tifffile.TiffFile(delivery / "result_rgb16.tif") as image:
        assert image.pages[0].tags[34675].value == srgb_profile()
        assert image.pages[0].compression == 1
    with Image.open(saved_raster(delivery / "result_RGB8_VIEW.png")) as image:
        np.testing.assert_array_equal(np.array(image), np.rint(expected / 257).astype(np.uint8))
    with Image.open(saved_raster(delivery / "transparent_RGBA8_VIEW.png")) as image:
        rgba = np.array(image)
    expected_rgba = np.zeros((7, 9, 4), np.uint8)
    for y in range(4):
        for x in range(6):
            h = 1 - opacity * int(weight[y, x]) / 65535
            expected_rgba[y + 2, x + 1] = [
                *[round(int(value) * h / 257) for value in foreground[y, x]],
                round(int(alpha[y, x]) / 257),
            ]
    np.testing.assert_array_equal(rgba, expected_rgba)
    record = json.loads((delivery / "manifest.json").read_bytes())
    assert record["kind"] == "framed-presentation" and record["schema_version"] == 2
    assert record["source_dimensions_wh"] == [6, 4]
    assert record["output_dimensions_wh"] == [9, 7]
    assert record["source_rect_xyxy"] == [1, 2, 7, 6]
    assert (
        record["revision_manifest_sha256"]
        == hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()
    )
    assert record["label"] == (
        "Framed presentation of accepted revision; framing has not been separately accepted"
    )
    for name, metadata in saved_hashes(record).items():
        assert (
            metadata["sha256"]
            == hashlib.sha256((saved_raster(delivery / name)).read_bytes()).hexdigest()
        )
    assert set(saved_hashes(record)) == {path.name for path in delivery.iterdir()} - {
        "manifest.json"
    }
    assert str(tmp_path) not in (delivery / "manifest.json").read_text()
    assert "original_path" not in (delivery / "manifest.json").read_text()
    assert before == (hashes(project / "revisions"), (project / "state.json").read_bytes())
    assert export_project(project, framing=margins(1, 2, 2, 1), framed_transparent=True) == output


def test_legacy_omission_zero_margins_variants_and_manifest_raw_identity(tmp_path):
    project, selected = legacy_project(tmp_path)
    original = export_project(project)
    original_hashes = hashes(Path(original["directory"]))
    framed = export_project(project, framing=margins(0, 0, 0, 0))
    assert framed["directory"] != original["directory"]
    np.testing.assert_array_equal(
        tifffile.imread(saved_raster(Path(framed["directory"]) / "result_rgb16.tif")),
        tifffile.imread(saved_raster(Path(original["directory"]) / "black_rgb16.tif")),
    )
    assert not (saved_raster(Path(framed["directory"]) / "transparent_RGBA8_VIEW.png")).exists()
    variant = export_project(project, framing=margins(0, 0, 0, 0), framed_transparent=True)
    assert variant["directory"] != framed["directory"]
    explicit_draft = export_project(
        project, revision=selected["revision"], draft=True, framing=margins(0, 0, 0, 0)
    )
    draft_record = json.loads(saved_raster(Path(explicit_draft["manifest_file"])).read_bytes())
    assert draft_record["draft"] is True
    assert draft_record["label"] == "DRAFT - explicit framed presentation"
    assert explicit_draft["directory"] not in {framed["directory"], variant["directory"]}
    assert export_project(project) == original
    assert hashes(Path(original["directory"])) == original_hashes
    path = project / "revisions" / selected["revision"] / "manifest.json"
    path.write_text(json.dumps(json.loads(saved_raster(path).read_bytes()), indent=2) + "\n")
    changed = export_project(project, framing=margins(0, 0, 0, 0))
    assert changed["directory"] != framed["directory"]


@pytest.mark.parametrize("transparent", [False, True])
def test_identical_framed_reuse_removes_only_its_verified_duplicate(tmp_path, transparent):
    project, _, _ = fixture_project(tmp_path)
    output = export_project(project, framing=margins(), framed_transparent=transparent)
    exports = project / "exports"
    retained_stage = exports / ".export-prior-failure"
    retained_stage.mkdir()
    (retained_stage / "evidence.txt").write_text("Preserve earlier failed work")
    before = hashes(project)
    for _ in range(2):
        assert export_project(project, framing=margins(), framed_transparent=transparent) == output
        assert list(exports.glob(".export-*")) == [retained_stage]
        assert hashes(project) == before


@pytest.mark.parametrize("failure", ["mismatch", "parent-sync"])
def test_framed_reuse_failure_preserves_duplicate_and_prior_work(tmp_path, monkeypatch, failure):
    project, _, _ = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    output = Path(export_project(project, framing=margins())["directory"])
    expected_stage = hashes(output)
    exports = project / "exports"
    retained_stage = exports / ".export-prior-failure"
    retained_stage.mkdir()
    (retained_stage / "evidence.txt").write_text("Preserve earlier failed work")
    if failure == "mismatch":
        readme = output / "README.txt"
        original = saved_raster(readme).read_bytes()
        saved_raster(readme).write_bytes(bytes([original[0] ^ 1]) + original[1:])
        message = "differing existing files"
    else:
        original_sync = export._sync_directory

        def fail_parent(path):
            if path == exports:
                raise OSError("injected reused parent sync")
            original_sync(path)

        monkeypatch.setattr(export, "_sync_directory", fail_parent)
        message = "visible.*durability"
    before = hashes(project)
    with pytest.raises(ProjectError, match=message):
        export_project(project, framing=margins())
    stages = set(exports.glob(".export-*"))
    assert retained_stage in stages and len(stages) == 2
    new_stage = (stages - {retained_stage}).pop()
    assert hashes(new_stage) == expected_stage
    after = hashes(project)
    assert all(after[name] == value for name, value in before.items())


def test_framed_reuse_partial_cleanup_failure_reports_published_delivery(tmp_path, monkeypatch):
    project, _, _ = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    output = Path(export_project(project, framing=margins())["directory"])
    before = hashes(project)
    synced = []
    cleaned = []
    original_sync = export._sync_directory

    def record_sync(path):
        original_sync(path)
        synced.append(path)

    def fail_partial_cleanup(path):
        assert synced[-1] == project / "exports"
        assert path.parent == project / "exports" and path.name.startswith(".export-")
        assert hashes(path) == hashes(output)
        cleaned.append(path)
        (path / "README.txt").unlink()
        raise OSError("injected partial cleanup")

    monkeypatch.setattr(export, "_sync_directory", record_sync)
    monkeypatch.setattr("shutil.rmtree", fail_partial_cleanup)
    with pytest.raises(ProjectError, match="published.*duplicate stage cleanup failed") as failure:
        export_project(project, framing=margins())
    assert len(cleaned) == 1
    assert str(output) in str(failure.value) and str(cleaned[0]) in str(failure.value)
    assert "durability is unconfirmed" not in str(failure.value)
    assert isinstance(failure.value.__cause__, OSError)
    assert not (cleaned[0] / "README.txt").exists()
    assert (saved_raster(cleaned[0] / "result_rgb16.tif")).is_file()
    after = hashes(project)
    assert all(after[name] == value for name, value in before.items())


def test_invalid_export_request_before_staging_or_expanded_allocation(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    with patch.object(export.tempfile, "mkdtemp", side_effect=AssertionError("staging")):
        with pytest.raises(ValueError, match="framing|margins"):
            export_project(project, framed_transparent=True)
        for settings in (margins(left=True), margins(left=32768), margins(10000, 0, 10000, 0)):
            with pytest.raises(ValueError):
                export_project(project, framing=settings)


@pytest.mark.parametrize(
    "collision", ["corrupt", "missing", "extra-file", "extra-dir", "directory-member", "symlink"]
)
def test_existing_delivery_collision_preserves_all_inputs_and_outputs(tmp_path, collision):
    project, _, _ = fixture_project(tmp_path)
    output = Path(export_project(project, framing=margins())["directory"])
    path = output / "README.txt"
    if collision == "corrupt":
        path.write_text("deliberately changed synthetic delivery")
    elif collision == "missing":
        saved_raster(path).rename(output.parent / "retained-readme.txt")
    elif collision == "extra-file":
        (output / "extra.txt").write_text("preserve")
    elif collision == "extra-dir":
        (output / "extra").mkdir()
    elif collision == "directory-member":
        saved_raster(path).rename(output.parent / "retained-readme.txt")
        path.mkdir()
    else:
        (output / "extra-link").symlink_to(path)
    state = (project / "state.json").read_bytes()
    before = hashes(output)
    with pytest.raises(ProjectError, match="collision"):
        export_project(project, framing=margins())
    assert before == hashes(output) and state == (project / "state.json").read_bytes()


@pytest.mark.parametrize("failure", ["disk", "before-rename", "after-rename"])
def test_failure_phases_preserve_native_delivery_and_report_visible_publication(
    tmp_path, monkeypatch, failure
):
    project, _, _ = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    native = Path(export_project(project)["directory"])
    before = hashes(native), (project / "state.json").read_bytes()
    if failure == "disk":
        monkeypatch.setattr(
            "blackmask.project.shutil.disk_usage",
            lambda path: type("Disk", (), {"free": 10 * 1024**3})(),
        )
        with (
            patch.object(export.tempfile, "mkdtemp", side_effect=AssertionError("staging")),
            pytest.raises(ProjectError, match="space"),
        ):
            export_project(project, framing=margins())
    else:
        if failure == "before-rename":
            monkeypatch.setattr(
                export,
                "_publish_new_directory",
                lambda *args: (_ for _ in ()).throw(OSError("injected before rename")),
            )
        else:
            original = export._sync_directory

            def fail_parent(path):
                if path == project / "exports":
                    raise OSError("injected parent sync")
                original(path)

            monkeypatch.setattr(export, "_sync_directory", fail_parent)
        expected_error = OSError if failure == "before-rename" else ProjectError
        expected_message = "injected" if failure == "before-rename" else "visible.*durability"
        with pytest.raises(expected_error, match=expected_message):
            export_project(project, framing=margins())
        published = list((project / "exports").glob("*-framed-*"))
        assert bool(published) == (failure == "after-rename")
        assert published or list((project / "exports").glob(".export-*"))
        if published:
            assert (published[0] / "manifest.json").is_file()
            monkeypatch.undo()
            assert Path(export_project(project, framing=margins())["directory"]) == published[0]
    assert before == (hashes(native), (project / "state.json").read_bytes())


@pytest.mark.parametrize("changed", ["state", "manifest"])
def test_captured_bytes_must_correspond_to_canonical_validated_objects(
    tmp_path, monkeypatch, changed
):
    project, _, selected = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    if changed == "state":
        path = project / "state.json"
        original = export.read_project
        name = "read_project"
    else:
        path = project / "revisions" / selected["revision"] / "manifest.json"
        original = export.saved_layers
        name = "saved_layers"
    captured = saved_raster(path).read_bytes()
    alternate = json.loads(captured)
    if changed == "state":
        alternate.update(accepted_revision=None, status="review_needed")
    else:
        alternate["synthetic_race_marker"] = "validated different bytes"
    called = False

    def canonical_read_between_changes(*args, **kwargs):
        nonlocal called
        if called:
            return original(*args, **kwargs)
        called = True
        path.write_text(json.dumps(alternate))
        try:
            result = original(*args, **kwargs)
        finally:
            saved_raster(path).write_bytes(captured)
        return result

    monkeypatch.setattr(export, name, canonical_read_between_changes)
    with (
        patch.object(export.tempfile, "mkdtemp", side_effect=AssertionError("staging")),
        pytest.raises(ProjectError, match="Stale"),
    ):
        export_project(project, framing=margins())
    assert called and saved_raster(path).read_bytes() == captured


@pytest.mark.parametrize("changed", ["state", "manifest", "source", "asset"])
def test_changes_during_render_fail_before_publication(tmp_path, monkeypatch, changed):
    project, _, selected = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    native = Path(export_project(project)["directory"])
    retained = hashes(native)
    original = export._write_framed_rgb8
    revision = project / "revisions" / selected["revision"]
    target = {
        "state": project / "state.json",
        "manifest": revision / "manifest.json",
        "source": project / "source.json",
        "asset": revision / "base_alpha16.png",
    }[changed]

    def change_after_render(*args):
        result = original(*args)
        if changed == "asset":
            saved_raster(target).write_bytes(b"deliberately corrupt synthetic saved alpha")
        else:
            value = json.loads(saved_raster(target).read_bytes())
            if changed == "state":
                value.update(accepted_revision=None, status="review_needed")
            elif changed == "source":
                value["original_path"] = "changed synthetic source identity"
            else:
                value["synthetic_race_marker"] = "changed during render"
            target.write_text(json.dumps(value))
        return result

    monkeypatch.setattr(export, "_write_framed_rgb8", change_after_render)
    with pytest.raises(ProjectError, match="Stale|hash"):
        export_project(project, framing=margins())
    assert not list((project / "exports").glob("*-framed-*"))
    assert retained == hashes(native)
    assert list((project / "exports").glob(".export-*"))


def test_stale_enabled_appearance_cannot_export_base_fallback(tmp_path):
    from test_operations import request

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, shading_request(project))
    stale = operations.apply_operation(project, request(project))
    # A new prepared trimap invalidates appearance; obtaining another complete
    # matte does not silently rebuild its dependent shading.
    from test_matte_operations import StubSession, approve, run_matte

    from blackmask.effects import effects_stale
    from blackmask.project import read_revision

    approve(project, stale)
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, trimap, device: (
            np.full(trimap.shape, 0.75),
            {"fixture": "synthetic-test-only"},
        ),
    ):
        complete = run_matte(project)
    assert effects_stale(read_revision(project, complete["revision"], complete["developed_id"]))
    with pytest.raises(ProjectError, match="Stale|stale"):
        export_project(project, revision=complete["revision"], draft=True, framing=margins())


def test_compact_manifest_records_identities_without_copying_private_metadata(tmp_path):
    project, _, selected = protected_project(tmp_path)
    path = project / "revisions" / selected["revision"] / "manifest.json"
    value = json.loads(saved_raster(path).read_bytes())
    value["model_configuration"] = {"private": "/private/synthetic/model-cache"}
    value["shading"]["private_note"] = "/private/synthetic/capture"
    path.write_text(json.dumps(value))
    output = export_project(project, framing=margins())
    record_bytes = saved_raster(Path(output["manifest_file"])).read_bytes()
    assert b"/private/" not in record_bytes and b"model_configuration" not in record_bytes
    record = json.loads(record_bytes)
    assert record["effects"]["shading"] == {
        "enabled": True,
        "record_sha256": hashlib.sha256(
            (
                json.dumps(value["shading"], sort_keys=True, separators=(",", ":"), allow_nan=False)
                + "\n"
            ).encode()
        ).hexdigest(),
    }


def test_saved_cleanup_exposure_fade_and_shading_are_composed_once(tmp_path):
    from test_effects import effect_request
    from test_exposure import exposure_request
    from test_shadow_fade import fade_request

    from blackmask.background import read_background
    from blackmask.effects import saved_shading

    project, source, _ = fixture_project(tmp_path)
    for make_request in (
        effect_request,
        lambda project: exposure_request(project, ev=1),
        lambda project: fade_request(project, amount=0.4),
        lambda project: shading_request(project, opacity=0.3),
    ):
        selected = operations.apply_operation(project, make_request(project))
    foreground, alpha, manifest = saved_layers(
        project, selected["revision"], selected["developed_id"]
    )
    assert np.any(foreground != source) and np.any(foreground % 257)
    backdrop = read_background(project, project / "revisions" / selected["revision"], manifest)
    weight, opacity = saved_shading(project, selected["revision"], alpha, manifest)
    assert weight.any() and opacity == 0.3
    expected = scalar_composite(foreground, alpha, backdrop, weight, opacity)
    output = export_project(
        project, revision=selected["revision"], draft=True, framing=margins(2, 1, 1, 3)
    )
    actual = tifffile.imread(saved_raster(Path(output["directory"]) / "result_rgb16.tif"))
    np.testing.assert_array_equal(actual[1:5, 2:8], expected)
    record = json.loads(saved_raster(Path(output["manifest_file"])).read_bytes())
    assert all(
        record["effects"][name]["enabled"] is True
        for name in ("color_cleanup", "shading", "local_exposure", "shadow_fade")
    )


def test_symlinked_delivery_is_rejected_without_following_or_replacing_it(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    output = Path(export_project(project, framing=margins())["directory"])
    retained = output.parent / "retained-synthetic-delivery"
    saved_raster(output).rename(retained)
    before = hashes(retained), (project / "state.json").read_bytes()
    output.symlink_to(retained, target_is_directory=True)
    with pytest.raises(ProjectError, match="symlink|alias|collision"):
        export_project(project, framing=margins())
    assert output.is_symlink()
    assert before == (hashes(retained), (project / "state.json").read_bytes())


@pytest.mark.parametrize("damaged", ["rgb16", "rgb8"])
def test_written_raster_must_roundtrip_before_publication(tmp_path, monkeypatch, damaged):
    project, _, _ = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    native = Path(export_project(project)["directory"])
    before = hashes(native), (project / "state.json").read_bytes()
    if damaged == "rgb16":
        original = export.write_developed

        def write_changed_tiff(path, pixels):
            changed = pixels.copy()
            changed[0, 0, 0] ^= 1
            original(path, changed)

        monkeypatch.setattr(export, "write_developed", write_changed_tiff)
    else:
        original_png = export._write_framed_rgb8

        def write_changed_png(path, pixels):
            expected = original_png(path, pixels)
            with Image.open(saved_raster(path)) as image:
                changed = np.array(image)
                profile = image.info["icc_profile"]
            changed[0, 0, 0] ^= 1
            with Image.fromarray(changed) as image:
                image.save(path, icc_profile=profile)
            return expected

        monkeypatch.setattr(export, "_write_framed_rgb8", write_changed_png)
    with pytest.raises(ProjectError, match="round trip"):
        export_project(project, framing=margins())
    assert not list((project / "exports").glob("*-framed-*"))
    assert before == (hashes(native), (project / "state.json").read_bytes())


def test_transparent_export_releases_render_buffer_before_readback(tmp_path, monkeypatch):
    from blackmask import framing

    project, _, _ = fixture_project(tmp_path)
    export = importlib.import_module("blackmask.export")
    original_frame = framing.frame_transparent
    original_verify = export._verify_framed_png
    buffers = []
    expected_pixels = []
    readbacks = []

    def track_render(*args):
        pixels = original_frame(*args)
        buffers.append(weakref.ref(pixels))
        expected_pixels.append(pixels.tobytes())
        return pixels

    def verify_after_release(path, mode, size, expected):
        if mode == "RGBA":
            assert len(buffers) == 1
            assert buffers[0]() is None, "expanded RGBA render still alive at readback"
            readbacks.append(path)
        original_verify(path, mode, size, expected)

    monkeypatch.setattr(framing, "frame_transparent", track_render)
    monkeypatch.setattr(export, "_verify_framed_png", verify_after_release)
    output = export_project(project, framing=margins(), framed_transparent=True)
    assert len(readbacks) == 1
    with Image.open(
        saved_raster(Path(output["directory"]) / "transparent_RGBA8_VIEW.png")
    ) as image:
        assert image.tobytes() == expected_pixels[0]


def test_transparent_save_failure_releases_image_and_preserves_prior_work(tmp_path, monkeypatch):
    from blackmask import framing

    project, _, _ = fixture_project(tmp_path)
    native = Path(export_project(project)["directory"])
    before = hashes(native), (project / "state.json").read_bytes()
    original_frame = framing.frame_transparent
    original_save = Image.Image.save
    buffers = []
    images = []

    def track_render(*args):
        pixels = original_frame(*args)
        buffers.append(weakref.ref(pixels))
        return pixels

    def fail_transparent_save(image, path, **kwargs):
        if Path(path).name == "transparent_RGBA8_VIEW.png":
            assert image.mode == "RGBA" and image.getpixel((0, 0)) == (0, 0, 0, 0)
            images.append(image)
            raise OSError("injected transparent PNG save failure")
        original_save(image, path, **kwargs)

    monkeypatch.setattr(framing, "frame_transparent", track_render)
    monkeypatch.setattr(Image.Image, "save", fail_transparent_save)
    with pytest.raises(OSError, match="injected transparent PNG save failure"):
        export_project(project, framing=margins(), framed_transparent=True)
    assert len(images) == len(buffers) == 1
    with pytest.raises(ValueError, match="closed image"):
        images[0].getpixel((0, 0))
    assert buffers[0]() is None
    assert before == (hashes(native), (project / "state.json").read_bytes())
    assert not list((project / "exports").glob("*-framed-*"))
    assert list((project / "exports").glob(".export-*"))
    monkeypatch.undo()
    output = export_project(project, framing=margins(), framed_transparent=True)
    assert (saved_raster(Path(output["directory"]) / "transparent_RGBA8_VIEW.png")).is_file()
    assert before == (hashes(native), (project / "state.json").read_bytes())
