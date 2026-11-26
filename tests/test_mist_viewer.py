import base64
import io
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from test_background import legacy_project
from test_effects import effect_request, fixture_project
from test_mist_project import mist_request
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask import operations
from blackmask.export import render_saved_result
from blackmask.project import read_project
from blackmask.review import review_project


def test_mist_only_saved_comparison_has_matching_result_and_independent_native_inventories(
    tmp_path,
):
    project, base = legacy_project(tmp_path)
    with running(project) as server:
        before = server.snapshot()
        row = next(item for item in before["revisions"] if item["revision"] == base["revision"])
        assert row["hard_protection_sha256"] and row["mist"] is None
        operation = mist_request(project)
        operation.pop("kind")
        operation.pop("schema_version")
        operation.update(
            action="effects",
            authoring_digest=before["authoring_digest"],
            revision_manifest_sha256=row["revision_manifest_sha256"],
        )
        assert (
            http(server, "/api/action", "POST", dict(operation, revision_manifest_sha256="b" * 64))[
                0
            ]
            == 202
        )
        with server.action_lock:
            assert "Stale raw revision" in server.action["error"]
        assert http(server, "/api/action", "POST", operation)[0] == 202
        with server.action_lock:
            assert server.action["error"] is None, server.action
            response = server.action["result"]
            revision = response["revision"]
        after = server.snapshot()
        saved = next(item for item in after["revisions"] if item["revision"] == revision)
        assert saved["mist_area"] == operation["mist"]["clear_area"]
        assert response["base_manifest_sha256"] == row["revision_manifest_sha256"]
        assert response["revision_manifest_sha256"] == saved["revision_manifest_sha256"]

        def pixels(panel, revision, suffix=""):
            status, png, _ = http(server, f"/image/{panel}/{revision}/0,0,6,4{suffix}")
            assert status == 200
            with Image.open(io.BytesIO(png)) as image:
                return np.array(image)

        expected = np.rint(
            render_saved_result(project, revision, base["developed_id"]).astype(float) / 257
        ).astype(np.uint8)
        np.testing.assert_array_equal(expected, pixels("result", revision))
        np.testing.assert_array_equal(
            pixels("result", revision, "/mist-off"), pixels("result", base["revision"])
        )
        for panel in ("black", "gray", "white", "alpha"):
            np.testing.assert_array_equal(pixels(panel, revision), pixels(panel, base["revision"]))

    receipt = review_project(project, comparison=True, retain_native=True)
    record = json.loads(Path(receipt["comparison_manifest_file"]).read_bytes())
    assert record["panel_order"][-1] == "result"
    for role in ("review", "review-before"):
        staged = json.loads(
            (project / "revisions" / revision / role / "manifest.json").read_bytes()
        )
        assert staged["panel_order"][-1] == "result"
    before_evidence = json.loads(
        (project / record["native_evidence"]["before"]["manifest_file"]).read_bytes()
    )
    after_evidence = json.loads(
        (project / record["native_evidence"]["after"]["manifest_file"]).read_bytes()
    )
    assert "result" not in before_evidence["panel_order"]
    assert after_evidence["panel_order"][-1] == "result"
    assert read_project(project)["accepted_revision"] == base["revision"]


def test_dedicated_fade_and_reduction_off_routes_keep_mist_on_result(tmp_path):
    from test_fade_reduction import reduction_request
    from test_spatial_fade import spatial_request

    project, _ = legacy_project(tmp_path)
    operations.apply_operation(project, spatial_request(project))
    reduced = operations.apply_operation(project, reduction_request(project))
    mist = operations.apply_operation(project, mist_request(project))
    with running(project) as server:
        state = server.snapshot()

        def pixels(route, revision, panel, **extra):
            selected = next(row for row in state["revisions"] if row["revision"] == revision)
            status, raw, _ = http(
                server,
                route,
                "POST",
                {
                    "developed_id": state["developed_id"],
                    "revision": revision,
                    "revision_manifest_sha256": selected["revision_manifest_sha256"],
                    "crop_xyxy": [0, 0, 6, 4],
                    "view": "off",
                    "panel": panel,
                    **extra,
                },
            )
            assert status == 200, raw
            with Image.open(io.BytesIO(base64.b64decode(json.loads(raw)["png_base64"]))) as image:
                return np.array(image)

        for route, options in (
            ("/api/spatial-preview", {}),
            ("/api/fade-reduction-preview", {"target": "spatial_fade"}),
        ):
            previous, current = reduced["revision"], mist["revision"]
            assert np.any(
                pixels(route, previous, "result", **options)
                != pixels(route, current, "result", **options)
            )
            np.testing.assert_array_equal(
                pixels(route, previous, "black", **options),
                pixels(route, current, "black", **options),
            )


