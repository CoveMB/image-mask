import importlib
from unittest.mock import patch

import numpy as np
import pytest
from test_ingest import saved_raster


def cache_identity():
    return {
        "developed_id": "a" * 64,
        "model": "synthetic-only",
        "revision": "b" * 40,
        "hashes": {
            "config.json": "c" * 64,
            "preprocessor_config.json": "d" * 64,
            "model.safetensors": "e" * 64,
        },
        "packages": {
            name: "test-version"
            for name in ("torch", "torchvision", "transformers", "safetensors", "numpy", "Pillow")
        },
        "preprocessing": "test-native-v1",
        "dtype": "float32",
        "attention": "eager",
    }


def engine():
    return importlib.import_module("blackmask.matte")


def cache_npy_members(*, dtype="float64", order="C", version=(1, 0), key="a" * 64):
    import hashlib
    import io

    alpha = np.array([[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]], dtype=dtype, order=order)
    alpha /= 16
    arrays = {
        "alpha.npy": alpha,
        "metadata.npy": np.array("{}"),
        "key.npy": np.array(key),
        "sha256.npy": np.array(hashlib.sha256(alpha.tobytes() + b"{}").hexdigest()),
    }
    members = {}
    for name, value in arrays.items():
        stream = io.BytesIO()
        np.lib.format.write_array(stream, value, version=version, allow_pickle=False)
        members[name] = stream.getvalue()
    return members, alpha


def cache_zip_members(members, methods=0, comment=b""):
    import io
    import zipfile

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for index, (name, body) in enumerate(members.items()):
            method = methods[index] if isinstance(methods, tuple) else methods
            archive.writestr(name, body, compress_type=method)
        archive.comment = comment
    return output.getvalue()


@pytest.mark.parametrize("embedded,comment", [(False, b""), (True, b""), (True, b"searched")])
def test_cache_directory_count_is_bounded_before_public_metadata(monkeypatch, embedded, comment):
    import io
    import struct
    import zipfile

    members, _ = cache_npy_members()
    five = cache_zip_members({**members, "fifth.npy": b"unused"})
    directory = five[five.index(b"PK\x01\x02") : -22]
    if embedded:
        raw = bytearray(cache_zip_members(members))
        outer = len(raw) - 22
        struct.pack_into("<H", raw, outer + 20, len(directory) + 22 + len(comment))
        directory_start = len(raw)
        raw.extend(directory)
        raw.extend(
            struct.pack(
                "<4s4H2IH", b"PK\x05\x06", 0, 0, 4, 4, len(directory), directory_start, len(comment)
            )
        )
        raw.extend(comment)
        # Both EOCD extents reach EOF; the later selection owns five physical records.
        assert outer + 22 + struct.unpack_from("<H", raw, outer + 20)[0] == len(raw)
    else:
        raw = bytearray(five)
        struct.pack_into("<HH", raw, len(raw) - 22 + 8, 4, 4)

    def forbidden(*args, **kwargs):
        pytest.fail("metadata constructed before fixed-four physical-directory admission")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    monkeypatch.setattr(zipfile, "ZipInfo", forbidden)
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


