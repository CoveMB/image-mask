"""Project-owned immutable raster objects and their logical revision bindings."""

import hashlib
import os
import re
import shutil
import stat
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from PIL import Image


class AssetReference(TypedDict):
    path: str
    sha256: str


def _checksum(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def _reference_values(reference: Any) -> tuple[str, str]:
    from .project import ProjectError

    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ProjectError("Invalid shared asset reference")
    name, checksum = reference["path"], reference["sha256"]
    if (
        not isinstance(name, str)
        or not isinstance(checksum, str)
        or re.fullmatch("[0-9a-f]{64}", checksum) is None
    ):
        raise ProjectError("Invalid shared asset path/hash binding")
    ordinary = re.fullmatch(r"assets/[0-9a-f]{64}\.(png|tif)", name)
    developed = re.fullmatch(r"assets/developed/[0-9a-f]{64}\.tif", name)
    if not developed and (ordinary is None or Path(name).stem != checksum):
        raise ProjectError("Invalid shared asset path/hash binding")
    return name, checksum


def resolve_asset(project: Path, reference: AssetReference) -> Path:
    from .project import ProjectError, _asset, _file_signature, _read_json, _read_validation

    name, checksum = _reference_values(reference)
    if name.startswith("assets/developed/"):
        record = _read_json(project, "source.json")
        if name != f"assets/developed/{record.get('developed_id')}.tif" or checksum != record.get(
            "developed_file_sha256"
        ):
            raise ProjectError("Invalid developed asset identity/hash binding")
    path = _asset(project, name)
    try:
        signature = _file_signature(path)
        if not stat.S_ISREG(signature[2]):
            raise ProjectError("Shared asset must be a regular file")
        cache = _read_validation.get()
        key = (str(path), checksum, signature)
        checked = cache.setdefault("assets", set()) if cache is not None else set()
        if key not in checked:
            if _checksum(path) != checksum or _file_signature(path) != signature:
                raise ProjectError("Stale shared asset hash mismatch or changed while reading")
            if cache is not None:
                checked.add(key)
        return path
    except OSError as error:
        raise ProjectError(f"Missing shared asset: {name}") from error


def store_asset(project: Path, source: Path) -> AssetReference:
    from .project import (
        ProjectError,
        _asset,
        _publish_new_file,
        _read_json,
        _sync_directory,
        check_space,
    )

    if (
        source.suffix.lower() not in {".png", ".tif"}
        or source.resolve() != source.absolute()
        or not source.is_file()
    ):
        raise ProjectError("Shared asset source must be an ordinary PNG or TIFF file")
    checksum = _checksum(source)
    record = _read_json(project, "source.json")
    name = f"assets/{checksum}{source.suffix.lower()}"
    if source.suffix.lower() == ".tif" and checksum == record.get("developed_file_sha256"):
        name = f"assets/developed/{record['developed_id']}.tif"
    reference: AssetReference = {"path": name, "sha256": checksum}
    root = _asset(project, "assets")
    root.mkdir(exist_ok=True)
    destination = _asset(project, reference["path"])
    if destination.exists() or destination.is_symlink():
        resolve_asset(project, reference)
        return reference
    check_space(project, source.stat().st_size + 1024**2)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".asset-", dir=root)
    temporary = Path(temporary_name)
    with os.fdopen(descriptor, "wb") as stream, source.open("rb") as original:
        shutil.copyfileobj(original, stream, length=1024 * 1024)
        stream.flush()
        os.fsync(stream.fileno())
    if _checksum(temporary) != checksum:
        raise ProjectError("Shared asset changed while capturing immutable bytes")
    _publish_new_file(temporary, destination)
    _sync_directory(root)
    # Only this successful attempt's disposable alias is removed; failures retain evidence.
    temporary.unlink()
    _sync_directory(root)
    resolve_asset(project, reference)
    return reference


def revision_hashes(manifest: dict[str, Any]) -> dict[str, str]:
    from .project import ProjectError

    files, assets = manifest.get("files", {}), manifest.get("assets", {})
    if not isinstance(files, dict) or not isinstance(assets, dict) or set(files) & set(assets):
        raise ProjectError("Invalid or overlapping revision file/asset roles")
    hashes: dict[str, str] = {}
    for name, checksum in files.items():
        if (
            not isinstance(name, str)
            or name.endswith((".png", ".tif"))
            or not isinstance(checksum, str)
            or re.fullmatch("[0-9a-f]{64}", checksum) is None
        ):
            raise ProjectError("Invalid revision text or shared raster binding")
        hashes[name] = checksum
    for name, reference in assets.items():
        if not isinstance(name, str) or not name.endswith((".png", ".tif")):
            raise ProjectError("Invalid shared raster role")
        _, checksum = _reference_values(reference)
        hashes[name] = checksum
    return hashes


