"""Execute shipped page handlers with controlled DOM/transport boundaries.

These behavioral transition checks complement actual-browser evidence; they do
not substitute for browser rendering, accessibility or human photographic review.
"""

import subprocess
from pathlib import Path

PRELUDE = r"""
const assert = require('node:assert/strict');
const nodes = new Map();
const context = new Proxy({}, {get: () => () => {}});
function makeNode(id = '') {
  return {id, value:'', checked:false, disabled:false, textContent:'', options:[],
    replaceChildren(){this.options=[];}, append(option){this.options.push(option);},
    querySelectorAll(){return [];},
    getBoundingClientRect(){return {left:0,top:0,width:300,height:200};},
    getContext(){return context;}, setPointerCapture(){} };
}
globalThis.document = {
  getElementById(id){if(!nodes.has(id))nodes.set(id,makeNode(id));return nodes.get(id);},
  createElement(){return makeNode();}, createTextNode(text){return text;}
};
globalThis.location={hash:'#synthetic-test-only'};
globalThis.ResizeObserver=class {observe(){}};
let poll;globalThis.setInterval=callback=>{poll=callback;return 0;};
globalThis.confirm=()=>true;
globalThis.createImageBitmap=async blob=>({width:blob.width,height:blob.height,close(){}});
const servedState={
 master_id:'master',working_revision:'rev-001',accepted_revision:'rev-001',
 inputs_digest:'draft',authoring_digest:'author',dimensions_wh:[100,100],
 recipe:{groups:[]},guides:{regions:[]},
 revisions:[{revision:'rev-001',kind:'matte',draft_digest:'draft',final_acceptable:true,candidates:[]}],
 operations:[],pending:null,action:{running:false,error:null,result:{directory:'exports/rev-001'}}
};
const posts=[], imageResolvers=[];
let holdImages=false, imageFailure=false;
globalThis.fetch=async(path,options)=>{
 if(options.method==='POST')posts.push(JSON.parse(options.body));
 const dimensions=path.startsWith('/image/')?path.split('/').at(-1).split(',').map(Number):[0,0,100,100];
 const response={ok:!(path.startsWith('/image/')&&imageFailure),
  json:async()=>path==='/api/state'?structuredClone(servedState):{started:true,error:'synthetic image unavailable'},
  blob:async()=>({width:dimensions[2]-dimensions[0],height:dimensions[3]-dimensions[1]})};
 if(holdImages&&path.startsWith('/image/'))return new Promise(resolve=>imageResolvers.push(()=>resolve(response)));
 return response;
};
"""


