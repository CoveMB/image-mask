"""Single encoded-sRGB base renderer and honest lower-precision views."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import tifffile
from PIL import Image

from .assets import revision_hashes, saved_asset
from .ingest import srgb_profile, write_developed
from .project import (
    ProjectError,
    _json_bytes,
    _publish_new_directory,
    _root,
    _sync_directory,
    check_space,
    digest,
    load_developed,
    project_lock,
    read_project,
    read_revision,
)
from .shadow_fade import shadow_fade_files
from .spatial_fade import (
    SpatialFadeOperands,
    blend_background_float,
    spatial_fade_amount,
    spatial_fade_files,
)

if TYPE_CHECKING:
    from .framing import Margins
    from .series_framing import SeriesSamplingPlan


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
            spatial_fade.weight16[rows],
            spatial_fade.protection[rows],
            spatial_fade.record,
            None if spatial_fade.reduction16 is None else spatial_fade.reduction16[rows],
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


def validated_layer_inputs(
    project: Path, revision: str, developed_id: str
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Validate permanent native operands without applying or composing appearance."""
    manifest = read_revision(project, revision, developed_id)
    if (
        manifest.get("kind") not in {"matte", "repair", "effects"}
        or manifest.get("final_acceptable") is not True
    ):
        raise ProjectError("Export/review requires a complete matte, not prepared-only state")
    foreground = read_rgb16(saved_asset(project, f"revisions/{revision}/foreground_rgb16.tif"))
    with Image.open(saved_asset(project, f"revisions/{revision}/base_alpha16.png")) as image:
        if image.format != "PNG" or image.mode not in {"I;16", "I;16B", "I;16L"}:
            raise ProjectError("Invalid saved scalar alpha16")
        alpha = np.array(image)
    master, _ = load_developed(project, developed_id)
    if foreground.shape != master.shape:
        raise ProjectError("Saved foreground dimensions differ from master")
    _validate_render_inputs(foreground, alpha)
    with Image.open(saved_asset(project, f"revisions/{revision}/trimap.png")) as image:
        trimap = np.array(image)
    with Image.open(saved_asset(project, f"revisions/{revision}/supports/protection.png")) as image:
        protection = np.array(image)
    with Image.open(
        saved_asset(project, f"revisions/{revision}/supports/lock_values16.png")
    ) as image:
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
    from .background import read_background
    from .background_light import read_background_light
    from .effects import read_cleanup, saved_shading, saved_spatial_fade
    from .exposure import read_exposure
    from .shadow_fade import read_shadow_fade
    from .sharpening import read_local_sharpening

    read_cleanup(project, revision, foreground, alpha, manifest)
    saved_shading(project, revision, alpha, manifest)
    directory = saved_asset(project, f"revisions/{revision}")
    read_exposure(project, directory, manifest, alpha)
    read_shadow_fade(project, directory, manifest, alpha)
    read_local_sharpening(project, directory, manifest, alpha)
    read_background(project, directory, manifest)
    read_background_light(project, directory, manifest)
    saved_spatial_fade(project, revision, alpha, manifest)
    return foreground, alpha, manifest


def saved_layers(
    project: Path,
    revision: str,
    developed_id: str,
    *,
    effects_off: bool = False,
    sharpening_off: bool = False,
    exposure_off: bool = False,
    shadow_fade_off: bool = False,
    shadow_reduction_off: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    foreground, alpha, manifest = validated_layer_inputs(project, revision, developed_id)
    from .effects import effects_stale, selected_foreground

    foreground = selected_foreground(
        project,
        revision,
        foreground,
        alpha,
        manifest,
        effects_off=effects_off or effects_stale(manifest),
        sharpening_off=sharpening_off,
        exposure_off=exposure_off,
        shadow_fade_off=shadow_fade_off,
        shadow_reduction_off=shadow_reduction_off,
    )
    return foreground, alpha, manifest


def render_saved_result(project: Path, revision: str, developed_id: str) -> np.ndarray:
    """Compose one explicitly selected saved Result without publishing a preview."""
    from .background_light import saved_backgrounds
    from .effects import saved_shading, saved_spatial_fade

    foreground, alpha, manifest = saved_layers(project, revision, developed_id)
    weight, opacity = saved_shading(project, revision, alpha, manifest)
    spatial = saved_spatial_fade(project, revision, alpha, manifest)
    base, background = saved_backgrounds(
        project, saved_asset(project, f"revisions/{revision}"), manifest
    )
    check_space(project, foreground.nbytes * 8 + 16 * 1024**2)
    target = (
        base if base is not None else np.zeros_like(foreground) if spatial is not None else None
    )
    return (
        render_black(
            foreground, alpha, weight, opacity, spatial_fade=spatial, fade_background16=target
        )
        if background is None
        else render_background(
            foreground,
            alpha,
            background,
            weight,
            opacity,
            spatial_fade=spatial,
            fade_background16=target,
        )
    )


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
        not stat.S_ISREG(path.lstat().st_mode) for path in members
    ):
        raise ProjectError("Output collision: unexpected delivery members preserved")


EXPORT_VERSION = "requested-result-v5"


def _delivery_effect_record(record: dict[str, Any]) -> dict[str, Any]:
    """Export finite recovery settings, rather than arbitrary private revision annotations."""
    keys = {
        "schema_version",
        "enabled",
        "stale",
        "settings",
        "opacity",
        "algorithm",
        "developed_id",
        "alpha_sha256",
        "support_sha256",
        "protection_sha256",
        "area_sha256",
        "candidate_comparison",
        "scope_xyxy",
        "weight_sha256",
        "corrected_sha256",
        "reduction_sha256",
        "reduction_area_sha256",
        "reduction_algorithm",
    }
    return {key: value for key, value in record.items() if key in keys}


def _export_execution_identity() -> dict[str, Any]:
    try:
        packages = {
            name: importlib.metadata.version(name) for name in ("numpy", "Pillow", "tifffile")
        }
    except importlib.metadata.PackageNotFoundError as error:
        raise ProjectError(
            "Cannot identify export encoding runtime; delivery not generated"
        ) from error
    return {
        "version": EXPORT_VERSION,
        "python": {"implementation": platform.python_implementation(), "version": sys.version},
        "packages": packages,
        "tiff": "uncompressed-rgb16-srgb-v1",
        "png": "uint8-straight-srgb-zlib6-v1",
        "rounding": "NumPy float64 ties-to-even",
        "icc_profile_sha256": digest(srgb_profile()),
    }