@lru_cache(maxsize=512)
def _validate_role(
    path: Path, name: str, shape: tuple[int, int], signature: tuple[int, ...]
) -> None:
    from .export import read_rgb16
    from .project import ProjectError

    if name.endswith(".tif"):
        pixels = read_rgb16(path)
        if pixels.shape != (*shape, 3):
            raise ProjectError(
                "Shared RGB16 role dimensions/registration differ from developed image"
            )
        return
    with Image.open(path, formats=["PNG"]) as image:
        if image.size != (shape[1], shape[0]):
            raise ProjectError("Shared mask dimensions/registration differ from developed image")
        if name == "source_proxy8.png":
            valid = image.mode == "RGB"
        elif name.endswith("16.png"):
            valid = image.mode in {"I;16", "I;16L", "I;16B"}
        else:
            valid = image.mode == "L"
        if not valid:
            raise ProjectError("Invalid shared raster role/precision")
        if (
            "protection" in name
            or name.startswith("candidates/")
            or name
            in {
                "selected_membership.png",
                "proposal_boundary.png",
                "trimap.png",
                "trimap_proposal.png",
            }
        ):
            values = np.asarray(image)
            expected = (
                [0, 128, 255]
                if name in {"trimap.png", "trimap_proposal.png"}
                else [0, 65535]
                if name.endswith("16.png")
                else [0, 255]
            )
            if not np.isin(values, expected).all():
                raise ProjectError("Invalid shared categorical raster role")


def revision_asset(
    project: Path, directory: Path, manifest: dict[str, Any], logical_name: str
) -> Path:
    from .project import ProjectError, _asset, _file_signature, _read_json

    relative = Path(logical_name)
    if (
        not isinstance(logical_name, str)
        or relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
    ):
        raise ProjectError("Invalid logical revision asset path")
    directory = Path(directory)
    if not directory.is_absolute():
        directory = _asset(project, str(directory))
    if directory.resolve() != directory or not directory.is_relative_to(project / "revisions"):
        raise ProjectError("Invalid revision asset directory")
    local = _asset(project, str((directory / relative).relative_to(project)))
    staging = directory.name.startswith((".prepare-", ".matte-", ".effects-"))
    # A freshly generated stage operand supersedes its inherited reference until sealing.
    if staging and local.is_file():
        return local
    if logical_name in manifest.get("assets", {}):
        if logical_name in manifest.get("files", {}):
            raise ProjectError("Overlapping revision raster and text roles")
        path = resolve_asset(project, manifest["assets"][logical_name])
        metadata = _read_json(project, "source.json")["metadata"]
        _validate_role(
            path, logical_name, (metadata["height"], metadata["width"]), _file_signature(path)
        )
        return path
    if logical_name.endswith((".png", ".tif")):
        raise ProjectError(f"Missing shared revision raster role: {logical_name}")
    if not staging and logical_name not in manifest.get("files", {}):
        raise ProjectError(f"Unbound revision text asset: {logical_name}")
    return local


def saved_asset(project: Path, relative_name: str) -> Path:
    """Resolve a saved revision locator through the same logical-role contract."""
    from .project import _asset, _read_json

    parts = Path(relative_name).parts
    if len(parts) < 3 or parts[0] != "revisions" or parts[-1] == "manifest.json":
        return _asset(project, relative_name)
    directory = Path(*parts[:2])
    manifest = _read_json(project, str(directory / "manifest.json"))
    return revision_asset(project, directory, manifest, str(Path(*parts[2:])))


def collect_stage_assets(project: Path, stage: Path, assets: dict[str, AssetReference]) -> None:
    """Seal newly generated operands before publishing a text-only revision directory."""
    from .project import ProjectError

    if stage.parent != project / "revisions" or not stage.name.startswith(
        (".prepare-", ".matte-", ".effects-")
    ):
        raise ProjectError("Only a new owned revision stage can seal raster operands")
    for path in sorted(stage.rglob("*")):
        if path.suffix.lower() not in {".png", ".tif"}:
            continue
        name = str(path.relative_to(stage))
        assets[name] = store_asset(project, path)
        path.unlink()


def stage_asset(project: Path, stage: Path, assets: dict[str, AssetReference], name: str) -> Path:
    return revision_asset(project, stage, {"assets": assets}, name)


def inherit_revision_files(
    project: Path,
    parent: str,
    stage: Path,
    assets: dict[str, AssetReference],
    names: tuple[str, ...] | list[str],
) -> None:
    from .project import _read_json

    manifest = _read_json(project, f"revisions/{parent}/manifest.json")
    for name in names:
        source = revision_asset(project, Path(f"revisions/{parent}"), manifest, name)
        if name in manifest["assets"]:
            assets[name] = {
                "path": manifest["assets"][name]["path"],
                "sha256": manifest["assets"][name]["sha256"],
            }
        else:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
