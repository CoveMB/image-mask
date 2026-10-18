"""Same-native-crop review assets with explicit lower-precision labels and transforms."""

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .export import publish_artifacts, render_black, saved_layers
from .guidance import coordinates
from .project import (
    ProjectError,
    _asset,
    _json_bytes,
    _read_json,
    _root,
    check_space,
    digest,
    load_master,
    project_lock,
    read_project,
)


def write_review(
    directory: Path,
    source: np.ndarray,
    foreground: np.ndarray,
    alpha16: np.ndarray,
    *,
    master_id: str,
    revision: str,
    crops: list[list[int]] | None = None,
) -> dict[str, Any]:
    height, width = alpha16.shape
    if crops is None:
        crops = [[0, 0, width, height]]
    if not isinstance(crops, list) or not crops:
        raise ValueError("Review crops must be a nonempty list of native half-open boxes")
    validated = [coordinates(c, width, height, box=True) for c in crops]
    directory.mkdir()
    records = []
    rows = []
    for index, (x0, y0, x1, y1) in enumerate(validated):
        source_crop = source[y0:y1, x0:x1]
        rgb = foreground[y0:y1, x0:x1]
        alpha = alpha16[y0:y1, x0:x1]
        factor = alpha.astype(np.float64)[..., None] / 65535
        panels = {
            "source_RGB8_VIEW": np.rint(source_crop.astype(np.float64) / 257).astype(np.uint8),
            "black_RGB8_VIEW": np.rint(render_black(rgb, alpha).astype(np.float64) / 257).astype(
                np.uint8
            ),
            "gray_RGB8_VIEW": np.rint(
                (rgb.astype(np.float64) * factor + 32768 * (1 - factor)) / 257
            ).astype(np.uint8),
            "white_RGB8_VIEW": np.rint(
                (rgb.astype(np.float64) * factor + 65535 * (1 - factor)) / 257
            ).astype(np.uint8),
            "alpha8_VIEW": np.repeat(
                np.rint(alpha.astype(np.float64) / 257).astype(np.uint8)[..., None], 3, axis=2
            ),
        }
        files = {}
        for label, pixels in panels.items():
            name = f"crop-{index:03d}-{label}.png"
            Image.fromarray(pixels).save(directory / name)
            files[label] = name
        rows.append(np.concatenate(list(panels.values()), axis=1))
        records.append(
            {
                "crop_xyxy": [x0, y0, x1, y1],
                "displayed_dimensions_wh": [x1 - x0, y1 - y0],
                "scale_xy": [1, 1],
                "native_origin_xy": [x0, y0],
                "files": files,
            }
        )
    contact = np.zeros(
        (sum(row.shape[0] for row in rows), max(row.shape[1] for row in rows), 3), dtype=np.uint8
    )
    offset = 0
    for row in rows:
        contact[offset : offset + row.shape[0], : row.shape[1]] = row
        offset += row.shape[0]
    Image.fromarray(contact).save(directory / "contact_RGB8_VIEW.png")
    record = {
        "schema_version": 1,
        "master_id": master_id,
        "revision": revision,
        "label": "RGB8/alpha8 viewing approximations; native pixels, no resize; inspect saved RGB16/alpha16 separately",
        "panel_order": ["source", "black", "gray", "white", "alpha"],
        "crops": records,
        "visual_review": "human photographic review pending",
    }
    (directory / "manifest.json").write_bytes(_json_bytes(record))
    return record


def review_project(
    project: Path, *, revision: str | None = None, crops: list[list[int]] | None = None
) -> dict[str, Any]:
    project = _root(project)
    with project_lock(project):
        state = read_project(project)
        revision = revision or state["working_revision"]
        if revision is None:
            raise ProjectError("No complete matte revision to review")
        foreground, alpha, _ = saved_layers(project, revision, state["master_id"])
        source, _ = load_master(project, state["master_id"])
        height, width = alpha.shape
        if crops is None:
            saved_review = _read_json(project, f"revisions/{revision}/review/manifest.json")
            saved_crops = saved_review.get("crops")
            if (
                saved_review.get("master_id") != state["master_id"]
                or saved_review.get("revision") != revision
                or not isinstance(saved_crops, list)
                or any(not isinstance(crop, dict) for crop in saved_crops)
            ):
                raise ProjectError("Invalid saved review crop identity")
            selected = [crop.get("crop_xyxy") for crop in saved_crops]
        else:
            selected = crops
        if not isinstance(selected, list) or not selected:
            raise ProjectError("Review crops must be a nonempty list")
        selected = [coordinates(c, width, height, box=True) for c in selected]
        before = _asset(project, "state.json").read_bytes()
        manifest_bytes = _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        check_space(
            project,
            source.nbytes * 30
            + sum((c[2] - c[0]) * (c[3] - c[1]) for c in selected) * 32
            + 1024**2,
        )
        root = _asset(project, f"reviews/{revision}")
        root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".review-", dir=root))
        directory = stage / "assets"
        write_review(
            directory,
            source,
            foreground,
            alpha,
            master_id=state["master_id"],
            revision=revision,
            crops=selected,
        )
        if (
            before != _asset(project, "state.json").read_bytes()
            or manifest_bytes != _asset(project, f"revisions/{revision}/manifest.json").read_bytes()
        ):
            raise ProjectError("Stale review inputs")
        saved_layers(project, revision, state["master_id"])
        key = digest(_json_bytes({"crops": selected, "manifest": digest(manifest_bytes)}))
        destination = root / key
        publish_artifacts(directory, destination)
        return {"revision": revision, "manifest_file": str(destination / "manifest.json")}
