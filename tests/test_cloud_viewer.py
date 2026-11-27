import base64
import io
import json
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_background import legacy_project
from test_background_pattern_project import pattern_request
from test_cloud_project import cloud_request, cloud_settings
from test_fade_reduction import reduction_request
from test_mist_project import mist_request
from test_spatial_fade import spatial_request
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask import operations


def _row(snapshot, revision):
    return next(row for row in snapshot["revisions"] if row["revision"] == revision)


def _viewer_action(snapshot, request):
    return {
        **{key: value for key, value in request.items() if key not in {"schema_version", "kind"}},
        "action": "effects",
        "authoring_digest": snapshot["authoring_digest"],
        "revision_manifest_sha256": _row(snapshot, request["base_revision"])[
            "revision_manifest_sha256"
        ],
    }


def test_cloud_http_apply_compare_disable_restore_preserves_other_saved_effects(tmp_path):
    project, base = legacy_project(tmp_path)
    operations.apply_operation(project, pattern_request(project))
    operations.apply_operation(project, spatial_request(project, candidate=True))
    operations.apply_operation(project, reduction_request(project))
    mist = operations.apply_operation(project, mist_request(project))
    area = {
        "coverage": [
            {
                "id": "coverage",
                "role": "support",
                "shape": "rectangle",
                "xyxy": [0, 0, 6, 4],
                "feather_px": 0,
            }
        ],
        "clear": [],
        "focus": {"center_xy": [5.25, 1.5], "radii_xy": [0.5, 0.5]},
    }
    with running(project) as server:
        snapshot = server.snapshot()
        previous = _row(snapshot, mist["revision"])
        assert previous["cloud"] is None and previous["cloud_area"] is None
        assert http(server, "/api/experimental-cloud-preview", "POST", {})[0] == 404
        action = _viewer_action(
            snapshot, cloud_request(project, config=cloud_settings(tint_srgb="#5a6972"), area=area)
        )
        assert (
            http(server, "/api/action", "POST", dict(action, mist={"action": "disable"}))[0] == 400
        )
        assert (
            http(server, "/api/action", "POST", dict(action, revision_manifest_sha256="b" * 64))[0]
            == 202
        )
        with server.action_lock:
            assert "Stale raw revision" in server.action["error"]
        assert http(server, "/api/action", "POST", action)[0] == 202
        with server.action_lock:
            assert server.action["error"] is None, server.action
            applied = server.action["result"]
        current = server.snapshot()
        saved = _row(current, applied["revision"])
        assert saved["hard_protection_sha256"] == previous["hard_protection_sha256"]
        assert saved["cloud_area"] == area
        assert saved["cloud"]["settings"]["tint_srgb"] == "#5A6972"
        assert applied["cloud"] == saved["cloud"]
        assert applied["base_manifest_sha256"] == previous["revision_manifest_sha256"]
        assert applied["revision_manifest_sha256"] == saved["revision_manifest_sha256"]
        assert current["accepted_revision"] == base["revision"]

        def pixels(panel, identity, suffix=""):
            status, raw, _ = http(server, f"/image/{panel}/{identity}/0,0,6,4{suffix}")
            assert status == 200, raw
            with Image.open(io.BytesIO(raw)) as image:
                return np.array(image)

        cloud_result = pixels("result", applied["revision"])
        assert np.any(cloud_result != pixels("result", mist["revision"]))
        np.testing.assert_array_equal(
            pixels("result", applied["revision"], "/cloud-off"), pixels("result", mist["revision"])
        )
        assert np.any(cloud_result != pixels("result", applied["revision"], "/mist-off"))
        assert np.any(
            cloud_result != pixels("result", applied["revision"], "/background-pattern-off")
        )
        for panel in ("black", "gray", "white", "alpha"):
            np.testing.assert_array_equal(
                pixels(panel, applied["revision"]), pixels(panel, mist["revision"])
            )
        np.testing.assert_array_equal(
            pixels("source", current["developed_id"], "/cloud-off"),
            pixels("source", current["developed_id"]),
        )

        def fade_off(route, row, panel, **extra):
            status, raw, _ = http(
                server,
                route,
                "POST",
                {
                    "developed_id": current["developed_id"],
                    "revision": row["revision"],
                    "revision_manifest_sha256": row["revision_manifest_sha256"],
                    "crop_xyxy": [0, 0, 6, 4],
                    "view": "off",
                    "panel": panel,
                    **extra,
                },
            )
            assert status == 200, raw
            with Image.open(io.BytesIO(base64.b64decode(json.loads(raw)["png_base64"]))) as image:
                return np.array(image)

        for route, extra in (
            ("/api/spatial-preview", {}),
            ("/api/fade-reduction-preview", {"target": "spatial_fade"}),
        ):
            assert np.any(
                fade_off(route, saved, "result", **extra)
                != fade_off(route, previous, "result", **extra)
            )
            np.testing.assert_array_equal(
                fade_off(route, saved, "black", **extra),
                fade_off(route, previous, "black", **extra),
            )

        disable = _viewer_action(current, cloud_request(project, disable=True, candidate=False))
        assert http(server, "/api/action", "POST", disable)[0] == 202
        with server.action_lock:
            assert server.action["error"] is None, server.action
            disabled_id = server.action["result"]["revision"]
        disabled = _row(server.snapshot(), disabled_id)
        assert disabled["cloud"]["settings"] == dict(saved["cloud"]["settings"], enabled=False)
        assert disabled["cloud_area"] == area
        np.testing.assert_array_equal(
            pixels("result", disabled_id), pixels("result", mist["revision"])
        )

    operations.restore_revision(project, applied["revision"], replace_drafts=True)
    with running(project) as reopened:
        current = reopened.snapshot()
        assert current["working_revision"] == applied["revision"]
        assert current["accepted_revision"] == base["revision"]
        restored = _row(current, applied["revision"])
        assert restored["cloud"] == saved["cloud"]
        assert restored["cloud_area"] == area


