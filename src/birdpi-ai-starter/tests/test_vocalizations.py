import json, tempfile, unittest
from pathlib import Path
from chirp_engine import pick_vocalizations
class VocalizationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'vocals.json'
        self.path.write_text(json.dumps({'pre':[{'id':'a','text':'BRAAWK!','weight':1}], 'post':[{'id':'b','text':'AWK!','weight':1}]}))
    def tearDown(self):self.tmp.cleanup()
    def test_both(self):
        clips=pick_vocalizations(self.path,'jose','both',1)
        self.assertEqual([x['role'] for x in clips],['pre','post'])
        self.assertEqual([x['text'] for x in clips],['BRAAWK!','AWK!'])
    def test_single(self):self.assertEqual(len(pick_vocalizations(self.path,'polly','pre',1)),1)
    def test_bad_bird(self):
        with self.assertRaises(ValueError): pick_vocalizations(self.path,'unknown')
if __name__=='__main__':unittest.main()
