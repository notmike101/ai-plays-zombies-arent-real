# PPO comparison signal coverage

Private comparison runs write `signal-coverage.json` after each completed
training checkpoint and after frozen evaluation. Older run files are
preserved. Resumes carry forward signal from earlier completed training
rounds and exclude interrupted batches. `first_recorded_round` identifies
the earliest available training evidence, including for older checkpoints
with limited history.

## Three questions to ask

1. **Did the game or learner exercise the mechanism?** For the breach
   penalty, use civilians exposed at a native occupied breach. For READY
   coverage and shortfall, use the session-bound coverage observation matched
   to the policy's READY step. The READY-delay study instead records each
   legal READY choice the policy deferred and applies its per-decision cost
   to that transition. A verified zero is distinct from missing data.
   For missile credit, distinguish native civilian losses from an attempt,
   deployment, or a loss that could not be assigned to a rollout step.
2. **Did the arms receive different treatment?** Reward studies keep the
   exact applied reward components per episode. A nonzero reference reward
   shows the underlying mechanism worked. The diagnostic records the
   experimental arm's reward with the reference coefficient applied to the
   same native measurement. A nonzero candidate reward at the baseline rate
   is reported as unexpected instead of verified differential treatment.
   Exploration studies compare the sampled masked distribution with the same logits and legal mask at
   temperature 1 and count actual changes. Optimizer comparisons record
   decision conditions that activate the extra planning entropy or phase
   weighting. Target-settle studies verify the one-frame wait during a
   dispatched model-selected single-click building cast. A stock decrease or native
   deploy remains separate evidence of execution. Spatial comparisons
   record when the location head had a
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

## Comparison for sustained shelter protection

Compare existing shelter rewards with the same rewards plus bounded credit
for simulated time civilians spend in intact, occupied shelters. Keep the
native occupied-breach penalty identical in both arms. Retain the existing
qualification criteria and official survival score.

Use the share of the starting civilian population observed inside an intact
shelter at both ends of an interval, counting each civilian once across
overlapping shelters. Credit only bounded, observed intervals in active battle
and stop credit at observed penetration. Empty zones, paused time, duplicate
samples and missing intervals earn zero. Preserve credit for earlier verified
protection when civilians subsequently leave or a zone is breached. Set an
episode cap before running the comparison so a prolonged collapse cannot earn
unbounded reward. In the first comparison, sample at the shelter tracker's
existing 0.5-second cadence and omit intervals longer than 1.25 simulated
seconds. The candidate earns 0.01 per full-starting-population equivalent
second, capped at 30 equivalent seconds (0.30 reward). The baseline records
the same exposure and earns zero additional credit. Both use the stock
normal-speed clock, which gave the frozen policy more decisions per simulated
second in the cadence probe.

Test duplicate and overlapping zones, departures and relocation, zero clock
advance, missing samples, a successful occupied interval and a later breach.
Report occupied civilian-seconds, the exact reward increment, time and number
of civilians exposed at the first breach, starting coverage, defense choices,
and fresh official outcomes separately. Trials without intact occupied
intervals leave the intervention unexercised. A learner that stalls or reduces
shelter occupancy can improve a single diagnostic while worsening survival.

### Follow-up after the preparation comparison

Queue a repeat on a frozen source checkpoint with recurring native occupied
shelter exposure in discovery games. Select the source using discovery data
and reserve new outbreaks for the frozen evaluation. Match the source weights
and optimizer, decision cadence, exploration, READY coverage credit and
occupied-breach cost. Vary only the duration credit. The candidate in 214952
received 0.1331 extra reward across two of 16 training games. Its frozen
comparison had seven total retries, one timeout and zero eligible natural
finishes. This verifies reward delivery and leaves the learning effect open.

Compare occupied starts, confirmed defensive placements and deployments, time
to first occupied breach, occupants exposed at breach, and protected
civilian-seconds alongside official saved fractions. Report the frequency of
occupied starts as well as the protection results among occupied starts.
Continue to count every eligible frozen game in the official comparison.
Use the existing advisory gate to flag low exposure and retain rare verified
intervals. A longer intact interval is a mechanism measure. A survival gain
requires a separate fresh-outbreak result.

## Exact shelter occupancy input

`--compare-shelter-input` widens both private policies by one input. The
control supplies zero and the candidate supplies the fraction of living
civilians inside the union of closed native safe-zone polygons. This measures
current occupancy and includes breached polygons whose geometry still exists.
The fraction can rise when civilians outside shelters die. Read it alongside
the civilian survival features and the occupied-breach evidence.

The new GRU input weight and its Adam moments start at zero in both arms.
Schema 5 identifies this private observation contract. Ordinary schema 4
checkpoints and the official evaluation continue through their existing paths.
The signal report counts exposure to a positive input. Separately, a
same-state replay can zero the input while holding the policy, observation,
incoming memory and mask fixed to measure changes in the action distribution.
Action distributions and official survival each require their own evidence.

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
