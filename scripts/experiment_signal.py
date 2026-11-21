"""Advisory evidence for private PPO comparisons. Never controls a rollout."""
import math

_DESIGN = {
    'occupied_breach_cost': ('occupied_exposure', 'occupied_breach'),
    'shelter_defense': ('occupied_exposure', 'occupied_breach'),
    'shelter_duration': ('occupied_duration', 'shelter_duration'),
    'ready_coverage': ('occupied_ready', 'ready_coverage'),
    'ready_shortfall': ('below_ready_target', 'ready_shortfall'),
    'ready_delay': ('legal_ready_declined', 'ready_delay'),
    'missile_civilian_credit': ('missile_civilian_loss', 'missile_civilian_loss'),
}
_SAMPLING = {'zone_exploration': 'zone_cells', 'planning_exploration': 'planning_tools',
             'battle_exploration': 'battle_tools'}
_OTHER = {'planning_entropy': 'planning_entropy',
          'phase_balance': 'phase_balance', 'spatial': 'spatial_cells',
          'shelter_input': 'shelter_occupancy_input',
          'shelter_geometry': 'shelter_geometry_input',
          'battle_boundary': 'battle_boundary',
          'opening_timing': 'opening_timing_input',
          'recurrent_capacity': 'recurrent_capacity',
          'preparation_credit': 'preparation_credit',
          'target_settle': 'snapped_cast'}


def reward_coefficients(config, component, arms):
    if component == 'missile_civilian_loss':
        return {arms[0]: 0., arms[1]: config['learning']['missile_civilian_cost']}
    key = {'occupied_breach': 'occupied_breach_cost_by_arm',
           'shelter_duration': 'shelter_duration_rate_by_arm',
           'ready_coverage': 'ready_coverage_credit_by_arm',
           'ready_shortfall': 'ready_shortfall_cost_by_arm',
           'ready_delay': 'ready_delay_cost_by_arm'}[component]
    return config[key]


def signal_state(sampled_seeds, unknown, receipt_games, changed_games, minimum):
    if changed_games:
        return 'treatment_observed'
    if sampled_seeds < minimum:
        return 'collecting'
    if unknown:
        return 'incomplete_receipts'
    return 'mechanism_without_treatment' if receipt_games else 'unexercised'


def summarize_signal(rows, config, arms, evaluation, *, start_round, minimum=4):
    """Count training receipts separately from frozen official outcomes."""
    design = config.get('comparison', 'spatial')
    arms = tuple(arms)
    coefficients = reward_coefficients(config, _DESIGN[design][1], arms) if design in _DESIGN else {}
    primary = {}
    for arm in arms:
        samples = [r for r in rows if r['arm'] == arm and r['phase'] == 'train']
        evidence = [r.get('experiment_signal') or {} for r in samples]
        seen = set()
        eligible = receipts = changed = components = unknown = unchecked = mismatches = 0
        variation = delta_sum = 0.
        for row, signal in zip(samples, evidence):
            seed = row.get('outbreak_seed')
            if design in _DESIGN:
                key, reward = _DESIGN[design]
                observed = (signal.get('receipts') or {}).get(key)
                occurrence = observed is True
                component = (signal.get('reward_components') or {}).get(reward)
                applied = occurrence and type(component) in (int, float) and math.isfinite(component) and component != 0.
                components += int(applied)
                basis = (signal.get('reward_bases') or {}).get(reward)
                difference = False
                if observed is not None:
                    if any(type(value) not in (int, float) or not math.isfinite(value)
                           for value in (basis, component)):
                        unchecked += 1
                    elif not math.isclose(component, coefficients[arm] * basis, rel_tol=1e-6, abs_tol=1e-9):
                        mismatches += 1
                    else:
                        reference = coefficients[arms[0]] * basis
                        difference = occurrence and not math.isclose(component, reference, rel_tol=1e-6, abs_tol=1e-9)
                        if difference:
                            delta_sum += component - reference
            elif design in _SAMPLING:
                distribution = (signal.get('distributions') or {}).get(_SAMPLING[design])
                observed = None if distribution is None else distribution['choices'] > 0
                occurrence = observed is True
                difference = bool(distribution and distribution['changed'])
                variation += distribution['variation'] if distribution else 0.
            else:
                receipts_seen = signal.get('receipts') or {}
                observed = receipts_seen.get(_OTHER[design])
                if design == 'recurrent_capacity':
                    if observed != config['recurrent_width_by_arm'][arm]:
                        observed = None
                    occurrence = observed is not None
                else:
                    occurrence = observed is True
                difference = occurrence and (
                    design == 'recurrent_capacity' and observed != config['recurrent_width_by_arm'][arms[0]]
                    or design == 'preparation_credit' and config['preparation_credit_by_arm'][arm]
                    or design == 'planning_entropy' and config['planning_tool_entropy_bonus_by_arm'][arm] > 0
                    or design == 'phase_balance' and arm == 'balanced'
                    or design == 'shelter_input' and config['shelter_input_by_arm'][arm]
                    or design == 'shelter_geometry' and config['shelter_geometry_by_arm'][arm]
                    or design == 'battle_boundary' and config['battle_boundary_by_arm'][arm]
                    or design == 'opening_timing' and config['opening_timing_by_arm'][arm]
                    or design == 'target_settle' and receipts_seen.get('target_pointer_settled') is True
                )
            if observed is None:
                unknown += 1
                continue
            eligible += 1
            if row.get('start_kind') == 'fresh' and type(seed) is int:
                seen.add(seed)
            receipts += int(occurrence)
            changed += int(difference)
        primary[arm] = dict(episodes=len(samples), observed_episodes=eligible,
                            distinct_observed_outbreaks=len(seen), unknown_episodes=unknown,
                            mechanism_episodes=receipts, reward_component_episodes=components,
                            treatment_episodes=changed, sampling_variation_sum=variation,
                            reward_difference_sum=delta_sum, unchecked_reward_episodes=unchecked,
                            reward_mismatch_episodes=mismatches)
    # Advisory only. A sparse event can become observable in later rounds.
    has_change = any(a['treatment_episodes'] for a in primary.values())
    has_mechanism = any(a['mechanism_episodes'] for a in primary.values())
    min_seen = min(a['distinct_observed_outbreaks'] for a in primary.values())
    unknown = sum(a['unknown_episodes'] + a['unchecked_reward_episodes'] for a in primary.values())
    state = signal_state(min_seen, unknown, has_mechanism, has_change, minimum)
    if any(a['reward_mismatch_episodes'] for a in primary.values()):
        state = 'unexpected_reward_components'
    if design == 'spatial' and has_mechanism:
        state = 'architecture_exercised_distribution_difference_unmeasured'
    natural = [result['complete'] for result in evaluation.values()]
    outcome = ('insufficient_independent_natural_finishes' if min(natural) < minimum else
               'descriptive_natural_finishes' if min(natural) < 30 else 'full_sized_cohorts')
    return dict(schema=1, comparison=design, first_recorded_round=start_round,
                outcome_evidence=outcome,
                advisory=state, advisory_minimum_distinct_observed_outbreaks_per_arm=minimum,
                configured_differences={k: v for k, v in config.items() if k.endswith('_by_arm')},
                arms=primary, frozen_outcomes=evaluation)
