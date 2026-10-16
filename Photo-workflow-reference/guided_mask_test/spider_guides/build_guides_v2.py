from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np, json
from scipy.ndimage import distance_transform_edt, binary_dilation, gaussian_filter
P=Path('/path/to/photo-workflow-reference/guided_mask_test'); O=P/'spider_guides'; O.mkdir(exist_ok=True)
im=Image.open(P/'spider_raw_preparation/spider_native_source.png').convert('RGB'); W,H=im.size
m=np.array(Image.open(P/'spider_sam/spider_and_prey_candidate1.png'))>0
din=distance_transform_edt(m); dout=distance_transform_edt(~m)
trim=np.zeros((H,W),np.uint8); trim[dout<=25]=128; trim[din>=12]=255
# Rear leg overlaps contain genuine background gaps; never force SAM's filled gaps solid.
uncertain_polygons=[[(608,1080),(706,1026),(749,1085),(808,1120),(817,1217),(708,1243),(627,1199)],[(975,1044),(1050,1024),(1117,1094),(1154,1185),(1048,1168),(994,1110)]]
for pts in uncertain_polygons:
 q=Image.new('L',(W,H));ImageDraw.Draw(q).polygon(pts,fill=255);a=np.array(q)>0;trim[a & (dout<=25)]=128
# Narrow verified leg interiors retained only where SAM is >=5 px inside.
legpaths=[([(1144,640),(1199,696),(1246,782),(1240,825),(1216,889),(1199,937),(1177,992),(1120,1020)],10), ([(997,820),(1045,833),(1108,875),(1104,918),(1100,969),(1095,1035),(1063,1090)],8), ([(554,1025),(554,1080),(569,1129),(624,1174),(702,1218),(780,1260)],8)]
q=Image.new('L',(W,H));dd=ImageDraw.Draw(q)
for pts,width in legpaths:dd.line(pts,fill=255,width=width)
a=np.array(q)>0;trim[a&(din>=5)]=255
# Filament paths are uncertain search corridors, not foreground line drawing.
paths=[
('far_left',[(39,0),(32,200),(25,400),(17,600),(6,900)],16),
('upper_left_anchor',[(254,0),(249,100),(253,200),(257,300),(264,455),(280,600),(291,700),(303,800),(316,913)],18),
('bright_left_vertical',[(297,0),(303,100),(308,200),(312,300),(316,400),(321,500),(325,600),(327,700),(328,800),(329,916)],18),
('left_slant_1',[(291,0),(338,200),(385,400),(433,600),(481,800),(509,922)],18),
('left_slant_2',[(353,0),(401,200),(447,400),(492,600),(538,800),(569,937)],18),
('left_slant_3',[(398,0),(460,200),(522,400),(585,600),(648,800),(697,961)],20),
('left_branch',[(264,455),(225,600),(196,700),(167,800),(138,900),(72,1015)],20),
('left_crossbar',[(316,913),(329,916),(405,912),(509,922),(569,937),(697,961),(777,965)],20),
('left_diagonal',[(311,1180),(396,1120),(470,1075),(553,1026),(697,961)],20),
('left_vertical_lower',[(316,925),(311,1180),(321,1470),(338,1820),(348,2039)],20),
('left_triangle_edge',[(329,923),(396,1120),(430,1470),(445,2039)],20),
('left_triangle_inner',[(470,1075),(430,1470),(443,2039)],20),
('left_leg_anchor_lower',[(553,1026),(526,1280),(493,1570),(456,2039)],20),
('left_outer_lower',[(72,1015),(99,1210),(67,1410),(99,2039)],24),
('left_edge_fragment',[(0,931),(72,1015),(127,915)],24),
('prey_support',[(1045,790),(1100,707),(1145,644),(1187,582),(1231,518),(1285,436),(1324,391),(1350,359)],30),
('upper_right_faint_1',[(780,0),(819,100),(867,200),(909,300),(943,400),(982,500),(1022,600),(1060,726)],24),
('upper_right_faint_2',[(855,0),(894,100),(936,200),(977,300),(1015,400),(1059,500),(1097,600),(1119,659)],22),
('upper_right_faint_3',[(930,0),(969,100),(1005,200),(1043,300),(1080,400),(1115,500),(1149,588)],22),
('upper_right_faint_4',[(985,0),(1023,100),(1062,200),(1101,300),(1140,400),(1179,500)],22),
('upper_right_faint_5',[(1060,0),(1099,100),(1140,200),(1181,300),(1223,400),(1230,418)],22),
('upper_right_faint_6',[(1130,0),(1172,100),(1213,200),(1256,300),(1280,363)],22),
('upper_right_faint_7',[(1217,0),(1260,100),(1303,200),(1341,293)],22),
('upper_right_faint_8',[(1313,0),(1350,91),(1385,177)],24),
('upper_right_faint_9',[(1393,0),(1438,100),(1487,198)],24),
('upper_right_crossbar',[(1310,406),(1410,453),(1535,509)],24),
('right_oblique',[(1325,520),(1408,600),(1501,700),(1535,733)],24),
('right_attachment',[(1250,792),(1330,890),(1373,949)],24),
('right_intersect',[(1459,862),(1535,784)],24),
('bottom_diagonal',[(1038,1549),(920,1726),(865,1801),(705,2039)],26),
('bottom_branch',[(865,1801),(973,1950),(1037,2039)],26),
('right_lower_diagonal',[(1535,1504),(1483,1590),(1429,1692),(1303,1920)],28),
('right_triangle',[(1235,1283),(1360,1468),(1483,1590)],24),
('right_horizontal',[(1125,1471),(1314,1469),(1535,1483)],24),
('right_crossbar',[(1235,1336),(1370,1373),(1535,1404)],26),
('right_middle_spoke',[(1285,1186),(1535,1288)],24),
('right_upper_spoke',[(1365,1044),(1535,1155)],24),
]
q=Image.new('L',(W,H));d=ImageDraw.Draw(q)
for name,pts,width in paths:d.line(pts,fill=255,width=width,joint='curve')
web=np.array(q)>0;trim[web&(trim!=255)]=128
Image.fromarray(trim).save(O/'trimap_v2.png'); Image.fromarray(np.uint8(web)*255).save(O/'web_corridors_v2.png');Image.fromarray(np.uint8(m)*255).save(O/'sam_selected.png')
(O/'filament_paths_v2.json').write_text(json.dumps(paths,indent=2));(O/'guide_metadata_v2.json').write_text(json.dumps({'source':str(P/'spider_raw_preparation/spider_native_source.png'),'dimensions':[W,H],'sam_candidate':1,'opaque_erosion_px':12,'uncertain_dilation_px':25,'value_counts':{str(v):int((trim==v).sum()) for v in [0,128,255]},'notes':['Web corridor line drawing marks only unknown trimap regions. No visible foreground strands are synthesized.','Large overlapping rear-leg areas changed from SAM foreground to unknown because mask includes background gaps.','Foreground stems require both a hand-guided center corridor and >=5 px SAM interior.']},indent=2))
a=np.array(im).copy();a[trim==0]=(a[trim==0]*.35).astype('uint8');a[trim==255]=(a[trim==255]*.55+np.array([0,230,70])*.45).astype('uint8'); a[(trim==128)&web]=(a[(trim==128)&web]*.65+np.array([220,100,0])*.35).astype('uint8');Image.fromarray(a).save(O/'trimap_evidence_v2.jpg',quality=95)
print('Written trimap',im.size,np.unique(trim,return_counts=True))
