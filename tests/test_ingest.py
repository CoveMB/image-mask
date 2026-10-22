import hashlib
import io
import struct
import zlib
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image, ImageCms

from blackmask.ingest import IngestError, decode_source, srgb_profile, write_master


def ramp():
    return np.array(
        [
            [[1000, 1001, 1002], [20003, 20004, 20005], [65535, 12345, 1]],
            [[500, 501, 502], [30001, 30002, 30003], [42, 43, 44]],
        ],
        dtype=np.uint16,
    )


def tiff(path, pixels=None, profile=None, **kwargs):
    tifffile.imwrite(
        path,
        ramp() if pixels is None else pixels,
        photometric="rgb",
        extratags=[(34675, "B", len(profile), profile, False)] if profile else [],
        metadata=None,
        **kwargs,
    )
    return path


def test_canonical_srgb_bytes_preserve_saved_project_identity():
    # Captured from the prior pinned runtime. Saved RGB16 validation compares
    # these normalized bytes exactly, so a library upgrade must not migrate them.
    assert hashlib.sha256(srgb_profile()).hexdigest() == (
        "6f6fe5cc53cd24ceeb7997fb24ce2889fdfb88d88ce4fdc5f8e25e0481294953"
    )


def test_rgb16_non_257_roundtrip(tmp_path):
    source = tiff(tmp_path / "misnamed.jpg", profile=srgb_profile())
    before = source.read_bytes()
    pixels, metadata = decode_source(before, {})
    assert np.any(pixels % 257)
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["format"] == "TIFF" and metadata["source_precision_bits"] == 16
    output = tmp_path / "master.tif"
    write_master(output, pixels)
    np.testing.assert_array_equal(tifffile.imread(output), ramp())
    assert source.read_bytes() == before
    with tifffile.TiffFile(output) as image:
        assert image.pages[0].compression == 1
        assert image.pages[0].tags[34675].value == srgb_profile()


@pytest.mark.parametrize("orientation", range(1, 9))
def test_orientation_once(tmp_path, orientation):
    source = tmp_path / "source.tif"
    profile = srgb_profile()
    tifffile.imwrite(
        source,
        ramp(),
        photometric="rgb",
        metadata=None,
        extratags=[(34675, "B", len(profile), profile, False), (274, "H", 1, orientation, False)],
    )
    pixels, metadata = decode_source(source.read_bytes(), {})
    # Independently enumerated corner/index order for 2 rows by 3 columns.
    indices = {
        1: [[0, 1, 2], [3, 4, 5]],
        2: [[2, 1, 0], [5, 4, 3]],
        3: [[5, 4, 3], [2, 1, 0]],
        4: [[3, 4, 5], [0, 1, 2]],
        5: [[0, 3], [1, 4], [2, 5]],
        6: [[3, 0], [4, 1], [5, 2]],
        7: [[5, 2], [4, 1], [3, 0]],
        8: [[2, 5], [1, 4], [0, 3]],
    }[orientation]
    expected = ramp().reshape(-1, 3)[indices]
    np.testing.assert_array_equal(pixels, expected)
    assert metadata["orientation"] == orientation


@pytest.mark.parametrize("format", ["JPEG", "PNG"])
def test_rgb8_precision_and_missing_profile(tmp_path, format):
    source = tmp_path / "source.bin"
    Image.fromarray(np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)).save(
        source, format=format
    )
    with pytest.raises(IngestError, match="profile"):
        decode_source(source.read_bytes(), {})
    pixels, metadata = decode_source(source.read_bytes(), {"assume_srgb": True})
    with Image.open(source) as image:
        expected = np.array(image, dtype=np.uint16) * 257
    np.testing.assert_array_equal(pixels, expected)
    assert metadata["source_precision_bits"] == 8
    assert metadata["profile_decision"] == "explicit_srgb_assumption"


def test_rgb8_profile_conversion_and_alpha_rejection(tmp_path):
    image = Image.new("RGB", (3, 2), (31, 97, 151))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", icc_profile=srgb_profile())
    pixels, metadata = decode_source(buffer.getvalue(), {})
    assert pixels.dtype == np.uint16
    assert metadata["profile_decision"] == "embedded_srgb"
    buffer = io.BytesIO()
    Image.new("RGBA", (2, 2), (1, 2, 3, 127)).save(buffer, format="PNG")
    with pytest.raises(IngestError, match="alpha|transparency"):
        decode_source(buffer.getvalue(), {"assume_srgb": True})