@pytest.mark.parametrize(
    "method,damage",
    [(12, "valid"), (12, "malformed"), (14, "valid"), (14, "malformed"), (14, "dictionary")],
)
def test_cache_later_unsupported_method_rejects_before_all_codec_and_npy_activity(
    monkeypatch, method, damage
):
    import bz2
    import io
    import lzma
    import struct
    import zipfile
    import zlib

    members, _ = cache_npy_members()
    raw = bytearray(cache_zip_members(members, (8, 8, 8, method)))
    if damage != "valid":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            local = archive.getinfo("sha256.npy").header_offset
        header = struct.unpack_from("<4s5H3I2H", raw, local)
        payload = local + 30 + header[-2] + header[-1]
        if damage == "dictionary":
            # The decoder spy below stops before any attacker-selected allocation.
            assert struct.unpack_from("<H", raw, payload + 2)[0] == 5
            struct.pack_into("<I", raw, payload + 5, 1 << 30)
        else:
            raw[payload + (4 if method == 14 else 0)] = 0xFF

    def forbidden(*args, **kwargs):
        pytest.fail("codec, CRC or NPY activity before whole-directory method admission")

    for module, names in (
        (zlib, ("decompress", "decompressobj", "crc32")),
        (zipfile, ("crc32",)),
        (bz2, ("BZ2Decompressor",)),
        (lzma, ("LZMADecompressor",)),
        (
            np.lib.format,
            ("read_magic", "read_array_header_1_0", "read_array_header_2_0", "read_array"),
        ),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


@pytest.mark.parametrize("method", [0, 8])
def test_cache_actual_expansion_is_bounded_before_npy(monkeypatch, method):
    import io
    import struct
    import zlib

    members, _ = cache_npy_members()
    prefix = members["alpha.npy"]
    assert len(prefix) == 224
    raw = bytearray(cache_zip_members({**members, "alpha.npy": prefix + b"x" * 8192}, method))
    central = raw.index(b"PK\x01\x02")
    for offset in (14, central + 16):
        struct.pack_into("<I", raw, offset, zlib.crc32(prefix))
    for offset in (22, central + 24):
        struct.pack_into("<I", raw, offset, len(prefix))
    original = zlib.decompressobj
    calls = []

    class BoundedDecoder:
        def __init__(self, *args, **kwargs):
            self.decoder = original(*args, **kwargs)

        def decompress(self, data, max_length=0):
            assert 0 < max_length <= 225, "declared size must bound every real decoder call"
            result = self.decoder.decompress(data, max_length)
            calls.append((max_length, len(result)))
            return result

        def flush(self, *args):
            pytest.fail("unbounded deflate termination")

        def __getattr__(self, name):
            return getattr(self.decoder, name)

    read_magic = np.lib.format.read_magic
    npy_calls = []

    def observe_magic(*args):
        npy_calls.append(True)
        return read_magic(*args)

    monkeypatch.setattr(zlib, "decompressobj", BoundedDecoder)
    monkeypatch.setattr(np.lib.format, "read_magic", observe_magic)
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    assert calls == ([(225, 225)] if method == 8 else [])
    assert npy_calls == []


def cache_zip_layout(
    members,
    *,
    method=0,
    descriptor=None,
    local_zip64=False,
    central_zip64=False,
    footer_zip64=False,
    populated=False,
    prefix=b"",
    comment=b"",
    extension=b"",
    transform_first=None,
    extra_bytes=3,
    raw_names=None,
    path_extras=None,
    utf8=True,
):
    """Independent small ZIP fixture with explicit offsets, sizes and descriptor layouts."""
    import struct
    import zlib

    raw = bytearray(prefix)
    central_records = []
    offsets = {name: [] for name in ("local", "payload", "descriptor", "central")}
    for name, body in members.items():
        filename = (raw_names or {}).get(name, name.encode())
        compression = method if isinstance(method, int) else method[len(central_records)]
        encoder = zlib.compressobj(wbits=-15)
        compressed = body if compression == 0 else encoder.compress(body) + encoder.flush()
        if transform_first is not None and not central_records:
            compressed = transform_first(compressed)
        checksum = zlib.crc32(body)
        flags = (0x800 if utf8 else 0) | (8 if descriptor else 0) | (2 if compression == 8 else 0)
        local_offset = len(raw) - len(prefix)
        offsets["local"].append(len(raw))
        local_size = len(body) if not descriptor or populated else 0
        local_compressed = len(compressed) if not descriptor or populated else 0
        # Unknown, well-formed extra fields and member comments must remain legal.
        extra = struct.pack("<HH", 0xCAFE, extra_bytes) + b"x" * extra_bytes
        extra += (path_extras or {}).get(name, b"")
        local_extra = extra
        if local_zip64:
            local_extra += struct.pack("<HHQQ", 1, 16, local_size, local_compressed)
        raw.extend(
            struct.pack(
                "<4s5H3I2H",
                b"PK\x03\x04",
                45 if local_zip64 else 20,
                flags,
                compression,
                0,
                33,
                checksum if not descriptor or populated else 0,
                0xFFFFFFFF if local_zip64 else local_compressed,
                0xFFFFFFFF if local_zip64 else local_size,
                len(filename),
                len(local_extra),
            )
        )
        raw.extend(filename + local_extra)
        offsets["payload"].append(len(raw))
        raw.extend(compressed)
        offsets["descriptor"].append(len(raw))
        if descriptor:
            if descriptor.startswith("signed"):
                raw.extend(b"PK\x07\x08")
            raw.extend(
                struct.pack(
                    "<IQQ" if descriptor.endswith("64") else "<III",
                    checksum,
                    len(compressed),
                    len(body),
                )
            )
        central_extra = extra
        if central_zip64:
            central_extra += struct.pack("<HHQQQ", 1, 24, len(body), len(compressed), local_offset)
        central_records.append(
            struct.pack(
                "<4s6H3I5H2I",
                b"PK\x01\x02",
                45,
                45,
                flags,
                compression,
                0,
                33,
                checksum,
                0xFFFFFFFF if central_zip64 else len(compressed),
                0xFFFFFFFF if central_zip64 else len(body),
                len(filename),
                len(central_extra),
                3,
                0,
                0,
                0,
                0xFFFFFFFF if central_zip64 else local_offset,
            )
            + filename
            + central_extra
            + b"tag"
        )
    directory_start = len(raw)
    for record in central_records:
        offsets["central"].append(len(raw))
        raw.extend(record)
    directory_size = len(raw) - directory_start
    if footer_zip64:
        footer_start = len(raw)
        raw.extend(
            struct.pack(
                "<4sQ2H2I4Q",
                b"PK\x06\x06",
                44 + len(extension),
                45,
                45,
                0,
                0,
                4,
                4,
                directory_size,
                directory_start - len(prefix),
            )
            + extension
        )
        raw.extend(struct.pack("<4sIQI", b"PK\x06\x07", 0, footer_start - len(prefix), 1))
    offsets["eocd"] = len(raw)
    raw.extend(
        struct.pack(
            "<4s4H2IH",
            b"PK\x05\x06",
            0,
            0,
            4,
            4,
            directory_size,
            directory_start - len(prefix),
            len(comment),
        )
    )
    raw.extend(comment)
    return raw, offsets


def cache_metadata_selection(raw, legacy):
    """Source-derived old/current selection simulation, never an older runtime execution."""
    import struct

    assert len(raw) < 16384 and raw[-22:-18] == b"PK\x05\x06" and raw[-2:] == b"\0\0"
    end = len(raw) - 22
    footer = struct.unpack_from("<4s4H2IH", raw, end)
    directory_size, directory_offset, location = footer[5], footer[6], end
    if raw[end - 20 : end - 16] == b"PK\x06\x07":
        target = struct.unpack_from("<4sIQI", raw, end - 20)[2]
        location = end - 76 if legacy else target
        if not legacy and raw[location : location + 4] != b"PK\x06\x06":
            location = end - 76
        record = struct.unpack_from("<4sQ2H2I4Q", raw, location)
        assert record[0] == b"PK\x06\x06"
        if not legacy:
            assert record[8] + record[9] == target
            assert location + 12 + record[1] == end - 20
        directory_size, directory_offset = record[8:10]
    start = location - directory_size
    position = start
    count = 0
    while position < location:
        fields = struct.unpack_from("<4s6H3I5H2I", raw, position)
        assert fields[0] == b"PK\x01\x02"
        position += 46 + sum(fields[10:13])
        count += 1
        assert count <= 6
    assert position == location
    return start, location, start - directory_offset, count


def cache_zip_metadata_counterexample(members, method, location):
    """Keep real NPY payloads while placing five metadata decoys in one opaque region."""
    import struct

    raw, offsets = cache_zip_layout(members, method=method, footer_zip64=True)
    start, end = offsets["central"][0], offsets["eocd"] - 76
    directory = bytearray(raw[start:end])
    decoys = (
        struct.pack("<4s6H3I5H2I", b"PK\x01\x02", 20, 20, 0, 0, 0, 33, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0)
        + b"x"
    ) * 5

    def zip64_record(count, size, offset, extension=b""):
        return (
            struct.pack(
                "<4sQ2H2I4Q",
                b"PK\x06\x06",
                44 + len(extension),
                45,
                45,
                0,
                0,
                count,
                count,
                size,
                offset,
            )
            + extension
        )

    extension = b""
    if location == "extension":
        decoy_start = end + 56 + 6
        hidden = decoys + zip64_record(5, len(decoys), decoy_start)
        extension = struct.pack("<HI", 0xCAFE, len(hidden)) + hidden
    else:
        last = offsets["central"][-1] - start
        fields = struct.unpack_from("<4s6H3I5H2I", directory, last)
        extra_end = last + 46 + fields[10] + fields[11]
        decoy_start = extra_end + (4 if location == "extra" else 0)
        hidden = decoys + zip64_record(5, len(decoys), decoy_start)
        hidden += struct.pack("<4sIQI", b"PK\x06\x07", 0, decoy_start + len(decoys), 1)
        directory = directory[:extra_end]
        if location == "extra":
            struct.pack_into("<HH", directory, last + 30, fields[11] + 4 + len(hidden), 0)
            directory.extend(struct.pack("<HH", 0xCAFE, len(hidden)) + hidden)
        else:
            struct.pack_into("<H", directory, last + 32, len(hidden))
            directory.extend(hidden)
    footer_start = start + len(directory)
    result = (
        raw[:start]
        + directory
        + zip64_record(4, len(directory), start, extension)
        + struct.pack("<4sIQI", b"PK\x06\x07", 0, footer_start, 1)
        + struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, 4, 4, len(directory), start, 0)
    )
    assert len(result) < 16384
    return result, bytes(directory)


