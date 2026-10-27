"""Execute shipped page handlers with controlled DOM/transport boundaries.

These behavioral transition checks complement actual-browser evidence; they do
not substitute for browser rendering, accessibility or human photographic review.
"""

import json
import subprocess
from pathlib import Path

import pytest

PRELUDE = r"""
const assert = require('node:assert/strict');
const nodes = new Map();
const context = new Proxy({}, {get: () => () => {}});
function makeNode(id = '') {
  return {id, value:'', checked:false, disabled:false, textContent:'', options:[], files:[],
    click(){if(this.onclick)return this.onclick();},
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
 developed_id:'master',working_revision:'rev-001',accepted_revision:'rev-001',
 inputs_digest:'draft',authoring_digest:'author',dimensions_wh:[100,100],
 recipe:{groups:[]},guides:{regions:[]},
 revisions:[{revision:'rev-001',kind:'matte',draft_digest:'draft',final_acceptable:true,candidates:[],revision_manifest_sha256:'a'.repeat(64)}],
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


APPEARANCE_SETUP = r"""
const appearanceValue={schema_version:1,kind:'appearance-recipe',name:'<img> saved source',reference:null,
 sections:{shadow_fade:{amount:.38,preserve_highlights:.7},local_exposure:{ev:1.25},
 color_cleanup:{strength:.45},background:{color_srgb:'#14283C',variation:.125},
 shading:{width_subject_fraction:.0125,direction_degrees:37,opacity:.4}}};
const appearanceConverted={shadow_fade:{amount:.38,preserve_highlights:.7},local_exposure:{ev:1.25},
 color_cleanup:{strength:.45},background:{color_srgb:'#14283C',variation:.125},
 shading:{width_px:1.25,direction_degrees:37,opacity:.4}};
const recipeRequests=[];let holdRecipeReply=null, recipeReplyGate=null;
const originalAppearanceFetch=fetch;
globalThis.fetch=async(path,options)=>{
 if(path.startsWith('/api/appearance-recipe-')){
  const data=JSON.parse(options.body);recipeRequests.push({path,data});
  const result={...data,working_revision:servedState.working_revision,
   inputs_digest:servedState.inputs_digest,authoring_digest:servedState.authoring_digest,
   recipe:structuredClone(appearanceValue),sections:structuredClone(appearanceConverted),unavailable:{},
   recipe_json:JSON.stringify(appearanceValue)};
  if(recipeReplyGate)await recipeReplyGate;
  return {ok:true,json:async()=>result};
 }
 return originalAppearanceFetch(path,options);
};
function appearanceFile(text=JSON.stringify(appearanceValue)){
 const bytes=new TextEncoder().encode(text);return {size:bytes.length,arrayBuffer:async()=>bytes.buffer};
}
function advanceAppearanceRevision(extra={}){
 const previous=servedState.working_revision;
 const next='rev-'+String(Number(previous.slice(4))+1).padStart(3,'0');
 servedState.working_revision=next;servedState.inputs_digest+='-next';
 servedState.revisions.push({...structuredClone(servedState.revisions.at(-1)),...extra,
  revision:next,revision_manifest_sha256:String(servedState.revisions.length+1).repeat(64)});
 return {previous,next};
}
"""


LAYOUT_SETUP = (
    APPEARANCE_SETUP
    + r"""
appearanceValue.schema_version=2;
appearanceValue.sections={spatial_layout:{preserve_highlights:.7,arcs_enabled:false,
 oval:{enabled:false,center_subject_xy:[.25,-.2],inner_radii_subject_xy:[.2,.1],rotation_degrees:37,transition_subject_fraction:.075,amount:.6},
 arcs:[{enabled:true,center_subject_xy:[.25,-.2],rotation_degrees:37,transition_subject_fraction:.075,amount:.4,
 half_span_subject_fraction:.3,bend_subject_fraction:-.1,end_softness_subject_fraction:.02,fade_side:'negative'}]},
 local_exposure:{ev:1.25}};
for(const key of Object.keys(appearanceConverted))delete appearanceConverted[key];
appearanceConverted.local_exposure={ev:1.25};
const layoutRequests=[];let layoutReplyGate=null, releaseLayoutReply, nextLayoutId=10;
const layoutFetch=fetch;
globalThis.fetch=async(path,options)=>{
 const data=options.body?JSON.parse(options.body):null;
 if(path==='/api/appearance-layout-preview'){
  layoutRequests.push(data);
  const arc={id:'00000000-0000-4000-8000-'+String(++nextLayoutId).padStart(12,'0'),enabled:false,
   center_xy:[75,30],rotation_degrees:37,transition_width:7.5,amount:.4,half_span:30,bend:-10,end_softness:2,fade_side:'negative'};
  const proposal=data.mode==='replace'?{enabled:data.spatial_draft.enabled,preserve_highlights:.7,arcs_enabled:false,
   oval:{enabled:false,center_xy:[75,30],inner_radii_xy:[20,10],rotation_degrees:37,transition_width:7.5,amount:.6},
   arcs:[{...arc,enabled:true}]}:{...structuredClone(data.spatial_draft),arcs:[...structuredClone(data.spatial_draft.arcs),arc]};
  const result={spatial_fade:proposal,warnings:data.mode==='add_arcs'?['Target arc group is OFF']:[],
   developed_id:data.developed_id,revision:data.revision,working_revision:data.revision,
   revision_manifest_sha256:data.revision_manifest_sha256,inputs_digest:data.inputs_digest,
   authoring_digest:data.authoring_digest,spatial_draft_version:data.spatial_draft_version,mode:data.mode};
  if(layoutReplyGate)await layoutReplyGate;
  return {ok:true,json:async()=>result};
 }
 const response=await layoutFetch(path,options);
 if(path==='/api/appearance-recipe-validate'&&data.layout_defaults_shape!==undefined){
  const result=await response.json();result.sections={local_exposure:{ev:1.25},spatial_fade:{transition_width:7.5,
   amount:data.layout_defaults_shape==='oval'?.6:.4,preserve_highlights:.7}};
  return {ok:true,json:async()=>result};
 }
 return response;
};
async function readyLayout(){
 await ready();addSpatialArc();spatialDraft.arcs_enabled=false;markSpatialDirty();
 $('spatialCandidate').checked=true;$('spatialProtection').value='draft/protected.png';
 for(const [index,target] of ['spatial_fade','shadow_fade'].entries())fadeReductionDrafts.set(target,{
  area:{schema_version:1,regions:[{shape:{id:'kept-'+target,role:'support',shape:'rectangle',xyxy:[10,20,30,40],feather_px:0},amount:.4}]},
  version:index+3,identity:spatialCurrentIdentity(),dirty:true});
 $('reductionTarget').value='spatial_fade';$('reductionAmount').value='37.50';$('reductionRadius').value='9';
 $('reductionFeather').value='0';$('reductionRectangle').value='10,20,30,40';$('reductionCandidate').checked=true;
 selectedReductionId='kept-spatial_fade';$('reductionSelect').value=selectedReductionId;
 $('exposureEV').value='1.8';$('exposureEV').oninput();
 await loadAppearanceRecipeFile(appearanceFile());$('appearanceLayoutMode').value='replace';
}
function layoutSnapshot(){return JSON.stringify({draft:spatialDraft,dirty:spatialDirty,binding:spatialDraftIdentity,
 selected:selectedSpatialId,candidate:$('spatialCandidate').checked,protection:$('spatialProtection').value,
 authorMode:$('authorMode').value,reductions:[...fadeReductionDrafts],selectedReductionId,
 reductionControls:['reductionTarget','reductionShape','reductionRadius','reductionFeather','reductionAmount','reductionRectangle','reductionSelect','reductionView'].map(id=>[id,$(id).value]),
 reductionCandidate:$('reductionCandidate').checked,exposure:$('exposureEV').value,exposureDirty:exposureControlsVersion});}
