"""Local Texture uses the working revision's native viewer and draft boundaries."""

import time

import numpy as np
import pytest
from test_effects import fixture_project
from test_shadow_fade import fade_request
from test_spatial_fade import spatial_request, spatial_settings
from test_texture import SETTINGS, gray16
from test_texture_project import texture_request
from test_tone_curve import curve_request
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask import operations
from blackmask.effects import saved_spatial_fade
from blackmask.export import saved_layers
from blackmask.spatial_fade import spatial_fade_amount


def test_texture_viewer_off_recomputes_downstream_effects_without_a_write(tmp_path):
    source = gray16(np.array([0.28, 0.28, 0.312, 0.348, 0.329, 0.292]), height=4)
    project, _, _ = fixture_project(tmp_path, source)
    operations.apply_operation(project, curve_request(project, candidate=True))
    operations.apply_operation(project, fade_request(project, amount=0.3))
    without_texture = operations.apply_operation(
        project,
        spatial_request(
            project, spatial_settings(6, 4) | {"preserve_highlights": 1}, candidate=True
        ),
    )["revision"]
    with running(project) as server:
        state = server.snapshot()
        parent = next(
            row for row in state["revisions"] if row["revision"] == state["working_revision"]
        )
        fields = texture_request(project, settings=SETTINGS | {"strength": 1})
        fields.pop("schema_version")
        fields.pop("kind")
        fields.update(
            action="effects",
            authoring_digest=state["authoring_digest"],
            revision_manifest_sha256=parent["revision_manifest_sha256"],
        )
        status, response, _ = http(server, "/api/action", "POST", fields)
        assert status == 202, response
        deadline = time.monotonic() + 10
        while server.action["running"]:
            assert time.monotonic() < deadline
            time.sleep(0.01)
        state = server.snapshot()
        assert state["action"]["error"] is None
        revision = state["working_revision"]
        row = next(row for row in state["revisions"] if row["revision"] == revision)
        assert row["texture_alpha_current"] and row["texture_area"] == fields["texture_area"]
        reference, matte, reference_manifest = saved_layers(
            project, without_texture, state["developed_id"]
        )
        active, actual_matte, _ = saved_layers(project, revision, state["developed_id"])
        np.testing.assert_array_equal(actual_matte, matte)
        spatial = saved_spatial_fade(project, without_texture, matte, reference_manifest)
        assert spatial is not None
        assert np.any(
            spatial_fade_amount(reference, matte, spatial)
            != spatial_fade_amount(active, matte, spatial)
        )
        state_paths = [
            project / name
            for name in ("state.json", "recipe.toml", f"revisions/{revision}/manifest.json")
        ]
        before_compare = {path: path.read_bytes() for path in state_paths}

        def crop(panel, selected, suffix=""):
            status, data, _ = http(server, f"/image/{panel}/{selected}/1,0,6,4{suffix}")
            assert status == 200
            return data

        for panel in ("result", "black", "gray", "white", "alpha"):
            expected = crop(panel, without_texture)
            assert crop(panel, revision, "/texture-off") == expected
            assert (crop(panel, revision) == expected) == (panel == "alpha")
        assert all(path.read_bytes() == content for path, content in before_compare.items())


def test_texture_keyboard_draft_and_saved_area_rebind_gate():
    run_page(r"""
servedState.texture_defaults={enabled:false,strength:0,scale_px:4,grain_guard:.0005,preserve_highlights:1};
await ready();
$('textureRole').value='regions'; $('textureFeather').value='3';
$('textureRectangle').value='10,20,70,80'; await $('textureAddRectangle').onclick();
$('textureStrength').value=''; $('textureStrength').oninput();
await $('textureApply').onclick(); assert.equal(posts.length,0);
$('textureStrength').value='25'; $('textureStrength').oninput();
await $('textureApply').onclick();
assert.deepEqual(posts[0].local_texture,{enabled:true,strength:.25,scale_px:4,grain_guard:.0005,preserve_highlights:1});
assert.equal(posts[0].texture_area.regions[0].feather_px,3);
const pairedArea=structuredClone(posts[0].texture_area);
const current=servedState.revisions.find(row=>row.revision===servedState.working_revision);
current.local_texture={enabled:false,stale:false,settings:{...posts[0].local_texture,enabled:false}};
current.texture_area=pairedArea; current.texture_alpha_current=false;
await refresh();
assert($('textureSavedApply').disabled);
assert.match($('textureStatus').textContent,/alpha.*rebuild/i);
$('textureCompare').checked=true; await $('textureCompare').onchange();
assert.equal($('toneCurveCompare').checked,false);
""")


@pytest.mark.parametrize("draft", ["area", "settings"])
def test_editing_stale_texture_draft_does_not_rebind_it(draft):
    run_page(
        f"const staleDraft = '{draft}';\n"
        + r"""
servedState.texture_defaults={enabled:false,strength:0,scale_px:4,grain_guard:.0005,preserve_highlights:1};
await ready();
async function rectangle(x) {
  $('textureRole').value='regions'; $('textureFeather').value='0';
  $('textureRectangle').value=`${x},20,70,80`; await $('textureAddRectangle').onclick();
}
function strength(value) { $('textureStrength').value=value; $('textureStrength').oninput(); }
if (staleDraft === 'area') await rectangle(10);
else strength('25');
const next='rev-002';
servedState.revisions.push({...servedState.revisions[0],revision:next,revision_manifest_sha256:'b'.repeat(64)});
servedState.working_revision=servedState.accepted_revision=next;
servedState.inputs_digest='new-inputs';
await refresh();
$('viewRevision').value=next; await loadImage();
await rectangle(15); strength('40');
await $('textureApply').onclick();
assert.equal(posts.length,0);
assert.match($('message').textContent, new RegExp('stale texture '+staleDraft,'i'));
"""
    )


def test_another_effect_completion_does_not_acknowledge_texture_draft():
    run_page(r"""
const settings={enabled:true,strength:.25,scale_px:4,grain_guard:.0005,preserve_highlights:1};
const original=servedState.revisions[0];
original.local_texture={enabled:true,stale:false,settings}; original.texture_alpha_current=true;
const originalFetch=fetch;
globalThis.fetch=(path,options)=>{
  if(options.method==='POST') servedState.action={running:true,name:'effects',error:null,result:null};
  return originalFetch(path,options);
};
await ready();
$('textureCandidate').checked=true; $('textureCandidate').onchange();
$('textureRole').value='regions'; $('textureFeather').value='0';
$('textureRectangle').value='10,20,70,80'; await $('textureAddRectangle').onclick();
await $('textureApply').onclick(); assert.equal(posts.length,1);
servedState.working_revision='rev-002'; servedState.inputs_digest='new-inputs';
servedState.revisions.push({...original,revision:'rev-002',revision_manifest_sha256:'b'.repeat(64)});
servedState.action={running:false,name:'effects',error:null,result:{revision:'rev-002',parent:original.revision,
 effects_reuse:{request:{local_exposure:{enabled:true,ev:.5}}}}};
await refresh();
assert.equal($('textureCandidate').checked,true);
assert.match($('textureDraftStatus').textContent,/stale settings/i);
""")
