# ZAR Tracker (live state â€” update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-17 — milestone 3 complete)
- Milestones1/2 committed/pushed; milestone3 committed e3e042e.
- Tests:18 learning/state,12 deck,3 spatial,34 visualizer; model parity and graph PASS.
- Owned inst9 PID34176 and worker44944 stopped after bounded model/UI/native probes.
- Real purchases, refunds, geometry, native stock and observer labels verified.
- Original policy2/history2 artifacts remain untouched. No active training run.
- Next: evaluation/report identity, PPO diagnostics, final scoped train/eval smoke.
- Evidence and limitations: notes/training-improvements.md.

## Prior snapshot (2026-11-17u â€” kit8 PPO run live on 5 fresh boards)
- RUN: train_run.py --copies inst1 inst2 inst4 inst5 inst8 --eps 2 --rounds 14
  -> analysis/nn2_train_kit8.log (bg_246). Boards = zar_boot fresh L1 (planning
  barrier PASS before trainer). Warm start = kit6 checkpoint (committed parent).
- PROVEN THIS RUN (pids 12612/47012 probes, killed): zar_boot fresh-boot works
  (~95 s to planning incl 75 s welcome); scripted garrison drags spend REAL money
  ($58-63/unit, receipts ok); L1 naked+3-garrison board = TOTAL loss ~5 s wall at
  8x (zomb 1447->8033 vs civ 8142); R-loop PERSISTS purchases+budget across losses
  (money 2935.80 + garrisons present in post-R dump) -> accumulation legit; kit
  {0:1} Police buys NOTHING on fresh L1 (SP-starved, DECK EMPTY expected early).
- NEW TELEMETRY (b470a84): hist rows now carry nbuy/ndeck/spend. First smoke row
  (pid 45772 r0): nbuy 5, spend $735.60, ndeck 0 -> random policy DOES build.
- kit5/6 post-mortem: t=6 wall + money-stuck-3111 ERR lines = modal-wedged boards
  wasting episodes (pre-zar_boot boards); accumulation was UNMEASURABLE then.
- Monitoring: after ~3 rounds check kit8 log for battle lengthening (t>6) and
  hist nbuy/spend growth = accumulation; if round 13 meanfrac still 0 with
  spend>0, escalate: reward/curriculum change (skill: score mid-state, boards
  carry via R). BC-warm start still queued after defense signal exists.
- Visualizer server 22604 up; stale preview demo killed; no other agents' workers.
- Live follow-up PASS: isolated inst9 normal Boston L1, game PID 38408 and
  evaluation worker 10824, current checkpoint. Captured 15 planning frames;
  browser LIVE, 32 displayed inputs, sampled action and history verified against
  SSE and the corresponding worker file. Initial civilian/money features matched
  actual game counters. No source changes required. Details: visualizer-live-check.md.
- Both test PIDs stopped; no game-copy processes remain. Checkpoint SHA-256
  unchanged. Browser returned to Connected / WAITING FOR WORKER / zero inputs.
  Normal server 22604 remains available. This proves planning attachment, not a
  full battle. Recursive deletion of the new inst9 copy was blocked by automatic
  approval review ("blocked by policy"); idle files remain, no bypass attempted.
- User clarified observation-only visualizer, delegated implementation choices,
  and authorized guidance updates and push. Implementation through e5da13d pushed
  to origin/main; final tracker/plan completion accompanies it in the next commit.
- Browser uses persistent SSE /api/events; /api/state remains diagnostic. One
  shared 200 ms file cache serves all clients, sampled even without viewers.
  Server retains 200 compact decision summaries globally, displays latest 50 for
  the selected stream, replays retained list on reconnect, resets on restart.
  Inputs/outputs remain actual observer data. This is sampled history, not durable
  trainer stdout or complete decisions, and never proof of game action execution.
- Current observation values and decision history are in the Inspector; Pause
  freezes the view only. Preview isolation, reconnect topology and idle status
  are maintained. At most 16 SSE viewers, with 3-second socket write timeout.
