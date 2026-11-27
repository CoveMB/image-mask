"""Immutable Cloud operands and request validation for saved revisions."""

import json
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .assets import _checksum, inherit_revision_files, revision_asset, revision_hashes, stage_asset
from .cloud import (
    CLOUD_ALGORITHM,
    CloudOperands,
    cloud_geometry_key,
    cloud_visible,
    make_cloud_clear,
    make_cloud_fields,
    validate_cloud_area,
    validate_cloud_settings,
)
from .mist import PROTECTION_ROLE, ROWS_PER_CHUNK
from .project import ProjectError, _json_bytes, digest
from .repair import scalar16

MAX_CLOUD_REQUEST_BYTES = 2_000_000
CLOUD_MEMBERS = {
    "density16.png": "density_sha256",
    "light16.png": "light_sha256",
    "clear16.png": "clear_sha256",
    "settings.json": "settings_sha256",
    "area.json": "area_sha256",
}


def parse_cloud_json(raw: bytes, *, bounded: bool = True) -> dict[str, Any]:
    if bounded and len(raw) > MAX_CLOUD_REQUEST_BYTES:
        raise ProjectError(f"Cloud JSON exceeds {MAX_CLOUD_REQUEST_BYTES} bytes")

    def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ProjectError("Duplicate Cloud JSON field")
        return fields

    def reject_constant(value: str) -> None:
        raise ProjectError(f"Nonfinite Cloud JSON value: {value}")

    try:
        value = json.loads(raw, object_pairs_hook=unique_fields, parse_constant=reject_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ProjectError("Invalid Cloud JSON") from error
    if not isinstance(value, dict):
        raise ProjectError("Cloud JSON must be an object")
    return value


def read_cloud_request_bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        return stream.read(MAX_CLOUD_REQUEST_BYTES + 1)


def validate_cloud_request(
    value: Any, developed_id: str, width: int, height: int
) -> dict[str, Any]:
    if isinstance(value, dict):
        if set(value) == {"action"} and value["action"] == "disable":
            return value
        if set(value) == {"action", "settings", "area"} and value["action"] == "apply":
            return {
                "action": "apply",
                "settings": validate_cloud_settings(value["settings"], width, height),
                "area": validate_cloud_area(value["area"], developed_id, width, height),
            }
    raise ProjectError("Cloud requires Apply with complete settings and area or Disable alone")


def read_cloud_area(project: Path, directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    record = manifest["cloud"]
    raw = read_cloud_request_bytes(revision_asset(project, directory, manifest, "cloud/area.json"))
    if digest(raw) != record["area_sha256"]:
        raise ProjectError("Saved Cloud area hash changed")
    area = validate_cloud_area(
        parse_cloud_json(raw), record["developed_id"], record["width"], record["height"]
    )
    if raw != _json_bytes(area):
        raise ProjectError("Invalid canonical saved Cloud area")
    return area


def validate_cloud_bindings(directory: Path, manifest: dict[str, Any]) -> None:
    """Check the Cloud namespace before either revision-validation cache can return."""
    expected_text = set()
    expected_rasters = set()
    if "cloud" in manifest:
        expected_text = {f"cloud/{name}" for name in CLOUD_MEMBERS if name.endswith(".json")}
        expected_rasters = {f"cloud/{name}" for name in CLOUD_MEMBERS if name.endswith(".png")}
    namespace = directory / "cloud"
    local = set()
    if namespace.exists() or namespace.is_symlink():
        if not expected_text or namespace.is_symlink() or not namespace.is_dir():
            raise ProjectError("Invalid saved Cloud namespace")
        for path in namespace.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ProjectError("Invalid saved Cloud member")
            local.add(f"cloud/{path.name}")
    if (
        local != expected_text
        or {name for name in manifest["files"] if name == "cloud" or name.startswith("cloud/")}
        != expected_text
        or {name for name in manifest["assets"] if name == "cloud" or name.startswith("cloud/")}
        != expected_rasters
    ):
        raise ProjectError("Missing, unknown or unbound Cloud operands")


def validate_cloud_revision(
    project: Path, directory: Path, manifest: dict[str, Any], size: tuple[int, int] | None = None
) -> None:
    prepared = manifest.get("kind") == "prepare"
    if "cloud" not in manifest:
        if not prepared and "cloud" in tomllib.loads((directory / "recipe.toml").read_text()):
            raise ProjectError("Unbound saved Cloud recipe settings")
        return
    record = manifest["cloud"]
    if size is None:
        raise ProjectError("Native dimensions required to validate saved Cloud")
    width, height = size
    if (
        not isinstance(record, dict)
        or set(record)
        != {
            "schema_version",
            "algorithm",
            "developed_id",
            "width",
            "height",
            "settings",
            "protection_sha256",
            *CLOUD_MEMBERS.values(),
        }
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["algorithm"] != CLOUD_ALGORITHM
        or record["developed_id"] != manifest["developed_id"]
        or type(record["width"]) is not int
        or type(record["height"]) is not int
        or (record["width"], record["height"]) != size
    ):
        raise ProjectError("Invalid saved Cloud identity, schema, algorithm or native dimensions")
    hashes = revision_hashes(manifest)
    if record["protection_sha256"] != hashes[PROTECTION_ROLE] or any(
        record[field] != hashes[f"cloud/{name}"] for name, field in CLOUD_MEMBERS.items()
    ):
        raise ProjectError("Cloud operand or hard protection hash differs from revision binding")
    settings = validate_cloud_settings(record["settings"], width, height)
    saved_settings = revision_asset(
        project, directory, manifest, "cloud/settings.json"
    ).read_bytes()
    if _json_bytes(settings) != saved_settings or _json_bytes(record["settings"]) != saved_settings:
        raise ProjectError("Invalid canonical saved Cloud settings")
    if not prepared:
        recipe = tomllib.loads((directory / "recipe.toml").read_text())
        if validate_cloud_settings(recipe.get("cloud"), width, height) != settings:
            raise ProjectError("Cloud effective recipe and saved settings differ")
    read_cloud_area(project, directory, manifest)
    clear = scalar16(revision_asset(project, directory, manifest, "cloud/clear16.png"))
    with Image.open(revision_asset(project, directory, manifest, PROTECTION_ROLE)) as raster:
        for y0 in range(0, height, ROWS_PER_CHUNK):
            y1 = min(y0 + ROWS_PER_CHUNK, height)
            if np.any((np.asarray(raster.crop((0, y0, width, y1))) != 0) & (clear[y0:y1] != 65535)):
                raise ProjectError("Saved Cloud clearance omits hard protection")


def read_cloud(project: Path, directory: Path, manifest: dict[str, Any]) -> CloudOperands | None:
    """Read active or retained OFF operands from a validated revision or its owned stage."""
    if "cloud" not in manifest:
        return None
    record = manifest["cloud"]
    return CloudOperands(
        scalar16(revision_asset(project, directory, manifest, "cloud/density16.png")),
        scalar16(revision_asset(project, directory, manifest, "cloud/light16.png")),
        scalar16(revision_asset(project, directory, manifest, "cloud/clear16.png")),
        record["settings"],
        read_cloud_area(project, directory, manifest),
        (record["width"], record["height"]),
    )


def saved_cloud(
    project: Path, directory: Path, manifest: dict[str, Any], *, effects_off: bool = False
) -> CloudOperands | None:
    """Load Cloud maps only when their settings contribute to Result."""
    if effects_off or "cloud" not in manifest or not cloud_visible(manifest["cloud"]["settings"]):
        return None
    return read_cloud(project, directory, manifest)


def stage_cloud(
    project: Path,
    parent: str | None,
    stage: Path,
    assets: dict[str, Any],
    manifest: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Write replacement operands or inherit still-valid immutable raster references."""
    record = manifest.get("cloud")
    replacement = request if request is not None and request["action"] == "apply" else None
    if record is None and replacement is None:
        return None
    protection_path = stage_asset(project, stage, assets, PROTECTION_ROLE)
    protection_hash = _checksum(protection_path)
    with Image.open(protection_path) as image:
        width, height = image.size
    developed_id = manifest["developed_id"]
    old_area = None
    if record is not None:
        assert parent is not None
        old_area = read_cloud_area(project, project / "revisions" / parent, manifest)
    if replacement is not None:
        settings, area = replacement["settings"], replacement["area"]
    else:
        assert record is not None and old_area is not None
        settings = (
            record["settings"] if request is None else dict(record["settings"], enabled=False)
        )
        area = old_area

    namespace = stage / "cloud"
    namespace.mkdir()
    encoded_area, encoded_settings = _json_bytes(area), _json_bytes(settings)
    (namespace / "area.json").write_bytes(encoded_area)
    (namespace / "settings.json").write_bytes(encoded_settings)

    inherited: list[str] = []
    hashes: dict[str, str] = {}
    if (
        record is not None
        and old_area is not None
        and cloud_geometry_key(settings) == cloud_geometry_key(record["settings"])
        and area["coverage"] == old_area["coverage"]
    ):
        inherited.extend(("cloud/density16.png", "cloud/light16.png"))
        hashes.update(density_sha256=record["density_sha256"], light_sha256=record["light_sha256"])
    else:
        density, light = make_cloud_fields(settings, area, developed_id, (width, height))
        for name, pixels in (("density16.png", density), ("light16.png", light)):
            path = namespace / name
            Image.fromarray(pixels).save(path)
            hashes[CLOUD_MEMBERS[name]] = _checksum(path)

    if (
        record is not None
        and old_area is not None
        and area["clear"] == old_area["clear"]
        and area["focus"] == old_area["focus"]
        and protection_hash == record["protection_sha256"]
    ):
        inherited.append("cloud/clear16.png")
        hashes["clear_sha256"] = record["clear_sha256"]
    else:
        with Image.open(protection_path) as image:
            protection = np.asarray(image) != 0
        path = namespace / "clear16.png"
        Image.fromarray(make_cloud_clear(area, developed_id, protection)).save(path)
        hashes["clear_sha256"] = _checksum(path)

    if inherited:
        assert parent is not None
        inherit_revision_files(project, parent, stage, assets, inherited)
    return {
        "schema_version": 1,
        "algorithm": CLOUD_ALGORITHM,
        "developed_id": developed_id,
        "width": width,
        "height": height,
        "settings": settings,
        "settings_sha256": digest(encoded_settings),
        "area_sha256": digest(encoded_area),
        "protection_sha256": protection_hash,
        **hashes,
    }
