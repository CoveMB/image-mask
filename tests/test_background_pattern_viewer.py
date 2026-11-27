import base64
import io
import json
from http.client import HTTPConnection

import numpy as np
import pytest
from PIL import Image
from test_background_pattern import wave
from test_background_pattern_project import pattern_request, target_settings
from test_cloud_project import cloud_request
from test_spatial_fade_target import lit_project
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask import operations, viewer


def png_pixels(payload):
    with Image.open(io.BytesIO(payload)) as image:
        return np.asarray(image).copy()


@pytest.mark.parametrize("style, shape_count", [("mixed", 3), ("abstract", 1)])
def test_pattern_generate_preview_and_saved_comparison(tmp_path, style, shape_count):
    project, _, _, lit, _ = lit_project(tmp_path)
    before = {path: path.read_bytes() for path in project.rglob("*") if path.is_file()}
    with running(project) as server:
        snapshot = server.snapshot()
        row = next(row for row in snapshot["revisions"] if row["revision"] == lit["revision"])
        binding = {
            "developed_id": snapshot["developed_id"],
            "revision": lit["revision"],
            "inputs_digest": snapshot["inputs_digest"],
            "revision_manifest_sha256": row["revision_manifest_sha256"],
        }
        generate_route = "/api/background-pattern-generate"
        preview_route = "/api/background-pattern-preview"
        generation = dict(binding, style=style, seed=None)
        status, payload, _ = http(server, generate_route, "POST", generation)
        assert status == 200, payload
        proposal = json.loads(payload)
        assert {key: proposal[key] for key in binding} == binding
        assert proposal["version"] == 1 and len(proposal["shapes"]) == shape_count
        assert (
            http(server, generate_route, "POST", dict(generation, seed=proposal["seed"]))[1]
            == payload
        )
        assert (
            http(server, generate_route, "POST", generation, **{"X-Blackmask-Token": ""})[0] == 403
        )
        assert (
            http(server, generate_route, "POST", generation, **{"Content-Length": "2000001"})[0]
            == 413
        )
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request(
            "POST",
            generate_route,
            json.dumps(generation)[:-1] + ', "seed": 0}',
            {
                "X-Blackmask-Token": server.token,
                "Origin": server.origin,
                "Content-Type": "application/json",
            },
        )
        assert connection.getresponse().status == 400
        connection.close()
        settings = target_settings()
        if style == "abstract":
            next_seed = (proposal["seed"] + 1) % 2**32
            status, payload, _ = http(
                server, generate_route, "POST", dict(generation, seed=next_seed)
            )
            assert status == 200, payload
            next_proposal = json.loads(payload)
            assert next_proposal["seed"] == next_seed
            assert next_proposal["shapes"] != proposal["shapes"]
            assert next_proposal["shapes"][0]["type"] == "contour"
            settings = target_settings(
                irregularity=0.625,
                shapes=[*next_proposal["shapes"], wave(center_xy=[3, 2])],
                generator={"version": 1, "style": style, "seed": next_seed},
            )
        crop = [1, 0, 6, 4]
        preview_request = dict(binding, crop_xyxy=crop, background_pattern=settings)
        status, payload, _ = http(server, preview_route, "POST", preview_request)
        assert status == 200, payload
        preview = json.loads(payload)
        assert preview["crop_xyxy"] == crop and preview["display_dimensions_wh"] == [5, 4]
        assert {key: preview[key] for key in binding} == binding
        assert (
            http(server, preview_route, "POST", dict(preview_request, crop_xyxy=[-1, 0, 6, 4]))[0]
            == 400
        )
        assert (
            http(
                server,
                preview_route,
                "POST",
                dict(preview_request, revision_manifest_sha256="b" * 64),
            )[0]
            == 409
        )
        assert {path: path.read_bytes() for path in project.rglob("*") if path.is_file()} == before

        operation = pattern_request(project, settings)
        operation.pop("kind")
        operation.pop("schema_version")
        operation.update(
            action="effects",
            authoring_digest=snapshot["authoring_digest"],
            revision_manifest_sha256=binding["revision_manifest_sha256"],
        )
        assert (
            http(server, "/api/action", "POST", dict(operation, candidate_comparison=False))[0]
            == 202
        )
        with server.action_lock:
            assert server.action["error"] and "candidate" in server.action["error"].lower()
        assert http(server, "/api/action", "POST", operation)[0] == 202
        with server.action_lock:
            assert server.action["error"] is None, server.action
            result = server.action["result"]
        assert result["base_manifest_sha256"] == binding["revision_manifest_sha256"]
        row = next(
            row for row in server.snapshot()["revisions"] if row["revision"] == result["revision"]
        )
        assert row["revision_manifest_sha256"] == result["revision_manifest_sha256"]
        assert row["background_pattern"]["settings_sha256"] == preview["settings_sha256"]
        assert row["background_pattern"]["settings"] == settings
        url = f"/image/result/{result['revision']}/1,0,6,4"
        status, pixels, _ = http(server, url)
        assert status == 200
        np.testing.assert_array_equal(
            png_pixels(base64.b64decode(preview["png_base64"])), png_pixels(pixels)
        )
        baseline = http(server, f"/image/result/{lit['revision']}/1,0,6,4")[1]
        assert http(server, url + "/background-pattern-off")[1] == baseline
        assert http(server, generate_route, "POST", generation)[0] == 409