def test_png16_rejected_before_pillow():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 16, 2, 0, 0, 0))
    with (
        patch("blackmask.ingest.Image.open", side_effect=AssertionError("lossy decoder called")),
        pytest.raises(IngestError, match="RGB16 PNG"),
    ):
        decode_source(data, {})


def test_tiff_profile_compression_and_depth(tmp_path):
    for profile in (None, ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()):
        source = tiff(tmp_path / "profile.tif", profile=profile)
        with pytest.raises(IngestError, match="profile|sRGB"):
            decode_source(source.read_bytes(), {})
    source = tiff(tmp_path / "compressed.tif", profile=srgb_profile(), compression="deflate")
    with pytest.raises(IngestError, match="compression"):
        decode_source(source.read_bytes(), {})
    source = tiff(tmp_path / "eight.tif", pixels=ramp().astype(np.uint8), profile=srgb_profile())
    with pytest.raises(IngestError, match="RGB16"):
        decode_source(source.read_bytes(), {})


def test_development_options_reject_unknown_or_wrong_types(tmp_path):
    source = tiff(tmp_path / "source.tif", profile=srgb_profile())
    for development in (
        {"assume_srgb": "false"},
        {"crop": [0, 0, 1, 1]},
        {"white_balance": "auto"},
    ):
        with pytest.raises(IngestError):
            decode_source(source.read_bytes(), development)


class FakeRaw:
    camera_whitebalance = (0, 0, 0, 0)
    daylight_whitebalance = (2, 1, 1.5, 0)
    color_desc = b"RGBG"
    num_colors = 3
    white_level = 16383
    sizes = type("Sizes", (), {"flip": 6, "width": 3, "height": 2})()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def postprocess(self, **settings):
        self.settings = settings
        return ramp()


def test_raw_invalid_wb_requires_explicit_daylight_and_exact_params():
    import rawpy

    raw = FakeRaw()
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=raw),
        pytest.raises(IngestError, match="white balance"),
    ):
        decode_source(b"synthetic RAW decoder boundary", {})
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        pixels, metadata = decode_source(
            b"synthetic RAW decoder boundary", {"white_balance": "daylight"}
        )
    np.testing.assert_array_equal(pixels, ramp())
    assert raw.settings == {
        "demosaic_algorithm": rawpy.DemosaicAlgorithm.AHD,
        "output_color": rawpy.ColorSpace.sRGB,
        "output_bps": 16,
        "half_size": False,
        "use_camera_wb": False,
        "use_auto_wb": False,
        "no_auto_bright": False,
        "auto_bright_thr": 0.01,
        "bright": 1.0,
        "gamma": (2.4, 12.92),
        "median_filter_passes": 0,
        "fbdd_noise_reduction": rawpy.FBDDNoiseReductionMode.Off,
    }
    assert metadata["orientation_owner"] == "LibRaw"
    assert metadata["source_precision_bits"] is None


def test_raw_camera_coefficients():
    raw = FakeRaw()
    raw.camera_whitebalance = [2, 1, 1.5, 0]
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        _, metadata = decode_source(b"RAW", {})
    assert raw.settings["use_camera_wb"] is True
    assert metadata["development"]["white_balance"] == "camera"


def dng_white_point_metadata(
    *, white_xy=(1, 4, 1, 2), overrides=None, byteorder="<", duplicate_tags=()
):
    # Metadata-only synthetic RAW boundary; no private pixels or camera profile.
    tags = {
        50706: ("B", 4, (1, 4, 0, 0)),
        50729: ("2I", 2, white_xy),
        50721: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1)),
    }
    for code, value in (overrides or {}).items():
        if value is None:
            tags.pop(code, None)
        else:
            tags[code] = value
    buffer = io.BytesIO()
    tifffile.imwrite(
        buffer,
        np.zeros((8, 8), dtype=np.uint16),
        byteorder=byteorder,
        metadata=None,
        extratags=[(code, kind, count, value, False) for code, (kind, count, value) in tags.items()]
        + list(duplicate_tags),
    )
    return buffer.getvalue()


