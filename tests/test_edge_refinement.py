"""Exercise native edge preview and Apply through the actual local viewer."""

import io
import uuid
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_effects import effect_request, fixture_project
from test_ingest import saved_raster
from test_matte_operations import StubSession, run_matte
from test_operations import edits, request
from test_viewer import http, perform, running

from blackmask import operations
from blackmask.project import ProjectError, read_project
from blackmask.repair import replay_repair


def edge_request(server, crop=(1, 0, 5, 4)):
    state = server.snapshot()
    parent = next(row for row in state["revisions"] if row["revision"] == state["working_revision"])
    return {
        "request_id": uuid.uuid4().hex,
        "revision_manifest_sha256": parent["revision_manifest_sha256"],
        "edge_area": {
            "crop_xyxy": list(crop),
            "regions": [{"shape": "stroke", "points": [[2, 1], [2, 2]], "radius_px": 1}],
        },
    }


def preview_pixels(server, preview, side, panel):
    url = f"/edge-preview/{preview['preview_id']}/{side}/{panel}"
    status, data, _ = http(server, url)
    assert status == 200, data
    return np.array(Image.open(io.BytesIO(data)))


def test_edge_preview_applies_exact_alpha_preserves_partial_lock_and_stales_cleanup(
    tmp_path, monkeypatch
):
    project, _, original = fixture_project(tmp_path)
    cleanup = operations.apply_operation(project, effect_request(project))
    guides = edits(
        project,
        [
            {
                "id": "old-support",
                "shape": "rectangle",
                "role": "support",
                "xyxy": [0, 0, 6, 4],
                "feather_px": 0,
            },
            {
                "id": "saved-tip",
                "shape": "point",
                "role": "lock",
                "xy": [2, 1],
                "revision": cleanup["revision"],
            },
        ],
    )
    operations.apply_operation(project, request(project, guide_edits_file=guides))
    parent = run_matte(project)
    parent_path = project / "revisions" / parent["revision"]
    source = project / "assets/developed" / f"{parent['developed_id']}.tif"
    source_bytes = source.read_bytes()
    foreground_bytes = saved_raster(parent_path / "foreground_rgb16.tif").read_bytes()
    parent_alpha = np.array(Image.open(saved_raster(parent_path / "base_alpha16.png")))
    assert parent_alpha[1, 2] == 16384
    state_bytes = (project / "state.json").read_bytes()
    guide_bytes = (project / "guides.json").read_bytes()
    revisions = set((project / "revisions").iterdir())
    requests = set((project / "requests").iterdir())

    class PredictOnlyOnce(StubSession):
        calls = 0

        def predict(self, rgb, trimap, device):
            self.__class__.calls += 1
            return np.full(trimap.shape, 0.75 if self.__class__.calls == 1 else 0.5), {}

    monkeypatch.setattr(operations, "VitMatteSession", PredictOnlyOnce)
    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-model")
        preview = perform(server, "edge-preview", **edge_request(server))
        assert set((project / "revisions").iterdir()) == revisions
        assert set((project / "requests").iterdir()) == requests
        assert (project / "state.json").read_bytes() == state_bytes
        assert (project / "guides.json").read_bytes() == guide_bytes
        assert preview["stale_effects"] == ["cleanup"]
        assert preview["changed_pixels"] == 7
        expected = parent_alpha.copy()
        expected[0, 2] = 49151
        expected[1, [1, 3]] = 49151
        expected[2, 1:4] = 49151
        expected[3, 2] = 49151
        coverage = preview_pixels(server, preview, "candidate", "area")
        np.testing.assert_array_equal(coverage[..., 2] == 255, expected != parent_alpha)
        np.testing.assert_array_equal(coverage[1, 2], [255, 96, 225, 144])
        np.testing.assert_array_equal(
            preview_pixels(server, preview, "before", "alpha")[..., 0],
            np.rint(parent_alpha.astype(float) / 257).astype(np.uint8),
        )
        displayed = {
            panel: preview_pixels(server, preview, "candidate", panel)
            for panel in ("alpha", "black", "gray", "white")
        }
        np.testing.assert_array_equal(displayed["alpha"][..., 0], np.rint(expected / 257))
        result = perform(server, "edge-apply", preview_id=preview["preview_id"])
        for panel, pixels in displayed.items():
            code, body, _ = http(server, f"/image/{panel}/{result['revision']}/0,0,6,4/base")
            assert code == 200, body
            np.testing.assert_array_equal(np.array(Image.open(io.BytesIO(body))), pixels)
        assert PredictOnlyOnce.calls == 1

    revision = project / "revisions" / result["revision"]
    assert saved_raster(revision / "foreground_rgb16.tif").read_bytes() == foreground_bytes
    np.testing.assert_array_equal(replay_repair(project, result["revision"]), expected)
    assert source.read_bytes() == source_bytes
    state = read_project(project)
    assert state["accepted_revision"] == original["revision"]
    assert state["latest_result_revision"] == parent["revision"]
    assert result["color_cleanup"]["stale"] is True
    with pytest.raises(ProjectError, match="Stale enabled appearance"):
        operations.accept_revision(project, result["revision"])
    operations.restore_revision(project, parent["revision"])
    assert read_project(project)["working_revision"] == parent["revision"]


