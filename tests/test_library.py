import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from test_ingest import FakeRaw, dng_white_point_metadata, ramp, tiff

from blackmask import library as storage
from blackmask.ingest import IngestError, srgb_profile
from blackmask.project import ProjectError, load_developed, read_project

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"


def command(*arguments, cwd=None):
    return subprocess.run(
        [sys.executable, "-B", "-m", "blackmask", *map(str, arguments)],
        check=False,
        cwd=cwd,
        env=dict(os.environ, PYTHONPATH=str(SOURCE_ROOT), HF_HUB_OFFLINE="1"),
        capture_output=True,
        text=True,
        timeout=30,
    )


def configuration(tmp_path):
    folder = tmp_path / "settings"
    folder.mkdir()
    path = folder / "storage.toml"
    path.write_text('[storage]\ndestination = "../photo library"\n')
    return path, tmp_path / "photo library"


@pytest.mark.parametrize("development", [{}, {"white_balance": "daylight"}])
def test_dng_import_resume_and_duplicate_keep_saved_white_balance_and_originals(
    tmp_path, development
):
    _, destination = configuration(tmp_path)
    config = storage.StorageConfig(destination)
    storage.ensure_library(config)
    source = destination / "Inbox/capture.dng"
    source.write_bytes(dng_white_point_metadata())
    source.chmod(0o640)
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"synthetic sidecar; do not apply its settings")
    sidecar.chmod(0o604)
    originals = {
        path.name: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in (source, sidecar)
    }
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    raw = FakeRaw()
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        project = storage.import_photo(
            config, source, subject="dng", development=development, sidecars=(sidecar,)
        )
    assert not source.exists() and not sidecar.exists()
    for name, (data, mode) in originals.items():
        moved = project.parent / "original" / name
        assert moved.read_bytes() == data and stat.S_IMODE(moved.stat().st_mode) == mode
    record = json.loads((project / "source.json").read_bytes())
    assert record["original_path"] == "../original/capture.dng"
    assert record["source_sha256"] == source_hash
    assert record["metadata"]["development_options"] == development
    assert record["library"]["photo_id"] == "P" + source_hash[:12]
    state = read_project(project)
    assert state["development_approved"] is False
    assert (
        state["working_revision"]
        is state["accepted_revision"]
        is state["latest_result_revision"]
        is None
    )
    pixels, metadata = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())
    if development:
        assert metadata["development"]["white_balance"] == "daylight"
        assert "as_shot_white_balance" not in metadata and "user_wb" not in raw.settings
    else:
        assert metadata["as_shot_white_balance"]["source"] == "DNG AsShotWhiteXY"
        assert metadata["as_shot_white_balance"]["multipliers"] == [2, 1, 2, 1]
        np.testing.assert_allclose(raw.settings["user_wb"], [2, 1, 2, 1], rtol=0, atol=1e-12)
    duplicate = destination / "Inbox/duplicate.dng"
    duplicate.write_bytes(originals[source.name][0])
    pending = next((destination / "Inbox/.imports").glob("*/import.json"))
    before = inventory(project.parent)
    different = {} if development else {"white_balance": "daylight"}
    with patch("blackmask.ingest.rawpy.imread", side_effect=AssertionError("must not redevelop")):
        assert (
            storage.import_photo(config, duplicate, subject="other", development=different)
            == project
        )
        assert storage.resume_import(config, pending) == project
        assert read_project(project) == state
        np.testing.assert_array_equal(load_developed(project, state["developed_id"])[0], ramp())
    assert inventory(project.parent) == before
    assert duplicate.read_bytes() == originals[source.name][0]
    assert len(list((destination / "Photos").iterdir())) == 1
    assert not list((destination / "Results Preview").iterdir())
    assert not list((destination / "Comparisons").iterdir())


def test_invalid_dng_import_and_retry_preserve_originals_and_failed_preparation(tmp_path):
    _, destination = configuration(tmp_path)
    config = storage.StorageConfig(destination)
    storage.ensure_library(config)
    source = destination / "Inbox/invalid.dng"
    source.write_bytes(dng_white_point_metadata(overrides={50721: None}))
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"unchanged synthetic sidecar")
    before = {
        path.name: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in (source, sidecar)
    }
    with patch("blackmask.ingest.rawpy.imread", return_value=FakeRaw()):
        with pytest.raises(IngestError):
            storage.import_photo(
                config, source, subject="invalid", development={}, sidecars=(sidecar,)
            )
        pending = next((destination / "Inbox/.imports").glob("*/import.json"))
        attempt = next(pending.parent.glob(".prepare-*"))
        failed = inventory(attempt)
        with pytest.raises(IngestError):
            storage.resume_import(config, pending)
    assert inventory(attempt) == failed
    assert len(list(pending.parent.glob(".prepare-*"))) == 2
    journal = json.loads(pending.read_bytes())
    assert journal["phase"] == "preparing"
    assert journal["source_sha256"] == hashlib.sha256(before[source.name][0]).hexdigest()
    assert not list((destination / "Photos").iterdir())
    assert not list((destination / "Results Preview").iterdir())
    for path in (source, sidecar):
        assert (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) == before[path.name]


def imported_spatial_project(tmp_path, *, enabled=True):
    from PIL import Image
    from test_background import background_request
    from test_matte_operations import approve, run_matte
    from test_operations import edits, request
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask import operations

    _, destination = configuration(tmp_path)
    config = storage.StorageConfig(destination)
    storage.ensure_library(config)
    source = np.tile(ramp(), (2, 2, 1))
    incoming = tiff(destination / "Inbox/spatial.tif", source, profile=srgb_profile())
    original = incoming.read_bytes()
    project = storage.import_photo(config, incoming, subject="spatial", development={})
    filename = edits(
        project,
        [
            {"id": "empty", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 4]},
            {"id": "solid", "role": "foreground", "shape": "rectangle", "xyxy": [5, 0, 6, 4]},
        ],
    )
    prepared = operations.apply_operation(project, request(project, guide_edits_file=filename))
    approve(project, prepared)  # Synthetic fixture approval, not human photographic evidence.
    parent = run_matte(project)
    operations.accept_revision(project, parent["revision"])
    operations.apply_operation(project, background_request(project, color="#000000", variation=0.0))
    protection = np.zeros((4, 6), dtype=np.uint16)
    protection[:, 5] = 65535
    protection[1, 3] = 65535
    Image.fromarray(protection).save(project / "spatial-protection.png")
    settings = spatial_settings(6, 4)
    settings["oval"].update(center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], transition_width=0.5)
    result = operations.apply_operation(
        project,
        spatial_request(
            project,
            settings,
            candidate=True,
            spatial_fade_protection_file="spatial-protection.png",
        ),
    )
    if not enabled:
        result = operations.apply_operation(
            project, spatial_request(project, dict(settings, enabled=False))
        )
    return project, source, original, parent, result, protection != 0


