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


def test_explicit_comparison_retains_only_sheet_and_exact_manifest(tmp_path):
    from blackmask.review import review_project

    _, project, result = prepared(tmp_path)
    approve(project, result)
    matted = run_matte(project)
    state = (project / "state.json").read_bytes()
    response = review_project(
        project, revision=matted["revision"], crops=[[1, 0, 3, 2]], comparison=True
    )
    directory = Path(response["comparison_manifest_file"]).parent
    assert {p.name for p in directory.iterdir()} == {"comparison_RGB8_VIEW.jpg", "manifest.json"}
    record = json.loads((directory / "manifest.json").read_bytes())
    assert record["kind"] == "comparison" and record["native_authoring_allowed"] is False
    assert record["native_evidence"] is None
    assert record["crops"][0]["crop_xyxy"] == [1, 0, 3, 2]
    assert record["crops"][0]["native_origin_xy"] == [1, 0]
    with Image.open(directory / "comparison_RGB8_VIEW.jpg") as image:
        assert image.format == "JPEG" and max(image.size) <= 1600
    assert not list((project / "reviews").rglob("*.png"))
    assert (project / "state.json").read_bytes() == state


@pytest.mark.parametrize("managed_library", [False, True])
def test_comparison_success_removes_only_current_intermediates(tmp_path, managed_library):
    from test_library import inventory
    from test_previews import generate, managed

    from blackmask.review import review_project

    if managed_library:
        _, config, project = managed(tmp_path)
        generate(project, config)
        photo_id = json.loads((project / "source.json").read_bytes())["library"]["photo_id"]
        root = config.destination / "Comparisons" / photo_id
    else:
        _, project, prepared_result = prepared(tmp_path)
        approve(project, prepared_result)
        run_matte(project)
        config = None
        root = project / "reviews/comparisons"
    prior_native = review_project(project, crops=[[0, 0, 1, 1]], storage_config=config)
    assert Path(prior_native["manifest_file"]).is_file()
    previous_stage = root / ".comparison-previous"
    (previous_stage / "review").mkdir(parents=True)
    (previous_stage / "review/manifest.json").write_bytes(b"previous recovery manifest")
    (previous_stage / "preview.jpg").write_bytes(b"previous recovery preview")
    (previous_stage / "unknown.txt").write_bytes(b"user stage notes")
    previous_output = root / "unrelated-output"
    previous_output.mkdir()
    (previous_output / "manifest.json").write_bytes(b"preserve unrelated output")
    (project / "user-notes.txt").write_bytes(b"preserve project notes")
    protected = inventory(project)
    prior_stage, prior_output = inventory(previous_stage), inventory(previous_output)

    response = review_project(
        project, crops=[[1, 0, 3, 2]], comparison=True, retain_native=True, storage_config=config
    )
    destination = Path(response["comparison_manifest_file"]).parent
    assert inventory(previous_stage) == prior_stage and inventory(previous_output) == prior_output
    current = inventory(project)
    assert all(current[name] == value for name, value in protected.items())
    assert {path.name for path in destination.iterdir()} == {
        "manifest.json",
        "comparison_RGB8_VIEW.jpg",
    }
    assert {path.name for path in root.iterdir()} == {
        previous_stage.name,
        previous_output.name,
        destination.name,
    }
    complete_project, complete_outputs = inventory(project), inventory(root)
    assert review_project(
        project, crops=[[1, 0, 3, 2]], comparison=True, retain_native=True, storage_config=config
    ) == {**response, "reused": True}
    assert inventory(project) == complete_project and inventory(root) == complete_outputs


