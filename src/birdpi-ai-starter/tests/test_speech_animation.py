import unittest
from speech_animation import phonemes_to_ranges, pcm_to_ranges, merge_ranges

class MovementTests(unittest.TestCase):
    def test_merges_nearby(self):
        self.assertEqual(merge_ranges([(0, 0.1), (0.15, 0.23)]), [[0, 0.23]])
    def test_vowels(self):
        data = [{'phoneme':'h','num_samples':100}, {'phoneme':'ɛ','num_samples':100},
                {'phoneme':'l','num_samples':100}, {'phoneme':'o','num_samples':100}]
        self.assertEqual(phonemes_to_ranges(data, 1000), [[0.1,0.2],[0.3,0.4]])
    def test_silence(self):
        self.assertEqual(pcm_to_ranges(bytes(2000), 1000), [])
    def test_long_pulse_is_split(self):
        r = merge_ranges([(0, 1)])
        self.assertTrue(all((b-a) <= 0.251 for a,b in r))

if __name__ == '__main__':
    unittest.main()