def test_imported_spatial_project_cold_export_preserves_precise_layers_and_protected_partial_pixels(
    tmp_path,
):
    import tifffile

    from blackmask.export import export_project, saved_layers
    from blackmask.repair import scalar16

    project, source, original, parent, result, protection = imported_spatial_project(tmp_path)
    state = read_project(project)
    assert state["development_approved"] is False
    assert state["accepted_revision"] == parent["revision"]
    assert state["latest_result_revision"] == result["revision"]
    foreground, alpha, manifest = saved_layers(project, result["revision"], state["developed_id"])
    expected_alpha = np.full((4, 6), 16384, dtype=np.uint16)
    expected_alpha[:, 0] = 0
    expected_alpha[:, 5] = 65535
    np.testing.assert_array_equal(foreground, source)
    np.testing.assert_array_equal(alpha, expected_alpha)
    assert np.any(protection & (alpha > 0) & (alpha < 65535))
    assert "effects/spatial-fade/weight16.png" in manifest["assets"]
    # Nontransparent pixel centres lie outside radius1: q=.6 except explicit protection.
    encoded = source.astype(np.float64) / 65535
    linear = np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)
    linear *= np.where(protection, 1.0, 0.4)[..., None]
    faded = np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - 0.055)
    expected = np.rint(faded * alpha[..., None]).astype(np.uint16)
    first = Path(export_project(project, revision=result["revision"], draft=True)["directory"])
    np.testing.assert_array_equal(tifffile.imread(first / "result_rgb16.tif"), expected)
    retained = tmp_path / "retained-first-export"
    first.rename(retained)
    original_path = project.parent / "original/spatial.tif"
    original_path.rename(tmp_path / "retained-original.tif")
    if (project / "cache").exists():
        (project / "cache").rename(tmp_path / "retained-cache")
    with patch(
        "blackmask.operations.VitMatteSession", side_effect=AssertionError("must not infer")
    ):
        assert read_project(project) == state
        second = Path(export_project(project, revision=result["revision"], draft=True)["directory"])
    assert retained.is_dir() and second.is_dir() and retained != second
    assert (tmp_path / "retained-original.tif").read_bytes() == original
    np.testing.assert_array_equal(tifffile.imread(second / "result_rgb16.tif"), expected)
    np.testing.assert_array_equal(tifffile.imread(second / "source_rgb16.tif"), source)
    np.testing.assert_array_equal(tifffile.imread(second / "foreground_rgb16.tif"), source)
    np.testing.assert_array_equal(scalar16(second / "alpha16.png"), expected_alpha)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("warmed", [False, True])
def test_imported_spatial_shared_operand_corruption_fails_closed_even_off_and_warm(
    tmp_path, enabled, warmed
):
    from blackmask.assets import revision_asset
    from blackmask.project import _validation_scope

    project, _, original, _, result, _ = imported_spatial_project(tmp_path, enabled=enabled)
    directory = project / "revisions" / result["revision"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    target = revision_asset(project, directory, manifest, "effects/spatial-fade/weight16.png")
    before_state = (project / "state.json").read_bytes()
    with _validation_scope():
        if warmed:
            read_project(project)
        target.write_bytes(b"synthetic corrupted shared spatial operand")
        with pytest.raises(ProjectError, match="shared asset.*hash|changed while reading"):
            read_project(project)
    assert (project / "state.json").read_bytes() == before_state
    assert (project.parent / "original/spatial.tif").read_bytes() == original


def test_explicit_config_initializes_same_private_library_from_two_working_directories(tmp_path):
    config, library = configuration(tmp_path)
    first = command("--config", config, "library-init", cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    assert Path(json.loads(first.stdout)["destination"]) == library
    (library / "Inbox" / "keep.txt").write_bytes(b"untouched")
    second = command("--config", config, "library-init", cwd=config.parent)
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout) == json.loads(first.stdout)
    assert (library / "Inbox" / "keep.txt").read_bytes() == b"untouched"
    for name in ("", "Inbox", "Photos", "Results Preview", "Comparisons"):
        assert stat.S_IMODE((library / name).stat().st_mode) == 0o700


def test_invalid_config_does_not_initialize_any_library(tmp_path):
    config, library = configuration(tmp_path)
    config.write_text('[storage]\ndestination = "../photo library"\nunknown = true\n')
    result = command("--config", config, "library-init")
    assert result.returncode == 1, result.stderr
    assert "unknown" in result.stderr.lower()
    assert not library.exists()


def test_cli_import_moves_once_preserves_sidecars_and_reopens_precise_project(tmp_path):
    config, library = configuration(tmp_path)
    initialized = command("--config", config, "library-init")
    assert initialized.returncode == 0, initialized.stderr
    source = tiff(library / "Inbox" / "CAMERA.tif", profile=srgb_profile())
    before = source.read_bytes()
    source_hash = hashlib.sha256(before).hexdigest()
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"preserved sidecar, not applied")
    other = source.with_suffix(".json")
    other.write_bytes(b"undeclared")
    imported = command(
        "--config", config, "import", source, "--subject", "spider", "--sidecar", sidecar
    )
    assert imported.returncode == 0, imported.stderr
    project = Path(json.loads(imported.stdout)["project"])
    assert project == library / "Photos" / f"P{source_hash[:12]}_undated_spider" / "project"
    assert not source.exists() and not sidecar.exists()
    assert other.read_bytes() == b"undeclared"
    assert (project.parent / "original" / "CAMERA.tif").read_bytes() == before
    assert (
        project.parent / "original" / "CAMERA.xmp"
    ).read_bytes() == b"preserved sidecar, not applied"
    record = json.loads((project / "source.json").read_bytes())
    assert record["original_path"] == "../original/CAMERA.tif"
    assert record["original_filename"] == "CAMERA.tif"
    assert record["source_sha256"] == source_hash
    state = read_project(project)
    assert state["schema_version"] == 2 and state["development_approved"] is False
    assert (
        state["working_revision"]
        is state["accepted_revision"]
        is state["latest_result_revision"]
        is None
    )
    pixels, _ = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())
    assert not list((library / "Results Preview").iterdir())
    assert not list((library / "Comparisons").iterdir())
    reopened = command("--config", config, "open", "--project", project, "--headless")
    assert reopened.returncode == 0, reopened.stderr
    duplicate = library / "Inbox" / "OTHER.tif"
    duplicate.write_bytes(before)
    again = command("--config", config, "import", duplicate, "--subject", "different")
    assert again.returncode == 0, again.stderr
    assert Path(json.loads(again.stdout)["project"]) == project
    assert json.loads(again.stdout)["input_preserved"] is True
    assert duplicate.read_bytes() == before
    assert len(list((library / "Photos").iterdir())) == 1