def test_pattern_preview_checks_native_allocation_before_render(tmp_path, monkeypatch):
    project, _, _, lit, _ = lit_project(tmp_path)
    native_wh = (8000, 5000)
    rendered = []
    with running(project) as server:
        binding = {"revision": lit["revision"]}
        monkeypatch.setattr(
            server, "_pattern_target", lambda data, fields: (binding, native_wh, {})
        )

        def render(path, **options):
            rendered.append(path)
            return b"preview"

        monkeypatch.setattr(server, "_image_png", render)
        route = "/api/background-pattern-preview"
        request = dict(binding, background_pattern=target_settings(), crop_xyxy=[0, 0, *native_wh])
        status, payload, _ = http(server, route, "POST", request)
        assert status == 400, payload
        assert "smaller crop" in json.loads(payload)["error"]
        assert rendered == []
        status, _, _ = http(server, route, "POST", dict(request, crop_xyxy=[0, 0, 512, 512]))
        assert status == 200
        assert rendered == [f"/image/result/{lit['revision']}/0,0,512,512"]


def test_pattern_preview_budget_includes_visible_saved_cloud(tmp_path, monkeypatch):
    project, _, _, _, _ = lit_project(tmp_path)
    monkeypatch.setattr(viewer, "_PATTERN_PREVIEW_MAX_BYTES", 16 * 1024**2 + 12 * 1024)
    with running(project) as server:

        def preview():
            snapshot = server.snapshot()
            revision = snapshot["working_revision"]
            row = next(row for row in snapshot["revisions"] if row["revision"] == revision)
            return http(
                server,
                "/api/background-pattern-preview",
                "POST",
                {
                    "developed_id": snapshot["developed_id"],
                    "revision": revision,
                    "inputs_digest": snapshot["inputs_digest"],
                    "revision_manifest_sha256": row["revision_manifest_sha256"],
                    "crop_xyxy": [0, 0, 6, 4],
                    "background_pattern": target_settings(),
                },
            )

        assert preview()[0] == 200
        operations.apply_operation(project, cloud_request(project))
        status, payload, _ = preview()
        assert status == 400, payload
        assert "smaller crop" in json.loads(payload)["error"]

        operations.apply_operation(project, cloud_request(project, disable=True))
        assert preview()[0] == 200


PATTERN_PAGE = r"""
function change(id, value) {
  const control = $(id);
  control.value = value;
  control.oninput();
}
const previousFetch = fetch;
let deferGeneration = false, lateGeneration;
let latePreview;
globalThis.fetch = async (path, options) => {
  if (path === '/api/background-pattern-generate') {
    const request = JSON.parse(options.body);
    const response = {ok:true, json:async()=>({
      ...request, version:1, seed:request.seed ?? 5,
      shapes:request.style === 'abstract' ? [
        {id:'abstract-contours',type:'contour',enabled:true,center_xy:[41,57],rotation_degrees:20,
         radii_xy:[80,82],softness:.72,seed:request.seed ?? 5}
      ] : [{id:'lower-wave',type:'wave',enabled:true,center_xy:[25,72+(request.seed ?? 5)],
               rotation_degrees:5,bend_px:8,wavelength_px:90,phase_degrees:1,
               spacing_px:9,band_count:3,feather_px:4,first_tone:'tone1'}],
    })};
    if (deferGeneration) return new Promise(resolve => {lateGeneration = () => resolve(response);});
    return response;
  }
  if (path === '/api/background-pattern-preview') {
    const request = JSON.parse(options.body);
    return new Promise(resolve => {latePreview = () => resolve({ok:true, json:async()=>({
      ...request, png_base64:'AAAA', label:'Temporary pattern view',
    })});});
  }
  if (path === '/api/action') servedState.action = {name:'effects', running:true, error:null, result:null};
  return previousFetch(path, options);
};
"""


