# Model and learning contract

Current implementation: `scripts/nn_play2.py`, schema4. This document supersedes
the old screenshot-based/L5 draft; Git history retains that draft. The objective
is at least35% actual civilians saved on every Boston level, consistently, at
normal difficulty. All strategy belongs to the policy.

## Observations

The policy receives2376 floats per decision. The first332 retain schema3 meanings:
- 32 scalar/legacy features: populations, money, elapsed time, population trends,
  four deck availability slots, previous action, purchase receipt, phase and spend.
  Thirteen legacy crowd features are currently constant because native-grid
  rollouts supply no screenshot blobs. They are retained for checkpoint compatibility.
- 240 spatial features: an8x6 grid of civilians, zombies, aggregated defender
  people, building counts and safe-zone occupancy. The bottom8 action cells are
  masked because their screen positions overlap the HUD.
- 57 ability features: level, remaining availability and pending arrival for each
  of19 abilities; plus3 features for unspent SP and a two-point geometry anchor.

Native memory is read only after matching the supported executable SHA256.
Positions use the live camera and client size. Zone geometry comes from fresh
the native read-only snapshot. Inputs, meanings and normalizations are pinned by visualizer
labels/tests. Changes require matching schema metadata; never reuse weights with
silently different feature meanings.

Schema4 appends2044 features: per-unit variants, selected-unit state, roster/perks,
camera/paint mode, native geometry, building classes, hazards, vehicles, HUD
availability, playable boundary and gesture/tool state. Exact meanings and
normalizations live in mechanic_contract.py and visualizer/labels.py. Remaining
coverage/proof gaps are tracked explicitly in mechanics-coverage.md; this is not
yet a claim of complete game coverage. Viewport/grid aiming still limits precision.

## Policy and actions

One128-unit single-layer GRU feeds171 tool logits,171x48 conditional cell logits
and a value head (2,043,324 parameters). Sampling uses the legal tool mask, then
the selected tool's cell mask. Evaluation can use legal argmax (`greedy`).

The original72 tools comprise34 wait/READY/planning/battle tools and38 buy/refund loadout
choices (19 abilities each). Geometry uses two model-selected cells. Loadout
controls use actual native ownership receipts; battle bindings use the saved
roster including gaps. Native stock governs resource availability.

Fresh training copies have full native availability:16 unit types,19 abilities,
16 upgrades and Extra_Zones, as explicitly requested. These are unlocks only;
normal campaign money/SP still pay for purchases. The model's current planning
roster exposes seven unit types plus the native Upgrade Unit action. Unlocking
the other unit types does not create policy actions for switching that roster.
All19 ability buy/refund actions already exist. Expanding unit selection needs
an interface/action/schema change with matching labels and checkpoint migration;
do not silently remap existing logits to newly unlocked units.

Tool selection cancels the previous tool through virtual right-click before
pressing a hotkey: hotkeys toggle and undo can leave a tool selected. Geometry
that violates native land/budget READY gates is undone once, with the prior board
and money verified. Failure to confirm execution or rollback stops the worker.

The action space is incomplete: no general unit/zone refund or reposition action,
no camera pan/zoom policy, no C4 detonation action, and no general selection,
repair or rebuilding interface. Masks do not yet predict every target's
buildability or purchase price. Do not claim all game mechanics are exposed.

## Reward

For each action, read the resulting state and compute:

    infection_reward = -max(infections_after - infections_before, 0) / initial_civilians

For a known completed/aborted outcome, add:

    terminal_reward = 5 * actual_saved_fraction
    episode_reward = sum(infection_reward) + terminal_reward

The outcome comes from this episode's native session-log footer, never a best
badge or the live civilian fraction. An aborted score is measured at retry, not
a completed game win. Evacuated civilians are not infections. There are no
purchase, spending, cast-emission, kill-count or READY bonuses.

Illustration: if35% are actually saved and65% are newly infected, the undiscounted
reward is1.75-0.65=1.10. A complete wipe with all civilians newly infected scores-1.
This assumes those infection totals; other deaths/evacuation can change the sum.
The35% goal is a curriculum/evaluation gate, not a discontinuous bonus cliff.

Timeouts are truncations: terminal reward0 and critic bootstrap, with saved_frac
null. observed_saved_frac retains the snapshot (often1.0 in planning) strictly
as diagnostics. History records reward_components, timeout_phase and learning
configuration; invalid/non-finite outcomes never enter PPO.

## Credit assignment and PPO

Planning GAE uses gamma=lambda=1: planning decisions do not advance simulation
time, so adding a longer planning prefix must not attenuate the battle signal.
Battle GAE uses gamma=.99 and lambda=.95 per decision. These are decision-based,
not elapsed-time discounts. Previously,60 planning steps attenuated a distant
TD residual by(.99*.95)^60, approximately0.0252. Preserving planning credit trades
lower attenuation for higher variance; actual gameplay gains require evaluation.

PPO uses a joint tool/cell likelihood ratio, clipping at0.2, value weight0.5,
entropy coefficient0.015, gradient-norm cap0.5 and4 epochs. Adam (lr3e-4) persists
across batches and is saved with the policy. KL, clipping, entropy and explained
variance are logged; there is not yet a KL-based early-stop gate.

One sequential episode batch owns each unique game PID. Episode/cap boundaries
currently reset GRU state. In particular, truncated planning may carry the board
but resets transient policy/anchor state: this is an approximation, not exact
recurrent continuation. Stalling can remain attractive while battle returns are
negative; no forced READY or arbitrary strategy reward hides this problem.
A proper persistent rollout state and stronger outcome evaluation remain needed.

## Checkpoints, evaluation and operations

Default model: sessions/nn_policy4.pt; history: analysis/nn_hist4.jsonl. Writes are
atomic and retain a.previous backup. Schema3 observation/action metadata is
validated. Learning revision1 records reward coefficients and phase-aware GAE;
older schema4 weights/Adam remain loadable. Policy2 is preserved separately.
`play`/`greedy` never optimize or write model checkpoints; use separate history.

Report actual >=35% saved with minimum/mean and unknown/incomplete/error counts,
separately by level, policy and fresh/carry/next-level start. Only confirmed wins
meeting35% advance curriculum. Repeated-board improvement is not fresh-board
or five-level generalization. Policy seed alone does not fix native game RNG.

Read notes/tracker.md for current PIDs and status. Launch with resource headroom;
never create competing workers for an owned PID. Runtime snapshots are discarded
only when newly created by trainer attachments inside owned game-copies; text
receipts, checkpoints and previous evidence are kept. Test copies are cleaned.

## Evidence and next priorities

See notes/learning-audit.md for this audit and notes/training-improvements.md for
prior implementation tests. Passing tests proves specific behavior, not strong
play. Priorities are complete observations of the carried board, missing recovery
and tactical actions, exact truncated-rollout continuation, better affordability
masks, then controlled fresh-board/multi-seed L1-L5 evaluation.

References: the [GAE paper](https://arxiv.org/abs/1506.02438) explains the trace
estimator; [OpenAI PPO documentation](https://spinningup.openai.com/en/latest/algorithms/ppo.html)
describes clipping limitations and a KL early-stop option. The phase-specific
choice here is a project decision, not a claim that those sources validate it.

Schema4 appends99 placement, roster/perk, selection/editing, native HUD, camera
and timing actions. Migration preserves source schema3 weights and Adam moments
in a new file; appended GRU input columns and Adam moments start at zero.
The battle decision floor is0.1s; native action completion can take longer.
