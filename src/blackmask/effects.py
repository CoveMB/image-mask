"""Source-only color cleanup and immutable effects publication; no model execution."""

import json
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

from .guidance import coordinates, rasterize_regions
from .ingest import write_master
from .project import (
    ProjectError,
    _asset,
    _atomic_json,
    _json_bytes,
    _root,
    check_space,
    digest,
    load_master,
    read_project,
    read_revision,
)
from .repair import scalar16, validate_support


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
    background = source16[tuple(indices)][permitted].astype(np.float64)
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
        for name in ("color_cleanup", "shading")
    )


def inherit_shading(
    project: Path, parent: str, stage: Path, master_id: str, alpha: np.ndarray | None = None
) -> dict[str, Any] | None:
    manifest = read_revision(project, parent, master_id)
    record = manifest.get("shading")
    if record is None:
        return None
    record = dict(record)
    for name in SHADING_FILES:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_asset(project, f"revisions/{parent}/{name}").read_bytes())
    if alpha is not None and record["enabled"]:
        record["stale"] = not np.array_equal(scalar16(stage / "effects/shading/alpha16.png"), alpha)
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
    weight = scalar16(_asset(project, f"revisions/{revision}/shadow_weight16.png"))
    dependency = scalar16(_asset(project, f"revisions/{revision}/effects/shading/alpha16.png"))
    support = scalar16(_asset(project, f"revisions/{revision}/effects/shading/support16.png"))
    protection = scalar16(_asset(project, f"revisions/{revision}/effects/shading/protection16.png"))
    if (
        any(value.shape != alpha.shape for value in (weight, dependency, support, protection))
        or type(record.get("enabled")) is not bool
        or type(record.get("stale")) is not bool
        or record.get("source_id") != manifest["master_id"]
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


def inherit_cleanup(
    project: Path,
    parent: str,
    stage: Path,
    master_id: str,
    alpha: np.ndarray | None = None,
    foreground: np.ndarray | None = None,
    rgb_protection: np.ndarray | None = None,
) -> dict[str, Any] | None:
    """Carry actual saved assets; refresh dependency status after an alpha operation."""
    manifest = read_revision(project, parent, master_id)
    record = manifest.get("color_cleanup")
    if record is None:
        return None
    record = dict(record)
    for name in EFFECT_FILES:
        if name in manifest["files"]:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_asset(project, f"revisions/{parent}/{name}").read_bytes())
    if alpha is not None and record["enabled"]:
        dependency = scalar16(stage / "effects/alpha16.png")
        record["stale"] = not np.array_equal(dependency, alpha)
        if foreground is not None and rgb_protection is not None:
            # The alpha operation already validated these explicit saved-value RGB locks
            # against its own write support. Layer selection must not override them.
            corrected = tifffile.imread(stage / "corrected_rgb16.tif")
            if np.any(corrected[rgb_protection] != foreground[rgb_protection]):
                corrected[rgb_protection] = foreground[rgb_protection]
                write_master(stage / "corrected_rgb16.tif", corrected)
    return record


def selected_foreground(
    project: Path,
    revision: str,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    effects_off: bool = False,
) -> np.ndarray:
    from .export import read_rgb16

    record = manifest.get("color_cleanup")
    if record:
        if (
            not isinstance(record, dict)
            or type(record.get("enabled")) is not bool
            or type(record.get("stale")) is not bool
            or record.get("source_id") != manifest["master_id"]
        ):
            raise ProjectError("Invalid saved cleanup identity/status")
        corrected = read_rgb16(_asset(project, f"revisions/{revision}/corrected_rgb16.tif"))
        dependency = scalar16(_asset(project, f"revisions/{revision}/effects/alpha16.png"))
        support = scalar16(_asset(project, f"revisions/{revision}/effects/support16.png"))
        with Image.open(_asset(project, f"revisions/{revision}/supports/protection.png")) as image:
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
    if not record or not record["enabled"] or effects_off or record["stale"]:
        return foreground
    return corrected


