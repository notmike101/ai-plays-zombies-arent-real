"""Offline trainer regressions. Never attach to a game PID."""
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
import nn_play2 as train


class LearningTests(unittest.TestCase):
    def test_zero_reward_terminal_returns(self):
        adv, ret = train.gae([0, 0, 0], [1, 1, 1], gamma=1, lam=1)
        np.testing.assert_allclose(adv, [-1, -1, -1])
        np.testing.assert_allclose(ret, [0, 0, 0])

    def test_lambda_and_bootstrap(self):
        adv, ret = train.gae([1, 2], [3, 4], gamma=.5, lam=0,
                             bootstrap=6)
        np.testing.assert_allclose(adv, [0, 1])
        np.testing.assert_allclose(ret, [3, 5])
        adv, _ = train.gae([1, 2], [3, 4], gamma=.5, lam=1,
                           bootstrap=6)
        np.testing.assert_allclose(adv, [.5, 1])

    def test_each_pid_is_owned_by_one_batch(self):
        active, overlap = set(), []
        lock = threading.Lock()

        def episode(args):
            pid = args[0]
            with lock:
                if pid in active:
                    overlap.append(pid)
                active.add(pid)
            time.sleep(.01)
            with lock:
                active.remove(pid)
            return {'pid': pid}

        with patch.object(train, 'run_episode', episode):
            jobs = train.episode_batches([101, 102, 103], {}, False, 'test', 3)
            with ThreadPoolExecutor(3) as pool:
                rows = list(pool.map(train.run_batch, jobs))
        self.assertEqual(overlap, [])
        self.assertEqual([[r['pid'] for r in batch] for batch in rows],
                         [[101]*3, [102]*3, [103]*3])
        with self.assertRaises(ValueError):
            train.episode_batches([101, 101], {}, False, 'test', 2)

    def test_checkpoint_restores_adam_and_retains_previous(self):
        net = train.PolicyNet2()
        opt = torch.optim.Adam(net.parameters())
        sum(p.sum() for p in net.parameters()).backward()
        opt.step()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model.pt'
            train.save_checkpoint(net, opt, path, 'run-a')
            original = path.read_bytes()
            restored = train.PolicyNet2()
            resumed = torch.optim.Adam(restored.parameters())
            train.load_checkpoint(restored, resumed, path)
            self.assertTrue(resumed.state)
            for a, b in zip(net.parameters(), restored.parameters()):
                torch.testing.assert_close(a, b)
            train.save_checkpoint(net, opt, path, 'run-b')
            self.assertEqual(Path(str(path) + '.previous').read_bytes(), original)

    def test_only_train_mode_can_update(self):
        self.assertTrue(train.training_enabled('train', False))
        for mode, random in [('play', False), ('greedy', False), ('train', True)]:
            self.assertFalse(train.training_enabled(mode, random))


if __name__ == '__main__':
    unittest.main()