@pytest.mark.parametrize(
    "failure",
    [
        "extra-root",
        "extra-review",
        "file-symlink",
        "review-symlink",
        "stage-symlink",
        "replacement",
        "changed",
        "unlink-first",
        "unlink-late",
    ],
)
def test_comparison_cleanup_failure_preserves_published_and_unfamiliar_files(
    tmp_path, monkeypatch, failure
):
    from test_library import inventory

    from blackmask import review
    from blackmask.project import ProjectError

    _, project, prepared_result = prepared(tmp_path)
    approve(project, prepared_result)
    run_matte(project)
    protected = inventory(project)
    outside = tmp_path / "unrelated"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"unrelated user data")
    reached = {}
    original_publish, original_unlink = review.publish_artifacts, review.os.unlink

    def publish_then_inject(directory, destination):
        comparison = (directory / "comparison_RGB8_VIEW.jpg").is_file()
        result = original_publish(directory, destination)
        if not comparison:
            return result
        stage = directory.parent
        if failure.startswith("extra-"):
            target = stage if failure == "extra-root" else stage / "review"
            (target / "unknown.txt").write_bytes(b"preserve unfamiliar stage content")
        elif failure in {"file-symlink", "replacement", "changed"}:
            preview = stage / "preview.jpg"
            if failure != "changed":
                preview.rename(outside / "original-preview.jpg")
            if failure == "file-symlink":
                (outside / "foreign.jpg").write_bytes(b"unrelated image")
                preview.symlink_to(outside / "foreign.jpg")
            elif failure == "replacement":
                preview.write_bytes((outside / "original-preview.jpg").read_bytes())
            else:
                preview.write_bytes(preview.read_bytes() + b"user change")
        elif failure in {"review-symlink", "stage-symlink"}:
            target = stage / "review" if failure == "review-symlink" else stage
            target.rename(outside / "original-directory")
            foreign = outside / "foreign-directory"
            foreign.mkdir()
            (foreign / "manifest.json").write_bytes(b"foreign manifest")
            target.symlink_to(foreign, target_is_directory=True)
        reached.update(
            stage=stage,
            destination=destination,
            stage_files=inventory(stage),
            outside=inventory(outside),
            published=inventory(destination),
            native={p.name: inventory(p) for p in (project / "reviews").glob("rev-*")},
        )
        return result

    def fail_unlink(name, *args, **kwargs):
        blocked = "manifest.json" if failure == "unlink-first" else "preview.jpg"
        if reached and failure.startswith("unlink-") and name == blocked:
            raise OSError("synthetic intermediate unlink failure")
        return original_unlink(name, *args, **kwargs)

    monkeypatch.setattr(review, "publish_artifacts", publish_then_inject)
    monkeypatch.setattr(review.os, "unlink", fail_unlink)
    with pytest.raises(ProjectError, match="durably published.*stage cleanup failed") as error:
        review.review_project(project, comparison=True, retain_native=True, crops=[[1, 0, 3, 2]])
    assert str(reached["destination"]) in str(error.value)
    assert str(reached["stage"]) in str(error.value)
    assert inventory(reached["destination"]) == reached["published"]
    assert inventory(outside) == reached["outside"]
    assert {p.name: inventory(p) for p in (project / "reviews").glob("rev-*")} == reached["native"]
    current = inventory(project)
    assert all(current[name] == value for name, value in protected.items())
    remaining = inventory(reached["stage"])
    if failure == "unlink-late":
        assert remaining == {"preview.jpg": reached["stage_files"]["preview.jpg"]}
    else:
        assert remaining == reached["stage_files"]
    recovered = review.review_project(
        project, comparison=True, retain_native=True, crops=[[1, 0, 3, 2]]
    )
    assert recovered["reused"] is True
    assert inventory(reached["stage"]) == remaining and inventory(outside) == reached["outside"]
    assert inventory(reached["destination"]) == reached["published"]


