import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_ingest import saved_hashes, saved_raster
from test_matte_operations import approve, prepared, run_matte


def test_same_native_crops_and_manifest_mapping(tmp_path):
    from blackmask.review import review_project

    _, project, result = prepared(tmp_path)
    approve(project, result)
    matted = run_matte(project)
    output = review_project(
        project, revision=matted["revision"], crops=[[1, 0, 3, 2], [0, 0, 1, 1]]
    )
    manifest = json.loads(Path(output["manifest_file"]).read_text())
    assert manifest["crops"][0]["displayed_dimensions_wh"] == [2, 2]
    assert manifest["crops"][0]["native_origin_xy"] == [1, 0]
    directory = Path(output["manifest_file"]).parent
    black = np.array(
        Image.open(saved_raster(directory / saved_hashes(manifest["crops"][0])["black_RGB8_VIEW"]))
    )
    assert black.shape == (2, 2, 3)
    assert (
        review_project(project, revision=matted["revision"], crops=[[1, 0, 3, 2], [0, 0, 1, 1]])
        == output
    )


def test_preparation_overview_is_reduced_and_does_not_claim_a_matte(tmp_path):
    _, project, result = prepared(tmp_path)
    directory = project / "revisions" / result["revision"]
    with Image.open(directory / "preview.jpg") as image:
        assert image.format == "JPEG"
        assert image.width <= 3 and image.height <= 2
    record = json.loads((directory / "review/manifest.json").read_bytes())
    assert record["overview"] is True
    assert "preparation" in record["label"].lower()
    assert "no matte" in record["label"].lower()


def test_assisted_assessment_materializes_matching_native_evidence_outside_revision(tmp_path):
    from test_assisted_review import assess, baseline, prepare_repair, proposal, repair, start

    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    envelope = proposal(project, cycle)
    operation = prepare_repair(project, envelope)
    result = repair(project, operation)
    cycle = assess(project, cycle)
    before_path = project / cycle["before_manifest"]
    after_path = project / cycle["after_manifest"]
    assert before_path.is_relative_to(project / "reviews")
    assert after_path.is_relative_to(project / "reviews")
    before = json.loads(before_path.read_bytes())
    after = json.loads(after_path.read_bytes())
    prepared_parent = json.loads(
        (project / "revisions" / operation["base_revision"] / "manifest.json").read_bytes()
    )
    assert before["revision"] == prepared_parent["parent"]
    assert after["revision"] == result["revision"]
    assert [c["crop_xyxy"] for c in before["crops"]] == [c["crop_xyxy"] for c in after["crops"]]
    for path, record in [(before_path, before), (after_path, after)]:
        assert not record.get("overview", False)
        for crop in record["crops"]:
            x0, y0, x1, y1 = crop["crop_xyxy"]
            assert crop["scale_xy"] == [1, 1]
            for name in saved_hashes(crop).values():
                with Image.open(path.parent / name) as image:
                    assert image.size == (x1 - x0, y1 - y0)


@pytest.mark.parametrize("shape", [(401, 803), (1600, 1), (4000, 1)])
@pytest.mark.parametrize("background", [False, True])
def test_repair_overview_is_one_bounded_jpeg_with_recoverable_panel_coordinates(
    tmp_path, shape, background
):
    from blackmask.review import write_revision_overview

    height, width = shape
    source = np.full((*shape, 3), [12231, 33333, 51001], np.uint16)
    alpha = np.full(shape, 32768, np.uint16)
    crops = [[0, 0, width, height]]
    if width > 1:
        crops.append([100, 0, 300, height])
    write_revision_overview(
        tmp_path / "review",
        source,
        source,
        alpha,
        developed_id="a" * 64,
        revision="rev-002",
        crops=crops,
        background16=source if background else None,
    )
    write_revision_overview(
        tmp_path / "review-before",
        source,
        source,
        alpha,
        developed_id="a" * 64,
        revision="rev-001",
        crops=crops,
        background16=source if background else None,
    )
    with Image.open(tmp_path / "preview.jpg") as image:
        assert image.format == "JPEG" and max(image.size) <= 1600
        size = image.size
    assert [p.name for p in tmp_path.rglob("*") if p.suffix in {".png", ".tif", ".jpg"}] == [
        "preview.jpg"
    ]
    boxes = []
    for name in ["review", "review-before"]:
        record = json.loads((tmp_path / name / "manifest.json").read_bytes())
        assert record["overview_dimensions_wh"] == list(size)
        for crop in record["crops"]:
            x0, y0, x1, y1 = crop["crop_xyxy"]
            assert crop["native_origin_xy"] == [x0, y0]
            for panel, box in crop["panel_boxes_xyxy"].items():
                left, top, right, bottom = box
                assert 0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]
                assert right - left <= x1 - x0 and bottom - top <= y1 - y0
                if panel == "source":
                    assert crop["displayed_dimensions_wh"] == [right - left, bottom - top]
                    assert crop["scale_xy"] == [
                        (x1 - x0) / (right - left),
                        (y1 - y0) / (bottom - top),
                    ]
                boxes.append((name, tuple(box)))
    assert len({box for _, box in boxes}) == len(boxes)
    for index, (_, first) in enumerate(boxes):
        for _, second in boxes[index + 1 :]:
            assert (
                first[2] <= second[0]
                or second[2] <= first[0]
                or first[3] <= second[1]
                or second[3] <= first[1]
            )
