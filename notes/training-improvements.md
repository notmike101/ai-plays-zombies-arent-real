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

- [x] 1. `nn_play2.py`: one sequential episode batch per unique PID; standard
  GAE with terminal/truncation bootstrap; persistent Adam; versioned atomic
  checkpoint with prior backup; explicit train/play/greedy semantics and run IDs.
  Tests: numerical returns/lambda/bootstrap; concurrent fake games cannot overlap
  per PID; optimizer round trip; evaluation does not update/save.
- [x] 2. `env_zar.py`, `nn_play2.py`: authoritative economy and outcome data,
  fresh dump handling, confirmed phase changes, action/next-state reward alignment,
  immediate doomed-run retry, no counter-only SPACE heuristic, save-based reward.
  Tests: stale outcomes, zero balance, failed READY, pause/lull, credit timing,
  unknown outcomes, evacuation, truncation. Live: owned copy only, bounded episode.
- [x] 3. `nn_play2.py`, environment, visualizer: reliable spatial observations,
  carried-board state, conditional placement via existing GRU/linear heads,
  legal geometry and gestures, policy-selected loadout with SP legality.
  Update labels, probes, observer/renderer as required in the same change.
  Tests: geometry, legal choices, observations, telemetry and exact model parity.
  Live: real planning/action receipts and a fresh actual worker observer frame.
- [x] 4. `nn_report.py`, launcher and documentation: run/checkpoint/board identity,
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
- Milestone 1: five new regression tests RED -> GREEN; 35 visualizer tests,
  actual-model parity (12 recurrent steps), and graph assertions PASS.
  Bootstrap support is in the math; actual cutoff observations land in milestone 2.
  Greedy sampling semantics and checkpoint schema compatibility are finalized
  with the expanded action/observation schema, not silently changed mid-run.
- Milestone 2: 13 learning/state, 13 deck, 5 boot and 33 visualizer tests PASS;
  model parity and graph checks PASS. Replaced the watchdog's old heuristic
  tests with explicit native pause/lull, retry, and next-state reward tests.
- Native build SHA a1bd5913ed3905aaaadfb5a14781004d28990f433ff1621c658c10f1795469d2
  matches retained REA dump-writer evidence. New REA saved_pct trace:
  ev_091fe3011d1d7161e240a486ae84a43038cdfa24b8ed6d4fc6de3b21804d003f
  in visualizer/runtime/train-saved-trace.json (static references, not runtime proof).
- Runtime session-log probe: Shift+F6 starts observer logging, F7 writes footer.
  Header includes SP, quota, loadout; snapshots every ~5 sim seconds and footer
  include the game's own saved_pct. Fresh header wall time binds one episode.
  Log timestamps state speed/2 is real-time multiplier; native sim clock avoids
  estimating from wall time. World Y is inverted in client projection.
- Scoped live model evaluation on fresh normal inst9 PID 50128: 7 sampled
  decisions, immediate doomed-run retry, end=aborted, actual footer saved 5.35%,
  reward -0.6801; no optimizer step. This is functional proof, not good play.
  Owned game stopped. User checkpoint SHA bd97460bfefa468c0c3564936cf9fcd74d390cf2c4d33bcccc34716e7df230ed unchanged.
  Evidence: visualizer/runtime/validation-result.json (later validations replace it).
- Ruling: use the documented session log for exact episode outcomes instead of
  deriving score from guessed memory fields. Unknown terminal outcomes are
  excluded; timeout samples use value bootstrap and never claim completed scores.
- Ruling: remove net-zombie/purchase/cast shaping. Next-state cumulative
  infections cost 1 per initial population, terminal saved fraction earns 5;
  no per-step floor. This coefficient choice requires later performance trials.

- Milestone 3: 18 learning/state, 12 deck, 3 spatial and 34 visualizer tests PASS;
  actual-model parity (12 steps) and graph checks PASS. Schema 3 is 332 inputs /
  632,649 parameters; old checkpoint loading now fails explicitly.
- Live inst9 PID 34176: UI Police buy/refund and scrolled Demolition buy/refund
  changed exact native levels and persisted roster order. Native enum ordering
  differs from picker order. Police level 2 means 40 individual officers.
- Native stock at 0x656488 was verified against session logs: Police 40 -> 28
  after a successful spray; failed clicks stayed at 40; Police20/Stungas1 matched
  all 39 footer stock entries. This replaces optimistic charge decrementing.
- Live model samples (seeds42/123, 12/20 planning decisions) spent $178.20 and
  $1611.24 through purchases/geometry, and changed loadout via receipts. Both
  were planning truncations, reward zero; neither is evidence of winning play.
