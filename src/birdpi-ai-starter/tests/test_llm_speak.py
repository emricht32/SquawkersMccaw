import unittest
from llm_speak import phrases, ThinkFilter

class PhraseTests(unittest.TestCase):
    def test_sentence(self):
        self.assertEqual(phrases('Ahoy! Welcome ab'), (['Ahoy!'], 'Welcome ab'))
    def test_completion(self):
        self.assertEqual(phrases('Welcome aboard', final=True), (['Welcome aboard'], ''))
    def test_think_filter_split_tag(self):
        f = ThinkFilter()
        self.assertEqual(f.feed('<thi'), '')
        self.assertEqual(f.feed('nk>secret</think>Ahoy!'), 'Ahoy!')
    def test_consecutive_sentences(self):
        self.assertEqual(phrases('Hi. Bye.'), (['Hi.', 'Bye.'], ''))

if __name__ == '__main__': unittest.main()