"""
)


@pytest.mark.parametrize("spatial_dirty", [False, True])
@pytest.mark.parametrize("reduction_state", ["absent", "clean", "dirty"])
def test_appearance_layout_survives_unchanged_poll_and_rejects_changed_binding(
    spatial_dirty, reduction_state
):
    run_page(
        LAYOUT_SETUP
        + f"\nconst spatialInitiallyDirty={json.dumps(spatial_dirty)}, reductionState={json.dumps(reduction_state)};\n"
        + r"""
 await readyLayout();
 servedState.revisions[0].spatial_fade={enabled:spatialDraft.enabled,settings:structuredClone(spatialDraft)};
 spatialDirty=spatialInitiallyDirty;
 if(reductionState==='absent')fadeReductionDrafts.clear();
 else {
  servedState.revisions[0].fade_reduction_areas=Object.fromEntries([...fadeReductionDrafts].map(([target,draft])=>[target,structuredClone(draft.area)]));
  for(const draft of fadeReductionDrafts.values())draft.dirty=reductionState==='dirty';
 }
 await refresh(false);
 const before=layoutSnapshot(), version=spatialDraftVersion;
 await previewAppearanceLayout('replace');assert(appearanceLayoutProposal);
 await refresh(false);
 assert(appearanceLayoutProposal,'Unchanged polling discarded the placement proposal');
 assert.equal(layoutSnapshot(),before);assert.equal(spatialDraftVersion,version);
 await loadAppearanceLayout();assert(appearanceLayoutUndo);
 await refresh(false);assert(appearanceLayoutUndo,'Unchanged polling discarded import Undo');
 undoAppearanceLayoutImport();assert.equal(layoutSnapshot(),before);
 await previewAppearanceLayout('replace');assert(appearanceLayoutProposal);
 servedState.revisions[0].revision_manifest_sha256='f'.repeat(64);
 await refresh(false);assert.equal(appearanceLayoutProposal,null);
 assert.equal(appearanceLayoutUndo,null);
 """
    )


def test_appearance_layout_preview_cancel_and_guarded_undo_preserve_exact_drafts():
    run_page(
        LAYOUT_SETUP
        + r"""
 await readyLayout();const before=layoutSnapshot(),version=spatialDraftVersion;
 await previewAppearanceLayout('replace');
 assert(appearanceLayoutProposal);assert.equal(layoutSnapshot(),before);assert.equal(spatialDraftVersion,version);
 assert($('appearanceLayoutStatus').textContent.includes('Placement preview — effects not applied'));
 cancelAppearanceLayout();assert.equal(appearanceLayoutProposal,null);assert.equal(layoutSnapshot(),before);
 assert.equal(spatialDraftVersion,version);assert.equal(posts.length,0);
 await previewAppearanceLayout('replace');let confirmed='';globalThis.confirm=text=>{confirmed=text;return false;};
 await loadAppearanceLayout();assert(confirmed.includes('Replace'));assert.equal(layoutSnapshot(),before);
 globalThis.confirm=()=>true;await loadAppearanceLayout();
 assert.equal(spatialDraftVersion,version+1);assert.equal(spatialDraft.enabled,false);
 assert.deepEqual(spatialDraft.oval.center_xy,[75,30]);assert.equal($('spatialProtection').value,'draft/protected.png');
 assert.equal([...fadeReductionDrafts][0][1].version,3);assert.equal($('reductionAmount').value,'37.50');
 assert.equal(posts.length,0);assert(appearanceLayoutUndo);
 undoAppearanceLayoutImport();assert.equal(layoutSnapshot(),before);assert.equal(spatialDraftVersion,version+2);
 assert.equal(appearanceLayoutUndo,null);assert.equal(posts.length,0);
 """
    )


def test_appearance_layout_add_preserves_group_and_existing_ids_then_native_apply():
    run_page(
        LAYOUT_SETUP
        + r"""
 await readyLayout();$('appearanceLayoutMode').value='add_arcs';
 const existing=structuredClone(spatialDraft),reductions=JSON.stringify([...fadeReductionDrafts]);
 await previewAppearanceLayout('add_arcs');await loadAppearanceLayout();
 assert.equal(spatialDraft.arcs_enabled,false);assert.deepEqual(spatialDraft.oval,existing.oval);
 assert.equal(spatialDraft.preserve_highlights,existing.preserve_highlights);
 assert.deepEqual(spatialDraft.arcs.slice(0,-1),existing.arcs);assert.equal(spatialDraft.arcs.at(-1).enabled,false);
 assert.equal(JSON.stringify([...fadeReductionDrafts]),reductions);
 $('spatialStrength').value='65';$('spatialStrength').oninput();assert.equal(appearanceLayoutUndo,null);
 await applySpatial();assert.equal(posts.length,1);assert.equal(posts[0].spatial_fade.arcs.at(-1).amount,.65);
 assert.equal(posts[0].spatial_fade.arcs_enabled,false);assert.equal(appearanceLayoutUndo,null);
 """
    )


def test_appearance_layout_replace_confirms_clean_draft_and_second_load_replaces_undo():
    run_page(
        LAYOUT_SETUP
        + r"""
 await readyLayout();spatialDirty=false;let confirmations=0;globalThis.confirm=()=>{confirmations++;return true;};
 await previewAppearanceLayout('replace');await loadAppearanceLayout();assert.equal(confirmations,1);
 const afterFirst=layoutSnapshot(),version=spatialDraftVersion;
 await previewAppearanceLayout('replace');assert.equal(appearanceLayoutUndo,null);
 await loadAppearanceLayout();assert.equal(confirmations,2);assert.equal(spatialDraftVersion,version+1);
 undoAppearanceLayoutImport();assert.equal(layoutSnapshot(),afterFirst);assert.equal(spatialDraftVersion,version+2);
 """
    )


@pytest.mark.parametrize(
    "change",
    [
        "spatial",
        "reduction",
        "raw-control",
        "selection",
        "mode",
        "authoring",
        "file",
        "apply",
        "disable",
        "reset",
    ],
)
def test_appearance_layout_late_preview_and_undo_cannot_overwrite_independent_changes(change):
    run_page(
        LAYOUT_SETUP
        + f"const change={change!r};"
        + r"""
 await readyLayout();await previewAppearanceLayout('replace');await loadAppearanceLayout();assert(appearanceLayoutUndo);
 async function edit(){
  if(change==='spatial'){$('spatialCenterX').value='44';$('spatialCenterX').oninput();}
  else if(change==='reduction'){fadeReductionDrafts.get('shadow_fade').version++;markFadeReductionDirty();}
  else if(change==='raw-control'){$('reductionRectangle').value='20,20,50,50';$('reductionRectangle').oninput();}
  else if(change==='selection'){$('spatialSelect').value='oval';$('spatialSelect').onchange();}
  else if(change==='mode'){$('appearanceLayoutMode').value='add_arcs';$('appearanceLayoutMode').onchange();}
  else if(change==='authoring'){state.authoring_digest+='changed';}
  else if(change==='file'){await loadAppearanceRecipeFile(appearanceFile());}
  else if(change==='apply'){await applySpatial();}
  else if(change==='disable'){await $('spatialDisable').onclick();}
  else resetSpatialFromSaved();
 }
 await edit();const edited=layoutSnapshot();
 assert.throws(()=>undoAppearanceLayoutImport(),/unavailable|changed|Undo|undo/i);
 assert.equal(layoutSnapshot(),edited);
 // A separate pending preview is bound to the same independent change classes.
 await readyLayout();layoutReplyGate=new Promise(resolve=>releaseLayoutReply=resolve);
 const pending=previewAppearanceLayout('replace');await Promise.resolve();await edit();
 const newer=layoutSnapshot();releaseLayoutReply();await pending;
 assert.equal(appearanceLayoutProposal,null);assert.equal(layoutSnapshot(),newer);
 """
    )


def test_appearance_layout_late_replace_confirmation_and_active_placement_do_not_load():
    run_page(
        LAYOUT_SETUP
        + r"""
 await readyLayout();await previewAppearanceLayout('replace');let answer;
 globalThis.confirm=()=>new Promise(resolve=>answer=resolve);
 const pending=loadAppearanceLayout();await Promise.resolve();
 $('reductionCandidate').checked=false;$('reductionCandidate').oninput();const newer=layoutSnapshot();
 answer(true);await pending;assert.equal(layoutSnapshot(),newer);assert.equal(appearanceLayoutUndo,null);
 globalThis.confirm=()=>true;await previewAppearanceLayout('replace');spatialAdding=true;
 await assert.rejects(loadAppearanceLayout(),/placement|gesture|finish/i);
 assert.equal(layoutSnapshot(),newer);
 """
    )


def test_appearance_layout_settings_only_fallback_preserves_file_geometry_and_switches():
    run_page(
        LAYOUT_SETUP
        + r"""
 await readyLayout();const recipe=JSON.stringify(appearanceRecipePreview.recipe),old=structuredClone(spatialDraft);
 $('appearanceTargetShape').value=selectedSpatialId;$('appearanceLayoutDefaultsShape').value='0';
 await loadAppearanceLayoutSettingsOnly();
 assert.equal(recipeRequests.at(-1).data.layout_defaults_shape,0);
 assert.equal(JSON.stringify(appearanceRecipePreview.recipe),recipe);
 const selected=spatialDraft.arcs.find(arc=>arc.id===selectedSpatialId);
 assert.equal(selected.transition_width,7.5);assert.equal(selected.amount,.4);
 const previous=old.arcs.find(arc=>arc.id===selectedSpatialId);
 assert.deepEqual(selected.center_xy,previous.center_xy);assert.equal(selected.enabled,previous.enabled);
 assert.equal(spatialDraft.arcs_enabled,old.arcs_enabled);assert.deepEqual(spatialDraft.oval,old.oval);
 assert.equal(spatialDraft.preserve_highlights,.7);assert.equal(posts.length,0);
 spatialDraftIdentity='older';await assert.rejects(loadAppearanceLayoutSettingsOnly(),/Stale/);
 """
    )


def test_appearance_layout_save_selection_is_explicit_and_exclusive():
    run_page(
        LAYOUT_SETUP
        + r"""
 await readyLayout();servedState.revisions[0].spatial_fade={enabled:false,settings:structuredClone(spatialDraft)};
 await refresh();$('appearanceSource').value='rev-001';syncAppearanceSource();
 assert.equal($('appearanceSave-spatial_layout').checked,false);
 $('appearanceSaveName').value='Saved layout';$('appearanceSave-spatial_layout').checked=true;
 const request=appearanceSaveRequest();assert.deepEqual(request.sections,['spatial_layout']);assert.equal(request.reference_shape_id,null);
 $('appearanceSave-spatial_fade').checked=true;assert.throws(appearanceSaveRequest,/at most one|exclusive/);
 """
    )


def test_appearance_recipe_loads_selected_scalars_without_geometry_or_jobs():
    run_page(
        APPEARANCE_SETUP
        + r"""
 await ready();
 const reductions={schema_version:1,regions:[{shape:{id:'protected',role:'support',shape:'rectangle',xyxy:[0,0,10,10],feather_px:0},amount:.5}]};
 fadeReductionDrafts.set('spatial_fade',{area:structuredClone(reductions),identity:'older',version:3,dirty:true});
 fadeReductionDrafts.set('shadow_fade',{area:structuredClone(reductions),identity:'older',version:4,dirty:true});
 const before=JSON.stringify({groups,regions,identity,exposureArea,fadeArea,spatialDraft,
  reductions:[...fadeReductionDrafts],accepted:state.accepted_revision});
 await loadAppearanceRecipeFile(appearanceFile());
 assert.equal($('appearanceName').textContent,'<img> saved source');
 for(const section of ['background','local_exposure','color_cleanup'])assert.equal($('appearanceLoad-'+section).checked,false);
 await loadAppearanceRecipeSections(['shadow_fade','local_exposure','shading']);
 assert.equal(Number($('fadeAmount').value),38);assert.equal(Number($('exposureEV').value),1.25);
 assert.equal(Number($('shadingWidth').value),1.25);assert.equal(Number($('shadingDirection').value),37);
 assert.equal(posts.length,0);assert.equal(Number($('backgroundVariation').value),0);
 assert.equal(JSON.stringify({groups,regions,identity,exposureArea,fadeArea,spatialDraft,
  reductions:[...fadeReductionDrafts],accepted:state.accepted_revision}),before);
 const old=$('exposureEV').value;$('exposureEV').value='2';$('exposureEV').oninput();
 let prompt='';globalThis.confirm=text=>{prompt=text;return false;};
 await loadAppearanceRecipeSections(['local_exposure']);
 assert(prompt.includes('Local exposure'));assert.equal($('exposureEV').value,'2');assert.notEqual(old,'2');
 """
    )


@pytest.mark.parametrize(
    "fraction,percentage",
    [(0, "0"), (0.29, "29"), (0.55, "55"), (0.07, "7"), (0.125, "12.5"), (1, "100")],
)
def test_appearance_shadow_percentages_display_cleanly_and_apply_unchanged(fraction, percentage):
    run_page(
        APPEARANCE_SETUP
        + f"const fraction={fraction!r},percentage={json.dumps(percentage)};"
        + r"""
 appearanceValue.sections.shadow_fade={amount:fraction,preserve_highlights:fraction};
 appearanceConverted.shadow_fade={amount:fraction,preserve_highlights:fraction};
 await ready();await loadAppearanceRecipeFile(appearanceFile());
 await loadAppearanceRecipeSections(['shadow_fade']);
 for(const field of ['fadeAmount','fadeRange','fadePreserve','fadePreserveRange'])
  assert.equal(String($(field).value),percentage);
 assert.equal(posts.length,0);
 await $('fadeAmountApply').onclick();
 assert.deepEqual(posts.at(-1).shadow_fade,{enabled:true,amount:fraction,preserve_highlights:fraction});
 """
    )


@pytest.mark.parametrize("section", ["shading", "shadow_fade", "spatial_fade"])
def test_appearance_summaries_display_clean_percentages(section):
    run_page(
        APPEARANCE_SETUP
        + f"const section={json.dumps(section)};"
        + r"""
 appearanceValue.sections={
  [section]:section==='shading'?{width_subject_fraction:.0125,direction_degrees:37,opacity:.29}
   :{amount:.55,preserve_highlights:.07,...(section==='spatial_fade'?{transition_subject_fraction:.02}:{})}};
 for(const key of Object.keys(appearanceConverted))delete appearanceConverted[key];
 appearanceConverted[section]=section==='shading'?{width_px:1.25,direction_degrees:37,opacity:.29}
  :{amount:.55,preserve_highlights:.07,...(section==='spatial_fade'?{transition_width:2}:{})};
 await ready();await loadAppearanceRecipeFile(appearanceFile());
 const percentages=$('appearanceValues-'+section).textContent.match(/[\d.]+%/g);
 assert.deepEqual(percentages,section==='shading'?['29%']:['55%','7%']);
 """
    )


def test_appearance_fractional_background_survives_load_and_colour_edit():
    run_page(
        APPEARANCE_SETUP
        + r"""
 await ready();servedState.revisions[0].background={settings:{color_srgb:'#14283C',variation:.125}};
 await refresh(true);assert.equal(Number($('backgroundVariation').value),12.5);
 await loadAppearanceRecipeFile(appearanceFile());await loadAppearanceRecipeSections(['background']);
 assert.equal(Number($('backgroundVariation').value),12.5);
 $('backgroundHex').value='#445566';$('backgroundHex').oninput();
 await $('backgroundApply').onclick();assert.deepEqual(posts.at(-1).background,{color_srgb:'#445566',variation:.125});
 assert.equal(Number($('backgroundVariation').value),12.5);
 """
    )


@pytest.mark.parametrize(
    "prefix,section", [("exposure", "local_exposure"), ("fade", "shadow_fade")]
)
def test_appearance_scalar_reload_never_rebinds_stale_area(prefix, section):
    run_page(
        APPEARANCE_SETUP
        + f"const prefix={prefix!r},section={section!r};"
        + r"""
 await ready();$(prefix+'Role').value='protection';$(prefix+'Feather').value='0';
 $(prefix+'Rectangle').value='10,20,30,40';await $(prefix+'AddRectangle').onclick();
 const originalArea=JSON.stringify(prefix==='exposure'?exposureArea:fadeArea);
 await loadAppearanceRecipeFile(appearanceFile());
 const {previous,next}=advanceAppearanceRevision();servedState.action={running:false,name:'effects',error:null,result:{parent:previous,revision:next}};
 actionWasRunning=true;await refresh();
 await reloadAppearanceRecipeSection(section);
 assert.equal(prefix==='exposure'?exposureControlsStale():fadeControlsStale(),false);
 assert(effectAreaDraftStale(prefix));
 const count=posts.length;await $(prefix+'Apply').onclick();assert.equal(posts.length,count);
 assert($('message').textContent.toLowerCase().includes('stale'));
 await $(prefix==='exposure'?'exposureAmount':'fadeAmountApply').onclick();
 assert.equal(posts.length,count+1);assert.equal(posts.at(-1).base_revision,next);
 assert(!('exposure_area' in posts.at(-1)));assert(!('shadow_fade_area' in posts.at(-1)));
 assert.equal(JSON.stringify(prefix==='exposure'?exposureArea:fadeArea),originalArea);
 assert(prefix==='exposure'?exposureDirty:fadeDirty);
 await $(prefix+'ReloadArea').onclick();assert(!effectAreaDraftStale(prefix));
 assert.equal(prefix==='exposure'?exposureDirty:fadeDirty,false);
 """
    )


@pytest.mark.parametrize(
    "section,field,new_value",
    [
        ("local_exposure", "exposureEV", "2"),
        ("shadow_fade", "fadeAmount", "80"),
        ("shading", "shadingWidth", "4"),
        ("color_cleanup", "cleanupStrength", ".8"),
        ("background", "backgroundVariation", "17.5"),
    ],
)
@pytest.mark.parametrize("reused", [False, True])
def test_appearance_late_apply_keeps_newer_scalar_edits(section, field, new_value, reused):
    run_page(
        APPEARANCE_SETUP
        + f"const section={section!r},field={field!r},newValue={new_value!r},reused={str(reused).lower()};"
        + r"""
 if(reused){const settings={...(section==='background'?{}:{enabled:true}),...appearanceConverted[section]};
  servedState.revisions[0][section]=section==='color_cleanup'?{...settings,stale:false}:{enabled:settings.enabled,stale:false,settings};}
 await ready();await loadAppearanceRecipeFile(appearanceFile());await loadAppearanceRecipeSections([section]);
 const original=fetch;
 globalThis.fetch=async(path,options)=>{if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return original(path,options);};
 const button={local_exposure:'exposureAmount',shadow_fade:'fadeAmountApply',shading:'shadingOpacityApply',color_cleanup:'cleanupApply',background:'backgroundApply'}[section];
 await $(button).onclick();assert.equal(posts.length,1,$('message').textContent);
 $(field).value=newValue;$(field).oninput();
 const sent=posts[0][section],record=section==='color_cleanup'?{...sent,stale:false}:{enabled:sent.enabled,stale:false,settings:sent};
 const {previous,next}=reused?{previous:servedState.working_revision,next:servedState.working_revision}:advanceAppearanceRevision({[section]:record});
 if(reused)assert.deepEqual(section==='color_cleanup'?{enabled:record.enabled,strength:record.strength}:servedState.revisions[0][section].settings,sent);
 servedState.action={running:false,name:'effects',error:null,result:{parent:previous,revision:next,reused,[section]:record}};
 await refresh();assert.equal($(field).value,newValue);assert(appearanceScalarState(section).dirty);
 assert.equal(appearanceScalarStale(section),!reused);assert(appearanceRecipePreview);
 """
    )


@pytest.mark.parametrize(
    "enabled,strength,reused",
    [(True, 0.8, False), (False, 0.8, False), (False, 0, False), (True, 0.45, True)],
)
def test_appearance_cleanup_uses_actual_saved_snapshot_and_completion(
    tmp_path, enabled, strength, reused
):
    from test_effects import effect_request, fixture_project

    from blackmask import operations
    from blackmask.viewer import ReviewServer

    project, _, _ = fixture_project(tmp_path)
    with ReviewServer(project) as server:
        empty = server.snapshot()
        operations.apply_operation(
            project,
            effect_request(project, enabled=enabled, strength=strength, candidate_comparison=True),
        )
        initial = server.snapshot()
        completed = operations.apply_operation(
            project, effect_request(project, strength=0.45, candidate_comparison=True)
        )
        assert completed["reused"] is reused
        server.action = {"running": False, "name": "effects", "error": None, "result": completed}
        settled = server.snapshot()
    run_page(
        APPEARANCE_SETUP
        + "const savedCleanupEvidence="
        + json.dumps(
            {
                "empty": empty,
                "initial": initial,
                "settled": settled,
                "enabled": enabled,
                "strength": strength,
            }
        )
        + ";"
        + r"""
 Object.assign(servedState,savedCleanupEvidence.empty);await ready();
 assert($('appearanceSave-color_cleanup').disabled);
 Object.assign(servedState,savedCleanupEvidence.initial);await refresh(true);
 $('appearanceSource').value=state.working_revision;syncAppearanceSource();
 assert.equal(Number($('cleanupStrength').value),savedCleanupEvidence.strength);
 assert.equal($('appearanceSave-color_cleanup').disabled,false);
 assert.equal($('appearanceSave-color_cleanup').checked,false);
 assert($('appearanceSaved-color_cleanup').textContent.includes(savedCleanupEvidence.enabled?'ON':'OFF'));
 const downloads=[];URL.createObjectURL=()=> 'blob:cleanup';URL.revokeObjectURL=()=>{};
 globalThis.setTimeout=()=>0;
 const create=document.createElement;document.createElement=tag=>{const node=create(tag);if(tag==='a')node.click=()=>downloads.push(node.download);return node;};
 $('appearanceSaveName').value='Saved cleanup';$('appearanceSave-color_cleanup').checked=true;
 await saveAppearanceRecipe();assert.equal(downloads.length,1);assert.deepEqual(recipeRequests.at(-1).data.sections,['color_cleanup']);
 await loadAppearanceRecipeFile(appearanceFile());await loadAppearanceRecipeSections(['color_cleanup']);
 assert.equal(Number($('cleanupStrength').value),.45);assert(appearanceScalarState('color_cleanup').dirty);
 $('cleanupCandidate').checked=true;$('cleanupCandidate').oninput();
 const original=fetch;globalThis.fetch=async(path,options)=>{
  if(path==='/api/action')Object.assign(servedState,structuredClone(savedCleanupEvidence.settled));
  return original(path,options);
 };
 await $('cleanupApply').onclick();assert.equal(posts.length,1,$('message').textContent);
 assert.deepEqual(posts[0].color_cleanup,{enabled:true,strength:.45});
 assert.equal(state.working_revision,savedCleanupEvidence.settled.working_revision);
 assert.equal(Number($('cleanupStrength').value),.45);assert(!appearanceScalarState('color_cleanup').dirty);
 assert(!appearanceScalarStale('color_cleanup'));assert(appearanceRecipePreview);
 await refresh(true);assert.equal(Number($('cleanupStrength').value),.45);
 """
    )


def test_appearance_spatial_defaults_require_current_explicit_shape():
    run_page(
        APPEARANCE_SETUP
        + r"""
 await ready();appearanceValue.sections={spatial_fade:{transition_subject_fraction:.02,amount:.4,preserve_highlights:.7}};
 for(const key of Object.keys(appearanceConverted))delete appearanceConverted[key];
 appearanceConverted.spatial_fade={transition_width:2,amount:.4,preserve_highlights:.7};
 await loadAppearanceRecipeFile(appearanceFile());const before=JSON.stringify(spatialDraft);
 await assert.rejects(()=>loadAppearanceRecipeSections(['spatial_fade']),/select|choose/i);
 assert.equal(JSON.stringify(spatialDraft),before);assert(appearanceRecipePreview);
 $('appearanceTargetShape').value='oval';$('appearanceTargetShape').onchange();
 const oldIdentity=spatialDraftIdentity;await loadAppearanceRecipeSections(['spatial_fade']);
 assert.equal(spatialDraft.oval.transition_width,2);assert.equal(spatialDraft.oval.amount,.4);
 assert.equal(spatialDraft.preserve_highlights,.7);assert.equal(spatialDraft.enabled,false);
 assert.equal(spatialDraftIdentity,oldIdentity);assert.deepEqual(spatialDraft.arcs,[]);
 advanceAppearanceRevision();await refresh();
 await assert.rejects(()=>reloadAppearanceRecipeSection('spatial_fade'),/stale/i);
 assert.equal(spatialDraftIdentity,oldIdentity);
 """
    )


def test_appearance_late_import_and_confirmation_cannot_replace_newer_work():
    run_page(
        APPEARANCE_SETUP
        + r"""
 await ready();await loadAppearanceRecipeFile(appearanceFile());
 const retained=appearanceRecipePreview;
 recipeReplyGate=new Promise(resolve=>holdRecipeReply=resolve);
 const pending=loadAppearanceRecipeFile(appearanceFile());await Promise.resolve();await Promise.resolve();
 $('exposureEV').value='2';$('exposureEV').oninput();holdRecipeReply();await pending;
 assert.equal(appearanceRecipePreview,retained);assert.equal($('exposureEV').value,'2');recipeReplyGate=null;
 let resolveConfirmation;globalThis.confirm=()=>new Promise(resolve=>resolveConfirmation=resolve);
 const loading=loadAppearanceRecipeSections(['local_exposure']);
 for(let i=0;i<20&&!resolveConfirmation;i++)await Promise.resolve();assert(resolveConfirmation);
 $('exposureEV').value='2.5';$('exposureEV').oninput();resolveConfirmation(true);await loading;
 assert.equal($('exposureEV').value,'2.5');
 let reads=0;await assert.rejects(()=>loadAppearanceRecipeFile({size:1572865,arrayBuffer:async()=>{reads++;return new ArrayBuffer(0);}}));assert.equal(reads,0);
 await assert.rejects(()=>loadAppearanceRecipeFile({size:1,arrayBuffer:async()=>new Uint8Array([255]).buffer}));
 """
    )


def test_appearance_sequential_apply_requires_explicit_remaining_section_reload():
    run_page(
        APPEARANCE_SETUP
        + r"""
 await ready();await loadAppearanceRecipeFile(appearanceFile());
 await loadAppearanceRecipeSections(['shadow_fade','local_exposure','shading']);
 const preview=appearanceRecipePreview,original=fetch;
 globalThis.fetch=async(path,options)=>{
  if(path==='/api/action'){
   const sent=JSON.parse(options.body),section=['shadow_fade','local_exposure','shading'].find(key=>key in sent);
   const record={enabled:sent[section].enabled,stale:false,settings:sent[section]};
   const {previous,next}=advanceAppearanceRevision({[section]:record});
   servedState.action={running:false,name:'effects',error:null,result:{parent:previous,revision:next,[section]:record}};
  }
  return original(path,options);
 };
 for(const [index,[section,button]] of [['shadow_fade','fadeAmountApply'],['local_exposure','exposureAmount'],['shading','shadingOpacityApply']].entries()){
  if(index){assert(appearanceScalarStale(section));const before=posts.length;
   await $(button).onclick();assert.equal(posts.length,before);
   await $('appearanceReload-'+section).onclick();assert(!appearanceScalarStale(section));}
  await $(button).onclick();assert.equal(posts.length,index+1,$('message').textContent);
  assert.equal(appearanceRecipePreview,preview);assert(!appearanceScalarState(section).dirty);
 }
 assert.equal(state.working_revision,'rev-004');assert.equal(Number($('shadingWidth').value),1.25);
 assert.equal(state.accepted_revision,'rev-001');
 """
    )


@pytest.mark.parametrize("prefix", ["exposure", "fade"])
@pytest.mark.parametrize("completion", ["success", "error", "other-action"])
def test_appearance_newer_area_survives_older_completion(prefix, completion):
    run_page(
        APPEARANCE_SETUP
        + f"const prefix={prefix!r},completion={completion!r};"
        + r"""
 await ready();$(prefix+'Role').value='regions';$(prefix+'Feather').value='0';
 $(prefix+'Rectangle').value='10,20,30,40';await $(prefix+'AddRectangle').onclick();
 const original=fetch;globalThis.fetch=async(path,options)=>{
  if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};
  return original(path,options);};
 await $(prefix+'Apply').onclick();assert.equal(posts.length,1,$('message').textContent);
 const area=prefix==='exposure'?exposureArea:fadeArea;
 area.protection.push({id:'new-protection',role:'protection',shape:'rectangle',xyxy:[40,40,50,50],feather_px:0});
 markEffectAreaDirty(prefix);const newer=JSON.stringify(area),version=effectAreaVersions[prefix];
 const key=prefix==='exposure'?'exposure_area':'shadow_fade_area';
 const section=prefix==='exposure'?'local_exposure':'shadow_fade',sent=posts[0];
 const record={enabled:true,stale:false,settings:sent[section]};
 const {previous,next}=advanceAppearanceRevision({[key]:sent[key],[section]:record});
 servedState.action={running:false,name:completion==='other-action'?'export':'effects',
  error:completion==='error'?'synthetic failure':null,result:{parent:previous,revision:next,[section]:record}};
 await refresh();assert.equal(JSON.stringify(prefix==='exposure'?exposureArea:fadeArea),newer);
 assert.equal(effectAreaVersions[prefix],version);assert(prefix==='exposure'?exposureDirty:fadeDirty);
 assert(effectAreaDraftStale(prefix));
 globalThis.confirm=()=>false;await $(prefix+'ReloadArea').onclick();
 assert.equal(JSON.stringify(prefix==='exposure'?exposureArea:fadeArea),newer);
 """
    )


@pytest.mark.parametrize(
    "prefix,section,key",
    [("exposure", "local_exposure", "exposure_area"), ("fade", "shadow_fade", "shadow_fade_area")],
)
def test_appearance_same_revision_area_edit_survives_reused_apply(prefix, section, key):
    run_page(
        APPEARANCE_SETUP
        + f"const prefix={prefix!r},section={section!r},key={key!r};"
        + r"""
 const saved={regions:[{id:'saved',role:'support',shape:'rectangle',xyxy:[0,0,10,10],feather_px:0}],protection:[]};
 servedState.revisions[0][key]=structuredClone(saved);
 servedState.revisions[0][section]={enabled:true,stale:false,settings:{enabled:true,...appearanceConverted[section]}};
 await ready();const original=fetch;globalThis.fetch=async(path,options)=>{
  if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return original(path,options);};
 await $(prefix+'Apply').onclick();assert.equal(posts.length,1,$('message').textContent);
 assert.deepEqual(posts[0][key],saved);
 const area=prefix==='exposure'?exposureArea:fadeArea;
 area.protection.push({id:'new',role:'protection',shape:'rectangle',xyxy:[0,0,2,2],feather_px:0});
 markEffectAreaDirty(prefix);const retained=JSON.stringify(area);
 servedState.action={running:false,name:'effects',error:null,result:{revision:'rev-001',reused:true,[section]:servedState.revisions[0][section]}};
 await refresh();assert.equal(JSON.stringify(prefix==='exposure'?exposureArea:fadeArea),retained);
 assert(prefix==='exposure'?exposureDirty:fadeDirty);assert(!effectAreaDraftStale(prefix));
 """
    )


def test_appearance_save_late_reply_and_reference_urls_have_explicit_ownership():
    run_page(
        APPEARANCE_SETUP
        + r"""
 const created=[],revoked=[],downloads=[],timers=[];
 URL.createObjectURL=blob=>{const url='blob:owned-'+created.length;created.push({url,blob});return url;};
 URL.revokeObjectURL=url=>revoked.push(url);globalThis.setTimeout=callback=>timers.push(callback);
 const createElement=document.createElement;document.createElement=tag=>{
  const node=createElement(tag);if(tag==='a')node.click=()=>downloads.push({href:node.href,name:node.download});return node;};
 servedState.revisions[0].background={settings:{color_srgb:'#14283C',variation:.125}};
 await ready();$('appearanceSaveName').value='Old saved look';
 for(const section of ['background','local_exposure','color_cleanup'])assert.equal($('appearanceSave-'+section).checked,false);
 assert.equal($('appearanceIncludeReference').checked,false);
 $('appearanceSave-background').checked=true;
 recipeReplyGate=new Promise(resolve=>holdRecipeReply=resolve);
 const saving=saveAppearanceRecipe();await Promise.resolve();$('appearanceSaveName').value='New name';$('appearanceSaveName').oninput();
 holdRecipeReply();await saving;assert.equal(downloads.length,0);recipeReplyGate=null;
 await saveAppearanceRecipe();assert.equal(downloads.length,1);assert.equal(downloads[0].name,'appearance-recipe.json');
 assert.equal(recipeRequests.at(-1).data.include_reference,false);assert.equal(posts.length,0);
 timers.splice(0).forEach(callback=>callback());assert(revoked.includes(downloads[0].href));
 appearanceValue.reference={mime:'image/png',width:1,height:1,png_base64:'cGl4ZWxz'};
 await loadAppearanceRecipeFile(appearanceFile());const first=appearanceReferenceUrl;
 await loadAppearanceRecipeFile(appearanceFile());const second=appearanceReferenceUrl;
 assert.notEqual(first,second);assert(revoked.includes(first));
 closeAppearanceRecipe();assert(revoked.includes(second));assert.equal(appearanceRecipePreview,null);
 assert.equal($('appearanceReference').src,'');
 """
    )


@pytest.mark.parametrize("fraction", [0, 1, 0.55, 0.12345678901234567, 1e-20])
def test_appearance_background_decimal_roundtrip_and_range_sync(fraction):
    run_page(
        f"const fraction={fraction!r};"
        + r"""
 servedState.revisions[0].background={settings:{color_srgb:'#14283C',variation:fraction}};
 await ready();const percentage=$('backgroundVariation').value;
 $('backgroundColor').value='#334455';$('backgroundColor').oninput();
 await $('backgroundApply').onclick();assert.equal(posts.at(-1).background.variation,fraction);
 assert.equal($('backgroundVariation').value,percentage);
 $('backgroundRange').value='27';$('backgroundRange').oninput();
 assert.equal($('backgroundVariation').value,'27');
 """
    )


@pytest.mark.parametrize("value", ["", "NaN", "Infinity", "-0.01", "100.01", "0x10"])
def test_appearance_background_rejects_invalid_percentage_before_action(value):
    run_page(
        f"const value={value!r};"
        + r"""
 await ready();$('backgroundHex').value='#334455';$('backgroundVariation').value=value;
 await $('backgroundApply').onclick();assert.equal(posts.length,0);assert($('message').textContent.includes('finite'));
 """
    )


def test_fade_reduction_drafts_keep_edits_local_and_bind_explicit_apply():
    run_page(r"""
 await ready();
 servedState.revisions[0].spatial_fade={enabled:true,stale:false,settings:spatialDefaultSettings()};
 servedState.revisions[0].fade_reduction_areas={spatial_fade:{schema_version:1,regions:[]}};
 await refresh(true);
 $('reductionRadius').value='3';$('reductionFeather').value='4';$('reductionAmount').value='50';
 $('reductionRectangle').value='10,20,30,40';
 await $('reductionAddRectangle').onclick();
 const draft=fadeReductionDrafts.get('spatial_fade');
 assert.equal(draft.area.regions.length,1);assert(draft.dirty);assert.equal(posts.length,0);
 const id=draft.area.regions[0].shape.id;
 assert.deepEqual(draft.area.regions[0].shape.xyxy,[10,20,30,40]);
 $('reductionAmount').value='75';$('reductionAmount').oninput();
 assert.equal(draft.area.regions[0].amount,.75);assert.equal(draft.area.regions[0].shape.id,id);
 await $('reductionApply').onclick();
 const sent=posts.at(-1);assert.equal(sent.action,'effects');
 assert.equal(sent.revision_manifest_sha256,'a'.repeat(64));
 assert.deepEqual(sent.fade_reduction,{target:'spatial_fade',area:draft.area});
 assert(!('spatial_fade' in sent));
 assert.deepEqual(sent.scope_xyxy,[0,0,100,100]);
 await $('reductionClear').onclick();assert.equal(draft.area.regions.length,0);
 assert.equal(posts.length,1);
 await $('reductionReload').onclick();assert.equal(fadeReductionDrafts.get('spatial_fade').dirty,false);
 """)


@pytest.mark.parametrize("completion", ["match", "newer", "error", "manifest"])
def test_fade_reduction_completion_preserves_newer_or_stale_draft(completion):
    run_page(
        "const completion="
        + repr(completion)
        + r""";
 await ready();
 servedState.revisions[0].spatial_fade={enabled:true,stale:false,settings:spatialDefaultSettings()};
 servedState.revisions[0].fade_reduction_areas={spatial_fade:{schema_version:1,regions:[]}};
 await refresh(true);$('reductionRadius').value='3';$('reductionFeather').value='0';$('reductionAmount').value='50';
 $('reductionRectangle').value='10,20,30,40';await $('reductionAddRectangle').onclick();
 const originalFetch=fetch;
 globalThis.fetch=async(path,options)=>{if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return originalFetch(path,options);};
 await $('reductionApply').onclick();const sent=posts.at(-1);
 if(completion==='newer'){$('reductionAmount').value='80';$('reductionAmount').oninput();}
 servedState.working_revision='rev-002';
 // Saved JSON sorts object keys; semantic equality must survive transport ordering.
 const savedArea=JSON.parse(JSON.stringify(sent.fade_reduction.area,
   ['amount','feather_px','id','points','radius_px','regions','role','schema_version','shape','xyxy']));
 assert.notEqual(JSON.stringify(savedArea),JSON.stringify(sent.fade_reduction.area));
 servedState.revisions.push({...structuredClone(servedState.revisions[0]),revision:'rev-002',revision_manifest_sha256:'b'.repeat(64),fade_reduction_areas:{spatial_fade:savedArea}});
 servedState.action={running:false,name:'effects',error:completion==='error'?'failed':null,result:{revision:'rev-002',parent:'rev-001',reused:false}};
 if(completion==='manifest')servedState.revisions[1].fade_reduction_areas.spatial_fade={schema_version:1,regions:[]};
 await refresh();const draft=fadeReductionDrafts.get('spatial_fade');
 assert.equal(draft.dirty,completion!=='match');
 if(completion==='newer')assert.equal(draft.area.regions[0].amount,.8);
 if(completion!=='match'){
   const count=posts.length;await $('reductionApply').onclick();assert.equal(posts.length,count);
   assert($('message').textContent.toLowerCase().includes('stale'));
 }
 """
    )


@pytest.mark.parametrize("target", ["spatial_fade", "shadow_fade"])
def test_reduction_target_switch_and_late_save_keep_other_draft(target):
    run_page(
        "const target="
        + repr(target)
        + r""";
 await ready();
 const other=target==='spatial_fade'?'shadow_fade':'spatial_fade';
 servedState.revisions[0].fade_reduction_areas={spatial_fade:{schema_version:1,regions:[]},shadow_fade:{schema_version:1,regions:[]}};
 await refresh(true);
 assert.deepEqual($('reductionTarget').options.map(option=>option.value),['spatial_fade','shadow_fade']);
 $('reductionTarget').value=target;await $('reductionTarget').onchange();
 assert.equal($('reductionTarget').value,target);
 $('reductionRadius').value='3';$('reductionFeather').value='0';$('reductionAmount').value='50';
 $('reductionRectangle').value='10,20,30,40';await $('reductionAddRectangle').onclick();
 const submittedDraft=fadeReductionDrafts.get(target);
 const originalFetch=fetch;
 globalThis.fetch=async(path,options)=>{if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return originalFetch(path,options);};
 await $('reductionApply').onclick();const sent=posts.at(-1);
 assert.equal(sent.fade_reduction.target,target);
 $('reductionTarget').value=other;await $('reductionTarget').onchange();
 assert.equal($('reductionTarget').value,other);
 $('reductionRectangle').value='40,40,60,60';await $('reductionAddRectangle').onclick();
 const otherDraft=fadeReductionDrafts.get(other),otherArea=structuredClone(otherDraft.area);
 assert(otherDraft.dirty);assert.equal(posts.length,1);
 servedState.working_revision='rev-002';
 servedState.revisions.push({...structuredClone(servedState.revisions[0]),revision:'rev-002',revision_manifest_sha256:'b'.repeat(64),
   fade_reduction_areas:{[target]:structuredClone(sent.fade_reduction.area),[other]:{schema_version:1,regions:[]}}});
 servedState.action={running:false,name:'effects',error:null,result:{revision:'rev-002',parent:'rev-001',reused:false}};
 await refresh();
 assert.equal($('reductionTarget').value,other);
 assert.equal(fadeReductionDrafts.get(target).dirty,false);
 assert.deepEqual(fadeReductionDrafts.get(target).area,submittedDraft.area);
 assert.equal(fadeReductionDrafts.get(other),otherDraft);assert.deepEqual(otherDraft.area,otherArea);
 assert($('reductionDraftStatus').textContent.includes('Stale'));
 await $('reductionApply').onclick();assert.equal(posts.length,1);
 await $('reductionReload').onclick();assert.equal(fadeReductionDrafts.get(other).dirty,false);
 $('reductionTarget').value=target;await $('reductionTarget').onchange();
 await $('reductionClear').onclick();assert.equal(fadeReductionDrafts.get(target).area.regions.length,0);
 assert.equal(fadeReductionDrafts.get(other).area.regions.length,0);assert.equal(posts.length,1);
 """
    )


def test_spatial_authoring_uses_stable_independent_shapes_and_cancel_preserves_other_drafts():
    run_page(r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.38,preserve_highlights:.7}};
 await ready();
 assert.equal(spatialDraft.enabled,false);assert.equal(spatialDraft.oval.enabled,true);
 assert.equal(spatialDraft.preserve_highlights,0);assert.equal(spatialDraft.arcs.length,0);
 assert.equal($('spatialCandidate').checked,false);
 const oval=JSON.stringify(spatialDraft.oval);
 addSpatialArc([20,30]);const first=selectedSpatialId;
 addSpatialArc([70,80]);const second=selectedSpatialId;
 assert.notEqual(first,second);assert.equal(spatialDraft.arcs.length,2);
 $('spatialSelect').value=first;$('spatialSelect').onchange();
 $('spatialBend').value='-7';$('spatialBend').oninput();
 $('spatialStrength').value='65';$('spatialStrength').oninput();
 assert.equal(spatialDraft.arcs.find(a=>a.id===first).bend,-7);
 assert.equal(spatialDraft.arcs.find(a=>a.id===first).amount,.65);
 assert.equal(spatialDraft.arcs.find(a=>a.id===second).amount,0);
 assert.equal(JSON.stringify(spatialDraft.oval),oval);
 await $('spatialDuplicate').onclick();const duplicate=selectedSpatialId;
 assert.notEqual(duplicate,first);assert.equal(spatialDraft.arcs.length,3);
 await $('spatialFlip').onclick();assert.equal(spatialDraft.arcs.find(a=>a.id===duplicate).fade_side,'negative');
 $('spatialUseArcs').checked=false;$('spatialUseArcs').oninput();
 assert.equal(spatialDraft.arcs.length,3);
 $('spatialUseArcs').checked=true;$('spatialUseArcs').oninput();
 $('spatialArcEnabled').checked=false;$('spatialArcEnabled').oninput();
 assert.equal(spatialDraft.arcs.find(a=>a.id===duplicate).enabled,false);
 await $('spatialRemove').onclick();assert(!spatialDraft.arcs.some(a=>a.id===duplicate));
 $('backgroundHex').value='#AB1234';$('backgroundHex').oninput();
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 await $('spatialCancel').onclick();assert.equal(spatialDraft.arcs.length,0);assert.equal(selectedSpatialId,'oval');
 assert.equal($('backgroundHex').value,'#AB1234');assert.equal($('exposureEV').value,'1.2');
 assert.equal($('fadeAmount').value,38);assert.equal($('fadePreserve').value,70);
 assert(!posts.some(p=>p.action==='effects'));
 """)