def inventory(root):
    return {
        str(path.relative_to(root)): (
            stat.S_IMODE(path.lstat().st_mode),
            os.readlink(path)
            if path.is_symlink()
            else path.read_bytes()
            if path.is_file()
            else None,
        )
        for path in root.rglob("*")
    }


def library_fixture(tmp_path, *, sidecars=0):
    config_path, destination = configuration(tmp_path)
    config = storage.load_storage_config(config_path)
    storage.ensure_library(config)
    source = tiff(destination / "Inbox/CAMERA.tif", profile=srgb_profile())
    others = tuple(source.with_suffix(suffix) for suffix in (".xmp", ".json")[:sidecars])
    for index, path in enumerate(others):
        path.write_bytes(f"sidecar {index}".encode())
    return config_path, config, source, others


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[storage]\n",
        "[storage]\ndestination = 2\n",
        '[storage]\ndestination = ""\n',
        '[storage]\ndestination = ["../wrong"]\n',
        '[storage]\ndestination = "../wrong"\nextra = 1\n',
        '[storage]\ndestination = "../wrong"\n[unknown]\n',
        '[storage]\ndestination = "../wrong"\n[models]\nunknown = 1\n',
        '[storage]\ndestination = "../wrong"\n[models]\nsam_cache = 1\n',
        '[storage]\ndestination = "../wrong"\n[models]\nvitmatte_cache = "missing"\n',
        '[storage]\ndestination = "unterminated\n',
    ],
)
def test_configuration_rejects_invalid_settings_without_writes(tmp_path, text):
    config, _ = configuration(tmp_path)
    config.write_text(text)
    before = inventory(tmp_path)
    with pytest.raises((ProjectError, ValueError)):
        storage.load_storage_config(config)
    assert inventory(tmp_path) == before


def test_configuration_read_only_paths_are_bound_to_config_parent(tmp_path, monkeypatch):
    config, destination = configuration(tmp_path)
    (config.parent / "sam").mkdir()
    (config.parent / "matte").mkdir()
    config.write_text(
        config.read_text() + '[models]\nsam_cache = "sam"\nvitmatte_cache = "matte"\n'
    )
    before = inventory(tmp_path)
    monkeypatch.chdir(config.parent)
    first = storage.load_storage_config(config)
    monkeypatch.chdir(tmp_path)
    assert storage.load_storage_config(config) == first
    assert first.destination == destination
    assert first.sam_cache == config.parent / "sam"
    assert first.vitmatte_cache == config.parent / "matte"
    assert inventory(tmp_path) == before and not destination.exists()


@pytest.mark.parametrize(
    "component", ["", "Inbox", "Photos", "Results Preview", "Comparisons", "Inbox/.imports"]
)
@pytest.mark.parametrize("conflict", ["file", "link", "dangling"])
def test_managed_path_conflicts_never_change_existing_bytes_or_modes(tmp_path, component, conflict):
    _, destination = configuration(tmp_path)
    target = destination / component
    target.parent.mkdir(parents=True, exist_ok=True)
    if conflict == "file":
        target.write_bytes(b"sentinel")
    else:
        external = tmp_path / "external"
        if conflict == "link":
            external.mkdir()
            (external / "keep").write_bytes(b"outside")
        target.symlink_to(external, target_is_directory=True)
    before = inventory(tmp_path)
    with pytest.raises((ProjectError, OSError)):
        storage.ensure_library(storage.StorageConfig(destination))
    assert inventory(tmp_path) == before


