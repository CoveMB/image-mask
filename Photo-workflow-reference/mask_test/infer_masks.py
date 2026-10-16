"""Local-only mask inference; outputs are simple alpha multiplication, not generated imagery."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['HF_HOME']=str(ROOT/'hf_cache')
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
import argparse,json,time,resource,gc,hashlib
import numpy as np
import torch
from PIL import Image,ImageCms
from transformers import AutoModelForImageSegmentation
p=argparse.ArgumentParser();p.add_argument('--indices',default='all');p.add_argument('--long-edge',type=int,default=1024);args=p.parse_args()
# Author-reviewed code hash checks before import/execution.
for name,expected in {'birefnet.py':'2a45b4e0ece72d7c4212bca1a988e7d7e52bfe9f98ec59c58b8809c8a8b7a831','BiRefNet_config.py':'e7b8c2a74f6cea6a59553d517f71d47f2c1d90e670a13416af17c25fe2f3dc52'}.items():
 assert hashlib.sha256((ROOT/'model_review'/name).read_bytes()).hexdigest()==expected
assert json.loads((ROOT/'model_review'/'config.json').read_text())['bb_pretrained'] is False
torch.set_num_threads(6);torch.set_num_interop_threads(2)
torch.manual_seed(0)
started=time.monotonic();model=AutoModelForImageSegmentation.from_pretrained(str(ROOT/'model_review'),trust_remote_code=True,local_files_only=True,use_safetensors=True,torch_dtype=torch.float32).eval()
print(json.dumps({'model_loaded_seconds':round(time.monotonic()-started,2),'parameters':sum(p.numel() for p in model.parameters()),'dtype':'float32','device':'CPU'}),flush=True)
out=ROOT/'deliverables';manifest=json.loads((out/'manifest.json').read_text());icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
selected=None if args.indices=='all' else [int(x) for x in args.indices.split(',')]
mean=torch.tensor([.485,.456,.406]).view(1,3,1,1);std=torch.tensor([.229,.224,.225]).view(1,3,1,1)
for item in manifest['photos']:
 if selected is not None and item['index'] not in selected:continue
 start=time.monotonic();source=Image.open(out/item['master_png']).convert('RGB');w,h=source.size
 scale=args.long_edge/max(w,h);nw=round(w*scale);nh=round(h*scale)
 # Pad with edge pixels up to multiples of 32, preserving content aspect ratio.
 pw=(-nw)%32;ph=(-nh)%32
 image_array=np.asarray(source.resize((nw,nh),Image.Resampling.LANCZOS))
 padded=np.pad(image_array,((0,ph),(0,pw),(0,0)),mode='edge')
 tensor=(torch.from_numpy(padded.copy()).permute(2,0,1).unsqueeze(0).float()/255-mean)/std
 print(json.dumps({'started':item['index'],'subject':item['subject'],'input_wh':[nw+pw,nh+ph],'unpadded_wh':[nw,nh]}),flush=True)
 with torch.inference_mode():prediction=model(tensor)[-1].sigmoid()[0,0,:nh,:nw].cpu().numpy()
 assert np.isfinite(prediction).all()
 alpha_full=np.asarray(Image.fromarray(prediction.astype(np.float32),mode='F').resize((w,h),Image.Resampling.BILINEAR))
 alpha16=np.rint(np.clip(alpha_full,0,1)*65535).astype(np.uint16)
 stem=item['stem'];mask=f'masks/{stem}_soft-mask16.png';black=f'black_composites/{stem}_black.png'
 Image.fromarray(alpha16,mode='I;16').save(out/mask)
 master=np.asarray(source);result=np.rint(master.astype(np.float64)*(alpha16.astype(np.float64)/65535)[...,None]).astype(np.uint8)
 Image.fromarray(result).save(out/black,icc_profile=icc)
 thumb=Image.fromarray(result);thumb.thumbnail((750,1000));thumb.save(out/'previews'/f'{stem}_black.jpg',quality=94,icc_profile=icc)
 item.update({'inference_dimensions_wh':[nw+pw,nh+ph],'inference_content_dimensions_wh':[nw,nh],'padding_right_bottom':[pw,ph],'model_mask_dimensions_wh':[nw,nh],'inference_dtype':'float32','mask_resampling':'Remove right/bottom padding then bilinear resize to developed native dimensions. This is not native-resolution inference.','mask_png':mask,'black_png':black,'alpha_bits':16,'alpha_min':int(alpha16.min()),'alpha_max':int(alpha16.max()),'alpha_soft_fraction':round(float(np.mean((alpha16>655)&(alpha16<64880))),5),'foreground_fraction_at_0_5':round(float(np.mean(alpha16>32767)),5),'inference_and_export_seconds':round(time.monotonic()-start,2),'peak_process_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1)})
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps({'completed':item['index'],'seconds':item['inference_and_export_seconds'],'peak_rss_mb':item['peak_process_rss_mb'],'foreground_fraction':item['foreground_fraction_at_0_5']}),flush=True)
 del tensor,prediction,alpha_full,alpha16,master,result,source,padded,image_array;gc.collect()
