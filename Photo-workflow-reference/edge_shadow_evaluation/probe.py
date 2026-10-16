"""Throwaway deterministic evaluation. Original photograph pixels + existing alpha only."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter
import json, hashlib, shutil, zipfile
ROOT=Path(__file__).parent
INPUT=ROOT.parent/'mask_test/deliverables'
OUT=ROOT/'assets'; OUT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(s): return ImageFont.truetype(FONT,s)
def smooth(x):
 x=np.clip(x,0,1); return x*x*(3-2*x)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[dict(stem='01_1000036098',name='Grasshopper',width=48,protect=14,crop=(1450,1390,1962,1902)),dict(stem='05_1000035853',name='Pink-dahlia',width=88,protect=14,crop=(365,1900,877,2412))]
summary=[]; sheets=[]
for c in cases:
 st=c['stem']; folder=OUT/c['name'];folder.mkdir(exist_ok=True)
 srcp=INPUT/'masters_png'/f'{st}_developed.png';maskp=INPUT/'masks'/f'{st}_soft-mask16.png'
 srcim=Image.open(srcp).convert('RGB'); rgb=np.asarray(srcim).astype(np.float32)/255
 ai=Image.open(maskp); a=np.asarray(ai).astype(np.float32)/65535
 assert srcim.size==ai.size==(3072,4080)
 s0,m0=sha(srcp),sha(maskp)
 # Inward distance to the existing 50% silhouette. Neither RGB nor base alpha is edited.
 d=distance_transform_edt(a>=0.5).astype(np.float32)
 edge=1-smooth(d/c['width'])
 # A thickness gate prevents an all-around dark stroke on isolated narrow structures.
 core=d>=c['protect']
 dc=distance_transform_edt(~core).astype(np.float32)
 thick=1-smooth((dc-c['protect'])/8)
 thick=gaussian_filter(thick,2)
 # Direction weighting: side/bottom edges receive more shade than top-facing edges.
 shape=gaussian_filter(a,12)
 gy,gx=np.gradient(shape); mag=np.hypot(gx,gy)
 ny=np.divide(-gy,mag,out=np.zeros_like(gy),where=mag>1e-5)
 direction=0.35+0.65*smooth((ny+1)/2)
 # Broad luminance protection retains bright rim highlights; never synthesize detail.
 lum=rgb[:,:,0]*0.2126+rgb[:,:,1]*0.7152+rgb[:,:,2]*0.0722
 light=gaussian_filter(lum,6)
 highlights=1-0.75*smooth((light-0.68)/0.25)
 weight=edge*thick*direction*highlights
 # Preserve almost-transparent photographed edges and avoid shading empty background.
 weight*=smooth(a/0.35)
 weight[a==0]=0
 weight[d>=c['width']]=0
 # Quantize the reusable relative shadow mask once to 16-bit.
 wi=np.rint(np.clip(weight,0,1)*65535).astype(np.uint16);w=wi.astype(np.float32)/65535
 Image.fromarray(wi).save(folder/'SHADOW_WEIGHT_16BIT.png')
 shutil.copy2(maskp,folder/'BASE_SUBJECT_MASK_16BIT.png')
 # A black layer carrying alpha is convenient in any layer-capable editor.
 # At 100% layer opacity these two PNGs bake only the effect strength into alpha.
 comps=[]
 for variant,opacity in [('Baseline',0),('Subtle',0.12),('Moderate',0.24)]:
  atten=(1-opacity*w)
  comp=np.rint(rgb*255*a[:,:,None]*atten[:,:,None]).clip(0,255).astype(np.uint8)
  im=Image.fromarray(comp);comps.append(im)
  if opacity:
   layer=np.zeros((*a.shape,4),np.uint8);layer[:,:,3]=np.rint(opacity*w*255).astype(np.uint8)
   Image.fromarray(layer).save(folder/f'{variant.upper()}_BLACK_LAYER_RGBA.png')
   im.save(folder/f'{variant.upper()}_FULLSIZE_PREVIEW.png',icc_profile=srcim.info.get('icc_profile',b''))
  assert np.array_equal(comp[a==0],np.zeros_like(comp[a==0]))
  assert np.array_equal(comp[d>=c['width']],np.rint(rgb*255*a[:,:,None]).astype(np.uint8)[d>=c['width']])
 assert sha(srcp)==s0 and sha(maskp)==m0
 # Explicit fine-detail QA crops: an isolated antenna and centre of flower/bee.
 pbox=(2000,1230,2520,1580) if c['name']=='Grasshopper' else (1080,1880,1680,2480)
 x0,y0,x1,y1=pbox
 diff=np.abs(np.asarray(comps[2]).astype(int)-np.asarray(comps[0]).astype(int))
 result=dict(**c,dimensions=[3072,4080],source_filename=srcp.name,source_sha256=s0,base_mask_sha256=m0,
             strengths=[0,0.12,0.24],maximum_effect_weight=float(w.max()),protected_detail_box=pbox,
             protected_detail_max_channel_difference=int(diff[y0:y1,x0:x1].max()),
             original_files_unchanged=True,background_unchanged=True,interior_beyond_band_unchanged=True)
 summary.append(result)
 # Native 1:1 crop: no resampling, 512 source pixels per image panel.
 sheet=Image.new('RGB',(1568,610),'#181a1d');dr=ImageDraw.Draw(sheet)
 dr.text((16,10),c['name'].replace('-',' ')+' | native-pixel crop, same location and scale',font=font(22),fill='white')
 for i,(lab,im) in enumerate(zip(['Baseline','Subtle: 12% maximum','Moderate: 24% maximum'],comps)):
  x=12+i*520;dr.text((x,48),lab,font=font(18),fill='#d5d8df');sheet.paste(im.crop(c['crop']),(x,82))
 sheet.save(ROOT/f"{c['name']}-native-crop.png")
 sheets.append((c,comps))
 print(c['name'],result,flush=True)
# Whole-frame small-screen comparison. 1/8 source scale, all 3 treatments identical framing.
board=Image.new('RGB',(1200,1190),'#181a1d');dr=ImageDraw.Draw(board)
dr.text((16,14),'Edge shading study | unchanged base mask + separate black layer',font=font(25),fill='white')
dr.text((16,49),'Original 3072 x 4080 pixel renders. Same framing. No generated or replaced detail.',font=font(17),fill='#c5c8cf')
for r,(c,comps) in enumerate(sheets):
 y=88+r*545
 dr.text((16,y),c['name'].replace('-',' ')+f"  |  inward fade: {c['width']} source pixels",font=font(20),fill='white')
 for i,(lab,im) in enumerate(zip(['Baseline','Subtle: up to 12%','Moderate: up to 24%'],comps)):
  x=12+i*396;dr.text((x,y+32),lab,font=font(18),fill='#d5d8df')
  board.paste(im.resize((384,510),Image.Resampling.LANCZOS),(x,y+60))
# fix board height to keep last row unclipped
# regenerate with enough height, preserving all panel rows
board2=Image.new('RGB',(1200,1260),'#181a1d'); board2.paste(board,(0,0)); dr=ImageDraw.Draw(board2)
# Last row bottom was clipped in prior board; paste complete panels again.
c,comps=sheets[1];y=633
for i,im in enumerate(comps):board2.paste(im.resize((384,510),Image.Resampling.LANCZOS),(12+i*396,y+60))
dr.text((16,1222),'Subtle is the candidate; moderate is a stress test for a visible dark rim.',font=font(19),fill='#c5c8cf')
board2.save(ROOT/'Edge-shadow-comparison.jpg',quality=96,subsampling=0)
(ROOT/'evaluation_checks.json').write_text(json.dumps(summary,indent=2))