def test_saved_comparison_resized_spatial_markers_and_singleton_geometry(tmp_path):
    from test_ingest import srgb_profile, tiff
    from test_operations import edits, request

    from blackmask import operations
    from blackmask.project import create_project
    from blackmask.review import review_project

    pixels = np.full((600, 1000, 3), 30 * 257, dtype=np.uint16)
    pixels[113:193, 141:261] = np.array([220, 35, 45], dtype=np.uint16) * 257
    pixels[233:313, 581:701] = np.array([20, 210, 65], dtype=np.uint16) * 257
    pixels[373:453, 781:881] = np.array([35, 65, 225], dtype=np.uint16) * 257
    pixels[599, 999] = 120 * 257
    source = tiff(tmp_path / "spatial-markers.tif", pixels, profile=srgb_profile())
    project = tmp_path / "project"
    create_project(source, project, {})
    guide = edits(
        project,
        [{"id": "solid", "role": "foreground", "shape": "rectangle", "xyxy": [0, 0, 1000, 600]}],
    )
    prepared_result = operations.apply_operation(project, request(project, guide_edits_file=guide))
    approve(project, prepared_result)
    run_matte(project)
    state = (project / "state.json").read_bytes()
    result = review_project(
        project, comparison=True, crops=[[101, 73, 902, 474], [999, 599, 1000, 600]]
    )
    manifest = Path(result["comparison_manifest_file"])
    record = json.loads(manifest.read_bytes())
    with Image.open(manifest.parent / "comparison_RGB8_VIEW.jpg") as image:
        assert image.format == "JPEG" and image.mode == "RGB"
        assert image.size == (1596, 182)
        decoded = np.array(image).astype(np.int16)
    # Independently calculated: six panels of an 801x401 crop fit 1600 pixels.
    # Each is floor(1600/6)=266 by floor(401*1600/(801*6))=133.
    # Two 24-pixel labels and the last native 1x1 row give height 182.
    assert record["dimensions_wh"] == [1596, 182]
    assert record["panel_order"] == ["source", "black", "gray", "white", "alpha", "result"]
    first, singleton = record["crops"]
    assert first["crop_xyxy"] == [101, 73, 902, 474]
    assert first["native_origin_xy"] == [101, 73]
    assert first["displayed_dimensions_wh"] == [266, 133]
    assert first["scale_xy"] == [801 / 266, 401 / 133]
    assert first["panel_boxes_xyxy"] == {
        "source": [0, 24, 266, 157],
        "black": [266, 24, 532, 157],
        "gray": [532, 24, 798, 157],
        "white": [798, 24, 1064, 157],
        "alpha": [1064, 24, 1330, 157],
        "result": [1330, 24, 1596, 157],
    }
    assert singleton["crop_xyxy"] == [999, 599, 1000, 600]
    assert singleton["native_origin_xy"] == [999, 599]
    assert singleton["displayed_dimensions_wh"] == [1, 1]
    assert singleton["scale_xy"] == [1, 1]
    assert singleton["panel_boxes_xyxy"] == {
        "source": [0, 181, 1, 182],
        "black": [1, 181, 2, 182],
        "gray": [2, 181, 3, 182],
        "white": [3, 181, 4, 182],
        "alpha": [4, 181, 5, 182],
        "result": [5, 181, 6, 182],
    }
    # Literal sample centers come from source markers, not generated boxes/scales.
    # Interior 3x3 samples avoid LANCZOS edges; 12/255 permits the two JPEG encodes
    # and chroma quantization, well below the >100-channel marker differences.
    for offset in [0, 266, 532, 798, 1330]:
        for x, y, color in [
            (33, 50, [220, 35, 45]),
            (179, 90, [20, 210, 65]),
            (242, 136, [35, 65, 225]),
        ]:
            sample = decoded[y - 1 : y + 2, x + offset - 1 : x + offset + 2]
            assert np.max(np.abs(sample - color)) <= 12
    assert np.min(decoded[49:52, 1096:1099]) >= 243
    assert (project / "state.json").read_bytes() == state


def test_comparison_reuse_does_not_recreate_missing_native_directory(tmp_path):
    from blackmask.project import ProjectError
    from blackmask.review import review_project

    _, project, result = prepared(tmp_path)
    approve(project, result)
    run_matte(project)
    response = review_project(project, comparison=True, retain_native=True)
    comparison = Path(response["comparison_manifest_file"])
    native = Path(response["native_manifest_file"]).parent
    original = {p.name: p.read_bytes() for p in native.iterdir()}
    preserved = tmp_path / "preserved-native-evidence"
    native.rename(preserved)
    comparison_bytes = {p.name: p.read_bytes() for p in comparison.parent.iterdir()}
    state = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError) as error:
        review_project(project, comparison=True, retain_native=True)
    assert str(comparison.parent) in str(error.value) and str(native) in str(error.value)
    assert not native.exists() and not native.is_symlink()
    assert {p.name: p.read_bytes() for p in preserved.iterdir()} == original
    assert {p.name: p.read_bytes() for p in comparison.parent.iterdir()} == comparison_bytes
    assert (project / "state.json").read_bytes() == state


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