def run_page(scenario):
    page = Path("src/blackmask/ui/review.html").read_text()
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    setup = r"""
async function ready(){
 $('panel').value='source';$('overlay').value='none';$('role').value='background';$('shape').value='point';
 await refresh(true);
 for(let i=0;i<30&&(!image||!transform);i++)await Promise.resolve();
 assert(image&&transform,'Initial native view did not load');
}
"""
    result = subprocess.run(
        ["node", "-"],
        input=PRELUDE
        + Path("src/blackmask/ui/coordinates.js").read_text()
        + script
        + setup
        + "\n(async()=>{"
        + scenario
        + "})().catch(error=>{console.error(error.stack);process.exitCode=1;});",
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_export_keeps_complete_unsaved_guides_and_groups():
    run_page(r"""
 await ready();
 $('newGroup').value='subject';await $('addGroup').onclick();addRegion([10,10]);
 const before=JSON.stringify({groups,regions});
 await $('exportAccepted').onclick();
 assert.equal(dirty,true,'Export discarded unsaved authoring');
 assert.equal(JSON.stringify({groups,regions}),before);
 assert.equal(posts.at(-1).action,'export');
 """)


def test_canvas_rejects_authoring_during_processing_and_crossing_action_boundary():
    run_page(r"""
 await ready();servedState.action.running=true;await refresh();
 canvas.onpointerdown({clientX:70,clientY:20,pointerId:1,shiftKey:false});
 canvas.onpointerup({clientX:70,clientY:20,pointerId:1});
 assert.equal(regions.length,0,'Accepted a guide during processing');
 servedState.action.running=false;await refresh();
 canvas.onpointerdown({clientX:70,clientY:20,pointerId:2,shiftKey:false});
 servedState.action.running=true;await refresh();
 canvas.onpointerup({clientX:70,clientY:20,pointerId:2});
 assert.equal(regions.length,0,'Gesture crossed an active writer boundary');
 """)


def test_crop_loading_blocks_coordinates_until_matching_view_arrives():
    run_page(r"""
 await ready();assert.deepEqual(nativePosition({clientX:70,clientY:20}),[10,10]);
 holdImages=true;$('crop').value='20,20,80,80';
 const loading=$('cropApply').onclick();
 assert.equal(nativePosition({clientX:70,clientY:20}),null,'Old image acquired the new crop origin');
 for(let i=0;i<30&&!imageResolvers.length;i++)await Promise.resolve();
 assert.equal(imageResolvers.length,1);holdImages=false;imageResolvers.shift()();await loading;
 const point=nativePosition({clientX:250/3,clientY:100/3});
 assert(Math.abs(point[0]-30)<1e-10&&Math.abs(point[1]-30)<1e-10);
 """)


def test_failed_crop_view_cannot_author_against_previous_pixels():
    run_page(r"""
 await ready();imageFailure=true;$('crop').value='20,20,80,80';await $('cropApply').onclick();
 assert.equal(nativePosition({clientX:70,clientY:20}),null,'Failed view kept mismatched old pixels authorable');
 """)


def test_reload_invalidates_review_confirmations_and_selects_current_revision():
    run_page(r"""
 await ready();$('photoReviewed').checked=true;$('trimapReviewed').checked=true;
 servedState.working_revision='rev-002';servedState.revisions.push({...servedState.revisions[0],revision:'rev-002'});
 await $('reload').onclick();
 assert.equal($('photoReviewed').checked,false,'Photo review carried to another revision');
 assert.equal($('trimapReviewed').checked,false,'Trimap review carried to another revision');
 assert.equal($('viewRevision').value,'rev-002');
 await $('accept').onclick();assert.equal(posts.length,0,'Accepted without renewed explicit review');
 """)


def test_resume_requires_saved_authoring():
    run_page(r"""
 await ready();addRegion([10,10]);$('operation').value='matte-synthetic';await $('resume').onclick();
 assert.equal(posts.length,0,'Resume could change the identity underneath unsaved authoring');
 assert.equal(dirty,true);assert.equal(regions.length,1);
 """)


def test_save_dispatch_blocks_authoring_even_when_polling_observes_idle():
    run_page(r"""
 await ready();
 const originalFetch=globalThis.fetch;let releasePost;
 globalThis.fetch=async(path,options)=>{
   const response=await originalFetch(path,options);
   if(options.method==='POST')return new Promise(resolve=>{releasePost=()=>resolve(response);});
   return response;
 };
 const saving=$('save').onclick();
 for(let i=0;i<30&&!releasePost;i++)await Promise.resolve();
 assert(releasePost);await refresh();
 assert.equal($('addGroup').disabled,true,'Polling released the dispatch guard');
 canvas.onpointerdown({clientX:70,clientY:20,pointerId:1,shiftKey:false});
 canvas.onpointerup({clientX:70,clientY:20,pointerId:1});
 $('newGroup').value='late';await $('addGroup').onclick();
 assert.equal(regions.length,0,'Guide accepted after save payload serialization');
 assert.equal(groups.length,0,'Group accepted after save payload serialization');
 servedState.action={name:'save',running:false,error:null,result:{record_file:'saved'}};
 releasePost();await saving;
 assert.equal(posts[0].actions.length,0);assert.equal(dirty,false);
 assert.equal($('addGroup').disabled,false);
 """)


def test_rejected_dispatch_releases_authoring_and_retains_unsaved_edits():
    run_page(r"""
 await ready();addRegion([10,10]);const before=JSON.stringify(regions);
 const originalFetch=globalThis.fetch;let rejectPost;
 globalThis.fetch=async(path,options)=>{
   if(options.method==='POST')return new Promise((resolve,reject)=>{rejectPost=reject;});
   return originalFetch(path,options);
 };
 const saving=$('save').onclick();
 for(let i=0;i<30&&!rejectPost;i++)await Promise.resolve();
 assert.equal($('addGroup').disabled,true);
 rejectPost(Error('Synthetic dispatch rejection'));await saving;
 assert.equal($('addGroup').disabled,false,'Rejected dispatch left authoring disabled');
 assert.equal(authoringBusy(),false);assert.equal(dirty,true);
 assert.equal(JSON.stringify(regions),before);
 assert.equal($('message').textContent,'Synthetic dispatch rejection');
 addRegion([20,20]);assert.equal(regions.length,2);
 """)


def test_cleanup_controls_use_shared_action_and_block_submission_during_image_load():
    run_page(r"""
 await ready();$('cleanupStrength').value='0.35';$('cleanupCandidate').checked=true;
 $('cleanupScope').value='10,10,50,50';$('cleanupSupport').value='supports/manual16.png';
 imageLoading=true;await $('cleanupApply').onclick();assert.equal(posts.length,0);
 imageLoading=false;await $('cleanupApply').onclick();
 assert.equal(posts.at(-1).action,'effects');
 assert.deepEqual(posts.at(-1).scope_xyxy,[10,10,50,50]);
 assert.deepEqual(posts.at(-1).color_cleanup,{enabled:true,strength:.35});
 assert.equal(posts.at(-1).candidate_comparison,true);
 actionWasRunning=false;servedState.action.running=false;await refresh();
 await $('cleanupDisable').onclick();assert.equal(posts.at(-1).color_cleanup.enabled,false);
 """)


def test_same_alpha_cleanup_toggle_requests_explicit_base_pixels():
    run_page(r"""
 await ready();const paths=[];const originalFetch=globalThis.fetch;
 globalThis.fetch=async(path, options)=>{paths.push(path);return originalFetch(path.replace('/base',''),options);};
 $('panel').value='black';$('cleanupBase').checked=true;
 await $('cleanupBase').onchange();
 assert(paths.some(p=>p==='/image/black/rev-001/0,0,100,100/base'));
 """)


def test_shading_controls_use_shared_action_and_retain_dirty_guides():
    run_page(r"""
await ready();
$('shadingWidth').value='12';$('shadingDirection').value='90';$('shadingOpacity').value='0.12';
$('shadingScope').value='0,0,100,100';$('shadingSupport').value='support.png';$('shadingProtection').value='protect.png';
$('shadingCandidate').checked=true;
await shading(true, false);
assert.equal(posts.at(-1).action, 'effects');
assert.equal(posts.at(-1).shading.width_px, 12);
assert.equal(posts.at(-1).shading.opacity, .12);
assert.equal(posts.at(-1).shading_protection_file, 'protect.png');
assert(!('color_cleanup' in posts.at(-1)));
await shading(true, true);
assert.equal(posts.at(-1).opacity_only, true);
for(let i=0;i<30&&(!image||!transform);i++)await Promise.resolve();
dirty=true;
const count=posts.length;
await assert.rejects(() => shading(true, false), /Save authoring/);
assert.equal(posts.length,count);
""")


def test_shading_labels_follow_matching_historical_base_and_stale_image():
    run_page(r"""
servedState.working_revision='rev-002';
servedState.revisions=[
{revision:'rev-001',kind:'effects',draft_digest:'draft',final_acceptable:true,candidates:[],shading:{enabled:true,stale:false,opacity:.12,settings:{width_px:12,direction_degrees:90}},color_cleanup:{enabled:false,stale:false}},
{revision:'rev-002',kind:'effects',draft_digest:'draft',final_acceptable:true,candidates:[],shading:{enabled:true,stale:false,opacity:.24,settings:{width_px:30,direction_degrees:180}},color_cleanup:{enabled:true,stale:false}}];
await ready();
$('viewRevision').value='rev-001';$('panel').value='black';$('shadingPreview').value='0.12';
await loadImage();
assert($('shadingStatus').textContent.includes('width 12 px'), $('shadingStatus').textContent);
assert($('shadingStatus').textContent.includes('90°'));
assert($('shadingStatus').textContent.includes('cleanup OFF'));
assert($('shadingStatus').textContent.includes('opacity 0.12'));
$('cleanupBase').checked=true;await $('cleanupBase').onchange();
assert($('shadingStatus').textContent.includes('BASE'));
assert($('shadingStatus').textContent.includes('shading OFF'));
assert(!$('shadingStatus').textContent.includes('baked shading'));
$('cleanupBase').checked=false;
servedState.revisions[1].shading.stale=true;await refresh(false);
assert($('shadingStatus').textContent.includes('STALE'));
assert($('shadingStatus').textContent.includes('shading OFF'));
servedState.revisions[1].shading.stale=false;await refresh(false);
holdImages=true;$('viewRevision').value='rev-002';
const loading=loadImage();
assert($('shadingStatus').textContent.includes('Loading'));
for(let i=0;i<30&&!imageResolvers.length;i++)await Promise.resolve();
holdImages=false;imageResolvers.shift()();await loading;
assert($('shadingStatus').textContent.includes('width 30 px'));
$('panel').value='source';await loadImage();
assert($('shadingStatus').textContent.includes('Source'));
assert($('shadingStatus').textContent.includes('shading OFF'));
""")


def test_first_shading_controls_default_to_authored_guide_protection():
    run_page(r"""
await ready();
assert.equal($('shadingProtection').value,'revisions/rev-001/supports/protection.png');
assert.equal($('shadingSupport').value,'revisions/rev-001/supports/support16.png');
$('shadingWidth').value='12';$('shadingDirection').value='90';$('shadingOpacity').value='0.12';
$('shadingScope').value='0,0,100,100';$('shadingCandidate').checked=true;
await shading(true, false);
assert.equal(posts.at(-1).shading_protection_file,'revisions/rev-001/supports/protection.png');
""")


def test_cleanup_enable_rejects_empty_invalid_and_off_strength_without_submitting():
    run_page(r"""
 await ready();$('cleanupScope').value='0,0,100,100';$('cleanupSupport').value='support16.png';
 for(const value of ['', '   ', 'bad', 'Infinity', '-0.1', '1.1', '0']){
   $('cleanupStrength').value=value;await $('cleanupApply').onclick();
   assert.equal(posts.length,0,'Invalid Enable input submitted an effects action: '+value);
   assert.match($('message').textContent,/Cleanup strength|Strength 0/);
 }
 """)


def test_cleanup_disable_remains_available_with_invalid_strength():
    run_page(r"""
 await ready();$('cleanupScope').value='0,0,100,100';$('cleanupSupport').value='support16.png';
 for(const value of ['', 'bad', 'Infinity', '-0.1', '1.1']){
   $('cleanupStrength').value=value;await $('cleanupDisable').onclick();
   assert.deepEqual(posts.at(-1).color_cleanup,{enabled:false,strength:0});
   actionWasRunning=false;servedState.action.running=false;await refresh();
 }
 """)


def test_cleanup_enable_accepts_finite_positive_strength_and_upper_boundary():
    run_page(r"""
 await ready();$('cleanupScope').value='0,0,100,100';$('cleanupSupport').value='support16.png';
 for(const value of [' 0.35 ', '1']){
   $('cleanupStrength').value=value;await $('cleanupApply').onclick();
   assert.deepEqual(posts.at(-1).color_cleanup,{enabled:true,strength:Number(value)});
   actionWasRunning=false;servedState.action.running=false;await refresh();
 }
 """)


def test_state_polls_do_not_overlap_manual_refresh_or_replay_completed_actions():
    run_page(r"""
 await ready();
 const originalFetch=globalThis.fetch;let release;let stateRequests=0;
 globalThis.fetch=async(path,options)=>{
   if(path==='/api/state'){
     stateRequests++;
     const captured=structuredClone(servedState);
     return new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>captured});});
   }
   return originalFetch(path,options);
 };
 servedState.action={name:'save',running:true,error:null};
 const first=refresh();poll();poll();
 assert.equal(stateRequests,1,'Polling overlapped an active manual refresh');
 release();await first;
 globalThis.fetch=originalFetch;
 servedState.action={name:'save',running:false,error:null,result:{record_file:'saved'}};
 await poll();addRegion([10,10]);const before=JSON.stringify(regions);
 await poll();
 assert.equal(dirty,true);assert.equal(JSON.stringify(regions),before);
 """)


def test_failed_poll_releases_refresh_guard_for_the_next_poll():
    run_page(r"""
 await ready();const originalFetch=globalThis.fetch;let reject;let calls=0;
 globalThis.fetch=(path,options)=>path==='/api/state'?(calls++,new Promise((resolve,rejectRequest)=>{reject=rejectRequest;})):originalFetch(path,options);
 const first=poll();poll();assert.equal(calls,1);
 reject(Error('Synthetic state failure'));await first;
 assert.equal($('message').textContent,'Synthetic state failure');
 globalThis.fetch=originalFetch;await poll();
 assert.equal(authoringBusy(),false);addRegion([10,10]);assert.equal(regions.length,1);
 """)
