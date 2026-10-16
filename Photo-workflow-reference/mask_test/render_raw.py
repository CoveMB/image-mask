"""Develop each DNG read-only with one consistent, explicit LibRaw recipe."""
import json, hashlib, time
from pathlib import Path
import numpy as np
import rawpy
from PIL import Image, ImageCms
import tifffile
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'deliverables'
for p in ['masters_png','masters_tiff16','masks','black_composites','previews']:(OUT/p).mkdir(parents=True,exist_ok=True)
raw_meta=json.loads((ROOT.parent/'original_photo_assessment'/'raw_metadata.json').read_text())
checks={x['file']:x['sha256'] for x in json.loads((ROOT/'original_checksums.json').read_text())}
icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
photos=[]
subjects=['Grasshopper','Red bug on leaf','Red and black bug on stem','Hairy caterpillar','Pink dahlia with bee','Green insect on bark','Red and yellow flower','Orange zinnia','Bee close-up on yellow flower','Yellow flower']
for i,meta in enumerate(raw_meta):
 p=ROOT.parent/'original_photo_assessment'/meta['file']; stem=f'{i+1:02d}_{p.stem.replace("(1)","")}'
 start=time.monotonic()
 with rawpy.imread(str(p)) as raw:
  sizes=raw.sizes._asdict();wb=list(raw.camera_whitebalance);daylight=list(raw.daylight_whitebalance);effective=[daylight[0]/daylight[1],1.0,daylight[2]/daylight[1],1.0];assert min(effective)>0
  rgb16=raw.postprocess(demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,use_camera_wb=False,use_auto_wb=False,output_color=rawpy.ColorSpace.sRGB,output_bps=16,no_auto_bright=False,auto_bright_thr=0.01,bright=1.0,gamma=(2.4,12.92),user_flip=None,half_size=False,median_filter_passes=0)
 rgb8=np.rint(rgb16.astype(np.float32)/257).astype(np.uint8)
 png=f'masters_png/{stem}_developed.png';tif=f'masters_tiff16/{stem}_developed.tif'
 Image.fromarray(rgb8).save(OUT/png,icc_profile=icc)
 tifffile.imwrite(OUT/tif,rgb16,photometric='rgb',compression='deflate',metadata=None,extratags=[(34675,'B',len(icc),icc,False)])
 thumb=Image.fromarray(rgb8);thumb.thumbnail((750,1000));thumb.save(OUT/'previews'/f'{stem}_source.jpg',quality=94,icc_profile=icc)
 item={'index':i+1,'subject':subjects[i],'source_file':p.name,'source_sha256':checks[p.name],'stem':stem,'raw_sizes':{k:list(v) if isinstance(v,tuple) else v for k,v in sizes.items()},'camera_whitebalance_reported':wb,'effective_whitebalance':effective,'white_balance_source':'LibRaw daylight coefficients; AsShotWhiteXY present but camera coefficients unavailable in this decoder','source_exif_orientation':meta['orientation'],'orientation_applied':'LibRaw automatic EXIF orientation (90 degrees clockwise for source orientation 6)','crop':'No additional crop; LibRaw visible image, default postprocess sizing. DNG DefaultCropSize not applied separately.','final_dimensions_wh':[rgb8.shape[1],rgb8.shape[0]],'master_png':png,'master_tiff16':tif,'raw_render_seconds':round(time.monotonic()-start,2)}
 photos.append(item)
 print(json.dumps({'rendered':i+1,'file':p.name,'dimensions':item['final_dimensions_wh'],'seconds':item['raw_render_seconds']}),flush=True)
manifest={'model':'ZhengPeng7/BiRefNet_dynamic-matting','model_revision':'074df545be87034e74a96bf71566ecbbc4c15f0a','model_weights_sha256':(ROOT/'model_review'/'weights.sha256').read_text().split()[0],'raw_recipe':{'rawpy':rawpy.__version__,'libraw':list(rawpy.libraw_version),'demosaic':'AHD','white_balance':'Explicit LibRaw daylight baseline; camera white balance disabled','output_space':'sRGB','gamma':[2.4,12.92],'output_bits':16,'auto_bright':True,'auto_bright_threshold':0.01,'brightness_multiplier':1,'noise_reduction_or_sharpening':'none added','note':'One consistent development recipe, not a reproduction of the Pixel embedded JPEG or the user\'s prior editing. PNG reference is rounded to 8-bit from the 16-bit TIFF.'},'photos':photos}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
