"""Same-native-crop review assets with explicit lower-precision labels and transforms."""

import json
import re
import tempfile
import tomllib
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .assets import saved_asset
from .effects import validate_cleanup
from .export import (
    _foreground_contribution,
    publish_artifacts,
    render_background,
    render_black,
    saved_layers,
    shading_factor,
)
from .guidance import coordinates
from .project import (
    ProjectError,
    _atomic_bytes,
    _atomic_json,
    _json_bytes,
    _read_json,
    _root,
    check_space,
    digest,
    load_developed,
    project_lock,
    read_project,
    read_revision,
)
from .spatial_fade import SpatialFadeOperands


def review_panels(
    source: np.ndarray,
    foreground: np.ndarray,
    alpha16: np.ndarray,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    *,
    background16: np.ndarray | None = None,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Shared labelled RGB8 approximations; authoritative layers remain RGB16/alpha16."""
    factor = alpha16.astype(np.float64)[..., None] / 65535
    appearance = (
        foreground.astype(np.float64) * shading_factor(alpha16.shape, weight16, opacity)[..., None]
    )
    black = render_black(
        foreground,
        alpha16,
        weight16,
        opacity,
        spatial_fade=spatial_fade,
        fade_background16=fade_background16,
    )
    contribution = (
        _foreground_contribution(
            foreground,
            alpha16,
            weight16,
            opacity,
            spatial_fade=spatial_fade,
            fade_background16=fade_background16,
        )
        if spatial_fade is not None
        and spatial_fade.record["enabled"]
        and not spatial_fade.record["stale"]
        else appearance * factor
    )
    return {
        "result": np.rint(
            (
                black
                if background16 is None
                else render_background(
                    foreground,
                    alpha16,
                    background16,
                    weight16,
                    opacity,
                    spatial_fade=spatial_fade,
                    fade_background16=fade_background16,
                )
            ).astype(np.float64)
            / 257
        ).astype(np.uint8),
        "source": np.rint(source.astype(np.float64) / 257).astype(np.uint8),
        "black": np.rint(black.astype(np.float64) / 257).astype(np.uint8),
        "gray": np.rint((contribution + 32768 * (1 - factor)) / 257).astype(np.uint8),
        "white": np.rint((contribution + 65535 * (1 - factor)) / 257).astype(np.uint8),
        "alpha": np.repeat(
            np.rint(alpha16.astype(np.float64) / 257).astype(np.uint8)[..., None], 3, axis=2
        ),
    }


def write_review(
    directory: Path,
    source: np.ndarray,
    foreground: np.ndarray,
    alpha16: np.ndarray,
    *,
    developed_id: str,
    revision: str,
    crops: list[list[int]] | None = None,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    background16: np.ndarray | None = None,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
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
        native_panels = review_panels(
            source_crop,
            rgb,
            alpha,
            None if weight16 is None else weight16[y0:y1, x0:x1],
            opacity,
            background16=None if background16 is None else background16[y0:y1, x0:x1],
            spatial_fade=None
            if spatial_fade is None
            else SpatialFadeOperands(
                spatial_fade.weight16[y0:y1, x0:x1],
                spatial_fade.protection[y0:y1, x0:x1],
                spatial_fade.record,
            ),
            fade_background16=None
            if fade_background16 is None
            else fade_background16[y0:y1, x0:x1],
        )
        names = {
            "source": "source_RGB8_VIEW",
            "black": "black_RGB8_VIEW",
            "gray": "gray_RGB8_VIEW",
            "white": "white_RGB8_VIEW",
            "alpha": "alpha8_VIEW",
        }
        if background16 is not None:
            names["result"] = "result_RGB8_VIEW"
        panels = {label: native_panels[name] for name, label in names.items()}
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
        "schema_version": 2,
        "developed_id": developed_id,
        "revision": revision,
        "label": "RGB8/alpha8 viewing approximations; native pixels, no resize; inspect saved RGB16/alpha16 separately",
        "panel_order": ["source", "black", "gray", "white", "alpha"]
        + (["result"] if background16 is not None else []),
        "crops": records,
        "visual_review": "human photographic review pending",
    }
    (directory / "manifest.json").write_bytes(_json_bytes(record))
    return record


def write_revision_overview(
    directory: Path,
    source: np.ndarray,
    foreground: np.ndarray,
    alpha16: np.ndarray,
    *,
    developed_id: str,
    revision: str,
    crops: list[list[int]] | None = None,
    weight16: np.ndarray | None = None,
    opacity: float = 0,
    background16: np.ndarray | None = None,
    spatial_fade: SpatialFadeOperands | None = None,
    fade_background16: np.ndarray | None = None,
) -> dict[str, Any]:
    """One reduced JPEG per revision; native inspection stays in explicit reviews/."""
    from .ingest import srgb_profile

    height, width = alpha16.shape
    boxes = [coordinates(c, width, height, box=True) for c in (crops or [[0, 0, width, height]])]
    selected = ["source", "black", "gray", "white", "alpha"] + (
        ["result"] if background16 is not None else []
    )
    preview = directory.parent / "preview.jpg"
    previous = directory.parent / "review/manifest.json"
    old_record = (
        json.loads(previous.read_bytes())
        if directory.name == "review-before" and previous.exists()
        else None
    )
    total_rows = len(boxes) + (len(old_record["crops"]) if old_record is not None else 0)
    if total_rows > 1600:
        raise ValueError("Too many overview rows for nonempty panels within 1600 pixels")
    row_height_limit = 1600 // total_rows
    rows: list[Image.Image] = []
    records = []

    def append_row(panels: dict[str, Image.Image], crop: dict[str, Any]) -> None:
        # Budget for the final combined layout before resizing any panel. Scaling
        # the whole sheet afterwards can erase a valid one-pixel-wide panel.
        panel_width, panel_height = panels["source"].size
        factor = min(1.0, 1600 / (panel_width * len(panels)), row_height_limit / panel_height)
        size = (max(1, int(panel_width * factor)), max(1, int(panel_height * factor)))
        row = Image.new("RGB", (size[0] * len(panels), size[1]))
        top = sum(r.height for r in rows)
        try:
            for index, image in enumerate(panels.values()):
                with image.resize(size, Image.Resampling.LANCZOS) as reduced:
                    row.paste(reduced, (index * size[0], 0))
        finally:
            for image in panels.values():
                image.close()
        rows.append(row)
        x0, y0, x1, y1 = crop["crop_xyxy"]
        crop.update(
            displayed_dimensions_wh=list(size),
            scale_xy=[(x1 - x0) / size[0], (y1 - y0) / size[1]],
            native_origin_xy=[x0, y0],
            files={"overview": "../preview.jpg"},
            display_reference_panel="source",
            panel_boxes_xyxy={
                name: [index * size[0], top, (index + 1) * size[0], top + size[1]]
                for index, name in enumerate(panels)
            },
        )

    for x0, y0, x1, y1 in boxes:
        pixels = review_panels(
            source[y0:y1, x0:x1],
            foreground[y0:y1, x0:x1],
            alpha16[y0:y1, x0:x1],
            None if weight16 is None else weight16[y0:y1, x0:x1],
            opacity,
            background16=None if background16 is None else background16[y0:y1, x0:x1],
            spatial_fade=None
            if spatial_fade is None
            else SpatialFadeOperands(
                spatial_fade.weight16[y0:y1, x0:x1],
                spatial_fade.protection[y0:y1, x0:x1],
                spatial_fade.record,
            ),
            fade_background16=None
            if fade_background16 is None
            else fade_background16[y0:y1, x0:x1],
        )
        crop: dict[str, Any] = {"crop_xyxy": [x0, y0, x1, y1]}
        append_row({name: Image.fromarray(pixels[name]) for name in selected}, crop)
        records.append(crop)
    if old_record is not None:
        with Image.open(preview) as image:
            for crop in old_record["crops"]:
                append_row(
                    {
                        name: image.crop(crop["panel_boxes_xyxy"][name])
                        for name in old_record["panel_order"]
                    },
                    crop,
                )
    sheet = Image.new("RGB", (max(row.width for row in rows), sum(row.height for row in rows)))
    offset = 0
    for row in rows:
        sheet.paste(row, (0, offset))
        offset += row.height
        row.close()
    record = {
        "schema_version": 2,
        "developed_id": developed_id,
        "revision": revision,
        "label": "Reduced RGB8 JPEG overview; use explicit native review crops for inspection",
        "overview": True,
        "panel_order": selected,
        "crops": records,
        "visual_review": "human photographic review pending",
    }
    for item in [record] + ([old_record] if old_record is not None else []):
        item["overview_dimensions_wh"] = list(sheet.size)
    directory.mkdir()
    try:
        sheet.save(preview, format="JPEG", quality=85, optimize=True, icc_profile=srgb_profile())
    finally:
        sheet.close()
    if old_record is not None:
        previous.write_bytes(_json_bytes(old_record))
    (directory / "manifest.json").write_bytes(_json_bytes(record))
    return record


def write_preparation_overview(
    directory: Path, source: np.ndarray, *, developed_id: str, revision: str
) -> None:
    from .ingest import srgb_profile

    with Image.fromarray((source // 257).astype(np.uint8)) as image:
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        image.save(
            directory / "preview.jpg",
            format="JPEG",
            quality=85,
            optimize=True,
            icc_profile=srgb_profile(),
        )
        displayed = list(image.size)
    review = directory / "review"
    review.mkdir()
    (review / "manifest.json").write_bytes(
        _json_bytes(
            {
                "schema_version": 2,
                "developed_id": developed_id,
                "revision": revision,
                "overview": True,
                "label": "Reduced preparation source overview; no matte generated",
                "overview_dimensions_wh": displayed,
                "files": {"overview": "../preview.jpg"},
            }
        )
    )


def review_project(
    project: Path, *, revision: str | None = None, crops: list[list[int]] | None = None
) -> dict[str, Any]:
    project = _root(project)
    with project_lock(project):
        return _review_project_locked(project, revision=revision, crops=crops)


def _review_project_locked(
    project: Path,
    *,
    revision: str | None = None,
    crops: list[list[int]] | None = None,
    include_before: bool = True,
    base_comparison: bool = False,
) -> dict[str, Any]:
    """Generate explicit native evidence; caller owns the project writer lock."""
    state = read_project(project)
    revision = revision or state["working_revision"]
    if revision is None:
        raise ProjectError("No complete matte revision to review")
    foreground, alpha, revision_manifest = saved_layers(
        project, revision, state["developed_id"], effects_off=base_comparison
    )
    from .effects import effects_stale, saved_shading, saved_spatial_fade

    weight, opacity = saved_shading(
        project, revision, alpha, revision_manifest, effects_off=base_comparison
    )
    source, _ = load_developed(project, state["developed_id"])
    prefix = f"revisions/{revision}"
    settings = tomllib.loads(saved_asset(project, f"{prefix}/recipe.toml").read_text())
    cleanup = revision_manifest.get("color_cleanup")
    if cleanup is not None:
        applied_cleanup = {
            "enabled": cleanup.get("enabled"),
            "strength": cleanup.get("strength"),
        }
        validate_cleanup(applied_cleanup)
        settings["color_cleanup"] = applied_cleanup
    height, width = alpha.shape
    if crops is None:
        saved_review = _read_json(project, f"revisions/{revision}/review/manifest.json")
        saved_crops = saved_review.get("crops")
        if (
            saved_review.get("developed_id") != state["developed_id"]
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
    before = saved_asset(project, "state.json").read_bytes()
    manifest_bytes = saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
    check_space(
        project,
        source.nbytes * 30 + sum((c[2] - c[0]) * (c[3] - c[1]) for c in selected) * 32 + 1024**2,
    )
    root = saved_asset(project, f"reviews/{revision}")
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".review-", dir=root))
    directory = stage / "assets"
    from .background import read_background

    background = (
        None
        if base_comparison or effects_stale(revision_manifest)
        else read_background(
            project, saved_asset(project, f"revisions/{revision}"), revision_manifest
        )
    )
    spatial = saved_spatial_fade(
        project, revision, alpha, revision_manifest, effects_off=base_comparison
    )
    target = (
        background
        if background is not None
        else np.zeros_like(foreground)
        if spatial is not None
        else None
    )
    record = write_review(
        directory,
        source,
        foreground,
        alpha,
        developed_id=state["developed_id"],
        revision=revision,
        crops=selected,
        background16=background,
        spatial_fade=spatial,
        fade_background16=target,
        weight16=weight,
        opacity=opacity,
    )
    from .operations import draft_digest, pending_guidance

    current_digest = draft_digest(project)
    stale = []
    if revision != state["working_revision"]:
        stale.append("not_current_working_revision")
    if current_digest != revision_manifest["draft_digest"]:
        stale.append("draft_changed")
    pending = pending_guidance(project)
    if pending and pending["current"] and pending["actions"]:
        stale.append("pending_guidance")
    if (
        revision_manifest.get("color_cleanup", {}).get("stale")
        and revision_manifest["color_cleanup"]["enabled"]
    ):
        stale.append("cleanup_stale")
        record["label"] += (
            "; BASE comparison: cleanup OFF; stale enabled cleanup needs scoped rebuild or explicit disable"
        )
    if revision_manifest.get("shading", {}).get("enabled") and revision_manifest["shading"].get(
        "stale"
    ):
        stale.append("shading_stale")
    if revision_manifest.get("local_exposure", {}).get("enabled") and revision_manifest[
        "local_exposure"
    ].get("stale"):
        stale.append("local_exposure_stale")
    if revision_manifest.get("shadow_fade", {}).get("enabled") and revision_manifest[
        "shadow_fade"
    ].get("stale"):
        stale.append("shadow_fade_stale")
    from .exposure import selected_exposure

    unexposed = saved_layers(
        project,
        revision,
        state["developed_id"],
        exposure_off=True,
        shadow_fade_off=True,
        effects_off=base_comparison,
    )[0]
    _, clipping = selected_exposure(
        project,
        saved_asset(project, f"revisions/{revision}"),
        unexposed,
        alpha,
        revision_manifest,
        exposure_off=base_comparison or effects_stale(revision_manifest),
    )
    if "local_exposure" in revision_manifest:
        record["label"] += (
            "; local exposure OFF"
            if base_comparison
            or effects_stale(revision_manifest)
            or not revision_manifest["local_exposure"]["enabled"]
            else f"; local exposure ON {revision_manifest['local_exposure']['settings']['ev']} EV"
        )
    if "shadow_fade" in revision_manifest:
        record["label"] += (
            "; Shadow fade OFF"
            if effects_stale(revision_manifest) or not revision_manifest["shadow_fade"]["enabled"]
            else "; Shadow fade ON"
        )
    if "spatial_fade" in revision_manifest:
        record["spatial_fade"] = revision_manifest["spatial_fade"]
        record["label"] += (
            "; Fade into background ON; diagnostics retain the selected background target"
            if spatial is not None
            else "; Fade into background OFF"
        )
        if (
            revision_manifest["spatial_fade"]["enabled"]
            and revision_manifest["spatial_fade"]["stale"]
        ):
            stale.append("spatial_fade_stale")
    if effects_stale(revision_manifest):
        record["label"] += (
            "; BASE comparison: cleanup OFF; shading OFF; stale enabled effects need independent rebuild or disable"
        )
    elif weight is not None:
        record["label"] += (
            f"; encoded-sRGB; baked shading p={opacity}; width={revision_manifest['shading']['settings']['width_px']} native px; cleanup={revision_manifest.get('color_cleanup', {}).get('enabled', False)}"
        )
    before_manifest = None
    if include_before and revision_manifest["kind"] == "repair":
        from .repair import prepared_parent_layers

        before_parent = read_revision(project, revision_manifest["parent"], state["developed_id"])
        if before_parent["kind"] == "prepare":
            before_parent = prepared_parent_layers(
                project, before_parent["revision"], state["developed_id"]
            )
        before_review = _review_project_locked(
            project,
            revision=before_parent["revision"],
            crops=selected,
            include_before=False,
            base_comparison=base_comparison or effects_stale(revision_manifest),
        )
        before_manifest = str(Path(before_review["manifest_file"]).relative_to(project))
    if base_comparison:
        record["label"] += "; BASE comparison: optional effects OFF on both sides"
    record.update(
        comparison="base" if base_comparison or effects_stale(revision_manifest) else "selected",
        inputs_digest=current_digest,
        revision_inputs_digest=revision_manifest["draft_digest"],
        working_revision=state["working_revision"],
        accepted_revision=state["accepted_revision"],
        stale_labels=stale,
        assets={
            "source_rgb16": f"assets/developed/{state['developed_id']}.tif",
            "foreground_rgb16": str(
                saved_asset(project, f"{prefix}/corrected_rgb16.tif").relative_to(project)
            )
            if revision_manifest.get("color_cleanup", {}).get("enabled")
            and not base_comparison
            and not effects_stale(revision_manifest)
            else str(saved_asset(project, f"{prefix}/foreground_rgb16.tif").relative_to(project)),
            "local_exposure": f"{prefix}/effects/exposure/settings.json"
            if "local_exposure" in revision_manifest
            else None,
            "shadow_fade": f"{prefix}/effects/shadow-fade/settings.json"
            if "shadow_fade" in revision_manifest
            else None,
            **(
                {"spatial_fade": f"{prefix}/effects/spatial-fade/settings.json"}
                if "spatial_fade" in revision_manifest
                else {}
            ),
            "foreground_selection": "base, optional cleanup, local exposure once, Shadow fade once; shading at render",
            "base_foreground_rgb16": str(
                saved_asset(project, f"{prefix}/foreground_rgb16.tif").relative_to(project)
            ),
            "alpha16": str(saved_asset(project, f"{prefix}/base_alpha16.png").relative_to(project)),
            "before_manifest": before_manifest,
        },
        settings=settings,
        model=revision_manifest.get("model"),
        qa=_read_json(project, f"{prefix}/qa.json"),
        effects={
            "available": True,
            "shadow_fade": revision_manifest.get("shadow_fade", {"enabled": False, "stale": False}),
            **(
                {"spatial_fade": revision_manifest["spatial_fade"]}
                if "spatial_fade" in revision_manifest
                else {}
            ),
            "color_cleanup": revision_manifest.get(
                "color_cleanup", {"enabled": False, "stale": False}
            ),
            "shading": revision_manifest.get("shading", {"enabled": False, "stale": False}),
            "local_exposure": dict(
                revision_manifest.get("local_exposure", {"enabled": False, "stale": False}),
                clipping=clipping,
            ),
        },
        status="review_needed",
        view_files={p.name: digest(p.read_bytes()) for p in directory.glob("*.png")},
    )
    (directory / "manifest.json").write_bytes(_json_bytes(record))
    if (
        current_digest != draft_digest(project)
        or before != saved_asset(project, "state.json").read_bytes()
        or manifest_bytes
        != saved_asset(project, f"revisions/{revision}/manifest.json").read_bytes()
    ):
        raise ProjectError("Stale review inputs")
    saved_layers(project, revision, state["developed_id"])
    key = digest(_json_bytes({"review": record, "manifest": digest(manifest_bytes)}))
    destination = root / key
    publish_artifacts(directory, destination)
    return {"revision": revision, "manifest_file": str(destination / "manifest.json")}


# Immutable review events are advisory history, never project revision/acceptance pointers.
def _cycle_events(project: Path, cycle_id: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(cycle_id, str) or re.fullmatch(r"review-[a-f0-9]{32}", cycle_id) is None:
        raise ProjectError("Invalid assisted review cycle identity")
    directory = saved_asset(project, f"requests/{cycle_id}")
    files = sorted(directory.glob("*.json"))
    if not files or len(files) > 7:
        raise ProjectError("Missing or invalid assisted review history")
    previous = None
    prior = None
    reservations = set()
    for index, path in enumerate(files):
        data = saved_asset(project, f"requests/{cycle_id}/{path.name}").read_bytes()
        if path.name != f"{index:03d}-{digest(data)}.json":
            raise ProjectError("Assisted review history event integrity mismatch")
        record = json.loads(data)
        if (
            not isinstance(record, dict)
            or record.get("cycle_id") != cycle_id
            or record.get("event_index") != index
            or record.get("previous_sha256") != previous
            or record.get("schema_version") != 2
            or record.get("status") != "review_needed"
            or type(record.get("attempts")) is not int
        ):
            raise ProjectError("Invalid assisted review event")
        event = record.get("event")
        request = record.get("request")
        if not isinstance(request, dict):
            raise ProjectError("Invalid assisted review event request")
        if prior is None:
            valid = (
                event == "start"
                and request.get("action") == "start"
                and record.get("attempts") == 0
                and record.get("phase") == "ready"
                and record.get("stop_reason") is None
                and record.get("best_revision")
                == record.get("last_revision")
                == request.get("base_revision")
                and record.get("developed_id") == request.get("developed_id")
                and record.get("user_request") == request.get("user_request")
            )
        else:
            valid = prior["phase"] != "stopped" and all(
                record.get(k) == prior.get(k)
                for k in ("developed_id", "user_request", "schema_version", "cycle_id", "status")
            )
            if event == "reserve":
                checksum = digest(_json_bytes(request))
                valid = (
                    valid
                    and prior["phase"] == "ready"
                    and prior["attempts"] < 2
                    and record.get("phase") == "awaiting_assessment"
                    and record["attempts"] == prior["attempts"] + 1
                    and record.get("operation_sha256") == checksum
                    and request.get("kind") == "repair"
                    and request.get("assisted_review", {}).get("cycle_id") == cycle_id
                    and record.get("stop_reason") is None
                    and all(
                        record.get(k) == prior.get(k) for k in ("best_revision", "last_revision")
                    )
                )
                reservations.add(checksum)
            elif event == "assess":
                outcome = record.get("outcome")
                expected_outcome = (
                    "no_progress"
                    if record.get("unchanged_alpha") is True
                    and request.get("outcome") == "improved"
                    else request.get("outcome")
                )
                stop = (
                    outcome
                    if outcome != "improved"
                    else "attempt_budget_exhausted"
                    if prior["attempts"] == 2
                    else None
                )
                result = record.get("result", {})
                valid = (
                    valid
                    and prior["phase"] == "awaiting_assessment"
                    and request.get("action") == "assess"
                    and outcome == expected_outcome
                    and outcome
                    in {
                        "improved",
                        "no_progress",
                        "regression",
                        "ambiguous",
                        "missing_source_evidence",
                        "user_decision",
                    }
                    and record.get("phase") == ("stopped" if stop else "ready")
                    and record.get("stop_reason") == stop
                    and record["attempts"] == prior["attempts"]
                    and record.get("operation_sha256") == prior.get("operation_sha256")
                    and record.get("last_revision")
                    == result.get("revision")
                    == request.get("base_revision")
                    and record.get("best_revision")
                    == (result.get("revision") if outcome == "improved" else prior["best_revision"])
                )
            elif event == "stop":
                valid = (
                    valid
                    and record.get("phase") == "stopped"
                    and bool(record.get("stop_reason"))
                    and record["attempts"] == prior["attempts"]
                    and all(
                        record.get(k) == prior.get(k)
                        for k in ("best_revision", "last_revision", "operation_sha256")
                    )
                )
            else:
                valid = False
        if not valid:
            raise ProjectError("Invalid assisted review history transition")
        previous = digest(data)
        prior = record
    from .operations import retained_assisted_requests

    if not retained_assisted_requests(project, cycle_id) <= reservations:
        raise ProjectError("Truncated assisted review history: retained repair reservation missing")
    if previous is None:
        raise ProjectError("Missing assisted review history events")
    return record, previous


def _cycle_record(project: Path, cycle_id: Any) -> dict[str, Any]:
    record, terminal = _cycle_events(project, cycle_id)
    anchor = saved_asset(project, f"requests/{cycle_id}/head.sha256")
    if not anchor.is_file() or anchor.read_bytes() != (terminal + "\n").encode():
        raise ProjectError("Assisted review history anchor mismatch; preserve and inspect history")
    return record


def _save_cycle(
    project: Path, record: dict[str, Any], event: str, **changes: Any
) -> dict[str, Any]:
    from .operations import draft_digest

    state_bytes = saved_asset(project, "state.json").read_bytes()
    inputs = draft_digest(project)
    old = _json_bytes(record)
    anchor = saved_asset(project, f"requests/{record['cycle_id']}/head.sha256")
    anchor_before = anchor.read_bytes()
    index = record["event_index"] + 1
    updated = dict(record, **changes)
    updated.update(event=event, event_index=index, previous_sha256=digest(old))
    path = saved_asset(
        project, f"requests/{record['cycle_id']}/{index:03d}-{digest(_json_bytes(updated))}.json"
    )

    def recheck():
        if (
            state_bytes != saved_asset(project, "state.json").read_bytes()
            or inputs != draft_digest(project)
            or _cycle_record(project, record["cycle_id"]) != record
        ):
            raise ProjectError("Stale assisted review history")

    check_space(project, len(_json_bytes(updated)) + 1024**2)
    _atomic_json(path, updated, replace_existing=False, validate_before_replace=recheck)

    def recheck_anchor():
        current, terminal = _cycle_events(project, record["cycle_id"])
        if (
            state_bytes != saved_asset(project, "state.json").read_bytes()
            or inputs != draft_digest(project)
            or anchor.read_bytes() != anchor_before
            or current != updated
            or terminal != digest(_json_bytes(updated))
        ):
            raise ProjectError("Stale assisted review history anchor publication")

    # Event first, then its integrity anchor. Either partial state fails closed on reopen.
    _atomic_bytes(
        anchor,
        (digest(_json_bytes(updated)) + "\n").encode(),
        validate_before_replace=recheck_anchor,
    )
    return updated


def _identity(project: Path, request: dict[str, Any]) -> dict[str, Any]:
    from .operations import _reject_pending_guidance, draft_digest

    state = read_project(project)
    _reject_pending_guidance(project)
    if (
        request.get("developed_id") != state["developed_id"]
        or request.get("base_revision") != state["working_revision"]
        or request.get("inputs_digest") != draft_digest(project)
    ):
        raise ProjectError("Stale assisted review identity or draft")
    return state


def review_cycle(project: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Record explicit cycle/visual dispositions under the canonical project writer lock."""
    project = _root(project)
    try:
        with project_lock(project):
            if (
                not isinstance(request, dict)
                or type(request.get("schema_version")) is not int
                or request["schema_version"] != 2
            ):
                raise ProjectError("Invalid schema-2 review cycle request")
            request = json.loads(_json_bytes(request))
            action = request.get("action")
            if not isinstance(action, str):
                raise ProjectError("Invalid review cycle action")
            common = {"schema_version", "action", "developed_id", "base_revision", "inputs_digest"}
            fields = {
                "start": {"user_request"},
                "assess": {"cycle_id", "outcome", "comparison"},
                "stop": {"cycle_id", "reason"},
                "status": {"cycle_id"},
            }
            expected = (
                {"schema_version", "action"} if action == "status" else common
            ) | fields.get(action, set())
            if action not in fields or set(request) != expected:
                raise ProjectError("Unknown or invalid review cycle action")
            if action == "status":
                return _cycle_record(project, request["cycle_id"])
            state = _identity(project, request)
            if action == "start":
                _text(request["user_request"], "explicit user request")
                saved_layers(project, state["working_revision"], state["developed_id"])
                check_space(project, 1024**2)
                cycle_id = f"review-{uuid.uuid4().hex}"
                directory = saved_asset(project, f"requests/{cycle_id}")
                directory.mkdir(parents=True)
                record = {
                    "schema_version": 2,
                    "cycle_id": cycle_id,
                    "developed_id": state["developed_id"],
                    "user_request": request["user_request"],
                    "event_index": 0,
                    "previous_sha256": None,
                    "event": "start",
                    "attempts": 0,
                    "phase": "ready",
                    "stop_reason": None,
                    "best_revision": state["working_revision"],
                    "last_revision": state["working_revision"],
                    "status": "review_needed",
                    "request": request,
                }

                def recheck_start():
                    _identity(project, request)

                _atomic_json(
                    directory / f"000-{digest(_json_bytes(record))}.json",
                    record,
                    replace_existing=False,
                    validate_before_replace=recheck_start,
                )

                def recheck_initial_anchor():
                    _identity(project, request)
                    current, terminal = _cycle_events(project, cycle_id)
                    if current != record or terminal != digest(_json_bytes(record)):
                        raise ProjectError("Stale initial assisted review history")

                _atomic_bytes(
                    directory / "head.sha256",
                    (digest(_json_bytes(record)) + "\n").encode(),
                    replace_existing=False,
                    validate_before_replace=recheck_initial_anchor,
                )
                return record
            record = _cycle_record(project, request["cycle_id"])
            if record["developed_id"] != state["developed_id"] or record["phase"] == "stopped":
                raise ProjectError("Assisted review cycle stopped or belongs to another master")
            if action == "stop":
                _text(request["reason"], "stop reason")
                return _save_cycle(
                    project,
                    record,
                    "stop",
                    phase="stopped",
                    stop_reason=request["reason"],
                    request=request,
                )
            if record["phase"] != "awaiting_assessment":
                raise ProjectError("No pending assisted repair assessment")
            outcomes = {
                "improved",
                "no_progress",
                "regression",
                "ambiguous",
                "missing_source_evidence",
                "user_decision",
            }
            if request["outcome"] not in outcomes:
                raise ProjectError("Unknown source comparison disposition")
            _text(request["comparison"], "source comparison")
            revision = state["working_revision"]
            _foreground, alpha, manifest = saved_layers(project, revision, state["developed_id"])
            prefix = f"revisions/{revision}"
            operation = _read_json(project, f"{prefix}/request.json")
            if (
                manifest["kind"] != "repair"
                or digest(_json_bytes(operation)) != record["operation_sha256"]
            ):
                raise ProjectError(
                    "Pending assisted request has no matching complete current repair"
                )
            parent = operation["base_revision"]
            from .repair import scalar16

            parent_alpha = scalar16(saved_asset(project, f"revisions/{parent}/base_alpha16.png"))
            overview = _read_json(project, f"{prefix}/review/manifest.json")
            native = _review_project_locked(
                project, revision=revision, crops=[c["crop_xyxy"] for c in overview["crops"]]
            )
            after_name = str(Path(native["manifest_file"]).relative_to(project))
            after = _read_json(project, after_name)
            before_name = after["assets"]["before_manifest"]
            before = _read_json(project, before_name)
            from .repair import prepared_parent_layers

            before_parent = read_revision(project, parent, state["developed_id"])
            if before_parent["kind"] == "prepare":
                before_parent = prepared_parent_layers(project, parent, state["developed_id"])
            if (
                [c["crop_xyxy"] for c in before["crops"]]
                != [c["crop_xyxy"] for c in after["crops"]]
                or before["developed_id"] != after["developed_id"]
                or before["revision"] != before_parent["revision"]
                or after["revision"] != revision
            ):
                raise ProjectError("Mismatched native before/after review")
            outcome = request["outcome"]
            unchanged = np.array_equal(alpha, parent_alpha)
            if unchanged and outcome == "improved":
                outcome = "no_progress"
            stop = (
                outcome
                if outcome != "improved"
                else "attempt_budget_exhausted"
                if record["attempts"] == 2
                else None
            )
            # This is recorded source-based judgement, not a calibrated numerical quality score.
            return _save_cycle(
                project,
                record,
                "assess",
                phase="stopped" if stop else "ready",
                stop_reason=stop,
                best_revision=revision if outcome == "improved" else record["best_revision"],
                last_revision=revision,
                outcome=outcome,
                unchanged_alpha=unchanged,
                comparison=request["comparison"],
                result=_read_json(project, f"{prefix}/result.json"),
                before_manifest=before_name,
                after_manifest=after_name,
                request=request,
            )
    except (ValueError, KeyError, TypeError) as error:
        if isinstance(error, ProjectError):
            raise
        raise ProjectError(f"Invalid assisted review: {error}") from error


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 8000:
        raise ProjectError(f"Missing or invalid {label}")


def validate_assisted(
    project: Path, operation: dict[str, Any], *, resuming: bool = False
) -> dict[str, Any]:
    """Validate advisory evidence and chain; callers already hold the project lock."""
    from .operations import _input_file

    envelope = operation["assisted_review"]
    if (
        operation["kind"] not in {"prepare", "repair"}
        or not isinstance(envelope, dict)
        or set(envelope) != {"cycle_id", "review_manifest_file", "defect"}
    ):
        raise ProjectError("Invalid assisted proposal; only prepare/alpha repair available")
    record = _cycle_record(project, envelope["cycle_id"])
    if record["phase"] == "stopped":
        raise ProjectError("Assisted cycle stopped; two-attempt budget exhausted")
    if resuming:
        if record["phase"] != "awaiting_assessment" or record.get("operation_sha256") != digest(
            _json_bytes(operation)
        ):
            raise ProjectError("Resume must reuse the pending assisted repair attempt")
        return record
    if record["phase"] != "ready":
        raise ProjectError("Pending assisted assessment required before another operation")
    if record["attempts"] >= 2:
        raise ProjectError("Assisted two-attempt budget exhausted")
    state = _identity(project, operation)
    if state["developed_id"] != record["developed_id"]:
        raise ProjectError("Assisted cycle master differs")
    # Preparation may add guides, but a manual/new completed result cannot silently join this cycle.
    ancestor = state["working_revision"]
    while ancestor != record["last_revision"]:
        manifest = read_revision(project, ancestor, state["developed_id"])
        if manifest["kind"] != "prepare":
            raise ProjectError("Stale assisted cycle candidate; explicitly start a new review")
        ancestor = manifest["parent"]
    defect = envelope["defect"]
    keys = {
        "id",
        "classification",
        "location_xyxy",
        "source_evidence",
        "likely_cause",
        "uncertainty",
        "source_resolved",
    }
    if not isinstance(defect, dict) or set(defect) != keys:
        raise ProjectError("Invalid concrete source-visible defect")
    if (
        defect["classification"] in {"color", "shading", "user_decision"}
        or defect["source_resolved"] is False
        or isinstance(defect["source_evidence"], str)
        and not defect["source_evidence"].strip()
    ):
        _save_cycle(
            project,
            record,
            "stop",
            phase="stopped",
            stop_reason="unresolved_source_or_user_decision",
            request=operation,
        )
        raise ProjectError("Unresolved source or user decision; automatic cycle stopped")
    for name in ("id", "source_evidence", "likely_cause", "uncertainty"):
        _text(defect[name], name)
    if defect["classification"] != "alpha" or defect["source_resolved"] is not True:
        raise ProjectError("Unresolved/user-decision defect; color/shading effects unavailable")
    source, _ = load_developed(project, state["developed_id"])
    height, width = source.shape[:2]
    location = coordinates(defect["location_xyxy"], width, height, box=True)
    review_path = _input_file(project, envelope["review_manifest_file"])
    reviewed = json.loads(review_path.read_bytes())
    expected_hash = digest(
        _json_bytes(
            {
                "review": reviewed,
                "manifest": digest(
                    saved_asset(
                        project, f"revisions/{record['last_revision']}/manifest.json"
                    ).read_bytes()
                ),
            }
        )
    )
    if review_path != saved_asset(
        project, f"reviews/{record['last_revision']}/{expected_hash}/manifest.json"
    ):
        raise ProjectError("Invalid or changed immutable review manifest path")
    for name, checksum in reviewed["view_files"].items():
        if (
            Path(name).name != name
            or digest(
                saved_asset(
                    project, f"reviews/{record['last_revision']}/{expected_hash}/{name}"
                ).read_bytes()
            )
            != checksum
        ):
            raise ProjectError("Stale inspected crop asset")
    expected_revision = read_revision(project, record["last_revision"], state["developed_id"])
    if (
        reviewed.get("developed_id") != state["developed_id"]
        or reviewed.get("revision") != record["last_revision"]
        or reviewed.get("revision_inputs_digest") != expected_revision["draft_digest"]
        or reviewed.get("inputs_digest") != expected_revision["draft_digest"]
        or reviewed.get("stale_labels") != []
    ):
        raise ProjectError("Stale assisted source review manifest")
    x0, y0, x1, y1 = location
    if not any(
        c["crop_xyxy"][0] <= x0
        and c["crop_xyxy"][1] <= y0
        and c["crop_xyxy"][2] >= x1
        and c["crop_xyxy"][3] >= y1
        for c in reviewed["crops"]
    ):
        raise ProjectError("Defect outside inspected native crop")
    if operation["kind"] == "repair":
        sx0, sy0, sx1, sy1 = coordinates(operation["scope_xyxy"], width, height, box=True)
        if not (sx0 <= x0 < x1 <= sx1 and sy0 <= y0 < y1 <= sy1):
            raise ProjectError("Defect outside repair scope")
    return record


def reserve_assisted(project: Path, operation: dict[str, Any], *, resuming: bool) -> None:
    if "assisted_review" not in operation:
        return
    record = validate_assisted(project, operation, resuming=resuming)
    if not resuming:
        _save_cycle(
            project,
            record,
            "reserve",
            attempts=record["attempts"] + 1,
            phase="awaiting_assessment",
            operation_sha256=digest(_json_bytes(operation)),
            request=operation,
        )
