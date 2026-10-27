"""Explicit local I10 technical evidence, separate from routine deterministic tests.

Set BLACKMASK_LIFECYCLE_RAW, BLACKMASK_SAM_CACHE and BLACKMASK_VITMATTE_CACHE.
A skipped prerequisite leaves mandatory I10 evidence open. Photos remain Draft.
"""

import hashlib
import json
import os
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image
from storage_journey_process import process_environment
from test_ingest import saved_raster
from test_library import configuration
from test_operations import edits, request

from blackmask import library, models, operations
from blackmask.export import export_project
from blackmask.ingest import srgb_profile
from blackmask.project import read_project, read_revision


@pytest.mark.integration
def test_local_raw_models_recovery_and_saved_delivery(tmp_path):
    names = ("BLACKMASK_LIFECYCLE_RAW", "BLACKMASK_SAM_CACHE", "BLACKMASK_VITMATTE_CACHE")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.skip("Mandatory I10 live evidence unavailable: set " + ", ".join(missing))
    source, sam_cache, matte_cache = (Path(os.environ[name]).resolve() for name in names)
    assert source.is_file() and source.suffix.lower() == ".dng"
    assert sam_cache.is_dir() and matte_cache.is_dir()
    record = {"evidence": "I10 technical; no photographic acceptance", "timings_seconds": {}}
    started = time.monotonic()

    def measure(name, action):
        start = time.monotonic()
        value = action()
        record["timings_seconds"][name] = time.monotonic() - start
        return value

    try:
        if os.environ.get("BLACKMASK_LIFECYCLE_NETWORK_DENIED") == "1":
            with socket.socket() as connection, pytest.raises(PermissionError):
                connection.connect(("127.0.0.1", 9))
            record["network"] = "OS-denied, verified with loopback negative control"
        else:
            record["network"] = "OS isolation unverified; offline flags alone are insufficient"
        record["model_hashes"] = {
            "sam": models.verify_sam(sam_cache),
            "vitmatte": models.verify_vitmatte(matte_cache),
        }
        original = source.read_bytes()
        record["source_sha256"] = hashlib.sha256(original).hexdigest()
        config_file, destination = configuration(tmp_path)
        config = library.load_storage_config(config_file)
        library.ensure_library(config)
        capture = destination / "Inbox/fixture.dng"
        capture.write_bytes(original)
        project = measure(
            "raw_import",
            lambda: library.import_photo(
                config, capture, subject="local-technical-fixture", development={}
            ),
        )
        record["project"] = str(project)
        state = read_project(project)
        identity = state["developed_id"]
        master_path = saved_raster(project / "assets/developed" / (identity + ".tif"))
        master_bytes = master_path.read_bytes()
        pixels = tifffile.imread(master_path)
        assert pixels.dtype == np.uint16 and np.any(pixels % 257)
        with tifffile.TiffFile(master_path) as image:
            assert image.pages[0].tags[34675].value == srgb_profile()
        height, width = pixels.shape[:2]
        record["dimensions_wh"] = [width, height]
        record["source_metadata"] = json.loads((project / "source.json").read_bytes())
        proxy = np.rint(pixels.astype(float) / 257).astype(np.uint8)
        Image.fromarray(proxy).save(tmp_path / "source_RGB8_VIEW.png")
        # Match the current matte writer's conservative payload estimate, before loading models.
        reserve = pixels.nbytes * 42 + 1024**2
        capacity = {
            "estimated_pending_write_bytes": reserve,
            "estimate_basis": "RGB16 nbytes * 42 + 1 MiB (current matte reserve)",
            "free_disk_bytes": shutil.disk_usage(tmp_path).free,
        }
        assert capacity["free_disk_bytes"] >= reserve
        if sys.platform == "darwin":
            pressure = subprocess.run(
                ["/usr/bin/memory_pressure", "-Q"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            capacity["memory_pressure_before_models"] = {
                "exit": pressure.returncode,
                "stdout": pressure.stdout,
                "stderr": pressure.stderr,
            }
        else:
            capacity["memory_pressure_before_models"] = "not measured on this platform"
        record["capacity_before_models"] = capacity
        session = measure("sam_cold_load", lambda: models.SamSession(sam_cache))
        arguments = (proxy, [[width // 2, height // 2]], [1], None)
        first = measure(
            "sam_cold_prediction", lambda: session.select(*arguments, "cpu", developed_id=identity)
        )
        warm = measure(
            "sam_warm_prediction", lambda: session.select(*arguments, "cpu", developed_id=identity)
        )
        assert first.masks.shape == (3, height, width) and warm.metadata["embedding_reused"]
        assert first.metadata["device"] == "cpu" and first.metadata["dtype"] == "float32"
        record["sam"] = first.metadata
        record["sam_warm"] = warm.metadata
        try:
            mps = measure(
                "sam_mps", lambda: session.select(*arguments, "mps", developed_id=identity)
            )
            assert mps.metadata["device"] == "mps" and mps.metadata["dtype"] == "float32"
            record["sam_mps"] = {"status": "success", "metadata": mps.metadata}
        except (ValueError, RuntimeError) as error:
            record["sam_mps"] = {"status": "unsupported-or-error", "error": str(error)}
        session = None
        del first, warm
        # Explicit technical guidance, not an assessment of the photograph's final mask.
        regions = [
            {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [0, 0, width, 3]},
            {"id": "fg", "role": "foreground", "shape": "point", "xy": [width // 2, height // 2]},
        ]
        operations.apply_operation(
            project,
            request(project, guide_edits_file=edits(project, regions)),
            storage_config=config,
        )
        result, recovery_times = interrupted_matte(project, config_file, matte_cache, tmp_path)
        record["timings_seconds"].update(recovery_times)
        manifest = read_revision(project, result["revision"], identity)
        record["native_matte"] = manifest["model"]
        assert manifest["model"]["reused_tiles"] >= 1
        alpha = np.array(
            Image.open(
                saved_raster(project / "revisions" / result["revision"] / "base_alpha16.png")
            )
        )
        assert np.all(alpha[:3] == 0) and alpha[height // 2, width // 2] == 65535
        partial = np.argwhere((alpha > 0) & (alpha < 65535))
        assert len(partial)
        y, x = map(int, partial[len(partial) // 2])
        scope = [max(0, x - 8), max(0, y - 8), min(width, x + 9), min(height, y + 9)]
        context = [max(0, x - 24), max(0, y - 24), min(width, x + 25), min(height, y + 25)]
        guides = [
            {
                "id": "partial-lock",
                "role": "lock",
                "shape": "point",
                "xy": [x, y],
                "revision": result["revision"],
            },
            {
                "id": "repair-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": scope,
                "feather_px": 0,
            },
        ]
        prepared = operations.apply_operation(
            project,
            request(project, guide_edits_file=edits(project, guides)),
            storage_config=config,
        )
        repair = measure(
            "local_repair",
            lambda: operations.apply_operation(
                project,
                request(
                    project,
                    kind="repair",
                    context_xyxy=context,
                    scope_xyxy=scope,
                    support_file=prepared["support_file"],
                    reason="Technical scoped-replay exercise; no claimed photographic defect or improvement",
                    merge_policy="replace",
                ),
                model_cache=matte_cache,
                storage_config=config,
            ),
        )
        repaired = np.array(
            Image.open(
                saved_raster(project / "revisions" / repair["revision"] / "base_alpha16.png")
            )
        )
        outside = np.ones(alpha.shape, dtype=bool)
        outside[scope[1] : scope[3], scope[0] : scope[2]] = False
        assert outside.any() and (~outside).any()
        np.testing.assert_array_equal(repaired[outside], alpha[outside])
        assert repaired[y, x] == alpha[y, x]
        record["repair"] = {
            "scope": scope,
            "context": context,
            "protected_partial": [x, y, int(alpha[y, x])],
        }
        model = measure("vitmatte_cold_load", lambda: models.VitMatteSession(matte_cache))
        crop = proxy[:65, :97]
        guide = np.full((65, 97), 128, dtype=np.uint8)
        try:
            _, metadata = measure("vitmatte_mps", lambda: model.predict(crop, guide, "mps"))
            assert metadata["device"] == "mps" and metadata["dtype"] == "float32"
            record["vitmatte_mps"] = {"status": "success", "metadata": metadata}
        except (ValueError, RuntimeError) as error:
            record["vitmatte_mps"] = {"status": "unsupported-or-error", "error": str(error)}
        delivery = measure(
            "editable_export",
            lambda: export_project(
                project, revision=repair["revision"], draft=True, variants=("editable",)
            ),
        )
        assert_saved_delivery(Path(delivery["directory"]), repaired, pixels)
        for saved_revision in (result["revision"], repair["revision"]):
            np.testing.assert_array_equal(
                tifffile.imread(
                    saved_raster(project / "revisions" / saved_revision / "foreground_rgb16.tif")
                ),
                pixels,
            )
        record["offline_continuation"] = offline_continuation(
            project, config_file, matte_cache, tmp_path
        )
        assert read_project(project)["accepted_revision"] is None
        assert master_path.read_bytes() == master_bytes
        assert (
            (project.parent / "original/fixture.dng").read_bytes()
            == original
            == source.read_bytes()
        )
        record["status"] = "passed"
    finally:
        record["total_seconds"] = time.monotonic() - started
        rss_bytes = 1 if sys.platform == "darwin" else 1024
        record["peak_rss_bytes_self"] = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_bytes
        )
        record["peak_rss_bytes_child"] = (
            resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * rss_bytes
        )
        record["retained_logical_bytes"] = sum(
            path.stat().st_size for path in tmp_path.rglob("*") if path.is_file()
        )
        record["free_disk_bytes_after"] = shutil.disk_usage(tmp_path).free
        (tmp_path / "live-evidence.json").write_text(json.dumps(record, indent=2))


def assert_saved_delivery(output, expected_alpha, expected_source):
    """Independent native equation from delivered layers, including saved background."""
    foreground = tifffile.imread(output / "foreground_rgb16.tif")
    np.testing.assert_array_equal(foreground, expected_source)
    np.testing.assert_array_equal(tifffile.imread(output / "source_rgb16.tif"), expected_source)
    background = tifffile.imread(output / "background_rgb16.tif")
    with Image.open(output / "alpha16.png") as image:
        alpha = np.array(image)
    np.testing.assert_array_equal(alpha, expected_alpha)
    opacity = alpha.astype(float)[..., None] / 65535
    expected = np.rint(
        foreground.astype(float) * opacity + background.astype(float) * (1 - opacity)
    ).astype(np.uint16)
    np.testing.assert_array_equal(tifffile.imread(output / "result_rgb16.tif"), expected)
    with Image.open(output / "result_RGB8_VIEW.png") as image:
        assert image.info["icc_profile"] == srgb_profile()
        np.testing.assert_array_equal(
            np.array(image), np.rint(expected.astype(float) / 257).astype(np.uint8)
        )


def offline_continuation(project, config_file, matte_cache, workspace):
    """Fresh CLI processes author, recover stale shading, export and restore offline."""
    from test_cache_management import inventory

    calls = []

    def invoke(label, *arguments, expected=0):
        calls.append(label)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "blackmask",
                "--config",
                str(config_file),
                *map(str, arguments),
            ],
            env=process_environment(workspace),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        (workspace / f"{label}.stdout").write_text(result.stdout)
        (workspace / f"{label}.stderr").write_text(result.stderr)
        assert result.returncode == expected, result.stdout + result.stderr
        return json.loads(result.stdout) if expected == 0 else result.stderr

    def run(label, operation):
        path = workspace / f"{label}.json"
        path.write_text(json.dumps(operation))
        return invoke(label, "run", project, "--request", path, "--model-cache", matte_cache)

    state = invoke("offline-reopen", "status", project)
    baseline = state["working_revision"]
    retained = inventory(project / "exports")
    source = tifffile.imread(
        saved_raster(project / "assets/developed" / (state["developed_id"] + ".tif"))
    )
    alpha = np.array(
        Image.open(saved_raster(project / "revisions" / baseline / "base_alpha16.png"))
    )
    height, width = alpha.shape
    partial = np.argwhere((alpha > 0) & (alpha < 65535))
    y, x = map(int, partial[len(partial) // 4])
    scope = [max(0, x - 8), max(0, y - 8), min(width, x + 9), min(height, y + 9)]
    context = [max(0, x - 24), max(0, y - 24), min(width, x + 25), min(height, y + 25)]
    support = np.zeros(alpha.shape, dtype=np.uint16)
    support[scope[1] : scope[3], scope[0] : scope[2]] = 65535
    Image.fromarray(support).save(project / "offline-support.png")
    protection = np.zeros(alpha.shape, dtype=np.uint16)
    protection[y, min(x + 1, width - 1)] = 65535
    Image.fromarray(protection).save(project / "offline-protection.png")

    def shading_request():
        return request(
            project,
            kind="effects",
            scope_xyxy=scope,
            support_file="offline-support.png",
            shading_protection_file="offline-protection.png",
            candidate_comparison=True,
            shading={"enabled": True, "opacity": 0.12, "width_px": 3.0, "direction_degrees": 90.0},
        )

    run("offline-shading", shading_request())
    changes = edits(
        project,
        [
            {"id": "offline-core", "role": "foreground", "shape": "point", "xy": [x, y]},
            {
                "id": "offline-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": scope,
                "feather_px": 0,
            },
        ],
    )
    prepared = run("offline-author", request(project, guide_edits_file=changes, scope_xyxy=scope))
    repaired = run(
        "offline-repair",
        request(
            project,
            kind="repair",
            context_xyxy=context,
            scope_xyxy=scope,
            support_file=prepared["support_file"],
            reason="Offline technical stale-dependency exercise",
            merge_policy="replace",
        ),
    )
    manifest = read_revision(project, repaired["revision"], state["developed_id"])
    assert manifest["shading"]["stale"]
    error = invoke(
        "offline-stale-export",
        "export",
        project,
        "--revision",
        repaired["revision"],
        "--draft",
        "--variant",
        "editable",
        expected=1,
    )
    assert "stale" in error.lower()
    rebuilt = run("offline-rebuild", shading_request())
    assert not read_revision(project, rebuilt["revision"], state["developed_id"])["shading"][
        "stale"
    ]
    delivered = invoke(
        "offline-export",
        "export",
        project,
        "--revision",
        rebuilt["revision"],
        "--draft",
        "--variant",
        "editable",
    )
    directory = Path(delivered["directory"])
    np.testing.assert_array_equal(tifffile.imread(directory / "source_rgb16.tif"), source)
    np.testing.assert_array_equal(tifffile.imread(directory / "foreground_rgb16.tif"), source)
    invoke("offline-restore", "restore", project, "--revision", baseline, "--replace-drafts")
    reopened = invoke("offline-reopened", "status", project)
    assert reopened["working_revision"] == baseline
    assert reopened["latest_result_revision"] == rebuilt["revision"]
    assert reopened["accepted_revision"] == state["accepted_revision"]
    # New authoring after restore must consume the restored identity, not the newer result.
    new_edits = edits(
        project,
        [{"id": "offline-new-background", "role": "background", "shape": "point", "xy": [0, 0]}],
    )
    authored = run("offline-new-authoring", request(project, guide_edits_file=new_edits))
    assert authored["parent"] == baseline
    current_exports = inventory(project / "exports")
    assert all(current_exports[name] == value for name, value in retained.items())
    return {
        "baseline": baseline,
        "rebuilt": rebuilt["revision"],
        "new_authoring": authored["revision"],
        "retained_export_files": len(retained),
        "fresh_cli_processes": len(calls),
    }


def interrupted_matte(project, config_file, matte_cache, workspace):
    """Kill only after actual tile publication, then resume through a fresh CLI."""
    timings = {}

    def measure(name, action):
        started = time.monotonic()
        value = action()
        timings[name] = time.monotonic() - started
        return value

    before = (project / "state.json").read_bytes()
    code = """import os,signal,sys
from pathlib import Path
from unittest.mock import patch
from test_operations import request
from blackmask import library,operations,project as owner
project=Path(sys.argv[1])
original=owner._publish_new_cache_file
def stop_after_verified_tile(start,end):
    original(start,end)
    os.kill(os.getpid(),signal.SIGKILL)
with patch.object(owner,'_publish_new_cache_file',stop_after_verified_tile):
    operations.apply_operation(project,request(project,kind='matte'),model_cache=Path(sys.argv[2]),storage_config=library.load_storage_config(Path(sys.argv[3])))
"""
    killed = measure(
        "interrupted_native_first_tile",
        lambda: subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                code,
                str(project),
                str(matte_cache),
                str(config_file),
            ],
            check=False,
            env=process_environment(workspace),
            capture_output=True,
            text=True,
            timeout=180,
        ),
    )
    (workspace / "interrupted.stderr").write_text(killed.stderr)
    assert killed.returncode == -signal.SIGKILL, killed.stdout + killed.stderr
    assert (project / "state.json").read_bytes() == before
    pending = operations.operation_status(project)["operations"]
    failed = [item for item in pending if item["status"] == "failed"]
    assert len(failed) == 1
    command = [
        sys.executable,
        "-B",
        "-m",
        "blackmask",
        "--config",
        str(config_file),
        "resume",
        str(project),
        "--operation",
        failed[0]["operation_id"],
        "--model-cache",
        str(matte_cache),
    ]
    resumed = measure(
        "native_matte_resume",
        lambda: subprocess.run(
            command,
            env=process_environment(workspace),
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        ),
    )
    (workspace / "resume.stdout").write_text(resumed.stdout)
    (workspace / "resume.stderr").write_text(resumed.stderr)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    result = json.loads(resumed.stdout)
    return result, timings


@pytest.mark.integration
def test_real_inference_resume_preserves_synthetic_acceptance(tmp_path):
    from test_cache_management import inventory
    from test_library_storage_journey import imported_project, matte

    cache = os.environ.get("BLACKMASK_VITMATTE_CACHE")
    if not cache:
        pytest.skip("Mandatory I10 accepted-work recovery evidence needs installed ViTMatte")
    config_file, config, project, _ = imported_project(tmp_path)
    baseline = matte(project, config)
    operations.accept_revision(project, baseline["revision"], storage_config=config)
    export = Path(export_project(project, variants=("editable",))["directory"])
    accepted = inventory(project / "revisions" / baseline["revision"])
    delivered = inventory(export)
    original = inventory(project.parent / "original")
    operations.apply_operation(project, request(project), storage_config=config)
    result, timings = interrupted_matte(project, config_file, Path(cache), tmp_path)
    state = read_project(project)
    assert state["accepted_revision"] == baseline["revision"]
    assert state["latest_result_revision"] == result["revision"]
    assert inventory(project / "revisions" / baseline["revision"]) == accepted
    assert inventory(export) == delivered
    assert inventory(project.parent / "original") == original
    manifest = read_revision(project, result["revision"], state["developed_id"])
    assert manifest["model"]["reused_tiles"] == 1 and manifest["model"]["inferred_tiles"] == 0
    (tmp_path / "accepted-recovery.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "synthetic_acceptance": True,
                "actual_inference_before_kill": True,
                "model": manifest["model"],
                "timings_seconds": timings,
            },
            indent=2,
        )
    )


@pytest.mark.integration
def test_optional_fixed_photo_smoke(tmp_path):
    """Optional B evidence, independently selected from mandatory I10 coverage."""
    name = os.environ.get("BLACKMASK_LIFECYCLE_SMOKE_PHOTO")
    cache = os.environ.get("BLACKMASK_VITMATTE_CACHE")
    if not name or not cache:
        pytest.skip(
            "Optional B smoke needs an explicit local RGB photo and installed ViTMatte cache"
        )
    source = Path(name).resolve()
    assert source.is_file()
    fixture = tmp_path / source.name
    shutil.copyfile(source, fixture)
    with Image.open(fixture) as image:
        assert image.mode == "RGB", "Select an oriented RGB photographic fixture"
        image.load()
        pixels = np.array(image)
    # Native pixels only: a bounded centre crop, with no resizing or claimed photo acceptance.
    height, width = pixels.shape[:2]
    y, x = max(0, (height - 256) // 2), max(0, (width - 256) // 2)
    crop = pixels[y : y + 256, x : x + 256]
    trimap = np.full(crop.shape[:2], 128, dtype=np.uint8)
    model_hashes = models.verify_vitmatte(Path(cache))
    started = time.monotonic()
    alpha, metadata = models.VitMatteSession(Path(cache)).predict(crop, trimap, "cpu")
    assert alpha.shape == crop.shape[:2] and np.isfinite(alpha).all()
    assert np.all((alpha >= 0) & (alpha <= 1))
    assert metadata["device"] == "cpu" and metadata["dtype"] == "float32"
    Image.fromarray(crop).save(tmp_path / "crop_RGB8_VIEW.png")
    Image.fromarray(np.rint(alpha * 65535).astype(np.uint16)).save(tmp_path / "alpha16.png")
    (tmp_path / "optional-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "evidence": "B optional computational smoke; no photographic acceptance",
                "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                "model_hashes": model_hashes,
                "metadata": metadata,
                "native_crop_xyxy": [x, y, x + crop.shape[1], y + crop.shape[0]],
                "seconds": time.monotonic() - started,
            },
            indent=2,
        )
    )
