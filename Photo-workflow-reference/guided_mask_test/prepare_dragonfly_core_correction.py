from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from PIL import Image,ImageDraw
r=Path('/path/to/photo-workflow-reference/guided_mask_test');out=r/'dragonfly_local_correction';out.mkdir(exist_ok=True)
source=Image.open(r/'dragonfly_pass2/aligned_source.png');tri=np.array(Image.open(r/'dragonfly_pass2/trimap.png'))
known=Image.new('L',source.size);d=ImageDraw.Draw(known)
d.polygon([(646,405),(626,455),(619,533),(626,590),(648,620),(671,587),(681,516),(680,441)],fill=255)
d.polygon([(744,765),(796,768),(832,815),(834,875),(794,913),(753,870)],fill=255)
core=np.array(known)>0;protect=ndi.binary_dilation(core,iterations=35)
tri[protect]=128;tri[core]=255
known.save(out/'localized_opaque_guides.png');Image.fromarray(tri).save(out/'corrected_full_trimap.png')
box=(200,0,1224,1024);source.crop(box).save(out/'source_crop.png');Image.fromarray(tri).crop(box).save(out/'trimap_crop.png')
# Full-strength only within source-backed correction zones; outside feather unchanged.
weight=np.clip(ndi.distance_transform_edt(protect)/20,0,1).astype(np.float32);np.save(out/'correction_weight.npy',weight)
