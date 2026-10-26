"""Decode untouched capture bytes into canonical oriented RGB16 sRGB samples."""

import hashlib
import io
import struct
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
import numpy.typing as npt
import rawpy
import tifffile
from PIL import Image, ImageCms, JpegImagePlugin, UnidentifiedImageError

from .dng_white_balance import dng_as_shot_white_balance

RGB16 = npt.NDArray[np.uint16]


class IngestError(ValueError):
    """Input needs correction or an explicit development decision."""


def normalize_profile(profile: bytes) -> bytes:
    # ICC header creation time and optional profile ID do not change the transform.
    if len(profile) < 128:
        return profile
    result = bytearray(profile)
    result[24:36] = struct.pack(">6H", 2000, 1, 1, 0, 0, 0)
    result[84:100] = bytes(16)
    return bytes(result)


@lru_cache(maxsize=1)
def srgb_profile() -> bytes:
    return normalize_profile(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())


def _profile_decision(profile: bytes | None, assumption: bool, declared: bool = False) -> str:
    if profile:
        if normalize_profile(profile) == srgb_profile():
            return "embedded_srgb"
        raise IngestError("Unsupported high-depth profile: export trusted uncompressed sRGB TIFF")
    if declared:
        return "declared_srgb"
    if assumption:
        return "explicit_srgb_assumption"
    raise IngestError("Missing color profile: explicitly assume sRGB or supply corrected input")


def _orient(pixels: RGB16, orientation: int) -> RGB16:
    if orientation not in range(1, 9):
        raise IngestError("Invalid EXIF orientation")
    if orientation == 2:
        pixels = pixels[:, ::-1]
    elif orientation == 3:
        pixels = pixels[::-1, ::-1]
    elif orientation == 4:
        pixels = pixels[::-1]
    elif orientation == 5:
        pixels = pixels.transpose(1, 0, 2)
    elif orientation == 6:
        pixels = np.rot90(pixels, -1)
    elif orientation == 7:
        pixels = pixels.transpose(1, 0, 2)[::-1, ::-1]
    elif orientation == 8:
        pixels = np.rot90(pixels, 1)
    return np.ascontiguousarray(pixels, dtype=np.uint16)


def _gain_map_property(image: Image.Image, name: str) -> list[str | None]:
    """Read only the declared gain-map namespace, without accepting XML entities."""
    # Pillow keeps only the last standard packet in info["xmp"]. Do not let it
    # hide an earlier declaration or an unsupported extended packet.
    packets = [
        payload
        for marker, payload in getattr(image, "applist", [])
        if marker == "APP1"
        and payload.startswith(
            (b"http://ns.adobe.com/xap/1.0/\x00", b"http://ns.adobe.com/xmp/extension/\x00")
        )
    ]
    if len(packets) != 1 or not packets[0].startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
        raise IngestError("Gain-map JPEG requires one standard XMP packet per image")
    packet = image.info.get("xmp", b"")
    if (
        not isinstance(packet, bytes)
        or len(packet) > 65533
        or b"\x00" in packet
        or b"<!DOCTYPE" in packet.upper()
        or b"<!ENTITY" in packet.upper()
    ):
        raise IngestError("Invalid gain-map JPEG XMP metadata")
    try:
        document = ElementTree.fromstring(packet)
    except ElementTree.ParseError as error:
        raise IngestError("Invalid gain-map JPEG XMP metadata") from error
    key = "{http://ns.adobe.com/hdr-gain-map/1.0/}" + name
    return [node.attrib[key] for node in document.iter() if key in node.attrib] + [
        node.text for node in document.iter(key)
    ]