def test_legacy_effects_comparison_ignores_unproven_reuse_provenance(tmp_path):
    project, _, _ = fixture_project(tmp_path)
    result = operations.apply_operation(project, effect_request(project))
    directory = project / "revisions" / result["revision"]
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest_path.write_text(json.dumps(dict(manifest, effects_reuse=None)))
    receipt = review_project(project, comparison=True, retain_native=True)
    comparison = json.loads(Path(receipt["comparison_manifest_file"]).read_bytes())
    assert comparison["native_evidence"]["before"] is None


@pytest.mark.parametrize("count,rule", [(65, "64 shapes"), (8193, "8192 stroke points")])
def test_viewer_refuses_oversized_clear_area_before_opening_native_pixels(tmp_path, count, rule):
    project, base = legacy_project(tmp_path)
    stroke = {
        "id": "brush",
        "role": "support",
        "shape": "stroke",
        "points": [[1, 1]],
        "radius_px": 1,
        "feather_px": 1,
    }
    regions = [stroke] * count if count == 65 else [dict(stroke, points=[[1, 1]] * count)]
    with running(project) as server:
        snapshot = server.snapshot()
        row = next(item for item in snapshot["revisions"] if item["revision"] == base["revision"])
        operation = mist_request(project, area={"regions": regions, "protection": []})
        operation.pop("kind")
        operation.pop("schema_version")
        operation.update(
            action="effects",
            authoring_digest=snapshot["authoring_digest"],
            revision_manifest_sha256=row["revision_manifest_sha256"],
        )
        with patch(
            "blackmask.viewer.read_project", side_effect=AssertionError("Loaded native pixels")
        ):
            assert http(server, "/api/action", "POST", operation)[0] == 202
            with server.action_lock:
                assert rule in server.action["error"]
    assert read_project(project)["working_revision"] == base["revision"]


MIST_PAGE = r"""
const baseRow = servedState.revisions[0];
baseRow.hard_protection_sha256 = 'c'.repeat(64);
const paths = [], originalFetch = fetch;
globalThis.fetch = async(path, options) => {
  if (path === '/api/action') servedState.action = {name:'effects', running:true, error:null, result:null};
  paths.push(path);
  return originalFetch(path.replace(/\/mist-off$/, ''), options);
};
function advanceMist(extra = {}) {
  const old = servedState.revisions.at(-1);
  const revision = 'rev-' + String(servedState.revisions.length + 1).padStart(3, '0');
  const row = {...structuredClone(old), revision, revision_manifest_sha256:String(servedState.revisions.length + 1).repeat(64), ...extra};
  servedState.revisions.push(row);
  servedState.working_revision = revision;
  servedState.inputs_digest += '-next';
  return row;
}
async function viewWorking() {
  $('viewRevision').value = state.working_revision;
  await $('viewRevision').onchange();
}
function completeMist(payload, base, override = {}) {
  const old = servedState.revisions.at(-1);
  const saved = payload.action === 'disable' ? {...old.mist, settings:{...old.mist.settings, enabled:false}}
    : {settings:payload.settings, area_sha256:'area', density_sha256:'density', clear_sha256:'clear', protection_sha256:old.hard_protection_sha256};
  const row = advanceMist({mist:saved, mist_area: payload.clear_area || old.mist_area});
  servedState.action = {name:'effects', running:false, error:null, result:{revision:row.revision, parent:base.revision,
    developed_id:servedState.developed_id, mist:saved, base_manifest_sha256:base.revision_manifest_sha256,
    revision_manifest_sha256:row.revision_manifest_sha256, ...override}};
  return row;
}
function editMistDensity(value) {
  $('mistDensity').value = String(value);
  $('mistDensity').oninput();
}
"""