def _delivery_notes(record: dict[str, Any]) -> bytes:
    mode = record["mode"]
    text = record["label"] + "\nProcessed sRGB RGB16 TIFF; PNGs are reduced-precision views. "
    text += "Selected foreground already includes Local sharpening, local exposure and Shadow fade; apply none again. "
    text += "Result/black use encoded-sRGB alpha and shading once. The optional straight RGBA8 view contains baked shading at effective opacity (saved opacity only when enabled); use opacity 0 when shading is disabled or absent. Its RGB is not alpha-multiplied.\n"
    if "background_light" in record:
        text += "Background light is separate from the unlit base B0. Native editable deliveries retain background_rgb16.tif as B0 (missing means zero), background_light_rgb16.tif as L16, and background_light_settings.json, including OFF. When enabled, B1=encode_srgb(clamp(decode_srgb(B0)+decode_srgb(L16),0,1)); encode to RGB16 with float64 ties-to-even and copy zero-light pixels exactly. OFF uses B1=B0. Native replay reads saved L16 without generating it. Light never changes the foreground contribution or alpha; it can clip a bright backdrop, so lower brightness to retain variation. Black/transparent diagnostics never display light.\n"
    if mode == "add-margins":
        text += "The native image is copied without resampling; margins extend saved backdrop edge pixels. Optional straight RGBA has zero RGBA margins.\n"
    elif mode == "match-series":
        if "background_light" in record:
            text += "This is a resized presentation using existing photographed detail. Regenerate B0 at full output dimensions; evaluate the delivered light settings at native coordinates (X+0.5-tx)/scale-0.5 and (Y+0.5-ty)/scale-0.5, including outside the transformed native rectangle. Combine once into B1; spatial fade still targets B0. The manifest freezes scale/translation and native companion identity. Enlargement adds no captured detail; reduction can hide fine features.\n"
        else:
            text += "This is a resized presentation using existing photographed detail. The saved backdrop recipe is regenerated at final output dimensions. Enlargement adds no captured detail; reduction can hide fine features.\n"
    if mode != "native":
        text += "No composition acceptance is recorded.\n"
        companion = record.get("editable_companion_request")
        if companion is not None:
            text += f"Keep this presentation and native editable folder {companion['directory_name']} together for portable editing. The manifest freezes presentation settings and exact companion hashes.\n"
        else:
            text += "Editable layers were not requested.\n"
    if "editable" in record["requested_variants"] and mode == "native":
        if "background_light" in record:
            text += "Native editable F/A/W/opacity/B0/L16 reconstruct Result: round(F*A*(1-opacity*W)+B1*(1-A)), float64 ties-to-even after the separate B0/L16 combination above. A and W divide scalar16 by 65535; use opacity 0 when shading is disabled or absent, otherwise saved shading.opacity. Missing W or B0 means zero. Foreground is pre-shading, already sharpened/exposed/faded; unexposed/unfaded/source and independent settings retain recovery. Scalar16 masks have no ICC/gamma.\n"
        else:
            text += "Native editable F/A/W/opacity/B reconstruct Result: round(F*A*(1-opacity*W)+B*(1-A)), float64 ties-to-even; A and W divide scalar16 by 65535; use opacity 0 when shading is disabled or absent, otherwise use saved shading.opacity. Missing W or B means zero. Foreground is pre-shading, already sharpened/exposed/faded; unexposed/unfaded/source and independent settings retain recovery. Scalar16 masks have no ICC/gamma.\n"
        if record.get("shadow_fade", {}).get("schema_version") == 3:
            text += "Retain shadow_fade_reduction16.png and shadow_fade_reduction.json, including when Shadow fade is OFF. To edit/replay Shadow fade, start from unfaded_foreground_rgb16.tif: multiply its support/highlight exponent weight by (1-reduction16/65535) exactly once before gain=2**(-6*amount*weight). Alpha gates eligibility; explicit protection copies unfaded RGB exactly. Disabled Shadow fade copies unfaded RGB. Selected foreground_rgb16.tif already includes this result: never fade it again. Then recompute downstream spatial highlights from that selected RGB, retaining spatial reduction independently.\n"
        if "spatial_fade" in record:
            if "background_light" in record:
                text += "With enabled spatial Fade into background, F is pre-spatial: derive q from saved weight/protection/highlight settings, blend decode_srgb(F) toward decode_srgb(B0) in linear light, encode without intermediate rounding, then composite once against B1 with unchanged A. Disabled spatial settings mean q=0; retain all operands. Black/transparent diagnostics keep B0 as Fade target. For series, sample P=R(A*F), a=R(A), Q=R(A*q), clamp Q to [0,a], blend P/a toward final-coordinate B0 using Q/a, then composite once against B1; zero transparent RGB where output alpha8 rounds to zero. Opaque pixels and protected underlying RGB remain unchanged by light; partial-alpha flattened colour changes naturally.\n"
            else:
                text += "With enabled spatial Fade into background, F is pre-spatial: derive combined q from saved weight/protection/highlight settings, blend decode_srgb(F) toward decode_srgb(B) in linear light, encode once, then composite once with unchanged A. Disabled spatial settings mean q=0; retain all four operands for editing. Black/transparent diagnostics keep selected B as Fade target. For series, sample P=R(A*F), a=R(A), Q=R(A*q), clamp Q to [0,a], blend P/a toward final-coordinate B using Q/a, then composite once; zero transparent RGB where output alpha8 rounds to zero.\n"
            if record["spatial_fade"]["schema_version"] == 2:
                text += "Also retain spatial_fade_reduction16.png and spatial_fade_reduction.json. Multiply q by (1-reduction16/65535) exactly once after protection/highlights and before blending or series sampling of A*q. Alpha is eligibility only; zero reduction preserves the original fade, full reduction removes only this effect. The raster is the rounded maximum of amount times each authored support16 field; overlaps never accumulate.\n"
    if "local_sharpening" in record and "editable" in record["requested_variants"]:
        text += (
            "Replay Local sharpening from unsharpened_foreground_rgb16.tif (cleanup-selected RGB), "
            "sharpening_support16.png/protection16.png/alpha16.png and sharpening_settings.json. "
            "Apply linear-srgb-local-sharpening-v1 once, then exposure, Shadow fade, shading or "
            "spatial fade, then alpha/background composition. Unexposed RGB already includes "
            "sharpening; unfaded RGB includes sharpening and exposure; foreground includes all "
            "three. These are alternative starting points: never sharpen them twice. "
            "Optional sharpening_area.json retains authored geometry. Older applications cannot "
            "reliably read new sharpening records; keep pre-feature projects/exports for them.\n"
        )
    if "result_compositing" in record:
        text += "Saved compositing: " + record["result_compositing"] + "\n"
    return text.encode()


