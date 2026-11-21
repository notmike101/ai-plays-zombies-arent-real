"""No live PIDs: the preparation-credit study journals the pre-validation attempt
result (the actual critic cutoff) even when the batch is rejected, and journals the
applied mode in a separate receipt only after a successful PPO update; evaluation
never infers a target and never emits a receipt."""
from contextlib import nullcontext
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nn_play2 as train


def episode_row(job, invalid_arm=None):
    rnd = int(job[4].split('/')[1])
    arm = job[1]
    if rnd == 0 and arm == 'preparation_control':
        outcome = dict(end='timeout', timeout_phase='planning', bootstrap=0.0, saved_frac=None)
    elif rnd == 0:
        outcome = dict(end='timeout', timeout_phase='planning', bootstrap=-0.3125, saved_frac=None)
    elif rnd == 1 and arm == 'preparation_credit':
        outcome = dict(end='timeout', timeout_phase='planning', bootstrap=0.5, saved_frac=None)
    elif rnd == 1:
        outcome = dict(end='timeout', timeout_phase='playing', bootstrap=-1.5, saved_frac=None)
    elif arm == 'preparation_control':
        outcome = dict(end='aborted', timeout_phase=None, bootstrap=0.0, saved_frac=.1)
    else:
        outcome = dict(end='timeout', timeout_phase='planning', bootstrap=3.25, saved_frac=None)
    row = dict(outcome, win=False, advance=False, sim=0., t=10., board_id='c6f9fa75237ad12a',
               log_started=1795252212157 + rnd, start_kind='fresh',
               outbreak={'seed': 836399025 + rnd * 7 + len(arm)},
               us=[], obs=[], battle_actions={}, reward_components={},
               ready_choices=None, ready_stats=None, shelter=None,
               experiment_signal=dict(receipts=dict(
                   preparation_credit=arm == 'preparation_credit')))
    if rnd == 0 and arm == invalid_arm:
        row['force_invalid'] = True
    return row


def journal_rows(invalid_arm=None, update_fails=False):
    """One training round plus two frozen rounds; returns (summary rows, receipts)
    where receipts is None while timeout-bootstrap-receipts.jsonl is absent."""
    import compare_spatial as comp
    torch = train.torch
    real_trajectory = train.valid_trajectory

    def ppo_update(*args, **kwargs):
        if update_fails:
            raise RuntimeError('optimizer step failed')
        return {}

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'analysis').mkdir()
        net = train.PolicyNet2()
        adam = torch.optim.Adam(train.PolicyNet2().parameters(), lr=3e-4).state_dict()
        with patch('sys.argv', ['compare_spatial', '--copies', 'inst13', 'inst14',
                                '--eval-copies', 'inst17', 'inst18', '--seed', '336571',
                                '--train-rounds', '1', '--eval-rounds', '2',
                                '--compare-preparation-credit', '--warm-start', 'paired.pt',
                                'preparation_control']), \
                patch.object(comp.operator, 'ROOT', root), \
                patch.object(comp.operator, 'training_lock', return_value=nullcontext()), \
                patch.object(comp.operator, 'inventory', return_value=[]), \
                patch.object(comp.operator, 'require_idle'), \
                patch.object(comp.operator, 'preflight', return_value={'ok': True}), \
                patch.object(comp.operator, 'limit_resources'), \
                patch.object(comp.operator, 'require_resource_headroom'), \
                patch.object(comp, 'ProcessPoolExecutor', return_value=nullcontext()), \
                patch.object(comp, 'load_warm_start',
                             return_value=(net.state_dict(), adam, {123},
                                           {'arm': 'preparation_control', 'sha256': 'a' * 64})), \
                patch.object(comp.trainer, 'valid_trajectory',
                             lambda row: not row.get('force_invalid') and real_trajectory(row)), \
                patch.object(comp.trainer, 'ppo_update', ppo_update), \
                patch.object(comp, 'retain_natural_win', lambda *args: -1.), \
                patch.object(comp, 'collect_pairs',
                             side_effect=lambda pool, jobs, run, **kwargs:
                             [episode_row(job, invalid_arm) for job in jobs]):
            failure = None
            try:
                comp.main()
            except RuntimeError as error:
                failure = error
        assert (failure is None) == (invalid_arm is None and not update_fails), failure
        run, = (root / 'analysis').iterdir()
        assert run.name.startswith('coverage-preparation-credit-'), run.name
        rows = [json.loads(line)
                for line in (run / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
        receipt_journal = run / 'timeout-bootstrap-receipts.jsonl'
        receipts = ([json.loads(line)
                     for line in receipt_journal.read_text(encoding='utf-8').splitlines()]
                    if receipt_journal.is_file() else None)
        return rows, receipts


def row_of(rows, rnd, arm):
    found = [row for row in rows if row['round'] == rnd and row['arm'] == arm]
    assert len(found) == 1, (rnd, arm, found)
    assert 'timeout_preparation' in found[0]
    return found[0]


class CutoffReceiptJournalTests(unittest.TestCase):
    def test_preupdate_summary_journals_cutoff_without_completing_the_disposition(self):
        rows, _ = journal_rows()
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertNotIn('timeout_bootstrap_update', row)
        trained = row_of(rows, 0, 'preparation_control')
        self.assertEqual(trained['timeout_bootstrap'], 0.0)
        self.assertIsNotNone(trained['timeout_bootstrap'])
        self.assertEqual(row_of(rows, 0, 'preparation_credit')['timeout_bootstrap'], -0.3125)

    def test_successful_update_emits_one_receipt_per_planning_timeout(self):
        _, receipts = journal_rows()
        self.assertEqual(receipts, [
            dict(round=0, arm='preparation_control', seed=336571,
                 log_started=1795252212157, timeout_bootstrap_update='consumed'),
            dict(round=0, arm='preparation_credit', seed=336571,
                 log_started=1795252212157, timeout_bootstrap_update='substituted')])

    def test_evaluation_journals_cutoffs_but_never_emits_receipts(self):
        rows, receipts = journal_rows()
        self.assertEqual(row_of(rows, 1, 'preparation_credit')['timeout_bootstrap'], 0.5)
        self.assertEqual(row_of(rows, 2, 'preparation_credit')['timeout_bootstrap'], 3.25)
        self.assertTrue(all(receipt['round'] == 0 for receipt in receipts))
        battle = row_of(rows, 1, 'preparation_control')
        self.assertEqual(battle['end'], 'timeout')
        self.assertIsNone(battle['timeout_bootstrap'])
        self.assertIsNone(row_of(rows, 2, 'preparation_control')['timeout_bootstrap'])

    def test_invalid_sibling_keeps_cutoff_but_emits_no_receipt(self):
        rows, receipts = journal_rows(invalid_arm='preparation_credit')
        self.assertEqual([(row['round'], row['arm']) for row in rows],
                         [(0, 'preparation_control'), (0, 'preparation_credit')])
        self.assertEqual(rows[0]['timeout_bootstrap'], 0.0)
        self.assertEqual(rows[1]['timeout_bootstrap'], -0.3125)
        self.assertIsNone(receipts)

    def test_failed_update_keeps_cutoff_but_emits_no_receipt(self):
        rows, receipts = journal_rows(update_fails=True)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['timeout_bootstrap'], 0.0)
        self.assertEqual(rows[1]['timeout_bootstrap'], -0.3125)
        self.assertIsNone(receipts)


if __name__ == '__main__':
    unittest.main()
