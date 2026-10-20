import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recognition import load_gallery, validate_person_id, enroll_folder

class FakeCV2:
    def imread(self, path): return object()
class FakeEngine:
    cv2 = FakeCV2()
    def faces(self, image): return [[1]*15]
    def embedding(self,image,face):
        class E:
            def tolist(self): return [0.1,0.2]
        return E()

class GalleryTests(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(validate_person_id('buddy-1'), 'buddy-1')
        for bad in ('../abc','hello there','.secret','a'*49):
            with self.assertRaises(ValueError): validate_person_id(bad)
    def test_empty_gallery(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_gallery(Path(d)/'absent.json'), {})
    def test_enrollment_consent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'friends'/'alex').mkdir(parents=True)
            p=root/'friends'/'alex'
            (p/'profile.json').write_text(json.dumps({'display_name':'Alex','consent_to_recognition':False}))
            (p/'a.jpg').write_bytes(b'fake')
            out=root/'gallery.json'
            self.assertEqual(enroll_folder(FakeEngine(),root/'friends',out)['enrolled'], {})
            (p/'profile.json').write_text(json.dumps({'display_name':'Alex','consent_to_recognition':True}))
            self.assertEqual(enroll_folder(FakeEngine(),root/'friends',out)['enrolled'], {'alex':1})
            self.assertEqual(len(load_gallery(out)['alex']['embeddings']),1)

if __name__=='__main__': unittest.main()
