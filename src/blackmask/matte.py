"""Native tiling and one quantization boundary, independent of model execution."""

import hashlib
import io
import json
import os
import stat
import struct
import tempfile
import uuid
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np

from .models import run_device_stage

TILE_SIZE = 1024
OVERLAP = 256
STRIDE = TILE_SIZE - OVERLAP


def _cache_file_identity(value: os.stat_result) -> dict[str, int]:
    """Fresh identity excludes access time, which inspection itself may update."""
    return {
        name: getattr(value, name)
        for name in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
            "st_nlink",
        )
    }


_CACHE_HEADER_LIMIT = 10000
_CACHE_ARCHIVE_LIMIT = TILE_SIZE**2 * 11 + 4 * _CACHE_HEADER_LIMIT


@dataclass(frozen=True)
class _TileCacheMember:
    name: bytes
    flags: int
    method: int
    checksum: int
    compressed_size: int
    size: int
    header_offset: int
    zip64_sizes: bool


def _tile_cache_directory(snapshot: bytes) -> tuple[int, int, int, bytes]:
    """Select and validate the original footer before public metadata allocation."""
    # Use the no-comment fast path, then the last-signature search. Never fall
    # back to an earlier, apparently valid EOCD hidden by a later signature.
    end = len(snapshot) - 22
    if end < 0:
        raise ValueError("Truncated tile cache footer")
    if snapshot[end : end + 4] != b"PK\x05\x06" or snapshot[-2:] != b"\0\0":
        end = snapshot.rfind(b"PK\x05\x06", max(0, len(snapshot) - 65535 - 22))
    if end < 0 or end + 22 > len(snapshot):
        raise ValueError("Missing tile cache footer")
    footer = struct.unpack_from("<4s4H2IH", snapshot, end)
    if end + 22 + footer[7] != len(snapshot):
        raise ValueError("Invalid tile cache comment extent")
    comment = snapshot[end + 22 :]
    disk, directory_disk, disk_count, count, size, offset = footer[1:7]
    location = end
    locator = end - 20
    if locator >= 0 and snapshot[locator : locator + 4] == b"PK\x06\x07":
        _, locator_disk, recorded_location, disks = struct.unpack_from("<4sIQI", snapshot, locator)
        fixed_location = locator - 56
        if locator_disk != 0 or disks > 1 or not 0 <= recorded_location <= fixed_location:
            raise ValueError("Invalid tile cache ZIP64 locator")
        location = recorded_location
        # This is the retained reader's direct-target/fixed-prefixed fallback,
        # not a scan for another valid record after a selected one fails.
        if snapshot[location : location + 4] != b"PK\x06\x06" and location != fixed_location:
            location = fixed_location
        record = struct.unpack_from("<4sQ2H2I4Q", snapshot, location)
        if (
            record[0] != b"PK\x06\x06"
            or location + 12 + record[1] != locator
            or record[8] + record[9] != recorded_location
        ):
            raise ValueError("Invalid tile cache ZIP64 footer")
        resolved = record[4:10]
        for declared, actual, sentinel in zip(
            footer[1:7], resolved, (65535,) * 4 + (0xFFFFFFFF,) * 2
        ):
            if declared not in (actual, sentinel):
                raise ValueError("Contradictory tile cache ZIP64 footer")
        disk, directory_disk, disk_count, count, size, offset = resolved
    start = location - size
    origin = start - offset
    if disk != 0 or directory_disk != 0 or disk_count != 4 or count != 4 or start < 0 or origin < 0:
        raise ValueError("Invalid tile cache directory")
    return start, location, origin, comment


