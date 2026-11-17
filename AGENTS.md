# Zombies Aren't Real — Agent Guidance (READ FIRST, EVERY RUN)

Mission: train an ML model (GRU policy) that becomes a god-tier player of Boston,
MA — it must SAVE >=35% civilians on EVERY level, consistently. The MODEL plays and
owns ALL strategy (unit buys, safe zones, placement, deployment, in-battle casts).
I FACILITATE: unblock the learner, keep episodes flowing, monitor progress. Never
hand-script strategy the model should learn. Curriculum L1->L5 (START OVER restarts
the campaign; badges persist as BEST; R restart keeps board + leftover budget).

## Process rules (every turn)
- TRACKER: live state, evidence, PIDs and next steps live in `notes/tracker.md`.
  Read it at the START of a run; UPDATE it at the END of every run (replace
  CURRENT STATE; keep entries dated). This AGENTS.md stays guidance-only — never
  log progress here.
- GIT: local repo at `D:\zar-scratch` with GitHub remote
  `https://github.com/notmike101/ai-plays-zombies-arent-real`. Commit EVERY file
  update IMMEDIATELY, ALWAYS Conventional Commits (`feat:`/`fix:`/`chore:`/
  `docs:`/`test:`); push at milestones. Never force-add gitignored artifacts.
- Update `notes/*` (not this file) with new verified mechanics/traps as found.
- No subagents. Kill test instances at phase end. Update tracker before yielding
  a long run.

