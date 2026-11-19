# Zombies Aren't Real — Agent Guidance (READ FIRST, EVERY RUN)

Mission: train an ML model (GRU policy) that becomes a god-tier player of Boston,
MA — it must SAVE >=35% civilians on EVERY level, consistently. The MODEL plays and
owns ALL strategy (unit buys, safe zones, placement, deployment, in-battle casts).
I FACILITATE: unblock the learner, keep episodes flowing, monitor progress. Never
hand-script strategy the model should learn. Curriculum L1->L5 (START OVER restarts
the campaign; badges persist as BEST; R restart keeps board + leftover budget).

## New session entry point
- Python setup: `.venv\Scripts\python.exe` is the repository interpreter. If it is
  missing, follow README.md to create it with Python3.14 x64 and requirements.txt.
  Never reinstall packages in an environment used by active workers. Both launchers
  default to .venv; no activation is needed. Game/DLL/checkpoint prerequisites remain.
- Run `.\local.ps1 status`, then `.\local.ps1 check` from this checkout. Preserve
  healthy active training. Use `.\local.ps1 train --rounds N` only when idle;
  it resumes schema4 with one owned copy by default and inherited CPU/priority limits.
  Repeat --extra-copy instN for up to eight prepared copies under the shared CPU
  cap and optimizer. Verify all game PIDs contribute before judging throughput.
  Select the deployed copy from tracker with `--copy instN` on check/train;
  inst1 is only the default name, not a guarantee its older unlock profile is valid.
- Use `.\local.ps1 visualizer-start` to reuse/start the server. Stop commands
  require current PID AND create_time; see `local.ps1 --help` and the runbook.
  Do not bypass duplicate-run/missing-checkpoint/foreign-process refusal checks.
- With zero prior context, follow `notes/operator-runbook.md` for status checks,
  checkpoint resume and training/visualizer start/stop. Then read CURRENT STATE
  in `notes/tracker.md`; revalidate PIDs and creation times before acting.
- Current training uses `scripts/train_run.py` -> `scripts/nn_play2.py`, schema4,
  `sessions/nn_policy4.pt`. A fresh clone does not include this ignored checkpoint.
  Missing resume weights are an error, never permission to start random training.
- For campaign team search, follow the active experiment in the tracker and
  the campaign section of the operator runbook. Resume with
  `scripts/team_search.py --seed-from <search-directory-or-team-bearing-release>`
  using 4–8 idle, full-availability owned copies. Check the per-stage report.
  The six-hour export now includes the newest compatible selected team plus
  its GRU; an older GRU-only release resumes PPO only.
- Active trainer/environment paths derive from this checkout. Copy zar.example.toml
  to ignored zar.local.toml and configure the read-only source game installation.
  `local.ps1 prepare-game --copy instN` creates a NEW owned copy; never overwrites
  one or imports campaign progress. User directive: fresh training copies MUST
  have full unit/ability/upgrade/perk availability. The default profile enables
  these options without purchases, SP, placements or difficulty changes. This is
  a training profile, not evidence of earned progression. Preflight enforces it.
- Build the input DLL with `local.ps1 build-input` while owned games are stopped.
  Preserve rust-toolchain.toml/Cargo.lock and protocol3. Two clean builds must match;
  generated DLL/PDB/build manifests stay ignored. See scripts/hookdll/README.md.
  The separate HUD observer protocol1 copies the native selection panel after its
  original builder call. Preserve build/call-site pins, original-call semantics,
  seqlock and read-only Python mapping. Never use it to alter simulation state.
- Checkpoint sharing is authorized every6h to this repository's GitHub Releases.
  Use local.ps1 checkpoint-publish; no duplicate release for unchanged bytes.
  Preserve checksum/schema validation and identity helper. Do not publish game
  assets/DLLs/saves/logs/configuration. See notes/checkpoint-sharing.md.

## Process rules (every turn)
- TRACKER: live state, evidence, PIDs and next steps live in `notes/tracker.md`.
  Read it at the START of a run; UPDATE it at the END of every run (replace
  CURRENT STATE; keep entries dated). This AGENTS.md stays guidance-only — never
  log progress here.
