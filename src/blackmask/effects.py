"""Source-only color cleanup and immutable effects publication; no model execution."""

import json
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
import tomli_w
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

from .assets import (
    collect_stage_assets,
    inherit_revision_files,
    revision_hashes,
    saved_asset,
    stage_asset,
)
from .exposure import (
    EXPOSURE_FILES,
    rasterize_effect_area,
    rasterize_exposure_area,
    read_exposure,
    selected_exposure,
    validate_exposure,
)
from .guidance import coordinates, rasterize_regions
from .ingest import write_developed
from .project import (
    ProjectError,
    _atomic_bytes,
    _atomic_json,
    _json_bytes,
    _root,
    _validate_revision_directory,
    check_space,
    digest,
    load_developed,
    read_project,
    read_revision,
    record_generated_result,
)
from .repair import scalar16, validate_support
from .shadow_fade import (
    SHADOW_FADE_FILES,
    read_shadow_fade,
    selected_shadow_fade,
    validate_shadow_fade,
)
from .spatial_fade import (
    SPATIAL_FADE_ALGORITHM,
    SPATIAL_FADE_FILES,
    SpatialFadeOperands,
    make_spatial_weight,
    read_spatial_fade,
    validate_spatial_fade,
)


def validate_shading(settings: Any) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings)
        not in ({"enabled", "opacity"}, {"enabled", "opacity", "width_px", "direction_degrees"})
        or type(settings.get("enabled")) is not bool
    ):
        raise ProjectError("Invalid shading settings")
    for name in set(settings) - {"enabled"}:
        if type(settings[name]) not in {int, float} or not np.isfinite(settings[name]):
            raise ProjectError("Shading settings must be finite numbers")
    if not 0 <= settings["opacity"] <= 1:
        raise ProjectError("Shading opacity must be in [0,1]")
    if settings["enabled"] and "width_px" not in settings:
        raise ProjectError("Shading requires explicit per-photo width and direction")
    if "width_px" in settings and (
        not 0 < settings["width_px"] or not 0 <= settings["direction_degrees"] < 360
    ):
        raise ProjectError("Shading requires positive width and direction in [0,360)")


def read_shading_protection(path: Path) -> np.ndarray:
    """Accept canonical authored categorical8 guides or explicit categorical16 masks."""
    with Image.open(path) as image:
        if image.format == "PNG" and image.mode == "L":
            values = np.array(image)
            if not np.isin(values, [0, 255]).all():
                raise ProjectError("Authored shading protection must contain only 0/255")
            return values.astype(np.uint16) * 257
    return scalar16(path)


def make_shadow_weight(
    source16: np.ndarray,
    alpha16: np.ndarray,
    support16: np.ndarray,
    settings: dict[str, Any],
    *,
    protection: np.ndarray,
) -> np.ndarray:
    """Relative inward weight; opacity is deliberately excluded, including at p=0."""
    validate_shading(settings)
    shape = alpha16.shape
    if (
        alpha16.dtype != np.uint16
        or alpha16.ndim != 2
        or source16.dtype != np.uint16
        or source16.shape != (*shape, 3)
        or support16.dtype != np.uint16
        or support16.shape != shape
        or protection.dtype != np.bool_
        or protection.shape != shape
    ):
        raise ProjectError("Shading requires aligned RGB16/A16/support16 and boolean protection")
    if not settings["enabled"]:
        return np.zeros(shape, dtype=np.uint16)
    width = settings["width_px"]
    if width > max(shape):
        raise ProjectError("Shading width exceeds native image extent")
    alpha = alpha16.astype(np.float64) / 65535

    def smooth(value):
        value = np.clip(value, 0, 1)
        return value * value * (3 - 2 * value)

    # Padding makes the image boundary an explicit empty exterior on every side.
    distance = distance_transform_edt(np.pad(alpha >= 0.5, 1))[1:-1, 1:-1]
    edge = 1 - smooth(distance / width)
    # Scale the reference thickness/normal heuristics to the chosen band, not a photo default.
    radius = width * 14 / 48
    core = distance >= radius
    thickness = (
        np.zeros(shape)
        if not core.any()
        else 1 - smooth((distance_transform_edt(~core) - radius) / (width * 8 / 48))
    )
    thickness = gaussian_filter(thickness, width * 2 / 48)
    blurred = gaussian_filter(alpha, width / 4)
    gy = np.gradient(blurred, axis=0) if shape[0] > 1 else np.zeros(shape)
    gx = np.gradient(blurred, axis=1) if shape[1] > 1 else np.zeros(shape)
    magnitude = np.hypot(gx, gy)
    angle = np.deg2rad(settings["direction_degrees"])
    normal = np.divide(
        -gx * np.cos(angle) - gy * np.sin(angle),
        magnitude,
        out=np.zeros(shape),
        where=magnitude > 1e-5,
    )
    direction = 0.35 + 0.65 * smooth((normal + 1) / 2)
    luminance = source16.astype(np.float64) @ np.array([0.2126, 0.7152, 0.0722]) / 65535
    highlights = 1 - 0.75 * smooth((gaussian_filter(luminance, width / 8) - 0.68) / 0.25)
    weight = edge * thickness * direction * highlights * smooth(alpha / 0.35)
    weight *= support16.astype(np.float64) / 65535
    weight[(alpha16 == 0) | (distance >= width) | protection] = 0
    return np.rint(np.clip(weight, 0, 1) * 65535).astype(np.uint16)


def validate_cleanup(settings: Any) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "strength"}
        or type(settings["enabled"]) is not bool
        or type(settings["strength"]) not in {int, float}
        or not np.isfinite(settings["strength"])
        or not 0 <= settings["strength"] <= 1
    ):
        raise ProjectError("Cleanup requires enabled boolean and finite strength in [0,1]")


def make_corrected_rgb(
    source16: np.ndarray,
    alpha16: np.ndarray,
    support16: np.ndarray,
    settings: dict[str, Any],
    *,
    known_empty: np.ndarray,
    protection: np.ndarray,
) -> np.ndarray:
    """Approximate nearest-known-empty inverse mixture; alpha is never modified."""
    validate_cleanup(settings)
    shape = source16.shape[:2]
    if (
        source16.dtype != np.uint16
        or source16.shape != (*shape, 3)
        or alpha16.dtype != np.uint16
        or alpha16.shape != shape
        or support16.dtype != np.uint16
        or support16.shape != shape
        or known_empty.dtype != np.bool_
        or known_empty.shape != shape
        or protection.dtype != np.bool_
        or protection.shape != shape
        or np.any(known_empty & (alpha16 != 0))
    ):
        raise ProjectError(
            "Cleanup requires aligned source RGB16/alpha16/support16 and boolean masks"
        )
    result = source16.copy()
    permitted = (alpha16 > 0) & (alpha16 < 65535) & (support16 > 0) & ~protection
    if not settings["enabled"] or settings["strength"] == 0 or not permitted.any():
        return result
    if not known_empty.any():
        raise ProjectError("Cleanup needs confirmed empty source pixels; revise guides explicitly")
    indices = distance_transform_edt(~known_empty, return_distances=False, return_indices=True)
    background = source16[indices[0][permitted], indices[1][permitted]].astype(np.float64)
    amount = settings["strength"] * (1 - alpha16[permitted].astype(np.float64) / 65535)
    amount *= support16[permitted].astype(np.float64) / 65535
    corrected = (source16[permitted].astype(np.float64) - amount[:, None] * background) / (
        1 - amount[:, None]
    )
    result[permitted] = np.rint(np.clip(corrected, 0, 65535)).astype(np.uint16)
    return result


