# Model and learning contract

Current implementation: `scripts/nn_play2.py`, schema4. This document supersedes
the old screenshot-based/L5 draft; Git history retains that draft. The objective
is at least35% actual civilians saved on every Boston level, consistently, at
normal difficulty. All strategy belongs to the policy.

## Observations

The policy receives4889 floats per decision. The first332 retain schema3 ordering:
32 scalar/legacy features,240 grid features,57 ability features and3 skill/geometry
features. The stock fractions correct the old false +alive-helicopter bonus; migration
explicitly recognizes those old labels and transfers the learned weights/Adam.
Thirteen legacy crowd features remain constant for checkpoint compatibility.
Schema4 adds4557 labeled native features for every unit variant, selected units and
buildings, roster/perks, geometry/land legality, ammunition/health/boosts, vehicles
and evac passengers, terrain/bridges, fire spread, hazards, mutation sites, camera,
normal timing, active tools, gestures and native HUD/modal affordances.

All native memory reads require the supported executable SHA256. Positions use
the current top-down camera and client size. Sparse terrain/fire sampling stays
bounded to48 grid points; bridge damage records identify their native span anchor.
Undamaged bridges have no damage record, explicitly distinguished from zero HP.
Exact ordering/normalization is in mechanic_contract.py and visualizer/labels.py,
with semantic regression probes. Native IDs are not interchangeable with toolbar IDs.

## Policy and actions

One128-unit single-layer GRU feeds185 tool logits,185x48 conditional cell logits
and a value head (3,096,810 parameters). Sampling uses the legal tool mask followed
by the selected tool's cell mask. Evaluation can use legal argmax (`greedy`).
The original72 actions retain their meanings;113 additions expose roster/perks,
all16 planning placements, selection/editing/refund/undo, native HUD choices,
detonation, camera, modal recovery, corridor width and normal speed/pause.

All19 battle ability buy/refund/cast actions use the actual purchased roster and
live stock. Quick Deploy reduces first-use unlock times using the native config
and equipped perk. Seek & Destroy snaps to garrisons; Demolition starts on an
eligible tall building, while the model chooses direction. Helicopters consume stock;
an existing aircraft does not grant another cast. Medevac departure, C4/Napalm armed-click and selected-panel detonations are explicit.
Native autonomous vehicle routing and combat are observed, never scripted.

Fresh copies enable59 catalog entries:16 units,19 abilities,16 SP upgrades and
8 perks. This does not buy levels or change normal money/SP. The shipped build
hides/disables SP tower upgrades; conditional HUD actions remain masked when absent.
The native game rejects officer movement/behavior orders during outbreak; masks
preserve that restriction. View overlays and3D tilt are presentation controls,
not additional game strategy; native height/class observations replace those views.

The model controls arbitrary polygon corners, endpoint geometry, edit handles,
selection and recovery from debt/land excess. READY is masked until native legality
passes; no automatic strategy rollback or forced READY. Corridor wheel adjusts width;
camera zoom is masked in that context. Modal dialogs block world actions and expose
confirm/cancel. See mechanics-coverage.md for scoped live and offline evidence.

The8x6 viewport grid and nearest-target snapping are still a spatial approximation;
zoom/pan improve precision. Masks do not predict every native price/buildability
condition. A sent key is never proof that a purchase or cast succeeded.

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
atomic and retain a.previous backup. Exact schema4 observation/action metadata is
validated. Learning revision1 records reward coefficients and phase-aware GAE;
only exactly matching schema4 weights/Adam are loadable. Policy2 is preserved separately.
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

Schema4 appends113 placement, roster/perk, selection/editing, native HUD, camera
and timing actions. Migration preserves source schema3 weights and Adam moments
in a new file; appended GRU input columns and Adam moments start at zero.
The battle decision floor is0.1s; native action completion can take longer.
