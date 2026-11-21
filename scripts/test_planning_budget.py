"""No live PIDs: planning budget feature edges, extend prefix, bins, archive, signal."""
from contextlib import nullcontext
from copy import deepcopy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

import nn_play2 as train


class PlanningBudgetFeatureTests(unittest.TestCase):
    def test_feature_counts_planning_decisions_and_zeroes_outside_planning(self):
        self.assertEqual(train.planning_budget_observation(0, 60, True), 1.)
        self.assertEqual(train.planning_budget_observation(30, 60, True), .5)
        self.assertAlmostEqual(train.planning_budget_observation(59, 60, True), 1 / 60)
        self.assertEqual(train.planning_budget_observation(60, 60, True), 0.)
        self.assertEqual(train.planning_budget_observation(75, 60, True), 0.)
        self.assertEqual(train.planning_budget_observation(0, 60, False), 0.)
        self.assertEqual(train.planning_budget_observation(45, 30, False), 0.)

    def test_ready_bins_split_the_cap_in_thirds(self):
        for decision in (0, 19):
            self.assertEqual(train.ready_budget_bin(decision, 60), 'early')
        for decision in (20, 39):
            self.assertEqual(train.ready_budget_bin(decision, 60), 'mid')
        for decision in (40, 59, 60, 75):
            self.assertEqual(train.ready_budget_bin(decision, 60), 'late')

    def test_make_obs_appends_only_an_explicit_budget_value(self):
        state = dict(t=0., planning=True, spend_frac=0., sim=0.)
        observed = dict(money=500., civ=100, zomb=0, converting=0, corpses=0, police=0)
        plain = train.make_obs(state, observed, .5, 0., 0., [], 0, 0, 0.)
        self.assertEqual(len(plain), train.NOBS)
        armed = train.make_obs(dict(state, planning_budget_value=.25),
                               observed, .5, 0., 0., [], 0, 0, 0.)
        self.assertEqual(len(armed), train.NOBS + 1)
        self.assertEqual(armed[-1], .25)
        self.assertEqual(armed[:-1], plain)
        zeroed = train.make_obs(dict(state, planning_budget_value=0.),
                                observed, .5, 0., 0., [], 0, 0, 0.)
        self.assertEqual(len(zeroed), train.NOBS + 1)
        self.assertEqual(zeroed[-1], 0.)
        self.assertEqual(zeroed[:-1], plain)


class PlanningBudgetModelTests(unittest.TestCase):
    def test_extension_preserves_weights_and_adam_prefixes(self):
        import compare_spatial as comp
        torch.manual_seed(7)
        source = train.PolicyNet2()
        optimizer = torch.optim.Adam(source.parameters())
        sum(p.sum() for p in source.parameters()).backward()
        optimizer.step()
        net, adam = comp.extend_private_model(source, optimizer.state_dict(), planning_budget=True)
        self.assertEqual(net.gru.input_size, source.gru.input_size + 1)
        weights = source.state_dict()
        extended = net.state_dict()
        self.assertEqual(extended['gru.weight_ih_l0'].shape[1],
                         weights['gru.weight_ih_l0'].shape[1] + 1)
        torch.testing.assert_close(extended['gru.weight_ih_l0'][:, :-1], weights['gru.weight_ih_l0'])
        self.assertFalse(bool(extended['gru.weight_ih_l0'][:, -1].any()))
        for name in weights:
            if name != 'gru.weight_ih_l0':
                torch.testing.assert_close(extended[name], weights[name])
        reference = optimizer.state_dict()
        self.assertEqual([index for group in adam['param_groups'] for index in group['params']],
                         [index for group in reference['param_groups'] for index in group['params']])
        gru_index = list(source.state_dict()).index('gru.weight_ih_l0')
        for index, old_state in reference['state'].items():
            new_state = adam['state'][index]
            self.assertEqual(sorted(new_state), sorted(old_state))
            for name, moment in old_state.items():
                padded = new_state[name]
                if name == 'step':
                    self.assertEqual(int(padded), int(moment))
                elif index == gru_index:
                    self.assertEqual(padded.shape, torch.Size([moment.shape[0], moment.shape[1] + 1]))
                    torch.testing.assert_close(padded[:, :-1], moment)
                    self.assertFalse(bool(padded[:, -1].any()))
                else:
                    torch.testing.assert_close(padded, moment)
        net(torch.zeros(1, 1, net.gru.input_size))

    def test_schema_versions_and_single_contract(self):
        schema = train.checkpoint_schema(planning_budget=True)
        self.assertEqual(schema['version'], 8)
        self.assertEqual(schema['inputs'], train.INPUT_LABELS + [train.PLANNING_BUDGET_LABEL])
        self.assertEqual(len(schema['inputs']), train.NOBS + 1)
        default = train.checkpoint_schema()
        self.assertEqual(default['version'], 4)
        self.assertEqual(len(default['inputs']), train.NOBS)
        self.assertEqual(train.checkpoint_schema()['version'],
                         train.checkpoint_schema(shelter_occupancy=False)['version'])
        with self.assertRaises(ValueError):
            train.checkpoint_schema(planning_budget=True, shelter_geometry=True)
        with self.assertRaises(ValueError):
            train.checkpoint_schema(planning_budget=True, opening_timing=True)


