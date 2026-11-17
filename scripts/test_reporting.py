import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import torch
import nn_play2 as train
import nn_report as report


class ReportingTests(unittest.TestCase):
    def test_saved_metric_and_start_kinds_stay_separate(self):
        rows = [dict(run_id='r', checkpoint_id='p', scenario=1, start_kind='fresh',
                     mode='play', end='won', saved_frac=.4, frac=.01),
                dict(run_id='r', checkpoint_id='p', scenario=1, start_kind='carry',
                     mode='play', end='won', saved_frac=.9),
                dict(run_id='r', checkpoint_id='p', scenario=1, start_kind='fresh',
                     mode='play', end='timeout', saved_frac=1.),
                dict(run_id='r', checkpoint_id='p', scenario=1, start_kind='fresh',
                     mode='play', end='lost', saved_frac=None)]
        fresh = next(r for r in report.aggregate(rows) if r['start_kind']=='fresh')
        self.assertEqual(fresh['completed_known'], 1)
        self.assertEqual(fresh['at_least_35_percent'], 1)
        self.assertEqual(fresh['incomplete'], 1)
        self.assertEqual(fresh['unknown_outcome'], 1)
        self.assertEqual(fresh['minimum_saved'], .4)

    def test_play_and_greedy_never_update_or_save(self):
        class Pool:
            jobs = None
            def __init__(self, n): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def map(self, fn, jobs):
                Pool.jobs = jobs
                return [[dict(pid=123, obs=[[0]*train.NOBS], end='timeout',
                              saved_frac=1., R=0., bootstrap=0.)]]
        with tempfile.TemporaryDirectory() as tmp:
            model, history = Path(tmp)/'model.pt', Path(tmp)/'history.jsonl'
            net = train.PolicyNet2()
            train.save_checkpoint(net, torch.optim.Adam(net.parameters()), model, 'test')
            original = model.read_bytes()
            for mode in ('play', 'greedy'):
                with self.subTest(mode=mode), patch.object(train.mp, 'Pool', Pool), \
                     patch.object(train, 'ppo_update') as update, patch.object(train, 'save_checkpoint') as save, \
                     patch('sys.argv', ['nn_play2.py', mode, '--pids', '123', '--pid', '123',
                           '--rounds', '1', '--eps', '1', '--model', str(model), '--history', str(history)]):
                    train.main()
                    update.assert_not_called()
                    save.assert_not_called()
                    self.assertEqual(Pool.jobs[0][0][4]['greedy'], mode=='greedy')
                    self.assertEqual(model.read_bytes(), original)
            self.assertEqual(len(history.read_text().splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