@pytest.mark.parametrize("limit", ["shapes", "stroke points"])
def test_invalid_cloud_geometry_is_rejected_before_reading_native_pixels(tmp_path, limit):
    project, base = legacy_project(tmp_path)
    brush = {"id": "brush", "role": "support", "shape": "stroke", "radius_px": 1, "feather_px": 0}
    area = {
        "coverage": [dict(brush, id=f"brush-{index}", points=[[1, 1]]) for index in range(64)]
        if limit == "shapes"
        else [dict(brush, points=[[1, 1]] * 8192)],
        "clear": [dict(brush, id="clear", points=[[1, 1]])] if limit == "stroke points" else [],
        "focus": {"center_xy": [2, 2], "radii_xy": [1, 1]} if limit == "shapes" else None,
    }
    with running(project) as server:
        operation = _viewer_action(server.snapshot(), cloud_request(project, area=area))
        with patch(
            "blackmask.viewer.read_project", side_effect=AssertionError("Read native pixels")
        ):
            assert http(server, "/api/action", "POST", operation)[0] == 202
            with server.action_lock:
                assert limit in server.action["error"]
        assert server.snapshot()["working_revision"] == base["revision"]


CLOUD_PAGE = r"""
const paths = [], originalFetch = fetch;
const baseRow = servedState.revisions[0];
baseRow.hard_protection_sha256 = 'c'.repeat(64);
baseRow.mist = {settings:{enabled:true, density:.22, tint_srgb:'#8C9192', wisp_size:.22, stretch:2,
  rotation_degrees:25, seed:1, coverage:{center_xy:[50,50],radii_xy:[60,50],softness:.72}}};
baseRow.mist_area = {regions:[],protection:[]};
globalThis.fetch = async(path, options) => {
  if (path === '/api/action') servedState.action = {name:'effects', running:true, error:null, result:null};
  paths.push(path);
  return originalFetch(path.replace(/\/(cloud|mist)-off$/, ''), options);
};
const initialSettings = {enabled:false,tint_srgb:'#282828',amount:.22,size:.28,warp:.62,light_amount:.55,
  seed:13,center_xy:[60,62],radii_xy:[100,100]};
const rect = (id, xyxy = [3,4,15,16]) => ({id,xyxy,role:'support',shape:'rectangle',feather_px:0});
function advanceCloud(changes = {}) {
  const old = servedState.revisions.at(-1), number = servedState.revisions.length + 1;
  const row = {...structuredClone(old), revision:'rev-' + String(number).padStart(3,'0'),
    revision_manifest_sha256:String(number).repeat(64), ...changes};
  servedState.revisions.push(row); servedState.working_revision = row.revision;
  return row;
}
function completeCloud(payload, base) {
  const cloud = payload.action === 'disable'
    ? {...base.cloud, settings:{...base.cloud.settings, enabled:false}}
    : {settings:payload.settings, area_sha256:'area' + base.revision};
  const row = advanceCloud({cloud, cloud_area:payload.area || base.cloud_area});
  servedState.action = {name:'effects', running:false, error:null, result:{revision:row.revision, parent:base.revision,
    developed_id:servedState.developed_id, cloud, base_manifest_sha256:base.revision_manifest_sha256,
    revision_manifest_sha256:row.revision_manifest_sha256}};
  return row;
}
function edit(id, value) {
  if (typeof value === 'boolean') $(id).checked = value;
  else $(id).value = String(value);
  $(id).oninput();
}
function pointer(point) {
  const [clientX,clientY] = nativeToScreen(point,canvas.getBoundingClientRect(),[canvas.width,canvas.height],transform,crop);
  return {clientX, clientY, pointerId:1};
}
async function view(row) {
  $('viewRevision').value=row.revision; await $('viewRevision').onchange();
}
"""