class PlanningBudgetEpisodeWiringTests(unittest.TestCase):
    def test_pair_changes_only_the_budget_option(self):
        import compare_spatial as comp
        with patch.object(comp.operator, 'owned_copy'), patch.object(comp.zar_boot, 'boot'), \
                patch.object(comp.zar_boot, 'stop'), patch.object(train, 'run_episode') as run:
            run.return_value = {'log_started': 123}
            settings_list = []
            for arm in comp.PLANNING_BUDGET_INPUT:
                result = comp.episode(('inst13', arm, {}, 123, 'test', True, None),
                                      audit_signal=True)
                self.assertEqual(result, run.return_value)
                self.assertIs(run.call_args.kwargs['policy_factory'].func, train.PolicyNet2)
                self.assertEqual(run.call_args.kwargs['policy_factory'].keywords,
                                 {'planning_budget': True})
                settings = run.call_args.args[0][4].copy()
                self.assertEqual(settings.pop('planning_budget_input'),
                                 comp.PLANNING_BUDGET_INPUT[arm])
                self.assertEqual(settings.pop('experiment_signal'), 'receipts')
                for untouched in ('fixed_speed', 'fixed_clock', 'planning_zone_audit',
                                  'ready_coverage_credit', 'planning_tool_temperature',
                                  'battle_boundary_filter', 'occupied_breach_cost',
                                  'shelter_geometry_input', 'settle_cast_target',
                                  'gate_receipts'):
                    self.assertNotIn(untouched, settings)
                self.assertEqual(settings, {'start_kind': 'fresh', 'seed': 123,
                                            'missile_credit': True})
                settings_list.append(settings)
            self.assertEqual(*settings_list)

    def test_archive_hook_runs_before_stop_for_bound_sessions(self):
        import compare_spatial as comp
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_dir = root / 'inst13'
            (copy_dir / 'logs').mkdir(parents=True)
            (copy_dir / 'logs' / 'session-a.jsonl').write_text(
                json.dumps({'wall': 123}) + '\n{"sequence": 1}\n', encoding='utf-8')
            with patch.object(comp.operator, 'owned_copy', return_value=copy_dir), \
                    patch.object(comp.zar_boot, 'boot'), \
                    patch.object(comp.zar_boot, 'stop') as stop, \
                    patch.object(train, 'run_episode') as run:
                run.return_value = {'log_started': 123}
                result = comp.episode(('inst13', 'budget_countdown', {}, 123, 'tag/1', True,
                                       root / 'run'), audit_signal=True)
                self.assertEqual(result['native_session']['status'], 'archived')
                self.assertTrue((root / 'native-sessions').exists() or
                                (root / 'run' / 'native-sessions' / 'tag_1-inst13.jsonl').exists())
                stop.assert_called_once()