def observe_cache_metadata_view(monkeypatch, directory):
    import zipfile
    from types import SimpleNamespace

    observed = []

    def constructor(stream, *args, **kwargs):
        view = stream.getvalue()
        legacy = cache_metadata_selection(view, True)
        current = cache_metadata_selection(view, False)
        assert legacy[3] == 4, "legacy simulated selector sees five records before public metadata"
        assert current[3] == 4
        assert legacy[:3] == current[:3] == (0, len(directory), 0)
        assert view[: len(directory)] == directory
        archive = zipfile.ZipFile(stream, *args, **kwargs)
        assert archive.comment == b""
        observed.append(archive.infolist())
        return archive

    # Replace only the application's module reference, not the shared stdlib module.
    monkeypatch.setattr(
        engine(), "zipfile", SimpleNamespace(**(vars(zipfile) | {"ZipFile": constructor}))
    )
    return observed


@pytest.mark.parametrize("method", [0, 8, (0, 8, 0, 8)])
def test_cache_metadata_view_is_bounded_across_reader_regimes(monkeypatch, method):
    import io

    members, expected = cache_npy_members(order="F")
    raw, directory = cache_zip_metadata_counterexample(members, method, "extension")
    assert cache_metadata_selection(raw, True)[3] == 5
    assert cache_metadata_selection(raw, False)[3] == 4
    observed = observe_cache_metadata_view(monkeypatch, directory)
    actual, metadata = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    assert len(observed) == 1 and len(observed[0]) == 4 and metadata == {}
    np.testing.assert_array_equal(actual, expected)
    assert actual[0, 3] == 3 / 16 and actual[2, 0] == 8 / 16


@pytest.mark.parametrize("location", ["comment", "extra"])
@pytest.mark.parametrize("method", [0, 8, (0, 8, 0, 8)])
def test_cache_metadata_view_owns_trailer(monkeypatch, location, method):
    import io
    import struct
    import zipfile

    members, expected = cache_npy_members()
    raw, directory = cache_zip_metadata_counterexample(members, method, location)
    assert cache_metadata_selection(raw, False)[3] == 4
    naive = directory + struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, 4, 4, len(directory), 0, 0)
    for legacy in (True, False):
        assert cache_metadata_selection(naive, legacy)[3] == 5
    with zipfile.ZipFile(io.BytesIO(naive)) as archive:
        assert len(archive.infolist()) == 5
    observed = observe_cache_metadata_view(monkeypatch, directory)
    actual, metadata = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    assert len(observed) == 1 and metadata == {}
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("method", [0, 8])
@pytest.mark.parametrize("prefix", [b"", b"p" * 37])
@pytest.mark.parametrize("central_zip64", [False, True])
@pytest.mark.parametrize(
    "normalization",
    [
        "plain",
        "utf8",
        "unicode",
        "cp437_unicode",
        "unicode_bad_crc",
        "unicode_bad_utf8",
        "unicode_truncated",
        "truncated_extra",
        "nul",
        "invalid_utf8_name",
    ],
)
def test_cache_metadata_view_preserves_public_name_normalization(
    monkeypatch, method, prefix, central_zip64, normalization
):
    import io
    import struct
    import zipfile
    import zlib

    members, expected = cache_npy_members(dtype="float32", order="F", version=(2, 0))
    name = b"alpha.npy"
    extra = b""
    utf8 = normalization in {"utf8", "invalid_utf8_name"}
    if "unicode" in normalization:
        name = b"\x82-source" if normalization == "cp437_unicode" else b"raw-alpha"
        checksum = zlib.crc32(name) ^ (1 if normalization == "unicode_bad_crc" else 0)
        value = struct.pack("<BI", 1, checksum) + (
            b"\xff" if normalization == "unicode_bad_utf8" else b"alpha.npy"
        )
        if normalization == "unicode_truncated":
            value = b"\x01\x00"
        extra = struct.pack("<HH", 0x7075, len(value)) + value
    elif normalization == "truncated_extra":
        extra = struct.pack("<HH", 0xCAFE, 2) + b"x"
    elif normalization == "nul":
        name += b"\0ignored"
    elif normalization == "invalid_utf8_name":
        name = b"\xffalpha.npy"
    raw, offsets = cache_zip_layout(
        members,
        method=method,
        prefix=prefix,
        central_zip64=central_zip64,
        footer_zip64=central_zip64,
        raw_names={"alpha.npy": name},
        path_extras={"alpha.npy": extra},
        utf8=utf8,
    )
    end = offsets["eocd"] - (76 if central_zip64 else 0)
    directory = bytes(raw[offsets["central"][0] : end])
    malformed = normalization in {
        "unicode_bad_utf8",
        "unicode_truncated",
        "truncated_extra",
        "invalid_utf8_name",
    }
    if malformed:
        with pytest.raises((zipfile.BadZipFile, UnicodeDecodeError)):
            zipfile.ZipFile(io.BytesIO(raw))
    else:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            original = archive.infolist()
    observed = observe_cache_metadata_view(monkeypatch, directory)
    if malformed or normalization == "unicode_bad_crc":
        monkeypatch.setattr(
            np.lib.format, "read_array", lambda *a, **k: pytest.fail("unsafe NPY allocation")
        )
        with pytest.raises(ValueError):
            engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
        if normalization == "unicode_bad_crc":
            assert observed[0][0].filename == original[0].filename == "raw-alpha"
        return
    actual, metadata = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    assert len(observed) == 1 and metadata == {} and actual.dtype == expected.dtype
    fields = (
        "filename",
        "orig_filename",
        "extra",
        "comment",
        "flag_bits",
        "compress_type",
        "CRC",
        "compress_size",
        "file_size",
        "create_version",
        "create_system",
        "extract_version",
        "reserved",
        "volume",
        "internal_attr",
        "external_attr",
        "date_time",
    )
    for before, after in zip(original, observed[0]):
        assert tuple(getattr(before, field) for field in fields) == tuple(
            getattr(after, field) for field in fields
        )
        assert after.header_offset + len(prefix) == before.header_offset
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("method", [0, 8, (0, 8, 0, 8)])
@pytest.mark.parametrize(
    "layout",
    [
        "ordinary",
        "unsigned32",
        "signed32",
        "unsigned64",
        "signed64",
        "populated",
        "central64",
        "prefix64",
        "extension64",
        "sentinel64",
        "unsigned32-populated",
        "signed32-populated",
        "unsigned64-populated",
    ],
)
def test_cache_supported_zip_layouts_preserve_exact_values(method, layout):
    import io

    members, alpha = cache_npy_members()
    options = {"method": method, "comment": b"ordinary archive comment"}
    base_layout = layout.removesuffix("-populated")
    if base_layout in {"unsigned32", "signed32", "unsigned64", "signed64"}:
        options.update(
            descriptor=base_layout,
            local_zip64=base_layout.endswith("64"),
            populated=layout.endswith("-populated"),
        )
    if layout == "populated":
        options.update(descriptor="signed64", local_zip64=True, populated=True)
    if layout == "central64":
        options.update(central_zip64=True, descriptor="unsigned64")
    if layout == "prefix64":
        options.update(prefix=b"prepended opaque data", local_zip64=True, footer_zip64=True)
    if layout == "extension64":
        options.update(footer_zip64=True, extension=b"opaque extensible bytes")
    if layout == "sentinel64":
        options.update(footer_zip64=True)
    raw, offsets = cache_zip_layout(members, **options)
    if layout == "sentinel64":
        import struct

        struct.pack_into("<HHII", raw, offsets["eocd"] + 8, 65535, 65535, 0xFFFFFFFF, 0xFFFFFFFF)
    actual, metadata = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    np.testing.assert_array_equal(actual, alpha)
    assert metadata == {}


