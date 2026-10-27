"""Bounded, self-contained appearance settings; importing never writes a project."""

import base64
import binascii
import io
import json
import math
import re
import struct
import unicodedata
import zlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngImageFile

from .assets import saved_asset
from .background import normalized_background
from .effects import effects_stale, validate_cleanup, validate_shading
from .export import render_saved_result, validated_layer_inputs
from .exposure import validate_exposure
from .project import ProjectError, _json_bytes, _root, digest, read_project, read_revision
from .series_framing import nonzero_alpha_bounds
from .shadow_fade import validate_shadow_fade
from .spatial_fade import validate_spatial_transition_width

JSON_LIMIT = 1572864
REFERENCE_LIMIT = 1048576
SECTION_FIELDS = {
    "shadow_fade": {"amount", "preserve_highlights"},
    "local_exposure": {"ev"},
    "color_cleanup": {"strength"},
    "background": {"color_srgb", "variation"},
    "shading": {"width_subject_fraction", "direction_degrees", "opacity"},
    "spatial_fade": {"transition_subject_fraction", "amount", "preserve_highlights"},
}


def _finite_number(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate appearance recipe JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ProjectError("Appearance recipe numbers must be finite")


def _check_json_depth(text: str) -> None:
    """Bound nesting before the JSON decoder allocates its containers."""
    depth = 0
    quoted = escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > 8:
                raise ProjectError("Appearance recipe nesting exceeds 8 levels")
        elif character in "]}":
            depth -= 1


def _reference_png(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"mime", "width", "height", "png_base64"}
        or value["mime"] != "image/png"
        or any(
            type(value[key]) is not int or not 1 <= value[key] <= 512 for key in ("width", "height")
        )
        or value["width"] * value["height"] > 262144
        or not isinstance(value["png_base64"], str)
        or len(value["png_base64"]) > 4 * ((REFERENCE_LIMIT + 2) // 3)
    ):
        raise ProjectError("Reference requires bounded RGB8 PNG dimensions and data")
    try:
        raw = base64.b64decode(value["png_base64"], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ProjectError("Invalid reference PNG base64") from error
    if len(raw) > REFERENCE_LIMIT or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ProjectError("Reference PNG exceeds 1048576 bytes or has an invalid signature")

    # Validate every chunk CRC, but never decompress untrusted text/ICC/EXIF metadata.
    # Only the pixel stream reaches Pillow; freshly encoded pixels carry no metadata.
    chunks: list[bytes] = [raw[:8]]
    offset = 8
    saw_header = saw_pixels = ended_pixels = saw_end = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ProjectError("Truncated reference PNG chunk")
        length = struct.unpack_from(">I", raw, offset)[0]
        end = offset + 12 + length
        if end > len(raw):
            raise ProjectError("Truncated reference PNG data")
        kind = raw[offset + 4 : offset + 8]
        payload = raw[offset + 8 : end - 4]
        crc = struct.unpack_from(">I", raw, end - 4)[0]
        if (
            len(kind) != 4
            or any(not (65 <= item <= 90 or 97 <= item <= 122) for item in kind)
            or zlib.crc32(kind + payload) != crc
        ):
            raise ProjectError("Invalid reference PNG chunk or checksum")
        if not saw_header and kind != b"IHDR":
            raise ProjectError("Reference PNG must start with IHDR")
        if kind == b"IHDR":
            if saw_header or length != 13:
                raise ProjectError("Invalid reference PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (
                (width, height) != (value["width"], value["height"])
                or depth != 8
                or color != 2
                or compression != 0
                or filtering != 0
                or interlace not in (0, 1)
            ):
                raise ProjectError("Reference must be RGB8 PNG with matching bounded dimensions")
            saw_header = True
            chunks.append(raw[offset:end])
        elif kind in {b"acTL", b"fcTL", b"fdAT", b"tRNS"}:
            raise ProjectError("Reference PNG must be opaque and contain one frame")
        elif kind == b"IDAT":
            if ended_pixels:
                raise ProjectError("Reference PNG pixel chunks must be contiguous")
            saw_pixels = True
            chunks.append(raw[offset:end])
        elif kind == b"IEND":
            if length or not saw_pixels or end != len(raw):
                raise ProjectError("Invalid reference PNG ending")
            saw_end = True
            chunks.append(raw[offset:end])
        elif not kind[0] & 32 and kind != b"PLTE":
            raise ProjectError("Unsupported critical reference PNG chunk")
        if saw_pixels and kind not in {b"IDAT", b"IEND"}:
            ended_pixels = True
        offset = end
    if not saw_end:
        raise ProjectError("Reference PNG is incomplete")
    safe_png = b"".join(chunks)
    try:
        with Image.open(io.BytesIO(safe_png), formats=["PNG"]) as opened:
            opened.verify()
        with Image.open(io.BytesIO(safe_png), formats=["PNG"]) as opened:
            if not isinstance(opened, PngImageFile) or opened.mode != "RGB" or opened.n_frames != 1:
                raise ProjectError("Reference PNG must contain one RGB8 frame")
            opened.load()
            clean = Image.frombytes("RGB", opened.size, opened.tobytes())
        with clean:
            output = io.BytesIO()
            clean.save(output, format="PNG")
    except (OSError, SyntaxError, ValueError) as error:
        raise ProjectError(f"Invalid reference PNG pixels: {error}") from error
    encoded = output.getvalue()
    if len(encoded) > REFERENCE_LIMIT:
        raise ProjectError("Sanitized reference PNG exceeds 1048576 bytes")
    return {
        "mime": "image/png",
        "width": value["width"],
        "height": value["height"],
        "png_base64": base64.b64encode(encoded).decode("ascii"),
    }


def _normalized_recipe(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "kind", "name", "sections", "reference"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["kind"] != "appearance-recipe"
    ):
        raise ProjectError("Unsupported appearance recipe schema, kind or root fields")
    name = value["name"]
    if not isinstance(name, str) or any(unicodedata.category(item) == "Cc" for item in name):
        raise ProjectError("Appearance recipe name must be text without control characters")
    try:
        name.encode("utf-8")
    except UnicodeError as error:
        raise ProjectError("Appearance recipe name must be valid Unicode") from error
    name = name.strip()
    if not 1 <= len(name) <= 80:
        raise ProjectError("Appearance recipe name must contain 1–80 trimmed Unicode characters")
    sections = value["sections"]
    if (
        not isinstance(sections, dict)
        or not sections
        or set(sections) - SECTION_FIELDS.keys()
        or {"shading", "spatial_fade"} <= sections.keys()
    ):
        raise ProjectError("Invalid or conflicting appearance recipe sections")
    normalized: dict[str, Any] = {}
    for section, settings in sections.items():
        if not isinstance(settings, dict) or set(settings) != SECTION_FIELDS[section]:
            raise ProjectError(f"Invalid appearance recipe {section} fields")
        if any(not _finite_number(item) for key, item in settings.items() if key != "color_srgb"):
            raise ProjectError(f"Appearance recipe {section} requires finite nonboolean numbers")
        if section == "background":
            normalized[section] = normalized_background(settings)
            continue
        if section == "shadow_fade":
            validate_shadow_fade({"enabled": False, **settings})
        elif section == "local_exposure":
            validate_exposure({"enabled": False, **settings})
        elif section == "color_cleanup":
            validate_cleanup({"enabled": False, **settings})
        elif section == "shading":
            validate_shading(
                {
                    "enabled": False,
                    "width_px": settings["width_subject_fraction"],
                    "direction_degrees": settings["direction_degrees"],
                    "opacity": settings["opacity"],
                }
            )
        else:
            if settings["transition_subject_fraction"] <= 0:
                raise ProjectError("Spatial transition fraction must be strictly positive")
            validate_shadow_fade(
                {
                    "enabled": False,
                    "amount": settings["amount"],
                    "preserve_highlights": settings["preserve_highlights"],
                }
            )
        normalized[section] = dict(settings)
    return {
        "schema_version": 1,
        "kind": "appearance-recipe",
        "name": name,
        "sections": normalized,
        "reference": _reference_png(value["reference"]),
    }


def parse_appearance_recipe(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or len(raw) > JSON_LIMIT:
        raise ProjectError("Appearance recipe exceeds 1572864 UTF-8 bytes")
    try:
        text = raw.decode("utf-8")
        _check_json_depth(text)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ProjectError("Appearance recipe must be bounded UTF-8 JSON") from error
    return _normalized_recipe(value)


def portable_appearance_recipe(value: dict[str, Any]) -> bytes:
    raw = _json_bytes(_normalized_recipe(value))
    if len(raw) > JSON_LIMIT:
        raise ProjectError("Appearance recipe exceeds 1572864 UTF-8 bytes")
    return raw


def _canonicalize_portable_interval(
    value: float, lower: float, upper: float, error_budget: float
) -> float:
    if (
        not all(_finite_number(item) for item in (value, lower, upper, error_budget))
        or error_budget < 0
    ):
        raise ProjectError("Portable conversion must have finite values and error budget")
    if value < lower and lower - value <= error_budget:
        return lower
    if value > upper and value - upper <= error_budget:
        return upper
    if not lower <= value <= upper:
        raise ProjectError("Converted width exceeds the target's native limits")
    return value


def appearance_recipe_form_values(
    value: dict[str, Any],
    target_subject_bounds: tuple[int, int, int, int] | None,
    target_dimensions_wh: tuple[int, int],
) -> dict[str, Any]:
    recipe = _normalized_recipe(value)
    if len(target_dimensions_wh) != 2 or any(
        type(item) is not int or item <= 0 for item in target_dimensions_wh
    ):
        raise ProjectError("Appearance conversion requires positive native dimensions")
    native_width, native_height = target_dimensions_wh
    subject_size = None
    if target_subject_bounds is not None:
        if len(target_subject_bounds) != 4 or any(
            type(item) is not int for item in target_subject_bounds
        ):
            raise ProjectError("Invalid target subject bounds")
        x0, y0, x1, y1 = target_subject_bounds
        if not (0 <= x0 < x1 <= native_width and 0 <= y0 < y1 <= native_height):
            raise ProjectError("Target subject bounds exceed native dimensions")
        subject_size = max(x1 - x0, y1 - y0)
    sections: dict[str, Any] = {}
    unavailable: dict[str, str] = {}
    for section, settings in recipe["sections"].items():
        if section not in {"shading", "spatial_fade"}:
            sections[section] = dict(settings)
            continue
        try:
            if subject_size is None:
                raise ProjectError("A saved matte with nonzero alpha is required for widths")
            shading = section == "shading"
            fraction_key = "width_subject_fraction" if shading else "transition_subject_fraction"
            product = settings[fraction_key] * subject_size
            if not _finite_number(product) or (shading and product <= 0):
                raise ProjectError("Converted width must be finite and strictly positive")
            lower = 0.0 if shading else 0.5
            upper = float(max(target_dimensions_wh) * (1 if shading else 2))
            endpoint = lower if product < lower else upper
            width = _canonicalize_portable_interval(
                product, lower, upper, 4 * (math.ulp(product) + math.ulp(endpoint))
            )
            if shading:
                converted = {
                    "width_px": width,
                    "direction_degrees": settings["direction_degrees"],
                    "opacity": settings["opacity"],
                }
                validate_shading({"enabled": False, **converted})
            else:
                validate_spatial_transition_width(width, native_width, native_height)
                converted = {
                    "transition_width": width,
                    "amount": settings["amount"],
                    "preserve_highlights": settings["preserve_highlights"],
                }
            sections[section] = converted
        except (ValueError, OverflowError) as error:
            unavailable[section] = str(error)
    return {"sections": sections, "unavailable": unavailable}


def appearance_recipe_from_revision(
    project: Path,
    revision: str,
    expected_manifest_sha256: str,
    name: str,
    sections: list[str],
    reference_shape_id: str | None,
    include_reference: bool,
) -> bytes:
    """Read exactly the selected complete revision, never current draft settings."""
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"rev-[0-9]{3,}", revision) is None
        or not isinstance(expected_manifest_sha256, str)
        or re.fullmatch(r"[a-f0-9]{64}", expected_manifest_sha256) is None
        or not isinstance(sections, list)
        or not sections
        or any(
            not isinstance(section, str) or section not in SECTION_FIELDS for section in sections
        )
        or len(set(sections)) != len(sections)
        or {"shading", "spatial_fade"} <= set(sections)
        or type(include_reference) is not bool
        or ("spatial_fade" not in sections and reference_shape_id is not None)
        or ("spatial_fade" in sections and not isinstance(reference_shape_id, str))
    ):
        raise ProjectError("Invalid saved appearance recipe selection or identity")
    project = _root(project)
    manifest_name = f"revisions/{revision}/manifest.json"
    captured = {
        key: saved_asset(project, key).read_bytes()
        for key in ("state.json", "source.json", manifest_name)
    }
    if digest(captured[manifest_name]) != expected_manifest_sha256:
        raise ProjectError("Stale appearance recipe revision manifest")
    state = read_project(project, validate_drafts=False)
    _, alpha, manifest = validated_layer_inputs(project, revision, state["developed_id"])
    if _json_bytes(json.loads(captured[manifest_name])) != _json_bytes(manifest) or effects_stale(
        manifest
    ):
        raise ProjectError("Stale selected appearance recipe source or effects")
    bounds = nonzero_alpha_bounds(alpha)
    subject_size = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) if bounds else None
    selected: dict[str, Any] = {}
    for section in sections:
        record = manifest.get(section)
        settings = (
            (record if section == "color_cleanup" else record.get("settings"))
            if isinstance(record, dict)
            else None
        )
        if not isinstance(settings, dict):
            raise ProjectError(f"Selected saved revision has no {section} settings")
        if section in {"shading", "spatial_fade"} and subject_size is None:
            raise ProjectError("Saving width settings requires nonzero saved alpha")
        if section == "shading":
            if "width_px" not in settings:
                raise ProjectError("Selected saved shading has no authored width/direction")
            selected[section] = {
                "width_subject_fraction": settings["width_px"] / subject_size,
                "direction_degrees": settings["direction_degrees"],
                "opacity": settings["opacity"],
            }
        elif section == "spatial_fade":
            shape = (
                settings["oval"]
                if reference_shape_id == "oval"
                else next(
                    (arc for arc in settings["arcs"] if arc["id"] == reference_shape_id), None
                )
            )
            if shape is None:
                raise ProjectError("Choose an actual saved oval or arc for spatial defaults")
            selected[section] = {
                "transition_subject_fraction": shape["transition_width"] / subject_size,
                "amount": shape["amount"],
                "preserve_highlights": settings["preserve_highlights"],
            }
        else:
            selected[section] = {key: settings[key] for key in SECTION_FIELDS[section]}
    recipe = _normalized_recipe(
        {
            "schema_version": 1,
            "kind": "appearance-recipe",
            "name": name,
            "sections": selected,
            "reference": None,
        }
    )
    if include_reference:
        pixels = render_saved_result(project, revision, state["developed_id"])
        with Image.fromarray(np.rint(pixels.astype(np.float64) / 257).astype(np.uint8)) as image:
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            recipe["reference"] = {
                "mime": "image/png",
                "width": image.width,
                "height": image.height,
                "png_base64": base64.b64encode(stream.getvalue()).decode("ascii"),
            }
    result = portable_appearance_recipe(recipe)
    # Existing canonical readers recheck immutable operands as well as captured raw bindings.
    read_project(project, validate_drafts=False)
    read_revision(project, revision, state["developed_id"])
    if any(saved_asset(project, key).read_bytes() != raw for key, raw in captured.items()):
        raise ProjectError("Stale appearance recipe inputs changed during creation")
    return result