def _delivery_members(
    request_record: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    variants = request_record["requested_variants"]
    width, height = request_record["output_dimensions_wh"]
    rgb = {
        "dimensions_wh": [width, height],
        "precision_bits": 16,
        "mode": "RGB",
        "icc_profile_sha256": digest(srgb_profile()),
    }
    view = {**rgb, "precision_bits": 8}
    members = {
        "result_rgb16.tif": dict(rgb),
        "result_RGB8_VIEW.png": dict(view),
        "recipe.toml": {},
        "README.txt": {},
    }
    if "black" in variants:
        members.update({"black_rgb16.tif": dict(rgb), "black_RGB8_VIEW.png": dict(view)})
    if "transparent" in variants:
        members["transparent_RGBA8_VIEW.png"] = {**view, "mode": "RGBA"}
    if "editable" in variants and request_record["mode"] == "native":
        names = {"foreground_rgb16.tif", "alpha16.png", "source_rgb16.tif"}
        saved = revision_hashes(manifest)
        names.update(
            name for name in ("shadow_weight16.png", "corrected_rgb16.tif") if name in saved
        )
        for effect in ("color_cleanup", "shading"):
            if effect in manifest:
                names.add(effect + "_settings.json")
        if "background" in manifest:
            names.update({"background_rgb16.tif", "background_settings.json"})
        if "background_light" in manifest:
            names.update({"background_light_rgb16.tif", "background_light_settings.json"})
        for section, directory, prefix in (
            ("local_sharpening", "sharpening", "sharpening"),
            ("local_exposure", "exposure", "exposure"),
            ("shadow_fade", "shadow-fade", "shadow_fade"),
        ):
            if section not in manifest:
                continue
            names.update({"unexposed_foreground_rgb16.tif", "base_foreground_rgb16.tif"})
            if section == "local_sharpening":
                names.add("unsharpened_foreground_rgb16.tif")
            if section == "shadow_fade":
                names.add("unfaded_foreground_rgb16.tif")
            files = (
                shadow_fade_files(manifest[section])
                if section == "shadow_fade"
                else (
                    "support16.png",
                    "protection16.png",
                    "alpha16.png",
                    "settings.json",
                    "area.json",
                )
            )
            for name in files:
                if f"effects/{directory}/{name}" in saved:
                    names.add(prefix + "_" + name)
        if "spatial_fade" in manifest:
            names.update(
                "spatial_fade_" + name for name in spatial_fade_files(manifest["spatial_fade"])
            )
        for name in names:
            members[name] = (
                dict(rgb)
                if name.endswith(".tif")
                else (
                    {
                        "dimensions_wh": [width, height],
                        "precision_bits": 16,
                        "mode": "I;16",
                        "icc_profile_sha256": None,
                    }
                    if name.endswith(".png")
                    else {}
                )
            )
    return members


def _member_signature(path: Path) -> tuple[int, ...]:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode):
        raise ProjectError("Output collision: nonregular delivery member preserved")
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _validate_delivery(
    directory: Path,
    request_record: dict[str, Any],
    members: dict[str, dict[str, Any]],
    *,
    companion_binding: dict[str, Any] | None = None,
) -> None:
    _check_flat_delivery(directory, {*members, "manifest.json"})
    signatures = {name: _member_signature(directory / name) for name in (*members, "manifest.json")}
    # Bound the compact file table before reading; no raster is decoded for reuse.
    if signatures["manifest.json"][2] > len(_json_bytes(request_record)) + len(
        members
    ) * 1024 + 1024 + (
        len(_json_bytes(companion_binding)) + 1024 if companion_binding is not None else 0
    ):
        raise ProjectError("Output collision: oversized delivery manifest preserved")
    try:
        raw = (directory / "manifest.json").read_bytes()
        record = json.loads(raw)
        if not isinstance(record, dict) or _json_bytes(record) != raw:
            raise ValueError("Noncanonical manifest")
        if "editable_companion_request" in request_record:
            expected = request_record["editable_companion_request"]
            if (
                companion_binding is None
                or set(companion_binding) != {"directory_name", "manifest_sha256", "files_sha256"}
                or companion_binding["directory_name"] != expected["directory_name"]
                or record.pop("editable_companion", None) != companion_binding
            ):
                raise ValueError("Editable companion binding mismatch")
        elif "editable_companion" in record or companion_binding is not None:
            raise ValueError("Unexpected editable companion binding")
        files = record.pop("files")
        if (
            _json_bytes(record) != _json_bytes(request_record)
            or not isinstance(files, dict)
            or set(files) != set(members)
        ):
            raise ValueError("Delivery request/member mismatch")
        for name, expected in members.items():
            path = directory / name
            metadata = files[name]
            if (
                not isinstance(metadata, dict)
                or set(metadata) != {"sha256", "bytes", *expected}
                or any(metadata[key] != value for key, value in expected.items())
            ):
                raise ValueError("Invalid delivery member metadata")
            if (
                type(metadata["bytes"]) is not int
                or metadata["bytes"] != signatures[name][2]
                or metadata["sha256"] != _file_digest(path)
            ):
                raise ValueError("Differing existing files")
            if name == "recipe.toml" and metadata["sha256"] != request_record["recipe_sha256"]:
                raise ValueError("Recipe binding mismatch")
            if name == "README.txt" and path.read_bytes() != _delivery_notes(request_record):
                raise ValueError("Notes binding mismatch")
            if name.endswith(".tif"):
                with tifffile.TiffFile(path) as image:
                    page = image.pages[0]
                    if (
                        not isinstance(page, tifffile.TiffPage)
                        or len(image.pages) != 1
                        or page.dtype != np.dtype("uint16")
                        or int(page.compression) != 1
                        or page.photometric != 2
                        or page.planarconfig != 1
                        or page.samplesperpixel != 3
                        or page.extrasamples
                        or page.shape
                        != (expected["dimensions_wh"][1], expected["dimensions_wh"][0], 3)
                        or page.tags.get(34675) is None
                        or page.tags[34675].value != srgb_profile()
                    ):
                        raise ValueError("Invalid delivery TIFF header/profile")
            elif name.endswith(".png"):
                with path.open("rb") as stream:
                    header = stream.read(26)
                # Pillow exposes multichannel PNG16 as RGB/RGBA too; inspect IHDR precision.
                if (
                    len(header) != 26
                    or header[:8] != b"\x89PNG\r\n\x1a\n"
                    or header[12:16] != b"IHDR"
                    or header[24] != expected["precision_bits"]
                    or header[25] != {"RGB": 2, "RGBA": 6, "I;16": 0}[expected["mode"]]
                ):
                    raise ValueError("Invalid delivery PNG file precision/channel header")
                with Image.open(path, formats=["PNG"]) as image:
                    if list(image.size) != expected["dimensions_wh"] or (
                        image.mode != expected["mode"]
                        if expected["mode"] != "I;16"
                        else image.mode not in {"I;16", "I;16L", "I;16B"}
                    ):
                        raise ValueError("Invalid delivery PNG precision/dimensions")
                    if expected["icc_profile_sha256"] is None:
                        if "icc_profile" in image.info or "gamma" in image.info:
                            raise ValueError("Scalar PNG must not carry ICC/gamma")
                    elif image.info.get("icc_profile") != srgb_profile():
                        raise ValueError("Invalid delivery PNG profile")
        if any(
            _member_signature(directory / name) != signature
            for name, signature in signatures.items()
        ):
            raise ValueError("Delivery changed during validation")
        _check_flat_delivery(directory, {*members, "manifest.json"})
    except (OSError, ValueError, TypeError, KeyError, tifffile.TiffFileError) as error:
        raise ProjectError(
            f"Output collision: differing existing files or invalid delivery preserved: {error}"
        ) from error