class NativeSessionArchiveTests(unittest.TestCase):
    def setUp(self):
        import compare_spatial as comp
        self.comp = comp
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.copy_dir = self.root / 'inst13'
        (self.copy_dir / 'logs').mkdir(parents=True)
        self.run_dir = self.root / 'run'

    def write(self, wall=123, name='session-a.jsonl'):
        (self.copy_dir / 'logs' / name).write_text(
            json.dumps({'wall': wall}) + '\n{"sequence": 1}\n', encoding='utf-8')

    def archive(self, started=123, episode='tag/1/budget_countdown/inst13'):
        return self.comp.archive_native_session(self.copy_dir, self.run_dir, episode, 'inst13',
                                                started)

    def test_archives_matching_header_and_never_overwrites(self):
        self.write(wall=123)
        status = self.archive()
        archived = self.run_dir / 'native-sessions' / 'tag_1_budget_countdown_inst13-inst13.jsonl'
        self.assertEqual(status['status'], 'archived')
        self.assertEqual(json.loads(archived.read_text(encoding='utf-8').splitlines()[0])['wall'],
                         123)
        self.assertEqual(json.loads((self.copy_dir / 'logs' / 'session-a.jsonl')
                                    .read_text(encoding='utf-8').splitlines()[0])['wall'], 123)
        second = self.archive()
        self.assertEqual(second['status'], 'collision')
        self.assertEqual(json.loads(archived.read_text(encoding='utf-8').splitlines()[0])['wall'],
                         123)
        self.assertEqual(json.loads((self.copy_dir / 'logs' / 'session-a.jsonl')
                                    .read_text(encoding='utf-8').splitlines()[0])['wall'], 123)

    def test_header_mismatch_is_reported_under_an_explicit_suffix(self):
        self.write(wall=999)
        status = self.archive(started=123)
        self.assertEqual(status['status'], 'header-mismatch')
        self.assertEqual(status['header_wall'], 999)
        self.assertEqual(status['expected_wall'], 123)
        self.assertTrue((self.run_dir / 'native-sessions' /
                         'tag_1_budget_countdown_inst13-inst13-header-mismatch.jsonl').exists())
        self.assertTrue((self.copy_dir / 'logs' / 'session-a.jsonl').exists())

    def test_missing_or_ambiguous_logs_are_reported(self):
        self.assertEqual(self.archive()['status'], 'missing-or-ambiguous')
        self.write(name='session-a.jsonl')
        self.write(name='session-b.jsonl')
        status = self.archive()
        self.assertEqual(status['status'], 'missing-or-ambiguous')
        self.assertEqual(status['files'], ['session-a.jsonl', 'session-b.jsonl'])

    def test_rows_without_a_started_session_are_skipped(self):
        self.write()
        self.assertEqual(self.comp.archive_native_session(self.copy_dir, self.run_dir, 'e',
                                                          'inst13', None)['status'], 'no-session')
        self.assertTrue((self.copy_dir / 'logs' / 'session-a.jsonl').exists())


class PlanningBudgetSignalTests(unittest.TestCase):
    def test_summarizer_sees_the_countdown_treatment_alone(self):
        import compare_spatial as comp
        from experiment_signal import summarize_signal
        config = dict(comparison='planning_budget',
                      planning_budget_input_by_arm=dict(comp.PLANNING_BUDGET_INPUT))
        rows = [dict(arm='budget_control', phase='train', start_kind='fresh', outbreak_seed=1,
                     experiment_signal=dict(receipts=dict(planning_budget_input=False))),
                dict(arm='budget_countdown', phase='train', start_kind='fresh', outbreak_seed=2,
                     experiment_signal=dict(receipts=dict(planning_budget_input=True))),
                dict(arm='budget_countdown', phase='train', start_kind='fresh', outbreak_seed=3,
                     experiment_signal=dict(receipts=dict(planning_budget_input=False)))]
        evaluation = {arm: dict(complete=6) for arm in comp.PLANNING_BUDGET_INPUT}
        signal = summarize_signal(rows, config, tuple(comp.PLANNING_BUDGET_INPUT), evaluation,
                                  start_round=0)
        self.assertEqual(signal['comparison'], 'planning_budget')
        self.assertEqual(signal['arms']['budget_control']['mechanism_episodes'], 0)
        self.assertEqual(signal['arms']['budget_control']['treatment_episodes'], 0)
        self.assertEqual(signal['arms']['budget_countdown']['mechanism_episodes'], 1)
        self.assertEqual(signal['arms']['budget_countdown']['treatment_episodes'], 1)
        self.assertEqual(signal['advisory'], 'treatment_observed')