def test_spatial_apply_is_complete_bound_and_candidate_choice_stays_explicit():
    run_page(r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();
 $('spatialMaster').checked=true;$('spatialMaster').oninput();
 $('spatialStrength').value='60';$('spatialStrength').oninput();
 await $('spatialApply').onclick();
 const sent=posts.at(-1);assert.equal(sent.action,'effects');assert.equal(sent.revision_manifest_sha256,'a'.repeat(64));
 assert.deepEqual(sent.scope_xyxy,[0,0,100,100]);assert.equal(sent.candidate_comparison,false);
 assert.deepEqual(Object.keys(sent.spatial_fade).sort(),['enabled','preserve_highlights','oval','arcs_enabled','arcs'].sort());
 assert.equal(sent.spatial_fade.oval.amount,.6);
 servedState.accepted_revision='rev-000';await refresh();
 const count=posts.length;await $('spatialApply').onclick();assert.equal(posts.length,count);
 assert.equal($('spatialCandidate').checked,false);assert($('message').textContent.includes('candidate'));
 $('spatialCandidate').checked=true;
 await $('spatialApply').onclick();assert.equal(posts.at(-1).candidate_comparison,true);
 $('spatialCandidate').checked=false;
 await $('spatialDisable').onclick();assert.equal(posts.at(-1).spatial_fade.enabled,false);
 assert.equal(posts.at(-1).candidate_comparison,false);
 """)


@pytest.mark.parametrize(
    "completion", ["match", "newer", "revision", "settings", "error", "source"]
)
def test_reused_spatial_apply_clears_only_the_matching_submitted_draft(completion):
    """Historical-parent matching must not strand Apply or consume a different draft."""
    run_page(
        "const completion="
        + repr(completion)
        + r""";
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();spatialDraft.enabled=true;spatialDraft.oval.amount=.6;
 const saved=structuredClone(spatialDraft);
 servedState.revisions[0].spatial_fade={enabled:true,stale:false,settings:saved};
 await refresh(true);
 $('backgroundHex').value='#AB1234';$('backgroundHex').oninput();
 const originalFetch=fetch;globalThis.fetch=async(path,options)=>{if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return originalFetch(path,options);};
 await $('spatialApply').onclick();
 if(completion==='newer'){spatialDraft.oval.amount=.4;markSpatialDirty();}
 const expectedDraft=structuredClone(spatialDraft),applied=structuredClone(saved);
 if(completion==='settings')applied.oval.amount=.2;
 if(completion==='source')servedState.developed_id='other-developed-source';
 servedState.action={running:false,name:'effects',error:completion==='error'?'failure':null,
   result:{revision:completion==='revision'?'rev-old':'rev-001',parent:'rev-000',reused:true,
   spatial_fade:{enabled:true,stale:false,settings:applied}}};
 await refresh();
 assert.equal(spatialDirty,completion!=='match');
 assert.deepEqual(spatialDraft,completion==='match'?saved:expectedDraft);
 assert.equal($('backgroundHex').value,'#AB1234');
 """
    )


@pytest.mark.parametrize("reused", [False, True])
@pytest.mark.parametrize("newer_edit", [False, True])
def test_imported_layout_apply_accepts_saved_key_order_without_consuming_newer_edit(
    reused, newer_edit
):
    run_page(
        LAYOUT_SETUP
        + f"\nconst reused={json.dumps(reused)},newerEdit={json.dumps(newer_edit)};\n"
        + r"""
 await readyLayout();await previewAppearanceLayout('replace');await loadAppearanceLayout();
 const priorFetch=fetch;globalThis.fetch=async(path,options)=>{
  if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};
  return priorFetch(path,options);
 };
 await applySpatial();const submitted=posts.at(-1).spatial_fade;
 // JSON object member order changes when the server saves a sorted manifest.
 const reordered={arcs:submitted.arcs,arcs_enabled:submitted.arcs_enabled,enabled:submitted.enabled,
  oval:{amount:submitted.oval.amount,...submitted.oval},preserve_highlights:submitted.preserve_highlights};
 assert.notEqual(JSON.stringify(reordered),JSON.stringify(submitted));
 if(newerEdit){spatialDraft.oval.amount=.23;markSpatialDirty();}
 const pending=structuredClone(spatialDraft), revision=reused?'rev-001':'rev-002';
 const record={...servedState.revisions[0],revision,spatial_fade:{enabled:reordered.enabled,settings:reordered}};
 if(reused)servedState.revisions[0]=record;else servedState.revisions.push(record);
 servedState.working_revision=revision;
 servedState.action={running:false,name:'effects',error:null,result:{revision,parent:'rev-001',reused,
  spatial_fade:{enabled:reordered.enabled,settings:reordered}}};
 await refresh(false);
 assert.equal(spatialDirty,newerEdit);
 assert.deepEqual(spatialDraft,newerEdit?pending:submitted);
 assert.equal(appearanceLayoutUndo,null);
 """
    )


def test_spatial_canvas_handles_and_numeric_values_match_without_saving_on_drag():
    run_page(r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();$('authorMode').value='spatial';
 $('spatialRotation').value='397';$('spatialRotation').oninput();assert.equal(spatialDraft.oval.rotation_degrees,37);
 $('spatialWidth').value='30';$('spatialWidth').oninput();assert.equal(spatialDraft.oval.inner_radii_xy[0],15);
 zoom=2;pan=[9,-7];draw();
 const handle=spatialHandles(spatialDraft.oval,true).find(h=>h.name==='center');
 const rect=canvas.getBoundingClientRect(),size=[canvas.width,canvas.height];
 const start=nativeToScreen(handle.point,rect,size,transform,crop),end=nativeToScreen([55,57],rect,size,transform,crop);
 canvas.onpointerdown({clientX:start[0],clientY:start[1],pointerId:1,shiftKey:false});
 canvas.onpointermove({clientX:end[0],clientY:end[1],pointerId:1});
 canvas.onpointerup({clientX:end[0],clientY:end[1],pointerId:1});
 assert(Math.abs(spatialDraft.oval.center_xy[0]-55)<1e-8);assert(Math.abs(spatialDraft.oval.center_xy[1]-57)<1e-8);
 assert.equal(posts.length,0);assert(spatialDirty);assert($('spatialDraftStatus').textContent.includes('Unapplied'));
 addSpatialArc([40,50]);$('spatialBend').value='-8';$('spatialBend').oninput();
 $('spatialSide').value='negative';$('spatialSide').oninput();
 const arc=spatialDraft.arcs.at(-1),mid=spatialHandles(arc,false).find(h=>h.name==='bend');
 assert.equal(mid.point[1],42);assert.equal(arc.fade_side,'negative');
 canvas.onkeydown({key:'Escape',preventDefault(){}});assert.equal(spatialDraft.arcs.length,0);
 """)