- GIT: local repo at `D:\zar-scratch` with GitHub remote
  `https://github.com/notmike101/ai-plays-zombies-arent-real`. Commit EVERY file
  update IMMEDIATELY, ALWAYS Conventional Commits (`feat:`/`fix:`/`chore:`/
  `docs:`/`test:`); push at milestones. Never force-add gitignored artifacts.
  Use `node D:/github-agent/identity.mjs git ...` (and `... gh ...`) for all
  Git/GitHub commands; preserve its default contribution identity.
- Update `notes/*` (not this file) with new verified mechanics/traps as found.
- No subagents. Kill test instances at phase end. Update tracker before yielding
  a long run.

## Hard rules (safety + fairness)
- NEVER modify the configured source install (`C:\Games\...` here). Work only in
  this checkout's owned copies (`game-copies\instN\`, steam_appid.txt=5185890; copies' own
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
- `notes/ml-spec.md` — model design; `scripts/nn_play2.py` — schema4 PPO trainer (train /
  play / greedy; checkpoint `sessions/nn_policy4.pt`, history `analysis/nn_hist4.jsonl`).
- `scripts/env_zar.py` — ZAREnv(pid): memory-RVA observation + ready()/cast/place
  primitives; `scripts/zar_input.py` + `scripts/hookdll/` — virtual input.
- `scripts/launch_boards.py <instN...>` — kill/relaunch/nav boards to planning.
- `notes/automation.md` — verified input matrix + traps; `notes/memory-map.md` —
  RVAs; `notes/game-rules.md` — mechanics; `notes/engine.md` — binary notes.
- `visualizer/` — Signal web app, optional policy observer, maintenance tests
  and `README.md`. Runtime telemetry/logs are ignored under `visualizer/runtime/`.

## Keep the live neural-network visualizer working
- The visualizer is observation-only: display the model's actual inputs, outputs
  and sampled decisions. Never use it to train, change rewards/checkpoints,
  inject observations, select actions, or control the trainer/game.
- Browser delivery uses one `EventSource` connection to `/api/events` (SSE).
  Keep `/api/state` for diagnostics; do not restore browser polling. The server
  samples the existing runtime JSON files through a shared 200 ms cache, even
  with no viewers. This is a server-to-browser stream, not a trainer socket.
  The sampler wakes SSE viewers after sampling; do not add a second viewer poll
  delay. Cache decoded files by actual bytes, not only size/mtime. Keep decision
  count/interval distinct from published sequence and telemetry age.
  Cache encoded topology bytes across decisions at the same model revision.
- Recent decisions are sampled telemetry: 200 compact records in server memory
  across all workers/modes, latest 50 for the selected stream in the Inspector.
  Reconnect sends current topology and retained history; restart clears history.
  Published sequence gaps are shown, but earlier observer drops are unknowable.
  Do not call this complete/durable logging, stdout capture or execution proof.
  Preview and real history stay separate. Pause freezes the view only.
- Keep viewer handling bounded (16 active SSE streams, 3-second write timeout),
  automatic reconnect, idle status updates, and connection-vs-inference status.
  A slow/disconnected viewer must never block a worker. Run `test_stream.js`
  and `test_mobile.js` via Playwright for transport/UI changes, using synthetic
  preview only; close test previews afterwards. See visualizer/README.md.
- For an authorized real attachment check, use an owned idle game copy and
  read-only policy evaluation, then match game/worker PIDs and actual browser
  values/actions to one fresh observer frame. See notes/visualizer-live-check.md.
  `nn_play2.py play` never optimizes or saves weights. Use a separate --history
  for evaluations. Do not force actions for visualizer attachment tests.
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
- Campaign search observes each worker in the batch. Training keeps the
  primary at up to 5 Hz and other workers at up to 1 Hz. Held-out observers use
  up to 1 Hz. The team
  observer captures final combined tool/cell logits from the model return.
  Draw edges for the GRU and value head only, identify the team and forecast
  in the revision, and retain native masks and actual selections. Layout
  construction before the decision loop has no synthetic neural activations.
- Serve the visualizer from the same deployed checkout as the observer's runtime
  directory. Existing workers must be relaunched normally to pick up integration
  changes. Coordinate source updates/restarts with the training owner; never
  edit live trainer code or stop another agent's workers for visualizer work.
