"""Battle pause-watchdog regression: the freeze check in run_episode()
must compare observations from DISTINCT battle iterations, never the
current observation against a snapshot already updated to it (the
cc8ef9f defect compared prev_o=dict(o) against o itself, so any battle
with zombies on screen pressed SPACE every second iteration).

These tests drive the REAL trainer function (run_episode) against a
scripted fake environment with a fake clock and a recording virtual
input: no live game, no real PIDs.

Obs indexing in the fake: 1 = to_planning(), 2 = first planning loop
iteration, 3 = the ready transition's prev_o re-observation, battle
iteration i = obs index 3 + i.
"""
import itertools
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch


class ScriptGame:
    """Fake ZAREnv: obs() replays (civ, zomb) samples; every key_press is
    recorded as (obs_index_at_press, vk, sc) so presses can be attributed
    to the iteration that triggered them."""

    def __init__(self, pid, script):
        assert pid == -1
        self.script = script
        self.calls = 0            # obs()s served
        self.keys = []            # (obs_index_at_press, vk, sc)
        self.cw, self.ch = 1920, 1200
        self.vi = SimpleNamespace(key_press=self._press)

    def _press(self, vk, sc=None, **kw):
        self.keys.append((self.calls, vk, sc))

    def obs(self):
        self.calls += 1
        civ, zomb = self.script[min(self.calls - 1, len(self.script) - 1)]
        return dict(civ=civ, zomb=zomb, converting=0, corpses=0, police=0,
                    money=3111.0)

    def to_planning(self):
        return self.obs()

    def crowd_topk(self):
        return [], 0

    def hot_spot(self):
        return None


def run_battle(samples):
    """Run one real episode: planning steps until PLAN_STEPS triggers
    ready, then `samples` as battle iterations; ends via the BATTLE_T
    bound of the fake 1 s/tick clock. Returns (episode_result, game)."""
    script = [(100, 0), (100, 0), (100, 42)] + list(samples) + [(60, 10)] * 6
    game_box = []

    def factory(pid):
        game = ScriptGame(pid, script)
        game_box.append(game)
        return game

    root = Path(__file__).resolve().parent
    source = runpy.run_path(str(root.parent / 'scripts' / 'nn_play2.py'),
                            run_name='test_watchdog')
    run_episode = source['run_episode']
    model = source['PolicyNet2']()
    clock = itertools.count(0, 1.0)

    def ready(_env):
        game_box[0].keys.append((-1, 0x52, 0))   # phase marker, not SPACE

    overrides = dict(Observer=None, PLAN_STEPS=1, BATTLE_T=60,
                     ready_once=ready,
                     time=SimpleNamespace(time=lambda: next(clock),
                                          sleep=lambda _s: None))
    with patch.dict(run_episode.__globals__, overrides), \
            patch.dict(sys.modules, {'env_zar':
                                     SimpleNamespace(ZAREnv=factory)}), \
            patch.object(torch.distributions.Categorical, 'sample',
                         return_value=torch.tensor([0])):
        result = run_episode((-1, model.state_dict(), False, 'wd-test'))
    return result, game_box[0]


def watchdog_presses(game, up_to_sample=None):
    """SPACE(sc=57) presses attributed to battle iterations 1..n
    (obs indices 4..3+n); the ready marker and 8x-speed key (0x74) are
    not watchdog presses."""
    lo = 4
    hi = up_to_sample + 3 + 1 if up_to_sample is not None else 1 << 30
    return [k for k in game.keys if k[1] == 0x20 and k[2] == 57
            and lo <= k[0] < hi]


class WatchdogTests(unittest.TestCase):
    def assert_no_err(self, result):
        self.assertNotIn('err', result, result.get('err'))

    def test_progressing_battle_gets_zero_presses(self):
        """THE reproduction: strictly changing observations must not
        trigger a single pause-recovery SPACE (cc8ef9f pressed every
        second iteration)."""
        res, g = run_battle([(100, 40), (90, 35), (85, 30), (78, 25),
                             (70, 20), (65, 15)])
        self.assert_no_err(res)
        self.assertGreaterEqual(g.calls - 3, 6, 'samples not consumed')
        self.assertEqual(watchdog_presses(g, up_to_sample=6), [])

    def test_either_counter_changes_counts_as_progress(self):
        res, g = run_battle([(100, 40), (99, 40), (98, 40), (98, 39),
                             (98, 38)])
        self.assert_no_err(res)
        self.assertEqual(watchdog_presses(g, up_to_sample=5), [])
    def test_progress_between_stationary_breaks_streak(self):
        """S,S -> one no-progress comparison; B resets the streak; the
        press fires only after the SECOND consecutive no-progress
        comparison of the new streak (battle iteration 6 = obs 9):
        progress between stationary samples really does clear it."""
        res, g = run_battle([(100, 40), (100, 40), (95, 40), (100, 40),
                             (100, 40), (100, 40)])
        self.assert_no_err(res)
        presses = watchdog_presses(g, up_to_sample=6)
        self.assertEqual([p[0] for p in presses], [9],
                         f'expected exactly one press at obs 9, got '
                         f'{presses}')

    def test_stationary_threshold_and_reset(self):
        """Cold start: first battle sample seeds the snapshot (no press);
        presses then land on every 2nd stationary iteration = threshold 2
        + counter reset (battle iters 3,5 = obs 6,8). (Not proof the
        game was paused — only that the streak machine behaves.)"""
        res, g = run_battle([(100, 40)] * 6)
        self.assert_no_err(res)
        self.assertGreaterEqual(g.calls - 3, 6, 'too few battle iters')
        presses = watchdog_presses(g, up_to_sample=6)
        self.assertEqual([p[0] for p in presses], [6, 8],
                         f'threshold-2 cadence broken: {presses}')

    def test_new_episode_starts_cold(self):
        """No stale freeze streak may cross the episode boundary: two
        identical episodes behave identically, and the first battle
        iterations never press."""
        res1, g1 = run_battle([(100, 40)] * 6)
        res2, g2 = run_battle([(100, 40)] * 6)
        self.assert_no_err(res1)
        self.assert_no_err(res2)
        self.assertEqual(watchdog_presses(g1, 6), watchdog_presses(g2, 6))
        self.assertTrue(all(p[0] >= 6 for p in watchdog_presses(g1, 6)),
                        'first battle iteration must not press')

    def test_reward_still_uses_true_previous_observation(self):
        """The fix must not disturb reward bookkeeping: battle r for
        civ 100->99 equals 8*dfrac = -0.08 (+kills term), NOT 0.0 (which
        a broken prev_o at loop top would produce)."""
        res, g = run_battle([(100, 40), (99, 39)])
        self.assert_no_err(res)
        # rews: [planning r=0, battle1 (dciv 0 vs seed, +3 kills),
        # battle2 (-1 civ, -1 zomb)]
        self.assertAlmostEqual(res['rews'][0], 0.0, places=6)
        self.assertAlmostEqual(res['rews'][1], 2 * 2e-6, places=6)
        self.assertAlmostEqual(res['rews'][2], -0.08 + 2e-6, places=5)

if __name__ == '__main__':
    unittest.main()