@pytest.mark.parametrize("dtype", ["float32", "float64"])
@pytest.mark.parametrize("order", ["C", "F"])
@pytest.mark.parametrize("version", [(1, 0), (2, 0)])
@pytest.mark.parametrize("method", [0, 8])
def test_cache_npy_order_and_precision_are_preserved(monkeypatch, dtype, order, version, method):
    import io
    import zipfile

    members, expected = cache_npy_members(dtype=dtype, order=order, version=version)
    raw = cache_zip_members(members, method)

    def forbidden(*args, **kwargs):
        pytest.fail("original ZIP passed to a payload reader")

    monkeypatch.setattr(np, "load", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "open", forbidden)
    actual, _ = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)
    assert actual[0, 3] == 3 / 16 and actual[2, 0] == 8 / 16


@pytest.mark.parametrize(
    "damage",
    [
        "local-name",
        "local-method",
        "local-flags",
        "local-size",
        "local-crc",
        "descriptor",
        "descriptor-truncated",
        "duplicate-offset",
        "overlap",
        "zip64-size",
        "directory-size",
    ],
)
def test_cache_container_disagreement_rejects_before_arrays(monkeypatch, damage):
    import io
    import struct

    members, _ = cache_npy_members()
    raw, offsets = cache_zip_layout(
        members,
        descriptor="signed64" if damage.startswith("descriptor") else None,
        local_zip64=damage.startswith("descriptor") or damage == "zip64-size",
    )
    if damage == "local-name":
        raw[30] = ord("x")
    elif damage == "local-method":
        struct.pack_into("<H", raw, 8, 8)
    elif damage == "local-flags":
        struct.pack_into("<H", raw, 6, 0)
    elif damage == "local-size":
        struct.pack_into("<I", raw, 22, 1)
    elif damage == "local-crc":
        struct.pack_into("<I", raw, 14, 1)
    elif damage == "descriptor":
        raw[offsets["descriptor"][0] + 4] ^= 1
    elif damage == "descriptor-truncated":
        struct.pack_into("<I", raw, offsets["central"][1] + 42, offsets["descriptor"][0] + 12)
    elif damage == "duplicate-offset":
        struct.pack_into("<I", raw, offsets["central"][1] + 42, 0)
    elif damage == "overlap":
        for offset in (18, offsets["central"][0] + 20):
            struct.pack_into("<I", raw, offset, offsets["local"][1])
    elif damage == "zip64-size":
        # filename + unknown seven-byte TLV + ZIP64 tag/length, then uncompressed size.
        struct.pack_into("<Q", raw, 30 + len("alpha.npy") + 7 + 4, 1)
    else:
        struct.pack_into("<I", raw, offsets["eocd"] + 12, 1)
    monkeypatch.setattr(
        np.lib.format, "read_array", lambda *a, **k: pytest.fail("unsafe array allocation")
    )
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


@pytest.mark.parametrize("damage", ["truncated", "trailing", "concatenated", "short", "crc"])
def test_cache_deflate_completion_precedes_array_allocation(monkeypatch, damage):
    import io
    import zlib

    members, _ = cache_npy_members()
    encoder = zlib.compressobj(wbits=-15)
    shorter = encoder.compress(members["alpha.npy"][:-1]) + encoder.flush()
    encoder = zlib.compressobj(wbits=-15)
    second = encoder.compress(b"second stream") + encoder.flush()
    transforms = {
        "truncated": lambda payload: payload[:-1],
        "trailing": lambda payload: payload + b"junk",
        "concatenated": lambda payload: payload + second,
        "short": lambda payload: shorter,
        "crc": lambda payload: payload,
    }
    raw, offsets = cache_zip_layout(members, method=8, transform_first=transforms[damage])
    if damage == "crc":
        for offset in (14, offsets["central"][0] + 16):
            raw[offset] ^= 1
    monkeypatch.setattr(
        np.lib.format,
        "read_array",
        lambda *a, **k: pytest.fail("allocation before complete stream validation"),
    )
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


def test_cache_deflate_every_tail_call_has_remaining_sentinel_and_no_flush(monkeypatch):
    import io
    import zlib

    members, expected = cache_npy_members()
    raw = cache_zip_members(members, 8)
    original = zlib.decompressobj
    sizes = list(map(len, members.values()))
    observed = []

    class ObservedDecoder:
        def __init__(self, *args, **kwargs):
            self.decoder = original(*args, **kwargs)
            self.remaining = sizes[len(observed)]
            self.calls = []
            observed.append(self)

        def decompress(self, data, max_length=0):
            assert max_length == self.remaining + 1 and max_length > 0
            # Smaller real output chunks force actual unconsumed-tail resubmission.
            chunk = self.decoder.decompress(data, min(17, max_length))
            self.calls.append((len(data), max_length, len(chunk)))
            self.remaining -= len(chunk)
            return chunk

        def flush(self, *args):
            pytest.fail("deflate flush is never bounded by its length parameter")

        def __getattr__(self, name):
            return getattr(self.decoder, name)

    monkeypatch.setattr(zlib, "decompressobj", ObservedDecoder)
    actual, _ = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    np.testing.assert_array_equal(actual, expected)
    assert len(observed) == 4
    assert all(item.remaining == 0 and len(item.calls) > 1 for item in observed)


