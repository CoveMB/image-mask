"""The tone curve's saved HTTP boundary and shipped keyboard editor."""

import io
import time

import numpy as np
from PIL import Image
from test_effects import fixture_project
from test_tone_curve import curve_request
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask.export import render_black, saved_layers


def test_curve_viewer_action_and_native_off_crop(tmp_path):
    source = np.full((4, 6, 3), 36000, np.uint16)
    project, _, _ = fixture_project(tmp_path, source)
    with running(project) as server:

        def submit(**changes):
            state = server.snapshot()
            request = curve_request(
                project, **{k: v for k, v in changes.items() if k != "overrides"}
            )
            request.pop("kind")
            request.pop("schema_version")
            revision = next(
                r for r in state["revisions"] if r["revision"] == state["working_revision"]
            )
            request.update(
                action="effects",
                authoring_digest=state["authoring_digest"],
                revision_manifest_sha256=revision["revision_manifest_sha256"],
            )
            request.update(changes.get("overrides", {}))
            status, response, _ = http(server, "/api/action", "POST", request)
            assert status == 202, response
            completion = time.monotonic() + 10
            while server.action["running"]:
                assert time.monotonic() < completion
                time.sleep(0.01)
            return server.snapshot(), request

        state, operation = submit()
        assert state["action"]["error"] is None
        first_revision = state["working_revision"]
        row = next(r for r in state["revisions"] if r["revision"] == first_revision)
        assert row["tone_curve_area"] == operation["tone_curve_area"]
        assert row["local_tone_curve"]["settings"] == operation["local_tone_curve"]
        state, _ = submit(settings_only=True, points=[[2500, 5000]])
        assert "candidate comparison" in state["action"]["error"]
        assert state["working_revision"] == first_revision
        for overrides in (
            {"revision_manifest_sha256": "0" * 64},
            {"authoring_digest": "wrong"},
        ):
            state, _ = submit(settings_only=True, candidate=True, overrides=overrides)
            assert "Stale" in state["action"]["error"]
            assert state["working_revision"] == first_revision
        state, _ = submit(settings_only=True, candidate=True, points=[[2500, 5000]])
        assert state["action"]["error"] is None
        revision = state["working_revision"]
        assert revision != first_revision
        before = (project / "state.json").read_bytes()
        revisions = set((project / "revisions").iterdir())
        crop = "1,0,5,4"
        for suffix in ("", "/tone-curve-off"):
            status, data, _ = http(server, f"/image/black/{revision}/{crop}{suffix}")
            assert status == 200
            rgb, alpha, _ = saved_layers(
                project, revision, state["developed_id"], tone_curve_off=bool(suffix)
            )
            with Image.open(io.BytesIO(data)) as image:
                actual = np.array(image)
            np.testing.assert_array_equal(
                actual, np.rint(render_black(rgb, alpha)[:, 1:5] / 257).astype(np.uint8)
            )
        assert (
            http(server, f"/image/alpha/{revision}/{crop}")[1]
            == http(server, f"/image/alpha/{revision}/{crop}/tone-curve-off")[1]
        )
        assert (
            http(server, f"/image/source/{state['developed_id']}/{crop}")[1]
            == http(server, f"/image/source/{state['developed_id']}/{crop}/tone-curve-off")[1]
        )
        assert (
            http(
                server,
                f"/image/black/{revision}/{crop}/tone-curve-off",
                **{"X-Blackmask-Token": "invalid"},
            )[0]
            == 403
        )
        assert (project / "state.json").read_bytes() == before
        assert set((project / "revisions").iterdir()) == revisions