def _tile_cache_zip64_values(extra: bytes, values: tuple[int, ...]) -> tuple[int, ...]:
    """Resolve only sentinel fields, in the ZIP64 size/offset/disk order."""
    resolved = list(values)
    needed = [value == (65535 if index == 3 else 0xFFFFFFFF) for index, value in enumerate(values)]
    position = 0
    while position < len(extra):
        if position + 4 > len(extra):
            raise ValueError("Truncated tile cache extra field")
        kind, size = struct.unpack_from("<HH", extra, position)
        position += 4
        end = position + size
        if end > len(extra):
            raise ValueError("Truncated tile cache extra field")
        if kind == 1:
            cursor = position
            for index, required in enumerate(needed):
                if required:
                    width = 4 if index == 3 else 8
                    if cursor + width > end:
                        raise ValueError("Truncated tile cache ZIP64 values")
                    resolved[index] = struct.unpack_from(
                        "<I" if width == 4 else "<Q", extra, cursor
                    )[0]
                    cursor += width
                    needed[index] = False
        position = end
    if any(needed):
        raise ValueError("Missing tile cache ZIP64 values")
    return tuple(resolved)


def _tile_cache_payload(snapshot: bytes, member: _TileCacheMember, boundary: int) -> bytes:
    """Validate local header, payload and descriptor ownership without decoding."""
    start = member.header_offset
    if start < 0 or start + 30 > boundary:
        raise ValueError("Overlapping tile cache header")
    header = struct.unpack_from("<4s5H3I2H", snapshot, start)
    name_start = start + 30
    extra_start = name_start + header[9]
    payload_start = extra_start + header[10]
    payload_end = payload_start + member.compressed_size
    if (
        header[0] != b"PK\x03\x04"
        or header[2] != member.flags
        or header[3] != member.method
        or not payload_start <= payload_end <= boundary
        or snapshot[name_start:extra_start] != member.name
    ):
        raise ValueError("Invalid tile cache local header or payload extent")
    size, compressed_size = _tile_cache_zip64_values(
        snapshot[extra_start:payload_start], (header[8], header[7])
    )
    if member.flags & 8:
        if (
            header[6] not in (0, member.checksum)
            or size not in (0, member.size)
            or compressed_size not in (0, member.compressed_size)
        ):
            raise ValueError("Contradictory tile cache streaming header")
        zip64 = member.zip64_sizes or header[7] == 0xFFFFFFFF or header[8] == 0xFFFFFFFF
        descriptor_ends = set()
        for width in (8,) if zip64 else (4, 8):
            for signed in (False, True):
                cursor = payload_end
                if signed:
                    if snapshot[cursor : cursor + 4] != b"PK\x07\x08":
                        continue
                    cursor += 4
                end = cursor + 4 + 2 * width
                if end <= boundary and struct.unpack_from(
                    "<IQQ" if width == 8 else "<III", snapshot, cursor
                ) == (member.checksum, member.compressed_size, member.size):
                    descriptor_ends.add(end)
        if len(descriptor_ends) != 1:
            raise ValueError("Missing, ambiguous or contradictory tile cache descriptor")
    elif (header[6], compressed_size, size) != (
        member.checksum,
        member.compressed_size,
        member.size,
    ):
        raise ValueError("Contradictory tile cache local sizes or checksum")
    return snapshot[payload_start:payload_end]


def _decode_tile_cache_member(payload: bytes, member: _TileCacheMember) -> bytes:
    if member.method == zipfile.ZIP_STORED:
        if len(payload) != member.size:
            raise ValueError("Invalid stored tile cache length")
        decoded = payload
    else:
        decoder = zlib.decompressobj(wbits=-15)
        result = bytearray()
        pending = payload
        while True:
            # A positive sentinel allowance is mandatory, including empty-input
            # drains. flush(length) is not an output cap and must not be used.
            chunk = decoder.decompress(pending, member.size - len(result) + 1)
            result.extend(chunk)
            if len(result) > member.size:
                raise ValueError("Excess tile cache decompression output")
            if decoder.eof:
                if decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError("Trailing tile cache compressed data")
                break
            tail = decoder.unconsumed_tail
            if not chunk and (not tail or tail == pending):
                raise ValueError("Truncated or stalled tile cache compressed data")
            pending = tail
        decoded = bytes(result)
    if len(decoded) != member.size or zlib.crc32(decoded) != member.checksum:
        raise ValueError("Invalid tile cache decoded length or checksum")
    return decoded