@pytest.mark.parametrize("damage", ["manifest", "pixel", "symlink", "foreign"])
def test_comparison_native_dependencies_fail_closed_without_republication(
    tmp_path, monkeypatch, damage
):
    from blackmask import review
    from blackmask.project import ProjectError

    _, project, result = prepared(tmp_path)
    approve(project, result)
    run_matte(project)
    output = review.review_project(project, comparison=True, retain_native=True)
    comparison = Path(output["comparison_manifest_file"])
    native = Path(output["native_manifest_file"])
    preserved = {p.name: p.read_bytes() for p in comparison.parent.iterdir()}
    if damage == "manifest":
        native.write_bytes(native.read_bytes() + b" ")
    elif damage == "pixel":
        member = next(native.parent.glob("*.png"))
        member.write_bytes(member.read_bytes() + b" ")
    elif damage == "symlink":
        original = native.parent
        original.rename(tmp_path / "retained-native")
        original.symlink_to(tmp_path / "retained-native", target_is_directory=True)
    else:
        record = json.loads(comparison.read_bytes())
        record["native_evidence"]["after"]["manifest_file"] = "../foreign/manifest.json"
        comparison.write_text(json.dumps(record))
        preserved["manifest.json"] = comparison.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("Existing comparison must validate dependencies before any native publisher")

    monkeypatch.setattr(review, "_review_project_locked", forbidden)
    with pytest.raises(ProjectError):
        review.review_project(project, comparison=True, retain_native=True)
    assert {p.name: p.read_bytes() for p in comparison.parent.iterdir()} == preserved


def test_comparison_direct_before_missing_and_intact_reuse(tmp_path, monkeypatch):
    from test_assisted_review import baseline, prepare_repair, proposal, repair, start

    from blackmask import review
    from blackmask.project import ProjectError

    _, project, _, _ = baseline(tmp_path)
    cycle = start(project)
    repair(project, prepare_repair(project, proposal(project, cycle)))
    first = review.review_project(project, comparison=True, retain_native=True)
    comparison = Path(first["comparison_manifest_file"])
    record = json.loads(comparison.read_bytes())
    before = project / record["native_evidence"]["before"]["manifest_file"]
    after = Path(first["native_manifest_file"])
    assert before != after

    def forbidden(*args, **kwargs):
        pytest.fail("Intact comparison reuse must not republish native evidence")

    monkeypatch.setattr(review, "_review_project_locked", forbidden)
    assert review.review_project(project, comparison=True, retain_native=True) == {
        **first,
        "reused": True,
    }
    native_bytes = after.read_bytes()
    before.parent.rename(tmp_path / "preserved-before")
    with pytest.raises(ProjectError) as error:
        review.review_project(project, comparison=True, retain_native=True)
    assert str(before.parent) in str(error.value) and str(comparison.parent) in str(error.value)
    assert not before.parent.exists()
    assert after.read_bytes() == native_bytes


def test_comparison_partial_native_publication_can_finish_without_replacing_evidence(
    tmp_path, monkeypatch
):
    from test_library import inventory

    from blackmask import review
    from blackmask.project import ProjectError

    _, project, result = prepared(tmp_path)
    approve(project, result)
    run_matte(project)
    original = review.publish_artifacts

    def interrupted(directory, destination):
        if (directory / "comparison_RGB8_VIEW.jpg").exists():
            raise OSError("synthetic publication interruption")
        return original(directory, destination)

    monkeypatch.setattr(review, "publish_artifacts", interrupted)
    state = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="native evidence retained") as error:
        review.review_project(project, comparison=True, retain_native=True)
    native = next((project / "reviews").glob("rev-*/*/manifest.json"))
    assert str(native) in str(error.value)
    kept = {p.name: (p.read_bytes(), p.stat().st_ino) for p in native.parent.iterdir()}
    assert not list((project / "reviews/comparisons").glob("rev-*/manifest.json"))
    stage = next((project / "reviews/comparisons").glob(".comparison-*"))
    retained_stage = inventory(stage)
    assert {"preview.jpg", "review/manifest.json", "bundle/manifest.json"} <= retained_stage.keys()
    monkeypatch.setattr(review, "publish_artifacts", original)
    result = review.review_project(project, comparison=True, retain_native=True)
    assert result["native_manifest_file"] == str(native)
    assert {p.name: (p.read_bytes(), p.stat().st_ino) for p in native.parent.iterdir()} == kept
    assert inventory(stage) == retained_stage
    assert (project / "state.json").read_bytes() == state