@pytest.mark.parametrize("pending", ["none", "geometry", "invalid", "stale"])
@pytest.mark.parametrize("reused", [False, True])
def test_spatial_disable_uses_saved_geometry_and_retains_unapplied_draft(pending, reused):
    run_page(
        "const pending="
        + repr(pending)
        + ",reused="
        + str(reused).lower()
        + r""";
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();addSpatialArc([30,40]);
 spatialDraft.enabled=true;spatialDraft.arcs[0].amount=.7;
 const saved=structuredClone(spatialDraft);saved.enabled=!reused;
 servedState.revisions[0].spatial_fade={enabled:!reused,stale:false,settings:saved};
 servedState.accepted_revision='rev-000';await refresh(true);
 if(pending!=='none') {
   await $('spatialRemove').onclick();addSpatialArc([60,70]);
   if(pending==='invalid') {$('spatialBend').value='99999';$('spatialBend').oninput();}
   if(pending==='stale') {servedState.revisions[0].revision_manifest_sha256='b'.repeat(64);await refresh();}
 }
 $('backgroundHex').value='#AB1234';$('backgroundHex').oninput();
 $('spatialProtection').value='pending-protection.png';
 const draft=structuredClone(spatialDraft),expected={...structuredClone(saved),enabled:false};
 const originalFetch=fetch;globalThis.fetch=async(path,options)=>{if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return originalFetch(path,options);};
 const count=posts.length;await $('spatialDisable').onclick();
 assert.equal(posts.length,count+1);
 const sent=posts.at(-1);assert.equal(sent.action,'effects');assert.deepEqual(sent.spatial_fade,expected);
 assert.equal(sent.candidate_comparison,false);assert(!('spatial_fade_protection_file' in sent));
 assert.equal(sent.revision_manifest_sha256,(pending==='stale'?'b':'a').repeat(64));
 assert.deepEqual(spatialDraft,draft,'Disable must not replace pending geometry or switches');
 const completedRevision=reused?'rev-001':'rev-002';servedState.working_revision=completedRevision;
 if(!reused)servedState.revisions.push({...servedState.revisions[0],revision:completedRevision,revision_manifest_sha256:'c'.repeat(64),spatial_fade:{enabled:false,stale:false,settings:expected}});
 servedState.action={running:false,name:'effects',error:null,result:{revision:completedRevision,parent:reused?'rev-000':'rev-001',reused,spatial_fade:{enabled:false,stale:false,settings:expected}}};
 await refresh();
 if(pending==='none') {assert(!spatialDirty);assert.deepEqual(spatialDraft,expected);}
 else {assert(spatialDirty);assert.deepEqual(spatialDraft,draft);assert($('spatialDraftStatus').textContent.includes(!reused||pending==='stale'?'Stale':'Unapplied'));}
 assert.equal($('backgroundHex').value,'#AB1234');
 """
    )


def test_spatial_shape_limit_and_late_apply_result_do_not_drop_newer_drafts():
    run_page(r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();for(let i=0;i<32;i++)addSpatialArc([50,50]);
 const ids=spatialDraft.arcs.map(a=>a.id);await $('spatialDuplicate').onclick();
 assert.deepEqual(spatialDraft.arcs.map(a=>a.id),ids);assert($('message').textContent.includes('32'));
 await $('spatialCancel').onclick();addSpatialArc([30,40]);
 $('spatialMaster').checked=true;$('spatialMaster').oninput();
 servedState.action={running:true,name:'effects',error:null,result:null};
 // Keep the mocked action initially available; it becomes running only after POST.
 const originalFetch=fetch;globalThis.fetch=async(path,options)=>{
  if(path==='/api/action')servedState.action.running=true;
  return originalFetch(path,options);
 };
 servedState.action.running=false;
 await $('spatialApply').onclick();const sent=posts.at(-1).spatial_fade,id=selectedSpatialId;
 $('spatialBend').value='-9';$('spatialBend').oninput();
 servedState.working_revision='rev-002';servedState.inputs_digest='new-draft';
 servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',draft_digest:'new-draft',revision_manifest_sha256:'b'.repeat(64),spatial_fade:{enabled:true,stale:false,settings:sent}});
 servedState.action={running:false,name:'effects',error:null,result:{revision:'rev-002',parent:'rev-001',spatial_fade:{enabled:true,stale:false,settings:sent}}};
 await refresh();assert.equal(selectedSpatialId,id);assert.equal(spatialDraft.arcs[0].bend,-9);assert(spatialDirty);
 assert($('spatialDraftStatus').textContent.includes('Stale'));
 """)


def test_spatial_export_status_distinguishes_paired_success_and_uncertain_error():
    run_page(r"""
 await ready();
 servedState.action={running:false,name:'export',error:null,result:{directory:'exports/frame',editable_companion:{directory:'exports/native',manifest_file:'exports/native/manifest.json',manifest_sha256:'a'.repeat(64)}}};
 await refresh();assert($('result').textContent.includes('exports/frame'));assert($('result').textContent.includes('exports/native'));assert($('result').textContent.includes('both'));
 servedState.action={running:false,name:'export',error:'Native-only pair incomplete; durability unconfirmed',result:{directory:'exports/native'}};
 await refresh();assert(!$('result').textContent.includes('Export saved:'));assert($('message').textContent.includes('unconfirmed'));
 """)


def test_spatial_keyboard_controls_round_trip_and_apply_preserves_other_dirty_controls():
    run_page(r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.38,preserve_highlights:.7}};
 await ready();
 for(const [id,value] of Object.entries({spatialCenterX:'41',spatialCenterY:'43',spatialWidth:'30',spatialHeight:'40',spatialTransition:'11',spatialRotation:'397',spatialStrength:'52',spatialPreserve:'20'})){$(id).value=value;$(id).oninput();}
 assert.deepEqual(spatialDraft.oval.center_xy,[41,43]);assert.deepEqual(spatialDraft.oval.inner_radii_xy,[15,20]);
 assert.equal(spatialDraft.oval.transition_width,11);assert.equal(spatialDraft.oval.rotation_degrees,37);assert.equal(spatialDraft.oval.amount,.52);
 addSpatialArc([30,40]);const id=selectedSpatialId;
 for(const [field,value] of Object.entries({spatialCenterX:'33',spatialCenterY:'44',spatialSpan:'30',spatialBend:'-10',spatialTransition:'7',spatialEndSoftness:'6',spatialRotation:'361',spatialStrength:'75'})){$(field).value=value;$(field).oninput();}
 const arc=spatialDraft.arcs[0];assert.equal(arc.id,id);assert.equal(arc.half_span,15);assert.equal(arc.bend,-10);assert.equal(arc.end_softness,6);assert.equal(arc.rotation_degrees,1);assert.equal(arc.amount,.75);
 assert.equal(spatialDraft.preserve_highlights,.2);assert.equal($('fadeAmount').value,38);assert.equal($('fadePreserve').value,70);
 $('backgroundHex').value='#AB1234';$('backgroundHex').oninput();
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 $('fadeAmount').value='42';$('fadeAmount').oninput();
 $('spatialMaster').checked=true;$('spatialMaster').oninput();
 const originalFetch=fetch;globalThis.fetch=async(path,options)=>{if(path==='/api/action')servedState.action={running:true,name:'effects',error:null,result:null};return originalFetch(path,options);};
 await $('spatialApply').onclick();const sent=structuredClone(posts.at(-1).spatial_fade);
 servedState.working_revision='rev-002';servedState.inputs_digest='new-draft';
 servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',draft_digest:'new-draft',revision_manifest_sha256:'b'.repeat(64),spatial_fade:{enabled:true,stale:false,settings:sent}});
 servedState.action={running:false,name:'effects',error:null,result:{revision:'rev-002',parent:'rev-001',spatial_fade:{enabled:true,stale:false,settings:sent}}};
 await refresh();assert(!spatialDirty);assert.equal(selectedSpatialId,id);assert.deepEqual(spatialDraft,sent);
 assert.equal($('backgroundHex').value,'#AB1234');assert.equal($('exposureEV').value,'1.2');assert.equal($('fadeAmount').value,'42');
 assert.equal(servedState.revisions.at(-1).shadow_fade.settings.amount,.38);
 """)


