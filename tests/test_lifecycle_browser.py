"""Real Chrome controls supplement the existing storage/reconstruction journey."""

import importlib.metadata
import json
import os
import re
import socket
import uuid
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image
from storage_journey_process import process_environment, running_process
from test_cache_management import inventory
from test_ingest import saved_raster
from test_library_storage_journey import assert_editable_native, imported_project

from blackmask.project import project_lock, read_project

pytestmark = pytest.mark.browser


def alpha(project, revision):
    with Image.open(saved_raster(project / f"revisions/{revision}/base_alpha16.png")) as image:
        return np.array(image)


def foreground(project, revision):
    return tifffile.imread(saved_raster(project / f"revisions/{revision}/foreground_rgb16.tif"))


def ready(page):
    from playwright.sync_api import expect

    # Use visible readiness without bypassing the shipped Content Security Policy.
    expect(page.locator("#shadingStatus")).to_have_text(
        re.compile(r"^(Viewed rev-\d+|Source RGB8|Alpha8).*"), timeout=10000
    )


def submit(page, control, action, *, keyboard=False, error=None):
    from playwright.sync_api import expect

    if action == "prepare":
        page.locator("#panel").select_option("source")
        ready(page)
    with page.expect_response(lambda response: response.url.endswith("/api/action")) as response:
        if keyboard:
            page.locator(control).press("Enter")
        else:
            page.locator(control).click()
    assert response.value.status == 202, response.value.text()
    completed = page.wait_for_event(
        "response",
        predicate=lambda response: (
            response.url.endswith("/api/state")
            and response.json()["action"].get("name") == action
            and not response.json()["action"]["running"]
        ),
        timeout=60000,
    ).json()
    expect(page.locator("#matte")).to_be_enabled()
    if error:
        expect(page.locator("#message")).to_contain_text(error)
        assert error in completed["action"]["error"]
    else:
        assert completed["action"]["error"] is None, completed["action"]
        expect(page.locator("#message")).to_have_text("")
        expect(page.locator("#status")).to_contain_text(
            "working " + (completed["working_revision"] or "none")
        )
        ready(page)
    return completed["action"]["result"]


def guide(page, role, coordinates, *, shape="rectangle", revision=None):
    page.locator("#role").select_option(role)
    page.locator("#shape").select_option(shape)
    if revision:
        page.locator("#lockRevision").select_option(revision)
    page.locator("#geometry").fill(coordinates)
    page.locator("#geometry").press("Tab")
    page.keyboard.press("Enter")


@contextmanager
def browser_session(playwright, server, workspace, name, receipt):
    from playwright.sync_api import expect

    environment = process_environment(workspace)
    environment["TMPDIR"] = os.environ["TMPDIR"]
    environment["MAC_CHROMIUM_TMPDIR"] = os.environ["MAC_CHROMIUM_TMPDIR"]
    with playwright.chromium.launch_persistent_context(
        str(workspace / f"profile-{name}"),
        channel="chrome",
        headless=True,
        # macOS cannot nest sandbox profiles. This synthetic-only lane uses the
        # enclosing OS sandbox after its negative controls pass, by explicit approval.
        chromium_sandbox=False,
        timeout=30000,
        viewport={"width": 1280, "height": 960},
        downloads_path=str(workspace / "downloads"),
        env=environment,
        service_workers="block",
    ) as context:
        from playwright.sync_api import Error

        probe = context.new_page()
        with pytest.raises(Error, match="ERR_ACCESS_DENIED"):
            probe.goto("http://198.51.100.1/", timeout=10000)
        probe.close()
        receipt["browser_external_network_denied"] = True
        receipt["browser_version"] = context.browser.version
        receipt.setdefault("application_pids", []).append(server.pid)
        context.tracing.start(screenshots=True, snapshots=True)
        failures = []
        page = context.new_page()
        page.on("pageerror", lambda error: failures.append(str(error)))
        try:
            page.goto(server.origin + "/#" + server.token)
            expect(page.locator("#status")).to_contain_text("working")
            # Preparation has no complete Result; Source remains available.
            page.locator("#panel").select_option("source")
            ready(page)
            yield page
            assert failures == [], failures
        finally:
            page.screenshot(path=str(workspace / f"{name}.png"), full_page=True)
            context.tracing.stop(path=str(workspace / f"{name}-trace.zip"))


