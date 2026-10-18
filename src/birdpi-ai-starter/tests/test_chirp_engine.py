import json,sqlite3,unittest
from chirp_engine import connect,validate,import_file,select,record
from pathlib import Path

SAMPLE=Path(__file__).resolve().parents[1]/'examples/sample_chirps.json'
class ChirpTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:');import_file(self.db,SAMPLE)
    def test_import(self):self.assertEqual(self.db.execute('select count(*) from chirps').fetchone()[0],3)
    def test_hat(self):
        ch=select(self.db,'jose',['hat'],[], 's1',seed=7)
        self.assertIsNotNone(ch)
    def test_polly_requires_adult(self):self.assertIsNone(select(self.db,'polly',['direct_insult'],[], 's1'))
    def test_polly_valid(self):self.assertIsNotNone(select(self.db,'polly',['adult_mode','direct_insult'],[], 's1'))
    def test_no_repeats(self):
        ch=select(self.db,'polly',['adult_mode','direct_insult'],['guest7'],'s1')
        record(self.db,ch,'s1',['guest7'])
        self.assertIsNone(select(self.db,'polly',['adult_mode','direct_insult'],['guest7'],'s2'))
    def test_polly_dialogue_rejected(self):
        ch=json.loads(self.db.execute("select body from chirps where speaker='polly'").fetchone()[0]);ch['dialogue']=[{'speaker':'polly','text':ch['text']}]
        with self.assertRaises(ValueError):validate(ch)
    def test_no_main_mentions_polly(self):
        ch=json.loads(self.db.execute("select body from chirps where speaker='jose' limit 1").fetchone()[0]);ch['text']='Hello Polly'
        with self.assertRaises(ValueError):validate(ch)
    def test_main_bird_no_polly_dialogue(self):
        ch=json.loads(self.db.execute("select body from chirps where speaker='jose' limit 1").fetchone()[0]);ch['type']='banter';ch['dialogue']=[{'speaker':'jose','text':ch['text']},{'speaker':'polly','text':'Hi'}]
        with self.assertRaises(ValueError):validate(ch)
if __name__=='__main__':unittest.main()