def test_page_pattern_edits_generate_cancel_and_apply():
    run_page(
        PATTERN_PAGE
        + r"""
await ready();
assert.equal(patternDraft.settings.strength, .28);
await $('patternAddWave').onclick();
change('patternCenterX', '11.125');
assert.equal(patternDraft.settings.shapes[0].center_xy[0], 11.125);
await $('patternAddOval').onclick();
change('patternStrength', '23.625');
change('patternTone1', '#090a0b');
change('patternTone2', '#213141');
$('patternReverse').checked = true;
$('patternReverse').oninput();
const original = structuredClone(patternDraft.settings);
$('patternStyle').value = 'mixed';
await $('patternGenerate').onclick();
const proposal = structuredClone(patternProposal);
await $('patternNext').onclick();
assert.equal(patternProposal.seed, (proposal.seed + 1) >>> 0);
await $('patternCancel').onclick();
assert.deepEqual(patternDraft.settings, original);
await $('patternGenerate').onclick();
await $('patternUse').onclick();
assert.deepEqual(patternDraft.settings.shapes, proposal.shapes);
assert.deepEqual(patternDraft.settings.tones_srgb, ['#090A0B','#213141']);
assert.equal(patternDraft.settings.generator.seed, proposal.seed);
$('patternEnabled').checked = true;
$('patternEnabled').oninput();
await $('patternApply').onclick();
assert.deepEqual(posts.at(-1).background_pattern, patternDraft.settings);
assert.equal(posts.at(-1).revision_manifest_sha256, 'a'.repeat(64));
const submitted = posts.at(-1).background_pattern;
const row = {...servedState.revisions[0], revision:'rev-002', revision_manifest_sha256:'b'.repeat(64),
  background_pattern:{settings:submitted}};
change('patternCenterX', '32.125');
servedState.revisions.push(row);
servedState.working_revision = row.revision;
servedState.action = {name:'effects', running:false, error:null, result:{revision:row.revision,
  revision_manifest_sha256:row.revision_manifest_sha256, parent:'rev-001',
  base_manifest_sha256:'a'.repeat(64), developed_id:servedState.developed_id,
  background_pattern:row.background_pattern}};
await refresh();
assert.equal(patternDraft.settings.shapes[0].center_xy[0], 32.125);
assert.match($('patternStatus').textContent, /stale/i);
"""
    )


def test_page_pattern_late_generation_cannot_replace_newer_draft():
    run_page(
        PATTERN_PAGE
        + r"""
await ready();
await $('patternAddOval').onclick();
$('patternStyle').value = 'abstract';
deferGeneration = true;
const pending = $('patternGenerate').onclick();
change('patternCenterX', '12.125');
lateGeneration();
await pending;
assert.equal(patternProposal, null);
assert.equal(patternDraft.settings.shapes[0].center_xy[0], 12.125);
const next = $('patternGenerate').onclick();
const newRow = {...servedState.revisions[0], revision:'rev-002', revision_manifest_sha256:'b'.repeat(64)};
servedState.working_revision = newRow.revision;
servedState.revisions.push(newRow);
await refresh();
lateGeneration();
await next;
assert.equal(patternProposal, null);
assert.match($('patternStatus').textContent, /stale/i);
await $('patternReload').onclick();
assert.equal(patternDraft.settings.shapes.length, 0);
"""
    )


def test_page_pattern_preview_and_saved_only_off_preserve_newer_edits():
    run_page(
        PATTERN_PAGE
        + r"""
await ready();
await $('patternAddOval').onclick();
change('patternIrregularity', '37.5');
$('patternEnabled').checked = true;
$('patternEnabled').oninput();
const base = servedState.revisions[0];
base.background_pattern = {settings:structuredClone(patternDraft.settings)};
await refresh(true);
const preview = $('patternPreview').onclick();
change('patternIrregularity', '74.25');
latePreview();
await preview;
assert.equal($('patternPreviewPanel').hidden, true);
const pending = structuredClone(patternDraft.settings);
await $('patternOff').onclick();
assert.deepEqual(posts.at(-1).background_pattern, {...base.background_pattern.settings, enabled:false});
const row = {...base, revision:'rev-002', revision_manifest_sha256:'b'.repeat(64),
  background_pattern:{settings:posts.at(-1).background_pattern}};
servedState.revisions.push(row);
servedState.working_revision = row.revision;
servedState.action = {name:'effects', running:false, error:null, result:{revision:row.revision,
  revision_manifest_sha256:row.revision_manifest_sha256, parent:base.revision,
  base_manifest_sha256:base.revision_manifest_sha256, developed_id:servedState.developed_id,
  background_pattern:row.background_pattern}};
await refresh();
assert.deepEqual(patternDraft.settings, pending);
assert.match($('patternStatus').textContent, /stale/i);
await $('patternReload').onclick();
assert.deepEqual(patternDraft.settings, row.background_pattern.settings);
"""
    )