def test_dng_as_shot_white_point_supplies_missing_camera_multipliers():
    raw = FakeRaw()
    data = dng_white_point_metadata()
    before = hashlib.sha256(data).hexdigest()
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        pixels, metadata = decode_source(data, {})
    # Identity XYZ-to-camera matrix and xy=(1/4,1/2) give neutral=(1/2,1,1/2).
    np.testing.assert_allclose(raw.settings["user_wb"], [2, 1, 2, 1], rtol=0, atol=1e-12)
    assert raw.settings["use_camera_wb"] is False
    assert raw.settings["use_auto_wb"] is False
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["camera_whitebalance_valid"] is False
    assert metadata["development"]["white_balance"] == "camera"
    assert metadata["as_shot_white_balance"]["source"] == "DNG AsShotWhiteXY"
    assert metadata["as_shot_white_balance"]["multipliers"] == [2, 1, 2, 1]
    assert hashlib.sha256(data).hexdigest() == before


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({50727: ("2I", 3, (2, 1, 1, 1, 1, 2))}, [1, 1, 4, 1]),
        (
            {50723: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 2, 1, 0, 1, 0, 1, 0, 1, 1, 1))},
            [4, 1, 4, 1],
        ),
        (
            {
                50723: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 2, 1, 0, 1, 0, 1, 0, 1, 1, 1)),
                50931: ("s", 0, "camera"),
                50932: ("s", 0, "other-profile"),
            },
            [2, 1, 2, 1],
        ),
    ],
)
def test_dng_white_point_applies_matching_calibration_and_analog_balance(overrides, expected):
    raw = FakeRaw()
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        decode_source(dng_white_point_metadata(overrides=overrides), {})
    np.testing.assert_allclose(raw.settings["user_wb"], expected, rtol=0, atol=1e-12)


@pytest.mark.parametrize(
    "overrides",
    [
        {50721: None},
        {50729: ("2I", 2, (1, 0, 1, 2))},
        {50729: ("2I", 2, (1, 1, 1, 2))},
        {50729: ("2I", 1, (1, 4))},
        {50728: ("2I", 3, (1, 1, 1, 1, 1, 1))},
        {50727: ("2I", 3, (0, 1, 1, 1, 1, 1))},
        {50721: ("2i", 9, (0, 1) * 9)},
        {50721: ("2i", 9, (-1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1))},
        {50722: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1))},
        {52531: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1))},
    ],
)
def test_unusable_dng_white_point_never_reaches_raw_processing(overrides):
    raw = FakeRaw()
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=raw),
        pytest.raises(IngestError, match="white balance"),
    ):
        decode_source(dng_white_point_metadata(overrides=overrides), {})
    assert not hasattr(raw, "settings")


@pytest.mark.parametrize(
    "duplicate_tag",
    [
        (50729, "2I", 2, (1, 3, 1, 3), False),
        (50706, "B", 4, (2, 0, 0, 0), False),
        (50721, "2i", 9, (0, 1) * 9, False),
    ],
)
def test_duplicate_dng_white_balance_tags_never_reach_processing(duplicate_tag):
    raw = FakeRaw()
    data = dng_white_point_metadata(duplicate_tags=[duplicate_tag])
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=raw),
        pytest.raises(IngestError, match="duplicate"),
    ):
        decode_source(data, {})
    assert not hasattr(raw, "settings")


@pytest.mark.parametrize("kind", ["s", "B"])
def test_dng_as_shot_profile_must_identify_the_primary_profile(kind):
    def name(value):
        return (kind, 0, value) if kind == "s" else (kind, len(value) + 1, value.encode() + b"\0")

    tags = {50934: name("as-shot"), 50936: name("primary")}
    raw = FakeRaw()
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=raw),
        pytest.raises(IngestError, match="primary profile"),
    ):
        decode_source(dng_white_point_metadata(overrides=tags), {})
    assert not hasattr(raw, "settings")

    tags[50936] = name("as-shot")
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        decode_source(dng_white_point_metadata(overrides=tags), {})
    assert raw.settings["user_wb"] == [2, 1, 2, 1]


def test_explicit_daylight_does_not_use_dng_white_point():
    raw = FakeRaw()
    data = dng_white_point_metadata(white_xy=(1, 0, 1, 2))
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        _, metadata = decode_source(data, {"white_balance": "daylight"})
    assert "user_wb" not in raw.settings
    assert "as_shot_white_balance" not in metadata
    assert metadata["development"]["white_balance"] == "daylight"