def test_page_cloud_colour_and_geometry_round_trip_with_independent_mist_and_comparison():
    run_page(
        CLOUD_PAGE
        + r"""
await ready();
assert.deepEqual(cloudFormSettings(), initialSettings);
assert.equal($('cloudCharcoal').ariaPressed,'true');
edit('mistDensity', 33);
edit('cloudHex','#aBcDe');
assert.equal($('cloudHex').value,'#aBcDe');
assert.equal($('cloudHex').ariaInvalid,'true');
assert.equal($('cloudApply').disabled,true);
assert.match($('cloudValidation').textContent,/six-digit #RRGGBB/);
assert.equal($('cloudColor').value,'#282828');
$('cloudBlack').click();
assert.equal($('cloudValidation').textContent,'');
assert.equal($('cloudBlackHelp').hidden,false);
assert.deepEqual(cloudFormSettings(), {...initialSettings,tint_srgb:'#000000'});
edit('cloudHex','  #aBcDeF ');
assert.equal($('cloudColor').value,'#abcdef');
assert.equal($('cloudBlack').ariaPressed,'false');
edit('cloudColor','#20242a');
assert.equal($('cloudHex').value,'#20242A');
assert.equal($('cloudCoolCharcoal').ariaPressed,'true');
edit('cloudEnabled',true); edit('cloudAmount',34.125); edit('cloudSize',29.25);
edit('cloudWarp',50); edit('cloudLight',31.25); edit('cloudSeed',4294967295);
await $('cloudNextPattern').onclick();
edit('cloudRadiusX',77.125); edit('cloudRadiusY',56.25);
edit('cloudCenterX',20.25); edit('cloudCenterY',21.25);
assert.deepEqual(cloudFormSettings().center_xy,[20.25,21.25]);
await $('cloudPlaceCentre').onclick();
canvas.onpointerdown(pointer([25.5, 35.5]));
assert.deepEqual(cloudFormSettings().center_xy,[25.5,35.5]);
await $('cloudDrawFocus').onclick();
canvas.onpointerdown(pointer([20,30])); canvas.onpointerup(pointer([30,50]));
assert.equal($('cloudFocusEnabled').checked,true);
assert.deepEqual(cloudFormArea().focus,{center_xy:[25,40],radii_xy:[5,10]});
edit('cloudFocusRadiusX',5.75);
$('cloudAreaRole').value='coverage'; $('cloudRectangle').value='4,8,20,24';
await $('cloudAddRectangle').onclick();
$('cloudShape').value='stroke'; $('cloudAreaRole').value='clear';
await $('cloudDrawShape').onclick();
canvas.onpointerdown(pointer([7.25,9.25])); canvas.onpointermove(pointer([7.75,9.75]));
canvas.onpointermove(pointer([8.25,10.25])); canvas.onpointerup(pointer([9.25,11.25]));
$('cloudStroke').value='13,17 14,18'; await $('cloudAddStroke').onclick();
$('cloudAreaRole').value='coverage'; $('cloudShape').value='rectangle';
await $('cloudDrawShape').onclick();
canvas.onpointerdown(pointer([31.5,41.5])); canvas.onpointerup(pointer([40.75,50.75]));
assert.equal(posts.length,0);
assert.equal(typeof paths.find(path => path.endsWith('/cloud-off')),'undefined');
assert.match($('cloudDraftStatus').textContent,/Unapplied changes/);
await $('cloudApply').onclick();
const post = posts.at(-1);
assert.deepEqual(post.scope_xyxy,[0,0,100,100]);
assert.equal(post.base_revision,baseRow.revision);
assert.equal(post.revision_manifest_sha256,baseRow.revision_manifest_sha256);
assert.equal(post.inputs_digest,servedState.inputs_digest);
assert.equal(post.authoring_digest,servedState.authoring_digest);
assert.deepEqual(post.cloud.settings,{enabled:true,tint_srgb:'#20242A',amount:.34125,size:.2925,warp:.5,
  light_amount:.3125,seed:0,center_xy:[25.5,35.5],radii_xy:[77.125,56.25]});
assert.deepEqual(post.cloud.area.focus,{center_xy:[25,40],radii_xy:[5.75,10]});
assert.deepEqual(post.cloud.area.coverage.map(shape=>shape.xyxy),[[4,8,20,24],[31,41,41,51]]);
assert.deepEqual(post.cloud.area.clear.map(shape=>shape.points),[[[7,9],[8,10],[9,11]],[[13,17],[14,18]]]);
assert.equal($('cloudApply').disabled,true);
await $('cloudApply').onclick();
assert.equal(posts.length,1,'Duplicate submission reached the API');
const on = completeCloud(post.cloud,baseRow); await refresh();
assert.deepEqual(cloudFormSettings(),post.cloud.settings);
assert.deepEqual(cloudFormArea(),post.cloud.area);
assert.equal($('cloudDraftStatus').textContent,'');
assert.equal($('mistDensity').value,'33');
assert.match($('mistDraftStatus').textContent,/Unapplied changes/);
$('mistCompare').checked=true; await $('mistCompare').onchange();
assert.ok(paths.at(-1).endsWith('/mist-off'));
edit('cloudHex','#12');
$('cloudCompare').checked=true; await $('cloudCompare').onchange();
assert.equal($('mistCompare').checked,false);
assert.ok(paths.at(-1).endsWith('/cloud-off'));
assert.equal($('cloudHex').value,'#12');
assert.equal($('cloudDisable').disabled,false);
await $('cloudDisable').onclick();
assert.deepEqual(posts.at(-1).cloud,{action:'disable'});
assert.equal(posts.at(-1).candidate_comparison,false);
completeCloud(posts.at(-1).cloud,on); await refresh();
assert.match($('cloudSavedStatus').textContent,/Saved Cloud OFF/);
assert.equal($('cloudHex').value,'#12');
assert.equal($('cloudFocusRadiusX').value,'5.75');
assert.doesNotMatch($('cloudDraftStatus').textContent,/Stale/);
globalThis.confirm=()=>false; await $('cloudReload').onclick();
assert.equal($('cloudHex').value,'#12');
globalThis.confirm=()=>true; await $('cloudReload').onclick();
assert.deepEqual(cloudFormSettings(), {...post.cloud.settings,enabled:false});
assert.deepEqual(cloudFormArea(),post.cloud.area);
assert.equal($('cloudCompare').checked,false);
"""
    )


