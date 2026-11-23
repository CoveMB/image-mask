"""Exercise native edge preview and Apply through the actual local viewer."""

import io
import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from scipy.ndimage import gaussian_filter
from test_effects import effect_request, fixture_project
from test_ingest import saved_raster
from test_matte_operations import StubSession, run_matte
from test_operations import edits, request
from test_viewer import http, perform, running

from blackmask import operations
from blackmask.exposure import linear_to_rgb16
from blackmask.ingest import write_developed
from blackmask.project import ProjectError, create_project, read_project
from blackmask.repair import (
    ORDER,
    edge_support,
    merge_alpha,
    replay_directory,
    replay_repair,
    scalar16,
)


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


def test_stronger_preview_resolves_source_detail_and_binds_local_marks(tmp_path, monkeypatch):
    height, width = 72, 120
    rows, columns = np.mgrid[:height, :width]
    true_alpha = (rows >= 45).astype(np.float64)
    for center, length in ((20, 18), (26, 15), (32, 20)):
        taper = np.clip((45 - rows) / length, 0, 1)
        bristle = np.clip(1.8 - taper - abs(columns - center), 0, 1) * (1 - 0.65 * taper)
        true_alpha = np.maximum(true_alpha, np.where(rows >= 45 - length, bristle, 0))
    soft = 0.5 + 0.5 * np.tanh((rows - 45) / 7)
    true_alpha[:, 74:] = soft[:, 74:]
    foreground, background = np.array([0.52, 0.28, 0.08]), np.array([0.12, 0.23, 0.27])
    source = tmp_path / "synthetic-edge.tif"
    write_developed(
        source, linear_to_rgb16(background + true_alpha[..., None] * (foreground - background))
    )
    project = tmp_path / "project"
    create_project(source, project, {})
    cores = edits(
        project,
        [
            {
                "id": "foreground",
                "role": "foreground",
                "shape": "rectangle",
                "xyxy": [0, 62, width, height],
            },
            {
                "id": "background",
                "role": "background",
                "shape": "rectangle",
                "xyxy": [0, 0, width, 16],
            },
        ],
    )
    operations.apply_operation(project, request(project, guide_edits_file=cores))
    run_matte(project)

    class SoftPrediction(StubSession):
        def predict(self, rgb, trimap, device):
            alpha = gaussian_filter(true_alpha, 1.5)
            alpha[:, 78:] = true_alpha[:, 78:]
            return alpha, {}

    monkeypatch.setattr(operations, "VitMatteSession", SoftPrediction)
    area = {
        "crop_xyxy": [0, 0, width, height],
        "regions": [{"shape": "rectangle", "xyxy": [8, 19, 112, 60]}],
    }

    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-model")
        baseline = perform(server, "edge-preview", **dict(edge_request(server), edge_area=area))
        before = server.edge_preview[1].before.copy()
        standard = server.edge_preview[1].merged.copy()
        options = {"mode": "stronger", "guides": []}
        preview = perform(
            server,
            "edge-preview",
            **dict(edge_request(server), edge_area=area, edge_refinement=options),
        )
        stronger = server.edge_preview[1].merged
        assert preview["edge_mode"] == "stronger"
        assert stronger[39, 23] < standard[39, 23] - 1500  # Empty gap between two bristles.
        assert stronger[28, 20] > standard[28, 20] + 1800  # Partial, in-focus tip.
        assert stronger[28, 20] < 32768
        np.testing.assert_array_equal(stronger[30:57, 88:104], standard[30:57, 88:104])
        with pytest.raises(AssertionError, match="unavailable"):
            perform(server, "edge-apply", preview_id=baseline["preview_id"])

        options["guides"] = [
            {"role": "background", "shape": "point", "xy": [23, 39]},
            {"role": "background", "shape": "point", "xy": [23, 19]},
            {"role": "protect", "shape": "rectangle", "xyxy": [20, 28, 21, 29]},
        ]
        preview = perform(
            server,
            "edge-preview",
            **dict(edge_request(server), edge_area=area, edge_refinement=options),
        )
        reviewed = server.edge_preview[1]
        assert reviewed.merged[39, 23] == 0
        assert 0 < reviewed.merged[19, 23] < before[19, 23]  # Preserve the boundary feather.
        assert 0 < reviewed.merged[28, 20] == before[28, 20] < 65535
        assert reviewed.support[28, 20] == 0
        assert 0 < reviewed.support[28, 21] < 65535
        np.testing.assert_array_equal(
            reviewed.merged[reviewed.support == 0], before[reviewed.support == 0]
        )

        def forbidden(*args, **kwargs):
            raise AssertionError("Apply and replay must not rerun inference")

        monkeypatch.setattr(operations, "VitMatteSession", forbidden)
        applied = perform(server, "edge-apply", preview_id=preview["preview_id"])

    directory = project / "revisions" / applied["revision"]
    assert json.loads((directory / "request.json").read_bytes())["edge_refinement"] == options
    assert json.loads((directory / "repair/merge.json").read_bytes())["edge_refinement"] == options
    np.testing.assert_array_equal(replay_repair(project, applied["revision"]), reviewed.merged)
    assert (
        saved_raster(directory / "foreground_rgb16.tif").read_bytes()
        == saved_raster(
            project / "revisions" / applied["parent"] / "foreground_rgb16.tif"
        ).read_bytes()
    )