def test_spatial_saved_map_decode_cannot_overwrite_removed_shape_selection_or_dirty_inputs():
    run_page(r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();addSpatialArc([20,30]);addSpatialArc([60,70]);
 servedState.revisions[0].spatial_fade={enabled:false,stale:false,settings:structuredClone(spatialDraft)};
 await refresh();
 resetSpatialFromSaved();$('spatialSelect').value=spatialDraft.arcs[1].id;$('spatialSelect').onchange();
 const removed=selectedSpatialId,remaining=spatialDraft.arcs[0].id;
 const originalFetch=fetch;let malformed=false;
 globalThis.fetch=async(path,options)=>{
  if(path!=='/api/spatial-preview')return originalFetch(path,options);
  const request=JSON.parse(options.body);return {ok:true,json:async()=>malformed ? {started:true} : {...request,png_base64:'AA=='}};
 };
 let pending=[],closed=0;globalThis.createImageBitmap=async blob=>{
  if(blob.width!==undefined)return {width:blob.width,height:blob.height,close(){}};
  return new Promise(resolve=>pending.push(()=>resolve({width:100,height:100,close(){closed++;}})));
 };
 $('spatialMap').value='selected';const old=loadImage();
 for(let i=0;i<30&&!pending.length;i++)await Promise.resolve();assert.equal(pending.length,1);
 await $('spatialRemove').onclick();
 for(let i=0;i<30&&pending.length<2;i++)await Promise.resolve();assert.equal(selectedSpatialId,'oval');assert.equal(spatialDraft.arcs[0].id,remaining);
 pending[0]();await old;assert.equal(closed,1);assert(!spatialDraft.arcs.some(a=>a.id===removed));
 pending[1]();for(let i=0;i<20;i++)await Promise.resolve();
 assert.equal(selectedSpatialId,'oval');assert(spatialDirty);assert(spatialOverlayLoaded);
 const geometry=JSON.stringify(spatialDraft),version=spatialDraftVersion;
 $('spatialOpacity').value='.1';$('spatialOpacity').oninput();assert.equal(JSON.stringify(spatialDraft),geometry);assert.equal(spatialDraftVersion,version);
 malformed=true;$('spatialMap').value='combined';await loadImage();
 assert($('message').textContent.includes('does not match'));assert.equal(JSON.stringify(spatialDraft),geometry);assert(spatialDirty);
 assert.equal(selectedSpatialId,'oval');assert.equal(image,null);
 """)


def test_prepare_does_not_require_development_review_or_change_appearance_controls():
    run_page(r"""
 servedState.development_approved=false;
 await ready();
 $('backgroundHex').value='#151515';$('backgroundHex').oninput();
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 $('scope').value='0,0,100,100';
 await $('prepare').onclick();
 assert.equal(posts.at(-1).action,'prepare');
 assert(!posts.some(post=>post.action==='development'||post.action==='effects'));
 assert.equal($('backgroundHex').value,'#151515');
 assert.equal($('exposureEV').value,'1.2');
 assert(!$('status').textContent.includes('development review required'));
 """)


def test_gallery_pending_repair_preserves_unsubmitted_forms_and_polling_is_read_only():
    run_page(r"""
 servedState.preview={status:'pending',reason:'missing',latest_result_revision:'rev-002',accepted_revision:'rev-001'};
 await ready();
 assert($('previewStatus').textContent.includes('pending'));
 assert($('previewStatus').textContent.includes('rev-002'));
 assert.equal(posts.length,0);
 $('backgroundHex').value='#151515';$('backgroundHex').oninput();
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 await $('previewRepair').onclick();
 assert.equal(posts.at(-1).action,'preview-repair');
 servedState.action={running:true,name:'preview-repair',error:null,result:null};await refresh();
 servedState.action={running:false,name:'preview-repair',error:null,result:{status:'current'}};
 servedState.preview={status:'current',revision:'rev-002',label:'Draft'};await refresh();
 assert.equal($('backgroundHex').value,'#151515');
 assert.equal($('exposureEV').value,'1.2');
 assert($('previewStatus').textContent.includes('Draft'));
 servedState.writer_busy=true;await refresh();assert($('previewRepair').disabled);
 """)


def test_series_mode_and_portable_controls_preserve_independent_forms():
    run_page(r"""
 servedState.series_settings={name:'Portrait series',output_width_px:40,output_height_px:50,side_margin_tenths_percent:150,minimum_vertical_margin_tenths_percent:50};
 await ready();
 $('framingLeft').value='7';$('framingLeft').oninput();$('cleanupSupport').value='keep';
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 $('framingMode').value='match-series';await $('framingMode').onchange();
 $('seriesName').value='Été 🦋 <series>';$('seriesName').oninput();
 assert.equal(seriesSettings().name,'Été 🦋 <series>');
 const native=JSON.stringify({identity,exposureControlsIdentity});
 $('framingMode').value='add-margins';await $('framingMode').onchange();
 $('framingMode').value='match-series';await $('framingMode').onchange();
 assert.equal($('framingLeft').value,'7');assert.equal($('seriesName').value,'Été 🦋 <series>');
 const originalFetch=globalThis.fetch;
 globalThis.fetch=async(path,options)=>{
  if(path!='/api/series-preset-validate')return originalFetch(path,options);
  const raw=JSON.parse(options.body).preset_json, preset=JSON.parse(raw);
  const {schema_version,kind,...settings}=preset;
  return {ok:true,json:async()=>({settings,preset_json:JSON.stringify(preset)})};
 };
 const bytes=new TextEncoder().encode(JSON.stringify({schema_version:1,kind:'series-framing-preset',...seriesSettings(),name:'Loaded series'}));
 $('seriesFile').files=[{size:bytes.length,arrayBuffer:async()=>bytes.buffer}];
 await $('seriesFile').onchange();assert.equal(seriesSettings().name,'Loaded series');
 assert.equal(seriesDirty,true);assert.equal(posts.length,0);
 let read=false;const before=JSON.stringify(seriesSettings());
 $('seriesFile').files=[{size:16385,arrayBuffer:async()=>{read=true;}}];
 await $('seriesFile').onchange();assert.equal(read,false);assert.equal(JSON.stringify(seriesSettings()),before);
 $('seriesFile').files=[];await $('seriesFile').onchange();assert.equal(JSON.stringify(seriesSettings()),before);
 const invalid=new Uint8Array([255]);$('seriesFile').files=[{size:1,arrayBuffer:async()=>invalid.buffer}];
 await $('seriesFile').onchange();assert.equal(JSON.stringify(seriesSettings()),before);
 let release;const pendingBytes=new Promise(resolve=>release=resolve);
 $('seriesFile').files=[{size:bytes.length,arrayBuffer:()=>pendingBytes}];
 const pending=$('seriesFile').onchange();$('seriesWidth').value='43';$('seriesWidth').oninput();
 release(bytes.buffer);await pending;assert.equal(seriesSettings().output_width_px,43);
 let downloaded=null,revoked=false;const oldCreate=document.createElement;
 document.createElement=tag=>{const node=oldCreate(tag);if(tag==='a')node.click=()=>{downloaded=node.download;};return node;};
 URL.createObjectURL=blob=>{assert(blob.size<=16384);return 'blob:synthetic';};
 URL.revokeObjectURL=url=>{assert.equal(url,'blob:synthetic');revoked=true;};
 await $('seriesDownload').onclick();await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(downloaded,'series-framing-preset.json');assert.equal(revoked,true);
 assert.equal(posts.length,0);assert.equal(JSON.stringify({identity,exposureControlsIdentity}),native);
 assert.equal($('cleanupSupport').value,'keep');assert.equal($('framingLeft').value,'7');
 """)


def test_series_preview_sequence_selection_and_bitmap_lifecycle():
    run_page(r"""
 servedState.series_settings={name:'Portrait series',output_width_px:40,output_height_px:50,side_margin_tenths_percent:150,minimum_vertical_margin_tenths_percent:50};
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);await ready();
 $('framingMode').value='match-series';await $('framingMode').onchange();
 const originalFetch=globalThis.fetch;let decode,closed=false;
 globalThis.fetch=async(path,options)=>{
  if(path!='/api/series-preview')return originalFetch(path,options);
  const request=JSON.parse(options.body);
  return {ok:true,json:async()=>({...request,algorithm:'series-lanczos-premultiplied-v1',output_dimensions_wh:[40,50],display_dimensions_wh:[40,50],layout:{scale:1.3,geometric_margins_lrtb_px:[6,6,11,11],transformed_subject_bounds_xyxy:[6,11,34,39],fit_reason:'side-margins-matched',source_edge_contact:true},png_base64:'AA=='})};
 };
 globalThis.createImageBitmap=()=>new Promise(resolve=>decode=()=>resolve({width:40,height:50,close(){closed=true;}}));
 const pending=previewSeries();for(let i=0;i<20&&!decode;i++)await Promise.resolve();assert(decode);
 $('seriesName').value='new fields';$('seriesName').oninput();decode();await pending;
 assert.equal(closed,true);assert.equal(seriesBitmap,null);
 globalThis.createImageBitmap=async()=>({width:40,height:50,close(){closed=true;}});
 await previewSeries();assert(seriesBitmap);assert.match($('seriesPreviewStatus').textContent,/Enlarged/);
 assert.match($('seriesPreviewStatus').textContent,/source edge/i);
 $('framingMode').value='add-margins';await $('framingMode').onchange();assert.equal(seriesBitmap,null);
 """)


def test_series_buttons_export_the_named_selection_and_visible_settings():
    run_page(r"""
 servedState.series_settings={name:'Portrait series',output_width_px:40,output_height_px:50,side_margin_tenths_percent:150,minimum_vertical_margin_tenths_percent:50};
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',revision_manifest_sha256:'b'.repeat(64)}, {...servedState.revisions[0],revision:'rev-003',revision_manifest_sha256:'c'.repeat(64)});
 servedState.working_revision='rev-003';await ready();
 $('framingMode').value='match-series';await $('framingMode').onchange();
 $('viewRevision').value='rev-002';await $('viewRevision').onchange();
 $('seriesWidth').value='43';$('seriesWidth').oninput();$('seriesTransparent').checked=true;
 $('geometry').value='17,23';await $('addGeometry').onclick();$('cleanupSupport').value='keep';
 const before=JSON.stringify({regions,identity,exposureControlsIdentity,fadeControlsIdentity});
 servedState.action={running:true,name:'series-export',error:null,result:null};
 await $('seriesExportDraft').onclick();assert.equal(posts.at(-1).revision,'rev-002');
 assert.equal(posts.at(-1).revision_manifest_sha256,'b'.repeat(64));assert.equal(posts.at(-1).draft,true);
 assert.deepEqual(posts.at(-1).settings,seriesSettings());assert.equal(posts.at(-1).transparent,true);
 servedState.action={running:false,name:'series-export',error:null,result:{settings:seriesSettings(),directory:'synthetic'}};await refresh();
 assert.equal(JSON.stringify({regions,identity,exposureControlsIdentity,fadeControlsIdentity}),before);
 assert.equal($('seriesExportAccepted').disabled,true);const count=posts.length;await $('seriesExportAccepted').onclick();assert.equal(posts.length,count);
 $('viewRevision').value='rev-001';await $('viewRevision').onchange();
 servedState.action={running:true,name:'series-export',error:null,result:null};
 $('seriesEditable').checked=true;
 await $('seriesExportAccepted').onclick();assert.equal(posts.at(-1).revision,'rev-001');assert.equal(posts.at(-1).draft,false);
 assert.deepEqual(posts.at(-1).variants,['editable']);
 assert.equal($('cleanupSupport').value,'keep');
 """)


def test_series_uncertain_save_requires_explicit_reload():
    run_page(r"""
 servedState.series_settings={name:'Portrait series',output_width_px:40,output_height_px:50,side_margin_tenths_percent:150,minimum_vertical_margin_tenths_percent:50};
 servedState.series_digest='old';await ready();
 $('seriesName').value='unsaved';$('seriesName').oninput();$('cleanupSupport').value='keep';
 servedState.action={running:true,name:'series-save',error:null,result:null};await $('seriesSave').onclick();
 servedState.series_settings={...seriesSettings(),name:'visible settings'};servedState.series_digest='visible';
 servedState.action={running:false,name:'series-save',error:'durability unconfirmed',result:{series_settings:servedState.series_settings,series_digest:'visible',series_reload_required:true}};
 await refresh();assert.equal($('seriesName').value,'unsaved');assert.equal(seriesNeedsReload,true);
 assert.equal($('seriesSave').disabled,true);const count=posts.length;await $('seriesSave').onclick();assert.equal(posts.length,count);
 await $('seriesReload').onclick();assert.equal(seriesNeedsReload,false);assert.equal(seriesDigest,'visible');
 assert.equal($('seriesName').value,'visible settings');assert.equal($('cleanupSupport').value,'keep');
 """)


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


def test_requested_exports_send_variants_and_preserve_independent_forms():
    run_page(r"""
 await ready();
 $('exportEditable').checked=true;$('exportBlack').checked=true;
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 const before=JSON.stringify({exposureControlsIdentity,ev:$('exposureEV').value});
 await $('exportAccepted').onclick();
 assert.deepEqual(posts.at(-1).variants,['black','editable']);
 assert.equal(posts.at(-1).revision_manifest_sha256,'a'.repeat(64));
 servedState.action={name:'export',running:false,error:null,result:{directory:'exports/new',reused:false}};
 await refresh();
 assert.equal(JSON.stringify({exposureControlsIdentity,ev:$('exposureEV').value}),before);
 $('framingBlack').checked=true;$('framingEditable').checked=true;await $('framingExportAccepted').onclick();
 assert.deepEqual(posts.at(-1).variants,['black','editable']);
 assert.equal(posts.at(-1).revision_manifest_sha256,'a'.repeat(64));
 """)


def test_framing_buttons_and_reload_preserve_independent_drafts():
    run_page(r"""
 servedState.framing={left_px:1,right_px:2,top_px:3,bottom_px:4};
 servedState.framing_digest='saved';servedState.framing_error=null;
 await ready();
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 $('fadeAmount').value='35';$('fadeAmount').oninput();
 $('cleanupSupport').value='pending-cleanup';$('shadingWidth').value='7';
 const subject=JSON.stringify({exposureControlsIdentity,fadeControlsIdentity});
 $('framingEqual').value='5';await $('framingSetAll').onclick();
 assert.deepEqual(framingMargins(),{left_px:5,right_px:5,top_px:5,bottom_px:5});
 $('framingLeft').value='2';$('framingLeft').oninput();
 await $('framingCentre').onclick();
 assert.deepEqual(framingMargins(),{left_px:3,right_px:4,top_px:5,bottom_px:5});
 await refresh();assert.equal(Number($('framingLeft').value),3);
 servedState.action={running:true,name:'framing-save',error:null,result:null};
 await $('framingSave').onclick();
 assert.deepEqual(posts.at(-1).margins,framingMargins());
 servedState.action={running:false,name:'framing-save',error:null,
  result:{framing:framingMargins(),framing_digest:'new'}};
 servedState.framing=framingMargins();servedState.framing_digest='new';
 actionWasRunning=true;await refresh();
 assert.equal($('cleanupSupport').value,'pending-cleanup');
 assert.equal($('shadingWidth').value,'7');
 assert.equal(JSON.stringify({exposureControlsIdentity,fadeControlsIdentity}),subject);
 assert.equal($('exposureEV').value,'1.2');assert.equal($('fadeAmount').value,'35');
 await $('framingReset').onclick();assert.equal(framingDirty,true);
 await $('framingReload').onclick();assert.deepEqual(framingMargins(),servedState.framing);
 assert.equal(JSON.stringify({exposureControlsIdentity,fadeControlsIdentity}),subject);
 """)


def test_framing_uncertain_save_retains_fields_until_explicit_reload():
    run_page(r"""
 servedState.framing={left_px:1,right_px:2,top_px:3,bottom_px:4};
 servedState.framing_digest='old';servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);await ready();
 $('framingLeft').value='8';$('framingLeft').oninput();
 $('geometry').value='17,23';$('cleanupSupport').value='keep-support';
 const nativeIdentity=JSON.stringify(identity), nativeTransform=JSON.stringify(transform);
 servedState.action={running:true,name:'framing-save',error:null,result:null};
 await $('framingSave').onclick();
 servedState.framing={left_px:8,right_px:2,top_px:3,bottom_px:4};servedState.framing_digest='visible';
 servedState.action={running:false,name:'framing-save',error:'durability unconfirmed',
   result:{framing:servedState.framing,framing_digest:'visible',framing_reload_required:true}};
 await refresh();
 assert.equal(Number($('framingLeft').value),8);assert.equal(framingDirty,true);
 assert.equal(framingNeedsReload,true);assert.equal($('framingSave').disabled,true);
 assert.match($('framingStatus').textContent,/Reload saved margins required/);
 const count=posts.length;await $('framingSave').onclick();assert.equal(posts.length,count);
 await $('framingReload').onclick();assert.equal(framingNeedsReload,false);
 assert.equal(framingDigest,'visible');assert.equal(framingDirty,false);
 assert.equal($('cleanupSupport').value,'keep-support');
 assert.equal(JSON.stringify(identity),nativeIdentity);assert.equal(JSON.stringify(transform),nativeTransform);
 await $('addGeometry').onclick();assert.deepEqual(regions.at(-1).xy,[17,23]);
 $('framingLeft').value='1.5';$('framingLeft').oninput();
 await $('framingPreview').onclick();assert.match($('message').textContent,/whole pixels/);
 $('framingLeft').value='9';$('framingLeft').oninput();
 servedState.developed_id='replacement-source';await refresh();
 assert.equal(Number($('framingLeft').value),9);assert.equal(framingNeedsReload,true);
 """)


def test_framing_exports_visible_form_without_resetting_other_drafts():
    run_page(r"""
 await ready();
 $('framingLeft').value='7';$('framingLeft').oninput();
 $('framingTransparent').checked=true;
 $('cleanupSupport').value='keep';$('exposureEV').value='1.1';$('exposureEV').oninput();
 $('fadeAmount').value='44';$('fadeAmount').oninput();
 $('geometry').value='17,23';await $('addGeometry').onclick();
 const drafts=JSON.stringify({regions,identity,exposureControlsIdentity,fadeControlsIdentity});
 servedState.action={running:true,name:'export',error:null,result:null};
 await $('framingExportAccepted').onclick();
 assert.equal(posts.at(-1).revision,'rev-001');assert.equal(posts.at(-1).draft,false);
 assert.equal(posts.at(-1).framing.left_px,7);assert.equal(posts.at(-1).framed_transparent,true);
 servedState.action={running:false,name:'export',error:null,result:{framing:framingMargins(),directory:'synthetic'}};
 await refresh();
 assert.equal(JSON.stringify({regions,identity,exposureControlsIdentity,fadeControlsIdentity}),drafts);
 assert.equal($('cleanupSupport').value,'keep');assert.equal(framingDirty,true);
 servedState.working_revision='rev-002';
 servedState.revisions.push({...servedState.revisions[0],revision:'rev-002'});await refresh();
 servedState.action={running:true,name:'export',error:null,result:null};
 await $('framingExportDraft').onclick();assert.equal(posts.at(-1).revision,'rev-002');assert.equal(posts.at(-1).draft,true);
 """)


@pytest.mark.parametrize("change", ["source", "revision", "digest", "margin"])
def test_framing_bitmap_pending_decode_rejects_changed_identity(change):
    run_page(
        r"""
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);await ready();
 let decode, closed=false;
 const originalFetch=globalThis.fetch;
 globalThis.fetch=async(path,options)=>{
  if(path!='/api/framing-preview')return originalFetch(path,options);
  const request=JSON.parse(options.body);
  return {ok:true,json:async()=>({...request,source_dimensions_wh:[100,100],
   output_dimensions_wh:[100,100],display_dimensions_wh:[100,100],source_rect_xyxy:[0,0,100,100],png_base64:'AA=='})};
 };
 globalThis.createImageBitmap=async()=>new Promise(resolve=>decode=()=>resolve({width:100,height:100,close(){closed=true;}}));
 const preview=previewFraming();for(let i=0;i<20&&!decode;i++)await Promise.resolve();assert(decode);
 """
        + {
            "source": "state.developed_id='new-source';",
            "revision": "$('viewRevision').value='rev-002';",
            "digest": "state.revisions[0].revision_manifest_sha256='b'.repeat(64);",
            "margin": "$('framingLeft').value='2';$('framingLeft').oninput();",
        }[change]
        + r"""
 decode();await preview;assert.equal(closed,true);assert.equal(framingBitmap,null);
 """
    )


def test_framing_preview_identity_order_and_bitmap_ownership():
    run_page(r"""
 servedState.framing={left_px:0,right_px:0,top_px:0,bottom_px:0};
 servedState.revisions[0].revision_manifest_sha256='a'.repeat(64);
 await ready();
 const nativeFetch=fetch, requests=[], closed=[];
 globalThis.fetch=async(path,options)=>{
   if(path!='/api/framing-preview')return nativeFetch(path,options);
   const request=JSON.parse(options.body);
   return new Promise(resolve=>requests.push({request,resolve}));
 };
 let bitmapId=0;
 globalThis.createImageBitmap=async blob=>{
   assert(blob instanceof Blob);assert.equal(blob.type,'image/png');
   const id=++bitmapId;return {width:100,height:100,close(){closed.push(id);}};
 };
 function respond(index, overrides={}){
   const {request,resolve}=requests[index];
   resolve({ok:true,json:async()=>({...request,source_dimensions_wh:[100,100],
    output_dimensions_wh:[100,100],display_dimensions_wh:[100,100],
    source_rect_xyxy:[0,0,100,100],png_base64:'AQID',...overrides})});
 }
 const first=previewFraming(),second=previewFraming();
 respond(1);await second;assert.equal(framingBitmap.width,100);
 respond(0);await first;assert.equal(bitmapId,1,'Stale response should be discarded before decode');
 const third=previewFraming();respond(2);await third;assert.deepEqual(closed,[1]);
 const fourth=previewFraming();
 $('framingLeft').value='3';$('framingLeft').oninput();
 respond(3);await fourth;assert.equal(bitmapId,2);
 assert($('framingPreviewStatus').textContent.includes('stale'));
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


