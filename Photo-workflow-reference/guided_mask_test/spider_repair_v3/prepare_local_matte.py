from PIL import Image,ImageDraw
from pathlib import Path
import numpy as np,json
r=Path('guided_mask_test');o=r/'spider_repair_v3';W,H=1536,2040
tri=np.array(Image.open(r/'spider_pass2/trimap.png'));mask=Image.new('L',(W,H));d=ImageDraw.Draw(mask)
# Verified small background cores. Model determines transitions; no foreground geometry painted.
polys=[[(753,924),(772,916),(786,918),(779,945),(763,952),(743,949)],[(707,1098),(731,1084),(741,1104),(733,1129),(710,1132),(695,1120)],[(720,1192),(734,1179),(749,1182),(762,1215),(769,1235),(745,1223),(729,1210)],[(956,931),(974,950),(982,970),(977,981),(963,973),(952,955)],[(1129,1051),(1140,1052),(1146,1074),(1139,1084),(1128,1070)]]
for pts in polys:d.polygon(pts,fill=255)
known=np.array(mask)>0;tri[known]=0
Image.fromarray(tri).save(o/'trimap_corrected.png');mask.save(o/'gap_cores.png')
box=(480,420,1504,1444);Image.open(r/'spider_pass2/aligned_source.png').crop(box).save(o/'local_source.png');Image.fromarray(tri).crop(box).save(o/'local_trimap.png')
(o/'gap_polygons.json').write_text(json.dumps({'crop':box,'background_polygons':polys},indent=2))
im=np.array(Image.open(r/'spider_pass2/aligned_source.png'));im[known]=(255,0,255);Image.fromarray(im).crop((520,810,1230,1360)).save(o/'gap_overlay.png')
