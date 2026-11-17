"""Native phase/pause and transition regressions; fake game PIDs only."""
import runpy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import torch
from fake_training import FakeGame, FakeClock


def run_battle(rate=0, pause=False):
    source = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/nn_play2.py'))
    fn = source['run_episode']
    game = FakeGame(-1)
    clock = FakeClock(game, rate)
    original_press = game.press
    first = True
    def press(vk, **kw):
        nonlocal first
        original_press(vk, **kw)
        if pause and vk == 0x20 and first:
            game.paused = True
            first = False
    game.vi.key_press = press
    with patch.dict(fn.__globals__, dict(Observer=None, PLAN_STEPS=1, BATTLE_T=3,
                    load_bind_keys=lambda e: [], time=clock)), \
            patch.dict(sys.modules, {'env_zar': SimpleNamespace(ZAREnv=lambda pid: game,
                         ZAREnvError=RuntimeError)}), \
            patch.object(torch.distributions.Categorical, 'sample', return_value=torch.tensor(0)):
        result = fn((-1, source['PolicyNet2']().state_dict(), False, 'test'))
    return result, game


class WatchdogTests(unittest.TestCase):
    def test_stationary_unpaused_battle_never_gets_space(self):
        result, game = run_battle()
        self.assertNotIn('err', result)
        self.assertEqual(game.keys.count(0x20), 1)  # READY only
        self.assertEqual(result['end'], 'timeout')
        self.assertIn('bootstrap', result)
        self.assertEqual(result['R'], 0)

    def test_confirmed_pause_gets_one_unpause(self):
        result, game = run_battle(pause=True)
        self.assertNotIn('err', result)
        self.assertEqual(game.keys.count(0x20), 2)

    def test_doomed_battle_retries_and_log_finishes(self):
        result, game = run_battle(rate=20)
        self.assertNotIn('err', result)
        self.assertEqual(result['end'], 'aborted')
        self.assertEqual(game.keys[-2:], [0x52, 0x52])
        self.assertTrue(game.closed_log)
        self.assertLessEqual(result['frac'], .1)

    def test_reward_tracks_next_state_infections(self):
        result, game = run_battle(rate=2)
        self.assertNotIn('err', result)
        self.assertLess(result['rews'][0], 0)  # READY transition's infections
        self.assertAlmostEqual(sum(result['rews']), -game.infections/100.)

if __name__ == '__main__':
    unittest.main()