def test_exposure_area_authoring_is_independent_and_uses_native_crop():
    run_page(r"""
await ready();$('authorMode').value='exposure';$('exposureRole').value='regions';$('exposureShape').value='rectangle';$('exposureFeather').value='2';
$('crop').value='20,20,80,80';await $('cropApply').onclick();
canvas.onpointerdown({clientX:100,clientY:50,pointerId:1,shiftKey:false});
canvas.onpointerup({clientX:200,clientY:150,pointerId:1});
assert.deepEqual(exposureArea.regions[0].xyxy,[35,35,65,65]);
assert.equal(exposureArea.regions[0].feather_px,2);
assert.equal(regions.length,0);assert.equal(dirty,false);assert.equal(exposureDirty,true);
$('exposureRole').value='protection';$('exposureRectangle').value='40,40,50,50';await $('exposureAddRectangle').onclick();
assert.equal(exposureArea.protection[0].feather_px,0);
assert.deepEqual(exposureArea.protection[0].xyxy,[40,40,50,50]);
""")


def test_exposure_amount_does_not_publish_pending_area_and_reset_keeps_it():
    run_page(r"""
await ready();$('exposureRole').value='regions';$('exposureShape').value='rectangle';$('exposureFeather').value='0';
$('exposureRectangle').value='10,10,40,40';await $('exposureAddRectangle').onclick();
const draft=JSON.stringify(exposureArea);$('exposureEV').value='0.5';$('exposureCandidate').checked=true;
await $('exposureAmount').onclick();
assert.equal(posts.at(-1).exposure_amount_only,true);
assert(!('exposure_area' in posts.at(-1)));assert(!('support_file' in posts.at(-1)));
assert.equal(posts.at(-1).local_exposure.ev,.5);
assert.equal(JSON.stringify(exposureArea),draft);assert.equal(exposureDirty,true);
actionWasRunning=false;await refresh();await $('exposureReset').onclick();
assert.deepEqual(posts.at(-1).local_exposure,{enabled:false,ev:0});
assert.equal(JSON.stringify(exposureArea),draft);
""")


def test_exposure_comparison_is_read_only_and_keeps_other_effects():
    run_page(r"""
await ready();const paths=[];const originalFetch=globalThis.fetch;
globalThis.fetch=async(path, options)=>{paths.push(path);return originalFetch(path.replace('/exposure-off',''),options);};
$('panel').value='black';$('exposureCompare').checked=true;await $('exposureCompare').onchange();
assert(paths.includes('/image/black/rev-001/0,0,100,100/exposure-off'));
assert.equal(posts.length,0);assert.equal($('cleanupBase').checked,false);
""")


def test_exposure_rejects_stale_view_and_transitional_pointer():
    run_page(r"""
await ready();$('exposureEV').value='1';$('viewRevision').value='rev-old';
await $('exposureAmount').onclick();assert.equal(posts.length,0);
$('viewRevision').value='rev-001';$('authorMode').value='exposure';$('exposureShape').value='stroke';$('exposureRole').value='regions';$('exposureRadius').value='3';$('exposureFeather').value='1';
imageLoading=true;canvas.onpointerdown({clientX:70,clientY:20,pointerId:1,shiftKey:false});
canvas.onpointerup({clientX:80,clientY:30,pointerId:1});assert.equal(exposureArea.regions.length,0);
imageLoading=false;canvas.onpointerdown({clientX:70,clientY:20,pointerId:2,shiftKey:false});
canvas.onpointermove({clientX:90,clientY:40});canvas.onpointerup({clientX:90,clientY:40,pointerId:2});
assert.deepEqual(exposureArea.regions[0].points,[[10,10],[20,20]]);
assert.equal(exposureArea.regions[0].radius_px,3);assert.equal(dirty,false);
""")


def test_exposure_prepare_transition_keeps_review_controls_and_current_identity():
    run_page(r"""
servedState.revisions[0].local_exposure={enabled:true,stale:false,settings:{enabled:true,ev:.5},clipping:{clipped_pixels:2,eligible_pixels:100}};
await ready();
assert($('exposureStatus').textContent.includes('clipped 2 / 100'));
servedState.action={name:'prepare',running:true,error:null,result:null};await refresh();
assert.equal($('trimap').disabled,true);
servedState.working_revision='rev-002';servedState.inputs_digest='prepared-draft';servedState.authoring_digest='prepared-author';
servedState.revisions.push({revision:'rev-002',kind:'prepare',draft_digest:'prepared-draft',final_acceptable:false,candidates:[],local_exposure:{enabled:true,stale:false,settings:{enabled:true,ev:.5}}});
servedState.action={name:'prepare',running:false,error:null,result:{revision:'rev-002'}};
await refresh();
assert($('exposureStatus').textContent.includes('clipping unavailable'),$('exposureStatus').textContent);
assert(!$('exposureStatus').textContent.includes('clipped 0'),'Invented zero clipping counts');
assert.equal(identity.base_revision,'rev-002');assert.equal(identity.inputs_digest,'prepared-draft');
assert.equal($('trimap').disabled,false);assert.equal($('matte').disabled,false);
$('trimapReviewed').checked=true;await $('trimap').onclick();
assert.equal(posts.at(-1).action,'trimap');assert.equal(posts.at(-1).revision,'rev-002');
assert.equal(posts.at(-1).base_revision,'rev-002');assert.equal(posts.at(-1).authoring_digest,'prepared-author');
await $('matte').onclick();assert.equal(posts.at(-1).action,'matte');
assert.equal(posts.at(-1).base_revision,'rev-002');assert.equal(posts.at(-1).inputs_digest,'prepared-draft');
""")


