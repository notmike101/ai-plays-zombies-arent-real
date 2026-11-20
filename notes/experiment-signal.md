# PPO comparison signal coverage

Private comparison runs write `signal-coverage.json` after each completed
training checkpoint and after frozen evaluation. Older run files are
preserved. The report covers rows collected by the current invocation.
`first_recorded_round` identifies a resumed invocation with partial history.

## Three questions to ask

1. **Did the game or learner exercise the mechanism?** For the breach
   penalty, use civilians exposed at a native occupied breach. For READY
   coverage and shortfall, use the session-bound coverage observation matched
   to the policy's READY step. A verified zero is distinct from missing data.
   For missile credit, distinguish native civilian losses from an attempt,
   deployment, or a loss that could not be assigned to a rollout step.
2. **Did the arms receive different treatment?** Reward studies keep the
   exact applied reward components per episode. A nonzero reference reward
   shows the underlying mechanism worked. The diagnostic records the
   experimental arm's nonzero reward separately. Exploration studies compare
   the sampled masked distribution with the same logits and legal mask at
   temperature 1 and count actual changes. Optimizer comparisons record
   decision conditions that activate the extra planning entropy or phase
   weighting. Spatial comparisons record when the location head had a
   choice. They do not measure a same-state architecture contrast.
3. **Can gameplay outcomes be compared?** The frozen report counts distinct
   fresh native outbreaks with an official natural finish for each frozen
   policy, excluding prior and training outbreaks. Retries and timeouts
   remain incomplete for the official gate. Fewer than four eligible finishes
   in either arm is marked insufficient. Cohorts below 30 eligible finishes per arm are descriptive. `passed` keeps the existing three blocks of ten with each
   block averaging at least 35% officially saved. A functioning intervention
   can still yield weak or inconclusive gameplay outcomes.

## Advisory gate

The runner reports a positive treatment as soon as it observes one, including
a rare event. With no verified differential treatment, it reports
`collecting` until both arms have four distinct observed training outbreaks.
It then distinguishes `unexercised`, `incomplete_receipts`, and
`mechanism_without_treatment`. This is an early review prompt. It is not a
statistical futility test and never stops training. Adaptive PPO rollouts and
repeated seeds are not independent evidence of a performance improvement.
If a run should stop, the existing `stop-after-round` file still takes effect
only after the paired checkpoint and diagnostics are saved.

## Examples from completed runs

- Shelter-defense study 198952 had no occupied breach in any valid training
  battle. A baseline frozen battle did incur a breach penalty. The stronger
  arm never exercised the stronger cost, and all eight frozen games retried.
- READY shortfall study 199952 applied the experimental penalty in ten training
  battles. Each arm had one occupied start during training. All eight frozen
  games retried, so treatment delivery was verified and the outcome comparison
  was inconclusive.
- Planning-entropy study 201952 produced no occupied shelters in either arm.
  Seven fresh reserve outcomes remained after exclusions, with only one
  natural finish. Shelter outcomes alone do not prove whether the optimizer
  term was exercised. Historical records lack the new effect diagnostic.
