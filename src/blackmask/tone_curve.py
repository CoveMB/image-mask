"""A registered, luminance-only adjustment of the selected RGB16 foreground."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .assets import inherit_revision_files, revision_asset, stage_asset
from .exposure import linear_to_rgb16, rasterize_effect_area, srgb_to_linear
from .guidance import coordinates
from .project import ProjectError, _json_bytes, digest, read_revision
from .repair import scalar16

TONE_CURVE_ALGORITHM = "linear-srgb-local-tone-curve-v1"
TONE_CURVE_PREFIX = "effects/tone-curve/"
TONE_CURVE_RASTERS = {
    "support16.png": "support_sha256",
    "protection16.png": "protection_sha256",
    "alpha16.png": "alpha_sha256",
}


def validate_local_tone_curve(settings: object) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != {"enabled", "points"}
        or type(settings["enabled"]) is not bool
        or not isinstance(settings["points"], list)
        or len(settings["points"]) > 6
    ):
        raise ProjectError("Local tone curve requires enabled and up to six interior points")
    previous_input = previous_output = 0
    for point in settings["points"]:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(type(value) is not int or not 1 <= value <= 9999 for value in point)
            or point[0] <= previous_input
            or point[1] <= previous_output
        ):
            raise ProjectError("Local tone curve coordinates must strictly increase in 1..9999")
        previous_input, previous_output = point


def apply_local_tone_curve(
    foreground: np.ndarray,
    alpha: np.ndarray,
    support: np.ndarray,
    protection: np.ndarray,
    settings: dict[str, Any],
) -> np.ndarray:
    """Apply a feathered, gamut-capped common gain to eligible straight RGB."""
    validate_local_tone_curve(settings)
    if (
        not all(isinstance(array, np.ndarray) for array in (foreground, alpha, support, protection))
        or foreground.dtype != np.uint16
        or foreground.ndim != 3
        or foreground.shape[2] != 3
        or alpha.dtype != np.uint16
        or alpha.shape != foreground.shape[:2]
        or support.dtype != np.uint16
        or support.shape != alpha.shape
        or protection.dtype != np.bool_
        or protection.shape != alpha.shape
    ):
        raise ProjectError(
            "Local tone curve requires aligned RGB16/A16/support16 and boolean protection"
        )
    result = foreground.copy()
    if not settings["enabled"]:
        return result
    input_knots, output_knots = np.array([[0, 0], *settings["points"], [10000, 10000]]).T
    deltas = (output_knots - input_knots) / 10000
    if not deltas.any():
        return result
    positions = input_knots / 10000
    luminance_weights = np.array([0.2126, 0.7152, 0.0722])
    rows_per_strip = max(1, 262144 // max(1, alpha.shape[1]))
    for top in range(0, alpha.shape[0], rows_per_strip):
        rows = slice(top, top + rows_per_strip)
        coverage = support[rows]
        eligible = (alpha[rows] != 0) & (coverage != 0) & ~protection[rows]
        vertical, horizontal = np.nonzero(eligible)
        linear = srgb_to_linear(foreground[rows][eligible].astype(np.float64) / 65535)
        luminance = linear @ luminance_weights
        delta = np.interp(luminance, positions, deltas)
        changed = (luminance > 0) & (delta != 0)
        linear = linear[changed]
        luminance = luminance[changed]
        gain = np.minimum((luminance + delta[changed]) / luminance, 1 / linear.max(axis=1))
        varies = gain != 1
        indices = (vertical[changed][varies], horizontal[changed][varies])
        weighted_gain = 1 + (coverage[indices] / 65535) * (gain[varies] - 1)
        result[rows][indices] = linear_to_rgb16(linear[varies] * weighted_gain[:, None])
    return result


def read_local_tone_curve(
    project: Path,
    directory: Path,
    manifest: dict[str, Any],
    alpha: np.ndarray,
    *,
    verify_geometry: bool = True,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None:
    """Validate the saved curve and its registered operands, including when disabled."""
    if "local_tone_curve" not in manifest:
        return None
    record = manifest["local_tone_curve"]
    keys = {
        "schema_version",
        "enabled",
        "settings",
        "stale",
        "developed_id",
        "algorithm",
        "scope_xyxy",
        "candidate_comparison",
        "area_sha256",
        *TONE_CURVE_RASTERS.values(),
    }
    if (
        not isinstance(record, dict)
        or set(record) != keys
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 2
        or any(
            type(record[name]) is not bool for name in ("enabled", "stale", "candidate_comparison")
        )
        or record["developed_id"] != manifest["developed_id"]
        or record["algorithm"] != TONE_CURVE_ALGORITHM
    ):
        raise ProjectError("Invalid saved Local tone curve identity/schema/status")
    validate_local_tone_curve(record["settings"])
    height, width = alpha.shape
    scope = coordinates(record["scope_xyxy"], width, height, box=True)
    if record["enabled"] != record["settings"]["enabled"]:
        raise ProjectError("Inconsistent saved Local tone curve settings")

    def operand(name: str) -> Path:
        return revision_asset(project, directory, manifest, TONE_CURVE_PREFIX + name)

    try:
        settings_bytes = _json_bytes(json.loads(operand("settings.json").read_bytes()))
    except (OSError, TypeError, ValueError) as error:
        raise ProjectError("Invalid saved Local tone curve settings record") from error
    if settings_bytes != _json_bytes(record):
        raise ProjectError("Inconsistent saved Local tone curve settings record")
    arrays = []
    for name, hash_key in TONE_CURVE_RASTERS.items():
        path = operand(name)
        if digest(path.read_bytes()) != record[hash_key]:
            raise ProjectError("Saved Local tone curve operand hash mismatch")
        values = scalar16(path)
        if values.shape != alpha.shape:
            raise ProjectError("Saved Local tone curve dimensions differ from master")
        arrays.append(values)
    support, protection16, dependency = arrays
    if np.any((protection16 != 0) & (protection16 != 65535)) or record["stale"] != (
        record["enabled"] and not np.array_equal(dependency, alpha)
    ):
        raise ProjectError("Invalid saved Local tone curve protection/dependency status")
    protection = protection16 != 0
    check_tone_curve_scope(support, scope)
    if record["area_sha256"] is not None:
        authored = operand("area.json").read_bytes()
        if digest(authored) != record["area_sha256"]:
            raise ProjectError("Saved Local tone curve authored area hash mismatch")
        if verify_geometry:
            try:
                area = json.loads(authored)
            except ValueError as error:
                raise ProjectError("Invalid saved Local tone curve authored area") from error
            authored_support, authored_protection = rasterize_effect_area(
                area, manifest["developed_id"], width, height
            )
            if not np.array_equal(authored_support, support) or np.any(
                authored_protection & ~protection
            ):
                raise ProjectError("Saved Local tone curve area differs from registered operands")
    elif (directory / TONE_CURVE_PREFIX / "area.json").exists():
        raise ProjectError("Unbound saved Local tone curve authored area")
    return support, protection, record


def check_tone_curve_scope(support: np.ndarray, scope: list[int]) -> None:
    x0, y0, x1, y1 = scope
    if any(
        section.any()
        for section in (support[:y0], support[y1:], support[y0:y1, :x0], support[y0:y1, x1:])
    ):
        raise ProjectError("Local tone curve scope must contain previous and replacement support")


def selected_local_tone_curve(
    project: Path,
    directory: Path,
    foreground: np.ndarray,
    alpha: np.ndarray,
    manifest: dict[str, Any],
    *,
    tone_curve_off: bool = False,
    verify_geometry: bool = True,
) -> np.ndarray:
    saved = read_local_tone_curve(
        project, directory, manifest, alpha, verify_geometry=verify_geometry
    )
    if saved is None:
        return foreground
    support, protection, record = saved
    if tone_curve_off or not record["enabled"] or record["stale"]:
        return foreground
    return apply_local_tone_curve(foreground, alpha, support, protection, record["settings"])


def inherit_local_tone_curve(
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
    if "local_tone_curve" not in manifest:
        return None
    previous = manifest["local_tone_curve"]
    record = dict(previous)
    names = [*TONE_CURVE_RASTERS, "settings.json"]
    if record["area_sha256"] is not None:
        names.append("area.json")
    inherit_revision_files(
        project, parent, stage, assets, [TONE_CURVE_PREFIX + name for name in names]
    )
    if alpha is not None and record["enabled"]:
        dependency = scalar16(
            stage_asset(project, stage, assets, TONE_CURVE_PREFIX + "alpha16.png")
        )
        record["stale"] = not np.array_equal(dependency, alpha)
    if rgb_protection is not None and rgb_protection.any():
        name = TONE_CURVE_PREFIX + "protection16.png"
        protection = scalar16(stage_asset(project, stage, assets, name))
        if np.any(protection[rgb_protection] == 0):
            protection[rgb_protection] = 65535
            Image.fromarray(protection).save(stage / name)
            record["protection_sha256"] = digest((stage / name).read_bytes())
    if record != previous:
        (stage / TONE_CURVE_PREFIX / "settings.json").write_bytes(_json_bytes(record))
    return record