- After changing policy architecture, features, action heads or telemetry, run:
  `$zarPython = (Resolve-Path .venv\Scripts\python.exe).Path`, then
  `& $zarPython -B -m unittest discover -s visualizer -p 'test_*.py'`,
  `& $zarPython -B visualizer/verify_model.py`, and
  `node visualizer/test_graph.mjs`. The integration tests use a fake game and
  must never target live game PIDs. Check a real fresh worker sample at the next
  coordinated launch; a preview or isolated test does not prove live attachment.

## CURRENT STATE — deterministic interface (2026-11-17)
- Live results: notes/tracker.md. Contract and offsets: notes/automation.md.
- scripts/zar_boot.py boots owned copies screenshot-free; scripts/test_interface.py
  --copy inst4 --repeat 2 checks purchases, gestures, zoom, battle and retry.
- Four-copy proof: python -B scripts/zar_boot.py inst1 inst2 inst3 inst4.
- v3 stores CLIENT coordinates. Mouse gestures use the DLL virtual cursor plus one
  PostMessage edge path. Raw-only menu/world actions FAILED the isolated audit;
  do not repeat the superseded absolute-RawInput-only menu claim.
- raw_sent counts emissions, not consumption. Validate actions with dumps/counters.
- Injection is once per boot; reconnect to the section, never re-inject. Keep DLL
  creation/version validation/client expectation equal (currently 3).

## Standing input traps (detail in notes/automation.md)
- Expanded mechanic work is tracked in `notes/mechanics-coverage.md`; action names
  or sent keys alone never establish coverage. Shared `game_controls.py` uses
  native receipts and UI-frame synchronization; `native_state.py` reads typed
  simulation state only. Never confuse toolbar IDs with simulation entity kinds.
- Right-click without an active tool can move selected units. Check tool state
  before using it to cancel; ESC can open a menu while phase still says planning.
- Keys require scan codes. READY=SPACE; confirm with SPACE only when needed; stray SPACE pauses.
- Menu clicks use calibrated GetClientRect fractions (1920x1200 or 3840x2160,
  English UI scale 1); the layouts have different fractions. Unconditional ESC can back out of the
  campaign page; dismiss only a blocker. Never resize a running game.
- Zones need a press at each corner then Enter; segment drags supply corner presses.
  Walls need start/end presses. One freehand stroke does not commit either shape.
- Wheel uses WM_MOUSEWHEEL at the virtual cursor; validate anchoring with F6 view.
- Current obs().money reads the verified native dump field, including debt; old
  positive mirrors can be stale. F6 writes in-world and names files to one-second precision.
- env_zar.py and trainer APIs remain unchanged. Never edit live trainer modules or
  stop another owner's workers as part of interface maintenance.

## Phase-end checklist
1. Tracker + notes updated with verified findings; lessons learned -> notes.
2. All uncommitted work committed (conventional).
3. Kill test instances (enumerate via psutil dirname).

## Training ownership and persistence
- scripts/team_search.py searches model-selected preparation sequences and
  battle targeting parameters on fresh boards. Keep the base checkpoint
  read-only, preserve legal masks and log true wins separately from survival
  fitness. Validate finalists on new boards before promoting them.
- For a live spatial-head comparison, use scripts/compare_spatial.py with idle,
  preflighted copies. Both arms use the training lock, fresh boards and private
  weights. Telemetry is off for both arms in this experiment. See the runbook.
- Schedule one sequential episode batch per unique game PID. Never submit
  multiple episodes for the same PID as independent pool jobs.
- Keep one optimizer across PPO rounds. Checkpoints include optimizer state and
  are replaced atomically with a .previous backup. Live tests use a separate
  --model and --history; never overwrite the user's training checkpoint.
- Training improvement milestones and evidence: notes/training-improvements.md.
- The trainer validates the executable hash before using native phase/clock,
  money or spatial fields. Unchanged populations do not justify pressing SPACE.
- Shift+F6/F7 session logging is observation-only and is allowed. Bind the header
  to this episode; use footer stats.saved_pct, not alive fraction or best badges.
  Aborted results are scores at retry; timeouts are incomplete, never successes.
- Reward transitions read AFTER actions. Do not reward purchases or emitted
  casts; track receipts separately. Keep evacuation distinct from infection.
- After battle geometry input, wait for UI frames before checking native
  stock. Keep session-bound game deploy events alongside stock receipts:
  a gesture start, an armed tool and individual bomb effects are separate.

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

