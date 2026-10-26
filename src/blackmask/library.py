"""Configured local library ownership and explicitly resumed original imports."""

import hashlib
import os
import re
import stat
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from io import BufferedReader
from pathlib import Path
from typing import Any

from .project import (
    ImportedPhotoIdentity,
    ProjectError,
    _atomic_json,
    _directory,
    _exclusive_rename,
    _file_lock,
    _filename_component,
    _private_temporary_directory,
    _read_json,
    _root,
    _sync_directory,
    _validate_imported_source,
    check_space,
    create_project,
    read_project,
)

FOLDERS = ("Inbox", "Photos", "Results Preview", "Comparisons")


@dataclass(frozen=True)
class StorageConfig:
    destination: Path
    sam_cache: Path | None = None
    vitmatte_cache: Path | None = None


class ResultPreviewNameTooLong(ProjectError):
    """An exact frozen gallery name cannot fit its selected filesystem."""

    def __init__(self, required_bytes: int, component_limit: int):
        self.required_bytes = required_bytes
        self.component_limit = component_limit
        super().__init__(
            f"Result preview name requires {required_bytes} bytes; filesystem component limit "
            f"is {component_limit}; frozen photo name preserved without rename or alias"
        )


def _component_limit(path: Path) -> int:
    try:
        with _directory(path) as descriptor:
            return os.fpathconf(descriptor, "PC_NAME_MAX")
    except FileNotFoundError:
        if path.parent == path:
            raise
        return _component_limit(path.parent)


def _check_result_preview_capacity(config: StorageConfig, folder_name_bytes: int) -> None:
    required = folder_name_bytes + len(os.fsencode(".jpg"))
    limit = _component_limit(config.destination / "Results Preview")
    if limit <= 0:
        raise ProjectError("Result preview filesystem component limit is unavailable")
    if required > limit:
        raise ResultPreviewNameTooLong(required, limit)


def validate_library_project(project: Path, config: StorageConfig | None) -> Path | None:
    """Bind managed writes to explicit library context without requiring the original."""
    project = _root(project)
    source = _read_json(project, "source.json")
    _validate_imported_source(source)
    if "library" not in source:
        return None
    if config is None:
        raise ProjectError("Imported project writes require matching explicit --config FILE")
    _validate_config_paths(config)
    bundle = config.destination / "Photos" / source["library"]["folder_basename"]
    if project != bundle / "project":
        raise ProjectError("Project does not match the configured library and frozen photo name")
    _inspect_directory(bundle, missing=False)
    return bundle


def _inspect_directory(path: Path, *, missing: bool = True, writable: bool = False) -> None:
    try:
        with _directory(path) as descriptor:
            if writable and not os.access(
                ".", os.W_OK | os.X_OK, dir_fd=descriptor, effective_ids=True
            ):
                raise ProjectError(f"Directory is not writable: {path}")
    except FileNotFoundError:
        if not missing:
            raise ProjectError(f"Configured directory is missing: {path}") from None
        # Check the nearest existing parent, including its permissions, before creating anything.
        if path.parent == path:
            raise
        _inspect_directory(path.parent, missing=True, writable=writable)
    except OSError as error:
        raise ProjectError(f"Unsafe or inaccessible directory {path}: {error}") from error


def _validate_config_paths(config: StorageConfig) -> None:
    for path in (config.destination, config.sam_cache, config.vitmatte_cache):
        if path is not None and (not path.is_absolute() or Path(os.path.abspath(path)) != path):
            raise ProjectError(
                "Storage paths must be absolute and normalized by the selected config"
            )
    for path in (config.destination, *(config.destination / name for name in FOLDERS)):
        _inspect_directory(path, writable=True)
    _inspect_directory(config.destination / "Inbox/.imports", writable=True)
    for model in (config.sam_cache, config.vitmatte_cache):
        if model is not None:
            _inspect_directory(model, missing=False)