def _tile_cache_arrays(snapshot: bytes) -> dict[str, bytes]:
    start, end, origin, _ = _tile_cache_directory(snapshot)
    records = []
    position = start
    for _ in range(4):
        if position + 46 > end:
            raise ValueError("Truncated tile cache central directory")
        fields = struct.unpack_from("<4s6H3I5H2I", snapshot, position)
        name_start = position + 46
        extra_start = name_start + fields[10]
        extra_end = extra_start + fields[11]
        position = extra_end + fields[12]
        if fields[0] != b"PK\x01\x02" or position > end:
            raise ValueError("Invalid tile cache central record")
        records.append((fields, snapshot[name_start:extra_start], snapshot[extra_start:extra_end]))
    if position != end:
        raise ValueError("Excess tile cache central records")
    # No public ZIP constructor, CRC routine or payload/NPY reader precedes this
    # whole-directory policy gate, even when the unsupported method comes last.
    if any(fields[4] not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for fields, _, _ in records):
        raise ValueError("Unsupported tile cache compression")
    members = []
    for fields, name, extra in records:
        allowed_flags = 0x800 | 8 | (6 if fields[4] == zipfile.ZIP_DEFLATED else 0)
        size, compressed_size, local_offset, disk = _tile_cache_zip64_values(
            extra, (fields[9], fields[8], fields[16], fields[13])
        )
        if fields[3] & ~allowed_flags or disk != 0:
            raise ValueError("Unsupported tile cache flags or disk")
        members.append(
            _TileCacheMember(
                name,
                fields[3],
                fields[4],
                fields[7],
                compressed_size,
                size,
                local_offset + origin,
                fields[8] == 0xFFFFFFFF or fields[9] == 0xFFFFFFFF,
            )
        )
    offsets = sorted(member.header_offset for member in members)
    if len(set(offsets)) != 4 or offsets[0] < 0 or offsets[-1] >= start:
        raise ValueError("Invalid tile cache member offsets")
    boundaries = dict(zip(offsets, offsets[1:] + [start]))
    payloads = []
    directory_size = end - start
    # Earlier Python 3.12 readers select ZIP64 records differently. A trusted
    # fixed trailer makes both selectors see only the already admitted records,
    # even when the last central comment/extra contains a forged ZIP64 locator.
    metadata_view = (
        snapshot[start:end]
        + struct.pack("<4sQ2H2I4Q", b"PK\x06\x06", 44, 45, 45, 0, 0, 4, 4, directory_size, 0)
        + struct.pack("<4sIQI", b"PK\x06\x07", 0, directory_size, 1)
        + struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, 4, 4, directory_size, 0, 0)
    )
    with zipfile.ZipFile(io.BytesIO(metadata_view)) as archive:
        information = archive.infolist()
        if (
            len(information) != 4
            or {item.filename for item in information}
            != {"alpha.npy", "metadata.npy", "key.npy", "sha256.npy"}
            or archive.comment != b""
        ):
            raise ValueError("Invalid tile cache members or metadata view")
        for item, member in zip(information, members):
            if (
                item.flag_bits,
                item.compress_type,
                item.CRC,
                item.compress_size,
                item.file_size,
                item.header_offset + origin,
            ) != (
                member.flags,
                member.method,
                member.checksum,
                member.compressed_size,
                member.size,
                member.header_offset,
            ):
                raise ValueError("Divergent tile cache metadata interpretation")
            limit = TILE_SIZE**2 * (8 if item.filename == "alpha.npy" else 1)
            if member.size > limit + _CACHE_HEADER_LIMIT:
                raise ValueError("Oversized tile cache member")
            payloads.append(
                (
                    item.filename,
                    member,
                    _tile_cache_payload(snapshot, member, boundaries[member.header_offset]),
                )
            )
    return {name: _decode_tile_cache_member(payload, member) for name, member, payload in payloads}