@pytest.mark.parametrize("dependency", ["after", "before"])
@pytest.mark.parametrize("existing_comparison", [False, True])
def test_comparison_native_parent_sync_failure_remains_unconfirmed_until_retry(
    tmp_path, monkeypatch, dependency, existing_comparison
):
    import importlib

    from test_assisted_review import baseline, prepare_repair, proposal, repair, start

    from blackmask import review
    from blackmask.project import ProjectError

    export = importlib.import_module("blackmask.export")
    _, project, before, _ = baseline(tmp_path)
    cycle = start(project)
    after = repair(project, prepare_repair(project, proposal(project, cycle)))
    crops = [[1, 0, 3, 2]]
    target_parent = project / "reviews" / (after if dependency == "after" else before)["revision"]

    def snapshot(directory):
        return {
            str(path.relative_to(directory)): (
                path.read_bytes() if path.is_file() else None,
                path.stat().st_mode,
                path.stat().st_ino,
            )
            for path in [directory, *directory.rglob("*")]
        }

    state = {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file() and path.relative_to(project).parts[0] != "reviews"
    }
    if existing_comparison:
        first = review.review_project(project, crops=crops, comparison=True, retain_native=True)
        comparison = Path(first["comparison_manifest_file"]).parent
        complete_bytes = snapshot(comparison)

    original_export_sync, original_review_sync = export._sync_directory, review._sync_directory
    failed_parents = []

    def failed_sync(path):
        if path == target_parent:
            failed_parents.append(path)
            raise OSError(f"synthetic native parent sync failure at {path}")
        original_export_sync(path)

    monkeypatch.setattr(export, "_sync_directory", failed_sync)
    monkeypatch.setattr(review, "_sync_directory", failed_sync)
    with pytest.raises(ProjectError, match="completion unconfirmed"):
        review.review_project(project, crops=crops, comparison=True, retain_native=True)
    assert failed_parents
    native = next(
        path.parent
        for path in target_parent.glob("*/manifest.json")
        if [item["crop_xyxy"] for item in json.loads(path.read_bytes())["crops"]] == crops
    )
    kept_native = snapshot(native)
    if not existing_comparison:
        # The fault follows rename of this exact native directory; no primary was published.
        assert not list((project / "reviews/comparisons").glob("rev-*/manifest.json"))
    with pytest.raises(ProjectError, match="completion unconfirmed") as retry_error:
        review.review_project(project, crops=crops, comparison=True, retain_native=True)
    assert str(target_parent) in str(retry_error.value)
    assert snapshot(native) == kept_native
    if existing_comparison:
        assert snapshot(comparison) == complete_bytes

    # Remove only the injected fault, retaining every partial file and its mode/inode.
    monkeypatch.setattr(export, "_sync_directory", original_export_sync)
    monkeypatch.setattr(review, "_sync_directory", original_review_sync)
    recovered = review.review_project(project, crops=crops, comparison=True, retain_native=True)
    record = json.loads(Path(recovered["comparison_manifest_file"]).read_bytes())
    assert (
        project / record["native_evidence"][dependency]["manifest_file"] == native / "manifest.json"
    )
    assert snapshot(native) == kept_native
    if existing_comparison:
        assert recovered == {**first, "reused": True}
        assert snapshot(comparison) == complete_bytes
    assert {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file() and path.relative_to(project).parts[0] != "reviews"
    } == state