- Full visualizer suite: 35 tests PASS (including new stream/history tests).
  Existing eight fake-game integration/watchdog failures were caused by missing
  newer loadout interfaces; fixtures updated, original assertions preserved.
- verify_model.py PASS: actual PolicyNet2, 32 inputs / 72,915 parameters; exact
  outputs and sampled decisions for 12 recurrent steps. Warm CPU medians 0.085 ms
  plain / 0.160 ms observed (not end-to-end latency or game performance).
- Node graph assertions and JS syntax PASS. Chromium SSE/no-polling, reconnect,
  pause/resume, worker switch, 32 displayed inputs and preview isolation PASS.
  WebGPU/Canvas 2D and mobile portrait/landscape/touch checks PASS; physical mobile
  devices untested. Self-review performed without subagents, per repo rule.
- Normal visualizer server PID 22604, port 8765, deployed from D:/zar-scratch.
  Old server 5624 replaced; test server 29832 and synthetic preview 45212 stopped.
  Final browser smoke: WAITING FOR WORKER via SSE, no decision history. No game
  processes found by psutil executable-directory inventory. No trainer/observer
  source, policy, game process, game install or real input was changed.
- Evidence (ignored): visualizer/runtime/stream-python-check.log,
  stream-browser-check.log, stream-mobile-check.log, stream-decision-log.png,
  stream-mobile-artifacts/ and stream-browser-artifacts/. Unrelated training
  logs/checkpoint changes remain unstaged. Server log/error files are runtime-only.

## Prior verified state (2026-11-17 â€” deterministic interface complete)
- Interface only: no ML/trainer source changes, subagents, console commands,
  physical cursor input or game-install writes. Unrelated training artifacts
  remain uncommitted and untouched by this work.
- v3 client-coordinate/Win32 ABI defects fixed. Mouse actions use VirtualInput
  polling/cursor plus one posted edge sequence. Raw-only claims were contradicted
  by isolated tests and REA/Ghidra WndProc analysis; raw is movement compatibility.
- TWO consecutive final mouse acceptance cycles PASS:
  analysis/interface-20261117-094110.log (PIDs 25820, 5804, both killed).
  Each: fresh L1 $3111/8142 civilians, READY NO click, exactly one garrison,
  22 polygon walls + one wall, zoom +/-1 with zero anchor drift, battle, R retry.
- FINAL FOUR-COPY mixed-layout proof PASS: analysis/interface-scale-final.log.
  inst1 30368 (unfinished campaign START OVER), inst2 43040, inst3 9604
  (3840x2160 fullscreen), inst4 17872; all four coexisted in planning at $3111.
  All four killed. Temporary inst1 progress and inst3 settings restored.
- CONTINUE API PASS in windowed/fullscreen: analysis/interface-continue-final.log.
  PIDs 11212/7560 resumed L5 planning with 209867 civilians, then were killed.
  Uses a temporary existing unfinished checkpoint; original progress restored.
- Eight offline Python checks + one native ABI/layout check PASS:
  analysis/interface-unit-tests.log. Scoped git diff whitespace check is clean.
- All game processes now absent (including stale copies named in the handoff).
  Final inventory, DLL hash, settings restoration and badges: analysis/interface-cleanup.json.
  inst1..4 retain badges 39.23/34.31/21.14/13.69/7.91; no badge repair was needed.
- Limits: English/UI scale 1, calibrated clients 1920x1200 or 3840x2160. Boston
  fresh stage1 and CONTINUE for partially cleared campaigns (1-4 badges) only.
  Other destinations/sizes fail loudly. Zero-badge/completed CONTINUE is rejected.
  Fresh dump economy is authoritative; unchanged env.money can read a stale mirror.

## NEXT STEPS
- Open/refresh http://localhost:8765. Real attachment has now been verified once;
  the server waits because the isolated test worker was deliberately cleaned up.
  Continue checking fresh real frames/labels after future integration changes.
