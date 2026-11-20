"""Advisory evidence for private PPO comparisons. Never controls a rollout."""
import math

_DESIGN = {
    'occupied_breach_cost': ('occupied_exposure', 'occupied_breach'),
    'shelter_defense': ('occupied_exposure', 'occupied_breach'),
    'ready_coverage': ('occupied_ready', 'ready_coverage'),
    'ready_shortfall': ('below_ready_target', 'ready_shortfall'),
    'missile_civilian_credit': ('missile_civilian_loss', 'missile_civilian_loss'),
}
_SAMPLING = {'zone_exploration': 'zone_cells', 'planning_exploration': 'planning_tools'}
_OTHER = {'planning_entropy': 'planning_entropy',
          'phase_balance': 'phase_balance', 'spatial': 'spatial_cells'}


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
    primary = {}
    for arm in arms:
        samples = [r for r in rows if r['arm'] == arm and r['phase'] == 'train']
        evidence = [r.get('experiment_signal') or {} for r in samples]
        seen = set()
        eligible = receipts = changed = components = unknown = 0
        variation = 0.
        for row, signal in zip(samples, evidence):
            seed = row.get('outbreak_seed')
            if design in _DESIGN:
                key, reward = _DESIGN[design]
                observed = (signal.get('receipts') or {}).get(key)
                occurrence = observed is True
                component = (signal.get('reward_components') or {}).get(reward)
                applied = occurrence and type(component) in (int, float) and math.isfinite(component) and component != 0.
                components += int(applied)
                difference = applied and arm != arms[0]
            elif design in _SAMPLING:
                distribution = (signal.get('distributions') or {}).get(_SAMPLING[design])
                observed = None if distribution is None else distribution['choices'] > 0
                occurrence = observed is True
                difference = bool(distribution and distribution['changed'])
                variation += distribution['variation'] if distribution else 0.
            else:
                observed = (signal.get('receipts') or {}).get(_OTHER[design])
                occurrence = observed is True
                difference = occurrence and (
                    design == 'planning_entropy' and config['planning_tool_entropy_bonus_by_arm'][arm] > 0
                    or design == 'phase_balance' and arm == 'balanced'
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
                            treatment_episodes=changed, sampling_variation_sum=variation)
    # Advisory only. A sparse event can become observable in later rounds.
    has_change = any(a['treatment_episodes'] for a in primary.values())
    has_mechanism = any(a['mechanism_episodes'] for a in primary.values())
    min_seen = min(a['distinct_observed_outbreaks'] for a in primary.values())
    unknown = sum(a['unknown_episodes'] for a in primary.values())
    state = signal_state(min_seen, unknown, has_mechanism, has_change, minimum)
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