@pytest.mark.parametrize("mode", ["add-margins", "match-series"])
def test_comparison_presentation_binds_layout_and_keeps_native_coordinates(tmp_path, mode):
    from test_effects import fixture_project
    from test_framing import margins
    from test_series_framing import series_settings

    from blackmask.project import ProjectError, digest, read_project
    from blackmask.review import review_project

    project, _, revision = fixture_project(tmp_path)
    presentation = {
        "mode": mode,
        "revision": revision["revision"],
        "developed_id": read_project(project)["developed_id"],
        "revision_manifest_sha256": digest(
            (project / "revisions" / revision["revision"] / "manifest.json").read_bytes()
        ),
        **(
            {"margins": margins()}
            if mode == "add-margins"
            else {"settings": series_settings(output_width_px=40, output_height_px=50).to_dict()}
        ),
    }
    before = (project / "state.json").read_bytes()
    result = review_project(
        project, comparison=True, presentation=presentation, crops=[[1, 0, 6, 4], [5, 3, 6, 4]]
    )
    path = Path(result["comparison_manifest_file"])
    record = json.loads(path.read_bytes())
    assert record["request"]["presentation"] == presentation
    assert record["presentation"]["mode"] == mode
    assert record["presentation"]["native_authoring_allowed"] is False
    assert [c["crop_xyxy"] for c in record["crops"]] == [[1, 0, 6, 4], [5, 3, 6, 4]]
    assert record["crops"][1]["native_origin_xy"] == [5, 3]
    assert max(record["dimensions_wh"]) <= 1600
    assert review_project(
        project, comparison=True, presentation=presentation, crops=[[1, 0, 6, 4], [5, 3, 6, 4]]
    ) == {**result, "reused": True}
    with pytest.raises(ProjectError, match="Stale comparison presentation"):
        review_project(
            project,
            comparison=True,
            presentation={**presentation, "revision_manifest_sha256": "0" * 64},
        )
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize(
    "damage", ["origin", "scale", "panel", "presentation", "jpeg", "label", "extra-field"]
)
def test_comparison_reuse_rejects_altered_geometry_or_sheet(tmp_path, damage):
    from blackmask.project import ProjectError
    from blackmask.review import review_project

    _, project, prepared_result = prepared(tmp_path)
    approve(project, prepared_result)
    run_matte(project)
    result = review_project(project, comparison=True, crops=[[1, 0, 3, 2]])
    path = Path(result["comparison_manifest_file"])
    record = json.loads(path.read_bytes())
    if damage == "origin":
        record["crops"][0]["native_origin_xy"] = [0, 0]
    elif damage == "scale":
        record["crops"][0]["scale_xy"] = [2, 2]
    elif damage == "panel":
        record["crops"][0]["panel_boxes_xyxy"]["source"][0] = 1
    elif damage == "presentation":
        record["presentation"] = {"mode": "add-margins"}
    elif damage == "label":
        record["label"] = "Native evidence"
    elif damage == "extra-field":
        record["foreign"] = True
    else:
        sheet = path.parent / "comparison_RGB8_VIEW.jpg"
        sheet.write_bytes(sheet.read_bytes() + b"changed")
    path.write_text(json.dumps(record))
    preserved = {p.name: p.read_bytes() for p in path.parent.iterdir()}
    with pytest.raises(ProjectError):
        review_project(project, comparison=True, crops=[[1, 0, 3, 2]])
    assert {p.name: p.read_bytes() for p in path.parent.iterdir()} == preserved


def test_managed_comparison_preserves_gallery_latest_acceptance_and_originals(tmp_path):
    from test_library import inventory
    from test_previews import generate, jpeg, managed

    from blackmask.project import read_project
    from blackmask.review import review_project

    _, config, project = managed(tmp_path, subject=("Écorce 多言語 " + "long name " * 20).strip())
    generate(project, config)
    state = read_project(project)
    protected = {
        name: inventory(project / name)
        for name in ("assets", "revisions", "exports")
        if (project / name).exists()
    }
    original = inventory(project.parent / "original")
    gallery = jpeg(config, project).read_bytes()
    preview = (project / "preview.json").read_bytes()
    result = review_project(project, comparison=True, storage_config=config)
    path = Path(result["comparison_manifest_file"])
    photo_id = json.loads((project / "source.json").read_bytes())["library"]["photo_id"]
    assert path.parent.parent == config.destination / "Comparisons" / photo_id
    record = json.loads(path.read_bytes())
    assert record["request"]["library"] == {
        "photo_id": photo_id,
        "folder_basename": project.parent.name,
    }
    assert record["request"]["appearance_stale_by_revision"] == {state["working_revision"]: False}
    assert read_project(project) == state
    assert inventory(project.parent / "original") == original
    assert all(inventory(project / name) == value for name, value in protected.items())
    assert jpeg(config, project).read_bytes() == gallery
    assert (project / "preview.json").read_bytes() == preview


