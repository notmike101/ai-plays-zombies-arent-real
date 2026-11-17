import unittest
from unittest.mock import patch
import build_hook


class HookBuildTests(unittest.TestCase):
    def test_live_game_refuses_build_before_running_cargo(self):
        with patch('local_agent.inventory', return_value=[{'role':'game','pid':123}]), \
             patch('subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'running game'):
                build_hook.build()
            run.assert_not_called()

    def test_flags_remove_path_and_link_timestamp_variation(self):
        flags = build_hook.rust_flags('C:/temporary build')
        self.assertIn('--remap-path-prefix=C:/temporary build=/zar-build', flags)
        self.assertIn('link-arg=/Brepro', flags)
        self.assertIn('link-arg=/PDBALTPATH:hookdll.pdb', flags)


if __name__ == '__main__': unittest.main()
