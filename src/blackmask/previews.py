"""Rebuildable native-result JPEGs; state.json remains the only pointer authority."""

import io
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .assets import saved_asset
from .ingest import srgb_profile
from .library import (
    ResultPreviewNameTooLong,
    StorageConfig,
    _check_result_preview_capacity,
    validate_library_project,
)
from .project import (
    ProjectError,
    _atomic_json,
    _directory,
    _exclusive_rename,
    _json_bytes,
    _read_json,
    check_space,
    digest,
    project_lock,
    read_project,
    read_revision,
)

JPEG_LIMIT = 16 * 1024**2
IDENTITY_FIELDS = {
    "schema_version",
    "kind",
    "photo_id",
    "folder_basename",
    "source_sha256",
    "developed_id",
    "revision",
    "revision_manifest_sha256",
    "status",
    "encoding",
}
LAYOUT_FIELDS = {"dimensions_wh", "photo_rectangle_xyxy"}


def _read_regular(parent: Path, name: str, limit: int, *, jpeg: bool = False) -> bytes:
    with _directory(parent) as directory:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_size > limit
                or (jpeg and info.st_nlink != 1)
            ):
                raise ProjectError("Preview output must be a bounded ordinary owned file")
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if len(data) > limit or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ProjectError("Preview output changed while reading")
            return data


def _identity(project: Path, state: dict[str, Any]) -> dict[str, Any]:
    source = _read_json(project, "source.json")
    revision = state["latest_result_revision"]
    manifest = read_revision(project, revision, state["developed_id"])
    from .effects import effects_stale

    if effects_stale(manifest) or not manifest["final_acceptable"]:
        raise ProjectError("Latest result cannot use a stale or prepared appearance")
    return {
        "schema_version": 1,
        "kind": "result-preview",
        "photo_id": source["library"]["photo_id"],
        "folder_basename": source["library"]["folder_basename"],
        "source_sha256": source["source_sha256"],
        "developed_id": state["developed_id"],
        "revision": revision,
        "revision_manifest_sha256": digest(
            saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        ),
        "status": "Accepted" if revision == state["accepted_revision"] else "Draft",
        "encoding": "native-result-jpeg-v1",
    }


def _validate_record(project: Path, value: Any, identity: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != IDENTITY_FIELDS | LAYOUT_FIELDS:
        raise ProjectError("Unrecognized result preview ownership record; preserved")
    for key in IDENTITY_FIELDS - {"revision", "revision_manifest_sha256", "status"}:
        if value[key] != identity[key] or type(value[key]) is not type(identity[key]):
            raise ProjectError("Foreign result preview identity; preserved")
    if value["status"] not in {"Draft", "Accepted"}:
        raise ProjectError("Invalid result preview label")
    revision = value["revision"]
    read_revision(project, revision, identity["developed_id"])
    if value["revision_manifest_sha256"] != digest(
        saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
    ):
        raise ProjectError("Stale result preview manifest binding")
    size, rectangle = value["dimensions_wh"], value["photo_rectangle_xyxy"]
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(v) is not int or v <= 0 for v in size)
        or size[0] > 1600
        or size[1] > 3200
        or not isinstance(rectangle, list)
        or len(rectangle) != 4
        or any(type(v) is not int for v in rectangle)
    ):
        raise ProjectError("Invalid preview dimensions")
    x0, y0, x1, y1 = rectangle
    if not (0 <= x0 < x1 <= size[0] and y0 == 0 < y1 < size[1] and max(x1 - x0, y1) <= 1600):
        raise ProjectError("Invalid preview photographic rectangle")
    return value


def _owned_jpeg(
    project: Path, parent: Path, name: str, identity: dict[str, Any]
) -> tuple[bytes, dict[str, Any]]:
    data = _read_regular(parent, name, JPEG_LIMIT, jpeg=True)
    try:
        with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
            comment = image.info.get("comment", b"")
            if not isinstance(comment, bytes) or len(comment) > 16384:
                raise ProjectError("Invalid preview ownership comment")
            record = _validate_record(project, json.loads(comment), identity)
            if (
                image.info.get("icc_profile") != srgb_profile()
                or list(image.size) != record["dimensions_wh"]
            ):
                raise ProjectError("Invalid preview profile or dimensions")
            if image.getexif() or "xmp" in image.info:
                raise ProjectError("Unexpected photographed metadata in preview")
    except (OSError, ValueError, TypeError, KeyError, Image.DecompressionBombError) as error:
        raise ProjectError(f"Unrecognized gallery JPEG; collision preserved: {error}") from error
    return data, record