def test_reload_prepared_exposure_reports_unavailable_clipping_without_blocking():
    run_page(r"""
servedState.working_revision='rev-002';servedState.inputs_digest='prepared-draft';servedState.authoring_digest='prepared-author';
servedState.revisions.push({revision:'rev-002',kind:'prepare',draft_digest:'prepared-draft',final_acceptable:false,candidates:[],local_exposure:{enabled:true,stale:false,settings:{enabled:true,ev:1}}});
await ready();
assert($('exposureStatus').textContent.includes('clipping unavailable'),$('exposureStatus').textContent);
assert(!$('exposureStatus').textContent.includes('clipped 0'),'Invented zero clipping counts');
identity.base_revision='rev-old';$('viewRevision').value='rev-001';$('photoReviewed').checked=true;$('trimapReviewed').checked=true;
await $('reload').onclick();
assert.equal(identity.base_revision,'rev-002');assert.equal(identity.inputs_digest,'prepared-draft');
assert.equal($('viewRevision').value,'rev-002');assert.equal($('photoReviewed').checked,false);assert.equal($('trimapReviewed').checked,false);
assert.equal($('trimap').disabled,false);assert.equal($('matte').disabled,false);
assert.equal($('message').textContent,'');
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


def test_fade_native_area_and_amount_reset_keep_independent_dirty_drafts():
    run_page(r"""
await ready();$('authorMode').value='fade';$('fadeRole').value='regions';$('fadeShape').value='rectangle';$('fadeFeather').value='2';
$('crop').value='20,20,80,80';await $('cropApply').onclick();
canvas.onpointerdown({clientX:100,clientY:50,pointerId:1,shiftKey:false});
canvas.onpointerup({clientX:200,clientY:150,pointerId:1});
assert.deepEqual(fadeArea.regions[0].xyxy,[35,35,65,65]);
assert.equal(fadeArea.regions[0].feather_px,2);assert.equal(regions.length,0);assert.equal(exposureArea.regions.length,0);
$('fadeRole').value='protection';$('fadeRectangle').value='40,40,50,50';await $('fadeAddRectangle').onclick();
assert.equal(fadeArea.protection[0].feather_px,0);
const draft=JSON.stringify(fadeArea);$('fadeAmount').value='50';$('fadePreserve').value='70';$('fadeCandidate').checked=true;
await $('fadeAmountApply').onclick();
assert.equal(posts.at(-1).shadow_fade_amount_only,true);assert(!('shadow_fade_area' in posts.at(-1)));assert(!('local_exposure' in posts.at(-1)));
assert.deepEqual(posts.at(-1).shadow_fade,{enabled:true,amount:.5,preserve_highlights:.7});
assert.equal(JSON.stringify(fadeArea),draft);assert.equal(fadeDirty,true);
servedState.revisions[0].shadow_fade={settings:structuredClone(posts.at(-1).shadow_fade)};actionWasRunning=false;await refresh();$('fadePreserve').value='70';await $('fadeReset').onclick();
assert.deepEqual(posts.at(-1).shadow_fade,{enabled:false,amount:0,preserve_highlights:.7});
assert.equal(JSON.stringify(fadeArea),draft);assert.equal(fadeDirty,true);assert.equal(dirty,false);
""")


def test_fade_comparisons_are_mutually_exclusive_and_labels_match_route():
    run_page(r"""
await ready();const paths=[];const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{paths.push(path);return originalFetch(path.replace('/shadow-fade-off','').replace('/exposure-off','').replace('/base',''),options);};
$('panel').value='black';$('cleanupBase').checked=true;await $('cleanupBase').onchange();
$('fadeCompare').checked=true;await $('fadeCompare').onchange();
assert.equal($('cleanupBase').checked,false);assert.equal($('exposureCompare').checked,false);
assert(paths.at(-1).endsWith('/shadow-fade-off'));assert($('shadingStatus').textContent.includes('Shadow fade OFF comparison'));
$('exposureCompare').checked=true;await $('exposureCompare').onchange();
assert.equal($('fadeCompare').checked,false);assert(paths.at(-1).endsWith('/exposure-off'));
assert($('shadingStatus').textContent.includes('fade recalculated'));
$('cleanupBase').checked=true;await $('cleanupBase').onchange();
assert.equal($('fadeCompare').checked,false);assert.equal($('exposureCompare').checked,false);assert(paths.at(-1).endsWith('/base'));
assert.equal(posts.length,0);
""")


def test_fade_rejects_stale_view_and_prepared_reload_recovers_saved_area():
    run_page(r"""
servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.35,preserve_highlights:.8}};
servedState.revisions[0].shadow_fade_area={regions:[{id:'a',role:'support',shape:'rectangle',xyxy:[1,2,40,50],feather_px:2}],protection:[]};
await ready();assert.equal($('fadeAmount').value,35);assert.equal(fadeArea.regions.length,1);
$('viewRevision').value='old';await $('fadeAmountApply').onclick();assert.equal(posts.length,0);
$('viewRevision').value='rev-001';$('authorMode').value='fade';$('fadeShape').value='stroke';$('fadeRole').value='regions';$('fadeRadius').value='3';$('fadeFeather').value='1';
imageLoading=true;canvas.onpointerdown({clientX:70,clientY:20,pointerId:1,shiftKey:false});canvas.onpointerup({clientX:80,clientY:30,pointerId:1});assert.equal(fadeArea.regions.length,1);
imageLoading=false;canvas.onpointerdown({clientX:70,clientY:20,pointerId:2,shiftKey:false});canvas.onpointermove({clientX:90,clientY:40});canvas.onpointerup({clientX:90,clientY:40,pointerId:2});assert.equal(fadeArea.regions[1].radius_px,3);
await $('reload').onclick();assert.equal(fadeArea.regions.length,1);assert.equal(fadeDirty,false);
""")


def test_background_completion_preserves_all_pending_subject_controls():
    run_page(r"""
await ready();
const pending = {
 cleanupSupport:'pending-cleanup16.png',
 shadingSupport:'pending-shading16.png',shadingProtection:'pending-protection16.png',
 shadingWidth:'17',shadingDirection:'78',shadingOpacity:'.22',
 exposureEV:'1.5',exposureRange:'1.5',fadeAmount:'37',fadeRange:'37',
 fadePreserve:'82',fadePreserveRange:'82'
};
for(const [id,value] of Object.entries(pending))$(id).value=value;
const candidates=['cleanupCandidate','shadingCandidate','exposureCandidate','fadeCandidate'];
for(const id of candidates){$(id).type='checkbox';$(id).checked=true;}
const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 if(options.method==='POST'){
   const payload=JSON.parse(options.body);
   assert.deepEqual(payload.background,{color_srgb:'#243050',variation:.55});
   assert(!('shading' in payload));assert(!('color_cleanup' in payload));
   servedState.working_revision='rev-002';servedState.inputs_digest='next-draft';
   servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',draft_digest:'next-draft',
     background:{settings:payload.background}});
   servedState.action={name:'effects',running:false,error:null,result:{revision:'rev-002'}};
 }
 return originalFetch(path,options);
};
$('backgroundHex').value='#243050';$('backgroundVariation').value='55';
await $('backgroundApply').onclick();
assert.equal(identity.base_revision,'rev-002');
assert.equal($('backgroundStatus').textContent,'Saved background · rev-002 · #243050 · variation 55%');
for(const [id,value] of Object.entries(pending))assert.equal($(id).value,value,'Background discarded '+id);
for(const id of candidates)assert.equal($(id).checked,true,'Background discarded '+id);
await $('reload').onclick();
assert.equal($('shadingWidth').value,'');assert.equal($('shadingCandidate').checked,false);
assert.equal($('cleanupSupport').value,'revisions/rev-002/supports/support16.png');
""")


@pytest.mark.parametrize("control", ["exposureEV", "exposureRange", "exposureCandidate"])
def test_export_completion_preserves_unsaved_exposure_controls(control):
    run_page(
        r"""
servedState.revisions[0].local_exposure={enabled:true,stale:false,settings:{enabled:true,ev:.5},clipping:{clipped_pixels:0,eligible_pixels:100}};
await ready();
const control=CONTROL;
if(control==='exposureCandidate') {$(control).checked=true;$(control).onchange?.();}
else {$(control).value='1.2';$(control).oninput();}
const draft={ev:Number($('exposureEV').value),range:Number($('exposureRange').value),candidate:$('exposureCandidate').checked};
await poll();
assert.deepEqual({ev:Number($('exposureEV').value),range:Number($('exposureRange').value),candidate:$('exposureCandidate').checked},draft,'Idle poll changed exposure controls');
const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST')servedState.action={name:'export',running:false,error:null,result:{revision:'rev-001',directory:'exports/rev-001'}};
 return response;
};
await $('exportAccepted').onclick();assert.equal(posts.at(-1).action,'export');
assert.deepEqual({ev:Number($('exposureEV').value),range:Number($('exposureRange').value),candidate:$('exposureCandidate').checked},draft,'Export discarded pending exposure controls');
assert.equal(dirty,false,'Exposure controls dirtied matting guides');
assert($('exposureDraftStatus').textContent.includes('Unsaved exposure settings'));
""".replace("CONTROL", repr(control))
    )


@pytest.mark.parametrize("button", ["exposureAmount", "exposureApply", "exposureReset"])
def test_applied_exposure_controls_clear_only_after_success_and_keep_area_semantics(button):
    run_page(
        r"""
const savedArea={regions:[{id:'saved-area',role:'support',shape:'rectangle',xyxy:[10,10,40,40],feather_px:0}],protection:[]};
servedState.revisions[0].exposure_area=structuredClone(savedArea);
servedState.revisions[0].local_exposure={enabled:true,stale:false,settings:{enabled:true,ev:.5},clipping:{clipped_pixels:0,eligible_pixels:100}};
await ready();$('exposureEV').value='1.2';$('exposureEV').oninput();$('exposureCandidate').checked=true;$('exposureCandidate').onchange?.();
$('exposureRole').value='regions';$('exposureShape').value='rectangle';$('exposureFeather').value='0';$('exposureRectangle').value='50,50,60,60';await $('exposureAddRectangle').onclick();
const areaDraft=JSON.stringify(exposureArea),button=BUTTON;
const originalFetch=globalThis.fetch;let release;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'){
   const sent=JSON.parse(options.body),record={enabled:sent.local_exposure.enabled,stale:false,settings:sent.local_exposure,clipping:{clipped_pixels:0,eligible_pixels:100}};
   servedState.working_revision='rev-002';servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',local_exposure:record,exposure_area:sent.exposure_area||savedArea});
   servedState.action={name:'effects',running:false,error:null,result:{revision:'rev-002',parent:sent.base_revision,local_exposure:record}};
   return new Promise(resolve=>{release=()=>resolve(response);});
 }
 return response;
};
const applying=$(button).onclick();for(let i=0;i<30&&!release;i++)await Promise.resolve();assert(release);
for(const id of ['exposureEV','exposureRange','exposureCandidate'])assert.equal($(id).disabled,true,'Editable control could change after payload serialization: '+id);
release();await applying;
assert.equal(Number($('exposureEV').value),button==='exposureReset'?0:1.2);assert.equal(Number($('exposureRange').value),button==='exposureReset'?0:1.2);
assert.equal($('exposureCandidate').checked,false);assert(!$('exposureDraftStatus').textContent.includes('Unsaved exposure settings'));
assert.equal(JSON.stringify(exposureArea),areaDraft);
assert.equal(exposureDirty,button!=='exposureApply','Controls changed independent area publication state');
for(const id of ['exposureEV','exposureRange','exposureCandidate'])assert.equal($(id).disabled,false);
""".replace("BUTTON", repr(button))
    )


@pytest.mark.parametrize("failure", ["dispatch", "processing", "other_action_result"])
def test_exposure_failure_or_other_action_result_keeps_pending_controls_for_retry(failure):
    run_page(
        r"""
servedState.revisions[0].local_exposure={enabled:true,stale:false,settings:{enabled:true,ev:.5},clipping:{clipped_pixels:0,eligible_pixels:100}};
await ready();$('exposureEV').value='1.2';$('exposureEV').oninput();$('exposureCandidate').checked=true;$('exposureCandidate').onchange?.();
const originalFetch=globalThis.fetch,failure=FAILURE;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'){
   if(failure==='dispatch')throw Error('Synthetic rejected dispatch');
   servedState.action=failure==='processing'?{name:'effects',running:false,error:'Synthetic processing failure',result:null}:{name:'export',running:false,error:null,result:{directory:'exports/rev-001'}};
 }
 return response;
};
await $('exposureAmount').onclick();
for(const id of ['exposureEV','exposureRange','exposureCandidate'])assert.equal($(id).disabled,false,'Failure left controls disabled');
assert.equal(Number($('exposureEV').value),1.2);assert.equal($('exposureCandidate').checked,true);
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST')servedState.action={name:'export',running:false,error:null,result:{directory:'exports/rev-001'}};
 return response;
};
await $('exportAccepted').onclick();
assert.equal(Number($('exposureEV').value),1.2);assert.equal(Number($('exposureRange').value),1.2);assert.equal($('exposureCandidate').checked,true);
assert($('exposureDraftStatus').textContent.includes('Unsaved exposure settings'));
""".replace("FAILURE", repr(failure))
    )


def test_exposure_control_draft_stays_bound_after_restore_and_explicit_reload_recovers():
    run_page(r"""
const record={enabled:true,stale:false,settings:{enabled:true,ev:.5},clipping:{clipped_pixels:0,eligible_pixels:100}};
servedState.revisions[0].local_exposure=record;servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',local_exposure:record});
await ready();$('exposureEV').value='1.2';$('exposureEV').oninput();$('exposureCandidate').checked=true;$('exposureCandidate').onchange?.();
$('restoreRevision').value='rev-002';const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'&&JSON.parse(options.body).action==='restore'){
   servedState.working_revision='rev-002';servedState.inputs_digest='restored-draft';servedState.authoring_digest='restored-author';
   servedState.action={name:'restore',running:false,error:null,result:{revision:'rev-002'}};
 }
 return response;
};
await $('restore').onclick();
assert.equal(identity.base_revision,'rev-002');assert.equal(Number($('exposureEV').value),1.2);assert.equal($('exposureCandidate').checked,true);
assert($('exposureDraftStatus').textContent.includes('Stale exposure settings'),$('exposureDraftStatus').textContent);
const before=posts.length;await $('exposureAmount').onclick();assert.equal(posts.length,before,'Applied controls against a different project identity');
assert.match($('message').textContent,/reload/i);
await $('reload').onclick();assert.equal(Number($('exposureEV').value),.5);assert.equal(Number($('exposureRange').value),.5);assert.equal($('exposureCandidate').checked,false);
assert(!$('exposureDraftStatus').textContent.includes('Stale exposure settings'));
$('exposureEV').value='1.2';$('exposureEV').oninput();$('exposureCandidate').checked=true;$('exposureCandidate').onchange?.();
await $('exposureAmount').onclick();assert.equal(posts.at(-1).action,'effects');assert.equal(posts.at(-1).base_revision,'rev-002');assert.equal(posts.at(-1).inputs_digest,'restored-draft');
""")


@pytest.mark.parametrize(
    "control", ["fadeAmount", "fadeRange", "fadePreserve", "fadePreserveRange", "fadeCandidate"]
)
def test_export_completion_preserves_unsaved_fade_controls(control):
    run_page(
        r"""
servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.5,preserve_highlights:.8}};
await ready();
const control=CONTROL;
if(control==='fadeCandidate') {$(control).checked=true;$(control).onchange?.();}
else {$(control).value='65';$(control).oninput();}
const draft={amount:Number($('fadeAmount').value),range:Number($('fadeRange').value),preserve:Number($('fadePreserve').value),preserveRange:Number($('fadePreserveRange').value),candidate:$('fadeCandidate').checked};
await poll();
assert.deepEqual({amount:Number($('fadeAmount').value),range:Number($('fadeRange').value),preserve:Number($('fadePreserve').value),preserveRange:Number($('fadePreserveRange').value),candidate:$('fadeCandidate').checked},draft,'Idle poll changed fade controls');
const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST')servedState.action={name:'export',running:false,error:null,result:{revision:'rev-001',directory:'exports/rev-001'}};
 return response;
};
await $('exportAccepted').onclick();assert.equal(posts.at(-1).action,'export');
assert.deepEqual({amount:Number($('fadeAmount').value),range:Number($('fadeRange').value),preserve:Number($('fadePreserve').value),preserveRange:Number($('fadePreserveRange').value),candidate:$('fadeCandidate').checked},draft,'Export discarded pending fade controls');
assert.equal(dirty,false,'Shadow fade controls dirtied matting guides');
assert($('fadeDraftStatus').textContent.includes('Unsaved Shadow fade settings'));
""".replace("CONTROL", repr(control))
    )


@pytest.mark.parametrize("effect", ["exposure", "fade"])
def test_reused_effect_completion_clears_only_matching_submission(effect):
    """A reused result has a historical parent, while unrelated controls stay pending."""
    run_page(
        r"""
const effect=EFFECT;
servedState.revisions[0].local_exposure={enabled:true,stale:false,settings:{enabled:true,ev:.5}};
servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.5,preserve_highlights:1}};
await ready();
$('cleanupSupport').value='pending-cleanup.png';$('shadingWidth').value='123';
$('backgroundHex').value='#223344';$('backgroundHex').oninput();
if(effect==='exposure'){$('exposureEV').value='.5';$('exposureEV').oninput();$('exposureCandidate').checked=true;}
else {$('fadeAmount').value='50';$('fadeAmount').oninput();$('fadeCandidate').checked=true;}
const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'){
   const sent=JSON.parse(options.body);
   servedState.action={name:'effects',running:false,error:null,result:{revision:'rev-001',parent:'rev-000',reused:true,
     local_exposure:servedState.revisions[0].local_exposure,shadow_fade:servedState.revisions[0].shadow_fade}};
   assert.equal(sent.base_revision,'rev-001');
 }
 return response;
};
await $(effect==='exposure'?'exposureAmount':'fadeAmountApply').onclick();
assert.equal($(effect==='exposure'?'exposureCandidate':'fadeCandidate').checked,false);
assert(!$(effect==='exposure'?'exposureDraftStatus':'fadeDraftStatus').textContent.includes('Unsaved '+(effect==='exposure'?'exposure settings':'Shadow fade settings')));
assert.equal($('cleanupSupport').value,'pending-cleanup.png');assert.equal($('shadingWidth').value,'123');
assert.equal($('backgroundHex').value,'#223344');assert.equal(backgroundDirty,true);
assert($('result').textContent.includes('Reused'));
await refresh();assert.equal($('cleanupSupport').value,'pending-cleanup.png');
""".replace("EFFECT", repr(effect))
    )


@pytest.mark.parametrize("effect", ["exposure", "fade"])
@pytest.mark.parametrize("completion", ["success", "error", "other-revision", "other-settings"])
def test_reused_reset_synchronizes_only_matching_submitted_controls(effect, completion):
    run_page(
        r"""
