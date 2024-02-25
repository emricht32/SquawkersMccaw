import sys
import unittest
from unittest.mock import patch

sys.path.append('../')
from hello_sweep import hello_sweep


class TestHelloSweep(unittest.TestCase):
    def test_hello_sweep_output(self):
        with patch('sys.stdout', new_callable=unittest.mock.mock_open()) as mocked_stdout:
            hello_sweep()
            mocked_stdout.assert_called_with("Hello Sweep\n")

if __name__ == "__main__":
    unittest.main()
