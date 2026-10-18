"""Recorded-guide synthetic J1; fixture approval controls are not human photo evidence."""

import importlib
import json
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from test_operations import edits, opened, request

from blackmask import operations
from blackmask.project import ProjectError, load_master, read_project


def prepared(tmp_path):
    source, project = opened(tmp_path)
    filename = edits(
        project,
        [
            {"id": "fg", "role": "foreground", "shape": "rectangle", "xyxy": [0, 0, 1, 1]},
            {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [2, 1, 3, 2]},
        ],
    )
    result = operations.apply_operation(project, request(project, guide_edits_file=filename))
    return source, project, result


def approve(project, result):
    return operations.accept_trimap(
        project, result["revision"], result["master_id"], result["inputs_digest"]
    )


class StubSession:
    identity: ClassVar[dict] = {"model": "synthetic-test-only", "packages": {}, "hashes": {}}

    def __init__(self, cache):
        pass

    def predict(self, rgb, trimap, device):
        return np.full(trimap.shape, 0.25), {"fixture": "synthetic-test-only", "device": device}


def run_matte(project):
    with patch("blackmask.operations.VitMatteSession", StubSession):
        return operations.apply_operation(
            project, request(project, kind="matte"), model_cache=Path("unused-explicit-test-cache")
        )


def test_recorded_synthetic_j1_saved_layers_acceptance_export(tmp_path):
    source, project, prepared_result = prepared(tmp_path)
    capture = source.read_bytes()
    approve(project, prepared_result)
    result = run_matte(project)
    revision = project / "revisions" / result["revision"]
    alpha = np.array(Image.open(revision / "base_alpha16.png"))
    assert (
        alpha.dtype == np.uint16
        and alpha[0, 0] == 65535
        and alpha[1, 2] == 0
        and alpha[0, 1] == 16384
    )
    master, _ = load_master(project, result["master_id"])
    np.testing.assert_array_equal(tifffile.imread(revision / "foreground_rgb16.tif"), master)
    review = json.loads((revision / "review/manifest.json").read_text())
    assert review["crops"][0]["crop_xyxy"] == [0, 0, 3, 2]
    assert review["crops"][0]["displayed_dimensions_wh"] == [3, 2]
    assert read_project(project)["accepted_revision"] is None
    export = importlib.import_module("blackmask.export")
    with pytest.raises(ProjectError, match="accepted"):
        export.export_project(project)
    draft = export.export_project(project, revision=result["revision"], draft=True)
    assert "DRAFT" in draft["directory"]
    operations.accept_revision(project, result["revision"])
    output = export.export_project(project)
    black = tifffile.imread(Path(output["directory"]) / "black_rgb16.tif")
    expected = np.rint(
        master.astype(np.float64) * (alpha.astype(np.float64) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(black, expected)
    np.testing.assert_array_equal(
        np.array(Image.open(Path(output["directory"]) / "alpha16.png")), alpha
    )
    rgba = np.array(Image.open(Path(output["directory"]) / "transparent_RGBA8_VIEW.png"))
    np.testing.assert_array_equal(rgba[..., :3], np.rint(master / 257).astype(np.uint8))
    assert export.export_project(project) == output
    assert source.read_bytes() == capture
    (Path(output["directory"]) / "black_rgb16.tif").write_bytes(b"different")
    with pytest.raises(ProjectError, match="collision|differ|hash"):
        export.export_project(project)


def test_trimap_gate_and_stale_approval_preserve_state(tmp_path):
    _, project, result = prepared(tmp_path)
    before = (project / "state.json").read_bytes()
    with pytest.raises(ProjectError, match="trimap|review"):
        run_matte(project)
    assert (project / "state.json").read_bytes() == before
    with pytest.raises(ProjectError, match="Stale|stale"):
        operations.accept_trimap(project, result["revision"], "0" * 64, result["inputs_digest"])
    approve(project, result)
    with (project / "recipe.toml").open("a") as stream:
        stream.write("\n# changed draft\n")
    with pytest.raises(ProjectError, match="Stale|stale"):
        run_matte(project)
    assert (project / "state.json").read_bytes() == before


@pytest.mark.parametrize("failure", ["low-disk", "nonfinite", "state-edit", "pointer"])
def test_matte_failure_retains_accepted_revision(tmp_path, failure):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    matted = run_matte(project)
    operations.accept_revision(project, matted["revision"])
    accepted = read_project(project)["accepted_revision"]
    prepared_again = operations.apply_operation(project, request(project))
    approve(project, prepared_again)
    before = (project / "state.json").read_bytes()

    def prediction(rgb, trimap, device):
        if failure == "state-edit":
            state = json.loads(before)
            state["status"] = "external edit"
            (project / "state.json").write_text(json.dumps(state))
        return np.full(trimap.shape, np.nan if failure == "nonfinite" else 0.75), {}

    with (
        patch.object(StubSession, "identity", {"fault_probe": failure}),
        patch.object(StubSession, "predict", side_effect=prediction),
        patch("blackmask.operations.VitMatteSession", StubSession),
    ):
        if failure == "low-disk":
            with (
                patch(
                    "blackmask.project.shutil.disk_usage",
                    return_value=type("Disk", (), {"free": 1})(),
                ),
                pytest.raises(ProjectError, match="space"),
            ):
                operations.apply_operation(
                    project, request(project, kind="matte"), model_cache=Path("unused")
                )
        elif failure == "pointer":
            with (
                patch("blackmask.operations._atomic_json", side_effect=OSError("injected pointer")),
                pytest.raises(OSError),
            ):
                operations.apply_operation(
                    project, request(project, kind="matte"), model_cache=Path("unused")
                )
        else:
            with pytest.raises((ProjectError, ValueError), match="finite|Stale|stale"):
                operations.apply_operation(
                    project, request(project, kind="matte"), model_cache=Path("unused")
                )
    after = json.loads((project / "state.json").read_text())
    assert after["accepted_revision"] == accepted
    if failure != "state-edit":
        assert (project / "state.json").read_bytes() == before


def test_full_rerun_preserves_partial_alpha_and_foreground_locks(tmp_path):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    first = run_matte(project)
    operations.accept_revision(project, first["revision"])
    saved = project / "revisions" / first["revision"]
    prior = np.array(Image.open(saved / "base_alpha16.png"))
    assert prior[0, 1] == 16384
    filename = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 1],
                "revision": first["revision"],
            }
        ],
    )
    prepared_again = operations.apply_operation(
        project, request(project, guide_edits_file=filename)
    )
    approve(project, prepared_again)
    with (
        patch.object(StubSession, "identity", {"model": "second-fixture"}),
        patch.object(StubSession, "predict", return_value=(np.full((2, 3), 0.75), {})),
    ):
        second = run_matte(project)
    current = project / "revisions" / second["revision"]
    alpha = np.array(Image.open(current / "base_alpha16.png"))
    assert alpha[0, 1] == prior[0, 1] and alpha[1, 1] == 49151
    np.testing.assert_array_equal(
        tifffile.imread(current / "foreground_rgb16.tif")[0, 1],
        tifffile.imread(saved / "foreground_rgb16.tif")[0, 1],
    )
    assert read_project(project)["accepted_revision"] == first["revision"]
    assert np.array_equal(np.array(Image.open(saved / "base_alpha16.png")), prior)


