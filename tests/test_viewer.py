import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

import pytest
from test_ingest import saved_raster
from test_operations import opened, request

from blackmask import operations
from blackmask.project import ProjectError, load_developed, project_lock, read_project


@pytest.mark.parametrize("target", ["spatial_fade", "shadow_fade"])
def test_fade_reduction_viewer_save_snapshot_and_saved_comparisons(tmp_path, target):
    import base64
    import io

    import numpy as np
    from PIL import Image
    from test_effects import fixture_project
    from test_fade_reduction import area, rectangle, reduction_request
    from test_shadow_fade import fade_request
    from test_spatial_fade import spatial_request, spatial_settings

    project, _, _ = fixture_project(tmp_path)
    legacy = operations.apply_operation(project, spatial_request(project))
    other_areas = {}
    if target == "shadow_fade":
        settings = dict(spatial_settings(6, 4), preserve_highlights=0.8)
        operations.apply_operation(project, spatial_request(project, settings, candidate=True))
        spatial_area = area(rectangle(amount=0.4, box=[0, 0, 6, 4]))
        operations.apply_operation(project, reduction_request(project, spatial_area))
        legacy = operations.apply_operation(project, fade_request(project, amount=0.4))
        other_areas["spatial_fade"] = spatial_area
    document = area(rectangle(amount=1, box=[0, 0, 6, 4]))
    with running(project) as server:
        state = server.snapshot()
        selected = next(r for r in state["revisions"] if r["revision"] == legacy["revision"])
        data = {key: state[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(
            action="effects",
            base_revision=legacy["revision"],
            revision_manifest_sha256=selected["revision_manifest_sha256"],
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            fade_reduction={"target": target, "area": document},
        )
        status, body, _ = http(server, "/api/action", "POST", data)
        assert status == 202, body
        assert server.action_lock.acquire(timeout=10)
        server.action_lock.release()
        assert server.action["error"] is None, server.action
        current = server.action["result"]["revision"]
        state = server.snapshot()
        selected = next(r for r in state["revisions"] if r["revision"] == current)
        assert selected["fade_reduction_areas"] == {**other_areas, target: document}
        identity = {
            "developed_id": state["developed_id"],
            "revision": current,
            "revision_manifest_sha256": selected["revision_manifest_sha256"],
            "crop_xyxy": [0, 0, 6, 4],
            "target": target,
        }
        responses = {}
        for view in ("coverage", "off"):
            status, body, _ = http(
                server, "/api/fade-reduction-preview", "POST", dict(identity, view=view)
            )
            assert status == 200, body
            result = json.loads(body)
            assert all(result[k] == v for k, v in identity.items())
            with Image.open(io.BytesIO(base64.b64decode(result["png_base64"]))) as image:
                responses[view] = np.array(image)
        assert np.all(responses["coverage"] == 255)
        for rev, expected_equal in ((legacy["revision"], True), (current, False)):
            status, body, _ = http(server, f"/image/result/{rev}/0,0,6,4")
            assert status == 200
            with Image.open(io.BytesIO(body)) as image:
                assert np.array_equal(responses["off"], np.array(image)) is expected_equal
        before = (project / "state.json").read_bytes()
        data.update(
            base_revision=current,
            inputs_digest=state["inputs_digest"],
            authoring_digest=state["authoring_digest"],
        )
        assert http(server, "/api/action", "POST", data)[0] == 202
        assert server.action_lock.acquire(timeout=10)
        server.action_lock.release()
        assert "Stale" in server.action["error"]
        assert (project / "state.json").read_bytes() == before
        del data["revision_manifest_sha256"]
        assert http(server, "/api/action", "POST", data)[0] == 400
        assert (
            http(
                server,
                "/api/fade-reduction-preview",
                "POST",
                dict(identity, view="off"),
                Origin="null",
            )[0]
            == 403
        )
        assert (
            http(
                server,
                "/api/fade-reduction-preview",
                "POST",
                dict(identity, view="coverage", panel="result"),
            )[0]
            == 400
        )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("target", ["spatial_fade", "shadow_fade"])
def test_reduction_native_previews_reuse_validated_geometry_even_off(tmp_path, enabled, target):
    from unittest.mock import patch

    from test_effects import fixture_project
    from test_fade_reduction import reduction_request
    from test_shadow_fade import fade_request
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask import fade_reduction
    from blackmask import project as project_module

    project, _, _ = fixture_project(tmp_path)
    settings = dict(spatial_settings(6, 4), enabled=enabled)
    operations.apply_operation(
        project,
        spatial_request(project, settings)
        if target == "spatial_fade"
        else fade_request(project, enabled=enabled),
    )
    result = operations.apply_operation(project, reduction_request(project, target=target))
    with running(project) as server:
        state = server.snapshot()
        selected = next(r for r in state["revisions"] if r["revision"] == result["revision"])
        identity = {
            "developed_id": state["developed_id"],
            "revision": result["revision"],
            "revision_manifest_sha256": selected["revision_manifest_sha256"],
            "crop_xyxy": [0, 0, 6, 4],
            "target": target,
        }
        path = f"/image/result/{result['revision']}/0,0,6,4"
        status, expected, _ = http(server, path)
        assert status == 200
        project_module._validate_spatial_fade_semantics.cache_clear()
        project_module._validate_shadow_fade_semantics.cache_clear()
        with patch.object(
            fade_reduction,
            "rasterize_fade_reduction",
            wraps=fade_reduction.rasterize_fade_reduction,
        ) as replay:
            status, pixels, _ = http(server, path)
            assert status == 200 and pixels == expected
            assert replay.call_count == 1  # Cold validation still checks the complete field.
            for _ in range(2):
                status, pixels, _ = http(server, path)
                assert status == 200 and pixels == expected
                for view in ("coverage", "off"):
                    status, body, _ = http(
                        server, "/api/fade-reduction-preview", "POST", dict(identity, view=view)
                    )
                    assert status == 200, body
            assert replay.call_count == 1  # Warm image/coverage/OFF views only read saved fields.


@pytest.mark.parametrize("field", ["target", "area"])
def test_fade_reduction_http_rejects_duplicate_nested_keys_before_start(tmp_path, field):
    from test_effects import fixture_project
    from test_fade_reduction import area
    from test_spatial_fade import spatial_request

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, spatial_request(project))
    with running(project) as server:
        snapshot = server.snapshot()
        current = next(
            r for r in snapshot["revisions"] if r["revision"] == snapshot["working_revision"]
        )
        data = {key: snapshot[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(
            action="effects",
            base_revision=snapshot["working_revision"],
            revision_manifest_sha256=current["revision_manifest_sha256"],
            scope_xyxy=[0, 0, 6, 4],
            candidate_comparison=True,
            fade_reduction={"target": "spatial_fade", "area": area()},
        )
        original = json.dumps(data)
        body = original.replace(
            '"' + field + '":', '"' + field + '": null, "' + field + '":'
        ).encode()
        before = dict(server.action)
        connection = HTTPConnection(*server.server_address, timeout=5)
        connection.request(
            "POST",
            "/api/action",
            body,
            {
                "Host": server.host,
                "Origin": server.origin,
                "Content-Type": "application/json",
                "X-Blackmask-Token": server.token,
            },
        )
        response = connection.getresponse()
        status, result = response.status, response.read()
        connection.close()
        assert status == 400, result
        assert b"Duplicate" in result
        assert server.action == before


def test_spatial_saved_preview_routes_bind_revision_shape_crop_and_preview_guard(tmp_path):
    import base64
    import io

    import numpy as np
    from PIL import Image
    from test_effects import fixture_project
    from test_shadow_fade import fade_request
    from test_spatial_fade import arc_settings, spatial_request, spatial_settings

    from blackmask.effects import saved_spatial_fade
    from blackmask.export import saved_layers
    from blackmask.spatial_fade import combined_fade_weight, spatial_fade_amount

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, fade_request(project, amount=0.38))
    settings = spatial_settings(6, 4)
    settings.update(
        arcs_enabled=True,
        arcs=[
            arc_settings(
                center_xy=[3, 2], half_span=2, bend=0, transition_width=0.5, end_softness=0.5
            )
        ],
    )
    result = operations.apply_operation(project, spatial_request(project, settings, candidate=True))
    foreground, alpha, manifest = saved_layers(project, result["revision"], result["developed_id"])
    saved = saved_spatial_fade(project, result["revision"], alpha, manifest)
    crop = [1, 1, 5, 3]
    with running(project) as server:
        snapshot = server.snapshot()
        revision = next(
            item for item in snapshot["revisions"] if item["revision"] == result["revision"]
        )
        assert revision["spatial_fade"] == manifest["spatial_fade"]
        identity = {
            "developed_id": snapshot["developed_id"],
            "revision": result["revision"],
            "revision_manifest_sha256": revision["revision_manifest_sha256"],
            "crop_xyxy": crop,
        }
        for view in ("combined", "effective", "selected", "off"):
            data = dict(identity, view=view)
            if view == "selected":
                data["shape_id"] = settings["arcs"][0]["id"]
            status, body, _ = http(server, "/api/spatial-preview", "POST", data)
            assert status == 200, body
            response = json.loads(body)
            assert all(response[key] == value for key, value in data.items())
            with Image.open(io.BytesIO(base64.b64decode(response["png_base64"]))) as image:
                pixels = np.array(image)
            if view == "combined":
                expected = np.rint(saved.weight16[1:3, 1:5] / 257).astype(np.uint8)
            elif view == "effective":
                expected = np.rint(
                    spatial_fade_amount(foreground, alpha, saved)[1:3, 1:5] * 255
                ).astype(np.uint8)
            elif view == "selected":
                x, y = np.meshgrid(np.arange(1, 5) + 0.5, np.arange(1, 3) + 0.5)
                expected = np.rint(
                    combined_fade_weight(x, y, settings, shape_id=data["shape_id"]) * 255
                ).astype(np.uint8)
            else:
                assert pixels.shape == (2, 4, 3)
                continue
            np.testing.assert_array_equal(pixels, expected)
        assert (
            http(
                server,
                "/api/spatial-preview",
                "POST",
                dict(identity, view="combined"),
                Origin="null",
            )[0]
            == 403
        )
        for bad in (
            dict(identity, view="combined", path="/tmp/private"),
            dict(identity, view="wrong"),
            dict(identity, view="selected", shape_id="../escape"),
            dict(identity, view="selected", shape_id="5ce6b442-6fa0-4c07-a938-dbf012c52c00"),
            dict(identity, view="combined", revision_manifest_sha256="0" * 64),
            dict(identity, view="combined", crop_xyxy=[-1, 0, 2, 3]),
        ):
            assert http(server, "/api/spatial-preview", "POST", bad)[0] in (400, 409)
        assert server.framing_preview_lock.acquire(blocking=False)
        try:
            assert (
                http(server, "/api/spatial-preview", "POST", dict(identity, view="combined"))[0]
                == 409
            )
        finally:
            server.framing_preview_lock.release()
        assert (
            http(server, "/api/spatial-preview", "POST", dict(identity, view="combined"))[0] == 200
        )
        disabled = dict(settings, arcs_enabled=False)
        disabled_result = operations.apply_operation(
            project, spatial_request(project, disabled, candidate=True)
        )
        selected_revision = next(
            item
            for item in server.snapshot()["revisions"]
            if item["revision"] == disabled_result["revision"]
        )
        newer = dict(
            identity,
            revision=disabled_result["revision"],
            revision_manifest_sha256=selected_revision["revision_manifest_sha256"],
        )
        status, body, _ = http(
            server,
            "/api/spatial-preview",
            "POST",
            dict(newer, view="selected", shape_id=settings["arcs"][0]["id"]),
        )
        assert status == 200, body
        with Image.open(io.BytesIO(base64.b64decode(json.loads(body)["png_base64"]))) as image:
            assert not np.array(image).any()
        removed = operations.apply_operation(
            project, spatial_request(project, dict(disabled, arcs=[]), candidate=True)
        )
        selected_revision = next(
            item
            for item in server.snapshot()["revisions"]
            if item["revision"] == removed["revision"]
        )
        newer.update(
            revision=removed["revision"],
            revision_manifest_sha256=selected_revision["revision_manifest_sha256"],
        )
        assert (
            http(
                server,
                "/api/spatial-preview",
                "POST",
                dict(newer, view="selected", shape_id=settings["arcs"][0]["id"]),
            )[0]
            == 409
        )


@pytest.mark.parametrize("reduction", [None, "spatial_fade", "shadow_fade"])
def test_spatial_viewer_raw_manifest_check_occurs_inside_the_writer_lock(
    tmp_path, monkeypatch, reduction
):
    from test_effects import fixture_project
    from test_fade_reduction import reduction_request
    from test_shadow_fade import fade_request
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask.project import digest

    project, _, parent = fixture_project(tmp_path)
    if reduction:
        parent = operations.apply_operation(
            project,
            spatial_request(project, spatial_settings(6, 4))
            if reduction == "spatial_fade"
            else fade_request(project),
        )
    manifest = project / "revisions" / parent["revision"] / "manifest.json"
    expected = digest(manifest.read_bytes())
    before = (project / "state.json").read_bytes()
    revisions_before = sorted(path.name for path in (project / "revisions").iterdir())
    original_lock = operations.project_lock

    @contextmanager
    def changed_under_lock(path):
        with original_lock(path):
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            yield

    monkeypatch.setattr(operations, "project_lock", changed_under_lock)
    with pytest.raises(ProjectError, match="Stale"):
        operations.apply_operation(
            project,
            reduction_request(project, target=reduction)
            if reduction
            else spatial_request(project, spatial_settings(6, 4)),
            expected_revision_manifest_sha256=expected,
        )
    assert (project / "state.json").read_bytes() == before
    assert sorted(path.name for path in (project / "revisions").iterdir()) == revisions_before


@pytest.mark.parametrize("with_spatial", [False, True])
def test_spatial_off_and_effective_maps_follow_working_stale_base_policy(tmp_path, with_spatial):
    import base64
    import io
    from unittest.mock import patch

    import numpy as np
    from PIL import Image
    from test_effects import fixture_project
    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair
    from test_shadow_fade import fade_request
    from test_spatial_fade import spatial_request

    project, _, _ = fixture_project(tmp_path)
    accepted = operations.apply_operation(project, fade_request(project, amount=0.38))
    if with_spatial:
        accepted = operations.apply_operation(project, spatial_request(project, candidate=True))
    operations.accept_revision(project, accepted["revision"])
    prepared = repair_guides(project, [1, 1, 4, 3])
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3]))
    with running(project) as server:
        snapshot = server.snapshot()
        viewed = next(
            item for item in snapshot["revisions"] if item["revision"] == accepted["revision"]
        )
        current = next(
            item
            for item in snapshot["revisions"]
            if item["revision"] == snapshot["working_revision"]
        )
        assert current["shadow_fade"]["stale"] and not viewed["shadow_fade"]["stale"]
        identity = {
            "developed_id": snapshot["developed_id"],
            "revision": accepted["revision"],
            "revision_manifest_sha256": viewed["revision_manifest_sha256"],
            "crop_xyxy": [0, 0, 6, 4],
        }
        for panel in ("result", "black", "gray", "white"):
            status, body, _ = http(
                server, "/api/spatial-preview", "POST", dict(identity, view="off", panel=panel)
            )
            assert status == 200, body
            response = json.loads(body)
            assert "BASE" in response["label"]
            with Image.open(io.BytesIO(base64.b64decode(response["png_base64"]))) as image:
                off = np.array(image)
            normal = http(server, f"/image/{panel}/{accepted['revision']}/0,0,6,4")
            assert normal[0] == 200
            with Image.open(io.BytesIO(normal[1])) as image:
                np.testing.assert_array_equal(off, np.array(image))
        status, body, _ = http(
            server, "/api/spatial-preview", "POST", dict(identity, view="effective")
        )
        assert status == 200, body
        with Image.open(io.BytesIO(base64.b64decode(json.loads(body)["png_base64"]))) as image:
            assert not np.array(image).any()


