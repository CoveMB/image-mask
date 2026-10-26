"""Shipped viewer handlers and real HTTP image/operation boundaries."""

import io
import time

import numpy as np
import pytest
from PIL import Image
from test_sharpening import sharpening_project, sharpening_request
from test_viewer import http, running
from test_viewer_page import run_page

from blackmask.export import render_black, saved_layers
from blackmask.project import ProjectError


def test_viewer_sharpening_submission_crop_compare_and_snapshot(tmp_path):
    project, _, _ = sharpening_project(tmp_path)
    guides = (project / "guides.json").read_bytes()
    with running(project) as server:
        state = server.snapshot()
        operation = sharpening_request(project)
        operation.pop("schema_version")
        operation.pop("kind")
        operation.update(action="effects", authoring_digest=state["authoring_digest"])
        assert (
            http(server, "/api/action", "POST", operation, Origin="https://attacker.invalid")[0]
            == 403
        )
        assert http(server, "/api/action", "POST", dict(operation, unknown=1))[0] == 400
        assert http(server, "/api/action", "POST", operation)[0] == 202
        # Polling action state avoids the known unrelated snapshot/writer lock race.
        for _ in range(400):
            if not server.action["running"]:
                break
            time.sleep(0.01)
        current = server.snapshot()
        assert not current["action"]["error"], current["action"]
        revision = current["working_revision"]
        record = next(r for r in current["revisions"] if r["revision"] == revision)
        assert record["sharpening_area"] == operation["sharpening_area"]
        assert record["local_sharpening"]["enabled"]
        state_before = (project / "state.json").read_bytes()
        with Image.open(
            io.BytesIO(server.image(f"/image/black/{revision}/1,0,5,4/sharpening-off"))
        ) as image:
            actual = np.array(image)
        rgb, alpha, _ = saved_layers(
            project, revision, current["developed_id"], sharpening_off=True
        )
        np.testing.assert_array_equal(
            actual, np.rint(render_black(rgb, alpha)[:, 1:5] / 257).astype(np.uint8)
        )
        assert server.image(f"/image/alpha/{revision}/0,0,6,4") == server.image(
            f"/image/alpha/{revision}/0,0,6,4/sharpening-off"
        )
        assert (project / "state.json").read_bytes() == state_before
        with pytest.raises(ProjectError, match="Stale"):
            server.execute(operation)
    assert (project / "guides.json").read_bytes() == guides


def test_sharpening_keyboard_area_controls_pending_drafts_and_off_comparison():
    run_page(r"""
await ready();
$('exposureEV').value='1.2';$('exposureEV').oninput();
$('sharpeningRole').value='regions';$('sharpeningFeather').value='2';
$('sharpeningRectangle').value='10,20,70,80';await $('sharpeningAddRectangle').onclick();
$('sharpeningRole').value='protection';$('sharpeningRectangle').value='30,40,50,60';
await $('sharpeningAddRectangle').onclick();
assert.equal(sharpeningArea.regions[0].feather_px,2);
assert.equal(sharpeningArea.protection[0].feather_px,0);
$('sharpeningAmount').value='45';$('sharpeningAmount').oninput();
$('sharpeningDetail').value='8';$('sharpeningDetail').oninput();
$('sharpeningNoise').value='0.13';$('sharpeningNoise').oninput();
$('sharpeningCandidate').checked=true;
await poll();assert.equal(Number($('sharpeningAmount').value),45);
await $('sharpeningApply').onclick();
assert.deepEqual(posts.at(-1).local_sharpening,{enabled:true,amount:.45,radius_px:8,noise_threshold:.0013});
assert.deepEqual(posts.at(-1).sharpening_area,sharpeningArea);
const pending=JSON.stringify(sharpeningArea);
await $('sharpeningAmountApply').onclick();
assert.equal(posts.at(-1).sharpening_amount_only,true);assert(!('sharpening_area' in posts.at(-1)));
await $('sharpeningReset').onclick();assert.equal(posts.at(-1).local_sharpening.enabled,false);
assert.equal(JSON.stringify(sharpeningArea),pending);assert.equal($('exposureEV').value,'1.2');
const count=posts.length;$('fadeCompare').checked=true;$('sharpeningCompare').checked=true;
await $('sharpeningCompare').onchange();assert.equal(posts.length,count);assert.equal($('fadeCompare').checked,false);
assert.equal(dirty,false);
""")


@pytest.mark.parametrize(
    "field,value",
    [
        ("Detail", "0.4"),
        ("Detail", "8.1"),
        ("Noise", "2.01"),
        ("Amount", "101"),
        ("Noise", ""),
        ("Detail", "NaN"),
    ],
)
def test_invalid_sharpening_controls_do_not_submit(field, value):
    run_page(
        r"""
await ready();$('sharpeningAmount').value='30';$('sharpeningDetail').value='1';$('sharpeningNoise').value='0.1';
$('sharpening'+FIELD).value=VALUE;await $('sharpeningAmountApply').onclick();assert.equal(posts.length,0);
""".replace("FIELD", repr(field)).replace("VALUE", repr(value))
    )


def test_sharpening_stale_controls_and_failed_action_keep_drafts():
    run_page(r"""
await ready();$('sharpeningAmount').value='65';$('sharpeningAmount').oninput();
$('sharpeningDetail').value='4.2';$('sharpeningDetail').oninput();
$('sharpeningNoise').value='0.12';$('sharpeningNoise').oninput();
servedState.action={name:'effects',running:false,error:'failure',result:null};
await poll();assert.equal(Number($('sharpeningDetail').value),4.2);
servedState.inputs_digest='changed';await refresh();
assert($('sharpeningDraftStatus').textContent.includes('Stale'));
await $('sharpeningAmountApply').onclick();assert.equal(posts.length,0);
""")


def test_sharpening_brush_uses_native_crop_and_separate_protection():
    run_page(r"""
await ready();$('authorMode').value='sharpening';$('sharpeningRole').value='regions';
$('sharpeningShape').value='stroke';$('sharpeningRadius').value='3';$('sharpeningFeather').value='2';
$('crop').value='20,20,80,80';await $('cropApply').onclick();
canvas.onpointerdown({clientX:100,clientY:50,pointerId:1,shiftKey:false});
canvas.onpointermove({clientX:150,clientY:100,pointerId:1});
canvas.onpointermove({clientX:200,clientY:150,pointerId:1});
canvas.onpointerup({clientX:200,clientY:150,pointerId:1});
assert.deepEqual(sharpeningArea.regions[0].points,[[35,35],[50,50],[65,65]]);
assert.equal(sharpeningArea.regions[0].radius_px,3);
assert.equal(sharpeningArea.regions[0].feather_px,2);
assert.equal(regions.length,0);assert.equal(exposureArea.regions.length,0);
assert.equal(dirty,false);assert.equal(sharpeningDirty,true);
$('sharpeningRole').value='protection';$('sharpeningShape').value='rectangle';
canvas.onpointerdown({clientX:100,clientY:50,pointerId:2,shiftKey:false});
canvas.onpointerup({clientX:200,clientY:150,pointerId:2});
assert.deepEqual(sharpeningArea.protection[0].xyxy,[35,35,65,65]);
assert.equal(sharpeningArea.protection[0].feather_px,0);
""")