def dual_illuminant_dng(*, reverse=False, white_xy=(22511, 59170, 33439, 88755), **kwargs):
    # Robertson's 250-mired table point is exactly 4000 K. Both color matrices
    # already have unit maximum D50 response, so normalization leaves them alone.
    first_color = (1, 2, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1)
    second_color = (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 2)
    first_calibration = (3, 2, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1)
    second_calibration = (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 3, 2)
    if reverse:
        first_color, second_color = second_color, first_color
        first_calibration, second_calibration = second_calibration, first_calibration
    return dng_white_point_metadata(
        white_xy=white_xy,
        overrides={
            50721: ("2i", 9, first_color),
            50722: ("2i", 9, second_color),
            50723: ("2i", 9, first_calibration),
            50724: ("2i", 9, second_calibration),
            50778: ("H", 1, 21 if reverse else 17),
            50779: ("H", 1, 17 if reverse else 21),
        },
        **kwargs,
    )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("byteorder", ["<", ">"])
def test_dng_white_point_interpolates_calibrated_matrices_in_reciprocal_temperature(
    reverse, byteorder
):
    raw = FakeRaw()
    data = dual_illuminant_dng(reverse=reverse, byteorder=byteorder)
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        _, metadata = decode_source(data, {})
    # Independently evaluated with exact rational arithmetic: first-profile
    # weight=(1/4000-1/6500)/(1/2850-1/6500); interpolate CC*CM, not CC and CM
    # separately. This also catches reversed profile order and wrong TIFF endian.
    np.testing.assert_allclose(
        raw.settings["user_wb"],
        [1.1279099096995633, 1, 1.7794995921242303, 1],
        rtol=0,
        atol=1e-12,
    )
    assert metadata["as_shot_white_balance"]["temperature_kelvin"] == pytest.approx(4000)


@pytest.mark.parametrize(
    ("white_xy", "expected"),
    [((11, 20, 2, 5), [32 / 33, 1, 8, 1]), ((1, 4, 1, 4), [1, 1, 2 / 3, 1])],
)
def test_dng_white_point_clamps_to_calibration_endpoints(white_xy, expected):
    raw = FakeRaw()
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        decode_source(dual_illuminant_dng(white_xy=white_xy), {})
    np.testing.assert_allclose(raw.settings["user_wb"], expected, rtol=0, atol=1e-12)


def triple_illuminant_dng(*, byteorder="<", extra_tags=None):
    # Third calibration's custom white is exactly the capture white. The other
    # two calibrations must receive zero weight, including for off-locus tint.
    tags = {
        50722: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1)),
        50778: ("H", 1, 17),
        50779: ("H", 1, 21),
        52529: ("H", 1, 255),
        52530: ("2i", 9, (2, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1)),
        52531: ("2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 2)),
        52535: (7, 18, struct.pack(byteorder + "HIIII", 0, 1, 4, 1, 2)),
    }
    tags.update(extra_tags or {})
    return dng_white_point_metadata(overrides=tags, byteorder=byteorder)


@pytest.mark.parametrize("byteorder", ["<", ">"])
def test_dng_white_point_uses_as_shot_third_calibration_and_custom_illuminant(byteorder):
    raw = FakeRaw()
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        _, metadata = decode_source(triple_illuminant_dng(byteorder=byteorder), {})
    np.testing.assert_allclose(raw.settings["user_wb"], [1, 1, 4, 1], rtol=0, atol=1e-12)
    np.testing.assert_allclose(metadata["as_shot_white_balance"]["calibration_weights"], [0, 0, 1])


def test_triple_profile_interpolation_matches_independent_sdk_reference():
    raw = FakeRaw()
    data = triple_illuminant_dng(
        extra_tags={
            50729: ("2I", 2, (6, 25, 8, 25)),
            52530: None,
            52535: (7, 18, struct.pack("<HIIII", 0, 9, 25, 3, 10)),
        }
    )
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        _, metadata = decode_source(data, {})
    # Adobe DNG SDK de700ad's C++ temperature/tint and triple-weight functions,
    # evaluated independently with A, D65 and custom xy=(.36,.30).
    np.testing.assert_allclose(
        metadata["as_shot_white_balance"]["calibration_weights"],
        [0.285394140303605, 0.6824219455389922, 0.03218391415740285],
        rtol=0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        raw.settings["user_wb"], [4 / 3, 1, 0.7391673769770177, 1], rtol=0, atol=1e-12
    )