- Use AGENTS.md and visualizer/README.md for current streaming maintenance;
  older PLAN.md polling/integration-branch sections are explicitly historical.
- No interface acceptance work outstanding. Future build/layout changes require
  calibration and fresh live checks; source/menu matrix is notes/automation.md.
- Reuse scripts/zar_boot.py for owned copies. Successful API callers own cleanup;
  the CLI and acceptance test clean up automatically. No games are left running.

## VERIFIED CAPABILITIES (condensed; details notes/automation.md)
1. Parallel unfocused copies; virtual input per instance (DLL): clicks, keys,
   wheel, admin console, HUD/menu clicks, dialogs; PrintWindow shots (planning).
2. Memory channel: civ base+0x650f10 zomb+0x650f18 police+0x650f20
   corpses+0x650f28 conv+0x650f80 (i64), money f32 0x6563c0/0x65d9c0/0x665ef0
   (env_zar set_direct; battle-verified vs HUD to 1%).
3. F5 = 8x battle speed (vk 0x74 sc 0x3F). heli watchdog hot_spot() = green
   blob hunter (2-tuple px ints).
4. Episodes: harness + CEM legacy baselines A/B/C ~0-0.19%; scripted L5 WIN x2
   bronze 6.90/7.91 (sessions/checkpoints/inst2-WIN-*). Badges: L1 39% emerald,
   L2 34% diamond, L3 21% silver, L4 13.69 silver, L5 7.91 bronze.