def test_final_acceptance_rejects_stale_and_corrupt_saved_inputs(tmp_path):
    _, project, result = prepared(tmp_path)
    approve(project, result)
    matted = run_matte(project)
    before = (project / "state.json").read_bytes()
    with (project / "recipe.toml").open("a") as f:
        f.write("\n# intervening edit\n")
    with pytest.raises(ProjectError, match="Stale|stale"):
        operations.accept_revision(project, matted["revision"])
    assert (project / "state.json").read_bytes() == before
    (project / "revisions" / matted["revision"] / "base_alpha16.png").write_bytes(b"corrupt")
    with pytest.raises(ProjectError, match="hash"):
        operations.accept_revision(project, matted["revision"])
    assert (project / "state.json").read_bytes() == before


def rgb_lock_fixture(project, values):
    from test_operations import saved_alpha_fixture

    from blackmask.ingest import write_master
    from blackmask.project import digest

    fixture = saved_alpha_fixture(project, np.full((2, 3), 12345, dtype=np.uint16))
    directory = Path(fixture["manifest_file"]).parent
    write_master(directory / "corrected_rgb16.tif", values)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["files"]["corrected_rgb16.tif"] = digest(
        (directory / "corrected_rgb16.tif").read_bytes()
    )
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return fixture


def test_applicable_foreground_lock_values_survive_and_outside_is_master(tmp_path):
    _, project = opened(tmp_path)
    values = np.full((2, 3, 3), 1234, dtype=np.uint16)
    fixture = rgb_lock_fixture(project, values)
    name = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 1],
                "revision": fixture["revision"],
            }
        ],
    )
    result = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, result)
    matted = run_matte(project)
    alpha = np.array(Image.open(project / "revisions" / matted["revision"] / "base_alpha16.png"))
    foreground = tifffile.imread(
        project / "revisions" / matted["revision"] / "foreground_rgb16.tif"
    )
    master, _ = load_master(project, matted["master_id"])
    assert alpha[0, 1] == 12345 and alpha[1, 1] == 16384
    np.testing.assert_array_equal(foreground[0, 1], [1234, 1234, 1234])
    np.testing.assert_array_equal(foreground[1], master[1])


def test_conflicting_rgb_locks_rejected_before_inference(tmp_path):
    _, project = opened(tmp_path)
    first = rgb_lock_fixture(project, np.full((2, 3, 3), 1234, dtype=np.uint16))
    second = rgb_lock_fixture(project, np.full((2, 3, 3), 4321, dtype=np.uint16))
    name = edits(
        project,
        [
            {
                "id": str(i),
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [1, 0, 2, 1],
                "revision": result["revision"],
            }
            for i, result in enumerate([first, second])
        ],
    )
    result = operations.apply_operation(project, request(project, guide_edits_file=name))
    approve(project, result)
    before = (project / "state.json").read_bytes()
    with (
        patch.object(
            StubSession, "predict", side_effect=AssertionError("conflict must precede inference")
        ),
        pytest.raises(ProjectError, match="Conflicting.*RGB|foreground.*lock"),
    ):
        run_matte(project)
    assert (project / "state.json").read_bytes() == before