- Fresh real worker44944/game34176 frame: 332 exact input labels, 3456 conditional
  cell outputs, actual sampled tool17/cell20 (flattened836), no label_warning.
  Evidence: visualizer/runtime/m3-frame.evidence. Owned game and worker stopped.
- Spatial reader captures native units, building candidates and planned-zone
  coverage. Candidates include unbuildable scenery; receipts remain required.
  Full obstacle/footprint and wall-health encoding is deferred pending validated
  native semantics, not guessed from screenshots.

- Milestone 4: report groups retain run/policy/level/start/mode identity; only
  actual known completed saved fractions count toward >=35%. Unknown outcomes,
  timeouts and errors are explicit. Source history2 is preserved and never read
  as proof of schema3 progress. Policy sampling seeds do not fix the game's RNG.
- Play/greedy main-path tests verify no PPO/save calls and byte-identical model;
  greedy now uses legal argmax. Adam state persists, PPO logs KL, clipping,
  entropy and explained variance, and nonfinite updates fail before saving.
- Curriculum: a game win below35% retries the level; >=35% leaves the win board
  for confirmed CONTINUE on the next episode. Final-level success stops the run.
  This path is covered with fake states; no live L1->L2 or full campaign win was
  achieved in these bounded tests.
- Full live validation initially caught a bottom-picker failure: eight rows fit,
  not seven. Fixed scroll clamp and ignored stale equipped names with zero native
  level. Regression test and live Cluster purchase/refund both PASS.
- Final normal inst9 PID12724/worker10300: seed42 policy sampled Mine, buy Cluster,
  READY, then waits (Cluster unlock45s; battle ended before that). Eight decisions,
  actual saved1.95%, immediate doomed-run abort, reward-0.88334. One real PPO step
  changed weights; validation checkpoint saved separately, optimizer state retained.
  This is functional evidence, not improved strength or a successful campaign.
- Reloaded validation checkpoint for a bounded greedy carry evaluation:12
  decisions, planning timeout, zero terminal reward, no optimization or checkpoint
  change. Original policy2 SHA remains
  bd97460bfefa468c0c3564936cf9fcd74d390cf2c4d33bcccc34716e7df230ed.
- Browser LIVE check:332 readable inputs, architecture332->GRU128->72/3456/1,
  actual Mine/cell25 matched native observer selected hu6/hc312. Larger graph
  layout now uses grids and inspector labels to avoid overprinted input names.
- Final checks:77 Python tests (21 learning/state,2 report/eval,3 spatial,12 deck,
  5 boot,34 visualizer);12-step exact-model parity; Node graph assertions; browser
  SSE/reconnect/pause/isolation; mobile WebGPU/Canvas2D and desktop gestures PASS.
  Mobile checks are emulated. Layout expansion was separately inspected with
  synthetic332/3456 data; it is not a second live-game test.
- Owned games, trainer attachments and test preview/browser are cleaned at end.
  Durable summary is this note; ignored runtime evidence includes
  final-validation.evidence, final-evaluation.evidence, validation-frame.evidence,
  schema3-browser.png and schema3-layout.png. No long training run started.

## Running the new schema

Use the configured PyTorch Python executable, not an unrelated system Python.
`python -B scripts/train_run.py --copies inst1 --rounds 1 --eps 1 --seed 42`
boots one fresh normal board, trains schema3 and cleans its owned game.
`--mode play --model sessions/nn_policy3.pt` evaluates an existing checkpoint;
`--start continue` resumes a partially cleared campaign. Subsequent episodes in
one run are carry retries or next-level starts, recorded separately. Fresh-board
benchmarking needs a fresh boot per evaluated episode; eps>1 is not a fresh-only
benchmark. `python -B scripts/nn_report.py --history analysis/nn_hist3.jsonl`
prints saved-score groups and unknown/incomplete counts.

`python -B scripts/validate_training.py --train --steps 60 --seconds 12` is the
bounded smoke harness; its checkpoint stays under visualizer/runtime. It refuses
busy copies and preserves both user policy2 and policy3. Long training and a
multi-seed L1-L5 benchmark remain separate work; no quality claim is supported yet.
### 2026-11-18 battle speed selection and UI confirmation

Across 1,194 sampled live battle frames, 37 of 65 sampled speed selections
requested the speed already running. The battle mask now reads the same native
pause and speed values used in the observation and disables that redundant
selection while unpaused. All four speed settings remain available when paused.
No action meanings, weights or optimizer slots changed.

Several eight-copy runs stopped on a two-frame UI receipt taking longer than
0.8 seconds. The UI-frame observer now allows up to two seconds and returns as
soon as it sees the required frames. It sends no extra inputs. Other picker
and game-state confirmation deadlines retain their existing bounds.
