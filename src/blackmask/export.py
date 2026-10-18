"""Single encoded-sRGB base renderer and honest lower-precision views."""

import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image

from .ingest import srgb_profile, write_master
from .project import (
    ProjectError,
    _asset,
    _json_bytes,
    _publish_new_directory,
    _root,
    _sync_directory,
    check_space,
    digest,
    load_master,
    project_lock,
    read_project,
    read_revision,
)


def render_black(foreground: np.ndarray, alpha16: np.ndarray) -> np.ndarray:
    if (
        foreground.dtype != np.uint16
        or foreground.ndim != 3
        or foreground.shape[2] != 3
        or alpha16.dtype != np.uint16
        or alpha16.shape != foreground.shape[:2]
    ):
        raise ValueError("Renderer requires aligned saved RGB16 and scalar alpha16")
    return np.rint(
        foreground.astype(np.float64) * (alpha16.astype(np.float64) / 65535)[..., None]
    ).astype(np.uint16)


def view_rgba(foreground: np.ndarray, alpha16: np.ndarray) -> np.ndarray:
    render_black(foreground, alpha16)  # Shared input contract, no flattened foreground reuse.
    return np.dstack(
        (
            np.rint(foreground.astype(np.float64) / 257).astype(np.uint8),
            np.rint(alpha16.astype(np.float64) / 257).astype(np.uint8),
        )
    )


def read_rgb16(path: Path) -> np.ndarray:
    """One saved foreground/corrected RGB16 precision and profile contract."""
    with tifffile.TiffFile(path) as image:
        page = image.pages[0]
        if not isinstance(page, tifffile.TiffPage):
            raise ProjectError("Invalid foreground RGB16 TIFF page")
        if (
            len(image.pages) != 1
            or int(page.compression) != 1
            or page.dtype != np.dtype("uint16")
            or page.tags.get(34675) is None
            or page.tags[34675].value != srgb_profile()
        ):
            raise ProjectError("Invalid foreground RGB16 profile/compression")
        return page.asarray()


