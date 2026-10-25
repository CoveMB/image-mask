"""Configured synthetic storage journey; model stubs are not photographic acceptance."""

import hashlib
import importlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_cache_management import inventory
from test_export import DEFAULT_MEMBERS
from test_ingest import saved_raster, tiff
from test_library import command, configuration
from test_matte import cache_identity
from test_operations import edits, request
from test_previews import jpeg, marker

from blackmask import library, operations, previews, review
from blackmask.export import export_project
from blackmask.framing import read_framing_preset, save_framing_preset
from blackmask.ingest import srgb_profile
from blackmask.project import ProjectError, read_project, read_revision
from blackmask.series_framing import read_series_settings, save_series_settings


class CachedPrediction:
    identity: ClassVar[dict] = {
        name: value for name, value in cache_identity().items() if name != "developed_id"
    }

    def __init__(self, cache):
        pass

    def predict(self, pixels, trimap, device):
        return np.full(trimap.shape, 0.5), {"fixture": "synthetic", "device": device}


def imported_project(tmp_path):
    config_file, destination = configuration(tmp_path)
    for name in ("sam", "vitmatte"):
        directory = tmp_path / "shared-models" / name
        directory.mkdir(parents=True)
        (directory / "retained-model.bin").write_bytes(
            b"Synthetic placeholder, not installed weights"
        )
    with config_file.open("a") as stream:
        stream.write(
            '[models]\nsam_cache = "../shared-models/sam"\nvitmatte_cache = "../shared-models/vitmatte"\n'
        )
    config = library.load_storage_config(config_file)
    library.ensure_library(config)
    pixels = np.full((64, 96, 3), [20001, 30002, 40003], dtype=np.uint16)
    source = tiff(destination / "Inbox/CAMERA.tif", pixels, profile=srgb_profile())
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"synthetic original sidecar")
    originals = {
        path.name: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in (source, sidecar)
    }
    project = library.import_photo(
        config, source, subject="synthetic", development={}, sidecars=(sidecar,)
    )
    assert not source.exists() and not sidecar.exists()
    assert inventory(project.parent / "original") == originals
    assert len(list((destination / "Photos").iterdir())) == 1
    regions = [
        {"id": "empty", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 8, 64]},
        {"id": "solid", "role": "foreground", "shape": "rectangle", "xyxy": [88, 0, 96, 64]},
    ]
    operations.apply_operation(
        project, request(project, guide_edits_file=edits(project, regions)), storage_config=config
    )
    return config_file, config, project, pixels


def matte(project, config):
    selected = config.vitmatte_cache or Path("explicit-synthetic-model-boundary")
    with patch.object(operations, "VitMatteSession", wraps=CachedPrediction) as construct:
        result = operations.apply_operation(
            project,
            request(project, kind="matte"),
            model_cache=selected,
            storage_config=config,
        )
        assert construct.call_count == 1 and construct.call_args.args == (selected,)
        return result


def shade(project, opacity, *, opacity_only=False):
    result = request(
        project,
        kind="effects",
        scope_xyxy=[8, 0, 88, 64],
        candidate_comparison=True,
        support_file="shading-support.png",
        shading={"enabled": True, "opacity": opacity, "width_px": 3.0, "direction_degrees": 90.0},
    )
    if opacity_only:
        result["opacity_only"] = True
    else:
        result["shading_protection_file"] = "shading-protection.png"
    return result


def assert_delivery(directory, size, members=DEFAULT_MEMBERS):
    assert {path.name for path in directory.iterdir()} == members
    with tifffile.TiffFile(directory / "result_rgb16.tif") as image:
        assert image.pages[0].dtype == np.dtype("uint16")
        assert image.pages[0].tags[34675].value == srgb_profile()
        pixels = image.asarray()
    assert pixels.shape == (size[1], size[0], 3)
    with Image.open(directory / "result_RGB8_VIEW.png") as image:
        assert image.info["icc_profile"] == srgb_profile()
        np.testing.assert_array_equal(
            np.array(image), np.rint(pixels.astype(float) / 257).astype(np.uint8)
        )
    return pixels


