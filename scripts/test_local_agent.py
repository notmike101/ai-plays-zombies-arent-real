"""Operator tests use temporary files/fake processes; never control live games."""
import json
from pathlib import Path
import tempfile
import unittest

import local_agent as ops


class InspectionTests(unittest.TestCase):
    def test_process_roles_require_the_exact_checkout_script(self):
        root = Path('D:/zar-scratch')
        self.assertEqual(ops.script_role(['python', '-B', 'scripts/train_run.py'],
                                       root, root), 'launcher')
        self.assertEqual(ops.script_role(['python', str(root/'scripts/nn_play2.py'), 'train'],
                                       root/'scripts', root), 'trainer')
        self.assertIsNone(ops.script_role(['python', 'E:/other/server.py'], root, root))
        self.assertIsNone(ops.script_role(['python', '-c', 'print("server.py")'], root, root))
        self.assertIsNone(ops.script_role(['python', str(root/'scripts/local_agent.py'), 'status'],
                                         root, root))
        self.assertEqual(ops.script_role(['python', str(root/'scripts/local_agent.py'), 'train'],
                                       root, root), 'operator')

    def test_history_tolerates_an_in_progress_last_line_and_bounds_reads(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'history.jsonl'
            p.write_text('x'*4000+'\n'+json.dumps({'kind':'update','round':7})+'\n{"kind":')
            self.assertEqual(ops.recent_history(p, limit=512), [{'kind':'update','round':7}])
            self.assertEqual(ops.recent_history(Path(d)/'missing'), [])

    def test_missing_checkpoint_never_means_random_training(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'missing.*resume'):
                ops.inspect_checkpoint(Path(d)/'missing.pt')

    def test_checkpoint_requires_exact_semantics_and_optimizer(self):
        import torch
        import nn_play2 as train
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'policy.pt'
            c = {'schema': train.checkpoint_schema(), 'policy': {}, 'optimizer': {}}
            c['schema']['inputs'] = list(c['schema']['inputs'])
            c['schema']['inputs'][0] = 'wrong meaning, same width'
            torch.save(c, p)
            with self.assertRaisesRegex(ValueError, 'schema'):
                ops.inspect_checkpoint(p)
            c['schema'] = train.checkpoint_schema()
            torch.save(c, p)
            with self.assertRaisesRegex(ValueError, 'optimizer'):
                ops.inspect_checkpoint(p)

    def test_copy_name_cannot_escape_owned_directory(self):
        for name in ('../inst1', 'inst1/../inst2', 'C:/Games', 'instX'):
            with self.assertRaises(ValueError):
                ops.owned_copy(name)
        self.assertEqual(ops.owned_copy('inst1'), ops.ROOT/'game-copies/inst1')


if __name__ == '__main__':
    unittest.main()
