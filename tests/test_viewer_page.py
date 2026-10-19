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
