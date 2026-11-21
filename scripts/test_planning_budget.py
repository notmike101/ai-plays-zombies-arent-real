"""No live PIDs: planning budget feature edges, extend prefix, bins, archive, signal."""
import json
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


if __name__ == '__main__':
    unittest.main()
