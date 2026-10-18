"""Canonical project identity, writer lock and safe publication boundaries."""

import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
import tomli_w

from .guidance import validate_guides
from .ingest import RGB16, decode_source, srgb_profile, write_master
from .recipe import Recipe

RESERVE_BYTES = 10 * 1024**3


class ProjectError(ValueError):
    """Project is busy, stale, incomplete or unsafe to modify."""


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
def project_lock(project: Path) -> Iterator[None]:
    """One stable nonblocking OS lock for every project writer; readers stay unlocked."""
    project = _root(project)
    path = _asset(project, ".writer.lock")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ProjectError("Project busy: another writer holds the project lock") from error
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
    if path.is_symlink():
        raise ProjectError("Refusing symlink state publication")
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=path.parent)
    # Failed temporary files are retained for diagnosis and never read as state.
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    if validate_before_replace is not None:
        validate_before_replace()
    if replace_existing:
        os.replace(temporary, path)
    else:
        _publish_new_file(Path(temporary), path)
    _sync_directory(path.parent)


def _publish_new_file(source: Path, destination: Path) -> None:
    # Hard-link publication is atomic create-if-absent on the same filesystem.
    # It cannot clobber text written outside our cooperative OS lock.
    try:
        os.link(source, destination, follow_symlinks=False)
    except FileExistsError as error:
        raise ProjectError(
            f"Initial publication collision: {destination.name}; incomplete project preserved"
        ) from error


def check_space(path: Path, pending_bytes: int) -> None:
    free = shutil.disk_usage(path).free
    if free < RESERVE_BYTES + pending_bytes:
        raise ProjectError(
            f"Insufficient space: need 10 GiB reserve plus {pending_bytes} pending bytes; "
            f"{free} bytes free"
        )


def _master_identity(pixels: RGB16, metadata: dict[str, Any]) -> str:
    return digest(_json_bytes(metadata) + pixels.astype("<u2", copy=False).tobytes())


def create_project(source: Path, project_dir: Path, development: dict[str, Any]) -> Path:
    """Create once; preserve source and all existing files, publish complete state last."""
    source = Path(source).resolve(strict=True)
    project = Path(project_dir).absolute()
    if project.resolve() != project or source == project or source.is_relative_to(project):
        raise ProjectError("Source/output alias or symlink project path refused")
    if not source.is_file():
        raise ProjectError("Source must be a regular file")
    project.mkdir(parents=True, exist_ok=True)
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
        master_id = _master_identity(pixels, metadata)
        check_space(project, source_size + pixels.nbytes * 3 + 1024**2)
        stage = Path(tempfile.mkdtemp(prefix=".initial-", dir=project))
        (stage / "masters").mkdir()
        master = stage / "masters" / f"{master_id}.tif"
        write_master(master, pixels)
        reloaded = tifffile.imread(master)
        if reloaded.dtype != np.uint16 or not np.array_equal(reloaded, pixels):
            raise ProjectError("Master TIFF round trip failed")
        source_record = {
            "schema_version": 1,
            "original_path": str(source),
            "source_sha256": source_hash,
            "master_id": master_id,
            "master_file_sha256": digest(master.read_bytes()),
            "metadata": metadata,
        }
        (stage / "source.json").write_bytes(_json_bytes(source_record))
        (stage / "recipe.toml").write_text(tomli_w.dumps(Recipe(master_id).to_dict()))
        (stage / "guides.json").write_bytes(
            _json_bytes(
                {
                    "schema_version": 1,
                    "master_id": master_id,
                    "width": pixels.shape[1],
                    "height": pixels.shape[0],
                    "regions": [],
                }
            )
        )
        (stage / "README.md").write_text(
            "# Photo project\n\nDevelopment review required. No final result exists.\n"
            "Open masters/<master-id>.tif in a trusted RGB16 sRGB viewer; inspect orientation, "
            "white balance and clipping. Only explicit human development acceptance approves it.\n"
            "source.json locates the untouched original; masters/ retains developed RGB16; "
            "recipe.toml/guides.json are drafts; state.json alone owns acceptance.\n"
        )
        for file in stage.rglob("*"):
            if file.is_file():
                with file.open("rb") as stream:
                    os.fsync(stream.fileno())
        _sync_directory(stage / "masters")
        _sync_directory(stage)
        if digest(source.read_bytes()) != source_hash:
            raise ProjectError("Stale source changed during ingestion; no state published")
        try:
            (project / "masters").mkdir()
        except FileExistsError as error:
            raise ProjectError("Initial masters collision; incomplete project preserved") from error
        _publish_new_file(master, project / "masters" / master.name)
        _sync_directory(project / "masters")
        for name in ("source.json", "recipe.toml", "guides.json", "README.md"):
            _publish_new_file(stage / name, project / name)
        _sync_directory(project)
        state = {
            "schema_version": 1,
            "master_id": master_id,
            "development_approved": False,
            "working_revision": None,
            "accepted_revision": None,
            "status": "review_needed",
        }
        # Validate the final saved assets before the state pointer becomes visible.
        _validate_assets(project, state)
        _atomic_json(project / "state.json", state, replace_existing=False)
    return project