def test_page_mist_defaults_keyboard_rectangle_and_matching_apply_and_compare():
    run_page(
        MIST_PAGE
        + r"""
await ready();
assert.equal($('mistEnabled').checked, false);
assert.equal(Number($('mistDensity').value), 22);
assert.equal($('mistHex').value, '#8C9192');
assert.equal(Number($('mistCenterX').value), 50);
assert.equal(Number($('mistRadiusX').value), 60);
$('mistEnabled').checked = true; $('mistEnabled').oninput();
$('mistDensityRange').value = '34.5'; $('mistDensityRange').oninput();
assert.equal(Number($('mistDensity').value), 34.5);
$('mistCenterX').value = '21.25'; $('mistCenterX').oninput();
$('mistSeed').value = '4294967295'; $('mistSeed').oninput();
await $('mistNextPattern').onclick();
$('mistRectangle').value = '10,20,30,40'; $('mistFeather').value = '6';
await $('mistAddRectangle').onclick();
assert.match($('mistDraftStatus').textContent, /Unapplied changes/);
await $('mistApply').onclick();
const submission = posts.at(-1);
assert.equal(submission.base_revision, 'rev-001');
assert.equal(submission.revision_manifest_sha256, baseRow.revision_manifest_sha256);
assert.equal(submission.mist.settings.seed, 0);
assert.equal(submission.mist.settings.density, .345);
assert.equal(submission.mist.settings.coverage.center_xy[0], 21.25);
const rect = submission.mist.clear_area.regions[0];
assert.deepEqual({...rect, id:'rect'}, {id:'rect', role:'support', shape:'rectangle', xyxy:[10,20,30,40], feather_px:6});
completeMist(submission.mist, baseRow);
await refresh();
assert.doesNotMatch($('mistDraftStatus').textContent, /Unapplied changes/);
$('viewRevision').value = 'rev-001'; await $('viewRevision').onchange();
assert.equal($('mistApply').disabled, true);
assert.equal($('mistDisable').disabled, true);
assert.match($('mistSavedStatus').textContent, /Viewed rev-001.*Working edit base rev-002/);
await viewWorking();
assert.equal($('mistDisable').disabled, false);
$('textureCompare').checked = true;
$('mistCompare').checked = true; await $('mistCompare').onchange();
assert.equal($('textureCompare').checked, false);
assert(paths.some(path=>path.startsWith('/image/result/rev-002/') && path.endsWith('/mist-off')));
"""
    )


def test_page_vapor_places_focus_saves_and_preserves_clear_shapes():
    run_page(
        MIST_PAGE
        + r"""
await ready();
$('mistRectangle').value = '10,20,30,40';
$('mistFeather').value = '0';
await $('mistAddRectangle').onclick();
editMistDensity(39.5);
$('mistStyle').value = 'vapor';
await $('mistStyle').onchange();
assert.equal($('mistPlaceCentre').textContent, 'Place clear focus on canvas');
$('mistEnabled').checked = true;
$('mistEnabled').oninput();
$('mistDensityRange').value = '82.5';
$('mistDensityRange').oninput();
$('mistCenterX').value = '27.25';
$('mistCenterX').oninput();
$('mistStyle').value = 'mist';
await $('mistStyle').onchange();
assert.equal(Number($('mistDensity').value), 39.5);
$('mistStyle').value = 'vapor';
await $('mistStyle').onchange();
await $('mistApply').onclick();
const submission = posts.at(-1).mist;
assert.equal(submission.settings.style, 'vapor');
assert.equal(submission.settings.pattern_version, 2);
assert.equal(submission.settings.density, .825);
assert.equal(submission.settings.focus_xy[0], 27.25);
assert.equal(submission.settings.coverage, undefined);
assert.equal(submission.clear_area.regions.length, 1);
completeMist(submission, baseRow);
await refresh();
await viewWorking();
assert.equal($('mistStyle').value, 'vapor');
assert.equal(Number($('mistCenterX').value), 27.25);
$('mistCompare').checked = true;
await $('mistCompare').onchange();
assert(paths.some(path => path.startsWith('/image/result/rev-002/') && path.endsWith('/mist-off')));
"""
    )