def test_existing_modes_and_permission_denial_are_preserved(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    config.destination.chmod(0o751)
    (config.destination / "Photos").chmod(0o500)
    before = inventory(tmp_path)
    with pytest.raises(ProjectError, match="writable|inaccessible"):
        storage.import_photo(config, source, subject="photo", development={})
    assert inventory(tmp_path) == before
    assert stat.S_IMODE(config.destination.stat().st_mode) == 0o751


@pytest.mark.parametrize("mask", [0, 0o077, 0o777])
def test_new_private_directories_survive_restrictive_umask(tmp_path, mask):
    destination = tmp_path / "new/nested/library"
    code = """import os,sys
from pathlib import Path
from blackmask.library import StorageConfig,ensure_library
os.umask(int(sys.argv[1]))
ensure_library(StorageConfig(Path(sys.argv[2])))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(mask), str(destination)],
        check=False,
        env=dict(os.environ, PYTHONPATH=str(SOURCE_ROOT)),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o700
        for path in (tmp_path / "new").rglob("*")
        if path.is_dir()
    )


@pytest.mark.parametrize(
    "subject", ["", ".", "..", "a/b", "a\\b", "bad\nname", " padded ", "x" * 300]
)
def test_invalid_names_preserve_originals(tmp_path, subject):
    _, config, source, _ = library_fixture(tmp_path)
    before = source.read_bytes()
    with pytest.raises((ProjectError, ValueError)):
        storage.import_photo(config, source, subject=subject, development={})
    assert source.read_bytes() == before
    assert not list((config.destination / "Photos").iterdir())


def test_invalid_decode_and_low_space_never_move_source(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    before = source.read_bytes()
    with (
        patch("blackmask.library.check_space", side_effect=ProjectError("low space")),
        pytest.raises(ProjectError, match="space"),
    ):
        storage.import_photo(config, source, subject="photo", development={})
    assert source.read_bytes() == before
    source.write_bytes(b"invalid capture")
    with pytest.raises(ValueError):
        storage.import_photo(config, source, subject="photo", development={})
    assert source.read_bytes() == b"invalid capture"
    assert not list((config.destination / "Photos").iterdir())


@pytest.mark.parametrize("when", ["before", "after"])
@pytest.mark.parametrize("boundary", ["CAMERA.tif", "CAMERA.xmp", "CAMERA.json", "bundle"])
def test_resume_after_each_exclusive_move_retains_exact_originals(tmp_path, boundary, when):
    config_path, config, source, sidecars = library_fixture(tmp_path, sidecars=2)
    expected = {path.name: path.read_bytes() for path in (source, *sidecars)}
    original = storage._exclusive_rename

    def interrupted(start, end, **kwargs):
        selected = start.name == boundary and kwargs.get("source_directory") is not None
        if selected and when == "before":
            raise RuntimeError("injected interruption")
        original(start, end, **kwargs)
        if selected:
            raise RuntimeError("injected interruption")

    with (
        patch("blackmask.library._exclusive_rename", side_effect=interrupted),
        pytest.raises(RuntimeError, match="interruption"),
    ):
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    duplicate = config.destination / "Inbox/DIFFERENT.tif"
    duplicate.write_bytes(expected["CAMERA.tif"])
    owner = storage.import_photo(config, duplicate, subject="another", development={})
    if boundary == "bundle" and when == "after":
        assert owner.name == "project"
    else:
        assert owner == pending
    resumed = command("--config", config_path, "import-resume", pending)
    assert resumed.returncode == 0, resumed.stderr
    project = Path(json.loads(resumed.stdout)["project"])
    for name, value in expected.items():
        assert (project.parent / "original" / name).read_bytes() == value
        assert not (config.destination / "Inbox" / name).exists()
    assert duplicate.read_bytes() == expected["CAMERA.tif"]
    assert len(list((config.destination / "Photos").iterdir())) == 1
    assert read_project(project)["latest_result_revision"] is None


@pytest.mark.parametrize("corruption", ["path", "hash", "unknown", "project_identity"])
def test_malformed_pending_ownership_fails_closed_before_moves(tmp_path, corruption):
    _, config, source, _ = library_fixture(tmp_path)
    original = storage._exclusive_rename

    def stop_before_move(start, end, **kwargs):
        if kwargs.get("source_directory") is not None:
            raise RuntimeError("pause")
        return original(start, end, **kwargs)

    with (
        patch("blackmask.library._exclusive_rename", side_effect=stop_before_move),
        pytest.raises(RuntimeError),
    ):
        storage.import_photo(config, source, subject="photo", development={})
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    record = json.loads(pending.read_bytes())
    if corruption == "path":
        record["files"][0]["filename"] = "../outside"
    elif corruption == "hash":
        record["files"][0]["sha256"] = "0" * 64
    elif corruption == "unknown":
        record["unknown"] = True
    else:
        record["development"] = {"assume_srgb": True}
    pending.write_text(json.dumps(record))
    before = inventory(tmp_path)
    with pytest.raises(ProjectError):
        storage.resume_import(config, pending)
    assert inventory(tmp_path) == before


def test_read_only_status_of_imported_project_does_not_write(tmp_path):
    config_path, config, source, _ = library_fixture(tmp_path)
    project = storage.import_photo(
        config, source, subject="Érable snow", capture_date="2026-10-22", development={}
    )
    before = inventory(tmp_path)
    result = command("--config", config_path, "status", project)
    assert result.returncode == 0, result.stderr
    assert inventory(tmp_path) == before


def pause_before_originals(config, source, sidecars=()):
    original = storage._exclusive_rename

    def stop(start, end, **kwargs):
        if kwargs.get("source_directory") is not None:
            raise RuntimeError("pause before originals")
        return original(start, end, **kwargs)

    with (
        patch("blackmask.library._exclusive_rename", side_effect=stop),
        pytest.raises(RuntimeError),
    ):
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
    return next((config.destination / "Inbox/.imports").glob("*/import.json"))


def test_ambiguous_later_sidecar_is_rejected_before_first_move(tmp_path):
    _, config, source, sidecars = library_fixture(tmp_path, sidecars=1)
    pending = pause_before_originals(config, source, sidecars)
    (pending.parent / "bundle/original" / sidecars[0].name).write_bytes(sidecars[0].read_bytes())
    before = inventory(tmp_path)
    with pytest.raises(ProjectError, match="Ambiguous"):
        storage.resume_import(config, pending)
    assert inventory(tmp_path) == before


def test_published_and_recovery_identity_disagreement_blocks_duplicate_without_writes(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    original = source.read_bytes()
    storage.import_photo(config, source, subject="photo", development={})
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    record = json.loads(pending.read_bytes())
    record["folder_basename"] += "_changed"
    pending.write_text(json.dumps(record))
    duplicate = config.destination / "Inbox/duplicate.tif"
    duplicate.write_bytes(original)
    before = inventory(tmp_path)
    with pytest.raises(ProjectError, match="ownership|identity"):
        storage.import_photo(config, duplicate, subject="different", development={})
    assert inventory(tmp_path) == before


def test_all_new_import_directories_are_private(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    storage.import_photo(config, source, subject="photo", development={})
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o700
        for path in config.destination.rglob("*")
        if path.is_dir()
    )


def test_component_swap_at_creation_never_chmods_external_directory(tmp_path):
    outside = tmp_path / "external"
    outside.mkdir(mode=0o751)
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"external")
    destination = tmp_path / "new/library"
    original = os.mkdir

    def swap(name, mode=0o777, *, dir_fd=None):
        original(name, mode, dir_fd=dir_fd)
        if name == "new" and dir_fd is not None:
            os.rename("new", "preserved-new", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            os.symlink(outside, "new", dir_fd=dir_fd, target_is_directory=True)

    with (
        patch("blackmask.library.os.mkdir", side_effect=swap),
        pytest.raises((ProjectError, OSError)),
    ):
        storage.ensure_library(storage.StorageConfig(destination))
    assert stat.S_IMODE(outside.stat().st_mode) == 0o751
    assert sentinel.read_bytes() == b"external"
    assert list(outside.iterdir()) == [sentinel]


def test_cross_device_preflight_and_source_mutation_preserve_all_inputs(tmp_path):
    _, config, source, sidecars = library_fixture(tmp_path, sidecars=1)
    original = storage._file_details

    def other_device(directory, name):
        result = original(directory, name)
        if name.endswith(".xmp"):
            result["device"] += 1
        return result

    expected = {path.name: path.read_bytes() for path in (source, *sidecars)}
    with (
        patch("blackmask.library._file_details", side_effect=other_device),
        pytest.raises(ProjectError, match="Cross-device"),
    ):
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
    assert all(path.read_bytes() == expected[path.name] for path in (source, *sidecars))
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    source.write_bytes(b"external mutation")
    with pytest.raises(ProjectError, match="changed"):
        storage.resume_import(config, pending)
    assert source.read_bytes() == b"external mutation"
    assert sidecars[0].read_bytes() == expected[sidecars[0].name]
    assert not list((config.destination / "Photos").iterdir())


def test_pending_prefix_collision_and_malformed_other_owner_block_new_import(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    pending = pause_before_originals(config, source)
    record = json.loads(pending.read_bytes())
    record["source_sha256"] = record["source_sha256"][:12] + "0" * 52
    record["files"][0]["sha256"] = record["source_sha256"]
    pending.write_text(json.dumps(record))
    before = source.read_bytes()
    with pytest.raises(ProjectError, match="prefix collision"):
        storage.import_photo(config, source, subject="different", development={})
    assert source.read_bytes() == before
    pending.write_text('{"malformed":true}')
    with pytest.raises(ProjectError, match="ownership"):
        storage.import_photo(config, source, subject="different", development={})
    assert source.read_bytes() == before


@pytest.mark.parametrize("boundary", ["prepare", "CAMERA.tif", "bundle"])
def test_real_import_process_lock_crash_and_fresh_resume(tmp_path, boundary):
    config_path, config, source, _ = library_fixture(tmp_path)
    expected = source.read_bytes()
    prior = tiff(config.destination / "Inbox/PRIOR.tif", ramp() // 2, profile=srgb_profile())
    prior_project = storage.import_photo(config, prior, subject="prior", development={})
    code = """import sys
from pathlib import Path
from blackmask import library as storage
config=storage.load_storage_config(Path(sys.argv[1]))
boundary=sys.argv[3]
def hold():
    print('holding',flush=True)
    sys.stdin.readline()
create=storage.create_project
def prepare(*args,**kwargs):
    if boundary=='prepare': hold()
    return create(*args,**kwargs)
storage.create_project=prepare
rename=storage._exclusive_rename
def move(start,end,**kwargs):
    rename(start,end,**kwargs)
    if kwargs.get('source_directory') is not None and start.name==boundary: hold()
storage._exclusive_rename=move
storage.import_photo(config,Path(sys.argv[2]),subject='photo',development={})
"""
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", code, str(config_path), str(source), boundary],
        env=dict(
            os.environ, PYTHONPATH=str(SOURCE_ROOT), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "holding"
        duplicate = config.destination / "Inbox/SECOND.tif"
        duplicate.write_bytes(expected)
        with pytest.raises(ProjectError, match="busy"):
            storage.import_photo(config, duplicate, subject="second", development={})
        from blackmask.project import project_lock

        with project_lock(prior_project):
            assert read_project(prior_project)["latest_result_revision"] is None
        status_result = command("--config", config_path, "status", prior_project)
        assert status_result.returncode == 0, status_result.stderr
        process.kill()
        _, error = process.communicate(timeout=10)
        assert process.returncode < 0, error
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    pending = next(
        path
        for path in (config.destination / "Inbox/.imports").glob("*/import.json")
        if json.loads(path.read_bytes())["source_sha256"] == hashlib.sha256(expected).hexdigest()
    )
    resumed = command("--config", config_path, "import-resume", pending)
    assert resumed.returncode == 0, resumed.stderr
    project = Path(json.loads(resumed.stdout)["project"])
    assert (project.parent / "original/CAMERA.tif").read_bytes() == expected
    assert duplicate.read_bytes() == expected
    assert len(list((config.destination / "Photos").iterdir())) == 2


@pytest.mark.parametrize("publication", [2, 3, 4, 5, 6])
@pytest.mark.parametrize("when", ["before", "after"])
def test_import_record_publication_faults_resume_without_source_loss(tmp_path, publication, when):
    _, config, source, sidecars = library_fixture(tmp_path, sidecars=2)
    expected = {path.name: path.read_bytes() for path in (source, *sidecars)}
    original = storage._atomic_json
    calls = 0

    def interrupted(path, value, **kwargs):
        nonlocal calls
        calls += 1
        if calls == publication and when == "before":
            raise OSError("injected record failure")
        original(path, value, **kwargs)
        if calls == publication:
            raise OSError("injected record failure")

    with (
        patch("blackmask.library._atomic_json", side_effect=interrupted),
        pytest.raises(OSError, match="record failure"),
    ):
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    project = storage.resume_import(config, pending)
    for name, value in expected.items():
        assert (project.parent / "original" / name).read_bytes() == value
        assert not (config.destination / "Inbox" / name).exists()
    assert len(list((config.destination / "Photos").iterdir())) == 1


def assert_fresh_import_recovery(config_path, config, expected, pending):
    # Observe each physical original location independently of the recovery implementation.
    record = json.loads(pending.read_bytes())
    final = config.destination / "Photos" / record["folder_basename"]
    for name, value in expected.items():
        locations = [
            directory / name
            for directory in (
                config.destination / "Inbox",
                pending.parent / "bundle/original",
                final / "original",
            )
            if (directory / name).exists()
        ]
        assert len(locations) == 1
        assert locations[0].read_bytes() == value
    result = command("--config", config_path, "import-resume", pending)
    assert result.returncode == 0, result.stderr
    project = Path(json.loads(result.stdout)["project"])
    assert project == final / "project"
    assert {path.name: path.read_bytes() for path in (final / "original").iterdir()} == expected
    for name in expected:
        assert not (config.destination / "Inbox" / name).exists()
    assert not (pending.parent / "bundle").exists()
    assert len(list((config.destination / "Photos").iterdir())) == 1
    assert len(list((config.destination / "Inbox/.imports").iterdir())) == 1
    saved = json.loads(pending.read_bytes())
    assert saved["phase"] == "published"
    assert saved["source_sha256"] == hashlib.sha256(expected["CAMERA.tif"]).hexdigest()
    assert saved["photo_id"] == "P" + saved["source_sha256"][:12]
    source = json.loads((project / "source.json").read_bytes())
    assert source["library"]["photo_id"] == saved["photo_id"]
    assert source["library"]["folder_basename"] == saved["folder_basename"]
    state = read_project(project)
    assert (
        state["working_revision"]
        is state["accepted_revision"]
        is state["latest_result_revision"]
        is None
    )
    assert state["development_approved"] is False
    np.testing.assert_array_equal(load_developed(project, state["developed_id"])[0], ramp())
    assert not list((config.destination / "Results Preview").iterdir())
    assert not list((config.destination / "Comparisons").iterdir())


@pytest.mark.parametrize(
    "boundary,point",
    [
        (name, point)
        for name in ("CAMERA.tif", "CAMERA.xmp", "CAMERA.json")
        for point in ("file", "Inbox", "original")
    ]
    + [("bundle", "staging"), ("bundle", "Photos")],
)
@pytest.mark.parametrize("when", ["before", "after"])
def test_import_sync_faults_report_uncertainty_and_preserve_resumable_locations(
    tmp_path, boundary, point, when
):
    config_path, config, source, sidecars = library_fixture(tmp_path, sidecars=2)
    expected = {path.name: path.read_bytes() for path in (source, *sidecars)}
    original_move = storage._exclusive_rename
    original_sync = os.fsync
    target = None
    hits = 0

    def moved(start, end, **kwargs):
        nonlocal target
        original_move(start, end, **kwargs)
        if start.name == boundary and kwargs.get("source_directory") is not None:
            if point == "file":
                pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
                info = (pending.parent / "bundle/original" / boundary).stat()
            else:
                descriptor = kwargs[
                    "source_directory" if point in {"Inbox", "staging"} else "destination_directory"
                ]
                info = os.fstat(descriptor)
            target = (info.st_dev, info.st_ino)

    def sync(descriptor):
        nonlocal hits
        info = os.fstat(descriptor)
        selected = target == (info.st_dev, info.st_ino) and hits == 0
        if selected:
            assert stat.S_ISREG(info.st_mode) if point == "file" else stat.S_ISDIR(info.st_mode)
            hits += 1
            if when == "before":
                raise OSError("injected directory durability uncertainty")
        original_sync(descriptor)
        if selected:
            raise OSError("injected directory durability uncertainty")

    with (
        patch("blackmask.library._exclusive_rename", side_effect=moved),
        patch("blackmask.library.os.fsync", side_effect=sync),
        pytest.raises(OSError, match="uncertainty"),
    ):
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
    assert hits == 1, (boundary, point, when)
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    assert_fresh_import_recovery(config_path, config, expected, pending)


@pytest.mark.parametrize("publication", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("point", ["write", "flush", "file-sync", "publish", "parent-sync"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_internal_import_journal_faults_preserve_ownership_and_fresh_recovery(
    tmp_path, publication, point, when
):
    from blackmask import project as project_io

    config_path, config, source, sidecars = library_fixture(tmp_path, sidecars=2)
    expected = {path.name: path.read_bytes() for path in (source, *sidecars)}
    atomic = storage._atomic_json
    fdopen = os.fdopen
    fsync = os.fsync
    replace = os.replace
    publish_new = project_io._publish_new_file
    calls = 0
    active = False
    hits = 0
    journal_parent = None

    def fault(boundary, function, *args, **kwargs):
        nonlocal hits
        selected = active and boundary == point and hits == 0
        if selected:
            hits += 1
            if when == "before":
                raise OSError("injected internal journal uncertainty")
        result = function(*args, **kwargs)
        if selected:
            raise OSError("injected internal journal uncertainty")
        return result

    def journal(path, value, **kwargs):
        nonlocal calls, active, journal_parent
        assert path.name == "import.json"
        calls += 1
        active = calls == publication
        journal_parent = path.parent.stat()
        try:
            return atomic(path, value, **kwargs)
        finally:
            active = False

    class JournalWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def write(self, value):
            return fault("write", self.stream.write, value)

        def flush(self):
            return fault("flush", self.stream.flush)

    def opened(*args, **kwargs):
        stream = fdopen(*args, **kwargs)
        return JournalWriter(stream) if active else stream

    def synced(descriptor):
        info = os.fstat(descriptor)
        if active and stat.S_ISDIR(info.st_mode):
            assert (info.st_dev, info.st_ino) == (journal_parent.st_dev, journal_parent.st_ino)
            return fault("parent-sync", fsync, descriptor)
        return fault("file-sync", fsync, descriptor)

    def replaced(start, end):
        return fault("publish", replace, start, end)

    def first_publication(start, end):
        return fault("publish", publish_new, start, end)

    with (
        patch("blackmask.library._atomic_json", side_effect=journal),
        patch("blackmask.project.os.fdopen", side_effect=opened),
        patch("blackmask.project.os.fsync", side_effect=synced),
        patch("blackmask.project.os.replace", side_effect=replaced),
        patch("blackmask.project._publish_new_file", side_effect=first_publication),
        pytest.raises(OSError, match="internal journal uncertainty"),
    ):
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
    assert hits == 1, (publication, point, when)
    reservation = next((config.destination / "Inbox/.imports").iterdir())
    pending = reservation / "import.json"
    if pending.exists():
        assert_fresh_import_recovery(config_path, config, expected, pending)
    else:
        assert publication == 1
        assert point in {"write", "flush", "file-sync"} or (point == "publish" and when == "before")
        assert {path.name: path.read_bytes() for path in (source, *sidecars)} == expected
        before = inventory(config.destination)
        result = command("--config", config_path, "import-resume", pending)
        assert result.returncode == 1
        assert "ownership" in result.stderr
        assert inventory(config.destination) == before
        result = command("--config", config_path, "import", source, "--subject", "retry")
        assert result.returncode == 1
        assert "ownership" in result.stderr
        assert inventory(config.destination) == before
        assert not list((config.destination / "Photos").iterdir())


def test_native_exclusive_move_collision_preserves_source_and_arriving_destination(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    expected = source.read_bytes()
    pending = pause_before_originals(config, source)
    original = storage._exclusive_rename

    def collide(start, end, **kwargs):
        if start.name == source.name and kwargs.get("source_directory") is not None:
            destination = pending.parent / "bundle/original" / source.name
            destination.write_bytes(b"arriving sentinel")
        return original(start, end, **kwargs)

    with (
        patch("blackmask.library._exclusive_rename", side_effect=collide),
        pytest.raises(ProjectError, match="collision"),
    ):
        storage.resume_import(config, pending)
    assert source.read_bytes() == expected
    assert (pending.parent / "bundle/original" / source.name).read_bytes() == b"arriving sentinel"


def test_preparation_failure_is_preserved_and_retry_uses_same_reservation(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    expected = source.read_bytes()
    original = storage.create_project

    def fail_after_prepare(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("lost preparation response")

    with (
        patch("blackmask.library.create_project", side_effect=fail_after_prepare),
        pytest.raises(RuntimeError),
    ):
        storage.import_photo(config, source, subject="photo", development={})
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    old_attempt = next(pending.parent.glob(".prepare-*"))
    before = inventory(old_attempt)
    project = storage.resume_import(config, pending)
    assert inventory(old_attempt) == before
    assert (project.parent / "original" / source.name).read_bytes() == expected
    assert len(list((config.destination / "Inbox/.imports").iterdir())) == 1


def test_imported_project_still_reopens_without_original_locator(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    project = storage.import_photo(config, source, subject="photo", development={})
    original = project.parent / "original" / source.name
    original.rename(project.parent / "retained-original.tif")
    state = read_project(project)
    pixels, _ = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())


def test_configured_invalid_operation_has_actionable_cli_error(tmp_path):
    config_path, config, source, _ = library_fixture(tmp_path)
    project = storage.import_photo(config, source, subject="photo", development={})
    request_path = tmp_path / "request.json"
    request_path.write_text("[]")
    result = command("--config", config_path, "run", project, "--request", request_path)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "blackmask:" in result.stderr


def test_relative_direct_config_cannot_choose_a_cwd_library(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ProjectError, match="absolute|normalized"):
        storage.ensure_library(storage.StorageConfig(Path("library")))
    assert not (tmp_path / "library").exists()


def test_invalid_development_in_another_pending_owner_blocks_new_import(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    pending = pause_before_originals(config, source)
    record = json.loads(pending.read_bytes())
    record["development"] = {"unknown": True}
    pending.write_text(json.dumps(record))
    other = tiff(config.destination / "Inbox/OTHER.tif", ramp() // 2, profile=srgb_profile())
    before = inventory(tmp_path)
    with pytest.raises(ProjectError, match="ownership"):
        storage.import_photo(config, other, subject="other", development={})
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink"])
def test_invalid_original_path_fails_before_library_or_lock_creation(tmp_path, kind):
    destination = tmp_path / "library"
    inbox = destination / "Inbox"
    inbox.mkdir(parents=True)
    source = inbox / "capture.tif"
    if kind == "directory":
        source.mkdir()
    elif kind == "symlink":
        outside = tmp_path / "external.tif"
        outside.write_bytes(b"outside sentinel")
        source.symlink_to(outside)
    before = inventory(tmp_path)
    with pytest.raises((ProjectError, OSError)):
        storage.import_photo(
            storage.StorageConfig(destination), source, subject="photo", development={}
        )
    assert inventory(tmp_path) == before


@pytest.mark.parametrize(
    "route", ["open", "prepare", "matte", "resume", "doctor-sam", "doctor-vitmatte"]
)
@pytest.mark.parametrize("explicit", [False, True])
def test_cli_routes_model_config_with_explicit_flag_precedence(
    tmp_path, monkeypatch, capsys, route, explicit
):
    from blackmask import cli

    config_path, config, source, _ = library_fixture(tmp_path)
    project = storage.import_photo(config, source, subject="photo", development={})
    sam = tmp_path / "sam-config"
    matte = tmp_path / "matte-config"
    flag = tmp_path / "explicit"
    for path in (sam, matte, flag):
        path.mkdir()
    config_path.write_text(
        config_path.read_text()
        + f"[models]\nsam_cache = {json.dumps(str(sam))}\nvitmatte_cache = {json.dumps(str(matte))}\n"
    )
    monkeypatch.setenv("BLACKMASK_SAM_CACHE", str(tmp_path / "unused-sam-environment"))
    monkeypatch.setenv("BLACKMASK_VITMATTE_CACHE", str(tmp_path / "unused-matte-environment"))
    selected = {}

    def open_window(project, model_cache, sam_cache, *, storage_config=None):
        assert storage_config.destination == config.destination
        selected.update(matte=str(model_cache), sam=str(sam_cache))

    def run(project, request, *, model_cache, request_file, storage_config=None):
        assert storage_config.destination == config.destination
        return {"selected": str(model_cache)}

    def resume(project, operation, *, model_cache, source, storage_config=None):
        assert storage_config.destination == config.destination
        return {"selected": str(model_cache)}

    def doctor(path, model_cache, model):
        return {"selected": str(model_cache)}

    monkeypatch.setattr("blackmask.viewer.open_viewer", open_window)
    monkeypatch.setattr(cli, "apply_operation", run)
    monkeypatch.setattr(cli, "resume_operation", resume)
    monkeypatch.setattr(cli, "doctor", doctor)
    arguments = ["blackmask", "--config", str(config_path)]
    if route == "open":
        arguments += ["open", "--project", str(project)]
        if explicit:
            arguments += ["--model-cache", str(flag), "--sam-cache", str(flag)]
    elif route.startswith("doctor"):
        arguments += ["doctor", "--project", str(project), "--model", route.removeprefix("doctor-")]
    elif route == "resume":
        arguments += ["resume", str(project), "--operation", "matte-example"]
    else:
        request = tmp_path / "request.json"
        request.write_text(json.dumps({"kind": route}))
        arguments += ["run", str(project), "--request", str(request)]
    if explicit and route != "open":
        arguments += ["--model-cache", str(flag)]
    monkeypatch.setattr(sys, "argv", arguments)
    assert cli.main() == 0
    if route == "open":
        assert selected == {
            "matte": str(flag if explicit else matte),
            "sam": str(flag if explicit else sam),
        }
    else:
        result = json.loads(capsys.readouterr().out)
        assert result["selected"] == str(
            flag if explicit else sam if route in {"prepare", "doctor-sam"} else matte
        )
    assert not list(sam.iterdir()) and not list(matte.iterdir())


def test_configured_status_does_not_create_a_missing_library(tmp_path):
    from blackmask.project import create_project

    config_path, destination = configuration(tmp_path)
    source = tiff(tmp_path / "standalone.tif", profile=srgb_profile())
    project = create_project(source, tmp_path / "project", {})
    before = inventory(tmp_path)
    result = command("--config", config_path, "status", project)
    assert result.returncode == 0, result.stderr
    assert not destination.exists()
    assert inventory(tmp_path) == before


def test_oversized_photo_name_is_rejected_before_creating_a_lock(tmp_path):
    _, config, source, _ = library_fixture(tmp_path)
    before = inventory(tmp_path)
    with pytest.raises(ProjectError, match="component limit"):
        storage.import_photo(config, source, subject="x" * 300, development={})
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("mask", [0o000, 0o022, 0o077, 0o777])
@pytest.mark.parametrize("action", ["import", "resume"])
def test_actual_import_and_preparation_resume_preserve_private_access_and_existing_modes(
    tmp_path, mask, action
):
    config_path, config, source, sidecars = library_fixture(tmp_path, sidecars=1)
    expected = {path.name: path.read_bytes() for path in (source, *sidecars)}
    source.chmod(0o640)
    config.destination.chmod(0o750)
    lock = config.destination / ".import.lock"
    lock.write_bytes(b"")
    lock.chmod(0o640)
    if action == "resume":
        with (
            patch("blackmask.library.create_project", side_effect=OSError("before preparation")),
            pytest.raises(OSError, match="before preparation"),
        ):
            storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
        pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
        pending.chmod(0o640)
        arguments = ["import-resume", str(pending)]
    else:
        arguments = ["import", str(source), "--subject", "photo", "--sidecar", str(sidecars[0])]
    existing_directories = {
        path: stat.S_IMODE(path.stat().st_mode)
        for path in [config.destination, *config.destination.rglob("*")]
        if path.is_dir()
    }
    code = """import json,os,sys
from blackmask.cli import main
mask=int(sys.argv[1]);os.umask(mask)
sys.argv=['blackmask',*sys.argv[2:]]
main()
observed=os.umask(mask)
assert observed==mask, (observed,mask)
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(mask), "--config", str(config_path), *arguments],
        env=dict(os.environ, PYTHONPATH=str(SOURCE_ROOT), HF_HUB_OFFLINE="1"),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    project = Path(json.loads(result.stdout)["project"])
    assert stat.S_IMODE(lock.stat().st_mode) == 0o640
    for path, mode in existing_directories.items():
        if action == "resume" and path.is_relative_to(pending.parent / "bundle"):
            path = project.parent / path.relative_to(pending.parent / "bundle")
        assert stat.S_IMODE(path.stat().st_mode) == mode
    for path in config.destination.rglob("*"):
        if path.is_dir() and path not in existing_directories:
            assert stat.S_IMODE(path.stat().st_mode) == 0o700
    for name, value in expected.items():
        assert (project.parent / "original" / name).read_bytes() == value
        assert not (config.destination / "Inbox" / name).exists()
    assert stat.S_IMODE((project.parent / "original" / source.name).stat().st_mode) == 0o640
    journal = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    assert stat.S_IMODE(journal.stat().st_mode) == (0o640 if action == "resume" else 0o600)
    for path in project.rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
    state = read_project(project)
    assert state["accepted_revision"] is state["latest_result_revision"] is None
    np.testing.assert_array_equal(load_developed(project, state["developed_id"])[0], ramp())
    assert len(list((config.destination / "Photos").iterdir())) == 1


