"""Execute the shipped coordinate mapping in Node; no browser/model substitutes."""

import subprocess
from pathlib import Path


def test_inverse_native_transform_points_boxes_and_letterbox(tmp_path):
    script = tmp_path / "coordinates.cjs"
    script.write_text("""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
vm.runInContext(`
for (const size of [[800,600],[1200,260],[360,800]]) {
 for (const zoom of [.5,1,2.75]) {
  for (const pan of [[0,0],[31,-19]]) {
   for (const crop of [[0,0,97,65],[7,5,76,46]]) {
    const t = viewTransform(size, crop, zoom, pan);
    const rect = {left:17,top:23,width:size[0]/2,height:size[1]/2};
    for (const point of [[crop[0]+.25,crop[1]+.75],[crop[2]-.25,crop[3]-.5]]) {
     const client=[rect.left+(t.x+(point[0]-crop[0])*t.scale)/2,rect.top+(t.y+(point[1]-crop[1])*t.scale)/2];
     const native=screenToNative(client,rect,size,t,crop,false);
     if (!native || Math.abs(native[0]-point[0])>1e-10 || Math.abs(native[1]-point[1])>1e-10) throw Error('Incorrect inverse');
    }
    if (screenToNative([rect.left+(t.x-2)/2,rect.top+t.y/2],rect,size,t,crop,false)!==null) throw Error('Letterbox accepted');
    const corner=[rect.left+(t.x+(crop[2]-crop[0])*t.scale)/2,rect.top+(t.y+(crop[3]-crop[1])*t.scale)/2];
    if (screenToNative(corner,rect,size,t,crop,false)!==null) throw Error('Half-open edge accepted as point');
    if (!screenToNative(corner,rect,size,t,crop,true)) throw Error('Half-open box endpoint rejected');
   }
  }
 }
}
const known=viewTransform([1000,600],[7,5,107,55],2,[13,-17]);
if (known.scale!==20 || known.x!==-487 || known.y!==-217) throw Error('Incorrect independently expected transform');
const expected=screenToNative([276,172],{left:17,top:23,width:500,height:300},[1000,600],known,[7,5,107,55],false);
if (JSON.stringify(expected)!=='[57.25,30.75]') throw Error('Incorrect independently expected native point');
const box=nativeBox([15.8,9.2],[7.1,5.9]);
if (JSON.stringify(box)!=='[7,5,16,10]') throw Error('Wrong half-open rounding');
`,context);
""")
    completed = subprocess.run(
        ["node", str(script), str(Path("src/blackmask/ui/coordinates.js").resolve())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_spatial_handles_share_native_rotation_and_real_arc_midpoint(tmp_path):
    script = tmp_path / "spatial-coordinates.cjs"
    script.write_text("""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({});vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
vm.runInContext(`
const arc={center_xy:[30,40],rotation_degrees:90,half_span:20,bend:10,transition_width:8,end_softness:5,fade_side:'positive'};
const handles=spatialHandles(arc,false);
const close=(a,b)=>{if(Math.hypot(a[0]-b[0],a[1]-b[1])>1e-9)throw Error(JSON.stringify([a,b]));};
close(handles.find(h=>h.name==='bend').point,[20,40]);
close(handles.find(h=>h.name==='width').point,[12,40]);
close(handles.find(h=>h.name==='span-positive').point,[30,60]);
close(handles.find(h=>h.name==='span-negative').point,[30,20]);
if(handles.filter(h=>h.name.startsWith('soft-')).length!==2)throw Error('Both soft end handles required');
for(const handle of handles)if(hitSpatialHandle(handle.point,handles,.01)?.name!==handle.name)throw Error('Handle hit mismatch');
close(spatialToLocal(spatialToNative([7,-13],arc),arc),[7,-13]);
for(const crop of [[0,0,100,100],[10,15,70,85]])for(const zoom of [.5,2.75]){
 const size=[600,400],rect={left:12,top:8,width:300,height:200},t=viewTransform(size,crop,zoom,[31,-17]);
 const point=[35.25,48.75],screen=nativeToScreen(point,rect,size,t,crop);
 close(screenToNative(screen,rect,size,t,crop),point);
}
const oval={center_xy:[30,40],rotation_degrees:0,inner_radii_xy:[5,12],transition_width:8};
const ovalHandles=spatialHandles(oval,true);
close(ovalHandles.find(h=>h.name==='radius-x').point,[35,40]);
close(ovalHandles.find(h=>h.name==='width').point,[43,40]);
`,context);
""")
    completed = subprocess.run(
        ["node", str(script), str(Path("src/blackmask/ui/coordinates.js").resolve())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