def test_page_mist_rebinds_only_same_saved_state_and_own_disable_only_retargets_bound_form():
    run_page(
        MIST_PAGE
        + r"""
await ready();
editMistDensity(48);
$('mistRectangle').value='10,10,30,30'; $('mistFeather').value='4';
await $('mistAddRectangle').onclick();
const shape = $('mistRegions').options[0].value;
const sameAbsence = advanceMist();
await refresh(true); await viewWorking();
assert.match($('mistDraftStatus').textContent,/Stale.*Unapplied/i);
assert.equal($('mistRebind').disabled,false);
await $('mistRebind').onclick();
assert.equal($('mistRegions').options[0].value,shape);
$('mistCandidate').checked = true;
await $('mistApply').onclick();
const onDraft = posts.at(-1).mist;
assert.equal(onDraft.settings.density,.48);
onDraft.settings.enabled=true;
const on = completeMist(onDraft, sameAbsence);
await refresh(); await viewWorking();
// An unproven response leaves the draft. Reload it explicitly before testing Disable.
await $('mistReload').onclick();
editMistDensity(72);
await $('mistDisable').onclick();
assert.deepEqual(posts.at(-1).mist,{action:'disable'});
const disabled = completeMist(posts.at(-1).mist,on);
await refresh(); await viewWorking();
assert.match($('mistDraftStatus').textContent,/Unapplied changes/);
assert.doesNotMatch($('mistDraftStatus').textContent,/Stale/);
assert.equal(Number($('mistDensity').value),72);
assert.equal($('mistRegions').options[0].value,shape);
const sameOff = advanceMist();
await refresh(true); await viewWorking();
assert.equal($('mistRebind').disabled,false);
await $('mistRebind').onclick();
assert.equal(Number($('mistDensity').value),72);
advanceMist({hard_protection_sha256:'d'.repeat(64)});
await refresh(true); await viewWorking();
assert.equal($('mistRebind').disabled,true);
assert.equal($('mistApply').disabled,true);
await $('mistReload').onclick();
assert.equal(Number($('mistDensity').value),48);
"""
    )


def test_page_mist_keeps_unacknowledged_and_newer_input_on_unrelated_and_uncertain_publication():
    run_page(
        MIST_PAGE
        + r"""
await ready();
editMistDensity(45);
await $('mistApply').onclick();
const first = posts.at(-1).mist;
editMistDensity(67);
const row = completeMist(first,baseRow);
await refresh(); await viewWorking();
assert.equal(Number($('mistDensity').value),67);
assert.match($('mistDraftStatus').textContent,/Stale.*Unapplied/i);
assert.equal($('mistRebind').disabled,true,'Absent and explicitly saved OFF differ');
await $('mistReload').onclick();
editMistDensity(55); $('mistCandidate').checked=true;
await $('mistApply').onclick();
servedState.action={name:'effects',running:false,error:'Mist publication durability unconfirmed: visible revision rev-003',result:null};
await refresh();
assert.match($('mistDraftStatus').textContent,/Unapplied changes/);
assert.equal(Number($('mistDensity').value),55);
const unrelated = advanceMist();
servedState.action={name:'effects',running:false,error:null,result:{revision:unrelated.revision,parent:row.revision}};
await refresh(true); await viewWorking();
assert.match($('mistDraftStatus').textContent,/Stale.*Unapplied/i);
assert.equal(Number($('mistDensity').value),55);
assert.equal($('mistRebind').disabled,false);
"""
    )


def test_page_mist_saved_only_disable_does_not_retarget_already_stale_area():
    run_page(
        MIST_PAGE
        + r"""
baseRow.mist = {settings:{enabled:true,density:.22,tint_srgb:'#8C9192',wisp_size:.22,stretch:2,rotation_degrees:25,seed:1,
  coverage:{center_xy:[50,50],radii_xy:[60,60],softness:.72}}, area_sha256:'initial-area', density_sha256:'density', clear_sha256:'clear'};
baseRow.mist_area = {regions:[],protection:[]};
await ready();
editMistDensity(49);
const later = advanceMist();
await refresh(true); await viewWorking();
assert.match($('mistDraftStatus').textContent,/Stale.*Unapplied/i);
await $('mistDisable').onclick();
completeMist(posts.at(-1).mist, later);
await refresh(); await viewWorking();
assert.match($('mistSavedStatus').textContent,/Saved Mist OFF/);
assert.match($('mistDraftStatus').textContent,/Stale.*Unapplied/i);
assert.equal($('mistApply').disabled,true);
assert.equal(Number($('mistDensity').value),49);
"""
    )