def test_browser_controls_restart_and_offline_recovery(tmp_path):
    if os.environ.get("BLACKMASK_BROWSER") != "1":
        pytest.skip("Real browser evidence not selected; use tests/run_browser.py after setup")
    missing_variables = [
        name for name in ("TMPDIR", "MAC_CHROMIUM_TMPDIR") if not os.environ.get(name)
    ]
    if missing_variables:
        pytest.fail(
            "Missing browser runner environment: "
            + ", ".join(missing_variables)
            + ". Use tests/run_browser.py.",
            pytrace=False,
        )
    # Explicit browser runs fail, rather than skip, if setup or isolation is missing.
    from playwright.sync_api import expect, sync_playwright

    with socket.socket() as connection:
        connection.settimeout(1)
        with pytest.raises(PermissionError):
            connection.connect(("198.51.100.1", 443))
    outside = Path("/private/tmp") / ("im-browser-denied-" + uuid.uuid4().hex)
    with pytest.raises(PermissionError):
        outside.write_bytes(b"must be denied")
    config_file, _config, project, pixels = imported_project(tmp_path)
    originals = inventory(project.parent / "original")
    source_assets = inventory(project / "assets")
    receipt = {
        "playwright_version": importlib.metadata.version("playwright"),
        "native_network_denied": True,
        "native_outside_write_denied": True,
    }
    try:
        with sync_playwright() as playwright:
            with (
                running_process(project, config_file, tmp_path) as server,
                browser_session(playwright, server, tmp_path, "initial", receipt) as page,
            ):
                first = submit(page, "#matte", "matte")["revision"]
                initial_alpha = alpha(project, first)
                assert np.all(initial_alpha[:, :8] == 0)
                assert np.all(initial_alpha[:, 88:] == 65535)
                assert initial_alpha[20, 30] == 32768
                page.locator("#crop").fill("10,8,50,40")
                page.locator("#cropApply").click()
                ready(page)
                page.locator("#native").click()
                page.locator("#canvas").focus()
                page.keyboard.press("+")
                page.keyboard.press("ArrowRight")
                page.keyboard.press("ArrowLeft")
                # 1:1 then one '+' gives 1.25 display pixels/native pixel.
                # Independent expected point (27,23) in the nonzero native crop.
                page.locator("#role").select_option("foreground")
                page.locator("#shape").select_option("point")
                canvas = page.locator("#canvas")
                canvas.scroll_into_view_if_needed()
                box = canvas.bounding_box()
                page.mouse.click(
                    box["x"] + box["width"] / 2 + (27.5 - 30) * 1.25,
                    box["y"] + box["height"] / 2 + (23.5 - 24) * 1.25,
                )
                guide(page, "background", "24,16,26,18")
                page.locator("#feather").fill("2")
                guide(page, "support", "20,10,40,30")
                guide(page, "lock", "30,20,31,21", revision=first)
                submit(page, "#save", "save", keyboard=True)
                page.locator("#scope").fill("20,10,40,30")
                page.locator("#context").fill("16,6,44,34")
                submit(page, "#prepare", "prepare")
                prepared = read_project(project)["working_revision"]
                assert np.array_equal(alpha(project, prepared), initial_alpha)
                guides = json.loads((project / "guides.json").read_bytes())["regions"]
                assert any(
                    item.get("xy") == [27, 23] and item["role"] == "foreground" for item in guides
                )
                assert any(
                    item.get("xyxy") == [24, 16, 26, 18] and item["role"] == "background"
                    for item in guides
                )
                assert any(
                    item["role"] == "support"
                    and item.get("xyxy") == [20, 10, 40, 30]
                    and item.get("feather_px") == 2
                    for item in guides
                )
                assert any(
                    item["role"] == "lock"
                    and item.get("xyxy") == [30, 20, 31, 21]
                    and item.get("revision") == first
                    for item in guides
                )
                with (
                    Image.open(
                        saved_raster(project / f"revisions/{prepared}/supports/support16.png")
                    ) as support_image,
                    Image.open(
                        saved_raster(project / f"revisions/{prepared}/supports/protection.png")
                    ) as protection_image,
                    Image.open(
                        saved_raster(project / f"revisions/{prepared}/supports/lock_values16.png")
                    ) as values_image,
                ):
                    support = np.array(support_image)
                    protection = np.array(protection_image)
                    assert support[23, 27] == 65535 and support[9, 19] == 0
                    assert np.any((support > 0) & (support < 65535))
                    assert protection[20, 30] == 255 and np.count_nonzero(protection) == 1
                    assert np.array(values_image)[20, 30] == 32768
                page.locator("#reason").fill("Synthetic browser preservation check")
                page.locator("#policy").select_option("replace")
                c = submit(page, "#repair", "repair")["revision"]
                repaired_alpha = alpha(project, c)
                assert np.all(repaired_alpha[16:18, 24:26] == 0)
                assert repaired_alpha[20, 30] == 32768
                assert repaired_alpha[23, 27] == 65535
                outside_scope = np.ones((64, 96), dtype=bool)
                outside_scope[10:30, 20:40] = False
                np.testing.assert_array_equal(
                    repaired_alpha[outside_scope], initial_alpha[outside_scope]
                )
                np.testing.assert_array_equal(foreground(project, c), pixels)

                page.locator("#panel").select_option("result")
                ready(page)
                page.locator("#shadingWidth").fill("3")
                page.locator("#shadingDirection").fill("90")
                page.locator("#shadingOpacity").fill("0.12")
                page.locator("#shadingScope").fill("20,10,40,30")
                page.locator("#shadingCandidate").check()
                a = submit(page, "#shadingApply", "effects")["revision"]
                page.locator("#photoReviewed").check()  # Synthetic control test only.
                submit(page, "#accept", "accept")
                accepted = inventory(project / "revisions" / a)
                page.locator("#exportEditable").check()
                accepted_export = submit(page, "#exportAccepted", "export")
                accepted_files = inventory(Path(accepted_export["directory"]))
                page.locator("#shadingOpacity").fill("0.24")
                b = submit(page, "#shadingOpacityApply", "effects")["revision"]
                draft_export = submit(page, "#exportDraft", "export")
                for result, revision, opacity in (
                    (accepted_export, a, 0.12),
                    (draft_export, b, 0.24),
                ):
                    manifest = json.loads(Path(result["manifest_file"]).read_bytes())
                    assert manifest["revision"] == revision
                    revision_root = project / "revisions" / revision
                    with Image.open(saved_raster(revision_root / "shadow_weight16.png")) as image:
                        weight = np.array(image)
                    background = tifffile.imread(
                        saved_raster(revision_root / "background/background_rgb16.tif")
                    )
                    expected = np.rint(
                        pixels.astype(float)
                        * (repaired_alpha.astype(float) / 65535)[..., None]
                        * (1 - opacity * weight.astype(float) / 65535)[..., None]
                        + background.astype(float)
                        * (1 - repaired_alpha.astype(float) / 65535)[..., None]
                    ).astype(np.uint16)
                    assert np.any(weight > 0) and weight[20, 30] == 0
                    assert_editable_native(
                        Path(result["directory"]),
                        pixels,
                        repaired_alpha,
                        weight,
                        background,
                        expected,
                        expected_opacity=opacity,
                    )
                assert not np.array_equal(
                    tifffile.imread(Path(accepted_export["directory"]) / "result_rgb16.tif"),
                    tifffile.imread(Path(draft_export["directory"]) / "result_rgb16.tif"),
                )
                page.locator("#framingLeft").fill("2")
                page.locator("#framingRight").fill("3")
                submit(page, "#framingSave", "framing-save")
                page.locator("#restoreRevision").select_option(c)
                page.locator("#replaceDrafts").check()
                submit(page, "#restore", "restore")
                # Export accepted A while comparison and working point elsewhere.
                page.locator("#viewRevision").select_option(b)
                ready(page)
                assert submit(page, "#exportAccepted", "export")["revision"] == a
                state = read_project(project)
                assert (
                    state["working_revision"],
                    state["accepted_revision"],
                    state["latest_result_revision"],
                ) == (c, a, b)
                expect(page.locator("#previewStatus")).to_contain_text("latest " + b)
                expect(page.locator("#previewStatus")).to_contain_text("Draft")
                saved = inventory(project)
            assert server.process.poll() is not None
            first_pid = server.pid
            with running_process(project, config_file, tmp_path) as server:
                assert server.pid != first_pid
                with browser_session(playwright, server, tmp_path, "reopened", receipt) as page:
                    assert inventory(project) == saved
                    expect(page.locator("#status")).to_contain_text(f"working {c} · accepted {a}")
                    expect(page.locator("#previewStatus")).to_contain_text("latest " + b)
                    expect(page.locator("#framingLeft")).to_have_value("2")
                    expect(page.locator("#framingRight")).to_have_value("3")
                    with project_lock(project):
                        expect(page.locator("#status")).to_contain_text(
                            "Project busy · another writer"
                        )
                        expect(page.locator("#matte")).to_be_disabled()
                        expect(page.locator("#save")).to_be_disabled()
                        page.locator("#panel").select_option("source")
                        ready(page)
                        page.locator("#canvas").screenshot(path=str(tmp_path / "busy-source.png"))
                    expect(page.locator("#matte")).to_be_enabled()
                    # A genuine second browser page changes saved authoring while this page is dirty.
                    guide(page, "unknown", "42,12", shape="point")
                    other = page.context.new_page()
                    other.goto(server.origin + "/#" + server.token)
                    ready(other)
                    guide(other, "unknown", "44,14", shape="point")
                    submit(other, "#save", "save")
                    pending = inventory(project)
                    page.locator("#save").click()
                    expect(page.locator("#message")).to_contain_text(
                        "Stale master, revision or draft inputs_digest"
                    )
                    assert inventory(project) == pending
                    expect(page.locator("#draftStatus")).to_contain_text("Stale authoring identity")
                    expect(page.locator("#regions")).to_contain_text("[42,12]")
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.locator("#reload").click()
                    expect(page.locator("#draftStatus")).to_contain_text("Saved pending guides")
                    other.close()
                    # Restore B, author a new core/support, then repair makes shading stale.
                    page.locator("#restoreRevision").select_option(b)
                    page.locator("#replaceDrafts").check()
                    submit(page, "#restore", "restore")
                    guide(page, "background", "32,16,34,18")
                    submit(page, "#save", "save")
                    page.locator("#scope").fill("20,10,40,30")
                    page.locator("#context").fill("16,6,44,34")
                    submit(page, "#prepare", "prepare")
                    page.locator("#reason").fill("Synthetic offline stale-effect recovery")
                    submit(page, "#repair", "repair")
                    page.locator("#panel").select_option("result")
                    ready(page)
                    expect(page.locator("#shadingStatus")).to_contain_text("STALE")
                    submit(page, "#exportDraft", "export", error="Stale enabled")
                    submit(page, "#shadingDisable", "effects")
                    page.locator("#exportEditable").check()
                    recovered = submit(page, "#exportDraft", "export")
                    assert Path(recovered["manifest_file"]).is_file()
                    assert (
                        alpha(project, read_project(project)["working_revision"])[20, 30] == 32768
                    )
                    assert read_project(project)["accepted_revision"] == a
                    assert inventory(project / "revisions" / a) == accepted
                    assert inventory(Path(accepted_export["directory"])) == accepted_files
                    receipt.update(
                        revisions={
                            "working_before_recovery": c,
                            "accepted": a,
                            "latest_before_recovery": b,
                        },
                        recovered_export=recovered["manifest_file"],
                    )
            assert server.process.poll() is not None
        assert inventory(project.parent / "original") == originals
        final_assets = inventory(project / "assets")
        for name, value in source_assets.items():
            assert final_assets[name] == value
        receipt["completed"] = True
    finally:
        (tmp_path / "browser-receipt.json").write_text(json.dumps(receipt, indent=2))