def test_page_cloud_retains_newer_edits_and_rebinds_only_compatible_current_views():
    run_page(
        CLOUD_PAGE
        + r"""
await ready();
edit('cloudAmount',48); edit('cloudEnabled',true);
await $('cloudApply').onclick();
const sent = posts.at(-1).cloud;
assert.equal($('cloudAmount').disabled,false);
edit('cloudAmount',72);
const saved = completeCloud(sent, baseRow); await refresh();
assert.equal($('cloudAmount').value,'72');
assert.equal(saved.cloud.settings.amount,.48);
assert.match($('cloudDraftStatus').textContent,/Unapplied changes/);
assert.doesNotMatch($('cloudDraftStatus').textContent,/Stale/);
await view(baseRow);
assert.match($('cloudSavedStatus').textContent,/Historical view/);
assert.equal($('cloudAmount').disabled,true);
assert.equal($('cloudApply').disabled,true);
await $('cloudApply').onclick();
assert.equal(posts.length,1);
await view(saved);
const compatible = advanceCloud(); await refresh(); await view(compatible);
assert.match($('cloudDraftStatus').textContent,/Stale/);
assert.equal($('cloudRebind').disabled,false);
await $('cloudRebind').onclick();
assert.equal($('cloudAmount').value,'72');
assert.equal($('cloudApply').disabled,true);
$('cloudCandidate').checked=true; $('cloudCandidate').onchange();
assert.equal($('cloudApply').disabled,false);
const differentProtection = advanceCloud({hard_protection_sha256:'d'.repeat(64)});
await refresh(); await view(differentProtection);
assert.equal($('cloudRebind').disabled,true);
assert.equal($('cloudApply').disabled,true);
assert.equal($('cloudAmount').value,'72');
await $('cloudDisable').onclick();
completeCloud(posts.at(-1).cloud,differentProtection); await refresh();
assert.match($('cloudDraftStatus').textContent,/Stale/);
assert.equal($('cloudAmount').value,'72');
await $('cloudReload').onclick();
assert.deepEqual(cloudFormSettings(), {...sent.settings,enabled:false});
"""
    )


