"""Single encoded-sRGB base renderer and honest lower-precision views."""

import hashlib
import json
import os
import shutil
import sys
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
from .spatial_fade import SpatialFadeOperands, blend_background_float, spatial_fade_amount


def shading_factor(
    shape: tuple[int, ...], weight16: np.ndarray | None, opacity: float
) -> np.ndarray:
    if type(opacity) not in {int, float} or not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError("Shading opacity must be finite in [0,1]")
    if weight16 is None:
        if opacity != 0:
            raise ValueError("Nonzero shading opacity requires saved W16")
        return np.ones(shape, dtype=np.float64)
    if weight16.dtype != np.uint16 or weight16.shape != shape:
        raise ValueError("Shading requires aligned scalar W16")
    return 1 - opacity * (weight16.astype(np.float64) / 65535)


def _validate_render_inputs(foreground: np.ndarray, alpha16: np.ndarray) -> None:
    if (
        foreground.dtype != np.uint16
        or foreground.ndim != 3
        or foreground.shape[2] != 3
        or alpha16.dtype != np.uint16
        or alpha16.shape != foreground.shape[:2]
    ):
        raise ValueError("Renderer requires aligned saved RGB16 and scalar alpha16")


def _spatial_appearance(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    spatial_fade: SpatialFadeOperands,
    fade_background16: np.ndarray | None,
) -> np.ndarray:
    if fade_background16 is None:
        raise ValueError("Active spatial fade requires its aligned selected background target")
    if fade_background16.dtype != np.uint16 or fade_background16.shape != foreground.shape:
        raise ValueError("Spatial fade target must be aligned RGB16")
    result = np.empty(foreground.shape, np.float64)
    for start in range(0, alpha16.shape[0], 64):
        rows = slice(start, start + 64)
        operands = SpatialFadeOperands(
            spatial_fade.weight16[rows], spatial_fade.protection[rows], spatial_fade.record
        )
        amount = spatial_fade_amount(foreground[rows], alpha16[rows], operands)
        result[rows] = blend_background_float(foreground[rows], fade_background16[rows], amount)
    return result


def _foreground_contribution(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    *,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
) -> np.ndarray:
    _validate_render_inputs(foreground, alpha16)
    factor = shading_factor(alpha16.shape, weight16, opacity)
    if (
        spatial_fade is not None
        and spatial_fade.record["enabled"]
        and not spatial_fade.record["stale"]
    ):
        if opacity != 0:
            raise ValueError("Spatial fade and inward shading are mutually exclusive")
        appearance = _spatial_appearance(foreground, alpha16, spatial_fade, fade_background16)
        appearance *= (alpha16.astype(np.float64) / 65535)[..., None]
        return appearance
    return (
        foreground.astype(np.float64)
        * (alpha16.astype(np.float64) / 65535)[..., None]
        * factor[..., None]
    )


def render_black(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    *,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
) -> np.ndarray:
    return np.rint(
        _foreground_contribution(
            foreground,
            alpha16,
            weight16,
            opacity,
            spatial_fade=spatial_fade,
            fade_background16=fade_background16,
        )
    ).astype(np.uint16)


def render_background(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    background16: np.ndarray,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    *,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
) -> np.ndarray:
    contribution = _foreground_contribution(
        foreground,
        alpha16,
        weight16,
        opacity,
        spatial_fade=spatial_fade,
        fade_background16=fade_background16,
    )
    if background16.dtype != np.uint16 or background16.shape != foreground.shape:
        raise ValueError("Background requires aligned saved RGB16")
    return np.rint(
        contribution
        + background16.astype(np.float64) * (1 - alpha16.astype(np.float64) / 65535)[..., None]
    ).astype(np.uint16)