EFFECT_FILES = (
    "corrected_rgb16.tif",
    "effects/support16.png",
    "effects/alpha16.png",
    "effects/settings.json",
)


SHADING_FILES = (
    "shadow_weight16.png",
    "effects/shading/support16.png",
    "effects/shading/alpha16.png",
    "effects/shading/protection16.png",
    "effects/shading/settings.json",
)


def effects_stale(manifest: dict[str, Any]) -> bool:
    return any(
        manifest.get(name, {}).get("enabled") and manifest[name].get("stale")
        for name in ("color_cleanup", "shading", "local_exposure", "shadow_fade", "spatial_fade")
    )


def inherit_shading(
    project: Path,
    parent: str,
    stage: Path,
    developed_id: str,
    alpha: np.ndarray | None = None,
    *,
    assets: dict[str, Any],
) -> dict[str, Any] | None:
    manifest = read_revision(project, parent, developed_id)
    record = manifest.get("shading")
    if record is None:
        return None
    record = dict(record)
    inherit_revision_files(project, parent, stage, assets, SHADING_FILES)
    if alpha is not None and record["enabled"]:
        record["stale"] = not np.array_equal(
            scalar16(stage_asset(project, stage, assets, "effects/shading/alpha16.png")), alpha
        )
    return record


def saved_shading(
    project: Path,
    revision: str,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    effects_off: bool = False,
):
    record = manifest.get("shading")
    if record is None:
        return None, 0.0
    validate_shading(record["settings"])
    weight = scalar16(saved_asset(project, f"revisions/{revision}/shadow_weight16.png"))
    dependency = scalar16(saved_asset(project, f"revisions/{revision}/effects/shading/alpha16.png"))
    support = scalar16(saved_asset(project, f"revisions/{revision}/effects/shading/support16.png"))
    protection = scalar16(
        saved_asset(project, f"revisions/{revision}/effects/shading/protection16.png")
    )
    if (
        any(value.shape != alpha.shape for value in (weight, dependency, support, protection))
        or type(record.get("enabled")) is not bool
        or type(record.get("stale")) is not bool
        or record.get("developed_id") != manifest["developed_id"]
        or record["enabled"] != record["settings"]["enabled"]
        or record["opacity"] != record["settings"]["opacity"]
        or np.any(weight[(protection != 0) | (support == 0)] != 0)
        or record["enabled"]
        and record["stale"] != (not np.array_equal(dependency, alpha))
    ):
        raise ProjectError("Invalid saved shading dependency/protection/status")
    return (
        (None, 0.0)
        if effects_off or effects_stale(manifest) or not record["enabled"]
        else (weight, record["opacity"])
    )


def inherit_exposure(
    project: Path,
    parent: str,
    stage: Path,
    developed_id: str,
    alpha: np.ndarray | None = None,
    rgb_protection: np.ndarray | None = None,
    *,
    assets: dict[str, Any],
) -> dict[str, Any] | None:
    manifest = read_revision(project, parent, developed_id)
    previous = manifest.get("local_exposure")
    if previous is None:
        return None
    record = dict(previous)
    directory = stage / "effects/exposure"
    directory.mkdir(parents=True, exist_ok=True)
    inherit_revision_files(
        project,
        parent,
        stage,
        assets,
        tuple(
            "effects/exposure/" + name
            for name in (*EXPOSURE_FILES, *(("area.json",) if record["area_sha256"] else ()))
        ),
    )
    if alpha is not None:
        record["stale"] = bool(
            record["enabled"]
            and not np.array_equal(
                scalar16(stage_asset(project, stage, assets, "effects/exposure/alpha16.png")), alpha
            )
        )
    if rgb_protection is not None:
        protection = scalar16(
            stage_asset(project, stage, assets, "effects/exposure/protection16.png")
        )
        protection[rgb_protection] = 65535
        Image.fromarray(protection).save(directory / "protection16.png")
        record["protection_sha256"] = digest(
            (stage_asset(project, stage, assets, "effects/exposure/protection16.png")).read_bytes()
        )
    (directory / "settings.json").write_bytes(_json_bytes(record))
    return record


def inherit_shadow_fade(
    project: Path,
    parent: str,
    stage: Path,
    developed_id: str,
    alpha: np.ndarray | None = None,
    rgb_protection: np.ndarray | None = None,
    *,
    assets: dict[str, Any],
) -> dict[str, Any] | None:
    manifest = read_revision(project, parent, developed_id)
    previous = manifest.get("shadow_fade")
    if previous is None:
        return None
    record = dict(previous)
    directory = stage / "effects/shadow-fade"
    directory.mkdir(parents=True, exist_ok=True)
    inherit_revision_files(
        project,
        parent,
        stage,
        assets,
        tuple(
            "effects/shadow-fade/" + name
            for name in (*SHADOW_FADE_FILES, *(("area.json",) if record["area_sha256"] else ()))
        ),
    )
    if alpha is not None:
        record["stale"] = bool(
            record["enabled"]
            and not np.array_equal(
                scalar16(stage_asset(project, stage, assets, "effects/shadow-fade/alpha16.png")),
                alpha,
            )
        )
    if rgb_protection is not None:
        protection = scalar16(
            stage_asset(project, stage, assets, "effects/shadow-fade/protection16.png")
        )
        protection[rgb_protection] = 65535
        Image.fromarray(protection).save(directory / "protection16.png")
        record["protection_sha256"] = digest(
            (
                stage_asset(project, stage, assets, "effects/shadow-fade/protection16.png")
            ).read_bytes()
        )
    (directory / "settings.json").write_bytes(_json_bytes(record))
    return record


def inherit_spatial_fade(
    project: Path,
    parent: str,
    stage: Path,
    developed_id: str,
    alpha: np.ndarray | None = None,
    rgb_protection: np.ndarray | None = None,
    *,
    assets: dict[str, Any],
) -> dict[str, Any] | None:
    manifest = read_revision(project, parent, developed_id)
    previous = manifest.get("spatial_fade")
    if previous is None:
        return None
    record = dict(previous)
    directory = stage / "effects/spatial-fade"
    directory.mkdir(parents=True, exist_ok=True)
    inherit_revision_files(
        project,
        parent,
        stage,
        assets,
        tuple("effects/spatial-fade/" + name for name in SPATIAL_FADE_FILES),
    )
    if alpha is not None:
        record["stale"] = bool(
            record["enabled"]
            and not np.array_equal(
                scalar16(stage_asset(project, stage, assets, "effects/spatial-fade/alpha16.png")),
                alpha,
            )
        )
    if rgb_protection is not None:
        protection = scalar16(
            stage_asset(project, stage, assets, "effects/spatial-fade/protection16.png")
        )
        protection[rgb_protection] = 65535
        Image.fromarray(protection).save(directory / "protection16.png")
        record["protection_sha256"] = digest(
            (
                stage_asset(project, stage, assets, "effects/spatial-fade/protection16.png")
            ).read_bytes()
        )
    (directory / "settings.json").write_bytes(_json_bytes(record))
    return record


def saved_spatial_fade(
    project: Path,
    revision: str,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    effects_off: bool = False,
    spatial_fade_off: bool = False,
) -> SpatialFadeOperands | None:
    saved = read_spatial_fade(
        project, saved_asset(project, f"revisions/{revision}"), manifest, alpha
    )
    if (
        saved is None
        or effects_off
        or spatial_fade_off
        or effects_stale(manifest)
        or not saved.record["enabled"]
    ):
        return None
    return saved