@pytest.mark.parametrize("descriptor", ["unsigned32", "signed32", "unsigned64", "signed64"])
@pytest.mark.parametrize("method", [0, 8])
def test_cache_descriptor_crc_equal_to_signature_is_not_misread(descriptor, method):
    import hashlib
    import io
    import struct
    import zlib

    members, _ = cache_npy_members()
    body = bytearray(members["alpha.npy"])
    body[-4:] = b"\0" * 4
    initial = zlib.crc32(body)
    # Solve the independent CRC32 linear system for four suffix bytes. The
    # resulting real NPY alpha has the descriptor signature as its actual CRC.
    basis = {}
    for bit in range(32):
        trial = body.copy()
        trial[-4 + bit // 8] ^= 1 << (bit % 8)
        value, mask = zlib.crc32(trial) ^ initial, 1 << bit
        while value:
            pivot = value.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (value, mask)
                break
            value ^= basis[pivot][0]
            mask ^= basis[pivot][1]
    value, suffix = 0x08074B50 ^ initial, 0
    while value:
        delta, mask = basis[value.bit_length() - 1]
        value ^= delta
        suffix ^= mask
    body[-4:] = struct.pack("<I", suffix)
    assert zlib.crc32(body) == 0x08074B50
    expected = np.frombuffer(body[128:], dtype="<f8").reshape(3, 4)
    assert np.isfinite(expected).all()
    members["alpha.npy"] = bytes(body)
    checksum = io.BytesIO()
    np.lib.format.write_array(
        checksum,
        np.array(hashlib.sha256(expected.tobytes() + b"{}").hexdigest()),
        allow_pickle=False,
    )
    members["sha256.npy"] = checksum.getvalue()
    raw, _ = cache_zip_layout(
        members, method=method, descriptor=descriptor, local_zip64=descriptor.endswith("64")
    )
    actual, _ = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize(
    "damage",
    [
        "dtype",
        "shape",
        "text-shape",
        "text-kind",
        "key-width",
        "key",
        "checksum",
        "nonfinite",
        "npy-trailing",
        "npy-short",
        "header-size",
        "text-size",
    ],
)
def test_cache_npy_and_domain_contract_remains_enforced(monkeypatch, damage):
    import io
    import struct

    members, _ = cache_npy_members()
    values = {
        "dtype": ("alpha.npy", np.ones((3, 4), dtype=np.int32)),
        "shape": ("alpha.npy", np.ones((1, 3, 4))),
        "text-shape": ("metadata.npy", np.array(["{}"])),
        "text-kind": ("metadata.npy", np.array(b"{}")),
        "key-width": ("key.npy", np.array("a" * 63)),
        "key": ("key.npy", np.array("b" * 64)),
        "checksum": ("sha256.npy", np.array("f" * 64)),
        "nonfinite": ("alpha.npy", np.full((3, 4), np.nan)),
    }
    if damage in values:
        name, value = values[damage]
        stream = io.BytesIO()
        np.lib.format.write_array(stream, value, allow_pickle=False)
        members[name] = stream.getvalue()
    elif damage == "npy-trailing":
        members["alpha.npy"] += b"x"
    elif damage == "npy-short":
        members["alpha.npy"] = members["alpha.npy"][:-1]
    elif damage == "header-size":
        members["alpha.npy"] = (
            b"\x93NUMPY\x02\x00" + struct.pack("<I", 10001) + b" " * 10000 + b"\n"
        )
    else:
        stream = io.BytesIO()
        np.lib.format.write_array(stream, np.array("x" * (1024**2 // 4 + 1)), allow_pickle=False)
        members["metadata.npy"] = stream.getvalue()
    raw = cache_zip_members(members)
    if damage not in {"key", "checksum", "nonfinite"}:
        monkeypatch.setattr(
            np.lib.format,
            "read_array",
            lambda *a, **k: pytest.fail("allocation before all headers validated"),
        )
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


@pytest.mark.parametrize(
    "damage",
    [
        "comment-length",
        "trailing-signature",
        "zip64-target",
        "zip64-count",
        "zip64-size",
        "zip64-disk",
    ],
)
def test_cache_footer_divergence_rejects_before_metadata(monkeypatch, damage):
    import io
    import struct
    import zipfile

    members, _ = cache_npy_members()
    raw, offsets = cache_zip_layout(
        members, footer_zip64=damage.startswith("zip64"), comment=b"comment"
    )
    end = offsets["eocd"]
    if damage == "comment-length":
        struct.pack_into("<H", raw, end + 20, 1)
    elif damage == "trailing-signature":
        raw[-4:] = b"PK\x05\x06"
    elif damage == "zip64-target":
        struct.pack_into("<Q", raw, end - 12, end)
    elif damage == "zip64-count":
        struct.pack_into("<Q", raw, end - 76 + 24, 5)
    elif damage == "zip64-size":
        struct.pack_into("<Q", raw, end - 76 + 4, 45)
    else:
        struct.pack_into("<I", raw, end - 16, 1)

    def forbidden(*args, **kwargs):
        pytest.fail("metadata allocated for a divergent footer")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    monkeypatch.setattr(zipfile, "ZipInfo", forbidden)
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


@pytest.mark.parametrize("compressed", [False, True])
def test_cache_actual_numpy_producers_keep_fortran_values(compressed):
    import hashlib
    import io

    _, expected = cache_npy_members(order="F")
    stream = io.BytesIO()
    (np.savez_compressed if compressed else np.savez)(
        stream,
        alpha=expected,
        metadata="{}",
        key="a" * 64,
        sha256=hashlib.sha256(expected.tobytes() + b"{}").hexdigest(),
    )
    actual, _ = engine()._read_tile_prediction(stream, "a" * 64)
    np.testing.assert_array_equal(actual, expected)


def test_cache_maximum_metadata_lengths_and_embedded_four_record_footer():
    import io
    import struct

    members, expected = cache_npy_members()
    raw, _ = cache_zip_layout(members, comment=b"x" * 65535, extra_bytes=65531)
    actual, _ = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    np.testing.assert_array_equal(actual, expected)
    ordinary = cache_zip_members(members)
    directory = ordinary[ordinary.index(b"PK\x01\x02") : -22]
    raw = bytearray(ordinary)
    struct.pack_into("<H", raw, len(raw) - 2, len(directory) + 22 + 7)
    directory_start = len(raw)
    raw.extend(directory)
    raw.extend(
        struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, 4, 4, len(directory), directory_start, 7)
    )
    raw.extend(b"comment")
    actual, _ = engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)
    np.testing.assert_array_equal(actual, expected)


def test_cache_selected_zip64_direct_record_cannot_fall_back(monkeypatch):
    import io
    import struct
    import zipfile

    members, _ = cache_npy_members()
    raw, offsets = cache_zip_layout(members, footer_zip64=True, prefix=b"p" * 4096)
    selected = struct.unpack_from("<Q", raw, offsets["eocd"] - 12)[0]
    assert selected + 56 < 4096  # The competing record is wholly in opaque prefix bytes.
    raw[selected : selected + 56] = struct.pack(
        "<4sQ2H2I4Q", b"PK\x06\x06", 44, 45, 45, 0, 0, 4, 4, 0, 0
    )

    def forbidden(*args, **kwargs):
        pytest.fail("metadata allocated before selected ZIP64 target rejection")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    with pytest.raises(ValueError):
        engine()._read_tile_prediction(io.BytesIO(raw), "a" * 64)


def test_cache_outer_ceiling_is_enforced_before_metadata(monkeypatch):
    import io
    import zipfile

    raw = io.BytesIO(b"x" * (11 * 1024**2 + 4 * 10000 + 1))

    def forbidden(*args, **kwargs):
        pytest.fail("metadata allocation for oversized archive")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    with pytest.raises(ValueError, match="Oversized"):
        engine()._read_tile_prediction(raw, "a" * 64)


def test_successful_tile_cache_has_one_name_and_one_link(tmp_path):
    rgb = np.zeros((31, 1025, 3), dtype=np.uint8)
    guide = np.full(rgb.shape[:2], 128, dtype=np.uint8)
    alpha, record = engine().native_matte(
        rgb,
        guide,
        lambda rgb, guide, device: (np.full(guide.shape, 0.25), {"device": device}),
        "cpu",
        cache_dir=tmp_path,
        cache_identity=cache_identity(),
    )
    assert np.all(alpha == 16384)
    assert record["inferred_tiles"] == 2
    entries = sorted(tmp_path.glob("*.npz"))
    assert len(entries) == 2
    assert not list(tmp_path.glob(".tile-*"))
    assert all(entry.stat().st_nlink == 1 for entry in entries)
    for entry in entries:
        with np.load(entry, allow_pickle=False) as data:
            assert np.all(data["alpha"] == 0.25)
            assert str(data["key"]) == entry.stem


@pytest.mark.parametrize("collision", ["symlink", "dangling", "directory", "fifo"])
def test_tile_cache_rejects_nonregular_destination(tmp_path, collision):
    rgb = np.zeros((3, 4, 3), dtype=np.uint8)
    guide = np.full((3, 4), 128, dtype=np.uint8)
    predict = lambda rgb, guide, device: (np.full(guide.shape, 0.25), {})
    engine().native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    entry = next(tmp_path.glob("*.npz"))
    preserved = tmp_path / "preserved"
    entry.rename(preserved)
    if collision == "directory":
        entry.mkdir()
    elif collision == "fifo":
        import os

        os.mkfifo(entry)
    else:
        entry.symlink_to(preserved if collision == "symlink" else tmp_path / "absent")
    before = preserved.read_bytes()
    with pytest.raises(ValueError, match="[Cc]ache|[Dd]estination|[Pp]rediction"):
        engine().native_matte(
            rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
        )
    assert preserved.read_bytes() == before


def test_corrupt_regular_cache_preserved_and_publication_reported(tmp_path):
    rgb = np.zeros((3, 4, 3), dtype=np.uint8)
    guide = np.full((3, 4), 128, dtype=np.uint8)
    predict = lambda rgb, guide, device: (np.full(guide.shape, 0.25), {})
    engine().native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    entry = next(tmp_path.glob("*.npz"))
    entry.write_bytes(b"retained corrupt regular prediction")
    alpha, result = engine().native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    assert np.all(alpha == 16384)
    assert entry.read_bytes() == b"retained corrupt regular prediction"
    assert result["tiles"][0]["cache_publication"] == "skipped_corrupt_existing"
    assert list(tmp_path.glob(".tile-*"))


@pytest.mark.parametrize("failure", ["arrival", "rename", "sync"])
def test_tile_publication_failure_preserves_visible_state(tmp_path, monkeypatch, failure):
    from blackmask import project

    rename = project._exclusive_rename
    published = []

    def publish(source, destination, **kwargs):
        if failure == "arrival":
            destination.write_bytes(b"arriving owner")
        if failure == "rename":
            raise OSError("injected unsupported rename")
        rename(source, destination, **kwargs)
        published.append(destination)

    sync = project._sync_directory

    def synchronize(path):
        if failure == "sync" and published:
            raise OSError("injected post-publication sync")
        sync(path)

    monkeypatch.setattr(project, "_exclusive_rename", publish)
    monkeypatch.setattr(project, "_sync_directory", synchronize)
    rgb = np.zeros((3, 4, 3), dtype=np.uint8)
    guide = np.full((3, 4), 128, dtype=np.uint8)
    with pytest.raises((ValueError, OSError), match="collision|rename|durability"):
        engine().native_matte(
            rgb,
            guide,
            lambda *args: (np.full((3, 4), 0.25), {}),
            "cpu",
            cache_dir=tmp_path,
            cache_identity=cache_identity(),
        )
    entries = list(tmp_path.glob("*.npz"))
    if failure == "sync":
        assert len(entries) == 1 and not list(tmp_path.glob(".tile-*"))
        assert entries[0].stat().st_nlink == 1
        with np.load(entries[0], allow_pickle=False) as data:
            assert np.all(data["alpha"] == 0.25)
    else:
        assert list(tmp_path.glob(".tile-*"))
        assert [p.read_bytes() for p in entries] == (
            [b"arriving owner"] if failure == "arrival" else []
        )


@pytest.mark.parametrize("invalid", ["extra", "duplicate", "object", "huge", "metadata"])
def test_cache_parser_rejects_unsafe_structures_before_array_load(tmp_path, invalid, monkeypatch):
    import hashlib
    import io
    import zipfile

    values = np.full((3, 4), 0.25)
    metadata = "[]" if invalid == "metadata" else "{}"
    members = {
        "alpha": values,
        "metadata": metadata,
        "key": "a" * 64,
        "sha256": hashlib.sha256(values.tobytes() + metadata.encode()).hexdigest(),
    }
    if invalid == "extra":
        members["unknown"] = np.zeros(1)
    if invalid == "object":
        members["alpha"] = np.array([[object()]], dtype=object)
    target = tmp_path / "prediction.npz"
    np.savez(target, **members)
    if invalid in {"duplicate", "huge"}:
        with zipfile.ZipFile(target, "a") as archive:
            if invalid == "duplicate":
                with pytest.warns(UserWarning):
                    archive.writestr("alpha.npy", archive.read("alpha.npy"))
            else:
                stream = io.BytesIO()
                np.lib.format.write_array_header_1_0(
                    stream, {"descr": "<f8", "fortran_order": False, "shape": (2**40, 2**40)}
                )
                # Keep a distinct archive without the normal alpha member.
                other = {
                    name: archive.read(name) for name in archive.namelist() if name != "alpha.npy"
                }
        if invalid == "huge":
            target = tmp_path / "huge.npz"
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("alpha.npy", stream.getvalue())
                for name, value in other.items():
                    archive.writestr(name, value)
    if invalid != "metadata":
        monkeypatch.setattr(
            np.lib.format, "read_array", lambda *a, **k: pytest.fail("unsafe allocation attempted")
        )
    with target.open("rb") as stream, pytest.raises(ValueError):
        engine()._read_tile_prediction(stream, "a" * 64)


@pytest.mark.parametrize("boundary", ["write", "sync", "readback"])
def test_tile_prepublication_failure_retains_diagnostic(tmp_path, monkeypatch, boundary):
    import os

    matte = engine()
    allocate = matte.tempfile.mkstemp
    synchronize = os.fsync
    tile_descriptor = []

    def allocate_tile(*args, **kwargs):
        descriptor, name = allocate(*args, **kwargs)
        if kwargs.get("prefix") == ".tile-":
            tile_descriptor.append(descriptor)
        return descriptor, name

    def sync(descriptor):
        if boundary == "sync" and descriptor in tile_descriptor:
            raise OSError("injected tile sync")
        synchronize(descriptor)

    def write(stream, **arrays):
        stream.write(b"retained invalid partial serialization")
        if boundary == "write":
            raise OSError("injected tile write")

    monkeypatch.setattr(matte.tempfile, "mkstemp", allocate_tile)
    monkeypatch.setattr(os, "fsync", sync)
    if boundary != "sync":
        monkeypatch.setattr(np, "savez", write)
    with pytest.raises((ValueError, OSError), match="tile|zip|ZIP|failed"):
        matte.native_matte(
            np.zeros((3, 4, 3), dtype=np.uint8),
            np.full((3, 4), 128, dtype=np.uint8),
            lambda *args: (np.full((3, 4), 0.25), {}),
            "cpu",
            cache_dir=tmp_path,
            cache_identity=cache_identity(),
        )
    assert list(tmp_path.glob(".tile-*")) and not list(tmp_path.glob("*.npz"))


@pytest.mark.parametrize("compression", ["ZIP_STORED", "ZIP_DEFLATED"])
def test_cache_parser_preserves_supported_zip_formats(compression):
    import hashlib
    import io
    import zipfile

    alpha = np.full((3, 4), 0.25)
    stream = io.BytesIO()
    np.savez(
        stream,
        alpha=alpha,
        metadata="{}",
        key="a" * 64,
        sha256=hashlib.sha256(alpha.tobytes() + b"{}").hexdigest(),
    )
    compressed = io.BytesIO()
    with (
        zipfile.ZipFile(stream) as original,
        zipfile.ZipFile(compressed, "w", compression=getattr(zipfile, compression)) as target,
    ):
        for name in original.namelist():
            target.writestr(name, original.read(name))
    decoded, metadata = engine()._read_tile_prediction(compressed, "a" * 64)
    np.testing.assert_array_equal(decoded, alpha)
    assert metadata == {}


@pytest.mark.parametrize(
    "damage",
    ["deflate", "lzma", "encrypted", "unsupported-compression", "bzip2-valid", "lzma-valid"],
)
def test_invalid_zip_envelope_is_protected_and_recomputed(tmp_path, damage):
    import hashlib
    import io
    import json
    import struct
    import zipfile

    from test_project import create

    from blackmask import operations

    _, project = create(tmp_path)
    cache = project / "cache/matte"
    pixels = np.zeros((3, 4, 3), dtype=np.uint8)
    guide = np.full((3, 4), 128, dtype=np.uint8)
    predict = lambda *args: (np.full((3, 4), 0.25), {})
    engine().native_matte(
        pixels, guide, predict, "cpu", cache_dir=cache, cache_identity=cache_identity()
    )
    entry = next(cache.glob("*.npz"))
    alpha = np.full((3, 4), 0.25)
    stream = io.BytesIO()
    np.savez_compressed(
        stream,
        alpha=alpha,
        metadata="{}",
        key=entry.stem,
        sha256=hashlib.sha256(alpha.tobytes() + b"{}").hexdigest(),
    )
    original = stream.getvalue()
    if damage in {"lzma", "bzip2-valid", "lzma-valid"}:
        compressed = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(original)) as source,
            zipfile.ZipFile(
                compressed,
                "w",
                compression=zipfile.ZIP_BZIP2 if damage == "bzip2-valid" else zipfile.ZIP_LZMA,
            ) as target,
        ):
            for name in source.namelist():
                target.writestr(name, source.read(name))
        original = compressed.getvalue()
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        local = archive.getinfo("alpha.npy").header_offset
        central = archive.start_dir
    damaged = bytearray(original)
    if damage in {"deflate", "lzma"}:
        header = struct.unpack("<4s5H3I2H", original[local : local + 30])
        payload = local + 30 + header[-2] + header[-1]
        # ZIP LZMA properties start after the four-byte method header.
        damaged[payload + (4 if damage == "lzma" else 0)] = 0xFF
    elif damage == "encrypted":
        struct.pack_into("<H", damaged, local + 6, 1)
        struct.pack_into("<H", damaged, central + 8, 1)
    elif damage == "unsupported-compression":
        struct.pack_into("<H", damaged, local + 8, 99)
        struct.pack_into("<H", damaged, central + 10, 99)
    entry.write_bytes(damaged)
    original_mode = entry.stat().st_mode
    with entry.open("rb") as saved, pytest.raises(ValueError, match="cache"):
        engine()._read_tile_prediction(saved, entry.stem)
    inspected = operations.inspect_processing_cache(project)
    assert inspected["candidates"] == [] and inspected["blockers"] == []
    assert str(entry.relative_to(project)) in {item["path"] for item in inspected["protected"]}
    if damage in {"lzma", "bzip2-valid", "lzma-valid"}:
        from test_cli import run

        inspected_cli = run("cache", "inspect", project)
        assert inspected_cli.returncode == 0, inspected_cli.stderr
        assert json.loads(inspected_cli.stdout)["protected"] == inspected["protected"]
        cleared_cli = run("cache", "clear", project, "--confirm", inspected["candidate_digest"])
        assert cleared_cli.returncode == 0, cleared_cli.stderr
        assert json.loads(cleared_cli.stdout)["removed"] == []
    cleared = operations.clear_processing_cache(project, inspected["candidate_digest"])
    assert cleared["removed"] == [] and entry.read_bytes() == damaged
    for attempt in range(2 if damage.endswith("valid") else 1):
        result, record = engine().native_matte(
            pixels, guide, predict, "cpu", cache_dir=cache, cache_identity=cache_identity()
        )
        assert np.all(result == 16384) and record["inferred_tiles"] == 1
        assert record["tiles"][0]["cache_publication"] == "skipped_corrupt_existing"
        assert entry.read_bytes() == damaged and entry.stat().st_mode == original_mode
        diagnostics = list(cache.glob(".tile-*"))
        assert len(diagnostics) == attempt + 1
        for diagnostic in diagnostics:
            with diagnostic.open("rb") as stream:
                actual, metadata = engine()._read_tile_prediction(stream, entry.stem, (3, 4))
            np.testing.assert_array_equal(actual, np.full((3, 4), 0.25))
            assert metadata == {}


