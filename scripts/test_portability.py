"""Portable roots and copy boundaries; fixtures never touch an installed game."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import prepare_game as prepare
import project


class PortabilityTests(unittest.TestCase):
    def test_relocated_active_modules_use_their_own_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'checkout with spaces'
            shutil.copytree(project.ROOT/'scripts', root/'scripts',
                            ignore=shutil.ignore_patterns('target', '__pycache__'))
            shutil.copytree(project.ROOT/'visualizer', root/'visualizer',
                            ignore=shutil.ignore_patterns('runtime', '__pycache__'))
            code = "import pathlib,nn_play2,env_zar,harness; r=pathlib.Path.cwd(); assert pathlib.Path(nn_play2.ROOT)==r; assert pathlib.Path(harness.ROOT)==r; assert pathlib.Path(env_zar.ZAREnv.__init__.__defaults__[0])==r; assert pathlib.Path(nn_play2.MODEL).is_relative_to(r)"
            result = subprocess.run([sys.executable, '-B', '-c',
                                     "import sys;sys.path.insert(0,'scripts');"+code],
                                    cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_config_paths_resolve_against_config_not_shell(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'zar.local.toml'
            path.write_text('[game]\ninstall_dir="../installed"\n')
            self.assertEqual(project.config_path(project.load_config(path), 'game', 'install_dir', path.parent),
                             (path.parent/'../installed').resolve())

    def test_copy_is_new_clean_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root, source = Path(d)/'repo', Path(d)/'installed'
            root.mkdir(); source.mkdir()
            (source/'zombies-arent-real.exe').write_bytes(b'fixture game')
            (source/'unlocks.ini').write_text('[start]\nunit Garrison\n[order]\nability Police\nupgrade Garrison_Rate\n')
            (source/'assets').mkdir(); (source/'assets/map').write_text('map')
            (source/'steam_cloud').mkdir(); (source/'steam_cloud/private').write_text('private')
            digest = hashlib.sha256(b'fixture game').hexdigest()
            with patch.object(prepare, 'ROOT', root), patch.object(prepare, 'expected_hash', return_value=digest):
                target = prepare.prepare_copy(source, 'inst1')
                self.assertEqual((target/'assets/map').read_text(), 'map')
                self.assertFalse((target/'steam_cloud/private').exists())
                self.assertIn('difficulty = normal', (target/'steam_cloud/settings.ini').read_text())
                self.assertIn('usage_sharing = false', (target/'steam_cloud/settings.ini').read_text())
                self.assertIn('usage_asked = true', (target/'steam_cloud/settings.ini').read_text())
                self.assertEqual((target/'steam_appid.txt').read_text().strip(), '5185890')
                self.assertFalse((source/'steam_appid.txt').exists())
                second = prepare.prepare_copy(target, 'inst2')
                self.assertEqual((second/'assets/map').read_text(), 'map')
                self.assertFalse((second/'steam_cloud/private').exists())
                earned = source/'steam_cloud/unlocks.ini'
                earned.write_text('breach_restarts = 2\nunlock = unit Garrison\n')
                third = prepare.prepare_copy(source, 'inst3')
                self.assertNotEqual((third/'steam_cloud/unlocks.ini').read_bytes(), earned.read_bytes())
                self.assertIn('unlock = upgrade Garrison_Rate', (third/'steam_cloud/unlocks.ini').read_text())
                unlocked = (target/'steam_cloud/unlocks.ini').read_text()
                self.assertIn('unlock = unit Garrison', unlocked)
                self.assertIn('unlock = ability Police', unlocked)
                self.assertIn('unlock = upgrade Garrison_Rate', unlocked)
                self.assertIn('unlock = perk Extra_Zones', unlocked)
                for perk in ('Flammable_Gas', 'Fall_Gas', 'Officer_Blast', 'Weak_Bridges',
                             'Blast_Gas', 'Hot_Fire', 'Quick_Deploy'):
                    self.assertIn('unlock = perk '+perk, unlocked)
                with self.assertRaises(FileExistsError): prepare.prepare_copy(source, 'inst1')
                with self.assertRaises(ValueError): prepare.prepare_copy(source, '../outside')
                with self.assertRaises(ValueError): prepare.prepare_copy(root, 'inst2')

    def test_wrong_build_and_links_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root, source = Path(d)/'repo', Path(d)/'installed'
            root.mkdir(); source.mkdir()
            (source/'zombies-arent-real.exe').write_bytes(b'wrong')
            with patch.object(prepare, 'ROOT', root), patch.object(prepare, 'expected_hash', return_value='invalid'):
                with self.assertRaisesRegex(ValueError, 'build'): prepare.prepare_copy(source, 'inst1')
                self.assertFalse((root/'game-copies/inst1').exists())
            with patch.object(prepare, 'is_link', return_value=True):
                with self.assertRaisesRegex(ValueError, 'link'): prepare.checked_files(source)


if __name__ == '__main__': unittest.main()
