from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageEnhance
from scipy.ndimage import gaussian_filter,distance_transform_edt,binary_dilation
import numpy as np,json,hashlib
r=Path('guided_mask_test');o=r/'spider_repair_v3';out=o/'final';out.mkdir(exist_ok=True)
rgb=np.array(Image.open(r/'spider_pass2/aligned_source.png'));a0=np.array(Image.open(r/'spider_pass2/mask16.png')).astype(float)/65535
local=np.array(Image.open(o/'local_matte/mask16.png')).astype(float)/65535
new=a0.copy();new[420:1444,480:1504]=local
sam=np.array(Image.open(r/'spider_guides/sam_selected.png'))>0
support=np.clip((35-distance_transform_edt(~sam))/15,0,1)
support[support < 0.5/255] = 0
a=a0+(new-a0)*support
# Original verified solid anatomy is locked, no transparency introduced there.
a[a0==1]=1
tri=np.array(Image.open(o/'trimap_corrected.png'));a[tri==0]=0
# Estimate the local photographed background using known empty pixels.
known=~binary_dilation(a>.012,iterations=4)
ix=distance_transform_edt(~known,return_distances=False,return_indices=True)
rgbf=rgb.astype(float)/255;bg=gaussian_filter(rgbf[tuple(ix)],(18,18,0))
# Limited inverse mixture. This is an approximate local color cleanup, not a color grade.
# It leaves opaque source RGB intact and does not alter the standalone web.
amount=.35*(1-a)*support
amount[a==0]=0
color=np.clip((rgbf-amount[...,None]*bg)/(1-amount[...,None]),0,1)
color=np.uint8(np.rint(color*255));a16=np.uint16(np.rint(a*65535))
black=np.uint8(np.rint(color*(a16.astype(float)/65535)[...,None]));rgba=np.dstack((color,np.uint8(np.rint(a16/257))))
for name,arr in [('SOURCE_ALIGNED.png',rgb),('FOREGROUND_COLOR_REPAIRED.png',color),('MASK_16BIT.png',a16),('BLACK_COMPOSITE.png',black),('TRANSPARENT.png',rgba),('TRIMAP.png',tri),('LOCAL_REPAIR_SUPPORT.png',np.uint8(np.rint(support*255)))]:Image.fromarray(arr).save(out/name)
old=np.array(Image.open(r/'spider_pass2/black.png'))
coords={'upper_left_loop':(754,934,778,950),'left_gap':(707,1097,733,1125),'lower_left_triangle':(725,1187,748,1212),'upper_triangle':(961,948,980,975)}
metrics={}
for k,(x1,y1,x2,y2) in coords.items():
 mask=np.zeros_like(a,dtype=bool);mask[y1:y2,x1:x2]=1
 metrics[k]={'before_alpha_median':float(np.median(a0[mask])),'after_alpha_median':float(np.median(a[mask])),'before_rgb_median':np.median(old[mask],axis=0).tolist(),'after_rgb_median':np.median(black[mask],axis=0).tolist()}
checks={'dimensions':[1536,2040],'untouched_source_rgb_exact':np.array_equal(rgb,np.array(Image.open(out/'SOURCE_ALIGNED.png'))),'opaque_rgb_exact':np.array_equal(color[a0==1],rgb[a0==1]),'opaque_alpha_exact':bool(np.all(a16[a0==1]==65535)),'web_outside_local_support_alpha_exact':np.array_equal(a16[support==0],np.uint16(np.rint(a0[support==0]*65535))),'web_outside_local_support_rgb_exact':np.array_equal(color[support==0],rgb[support==0]),'composite_from_saved_files_exact':np.array_equal(black,np.uint8(np.rint(color*(a16.astype(float)/65535)[...,None]))),'changed_alpha_pixels':int(np.count_nonzero(a16!=np.uint16(np.rint(a0*65535)))),'changed_color_pixels':int(np.count_nonzero(np.any(color!=rgb,axis=2))),'gap_samples':metrics}
(o/'repair_validation.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';f=ImageFont.truetype(font,23);sm=ImageFont.truetype(font,17)
can=Image.new('RGB',(1640,1800),(24,26,29));d=ImageDraw.Draw(can)
d.text((20,15),'Spider repair: before / after',font=f,fill='white');d.text((20,49),'Same photograph, same scale. Empty gaps corrected; local edge color spill reduced.',font=sm,fill=(210,210,210))
for x,arr,label in [(20,old,'Before'),(840,black,'Repaired')]:
 d.text((x,80),label,font=f,fill='white');im=Image.fromarray(arr).crop((500,570,1310,1380));can.paste(im,(x,120))
 d.text((x,952),'Close view: left-leg gaps',font=sm,fill='white');crop=Image.fromarray(arr).crop((620,900,825,1285));crop=crop.resize((410,770));can.paste(crop,(x,990))
 d.text((x+430,952),'Close view: right legs',font=sm,fill='white');crop=Image.fromarray(arr).crop((950,850,1240,1270));crop.thumbnail((350,640));can.paste(crop,(x+430,990))
can.save(o/'Spider-repair-before-after.jpg',quality=96)
# Compact preview to share before packaging.
preview=can.crop((0,0,1640,940));preview.thumbnail((1200,688));preview.save(o/'Spider-repair-preview.jpg',quality=94)
# Inspection views with boosted shadows and white background.
can=Image.new('RGB',(1640,960),(24,26,29));d=ImageDraw.Draw(can)
for x,arr,label in [(20,old,'Before, +2.3x exposure'),(840,black,'After, +2.3x exposure')]:
 im=ImageEnhance.Brightness(Image.fromarray(arr).crop((500,570,1310,1380))).enhance(2.3);can.paste(im,(x,70));d.text((x,20),label,font=f,fill='white')
can.save(o/'boosted_check.jpg',quality=96)
white=np.uint8(np.rint(color*a[...,None]+255*(1-a[...,None])));Image.fromarray(white).crop((500,570,1310,1380)).save(o/'white_check.png')