def _read_tile_prediction(
    stream: BinaryIO, expected_key: str, expected_shape: tuple[int, int] | None = None
) -> tuple[np.ndarray, dict[str, Any]]:
    """Bound container metadata and actual decoded bytes before allocating arrays."""
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        if size > _CACHE_ARCHIVE_LIMIT:
            raise ValueError("Oversized tile cache archive")
        stream.seek(0)
        snapshot = stream.read(_CACHE_ARCHIVE_LIMIT + 1)
        if len(snapshot) != size:
            raise ValueError("Changed or incomplete tile cache archive")
        arrays = _tile_cache_arrays(snapshot)
        # NumPy 2.3.5 defaults to the required 10,000-byte header cap; its public
        # stubs omit that keyword. Use the verified default without a suppression.
        for name, body in arrays.items():
            array_stream = io.BytesIO(body)
            version = np.lib.format.read_magic(array_stream)
            if version == (1, 0):
                shape, _, dtype = np.lib.format.read_array_header_1_0(array_stream)
            elif version == (2, 0):
                shape, _, dtype = np.lib.format.read_array_header_2_0(array_stream)
            else:
                raise ValueError("Unsupported tile cache array header")
            if name == "alpha.npy":
                if (
                    len(shape) != 2
                    or any(
                        type(dimension) is not int or not 1 <= dimension <= TILE_SIZE
                        for dimension in shape
                    )
                    or dtype not in (np.dtype("float32"), np.dtype("float64"))
                    or (expected_shape is not None and shape != expected_shape)
                ):
                    raise ValueError("Invalid tile cache alpha shape or dtype")
                array_size = shape[0] * shape[1] * dtype.itemsize
            else:
                if shape != () or dtype.kind != "U" or not 0 < dtype.itemsize <= TILE_SIZE**2:
                    raise ValueError("Invalid tile cache scalar text")
                if name in {"key.npy", "sha256.npy"} and dtype.itemsize != 64 * 4:
                    raise ValueError("Invalid tile cache identity")
                array_size = dtype.itemsize
            if len(body) != array_stream.tell() + array_size:
                raise ValueError("Invalid tile cache array length")
        data = {
            name: np.lib.format.read_array(io.BytesIO(body), allow_pickle=False)
            for name, body in arrays.items()
        }
        alpha = data["alpha.npy"]
        metadata = json.loads(str(data["metadata.npy"]))
        if (
            not isinstance(metadata, dict)
            or str(data["key.npy"]) != expected_key
            or not np.isfinite(alpha).all()
            or hashlib.sha256(
                alpha.tobytes() + json.dumps(metadata, sort_keys=True).encode()
            ).hexdigest()
            != str(data["sha256.npy"])
        ):
            raise ValueError("Invalid tile cache content or checksum")
        return alpha, metadata
    except (
        zipfile.BadZipFile,
        zlib.error,
        struct.error,
        NotImplementedError,
        EOFError,
        UnicodeError,
        RecursionError,
    ) as error:
        raise ValueError("Invalid tile cache archive") from error


def tile_origins(length: int) -> list[int]:
    if type(length) is not int or length < 1:
        raise ValueError("Native dimension must be positive")
    if length <= TILE_SIZE:
        return [0]
    origins = list(range(0, length - TILE_SIZE + 1, STRIDE))
    if origins[-1] != length - TILE_SIZE:
        origins.append(length - TILE_SIZE)
    return origins


def _axis_weights(length: int, origin: int, total: int) -> np.ndarray:
    weights = np.ones(length, dtype=np.float64)
    ramp_length = min(OVERLAP, length)
    ramp = np.sin((np.arange(ramp_length) + 0.5) / OVERLAP * np.pi / 2) ** 2
    if origin > 0:
        weights[:ramp_length] *= ramp
    if origin + length < total:
        weights[-ramp_length:] *= ramp[::-1]
    return weights