@pytest.mark.parametrize(
    "length,expected",
    [(17, [0]), (1024, [0]), (1025, [0, 1]), (1793, [0, 768, 769]), (2049, [0, 768, 1025])],
)
def test_native_boundary_origins(length, expected):
    assert engine().tile_origins(length) == expected


def test_native_merge_known_bypass_clamp_and_positive_weights():
    matte = engine()
    pixels = np.zeros((1031, 1793, 3), dtype=np.uint8)
    trimap = np.full(pixels.shape[:2], 128, dtype=np.uint8)
    trimap[:2] = 0
    trimap[-2:] = 255
    calls = []

    def predict(rgb, guide, device):
        calls.append((rgb.shape, device))
        return np.full(guide.shape, 0.25), {"device": device}

    alpha, record = matte.native_matte(pixels, trimap, predict, "cpu")
    assert np.all(alpha[:2] == 0) and np.all(alpha[-2:] == 65535)
    assert np.all(alpha[2:-2] == 16384)
    assert record["minimum_weight"] > 0 and len(calls) == 6
    assert all(shape == (1024, 1024, 3) for shape, _ in calls)
    known = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    result, record = matte.native_matte(
        np.zeros((2, 2, 3), dtype=np.uint8),
        known,
        lambda *args: pytest.fail("known tile inference"),
        "cpu",
    )
    np.testing.assert_array_equal(result, known.astype(np.uint16) * 257)
    assert record["inferred_tiles"] == 0