const effect=EFFECT,completion=COMPLETION;
servedState.revisions[0].local_exposure={enabled:false,stale:false,settings:{enabled:false,ev:0}};
servedState.revisions[0].shadow_fade={enabled:false,stale:false,settings:{enabled:false,amount:0,preserve_highlights:.3}};
await ready();
$('exposureEV').value='1.2';$('exposureEV').oninput();$('exposureCandidate').checked=true;$('exposureCandidate').onchange?.();
$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadeCandidate').checked=true;$('fadeCandidate').onchange?.();
for(const prefix of ['exposure','fade']) {
 $(prefix+'Role').value='regions';$(prefix+'Shape').value='rectangle';$(prefix+'Feather').value='0';
 $(prefix+'Rectangle').value='50,50,60,60';await $(prefix+'AddRectangle').onclick();
}
$('cleanupSupport').value='pending-cleanup.png';$('shadingWidth').value='123';$('geometry').value='17,23';
$('backgroundHex').value='#223344';$('backgroundHex').oninput();
$('framingLeft').value='7';$('framingLeft').oninput();$('seriesName').value='Pending series';$('seriesName').oninput();
const drafts=JSON.stringify({exposureArea,fadeArea,groups,regions,identity,exposureDirty,fadeDirty,backgroundDirty,framingDirty,seriesDirty});
const unrelated=effect==='exposure'?fadeControlsIdentity:exposureControlsIdentity;
const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST') {
  const sent=JSON.parse(options.body);
  assert.deepEqual(effect==='exposure'?sent.local_exposure:sent.shadow_fade,
    effect==='exposure'?{enabled:false,ev:0}:{enabled:false,amount:0,preserve_highlights:.3});
  const exposure=structuredClone(servedState.revisions[0].local_exposure),fade=structuredClone(servedState.revisions[0].shadow_fade);
  if(completion==='other-settings') {exposure.settings.ev=.2;fade.settings.amount=.2;}
  servedState.action={name:'effects',running:false,error:completion==='error'?'synthetic failure':null,
   result:{revision:completion==='other-revision'?'rev-old':'rev-001',parent:'rev-000',reused:true,local_exposure:exposure,shadow_fade:fade}};
 }
 return response;
};
await $(effect==='exposure'?'exposureReset':'fadeReset').onclick();
const success=completion==='success';
assert.equal(Number($('exposureEV').value),success&&effect==='exposure'?0:1.2);
assert.equal(Number($('exposureRange').value),success&&effect==='exposure'?0:1.2);
assert.equal(Number($('fadeAmount').value),success&&effect==='fade'?0:65);
assert.equal(Number($('fadeRange').value),success&&effect==='fade'?0:65);
assert.equal(Number($('fadePreserve').value),30);assert.equal(Number($('fadePreserveRange').value),30);
assert.equal($(effect==='exposure'?'exposureCandidate':'fadeCandidate').checked,!success);
assert.equal((effect==='exposure'?exposureControlsIdentity:fadeControlsIdentity)===null,success);
assert.equal(effect==='exposure'?fadeControlsIdentity:exposureControlsIdentity,unrelated);
assert.equal(JSON.stringify({exposureArea,fadeArea,groups,regions,identity,exposureDirty,fadeDirty,backgroundDirty,framingDirty,seriesDirty}),drafts);
assert.equal($('cleanupSupport').value,'pending-cleanup.png');assert.equal($('shadingWidth').value,'123');assert.equal($('geometry').value,'17,23');
assert.equal($('backgroundHex').value,'#223344');assert.equal($('framingLeft').value,'7');assert.equal($('seriesName').value,'Pending series');
assert.equal($(effect==='exposure'?'exposureDraftStatus':'fadeDraftStatus').textContent.includes('Unsaved '+(effect==='exposure'?'exposure settings':'Shadow fade settings')),!success);
await refresh();assert.equal(Number($(effect==='exposure'?'exposureEV':'fadeAmount').value),success?0:effect==='exposure'?1.2:65);
""".replace("EFFECT", repr(effect)).replace("COMPLETION", repr(completion))
    )


@pytest.mark.parametrize("effect", ["shading", "exposure", "fade"])
def test_explicit_reload_during_reused_completion_needs_no_submitted_controls(effect):
    run_page(
        r"""
await ready();
const effect=EFFECT,result={revision:'rev-001',parent:'rev-000',reused:true};
if(effect==='exposure')result.local_exposure={settings:{enabled:false,ev:0}};
if(effect==='fade')result.shadow_fade={settings:{enabled:false,amount:0,preserve_highlights:1}};
servedState.action={name:'effects',running:false,error:null,result};
actionWasRunning=true;
await $('reload').onclick();
assert.equal($('message').textContent,'');assert.equal(actionWasRunning,false);
assert.equal(exposureControlsIdentity,null);assert.equal(fadeControlsIdentity,null);
assert.equal(Number($('exposureEV').value),0);assert.equal(Number($('fadeAmount').value),0);
""".replace("EFFECT", repr(effect))
    )


@pytest.mark.parametrize("button", ["fadeAmountApply", "fadeApply", "fadeReset"])
def test_applied_fade_controls_clear_only_after_success_and_keep_area_semantics(button):
    run_page(
        r"""
const savedArea={regions:[{id:'saved-area',role:'support',shape:'rectangle',xyxy:[10,10,40,40],feather_px:0}],protection:[]};
servedState.revisions[0].shadow_fade_area=structuredClone(savedArea);
servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.5,preserve_highlights:.8}};
await ready();$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadePreserve').value='30';$('fadePreserve').oninput();$('fadeCandidate').checked=true;$('fadeCandidate').onchange?.();
$('fadeRole').value='regions';$('fadeShape').value='rectangle';$('fadeFeather').value='0';$('fadeRectangle').value='50,50,60,60';await $('fadeAddRectangle').onclick();
const areaDraft=JSON.stringify(fadeArea),button=BUTTON;
const originalFetch=globalThis.fetch;let release;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'){
   const sent=JSON.parse(options.body),record={enabled:sent.shadow_fade.enabled,stale:false,settings:sent.shadow_fade};
   servedState.working_revision='rev-002';servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',shadow_fade:record,shadow_fade_area:sent.shadow_fade_area||savedArea});
   servedState.action={name:'effects',running:false,error:null,result:{revision:'rev-002',parent:sent.base_revision,shadow_fade:record}};
   return new Promise(resolve=>{release=()=>resolve(response);});
 }
 return response;
};
const applying=$(button).onclick();for(let i=0;i<30&&!release;i++)await Promise.resolve();assert(release);
for(const id of ['fadeAmount','fadeRange','fadePreserve','fadePreserveRange','fadeCandidate'])assert.equal($(id).disabled,true,'Editable control could change after payload serialization: '+id);
release();await applying;
assert.equal(Number($('fadeAmount').value),button==='fadeReset'?0:65);assert.equal(Number($('fadeRange').value),button==='fadeReset'?0:65);
assert.equal(Number($('fadePreserve').value),30);assert.equal(Number($('fadePreserveRange').value),30);
assert.equal($('fadeCandidate').checked,false);assert(!$('fadeDraftStatus').textContent.includes('Unsaved Shadow fade settings'));
assert.equal(JSON.stringify(fadeArea),areaDraft);
assert.equal(fadeDirty,button!=='fadeApply','Controls changed independent area publication state');
for(const id of ['fadeAmount','fadeRange','fadePreserve','fadePreserveRange','fadeCandidate'])assert.equal($(id).disabled,false);
""".replace("BUTTON", repr(button))
    )


@pytest.mark.parametrize("failure", ["dispatch", "processing", "other_action_result"])
def test_fade_failure_or_other_action_result_keeps_pending_controls_for_retry(failure):
    run_page(
        r"""
servedState.revisions[0].shadow_fade={enabled:true,stale:false,settings:{enabled:true,amount:.5,preserve_highlights:.8}};
await ready();$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadePreserve').value='30';$('fadePreserve').oninput();$('fadeCandidate').checked=true;$('fadeCandidate').onchange?.();
const originalFetch=globalThis.fetch,failure=FAILURE;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'){
   if(failure==='dispatch')throw Error('Synthetic rejected dispatch');
   servedState.action=failure==='processing'?{name:'effects',running:false,error:'Synthetic processing failure',result:null}:{name:'export',running:false,error:null,result:{directory:'exports/rev-001'}};
 }
 return response;
};
await $('fadeAmountApply').onclick();
for(const id of ['fadeAmount','fadeRange','fadePreserve','fadePreserveRange','fadeCandidate'])assert.equal($(id).disabled,false,'Failure left controls disabled');
assert.equal(Number($('fadeAmount').value),65);assert.equal(Number($('fadePreserve').value),30);assert.equal($('fadeCandidate').checked,true);
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST')servedState.action={name:'export',running:false,error:null,result:{directory:'exports/rev-001'}};
 return response;
};
await $('exportAccepted').onclick();
assert.equal(Number($('fadeAmount').value),65);assert.equal(Number($('fadeRange').value),65);assert.equal(Number($('fadePreserve').value),30);assert.equal(Number($('fadePreserveRange').value),30);assert.equal($('fadeCandidate').checked,true);
assert($('fadeDraftStatus').textContent.includes('Unsaved Shadow fade settings'));
""".replace("FAILURE", repr(failure))
    )


def test_fade_control_draft_stays_bound_after_restore_and_explicit_reload_recovers():
    run_page(r"""
const record={enabled:true,stale:false,settings:{enabled:true,amount:.5,preserve_highlights:.8}};
servedState.revisions[0].shadow_fade=record;servedState.revisions.push({...servedState.revisions[0],revision:'rev-002',shadow_fade:record});
await ready();$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadePreserve').value='30';$('fadePreserve').oninput();$('fadeCandidate').checked=true;$('fadeCandidate').onchange?.();
$('restoreRevision').value='rev-002';const originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'&&JSON.parse(options.body).action==='restore'){
   servedState.working_revision='rev-002';servedState.inputs_digest='restored-draft';servedState.authoring_digest='restored-author';
   servedState.action={name:'restore',running:false,error:null,result:{revision:'rev-002'}};
 }
 return response;
};
await $('restore').onclick();
assert.equal(identity.base_revision,'rev-002');assert.equal(Number($('fadeAmount').value),65);assert.equal(Number($('fadePreserve').value),30);assert.equal($('fadeCandidate').checked,true);
assert($('fadeDraftStatus').textContent.includes('Stale Shadow fade settings'),$('fadeDraftStatus').textContent);
const before=posts.length;await $('fadeAmountApply').onclick();assert.equal(posts.length,before,'Applied controls against a different project identity');
assert.match($('message').textContent,/reload/i);
await $('reload').onclick();assert.equal(Number($('fadeAmount').value),50);assert.equal(Number($('fadeRange').value),50);assert.equal(Number($('fadePreserve').value),80);assert.equal(Number($('fadePreserveRange').value),80);assert.equal($('fadeCandidate').checked,false);
assert(!$('fadeDraftStatus').textContent.includes('Stale Shadow fade settings'));
$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadePreserve').value='30';$('fadePreserve').oninput();$('fadeCandidate').checked=true;$('fadeCandidate').onchange?.();
await $('fadeAmountApply').onclick();assert.equal(posts.at(-1).action,'effects');assert.equal(posts.at(-1).base_revision,'rev-002');assert.equal(posts.at(-1).inputs_digest,'restored-draft');
""")


@pytest.mark.parametrize("mismatch", ["parent", "enabled", "amount", "preserve_highlights"])
def test_fade_controls_do_not_clear_for_nonmatching_effect_completion(mismatch):
    run_page(
        r"""
await ready();$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadePreserve').value='30';$('fadePreserve').oninput();$('fadeCandidate').checked=true;$('fadeCandidate').onchange?.();
const mismatch=MISMATCH,originalFetch=globalThis.fetch;
globalThis.fetch=async(path,options)=>{
 const response=await originalFetch(path,options);
 if(options.method==='POST'){
   const sent=JSON.parse(options.body),settings={...sent.shadow_fade},result={parent:sent.base_revision,shadow_fade:{settings}};
   if(mismatch==='parent')result.parent='rev-other';
   else settings[mismatch]=mismatch==='enabled'?false:.9;
   servedState.action={name:'effects',running:false,error:null,result};
 }
 return response;
};
await $('fadeAmountApply').onclick();
assert.equal(Number($('fadeAmount').value),65);assert.equal(Number($('fadePreserve').value),30);assert.equal($('fadeCandidate').checked,true);
assert($('fadeDraftStatus').textContent.includes('Unsaved Shadow fade settings'));
""".replace("MISMATCH", repr(mismatch))
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("developed_id", "other-master"),
        ("working_revision", "rev-002"),
        ("inputs_digest", "other-draft"),
        ("authoring_digest", "other-author"),
    ],
)
def test_fade_controls_reject_each_changed_project_identity(field, value):
    run_page(
        r"""
await ready();$('fadeAmount').value='65';$('fadeAmount').oninput();$('fadePreserve').value='30';$('fadePreserve').oninput();
servedState.revisions.push({...servedState.revisions[0],revision:'rev-002'});servedState[FIELD]=VALUE;
await refresh();
assert.equal(Number($('fadeAmount').value),65);assert.equal(Number($('fadePreserve').value),30);
assert($('fadeDraftStatus').textContent.includes('Stale Shadow fade settings'));
await $('fadeAmountApply').onclick();await $('fadeApply').onclick();assert.equal(posts.length,0,'Applied settings to changed inputs');
assert.match($('message').textContent,/reload/i);
""".replace("FIELD", repr(field)).replace("VALUE", repr(value))
    )


def test_comparison_submission_preserves_drafts_binds_crop_and_reports_saved_paths():
    run_page(r"""
 await ready();
 $('comparisonPresentation').value='native';$('comparisonNative').checked=false;
 $('exposureEV').value='1.2';$('exposureEV').oninput();
 $('backgroundHex').value='#AB1234';$('backgroundHex').oninput();
 const selectedCrop=[...crop];
 await $('comparisonSave').onclick();
 let sent=posts.at(-1);
 assert.equal(sent.action,'comparison');assert.equal(sent.revision,'rev-001');
 assert.equal(sent.revision_manifest_sha256,'a'.repeat(64));
 assert.deepEqual(sent.crops,[selectedCrop]);assert.equal(sent.presentation,null);
 assert.equal(sent.retain_native,false);
 servedState.action={name:'comparison',running:false,error:null,result:{comparison_manifest_file:'/synthetic/comparison/manifest.json',reused:false,view:{jpeg_base64:'YWJj',manifest_json:'{}'}}};
 await refresh();
 assert($('comparisonStatus').textContent.includes('/synthetic/comparison/manifest.json'));
 assert.equal($('comparisonOpen').hidden,false);assert($('comparisonOpen').href.startsWith('blob:'));
 assert.equal($('comparisonManifest').hidden,false);
 assert.equal($('exposureEV').value,'1.2');assert.equal($('backgroundHex').value,'#AB1234');
 $('comparisonPresentation').value='add-margins';$('comparisonNative').checked=true;
 await $('comparisonSave').onclick();sent=posts.at(-1);
 assert.equal(sent.presentation.mode,'add-margins');assert.equal(sent.presentation.revision,'rev-001');
 assert.equal(sent.retain_native,true);
 servedState.action={name:'comparison',running:false,error:'Missing bound native evidence',result:null};
 await refresh();assert($('comparisonStatus').textContent.includes('Missing bound native evidence'));
 const count=posts.length;imageLoading=true;await $('comparisonSave').onclick();
 assert.equal(posts.length,count);assert($('message').textContent.includes('Load the matching native crop'));
 """)
