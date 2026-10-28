"""Bounded, native reduction geometry shared by optional fade effects."""

import json
from pathlib import Path
from typing import Any

import numpy as np

from .exposure import rasterize_effect_area
from .guidance import validate_guides
from .project import ProjectError, digest
from .repair import scalar16

REDUCTION_ALGORITHM = "native-support-max-reduction-v1"


def validate_fade_reduction(area: Any, developed_id: str, width: int, height: int) -> None:
    """Bound all authored geometry before allocating any native raster."""
    if (
        any(type(value) is not int or value <= 0 for value in (width, height))
        or not isinstance(area, dict)
        or set(area) != {"schema_version", "regions"}
        or type(area["schema_version"]) is not int
        or area["schema_version"] != 1
        or not isinstance(area["regions"], list)
        or len(area["regions"]) > 128
    ):
        raise ProjectError("Invalid fade reduction document or region limit (maximum 128)")
    shapes = []
    point_count = 0
    for region in area["regions"]:
        if (
            not isinstance(region, dict)
            or set(region) != {"shape", "amount"}
            or type(region["amount"]) not in {int, float}
            or not 0 <= region["amount"] <= 1
            or not np.isfinite(region["amount"])
            or not isinstance(region["shape"], dict)
            or region["shape"].get("shape") not in ("stroke", "rectangle")
            or region["shape"].get("role") != "support"
        ):
            raise ProjectError("Invalid fade reduction shape or amount")
        shape = region["shape"]
        if shape["shape"] == "stroke":
            points = shape.get("points")
            if not isinstance(points, list):
                raise ProjectError("Fade reduction stroke requires native points")
            point_count += len(points)
            if point_count > 8192:
                raise ProjectError("Fade reduction exceeds 8192 total stroke points")
        shapes.append(shape)
    try:
        validate_guides(
            {
                "schema_version": 2,
                "developed_id": developed_id,
                "width": width,
                "height": height,
                "regions": shapes,
            },
            developed_id,
            width,
            height,
        )
    except (ValueError, TypeError) as error:
        raise ProjectError(f"Invalid fade reduction geometry: {error}") from error


def rasterize_fade_reduction(
    area: dict[str, Any], developed_id: str, width: int, height: int
) -> np.ndarray:
    """Rasterize the maximum authored reduction with one final quantization."""
    validate_fade_reduction(area, developed_id, width, height)
    maximum = np.zeros((height, width), np.float64)
    for region in area["regions"]:
        support, _ = rasterize_effect_area(
            {"regions": [region["shape"]], "protection": []}, developed_id, width, height
        )
        # Support is the established quantized inward feather. Keep only this
        # shape's scratch raster; do not quantize or accumulate overlaps here.
        np.maximum(maximum, region["amount"] * support, out=maximum)
    return np.rint(maximum).astype(np.uint16)


def read_fade_reduction(
    project: Path, directory: Path, manifest: dict[str, Any], effect: str, alpha: np.ndarray
) -> np.ndarray | None:
    """Read bound operands; the project semantic cache owns geometry replay."""
    from .assets import revision_asset

    targets = {"spatial_fade": ("spatial-fade", 1), "shadow_fade": ("shadow-fade", 2)}
    if effect not in targets:
        raise ProjectError("Unknown fade reduction target")
    folder, legacy_version = targets[effect]
    record = manifest.get(effect)
    if record is None or record["schema_version"] == legacy_version:
        return None
    if (
        type(record.get("schema_version")) is not int
        or record["schema_version"] != legacy_version + 1
        or record.get("reduction_algorithm") != REDUCTION_ALGORITHM
    ):
        raise ProjectError("Invalid saved fade reduction algorithm")
    try:
        raster = revision_asset(project, directory, manifest, f"effects/{folder}/reduction16.png")
        document = revision_asset(project, directory, manifest, f"effects/{folder}/reduction.json")
        document_bytes = document.read_bytes()
        if digest(raster.read_bytes()) != record.get("reduction_sha256") or digest(
            document_bytes
        ) != record.get("reduction_area_sha256"):
            raise ProjectError("Saved fade reduction dependency hash mismatch")
        reduction = scalar16(raster)
        height, width = alpha.shape
        validate_fade_reduction(json.loads(document_bytes), manifest["developed_id"], width, height)
        if reduction.shape != alpha.shape:
            raise ProjectError("Saved fade reduction dimensions differ from alpha")
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectError("Missing or invalid saved fade reduction operands") from error
    return reduction
