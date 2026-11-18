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

All native memory reads require the supported executable SHA256. Parallel unit
arrays must share a simulation tick; independent systems are sampled separately
with bounds/occupancy checks. A complete observation can span ticks. Positions use
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

ghts and Adam state remain resumable; new saves record revision 2.
The previous decision-count discount was learning revision 1.