def test_nonfinite_rejected_and_auto_restarts_entire_geometry():
    matte = engine()
    rgb = np.zeros((19, 1025, 3), dtype=np.uint8)
    guide = np.full((19, 1025), 128, dtype=np.uint8)
    with pytest.raises(ValueError, match="finite|failed"):
        matte.native_matte(rgb, guide, lambda *args: (np.full(args[1].shape, np.nan), {}), "cpu")
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        if device == "mps" and calls.count("mps") == 2:
            raise RuntimeError("injected backend failure")
        return np.full(guide.shape, 0.9 if device == "mps" else 0.25), {}

    alpha, record = matte.native_matte(rgb, guide, predict, "auto", auto_mps=True)
    assert calls == ["mps", "mps", "cpu", "cpu"]
    assert np.all(alpha == 16384) and record["device"] == "cpu"
    assert "injected" in record["fallback"]


def test_scalar_render_exact_independent_sentinels_and_straight_view():
    export = importlib.import_module("blackmask.export")
    foreground = np.array(
        [[[65535, 5, 7], [12345, 257, 65535], [65535, 65535, 65535]]], dtype=np.uint16
    )
    alpha = np.array([[32768, 0, 65535]], dtype=np.uint16)
    actual = export.render_black(foreground, alpha)
    np.testing.assert_array_equal(
        actual, np.array([[[32768, 3, 4], [0, 0, 0], [65535, 65535, 65535]]], dtype=np.uint16)
    )
    rgba = export.view_rgba(foreground, alpha)
    assert rgba[0, 0, 0] == 255 and rgba[0, 1, 0] == 48
    assert rgba[0, 0, 3] == 128 and rgba[0, 1, 3] == 0


