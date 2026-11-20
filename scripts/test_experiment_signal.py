import unittest

from experiment_signal import summarize_signal
import nn_play2 as trainer


class SignalTests(unittest.TestCase):
    def config(self, name):
        return dict(comparison=name, learning={'missile_civilian_cost': 1.},
                    planning_tool_entropy_bonus_by_arm={'reference': 0., 'candidate': .045},
                    occupied_breach_cost_by_arm={'reference': .10, 'candidate': .30},
                    ready_coverage_credit_by_arm={'reference': 0., 'candidate': .30},
                    ready_shortfall_cost_by_arm={'reference': 0., 'candidate': .15},
                    ready_delay_cost_by_arm={'reference': 0., 'candidate': .002})

    def report(self, kind, rows, *, complete=0):
        arms = ('reference', 'candidate')
        frozen = {arm: dict(complete=complete, passed=False) for arm in arms}
        return summarize_signal(rows, self.config(kind), arms, frozen, start_round=0)

    def rows(self, receipts, rewards, *, unique=True):
        return [dict(arm=arm, phase='train', start_kind='fresh', outbreak_seed=i if unique else 1,
                     experiment_signal=dict(receipts=receipts, reward_components=rewards,
                                            reward_bases=dict.fromkeys(rewards, 0.)))
                for arm in ('reference', 'candidate') for i in range(4)]

    def test_empty_shelters_and_zero_breaches_are_unexercised(self):
        for kind, receipt, component in (
                ('occupied_breach_cost', 'occupied_exposure', 'occupied_breach'),
                ('ready_coverage', 'occupied_ready', 'ready_coverage')):
            report = self.report(kind, self.rows({receipt: False}, {component: 0.}))
            self.assertEqual(report['advisory'], 'unexercised')
            self.assertEqual(report['arms']['candidate']['mechanism_episodes'], 0)
            self.assertEqual(report['outcome_evidence'], 'insufficient_independent_natural_finishes')

    def test_unknown_and_repeated_outbreaks_cannot_establish_absence(self):
        rows = self.rows({'occupied_ready': False}, {'ready_coverage': 0.}, unique=False)
        self.assertEqual(self.report('ready_coverage', rows)['advisory'], 'collecting')
        rows = self.rows({'occupied_ready': False}, {'ready_coverage': 0.})
        rows.append(dict(rows[-1], experiment_signal=None))
        self.assertEqual(self.report('ready_coverage', rows)['advisory'], 'incomplete_receipts')

    def test_reference_only_breach_does_not_verify_stronger_treatment(self):
        rows = self.rows({'occupied_exposure': False}, {'occupied_breach': 0.})
        rows[0]['experiment_signal'] = dict(receipts={'occupied_exposure': True},
                                            reward_components={'occupied_breach': -.01},
                                            reward_bases={'occupied_breach': -.1})
        report = self.report('shelter_defense', rows, complete=4)
        self.assertEqual(report['advisory'], 'mechanism_without_treatment')
        self.assertEqual(report['arms']['reference']['reward_component_episodes'], 1)
        self.assertEqual(report['outcome_evidence'], 'descriptive_natural_finishes')

    def test_one_rare_native_reward_is_observed_before_gate_threshold(self):
        rows = self.rows({'below_ready_target': True}, {'ready_shortfall': 0.})[-1:]
        rows[0]['experiment_signal']['reward_components'] = {'ready_shortfall': -.15}
        rows[0]['experiment_signal']['reward_bases'] = {'ready_shortfall': -1.}
        report = self.report('ready_shortfall', rows)
        self.assertEqual(report['advisory'], 'treatment_observed')
        self.assertEqual(report['arms']['candidate']['treatment_episodes'], 1)
        self.assertEqual(report['outcome_evidence'], 'insufficient_independent_natural_finishes')

    def test_stronger_breach_cost_detects_a_reference_rate_on_candidate(self):
        rows = self.rows({'occupied_exposure': True}, {'occupied_breach': -.01})[-1:]
        rows[0]['experiment_signal']['reward_bases'] = {'occupied_breach': -.1}
        report = self.report('occupied_breach_cost', rows)
        self.assertEqual(report['advisory'], 'unexpected_reward_components')
        self.assertEqual(report['arms']['candidate']['treatment_episodes'], 0)
        self.assertEqual(report['arms']['candidate']['reward_mismatch_episodes'], 1)

        rows[0]['experiment_signal']['reward_components'] = {'occupied_breach': -.03}
        report = self.report('occupied_breach_cost', rows)
        self.assertEqual(report['advisory'], 'treatment_observed')
        self.assertAlmostEqual(report['arms']['candidate']['reward_difference_sum'], -.02)

    def test_same_state_distribution_comparison_detects_real_tempering(self):
        t = trainer.torch
        mask = [1, 1, 0]
        signal = dict(choices=0, changed=0, variation=0.)
        for logits in (t.tensor([2., 2., 50.]), t.tensor([2., 0., 50.])):
            trainer.record_distribution_signal(
                signal, trainer.tool_distribution(logits, mask, temperature=1.35),
                trainer.tool_distribution(logits, mask))
        self.assertEqual(signal['choices'], 2)
        self.assertEqual(signal['changed'], 1)
        self.assertGreater(signal['variation'], 0.)
        row = dict(arm='candidate', phase='train', start_kind='fresh', outbreak_seed=42,
                   experiment_signal=dict(distributions={'zone_cells': signal}))
        self.assertEqual(self.report('zone_exploration', [row])['advisory'], 'treatment_observed')

    def test_ready_delay_checks_the_reward_against_the_number_of_declines(self):
        rows = self.rows({'legal_ready_declined': True}, {'ready_delay': -.04})[-1:]
        rows[0]['experiment_signal']['reward_bases'] = {'ready_delay': -20}
        report = self.report('ready_delay', rows)
        self.assertEqual(report['advisory'], 'treatment_observed')
        self.assertAlmostEqual(report['arms']['candidate']['reward_difference_sum'], -.04)

    def test_target_settle_requires_an_executed_snapped_cast_with_the_frame_wait(self):
        rows = self.rows({'snapped_cast': True, 'target_pointer_settled': False}, {})
        self.assertEqual(self.report('target_settle', rows)['advisory'], 'mechanism_without_treatment')
        rows[-1]['experiment_signal']['receipts'] = {'snapped_cast': True, 'target_pointer_settled': True}
        report = self.report('target_settle', rows)
        self.assertEqual(report['advisory'], 'treatment_observed')
        self.assertEqual(report['arms']['candidate']['treatment_episodes'], 1)

    def test_spatial_head_activity_does_not_claim_measured_ab_difference(self):
        report = self.report('spatial', self.rows({'spatial_cells': True}, {}))
        self.assertEqual(report['advisory'], 'architecture_exercised_distribution_difference_unmeasured')
        self.assertEqual(report['arms']['candidate']['treatment_episodes'], 0)