def _recheck_export_inputs(
    project: Path,
    captured: dict[str, bytes],
    state: dict[str, Any],
    revision: str,
    manifest: dict[str, Any],
) -> None:
    if any(saved_asset(project, name).read_bytes() != value for name, value in captured.items()):
        raise ProjectError("Stale export state or saved inputs")
    final_state = read_project(project)
    _, _, final_manifest = validated_layer_inputs(project, revision, state["developed_id"])
    if (
        final_state != state
        or final_manifest != manifest
        or any(saved_asset(project, name).read_bytes() != value for name, value in captured.items())
    ):
        raise ProjectError("Stale export state or saved inputs")


def _write_rgb_pair(stage: Path, stem: str, pixels: np.ndarray) -> tuple[str, str]:
    checksum = _pixel_digest(pixels)
    write_developed(stage / (stem + "_rgb16.tif"), pixels)
    view = _write_framed_rgb8(stage / (stem + "_RGB8_VIEW.png"), pixels)
    return checksum, view


def _verify_rgb_pair(
    stage: Path, stem: str, size: tuple[int, int], checksums: tuple[str, str]
) -> None:
    restored = read_rgb16(stage / (stem + "_rgb16.tif"))
    if restored.shape != (size[1], size[0], 3) or _pixel_digest(restored) != checksums[0]:
        raise ProjectError("RGB16 export round trip failed")
    del restored
    _verify_framed_png(stage / (stem + "_RGB8_VIEW.png"), "RGB", size, checksums[1])


def export_project(
    project: Path,
    *,
    revision: str | None = None,
    draft: bool = False,
    framing: dict[str, int] | None = None,
    framed_transparent: bool = False,
    series: dict[str, object] | None = None,
    expected_developed_id: str | None = None,
    expected_revision_manifest_sha256: str | None = None,
    variants: tuple[str, ...] = (),
) -> dict[str, Any]:
    if type(draft) is not bool or type(framed_transparent) is not bool:
        raise ValueError("Export draft and transparent flags must be booleans")
    if (
        not isinstance(variants, (tuple, list))
        or any(
            type(value) is not str or value not in {"black", "transparent", "editable"}
            for value in variants
        )
        or len(set(variants)) != len(variants)
    ):
        raise ValueError("Export variants must be distinct black, transparent or editable tokens")
    if framing is not None and series is not None:
        raise ValueError("Series settings and pixel margins are mutually exclusive")
    if framed_transparent and framing is None and series is None:
        raise ValueError("Transparent framing requires explicit margins or series settings")
    if (expected_developed_id is None) != (expected_revision_manifest_sha256 is None):
        raise ValueError("Export requires paired expected source and revision identities")
    for value in (expected_developed_id, expected_revision_manifest_sha256):
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("Expected export identities must be SHA-256 hex strings")
    selected = set(variants) | ({"transparent"} if framed_transparent else set())
    normalized = tuple(name for name in ("black", "transparent", "editable") if name in selected)
    project = _root(project)
    with project_lock(project):
        return _export_delivery(
            project,
            revision,
            draft,
            framing,
            series,
            normalized,
            expected_developed_id,
            expected_revision_manifest_sha256,
        )


