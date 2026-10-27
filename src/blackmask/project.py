"""Canonical project identity, writer lock and safe publication boundaries."""

import copy
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import sys
import tempfile
import tomllib
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
import tifffile
import tomli_w

from .guidance import validate_guides
from .ingest import RGB16, decode_source, srgb_profile, write_developed
from .recipe import Recipe

RESERVE_BYTES = 10 * 1024**3


class ProjectError(ValueError):
    """Project is busy, stale, incomplete or unsafe to modify."""


class OriginalSidecar(TypedDict):
    filename: str
    sha256: str


class ImportedPhotoIdentity(TypedDict):
    photo_id: str
    folder_basename: str
    original_filename: str
    sidecars: list[OriginalSidecar]


def _filename_component(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
    ):
        raise ProjectError("Photo names must be single nonempty filename components")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _root(project: Path) -> Path:
    project = Path(project).absolute()
    if project.resolve() != project or not project.is_dir():
        raise ProjectError("Project path missing or contains a symlink")
    return project


def _asset(project: Path, name: str) -> Path:
    path = project / name
    if path.resolve() != path:
        raise ProjectError(f"Managed asset contains a symlink: {name}")
    return path


def _read_json(project: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_asset(project, name).read_bytes())
        if not isinstance(value, dict):
            raise TypeError("expected object")
        return value
    except (OSError, ValueError, TypeError) as error:
        raise ProjectError(f"Invalid or incomplete {name}: {error}") from error


