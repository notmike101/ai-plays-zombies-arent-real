# Complete normal-campaign mechanics and latency

User directive (2026-11-17): implement all remaining gameplay actions and complete
mechanic coverage, with milestone tests; diagnose and improve decision/visualizer
latency. Execute inline, no subagents. Keep the installed game read-only and all
actions virtual. Never claim completion from an action name or emitted key alone.

## Acceptance and design

Coverage means the supported native build's normal campaign mechanics have model
observations, model-selected actions where human control exists, valid masks,
execution receipts, tests and documentation. Native autonomous physics/combat
must be observed accurately, not replaced. Admin/debug cheats, external social
features, cosmetic settings and changing difficulty are outside gameplay policy.
Boston L1-L5 is the existing mission; do not redefine success as merely surviving.

Reuse the existing GRU/tool/conditional-cell interface. Preserve old feature and
action meanings; append features/actions and explicitly migrate checkpoint and
Adam tensors into a new schema without overwriting the source checkpoint.
Model owns all strategy. Multi-click geometry/selection are stateful policy
actions, not scripted strategies. Temporary planning debt/land-cap excess needs
refund/reshape recovery and a native READY gate, not arbitrary automatic undo.

## Milestones

1. Inventory shipped unlocks, controls, config/lang and cached matching-build
   Ghidra output. Create an exhaustive mechanics ledger; mark unverified items
   honestly. Reproduce the geometry rollback failure. Profile actual decisions,
   native reads/actions/dumps, observer, server and browser separately.
2. Native observation/action interface: all16 unit placements and roster control;
   selection/refund/move/aim; geometry creation/edit/removal; money upgrades and
   all16 SP upgrades/refunds; building-special choices; all19 ability gestures
   and follow-up controls; officer behavior/paint; C4/evac/target controls;
   camera, timing and campaign perk choices. Verify each against native state.
3. Policy integration: masks and receipts for all actions, carried-board and
   combat/resource/terrain observations, persistent gesture/selection state,
   explicit checkpoint migration with optimizer preservation. Update labels,
   preview, schema checks, operator/sharing and regression tests together.
4. Latency: replace unnecessary waits/dumps with bounded native completion
   observations; retain input calibration. Publish honest decision/transport
   timings and bounded telemetry without blocking inference. Run transport and
   mobile browser tests for UI changes and measure before/after on real workers.
5. Acceptance: every ledger item has implementation and proof, no hidden missing
   mechanics; offline suites, scoped native trials, migrated checkpoint resume,
   fresh real visualizer sample and completed update. Update AGENTS/tracker;
   commit each milestone conventionally and push. Leave headroom and clean probes.

## Starting evidence

- Run83bfa5642d1d ended at round3 after `finish_geometry` could not verify an undo.
  Launcher cleaned game528. Last saved policyc46cf2f2f5696822 remains intact.
- A30-second initial server sample had no live frames because that run had ended;
  it is not a latency baseline. Reproduce on owned inst13 with isolated evaluation.
- Cached REA/Ghidra output in analysis/decomp has a journal pinned to supported
  EXE SHA256 a1bd5913ed3905aaaadfb5a14781004d28990f433ff1621c658c10f1795469d2.
  Reuse it before starting another analysis engine. Static pseudocode is evidence
  for structure, not proof of runtime input behavior.
- Preserve unrelated policy2/history2 dirt and old untracked analysis artifacts.
