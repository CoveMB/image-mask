"""Source-preserving SAM2 guide and native-pixel ViTMatte tile runner.

No image synthesis. Neither stage alters the input RGB. The SAM2 overview is
resized by its standard processor; matting inputs are native-resolution crops.
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from pathlib import Path
import argparse, gc, hashlib, json, time
import numpy as np
import torch
from PIL import Image

ROOT=Path(__file__).resolve().parent

def origins(length, tile, stride):
    if length <= tile:
        return [0]
    starts=list(range(0,length-tile+1,stride))
    if starts[-1] != length-tile:
        starts.append(length-tile)
    return starts

def weights(h,w,x,y,width,height,overlap):
    wx=np.ones(w,dtype=np.float32);wy=np.ones(h,dtype=np.float32)
    nx=min(overlap,w//2);ny=min(overlap,h//2)
    if nx:
        ramp=np.sin((np.arange(nx,dtype=np.float32)+.5)/nx*np.pi/2)**2
        if x>0:wx[:nx]=ramp
        if x+w<width:wx[-nx:]=ramp[::-1]
    if ny:
        ramp=np.sin((np.arange(ny,dtype=np.float32)+.5)/ny*np.pi/2)**2
        if y>0:wy[:ny]=ramp
        if y+h<height:wy[-ny:]=ramp[::-1]
    return wy[:,None]*wx[None,:]

def save_outputs(source, alpha, out):
    rgb=np.asarray(source)
    a16=np.rint(np.clip(alpha,0,1)*65535).astype(np.uint16)
    Image.fromarray(a16).save(out/'mask16.png')
    # Composite is exactly the decoded source multiplied by this saved mask.
    comp=np.rint(rgb.astype(np.float64)*(a16.astype(np.float64)/65535)[...,None]).astype(np.uint8)
    Image.fromarray(comp).save(out/'black.png')
    Image.fromarray(np.dstack([rgb,np.rint(a16/257).astype(np.uint8)])).save(out/'transparent.png')
    source.save(out/'aligned_source.png')
    # Verify round trip dimensions and arithmetic from the saved file bytes.
    reloaded=np.asarray(Image.open(out/'mask16.png')).astype(np.uint16)
    assert np.array_equal(a16,reloaded)
    assert np.array_equal(comp,np.asarray(Image.open(out/'black.png')))
    assert np.array_equal(rgb,np.asarray(Image.open(out/'aligned_source.png')))
    return {'source_dimensions':list(source.size),'source_rgb_preserved':True,
            'composite_verified':True,'alpha_bits':16,
            'foreground_fraction_at_0_5':float(np.mean(alpha>.5))}

def sam(args):
    from transformers import Sam2Model,Sam2Processor
    source=Image.open(args.source).convert('RGB');out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    prompts=json.loads(Path(args.prompts).read_text())
    processor=Sam2Processor.from_pretrained(ROOT/'models/sam2',local_files_only=True)
    model=Sam2Model.from_pretrained(ROOT/'models/sam2',local_files_only=True,use_safetensors=True,dtype=torch.float32).eval()
    records=[]
    for obj in prompts:
        start=time.monotonic();kw={}
        if obj.get('points'):
            kw.update(input_points=[[obj['points']]],input_labels=[[obj['labels']]])
        if obj.get('box'):
            kw['input_boxes']=[[obj['box']]]
        inputs=processor(images=source,return_tensors='pt',**kw)
        with torch.inference_mode():prediction=model(**inputs,multimask_output=True)
        masks=processor.post_process_masks(prediction.pred_masks.cpu(),inputs['original_sizes'])[0][0].numpy()
        scores=prediction.iou_scores.cpu().numpy()[0,0]
        for i,mask in enumerate(masks):
            Image.fromarray(mask.astype(np.uint8)*255).save(out/f"{obj['name']}_candidate{i}.png")
        rec={'prompt':obj,'scores':scores.tolist(),'seconds':round(time.monotonic()-start,2),'guide_input_shape':list(inputs['pixel_values'].shape),'source_dimensions':list(source.size)}
        records.append(rec);print(json.dumps(rec),flush=True)
    (out/'sam_metadata.json').write_text(json.dumps(records,indent=2))

def matte(args):
    from transformers import VitMatteForImageMatting,VitMatteImageProcessor
    source=Image.open(args.source).convert('RGB');trimap=Image.open(args.trimap).convert('L')
    assert source.size==trimap.size,'Source and trimap dimensions must match exactly.'
    tri=np.asarray(trimap);assert set(np.unique(tri)) <= {0,128,255},'Trimap must contain only 0,128,255.'
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    width,height=source.size;tile=args.tile;overlap=args.overlap
    assert tile>overlap>0 and tile%32==0
    processor=VitMatteImageProcessor.from_pretrained(ROOT/'models/vitmatte',local_files_only=True)
    model=VitMatteForImageMatting.from_pretrained(ROOT/'models/vitmatte',local_files_only=True,use_safetensors=True,dtype=torch.float32).eval()
    sums=np.zeros((height,width),np.float32);squares=sums.copy();norm=sums.copy();count=np.zeros_like(sums,dtype=np.uint16)
    records=[];started=time.monotonic()
    for y in origins(height,tile,tile-overlap):
        for x in origins(width,tile,tile-overlap):
            box=(x,y,min(x+tile,width),min(y+tile,height));w=box[2]-x;h=box[3]-y
            tr=tri[y:y+h,x:x+w];t=time.monotonic();unknown=bool(np.any(tr==128))
            if unknown:
                inputs=processor(images=source.crop(box),trimaps=trimap.crop(box),return_tensors='pt')
                with torch.inference_mode():prediction=model(**inputs).alphas[0,0,:h,:w].cpu().numpy()
                assert np.isfinite(prediction).all()
                prediction=np.clip(prediction,0,1)
                del inputs
            else:
                prediction=(tr==255).astype(np.float32)
            wt=weights(h,w,x,y,width,height,overlap)
            sums[y:y+h,x:x+w]+=prediction*wt;squares[y:y+h,x:x+w]+=prediction**2*wt
            norm[y:y+h,x:x+w]+=wt;count[y:y+h,x:x+w]+=1
            rec={'crop_xyxy':box,'native_pixels':True,'inferred':unknown,'seconds':round(time.monotonic()-t,2)}
            records.append(rec);print(json.dumps(rec),flush=True)
    assert np.all(norm>0)
    alpha=np.clip(sums/norm,0,1)
    disagreement=np.sqrt(np.maximum(0,squares/norm-alpha**2))
    np.save(out/'unconstrained_model_alpha.npy',alpha)
    # Matting must not turn verified opaque anatomy transparent or regrow background.
    alpha[tri==0]=0;alpha[tri==255]=1
    meta=save_outputs(source,alpha,out)
    Image.fromarray(np.rint(np.clip(disagreement*4,0,1)*255).astype(np.uint8)).save(out/'tile_disagreement_x4.png')
    trimap.save(out/'trimap.png')
    samples=disagreement[(tri==128)&(count>1)]
    meta.update({'source_sha256':hashlib.sha256(Path(args.source).read_bytes()).hexdigest(),
        'method':'SAM2 guided trimap then native-pixel ViTMatte overlapping crops',
        'matte_no_downsampling':True,'tile_size':tile,'overlap':overlap,'tiles':records,
        'overlap_unknown_disagreement_p95':float(np.percentile(samples,95)) if len(samples) else 0,
        'total_seconds':round(time.monotonic()-started,2),
        'limitations':'Mask only; source RGB, focus, geometry and background contamination inside translucent material are unchanged. No foreground colour decontamination.'})
    (out/'metadata.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['sam','matte']);p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--prompts');p.add_argument('--trimap');p.add_argument('--tile',type=int,default=1024);p.add_argument('--overlap',type=int,default=256)
    a=p.parse_args();torch.set_num_threads(6);torch.set_num_interop_threads(2);torch.manual_seed(0)
    if a.stage=='sam':assert a.prompts;sam(a)
    else:assert a.trimap;matte(a)
