"""Discovery must never execute historical live-game diagnostics."""
import importlib
import unittest
from unittest.mock import patch


class ProbeImportTests(unittest.TestCase):
    def test_live_probes_are_inert_when_imported(self):
        with patch('psutil.process_iter', side_effect=AssertionError('live process scan')), \
             patch('subprocess.run', side_effect=AssertionError('process launch')):
            for name in ('test_menu_chain', 'test_rawinput', 'test_welcome', 'test_welcome2'):
                importlib.reload(importlib.import_module(name))


if __name__ == '__main__':
    unittest.main()