def test_spatial_viewer_action_forwards_exact_protection_and_raw_identity(tmp_path):
    import numpy as np
    from PIL import Image
    from test_effects import fixture_project
    from test_spatial_fade import spatial_settings

    from blackmask.export import render_background, saved_layers
    from blackmask.spatial_fade import read_spatial_fade

    project, _, parent = fixture_project(tmp_path)
    protected = np.zeros((4, 6), np.uint16)
    protected[1, 3] = 65535
    Image.fromarray(protected).save(project / "explicit-protection.png")
    settings = spatial_settings(6, 4)
    with running(project) as server:

        def payload(*, enabled=True, explicit=False, candidate=False):
            state = server.snapshot()
            selected = next(
                item for item in state["revisions"] if item["revision"] == state["working_revision"]
            )
            data = {
                "action": "effects",
                "developed_id": state["developed_id"],
                "base_revision": state["working_revision"],
                "inputs_digest": state["inputs_digest"],
                "authoring_digest": state["authoring_digest"],
                "revision_manifest_sha256": selected["revision_manifest_sha256"],
                "scope_xyxy": [0, 0, 6, 4],
                "candidate_comparison": candidate,
                "spatial_fade": dict(settings, enabled=enabled),
            }
            if explicit:
                data["spatial_fade_protection_file"] = "explicit-protection.png"
            return data

        for data in (payload(explicit=True), payload(candidate=True), payload(enabled=False)):
            # Refresh each complete request after the preceding action; never merge by index.
            data = payload(
                enabled=data["spatial_fade"]["enabled"],
                explicit="spatial_fade_protection_file" in data,
                candidate=data["candidate_comparison"],
            )
            status, body, _ = http(server, "/api/action", "POST", data)
            assert status == 202, body
            assert server.action_lock.acquire(timeout=5)
            server.action_lock.release()
            assert server.action["error"] is None, server.action
            result = server.action["result"]
            foreground, alpha, manifest = saved_layers(
                project, result["revision"], result["developed_id"]
            )
            saved = read_spatial_fade(
                project, project / "revisions" / result["revision"], manifest, alpha
            )
            assert 0 < alpha[1, 3] < 65535 and saved.protection[1, 3]
            background = np.full_like(foreground, [4608, 1792, 2048])
            expected = render_background(foreground, alpha, background)
            np.testing.assert_array_equal(
                render_background(
                    foreground, alpha, background, spatial_fade=saved, fade_background16=background
                )[1, 3],
                expected[1, 3],
            )
        before = (project / "state.json").read_bytes()
        bad = payload(candidate=True)
        bad["revision_manifest_sha256"] = "0" * 64
        assert http(server, "/api/action", "POST", bad)[0] == 202
        assert server.action_lock.acquire(timeout=5)
        server.action_lock.release()
        assert "Stale" in server.action["error"]
        assert (project / "state.json").read_bytes() == before
        missing = payload(candidate=True)
        del missing["revision_manifest_sha256"]
        assert http(server, "/api/action", "POST", missing)[0] == 400
    assert read_project(project)["accepted_revision"] == parent["revision"]


