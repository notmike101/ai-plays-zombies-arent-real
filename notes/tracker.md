# ZAR Tracker (live state — update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-17 — telemetry transport assessment)
- Read-only source assessment: observer publishes latest-only JSON at <=5 Hz;
  browser polls /api/state with a 50 ms delay after each completed request.
  Server re-reads runtime snapshots per request; no persistent event/log stream.
- Proposed direction for discussion: SSE for browser telemetry/log delivery;
  retain nonblocking observation and give logs bounded history/replay distinct
  from replaceable activation snapshots. WebSocket depends on whether actual
  bidirectional commands are wanted. No transport implementation authorized yet.
- No trainer/game/server launched, stopped or modified in this assessment;
  runtime/process state below is prior interface evidence, not revalidated here.

## Prior verified state (2026-11-17 — deterministic interface complete)
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

## CURRENT STATE (2026-11-17t — SP-honest deck model, kit5 trainer live)
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
  (civ==0 bt>6). Win is possible (kit2 hist: one r3 win frac 1.0) — trainer
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