5. Board clone = copy steam_cloud/plans/*.prep; progress resume_* file edits.

## THE SCRIPTED L5 RECIPE (reference dataset for BC; bronze 6.90 it17)
Conversion-snowball race. Won via: carry board (95 garrisons/39 mortars/15
snipers + CTA/Command_Post/Police/Repair/Radio trades -> Militia #2 killer
50.7k), t=0 heli sweep of 6 outbreak sites, burn kit early, then heli
redeploy every ~6 s onto densest contact cluster ALL BATTLE (micro-control
stops conversions; civ curve flattened at 31% alive); mortars 52.7k kills
until ammo dry. Badge % counts SAVINGS (in-zone/evac), not alive. Zones over
dense crowds + Battleship water AOE = path to silver. (notes/game-rules.md)

## SAFE-ZONE / DIALOG MECHANICS (user-confirmed + en.lang)
- Zone tool: click perimeter points, close loop with Enter; fee ON CLOSE
  (L1 800x760px = $1155); land cap L1 30%. Select zone wall -> X -> YES(X)
  refunds. Dialogs accept virtual posted clicks or keys: YES(X)/NO, OK=Enter, ready-short YES=SPACE,
  ESC=NO (2nd ESC=pause). F6 writer frozen while dialog/menu up.

## EVIDENCE / PATHS
- Screenshots: analysis/*.png (gitignored): win2-791.png, deck_probe4.png,
  after_startover2.png (MAP COMPLETE campaign screen), epfail_<pid>.png.
- Ghidra Evidence: analysis/nzstate_trace.json (state-dump writer
  0x140015d00, "NZSTATE1" @0x1405376e8); Ghidra 12.1.4 D:\ghidra; REA MCP
  registered (omp restart needed for tools).
- Old dead pids: [9820,48672,38188,19400,48508,37400,26868,30508,20944,46284,
  24980,23776,49320-old etc]; user game pid 19588-era = user's own (untouched).

## HISTORY (dated run summaries)
- 2026-11-17: User-requested live attachment proof passed on isolated inst9 with
  actual checkpoint inference and browser SSE. Fifteen planning frames captured,
  exact values/actions checked, checkpoint unchanged, test processes stopped.
- 2026-11-17: Deployed read-only SSE, shared snapshot sampling, readable inputs
  and bounded sampled decision history. Tests and docs updated, changes pushed;
  no trainer/observer or gameplay changes. Synthetic preview cleaned up.
- 2026-11-17: Assessed persistent telemetry and log streaming from current
  observer/server/browser source; discussed SSE versus bidirectional WebSocket.
  Product code unchanged; no live latency measurements or game tests performed.
- 2026-11-15: L5 RE + scripted WIN x2 bronze (RE phase complete).
- 2026-11-16: env_zar memory channel FAST mode, parallel CEM, F5 speed,
  loadout file model, 4-board L3 farm; CEM plateaued (board-bound).
- 2026-11-17: Steam updated install (copies stale; port + RVA re-derive pending).
  NN pivot per user: curriculum L1->L5 via START OVER; nn_play PPO live;
  deck decode: battle row = fixed SP deck para/heli/gas/ac130 (no cure card in
  build); planning cards = money buys; extra-safe-zones perk active.
  Git repo created + GitHub remote pushed. AGENTS.md split (guidance vs tracker).

## Prior tracker snapshot (before interface task)

## CURRENT STATE (2026-11-17t â€” SP-honest deck model, kit5 trainer live)
- Git HEAD 888b1a8 UNPUSHED (deck model + env_zar dump channel + hookdll v2 +
  probe/test scripts; shim git only). Tests 17/17 green
  (scripts/test_deck.py 11 + visualizer/test_labels.py 6).
- DECK MODEL (nn_play2): deck built ONLY from battle-dump [economy]
  'loadout <Name> = lvl' echo = what SP actually bought. KIT TRUTH (probe
  2026-11-17, kit_probe.py): SP-starved L1 board CONSUMES resume_loadout and
  buys ZERO (economy echo empty); ability_charges shows UNOWNED defaults
  (.Police = 1) and loadout_police_cost = 1/level; R-retry boards NEVER earn
  SP (6/6 EMPTY on the once-won board) -> SP comes from SAVINGS (sp_base=1 +
  sp_per_root_10k=1 per 10k saved) -> decks exist only after good outcomes
  (it17 L5 kit proves purchases at scale). Deck keys READ from settings.ini
  bind_slot1..7 ('_1'->'1', T). Charges + *_unlock/_arrival_seconds from the
  [counts] rules echo; refresh_battle_state re-syncs charges + game
  ability_cooldown -> exact blocked window (HELI exempt: free re-aim while
  flying, counts.helicopters = liveness truth). ready_once verifies
  phase='playing' via F6 dump (memory counters LIE on lost screens).
- L1 reality: civ0 8142 naked board dies ~6 s wall @8x -> early-loss break
  (civ==0 bt>6). Win is possible (kit2 hist: one r3 win frac 1.0) â€” trainer
  must find defense; battle mask when deck EMPTY = wait-only HONESTLY (old
  code cast phantom abilities for reward: fixed).
- Dump channel (env_zar.dump/phase_now): raw debug_dumps txt = plain
  '[section]' headers, parses to build/where/clock/view/economy/counts;
  analysis/dump-plan-44716.txt copy was re-formatted to '== [x] ==' by the
  earlier session (live files differ).
- Trainer RUNNING: TrainerKit5 = train --pids 39092,10428,29948,17224
  --eps 2 --rounds 14 > analysis/nn2_train_kit5.log (started ~04:10).
  kit2 (01:06, pre-fix) = all frac 0 + UNPAUSE flood: superseded.
- Instances idle/live: 39092 10428 29948 17224 (inst4/5/6/8, L1) in trainer;
  44716 inst3 lost screen; 3588 inst7 wedged welcome page (kill at end).
  NO Subagents rule stands (this run).
## NEXT STEPS
1. Monitor kit5 log: planning defense quality (money receipts), early-loss
   breaks ~6-9 s, one L1 win -> SP>0 -> DECK lines become non-EMPTY = the
   final live proof of purchase+cast (todo item 5's tail).
2. Deck-live proof audit: 'DECK <pid>: <name>xN@key' lines vs economy echo;
   kills Paratrooper/Heli counters move after casts.
3. BC from winners + it17 recipe -> PPO warm start (ml-spec gates 4/13.69/35%).
4. Phase end: kill instances (incl 3588/44716), update tracker + push.