## Battle input and schema contract (2026-11-17)
- `nn_play2` schema 4 uses 2485 inputs, 181 tools and 48 conditional cells.
  Checkpoints default to sessions/nn_policy4.pt. Never silently reinterpret v2
  weights: checkpoint metadata must match labels/action meanings exactly.
- Battle hotkeys follow steam_cloud/settings.ini roster_battle, including gaps,
  plus bind_slot1..7. battle_order.txt controls the picker, not the equipped bar.
  UI purchases/refunds require native level receipts; do not use resume_loadout
  file edits as proof of ownership. Fresh normal L1 has 2 SP on this build.
- Dump [config] ability_charges/cooldown are balance defaults, NOT live stock.
  Native stock is 39 float32 values at RVA 0x656488 in Stock_Item enum order.
  Validate the executable hash first. Paratrooper stock counts individual officers.
- Model geometry uses two sampled cells; never wrap an endpoint across the grid
  or substitute READY when a planning cap expires. A cap is truncation.
- Native positions/camera replace battle screenshots. Grid building centers are
  candidate targets; scenery outside the play area can still reject purchases.
  Money/stock receipts decide success. Never infer execution from a sent input.
- The loadout UI is calibrated for 1920x1200 English UI scale 1 only; unsupported
  layouts fail explicitly. Battle geometry follows the shipped config comments.
- Native stock and post-cast receipts govern resource masks. Helicopter liveness
  refreshes from the native snapshot every decision; do not fabricate replenishment.
- Evaluation is read-only for model/optimizer; game actions still change its board.

## Evaluation and curriculum records
- Use an existing compatible checkpoint for play/greedy; only train optimizes.
  Greedy means legal argmax. Policy seeds do not guarantee identical game RNG.
- History records actual campaign/scenario, board fingerprint, policy ID, mode,
  seed and start kind. Fresh, carry and next-level scores must remain separate.
- Report >=35% actual saved, plus minimum/mean and unknown/incomplete counts.
  A planning timeout with100% civilians alive is never a completed success.
- Default training and evaluation are L1-only. Require explicit user direction
  and `--allow-progression` for L2–L5. In opted-in campaigns, advance only after
  a confirmed win with >=35% saved. CONTINUE is phase-gated.
- Eight picker rows fit the calibrated1920x1200 loadout UI. Clamp scroll to N-8.
  A persisted roster name with native level0 is an empty card, not a plus button.
- Dense graph layers use grids; labels remain accessible in the Inspector.
  Keep masked conditional probabilities and raw head outputs distinct.

## Spatial input boundary (2026-11-17)
- At calibrated1920x1200, the bottom grid row (cells40-47, Y=.76*height)
  overlaps the HUD. WORLD_CELLS must mask it out for every spatial action and
  building-target availability. Only explicit READY may press the READY control.
- Do not recover an accidental READY dialog by starting the battle. Fix the
  invalid click boundary; preserve model control over phase transitions.

## Native economy validity
- Safe-zone placement can overdraw money. Preserve signed finite native balances;
  negative money is valid debt, not missing memory. See notes/automation.md.

## Planning geometry validity
- After a model geometry edit, mask READY using native land/debt legality.
  The model chooses undo/refund/reshape to recover; never automatically roll back
  its strategy. Draft polygons and gesture anchors must be visible to the policy.

## Training dump retention
- Trainer attachments discard only newly generated .state companions after reading
  their text dump, and only within owned game-copies. Keep .txt receipts, session
  logs and all pre-existing replay evidence; diagnostic attachments retain states.

## Learning credit by phase
- Planning targets use the full remaining episode reward, plus the critic
  bootstrap on truncations. Battle GAE follows elapsed simulation time.
  Preserve phase-specific targets, reward receipts and learning metadata.

## Idempotent tool selection
- Tool hotkeys toggle. Undo may leave the old tool armed. Before selecting a
  planning/battle tool, cancel via virtual right-click and then press its hotkey.
  Repeated identical actions must reselect, never silently disarm the tool.

## Reward evidence
- Block gameplay targets outside the native playable polygon before sending input.
  Charge the rejected decision in PPO and campaign-search fitness. Check snapped
  targets and gesture endpoints. Preserve camera, UI and cancellation controls.