def assert_editable_native(directory, foreground, alpha, weight, background, expected):
    members = DEFAULT_MEMBERS | {
        "foreground_rgb16.tif",
        "alpha16.png",
        "source_rgb16.tif",
        "shadow_weight16.png",
        "shading_settings.json",
        "background_rgb16.tif",
        "background_settings.json",
    }
    np.testing.assert_array_equal(assert_delivery(directory, (96, 64), members), expected)
    record = json.loads((directory / "manifest.json").read_bytes())
    assert record["mode"] == "native" and record["requested_variants"] == ["editable"]
    assert set(record["files"]) == members - {"manifest.json"}
    profile_digest = hashlib.sha256(srgb_profile()).hexdigest()
    for name, metadata in record["files"].items():
        raw = (directory / name).read_bytes()
        assert metadata["bytes"] == len(raw)
        assert metadata["sha256"] == hashlib.sha256(raw).hexdigest()
        if name.endswith(".tif"):
            assert metadata["precision_bits"] == 16 and metadata["mode"] == "RGB"
            assert metadata["dimensions_wh"] == [96, 64]
            assert metadata["icc_profile_sha256"] == profile_digest
            with tifffile.TiffFile(directory / name) as image:
                assert image.pages[0].dtype == np.dtype("uint16")
                assert image.pages[0].tags[34675].value == srgb_profile()
        elif name in {"alpha16.png", "shadow_weight16.png"}:
            assert metadata["precision_bits"] == 16 and metadata["mode"] == "I;16"
            assert metadata["dimensions_wh"] == [96, 64]
            assert metadata["icc_profile_sha256"] is None
            assert raw[24:26] == bytes((16, 0))
            with Image.open(directory / name) as image:
                assert "icc_profile" not in image.info and "gamma" not in image.info
    delivered_foreground = tifffile.imread(directory / "foreground_rgb16.tif")
    delivered_background = tifffile.imread(directory / "background_rgb16.tif")
    with Image.open(directory / "alpha16.png") as image:
        delivered_alpha = np.array(image)
    with Image.open(directory / "shadow_weight16.png") as image:
        delivered_weight = np.array(image)
    for actual, saved in (
        (delivered_foreground, foreground),
        (delivered_background, background),
        (delivered_alpha, alpha),
        (delivered_weight, weight),
        (tifffile.imread(directory / "source_rgb16.tif"), foreground),
    ):
        np.testing.assert_array_equal(actual, saved)
    settings = json.loads((directory / "shading_settings.json").read_bytes())
    assert settings["enabled"] is True and settings["opacity"] == 0.12
    assert record["shading"]["opacity"] == settings["opacity"]
    reconstructed = np.rint(
        delivered_foreground.astype(float)
        * (delivered_alpha.astype(float) / 65535)[..., None]
        * (1 - settings["opacity"] * delivered_weight.astype(float) / 65535)[..., None]
        + delivered_background.astype(float)
        * (1 - delivered_alpha.astype(float) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(reconstructed, expected)
    return record


def assert_intact_editable_reuse(project, selected, options, deliveries):
    export_module = importlib.import_module("blackmask.export")
    with (
        patch.object(export_module, "_write_delivery", side_effect=AssertionError("output staged")),
        patch.object(
            export_module, "render_background", side_effect=AssertionError("native rendered")
        ),
        patch("blackmask.framing.frame_result", side_effect=AssertionError("margins rendered")),
        patch(
            "blackmask.series_framing.render_series", side_effect=AssertionError("series rendered")
        ),
    ):
        for mode, original in zip(options, deliveries, strict=True):
            repeated = export_project(
                project, revision=selected, draft=True, variants=("editable",), **mode
            )
            assert repeated == {**original, "reused": True}


def test_configured_storage_cache_and_forced_saved_reconstruction(tmp_path):
    config_file, config, project, pixels = imported_project(tmp_path)
    model_root = tmp_path / "shared-models"
    models_before = inventory(model_root)
    assert len(models_before) == 2
    first = matte(project, config)
    operations.accept_revision(project, first["revision"], storage_config=config)
    # A saved lock protects real partial alpha through a second native operation.
    lock = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [30, 20, 31, 21],
                "revision": first["revision"],
            }
        ],
    )
    operations.apply_operation(
        project, request(project, guide_edits_file=lock), storage_config=config
    )
    native = matte(project, config)
    assert native["revision"] == "rev-004"
    support = np.zeros((64, 96), dtype=np.uint16)
    support[:, 8:88] = 65535
    protection = np.zeros((64, 96), dtype=np.uint16)
    protection[20, 30] = 65535
    Image.fromarray(support).save(project / "shading-support.png")
    Image.fromarray(protection).save(project / "shading-protection.png")
    twelve = operations.apply_operation(project, shade(project, 0.12), storage_config=config)
    twenty_four = operations.apply_operation(
        project, shade(project, 0.24, opacity_only=True), storage_config=config
    )
    old_manifest = read_revision(project, twelve["revision"], read_project(project)["developed_id"])
    manifest = read_revision(
        project, twenty_four["revision"], read_project(project)["developed_id"]
    )
    for role in (
        "foreground_rgb16.tif",
        "base_alpha16.png",
        "shadow_weight16.png",
        "supports/support16.png",
        "supports/protection.png",
        "effects/shading/protection16.png",
    ):
        assert old_manifest["assets"][role] == manifest["assets"][role]
    before_reuse = inventory(project)
    with (
        patch.object(operations, "VitMatteSession", side_effect=AssertionError("unexpected model")),
        patch("blackmask.effects.make_shadow_weight", side_effect=AssertionError("unexpected W")),
        patch.object(
            previews, "_render_latest", side_effect=AssertionError("unexpected result render")
        ),
    ):
        repeated = operations.apply_operation(
            project, shade(project, 0.24, opacity_only=True), storage_config=config
        )
    assert repeated["reused"] is True and repeated["revision"] == "rev-006"
    assert inventory(project) == before_reuse
    gallery = jpeg(config, project)
    assert marker(gallery)["status"] == "Draft"
    operations.accept_revision(project, twenty_four["revision"], storage_config=config)
    assert marker(gallery)["status"] == "Accepted"

    margins = {"left_px": 2, "right_px": 3, "top_px": 4, "bottom_px": 5}
    series = {
        "name": "Synthetic",
        "output_width_px": 137,
        "output_height_px": 181,
        "side_margin_tenths_percent": 150,
        "minimum_vertical_margin_tenths_percent": 50,
    }
    identity = read_project(project)["developed_id"]
    save_framing_preset(project, margins, expected_digest=None, expected_developed_id=identity)
    save_series_settings(project, series, expected_digest=None, expected_developed_id=identity)
    presets = {
        name: (project / name).read_bytes() for name in ("framing.json", "series-framing.json")
    }
    # Literal selected, working and accepted identities differ.
    operations.restore_revision(
        project, native["revision"], replace_drafts=True, storage_config=config
    )
    assert read_project(project)["working_revision"] == "rev-004"
    assert read_project(project)["accepted_revision"] == "rev-006"
    assert read_project(project)["latest_result_revision"] == "rev-006"
    selected = twelve["revision"]
    assert selected == "rev-005"
    state_before = (project / "state.json").read_bytes()
    comparison = review.review_project(
        project,
        revision=selected,
        crops=[[80, 0, 96, 9]],
        comparison=True,
        retain_native=True,
        storage_config=config,
    )
    assert Path(comparison["comparison_manifest_file"]).is_file()
    assert (project / "state.json").read_bytes() == state_before
    assert len(list((config.destination / "Results Preview").glob("*.jpg"))) == 1
    assert marker(gallery)["revision"] == "rev-006" and marker(gallery)["status"] == "Accepted"
    reopened = command("--config", config_file, "status", project, cwd=tmp_path)
    assert reopened.returncode == 0, reopened.stderr
    assert json.loads(reopened.stdout)["working_revision"] == "rev-004"

    options = ({}, {"framing": margins}, {"series": series})
    default_deliveries = [
        export_project(project, revision=selected, draft=True, **mode) for mode in options
    ]
    native_pixels = assert_delivery(Path(default_deliveries[0]["directory"]), (96, 64))
    framed_pixels = assert_delivery(Path(default_deliveries[1]["directory"]), (101, 73))
    series_pixels = assert_delivery(Path(default_deliveries[2]["directory"]), (137, 181))
    for result in default_deliveries:
        record = json.loads(Path(result["manifest_file"]).read_bytes())
        assert record["requested_variants"] == [] and "editable_companion" not in record
    np.testing.assert_array_equal(framed_pixels[4:68, 2:98], native_pixels)
    background = tifffile.imread(
        saved_raster(project / f"revisions/{selected}/background/background_rgb16.tif")
    )
    expected_padding = np.pad(background, ((4, 5), (2, 3), (0, 0)), mode="edge")
    expected_padding[4:68, 2:98] = native_pixels
    np.testing.assert_array_equal(framed_pixels, expected_padding)
    # Independently evaluate the saved native scalar equation at every pixel/channel.
    alpha = np.array(
        Image.open(saved_raster(project / f"revisions/{selected}/base_alpha16.png")),
        dtype=np.uint16,
    )
    weight = np.array(
        Image.open(saved_raster(project / f"revisions/{selected}/shadow_weight16.png")),
        dtype=np.uint16,
    )
    assert alpha[20, 30] == 32768 and weight[20, 30] == 0
    assert np.any(weight > 0) and np.any((alpha > 0) & (alpha < 65535))
    expected = np.rint(
        pixels.astype(float)
        * (alpha.astype(float) / 65535)[..., None]
        * (1 - 0.12 * weight.astype(float) / 65535)[..., None]
        + background.astype(float) * (1 - alpha.astype(float) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(native_pixels, expected)
    assert np.any(native_pixels % 257)
    deliveries = [
        export_project(project, revision=selected, draft=True, variants=("editable",), **mode)
        for mode in options
    ]
    native_directory = Path(deliveries[0]["directory"])
    native_record = assert_editable_native(
        native_directory, pixels, alpha, weight, background, expected
    )
    saved_revision = project / "revisions" / selected
    assert native_record["revision"] == selected and native_record["draft"] is True
    assert (
        native_record["revision_manifest_sha256"]
        == hashlib.sha256((saved_revision / "manifest.json").read_bytes()).hexdigest()
    )
    for delivered_name, saved_name in (
        ("recipe.toml", "recipe.toml"),
        ("background_settings.json", "background/settings.json"),
    ):
        assert (native_directory / delivered_name).read_bytes() == (
            saved_revision / saved_name
        ).read_bytes()
    assert (
        json.loads((native_directory / "shading_settings.json").read_bytes())
        == native_record["shading"]
    )
    for output, size, expected_pixels in zip(
        deliveries[1:], ((101, 73), (137, 181)), (framed_pixels, series_pixels), strict=True
    ):
        primary = Path(output["directory"])
        np.testing.assert_array_equal(assert_delivery(primary, size), expected_pixels)
        record = json.loads((primary / "manifest.json").read_bytes())
        assert record["requested_variants"] == ["editable"]
        assert record["editable_companion_request"] == {
            "directory_name": native_directory.name,
            "identity_sha256": native_record["identity_sha256"],
        }
        binding = {
            "directory_name": native_directory.name,
            "manifest_sha256": hashlib.sha256(
                (native_directory / "manifest.json").read_bytes()
            ).hexdigest(),
            "files_sha256": {name: item["sha256"] for name, item in native_record["files"].items()},
        }
        assert record["editable_companion"] == binding
        assert output["editable_companion"] == {
            "directory": str(native_directory),
            "manifest_file": str(native_directory / "manifest.json"),
            "manifest_sha256": binding["manifest_sha256"],
        }
    assert_intact_editable_reuse(project, selected, options, deliveries)

    save_framing_preset(
        project,
        {key: value + 1 for key, value in margins.items()},
        expected_digest=read_framing_preset(project, identity, (96, 64))[1],
        expected_developed_id=identity,
    )
    save_series_settings(
        project,
        series | {"name": "Changed", "output_width_px": 139},
        expected_digest=read_series_settings(project, identity, (96, 64))[1],
        expected_developed_id=identity,
    )
    assert all((project / name).read_bytes() != raw for name, raw in presets.items())
    failure = project / "exports/.retained-failure"
    failure.mkdir()
    (failure / "diagnostic.txt").write_bytes(b"preserved synthetic failed export stage")
    before_clear = inventory(config.destination)
    inspected = operations.inspect_processing_cache(project)
    assert inspected["candidates"] and inspected["blockers"] == []
    cleared = operations.clear_processing_cache(
        project, inspected["candidate_digest"], storage_config=config
    )
    assert cleared["status"] == "cleared"
    removed = {str((project / name).relative_to(config.destination)) for name in cleared["removed"]}
    assert inventory(config.destination) == {
        name: data for name, data in before_clear.items() if name not in removed
    }
    assert inventory(model_root) == models_before
    assert_intact_editable_reuse(project, selected, options, deliveries)

    # Reconstruction has no existing exports/cache or reachable original capture/model.
    reconstructed = tmp_path / "reconstruction"
    shutil.copytree(
        project,
        reconstructed,
        ignore=shutil.ignore_patterns("exports", "cache", "framing.json", "series-framing.json"),
    )
    reference_root = tmp_path / "retained-original-bundle"
    relative_deliveries = [
        Path(result["directory"]).relative_to(project.parent) for result in deliveries
    ]
    project.parent.rename(reference_root)
    assert not project.exists() and not (reconstructed / "exports").exists()
    assert not any((reconstructed / name).exists() for name in presets)
    frozen = [
        json.loads((reference_root / path / "manifest.json").read_bytes())
        for path in relative_deliveries
    ]
    program = """import importlib,json,socket,sys
from pathlib import Path
from unittest.mock import patch
from blackmask.export import export_project
outputs=[]
with patch.object(socket,'socket',side_effect=AssertionError('offline')):
    for record in json.loads(sys.argv[2]):
        module=importlib.import_module({'native':'blackmask.export','add-margins':'blackmask.framing','match-series':'blackmask.series_framing'}[record['mode']])
        name={'native':'render_background','add-margins':'frame_result','match-series':'render_series'}[record['mode']]
        arguments={'revision':record['revision'],'draft':record['draft'],'variants':tuple(record['requested_variants'])}
        if record['mode']=='add-margins': arguments['framing']=record['margins']
        if record['mode']=='match-series': arguments['series']=record['settings']
        with patch.object(module,name,wraps=getattr(module,name)) as render:
            output=export_project(Path(sys.argv[1]),**arguments)
            assert render.call_count>0 and output['reused'] is False
        outputs.append(dict(output,render_calls=render.call_count))
print(json.dumps(outputs))
"""
    child = subprocess.run(
        [sys.executable, "-B", "-c", program, str(reconstructed), json.dumps(frozen)],
        env=dict(
            os.environ,
            BLACKMASK_VITMATTE_CACHE=str(tmp_path / "unavailable-models"),
            BLACKMASK_SAM_CACHE=str(tmp_path / "unavailable-models"),
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    outputs = json.loads(child.stdout)
    assert inventory(model_root) == models_before
    for relative, output in zip(relative_deliveries, outputs, strict=True):
        reference, rebuilt = reference_root / relative, Path(output["directory"])
        assert inventory(reference) == inventory(rebuilt)
        assert (reference / "manifest.json").read_bytes() == (
            rebuilt / "manifest.json"
        ).read_bytes()
        np.testing.assert_array_equal(
            tifffile.imread(reference / "result_rgb16.tif"),
            tifffile.imread(rebuilt / "result_rgb16.tif"),
        )
        with (
            Image.open(reference / "result_RGB8_VIEW.png") as first_view,
            Image.open(rebuilt / "result_RGB8_VIEW.png") as second_view,
        ):
            assert (
                first_view.info["icc_profile"] == second_view.info["icc_profile"] == srgb_profile()
            )
            np.testing.assert_array_equal(np.array(first_view), np.array(second_view))
        record = json.loads((rebuilt / "manifest.json").read_bytes())
        if record["mode"] == "native":
            assert_editable_native(rebuilt, pixels, alpha, weight, background, expected)
        else:
            companion = Path(output["editable_companion"]["directory"])
            assert companion == Path(outputs[0]["directory"])
            assert inventory(
                reference.parent / record["editable_companion"]["directory_name"]
            ) == inventory(companion)
            assert_editable_native(companion, pixels, alpha, weight, background, expected)
    (tmp_path / "journey-evidence.json").write_text(
        json.dumps(
            {
                "removed": cleared,
                "selected_revision": selected,
                "working_revision": "rev-004",
                "accepted_revision": "rev-006",
                "model_locators": {
                    "sam": str(config.sam_cache),
                    "vitmatte": str(config.vitmatte_cache),
                },
                "model_fixture": "Two retained synthetic placeholders; no installed weights or download",
                "model_files_preserved": len(models_before),
                "before_clear_files": len(before_clear),
                "before_clear_logical_bytes": sum(len(value[0]) for value in before_clear.values()),
                "reconstructed": outputs,
                "retained_file_count": len(inventory(reference_root)),
                "retained_logical_bytes": sum(
                    len(value[0]) for value in inventory(reference_root).values()
                ),
            },
            indent=2,
        )
    )


@pytest.mark.parametrize("boundary", ["CAMERA.tif", "bundle"])
def test_combined_import_processing_and_gallery_interruption_recovery(tmp_path, boundary):
    config_file, destination = configuration(tmp_path)
    config = library.load_storage_config(config_file)
    library.ensure_library(config)
    source = tiff(destination / "Inbox/CAMERA.tif", profile=srgb_profile())
    original = source.read_bytes()
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"retained sidecar")
    rename = library._exclusive_rename
    triggered = []

    def interrupt_move(start, end, **kwargs):
        rename(start, end, **kwargs)
        if start.name == boundary and kwargs.get("source_directory") is not None and not triggered:
            triggered.append(start.name)
            raise OSError("injected after visible import move")

    with (
        patch.object(library, "_exclusive_rename", side_effect=interrupt_move),
        pytest.raises(OSError, match="visible import"),
    ):
        library.import_photo(
            config, source, subject="synthetic", development={}, sidecars=(sidecar,)
        )
    assert triggered == [boundary]
    pending = next((destination / "Inbox/.imports").glob("*/import.json"))
    retained = inventory(pending.parent)
    child = command("--config", config_file, "import-resume", pending, cwd=tmp_path)
    assert child.returncode == 0, child.stderr
    project = Path(json.loads(child.stdout)["project"])
    assert (project.parent / "original/CAMERA.tif").read_bytes() == original
    assert (project.parent / "original/CAMERA.xmp").read_bytes() == b"retained sidecar"
    assert not source.exists() and not sidecar.exists()
    assert len(list((destination / "Photos").iterdir())) == 1 and retained
    operations.apply_operation(project, request(project), storage_config=config)
    state_before = (project / "state.json").read_bytes()
    publish = operations._atomic_json

    def fail_pointer(path, value, **kwargs):
        if path.name == "state.json":
            raise OSError("injected before native pointer")
        return publish(path, value, **kwargs)

    with (
        patch.object(operations, "_atomic_json", side_effect=fail_pointer),
        pytest.raises(OSError, match="native pointer"),
    ):
        matte(project, config)
    assert (project / "state.json").read_bytes() == state_before
    operation = next((project / "requests").glob("matte-*"))
    assert (operation / "completion.json").is_file()
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    preserved = inventory(project)
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(
            project, report["candidate_digest"], storage_config=config
        )
    assert inventory(project) == preserved
    with patch.object(
        operations, "VitMatteSession", side_effect=AssertionError("completed stage loaded model")
    ):
        resumed = operations.resume_operation(project, operation.name, storage_config=config)
    assert resumed["resumed_completed_stage"] is True
    assert marker(jpeg(config, project))["status"] == "Draft"

    def fail_after_pointer(path, value, **kwargs):
        publish(path, value, **kwargs)
        if path.name == "state.json":
            raise OSError("injected after visible acceptance")

    with (
        patch.object(operations, "_atomic_json", side_effect=fail_after_pointer),
        pytest.raises(OSError, match="visible acceptance"),
    ):
        operations.accept_revision(project, resumed["revision"], storage_config=config)
    assert read_project(project)["accepted_revision"] == resumed["revision"]
    assert marker(jpeg(config, project))["status"] == "Draft"
    assert previews.result_preview_status(project, config)["status"] == "pending"
    assert previews.refresh_result_preview(project, config)["status"] == "current"
    assert marker(jpeg(config, project))["status"] == "Accepted"
    export = Path(export_project(project)["directory"])
    delivery = inventory(export)
    operations.apply_operation(project, request(project), storage_config=config)
    with patch.object(previews, "_atomic_json", side_effect=OSError("injected gallery receipt")):
        newer = matte(project, config)
    assert newer["preview_pending"] is True
    assert read_project(project)["accepted_revision"] == resumed["revision"]
    assert read_project(project)["latest_result_revision"] == newer["revision"]
    assert marker(jpeg(config, project))["status"] == "Draft"
    assert previews.refresh_result_preview(project, config)["status"] == "current"
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"] == []
    before_clear = inventory(project)
    result = operations.clear_processing_cache(
        project, report["candidate_digest"], storage_config=config
    )
    assert result["status"] == "cleared"
    assert inventory(project) == {
        name: value for name, value in before_clear.items() if name not in result["removed"]
    }
    assert inventory(export) == delivery
    assert (project.parent / "original/CAMERA.tif").read_bytes() == original