## Hard rules (safety + fairness)
- NEVER modify `C:\Games\...` (read-only install). Work only in `D:\zar-scratch`
  copies (`game-copies\instN\`, each with `steam_appid.txt`=5185890; copies' own
  ini files MAY be edited). NEVER write the user's game install.
- Admin console = CHEAT: manual one-off human-driven diagnostics ONLY. NEVER in
  training/automation loops.
- Difficulty stays pinned (normal) — no difficulty farming for scores.
- Input: virtual-input DLL + PostMessage ONLY. NEVER the real mouse
  (no SetCursorPos/mouse_event), never take over the user's cursor. NEVER resize
  a live game window (pick size via settings.ini before launch).
- Lost battle (civ <= ~10%) => press R,R immediately (user directive) — never
  watch doomed runs. OPEN DIALOG/menu pauses the sim + dump writer: that's state,
  not a hang.
- Extra game instances are allowed to speed training, but leave CPU/GPU/RAM
  headroom on the user's machine; enumerate pids via psutil by exe dirname.
- Screenshots/observations: PrintWindow works in planning/menu only.

## Where things live
- `notes/tracker.md` — CURRENT STATE, NEXT STEPS, PIDs, evidence index.
- `notes/ml-spec.md` — model design; `scripts/nn_play.py` — PPO trainer (train /
  play / greedy modes; checkpoint `sessions/nn_policy.pt`; logs
  `analysis/nn_*.log|jsonl`).
- `scripts/env_zar.py` — ZAREnv(pid): memory-RVA observation + ready()/cast/place
  primitives; `scripts/zar_input.py` + `scripts/hookdll/` — virtual input.
- `scripts/launch_boards.py <instN...>` — kill/relaunch/nav boards to planning.
- `notes/automation.md` — verified input matrix + traps; `notes/memory-map.md` —
  RVAs; `notes/game-rules.md` — mechanics; `notes/engine.md` — binary notes.
- `visualizer/` — Signal web app, optional policy observer, maintenance tests
  and `README.md`. Runtime telemetry/logs are ignored under `visualizer/runtime/`.

## Keep the live neural-network visualizer working
- Launch `./visualizer/start.ps1` from the deployed checkout; open
  `http://localhost:8765` (binds `0.0.0.0:8765`). `-Preview` starts a separate,
  clearly labeled synthetic network, not a game. Reuse an existing server;
  do not start competing servers or trainers. WebGPU needs localhost/trusted
  HTTPS; plain HTTP LAN access can use the Canvas 2D fallback.
- `scripts/nn_play2.py` creates an optional `Observer` after loading/evaluating
  each episode's actual policy. Preserve its `publish` call AFTER masking and
  sampling, with the actual probabilities, selected tool/cell and phase.
  Preserve `close()` in `finally`, including early returns and failed episodes.
  Random-policy runs have no neural activations and should not impersonate one.
- Keep observation labels in `visualizer/labels.py` in EXACT `make_obs` order.
  Update supplied tool/cell labels with action meanings. Dimensions and weights
  refresh automatically; feature semantics do not. Never silently reuse old
  labels when reordering/replacing features, even if the feature count matches.
- The observer supports one single-layer, unidirectional GRU directly feeding
  linear heads. If architecture/forward behavior changes (new layers, gates,
  functional transforms, bidirectionality, multiple steps), update the observer,
  renderer and tests in the SAME change. Unsupported models must be reported
  explicitly. GRU edges are unsigned gate-weight RMS summaries, not individual
  synapses. Maintain the distinction between raw outputs, masked probabilities,
  sampled actions and the value head's predicted reward.
- Keep telemetry read-only, detached, bounded and best-effort. Never mutate
  model tensors, consume policy RNG, block inference on disk/network, or add
  game controls to the visualizer. Do not replace missing live data with preview
  data. A stale stream can mean paused/idle inference; check worker activity and
  telemetry before diagnosing a hang. Auto-attach needs an instrumented worker's
  first decision, not merely a spawned game process.
- Serve the visualizer from the same deployed checkout as the observer's runtime
  directory. Existing workers must be relaunched normally to pick up integration
  changes. Coordinate source updates/restarts with the training owner; never
  edit live trainer code or stop another agent's workers for visualizer work.
- After changing policy architecture, features, action heads or telemetry, run:
  `$zarPython = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"`, then
  `& $zarPython -B -m unittest discover -s visualizer -p 'test_*.py'`,
  `& $zarPython -B visualizer/verify_model.py`, and
  `node visualizer/test_graph.mjs`. The integration tests use a fake game and
  must never target live game PIDs. Check a real fresh worker sample at the next
  coordinated launch; a preview or isolated test does not prove live attachment.

## Standing input traps (detail in notes/automation.md)
- `key_press` needs scan codes (zar_input SC table); READY = SPACE (stray SPACE =
  pause trap); placements = `vi.click` (CLICK MODE; drags dead in current build);
  menu clicks = raw screenshot px; NEVER click CHOOSE; edit progress/config FILES
  + restart instead of dead menu paths; never edit `scripts/*.py` while trainer
  workers are live (they reimport per episode); F6 dumps freeze while dialogs open.

## Phase-end checklist
1. Tracker + notes updated with verified findings; lessons learned -> notes.
2. All uncommitted work committed (conventional).
3. Kill test instances (enumerate via psutil dirname).

## Visualizer label maintenance contract (2026-11-16, enforceable)
Any change to `make_obs()` in `scripts/nn_play2.py` — feature add, removal,
reorder, or semantic/normalization change — MUST land in the SAME change with:
1. `visualizer/labels.py` `INPUT_LABELS` (names embed exact normalization);
2. `visualizer/test_labels.py` `EXPECT` + `LABEL_PINS` probe table;
3. `visualizer/demo.py` on width change (preview derives its width from
   `INPUT_LABELS`, so never hand-edit it);
4. green `python -m unittest test_labels test_observer test_integration
   test_server` from `visualizer/` AND `python verify_model.py` (which checks
   the labels the trainer actually supplies, verbatim, no generic fallbacks).
Enforcement: `nn_play2.main()` refuses to launch training when
`len(INPUT_LABELS) != NOBS` (`validate()` raises); a mismatch is a deployment
bug and must never degrade into generic `input <n>` labels. Dimension-only
tests or checking the synthetic preview are NOT sufficient proof: after
deployment, inspect one fresh REAL worker frame (`visualizer/runtime/<pid>-*.json`
— `graph.layers[input].labels` readable, no `label_warning` key present).

## Battle keybind contract (2026-11-16s, user directive)
- Battle kit keys 1-5 are bound BY THE RUN LOADOUT (SP picks rebind the
  bar). Pinned WIN-board kit (0/2 SP spent, confirmed on L1 end screen):
  key1 = heli (redeployable), 2 = CTA x2, 3 = Rally x3, 4 = MEDEVAC x4,
  5 = Seek x1 (it17 evidence). `nn_play2` BATTLE_U + st['charges'] +
  TOOLS idx 11-14/19 mirror exactly this.
- ANY loadout pick change: read the live battle HUD bar screenshot BEFORE
  trusting battle fitness, then update BATTLE_U + charges + TOOLS in the
  same change. A stale binding is a silent no-op keypress (the old table
  pressed '2' as heli when key2 was actually CTA — every battle cast was
  off one slot).
- L1 battle dies in <4 s on a naked board (t=4 end screen already shows
  'nothing deployed', 0 kills) — bare boards are useless as HUD probes.
