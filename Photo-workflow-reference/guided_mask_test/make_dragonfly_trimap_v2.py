from pathlib import Path
from PIL import Image,ImageDraw
from scipy import ndimage as ndi
import numpy as np,json
r=Path('/path/to/photo-workflow-reference/guided_mask_test');out=r/'dragonfly_guides'
def load(n):return np.asarray(Image.open(r/f'dragonfly_sam/{n}.png'))>0
def filled(m):return ndi.binary_fill_holes(ndi.binary_closing(m,iterations=8))
body=filled(load('body_candidate1'));core=ndi.binary_erosion(body,iterations=25,border_value=1)
whole=filled(load('whole_dragonfly_candidate1'));up=filled(load('upper_right_wing_candidate1'));low=filled(load('lower_right_wing_candidate1'))
allowed=ndi.binary_dilation(whole|up|low|body,iterations=30)
# Source-visible lower-left defocused wings need broader uncertain support than SAM.
manual=Image.new('L',(2047,2048));d=ImageDraw.Draw(manual)
polys=[[(316,450),(180,560),(0,690),(0,982),(138,925),(219,838),(290,724),(343,622)],[(329,554),(270,723),(160,1024),(294,1024),(342,892),(428,693)]]
for poly in polys:d.polygon([(round(x*2047/1024),round(y*2)) for x,y in poly],fill=255)
allowed|=np.asarray(manual)>0
tri=np.zeros_like(whole,dtype=np.uint8);tri[allowed]=128;tri[core]=255
Image.fromarray(tri).save(out/'trimap_v2.png')
source=Image.open(next((r/'inputs/dragonfly_source').iterdir())).convert('RGB');arr=np.array(source).astype(float);overlay=arr.copy();overlay[tri==0]=overlay[tri==0]*.45+[90,0,0];overlay[tri==255]=overlay[tri==255]*.65+[0,70,0];overlay[tri==128]=overlay[tri==128]*.8+[0,0,45];Image.fromarray(np.clip(overlay,0,255).astype(np.uint8)).save(out/'trimap_v2_overlay.png')
(out/'guide_notes_v2.json').write_text(json.dumps({'source_dimensions':[2047,2048],'sam_source':'whole_dragonfly candidate1 + separate upper/lower wings candidate1 + body candidate1','method':'More selective SAM wing silhouettes exclude inter-wing background; filled tiny gaps then 30px uncertainty; smaller conservative body opaque core; source-observed lower-left defocused wing extension unknown','known_background_fraction':float(np.mean(tri==0)),'known_foreground_fraction':float(np.mean(tri==255)),'uncertain_fraction':float(np.mean(tri==128))},indent=2))
