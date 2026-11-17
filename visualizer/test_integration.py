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


class FakeGame:
    fail = False

    def __init__(self, pid):
        assert pid == -1
        self.calls = 0
        self.cw, self.ch = 1920, 1200
        self.vi = SimpleNamespace(key_press=lambda *args, **kwargs: None)

    def obs(self):
        self.calls += 1
        if self.fail and self.calls == 3:
            raise RuntimeError('synthetic observation failure')
        return dict(civ=100, zomb=1, converting=0, corpses=0, police=0, money=3111.0)

    def to_planning(self):
        return self.obs()

    def ready(self):
        pass

    def set_loadout(self, kit):
        pass

    def dump(self):
        return {'where': {'phase': 'playing'}, 'clock': {}, 'economy': {}, 'counts': {}}

    def crowd_topk(self):
        return [], 0

    def hot_spot(self):
        return None


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

    def episode(self, observer, fail=False):
        clock = itertools.count(0, .01)
        FakeGame.fail = fail
        overrides = dict(Observer=observer, PLAN_STEPS=1, BATTLE_T=0,
                         load_bind_keys=lambda env: [], q_saved=lambda pid, dur: None,
                         time=SimpleNamespace(time=lambda: next(clock), sleep=lambda _: None))
        with patch.dict(self.globals, overrides), patch.dict(sys.modules, {'env_zar': SimpleNamespace(ZAREnv=FakeGame)}):
            with patch.object(torch.distributions.Categorical, 'sample', return_value=torch.tensor([0])):
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
            self.assertEqual(frame['selected'], {'hu': observed['us'][index], 'hc': observed['cs'][index]})
            self.assertEqual(len(frame['values']['input']),
                             self.globals['NOBS'])
            inp = next(l for l in frame['graph']['layers']
                       if l['id'] == 'input')
            self.assertEqual(inp['labels'], self.globals['INPUT_LABELS'])
            self.assertNotRegex(' '.join(inp['labels']), r'\binput \d+\b')
            self.assertAlmostEqual(sum(frame['probabilities']['hu']), 1, places=6)
        self.assertFalse(list(Path(self.temp.name).glob('*.json')))

    def test_episode_failure_still_closes_observer(self):
        result = self.episode(self.factory, fail=True)
        self.assertEqual(result['err'], 'synthetic observation failure')
        self.assertEqual(len(self.observers), 1)
        self.assertTrue(self.observers[0]._closed)
        self.assertFalse(list(Path(self.temp.name).glob('*.json')))


if __name__ == '__main__':
    unittest.main()