def test_curve_keyboard_points_and_independent_drafts():
    run_page(r"""
const originalFetch = fetch;
globalThis.fetch = (path, options) => {
 if (options.method === 'POST') servedState.action={running:true,name:'effects',error:null,result:null};
 return originalFetch(path, options);
};
function input(row, x, y) {
 const [input, output] = toneCurvePointRows[row];
 input.value=x; output.value=y; output.oninput();
}
async function complete(revision, effect, error=null) {
 const submitted = posts.at(-1);
 const parent = servedState.working_revision;
 if (!error) {
  const base = servedState.revisions.find(item=>item.revision===parent);
  servedState.working_revision=revision;
  servedState.inputs_digest='input-'+revision;
  const current={...base,revision,revision_manifest_sha256:revision.repeat(10),
    local_tone_curve:{enabled:effect.enabled,stale:false,settings:effect},
    tone_curve_area:submitted.tone_curve_area || base.tone_curve_area};
  servedState.revisions.push(current);
 }
 servedState.action={running:false,name:'effects',error,result:error?null:{
  parent,revision,local_tone_curve:{settings:effect},effects_reuse:{request:submitted}
 }};
 await refresh();
}
await ready();
assert.equal($('toneCurveCandidate').checked,false);
await $('toneCurveAddPoint').onclick(); input(0,'8','5.50');
await $('toneCurveAddPoint').onclick(); input(1,'8','38');
$('toneCurveRole').value='regions'; $('toneCurveFeather').value='2';
$('toneCurveRectangle').value='10,20,70,80'; await $('toneCurveAddRectangle').onclick();
$('authorMode').value='toneCurve'; $('toneCurveRole').value='protection'; $('toneCurveShape').value='rectangle';
canvas.onpointerdown({clientX:100,clientY:50,pointerId:2,shiftKey:false});
canvas.onpointerup({clientX:200,clientY:150,pointerId:2,shiftKey:false});
assert.equal(toneCurveArea.regions[0].feather_px,2);
assert.equal(toneCurveArea.protection[0].feather_px,0);
assert.equal(regions.length,0);
await $('toneCurveApply').onclick(); assert.equal(posts.length,0);
input(1,'32','4'); await $('toneCurveApply').onclick(); assert.equal(posts.length,0);
input(1,'32',''); await $('toneCurveApply').onclick(); assert.equal(posts.length,0);
input(1,'32','38.001'); await $('toneCurveApply').onclick(); assert.equal(posts.length,0);
input(0,'32','38'); input(1,'8','5.50'); await $('toneCurveApply').onclick();
assert.deepEqual(posts[0].local_tone_curve,{enabled:true,points:[[800,550],[3200,3800]]});
assert.deepEqual(posts[0].tone_curve_area,toneCurveArea);
assert.equal(posts[0].candidate_comparison,false);
assert.equal(posts[0].revision_manifest_sha256,'a'.repeat(64));
await complete('rev-002',posts[0].local_tone_curve);
await $('toneCurveSavedApply').onclick(); assert.equal(posts.length,1);

$('toneCurveRole').value='regions';$('toneCurveRectangle').value='14,20,72,80';
await $('toneCurveAddRectangle').onclick();
const pending=structuredClone(toneCurveArea);
$('toneCurveCandidate').checked=true; $('toneCurveCandidate').onchange();
await $('toneCurveSavedApply').onclick();
assert.equal(posts[1].candidate_comparison,true);
assert.equal(posts[1].tone_curve_settings_only,true);
assert(!('tone_curve_area' in posts[1]));
await complete('rev-003',posts[1].local_tone_curve,'write failed');
assert.deepEqual(toneCurveArea,pending);
assert.equal($('toneCurveCandidate').checked,true);

await $('toneCurveSavedApply').onclick();
input(0,'8','5.75'); // A queued edit belongs to a newer settings version.
await complete('rev-003',posts[2].local_tone_curve);
assert.deepEqual(toneCurveArea,pending);
assert.equal(toneCurvePointRows[0][1].value,'5.75');
assert.match($('toneCurveDraftStatus').textContent,/Stale/);
await $('toneCurveReload').onclick();
assert.deepEqual(toneCurveArea,pending);
$('toneCurveCandidate').checked=true; $('toneCurveCandidate').onchange();
await $('toneCurveApply').onclick(); assert.equal(posts.length,3,'Stale area must not replace current area');
assert.match($('message').textContent,/stale.*area/i);

input(0,'','');
await $('toneCurveDisable').onclick();
assert.deepEqual(posts[3].local_tone_curve,{enabled:false,points:[[800,550],[3200,3800]]});
assert(!('tone_curve_area' in posts[3]));
await complete('rev-004',posts[3].local_tone_curve);
assert.deepEqual(toneCurveArea,pending);
assert.equal(toneCurvePointRows[0][0].value,'');
servedState.action={running:false,name:'effects',error:null,result:{revision:'rev-004',local_exposure:{enabled:true}}};
await refresh(); assert.deepEqual(toneCurveArea,pending);
await $('toneCurveReloadArea').onclick();
assert.deepEqual(toneCurveArea,posts[0].tone_curve_area);
assert.equal(toneCurvePointRows[0][0].value,'');
$('sharpeningCompare').checked=true;$('toneCurveCompare').checked=true;
await $('toneCurveCompare').onchange();assert.equal($('sharpeningCompare').checked,false);
assert.equal(posts.length,4);
""")
