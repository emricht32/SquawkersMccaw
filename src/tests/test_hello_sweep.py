import sys
import unittest
from unittest.mock import patch

sys.path.append('../')
from hello_sweep import print_hello_sweep


class TestHelloSweep(unittest.TestCase):
    @patch('builtins.print')
    def test_print_hello_sweep(self, mock_print):
        print_hello_sweep()
        mock_print.assert_called_once_with("Hello Sweep")

if __name__ == '__main__':
    unittest.main()
