import unittest, json, hashlib
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
class OutputContract(unittest.TestCase):
    def test_expected_batch_exists(self):
        path=ROOT/'deliverables'/'manifest.json'
        self.assertTrue(path.is_file(), 'Batch manifest has not been produced')
        data=json.loads(path.read_text())
        self.assertEqual(len(data['photos']),10)
        for photo in data['photos']:
            with self.subTest(photo=photo['source_file']):
                master=np.array(Image.open(ROOT/'deliverables'/photo['master_png']))
                mask_img=Image.open(ROOT/'deliverables'/photo['mask_png'])
                alpha=np.array(mask_img).astype(np.float64)/65535
                black=np.array(Image.open(ROOT/'deliverables'/photo['black_png']))
                self.assertEqual(master.shape[:2], alpha.shape)
                self.assertEqual(master.shape, black.shape)
                self.assertEqual(list(mask_img.size), photo['final_dimensions_wh'])
                self.assertGreater(np.unique(alpha).size,256,'Mask should retain soft alpha beyond 8-bit')
                self.assertLessEqual(float(np.max(np.abs(black.astype(float)-np.rint(master.astype(float)*alpha[...,None])))),0)
                self.assertTrue(np.all(black[alpha==0]==0))
                self.assertTrue(np.array_equal(black[alpha==1], master[alpha==1]))
    def test_white_balance_is_valid_and_explicit(self):
        data=json.loads((ROOT/'deliverables'/'manifest.json').read_text())
        self.assertEqual(data['raw_recipe']['white_balance'], 'Explicit LibRaw daylight baseline; camera white balance disabled')
        for photo in data['photos']:
            self.assertTrue(all(x>0 for x in photo['effective_whitebalance'][:3]))

    def test_originals_unchanged(self):
        before=json.loads((ROOT/'original_checksums.json').read_text())
        self.assertEqual(len(before),10)
        for x in before:
            p=ROOT.parent/'original_photo_assessment'/x['file']
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),x['sha256'])
if __name__=='__main__': unittest.main()