def test_tile_cache_hash_validation_and_device_separation(tmp_path):
    matte = engine()
    rgb = np.zeros((17, 1025, 3), dtype=np.uint8)
    guide = np.full(rgb.shape[:2], 128, dtype=np.uint8)
    calls = []

    def predict(rgb, guide, device):
        calls.append(device)
        return np.full(guide.shape, 0.4), {"device": device}

    first, _ = matte.native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    second, record = matte.native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    assert calls == ["cpu", "cpu"] and record["reused_tiles"] == 2
    np.testing.assert_array_equal(first, second)
    saved_raster(next(tmp_path.glob("*.npz"))).write_bytes(b"corrupt")
    matte.native_matte(
        rgb, guide, predict, "cpu", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    assert len(calls) == 3
    matte.native_matte(
        rgb, guide, predict, "mps", cache_dir=tmp_path, cache_identity=cache_identity()
    )
    assert calls[-2:] == ["mps", "mps"]


def test_vitmatte_missing_assets_no_network(tmp_path):
    from blackmask import models

    with (
        patch("urllib.request.urlopen", side_effect=AssertionError("hidden download")),
        pytest.raises(ValueError, match="missing|setup|hash"),
    ):
        models.VitMatteSession(tmp_path)


@pytest.mark.integration
def test_real_cpu_vitmatte_native_pad_unpad_normalization():
    import os
    from pathlib import Path

    from blackmask import models

    cache = os.environ.get("BLACKMASK_VITMATTE_CACHE")
    if not cache:
        pytest.skip("Set BLACKMASK_VITMATTE_CACHE to explicitly installed pinned assets")
    session = models.VitMatteSession(Path(cache))
    rgb = np.zeros((65, 97, 3), dtype=np.uint8)
    rgb[10:50, 20:70] = [200, 100, 50]
    guide = np.full((65, 97), 128, dtype=np.uint8)
    guide[:3] = 0
    guide[-3:] = 255
    alpha, record = session.predict(rgb, guide, "cpu")
    assert alpha.shape == (65, 97) and np.isfinite(alpha).all()
    assert record["pixel_values_shape"] == [1, 4, 96, 128]
    assert record["output_shape"] == [1, 1, 96, 128]
    assert record["padding_ltrb"] == [0, 0, 31, 31]
    assert (
        record["dtype"] == "float32"
        and record["device"] == "cpu"
        and record["attention"] == "eager"
    )
    assert record["corner_tensor"] == [-1.0, -1.0, -1.0, 0.0]
    assert record["normalization"]["mean"] == [0.5, 0.5, 0.5]
    assert np.isclose(record["unknown_tensor"], 128 / 255)


def test_existing_empty_output_directory_is_never_replaced(tmp_path):
    from blackmask.project import ProjectError, _publish_new_directory

    source = tmp_path / "stage"
    source.mkdir()
    (source / "complete").write_text("saved")
    destination = tmp_path / "already-owned"
    destination.mkdir()
    with pytest.raises(ProjectError, match="collision|exists"):
        _publish_new_directory(source, destination)
    assert source.is_dir() and destination.is_dir() and not list(destination.iterdir())


def test_spatial_tile_registration_and_independent_sine_blend_sentinels():
    import math

    matte = engine()
    width, height = 1793, 7
    x = np.arange(width)
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = x % 256
    rgb[..., 1] = x // 256
    rgb[..., 2] = np.arange(height)[:, None]
    trimap = np.full((height, width), 128, dtype=np.uint8)
    seen = []

    def predict(crop, guide, device):
        origin = int(crop[0, 0, 0]) + 256 * int(crop[0, 0, 1])
        seen.append(origin)
        np.testing.assert_array_equal(crop, rgb[:, origin : origin + 1024])
        local_x = np.arange(1024)[None, :]
        row = np.arange(height)[:, None]
        return 0.2 + 0.0005 * local_x + 0.01 * row, {}

    alpha, record = matte.native_matte(rgb, trimap, predict, "cpu")
    assert seen == [0, 768, 769] and record["minimum_weight"] > 0
    for sample_x in [0, 100, 768, 769, 800, 900, 1000, 1023, 1024, 1200, 1536, 1700, 1791, 1792]:
        for sample_y in [0, 3, 6]:
            # Independent scalar cases for these three hand-derived tile bounds.
            operands = []
            if sample_x < 1024:
                weight = (
                    1.0
                    if sample_x < 768
                    else math.sin((1023 - sample_x + 0.5) / 256 * math.pi / 2) ** 2
                )
                operands.append((weight, 0.2 + 0.0005 * sample_x + 0.01 * sample_y))
            if 768 <= sample_x < 1792:
                local = sample_x - 768
                weight = 1.0
                if local < 256:
                    weight *= math.sin((local + 0.5) / 256 * math.pi / 2) ** 2
                if local >= 768:
                    weight *= math.sin((1023 - local + 0.5) / 256 * math.pi / 2) ** 2
                operands.append((weight, 0.2 + 0.0005 * local + 0.01 * sample_y))
            if sample_x >= 769:
                local = sample_x - 769
                weight = 1.0 if local >= 256 else math.sin((local + 0.5) / 256 * math.pi / 2) ** 2
                operands.append((weight, 0.2 + 0.0005 * local + 0.01 * sample_y))
            expected = round(sum(w * v for w, v in operands) / sum(w for w, _ in operands) * 65535)
            assert alpha[sample_y, sample_x] == expected, (sample_x, sample_y)


def test_finite_extremes_clamp_before_single_alpha16_quantization():
    rgb = np.zeros((1, 3, 3), dtype=np.uint8)
    guide = np.full((1, 3), 128, dtype=np.uint8)
    alpha, _ = engine().native_matte(
        rgb, guide, lambda *args: (np.array([[-0.25, 0.4, 1.25]]), {}), "cpu"
    )
    np.testing.assert_array_equal(alpha, [[0, 26214, 65535]])
