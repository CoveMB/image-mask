import json
import threading
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

import pytest
from test_operations import opened, request

from blackmask import operations
from blackmask.project import ProjectError, project_lock, read_project


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


def test_new_viewer_serves_only_authenticated_project_and_packaged_page(tmp_path):
    _, project = opened(tmp_path)
    with running(project) as server:
        assert server.server_address[0] == "127.0.0.1"
        status, body, headers = http(server, "/")
        assert status == 200 and b"<canvas" in body
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        status, body, _ = http(server)
        state = json.loads(body)
        assert status == 200 and state["master_id"] == read_project(project)["master_id"]
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
        assert http(server, path.replace(state["master_id"], "0" * 64))[0] == 404
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
            if k in {"master_id", "base_revision", "inputs_digest"}
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
        if k in {"master_id", "base_revision", "inputs_digest"}
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
        "master_id": state["master_id"],
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
    original = (project / "masters" / (read_project(project)["master_id"] + ".tif")).read_bytes()
    with running(project) as server:
        server.model_cache = Path("explicit-synthetic-test-cache")
        perform(server, "prepare", scope_xyxy=[0, 0, 3, 2])
        perform(server, "trimap", revision="rev-001")
        perform(server, "matte")
        alpha = np.array(Image.open(project / "revisions/rev-002/base_alpha16.png"))
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
        perform(server, "trimap", revision="rev-003")
        perform(
            server,
            "repair",
            scope_xyxy=[0, 0, 2, 2],
            context_xyxy=[0, 0, 3, 2],
            reason="Synthetic BG correction; automated control test, no human approval",
            merge_policy="replace",
        )
        repaired = np.array(Image.open(project / "revisions/rev-004/base_alpha16.png"))
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
            project / "masters" / (read_project(project)["master_id"] + ".tif")
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
        data = {k: state[k] for k in ("master_id", "inputs_digest", "authoring_digest")}
        data.update(action="matte", base_revision=state["working_revision"])
        assert http(server, "/api/action", "POST", data)[0] == 202
        try:
            assert started.wait(5)
            assert json.loads(http(server)[1])["writer_busy"]
            assert http(server, state["source_url"])[0] == 200
            for arguments in [
                ["accept", str(project), "--development", "--master-id", state["master_id"]],
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