def view_rgba(
    foreground: np.ndarray,
    alpha16: np.ndarray,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    *,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
) -> np.ndarray:
    _validate_render_inputs(foreground, alpha16)
    factor = shading_factor(alpha16.shape, weight16, opacity)
    if (
        spatial_fade is not None
        and spatial_fade.record["enabled"]
        and not spatial_fade.record["stale"]
    ):
        if opacity != 0:
            raise ValueError("Spatial fade and inward shading are mutually exclusive")
        appearance = _spatial_appearance(foreground, alpha16, spatial_fade, fade_background16)
    else:
        appearance = foreground.astype(np.float64) * factor[..., None]
    return np.dstack(
        (
            np.rint(appearance / 257).astype(np.uint8),
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
    project: Path,
    revision: str,
    master_id: str,
    *,
    effects_off: bool = False,
    exposure_off: bool = False,
    shadow_fade_off: bool = False,
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
    from .effects import effects_stale, saved_shading, selected_foreground

    effects_off = effects_off or effects_stale(manifest)
    saved_shading(project, revision, alpha, manifest, effects_off=effects_off)

    foreground = selected_foreground(
        project,
        revision,
        foreground,
        alpha,
        manifest,
        effects_off=effects_off,
        exposure_off=exposure_off,
        shadow_fade_off=shadow_fade_off,
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
    project: Path,
    *,
    revision: str | None = None,
    draft: bool = False,
    framing: dict[str, int] | None = None,
    framed_transparent: bool = False,
    series: dict[str, object] | None = None,
    expected_master_id: str | None = None,
    expected_revision_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    if type(framed_transparent) is not bool:
        raise ValueError("framed_transparent must be a boolean")
    if series is not None and framing is not None:
        raise ValueError("Series settings and pixel margins are mutually exclusive")
    if series is None and (
        expected_master_id is not None or expected_revision_manifest_sha256 is not None
    ):
        raise ValueError("Expected presentation identities require series settings")
    if series is not None:
        if type(draft) is not bool or (expected_master_id is None) != (
            expected_revision_manifest_sha256 is None
        ):
            raise ValueError(
                "Series export requires a boolean draft flag and paired expected identities"
            )
        if any(
            value is not None
            and (
                not isinstance(value, str)
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            )
            for value in (expected_master_id, expected_revision_manifest_sha256)
        ):
            raise ValueError("Series expected identities must be SHA-256 hex strings")
    if framed_transparent and framing is None and series is None:
        raise ValueError("Transparent framing requires explicit margins")
    project = _root(project)
    with project_lock(project):
        if framing is not None or series is not None:
            return _export_framed(
                project,
                revision,
                draft,
                framing,
                framed_transparent,
                series=series,
                expected_master_id=expected_master_id,
                expected_revision_manifest_sha256=expected_revision_manifest_sha256,
            )
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
        return _export_native_locked(
            project,
            revision=revision,
            draft=draft,
            state=state,
            foreground=foreground,
            alpha=alpha,
            manifest=manifest,
        )


def _export_native_locked(
    project: Path,
    *,
    revision: str,
    draft: bool,
    state: dict[str, Any],
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical native delivery using arrays validated under the caller's lock."""
    from .effects import effects_stale, saved_shading, saved_spatial_fade

    if effects_stale(manifest):
        raise ProjectError(
            "Stale enabled cleanup/shading/local exposure/Shadow fade: scoped rebuild or explicit disable required before export"
        )
    weight, opacity = saved_shading(project, revision, alpha, manifest)
    spatial = saved_spatial_fade(project, revision, alpha, manifest)
    before = _asset(project, "state.json").read_bytes()
    manifest_bytes = _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
    check_space(
        project,
        foreground.nbytes * (22 if "background" in manifest else 18)
        + (
            alpha.nbytes * 3 + len(_json_bytes(manifest["spatial_fade"]))
            if "spatial_fade" in manifest
            else 0
        )
        + 1024**2,
    )
    exports = _asset(project, "exports")
    exports.mkdir(exist_ok=True)
    label = f"{revision}-DRAFT" if draft else revision
    stage = Path(tempfile.mkdtemp(prefix=".export-", dir=exports))
    from .background import read_background

    background = read_background(_asset(project, f"revisions/{revision}"), manifest)
    target = (
        background
        if background is not None
        else np.zeros_like(foreground)
        if spatial is not None
        else None
    )
    if background is not None:
        result_pixels = render_background(
            foreground,
            alpha,
            background,
            weight,
            opacity,
            spatial_fade=spatial,
            fade_background16=target,
        )
        write_master(stage / "result_rgb16.tif", result_pixels)
        Image.fromarray(np.rint(result_pixels.astype(np.float64) / 257).astype(np.uint8)).save(
            stage / "result_RGB8_VIEW.png"
        )
        for saved, delivered in (
            ("background/background_rgb16.tif", "background_rgb16.tif"),
            ("background/settings.json", "background_settings.json"),
        ):
            (stage / delivered).write_bytes(
                _asset(project, f"revisions/{revision}/{saved}").read_bytes()
            )
        if not np.array_equal(read_rgb16(stage / "result_rgb16.tif"), result_pixels):
            raise ProjectError("Result RGB16 export round trip failed")
    black = render_black(
        foreground, alpha, weight, opacity, spatial_fade=spatial, fade_background16=target
    )
    write_master(stage / "black_rgb16.tif", black)
    Image.fromarray(alpha).save(stage / "alpha16.png")
    Image.fromarray(np.rint(black.astype(np.float64) / 257).astype(np.uint8)).save(
        stage / "black_RGB8_VIEW.png"
    )
    Image.fromarray(
        view_rgba(
            foreground, alpha, weight, opacity, spatial_fade=spatial, fade_background16=target
        )
    ).save(stage / "transparent_RGBA8_VIEW.png")
    if not np.array_equal(tifffile.imread(stage / "black_rgb16.tif"), black):
        raise ProjectError("RGB16 export round trip failed")
    with Image.open(stage / "alpha16.png") as image:
        if (
            not np.array_equal(np.array(image), alpha)
            or "icc_profile" in image.info
            or "gamma" in image.info
        ):
            raise ProjectError("Scalar16 export round trip/profile failed")
    write_master(stage / "foreground_rgb16.tif", foreground)
    if "local_exposure" in manifest:
        unexposed, _, _ = saved_layers(
            project, revision, state["master_id"], exposure_off=True, shadow_fade_off=True
        )
        write_master(stage / "unexposed_foreground_rgb16.tif", unexposed)
        base = _asset(project, f"revisions/{revision}/foreground_rgb16.tif")
        (stage / "base_foreground_rgb16.tif").write_bytes(base.read_bytes())
        for name in (
            "support16.png",
            "protection16.png",
            "alpha16.png",
            "settings.json",
            "area.json",
        ):
            asset = f"effects/exposure/{name}"
            if asset in manifest["files"]:
                (stage / ("exposure_" + name)).write_bytes(
                    _asset(project, f"revisions/{revision}/{asset}").read_bytes()
                )
    if "shadow_fade" in manifest:
        unfaded, _, _ = saved_layers(project, revision, state["master_id"], shadow_fade_off=True)
        write_master(stage / "unfaded_foreground_rgb16.tif", unfaded)
        if "local_exposure" not in manifest:
            write_master(stage / "unexposed_foreground_rgb16.tif", unfaded)
            (stage / "base_foreground_rgb16.tif").write_bytes(
                _asset(project, f"revisions/{revision}/foreground_rgb16.tif").read_bytes()
            )
        for name in (
            "support16.png",
            "protection16.png",
            "alpha16.png",
            "settings.json",
            "area.json",
        ):
            asset = f"effects/shadow-fade/{name}"
            if asset in manifest["files"]:
                (stage / ("shadow_fade_" + name)).write_bytes(
                    _asset(project, f"revisions/{revision}/{asset}").read_bytes()
                )
    write_master(stage / "source_rgb16.tif", load_master(project, state["master_id"])[0])
    if "spatial_fade" in manifest:
        from .spatial_fade import SPATIAL_FADE_FILES

        for name in SPATIAL_FADE_FILES:
            (stage / ("spatial_fade_" + name)).write_bytes(
                _asset(project, f"revisions/{revision}/effects/spatial-fade/{name}").read_bytes()
            )
    for name in ("shadow_weight16.png", "corrected_rgb16.tif", "recipe.toml"):
        if name in manifest["files"]:
            (stage / name).write_bytes(_asset(project, f"revisions/{revision}/{name}").read_bytes())
    for effect, name in (
        ("color_cleanup", "effects/settings.json"),
        ("shading", "effects/shading/settings.json"),
    ):
        if effect in manifest:
            (stage / (effect + "_settings.json")).write_bytes(_json_bytes(manifest[effect]))
    record = {
        "schema_version": 1,
        "revision": revision,
        "master_id": state["master_id"],
        "draft": draft,
        "label": "DRAFT - unaccepted explicit export" if draft else "Human-accepted saved revision",
        "revision_manifest_sha256": digest(manifest_bytes),
        "compositing": manifest["compositing"],
        "color_cleanup": manifest.get("color_cleanup", {"enabled": False}),
        "shading": manifest.get("shading", {"enabled": False}),
        **({"local_exposure": manifest["local_exposure"]} if "local_exposure" in manifest else {}),
        **({"shadow_fade": manifest["shadow_fade"]} if "shadow_fade" in manifest else {}),
        **({"spatial_fade": manifest["spatial_fade"]} if "spatial_fade" in manifest else {}),
        **({"background": manifest["background"]} if "background" in manifest else {}),
        "views": "RGB8/RGBA8 reduced color/alpha precision; straight RGB is not alpha-multiplied; selected saved cleanup; baked shading at saved p; editable W16 plus p retained separately"
        + (
            "; selected foreground includes linear-sRGB local exposure once; unexposed foreground and independent support/protection/alpha/settings retained"
            if "local_exposure" in manifest
            else ""
        )
        + (
            "; replay unexposed -> exposure once -> unfaded -> linear-sRGB Shadow fade once -> selected foreground -> encoded-sRGB shading and alpha once; selected foreground is already faded; independent fade operands retained"
            if "shadow_fade" in manifest
            else ""
        ),
        **(
            {
                "result_compositing": "encoded-sRGB float64 round ties-to-even(F*A*H+B*(1-A)); H=1-opacity*W16/65535, A=alpha16/65535; selected foreground already includes exposure/fade; B is saved background RGB16; processed sRGB TIFF, not sensor RAW"
            }
            if "background" in manifest
            else {}
        ),
        "files": {p.name: digest(p.read_bytes()) for p in stage.iterdir() if p.is_file()},
    }
    if "spatial_fade" in manifest:
        record["views"] += (
            "; When enabled, Fade into background blends selected pre-spatial foreground toward the selected background in linear sRGB before encoded alpha compositing; transparent RGB retains that tint and alpha is unchanged. When disabled, the active inward-shading setting still applies. foreground_rgb16.tif remains pre-spatial and pre-shading; spatial_fade_* operands include inactive vectors."
        )
        if manifest["spatial_fade"]["enabled"] and "result_compositing" in record:
            record["result_compositing"] = (
                "round(blend_linear_srgb(F,B,q)*A+B*(1-A)); q from delivered combined W16, explicit protection and independent highlight preservation; exact q=0/q=1 endpoints"
            )
    (stage / "manifest.json").write_bytes(_json_bytes(record))
    (stage / "README.txt").write_text(
        record["label"]
        + "\nRGB16 black TIFF and scalar alpha16 are lossless. "
        + record["views"]
        + (
            "\nResult RGB16 TIFF uses the saved chosen background; black TIFF stays pure black. Background RGB16/settings are independent editable operands; foreground RGB16 is pre-shading, already exposed/faded. Reconstruct: "
            + record["result_compositing"]
            + ". All RGB16 TIFFs carry sRGB profiles. Algorithm: "
            + manifest["background"]["algorithm"]
            if "background" in manifest
            else ""
        )
        + "\n"
    )
    if (
        before != _asset(project, "state.json").read_bytes()
        or manifest_bytes != _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
    ):
        raise ProjectError("Stale export state or saved inputs")
    read_revision(project, revision, state["master_id"])
    destination = _asset(project, f"exports/{label}")
    if "spatial_fade" in manifest:
        expected = {p.name: _file_digest(p) for p in stage.iterdir()}
        reused = destination.exists() or destination.is_symlink()
        if reused:
            _check_flat_delivery(destination, set(expected))
        try:
            publish_artifacts(stage, destination)
            if reused:
                _sync_directory(destination.parent)
        except OSError as error:
            if destination.exists():
                raise ProjectError(
                    f"Native editable delivery visible at {destination}, but durability is unconfirmed; preserve it and retry identical export: {error}"
                ) from error
            raise
        _check_flat_delivery(destination, set(expected))
        if any(_file_digest(destination / name) != checksum for name, checksum in expected.items()):
            raise ProjectError(
                f"Native editable delivery changed during publication at {destination}"
            )
        if reused:
            # The current attempt's byte-verified duplicate is disposable only
            # after the native delivery and its parent directory are durable.
            try:
                shutil.rmtree(stage)
            except OSError as error:
                raise ProjectError(
                    f"Native editable delivery is durably published at {destination}, but duplicate "
                    f"stage cleanup failed at {stage}; inspect remaining stage files: {error}"
                ) from error
    else:
        publish_artifacts(stage, destination)
    return {
        "revision": revision,
        "draft": draft,
        "directory": str(destination),
        "manifest_file": str(destination / "manifest.json"),
    }


def _pixel_digest(pixels: np.ndarray) -> str:
    value = hashlib.sha256()
    for row in pixels:
        value.update(row.tobytes())
    return value.hexdigest()


def _file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_framed_rgb8(path: Path, pixels: np.ndarray) -> str:
    """Keep conversion scratch to one row, rather than an expanded float64 RGB."""
    expected = hashlib.sha256()
    with Image.new("RGB", (pixels.shape[1], pixels.shape[0])) as image:
        for y, row in enumerate(pixels):
            converted = np.rint(row.astype(np.float64) / 257).astype(np.uint8)
            expected.update(converted.tobytes())
            with Image.fromarray(converted[None]) as strip:
                image.paste(strip, (0, y))
        image.save(path, icc_profile=srgb_profile())
    return expected.hexdigest()


def _verify_framed_png(path: Path, mode: str, size: tuple[int, int], expected: str) -> None:
    with Image.open(path, formats=["PNG"]) as image:
        if (
            image.mode != mode
            or image.size != size
            or image.info.get("icc_profile") != srgb_profile()
        ):
            raise ProjectError("Framed viewing PNG round trip/profile failed")
        actual = hashlib.sha256()
        for y in range(size[1]):
            with image.crop((0, y, size[0], y + 1)) as row:
                actual.update(row.tobytes())
        if actual.hexdigest() != expected:
            raise ProjectError("Framed viewing PNG round trip/profile failed")


def _check_flat_delivery(directory: Path, names: set[str]) -> None:
    """Compact presentations have exactly these regular files, including on reuse."""
    if directory.is_symlink() or not directory.is_dir():
        raise ProjectError("Output collision; existing delivery preserved")
    members = list(directory.iterdir())
    if {path.name for path in members} != names or any(
        path.is_symlink() or not path.is_file() for path in members
    ):
        raise ProjectError("Output collision: unexpected delivery members preserved")


def _editable_companion_binding(
    directory: Path,
    manifest: dict[str, Any],
    revision_manifest_sha256: str,
    draft: bool,
) -> dict[str, Any]:
    """Verify portable native bytes and bind the full inventory, including its notes."""
    if directory.name != f"{manifest['revision']}{'-DRAFT' if draft else ''}":
        raise ProjectError("Invalid native editable companion directory identity")
    if directory.is_symlink() or (directory / "manifest.json").is_symlink():
        raise ProjectError("Output collision: symlinked native editable companion")
    raw = (directory / "manifest.json").read_bytes()
    native = json.loads(raw)
    if any(
        native.get(key) != value
        for key, value in (
            ("revision", manifest["revision"]),
            ("master_id", manifest["master_id"]),
            ("draft", draft),
            ("revision_manifest_sha256", revision_manifest_sha256),
            ("spatial_fade", manifest["spatial_fade"]),
            ("background", manifest.get("background")),
        )
    ):
        raise ProjectError("Native editable companion identity differs from presentation")
    names = set(native["files"]) | {"README.txt", "manifest.json"}
    _check_flat_delivery(directory, names)
    hashes = {name: _file_digest(directory / name) for name in names - {"manifest.json"}}
    if any(hashes[name] != value for name, value in native["files"].items()):
        raise ProjectError("Native editable companion file hash mismatch")
    return {
        "directory_name": directory.name,
        "manifest_sha256": digest(raw),
        "files_sha256": hashes,
    }


def _export_framed(
    project: Path,
    revision: str | None,
    draft: bool,
    framing: dict[str, int] | None,
    transparent: bool,
    *,
    series: dict[str, object] | None = None,
    expected_master_id: str | None = None,
    expected_revision_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Publish one compact presentation while holding the canonical project lock."""
    from .background import read_background
    from .effects import effects_stale, saved_shading, saved_spatial_fade
    from .framing import frame_result, frame_transparent, framed_geometry, validate_margins

    # Capture before validation, then bind the actual returned objects to these bytes.
    # Cooperative writers use the project lock; this is not a hostile-writer snapshot.
    captured = {name: _asset(project, name).read_bytes() for name in ("state.json", "source.json")}
    state = read_project(project)
    if expected_master_id is not None and state["master_id"] != expected_master_id:
        raise ProjectError("Stale series source identity; reload the selected photo")
    if _json_bytes(json.loads(captured["state.json"])) != _json_bytes(state):
        raise ProjectError("Stale framed export state")
    if revision is None:
        if draft:
            raise ProjectError("Draft export requires explicit revision")
        revision = state["accepted_revision"]
    if revision is None:
        raise ProjectError("No accepted result to export")
    if revision != state["accepted_revision"] and not draft:
        raise ProjectError("Unaccepted revision requires explicit --draft")
    manifest_name = f"revisions/{revision}/manifest.json"
    captured[manifest_name] = _asset(project, manifest_name).read_bytes()
    if (
        expected_revision_manifest_sha256 is not None
        and digest(captured[manifest_name]) != expected_revision_manifest_sha256
    ):
        raise ProjectError("Stale series revision manifest; reload the selected result")
    foreground, alpha, manifest = saved_layers(project, revision, state["master_id"])
    if _json_bytes(json.loads(captured[manifest_name])) != _json_bytes(manifest):
        raise ProjectError("Stale framed export revision manifest")
    master, metadata = load_master(project, state["master_id"])
    source = json.loads(captured["source.json"])
    if source["master_id"] != state["master_id"] or source["metadata"] != metadata:
        raise ProjectError("Stale framed export source")
    del master
    if any(_asset(project, name).read_bytes() != value for name, value in captured.items()):
        raise ProjectError("Stale framed export state or saved inputs")
    if effects_stale(manifest):
        raise ProjectError("Stale enabled appearance: rebuild or explicitly disable before export")
    size = (foreground.shape[1], foreground.shape[0])
    sampling = None
    series_settings = None
    settings_record: dict[str, object] = {}
    if series is not None:
        from .series_framing import (
            compute_series_layout,
            estimate_series_resources,
            series_sampling_plan,
            validate_series_settings,
        )

        series_settings = validate_series_settings(series)
        sampling = series_sampling_plan(compute_series_layout(alpha, series_settings))
        width, height = sampling.layout.output_dimensions_wh
        source_rect = sampling.layout.subject_bounds_xyxy
        settings_record.update(series_settings.to_dict())
    else:
        settings = validate_margins(framing, size)
        width, height, source_rect = framed_geometry(size, settings)
        settings_record.update(settings.to_dict())
    # Disk admission retains the native allowance and adds framed TIFF/PNG payloads
    # with headroom. RAM use is separate; expanded variants are processed in sequence.
    check_space(
        project,
        foreground.nbytes * (22 if "background" in manifest else 18)
        + (
            alpha.nbytes * 3 + len(_json_bytes(manifest["spatial_fade"]))
            if "spatial_fade" in manifest
            else 0
        )
        + 16 * width * height
        + 2 * 1024**2,
    )
    weight, opacity = saved_shading(project, revision, alpha, manifest)
    spatial = saved_spatial_fade(project, revision, alpha, manifest)
    background = read_background(_asset(project, f"revisions/{revision}"), manifest)
    # Native layer conversion/readback and framed rendering run sequentially. This
    # conservative native envelope includes retained layers, float conversion and
    # allocator scratch; it is an admission estimate, not measured resident memory.
    native_peak = foreground.nbytes * 28 + alpha.nbytes * 8 if "spatial_fade" in manifest else 0
    if (
        native_peak
        and max(native_peak, foreground.nbytes * 8 + alpha.nbytes * 8 + 16 * width * height)
        > sys.maxsize
    ):
        raise ProjectError("Paired export memory estimate exceeds allocation bounds")
    if sampling is not None:
        estimate_series_resources(
            sampling,
            retained_native_bytes=foreground.nbytes
            + alpha.nbytes
            + (0 if weight is None else weight.nbytes)
            + (0 if background is None else background.nbytes)
            + (0 if spatial is None else spatial.weight16.nbytes + spatial.protection.nbytes),
            transparent=transparent,
            **({"spatial_fade_pixels": alpha.size} if spatial is not None else {}),
            **({"native_export_peak_bytes": native_peak} if native_peak else {}),
        )
    variants = ["result_rgb16.tif", "result_RGB8_VIEW.png"]
    if transparent:
        variants.append("transparent_RGBA8_VIEW.png")
    native_names = {
        "foreground_rgb16.tif",
        "base_alpha16.png",
        "corrected_rgb16.tif",
        "shadow_weight16.png",
        "trimap.png",
        "supports/protection.png",
        "supports/lock_values16.png",
        "background/background_rgb16.tif",
        "background/settings.json",
        "effects/settings.json",
        *(
            f"effects/{effect}/{name}"
            for effect in ("shading", "exposure", "shadow-fade")
            for name in (
                "support16.png",
                "protection16.png",
                "alpha16.png",
                "settings.json",
                "area.json",
            )
        ),
    }
    record = {
        "schema_version": 1,
        "kind": "framed-presentation",
        "revision": revision,
        "master_id": state["master_id"],
        "revision_manifest_sha256": digest(captured[manifest_name]),
        "draft": draft,
        "label": "DRAFT - explicit framed presentation"
        if draft
        else "Framed presentation of accepted revision; framing has not been separately accepted",
        "source_dimensions_wh": list(size),
        "margins": settings_record,
        "output_dimensions_wh": [width, height],
        "source_rect_xyxy": list(source_rect),
        "algorithm": "saved-backdrop-edge-padding-v1",
        "encoding": {
            "result": "uncompressed processed sRGB RGB16 TIFF; native samples copied exactly",
            "views": "sRGB RGB8/RGBA8 reduced precision; straight RGB, zero RGBA margins",
            "icc_profile_sha256": digest(srgb_profile()),
        },
        "variants": variants,
        "effects": {
            name: {
                "enabled": manifest.get(name, {}).get("enabled", False),
                "record_sha256": digest(_json_bytes(manifest[name])) if name in manifest else None,
            }
            for name in (
                "color_cleanup",
                "shading",
                "local_exposure",
                "shadow_fade",
                *(("spatial_fade",) if "spatial_fade" in manifest else ()),
            )
        },
        "background": {
            "record_sha256": digest(_json_bytes(manifest["background"])),
            "background_sha256": manifest["background"]["background_sha256"],
        }
        if "background" in manifest
        else None,
        "native_assets": {
            f"masters/{state['master_id']}.tif": source["master_file_sha256"],
            **{
                f"revisions/{revision}/{name}": value
                for name, value in manifest["files"].items()
                if name in native_names
            },
        },
    }
    if sampling is not None and series_settings is not None:
        from PIL import __version__ as pillow_version

        record.pop("margins")
        record.pop("source_rect_xyxy")
        record.update(
            {
                "kind": "series-framed-presentation",
                "source_record_sha256": digest(captured["source.json"]),
                "label": "DRAFT - explicit resized series presentation"
                if draft
                else "Resized series presentation of accepted revision; composition has not been separately accepted",
                "settings": settings_record,
                "layout": sampling.layout.to_dict(),
                "sampling": sampling.to_dict(),
                "algorithm": "series-lanczos-premultiplied-v1",
                "backend": {
                    "name": "Pillow",
                    "version": pillow_version,
                    "mode": "F",
                    "filter": "Lanczos",
                    "source_box": "float32",
                    "reducing_gap": None,
                    "quantization": "NumPy ties-to-even",
                },
                "encoding": {
                    "result": "uncompressed processed sRGB RGB16 TIFF; resampled existing detail",
                    "views": "sRGB RGB8/RGBA8 reduced precision; straight RGB, zero RGB where quantized alpha is zero",
                    "icc_profile_sha256": digest(srgb_profile()),
                },
                "background": {
                    "algorithm": manifest.get("background", {}).get("algorithm", "legacy-black"),
                    "settings": manifest.get("background", {}).get(
                        "settings", {"color_srgb": "#000000", "variation": 0.0}
                    ),
                    "placement": "recipe-regenerated-at-final-output-size",
                    "native_record_sha256": digest(_json_bytes(manifest["background"]))
                    if "background" in manifest
                    else None,
                },
            }
        )
    companion = None
    companion_binding = None
    if "spatial_fade" in manifest:
        companion_directory = _asset(project, f"exports/{revision}{'-DRAFT' if draft else ''}")
        try:
            companion = _export_native_locked(
                project,
                revision=revision,
                draft=draft,
                state=state,
                foreground=foreground,
                alpha=alpha,
                manifest=manifest,
            )
            companion_binding = _editable_companion_binding(
                companion_directory, manifest, digest(captured[manifest_name]), draft
            )
        except (OSError, ValueError, MemoryError) as error:
            if companion_directory.exists():
                raise ProjectError(
                    f"Incomplete framed delivery pair. Native folder is visible at {companion_directory}; inspect or retry identical export. {error}"
                ) from error
            raise
        record["editable_companion"] = companion_binding
    try:
        identity = digest(_json_bytes(record))
        label = f"{revision}-DRAFT" if draft else revision
        delivery_mode = "series-framed" if sampling is not None else "framed"
        destination = _asset(project, f"exports/{label}-{delivery_mode}-{identity}")
        names = {*variants, "README.txt", "manifest.json"}
        reused = destination.exists() or destination.is_symlink()
        if reused:
            _check_flat_delivery(destination, names)
        exports = _asset(project, "exports")
        exports.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".export-", dir=exports))
        if sampling is not None:
            from .series_framing import render_series

            del background
            result = render_series(
                foreground,
                alpha,
                sampling,
                weight16=weight,
                opacity=opacity,
                background_settings=manifest.get("background", {}).get("settings"),
                spatial_fade=spatial,
            )
        else:
            native = (
                render_black(
                    foreground,
                    alpha,
                    weight,
                    opacity,
                    spatial_fade=spatial,
                    fade_background16=background
                    if background is not None
                    else np.zeros_like(foreground)
                    if spatial is not None
                    else None,
                )
                if background is None
                else render_background(
                    foreground,
                    alpha,
                    background,
                    weight,
                    opacity,
                    spatial_fade=spatial,
                    fade_background16=background,
                )
            )
            result = frame_result(native, background, settings)
            del native
        result_digest = _pixel_digest(result)
        write_master(stage / "result_rgb16.tif", result)
        view_digest = _write_framed_rgb8(stage / "result_RGB8_VIEW.png", result)
        del result
        # Release the expanded render before any expanded readback or next variant.
        restored = read_rgb16(stage / "result_rgb16.tif")
        if restored.shape != (height, width, 3) or _pixel_digest(restored) != result_digest:
            raise ProjectError("Framed RGB16 export round trip failed")
        del restored
        _verify_framed_png(stage / "result_RGB8_VIEW.png", "RGB", (width, height), view_digest)
        if transparent:
            rgba = (
                render_series(
                    foreground,
                    alpha,
                    sampling,
                    weight16=weight,
                    opacity=opacity,
                    background_settings=manifest.get("background", {}).get("settings"),
                    transparent=True,
                    spatial_fade=spatial,
                )
                if sampling is not None
                else frame_transparent(
                    view_rgba(
                        foreground,
                        alpha,
                        weight,
                        opacity,
                        spatial_fade=spatial,
                        fade_background16=background
                        if background is not None
                        else np.zeros_like(foreground)
                        if spatial is not None
                        else None,
                    ),
                    settings,
                )
            )
            rgba_digest = _pixel_digest(rgba)
            image = Image.fromarray(rgba)
            try:
                image.save(stage / "transparent_RGBA8_VIEW.png", icc_profile=srgb_profile())
            finally:
                # RGBA images map the NumPy buffer; the context manager does not close it.
                image.close()
                del rgba
            _verify_framed_png(
                stage / "transparent_RGBA8_VIEW.png", "RGBA", (width, height), rgba_digest
            )
        notes = (
            "\nThis is a resized presentation using existing photographed detail. "
            "The saved backdrop recipe is regenerated at final output dimensions, including beneath partial-alpha edges. "
            "Enlargement adds no captured detail; reduction can hide fine features. "
            "RGB16 TIFF retains processed precision; PNGs are reduced-precision views. "
            "The native editable project remains authoritative and unchanged; retain it for editing. "
            "Series framing confers no photographic acceptance.\n"
            if sampling is not None
            else "\nThe native image is copied without resampling at the manifest's source rectangle. "
            "Margins extend saved backdrop edge pixels (black for legacy projects); visible bands "
            "are possible. RGB16 TIFF retains processed sRGB precision. PNGs are reduced-precision "
            "views; optional RGBA is straight and has zero RGBA margins. Framing does not alter "
            "native editing coordinates or confer photographic acceptance. Editable source layers "
            "remain in the local project at the manifest's relative native asset paths.\n"
        )
        if companion_binding is not None:
            notes += f"\nKeep and copy BOTH this presentation folder and its native editable sibling {companion_binding['directory_name']}. The sibling contains unfaded editable layers and complete spatial operands; no original project is needed for layer/render reconstruction.\n"
        (stage / "README.txt").write_text(str(record["label"]) + notes)
        record["files"] = {
            name: {
                "sha256": _file_digest(stage / name),
                **(
                    {
                        "dimensions_wh": [width, height],
                        "precision_bits": 16 if name.endswith(".tif") else 8,
                    }
                    if name in variants
                    else {}
                ),
            }
            for name in sorted(names - {"manifest.json"})
        }
        (stage / "manifest.json").write_bytes(_json_bytes(record))
        _check_flat_delivery(stage, names)
        if any(_asset(project, name).read_bytes() != value for name, value in captured.items()):
            raise ProjectError("Stale framed export state or saved inputs")
        final_state = read_project(project)
        final_manifest = read_revision(project, revision, state["master_id"])
        if (
            final_state != state
            or final_manifest != manifest
            or any(_asset(project, name).read_bytes() != value for name, value in captured.items())
        ):
            raise ProjectError("Stale framed export state or saved inputs")
        if destination.exists() or destination.is_symlink():
            _check_flat_delivery(destination, names)
            if any(
                (destination / name).stat().st_size != (stage / name).stat().st_size
                for name in names
            ):
                raise ProjectError("Output collision: differing existing file sizes preserved")
        try:
            publish_artifacts(stage, destination)
            if reused:
                # A prior exclusive rename may have succeeded before its parent sync
                # failed. Identical retry also confirms that directory publication.
                _sync_directory(destination.parent)
        except OSError as error:
            if not stage.exists() or reused:
                raise ProjectError(
                    f"Framed delivery is visible at {destination}, but publication durability "
                    f"is unconfirmed; preserve it and retry identical export: {error}"
                ) from error
            raise
        if reused:
            # Only this verified duplicate is disposable, after publication is durable.
            try:
                shutil.rmtree(stage)
            except OSError as error:
                raise ProjectError(
                    f"Framed delivery is durably published at {destination}, but duplicate stage "
                    f"cleanup failed at {stage}; inspect remaining stage files: {error}"
                ) from error
        response = {
            "revision": revision,
            "draft": draft,
            "directory": str(destination),
            "manifest_file": str(destination / "manifest.json"),
            "framing": settings_record,
            "output_dimensions_wh": [width, height],
            "source_rect_xyxy": list(source_rect),
        }
        if sampling is not None:
            response.pop("framing")
            response.pop("source_rect_xyxy")
            response.update({"settings": settings_record, "layout": sampling.layout.to_dict()})
        if companion is not None:
            _check_flat_delivery(destination, names)
            if (destination / "manifest.json").read_bytes() != _json_bytes(record) or any(
                _file_digest(destination / name) != value["sha256"]
                for name, value in record["files"].items()
            ):
                raise ProjectError(f"Presentation changed after publication at {destination}")
            verified = _editable_companion_binding(
                Path(companion["directory"]), manifest, digest(captured[manifest_name]), draft
            )
            if verified != companion_binding:
                raise ProjectError(
                    f"Native editable companion changed after presentation publication at {companion['directory']}"
                )
            response["editable_companion"] = {
                "directory": companion["directory"],
                "manifest_file": companion["manifest_file"],
                "manifest_sha256": verified["manifest_sha256"],
            }
        return response
    except (OSError, ValueError, MemoryError) as error:
        if companion is not None:
            presentation = (
                f" Presentation path: {destination}." if "destination" in locals() else ""
            )
            raise ProjectError(
                f"Incomplete framed delivery pair. Native editable folder {companion['directory']} is retained.{presentation} Inspect and retry identical export; {error}"
            ) from error
        raise