def _sdr_primary_selection(
    data: bytes, image: JpegImagePlugin.JpegImageFile, multi_picture: dict[int, Any]
) -> dict[str, Any]:
    """Admit only the first SDR image of a bounded, recognized two-image gain map."""
    entries = multi_picture[0xB002]
    if multi_picture[0xB001] != 2 or len(entries) != 2:
        raise IngestError("SDR primary requires a two-image gain-map JPEG")
    primary, auxiliary = entries
    primary_size = primary["Size"]
    offset = image.info["mpoffset"] + auxiliary["DataOffset"]
    end = offset + auxiliary["Size"]
    if (
        primary["DataOffset"] != 0
        or primary["Attribute"]["MPType"] != "Baseline MP Primary Image"
        or auxiliary["Attribute"]["MPType"] != "Undefined"
        or not 2 < primary_size <= offset < end <= len(data)
        or data[primary_size - 2 : primary_size] != b"\xff\xd9"
        or data[offset : offset + 2] != b"\xff\xd8"
        or data[end - 2 : end] != b"\xff\xd9"
        or _gain_map_property(image, "Version") != ["1.0"]
    ):
        raise IngestError("Invalid SDR-primary gain-map JPEG layout or version")
    if _gain_map_property(image, "BaseRenditionIsHDR") not in ([], ["False"]):
        raise IngestError("Gain-map JPEG must explicitly identify an SDR base")
    # Only inspect the auxiliary header: its pixels never become a master or a mask.
    with Image.open(io.BytesIO(data[offset:end])) as gain_map:
        if (
            gain_map.format != "JPEG"
            or getattr(gain_map, "n_frames", 1) != 1
            or _gain_map_property(gain_map, "Version") != ["1.0"]
            or _gain_map_property(gain_map, "BaseRenditionIsHDR") != ["False"]
        ):
            raise IngestError("Gain-map JPEG must explicitly identify an SDR base")
    return {
        "selected_image": 0,
        "image_count": 2,
        "base_rendition": "SDR",
        "hdr_gain_map_applied": False,
    }


def _decode_raw(data: bytes, settings: dict[str, Any]) -> tuple[RGB16, dict[str, Any]]:
    try:
        opened_raw = rawpy.imread(io.BytesIO(data))
    except rawpy.LibRawFileUnsupportedError:
        # Only failure to recognize RAW permits ordinary TIFF validation.
        raise
    except rawpy.LibRawError as error:
        raise IngestError(f"Unsupported or invalid RAW capture: {error}") from error
    try:
        with opened_raw as raw:
            coefficients = np.asarray(raw.camera_whitebalance, dtype=np.float64)
            credible = (
                coefficients.shape == (4,)
                and np.isfinite(coefficients).all()
                and (coefficients[:3] > 0).all()
                and coefficients[3] >= 0
            )
            white_balance = settings.get("white_balance", "camera")
            as_shot_white_balance = None
            if white_balance == "camera" and not credible:
                try:
                    as_shot_white_balance = dng_as_shot_white_balance(data)
                except ValueError as error:
                    raise IngestError(
                        f"{error}; explicitly select daylight preview or supply a trusted developed TIFF"
                    ) from error
                if as_shot_white_balance is None:
                    raise IngestError(
                        "Camera white balance multipliers unavailable from the RAW reader: "
                        "explicitly select daylight preview or export a trusted developed TIFF"
                    )
                if raw.num_colors != 3 or raw.color_desc != b"RGBG":
                    raise IngestError("DNG white balance requires a three-channel RGBG RAW layout")
            parameters: dict[str, Any] = {
                "demosaic_algorithm": rawpy.DemosaicAlgorithm.AHD,
                "output_color": rawpy.ColorSpace.sRGB,
                "output_bps": 16,
                "half_size": False,
                "use_camera_wb": white_balance == "camera" and as_shot_white_balance is None,
                "use_auto_wb": False,
                "no_auto_bright": False,
                "auto_bright_thr": 0.01,
                "bright": 1.0,
                "gamma": (2.4, 12.92),
                "median_filter_passes": 0,
                "fbdd_noise_reduction": rawpy.FBDDNoiseReductionMode.Off,
            }
            if as_shot_white_balance is not None:
                parameters["user_wb"] = as_shot_white_balance["multipliers"]
            raw_pixels = raw.postprocess(**parameters)
            if raw_pixels.dtype != np.uint16:
                raise IngestError("RAW decoder did not return RGB16")
            pixels = np.ascontiguousarray(raw_pixels, dtype=np.uint16)
            metadata = {
                "format": "RAW",
                "source_precision_bits": None,
                "raw_white_level": int(raw.white_level),
                "orientation": int(raw.sizes.flip),
                "orientation_owner": "LibRaw",
                "profile_decision": "explicit_raw_srgb",
                "crop": "full_visible_no_extra_crop",
                # Non-finite rejected coefficients cannot enter canonical JSON identities.
                "camera_whitebalance": [
                    float(value) if np.isfinite(value) else None for value in coefficients.ravel()
                ],
                "camera_whitebalance_shape": list(coefficients.shape),
                "camera_whitebalance_valid": bool(credible),
                "development": {
                    "white_balance": white_balance,
                    "demosaic": "AHD",
                    "gamma": [2.4, 12.92],
                    "bright": 1.0,
                    "auto_bright_thr": 0.01,
                    "half_size": False,
                    "noise_reduction": "off",
                    "sharpening": "none",
                    "extra_DefaultCropSize": False,
                },
                "libraw": list(rawpy.libraw_version),
                **(
                    {"as_shot_white_balance": as_shot_white_balance}
                    if as_shot_white_balance is not None
                    else {}
                ),
            }
            return pixels, metadata
    except rawpy.LibRawError as error:
        raise IngestError(f"Unsupported or invalid RAW capture: {error}") from error