def inherit_cleanup(
    project: Path,
    parent: str,
    stage: Path,
    developed_id: str,
    alpha: np.ndarray | None = None,
    foreground: np.ndarray | None = None,
    rgb_protection: np.ndarray | None = None,
    *,
    assets: dict[str, Any],
) -> dict[str, Any] | None:
    """Carry actual saved assets; refresh dependency status after an alpha operation."""
    manifest = read_revision(project, parent, developed_id)
    record = manifest.get("color_cleanup")
    if record is None:
        return None
    record = dict(record)
    inherit_revision_files(project, parent, stage, assets, EFFECT_FILES)
    if alpha is not None and record["enabled"]:
        dependency = scalar16(stage_asset(project, stage, assets, "effects/alpha16.png"))
        record["stale"] = not np.array_equal(dependency, alpha)
        if foreground is not None and rgb_protection is not None:
            # The alpha operation already validated these explicit saved-value RGB locks
            # against its own write support. Layer selection must not override them.
            corrected = tifffile.imread(stage_asset(project, stage, assets, "corrected_rgb16.tif"))
            if np.any(corrected[rgb_protection] != foreground[rgb_protection]):
                corrected[rgb_protection] = foreground[rgb_protection]
                write_developed(stage / "corrected_rgb16.tif", corrected)
    return record


def selected_foreground(
    project: Path,
    revision: str,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    effects_off: bool = False,
    exposure_off: bool = False,
    shadow_fade_off: bool = False,
) -> np.ndarray:
    from .export import read_rgb16

    record = manifest.get("color_cleanup")
    if record:
        if (
            not isinstance(record, dict)
            or type(record.get("enabled")) is not bool
            or type(record.get("stale")) is not bool
            or record.get("developed_id") != manifest["developed_id"]
        ):
            raise ProjectError("Invalid saved cleanup identity/status")
        corrected = read_rgb16(saved_asset(project, f"revisions/{revision}/corrected_rgb16.tif"))
        dependency = scalar16(saved_asset(project, f"revisions/{revision}/effects/alpha16.png"))
        support = scalar16(saved_asset(project, f"revisions/{revision}/effects/support16.png"))
        with Image.open(
            saved_asset(project, f"revisions/{revision}/supports/protection.png")
        ) as image:
            protection = np.array(image) != 0
        if protection.shape != alpha.shape:
            raise ProjectError("Invalid saved RGB protection dimensions")
        if corrected.shape != foreground.shape:
            raise ProjectError("Invalid corrected RGB16 dimensions")
        if record["enabled"] and np.any(corrected[protection] != foreground[protection]):
            raise ProjectError("Saved corrected RGB violates explicit RGB locks")
        if (
            corrected.shape != foreground.shape
            or dependency.shape != alpha.shape
            or support.shape != alpha.shape
            or record["enabled"]
            and record["stale"] != (not np.array_equal(dependency, alpha))
        ):
            raise ProjectError("Invalid saved cleanup dependency/status")
    unexposed = (
        foreground
        if not record or not record["enabled"] or effects_off or record["stale"]
        else corrected
    )
    exposed = selected_exposure(
        project,
        saved_asset(project, f"revisions/{revision}"),
        unexposed,
        alpha,
        manifest,
        exposure_off=exposure_off or effects_off,
    )[0]
    return selected_shadow_fade(
        project,
        saved_asset(project, f"revisions/{revision}"),
        exposed,
        alpha,
        manifest,
        shadow_fade_off=shadow_fade_off or effects_off,
    )


def saved_effect_lock_layers(project: Path, revision: str, developed_id: str):
    """Prepared lock snapshots bind the inherited complete appearance, before new guides apply."""
    from .export import saved_layers
    from .repair import prepared_parent_layers

    manifest = read_revision(project, revision, developed_id)
    if manifest["kind"] == "prepare":
        parent = prepared_parent_layers(project, revision, developed_id)
        if manifest.get("color_cleanup") != parent.get("color_cleanup") or revision_hashes(
            manifest
        ).get("corrected_rgb16.tif") != revision_hashes(parent).get("corrected_rgb16.tif"):
            raise ProjectError("Prepared lock must retain its inherited corrected RGB")
        if manifest.get("local_exposure") != parent.get("local_exposure") or any(
            revision_hashes(manifest).get(name) != revision_hashes(parent).get(name)
            for name in revision_hashes(parent)
            if name.startswith("effects/exposure/")
        ):
            raise ProjectError("Prepared lock must retain inherited local exposure")
        if manifest.get("shadow_fade") != parent.get("shadow_fade") or any(
            revision_hashes(manifest).get(name) != revision_hashes(parent).get(name)
            for name in revision_hashes(parent)
            if name.startswith("effects/shadow-fade/") or name == "base_alpha16.png"
        ):
            raise ProjectError("Prepared lock must retain inherited Shadow fade and alpha")
        if manifest.get("spatial_fade") != parent.get("spatial_fade") or any(
            manifest["files"].get(name) != parent["files"].get(name)
            for name in parent["files"]
            if name.startswith("effects/spatial-fade/")
        ):
            raise ProjectError("Prepared lock must retain inherited spatial fade")
        revision = parent["revision"]
    return saved_layers(project, revision, developed_id)


