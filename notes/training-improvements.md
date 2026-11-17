# Training correctness and capability implementation plan

User approved the twelve proposals in this chat on 2026-11-17, including
bounded live tests, regular conventional commits, and documentation updates.
Implementation is inline, without subagents. Existing checkpoint/log changes
are preserved. No user install writes, console automation, real cursor input,
or changes to normal difficulty.

## Design

Keep the GRU and existing virtual-input environment. Correct the data collection
and objective before expanding observations/actions. Prefer existing helpers.
Game truth must distinguish missing data from zero and actual saves from alive
civilians. Model decisions retain control of strategy. Evaluation never trains.

## Milestones

- [ ] 1. `nn_play2.py`: one sequential episode batch per unique PID; standard
  GAE with terminal/truncation bootstrap; persistent Adam; versioned atomic
  checkpoint with prior backup; explicit train/play/greedy semantics and run IDs.
  Tests: numerical returns/lambda/bootstrap; concurrent fake games cannot overlap
  per PID; optimizer round trip; evaluation does not update/save.
- [ ] 2. `env_zar.py`, `nn_play2.py`: authoritative economy and outcome data,
  fresh dump handling, confirmed phase changes, action/next-state reward alignment,
  immediate doomed-run retry, no counter-only SPACE heuristic, save-based reward.
  Tests: stale outcomes, zero balance, failed READY, pause/lull, credit timing,
  unknown outcomes, evacuation, truncation. Live: owned copy only, bounded episode.
- [ ] 3. `nn_play2.py`, environment, visualizer: reliable spatial observations,
  carried-board state, conditional placement via existing GRU/linear heads,
  legal geometry and gestures, policy-selected loadout with SP legality.
  Update labels, probes, observer/renderer as required in the same change.
  Tests: geometry, legal choices, observations, telemetry and exact model parity.
  Live: real planning/action receipts and a fresh actual worker observer frame.
- [ ] 4. `nn_report.py`, launcher and documentation: run/checkpoint/board identity,
  separate fresh versus carry evaluation, >=35% saved success rate and unknowns,
  useful PPO diagnostics. Final offline suites and scoped live train/eval smoke,
  checkpoint isolation, process cleanup, guidance/tracker update and milestone push.

For each milestone: add regression tests, observe failures, implement, run focused
tests and applicable visualizer suite, review the connected code, commit. Tests
use fake PIDs and temporary files unless explicitly labelled live. Existing
hardware probe scripts are not safe automatic test-discovery targets.

## Review focus

- Multiple workers must never own one game; duplicate input PIDs fail early.
- Missing/late/stale telemetry must not become a zero score or phantom purchase.
- Failed transitions/timeouts must not contaminate terminal returns.
- Schema changes must never silently reinterpret old checkpoint columns/heads.
- Evaluation and tests must preserve the user's checkpoint and clean owned games.

## Evidence and decisions

- Initial process inventory: no game-copy/trainer processes; visualizer PID 22604.
- Baseline working tree has prior modified history, tracker and policy plus
  untracked run artifacts. Those artifacts are not inputs to performance claims.
- REA is available by skill, but no REA MCP tools are exposed in this session;
  use existing CLI/Ghidra only when a concrete runtime-format question needs it.
