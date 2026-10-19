"""Saved native RGB16 backdrops, independent of foreground and matte geometry."""

import json
import math
import re
import tomllib
from pathlib import Path
from typing import Any

import numpy as np

from .exposure import linear_to_rgb16, srgb_to_linear
from .project import ProjectError, _asset, _json_bytes, digest, read_revision

DEFAULT_BACKGROUND = {"color_srgb": "#120708", "variation": 0.55}
LEGACY_BACKGROUND = {"color_srgb": "#000000", "variation": 0.0}
ALGORITHM = "smooth-tonal-background-v1"
BACKGROUND_FILES = ("background/background_rgb16.tif", "background/settings.json")


def validate_background(settings: Any) -> None:
    if (
        not isinstance(settings, dict)
        or set(settings) != {"color_srgb", "variation"}
        or not isinstance(settings["color_srgb"], str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", settings["color_srgb"]) is None
        or type(settings["variation"]) not in {int, float}
        or not 0 <= settings["variation"] <= 1
        or not math.isfinite(settings["variation"])
    ):
        raise ProjectError("Background requires #RRGGBB and finite variation in [0,1]")


def normalized_background(settings: Any) -> dict[str, Any]:
    validate_background(settings)
    return {"color_srgb": settings["color_srgb"].upper(), "variation": settings["variation"]}


def make_background(shape: tuple[int, int], settings: dict[str, Any]) -> np.ndarray:
    """Two passes in bounded row chunks; statistics reduce rows in native order."""
    validate_background(settings)
    if len(shape) != 2 or any(type(n) is not int or n < 1 for n in shape):
        raise ProjectError("Background requires positive native height and width")
    height, width = shape
    color = np.array([int(settings["color_srgb"][i : i + 2], 16) for i in (1, 3, 5)])
    result = np.empty((height, width, 3), dtype=np.uint16)
    if settings["variation"] == 0 or not color.any():
        result[:] = color * 257
        return result
    x = np.arange(width, dtype=np.float64)[None, :] / max(width - 1, 1)

    def field_rows(start: int) -> np.ndarray:
        y = np.arange(start, min(start + 64, height), dtype=np.float64)[:, None] / max(
            height - 1, 1
        )
        return (
            0.48 * np.cos(2 * np.pi * (0.58 * x - 0.72 * y) + 1.2)
            + 0.30 * np.sin(2 * np.pi * (1.12 * x + 0.33 * y) - 0.7)
            + 0.22 * np.cos(2 * np.pi * (0.24 * x + 1.23 * y) + 0.5)
        )

    sums: list[float] = []
    minimum, maximum = math.inf, -math.inf
    for start in range(0, height, 64):
        q = field_rows(start)
        sums.extend(float(np.sum(row, dtype=np.float64)) for row in q)
        minimum, maximum = min(minimum, float(q.min())), max(maximum, float(q.max()))
    mean = math.fsum(sums) / (height * width)
    amplitude = max(abs(minimum - mean), abs(maximum - mean))
    linear = srgb_to_linear(color.astype(np.float64) / 255)
    for start in range(0, height, 64):
        q = field_rows(start) - mean
        field = q / amplitude if amplitude else np.zeros_like(q)
        result[start : start + 64] = linear_to_rgb16(
            linear * np.exp2(settings["variation"] * field)[..., None]
        )
    return result


def validate_background_bindings(directory: Path, manifest: dict[str, Any]) -> None:
    """Check unlisted assets before request-local validation can return early."""
    files = {name for name in manifest["files"] if name.startswith("background/")}
    expected = set(BACKGROUND_FILES) if "background" in manifest else set()
    saved = directory / "background"
    actual = set()
    if saved.exists() or saved.is_symlink():
        if saved.is_symlink() or not saved.is_dir():
            raise ProjectError("Invalid saved background directory")
        actual = {"background/" + p.name for p in saved.iterdir()}
        if any(p.is_symlink() or not p.is_file() for p in saved.iterdir()):
            raise ProjectError("Invalid saved background asset")
    if files != expected or actual != expected:
        raise ProjectError("Missing, unknown or unbound background assets")


def read_background(directory: Path, manifest: dict[str, Any]) -> np.ndarray | None:
    """Saved pixels are authoritative; never regenerate the analytic field on read."""
    from .export import read_rgb16

    validate_background_bindings(directory, manifest)
    recipe = tomllib.loads((directory / "recipe.toml").read_text())
    if "background" not in manifest:
        if "background" in recipe:
            raise ProjectError("Unbound background recipe settings")
        return None
    record = manifest["background"]
    if (
        not isinstance(record, dict)
        or set(record)
        != {
            "schema_version",
            "algorithm",
            "master_id",
            "width",
            "height",
            "settings",
            "background_sha256",
            "settings_sha256",
        }
        or type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["algorithm"] != ALGORITHM
        or record["master_id"] != manifest["master_id"]
        or any(type(record[n]) is not int or record[n] < 1 for n in ("width", "height"))
    ):
        raise ProjectError("Invalid saved background identity/schema/algorithm")
    validate_background(record["settings"])
    if normalized_background(recipe.get("background")) != record["settings"]:
        raise ProjectError("Background recipe and saved settings differ")
    for name, key in zip(BACKGROUND_FILES, ("background_sha256", "settings_sha256"), strict=True):
        if (
            manifest["files"][name] != record[key]
            or digest((directory / name).read_bytes()) != record[key]
        ):
            raise ProjectError("Saved background hash mismatch")
    if json.loads((directory / BACKGROUND_FILES[1]).read_bytes()) != record["settings"]:
        raise ProjectError("Saved background settings differ")
    pixels = read_rgb16(directory / BACKGROUND_FILES[0])
    if pixels.shape != (record["height"], record["width"], 3):
        raise ProjectError("Saved background dimensions differ")
    settings = record["settings"]
    if settings["variation"] == 0 or settings["color_srgb"] == "#000000":
        color = [int(settings["color_srgb"][i : i + 2], 16) * 257 for i in (1, 3, 5)]
        if not np.all(pixels == color):
            raise ProjectError("Saved uniform/black background pixels differ from settings")
    return pixels


def save_background(
    stage: Path, master_id: str, shape: tuple[int, int], settings: dict[str, Any]
) -> dict[str, Any]:
    from .ingest import write_master

    settings = normalized_background(settings)
    pixels = make_background(shape, settings)
    (stage / "background").mkdir(exist_ok=True)
    write_master(stage / BACKGROUND_FILES[0], pixels)
    (stage / BACKGROUND_FILES[1]).write_bytes(_json_bytes(settings))
    return {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "master_id": master_id,
        "width": shape[1],
        "height": shape[0],
        "settings": settings,
        "background_sha256": digest((stage / BACKGROUND_FILES[0]).read_bytes()),
        "settings_sha256": digest((stage / BACKGROUND_FILES[1]).read_bytes()),
    }


def inherit_background(
    project: Path,
    parent: str | None,
    stage: Path,
    master_id: str,
    shape: tuple[int, int],
    settings: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if parent is None:
        return save_background(stage, master_id, shape, settings) if settings is not None else None
    manifest = read_revision(project, parent, master_id)
    record = manifest.get("background")
    expected = record["settings"] if record is not None else None
    current = normalized_background(settings) if settings is not None else None
    if current != expected:
        raise ProjectError("Changed background draft requires explicit Apply background")
    if record is not None:
        (stage / "background").mkdir(exist_ok=True)
        for name in BACKGROUND_FILES:
            (stage / name).write_bytes(_asset(project, f"revisions/{parent}/{name}").read_bytes())
    return record