def saved_layers(
    project: Path, revision: str, master_id: str, *, effects_off: bool = False
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    manifest = read_revision(project, revision, master_id)
    if (
        manifest.get("kind") not in {"matte", "repair", "effects"}
        or manifest.get("final_acceptable") is not True
    ):
        raise ProjectError("Export/review requires a complete matte, not prepared-only state")
    foreground = read_rgb16(_asset(project, f"revisions/{revision}/foreground_rgb16.tif"))
    with Image.open(_asset(project, f"revisions/{revision}/base_alpha16.png")) as image:
        if image.format != "PNG" or image.mode not in {"I;16", "I;16B", "I;16L"}:
            raise ProjectError("Invalid saved scalar alpha16")
        alpha = np.array(image)
    master, _ = load_master(project, master_id)
    if foreground.shape != master.shape:
        raise ProjectError("Saved foreground dimensions differ from master")
    render_black(foreground, alpha)
    with Image.open(_asset(project, f"revisions/{revision}/trimap.png")) as image:
        trimap = np.array(image)
    with Image.open(_asset(project, f"revisions/{revision}/supports/protection.png")) as image:
        protection = np.array(image)
    with Image.open(_asset(project, f"revisions/{revision}/supports/lock_values16.png")) as image:
        locked = np.array(image)
    if (
        trimap.shape != alpha.shape
        or not np.isin(trimap, [0, 128, 255]).all()
        or protection.shape != alpha.shape
        or locked.shape != alpha.shape
        or np.any(alpha[trimap == 0] != 0)
        or np.any(alpha[trimap == 255] != 65535)
        or not np.array_equal(alpha[protection != 0], locked[protection != 0])
    ):
        raise ProjectError("Saved matte core/lock validation failed")
    if manifest.get("kind") == "repair":
        from .repair import replay_repair

        replay_repair(project, revision)
    from .effects import selected_foreground

    foreground = selected_foreground(
        project, revision, foreground, alpha, manifest, effects_off=effects_off
    )
    return foreground, alpha, manifest


def publish_artifacts(stage: Path, destination: Path) -> None:
    """Validate identical reuse; differing or incomplete existing deliveries are preserved."""
    for path in stage.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted((p for p in stage.rglob("*") if p.is_dir()), reverse=True):
        _sync_directory(path)
    _sync_directory(stage)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_dir():
            raise ProjectError("Output collision; existing delivery preserved")
        expected = {
            str(p.relative_to(stage)): digest(p.read_bytes())
            for p in stage.rglob("*")
            if p.is_file()
        }
        actual = {
            str(p.relative_to(destination)): digest(p.read_bytes())
            for p in destination.rglob("*")
            if p.is_file() and not p.is_symlink()
        }
        if expected != actual or any(p.is_symlink() for p in destination.rglob("*")):
            raise ProjectError("Output collision: differing existing files preserved")
    else:
        _publish_new_directory(stage, destination)
        _sync_directory(destination.parent)


def export_project(
    project: Path, *, revision: str | None = None, draft: bool = False
) -> dict[str, Any]:
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        if revision is None:
            if draft:
                raise ProjectError("Draft export requires explicit revision")
            revision = state["accepted_revision"]
        if revision is None:
            raise ProjectError("No accepted result to export")
        if revision != state["accepted_revision"] and not draft:
            raise ProjectError("Unaccepted revision requires explicit --draft")
        foreground, alpha, manifest = saved_layers(project, revision, state["master_id"])
        if manifest.get("color_cleanup", {}).get("stale") and manifest["color_cleanup"]["enabled"]:
            raise ProjectError(
                "Stale enabled cleanup: scoped rebuild or explicit disable required before export"
            )
        before = _asset(project, "state.json").read_bytes()
        manifest_bytes = _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        check_space(project, foreground.nbytes * 12 + 1024**2)
        exports = _asset(project, "exports")
        exports.mkdir(exist_ok=True)
        label = f"{revision}-DRAFT" if draft else revision
        stage = Path(tempfile.mkdtemp(prefix=".export-", dir=exports))
        black = render_black(foreground, alpha)
        write_master(stage / "black_rgb16.tif", black)
        Image.fromarray(alpha).save(stage / "alpha16.png")
        Image.fromarray(np.rint(black.astype(np.float64) / 257).astype(np.uint8)).save(
            stage / "black_RGB8_VIEW.png"
        )
        Image.fromarray(view_rgba(foreground, alpha)).save(stage / "transparent_RGBA8_VIEW.png")
        if not np.array_equal(tifffile.imread(stage / "black_rgb16.tif"), black):
            raise ProjectError("RGB16 export round trip failed")
        with Image.open(stage / "alpha16.png") as image:
            if (
                not np.array_equal(np.array(image), alpha)
                or "icc_profile" in image.info
                or "gamma" in image.info
            ):
                raise ProjectError("Scalar16 export round trip/profile failed")
        record = {
            "schema_version": 1,
            "revision": revision,
            "master_id": state["master_id"],
            "draft": draft,
            "label": "DRAFT - unaccepted explicit export"
            if draft
            else "Human-accepted saved revision",
            "revision_manifest_sha256": digest(manifest_bytes),
            "compositing": manifest["compositing"],
            "color_cleanup": manifest.get("color_cleanup", {"enabled": False}),
            "views": "RGB8/RGBA8 reduced color/alpha precision; straight RGB is not alpha-multiplied; selected saved cleanup; no shading",
            "files": {p.name: digest(p.read_bytes()) for p in stage.iterdir() if p.is_file()},
        }
        (stage / "manifest.json").write_bytes(_json_bytes(record))
        (stage / "README.txt").write_text(
            record["label"]
            + "\nRGB16 black TIFF and scalar alpha16 are lossless. "
            + record["views"]
            + "\n"
        )
        if (
            before != _asset(project, "state.json").read_bytes()
            or manifest_bytes != _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        ):
            raise ProjectError("Stale export state or saved inputs")
        saved_layers(project, revision, state["master_id"])
        destination = _asset(project, f"exports/{label}")
        publish_artifacts(stage, destination)
        return {
            "revision": revision,
            "draft": draft,
            "directory": str(destination),
            "manifest_file": str(destination / "manifest.json"),
        }