- Record infection, outside-playarea and terminal reward components separately, plus the learning
  configuration in history/checkpoints. Timeouts have saved_frac=null; keep their
  HUD snapshot only as observed_saved_frac with timeout_phase. Never count it as
  terminal success. Reject non-finite outcomes/bootstrap values before PPO.

## Expanded mechanics schema
- Schema4 preserves332-input/72-tool ordering and appends native mechanics;
  stock fractions explicitly correct the old false +alive-helicopter bonus.
  All feature/action changes must update mechanic_contract.py, labels, schema,
  tests and migration together. Coverage/proof gaps live in notes/mechanics-coverage.md.
- Explicit migration: `.venv/Scripts/python.exe -B scripts/migrate_policy.py
  sessions/nn_policy3.pt sessions/nn_policy4.pt` (one command). It requires a new
  destination and preserves weights/Adam prefixes. Never reset learning silently.
- Historical live probes have main guards; importing/discovering tests must never
  launch, stop or send input to a game. Live diagnostics require explicit execution.

- Boot assigns previously unbound placement modes K=click/J=paint on stopped owned
  copies. Conflicting custom bindings fail explicitly. Do not alter a live copy.
- Native map values use64-byte cache-line groups (e.g. three20-byte boosts per
  group, one56-byte AI record). Do not decode these as tightly packed arrays.
- Sample queried terrain cells only: L5 storage exceeds91 million cells. Never
  read or allocate the entire terrain grid on every policy decision.


## Modal gameplay contract
- Native modal667868 can pause simulation without changing the pause flag (the
  first mutation tutorial does this). Preserve explicit dialog observation and
  model confirm/cancel actions; mask world actions until the dialog is closed.
  Do not diagnose a static clock alone as a hang or send unconditional SPACE.

## Complete mechanics interface maintenance
- Current policy schema4 has4889 inputs/185 tools. Keep the catalog/status table in
  notes/mechanics-coverage.md synchronized with supported native controls. Existing
  stock features now mean charges/max: a live helicopter grants no free cast.
- Test action reachability as well as dispatch. Placement mode toggles share the
  place_ prefix with units but must not require roster membership.
- Native-disabled SP tower upgrades and planning-only officer orders stay conditional;
  never enable cheats/config modifications to fabricate normal-campaign coverage.
- Larger observations require bounded telemetry; preserve the8MiB frame limit,
  cached topology/200ms sampler and read-only observer. Policy step floor is100ms,
  not a promise of10 decisions/sec; native action/observation cost also matters.

- Native snapshots require matching counts/tick for parallel unit arrays. Other
  systems are sampled independently with bounded reads and validation; do not
  require the entire terrain/fire/world read to fit inside one accelerated tick.
- Missing F6 observer requests get one bounded retry only in an unobstructed game
  world. Never dismiss modal/menu state merely to force an observation. Persistent
  initial-dump failures report phase/modal/menu state and still stop the run.

## Campaign search selection
Pool fresh uninterrupted trials by frozen GRU and stage-policy prefix. Deduplicate native outbreak seeds. Keep carry and CONTINUE for practice. Preserve the incumbent until a challenger qualifies repeatedly and beats it on fresh held-out campaigns. Report counts and mean saved alongside the best score. See notes/operator-runbook.md.

Keep L1 parent selection and mutations independent of later-stage scores. Later-stage search overrides and PPO optimizers are stage-specific. Native playable-boundary camera framing applies to all episode modes. Preserve deliberate pan/zoom excursions, open dialogs and incomplete gestures. Re-evaluate policies under the same camera revision before comparing results.

Keep cast-timing proposals separate from target preferences in campaign comparisons. The timing feature uses legal, playable targets and the current civilian/zombie counts. Retain observed layout costs scoped to the matching stage, tool and points across search blocks.

## Safe-zone defense credit
Track unique sheltered civilians from native positions. Preserve credit after departure and charge only civilians still present at the first observed penetration of a previously intact zone. A civilian who reaches another intact shelter can incur a new exposure penalty if it falls. Do not count wall-cell breaches or overlapping failures as separate exposures. Preserve official saved fractions and qualification as the comparison criteria.

Special-building exploration stays bounded. Reward an activation only when the selected building previously had no ability and the native ability becomes the exact HUD choice. One credit per building, capped at three per episode. Use official saved outcomes for promotion.
