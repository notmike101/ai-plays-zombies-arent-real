"""Exercise the trainer's real episode function against a fake game, never a live PID."""
from contextlib import redirect_stderr
import io
import itertools
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from observer import Observer


from fake_training import FakeGame, FakeClock, FakeMechanics


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent
        (root / 'runtime').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root / 'runtime')
        source = runpy.run_path(str(root.parent / 'scripts' / 'nn_play2.py'), run_name='test_trainer')
        self.run_episode = source['run_episode']
        self.globals = self.run_episode.__globals__
        self.model = source['PolicyNet2']()
        self.assertTrue('Observer' in self.globals, 'Trainer must import the optional observer')
        self.assertIsNotNone(self.globals['Observer'], 'The real observer import must succeed')
        self.observers = []
        test = self

        class RecordingObserver(Observer):
            def __init__(self, net, pid, episode, **kwargs):
                super().__init__(net, pid, episode, directory=test.temp.name, **kwargs)
                self.frames = []
                test.observers.append(self)

            def publish(self, **kwargs):
                self.frames.append(self.snapshot(**kwargs))
                return super().publish(**kwargs)

        self.factory = RecordingObserver

    def tearDown(self):
        FakeGame.fail = False
        for observer in getattr(self, 'observers', []):
            observer.close()
        if hasattr(self, 'temp'):
            self.temp.cleanup()

    def episode(self, observer, fail=False, missile_cell=None, special_receipts=None):
        game = FakeGame(-1)
        clock = FakeClock(game)
        FakeGame.fail = fail
        overrides = dict(Observer=observer, PLAN_STEPS=1, BATTLE_T=.1,
                         Mechanics=FakeMechanics,
                         load_bind_keys=lambda env: [], q_saved=lambda pid, dur: None,
                         time=clock)
        samples = (1, 0, 0, 0)
        self.casts = []
        if missile_cell is not None:
            game.cast = lambda key, x, y: self.casts.append((key,x,y))
            game.battle_stock = lambda: {'Missile': 1-int(bool(self.casts))}
            overrides['build_deck'] = lambda *args: [
                dict(name='Missile', key='1', charges=1, unlock=0, arrival=0, pending=False)]
            class BoundedMechanics(FakeMechanics):
                def refresh(self, st):
                    super().refresh(st)
                    st['playarea_boundary'] = [(0,0),(500,0),(500,1000),(0,1000)]
            overrides['Mechanics'] = BoundedMechanics
            samples = (1, 0, 26, missile_cell)
        if special_receipts is not None:
            pending=iter(special_receipts)
            class SpecialMechanics(FakeMechanics):
                def execute(self,st,name,cell):
                    return next(pending)
            overrides.update(Mechanics=SpecialMechanics,PLAN_STEPS=10)
            tool=self.globals['TOOLS'].index('panel_building_5')
            samples=(tool,0)*len(special_receipts)+(1,0)+(0,0)*3
        with patch.dict(self.globals, overrides), patch.dict(sys.modules, {'env_zar': SimpleNamespace(ZAREnv=lambda pid: game, ZAREnvError=RuntimeError)}):
            with patch.object(torch.distributions.Categorical, 'sample', side_effect=[torch.tensor(v) for v in samples]):
                with redirect_stderr(io.StringIO()):
                    return self.run_episode((-1, self.model.state_dict(), False, 'test-episode'))

    def test_real_episode_publishes_actual_actions_and_preserves_result(self):
        baseline = self.episode(None)
        observed = self.episode(self.factory)
        self.assertNotIn('err', observed)
        for key in ('obs', 'us', 'cs', 'rews', 'R', 'win', 'frac'):
            self.assertEqual(baseline[key], observed[key])
        self.assertEqual(len(self.observers), 1)
        observer = self.observers[0]
        self.assertTrue(observer._closed)
        self.assertEqual([frame['phase'] for frame in observer.frames], ['planning', 'battle'])
        for index, frame in enumerate(observer.frames):
            self.assertEqual(frame['selected'], {'hu': observed['us'][index], 'hc': observed['us'][index]*self.globals['NC']+observed['cs'][index]})
            self.assertEqual(len(frame['values']['input']),
                             self.globals['NOBS'])
            inp = next(l for l in frame['graph']['layers']
                       if l['id'] == 'input')
            self.assertEqual(inp['labels'], self.globals['INPUT_LABELS'])
            self.assertNotRegex(' '.join(inp['labels']), r'\binput \d+\b')
            self.assertAlmostEqual(sum(frame['probabilities']['hu']), 1, places=6)
        self.assertFalse(list(Path(self.temp.name).glob('*.json')))

    def test_outside_missile_penalizes_transition_without_spending_charge(self):
        outside = self.episode(None, missile_cell=7)
        self.assertNotIn('err', outside)
        self.assertEqual(self.casts, [])
        self.assertEqual(outside['outside_playarea_actions'], 1)
        self.assertEqual(outside['rews'][-1], -.02)
        self.assertEqual(outside['reward_components']['outside_playarea'], -.02)
        inside = self.episode(None, missile_cell=0)
        self.assertNotIn('err', inside)
        self.assertEqual(len(self.casts), 1)
        self.assertEqual(inside['battle_actions']['stock_decreased'], 1)
        self.assertEqual(inside['reward_components']['outside_playarea'], 0.)

    def test_special_activation_receipts_credit_unique_buildings_and_cap_bonus(self):
        result=self.episode(None,special_receipts=[None,(0,5),(0,5),(1,5),(2,5),(3,5)])
        self.assertNotIn('err',result)
        self.assertEqual(len(result['special_activations']),4)
        self.assertAlmostEqual(result['reward_components']['special_activation'],.03)
        self.assertEqual(result['rews'][:6],[0.,.01,0.,.01,.01,0.])

    def test_episode_failure_still_closes_observer(self):
        result = self.episode(self.factory, fail=True)
        self.assertEqual(result['err'], 'synthetic observation failure')
        self.assertEqual(len(self.observers), 1)
        self.assertTrue(self.observers[0]._closed)
        self.assertFalse(list(Path(self.temp.name).glob('*.json')))

    def test_timeout_separates_snapshot_from_outcome_and_reward(self):
        result = self.episode(None)
        self.assertEqual(result['end'], 'timeout')
        self.assertIsNone(result['saved_frac'])
        self.assertEqual(result['observed_saved_frac'], 1.)
        self.assertEqual(result['timeout_phase'], 'playing')
        self.assertEqual(result['reward_components']['terminal'], 0.)
        self.assertAlmostEqual(sum(result['reward_components'].values()), result['R'])


if __name__ == '__main__':
    unittest.main()