def saved_effect_lock_layers(project: Path, revision: str, master_id: str):
    """Prepared lock snapshots bind the inherited complete appearance, before new guides apply."""
    from .export import saved_layers
    from .repair import prepared_parent_layers

    manifest = read_revision(project, revision, master_id)
    if manifest["kind"] == "prepare":
        parent = prepared_parent_layers(project, revision, master_id)
        if manifest.get("color_cleanup") != parent.get("color_cleanup") or manifest["files"].get(
            "corrected_rgb16.tif"
        ) != parent["files"].get("corrected_rgb16.tif"):
            raise ProjectError("Prepared lock must retain its inherited corrected RGB")
        revision = parent["revision"]
    return saved_layers(project, revision, master_id)


def run_effects(
    project: Path, operation: dict[str, Any], request_file: Path | None
) -> dict[str, Any]:
    """Caller holds the canonical writer lock; preserve all prior complete revisions."""
    from .export import publish_artifacts, saved_layers
    from .operations import _input_file, _reject_pending_guidance, draft_digest
    from .review import write_review

    required = {
        "schema_version",
        "kind",
        "master_id",
        "base_revision",
        "inputs_digest",
        "scope_xyxy",
        "support_file",
        "candidate_comparison",
    }
    if (
        not required <= set(operation)
        or set(operation)
        - required
        - {"color_cleanup", "shading", "shading_protection_file", "opacity_only"}
        or type(operation["schema_version"]) is not int
        or operation["schema_version"] != 1
        or operation["kind"] != "effects"
        or type(operation["candidate_comparison"]) is not bool
    ):
        raise ProjectError("Invalid schema-1 effects request")
    operation = json.loads(_json_bytes(operation))
    request_bytes = request_file.read_bytes() if request_file else _json_bytes(operation)
    if json.loads(request_bytes) != operation:
        raise ProjectError("Stale effects request file")
    project = _root(project)
    state = read_project(project)
    _reject_pending_guidance(project)
    if (
        not state["development_approved"]
        or operation["master_id"] != state["master_id"]
        or operation["base_revision"] != state["working_revision"]
        or operation["inputs_digest"] != draft_digest(project)
    ):
        raise ProjectError("Stale effects master, base revision or draft identity")
    parent = state["working_revision"]
    cleanup_changed = "color_cleanup" in operation or "shading" not in operation
    settings = operation.get(
        "color_cleanup", tomllib.loads(_asset(project, "recipe.toml").read_text())["color_cleanup"]
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
        project, parent, state["master_id"], effects_off=True
    )
    source, _ = load_master(project, state["master_id"])
    height, width = alpha.shape
    scope = coordinates(operation["scope_xyxy"], width, height, box=True)
    support_path = _input_file(project, operation["support_file"])
    support_bytes = support_path.read_bytes()
    support = scalar16(support_path)
    if enabled:
        validate_support(support, alpha.shape, [0, 0, width, height], scope)
    elif support.shape != alpha.shape:
        raise ProjectError("Cleanup support must align with master even when disabled")
    snapshots = {
        name: _asset(project, name).read_bytes()
        for name in ("state.json", "source.json", "recipe.toml", "guides.json")
    }
    if (
        operation["inputs_digest"]
        != digest(snapshots["recipe.toml"] + b"\0" + snapshots["guides.json"])
        or json.loads(snapshots["state.json"]) != state
    ):
        raise ProjectError("Stale effects snapshot before processing")
    parent_bytes = _asset(project, f"revisions/{parent}/manifest.json").read_bytes()
    parent_guides = _asset(project, f"revisions/{parent}/guides.json").read_bytes()
    parent_recipe = tomllib.loads(_asset(project, f"revisions/{parent}/recipe.toml").read_text())
    current_recipe = tomllib.loads(snapshots["recipe.toml"].decode())
    if json.loads(snapshots["guides.json"]) != json.loads(parent_guides) or any(
        current_recipe[name] != parent_recipe[name]
        for name in current_recipe
        if name not in {"color_cleanup", "shading", "notes"}
    ):
        raise ProjectError(
            "Changed guidance/base recipe requires prepare and complete matte before effects"
        )
    with Image.open(_asset(project, f"revisions/{parent}/trimap.png")) as image:
        trimap = np.array(image)
    with Image.open(_asset(project, f"revisions/{parent}/supports/protection.png")) as image:
        protection = np.array(image) != 0
    guides = json.loads(_asset(project, f"revisions/{parent}/guides.json").read_bytes())
    # Explicit saved-value locks use the selected saved RGB, including partial-alpha colors.
    lock_values = foreground.copy()
    lock_dependencies = {}
    locked = np.zeros(alpha.shape, dtype=bool)
    for region in guides["regions"]:
        if region["role"] != "lock":
            continue
        revision = region["revision"]
        rgb, locked_alpha, _lock_manifest = saved_effect_lock_layers(
            project, revision, state["master_id"]
        )
        lock_dependencies[revision] = _asset(
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
    check_space(project, source.nbytes * 35 + 1024**2)
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
            and "corrected_rgb16.tif" in manifest["files"]
        ):
            prior = tifffile.imread(_asset(project, f"revisions/{parent}/corrected_rgb16.tif"))
            corrected[support == 0] = prior[support == 0]
            dependency = scalar16(_asset(project, f"revisions/{parent}/effects/alpha16.png"))
            dependency[support != 0] = alpha[support != 0]
            cumulative_support = scalar16(
                _asset(project, f"revisions/{parent}/effects/support16.png")
            )
            cumulative_support[support != 0] = support[support != 0]
        corrected[protection & (support != 0)] = lock_values[protection & (support != 0)]
        record = {
            "enabled": bool(enabled),
            "strength": settings["strength"],
            "stale": bool(enabled and not np.array_equal(dependency, alpha)),
            "source_id": state["master_id"],
            "algorithm": "nearest-confirmed-empty-inverse-mixture-v1",
            "scope_xyxy": scope,
            "support_sha256": digest(support_bytes),
            "alpha_sha256": manifest["files"]["base_alpha16.png"],
            "parent_manifest_sha256": digest(parent_bytes),
            "candidate_comparison": operation["candidate_comparison"],
        }
    else:
        record = manifest.get("color_cleanup")
        enabled = bool(record and record["enabled"])
        corrected = (
            tifffile.imread(_asset(project, f"revisions/{parent}/corrected_rgb16.tif"))
            if record
            else foreground.copy()
        )
        cumulative_support = support
        dependency = alpha
    if not cleanup_changed and current_recipe["color_cleanup"] != parent_recipe["color_cleanup"]:
        raise ProjectError("Changed cleanup recipe requires explicit cleanup operation")
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
    elif any(
        current_recipe["shading"].get(key) != parent_recipe["shading"].get(key)
        for key in current_recipe["shading"]
    ):
        raise ProjectError("Changed shading recipe requires explicit shading operation")
    revisions = _asset(project, "revisions")
    existing = [
        int(p.name[4:]) for p in revisions.iterdir() if re.fullmatch(r"rev-[0-9]{3,}", p.name)
    ]
    revision = f"rev-{max(existing, default=0) + 1:03d}"
    stage = Path(tempfile.mkdtemp(prefix=".effects-", dir=revisions))
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
        "trimap_approval.json",
    ):
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_asset(project, f"revisions/{parent}/{name}").read_bytes())
    for name in ("recipe.toml", "guides.json"):
        (stage / name).write_bytes(snapshots[name])
    (stage / "effects").mkdir(exist_ok=True)
    if cleanup_changed:
        assert record is not None
        Image.fromarray(cumulative_support).save(stage / "effects/support16.png")
        Image.fromarray(dependency).save(stage / "effects/alpha16.png")
        (stage / "effects/settings.json").write_bytes(_json_bytes(dict(record, settings=settings)))
        (stage / "effects/write_support16.png").write_bytes(support_bytes)
        write_master(stage / "corrected_rgb16.tif", corrected)
        if not np.array_equal(tifffile.imread(stage / "corrected_rgb16.tif"), corrected):
            raise ProjectError("Corrected RGB16 round trip failed")
    else:
        inherit_cleanup(project, parent, stage, state["master_id"])
    shading_record = inherit_shading(project, parent, stage, state["master_id"])
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
            weight = scalar16(stage / "shadow_weight16.png")
            shading_dependency = scalar16(stage / "effects/shading/alpha16.png")
            shading_support = scalar16(stage / "effects/shading/support16.png")
            saved_protection = scalar16(stage / "effects/shading/protection16.png")
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
            "source_id": state["master_id"],
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
        for name, value in (
            ("support16", shading_support),
            ("alpha16", shading_dependency),
            ("protection16", saved_protection),
        ):
            Image.fromarray(value).save(directory / (name + ".png"))
        Image.fromarray(weight).save(stage / "shadow_weight16.png")
        (directory / "settings.json").write_bytes(_json_bytes(shading_record))
        if not np.array_equal(scalar16(stage / "shadow_weight16.png"), weight):
            raise ProjectError("Shadow W16 round trip failed")
    (stage / "request.json").write_bytes(request_bytes)
    (stage / "inputs").mkdir()
    for name, data in snapshots.items():
        (stage / "inputs" / name).write_bytes(data)
    effect_records = {}
    if record is not None:
        effect_records["color_cleanup"] = record
    if shading_record is not None:
        effect_records["shading"] = shading_record
    stale = effects_stale(effect_records)
    appearance = corrected if enabled and not stale else foreground
    review_weight, opacity = (
        (scalar16(stage / "shadow_weight16.png"), shading_record["opacity"])
        if shading_record and shading_record["enabled"] and not stale
        else (None, 0.0)
    )
    review = write_review(
        stage / "review",
        source,
        appearance,
        alpha,
        master_id=state["master_id"],
        revision=revision,
        weight16=review_weight,
        opacity=opacity,
    )
    review.update(effect_records)
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
        "master_id": state["master_id"],
        "kind": "effects",
        "model": {"inference": "not invoked; saved base layers only"},
        "status": "review_needed",
        "final_acceptable": True,
        "inputs_digest": operation["inputs_digest"],
        **effect_records,
    }
    (stage / "result.json").write_bytes(_json_bytes(result))
    files = {
        str(p.relative_to(stage)): digest(p.read_bytes()) for p in stage.rglob("*") if p.is_file()
    }
    new_manifest = dict(
        manifest,
        **result,
        complete=True,
        files=files,
        parent_manifest_sha256=digest(parent_bytes),
        scope_xyxy=scope,
        draft_digest=operation["inputs_digest"],
        foreground_asset="corrected_rgb16.tif" if enabled else "foreground_rgb16.tif",
    )
    (stage / "manifest.json").write_bytes(_json_bytes(new_manifest))

    def recheck():
        for path, data in shading_inputs.items():
            if path.read_bytes() != data:
                raise ProjectError("Stale shading protection input")
        for name, data in snapshots.items():
            if _asset(project, name).read_bytes() != data:
                raise ProjectError(f"Stale effects input: {name}")
        if (
            support_path.read_bytes() != support_bytes
            or _asset(project, f"revisions/{parent}/manifest.json").read_bytes() != parent_bytes
            or request_file
            and request_file.read_bytes() != request_bytes
        ):
            raise ProjectError("Stale effects support/request/parent")
        read_revision(project, parent, state["master_id"])
        load_master(project, state["master_id"])
        for saved_revision, data in lock_dependencies.items():
            read_revision(project, saved_revision, state["master_id"])
            if _asset(project, f"revisions/{saved_revision}/manifest.json").read_bytes() != data:
                raise ProjectError("Stale cleanup saved RGB lock")

    recheck()
    destination = revisions / revision
    publish_artifacts(stage, destination)
    read_revision(project, revision, state["master_id"])
    state.update(working_revision=revision, status="review_needed")
    _atomic_json(_asset(project, "state.json"), state, validate_before_replace=recheck)
    return dict(
        result,
        manifest_file=str(destination / "manifest.json"),
        review_manifest_file=str(destination / "review/manifest.json"),
    )