def test_comparison_rechecks_native_pixels_after_publication_before_completion(
    tmp_path, monkeypatch
):
    from blackmask import review
    from blackmask.project import ProjectError

    _, project, result = prepared(tmp_path)
    approve(project, result)
    run_matte(project)
    original = review._comparison_native_binding
    changed = []

    def mutate_after_binding(*args, **kwargs):
        binding = original(*args, **kwargs)
        native = (project / binding["manifest_file"]).parent
        member = next(native.glob("*.png"))
        member.write_bytes(member.read_bytes() + b"changed after binding")
        changed.append(member)
        return binding

    monkeypatch.setattr(review, "_comparison_native_binding", mutate_after_binding)
    state = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="native evidence retained"):
        review.review_project(project, comparison=True, retain_native=True, crops=[[1, 0, 3, 2]])
    assert changed and changed[0].read_bytes().endswith(b"changed after binding")
    assert not list((project / "reviews/comparisons").glob("rev-*/manifest.json"))
    assert (project / "state.json").read_bytes() == state


@pytest.mark.parametrize("damage", ["extra", "missing", "symlink"])
def test_comparison_output_collision_preserves_owned_artifacts(tmp_path, damage):
    from blackmask.project import ProjectError
    from blackmask.review import review_project

    _, project, result = prepared(tmp_path)
    approve(project, result)
    run_matte(project)
    first = review_project(project, comparison=True, crops=[[1, 0, 3, 2]])
    path = Path(first["comparison_manifest_file"])
    if damage == "extra":
        (path.parent / "unknown.txt").write_text("preserve")
    elif damage == "missing":
        path.rename(tmp_path / "retained-manifest.json")
    else:
        path.parent.rename(tmp_path / "retained-comparison")
        path.parent.symlink_to(tmp_path / "retained-comparison", target_is_directory=True)
    before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
    with pytest.raises((ProjectError, OSError)):
        review_project(project, comparison=True, crops=[[1, 0, 3, 2]])
    assert {p.name: p.read_bytes() for p in path.parent.iterdir()} == before


@pytest.mark.parametrize("failure", ["sync", "late-source"])
def test_comparison_late_publication_failure_preserves_output_and_reports_uncertainty(
    tmp_path, monkeypatch, failure
):
    import importlib

    from test_library import inventory

    export = importlib.import_module("blackmask.export")
    from blackmask.project import ProjectError
    from blackmask.review import review_project

    _, project, result = prepared(tmp_path)
    approve(project, result)
    run_matte(project)
    source = project / "source.json"
    source_bytes = source.read_bytes()
    original = export._sync_directory
    reached = []

    def failed_sync(path):
        original(path)
        if path == project / "reviews/comparisons":
            reached.append(path)
            if failure == "sync":
                raise OSError("synthetic parent sync failure")
            source.write_bytes(source_bytes + b" ")

    monkeypatch.setattr(export, "_sync_directory", failed_sync)
    with pytest.raises(ProjectError, match="completion unconfirmed"):
        review_project(project, comparison=True, crops=[[1, 0, 3, 2]])
    assert reached
    manifest = next((project / "reviews/comparisons").glob("rev-*/manifest.json"))
    kept = {p.name: p.read_bytes() for p in manifest.parent.iterdir()}
    assert set(kept) == {"manifest.json", "comparison_RGB8_VIEW.jpg"}
    stage = next((project / "reviews/comparisons").glob(".comparison-*"))
    retained_stage = inventory(stage)
    assert {"preview.jpg", "review/manifest.json"} <= retained_stage.keys()
    monkeypatch.setattr(export, "_sync_directory", original)
    source.write_bytes(source_bytes)
    recovered = review_project(project, comparison=True, crops=[[1, 0, 3, 2]])
    assert recovered["reused"] is True and recovered["comparison_manifest_file"] == str(manifest)
    assert {p.name: p.read_bytes() for p in manifest.parent.iterdir()} == kept
    assert inventory(stage) == retained_stage