def _complete_cache_identity(identity: dict[str, Any] | None) -> bool:
    required = {
        "developed_id",
        "model",
        "revision",
        "hashes",
        "packages",
        "preprocessing",
        "dtype",
        "attention",
    }
    if not isinstance(identity, dict) or not required <= identity.keys():
        return False
    hashes, packages = identity["hashes"], identity["packages"]
    return (
        all(
            isinstance(identity[name], str) and identity[name]
            for name in required - {"hashes", "packages"}
        )
        and isinstance(hashes, dict)
        and {"config.json", "preprocessor_config.json", "model.safetensors"} <= hashes.keys()
        and all(isinstance(value, str) and len(value) == 64 for value in hashes.values())
        and isinstance(packages, dict)
        and {"torch", "torchvision", "transformers", "safetensors", "numpy", "Pillow"}
        <= packages.keys()
        and all(isinstance(value, str) and value for value in packages.values())
    )


def _cache_generation(cache: Path, backend: str) -> str:
    from .project import _atomic_json, check_space

    if cache.resolve() != cache.absolute():
        raise ValueError("Unsafe matte cache path")
    cache.mkdir(parents=True, exist_ok=True)
    marker = cache / "backend.json"
    try:
        if marker.is_symlink():
            raise ValueError("Unsafe matte backend marker")
        record = json.loads(marker.read_bytes())
        if (
            set(record) == {"backend", "generation"}
            and record["backend"] == backend
            and isinstance(record["generation"], str)
            and len(record["generation"]) == 32
        ):
            return record["generation"]
    except (OSError, ValueError, TypeError):
        pass
    check_space(cache, 1024**2)
    generation = uuid.uuid4().hex
    _atomic_json(marker, {"backend": backend, "generation": generation})
    return generation