def load_storage_config(path: Path) -> StorageConfig:
    """Read an explicitly selected TOML file; never search or create a destination."""
    path = Path(os.path.abspath(path))
    with _directory(path.parent) as descriptor:
        opened = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(opened, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ProjectError("Storage configuration must be a regular file")
            value = tomllib.load(stream)
    if set(value) - {"storage", "models"}:
        raise ProjectError("Unknown storage configuration table")
    storage = value.get("storage")
    models = value.get("models", {})
    if not isinstance(storage, dict) or set(storage) != {"destination"}:
        raise ProjectError("Storage requires destination only; missing or unknown key")
    if not isinstance(models, dict) or set(models) - {"sam_cache", "vitmatte_cache"}:
        raise ProjectError("Unknown model configuration key")

    def selected(value: object) -> Path:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ProjectError("Configured paths must be nonempty strings")
        return Path(os.path.abspath(path.parent / value))

    config = StorageConfig(
        selected(storage["destination"]),
        selected(models["sam_cache"]) if "sam_cache" in models else None,
        selected(models["vitmatte_cache"]) if "vitmatte_cache" in models else None,
    )
    _validate_config_paths(config)
    return config


def ensure_library(config: StorageConfig) -> None:
    """Create only validated missing directories, preserving all existing modes and contents."""
    _validate_config_paths(config)
    for path in (config.destination, *(config.destination / name for name in FOLDERS)):
        with _directory(path, create=True):
            pass
    with _directory(config.destination / "Inbox/.imports", create=True):
        pass
    _sync_directory(config.destination)


def _development_settings(value: object) -> dict[str, Any]:
    # Recovery records must be validated before choosing any new source owner.
    # Actual decoding and photographic conversion remain exclusively in ingest.
    if (
        not isinstance(value, dict)
        or set(value) - {"assume_srgb", "white_balance", "jpeg_sdr_primary"}
        or type(value.get("assume_srgb", False)) is not bool
        or type(value.get("jpeg_sdr_primary", False)) is not bool
        or value.get("white_balance", "camera") not in ("camera", "daylight")
    ):
        raise ProjectError("Invalid import development options")
    return value


@contextmanager
def _original_file(directory: Path, name: str) -> Iterator[tuple[BufferedReader, int]]:
    _filename_component(name)
    with _directory(directory) as parent:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with open(descriptor, "rb", closefd=True) as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ProjectError(f"Original must be a regular file: {directory / name}")
            yield stream, parent


def _file_details(directory: Path, name: str) -> dict[str, Any]:
    with _original_file(directory, name) as (stream, parent):
        before = os.fstat(stream.fileno())
        hashed = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        signature = lambda info: (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )
        if signature(before) != signature(after) or signature(current) != signature(after):
            raise ProjectError(f"Original changed during hashing: {directory / name}")
        return {
            "filename": name,
            "sha256": hashed,
            "size_bytes": after.st_size,
            "device": after.st_dev,
            "inode": after.st_ino,
        }


def _matches(details: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(details[key] == expected[key] for key in ("filename", "sha256", "size_bytes"))


def _read_import(directory: Path) -> dict[str, Any]:
    try:
        _inspect_directory(directory, missing=False)
        record = _read_json(directory, "import.json")
        if (
            set(record)
            != {
                "schema_version",
                "kind",
                "photo_id",
                "folder_basename",
                "source_sha256",
                "development",
                "phase",
                "files",
            }
            or type(record["schema_version"]) is not int
            or record["schema_version"] != 2
            or record["kind"] != "photo-import"
            or not isinstance(record["source_sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", record["source_sha256"]) is None
            or record["photo_id"] != "P" + record["source_sha256"][:12]
            or directory.name != record["photo_id"]
            or not _filename_component(record["folder_basename"]).startswith(
                record["photo_id"] + "_"
            )
            or record["phase"] not in {"preparing", "moving", "published"}
            or not isinstance(record["development"], dict)
            or not isinstance(record["files"], list)
            or not record["files"]
        ):
            raise ValueError("invalid identity or fields")
        names: set[str] = set()
        for item in record["files"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"filename", "sha256", "size_bytes"}
                or _filename_component(item["filename"]) in names
                or not isinstance(item["sha256"], str)
                or re.fullmatch("[0-9a-f]{64}", item["sha256"]) is None
                or type(item["size_bytes"]) is not int
                or item["size_bytes"] < 0
            ):
                raise ValueError("invalid original record")
            names.add(item["filename"])
        if record["files"][0]["sha256"] != record["source_sha256"]:
            raise ValueError("source hash mismatch")
        _development_settings(record["development"])
        if any(
            Path(item["filename"]).stem != Path(record["files"][0]["filename"]).stem
            for item in record["files"][1:]
        ):
            raise ValueError("sidecar filename stem mismatch")
        for path in (
            directory / "bundle",
            directory / "bundle/original",
            directory / "bundle/project",
        ):
            if os.path.lexists(path):
                _inspect_directory(path, missing=False)
        return record
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise ProjectError(
            f"Invalid import ownership; preserve and inspect {directory}: {error}"
        ) from error


def _identity(record: dict[str, Any]) -> ImportedPhotoIdentity:
    return {
        "photo_id": record["photo_id"],
        "folder_basename": record["folder_basename"],
        "original_filename": record["files"][0]["filename"],
        "sidecars": [
            {"filename": item["filename"], "sha256": item["sha256"]} for item in record["files"][1:]
        ],
    }


def _check_source_ownership(source: dict[str, Any], record: dict[str, Any]) -> None:
    expected = _identity(record)
    if (
        source.get("source_sha256") != record["source_sha256"]
        or source.get("original_filename") != expected["original_filename"]
        or source.get("library")
        != {key: expected[key] for key in ("photo_id", "folder_basename", "sidecars")}
        or source["metadata"].get("development_options") != record["development"]
    ):
        raise ProjectError("Import project and recovery ownership disagree")


def _validate_prepared_project(project: Path, record: dict[str, Any]) -> None:
    read_project(project)
    _check_source_ownership(_read_json(project, "source.json"), record)


def _validate_bundle(bundle: Path, record: dict[str, Any]) -> Path:
    _inspect_directory(bundle, missing=False)
    project = bundle / "project"
    _validate_prepared_project(project, record)
    for item in record["files"]:
        if not _matches(_file_details(bundle / "original", item["filename"]), item):
            raise ProjectError(f"Imported original hash mismatch: {bundle}")
    return project


def _check_import_locations(config: StorageConfig, directory: Path, record: dict[str, Any]) -> Path:
    final = config.destination / "Photos" / record["folder_basename"]
    if os.path.lexists(final) and os.path.lexists(directory / "bundle"):
        raise ProjectError(f"Both staged and final import exist; preserve {directory}")
    if record["phase"] == "published" and not os.path.lexists(final):
        raise ProjectError(f"Published import is missing; preserve {directory}")
    return final


def _existing_owner(config: StorageConfig, source_hash: str) -> Path | None:
    published: dict[str, Path] = {}
    for bundle in (config.destination / "Photos").iterdir():
        if bundle.name == ".DS_Store" and stat.S_ISREG(bundle.lstat().st_mode):
            continue
        _inspect_directory(bundle, missing=False)
        source = _read_json(bundle / "project", "source.json")
        _validate_imported_source(source)
        identity = source.get("library")
        if not isinstance(identity, dict) or identity["folder_basename"] != bundle.name:
            raise ProjectError(f"Invalid published photo ownership: {bundle}")
        key = source["source_sha256"]
        if key in published:
            raise ProjectError("Multiple published owners for the same source; preserve both")
        if key[:12] == source_hash[:12] and key != source_hash:
            raise ProjectError("Photo ID prefix collision; originals preserved")
        published[key] = bundle
    pending: Path | None = None
    for directory in (config.destination / "Inbox/.imports").iterdir():
        if directory.name == ".DS_Store" and stat.S_ISREG(directory.lstat().st_mode):
            continue
        record = _read_import(directory)
        key = record["source_sha256"]
        if key[:12] == source_hash[:12] and key != source_hash:
            raise ProjectError("Pending photo ID prefix collision; originals preserved")
        if record["phase"] == "published" and key not in published:
            raise ProjectError(f"Published import owner is missing: {directory}")
        if key in published:
            _check_source_ownership(_read_json(published[key] / "project", "source.json"), record)
        _check_import_locations(config, directory, record)
        if key == source_hash:
            pending = directory / "import.json"
    if source_hash in published:
        bundle = published[source_hash]
        source = _read_json(bundle / "project", "source.json")
        read_project(bundle / "project")
        if _file_details(bundle / "original", source["original_filename"])["sha256"] != source_hash:
            raise ProjectError(f"Published original hash mismatch: {bundle}")
        for item in source["library"]["sidecars"]:
            if _file_details(bundle / "original", item["filename"])["sha256"] != item["sha256"]:
                raise ProjectError(f"Published sidecar hash mismatch: {bundle}")
        return bundle / "project"
    return pending


def import_photo(
    config: StorageConfig,
    source: Path,
    *,
    subject: str,
    capture_date: str | None = None,
    development: dict[str, Any],
    sidecars: tuple[Path, ...] = (),
) -> Path:
    """Move declared Inbox originals once, or return their exact existing owner/recovery."""
    subject = _filename_component(subject)
    _development_settings(development)
    if subject.strip() != subject:
        raise ProjectError("Subject must not start or end with whitespace")
    if capture_date is not None and (
        not isinstance(capture_date, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", capture_date) is None
        or date.fromisoformat(capture_date).isoformat() != capture_date
    ):
        raise ProjectError("Capture date must be YYYY-MM-DD")
    source = Path(os.path.abspath(source))
    selected = (source, *(Path(os.path.abspath(path)) for path in sidecars))
    inbox = config.destination / "Inbox"
    if any(path.parent != inbox for path in selected):
        raise ProjectError("Select regular files directly inside this configured Inbox")
    if any(path.stem != source.stem for path in selected[1:]):
        raise ProjectError("Declared sidecars must have the original's filename stem")
    _validate_config_paths(config)
    name_suffix = f"_{capture_date or 'undated'}_{subject}"
    with _directory(inbox) as inbox_descriptor:
        # P plus twelve hexadecimal characters precede this frozen readable suffix.
        if 13 + len(os.fsencode(name_suffix)) > os.fpathconf(inbox_descriptor, "PC_NAME_MAX"):
            raise ProjectError("Photo folder name exceeds the filesystem component limit")
    proposed_bytes = 13 + len(os.fsencode(name_suffix))
    if proposed_bytes > _component_limit(config.destination / "Photos"):
        raise ProjectError("Photo folder name exceeds the Photos filesystem component limit")
    _check_result_preview_capacity(config, proposed_bytes)
    # Invalid selected paths must fail before creating even a lock or empty folders.
    for path in selected:
        with _original_file(inbox, path.name):
            pass
    check_space(config.destination, source.stat().st_size * 3 + 1024**2)
    # Hashing/decoding/ownership decisions are serialized, including retries after process death.
    with _file_lock(config.destination / ".import.lock", "Library import"):
        ensure_library(config)
        _check_result_preview_capacity(config, proposed_bytes)
        details = [_file_details(inbox, path.name) for path in selected]
        if len({(item["device"], item["inode"]) for item in details}) != len(details):
            raise ProjectError("Original and sidecars must be distinct regular files")
        source_hash = details[0]["sha256"]
        owner = _existing_owner(config, source_hash)
        if owner is not None:
            return owner
        photo_id = "P" + source_hash[:12]
        basename = photo_id + name_suffix
        check_space(inbox, details[0]["size_bytes"] * 3 + 1024**2)
        directory = inbox / ".imports" / photo_id
        if os.path.lexists(directory):
            raise ProjectError(f"Import reservation collision; preserve {directory}")
        with _directory(directory, create=True):
            pass
        record = {
            "schema_version": 2,
            "kind": "photo-import",
            "photo_id": photo_id,
            "folder_basename": basename,
            "source_sha256": source_hash,
            "development": development,
            "phase": "preparing",
            "files": [
                {key: item[key] for key in ("filename", "sha256", "size_bytes")} for item in details
            ],
        }
        _atomic_json(directory / "import.json", record, replace_existing=False)
        return _resume_locked(config, directory)


def resume_import(config: StorageConfig, pending: Path) -> Path:
    """Inspect actual saved locations and resume only this selected library's import."""
    pending = Path(os.path.abspath(pending))
    if (
        pending.name != "import.json"
        or pending.parent.parent != config.destination / "Inbox/.imports"
    ):
        raise ProjectError("Select the exact import.json in this configured library")
    _validate_config_paths(config)
    # Resume never creates a replacement library for a missing or changed configuration.
    _inspect_directory(config.destination / "Inbox/.imports", missing=False)
    with _file_lock(config.destination / ".import.lock", "Library import"):
        record = _read_import(pending.parent)
        _existing_owner(config, record["source_sha256"])
        return _resume_locked(config, pending.parent)


def _resume_locked(config: StorageConfig, directory: Path) -> Path:
    record = _read_import(directory)
    bundle = directory / "bundle"
    final = _check_import_locations(config, directory, record)
    inbox = config.destination / "Inbox"
    if os.path.lexists(final):
        project = _validate_bundle(final, record)
        _sync_directory(final.parent)
        _sync_directory(directory)
        record["phase"] = "published"
        _atomic_json(directory / "import.json", record)
        return project
    if record["phase"] == "moving":
        for path in (bundle, bundle / "original", bundle / "project"):
            _inspect_directory(path, missing=False)
    for path in (bundle, bundle / "original"):
        with _directory(path, create=True):
            pass
    project = bundle / "project"
    if not os.path.lexists(project):
        if record["phase"] != "preparing":
            raise ProjectError(f"Prepared project is missing; preserve {directory}")
        for item in record["files"]:
            if not _matches(_file_details(inbox, item["filename"]), item):
                raise ProjectError(f"Inbox original changed; preserve {directory}")
        attempt = _private_temporary_directory(directory, ".prepare-")
        create_project(
            inbox / record["files"][0]["filename"],
            attempt,
            record["development"],
            imported_photo=_identity(record),
        )
        read_project(attempt)
        _exclusive_rename(attempt, project)
        _sync_directory(bundle)
        _sync_directory(directory)
    _validate_prepared_project(project, record)
    with _directory(inbox) as inbox_descriptor, _directory(bundle / "original") as originals:
        devices = {
            os.fstat(inbox_descriptor).st_dev,
            os.fstat(originals).st_dev,
            final.parent.stat().st_dev,
        }
        identities: set[tuple[int, int]] = set()
        for item in record["files"]:
            locations = 0
            for parent in (inbox, bundle / "original"):
                try:
                    details = _file_details(parent, item["filename"])
                except FileNotFoundError:
                    continue
                if not _matches(details, item):
                    raise ProjectError(f"Import original changed; preserve {directory}")
                locations += 1
                devices.add(details["device"])
                identity = (details["device"], details["inode"])
                if identity in identities:
                    raise ProjectError(
                        f"Original aliases another selected file; preserve {directory}"
                    )
                identities.add(identity)
            if locations != 1:
                raise ProjectError(f"Ambiguous original locations; preserve {directory}")
        if len(devices) != 1:
            raise ProjectError("Cross-device import refused before original moves")
        record["phase"] = "moving"
        _atomic_json(directory / "import.json", record)
        for item in record["files"]:
            name = item["filename"]
            incoming = os.path.lexists(inbox / name)
            owned = os.path.lexists(bundle / "original" / name)
            if incoming == owned:
                raise ProjectError(f"Ambiguous original locations; preserve {directory}: {name}")
            if incoming:
                if not _matches(_file_details(inbox, name), item):
                    raise ProjectError(f"Inbox original changed; preserve {directory}")
                _exclusive_rename(
                    Path(name),
                    Path(name),
                    source_directory=inbox_descriptor,
                    destination_directory=originals,
                )
            if not _matches(_file_details(bundle / "original", name), item):
                raise ProjectError(f"Moved original changed; preserve {directory}")
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=originals)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.fsync(inbox_descriptor)
            os.fsync(originals)
            _atomic_json(directory / "import.json", record)
    _validate_bundle(bundle, record)
    for directory_name, children, _ in os.walk(bundle, topdown=False, followlinks=False):
        for name in children:
            _inspect_directory(Path(directory_name) / name, missing=False)
        _sync_directory(Path(directory_name))
    with _directory(directory) as staging, _directory(final.parent) as photos:
        _exclusive_rename(
            Path("bundle"), Path(final.name), source_directory=staging, destination_directory=photos
        )
        os.fsync(staging)
        os.fsync(photos)
    record["phase"] = "published"
    _atomic_json(directory / "import.json", record)
    return final / "project"