def _base_status(state: dict[str, Any], status: str, **fields: Any) -> dict[str, Any]:
    return dict(
        status=status,
        latest_result_revision=state["latest_result_revision"],
        accepted_revision=state["accepted_revision"],
        **fields,
    )


def result_preview_status(project: Path, config: StorageConfig | None = None) -> dict[str, Any]:
    """Inspect bounded derivative identities without rendering or writing."""
    state = read_project(project, validate_drafts=False)
    source = _read_json(project, "source.json")
    if "library" not in source:
        return _base_status(state, "not_applicable")
    try:
        bundle = validate_library_project(project, config)
        assert bundle is not None and config is not None
        _check_result_preview_capacity(config, len(os.fsencode(bundle.name)))
        if state["latest_result_revision"] is None:
            return _base_status(state, "no_result")
        identity = _identity(project, state)
        data, record = _owned_jpeg(
            project, config.destination / "Results Preview", bundle.name + ".jpg", identity
        )
        receipt = json.loads(_read_regular(project, "preview.json", 16384))
        if receipt != dict(record, jpeg_sha256=digest(data)) or any(
            record[k] != v for k, v in identity.items()
        ):
            return _base_status(
                state,
                "pending",
                reason="stale",
                displayed_revision=record["revision"],
                displayed_status=record["status"],
            )
        if read_project(project, validate_drafts=False) != state:
            raise ProjectError("State changed during preview status; retry")
        return _base_status(state, "current", revision=record["revision"], label=record["status"])
    except ResultPreviewNameTooLong as error:
        return _base_status(
            state,
            "pending",
            reason="name_too_long",
            error=str(error),
            required_bytes=error.required_bytes,
            component_limit=error.component_limit,
        )
    except FileNotFoundError:
        return _base_status(
            state, "pending", reason="missing", recovery="Explicitly repair the result preview"
        )
    except (OSError, ValueError, TypeError, KeyError) as error:
        return _base_status(
            state,
            "pending",
            reason="configuration_required" if config is None else "publication_error",
            error=str(error),
        )


def _render_latest(project: Path, state: dict[str, Any]) -> np.ndarray:
    from .background import read_background
    from .effects import saved_shading
    from .export import render_background, render_black, saved_layers

    revision = state["latest_result_revision"]
    foreground, alpha, manifest = saved_layers(project, revision, state["developed_id"])
    weight, opacity = saved_shading(project, revision, alpha, manifest)
    background = read_background(project, saved_asset(project, f"revisions/{revision}"), manifest)
    check_space(project, foreground.nbytes * 8 + 16 * 1024**2)
    return (
        render_black(foreground, alpha, weight, opacity)
        if background is None
        else render_background(foreground, alpha, background, weight, opacity)
    )


def _encode_preview(pixels: np.ndarray, record: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    if pixels.dtype != np.uint16 or pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ProjectError("Preview requires native RGB16 Result pixels")
    with Image.fromarray(np.rint(pixels.astype(np.float64) / 257).astype(np.uint8)) as photo:
        photo.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        width = max(360, photo.width)
        font = ImageFont.load_default(size=18)
        text = f"{record['status']} | {record['revision']}"
        lines: list[str] = []
        line = ""
        for character in text:
            if font.getbbox(line + character)[2] > width - 24:
                lines.append(line)
                line = ""
            line += character
        lines.append(line)
        height = photo.height + max(44, 24 + len(lines) * 24)
        with Image.new("RGB", (width, height), "#181818") as canvas:
            left = (width - photo.width) // 2
            canvas.paste(photo, (left, 0))
            ImageDraw.Draw(canvas).multiline_text(
                (12, photo.height + 12), "\n".join(lines), font=font, fill="white", spacing=6
            )
            layout = {
                "dimensions_wh": [width, height],
                "photo_rectangle_xyxy": [left, 0, left + photo.width, photo.height],
            }
            output = io.BytesIO()
            canvas.save(
                output,
                format="JPEG",
                quality=85,
                optimize=True,
                icc_profile=srgb_profile(),
                comment=_json_bytes(dict(record, **layout)),
            )
    data = output.getvalue()
    if len(data) > JPEG_LIMIT:
        raise ProjectError("Encoded result preview exceeds its bounded size")
    with Image.open(io.BytesIO(data), formats=["JPEG"]) as verified:
        verified.load()
    return data, layout


def _publish_gallery_bytes(
    parent: Path, name: str, data: bytes, recheck: Any, *, replace_existing: bool
) -> None:
    with _directory(parent, create=True) as directory:
        held = os.fstat(directory)
        temporary = ".preview-" + uuid.uuid4().hex + ".tmp"
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory
        )
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

        def parent_current() -> None:
            with _directory(parent) as current:
                visible = os.fstat(current)
                if (held.st_dev, held.st_ino) != (visible.st_dev, visible.st_ino):
                    raise ProjectError("Gallery directory changed; retained temporary preserved")

        parent_current()
        recheck()
        if replace_existing:
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        else:
            _exclusive_rename(
                Path(temporary),
                Path(name),
                source_directory=directory,
                destination_directory=directory,
            )
        os.fsync(directory)
        parent_current()