def native_matte(
    pixels: np.ndarray,
    trimap: np.ndarray,
    predict: Callable[[np.ndarray, np.ndarray, str], tuple[np.ndarray, dict[str, Any]]],
    device: str,
    *,
    auto_mps: bool = False,
    cache_dir: Path | None = None,
    cache_identity: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Retry the entire stage on device switch; never mix tile predictions across devices."""
    if (
        pixels.dtype != np.uint8
        or pixels.ndim != 3
        or pixels.shape[2] != 3
        or trimap.dtype != np.uint8
        or trimap.shape != pixels.shape[:2]
        or not np.isin(trimap, [0, 128, 255]).all()
    ):
        raise ValueError("Matting requires aligned RGB8 and categorical trimap")
    height, width = trimap.shape
    ys, xs = tile_origins(height), tile_origins(width)

    def stage(selected: str) -> tuple[np.ndarray, dict[str, Any]]:
        generation = (
            _cache_generation(cache_dir, selected)
            if cache_dir is not None and _complete_cache_identity(cache_identity)
            else None
        )
        accumulated = np.zeros(trimap.shape, dtype=np.float64)
        total_weight = np.zeros(trimap.shape, dtype=np.float64)
        records = []
        inferred = 0
        reused = 0
        for y in ys:
            for x in xs:
                h, w = min(TILE_SIZE, height - y), min(TILE_SIZE, width - x)
                guide = trimap[y : y + h, x : x + w]
                if np.any(guide == 128):
                    rgb = pixels[y : y + h, x : x + w]
                    key = hashlib.sha256(
                        json.dumps(
                            {
                                "identity": cache_identity,
                                "backend": selected,
                                "crop": [x, y, x + w, y + h],
                                "tile_size": TILE_SIZE,
                                "overlap": OVERLAP,
                                "version": 2,
                                "generation": generation,
                            },
                            sort_keys=True,
                        ).encode()
                        + rgb.tobytes()
                        + guide.tobytes()
                    ).hexdigest()
                    entry = (
                        cache_dir / f"{key}.npz"
                        if cache_dir is not None and generation is not None
                        else None
                    )
                    cached = None
                    occupied = None
                    if entry is not None:
                        try:
                            occupied = entry.lstat()
                        except FileNotFoundError:
                            pass
                        if occupied is not None:
                            if not stat.S_ISREG(occupied.st_mode):
                                raise ValueError(
                                    "Unsafe matte cache destination; expected regular prediction"
                                )
                            try:
                                descriptor = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW)
                                with os.fdopen(descriptor, "rb") as stream:
                                    if _cache_file_identity(
                                        os.fstat(stream.fileno())
                                    ) != _cache_file_identity(occupied):
                                        raise ValueError("Matte cache destination changed")
                                    cached, metadata = _read_tile_prediction(
                                        stream, key, guide.shape
                                    )
                            except (
                                OSError,
                                ValueError,
                                TypeError,
                                KeyError,
                                EOFError,
                                zipfile.BadZipFile,
                            ):
                                pass  # An initially occupied corrupt regular file remains a miss.
                    if cached is not None:
                        prediction = cached
                        metadata = dict(metadata, cache_reused=True)
                        reused += 1
                    else:
                        prediction, metadata = predict(rgb, guide, selected)
                        inferred += 1
                        if prediction.shape != guide.shape or not np.isfinite(prediction).all():
                            raise FloatingPointError("Non-finite or invalid native tile prediction")
                        if entry is not None:
                            from .project import _publish_new_cache_file, check_space

                            if cache_dir is None or cache_dir.resolve() != cache_dir.absolute():
                                raise ValueError("Unsafe matte cache path")
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            check_space(cache_dir, prediction.nbytes * 2 + 1024**2)
                            descriptor, temporary = tempfile.mkstemp(prefix=".tile-", dir=cache_dir)
                            serialized = json.dumps(metadata, sort_keys=True)
                            checksum = hashlib.sha256(
                                prediction.tobytes() + serialized.encode()
                            ).hexdigest()
                            with os.fdopen(descriptor, "wb") as stream:
                                np.savez(
                                    stream,
                                    alpha=prediction,
                                    metadata=serialized,
                                    sha256=checksum,
                                    key=key,
                                )
                                stream.flush()
                                os.fsync(stream.fileno())
                            with Path(temporary).open("rb") as stream:
                                _read_tile_prediction(stream, key, guide.shape)
                            if occupied is not None:
                                current = entry.lstat()
                                if _cache_file_identity(current) != _cache_file_identity(occupied):
                                    raise ValueError(
                                        "Matte cache destination changed during recomputation"
                                    )
                                metadata = dict(
                                    metadata, cache_publication="skipped_corrupt_existing"
                                )
                            else:
                                _publish_new_cache_file(Path(temporary), entry)
                else:
                    prediction, metadata = guide.astype(np.float64) / 255, {"bypassed": True}
                if prediction.shape != guide.shape or not np.isfinite(prediction).all():
                    raise FloatingPointError("Non-finite or invalid native tile prediction")
                prediction = np.clip(prediction, 0, 1)
                weight = _axis_weights(h, y, height)[:, None] * _axis_weights(w, x, width)[None, :]
                accumulated[y : y + h, x : x + w] += prediction * weight
                total_weight[y : y + h, x : x + w] += weight
                records.append({"crop_xyxy": [x, y, x + w, y + h], **metadata})
        if not np.isfinite(accumulated).all() or not np.all(total_weight > 0):
            raise FloatingPointError("Invalid matte coverage or accumulation")
        alpha = np.clip(accumulated / total_weight, 0, 1)
        alpha[trimap == 0] = 0
        alpha[trimap == 255] = 1
        return np.rint(alpha * 65535).astype(np.uint16), {
            "tile_size_px": TILE_SIZE,
            "overlap_px": OVERLAP,
            "stride_px": STRIDE,
            "origins_x": xs,
            "origins_y": ys,
            "tiles": records,
            "inferred_tiles": inferred,
            "reused_tiles": reused,
            "minimum_weight": float(total_weight.min()),
            "quantization": "once float64 ties-to-even",
        }

    (alpha, record), selected, fallback = run_device_stage(stage, device, auto_mps=auto_mps)
    return alpha, dict(record, device=selected, fallback=fallback)