def test_page_cloud_area_rejects_excess_combined_shapes_and_points_without_mutating_draft():
    run_page(
        CLOUD_PAGE
        + r"""
baseRow.cloud = {settings:initialSettings,area_sha256:'area'};
baseRow.cloud_area = {coverage:Array.from({length:63},(_,index)=>rect('r' + index)),clear:[],focus:null};
await ready();
edit('cloudFocusEnabled',true);
$('cloudAreaRole').value='clear'; $('cloudRectangle').value='3,4,15,16';
await $('cloudAddRectangle').onclick();
assert.match($('message').textContent,/64 combined shapes/);
assert.equal($('cloudRegions').options.length,63);
edit('cloudFocusEnabled',false);
$('cloudRectangle').value=',4,15,16'; await $('cloudAddRectangle').onclick();
assert.match($('message').textContent,/four native integer coordinates/);
assert.equal($('cloudRegions').options.length,63);
$('cloudRectangle').value='3,4,15,16';
await $('cloudAddRectangle').onclick();
assert.equal($('cloudRegions').options.length,64);
await $('cloudRemove').onclick();
$('cloudStroke').value=Array(8193).fill('7,8').join(' ');
await $('cloudAddStroke').onclick();
assert.match($('message').textContent,/8192 stroke points/);
assert.equal($('cloudRegions').options.length,63);
assert.equal(posts.length,0);
"""
    )