def test_dng_white_point_project_reopens_saved_master_without_raw_decoder(tmp_path):
    import json

    from blackmask.project import create_project, load_master, read_project

    source = tmp_path / "capture.dng"
    source.write_bytes(dng_white_point_metadata())
    original_bytes = source.read_bytes()
    project = tmp_path / "photo-project"
    with patch("blackmask.ingest.rawpy.imread", return_value=FakeRaw()):
        create_project(source, project, {})
    created = json.loads((project / "state.json").read_bytes())
    with patch("blackmask.ingest.rawpy.imread", side_effect=AssertionError("must not redevelop")):
        reopened = read_project(project)
        pixels, metadata = load_master(project, reopened["master_id"])
    assert created["master_id"] == reopened["master_id"]
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["as_shot_white_balance"]["multipliers"] == [2, 1, 2, 1]
    assert reopened["development_approved"] is False
    assert source.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "extra_tags",
    [
        {52535: None},
        {52535: (7, 18, struct.pack("<HIIII", 0, 1, 0, 1, 2))},
        {52535: (7, 18, struct.pack("<HIIII", 1, 1, 4, 1, 2))},
        {52535: (7, 17, bytes(17))},
        {52535: (7, 18, struct.pack("<HIIII", 0, 3127, 10000, 329, 1000))},
        {50722: None},
        {52530: ("2i", 9, (0, 1) * 9)},
    ],
)
def test_incomplete_or_ambiguous_triple_profile_is_rejected_before_processing(extra_tags):
    raw = FakeRaw()
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=raw),
        pytest.raises(IngestError, match="white balance"),
    ):
        decode_source(triple_illuminant_dng(extra_tags=extra_tags), {})
    assert not hasattr(raw, "settings")


def test_rgb8_actual_icc_transform_route():
    # Synthetic linear-light RGB profile with sRGB primaries, independently known
    # transfer: encoded = 1.055 * linear**(1/2.4) - .055 for these samples.
    profile = bytearray(srgb_profile())
    count = struct.unpack_from(">I", profile, 128)[0]
    for index in range(count):
        position = 132 + index * 12
        signature, offset, _size = struct.unpack_from(">4sII", profile, position)
        if signature in {b"rTRC", b"gTRC", b"bTRC"}:
            profile[offset : offset + 16] = b"para" + bytes(4) + struct.pack(">HHI", 0, 0, 65536)
            struct.pack_into(">I", profile, position + 8, 16)
    buffer = io.BytesIO()
    Image.new("RGB", (3, 2), (16, 64, 128)).save(buffer, format="PNG", icc_profile=bytes(profile))
    pixels, metadata = decode_source(buffer.getvalue(), {})
    assert metadata["profile_decision"] == "rgb8_icc_to_srgb"
    np.testing.assert_array_equal(pixels[0, 0], np.array([71, 137, 188], dtype=np.uint16) * 257)


