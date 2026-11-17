# ZAR Tracker (live state — update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-17k — kit-corrected PPO, 7 boards)
- Git: pushed thru 0417638. KEYBIND CONTRACT (AGENTS.md): battle keys 1-5 are
  loadout-bound; pinned WIN kit = 1 heli, 2 CTA x2, 3 Rally x3, 4 MEDEVAC x4,
  5 Seek x1 (0/2 SP). cc8ef9f wired this + obs kit slots + labels (24/24).
- 0417638: pause watchdog FIXED (compared o against prev_o=dict(o) copy of
  itself -> false SPACE every 2nd battle iteration; now dedicated wprev
  snapshot, phase resets, 2-comparison threshold, UNPAUSE log line) +
  restored lost obs.append (all episodes were SKIP short traj = PPO dead) +
  scripts/launch_extra.py (clone boot). visualizer/test_watchdog.py 6 tests
  drive real run_episode w/ fake env (5 fail on cc8ef9f, 30/30 after).
  LIMITATION: stationary counters can't distinguish pause vs dialog/menu.
- Boards: inst1..inst6 live L1 (pids per psutil dirname; DLL injected);
  inst7/inst8 clones (from inst6) booting via launch_boards.py; tile new
  pids into SLOTS (0,301)/(1265,301) 1295x837 via launch_extra.tile().
- L1 facts: civ0 8142, money 3111, naked board dies <4 s (t=4 end screen,
  no HUD bar visible = kit bar probe needs a surviving board).
- Trainer: python -u scripts/nn_play2.py train --pids <7 pids> --eps 2
  --rounds 14 | tee analysis/nn2_train_kit2.log. NEVER edit scripts/*.py
  while workers live. First-round audit: 'ep pid' lines (no SKIP), no
  UNPAUSE during falling zomb curve, runtime frames labels-ok.
## NEXT STEPS
1. Monitor kit2 log: wins/meanfrac trend; UNPAUSE lines only on true wedges.
2. Kit receipts audit: garrison money drops (succ rows), heli zomb drops,
   charges decrement vs reality; badge>=35% goal per ml-spec gates.
3. BC from best episodes (winners + it17 recipe) -> PPO warm start.
4. Phase end: kill instances, update tracker + AGENTS, push.

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
  refunds. Dialogs keyboard-only: YES(X)/NO, OK=Enter, ready-short YES=SPACE,
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
- 2026-11-15: L5 RE + scripted WIN x2 bronze (RE phase complete).
- 2026-11-16: env_zar memory channel FAST mode, parallel CEM, F5 speed,
  loadout file model, 4-board L3 farm; CEM plateaued (board-bound).
- 2026-11-17: Steam updated install (copies stale; port + RVA re-derive pending).
  NN pivot per user: curriculum L1->L5 via START OVER; nn_play PPO live;
  deck decode: battle row = fixed SP deck para/heli/gas/ac130 (no cure card in
  build); planning cards = money buys; extra-safe-zones perk active.
  Git repo created + GitHub remote pushed. AGENTS.md split (guidance vs tracker).