def test_page_irregularity_and_abstract_geometry_share_the_pattern_draft():
    run_page(
        PATTERN_PAGE
        + r"""
await ready();
assert.equal($('patternIrregularity').value, '0');
await $('patternAddWave').onclick();
change('patternIrregularity', '62.5');
assert.equal(patternDraft.settings.irregularity, .625);
assert.equal($('patternIrregularityRange').value, '62.5');
const original = structuredClone(patternDraft.settings);
$('patternStyle').value = 'abstract';
await $('patternGenerate').onclick();
await $('patternNext').onclick();
assert.equal(patternProposal.seed, 6);
await $('patternCancel').onclick();
assert.deepEqual(patternDraft.settings, original);
await $('patternGenerate').onclick();
await $('patternNext').onclick();
await $('patternUse').onclick();
assert.equal(patternDraft.settings.generator.seed, 6);
assert.equal(patternDraft.settings.shapes[0].type, 'contour');
assert.equal(patternDraft.settings.irregularity, .625);
assert.equal($('patternOval').hidden, false);
assert.equal($('patternShapeToneControl').hidden, true);
change('patternRadiusX', '74.125');
change('patternSoftness', '0.68');
assert.equal(patternDraft.settings.shapes[0].radii_xy[0], 74.125);
assert.equal(patternDraft.settings.shapes[0].softness, .68);
change('patternIrregularity', '101');
await $('patternApply').onclick();
assert.match($('message').textContent, /irregularity/i);
assert.equal(posts.length, 0);
change('patternIrregularityRange', '0');
assert.equal($('patternIrregularity').value, '0');
assert.equal(Object.hasOwn(patternDraft.settings, 'irregularity'), false);
await $('patternApply').onclick();
assert.deepEqual(posts.at(-1).background_pattern, patternDraft.settings);
"""
    )


def test_page_disables_pattern_authoring_for_stale_enabled_effects():
    run_page(
        PATTERN_PAGE
        + r"""
await ready();
await $('patternAddOval').onclick();
const current = servedState.revisions[0];
current.local_texture = {enabled:true, stale:true};
await refresh();
const controls = ['patternGenerate', 'patternPreview', 'patternApply'];
for (const id of controls) assert.equal($(id).disabled, true, id);
assert.match($('patternStatus').textContent, /rebuild or disable.*stale/i);
const originalFetch = fetch, patternRequests = [];
globalThis.fetch = (path, options) => {
  if (path.startsWith('/api/background-pattern-') || path === '/api/action') {
    patternRequests.push(path);
    throw Error('Unexpected authoring request');
  }
  return originalFetch(path, options);
};
for (const id of controls) await $(id).onclick();
assert.deepEqual(patternRequests, []);
current.local_texture.enabled = false;
await refresh();
for (const id of controls) assert.equal($(id).disabled, false, id);
"""
    )


def test_page_pattern_rotation_handle_tracks_pixel_centres_at_high_zoom():
    run_page(
        PATTERN_PAGE
        + r"""
await ready();
await $('patternAddOval').onclick();
change('patternCenterX', '42');
change('patternCenterY', '50');
servedState.revisions[0].background_pattern = {settings:structuredClone(patternDraft.settings)};
await refresh(true);
$('authorMode').value = 'background-pattern';
zoom = 8;
draw();
assert.equal(transform.scale, 16);
const shape = currentPatternShape();
const radius = Math.hypot(...state.dimensions_wh) * .09;
const rect = canvas.getBoundingClientRect();
function pointer(x, y) {
  const [clientX, clientY] = nativeToScreen([x + .5, y + .5], rect,
    [canvas.width, canvas.height], transform, crop);
  return {clientX, clientY, pointerId:1};
}
canvas.onpointerdown(pointer(42 + radius, 50));
assert.equal(gesture?.patternRotation, shape.id);
canvas.onpointermove(pointer(42, 52));
canvas.onpointerup(pointer(42, 52));
assert.deepEqual(shape.center_xy, [42, 50]);
assert.equal(shape.rotation_degrees, 90);
canvas.onpointerdown(pointer(49.25, 51.125));
assert.deepEqual(shape.center_xy, [49.25, 51.125]);
await $('patternReload').onclick();
canvas.onpointerdown(pointer(42 + radius, 50));
assert.equal(gesture?.patternRotation, shape.id);
await $('patternReload').onclick();
canvas.onpointermove(pointer(42, 52));
assert.equal(currentPatternShape().rotation_degrees, 0);
assert.equal(patternDraft.dirty, false);
"""
    )
