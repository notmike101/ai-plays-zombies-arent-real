# Real-game visualizer attachment — 2026-11-17

Result: PASS for the real game -> current policy inference -> observer file ->
SSE -> browser observations, sampled decision and recent-history path.
This was a bounded planning-phase smoke check, not a completed battle/campaign.

## Execution and ownership
- No existing game/trainer processes were running; approximately 14.9 GiB RAM
  was available before launch. Reused the normal visualizer server, PID 22604.
- Created an isolated `game-copies/inst9` from the owned inst4 copy. Booted with
  `scripts/zar_boot.py`'s `boot()` API: normal Boston L1, PID 38408, 8,142 civilians,
  zero zombies, $3,111. No installed-game writes, console, real cursor or resize.
- Evaluation worker PID 10824 loaded the existing `nn_policy2.pt` through
  `load_pretrained`, then called the unmodified `run_episode` with the actual
  policy and normal observer integration. No random policy, injected observations,
  scripted actions, optimization or checkpoint save. The model chose all actions.
- Captured 15 actual planning samples, sequence 0..14. Worker was stopped once
  the bounded browser proof was recorded, then the owned game was closed.

## Assertions and evidence
- Stream `10824-85d8f2c61dd4`, model revision `9f46809b1e6fecda`, preview=false.
  No `error` or `label_warning`; all 32 input labels matched INPUT_LABELS exactly.
- Browser observed at least three distinct samples via its actual EventSource
  connection. At sample 2, displayed action was corridor (tool 17), Cell 1
  (cell index 0); chosen probabilities approximately 5.6% and 0.9%.
- All 32 displayed input values and labels matched that SSE frame. Displayed
  action, sequence and latest history record matched the same sample.
- Browser-received values, probabilities, selected actions, timestamp, model
  revision and both PIDs exactly equaled the corresponding saved worker frame.
- First frame's log1p civilian count and money/1000 matched the real game counters.
- Checkpoint SHA-256 before and after was identical:
  `59cc9ccd26479de0b3c2e12d6f94648ed780b9710e7713205a93019c6d133699`.
- psutil confirmed both test PIDs absent and no game-copy processes remaining.
  Browser then reported WAITING FOR WORKER, Connected, with zero input rows.
- No application/trainer source changes were needed to pass this live check.

Ignored local evidence is under `visualizer/runtime/live-attachment/`:
`report.json`, `running.json`, `frames.json`, `browser-proof.json`,
`browser-output.txt`, `browser-live.png`, `worker.log`; parent log is
`visualizer/runtime/live-attachment-check.log`. One-off probe scripts also remain
under runtime. The screenshot is an actual live frame, paused only for capture.

## Guidance for repeating
Use an owned idle copy and the normal boot API; never stop another owner's game
or trainer. Reuse the existing server. Load the checkpoint for evaluation and use
the normal observer integration. In the current trainer, the CLI `play` path
shares PPO/update/save logic with `train`; do NOT use `play` for read-only checks.
Use the `greedy` evaluation path or a bounded direct `run_episode` invocation
without calling the optimizer or saving weights. The current `greedy` name does
not mean argmax: run_episode still samples actions from the policy.

Match real game/worker PIDs, require preview=false, compare current input labels
and actual browser values/actions to the same worker sample. Do not count an open
game window or a synthetic preview as proof. End the test after sufficient
evidence, close only owned processes, verify checkpoint integrity and inventory
processes by executable directory. Respect the immediate loss/retry rule if a
test enters battle. Keep the live server available afterwards.

Cleanup limit: automatic approval review rejected recursive deletion of the newly
created inst9 directory with only "blocked by policy" as its reason. No alternate
deletion was attempted. The idle copy remains on disk; it has no running process.