def _validate_assets(project: Path, state: dict[str, Any]) -> tuple[RGB16, dict[str, Any]]:
    master_id = state.get("master_id")
    if not isinstance(master_id, str) or re.fullmatch("[0-9a-f]{64}", master_id) is None:
        raise ProjectError("Invalid master identity")
    record = _read_json(project, "source.json")
    metadata = record.get("metadata")
    if record.get("master_id") != master_id or not isinstance(metadata, dict):
        raise ProjectError("Source/master identity mismatch")
    master = _asset(project, f"masters/{master_id}.tif")
    try:
        if digest(master.read_bytes()) != record.get("master_file_sha256"):
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
            or _master_identity(pixels, metadata) != master_id
        ):
            raise ProjectError("Master sample/metadata identity mismatch")
        recipe = tomllib.loads(_asset(project, "recipe.toml").read_text())
        Recipe.from_dict(recipe, master_id)
        guides = _read_json(project, "guides.json")
        validate_guides(guides, master_id, pixels.shape[1], pixels.shape[0])
    except (OSError, ValueError, TypeError, KeyError, tifffile.TiffFileError) as error:
        raise ProjectError(f"Invalid project master or recipe: {error}") from error
    return pixels, metadata


def read_project(project: Path) -> dict[str, Any]:
    project = _root(project)
    state = _read_json(project, "state.json")
    expected = {
        "schema_version",
        "master_id",
        "development_approved",
        "working_revision",
        "accepted_revision",
        "status",
    }
    if (
        set(state) != expected
        or type(state["schema_version"]) is not int
        or state["schema_version"] != 1
        or type(state["development_approved"]) is not bool
        or state["accepted_revision"] is not None
        or state["status"]
        != (
            "review_needed"
            if state["working_revision"] is not None or not state["development_approved"]
            else "ready"
        )
    ):
        raise ProjectError("Invalid project state")
    _validate_assets(project, state)
    if state["working_revision"] is not None:
        read_revision(project, state["working_revision"], state["master_id"])
    return state


def load_master(project: Path, master_id: str) -> tuple[RGB16, dict[str, Any]]:
    project = _root(project)
    state = read_project(project)
    if state["master_id"] != master_id:
        raise ProjectError("Requested master identity is stale")
    return _validate_assets(project, state)


def accept_development(project: Path, master_id: str) -> dict[str, Any]:
    """Record a human's explicit approval of this identity, never final-photo acceptance."""
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        if state["master_id"] != master_id:
            raise ProjectError("Development approval master identity is stale")
        check_space(project, 1024**2)
        state.update(
            development_approved=True,
            status="review_needed" if state["working_revision"] else "ready",
        )
        _atomic_json(_asset(project, "state.json"), state)
    return state


def read_revision(project: Path, revision: str, master_id: str) -> dict[str, Any]:
    """Validate application-immutable saved dependencies before reuse; never infer pointers."""
    if not isinstance(revision, str) or re.fullmatch(r"rev-[0-9]{3,}", revision) is None:
        raise ProjectError("Invalid saved revision identity")
    manifest = _read_json(project, f"revisions/{revision}/manifest.json")
    if (
        manifest.get("revision") != revision
        or manifest.get("master_id") != master_id
        or manifest.get("complete") is not True
        or not isinstance(manifest.get("files"), dict)
    ):
        raise ProjectError("Invalid saved revision/master/complete manifest")
    for name, expected_hash in manifest["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ProjectError("Invalid revision asset path")
        path = _asset(project, f"revisions/{revision}/{name}")
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
    } <= set(manifest["files"]):
        raise ProjectError("Incomplete prepared revision files")
    return manifest