def run_effects(
    project: Path, operation: dict[str, Any], request_file: Path | None
) -> dict[str, Any]:
    """Caller holds the canonical writer lock; preserve all prior complete revisions."""
    from .export import publish_artifacts, read_rgb16, saved_layers
    from .operations import _input_file, _reject_pending_guidance, draft_digest
    from .review import write_revision_overview

    required = {
        "schema_version",
        "kind",
        "developed_id",
        "base_revision",
        "inputs_digest",
        "scope_xyxy",
        "candidate_comparison",
    }
    if (
        not required <= set(operation)
        or set(operation)
        - required
        - {
            "background",
            "support_file",
            "color_cleanup",
            "shading",
            "shading_protection_file",
            "opacity_only",
            "local_exposure",
            "exposure_area",
            "exposure_protection_file",
            "exposure_amount_only",
            "shadow_fade",
            "shadow_fade_area",
            "shadow_fade_protection_file",
            "shadow_fade_amount_only",
            "spatial_fade",
            "spatial_fade_protection_file",
        }
        or type(operation["schema_version"]) is not int
        or operation["schema_version"] != 2
        or operation["kind"] != "effects"
        or type(operation["candidate_comparison"]) is not bool
    ):
        raise ProjectError("Invalid schema-2 effects request")
    spatial_changed = "spatial_fade" in operation
    if spatial_changed:
        if set(operation) - required - {"spatial_fade", "spatial_fade_protection_file"}:
            raise ProjectError("Spatial fade must be an exclusive effects operation")
    elif "spatial_fade_protection_file" in operation:
        raise ProjectError("Spatial protection requires spatial fade settings")
    background_changed = "background" in operation
    if background_changed:
        from .background import validate_background

        validate_background(operation["background"])
        if set(operation) != required | {"background"}:
            raise ProjectError("Background must be an exclusive effects operation")
    fade_changed = "shadow_fade" in operation
    exposure_changed = "local_exposure" in operation
    exposure_fields = {"exposure_area", "exposure_protection_file", "exposure_amount_only"}
    if exposure_changed:
        validate_exposure(operation["local_exposure"])
        if set(operation) & {
            "color_cleanup",
            "shading",
            "shading_protection_file",
            "opacity_only",
            "shadow_fade",
            "shadow_fade_area",
            "shadow_fade_amount_only",
            "shadow_fade_protection_file",
        }:
            raise ProjectError("Local exposure must be a separate effects operation")
        if type(operation.get("exposure_amount_only", False)) is not bool:
            raise ProjectError("exposure_amount_only must be boolean")
        reuse = (
            operation.get("exposure_amount_only", False)
            or not operation["local_exposure"]["enabled"]
        )
        if reuse and set(operation) & {"support_file", "exposure_area", "exposure_protection_file"}:
            raise ProjectError("Exposure amount-only/disable cannot replace area or protection")
        if not reuse and not (
            (
                "exposure_area" in operation
                and not set(operation) & {"support_file", "exposure_protection_file"}
            )
            or (
                "exposure_area" not in operation
                and {"support_file", "exposure_protection_file"} <= set(operation)
            )
        ):
            raise ProjectError("Exposure rebuild requires exactly one registered area source")
    elif (
        set(operation) & exposure_fields
        or not fade_changed
        and not background_changed
        and not spatial_changed
        and "support_file" not in operation
    ):
        raise ProjectError("Invalid effects support/exposure fields")
    fade_fields = {"shadow_fade_area", "shadow_fade_protection_file", "shadow_fade_amount_only"}
    if fade_changed:
        validate_shadow_fade(operation["shadow_fade"])
        if set(operation) & {
            "color_cleanup",
            "shading",
            "shading_protection_file",
            "opacity_only",
            "local_exposure",
        }:
            raise ProjectError("Shadow fade must be a separate effects operation")
        if type(operation.get("shadow_fade_amount_only", False)) is not bool:
            raise ProjectError("shadow_fade_amount_only must be boolean")
        fade_reuse = (
            operation.get("shadow_fade_amount_only", False)
            or not operation["shadow_fade"]["enabled"]
        )
        if fade_reuse and set(operation) & {
            "support_file",
            "shadow_fade_area",
            "shadow_fade_protection_file",
        }:
            raise ProjectError("Shadow fade amount-only/disable cannot replace area or protection")
        if not fade_reuse and not (
            "shadow_fade_area" in operation
            and not set(operation) & {"support_file", "shadow_fade_protection_file"}
            or "shadow_fade_area" not in operation
            and {"support_file", "shadow_fade_protection_file"} <= set(operation)
        ):
            raise ProjectError("Shadow fade rebuild requires exactly one registered area source")
    elif set(operation) & fade_fields:
        raise ProjectError("Shadow fade fields require shadow_fade settings")
    operation = json.loads(_json_bytes(operation))
    request_bytes = request_file.read_bytes() if request_file else _json_bytes(operation)
    if json.loads(request_bytes) != operation:
        raise ProjectError("Stale effects request file")
    project = _root(project)
    state = read_project(project)
    _reject_pending_guidance(project)
    if (
        operation["developed_id"] != state["developed_id"]
        or operation["base_revision"] != state["working_revision"]
        or operation["inputs_digest"] != draft_digest(project)
    ):
        raise ProjectError("Stale effects master, base revision or draft identity")
    parent = state["working_revision"]
    cleanup_changed = "color_cleanup" in operation or not (
        "shading" in operation
        or exposure_changed
        or fade_changed
        or background_changed
        or spatial_changed
    )
    settings = operation.get(
        "color_cleanup",
        tomllib.loads(saved_asset(project, "recipe.toml").read_text())["color_cleanup"],
    )
    validate_cleanup(settings)
    enabled = settings["enabled"] and settings["strength"] != 0
    if (
        cleanup_changed
        and enabled
        and parent != state["accepted_revision"]
        and not operation["candidate_comparison"]
    ):
        raise ProjectError("Cleanup requires accepted base or explicit candidate comparison")
    foreground, alpha, manifest = saved_layers(
        project, parent, state["developed_id"], effects_off=True
    )
    source, _ = load_developed(project, state["developed_id"])
    height, width = alpha.shape
    scope = coordinates(operation["scope_xyxy"], width, height, box=True)
    if spatial_changed:
        validate_spatial_fade(operation["spatial_fade"], width, height)
        if scope != [0, 0, width, height]:
            raise ProjectError("Spatial fade scope must cover the full native image")
        if operation["spatial_fade"]["enabled"]:
            if parent != state["accepted_revision"] and not operation["candidate_comparison"]:
                raise ProjectError(
                    "Spatial fade requires accepted base or explicit candidate comparison"
                )
        elif "spatial_fade_protection_file" in operation:
            raise ProjectError("Spatial fade disable cannot replace protection")
    if background_changed and scope != [0, 0, width, height]:
        raise ProjectError("Background scope must cover the full native image")
    if (
        background_changed
        and parent != state["accepted_revision"]
        and not operation["candidate_comparison"]
    ):
        raise ProjectError("Background requires accepted base or explicit candidate comparison")
    support_path = (
        _input_file(project, operation["support_file"]) if "support_file" in operation else None
    )
    support_bytes = support_path.read_bytes() if support_path else b""
    support = scalar16(support_path) if support_path else np.zeros(alpha.shape, dtype=np.uint16)
    if cleanup_changed and enabled:
        validate_support(support, alpha.shape, [0, 0, width, height], scope)
    elif support.shape != alpha.shape:
        raise ProjectError("Cleanup support must align with master even when disabled")
    snapshots = {
        name: saved_asset(project, name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    if (
        operation["inputs_digest"]
        != digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
        or json.loads(snapshots["state.json"]) != state
    ):
        raise ProjectError("Stale effects snapshot before processing")
    parent_bytes = saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes()
    parent_guides = saved_asset(project, f"revisions/{parent}/guides.json").read_bytes()
    parent_recipe = tomllib.loads(
        saved_asset(project, f"revisions/{parent}/recipe.toml").read_text()
    )
    current_recipe = tomllib.loads(snapshots["recipe.toml"].decode())
    if json.loads(snapshots["guides.json"]) != json.loads(parent_guides) or any(
        current_recipe[name] != parent_recipe.get(name)
        for name in current_recipe
        if name
        not in {
            "color_cleanup",
            "shading",
            "local_exposure",
            "shadow_fade",
            "spatial_fade",
            "background",
            "notes",
        }
    ):
        raise ProjectError(
            "Changed guidance/base recipe requires prepare and complete matte before effects"
        )
    with Image.open(saved_asset(project, f"revisions/{parent}/trimap.png")) as image:
        trimap = np.array(image)
    with Image.open(saved_asset(project, f"revisions/{parent}/supports/protection.png")) as image:
        protection = np.array(image) != 0
    guides = json.loads(saved_asset(project, f"revisions/{parent}/guides.json").read_bytes())
    # Explicit saved-value locks use the selected saved RGB, including partial-alpha colors.
    lock_values = foreground.copy()
    lock_dependencies = {}
    locked = np.zeros(alpha.shape, dtype=bool)
    for region in guides["regions"]:
        if region["role"] != "lock":
            continue
        revision = region["revision"]
        rgb, locked_alpha, _lock_manifest = saved_effect_lock_layers(
            project, revision, state["developed_id"]
        )
        lock_dependencies[revision] = saved_asset(
            project, f"revisions/{revision}/manifest.json"
        ).read_bytes()
        mask = rasterize_regions(
            dict(guides, regions=[region]),
            scope_xyxy=[0, 0, width, height],
            saved_alpha={revision: locked_alpha},
        ).protection
        if np.any(mask & locked & np.any(lock_values != rgb, axis=2)):
            raise ProjectError("Conflicting saved cleanup RGB locks")
        lock_values[mask] = rgb[mask]
        locked |= mask
    protection |= locked
    check_space(
        project,
        source.nbytes * (47 if background_changed or "background" in manifest else 45) + 1024**2,
    )
    record: dict[str, Any] | None
    if cleanup_changed:
        corrected = make_corrected_rgb(
            source,
            alpha,
            support,
            settings,
            known_empty=(trimap == 0) & (alpha == 0),
            protection=protection,
        )
        # Unaffected pixels start from the actual saved base (including its RGB locks).
        # Correction math above always starts from source, never this saved output.
        writable = (support != 0) & (alpha > 0) & (alpha < 65535) & ~protection
        corrected[~writable] = foreground[~writable]
        previous = manifest.get("color_cleanup")
        dependency = alpha.copy()
        cumulative_support = support.copy()
        if (
            enabled
            and previous is not None
            and previous["enabled"]
            and "corrected_rgb16.tif" in revision_hashes(manifest)
        ):
            prior = tifffile.imread(saved_asset(project, f"revisions/{parent}/corrected_rgb16.tif"))
            corrected[support == 0] = prior[support == 0]
            dependency = scalar16(saved_asset(project, f"revisions/{parent}/effects/alpha16.png"))
            dependency[support != 0] = alpha[support != 0]
            cumulative_support = scalar16(
                saved_asset(project, f"revisions/{parent}/effects/support16.png")
            )
            cumulative_support[support != 0] = support[support != 0]
        corrected[protection & (support != 0)] = lock_values[protection & (support != 0)]
        record = {
            "enabled": bool(enabled),
            "strength": settings["strength"],
            "stale": bool(enabled and not np.array_equal(dependency, alpha)),
            "developed_id": state["developed_id"],
            "algorithm": "nearest-confirmed-empty-inverse-mixture-v1",
            "scope_xyxy": scope,
            "support_sha256": digest(support_bytes),
            "alpha_sha256": revision_hashes(manifest)["base_alpha16.png"],
            "parent_manifest_sha256": digest(parent_bytes),
            "candidate_comparison": operation["candidate_comparison"],
        }
    else:
        record = manifest.get("color_cleanup")
        enabled = bool(record and record["enabled"])
        corrected = (
            tifffile.imread(saved_asset(project, f"revisions/{parent}/corrected_rgb16.tif"))
            if record
            else foreground.copy()
        )
        cumulative_support = support
        dependency = alpha
    shading_record = manifest.get("shading")
    shading_inputs = {}
    if "shading" in operation:
        shading_settings = operation["shading"]
        validate_shading(shading_settings)
        if (
            shading_settings["enabled"]
            and parent != state["accepted_revision"]
            and not operation["candidate_comparison"]
        ):
            raise ProjectError("Shading requires accepted base or explicit candidate comparison")
        if type(operation.get("opacity_only", False)) is not bool:
            raise ProjectError("opacity_only must be boolean")
        if operation.get("opacity_only"):
            if manifest.get("spatial_fade", {}).get("enabled") and shading_settings["enabled"]:
                raise ProjectError(
                    "Opacity-only cannot select inward shading; explicitly select that mode"
                )
            if shading_record is None:
                raise ProjectError("Opacity-only operation requires saved shading")
            if any(
                shading_settings.get(key) != shading_record["settings"].get(key)
                for key in ("width_px", "direction_degrees")
            ):
                raise ProjectError("Opacity-only operation cannot change geometry")
        elif shading_settings["enabled"]:
            validate_support(support, alpha.shape, [0, 0, width, height], scope)
            if "shading_protection_file" not in operation:
                raise ProjectError("Shading rebuild requires explicit protection file")
            path = _input_file(project, operation["shading_protection_file"])
            shading_inputs[path] = path.read_bytes()
            own_protection = read_shading_protection(path)
            if own_protection.shape != alpha.shape or not np.isin(own_protection, [0, 65535]).all():
                raise ProjectError("Shading protection must be aligned categorical scalar16")
        if shading_record is None and not shading_settings["enabled"]:
            own_protection = np.zeros(alpha.shape, dtype=np.uint16)
    exposure_record = manifest.get("local_exposure")
    exposure_inputs = {}
    exposure_area_bytes = None
    if exposure_changed:
        exposure_settings = operation["local_exposure"]
        saved = read_exposure(project, saved_asset(project, f"revisions/{parent}"), manifest, alpha)
        if (
            exposure_settings["enabled"]
            and parent != state["accepted_revision"]
            and not operation["candidate_comparison"]
        ):
            raise ProjectError(
                "Local exposure requires accepted base or explicit candidate comparison"
            )
        if operation.get("exposure_amount_only") and saved is None:
            raise ProjectError("Exposure amount-only requires a saved area")
        if reuse:
            if saved is None:
                exposure_support = np.zeros(alpha.shape, dtype=np.uint16)
                exposure_protection = protection.copy()
                exposure_dependency = alpha.copy()
            else:
                exposure_support, exposure_protection, old_record = saved
                exposure_dependency = scalar16(
                    saved_asset(project, f"revisions/{parent}/effects/exposure/alpha16.png")
                )
                if exposure_settings["enabled"] and not np.array_equal(exposure_dependency, alpha):
                    raise ProjectError("Stale local exposure alpha: rebuild or disable")
                if old_record["area_sha256"]:
                    exposure_area_bytes = saved_asset(
                        project, f"revisions/{parent}/effects/exposure/area.json"
                    ).read_bytes()
        else:
            if "exposure_area" in operation:
                exposure_support, exposure_protection = rasterize_exposure_area(
                    operation["exposure_area"], state["developed_id"], width, height
                )
                exposure_area_bytes = _json_bytes(operation["exposure_area"])
            else:
                assert support_path is not None
                exposure_inputs[support_path] = support_bytes
                exposure_support = support
                path = _input_file(project, operation["exposure_protection_file"])
                exposure_inputs[path] = path.read_bytes()
                explicit = read_shading_protection(path)
                if explicit.shape != alpha.shape or not np.isin(explicit, [0, 65535]).all():
                    raise ProjectError("Exposure protection must be aligned categorical scalar16/8")
                exposure_protection = explicit != 0
            exposure_dependency = alpha.copy()
        exposure_protection |= protection
        # Replacing A with B removes A as well: both areas must be inside the declared scope.
        combined = (exposure_support != 0) | (saved[0] != 0 if saved else False)
        x0, y0, x1, y1 = scope
        outside = combined.copy()
        outside[y0:y1, x0:x1] = False
        if outside.any():
            raise ProjectError("Exposure scope must contain both previous and replacement area")
        if exposure_settings["enabled"] and not np.any(
            (exposure_support != 0) & (alpha != 0) & ~exposure_protection
        ):
            raise ProjectError("Enabled local exposure requires a nonempty eligible selection")
    fade_record = manifest.get("shadow_fade")
    fade_inputs = {}
    fade_area_bytes = None
    if fade_changed:
        fade_settings = operation["shadow_fade"]
        saved = read_shadow_fade(
            project, saved_asset(project, f"revisions/{parent}"), manifest, alpha
        )
        if (
            fade_settings["enabled"]
            and parent != state["accepted_revision"]
            and not operation["candidate_comparison"]
        ):
            raise ProjectError(
                "Shadow fade requires accepted base or explicit candidate comparison"
            )
        if operation.get("shadow_fade_amount_only") and fade_settings["enabled"] and saved is None:
            raise ProjectError("Shadow fade amount-only requires a saved area")
        if fade_reuse:
            if saved is None:
                fade_support = np.zeros(alpha.shape, dtype=np.uint16)
                fade_protection = protection.copy()
                fade_dependency = alpha.copy()
            else:
                fade_support, fade_protection, old_record = saved
                fade_dependency = scalar16(
                    saved_asset(project, f"revisions/{parent}/effects/shadow-fade/alpha16.png")
                )
                if fade_settings["enabled"] and not np.array_equal(fade_dependency, alpha):
                    raise ProjectError("Stale Shadow fade alpha: rebuild or disable")
                if old_record["area_sha256"]:
                    fade_area_bytes = saved_asset(
                        project, f"revisions/{parent}/effects/shadow-fade/area.json"
                    ).read_bytes()
        else:
            if "shadow_fade_area" in operation:
                fade_support, fade_protection = rasterize_effect_area(
                    operation["shadow_fade_area"], state["developed_id"], width, height
                )
                fade_area_bytes = _json_bytes(operation["shadow_fade_area"])
            else:
                assert support_path is not None
                fade_inputs[support_path] = support_bytes
                fade_support = support
                path = _input_file(project, operation["shadow_fade_protection_file"])
                fade_inputs[path] = path.read_bytes()
                explicit = read_shading_protection(path)
                if explicit.shape != alpha.shape or not np.isin(explicit, [0, 65535]).all():
                    raise ProjectError(
                        "Shadow fade protection must be aligned categorical scalar16/8"
                    )
                fade_protection = explicit != 0
            fade_dependency = alpha.copy()
        fade_protection |= protection
        # Replacing A with B removes A as well: both areas must be inside the declared scope.
        combined = (fade_support != 0) | (saved[0] != 0 if saved else False)
        x0, y0, x1, y1 = scope
        outside = combined.copy()
        outside[y0:y1, x0:x1] = False
        if outside.any():
            raise ProjectError("Shadow fade scope must contain both previous and replacement area")
        if fade_settings["enabled"] and not np.any(
            (fade_support != 0) & (alpha != 0) & ~fade_protection
        ):
            raise ProjectError("Enabled Shadow fade requires a nonempty eligible selection")
    if not spatial_changed and current_recipe.get("spatial_fade") != parent_recipe.get(
        "spatial_fade"
    ):
        raise ProjectError("Changed spatial fade recipe requires explicit spatial fade operation")
    spatial_inputs = {}
    if spatial_changed:
        spatial_settings = operation["spatial_fade"]
        previous_spatial = read_spatial_fade(
            project, saved_asset(project, f"revisions/{parent}"), manifest, alpha
        )
        spatial_protection = protection.copy()
        if previous_spatial is not None:
            spatial_protection |= previous_spatial.protection
        if shading_record is not None:
            spatial_protection |= (
                scalar16(
                    saved_asset(project, f"revisions/{parent}/effects/shading/protection16.png")
                )
                != 0
            )
        if "spatial_fade_protection_file" in operation:
            path = _input_file(project, operation["spatial_fade_protection_file"])
            spatial_inputs[path] = path.read_bytes()
            explicit = read_shading_protection(path)
            if explicit.shape != alpha.shape or not np.isin(explicit, [0, 65535]).all():
                raise ProjectError("Spatial protection must be aligned categorical scalar16/8")
            spatial_protection |= explicit != 0
        geometric_keys = ("oval", "arcs_enabled", "arcs")
        spatial_weight = (
            previous_spatial.weight16
            if previous_spatial is not None
            and all(
                spatial_settings[key] == previous_spatial.record["settings"][key]
                for key in geometric_keys
            )
            else make_spatial_weight(alpha.shape, spatial_settings)
        )
        spatial_dependency = (
            scalar16(saved_asset(project, f"revisions/{parent}/effects/spatial-fade/alpha16.png"))
            if previous_spatial is not None and not spatial_settings["enabled"]
            else alpha
        )
    revisions = saved_asset(project, "revisions")
    existing = [
        int(p.name[4:]) for p in revisions.iterdir() if re.fullmatch(r"rev-[0-9]{3,}", p.name)
    ]
    revision = f"rev-{max(existing, default=0) + 1:03d}"
    stage = Path(tempfile.mkdtemp(prefix=".effects-", dir=revisions))
    assets: dict[str, Any] = {}
    for name in (
        "recipe.toml",
        "guides.json",
        "trimap.png",
        "supports/support16.png",
        "supports/protection.png",
        "supports/lock_values16.png",
        "base_alpha16.png",
        "foreground_rgb16.tif",
        "qa.json",
    ):
        inherit_revision_files(project, parent, stage, assets, (name,))
    if "trimap_approval.json" in revision_hashes(manifest):
        (stage / "trimap_approval.json").write_bytes(
            saved_asset(project, f"revisions/{parent}/trimap_approval.json").read_bytes()
        )
    for name in ("recipe.toml", "guides.json"):
        (stage / name).write_bytes(snapshots[name])
    (stage / "effects").mkdir(exist_ok=True)
    if cleanup_changed:
        assert record is not None
        Image.fromarray(cumulative_support).save(stage / "effects/support16.png")
        Image.fromarray(dependency).save(stage / "effects/alpha16.png")
        (stage / "effects/settings.json").write_bytes(_json_bytes(dict(record, settings=settings)))
        (stage / "effects/write_support16.png").write_bytes(support_bytes)
        write_developed(stage / "corrected_rgb16.tif", corrected)
        if not np.array_equal(
            tifffile.imread(stage_asset(project, stage, assets, "corrected_rgb16.tif")), corrected
        ):
            raise ProjectError("Corrected RGB16 round trip failed")
    else:
        inherit_cleanup(project, parent, stage, state["developed_id"], assets=assets)
    shading_record = inherit_shading(project, parent, stage, state["developed_id"], assets=assets)
    if "shading" in operation:
        old = shading_record
        if old and not shading_settings["enabled"] and "width_px" not in shading_settings:
            shading_settings = dict(old["settings"], **shading_settings)
        if old is None:
            weight = np.zeros(alpha.shape, dtype=np.uint16)
            shading_dependency = alpha.copy()
            shading_support = np.zeros(alpha.shape, dtype=np.uint16)
            saved_protection = np.zeros(alpha.shape, dtype=np.uint16)
        else:
            weight = scalar16(stage_asset(project, stage, assets, "shadow_weight16.png"))
            shading_dependency = scalar16(
                stage_asset(project, stage, assets, "effects/shading/alpha16.png")
            )
            shading_support = scalar16(
                stage_asset(project, stage, assets, "effects/shading/support16.png")
            )
            saved_protection = scalar16(
                stage_asset(project, stage, assets, "effects/shading/protection16.png")
            )
        if shading_settings["enabled"] and not operation.get("opacity_only"):
            explicit = (own_protection != 0) | (saved_protection != 0) | protection
            rebuilt = make_shadow_weight(
                source, alpha, support, shading_settings, protection=explicit
            )
            writable = support != 0
            # Rebuild only its declared support; preserve prior W elsewhere.
            weight[writable] = rebuilt[writable]
            shading_dependency[writable] = alpha[writable]
            shading_support[writable] = support[writable]
            saved_protection[writable] = explicit[writable].astype(np.uint16) * 65535
        shading_record = {
            "enabled": shading_settings["enabled"],
            "opacity": shading_settings["opacity"],
            "settings": shading_settings,
            "developed_id": state["developed_id"],
            "stale": bool(
                shading_settings["enabled"] and not np.array_equal(shading_dependency, alpha)
            ),
            "algorithm": "inward-smoothstep-thickness-direction-highlight-v1",
            "scope_xyxy": scope,
            "operation_scope": "global opacity only"
            if operation.get("opacity_only")
            else "scoped rebuild"
            if shading_settings["enabled"]
            else "global explicit disable",
            "candidate_comparison": operation["candidate_comparison"],
        }
        directory = stage / "effects/shading"
        directory.mkdir(parents=True, exist_ok=True)
        if old is None or (shading_settings["enabled"] and not operation.get("opacity_only")):
            for name, value in (
                ("support16", shading_support),
                ("alpha16", shading_dependency),
                ("protection16", saved_protection),
            ):
                Image.fromarray(value).save(directory / (name + ".png"))
            Image.fromarray(weight).save(stage / "shadow_weight16.png")
        (directory / "settings.json").write_bytes(_json_bytes(shading_record))
        if not np.array_equal(
            scalar16(stage_asset(project, stage, assets, "shadow_weight16.png")), weight
        ):
            raise ProjectError("Shadow W16 round trip failed")
    spatial_record = inherit_spatial_fade(
        project, parent, stage, state["developed_id"], assets=assets
    )
    if spatial_changed:
        directory = stage / "effects/spatial-fade"
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in (
            ("weight16", spatial_weight),
            ("protection16", spatial_protection.astype(np.uint16) * 65535),
            ("alpha16", spatial_dependency),
        ):
            Image.fromarray(value).save(directory / (name + ".png"))
        spatial_record = {
            "schema_version": 1,
            "enabled": spatial_settings["enabled"],
            "settings": spatial_settings,
            "stale": False,
            "source_id": state["developed_id"],
            "algorithm": SPATIAL_FADE_ALGORITHM,
            "scope_xyxy": [0, 0, width, height],
            "candidate_comparison": operation["candidate_comparison"],
            **{
                key: digest((directory / name).read_bytes())
                for name, key in (
                    ("weight16.png", "weight_sha256"),
                    ("protection16.png", "protection_sha256"),
                    ("alpha16.png", "alpha_sha256"),
                )
            },
        }
        (directory / "settings.json").write_bytes(_json_bytes(spatial_record))
        if spatial_settings["enabled"] and shading_record is not None:
            shading_record = dict(
                shading_record,
                enabled=False,
                stale=False,
                settings=dict(shading_record["settings"], enabled=False),
            )
            (stage / "effects/shading/settings.json").write_bytes(_json_bytes(shading_record))
    if "shading" in operation and spatial_record is not None and shading_settings["enabled"]:
        spatial_record = dict(
            spatial_record,
            enabled=False,
            stale=False,
            settings=dict(spatial_record["settings"], enabled=False),
        )
        (stage / "effects/spatial-fade/settings.json").write_bytes(_json_bytes(spatial_record))
    exposure_record = inherit_exposure(project, parent, stage, state["developed_id"], assets=assets)
    if exposure_changed:
        directory = stage / "effects/exposure"
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in (
            ("support16", exposure_support),
            ("protection16", exposure_protection.astype(np.uint16) * 65535),
            ("alpha16", exposure_dependency),
        ):
            Image.fromarray(value).save(directory / (name + ".png"))
        if exposure_area_bytes is not None:
            (directory / "area.json").write_bytes(exposure_area_bytes)
        elif (directory / "area.json").exists():
            # Stage is new; omit inherited authored geometry when replacing with scalar inputs.
            (directory / "area.json").unlink()
        exposure_record = {
            "schema_version": 2,
            "enabled": exposure_settings["enabled"],
            "settings": exposure_settings,
            "stale": bool(
                exposure_settings["enabled"] and not np.array_equal(exposure_dependency, alpha)
            ),
            "developed_id": state["developed_id"],
            "algorithm": "linear-srgb-local-exposure-v1",
            "scope_xyxy": scope,
            "candidate_comparison": operation["candidate_comparison"],
            "area_sha256": digest(exposure_area_bytes) if exposure_area_bytes is not None else None,
            **{
                key: digest((directory / name).read_bytes())
                for name, key in (
                    ("support16.png", "support_sha256"),
                    ("protection16.png", "protection_sha256"),
                    ("alpha16.png", "alpha_sha256"),
                )
            },
        }
        (directory / "settings.json").write_bytes(_json_bytes(exposure_record))
    fade_record = inherit_shadow_fade(project, parent, stage, state["developed_id"], assets=assets)
    if fade_changed:
        directory = stage / "effects/shadow-fade"
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in (
            ("support16", fade_support),
            ("protection16", fade_protection.astype(np.uint16) * 65535),
            ("alpha16", fade_dependency),
        ):
            Image.fromarray(value).save(directory / (name + ".png"))
        if fade_area_bytes is not None:
            (directory / "area.json").write_bytes(fade_area_bytes)
        elif (directory / "area.json").exists():
            # Stage is new; omit inherited authored geometry when replacing with scalar inputs.
            (directory / "area.json").unlink()
        fade_record = {
            "schema_version": 2,
            "enabled": fade_settings["enabled"],
            "settings": fade_settings,
            "stale": bool(fade_settings["enabled"] and not np.array_equal(fade_dependency, alpha)),
            "developed_id": state["developed_id"],
            "algorithm": "linear-srgb-shadow-fade-v1",
            "scope_xyxy": scope,
            "candidate_comparison": operation["candidate_comparison"],
            "area_sha256": digest(fade_area_bytes) if fade_area_bytes is not None else None,
            **{
                key: digest((directory / name).read_bytes())
                for name, key in (
                    ("support16.png", "support_sha256"),
                    ("protection16.png", "protection_sha256"),
                    ("alpha16.png", "alpha_sha256"),
                )
            },
        }
        (directory / "settings.json").write_bytes(_json_bytes(fade_record))
    (stage / "request.json").write_bytes(request_bytes)
    (stage / "inputs").mkdir()
    for name, data in snapshots.items():
        (stage / "inputs" / name).write_bytes(data)
    from .background import inherit_background, save_background

    background_record: dict[str, Any] | None
    if background_changed:
        background_record = save_background(
            stage, state["developed_id"], (height, width), operation["background"]
        )
    else:
        background_record = inherit_background(
            project,
            parent,
            stage,
            state["developed_id"],
            (height, width),
            parent_recipe.get("background"),
            assets=assets,
        )
    effect_records = {}
    if background_record is not None:
        effect_records["background"] = background_record
    if record is not None:
        effect_records["color_cleanup"] = record
    if shading_record is not None:
        effect_records["shading"] = shading_record
    if exposure_record is not None:
        effect_records["local_exposure"] = exposure_record
    if fade_record is not None:
        effect_records["shadow_fade"] = fade_record
    if spatial_record is not None:
        effect_records["spatial_fade"] = spatial_record
    effective_recipe = dict(parent_recipe)
    applied_sections = set()
    if cleanup_changed:
        assert record is not None
        effective_recipe["color_cleanup"] = {
            "enabled": record["enabled"],
            "strength": record["strength"],
        }
        applied_sections.add("color_cleanup")
    for name, changed in (
        (
            "shading",
            "shading" in operation
            or spatial_changed
            and spatial_settings["enabled"]
            and shading_record is not None,
        ),
        ("local_exposure", exposure_changed),
        ("shadow_fade", fade_changed),
        (
            "spatial_fade",
            spatial_changed
            or "shading" in operation
            and shading_settings["enabled"]
            and spatial_record is not None,
        ),
        ("background", background_changed),
    ):
        if changed:
            effective_recipe[name] = dict(effect_records[name]["settings"])
            applied_sections.add(name)
    synchronized_recipe = dict(current_recipe)
    for name in applied_sections:
        synchronized_recipe[name] = effective_recipe[name]
    published_recipe = (
        snapshots["recipe.toml"]
        if synchronized_recipe == current_recipe
        else tomli_w.dumps(synchronized_recipe).encode()
    )
    effective_recipe_bytes = (
        published_recipe
        if synchronized_recipe == effective_recipe
        else tomli_w.dumps(effective_recipe).encode()
    )
    (stage / "recipe.toml").write_bytes(effective_recipe_bytes)
    stale = effects_stale(effect_records)
    appearance = corrected if enabled and not stale else foreground
    appearance, clipping = selected_exposure(
        project,
        stage,
        appearance,
        alpha,
        dict(effect_records, developed_id=state["developed_id"], assets=assets),
        exposure_off=stale,
    )
    appearance = selected_shadow_fade(
        project,
        stage,
        appearance,
        alpha,
        dict(effect_records, developed_id=state["developed_id"], assets=assets),
        shadow_fade_off=stale,
    )
    review_weight, opacity = (
        (
            scalar16(stage_asset(project, stage, assets, "shadow_weight16.png")),
            shading_record["opacity"],
        )
        if shading_record and shading_record["enabled"] and not stale
        else (None, 0.0)
    )
    spatial_operands = (
        SpatialFadeOperands(
            scalar16(stage_asset(project, stage, assets, "effects/spatial-fade/weight16.png")),
            scalar16(stage_asset(project, stage, assets, "effects/spatial-fade/protection16.png"))
            != 0,
            spatial_record,
        )
        if spatial_record is not None and spatial_record["enabled"] and not stale
        else None
    )
    review_background = (
        read_rgb16(stage_asset(project, stage, assets, "background/background_rgb16.tif"))
        if background_record is not None and not stale
        else None
    )
    review = write_revision_overview(
        stage / "review",
        source,
        appearance,
        alpha,
        developed_id=state["developed_id"],
        revision=revision,
        background16=review_background,
        spatial_fade=spatial_operands,
        fade_background16=review_background
        if review_background is not None
        else np.zeros_like(appearance)
        if spatial_operands is not None
        else None,
        weight16=review_weight,
        opacity=opacity,
    )
    review.update(effect_records)
    if exposure_record is not None:
        review["local_exposure_clipping"] = clipping
        review["label"] += (
            "; local exposure OFF"
            if stale or not exposure_record["enabled"]
            else f"; local exposure ON {exposure_record['settings']['ev']} EV"
        )
    if fade_record is not None:
        review["label"] += (
            "; Shadow fade ON" if fade_record["enabled"] and not stale else "; Shadow fade OFF"
        )
    if spatial_record is not None:
        review["label"] += (
            "; Fade into background ON; diagnostic backdrops retain its selected target"
            if spatial_operands is not None
            else "; Fade into background OFF"
        )
    review["label"] += "; cleanup ON" if enabled and not stale else "; cleanup OFF"
    review["label"] += (
        "; shading ON; baked shading preview" if review_weight is not None else "; shading OFF"
    )
    if stale:
        review["label"] += (
            "; BASE comparison: cleanup OFF; shading OFF; stale enabled effects need scoped rebuild or explicit disable"
        )
    (stage / "review/manifest.json").write_bytes(_json_bytes(review))
    result = {
        "revision": revision,
        "parent": parent,
        "developed_id": state["developed_id"],
        "kind": "effects",
        "model": {"inference": "not invoked; saved base layers only"},
        "status": "review_needed",
        "final_acceptable": True,
        "inputs_digest": operation["inputs_digest"],
        **effect_records,
    }
    (stage / "result.json").write_bytes(_json_bytes(result))
    collect_stage_assets(project, stage, assets)
    files = {
        str(p.relative_to(stage)): digest(p.read_bytes()) for p in stage.rglob("*") if p.is_file()
    }
    new_manifest = dict(
        manifest,
        **result,
        complete=True,
        files=files,
        assets=assets,
        parent_manifest_sha256=digest(parent_bytes),
        scope_xyxy=scope,
        draft_digest=digest(effective_recipe_bytes + b"\0" + snapshots["guides.json"]),
        foreground_asset="corrected_rgb16.tif" if enabled else "foreground_rgb16.tif",
    )
    (stage / "manifest.json").write_bytes(_json_bytes(new_manifest))

    def recheck():
        for path, data in spatial_inputs.items():
            if path.read_bytes() != data:
                raise ProjectError("Stale spatial fade protection input")
        for path, data in fade_inputs.items():
            if path.read_bytes() != data:
                raise ProjectError("Stale Shadow fade input")
        for path, data in exposure_inputs.items():
            if path.read_bytes() != data:
                raise ProjectError("Stale local exposure input")
        for path, data in shading_inputs.items():
            if path.read_bytes() != data:
                raise ProjectError("Stale shading protection input")
        for name, data in snapshots.items():
            if saved_asset(project, name).read_bytes() != data:
                raise ProjectError(f"Stale effects input: {name}")
        if (
            support_path is not None
            and support_path.read_bytes() != support_bytes
            or saved_asset(project, f"revisions/{parent}/manifest.json").read_bytes()
            != parent_bytes
            or request_file
            and request_file.read_bytes() != request_bytes
        ):
            raise ProjectError("Stale effects support/request/parent")
        read_revision(project, parent, state["developed_id"])
        load_developed(project, state["developed_id"])
        for saved_revision, data in lock_dependencies.items():
            read_revision(project, saved_revision, state["developed_id"])
            if (
                saved_asset(project, f"revisions/{saved_revision}/manifest.json").read_bytes()
                != data
            ):
                raise ProjectError("Stale cleanup saved RGB lock")

    recheck()
    destination = revisions / revision
    if spatial_record is not None:
        _validate_revision_directory(
            project, revision, state["developed_id"], str(stage.relative_to(project))
        )
    try:
        publish_artifacts(stage, destination)
        read_revision(project, revision, state["developed_id"])
        if published_recipe != snapshots["recipe.toml"]:
            _atomic_bytes(
                saved_asset(project, "recipe.toml"),
                published_recipe,
                validate_before_replace=recheck,
            )
            snapshots["recipe.toml"] = published_recipe
        record_generated_result(state, revision, new_manifest)
        _atomic_json(saved_asset(project, "state.json"), state, validate_before_replace=recheck)
    except OSError as error:
        if spatial_record is not None and destination.exists():
            raise ProjectError(
                f"Fade into background publication durability unconfirmed: visible revision {destination}. "
                "Reload project status and inspect or explicitly restore this revision before retrying; "
                "its files and earlier accepted work were retained."
            ) from error
        raise
    return dict(
        result,
        inputs_digest=draft_digest(project),
        revision_inputs_digest=new_manifest["draft_digest"],
        manifest_file=str(destination / "manifest.json"),
        review_manifest_file=str(destination / "review/manifest.json"),
    )