@pytest.mark.parametrize("series_mode", [False, True])
def test_spatial_framing_preview_uses_saved_fade_and_bound_target(tmp_path, series_mode):
    import base64
    import io

    import numpy as np
    import tifffile
    from PIL import Image
    from test_effects import fixture_project
    from test_series_framing import series_settings
    from test_spatial_fade import spatial_request, spatial_settings

    from blackmask.background import make_background
    from blackmask.framing import framing_preview, validate_margins

    project, _, _ = fixture_project(tmp_path)
    settings = spatial_settings(6, 4)
    settings["oval"].update(
        center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], transition_width=0.5, amount=1
    )
    result = operations.apply_operation(project, spatial_request(project, settings))
    margins = {"left_px": 1, "right_px": 2, "top_px": 1, "bottom_px": 2}
    values = series_settings(output_width_px=17, output_height_px=19).to_dict()
    with running(project) as server:
        state = json.loads(http(server)[1])
        selected = next(
            item for item in state["revisions"] if item["revision"] == result["revision"]
        )
        request = {
            "developed_id": state["developed_id"],
            "revision": result["revision"],
            "revision_manifest_sha256": selected["revision_manifest_sha256"],
            "settings" if series_mode else "margins": values if series_mode else margins,
        }
        status, body, _ = http(
            server,
            "/api/series-preview" if series_mode else "/api/framing-preview",
            "POST",
            request,
        )
        assert status == 200, body
        data = json.loads(body)
        if series_mode:
            expected = np.rint(
                make_background((19, 17), {"color_srgb": "#120708", "variation": 0.55}) / 257
            ).astype(np.uint8)
        else:
            background = tifffile.imread(
                saved_raster(
                    project / "revisions" / result["revision"] / "background/background_rgb16.tif"
                )
            )
            expected = framing_preview(background, background, validate_margins(margins, (6, 4)))[0]
        with Image.open(io.BytesIO(base64.b64decode(data["png_base64"]))) as image:
            np.testing.assert_array_equal(np.array(image), expected)


def test_series_http_validation_preview_and_independent_errors(tmp_path):
    import base64
    import io

    from PIL import Image
    from test_effects import fixture_project
    from test_series_framing import series_settings

    from blackmask.series_framing import portable_series_preset

    project, _, parent = fixture_project(tmp_path)
    before = (project / "state.json").read_bytes()
    settings = series_settings(name="Été <series>", output_width_px=40, output_height_px=50)
    with running(project) as server:
        state = json.loads(http(server)[1])
        assert state["series_digest"] is None and state["series_error"] is None
        raw = portable_series_preset(settings).decode("utf-8")
        status, body, _ = http(server, "/api/series-preset-validate", "POST", {"preset_json": raw})
        assert status == 200 and json.loads(body)["settings"] == settings.to_dict()
        for invalid in (
            {"preset_json": raw, "path": "/tmp"},
            {"preset_json": " " * 16385},
            {"preset_json": raw.replace('"name":', '"name":"duplicate","name":')},
        ):
            assert http(server, "/api/series-preset-validate", "POST", invalid)[0] == 400
        revision = next(r for r in state["revisions"] if r["revision"] == parent["revision"])
        data = {
            "developed_id": state["developed_id"],
            "revision": parent["revision"],
            "revision_manifest_sha256": revision["revision_manifest_sha256"],
            "settings": settings.to_dict(),
        }
        status, body, headers = http(server, "/api/series-preview", "POST", data)
        assert status == 200, body
        result = json.loads(body)
        assert all(result[key] == value for key, value in data.items())
        assert result["output_dimensions_wh"] == [40, 50]
        with Image.open(saved_raster(io.BytesIO(base64.b64decode(result["png_base64"])))) as image:
            assert image.mode == "RGB" and image.size == (40, 50)
        assert "img-src 'self' blob:" in headers["Content-Security-Policy"]
        assert http(server, "/api/series-preview", "POST", data, Origin="null")[0] == 403
        assert (
            http(server, "/api/series-preview", "POST", data, **{"X-Blackmask-Token": "wrong"})[0]
            == 403
        )
        assert http(server, "/api/series-preview", "POST", {**data, "path": "/tmp"})[0] == 400
        assert (
            http(
                server,
                "/api/series-preview",
                "POST",
                {**data, "revision_manifest_sha256": "0" * 64},
            )[0]
            == 409
        )
        (project / "series-framing.json").write_text("{broken")
        state = json.loads(http(server)[1])
        assert state["series_settings"] is None and "series-framing.json" in state["series_error"]
        assert state["framing_error"] is None
        assert http(server, "/api/series-preview", "POST", data)[0] == 200
        assert (project / "state.json").read_bytes() == before