def test_stale_and_discarded_edge_previews_cannot_publish(tmp_path, monkeypatch):
    project, _, parent = fixture_project(tmp_path)
    monkeypatch.setattr(operations, "VitMatteSession", StubSession)
    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-model")
        preview = perform(server, "edge-preview", **edge_request(server))
        perform(server, "edge-discard", preview_id=preview["preview_id"])
        code, _, _ = http(server, f"/edge-preview/{preview['preview_id']}/candidate/alpha")
        assert code == 404
        preview = perform(server, "edge-preview", **edge_request(server))
        # Independently edit the working recipe while this preview remains open.
        recipe = project / "recipe.toml"
        recipe.write_bytes(recipe.read_bytes() + b"\n# intervening draft\n")
        with pytest.raises(AssertionError, match="[Ss]tale"):
            perform(server, "edge-apply", preview_id=preview["preview_id"])
        assert b"# intervening draft" in recipe.read_bytes()
    assert read_project(project)["working_revision"] == parent["revision"]
    assert read_project(project)["accepted_revision"] == parent["revision"]


def test_interrupted_edge_apply_preserves_head_and_leaves_replayable_orphan(tmp_path, monkeypatch):
    project, _, parent = fixture_project(tmp_path)
    state_bytes = (project / "state.json").read_bytes()
    requests = set((project / "requests").iterdir())
    revisions = set((project / "revisions").iterdir())

    class ChangedPrediction(StubSession):
        def predict(self, rgb, trimap, device):
            return np.full(trimap.shape, 0.75), {}

    monkeypatch.setattr(operations, "VitMatteSession", ChangedPrediction)
    publish = operations._atomic_json

    def interrupt_state(path, *args, **kwargs):
        if path == project / "state.json":
            raise OSError("fixture interruption before edge state publication")
        return publish(path, *args, **kwargs)

    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-model")
        preview = perform(server, "edge-preview", **edge_request(server))
        with monkeypatch.context() as injection:
            injection.setattr(operations, "_atomic_json", interrupt_state)
            with pytest.raises(AssertionError, match="fixture interruption"):
                perform(server, "edge-apply", preview_id=preview["preview_id"])

    assert (project / "state.json").read_bytes() == state_bytes
    assert set((project / "requests").iterdir()) == requests
    (orphan,) = set((project / "revisions").iterdir()) - revisions
    assert replay_repair(project, orphan.name)[1, 2] == 49151
    operations.restore_revision(project, orphan.name)
    state = read_project(project)
    assert state["working_revision"] == orphan.name
    assert state["accepted_revision"] == parent["revision"]