def _delivery_request_record(
    state: dict[str, Any],
    source: dict[str, Any],
    manifest: dict[str, Any],
    captured: dict[str, bytes],
    recipe: bytes,
    *,
    draft: bool,
    variants: tuple[str, ...],
    native_dimensions_wh: tuple[int, int],
    sampling: SeriesSamplingPlan | None = None,
    margins_settings: Margins | None = None,
    settings: dict[str, Any] | None = None,
    companion_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build lookup identity entirely from validated request facts, never delivery bytes."""
    from .framing import framed_geometry

    revision = manifest["revision"]
    manifest_name = f"revisions/{revision}/manifest.json"
    size = native_dimensions_wh
    width, height = size
    rectangle = (0, 0, *size)
    mode = "native"
    settings = {} if settings is None else settings
    if sampling is not None:
        mode = "match-series"
        width, height = sampling.layout.output_dimensions_wh
    elif margins_settings is not None:
        mode = "add-margins"
        width, height, rectangle = framed_geometry(size, margins_settings)
        settings = margins_settings.to_dict()
    record: dict[str, Any] = {
        "schema_version": 2,
        "kind": {
            "native": "native-result",
            "add-margins": "framed-presentation",
            "match-series": "series-framed-presentation",
        }[mode],
        "mode": mode,
        "export_version": EXPORT_VERSION,
        "revision": revision,
        "developed_id": state["developed_id"],
        "revision_manifest_sha256": digest(captured[manifest_name]),
        "source_record_sha256": digest(captured["source.json"]),
        "recipe_sha256": digest(recipe),
        "draft": draft,
        "requested_variants": list(variants),
        "label": (
            "DRAFT - explicit resized series presentation"
            if draft
            else "Resized series presentation of accepted revision; composition has not been separately accepted"
        )
        if sampling is not None
        else (
            (
                "DRAFT - explicit framed presentation"
                if draft
                else "Framed presentation of accepted revision; framing has not been separately accepted"
            )
            if margins_settings is not None
            else (
                "DRAFT - unaccepted explicit export" if draft else "Human-accepted saved revision"
            )
        ),
        "source_dimensions_wh": list(size),
        "output_dimensions_wh": [width, height],
        "algorithm": "series-lanczos-premultiplied-v1"
        if sampling is not None
        else (
            "saved-backdrop-edge-padding-v1"
            if margins_settings is not None
            else "saved-native-result-v1"
        ),
        "encoding": _export_execution_identity(),
        "compositing": manifest["compositing"],
        "native_assets": {
            f"assets/developed/{state['developed_id']}.tif": source["developed_file_sha256"],
            **{reference["path"]: reference["sha256"] for reference in manifest["assets"].values()},
        },
        "effects": {
            name: {
                "enabled": manifest.get(name, {}).get("enabled", False),
                "record_sha256": digest(_json_bytes(manifest[name])) if name in manifest else None,
            }
            for name in (
                "color_cleanup",
                "shading",
                "local_sharpening",
                "local_exposure",
                "shadow_fade",
                "spatial_fade",
            )
        },
        "views": "RGB8/RGBA8 reduced color/alpha precision; straight RGB is not alpha-multiplied; selected saved foreground already includes Local sharpening, local exposure and Shadow fade; apply none again; baked shading at effective p (saved p when enabled, 0 when disabled or absent); editable W16 plus p retained separately only when requested",
        **{
            name: (
                _delivery_effect_record(manifest[name]) if name != "background" else manifest[name]
            )
            for name in (
                "color_cleanup",
                "shading",
                "local_sharpening",
                "local_exposure",
                "shadow_fade",
                "background",
            )
            if name in manifest
        },
    }
    if "spatial_fade" in manifest:
        record["spatial_fade"] = manifest["spatial_fade"]
    if "background_light" in manifest:
        record["background_light"] = manifest["background_light"]
        if sampling is not None:
            record["background_light_transform"] = {
                "scale": sampling.layout.scale,
                "translation_xy": list(sampling.layout.translation_xy),
                "native_dimensions_wh": list(native_dimensions_wh),
                "output_dimensions_wh": list(sampling.layout.output_dimensions_wh),
                "sample_coordinates": "native=(output_integer+0.5-translation)/scale-0.5",
            }
    if sampling is not None:
        record.update(
            {
                "settings": settings,
                "layout": sampling.layout.to_dict(),
                "sampling": sampling.to_dict(),
                "backend": {
                    "name": "Pillow",
                    "version": record["encoding"]["packages"]["Pillow"],
                    "mode": "F",
                    "filter": "Lanczos",
                    "source_box": "float32",
                    "reducing_gap": None,
                    "quantization": "NumPy ties-to-even",
                },
            }
        )
    else:
        record["source_rect_xyxy"] = list(rectangle)
        if margins_settings is not None:
            record["margins"] = settings
    if mode != "native":
        for name in (
            "color_cleanup",
            "shading",
            "local_sharpening",
            "local_exposure",
            "shadow_fade",
            "spatial_fade",
        ):
            record.pop(name, None)
        if "background" in manifest:
            record["background"] = {
                "record_sha256": digest(_json_bytes(manifest["background"])),
                "background_sha256": manifest["background"]["background_sha256"],
                **(
                    {
                        "algorithm": manifest["background"]["algorithm"],
                        "settings": manifest["background"]["settings"],
                        "placement": "recipe-regenerated-at-final-output-size",
                    }
                    if sampling is not None
                    else {}
                ),
            }
    if mode == "native":
        record["result_compositing"] = (
            "round(blend_linear_srgb(F,B,q)*A+B*(1-A)); q from delivered combined W16, explicit protection and independent highlight preservation; exact q=0/q=1 endpoints"
            if manifest.get("spatial_fade", {}).get("enabled")
            else "encoded-sRGB float64 round ties-to-even(F*A*H+B*(1-A)); H=1-p*W16/65535, A=alpha16/65535; p is saved opacity only when shading is enabled, otherwise zero; B is saved background RGB16 or zero"
        ) + "; F already includes Local sharpening, local exposure and Shadow fade"
        if "background_light" in manifest:
            record["result_compositing"] = (
                (
                    "round(blend_linear_srgb(F,B0,q)*A+B1*(1-A)); spatial q retains all saved protection/highlight/reduction operands"
                    if manifest.get("spatial_fade", {}).get("enabled")
                    else "encoded-sRGB float64 round ties-to-even(F*A*H+B1*(1-A)); H=1-p*W16/65535; p is saved opacity only when shading is enabled, otherwise zero"
                )
                + "; B0 is saved unlit background or zero; enabled B1=RGB16(encode_srgb(clamp(decode_srgb(B0)+decode_srgb(L16),0,1))), OFF B1=B0; A=alpha16/65535; F already includes Local sharpening, local exposure and Shadow fade"
            )
        if manifest.get("spatial_fade", {}).get("schema_version") == 2:
            record["result_compositing"] += (
                "; when spatial fade is enabled, multiply q once by (1-reduction16/65535) after protection/highlights"
            )
    if companion_request is not None:
        record["editable_companion_request"] = companion_request
    record["identity_sha256"] = digest(_json_bytes(record))
    return record


def _delivery_destination(project: Path, record: dict[str, Any]) -> Path:
    label = record["revision"] + ("-DRAFT" if record["draft"] else "")
    suffix = {"native": "native", "add-margins": "framed", "match-series": "series-framed"}[
        record["mode"]
    ]
    return saved_asset(project, f"exports/{label}-{suffix}-{record['identity_sha256']}")


def _export_delivery(
    project: Path,
    revision: str | None,
    draft: bool,
    framing: dict[str, int] | None,
    series: dict[str, object] | None,
    variants: tuple[str, ...],
    expected_developed_id: str | None,
    expected_revision_manifest_sha256: str | None,
) -> dict[str, Any]:
    from .effects import effects_stale, selected_foreground
    from .framing import framed_geometry, validate_margins

    captured = {
        name: saved_asset(project, name).read_bytes() for name in ("state.json", "source.json")
    }
    state = read_project(project)
    if _json_bytes(json.loads(captured["state.json"])) != _json_bytes(state):
        raise ProjectError("Stale export state")
    if expected_developed_id is not None and state["developed_id"] != expected_developed_id:
        raise ProjectError("Stale export source identity; reload the selected photo")
    if revision is None:
        if draft:
            raise ProjectError("Draft export requires explicit revision")
        revision = state["accepted_revision"]
    if revision is None:
        raise ProjectError("No accepted result to export")
    if revision != state["accepted_revision"] and not draft:
        raise ProjectError("Unaccepted revision requires explicit --draft")
    manifest_name = f"revisions/{revision}/manifest.json"
    captured[manifest_name] = saved_asset(project, manifest_name).read_bytes()
    if (
        expected_revision_manifest_sha256 is not None
        and digest(captured[manifest_name]) != expected_revision_manifest_sha256
    ):
        raise ProjectError("Stale export revision manifest; reload the selected result")
    base, alpha, manifest = validated_layer_inputs(project, revision, state["developed_id"])
    if _json_bytes(json.loads(captured[manifest_name])) != _json_bytes(manifest):
        raise ProjectError("Stale export revision manifest")
    if effects_stale(manifest):
        raise ProjectError(
            "Stale enabled cleanup/shading/local exposure/Shadow fade: scoped rebuild or explicit disable required before export"
        )
    source = json.loads(captured["source.json"])
    size = (base.shape[1], base.shape[0])
    sampling = None
    margins_settings = None
    settings: dict[str, Any] = {}
    rectangle = (0, 0, *size)
    mode = "native"
    width, height = size
    if series is not None:
        from .series_framing import (
            compute_series_layout,
            series_sampling_plan,
            validate_series_settings,
        )

        series_settings = validate_series_settings(series)
        sampling = series_sampling_plan(compute_series_layout(alpha, series_settings))
        width, height = sampling.layout.output_dimensions_wh
        settings = series_settings.to_dict()
        mode = "match-series"
    elif framing is not None:
        margins_settings = validate_margins(framing, size)
        width, height, rectangle = framed_geometry(size, margins_settings)
        settings = margins_settings.to_dict()
        mode = "add-margins"
    recipe = saved_asset(project, f"revisions/{revision}/recipe.toml").read_bytes()
    native_record = None
    native_directory = None
    companion_request = None
    if mode != "native" and "editable" in variants:
        native_record = _delivery_request_record(
            state,
            source,
            manifest,
            captured,
            recipe,
            draft=draft,
            variants=("editable",),
            native_dimensions_wh=size,
        )
        native_directory = _delivery_destination(project, native_record)
        companion_request = {
            "identity_sha256": native_record["identity_sha256"],
            "directory_name": native_directory.name,
        }
    record = _delivery_request_record(
        state,
        source,
        manifest,
        captured,
        recipe,
        draft=draft,
        variants=variants,
        native_dimensions_wh=size,
        sampling=sampling,
        margins_settings=margins_settings,
        settings=settings,
        companion_request=companion_request,
    )
    destination = _delivery_destination(project, record)
    members = _delivery_members(record, manifest)
    _recheck_export_inputs(project, captured, state, revision, manifest)
    present = destination.exists() or destination.is_symlink()
    binding = None
    if native_directory is not None and native_record is not None:
        child_present = native_directory.exists() or native_directory.is_symlink()
        if present and not child_present:
            raise ProjectError(
                f"Incomplete delivery pair: native editable companion is missing at {native_directory}; "
                f"existing primary preserved at {destination}. Restore the intact native folder before retrying."
            )
        if child_present:
            binding = _editable_companion_binding(native_directory, native_record, manifest)
    response: dict[str, Any] = {
        "revision": revision,
        "draft": draft,
        "directory": str(destination),
        "manifest_file": str(destination / "manifest.json"),
        "mode": mode,
        "variants": list(variants),
        "output_dimensions_wh": [width, height],
    }
    if sampling is not None:
        response.update({"settings": settings, "layout": sampling.layout.to_dict()})
    elif margins_settings is not None:
        response.update({"framing": settings, "source_rect_xyxy": list(rectangle)})

    def recheck_pair() -> None:
        _recheck_export_inputs(project, captured, state, revision, manifest)
        if native_directory is not None and native_record is not None:
            actual = _editable_companion_binding(native_directory, native_record, manifest)
            if actual != binding:
                raise ProjectError("Output collision: native editable companion binding changed")

    if present:
        _validate_delivery(destination, record, members, companion_binding=binding)
        recheck_pair()
        try:
            if native_directory is not None:
                _sync_directory(native_directory.parent)
            _sync_directory(destination.parent)
        except OSError as error:
            raise ProjectError(
                f"Delivery is visible at {destination}, but publication durability is unconfirmed; preserve it and retry identical export: {error}"
            ) from error
        _validate_delivery(destination, record, members, companion_binding=binding)
        recheck_pair()
        if binding is not None and native_directory is not None:
            response["editable_companion"] = {
                "directory": str(native_directory),
                "manifest_file": str(native_directory / "manifest.json"),
                "manifest_sha256": binding["manifest_sha256"],
            }
        return {**response, "reused": True}
    # Conservative bound covers retained native operands, both pending deliveries and scratch.
    pending = base.nbytes * (22 if "background" in manifest else 18)
    reduction_bytes = alpha.nbytes * sum(
        manifest.get(target, {}).get("schema_version") == version
        for target, version in (("spatial_fade", 2), ("shadow_fade", 3))
    )
    pending += reduction_bytes
    if "background_light" in manifest:
        pending += base.nbytes * 4 + min(64, base.shape[0]) * base.shape[1] * 198
    pending += (16 + (10 if "black" in variants else 0)) * width * height + 2 * 1024**2
    if native_record is not None and binding is None:
        pending += base.nbytes * 22 + 2 * 1024**2
    check_space(project, pending)
    if sampling is not None:
        from .series_framing import estimate_series_resources

        estimate_series_resources(
            sampling,
            retained_native_bytes=base.nbytes + alpha.nbytes + reduction_bytes,
            transparent="transparent" in variants,
            spatial_fade_pixels=alpha.size
            if manifest.get("spatial_fade", {}).get("enabled")
            else 0,
            black_background="black" in variants,
            native_export_peak_bytes=base.nbytes * 22 if native_record is not None else 0,
            background_light=bool(
                manifest.get("background_light", {}).get("settings", {}).get("enabled")
            ),
        )
    foreground = selected_foreground(project, revision, base, alpha, manifest)
    del base
    if native_record is not None and native_directory is not None and binding is None:
        if destination.exists() or destination.is_symlink():
            raise ProjectError(
                f"Incomplete delivery pair: primary appeared at {destination} before native companion "
                f"publication at {native_directory}; existing output preserved"
            )
        _export_native_locked(
            project,
            state=state,
            foreground=foreground,
            alpha=alpha,
            manifest=manifest,
            record=native_record,
            recipe=recipe,
            captured=captured,
            paired_primary=destination,
        )
        binding = _editable_companion_binding(native_directory, native_record, manifest)
    if binding is not None and native_directory is not None:
        response["editable_companion"] = {
            "directory": str(native_directory),
            "manifest_file": str(native_directory / "manifest.json"),
            "manifest_sha256": binding["manifest_sha256"],
        }
    try:
        reused = _write_delivery(
            project,
            state=state,
            foreground=foreground,
            alpha=alpha,
            manifest=manifest,
            record=record,
            recipe=recipe,
            captured=captured,
            sampling=sampling,
            margins_settings=margins_settings,
            companion_binding=binding,
            companion_record=native_record,
        )
    except (OSError, ValueError, MemoryError) as error:
        if binding is not None and native_directory is not None:
            raise ProjectError(
                f"Incomplete delivery pair. Native folder is visible at {native_directory}; inspect or retry identical export. {error}"
            ) from error
        raise
    return {**response, "reused": reused}


def _editable_companion_binding(
    directory: Path, native_request: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    """Verify the exact requested native inventory before binding its observed bytes."""
    if directory.name != _delivery_destination(directory.parent.parent, native_request).name:
        raise ProjectError("Invalid native editable companion directory identity")
    _validate_delivery(directory, native_request, _delivery_members(native_request, manifest))
    raw = (directory / "manifest.json").read_bytes()
    return {
        "directory_name": directory.name,
        "manifest_sha256": digest(raw),
        "files_sha256": {
            name: _file_digest(directory / name)
            for name in (*_delivery_members(native_request, manifest),)
        },
    }


def _export_native_locked(
    project: Path,
    *,
    state: dict[str, Any],
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    record: dict[str, Any],
    recipe: bytes,
    captured: dict[str, bytes],
    paired_primary: Path,
) -> bool:
    """Use the one requested writer with native geometry and caller-owned arrays/lock."""
    return _write_delivery(
        project,
        state=state,
        foreground=foreground,
        alpha=alpha,
        manifest=manifest,
        record=record,
        recipe=recipe,
        captured=captured,
        paired_primary=paired_primary,
    )


def _write_delivery(
    project: Path,
    *,
    state: dict[str, Any],
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    record: dict[str, Any],
    recipe: bytes,
    captured: dict[str, bytes],
    sampling: SeriesSamplingPlan | None = None,
    margins_settings: Margins | None = None,
    companion_binding: dict[str, Any] | None = None,
    companion_record: dict[str, Any] | None = None,
    paired_primary: Path | None = None,
) -> bool:
    from .background_light import saved_backgrounds
    from .effects import saved_shading, saved_spatial_fade
    from .framing import frame_result, frame_transparent

    revision = record["revision"]
    variants = record["requested_variants"]
    width, height = record["output_dimensions_wh"]
    destination = _delivery_destination(project, record)
    members = _delivery_members(record, manifest)

    def recheck() -> None:
        _recheck_export_inputs(project, captured, state, revision, manifest)
        if paired_primary is not None and (paired_primary.exists() or paired_primary.is_symlink()):
            raise ProjectError(
                f"Incomplete delivery pair: primary appeared at {paired_primary} before native companion "
                f"publication at {destination}; existing output preserved"
            )
        if companion_record is not None:
            native = _delivery_destination(project, companion_record)
            if _editable_companion_binding(native, companion_record, manifest) != companion_binding:
                raise ProjectError("Output collision: native editable companion binding changed")

    recheck()
    weight, opacity = saved_shading(project, revision, alpha, manifest)
    spatial = saved_spatial_fade(project, revision, alpha, manifest)
    base, background = (
        (None, None)
        if sampling is not None
        else saved_backgrounds(project, saved_asset(project, f"revisions/{revision}"), manifest)
    )
    target = (
        base
        if base is not None
        else np.zeros_like(foreground)
        if spatial is not None and sampling is None
        else None
    )
    exports = saved_asset(project, "exports")
    exports.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".export-", dir=exports))
    for stem in ("result", *(["black"] if "black" in variants else [])):
        if sampling is not None:
            from .series_framing import render_series

            pixels = render_series(
                foreground,
                alpha,
                sampling,
                weight16=weight,
                opacity=opacity,
                background_settings=manifest.get("background", {}).get("settings"),
                background_light_settings=manifest.get("background_light", {}).get("settings"),
                spatial_fade=spatial,
                black_background=stem == "black",
            )
        else:
            native = (
                render_background(
                    foreground,
                    alpha,
                    background,
                    weight,
                    opacity,
                    spatial_fade=spatial,
                    fade_background16=target,
                )
                if stem == "result" and background is not None
                else render_black(
                    foreground,
                    alpha,
                    weight,
                    opacity,
                    spatial_fade=spatial,
                    fade_background16=target,
                )
            )
            pixels = (
                frame_result(native, background if stem == "result" else None, margins_settings)
                if margins_settings is not None
                else native
            )
            del native
        checksums = _write_rgb_pair(stage, stem, pixels)
        del pixels
        _verify_rgb_pair(stage, stem, (width, height), checksums)
    if "transparent" in variants:
        rgba = (
            render_series(
                foreground,
                alpha,
                sampling,
                weight16=weight,
                opacity=opacity,
                transparent=True,
                spatial_fade=spatial,
                background_settings=manifest.get("background", {}).get("settings"),
                background_light_settings=manifest.get("background_light", {}).get("settings"),
            )
            if sampling is not None
            else (
                frame_transparent(
                    view_rgba(
                        foreground,
                        alpha,
                        weight,
                        opacity,
                        spatial_fade=spatial,
                        fade_background16=target,
                    ),
                    margins_settings,
                )
                if margins_settings is not None
                else view_rgba(
                    foreground,
                    alpha,
                    weight,
                    opacity,
                    spatial_fade=spatial,
                    fade_background16=target,
                )
            )
        )
        checksum = _pixel_digest(rgba)
        image = Image.fromarray(rgba)
        try:
            image.save(stage / "transparent_RGBA8_VIEW.png", icc_profile=srgb_profile())
        finally:
            image.close()
            del rgba
        _verify_framed_png(stage / "transparent_RGBA8_VIEW.png", "RGBA", (width, height), checksum)
    if "editable" in variants and record["mode"] == "native":
        _write_editable(project, stage, revision, state, foreground, alpha, manifest)
    (stage / "recipe.toml").write_bytes(recipe)
    (stage / "README.txt").write_bytes(_delivery_notes(record))
    files = {
        name: {
            **metadata,
            "sha256": _file_digest(stage / name),
            "bytes": (stage / name).stat().st_size,
        }
        for name, metadata in members.items()
    }
    (stage / "manifest.json").write_bytes(
        _json_bytes(
            {
                **record,
                **(
                    {"editable_companion": companion_binding}
                    if companion_binding is not None
                    else {}
                ),
                "files": files,
            }
        )
    )
    _validate_delivery(stage, record, members, companion_binding=companion_binding)
    recheck()
    for path in stage.iterdir():
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
    _sync_directory(stage)
    recheck()
    late_reuse = destination.exists() or destination.is_symlink()
    try:
        if late_reuse:
            _validate_delivery(destination, record, members, companion_binding=companion_binding)
            if any(
                _file_digest(destination / name) != _file_digest(stage / name)
                for name in (*members, "manifest.json")
            ):
                raise ProjectError("Output collision: differing existing files preserved")
            recheck()
        else:
            _publish_new_directory(stage, destination)
        _sync_directory(destination.parent)
    except OSError as error:
        if not stage.exists() or late_reuse:
            raise ProjectError(
                f"Delivery is visible at {destination}, but publication durability is unconfirmed; preserve it and retry identical export: {error}"
            ) from error
        raise
    if late_reuse:
        _validate_delivery(destination, record, members, companion_binding=companion_binding)
        recheck()
        _validate_delivery(stage, record, members, companion_binding=companion_binding)
        try:
            shutil.rmtree(stage)
        except OSError as error:
            raise ProjectError(
                f"Delivery is durably published at {destination}, but duplicate stage cleanup failed at {stage}; inspect remaining stage files: {error}"
            ) from error
    _validate_delivery(destination, record, members, companion_binding=companion_binding)
    recheck()
    return late_reuse


def _write_editable(
    project: Path,
    stage: Path,
    revision: str,
    state: dict[str, Any],
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
) -> None:
    """Native independent layers retain the existing precision and replay contracts."""
    Image.fromarray(alpha).save(stage / "alpha16.png")
    if "background" in manifest:
        for saved, delivered in (
            ("background/background_rgb16.tif", "background_rgb16.tif"),
            ("background/settings.json", "background_settings.json"),
        ):
            (stage / delivered).write_bytes(
                saved_asset(project, f"revisions/{revision}/{saved}").read_bytes()
            )
    if "background_light" in manifest:
        for saved, delivered in (
            ("background_light/light_rgb16.tif", "background_light_rgb16.tif"),
            ("background_light/settings.json", "background_light_settings.json"),
        ):
            (stage / delivered).write_bytes(
                saved_asset(project, f"revisions/{revision}/{saved}").read_bytes()
            )
    write_developed(stage / "foreground_rgb16.tif", foreground)
    if "local_sharpening" in manifest:
        unsharpened, _, _ = saved_layers(
            project,
            revision,
            state["developed_id"],
            sharpening_off=True,
            exposure_off=True,
            shadow_fade_off=True,
        )
        write_developed(stage / "unsharpened_foreground_rgb16.tif", unsharpened)
        unexposed, _, _ = saved_layers(
            project,
            revision,
            state["developed_id"],
            exposure_off=True,
            shadow_fade_off=True,
        )
        write_developed(stage / "unexposed_foreground_rgb16.tif", unexposed)
        (stage / "base_foreground_rgb16.tif").write_bytes(
            saved_asset(project, f"revisions/{revision}/foreground_rgb16.tif").read_bytes()
        )
        for name in (
            "support16.png",
            "protection16.png",
            "alpha16.png",
            "settings.json",
            "area.json",
        ):
            asset = f"effects/sharpening/{name}"
            if asset in revision_hashes(manifest):
                (stage / ("sharpening_" + name)).write_bytes(
                    saved_asset(project, f"revisions/{revision}/{asset}").read_bytes()
                )
    if "local_exposure" in manifest:
        unexposed, _, _ = saved_layers(
            project, revision, state["developed_id"], exposure_off=True, shadow_fade_off=True
        )
        write_developed(stage / "unexposed_foreground_rgb16.tif", unexposed)
        base = saved_asset(project, f"revisions/{revision}/foreground_rgb16.tif")
        (stage / "base_foreground_rgb16.tif").write_bytes(base.read_bytes())
        for name in (
            "support16.png",
            "protection16.png",
            "alpha16.png",
            "settings.json",
            "area.json",
        ):
            asset = f"effects/exposure/{name}"
            if asset in revision_hashes(manifest):
                (stage / ("exposure_" + name)).write_bytes(
                    saved_asset(project, f"revisions/{revision}/{asset}").read_bytes()
                )
    if "shadow_fade" in manifest:
        unfaded, _, _ = saved_layers(project, revision, state["developed_id"], shadow_fade_off=True)
        write_developed(stage / "unfaded_foreground_rgb16.tif", unfaded)
        if "local_exposure" not in manifest:
            write_developed(stage / "unexposed_foreground_rgb16.tif", unfaded)
            (stage / "base_foreground_rgb16.tif").write_bytes(
                saved_asset(project, f"revisions/{revision}/foreground_rgb16.tif").read_bytes()
            )
        for name in shadow_fade_files(manifest["shadow_fade"]):
            asset = f"effects/shadow-fade/{name}"
            if asset in revision_hashes(manifest):
                (stage / ("shadow_fade_" + name)).write_bytes(
                    saved_asset(project, f"revisions/{revision}/{asset}").read_bytes()
                )
    write_developed(stage / "source_rgb16.tif", load_developed(project, state["developed_id"])[0])
    if "spatial_fade" in manifest:
        for name in spatial_fade_files(manifest["spatial_fade"]):
            (stage / ("spatial_fade_" + name)).write_bytes(
                saved_asset(
                    project, f"revisions/{revision}/effects/spatial-fade/{name}"
                ).read_bytes()
            )
    for name in ("shadow_weight16.png", "corrected_rgb16.tif", "recipe.toml"):
        if name in revision_hashes(manifest):
            (stage / name).write_bytes(
                saved_asset(project, f"revisions/{revision}/{name}").read_bytes()
            )
    for effect, name in (
        ("color_cleanup", "effects/settings.json"),
        ("shading", "effects/shading/settings.json"),
    ):
        if effect in manifest:
            (stage / (effect + "_settings.json")).write_bytes(
                _json_bytes(_delivery_effect_record(manifest[effect]))
            )