class PlanningBudgetSummaryProjectionTests(unittest.TestCase):
    '''The real summary projection reads the payload from experiment_signal as the
    producer journals it, retaining both arms' values through serialization.'''

    CONTROL_BINS = {'early': {'decisions': 12, 'ready_probability_mean': 0.0297837119239072,
                              'ready_choices': 1},
                    'mid': {'decisions': 0, 'ready_probability_mean': None, 'ready_choices': 0},
                    'late': {'decisions': 0, 'ready_probability_mean': None, 'ready_choices': 0}}
    COUNTDOWN_BINS = {'early': {'decisions': 14, 'ready_probability_mean': 0.012541370932012796,
                                'ready_choices': 0},
                      'mid': {'decisions': 3, 'ready_probability_mean': 0.041015625,
                              'ready_choices': 1},
                      'late': {'decisions': 0, 'ready_probability_mean': None, 'ready_choices': 0}}
    CONTROL_OBSERVATIONS = {'ready': {'wall_segments': 0, 'gates': 0, 'closed_zones': 0,
                                      'corridors': 0, 'holds': 0, 'other_units': {},
                                      'civilian_zone_fraction': 0.0, 'money': 2705.39990234375},
                            'timeout': None}
    COUNTDOWN_OBSERVATIONS = {'ready': None,
                              'timeout': {'wall_segments': 54, 'gates': 1, 'closed_zones': 1,
                                          'corridors': 0, 'holds': 0, 'other_units': {},
                                          'money': 1390.28125,
                                          'civilian_zone_fraction': 0.25448292802751166,
                                          'embedded_defenses': {}}}
    NATIVE = {'status': 'archived', 'header_wall': 1795251990242, 'expected_wall': 1795251990242}

    @classmethod
    def _episode(cls, job):
        countdown = job[1] == 'budget_countdown'
        row = dict(end='timeout' if countdown else 'aborted',
                   saved_frac=None if countdown else .0999, bootstrap=0.0,
                   win=False, advance=False, sim=0.0 if countdown else 33.799827575683594,
                   t=15.67233629990369 if countdown else 100.65187820000574,
                   board_id='c6f9fa75237ad12a',
                   log_started=1795252212157 if countdown else 1795251990242,
                   start_kind='fresh', outbreak=None if countdown else {'seed': 836399025},
                   us=[], obs=[], battle_actions={}, reward_components={},
                   ready_choices=None, ready_stats=None, shelter=None,
                   experiment_signal=dict(
                       receipts=dict(planning_budget_input=countdown),
                       planning_budget_bins=deepcopy(cls.COUNTDOWN_BINS if countdown
                                                     else cls.CONTROL_BINS),
                       budget_observations=deepcopy(cls.COUNTDOWN_OBSERVATIONS if countdown
                                                    else cls.CONTROL_OBSERVATIONS)))
        if not countdown:
            row['native_session'] = dict(cls.NATIVE)
        return row

    def test_projection_retains_both_arms_through_the_serialized_summary(self):
        import compare_spatial as comp
        torch = train.torch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'analysis').mkdir()
            net = train.PolicyNet2()
            adam = torch.optim.Adam(train.PolicyNet2().parameters(), lr=3e-4).state_dict()
            with patch('sys.argv', ['compare_spatial', '--copies', 'inst13', 'inst14',
                                    '--eval-copies', 'inst17', 'inst18', '--seed', '336571',
                                    '--train-rounds', '1', '--eval-rounds', '2',
                                    '--compare-planning-budget', '--warm-start', 'paired.pt',
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
                    patch.object(comp.trainer, 'ppo_update', lambda *args, **kwargs: {}), \
                    patch.object(comp, 'retain_natural_win', lambda *args: -1.), \
                    patch.object(comp, 'collect_pairs',
                                 side_effect=lambda pool, jobs, run, **kwargs:
                                 [self._episode(job) for job in jobs]):
                comp.main()
            run, = (root / 'analysis').iterdir()
            self.assertTrue(run.name.startswith('coverage-planning-budget-'))
            rows = [json.loads(line)
                    for line in (run / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 6)
            for arm, bins, observations, receipt in (
                    ('budget_control', self.CONTROL_BINS, self.CONTROL_OBSERVATIONS, False),
                    ('budget_countdown', self.COUNTDOWN_BINS, self.COUNTDOWN_OBSERVATIONS, True)):
                chosen = [row for row in rows if row['arm'] == arm]
                self.assertEqual(len(chosen), 3)
                self.assertEqual({row['phase'] for row in chosen}, {'train', 'evaluation'})
                self.assertEqual({row['end'] for row in chosen},
                                 {'timeout'} if receipt else {'aborted'})
                for row in chosen:
                    self.assertEqual(row['planning_budget_bins'], bins)
                    self.assertEqual(row['budget_observations'], observations)
                    self.assertIs(row['experiment_signal']['receipts']['planning_budget_input'],
                                  receipt)
                    self.assertEqual(row['native_session'],
                                     None if receipt else self.NATIVE)



class PlanningCreditAuditTests(unittest.TestCase):
    '''The audit flag journals per-decision planning credit before any optimizer step.'''

    @staticmethod
    def _row(training=True, budget=False):
        import numpy as np
        mu = np.ones(train.NU, dtype=np.float32)
        mc = np.ones(train.NC, dtype=np.float32)
        row = dict(pid=43001, board_id='c6f9fa75237ad12a', log_started=1795251990242,
                   obs=[[1. if index == train.PLANNING_INDEX else 0. for index in range(train.NOBS + 1)]
                        for _ in range(3)],
                   us=[2, 5, 1 if training else 2], cs=[0, 0, 0],
                   ulps=[-1., -1., -1.], clps=[-1., -1., -1.],
                   masks=[(mu.copy(), mc.copy()) for _ in range(3)],
                   rews=[-0.01, 0.0, -0.02], sim_elapsed=[0.1, 0.1, 0.1],
                   bootstrap=0.25, start_kind='fresh',
                   outbreak={'seed': 836399025} if training else None,
                   t=30.0, win=False, advance=False, battle_actions={},
                   reward_components={}, ready_choices=None, ready_stats=None, shelter=None,
                   experiment_signal=dict(receipts=dict(planning_budget_input=budget)))
        if training:
            row.update(end='aborted', saved_frac=.0999, timeout_phase=None, sim=30.0)
        else:
            row.update(end='timeout', saved_frac=None, timeout_phase='planning', sim=0.0)
        return row

    @staticmethod
    def _wide_critic():
        net = train.PolicyNet2(planning_budget=True)
        state = net.state_dict()
        state['val.weight'] = state['val.weight'] * 1e6
        state['val.bias'] = state['val.bias'] * 1e6
        net.load_state_dict(state)
        return net

    @staticmethod
    def _critic_values(net, row):
        import numpy as np
        X = train.torch.tensor(np.array(row['obs'], dtype=np.float32)).unsqueeze(0)
        with train.torch.no_grad():
            return net(X)[2].squeeze(0).numpy()

    def test_journal_uses_true_critic_values_without_optimizer_step(self):
        torch = train.torch
        net = self._wide_critic()
        rows = [self._row(), self._row(training=False)]
        expected = [self._critic_values(net, row) for row in rows]
        original, calls = torch.Tensor.numpy, []
        def spy(self):
            calls.append(self)
            return original(self)
        with patch.object(train.torch.Tensor, 'numpy', spy):
            torch.manual_seed(7)
            summary = train.ppo_update(net, rows, None, epochs=0, audit_phases=True)
            self.assertEqual(len(calls), 4 * len(rows))  # vals + alladv + raw adv/ret per episode
            calls.clear()
            summary_off = train.ppo_update(net, rows, None, epochs=0)
        self.assertEqual(len(calls), 2 * len(rows))  # audit-off performs no journaling reads
        self.assertNotIn('planning_credit', summary_off)
        credit = summary['planning_credit']
        self.assertTrue(math.isfinite(credit['pooled_mean']))
        self.assertTrue(math.isfinite(credit['pooled_std']))
        self.assertGreater(credit['pooled_std'], 0.)
        self.assertEqual(len(credit['episodes']), 2)
        for episode, row, values in zip(credit['episodes'], rows, expected):
            self.assertEqual((episode['pid'], episode['board_id'], episode['log_started']),
                             (43001, 'c6f9fa75237ad12a', 1795251990242))
            self.assertEqual((episode['end'], episode['bootstrap']), (row['end'], 0.25))
            records = episode['decisions']
            self.assertEqual([record['decision'] for record in records], [0, 1, 2])
            self.assertEqual([record['tool'] for record in records], row['us'])
            self.assertEqual([record['ready'] for record in records],
                             [False, False, row['us'][2] == 1])
            self.assertEqual([record['reward'] for record in records], row['rews'])
            self.assertAlmostEqual(records[2]['raw_return'], records[2]['reward'] + 0.25, places=1)
            # Journaled returns are the float32 tensors PPO consumed, so the suffix
            # identity G_i = reward_i + G_{i+1} holds only to tensor precision.
            self.assertAlmostEqual(records[0]['raw_return'] - records[1]['raw_return'],
                                   records[0]['reward'], places=1)
            self.assertAlmostEqual(records[1]['raw_return'] - records[2]['raw_return'],
                                   records[1]['reward'], places=1)
            for record in records:
                self.assertEqual(record['value'], float(values[record['decision']]))
                # The scaled critic cancels float32 bits inside gae, so exact suffix
                # returns derived from rewards alone miss the float32 returns PPO used;
                # the journaled value must still equal the true pre-update critic output.
                exact = math.fsum(row['rews'][record['decision']:]) + 0.25
                self.assertGreater(abs(record['raw_return'] - exact), 1e-5)
                self.assertAlmostEqual(
                    record['normalized_advantage'],
                    (record['raw_advantage'] - credit['pooled_mean']) / credit['pooled_std'],
                    delta=max(1e-3, abs(record['normalized_advantage']) * 1e-5))
                self.assertEqual(record['phase_weight'], 1.)

    def test_writers_serialize_credit_on_native_shaped_rows(self):
        import compare_spatial as comp
        torch = train.torch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'analysis').mkdir()
            net = train.PolicyNet2()
            adam = torch.optim.Adam(train.PolicyNet2().parameters(), lr=3e-4).state_dict()
            with patch('sys.argv', ['compare_spatial', '--copies', 'inst13', 'inst14',
                                    '--seed', '336571', '--train-rounds', '1',
                                    '--eval-rounds', '2', '--audit-phase-gradients',
                                    '--compare-planning-budget', '--warm-start', 'paired.pt',
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
                    patch.object(comp, 'retain_natural_win', lambda *args: -1.), \
                    patch.object(comp, 'collect_pairs',
                                 side_effect=lambda pool, jobs, run, **kwargs:
                                 [self._row(job[5], job[1] == 'budget_countdown') for job in jobs]):
                torch.manual_seed(5)
                comp.main()
            run, = (root / 'analysis').iterdir()
            training_lines = [json.loads(line)
                              for line in (run / 'phase-gradients.jsonl')
                              .read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(training_lines), 2)
            for line in training_lines:
                credit = line['planning_credit']
                episode = credit['episodes'][0]
                self.assertEqual((episode['end'], episode['bootstrap']), ('aborted', 0.25))
                self.assertEqual((episode['board_id'], episode['log_started']),
                                 ('c6f9fa75237ad12a', 1795251990242))
                records = episode['decisions']
                self.assertEqual([record['ready'] for record in records], [False, False, True])
                self.assertEqual([record['reward'] for record in records], [-0.01, 0.0, -0.02])
                self.assertAlmostEqual(records[2]['raw_return'], records[2]['reward'] + 0.25,
                                       places=1)
                self.assertAlmostEqual(records[0]['raw_return'] - records[1]['raw_return'],
                                       records[0]['reward'], places=1)
                for record in records:
                    self.assertAlmostEqual(record['raw_advantage'],
                                           record['raw_return'] - record['value'], places=4)
                    self.assertAlmostEqual(
                        record['normalized_advantage'],
                        (record['raw_advantage'] - credit['pooled_mean']) / credit['pooled_std'],
                        places=3)
                    self.assertEqual(record['phase_weight'], 1.)
            frozen_lines = [json.loads(line)
                            for line in (run / 'frozen-replay.jsonl')
                            .read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(frozen_lines), 4)
            for line in frozen_lines:
                episode = line['planning_credit']['episodes'][0]
                self.assertEqual((episode['end'], episode['bootstrap']), ('timeout', 0.25))
                self.assertEqual([record['ready'] for record in episode['decisions']],
                                 [False, False, False])
                self.assertAlmostEqual(episode['decisions'][2]['raw_return'],
                                       episode['decisions'][2]['reward'] + 0.25, places=1)


if __name__ == '__main__':
    unittest.main()