def _publish_locked(
    project: Path, config: StorageConfig, *, demote: bool = False
) -> dict[str, Any]:
    state = read_project(project)
    bundle = validate_library_project(project, config)
    if bundle is None or state["latest_result_revision"] is None:
        return result_preview_status(project, config)
    _check_result_preview_capacity(config, len(os.fsencode(bundle.name)))
    identity = _identity(project, state)
    if demote:
        identity["status"] = "Draft"
    parent, name = config.destination / "Results Preview", bundle.name + ".jpg"
    captured = {
        name: saved_asset(project, name).read_bytes()
        for name in (
            "state.json",
            "source.json",
            f"revisions/{state['latest_result_revision']}/manifest.json",
        )
    }
    try:
        previous, _ = _owned_jpeg(project, parent, name, identity)
    except FileNotFoundError:
        previous = None
    pixels = _render_latest(project, state)
    data, layout = _encode_preview(pixels, identity)

    def recheck() -> None:
        if any(saved_asset(project, name).read_bytes() != raw for name, raw in captured.items()):
            raise ProjectError("Stale result preview inputs; publication refused")
        read_project(project)
        validate_library_project(project, config)
        try:
            current, _ = _owned_jpeg(project, parent, name, identity)
        except FileNotFoundError:
            current = None
        if current != previous:
            raise ProjectError("Gallery destination changed; existing bytes preserved")

    _publish_gallery_bytes(parent, name, data, recheck, replace_existing=previous is not None)
    if demote:
        return _base_status(state, "pending", reason="acceptance_demotion")
    receipt = dict(identity, **layout, jpeg_sha256=digest(data))
    try:
        old = _read_regular(project, "preview.json", 16384)
        value = json.loads(old)
        if not isinstance(value, dict) or "jpeg_sha256" not in value:
            raise ProjectError("Unrecognized preview receipt; preserved")
        _validate_record(project, {k: v for k, v in value.items() if k != "jpeg_sha256"}, identity)
    except FileNotFoundError:
        old = None

    def receipt_recheck() -> None:
        if any(saved_asset(project, name).read_bytes() != raw for name, raw in captured.items()):
            raise ProjectError("State changed before preview receipt publication")
        visible, _ = _owned_jpeg(project, parent, name, identity)
        if visible != data:
            raise ProjectError("Gallery changed before receipt publication")
        try:
            current = _read_regular(project, "preview.json", 16384)
        except FileNotFoundError:
            current = None
        if current != old:
            raise ProjectError("Receipt changed; preserved")

    _atomic_json(
        project / "preview.json",
        receipt,
        replace_existing=old is not None,
        validate_before_replace=receipt_recheck,
    )
    return result_preview_status(project, config)


def _refresh_result_preview_locked(project: Path, config: StorageConfig) -> dict[str, Any]:
    current = result_preview_status(project, config)
    if (
        current["status"] in {"current", "no_result", "not_applicable"}
        or current.get("reason") == "name_too_long"
    ):
        return current
    try:
        return _publish_locked(project, config)
    except (OSError, ValueError, TypeError, KeyError) as error:
        return dict(result_preview_status(project, config), status="pending", error=str(error))


def _demote_result_preview_locked(project: Path, config: StorageConfig) -> None:
    try:
        _publish_locked(project, config, demote=True)
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise ProjectError(
            f"Acceptance unchanged: Draft preview demotion failed: {error}"
        ) from error


def refresh_result_preview(
    project: Path, config: StorageConfig, *, expected_identity: dict[str, Any] | None = None
) -> dict[str, Any]:
    with project_lock(project):
        validate_library_project(project, config)
        if expected_identity is not None:
            from .operations import _check_draft_identity, guidance_draft_digest

            _check_draft_identity(project, expected_identity)
            if expected_identity.get("authoring_digest") != guidance_draft_digest(project):
                raise ProjectError("Stale preview repair authoring identity")
        return _refresh_result_preview_locked(project, config)
