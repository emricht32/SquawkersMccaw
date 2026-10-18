import unittest
from llm_speak import clean_for_speech, JOKES, is_joke_request

class JokeTests(unittest.TestCase):
    def test_joke_detection(self):
        self.assertTrue(is_joke_request("Tell me a pirate joke"))
        self.assertFalse(is_joke_request("What color is the sky?"))
    def test_no_tts_markup(self):
        self.assertEqual(clean_for_speech('**Setup:** A pirate. **Punchline:** Arrr!'), 'A pirate. Arrr!')
    def test_library_content(self):
        self.assertGreaterEqual(len(JOKES), 6)
        self.assertTrue(all('?' in joke for joke in JOKES))

if __name__ == '__main__': unittest.main()