@contextmanager
def _directory(path: Path, *, create: bool = False) -> Iterator[int]:
    """Walk held parents without following links; chmod only directories we create."""
    path = Path(os.path.abspath(path))
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in path.parts[1:]:
            created = False
            try:
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
                )
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(name, 0o700, dir_fd=descriptor)
                    created = True
                except FileExistsError:
                    pass
                if created:
                    observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if not stat.S_ISDIR(observed.st_mode):
                        raise ProjectError(f"Created directory was replaced: {path}")
                    # A restrictive umask can remove even owner access. Do not change the
                    # process-wide umask or permissions on any pre-existing component.
                    os.chmod(name, 0o700, dir_fd=descriptor, follow_symlinks=False)
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
                )
            try:
                observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                opened = os.fstat(child)
                if (observed.st_dev, observed.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ProjectError(f"Directory changed during creation: {path}")
                if created:
                    os.fchmod(child, 0o700)
                    os.fsync(child)
                    os.fsync(descriptor)
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _private_temporary_directory(parent: Path, prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    # This path was just exclusively created; never repair a retained attempt.
    path.chmod(0o700, follow_symlinks=False)
    return path


@contextmanager
def project_lock(project: Path) -> Iterator[None]:
    """One stable nonblocking OS lock for every project writer; readers stay unlocked."""
    project = _root(project)
    state_path = _asset(project, "state.json")
    if state_path.exists() and _read_json(project, "state.json").get("schema_version") != 2:
        raise ProjectError("Unsupported project schema; old project preserved without migration")
    path = _asset(project, ".writer.lock")
    with _file_lock(path, "Project"):
        yield


def project_writer_busy(project: Path) -> bool:
    """Observe the existing writer flock without acquiring a lock or creating a file."""
    project = _root(project)
    if sys.platform != "darwin":
        raise ProjectError("Writer lock inspection requires supported native macOS")
    try:
        descriptor = os.open(
            _asset(project, ".writer.lock"), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        )
    except FileNotFoundError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ProjectError("Invalid writer lock")
        # Darwin F_GETLK sees flock locks, including this process's other open
        # descriptions. struct flock: off_t start/length, pid_t, short type/whence.
        # Neither a shared nor an exclusive flock probe is safe: both reject writers.
        layout = struct.Struct("@qqihh")
        query = layout.pack(0, 0, 0, fcntl.F_WRLCK, os.SEEK_SET)
        observed = fcntl.fcntl(descriptor, fcntl.F_GETLK, query)
        return layout.unpack(observed)[3] != fcntl.F_UNLCK
    finally:
        os.close(descriptor)


@contextmanager
def _file_lock(path: Path, owner: str) -> Iterator[None]:
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    else:
        try:
            os.fchmod(descriptor, 0o600)
        except BaseException:
            os.close(descriptor)
            raise
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ProjectError(f"{owner} busy: another writer holds the lock") from error
        yield
    finally:
        os.close(descriptor)


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(
    path: Path,
    value: dict[str, Any],
    *,
    replace_existing: bool = True,
    validate_before_replace: Callable[[], None] | None = None,
) -> None:
    _atomic_bytes(
        path,
        _json_bytes(value),
        replace_existing=replace_existing,
        validate_before_replace=validate_before_replace,
    )


def _atomic_bytes(
    path: Path,
    value: bytes,
    *,
    replace_existing: bool = True,
    validate_before_replace: Callable[[], None] | None = None,
) -> None:
    if path.is_symlink():
        raise ProjectError("Refusing symlink state publication")
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=path.parent)
    # Failed temporary files are retained for diagnosis and never read as state.
    with os.fdopen(descriptor, "wb") as stream:
        # Set access on our new temporary inode, preserving an existing target's mode.
        mode = stat.S_IMODE(path.stat().st_mode) if replace_existing and path.exists() else 0o600
        os.fchmod(stream.fileno(), mode)
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    if validate_before_replace is not None:
        validate_before_replace()
    if replace_existing:
        os.replace(temporary, path)
    else:
        _publish_new_file(Path(temporary), path)
    try:
        _sync_directory(path.parent)
    except OSError as error:
        if path.name != "state.json" or not replace_existing:
            raise
        try:
            observed = _read_json(path.parent, "state.json")
            description = json.dumps(observed, sort_keys=True)
        except ProjectError:
            description = "state could not be reread"
        raise ProjectError(
            f"State replacement occurred; directory durability is uncertain; observed {description}"
        ) from error


def _publish_new_file(source: Path, destination: Path) -> None:
    # Hard-link publication is atomic create-if-absent on the same filesystem.
    # It cannot clobber text written outside our cooperative OS lock.
    try:
        os.link(source, destination, follow_symlinks=False)
    except FileExistsError as error:
        raise ProjectError(
            f"Initial publication collision: {destination.name}; incomplete project preserved"
        ) from error


def _publish_new_directory(source: Path, destination: Path) -> None:
    """Atomic exclusive publication on the supported native macOS filesystem."""
    _exclusive_rename(source, destination)


def _publish_new_cache_file(source: Path, destination: Path) -> None:
    """Move a validated prediction once; preserve visible publication on sync failure."""
    try:
        _exclusive_rename(source, destination)
    except (OSError, ProjectError) as error:
        raise ProjectError(
            f"Cache file publication failed: {destination.name}; temporary retained: {error}"
        ) from error
    try:
        _sync_directory(destination.parent)
    except OSError as error:
        raise ProjectError(
            f"Cache file published: {destination.name}; directory durability is uncertain"
        ) from error


def _exclusive_rename(
    source: Path,
    destination: Path,
    *,
    source_directory: int | None = None,
    destination_directory: int | None = None,
) -> None:
    """Same-filesystem move without replacement; held parents confine original imports."""
    if sys.platform != "darwin":
        raise ProjectError("Exclusive revision publication requires supported native macOS")
    library = ctypes.CDLL(None, use_errno=True)
    arguments: tuple[object, ...]
    if source_directory is None and destination_directory is None:
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = (os.fsencode(source), os.fsencode(destination), 4)
    elif source_directory is not None and destination_directory is not None:
        rename = library.renameatx_np
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        arguments = (
            source_directory,
            os.fsencode(source),
            destination_directory,
            os.fsencode(destination),
            4,
        )
    else:
        raise ProjectError("Exclusive move needs both parent descriptors")
    rename.restype = ctypes.c_int
    # Darwin stdio.h RENAME_EXCL=4; ordinary rename can replace an empty directory.
    if rename(*arguments) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise ProjectError("Directory publication collision; existing output preserved")
        raise OSError(code, os.strerror(code), str(destination))


def check_space(path: Path, pending_bytes: int) -> None:
    free = shutil.disk_usage(path).free
    if free < RESERVE_BYTES + pending_bytes:
        raise ProjectError(
            f"Insufficient space: need 10 GiB reserve plus {pending_bytes} pending bytes; "
            f"{free} bytes free"
        )


def _developed_identity(pixels: RGB16, metadata: dict[str, Any]) -> str:
    return digest(_json_bytes(metadata) + pixels.astype("<u2", copy=False).tobytes())


def create_project(
    source: Path,
    project_dir: Path,
    development: dict[str, Any],
    *,
    imported_photo: ImportedPhotoIdentity | None = None,
) -> Path:
    """Create once; preserve source and all existing files, publish complete state last."""
    source = Path(source).resolve(strict=True)
    project = Path(project_dir).absolute()
    if project.resolve() != project or source == project or source.is_relative_to(project):
        raise ProjectError("Source/output alias or symlink project path refused")
    if not source.is_file():
        raise ProjectError("Source must be a regular file")
    directory_mode = 0o700 if imported_photo is not None else 0o777
    if imported_photo is None:
        project.mkdir(parents=True, exist_ok=True, mode=directory_mode)
    else:
        with _directory(project, create=True):
            pass

    def make_directory(path: Path) -> None:
        path.mkdir(mode=directory_mode)
        if imported_photo is not None:
            path.chmod(0o700, follow_symlinks=False)

    with project_lock(project):
        if any(path.name != ".writer.lock" for path in project.iterdir()):
            raise ProjectError(
                "Existing or incomplete project is preserved; choose a new empty project"
            )
        source_size = source.stat().st_size
        check_space(project, source_size * 3 + 1024**2)
        capture = source.read_bytes()
        source_hash = digest(capture)
        pixels, metadata = decode_source(capture, development)
        metadata["source_sha256"] = source_hash
        developed_id = _developed_identity(pixels, metadata)
        check_space(project, source_size + pixels.nbytes * 3 + 1024**2)
        stage = _private_temporary_directory(project, ".initial-")
        make_directory(stage / "assets")
        make_directory(stage / "assets/developed")
        master = stage / "assets/developed" / f"{developed_id}.tif"
        write_developed(master, pixels)
        if imported_photo is not None:
            master.chmod(0o600, follow_symlinks=False)
        reloaded = tifffile.imread(master)
        if reloaded.dtype != np.uint16 or not np.array_equal(reloaded, pixels):
            raise ProjectError("Master TIFF round trip failed")
        source_record = {
            "schema_version": 2,
            "original_path": str(source),
            "source_sha256": source_hash,
            "developed_id": developed_id,
            "developed_file_sha256": digest(master.read_bytes()),
            "metadata": metadata,
        }
        if imported_photo is not None:
            source_record.update(
                original_path=f"../original/{source.name}",
                original_filename=source.name,
                library={
                    "photo_id": imported_photo["photo_id"],
                    "folder_basename": imported_photo["folder_basename"],
                    "sidecars": imported_photo["sidecars"],
                },
            )
            if imported_photo["original_filename"] != source.name:
                raise ProjectError("Imported original filename mismatch")
            _validate_imported_source(source_record)
        (stage / "source.json").write_bytes(_json_bytes(source_record))
        from .background import DEFAULT_BACKGROUND

        (stage / "recipe.toml").write_text(
            tomli_w.dumps(Recipe(developed_id, background=dict(DEFAULT_BACKGROUND)).to_dict())
        )
        (stage / "guides.json").write_bytes(
            _json_bytes(
                {
                    "schema_version": 2,
                    "developed_id": developed_id,
                    "width": pixels.shape[1],
                    "height": pixels.shape[0],
                    "regions": [],
                }
            )
        )
        (stage / "README.md").write_text(
            "# Photo project\n\nReady for mask preparation. No final result exists.\n"
            "Open assets/developed/<master-id>.tif in a trusted RGB16 sRGB viewer; inspect orientation, "
            "white balance and clipping if desired; source-development approval is optional.\n"
            "source.json locates the untouched original; assets/developed/ retains developed RGB16; "
            "recipe.toml/guides.json are drafts; state.json alone owns acceptance.\n"
        )
        for file in stage.rglob("*"):
            if file.is_file():
                if imported_photo is not None:
                    file.chmod(0o600, follow_symlinks=False)
                with file.open("rb") as stream:
                    os.fsync(stream.fileno())
        _sync_directory(stage / "assets/developed")
        _sync_directory(stage)
        if digest(source.read_bytes()) != source_hash:
            raise ProjectError("Stale source changed during ingestion; no state published")
        try:
            make_directory(project / "assets")
            make_directory(project / "assets/developed")
        except FileExistsError as error:
            raise ProjectError("Initial masters collision; incomplete project preserved") from error
        _publish_new_file(master, project / "assets/developed" / master.name)
        _sync_directory(project / "assets/developed")
        for name in ("source.json", "recipe.toml", "guides.json", "README.md"):
            _publish_new_file(stage / name, project / name)
        _sync_directory(project)
        state = {
            "schema_version": 2,
            "developed_id": developed_id,
            "development_approved": False,
            "working_revision": None,
            "accepted_revision": None,
            "latest_result_revision": None,
            "status": "ready",
        }
        # Validate the final saved assets before the state pointer becomes visible.
        _validate_assets(project, state)
        _atomic_json(project / "state.json", state, replace_existing=False)
    return project


# Read-only viewer requests reuse validated immutable bytes, never across requests.
_read_validation: ContextVar[dict[str, Any] | None] = ContextVar("read_validation", default=None)


@contextmanager
def _validation_scope() -> Iterator[None]:
    token = _read_validation.set({"master": None, "revisions": {}})
    try:
        yield
    finally:
        _read_validation.reset(token)


def _file_signature(path: Path) -> tuple[int, ...]:
    value = path.stat()
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _revision_signature(project: Path, directory: str, manifest: dict[str, Any]) -> tuple[Any, ...]:
    signatures = []
    from .assets import revision_asset, revision_hashes

    for name in revision_hashes(manifest):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ProjectError("Invalid revision asset path")
        try:
            signatures.append(
                (name, _file_signature(revision_asset(project, Path(directory), manifest, name)))
            )
        except OSError as error:
            raise ProjectError(f"Missing saved revision asset: {name}") from error
    return (digest(_json_bytes(manifest)), tuple(signatures))


def _validate_imported_source(record: dict[str, Any]) -> None:
    if "library" not in record and "original_filename" not in record:
        return
    identity = record.get("library")
    filename = record.get("original_filename")
    source_hash = record.get("source_sha256")

    if (
        not isinstance(identity, dict)
        or set(identity) != {"photo_id", "folder_basename", "sidecars"}
        or not isinstance(source_hash, str)
        or type(record.get("schema_version")) is not int
        or record["schema_version"] != 2
        or re.fullmatch("[0-9a-f]{64}", source_hash) is None
        or identity.get("photo_id") != "P" + source_hash[:12]
        or not _filename_component(identity.get("folder_basename"))
        or not identity["folder_basename"].startswith(identity["photo_id"] + "_")
        or not _filename_component(filename)
        or record.get("original_path") != f"../original/{filename}"
        or not isinstance(identity.get("sidecars"), list)
        or not isinstance(record.get("metadata"), dict)
        or record["metadata"].get("source_sha256") != source_hash
    ):
        raise ProjectError("Invalid imported source ownership")
    names = {filename}
    for sidecar in identity["sidecars"]:
        if (
            not isinstance(sidecar, dict)
            or set(sidecar) != {"filename", "sha256"}
            or not _filename_component(sidecar.get("filename"))
            or sidecar["filename"] in names
            or not isinstance(sidecar.get("sha256"), str)
            or re.fullmatch("[0-9a-f]{64}", sidecar["sha256"]) is None
        ):
            raise ProjectError("Invalid imported sidecar ownership")
        names.add(sidecar["filename"])


def _validate_assets(
    project: Path, state: dict[str, Any], *, validate_drafts: bool = True
) -> tuple[RGB16, dict[str, Any]]:
    developed_id = state.get("developed_id")
    if not isinstance(developed_id, str) or re.fullmatch("[0-9a-f]{64}", developed_id) is None:
        raise ProjectError("Invalid master identity")
    record = _read_json(project, "source.json")
    _validate_imported_source(record)
    metadata = record.get("metadata")
    if (
        type(record.get("schema_version")) is not int
        or record["schema_version"] != 2
        or record.get("developed_id") != developed_id
        or not isinstance(metadata, dict)
    ):
        raise ProjectError("Source/master identity mismatch")
    master = _asset(project, f"assets/developed/{developed_id}.tif")
    try:
        validation = _read_validation.get()
        key = (str(master), digest(_json_bytes(record)), _file_signature(master))
        cached = validation["master"] if validation is not None else None
        if cached is not None and cached[0] == key:
            pixels = cached[1]
        else:
            if digest(master.read_bytes()) != record.get("developed_file_sha256"):
                raise ProjectError("Master file hash mismatch")
            with tifffile.TiffFile(master) as image:
                page = image.pages[0]
                if not isinstance(page, tifffile.TiffPage):
                    raise ProjectError("Invalid master TIFF page")
                if (
                    len(image.pages) != 1
                    or int(page.compression) != 1
                    or page.dtype != np.dtype("uint16")
                    or page.tags[34675].value != srgb_profile()
                ):
                    raise ProjectError("Invalid master precision/profile/compression")
                pixels = page.asarray()
            if (
                pixels.ndim != 3
                or pixels.shape[2] != 3
                or _developed_identity(pixels, metadata) != developed_id
            ):
                raise ProjectError("Master sample/metadata identity mismatch")
            if validation is not None and _file_signature(master) == key[2]:
                pixels.flags.writeable = False
                validation["master"] = (key, pixels)
        if validate_drafts:
            recipe = tomllib.loads(_asset(project, "recipe.toml").read_text())
            Recipe.from_dict(
                recipe,
                developed_id,
                max_margin_px=max(pixels.shape[:2]),
                dimensions_wh=(pixels.shape[1], pixels.shape[0]),
            )
            guides = _read_json(project, "guides.json")
            validate_guides(guides, developed_id, pixels.shape[1], pixels.shape[0])
    except (OSError, ValueError, TypeError, KeyError, tifffile.TiffFileError) as error:
        raise ProjectError(f"Invalid project master or recipe: {error}") from error
    return pixels, metadata


def read_project(project: Path, *, validate_drafts: bool = True) -> dict[str, Any]:
    """Validate state/immutable assets; draft parsing may be deferred for explicit restore only."""
    project = _root(project)
    state = _read_json(project, "state.json")
    if state.get("schema_version") != 2:
        raise ProjectError("Unsupported project schema; old project preserved without migration")
    expected = {
        "schema_version",
        "developed_id",
        "development_approved",
        "working_revision",
        "accepted_revision",
        "latest_result_revision",
        "status",
    }
    if (
        set(state) != expected
        or type(state["schema_version"]) is not int
        or state["schema_version"] != 2
        or type(state["development_approved"]) is not bool
        or type(state["status"]) is not str
        or state["status"]
        not in (
            {"accepted"}
            if state["accepted_revision"] is not None
            and state["working_revision"] == state["accepted_revision"]
            else {"review_needed"}
            if state["working_revision"] is not None
            else {"ready", "review_needed"}
        )
    ):
        raise ProjectError("Invalid project state")
    _validate_assets(project, state, validate_drafts=validate_drafts)
    if state["working_revision"] is not None:
        read_revision(project, state["working_revision"], state["developed_id"])
    if state["accepted_revision"] is not None:
        accepted = read_revision(project, state["accepted_revision"], state["developed_id"])
        if (
            accepted.get("kind") not in {"matte", "repair", "effects"}
            or accepted.get("final_acceptable") is not True
        ):
            raise ProjectError("Invalid accepted complete matte revision")
    latest = state["latest_result_revision"]
    if latest is not None:
        result = read_revision(project, latest, state["developed_id"])
        from .effects import effects_stale

        if (
            result.get("kind") not in {"matte", "repair", "effects"}
            or result.get("final_acceptable") is not True
            or effects_stale(result)
        ):
            raise ProjectError("Invalid latest complete result revision")
    return state


def record_generated_result(state: dict[str, Any], revision: str, manifest: dict[str, Any]) -> None:
    """Advance generation history only alongside a fresh complete working result."""
    from .effects import effects_stale

    state.update(working_revision=revision, status="review_needed")
    if (
        manifest.get("complete") is True
        and manifest.get("kind") in {"matte", "repair", "effects"}
        and manifest.get("final_acceptable") is True
        and not effects_stale(manifest)
    ):
        state["latest_result_revision"] = revision


def load_developed(project: Path, developed_id: str) -> tuple[RGB16, dict[str, Any]]:
    project = _root(project)
    state = read_project(project)
    if state["developed_id"] != developed_id:
        raise ProjectError("Requested master identity is stale")
    return _validate_assets(project, state)


def accept_development(project: Path, developed_id: str) -> dict[str, Any]:
    """Optional legacy development review; never required for masking or photo acceptance."""
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        if state["developed_id"] != developed_id:
            raise ProjectError("Development approval master identity is stale")
        check_space(project, 1024**2)
        state.update(
            development_approved=True,
            status=(
                "accepted"
                if state["accepted_revision"]
                and state["accepted_revision"] == state["working_revision"]
                else "review_needed"
                if state["working_revision"]
                else "ready"
            ),
        )
        _atomic_json(_asset(project, "state.json"), state)
    return state


def read_revision(project: Path, revision: str, developed_id: str) -> dict[str, Any]:
    """Validate application-immutable saved dependencies before reuse; never infer pointers."""
    if not isinstance(revision, str) or re.fullmatch(r"rev-[0-9]{3,}", revision) is None:
        raise ProjectError("Invalid saved revision identity")
    return _validate_revision_directory(project, revision, developed_id, f"revisions/{revision}")


@lru_cache(maxsize=128)
def _validate_exposure_semantics(project: Path, directory: Path, manifest_bytes: bytes) -> None:
    """Bound successful checks only; callers must rehash every operand before reuse."""
    from .assets import revision_asset
    from .exposure import read_exposure
    from .repair import scalar16

    read_exposure(
        project,
        directory,
        json.loads(manifest_bytes),
        scalar16(
            revision_asset(project, directory, json.loads(manifest_bytes), "base_alpha16.png")
        ),
    )


@lru_cache(maxsize=128)
def _validate_shadow_fade_semantics(project: Path, directory: Path, manifest_bytes: bytes) -> None:
    """Bound successful checks only; callers must rehash every operand before reuse."""
    from .assets import revision_asset
    from .repair import scalar16
    from .shadow_fade import read_shadow_fade

    read_shadow_fade(
        project,
        directory,
        json.loads(manifest_bytes),
        scalar16(
            revision_asset(project, directory, json.loads(manifest_bytes), "base_alpha16.png")
        ),
    )


@lru_cache(maxsize=128)
def _validate_local_sharpening_semantics(
    project: Path, directory: Path, manifest_bytes: bytes
) -> None:
    """Bound successful checks only; callers must rehash every operand before reuse."""
    from .assets import revision_asset
    from .repair import scalar16
    from .sharpening import read_local_sharpening

    read_local_sharpening(
        project,
        directory,
        json.loads(manifest_bytes),
        scalar16(
            revision_asset(project, directory, json.loads(manifest_bytes), "base_alpha16.png")
        ),
    )


@lru_cache(maxsize=128)
def _validate_background_semantics(project: Path, directory: Path, manifest_bytes: bytes) -> None:
    from .background import read_background

    read_background(project, directory, json.loads(manifest_bytes))


@lru_cache(maxsize=128)
def _validate_spatial_fade_semantics(project: Path, directory: Path, manifest_bytes: bytes) -> None:
    """Replay bound geometry after fresh hashes; ordinary renders reuse saved fields."""
    from .assets import revision_asset
    from .fade_reduction import rasterize_fade_reduction
    from .repair import scalar16
    from .spatial_fade import make_spatial_weight, read_spatial_fade

    manifest = json.loads(manifest_bytes)
    alpha = scalar16(revision_asset(project, directory, manifest, "base_alpha16.png"))
    saved = read_spatial_fade(project, directory, manifest, alpha)
    if saved is not None and not np.array_equal(
        saved.weight16, make_spatial_weight(alpha.shape, saved.record["settings"])
    ):
        raise ProjectError("Saved spatial fade geometry differs from its settings")
    if saved is not None and saved.reduction16 is not None:
        area = json.loads(
            revision_asset(
                project, directory, manifest, "effects/spatial-fade/reduction.json"
            ).read_bytes()
        )
        if not np.array_equal(
            saved.reduction16,
            rasterize_fade_reduction(
                area, manifest["developed_id"], alpha.shape[1], alpha.shape[0]
            ),
        ):
            raise ProjectError("Saved fade reduction geometry differs from its raster")


def _validate_revision_directory(
    project: Path, revision: str, developed_id: str, directory: str
) -> dict[str, Any]:
    """Same immutable contract for a retained completed stage and a published revision."""
    manifest = _read_json(project, f"{directory}/manifest.json")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 2
        or manifest.get("revision") != revision
        or manifest.get("developed_id") != developed_id
        or manifest.get("complete") is not True
        or not isinstance(manifest.get("files"), dict)
        or not isinstance(manifest.get("assets"), dict)
    ):
        raise ProjectError("Invalid saved revision/developed identity/schema/complete manifest")
    # An unlisted area is absent from file signatures; reject it before either cache can return.
    record = manifest.get("local_exposure")
    if (
        isinstance(record, dict)
        and record.get("area_sha256") is None
        and _asset(project, f"{directory}/effects/exposure/area.json").exists()
    ):
        raise ProjectError("Unbound saved local exposure authored area")
    record = manifest.get("shadow_fade")
    if (
        isinstance(record, dict)
        and record.get("area_sha256") is None
        and _asset(project, f"{directory}/effects/shadow-fade/area.json").exists()
    ):
        raise ProjectError("Unbound saved Shadow fade authored area")
    record = manifest.get("local_sharpening")
    if (
        isinstance(record, dict)
        and record.get("area_sha256") is None
        and _asset(project, f"{directory}/effects/sharpening/area.json").exists()
    ):
        raise ProjectError("Unbound saved Local sharpening authored area")
    from .background import validate_background_bindings
    from .spatial_fade import validate_spatial_bindings

    validate_background_bindings(project, _asset(project, directory), manifest)
    validate_spatial_bindings(project, _asset(project, directory), manifest)
    if "background" in manifest:
        record = manifest["background"]
        metadata = _read_json(project, "source.json")["metadata"]
        if not isinstance(record, dict) or any(
            record.get(n) != metadata[n] for n in ("width", "height")
        ):
            raise ProjectError("Saved background dimensions differ from master")
    validation = _read_validation.get()
    key = (str(project), directory)
    signature = (
        _revision_signature(project, directory, manifest) if validation is not None else None
    )
    if validation is not None:
        cached = validation["revisions"].get(key)
        if cached is not None and cached[0] == signature:
            return copy.deepcopy(cached[1])
    from .assets import revision_asset, revision_hashes

    for name, expected_hash in revision_hashes(manifest).items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ProjectError("Invalid revision asset path")
        path = revision_asset(project, Path(directory), manifest, name)
        if name in manifest["assets"]:
            # The canonical resolver already hashes every shared object before cache reuse.
            continue
        try:
            if digest(path.read_bytes()) != expected_hash:
                raise ProjectError(f"Saved revision hash mismatch: {revision}/{name}")
        except OSError as error:
            raise ProjectError(f"Missing saved revision asset: {name}") from error
    if not {
        "recipe.toml",
        "guides.json",
        "request.json",
        "result.json",
        "trimap.png",
        "supports/support16.png",
        "supports/protection.png",
        "supports/lock_values16.png",
    } <= set(revision_hashes(manifest)):
        raise ProjectError("Incomplete prepared revision files")
    if manifest.get("kind") in {"matte", "repair", "effects"} and (
        not {
            "base_alpha16.png",
            "foreground_rgb16.tif",
            "qa.json",
            "review/manifest.json",
        }
        <= set(revision_hashes(manifest))
        or manifest.get("final_acceptable") is not True
    ):
        raise ProjectError("Incomplete matte revision files")
    if manifest.get("kind") == "repair" and not {
        "repair/parent_alpha16.png",
        "repair/candidate_alpha16.png",
        "repair/support16.png",
        "repair/merge.json",
    } <= set(revision_hashes(manifest)):
        raise ProjectError("Incomplete repair operands")
    _validate_background_semantics(project, _asset(project, directory), _json_bytes(manifest))
    if "local_exposure" in manifest:
        record = manifest["local_exposure"]
        from .exposure import EXPOSURE_FILES

        required_exposure = {"base_alpha16.png"} | {
            f"effects/exposure/{name}" for name in EXPOSURE_FILES
        }
        if not required_exposure <= set(revision_hashes(manifest)):
            raise ProjectError("Incomplete local exposure assets")
        if (
            isinstance(record, dict)
            and record.get("area_sha256") is not None
            and "effects/exposure/area.json" not in manifest["files"]
        ):
            raise ProjectError("Missing bound local exposure authored area")
        _validate_exposure_semantics(project, _asset(project, directory), _json_bytes(manifest))
    if "shadow_fade" in manifest:
        record = manifest["shadow_fade"]
        from .shadow_fade import SHADOW_FADE_FILES

        required_fade = {"base_alpha16.png"} | {
            f"effects/shadow-fade/{name}" for name in SHADOW_FADE_FILES
        }
        if not required_fade <= set(revision_hashes(manifest)):
            raise ProjectError("Incomplete Shadow fade assets")
        if (
            isinstance(record, dict)
            and record.get("area_sha256") is not None
            and "effects/shadow-fade/area.json" not in manifest["files"]
        ):
            raise ProjectError("Missing bound Shadow fade authored area")
        _validate_shadow_fade_semantics(project, _asset(project, directory), _json_bytes(manifest))
    if "local_sharpening" in manifest:
        record = manifest["local_sharpening"]
        from .sharpening import SHARPENING_FILES

        required_fade = {"base_alpha16.png"} | {
            f"effects/sharpening/{name}" for name in SHARPENING_FILES
        }
        if not required_fade <= set(revision_hashes(manifest)):
            raise ProjectError("Incomplete Local sharpening assets")
        if (
            isinstance(record, dict)
            and record.get("area_sha256") is not None
            and "effects/sharpening/area.json" not in manifest["files"]
        ):
            raise ProjectError("Missing bound Local sharpening authored area")
        _validate_local_sharpening_semantics(
            project, _asset(project, directory), _json_bytes(manifest)
        )
    if "spatial_fade" in manifest:
        _validate_spatial_fade_semantics(project, _asset(project, directory), _json_bytes(manifest))
    if (
        validation is not None
        and _revision_signature(project, directory, manifest) == signature
        and (len(validation["revisions"]) < 128 or key in validation["revisions"])
    ):
        validation["revisions"][key] = (signature, copy.deepcopy(manifest))

    return manifest
