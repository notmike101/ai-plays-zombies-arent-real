"""Operator tests use temporary files/fake processes; never control live games."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

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

    def test_preflight_accepts_policy_selected_roster_and_empty_slots(self):
        self.assertEqual(ops.planning_roster('roster_plan = Oil Sniper - Garrison Mine C4 MLRS'),
                         ['Oil','Sniper','-','Garrison','Mine','C4','MLRS'])
        for line in ('', 'roster_plan = Garrison', 'roster_plan = Unknown - - - - - -'):
            with self.assertRaisesRegex(ValueError,'roster'):ops.planning_roster(line)

    def test_copy_name_cannot_escape_owned_directory(self):
        for name in ('../inst1', 'inst1/../inst2', 'C:/Games', 'instX'):
            with self.assertRaises(ValueError):
                ops.owned_copy(name)
        self.assertEqual(ops.owned_copy('inst1'), ops.ROOT/'game-copies/inst1')


class LifecycleTests(unittest.TestCase):
    def test_training_refuses_an_existing_launcher_or_busy_copy(self):
        with self.assertRaisesRegex(ValueError, 'already active'):
            ops.require_idle([dict(pid=12, role='game',
                                  exe=str(ops.ROOT/'game-copies/inst1/zombies-arent-real.exe')),
                              dict(pid=13, role='launcher')], 'inst1', self_pid=999)
        for role in ('operator', 'launcher', 'trainer'):
            with self.assertRaisesRegex(ValueError, 'already active'):
                ops.require_idle([dict(pid=123, role=role)], 'inst1', self_pid=999)
        with self.assertRaisesRegex(ValueError, 'already running'):
            ops.require_idle([dict(pid=123, role='game',
                                  exe=str(ops.ROOT/'game-copies/inst1/zombies-arent-real.exe'))],
                             'inst1', self_pid=999)
        ops.require_idle([dict(pid=999, role='operator')], 'inst1', self_pid=999)
        ops.require_idle([dict(pid=888, role='operator')], 'inst1', self_pid=999, parent_pid=888)
        ops.require_idle([dict(pid=888, role='operator'), dict(pid=887, role='operator')],
                         'inst1', self_pid=999, ancestor_pids=[888, 887])
        with self.assertRaisesRegex(ValueError, 'already active'):
            ops.require_idle([dict(pid=888, role='trainer')], 'inst1', self_pid=999, parent_pid=888)

    def test_only_one_operator_can_hold_training_lock(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'lock'
            with ops.training_lock(path):
                with self.assertRaisesRegex(ValueError, 'operator'):
                    with ops.training_lock(path):
                        self.fail('Second lock was granted')
            with ops.training_lock(path):
                pass

    def test_failed_preflight_cannot_launch_training(self):
        args = SimpleNamespace(copy='inst1', rounds=1, seed=42, foreground=False)
        with patch.object(ops, 'inventory', return_value=[]), \
             patch.object(ops, 'preflight', return_value=dict(ok=False, errors=['missing checkpoint'])), \
             patch('subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'missing checkpoint'):
                ops.train(args)
            launch.assert_not_called()

    def test_background_start_uses_hidden_operator_with_explicit_run_options(self):
        import subprocess
        args = SimpleNamespace(copy='inst1', rounds=2, seed=42, foreground=False)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'analysis').mkdir()
            with patch.object(ops, 'ROOT', root), \
                 patch.object(ops, 'inventory', return_value=[]), \
                 patch.object(ops, 'preflight', return_value=dict(ok=True)), \
                 patch('subprocess.Popen') as launch:
                launch.return_value.pid = 123
                result = ops.train(args)
                self.assertEqual(result['status'], 'starting')
                self.assertEqual(result['pid'], 123)
                self.assertTrue(Path(result['log']).is_file())
                argv = launch.call_args.args[0]
                self.assertIn('--foreground', argv)
                self.assertEqual(argv[argv.index('--copy')+1], 'inst1')
                self.assertEqual(argv[argv.index('--seed')+1], '42')
                self.assertEqual(launch.call_args.kwargs['creationflags'], subprocess.CREATE_NO_WINDOW)

    def test_insufficient_resources_never_launches_game_or_trainer(self):
        args = SimpleNamespace(copy='inst1', rounds=1, seed=42, foreground=True)
        with tempfile.TemporaryDirectory() as d, \
             patch.object(ops, 'LOCK', Path(d)/'lock'), \
             patch.object(ops, 'inventory', return_value=[]), \
             patch.object(ops, 'preflight', return_value=dict(ok=True)), \
             patch.object(ops, 'limit_resources', side_effect=ValueError('Insufficient headroom')), \
             patch('subprocess.call') as launch:
            with self.assertRaisesRegex(ValueError, 'headroom'):
                ops.train(args)
            launch.assert_not_called()

    def test_foreground_training_passes_explicit_resume_paths_and_limits_before_launch(self):
        args = SimpleNamespace(copy='inst1', rounds=2, seed=42, foreground=True)
        with tempfile.TemporaryDirectory() as d, \
             patch.object(ops, 'LOCK', Path(d)/'lock'), \
             patch.object(ops, 'inventory', return_value=[]), \
             patch.object(ops, 'preflight', return_value=dict(ok=True)), \
             patch.object(ops, 'limit_resources') as limits, \
             patch('subprocess.call', return_value=0) as call:
            call.side_effect = lambda *a, **k: (limits.assert_called_once(), 0)[1]
            self.assertTrue(ops.train(args)['ok'])
            argv = call.call_args.args[0]
            self.assertEqual(argv[argv.index('--model')+1], str(ops.MODEL))
            self.assertEqual(argv[argv.index('--history')+1], str(ops.HISTORY))
            self.assertEqual(argv[argv.index('--copies')+1], 'inst1')
            self.assertNotIn('--random', argv)

    def test_visualizer_reuses_own_listener_and_rejects_foreign_listener(self):
        with patch.object(ops, 'listener', return_value=dict(pid=123, role='visualizer')), \
             patch('subprocess.Popen') as launch:
            self.assertEqual(ops.start_visualizer(8765, '127.0.0.1')['status'], 'already_running')
            launch.assert_not_called()
        with patch.object(ops, 'listener', return_value=dict(pid=456, role=None)), \
             patch('subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'another process'):
                ops.start_visualizer(8765, '127.0.0.1')
            launch.assert_not_called()

    def test_visualizer_accepts_its_venv_redirector_child_as_listener(self):
        server = dict(pid=321, create_time=100., role='visualizer', port=8766)
        parent = Mock()
        parent.pid = 123
        parent.children.return_value = [SimpleNamespace(pid=321)]
        parent.create_time.return_value = 99.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'analysis').mkdir()
            with patch.object(ops, 'ROOT', root), \
                 patch.object(ops, 'listener', side_effect=[None, server]), \
                 patch('subprocess.Popen') as launch, \
                 patch('psutil.Process', return_value=parent):
                launch.return_value.pid = 123
                launch.return_value.poll.return_value = None
                self.assertEqual(ops.start_visualizer(8766, '127.0.0.1')['pid'], 321)

    def test_stop_accepts_venv_and_base_python_children(self):
        p = Mock()
        p.create_time.return_value = 100.
        p.cmdline.return_value = ['python', str(ops.ROOT/'visualizer/server.py')]
        p.cwd.return_value = str(ops.ROOT)
        p.exe.return_value = 'C:/Python/python.exe'
        child = Mock()
        child.exe.return_value = 'D:/zar-scratch/.venv/Scripts/python.exe'
        p.children.return_value = [child]
        with patch('psutil.Process', return_value=p), \
             patch('psutil.wait_procs', return_value=([], [])), \
             patch.object(ops.sys, 'executable', child.exe()), \
             patch.object(ops.sys, '_base_executable', p.exe()):
            self.assertTrue(ops.stop_process(123, 100., 'visualizer')['ok'])
            p.kill.assert_called_once()
            child.kill.assert_called_once()
    def test_stop_rejects_reused_pid_foreign_script_and_unknown_child(self):
        p = Mock()
        p.create_time.return_value = 100.
        p.cmdline.return_value = ['python', str(ops.ROOT/'visualizer/server.py')]
        p.cwd.return_value = str(ops.ROOT)
        p.exe.return_value = 'C:/Python/python.exe'
        p.children.return_value = []
        with patch('psutil.Process', return_value=p):
            with self.assertRaisesRegex(ValueError, 'identity'):
                ops.stop_process(123, float('nan'), 'visualizer')
            p.kill.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'identity'):
                ops.stop_process(123, 99., 'visualizer')
            p.kill.assert_not_called()
            p.cmdline.return_value = ['python', 'E:/other/server.py']
            with self.assertRaisesRegex(ValueError, 'script'):
                ops.stop_process(123, 100., 'visualizer')
            p.kill.assert_not_called()
            p.cmdline.return_value = ['python', str(ops.ROOT/'visualizer/server.py')]
            child = Mock()
            child.exe.return_value = 'C:/other/app.exe'
            p.children.return_value = [child]
            with self.assertRaisesRegex(ValueError, 'child'):
                ops.stop_process(123, 100., 'visualizer')
            p.kill.assert_not_called()
            child.kill.assert_not_called()


if __name__ == '__main__':
    unittest.main()