@pytest.mark.parametrize(
    "options, diagnostic",
    [
        ({"mode": "unknown", "guides": []}, "edge refinement mode"),
        (
            {
                "mode": "standard",
                "guides": [{"role": "protect", "shape": "rectangle", "xyxy": [2, 2, 3, 3]}],
            },
            "require Stronger",
        ),
        (
            {
                "mode": "stronger",
                "guides": [{"role": "background", "shape": "rectangle", "xyxy": [4, 0, 5, 1]}],
            },
            "inside the writable edge area",
        ),
        (
            {
                "mode": "stronger",
                "guides": [
                    {"role": "protect", "shape": "rectangle", "xyxy": [2, 2, 3, 3]},
                    {"role": "background", "shape": "rectangle", "xyxy": [2, 2, 3, 3]},
                ],
            },
            "overlaps tip protection",
        ),
    ],
)
def test_edge_rejects_invalid_local_guidance_before_inference(tmp_path, options, diagnostic):
    project, _, parent = fixture_project(tmp_path)
    with running(project) as server:
        with pytest.raises(AssertionError, match=diagnostic):
            perform(server, "edge-preview", **edge_request(server), edge_refinement=options)
        assert server.edge_preview is None
    assert read_project(project)["working_revision"] == parent["revision"]


def test_edge_brush_blends_partial_alpha_at_sides_and_round_ends():
    parent = np.full((23, 31), 24576, dtype=np.uint16)
    candidate = np.full_like(parent, 53248)
    protection = np.zeros(parent.shape, dtype=bool)
    trimap = np.full(parent.shape, 128, dtype=np.uint8)
    area = {
        "crop_xyxy": [0, 0, 31, 23],
        "regions": [{"shape": "stroke", "points": [[10, 11], [21, 11]], "radius_px": 5}],
    }
    support = edge_support(area, "fixture", protection, parent, trimap).support
    merged = merge_alpha(parent, candidate, support, protection, np.zeros_like(parent), "replace")

    np.testing.assert_array_equal(support[5:10, 15], [0, 4854, 32768, 60681, 65535])
    np.testing.assert_array_equal(support[13:18, 15], [65535, 60681, 32768, 4854, 0])
    assert support[11, 5] == support[11, 26] == 4854
    for cross_section in (merged[5:10, 15], merged[11, 4:10], merged[11, 27:21:-1]):
        assert cross_section[0] == 24576 and cross_section[-1] == 53248
        assert np.all(np.diff(cross_section.astype(int)) > 0)
    np.testing.assert_array_equal(merged[support == 0], parent[support == 0])
    np.testing.assert_array_equal(merged[support == 65535], candidate[support == 65535])


def test_edge_feathers_the_clipped_union_with_no_internal_join():
    parent = np.full((24, 35), 24576, dtype=np.uint16)
    protection = np.zeros(parent.shape, dtype=bool)
    trimap = np.full(parent.shape, 128, dtype=np.uint8)
    first = {"shape": "stroke", "points": [[8, 12], [14, 12]], "radius_px": 5}
    second = {"shape": "stroke", "points": [[20, 12], [27, 12]], "radius_px": 5}
    narrow = {"shape": "rectangle", "xyxy": [5, 3, 6, 6]}
    clipped = {"shape": "stroke", "points": [[20, 3], [24, 3]], "radius_px": 1}
    crop = [4, 3, 32, 22]

    support = edge_support(
        {"crop_xyxy": crop, "regions": [first, second, narrow, clipped]},
        "fixture",
        protection,
        parent,
        trimap,
    ).support
    for mark in (first, second):
        single = edge_support(
            {"crop_xyxy": crop, "regions": [mark]}, "fixture", protection, parent, trimap
        ).support
        assert 0 < single[12, 17] < 65535
    np.testing.assert_array_equal(support[12, 14:21], 65535)
    np.testing.assert_array_equal(support[3:6, 5], 4854)
    np.testing.assert_array_equal(support[3:5, 22], 4854)
    assert not support[:3].any() and not support[:, :4].any() and not support[:, 32:].any()