@pytest.mark.parametrize("duplicate", [True, False])
def test_contradictory_staged_and_published_owner_blocks_every_import_without_writes(
    tmp_path, duplicate
):
    _, config, source, _ = library_fixture(tmp_path)
    original = source.read_bytes()
    project = storage.import_photo(config, source, subject="photo", development={})
    pending = next((config.destination / "Inbox/.imports").glob("*/import.json"))
    staged = pending.parent / "bundle"
    staged.mkdir()
    (staged / "retained.txt").write_bytes(b"uncertain staged ownership")
    incoming = config.destination / "Inbox/OTHER.tif"
    if duplicate:
        incoming.write_bytes(original)
    else:
        tiff(incoming, ramp() // 2, profile=srgb_profile())
    before = inventory(tmp_path)
    with pytest.raises(ProjectError, match="Both staged and final"):
        storage.import_photo(config, incoming, subject="other", development={})
    assert inventory(tmp_path) == before
    with pytest.raises(ProjectError, match="Both staged and final"):
        storage.resume_import(config, pending)
    assert inventory(tmp_path) == before
    assert (project.parent / "original/CAMERA.tif").read_bytes() == original


def ownership_command_fixture(tmp_path, action):
    config_path, config, source, sidecars = library_fixture(tmp_path, sidecars=1)
    expected = {
        path.name: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in (source, *sidecars)
    }
    if action == "import":
        prior = tiff(config.destination / "Inbox/PRIOR.tif", ramp() // 2, profile=srgb_profile())
        storage.import_photo(config, prior, subject="prior", development={})
        arguments = ["import", source, "--subject", "photo", "--sidecar", sidecars[0]]
    elif action == "duplicate":
        storage.import_photo(config, source, subject="photo", development={}, sidecars=sidecars)
        duplicate = config.destination / "Inbox/COPY.tif"
        duplicate.write_bytes(expected[source.name][0])
        arguments = ["import", duplicate, "--subject", "different"]
    else:
        assert action == "resume"
        pending = pause_before_originals(config, source, sidecars)
        arguments = ["import-resume", pending]
    return config_path, config, expected, arguments


@pytest.mark.parametrize("location", ["Photos", "Inbox/.imports"])
@pytest.mark.parametrize("action", ["import", "duplicate", "resume"])
def test_regular_finder_metadata_preserves_successful_import_duplicate_and_resume(
    tmp_path, location, action
):
    config_path, config, expected, arguments = ownership_command_fixture(tmp_path, action)
    metadata = config.destination / location / ".DS_Store"
    metadata.write_bytes(b"\x00\xffsynthetic Finder metadata; preserve without parsing")
    metadata.chmod(0o640)
    before = inventory(tmp_path)
    result = command("--config", config_path, *arguments)
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    source_hash = hashlib.sha256(expected["CAMERA.tif"][0]).hexdigest()
    project = config.destination / "Photos" / f"P{source_hash[:12]}_undated_photo/project"
    assert outcome["status"] == "ready" and Path(outcome["project"]) == project
    if action == "duplicate":
        assert outcome["input_preserved"] is True
        assert inventory(tmp_path) == before
    for name, (value, mode) in expected.items():
        original = project.parent / "original" / name
        assert original.read_bytes() == value
        assert stat.S_IMODE(original.stat().st_mode) == mode
    assert metadata.read_bytes() == before[str(metadata.relative_to(tmp_path))][1]
    assert stat.S_IMODE(metadata.lstat().st_mode) == 0o640
    state = read_project(project)
    assert (
        state["working_revision"]
        is state["accepted_revision"]
        is state["latest_result_revision"]
        is None
    )
    assert state["development_approved"] is False
    pixels, _ = load_developed(project, state["developed_id"])
    np.testing.assert_array_equal(pixels, ramp())
    assert np.any(pixels % 257 != 0)
    assert not list((config.destination / "Results Preview").iterdir())
    assert not list((config.destination / "Comparisons").iterdir())


@pytest.mark.parametrize("location", ["Photos", "Inbox/.imports"])
@pytest.mark.parametrize("action", ["import", "duplicate", "resume"])
@pytest.mark.parametrize(
    "kind",
    [
        "directory",
        "symlink-file",
        "symlink-directory",
        "dangling",
        "unknown-file",
        "unknown-directory",
        "hidden-file",
        "lookalike",
        "case-variant",
        "fifo",
    ],
)
def test_nonregular_finder_and_unknown_ownership_entries_fail_closed_without_writes(
    tmp_path, location, action, kind
):
    config_path, config, _, arguments = ownership_command_fixture(tmp_path, action)
    name = {
        "unknown-file": "unexpected",
        "unknown-directory": "unexpected",
        "hidden-file": ".unexpected",
        "lookalike": ".DS_Store.extra",
        "case-variant": ".ds_store",
    }.get(kind, ".DS_Store")
    entry = config.destination / location / name
    if kind in {"directory", "unknown-directory"}:
        entry.mkdir()
        (entry / "sentinel").write_bytes(b"unknown owned directory, preserve")
    elif kind in {"symlink-file", "symlink-directory", "dangling"}:
        outside = tmp_path / "outside-library"
        if kind == "symlink-file":
            outside.write_bytes(b"never follow this target")
        elif kind == "symlink-directory":
            outside.mkdir()
            (outside / "sentinel").write_bytes(b"never follow this directory")
        entry.symlink_to(outside, target_is_directory=kind == "symlink-directory")
    elif kind == "fifo":
        os.mkfifo(entry, 0o600)
    else:
        entry.write_bytes(b"unknown regular entry, preserve")
    before = inventory(tmp_path)
    result = command("--config", config_path, *arguments)
    assert result.returncode == 1
    assert "blackmask:" in result.stderr and "Traceback" not in result.stderr
    assert inventory(tmp_path) == before