def test_png_exif_orientation_and_explicit_assumption():
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.fromarray((ramp() // 257).astype(np.uint8)).save(buffer, format="PNG", exif=exif)
    pixels, metadata = decode_source(buffer.getvalue(), {"assume_srgb": True})
    expected = (ramp() // 257 * 257).reshape(-1, 3)[[[3, 0], [4, 1], [5, 2]]]
    np.testing.assert_array_equal(pixels, expected)
    assert metadata["source_width"] == 3 and metadata["source_height"] == 2


def test_big_endian_tiff_and_missing_profile_assumption(tmp_path):
    source = tmp_path / "big.tif"
    tifffile.imwrite(source, ramp(), photometric="rgb", byteorder=">", metadata=None)
    pixels, metadata = decode_source(source.read_bytes(), {"assume_srgb": True})
    np.testing.assert_array_equal(pixels, ramp())
    assert metadata["profile_decision"] == "explicit_srgb_assumption"


def test_tiff_raw_preview_does_not_choose_the_rgb8_route():
    # RAW containers can expose an RGB8 preview in IFD0 without DNG/CFA tags.
    buffer = io.BytesIO()
    Image.new("RGB", (7, 4), (10, 20, 30)).save(buffer, format="TIFF")
    raw = FakeRaw()
    raw.camera_whitebalance = [2, 1, 1.5, 0]
    with patch("blackmask.ingest.rawpy.imread", return_value=raw):
        pixels, metadata = decode_source(buffer.getvalue(), {})
    np.testing.assert_array_equal(pixels, ramp())
    assert pixels.shape == (2, 3, 3) and pixels.dtype == np.uint16
    assert metadata["format"] == "RAW"
    assert metadata["orientation_owner"] == "LibRaw"
    assert metadata["source_precision_bits"] is None


def test_recognized_tiff_raw_development_error_cannot_fall_back_to_preview():
    buffer = io.BytesIO()
    Image.new("RGB", (7, 4), (10, 20, 30)).save(buffer, format="TIFF")
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=FakeRaw()),
        pytest.raises(IngestError, match="white balance"),
    ):
        decode_source(buffer.getvalue(), {"assume_srgb": True})


@pytest.mark.parametrize("error_name", ["LibRawDataError", "LibRawFileUnsupportedError"])
def test_recognized_tiff_raw_decode_error_cannot_fall_back_to_tiff(error_name):
    import rawpy

    buffer = io.BytesIO()
    write_profile = srgb_profile()
    tifffile.imwrite(
        buffer,
        ramp(),
        photometric="rgb",
        metadata=None,
        extratags=[(34675, "B", len(write_profile), write_profile, False)],
    )
    raw = FakeRaw()
    raw.camera_whitebalance = [2, 1, 1.5, 0]
    with (
        patch("blackmask.ingest.rawpy.imread", return_value=raw),
        patch.object(raw, "postprocess", side_effect=getattr(rawpy, error_name)("damaged RAW")),
        pytest.raises(IngestError, match="invalid RAW"),
    ):
        decode_source(buffer.getvalue(), {})


def test_unknown_raw_is_an_actionable_ingest_error():
    with pytest.raises(IngestError, match="Unsupported or invalid RAW"):
        decode_source(b"Not a decodable capture", {})


def test_unrecognized_dng_cannot_be_imported_as_ordinary_rgb16_tiff():
    import rawpy

    buffer = io.BytesIO()
    profile = srgb_profile()
    tifffile.imwrite(
        buffer,
        ramp(),
        photometric="rgb",
        metadata=None,
        extratags=[
            (34675, "B", len(profile), profile, False),
            (50706, "B", 4, (1, 4, 0, 0), False),
        ],
    )
    with (
        patch("blackmask.ingest.rawpy.imread", side_effect=rawpy.LibRawFileUnsupportedError()),
        pytest.raises(IngestError, match="RAW"),
    ):
        decode_source(buffer.getvalue(), {})


def multi_image_jpeg(*, gain_map=False):
    """Build two actual JPEG payloads and an MPF directory, without photo assets."""
    buffer = io.BytesIO()
    options = {}
    if gain_map:
        options["xmp"] = (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:Description xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" '
            b'hdrgm:Version="1.0"/></x:xmpmeta>'
        )
    Image.new("RGB", (8, 6), (20, 80, 160)).save(
        buffer,
        format="MPO",
        save_all=True,
        append_images=[Image.new("RGB", (8, 6), (100, 100, 100))],
        **options,
    )
    return buffer.getvalue()


def test_mpo_rejection_names_actual_format_and_recovery():
    data = multi_image_jpeg()
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "MPO" and image.n_frames == 2
    with pytest.raises(IngestError, match="Multi-frame MPO.*single-image SDR JPEG/PNG8"):
        decode_source(data, {"assume_srgb": True})


def test_gain_map_jpeg_cannot_silently_become_an_sdr_master():
    data = multi_image_jpeg(gain_map=True)
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG" and getattr(image, "n_frames", 1) == 1
        assert image._getmp()[0xB001] == 2
    with pytest.raises(
        IngestError, match="Multi-image JPEG.*Ultra HDR.*single-image SDR JPEG/PNG8"
    ):
        decode_source(data, {"assume_srgb": True})


@pytest.mark.parametrize("disposal", [0, 1, 2])
def test_animated_png_rejection_names_actual_format_and_recovery(disposal):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (20, 80, 160)).save(
        buffer,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (8, 6), (100, 100, 100))],
        disposal=disposal,
    )
    with Image.open(io.BytesIO(buffer.getvalue())) as image:
        assert image.format == "PNG" and image.n_frames == 2
    with pytest.raises(IngestError, match="Multi-frame PNG.*single-image SDR JPEG/PNG8"):
        decode_source(buffer.getvalue(), {"assume_srgb": True})