def test_edge_keeps_changed_confirmed_cores_at_full_strength_inside_a_narrow_mark(
    tmp_path, monkeypatch
):
    project, _, _ = fixture_project(tmp_path)
    cores = edits(
        project,
        [
            {"id": "new-foreground", "role": "foreground", "shape": "point", "xy": [2, 1]},
            {"id": "new-background", "role": "background", "shape": "point", "xy": [2, 2]},
            {
                "id": "prepare-core-support",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [2, 1, 3, 3],
                "feather_px": 0,
            },
        ],
    )
    operations.apply_operation(project, request(project, guide_edits_file=cores))
    monkeypatch.setattr(operations, "VitMatteSession", StubSession)
    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-model")
        incomplete = edge_request(server)
        incomplete["edge_area"]["regions"] = [{"shape": "rectangle", "xyxy": [2, 0, 3, 2]}]
        with pytest.raises(AssertionError, match="Change-required core needs full support"):
            perform(server, "edge-preview", **incomplete)

        complete = edge_request(server)
        complete["edge_area"]["regions"] = [{"shape": "rectangle", "xyxy": [2, 0, 3, 3]}]
        preview = perform(server, "edge-preview", **complete)
        assert preview["changed_pixels"] == 2
        result = perform(server, "edge-apply", preview_id=preview["preview_id"])

    directory = project / "revisions" / result["revision"]
    support = scalar16(saved_raster(directory / "repair/support16.png"))
    np.testing.assert_array_equal(support[:, 2], [4854, 65535, 65535, 0])
    np.testing.assert_array_equal(
        replay_repair(project, result["revision"])[:, 2], [16384, 65535, 0, 16384]
    )


def test_legacy_edge_replay_uses_hard_support_for_records_without_a_weighting_rule(tmp_path):
    directory = tmp_path / "revisions/.matte-legacy"
    (directory / "repair").mkdir(parents=True)
    (directory / "supports").mkdir()
    parent = np.full((5, 7), 16384, dtype=np.uint16)
    candidate = np.full_like(parent, 49151)
    support = np.zeros_like(parent)
    support[1:3, 2:5] = 65535
    protection = np.zeros(parent.shape, dtype=np.uint8)
    protection[2, 3] = 255
    support[2, 3] = 0
    for name, pixels in {
        "repair/parent_alpha16.png": parent,
        "repair/candidate_alpha16.png": candidate,
        "repair/support16.png": support,
        "supports/protection.png": protection,
        "supports/lock_values16.png": np.where(protection != 0, parent, 0).astype(np.uint16),
        "trimap.png": np.full(parent.shape, 128, dtype=np.uint8),
    }.items():
        Image.fromarray(pixels).save(directory / name)
    record = {
        "developed_id": "fixture",
        "context_xyxy": [0, 0, 7, 5],
        "scope_xyxy": [2, 1, 5, 3],
        "crop_mapping": {
            "origin_xy": [0, 0],
            "dimensions_wh": [7, 5],
            "native_scale": 1,
            "half_open": True,
        },
        "operation_order": ORDER,
        "merge_policy": "replace",
        "edge_area": {
            "crop_xyxy": [0, 0, 7, 5],
            "regions": [{"shape": "rectangle", "xyxy": [2, 1, 5, 3]}],
        },
    }
    (directory / "repair/merge.json").write_text(json.dumps(record))
    expected = parent.copy()
    expected[1:3, 2:5] = 49151
    expected[2, 3] = 16384
    np.testing.assert_array_equal(replay_directory(tmp_path, directory, {}), expected)


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
        reviewed = server.edge_preview[1]
        expected = parent_alpha.copy()
        # All writable samples are one pixel from the perimeter, including the
        # center sample immediately below the saved partial-alpha lock.
        expected[0, 2] = 18811
        expected[1, [1, 3]] = 18811
        expected[2, 1:4] = 18811
        expected[3, 2] = 18811
        np.testing.assert_array_equal(reviewed.merged, expected)
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
    np.testing.assert_array_equal(
        scalar16(saved_raster(revision / "repair/support16.png")), reviewed.support
    )
    np.testing.assert_array_equal(scalar16(saved_raster(revision / "base_alpha16.png")), expected)
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
        reviewed = server.edge_preview[1]
        with monkeypatch.context() as injection:
            injection.setattr(operations, "_atomic_json", interrupt_state)
            with pytest.raises(AssertionError, match="fixture interruption"):
                perform(server, "edge-apply", preview_id=preview["preview_id"])

    assert (project / "state.json").read_bytes() == state_bytes
    assert set((project / "requests").iterdir()) == requests
    (orphan,) = set((project / "revisions").iterdir()) - revisions
    np.testing.assert_array_equal(replay_repair(project, orphan.name), reviewed.merged)
    operations.restore_revision(project, orphan.name)
    state = read_project(project)
    assert state["working_revision"] == orphan.name
    assert state["accepted_revision"] == parent["revision"]