def decode_source(data: bytes, development: dict[str, Any]) -> tuple[RGB16, dict[str, Any]]:
    """Detect signatures; never let a multichannel PNG16 enter Pillow's RGB8 route."""
    if set(development) - {"assume_srgb", "white_balance", "jpeg_sdr_primary"}:
        raise IngestError("Unknown development option")
    if type(development.get("assume_srgb", False)) is not bool:
        raise IngestError("assume_srgb must be a boolean")
    if type(development.get("jpeg_sdr_primary", False)) is not bool:
        raise IngestError("jpeg_sdr_primary must be a boolean")
    sdr_primary = development.get("jpeg_sdr_primary", False)
    if sdr_primary and not data.startswith(b"\xff\xd8"):
        raise IngestError("SDR primary requires a gain-map JPEG")
    selection = None
    if development.get("white_balance", "camera") not in {"camera", "daylight"}:
        raise IngestError("white_balance must be camera or daylight")
    assumption = development.get("assume_srgb", False)
    is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    is_tiff = data[:4] in {b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"}
    if is_png and len(data) >= 26 and data[24] == 16 and data[25] in {2, 4, 6}:
        raise IngestError("RGB16 PNG unsupported: export trusted uncompressed sRGB TIFF")
    if is_tiff:
        try:
            # IFD0 may be only an RGB preview; LibRaw owns RAW identification.
            pixels, metadata = _decode_raw(data, development)
        except rawpy.LibRawFileUnsupportedError as unsupported_raw:
            try:
                with tifffile.TiffFile(io.BytesIO(data)) as image:
                    page = image.pages[0]
                    if not isinstance(page, tifffile.TiffPage):
                        raise IngestError("TIFF frame is not a supported image page")
                    if 50706 in page.tags or int(page.photometric) == 32803:
                        raise IngestError(
                            "LibRaw cannot decode this RAW TIFF container"
                        ) from unsupported_raw
                    if (
                        len(image.pages) != 1
                        or page.dtype != np.dtype("uint16")
                        or page.shape[-1:] != (3,)
                        or len(page.shape) != 3
                        or int(page.photometric) != 2
                        or int(page.planarconfig) != 1
                    ):
                        raise IngestError("TIFF input must be single-page contiguous RGB16")
                    if int(page.compression) != 1:
                        raise IngestError(
                            f"Unsupported TIFF compression {page.compression}; export uncompressed"
                        )
                    profile = page.tags[34675].value if 34675 in page.tags else None
                    decision = _profile_decision(profile, assumption)
                    orientation = int(page.tags[274].value) if 274 in page.tags else 1
                    pixels = _orient(page.asarray(), orientation)
                    metadata = {
                        "format": "TIFF",
                        "source_precision_bits": 16,
                        "orientation": orientation,
                        "orientation_owner": "blackmask",
                        "profile_decision": decision,
                        "crop": "none",
                        "source_profile_sha256": hashlib.sha256(profile).hexdigest()
                        if profile
                        else None,
                        "source_width": page.imagewidth,
                        "source_height": page.imagelength,
                    }
            except (tifffile.TiffFileError, IndexError) as error:
                raise IngestError(f"Invalid TIFF: {error}") from error
    elif is_png or data.startswith(b"\xff\xd8"):
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.mode != "RGB" or "transparency" in image.info:
                    raise IngestError(
                        "Only opaque RGB JPEG/PNG8 supported; alpha/transparency or other modes require a trusted TIFF"
                    )
                recovery = (
                    "export a single-image SDR JPEG/PNG8 or trusted uncompressed sRGB RGB16 TIFF"
                )
                if getattr(image, "n_frames", 1) != 1:
                    raise IngestError(
                        f"Multi-frame {image.format} is not a single photograph; {recovery}"
                    )
                if isinstance(image, JpegImagePlugin.JpegImageFile):
                    # Pillow 12.3 exposes Ultra HDR gain-map JPEGs as one frame.
                    # Its MPF parser still reports the additional image payloads.
                    try:
                        multi_picture = image._getmp()
                        if multi_picture is not None and multi_picture[0xB001] != 1:
                            if not sdr_primary:
                                raise IngestError(
                                    "Multi-image JPEG (including Ultra HDR gain maps) is "
                                    f"unsupported without explicit --jpeg-sdr-primary; {recovery}"
                                )
                            selection = _sdr_primary_selection(data, image, multi_picture)
                    except (SyntaxError, TypeError, IndexError, KeyError) as error:
                        raise IngestError(
                            f"Invalid JPEG multi-picture metadata; {recovery}"
                        ) from error
                if sdr_primary and selection is None:
                    raise IngestError("SDR primary requires a two-image gain-map JPEG")
                profile = image.info.get("icc_profile")
                if profile and normalize_profile(profile) != srgb_profile():
                    try:
                        converted = ImageCms.profileToProfile(
                            image,
                            ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                            ImageCms.ImageCmsProfile(io.BytesIO(srgb_profile())),
                            outputMode="RGB",
                        )
                    except (ImageCms.PyCMSError, OSError, ValueError) as error:
                        raise IngestError(f"Unsupported RGB8 color profile: {error}") from error
                    decision = "rgb8_icc_to_srgb"
                else:
                    converted = image
                    decision = _profile_decision(profile, assumption, "srgb" in image.info)
                orientation = int(image.getexif().get(274, 1))
                pixels = _orient(np.array(converted, dtype=np.uint16) * 257, orientation)
                metadata = {
                    "format": image.format,
                    "source_precision_bits": 8,
                    "orientation": orientation,
                    "orientation_owner": "blackmask",
                    "profile_decision": decision,
                    "crop": "none",
                    "source_profile_sha256": hashlib.sha256(profile).hexdigest()
                    if profile
                    else None,
                    "source_width": image.width,
                    "source_height": image.height,
                }
        except (UnidentifiedImageError, OSError) as error:
            raise IngestError(f"Invalid JPEG/PNG: {error}") from error
    else:
        try:
            pixels, metadata = _decode_raw(data, development)
        except rawpy.LibRawFileUnsupportedError as error:
            raise IngestError(f"Unsupported or invalid RAW capture: {error}") from error
    if (
        pixels.dtype != np.uint16
        or pixels.ndim != 3
        or pixels.shape[2] != 3
        or min(pixels.shape[:2]) < 1
    ):
        raise IngestError("Decoder did not return a nonempty RGB16 image")
    pixels = np.ascontiguousarray(pixels, dtype=np.uint16)
    if selection is not None:
        metadata["jpeg_sdr_primary"] = selection
    metadata.update(
        {
            "width": pixels.shape[1],
            "height": pixels.shape[0],
            "encoding": "sRGB",
            "profile_sha256": hashlib.sha256(srgb_profile()).hexdigest(),
            "development_options": development,
            "clipped_channel_samples": int(np.count_nonzero(pixels == 65535)),
        }
    )
    return pixels, metadata


def write_developed(path: Path, pixels: RGB16) -> None:
    profile = srgb_profile()
    tifffile.imwrite(
        path,
        pixels,
        photometric="rgb",
        compression=None,
        metadata=None,
        extratags=[(34675, "B", len(profile), profile, False)],
    )
