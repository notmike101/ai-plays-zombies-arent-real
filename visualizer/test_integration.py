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

    def test_geometry_input_is_recomputed_at_planning_timeout(self):
        import numpy as np

        game = FakeGame(-1)
        source = self.globals
        observations = []

        class GeometryMechanics(FakeMechanics):
            refreshes = 0
            def refresh(self, st):
                super().refresh(st)
                self.refreshes += 1
                point = [0., 140.] if self.refreshes == 1 else [3000., 3000.]
                st.update(playarea_boundary=[(0, 0), (1920, 0), (1920, 1200), (0, 1200)],
                          native=dict(camera=(0., 0., 1.), zones=[],
                                      units=dict(pos=np.array([point]), kind=np.array([0]))))

        class RecordingPolicy(source['PolicyNet2']):
            def __init__(self):
                super().__init__(shelter_geometry=True)

            def forward(self, x, h=None):
                observations.append(x.detach().clone())
                return super().forward(x, h)

        overrides = dict(Observer=None, PLAN_STEPS=1, Mechanics=GeometryMechanics,
                         load_bind_keys=lambda env: [], time=FakeClock(game),
                         extra_masks=lambda st: np.zeros((source['NU'] - 72, source['NC'])))
        with patch.dict(source, overrides), patch.dict(sys.modules, {
                'env_zar': SimpleNamespace(ZAREnv=lambda pid: game, ZAREnvError=RuntimeError)}):
            with patch.object(torch.distributions.Categorical, 'sample',
                              side_effect=[torch.tensor(0), torch.tensor(0)]):
                model = RecordingPolicy()
                result = self.run_episode((-1, model.state_dict(), False, 'geometry-timeout',
                                           dict(shelter_geometry_input=True)),
                                          policy_factory=RecordingPolicy)
        self.assertNotIn('err', result)
        self.assertEqual(result['end'], 'timeout')
        self.assertEqual(len(observations), 2)
        self.assertTrue(observations[0][..., -source['NC']:].any())
        self.assertFalse(observations[1][..., -source['NC']:].any())

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

    def test_greedy_episode_tries_the_next_target_after_one_rejection(self):
        result, casts = self.battle_boundary_episode(False)
        self.assertEqual(result['outside_targets'], {'missile/8': 1})
        self.assertEqual(result['cs'][1:3], [7, 0])
        self.assertEqual(len(casts), 1)

    def test_battle_boundary_filter_prevents_the_same_rejected_choice(self):
        result, casts = self.battle_boundary_episode(True)
        self.assertEqual(result['outside_targets'], {})
        self.assertEqual(result['cs'][1], 0)
        self.assertEqual(len(casts), 1)
        signal = result['experiment_signal']
        self.assertTrue(signal['receipts']['battle_boundary'])
        self.assertGreater(signal['battle_boundary']['reference_rejected_probability_sum'], .9)
        self.assertEqual(signal['battle_boundary']['battle_rejections'], {})

    def battle_boundary_episode(self, enable_filter):
        game=FakeGame(-1)
        casts=[]
        game.cast=lambda key,x,y: casts.append((key,x,y))
        game.battle_stock=lambda: {'Missile':1-int(bool(casts))}
        source=self.globals

        class BoundedMechanics(FakeMechanics):
            def refresh(self, st):
                super().refresh(st)
                st['playarea_boundary']=[(0,0),(500,0),(500,1000),(0,1000)]

        class GreedyPolicy(source['PolicyNet2']):
            def forward(self, x, h=None):
                tools,cells,value,h=super().forward(x,h)
                tools.zero_()
                tools[...,1 if x[0,0,source['PLANNING_INDEX']] else 26]=10.
                cells.zero_()
                cells[...,26*source['NC']+7]=10.
                cells[...,26*source['NC']]=5.
                return tools,cells,value,h

        overrides=dict(Observer=None,PLAN_STEPS=1,BATTLE_T=.2,Mechanics=BoundedMechanics,
                       load_bind_keys=lambda env: [],time=FakeClock(game),build_deck=lambda *args: [
                           dict(name='Missile',key='1',charges=1,unlock=0,arrival=0,pending=False)])
        with patch.dict(source,overrides), patch.dict(sys.modules, {
                'env_zar':SimpleNamespace(ZAREnv=lambda pid:game,ZAREnvError=RuntimeError)}):
            options = dict(greedy=True, battle_boundary_filter=enable_filter, experiment_signal='receipts')
            result = self.run_episode((-1, self.model.state_dict(), False, 'repeat-reject', options),
                                      policy_factory=GreedyPolicy)
        self.assertNotIn('err', result)
        return result, casts

    def test_special_activation_receipts_credit_unique_buildings_and_cap_bonus(self):
        result=self.episode(None,special_receipts=[None,(0,5),(0,5),(1,5),(2,5),(3,5)])
        self.assertNotIn('err',result)
        self.assertEqual(len(result['special_activations']),4)
        self.assertAlmostEqual(result['reward_components']['special_activation'],.03)
        self.assertEqual(result['rews'][:6],[0.,.01,0.,.01,.01,0.])

    def test_battle_sampling_preserves_greedy_preparation(self):
        game = FakeGame(-1)

        class GreedyReady(self.globals['PolicyNet2']):
            def forward(self, x, h=None):
                tools, cells, value, h = super().forward(x, h)
                tools[..., 1] = 1000.
                return tools, cells, value, h

        overrides = dict(Observer=None, Mechanics=FakeMechanics, BATTLE_T=.1,
                         load_bind_keys=lambda env: [], time=FakeClock(game))
        with patch.dict(self.globals, overrides), patch.dict(sys.modules, {
                'env_zar': SimpleNamespace(ZAREnv=lambda pid: game, ZAREnvError=RuntimeError)}):
            with patch.object(torch.distributions.Categorical, 'sample',
                              side_effect=[torch.tensor(0), torch.tensor(0)]) as sample:
                result = self.run_episode((-1, self.model.state_dict(), False, 'battle-sampling',
                                           dict(greedy=True, sample_battle=True)), policy_factory=GreedyReady)
        self.assertNotIn('err', result)
        self.assertEqual(result['us'], [1, 0])
        self.assertEqual(sample.call_count, 2)

    def test_episode_rejects_native_battle_without_model_ready(self):
        game = FakeGame(-1)

        class UnexpectedPhase(FakeMechanics):
            def execute(self, st, name, cell):
                game.phase = 'playing'

        overrides = dict(Observer=None, Mechanics=UnexpectedPhase,
                         load_bind_keys=lambda env: [], time=FakeClock(game))
        tool = self.globals['TOOLS'].index('panel_building_5')
        with patch.dict(self.globals, overrides), patch.dict(sys.modules, {
                'env_zar': SimpleNamespace(ZAREnv=lambda pid: game, ZAREnvError=RuntimeError)}):
            with patch.object(torch.distributions.Categorical, 'sample',
                              side_effect=[torch.tensor(tool), torch.tensor(0)]):
                with redirect_stderr(io.StringIO()):
                    result = self.run_episode((-1, self.model.state_dict(), False, 'unexpected-phase'))
        self.assertRegex(result['err'], 'without model READY after panel_building_5')
        self.assertNotIn('saved_frac', result)
        self.assertTrue(game.closed_log and game.closed)
        self.assertNotIn(0x20, game.keys)

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