def test_series_preview_busy_disconnect_and_identity_races(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from test_effects import fixture_project
    from test_framing import margins
    from test_series_framing import series_settings

    from blackmask import series_framing

    project, _, parent = fixture_project(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = series_framing.render_series

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    with running(project) as server:
        state = server.snapshot()
        revision = next(r for r in state["revisions"] if r["revision"] == parent["revision"])
        data = {
            "developed_id": state["developed_id"],
            "revision": parent["revision"],
            "revision_manifest_sha256": revision["revision_manifest_sha256"],
            "settings": series_settings(output_width_px=40, output_height_px=50).to_dict(),
        }
        monkeypatch.setattr(series_framing, "render_series", paused)
        with ThreadPoolExecutor() as executor:
            first = executor.submit(http, server, "/api/series-preview", "POST", data)
            assert entered.wait(5)
            framing = {
                key: data[key] for key in ("developed_id", "revision", "revision_manifest_sha256")
            }
            assert (
                http(server, "/api/framing-preview", "POST", {**framing, "margins": margins()})[0]
                == 409
            )
            assert http(server, "/api/series-preview", "POST", data)[0] == 409
            release.set()
            assert first.result(timeout=5)[0] == 200
        path = project / "revisions" / parent["revision"] / "manifest.json"
        raw = saved_raster(path).read_bytes()

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            saved_raster(path).write_bytes(raw + b"\n")
            return result

        monkeypatch.setattr(series_framing, "render_series", changed)
        assert http(server, "/api/series-preview", "POST", data)[0] == 409
        saved_raster(path).write_bytes(raw)
        monkeypatch.setattr(series_framing, "render_series", original)
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request(
            "POST",
            "/api/series-preview",
            json.dumps(data),
            {
                "Origin": server.origin,
                "Content-Type": "application/json",
                "X-Blackmask-Token": server.token,
            },
        )
        connection.close()
        assert http(server, "/api/series-preview", "POST", data)[0] in {200, 409}


def test_series_actions_bind_selected_revision_and_preserve_other_drafts(tmp_path):
    from test_effects import fixture_project, shading_request
    from test_series_framing import series_settings

    project, _, accepted = fixture_project(tmp_path)
    selected = operations.apply_operation(project, shading_request(project, opacity=0.12))[
        "revision"
    ]
    working = operations.apply_operation(project, shading_request(project, opacity=0.22))[
        "revision"
    ]
    assert len({accepted["revision"], selected, working}) == 3
    before = {
        name: (saved_raster(project / name)).read_bytes()
        for name in ("state.json", "recipe.toml", "guides.json")
    }
    settings = series_settings(output_width_px=40, output_height_px=50).to_dict()
    with running(project) as server:
        saved = perform(server, "series-save", settings=settings, expected_digest=None)
        assert saved["series_settings"] == settings
        revision = next(r for r in server.snapshot()["revisions"] if r["revision"] == selected)
        output = perform(
            server,
            "series-export",
            revision=selected,
            draft=True,
            revision_manifest_sha256=revision["revision_manifest_sha256"],
            settings=settings,
            transparent=True,
        )
        assert output["revision"] == selected and output["draft"] is True
        record = json.loads(saved_raster(Path(output["manifest_file"])).read_bytes())
        assert record["settings"] == settings
        assert record["revision_manifest_sha256"] == revision["revision_manifest_sha256"]
        assert all(
            (saved_raster(project / name)).read_bytes() == value for name, value in before.items()
        )


def test_framing_snapshot_preview_and_preset_error_are_independent(tmp_path):
    import base64
    import hashlib
    import io

    from PIL import Image
    from test_background import legacy_project
    from test_framing import margins

    project, parent = legacy_project(tmp_path)
    before = (project / "state.json").read_bytes()
    with running(project) as server:
        status, body, _ = http(server)
        state = json.loads(body)
        assert status == 200 and state["framing"] == margins(0, 0, 0, 0)
        record = next(r for r in state["revisions"] if r["revision"] == parent["revision"])
        expected = hashlib.sha256(
            (project / "revisions" / parent["revision"] / "manifest.json").read_bytes()
        ).hexdigest()
        assert record["revision_manifest_sha256"] == expected
        request = {
            "developed_id": state["developed_id"],
            "revision": parent["revision"],
            "revision_manifest_sha256": record["revision_manifest_sha256"],
            "margins": margins(),
        }
        status, body, headers = http(server, "/api/framing-preview", "POST", request)
        assert status == 200
        result = json.loads(body)
        for key, value in request.items():
            assert result[key] == value
        assert result["output_dimensions_wh"] == [9, 5]
        assert result["source_rect_xyxy"] == [1, 1, 7, 5]
        with Image.open(saved_raster(io.BytesIO(base64.b64decode(result["png_base64"])))) as image:
            assert image.mode == "RGB" and image.size == (9, 5)
            assert image.getpixel((0, 0)) == (0, 0, 0)
        assert "img-src 'self' blob:" in headers["Content-Security-Policy"]
        assert http(server, "/api/framing-preview", "POST", request, Origin="null")[0] == 403
        assert http(server, "/api/framing-preview", "POST", {**request, "path": "/tmp"})[0] == 400
        assert (
            http(
                server,
                "/api/framing-preview",
                "POST",
                {**request, "revision_manifest_sha256": "0" * 64},
            )[0]
            == 409
        )
        (project / "framing.json").write_text("{broken")
        state = json.loads(http(server)[1])
        assert state["framing"] is None and "framing.json" in state["framing_error"]
        assert http(server, "/api/framing-preview", "POST", request)[0] == 200
        assert (project / "state.json").read_bytes() == before


def test_framing_save_and_explicit_export_use_independent_form(tmp_path):
    from test_effects import fixture_project
    from test_framing import margins

    project, _, _ = fixture_project(tmp_path)
    before = (project / "recipe.toml").read_bytes()
    with running(project) as server:
        saved = perform(server, "framing-save", margins=margins(), expected_digest=None)
        assert saved["framing"] == margins()
        exported = perform(
            server,
            "export",
            revision=None,
            draft=False,
            framing=margins(7),
            framed_transparent=True,
        )
        assert exported["framing"] == margins(7)
        assert json.loads((project / "framing.json").read_bytes())["margins"] == margins()
        assert (project / "recipe.toml").read_bytes() == before


def test_framing_http_guard_disconnect_errors_and_race(tmp_path, monkeypatch):
    import socket
    from concurrent.futures import ThreadPoolExecutor

    from test_effects import fixture_project
    from test_framing import margins

    from blackmask import framing

    project, _, parent = fixture_project(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = framing.framing_preview

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    with running(project) as server:
        state = json.loads(http(server)[1])
        record = next(item for item in state["revisions"] if item["revision"] == parent["revision"])
        data = {
            "developed_id": state["developed_id"],
            "revision": record["revision"],
            "revision_manifest_sha256": record["revision_manifest_sha256"],
            "margins": margins(),
        }
        monkeypatch.setattr(framing, "framing_preview", paused)
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(http, server, "/api/framing-preview", "POST", data)
            assert entered.wait(3)
            assert http(server, "/api/framing-preview", "POST", data)[0] == 409
            assert http(server)[0] == 200
            release.set()
            assert first.result(timeout=5)[0] == 200
        # A disconnected client cannot retain the per-server render guard.
        entered.clear()
        release.clear()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request(
            "POST",
            "/api/framing-preview",
            json.dumps(data),
            {
                "X-Blackmask-Token": server.token,
                "Origin": server.origin,
                "Content-Type": "application/json",
            },
        )
        assert entered.wait(3)
        connection.sock.shutdown(socket.SHUT_RDWR)
        connection.close()
        release.set()
        assert server.framing_preview_lock.acquire(timeout=5)
        server.framing_preview_lock.release()
        monkeypatch.setattr(framing, "framing_preview", original)
        assert http(server, "/api/framing-preview", "POST", data)[0] == 200
        # A raw-byte edit during sampling must not be labelled with the old digest.
        path = project / "revisions" / record["revision"] / "manifest.json"
        raw = saved_raster(path).read_bytes()

        def changed(*args, **kwargs):
            saved_raster(path).write_bytes(raw + b"\n")
            return original(*args, **kwargs)

        monkeypatch.setattr(framing, "framing_preview", changed)
        assert http(server, "/api/framing-preview", "POST", data)[0] == 409
        monkeypatch.setattr(framing, "framing_preview", original)
        assert http(server, "/api/framing-preview", "POST", data)[0] == 409
        current = json.loads(http(server)[1])
        updated = next(
            item for item in current["revisions"] if item["revision"] == record["revision"]
        )
        assert updated["draft_digest"] == record["draft_digest"]
        assert updated["revision_manifest_sha256"] != record["revision_manifest_sha256"]
        data["revision_manifest_sha256"] = updated["revision_manifest_sha256"]
        assert http(server, "/api/framing-preview", "POST", data)[0] == 200
        assert http(server, "/api/framing-preview", "POST", data, Host="attacker.example")[0] == 403
        assert (
            http(server, "/api/framing-preview", "POST", data, **{"X-Blackmask-Token": "wrong"})[0]
            == 403
        )
        assert (
            http(server, "/api/framing-preview", "POST", data, **{"Content-Length": "2000001"})[0]
            == 413
        )


def test_framing_snapshot_rejects_manifest_replacement_during_validation(tmp_path, monkeypatch):
    from test_effects import fixture_project

    from blackmask import viewer

    project, _, parent = fixture_project(tmp_path)
    original = viewer.read_revision

    def replaced(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[1] == parent["revision"]:
            path = project / "revisions" / parent["revision"] / "manifest.json"
            saved_raster(path).write_bytes(saved_raster(path).read_bytes() + b"\n")
        return result

    monkeypatch.setattr(viewer, "read_revision", replaced)
    with viewer.ReviewServer(project) as server, pytest.raises(ProjectError, match="Stale"):
        server.snapshot()


def test_framing_snapshot_rejects_source_change_despite_benign_pointer_progress(
    tmp_path, monkeypatch
):
    from test_effects import fixture_project

    from blackmask.viewer import ReviewServer

    project, _, _ = fixture_project(tmp_path)
    original = operations.operation_status

    def changed(*args, **kwargs):
        state = original(*args, **kwargs)
        source = project / "source.json"
        source.write_bytes(source.read_bytes() + b"\n")
        return state

    monkeypatch.setattr(operations, "operation_status", changed)
    with (
        ReviewServer(project) as server,
        pytest.raises(ProjectError, match="Stale snapshot source"),
    ):
        server.snapshot()


def test_framing_preview_rejects_stale_enabled_effect_without_base_fallback(tmp_path):
    from unittest.mock import patch

    import numpy as np
    from test_effects import effect_request, fixture_project
    from test_framing import margins
    from test_matte_operations import StubSession
    from test_repair_operations import repair_guides, repair_request, run_repair

    project, _, _ = fixture_project(tmp_path)
    operations.apply_operation(project, effect_request(project))
    prepared = repair_guides(project, [1, 1, 4, 3])
    with patch.object(
        StubSession,
        "predict",
        side_effect=lambda rgb, guide, device: (np.full(guide.shape, 0.75), {}),
    ):
        result = run_repair(project, repair_request(project, prepared, [0, 0, 6, 4], [1, 1, 4, 3]))
    with running(project) as server:
        state = json.loads(http(server)[1])
        record = next(item for item in state["revisions"] if item["revision"] == result["revision"])
        assert record["color_cleanup"]["stale"]
        status, body, _ = http(
            server,
            "/api/framing-preview",
            "POST",
            {
                "developed_id": state["developed_id"],
                "revision": record["revision"],
                "revision_manifest_sha256": record["revision_manifest_sha256"],
                "margins": margins(),
            },
        )
        assert status == 409 and "Stale enabled appearance" in json.loads(body)["error"]


@contextmanager
def running(project):
    from blackmask.viewer import ReviewServer

    server = ReviewServer(project)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def http(server, path="/api/state", method="GET", data=None, **headers):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    defaults = {"X-Blackmask-Token": server.token}
    if method == "POST":
        defaults.update({"Origin": server.origin, "Content-Type": "application/json"})
    defaults.update(headers)
    body = json.dumps(data).encode() if data is not None else None
    connection.request(method, path, body, defaults)
    response = connection.getresponse()
    result = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return result


@pytest.mark.parametrize("reader", ["snapshot", "cache"])
def test_status_observation_does_not_reject_overlapping_viewer_writer(
    tmp_path, monkeypatch, reader
):
    import fcntl

    from test_project import create

    from blackmask.viewer import ReviewServer

    _, project = create(tmp_path)
    retained = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file() and path.name != "state.json"
    }
    observed = threading.Event()
    release = threading.Event()
    reader_thread = None

    def pause_after_observation(function):
        def observe(*arguments):
            result = function(*arguments)
            if threading.get_ident() == reader_thread:
                observed.set()
                assert release.wait(10), "Status observation was not released"
            return result

        return observe

    with ReviewServer(project) as server, ThreadPoolExecutor(max_workers=1) as executor:
        snapshot = server.snapshot()
        data = {key: snapshot[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(action="development", base_revision=None)

        def poll():
            nonlocal reader_thread
            reader_thread = threading.get_ident()
            return (
                server.snapshot()
                if reader == "snapshot"
                else operations.inspect_processing_cache(project)
            )

        # Keep real OS calls: suspend immediately after the observation so the
        # writer deterministically overlaps any lock accidentally held by it.
        monkeypatch.setattr(fcntl, "flock", pause_after_observation(fcntl.flock))
        monkeypatch.setattr(fcntl, "fcntl", pause_after_observation(fcntl.fcntl))
        pending = executor.submit(poll)
        try:
            assert observed.wait(10), "Reader did not observe the writer lock"
            result = server.execute(data)
            assert result["development_approved"] is True
        finally:
            release.set()
            status = pending.result(timeout=10)
        assert status["writer_busy"] is False
        assert read_project(project)["accepted_revision"] is None
        assert all((project / name).read_bytes() == raw for name, raw in retained.items())


def test_new_viewer_serves_only_authenticated_project_and_packaged_page(tmp_path):
    _, project = opened(tmp_path)
    with running(project) as server:
        assert server.server_address[0] == "127.0.0.1"
        status, body, headers = http(server, "/")
        assert status == 200 and b"<canvas" in body
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        status, body, _ = http(server)
        state = json.loads(body)
        assert status == 200 and state["developed_id"] == read_project(project)["developed_id"]
        assert state["dimensions_wh"] == [3, 2]
        assert http(server, "/api/state", **{"X-Blackmask-Token": ""})[0] == 403
        assert http(server, "/api/state", Host="attacker.example")[0] == 403
        assert http(server, "/api/state", Origin="https://attacker.example")[0] == 403
        for path in [
            "/../state.json",
            "/%2e%2e/state.json",
            "/assets/recipe.toml",
            "/source.json",
            "/api/state?path=/etc/passwd",
        ]:
            assert http(server, path)[0] in (400, 404)
        assert http(server, "/api/action", "POST", {}, Origin="null")[0] == 403
        assert http(server, "/api/action", "POST", {}, **{"Content-Length": "2000001"})[0] == 413


def test_viewer_draft_authoring_stale_and_once_only_prepare(tmp_path):
    _, project = opened(tmp_path)
    region = {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 1]}
    identity = request(project)
    saved = operations.save_guidance_draft(
        project, identity, [], [{"action": "upsert", "region": region}]
    )
    assert json.loads((project / "guides.json").read_text())["regions"] == []
    with pytest.raises(ProjectError, match="Stale"):
        operations.save_guidance_draft(project, dict(identity, inputs_digest="0" * 64), [], [])
    result = operations.prepare_guidance_draft(
        project, dict(identity, inputs_digest=saved["inputs_digest"]), [0, 0, 3, 2]
    )
    assert json.loads((project / "guides.json").read_text())["regions"] == [region]
    again = operations.prepare_guidance_draft(project, request(project), [0, 0, 3, 2])
    assert again["parent"] == result["revision"]
    assert json.loads((project / "guides.json").read_text())["regions"] == [region]


def test_viewer_asset_identity_and_symlink_rejection(tmp_path):
    _, project = opened(tmp_path)
    with running(project) as server:
        _, body, _ = http(server)
        state = json.loads(body)
        path = state["source_url"]
        status, png, _ = http(server, path)
        assert status == 200 and png.startswith(b"\x89PNG")
        assert http(server, path.replace(state["developed_id"], "0" * 64))[0] == 404
        source = project / "source.json"
        original = source.read_bytes()
        source.rename(project / "source-original.json")
        source.symlink_to(project / "source-original.json")
        assert http(server, path)[0] in (400, 409)
        assert (project / "source-original.json").read_bytes() == original


def test_viewer_reads_responsive_and_writer_reports_busy(tmp_path):
    _, project = opened(tmp_path)
    with running(project) as server, project_lock(project):
        status, body, _ = http(server)
        assert status == 200 and json.loads(body)["writer_busy"]
        data = {
            k: v
            for k, v in request(project).items()
            if k in {"developed_id", "base_revision", "inputs_digest"}
        }
        data["action"] = "development"
        data["authoring_digest"] = operations.guidance_draft_digest(project)
        status, _, _ = http(server, "/api/action", "POST", data)
        assert status == 202
        for _ in range(100):
            _, body, _ = http(server)
            state = json.loads(body)
            if not state["action"]["running"]:
                break
        assert "busy" in state["action"]["error"].lower()


def test_saved_pending_guides_block_approval_and_replaced_restore_rejects_stale_identity(tmp_path):
    from test_matte_operations import prepared

    from blackmask.viewer import ReviewServer

    _, project, prepared_result = prepared(tmp_path)
    identity = {
        k: v
        for k, v in request(project).items()
        if k in {"developed_id", "base_revision", "inputs_digest"}
    }
    region = {"id": "pending", "role": "unknown", "shape": "point", "xy": [1, 1]}
    operations.save_guidance_draft(project, identity, [], [{"action": "upsert", "region": region}])
    with ReviewServer(project) as server, pytest.raises(ProjectError, match="pending"):
        server.execute(
            dict(
                identity,
                authoring_digest=operations.guidance_draft_digest(project),
                action="trimap",
                revision=prepared_result["revision"],
            )
        )
    with pytest.raises(ProjectError, match="Stale"):
        operations.restore_revision(
            project,
            prepared_result["revision"],
            replace_drafts=True,
            expected_identity=dict(identity, inputs_digest="0" * 64),
        )


def perform(server, action, **extra):
    status, body, _ = http(server)
    assert status == 200, body
    state = json.loads(body)
    data = {
        "action": action,
        "developed_id": state["developed_id"],
        "base_revision": state["working_revision"],
        "inputs_digest": state["inputs_digest"],
        "authoring_digest": state["authoring_digest"],
        **extra,
    }
    status, body, _ = http(server, "/api/action", "POST", data)
    assert status == 202, body
    for _ in range(500):
        status, body, _ = http(server)
        assert status == 200, body
        state = json.loads(body)
        if not state["action"]["running"]:
            assert state["action"]["error"] is None, state["action"]
            return state["action"]["result"]
    raise AssertionError("Viewer action did not finish")


def test_actual_http_manual_journey_new_support_partial_lock_accept_restore_resume(
    tmp_path, monkeypatch
):
    import numpy as np
    from PIL import Image
    from test_matte_operations import StubSession

    monkeypatch.setattr(operations, "VitMatteSession", StubSession)
    _, project = opened(tmp_path)
    original = (
        saved_raster(
            project / "assets/developed" / (read_project(project)["developed_id"] + ".tif")
        )
    ).read_bytes()
    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-cache")
        perform(server, "prepare", scope_xyxy=[0, 0, 3, 2])
        perform(server, "matte")
        assert not (project / "revisions/rev-002/trimap_approval.json").exists()
        alpha = np.array(Image.open(saved_raster(project / "revisions/rev-002/base_alpha16.png")))
        assert np.any((alpha > 0) & (alpha < 65535))
        perform(server, "accept", revision="rev-002")
        accepted = perform(server, "export", revision="rev-002", draft=False)
        paths = list(Path(accepted["directory"]).glob("*"))
        hashes = {p.name: p.read_bytes() for p in paths if p.is_file()}
        actions = [
            {"action": "upsert", "region": r}
            for r in [
                {"id": "bg", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 1, 1]},
                {
                    "id": "support",
                    "role": "support",
                    "shape": "rectangle",
                    "xyxy": [0, 0, 2, 2],
                    "feather_px": 0,
                },
                {
                    "id": "lock",
                    "role": "lock",
                    "shape": "point",
                    "xy": [1, 1],
                    "revision": "rev-002",
                },
            ]
        ]
        perform(server, "save", groups=[], actions=actions)
        perform(server, "prepare", scope_xyxy=[0, 0, 2, 2])
        perform(
            server,
            "repair",
            scope_xyxy=[0, 0, 2, 2],
            context_xyxy=[0, 0, 3, 2],
            reason="Synthetic BG correction; automated control test, no human approval",
            merge_policy="replace",
        )
        repaired = np.array(
            Image.open(saved_raster(project / "revisions/rev-004/base_alpha16.png"))
        )
        assert not (project / "revisions/rev-004/trimap_approval.json").exists()
        assert repaired[0, 0] == 0 and repaired[1, 1] == alpha[1, 1]
        assert np.array_equal(repaired[:, 2], alpha[:, 2])
        perform(server, "accept", revision="rev-004")
        perform(server, "restore", revision="rev-002", replace_drafts=True)
        assert read_project(project)["accepted_revision"] == "rev-004"
        perform(
            server,
            "resume",
            operation_id=next(
                o["operation_id"]
                for o in operations.operation_status(project)["operations"]
                if o.get("revision") == "rev-002"
            ),
        )
        for p in paths:
            if p.is_file():
                assert p.read_bytes() == hashes[p.name]
        assert (
            saved_raster(
                project / "assets/developed" / (read_project(project)["developed_id"] + ".tif")
            )
        ).read_bytes() == original


def test_pending_removal_not_reapplied_after_restore(tmp_path):
    from test_matte_operations import prepared

    _, project, result = prepared(tmp_path)
    identity = request(project)
    actions = [{"action": "remove", "id": "fg"}]
    operations.save_guidance_draft(project, identity, [], actions)
    updated = operations.prepare_guidance_draft(project, request(project), [0, 0, 3, 2])
    operations.restore_revision(project, result["revision"], replace_drafts=True)
    assert operations.pending_guidance(project)["consumed"]
    again = operations.prepare_guidance_draft(project, request(project), [0, 0, 3, 2])
    assert again["revision"] != updated["revision"]
    assert any(
        r["id"] == "fg" for r in json.loads((project / "guides.json").read_text())["regions"]
    )


def test_viewer_malformed_drafts_remain_readable_and_explicit_restore_preserves_bytes(tmp_path):
    from test_matte_operations import prepared

    _, project, result = prepared(tmp_path)
    malformed = b"{broken draft bytes"
    (project / "guides.json").write_bytes(malformed)
    with running(project) as server:
        status, body, _ = http(server)
        assert status == 200, body
        assert json.loads(body)["draft_error"]
        perform(server, "restore", revision=result["revision"], replace_drafts=True)
    assert any(p.read_bytes() == malformed for p in (project / "recovery").rglob("guides.json"))


def test_two_authoring_clients_cannot_overwrite_same_recipe_pending_edits(tmp_path):
    _, project = opened(tmp_path)
    identity = dict(request(project), authoring_digest=operations.guidance_draft_digest(project))
    actions = [
        {
            "action": "upsert",
            "region": {"id": "first", "role": "unknown", "shape": "point", "xy": [1, 1]},
        }
    ]
    first = operations.save_guidance_draft(project, identity, [], actions)
    with pytest.raises(ProjectError, match="Stale"):
        operations.save_guidance_draft(project, identity, [], [])
    assert json.loads((project / "viewer-draft.json").read_text())["actions"] == actions
    assert first["inputs_digest"] == operations.draft_digest(project)


def test_save_guidance_rechecks_drafts_before_recipe_publication(tmp_path, monkeypatch):
    _, project = opened(tmp_path)
    original = operations._atomic_json
    identity = request(project)

    def inject(path, value, **kwargs):
        result = original(path, value, **kwargs)
        if path.name.startswith("viewer-edits-"):
            with (project / "recipe.toml").open("ab") as stream:
                stream.write(b"\n# concurrent newer draft\n")
        return result

    monkeypatch.setattr(operations, "_atomic_json", inject)
    with pytest.raises(ProjectError, match="Stale"):
        operations.save_guidance_draft(project, identity, [], [])
    assert b"concurrent newer draft" in (project / "recipe.toml").read_bytes()


def test_actual_viewer_writer_excludes_cli_accept_restore_and_keeps_reads_responsive(
    tmp_path, monkeypatch
):
    import subprocess
    import sys
    import threading

    from test_matte_operations import StubSession

    started, release = threading.Event(), threading.Event()

    class PausedSession(StubSession):
        def predict(self, rgb, trimap, device):
            started.set()
            assert release.wait(10)
            return super().predict(rgb, trimap, device)

    monkeypatch.setattr(operations, "VitMatteSession", PausedSession)
    _, project = opened(tmp_path)
    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-cache")
        perform(server, "prepare", scope_xyxy=[0, 0, 3, 2])
        perform(server, "trimap", revision="rev-001")
        state = json.loads(http(server)[1])
        data = {k: state[k] for k in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(action="matte", base_revision=state["working_revision"])
        assert http(server, "/api/action", "POST", data)[0] == 202
        try:
            assert started.wait(5)
            assert json.loads(http(server)[1])["writer_busy"]
            assert http(server, state["source_url"])[0] == 200
            for arguments in [
                ["accept", str(project), "--development", "--developed-id", state["developed_id"]],
                ["restore", str(project), "--revision", "rev-001"],
            ]:
                child = subprocess.run(
                    [sys.executable, "-m", "blackmask", *arguments],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                assert child.returncode == 1 and "busy" in child.stderr.lower(), child.stderr
        finally:
            release.set()
        for _ in range(100):
            if not json.loads(http(server)[1])["action"]["running"]:
                break
        assert read_project(project)["working_revision"] == "rev-002"


def test_restore_same_revision_explicitly_preserves_and_retires_pending_authoring(tmp_path):
    from test_matte_operations import prepared

    _, project, result = prepared(tmp_path)
    actions = [
        {
            "action": "upsert",
            "region": {"id": "pending", "role": "unknown", "shape": "point", "xy": [1, 1]},
        }
    ]
    operations.save_guidance_draft(project, request(project), [], actions)
    before = (project / "viewer-draft.json").read_bytes()
    with pytest.raises(ProjectError, match="pending"):
        operations.restore_revision(project, result["revision"])
    restored = operations.restore_revision(project, result["revision"], replace_drafts=True)
    assert (Path(restored["recovery_directory"]) / "viewer-draft.json").read_bytes() == before
    assert not operations.pending_guidance(project)["current"]
    assert not operations.pending_guidance(project)["consumed"]


@pytest.mark.parametrize(
    "damage",
    [
        "pointer-json",
        "pointer-fields",
        "missing-record",
        "record-fields",
        "missing-edits",
        "edits-json",
    ],
)
def test_damaged_pending_guidance_stays_readable_and_explicit_restore_preserves_bytes(
    tmp_path, damage
):
    from test_matte_operations import prepared

    _, project, result = prepared(tmp_path)
    operations.save_guidance_draft(
        project,
        request(project),
        [],
        [
            {
                "action": "upsert",
                "region": {"id": "pending", "role": "unknown", "shape": "point", "xy": [1, 1]},
            }
        ],
    )
    pointer = project / "viewer-draft.json"
    pending = json.loads(saved_raster(pointer).read_bytes())
    if damage == "pointer-json":
        saved_raster(pointer).write_bytes(b"{broken pending pointer")
    elif damage == "pointer-fields":
        pointer.write_text("[]")
    elif damage == "missing-record":
        (saved_raster(project / pending["record_file"])).rename(project / "retained-record.json")
    elif damage == "record-fields":
        record = json.loads((saved_raster(project / pending["record_file"])).read_bytes())
        del record["actions"]
        (project / pending["record_file"]).write_text(json.dumps(record))
    elif damage == "missing-edits":
        (saved_raster(project / pending["guide_edits_file"])).rename(
            project / "retained-edits.json"
        )
    else:
        (project / pending["guide_edits_file"]).write_text("{broken edits")
    before = saved_raster(pointer).read_bytes()
    state_before = read_project(project)
    with pytest.raises(ProjectError):
        operations.pending_guidance(project)
    with pytest.raises(ProjectError):
        operations.restore_revision(project, result["revision"])
    with running(project) as server:
        status, body, _ = http(server)
        assert status == 200, body
        assert json.loads(body)["draft_error"]
        restored = perform(server, "restore", revision=result["revision"], replace_drafts=True)
        assert (Path(restored["recovery_directory"]) / "viewer-draft.json").read_bytes() == before
        assert http(server)[0] == 200
    assert operations.pending_guidance(project) is None
    assert read_project(project)["accepted_revision"] == state_before["accepted_revision"]
    assert read_project(project)["developed_id"] == state_before["developed_id"]


def test_snapshot_reuses_validated_master_and_revision_within_one_read(tmp_path, monkeypatch):
    from test_matte_operations import prepared

    from blackmask.viewer import ReviewServer

    _, project, result = prepared(tmp_path)
    operations.save_guidance_draft(project, request(project), [], [])
    master = project / "assets/developed" / (result["developed_id"] + ".tif")
    trimap = saved_raster(project / "revisions" / result["revision"] / "trimap.png")
    from blackmask import assets

    checksum = assets._checksum
    reads = {master: 0, trimap: 0}
    original = Path.read_bytes

    def counted(path):
        if path in reads:
            reads[path] += 1
        return original(path)

    def counted_checksum(path):
        if path in reads:
            reads[path] += 1
        return checksum(path)

    with ReviewServer(project) as server:
        monkeypatch.setattr(Path, "read_bytes", counted)
        monkeypatch.setattr(assets, "_checksum", counted_checksum)
        snapshot = server.snapshot()
        assert snapshot["pending"]["current"]
        assert reads == {master: 1, trimap: 1}
        snapshot = server.snapshot()
        assert reads == {master: 2, trimap: 2}, "Validation must not survive a request"
    pixels, _ = load_developed(project, result["developed_id"])
    assert pixels.flags.writeable, "Read-only viewer buffers leaked into processing callers"


@pytest.mark.parametrize("asset", ["master", "source", "trimap"])
def test_snapshot_rejects_changes_during_reused_validation(tmp_path, monkeypatch, asset):
    from test_matte_operations import prepared

    from blackmask import viewer

    _, project, result = prepared(tmp_path)
    path = {
        "master": project / "assets/developed" / (result["developed_id"] + ".tif"),
        "source": project / "source.json",
        "trimap": project / "revisions" / result["revision"] / "trimap.png",
    }[asset]
    original = viewer._validate_assets

    def changed(*args, **kwargs):
        data = saved_raster(path).read_bytes()
        saved_raster(path).write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        return original(*args, **kwargs)

    with viewer.ReviewServer(project) as server:
        monkeypatch.setattr(viewer, "_validate_assets", changed)
        with pytest.raises(ProjectError):
            server.snapshot()


def test_request_local_master_reuse_keeps_buffers_readonly_and_metadata_independent(tmp_path):
    import copy

    from blackmask.project import _validation_scope

    _, project = opened(tmp_path)
    developed_id = read_project(project)["developed_id"]
    with _validation_scope():
        pixels, metadata = load_developed(project, developed_id)
        expected_metadata = copy.deepcopy(metadata)
        assert not pixels.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            pixels[0, 0] = 0
        metadata["reader_note"] = "not saved"
        reused_pixels, fresh_metadata = load_developed(project, developed_id)
        assert not reused_pixels.flags.writeable
        assert fresh_metadata == expected_metadata
    assert load_developed(project, developed_id)[0].flags.writeable


def test_request_local_revision_reuse_preserves_identity_and_manifest_copies(tmp_path):
    from test_matte_operations import prepared

    from blackmask.project import _validation_scope, read_revision

    _, project, result = prepared(tmp_path)
    with _validation_scope():
        expected = read_revision(project, result["revision"], result["developed_id"])
        changed_by_reader = read_revision(project, result["revision"], result["developed_id"])
        changed_by_reader["files"].clear()
        assert read_revision(project, result["revision"], result["developed_id"]) == expected
        with pytest.raises(ProjectError, match="developed identity"):
            read_revision(project, result["revision"], "0" * 64)
        assert read_revision(project, result["revision"], result["developed_id"]) == expected


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (IndexError("synthetic worker failure"), "synthetic worker failure"),
        (ValueError(), "ValueError"),
        (ValueError("   "), "ValueError"),
    ],
)
def test_background_action_failure_is_visible_and_next_action_succeeds(
    tmp_path, monkeypatch, error, expected
):
    _, project = opened(tmp_path)
    with running(project) as server:
        execute = server.execute

        def fail(data):
            raise error

        monkeypatch.setattr(server, "execute", fail)
        status, body, _ = http(server)
        assert status == 200
        state = json.loads(body)
        data = {key: state[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(action="development", base_revision=state["working_revision"])
        assert http(server, "/api/action", "POST", data)[0] == 202
        for _ in range(100):
            status, body, _ = http(server)
            assert status == 200
            action = json.loads(body)["action"]
            if not action["running"]:
                break
        assert action["running"] is False
        assert action["error"] == expected
        assert action["result"] is None
        assert server.action_lock.acquire(blocking=False), "Failed worker retained its lock"
        server.action_lock.release()
        monkeypatch.setattr(server, "execute", execute)
        result = perform(server, "development")
        assert result["developed_id"] == state["developed_id"]
        assert result["development_approved"] is True


@pytest.mark.parametrize("error", [SystemExit(), KeyboardInterrupt()])
def test_background_action_base_exception_propagates_after_cleanup(tmp_path, monkeypatch, error):
    _, project = opened(tmp_path)
    observed = []
    propagated = threading.Event()

    def capture(arguments):
        observed.append(arguments.exc_value)
        propagated.set()

    monkeypatch.setattr(threading, "excepthook", capture)
    with running(project) as server:
        execute = server.execute

        def fail(data):
            raise error

        monkeypatch.setattr(server, "execute", fail)
        status, body, _ = http(server)
        assert status == 200
        state = json.loads(body)
        data = {key: state[key] for key in ("developed_id", "inputs_digest", "authoring_digest")}
        data.update(action="development", base_revision=state["working_revision"])
        assert http(server, "/api/action", "POST", data)[0] == 202
        assert propagated.wait(3), "BaseException was swallowed by the worker"
        assert observed == [error]
        status, body, _ = http(server)
        assert status == 200
        assert json.loads(body)["action"] == {
            "running": False,
            "name": "development",
            "error": None,
            "result": None,
        }
        assert server.action_lock.acquire(blocking=False)
        server.action_lock.release()
        monkeypatch.setattr(server, "execute", execute)
        assert perform(server, "development")["development_approved"] is True


@pytest.mark.parametrize("prepublished_native", [False, True])
def test_comparison_http_retains_native_without_successful_duplicate_stages(
    tmp_path, prepublished_native
):
    import base64

    from test_effects import fixture_project
    from test_library import inventory

    from blackmask import review
    from blackmask.project import digest

    project, _, revision = fixture_project(tmp_path)
    crops = [[1, 0, 6, 4]]
    prior = project / "reviews" / revision["revision"] / ".review-earlier"
    prior.mkdir(parents=True)
    (prior / "keep.txt").write_bytes(b"earlier recovery material")
    (project / "notes.txt").write_bytes(b"unrelated data")
    canonical = None
    if prepublished_native:
        canonical = Path(review.review_project(project, crops=crops)["manifest_file"])
        canonical_inodes = {p.name: p.stat().st_ino for p in canonical.parent.iterdir()}
    protected = inventory(tmp_path)
    with running(project) as server:
        status, body, _ = http(server)
        assert status == 200
        snapshot = json.loads(body)
        selected = next(r for r in snapshot["revisions"] if r["revision"] == revision["revision"])
        fields = {
            "revision": revision["revision"],
            "revision_manifest_sha256": selected["revision_manifest_sha256"],
            "crops": crops,
            "retain_native": True,
            "presentation": None,
        }
        output = perform(server, "comparison", **fields)
        manifest = Path(output["comparison_manifest_file"])
        record = json.loads(manifest.read_bytes())
        native = Path(output["native_manifest_file"])
        binding = record["native_evidence"]
        assert binding["before"] is None
        assert binding["after"]["manifest_file"] == str(native.relative_to(project))
        assert binding["after"]["sha256"] == digest(native.read_bytes())
        native_record = review._native_review_record(project, str(native.relative_to(project)))
        assert [crop["crop_xyxy"] for crop in native_record["crops"]] == crops
        assert (
            base64.b64decode(output["view"]["jpeg_base64"])
            == (manifest.parent / "comparison_RGB8_VIEW.jpg").read_bytes()
        )
        assert json.loads(output["view"]["manifest_json"]) == record
        assert list(native.parent.parent.glob(".review-*")) == [prior]
        assert {p.name for p in native.parent.parent.iterdir()} == {native.parent.name, prior.name}
        if canonical is not None:
            assert native == canonical
            assert {p.name: p.stat().st_ino for p in native.parent.iterdir()} == canonical_inodes
        complete = inventory(tmp_path)
        assert all(complete[name] == value for name, value in protected.items())
        added = set(complete) - set(protected)
        allowed = {
            str(p.relative_to(tmp_path))
            for p in (
                project / "reviews/comparisons",
                manifest.parent,
                native.parent,
                *manifest.parent.iterdir(),
                *native.parent.iterdir(),
            )
        }
        assert added <= allowed
        assert perform(server, "comparison", **fields) == {**output, "reused": True}
        assert inventory(tmp_path) == complete


def test_comparison_action_binds_selected_revision_crop_and_preserves_drafts(tmp_path):
    from test_effects import fixture_project

    project, _, revision = fixture_project(tmp_path)
    before = {
        name: (project / name).read_bytes() for name in ("state.json", "recipe.toml", "guides.json")
    }
    with running(project) as server:
        snapshot = server.snapshot()
        selected = next(r for r in snapshot["revisions"] if r["revision"] == revision["revision"])
        output = perform(
            server,
            "comparison",
            revision=revision["revision"],
            revision_manifest_sha256=selected["revision_manifest_sha256"],
            crops=[[1, 0, 6, 4]],
            retain_native=False,
            presentation=None,
        )
        record = json.loads(Path(output["comparison_manifest_file"]).read_bytes())
        import base64

        assert (
            base64.b64decode(output["view"]["jpeg_base64"])
            == (
                Path(output["comparison_manifest_file"]).parent / "comparison_RGB8_VIEW.jpg"
            ).read_bytes()
        )
        assert json.loads(output["view"]["manifest_json"]) == record
        assert record["request"]["revision"] == revision["revision"]
        assert record["request"]["crops"] == [[1, 0, 6, 4]]
        assert record["native_evidence"] is None
        assert all((project / name).read_bytes() == value for name, value in before.items())
        with pytest.raises(ProjectError, match="Stale comparison"):
            server.execute(
                {
                    "action": "comparison",
                    "developed_id": snapshot["developed_id"],
                    "base_revision": snapshot["working_revision"],
                    "inputs_digest": snapshot["inputs_digest"],
                    "authoring_digest": snapshot["authoring_digest"],
                    "revision": revision["revision"],
                    "revision_manifest_sha256": "0" * 64,
                    "crops": [[1, 0, 6, 4]],
                    "retain_native": False,
                    "presentation": None,
                }
            )
