# ZAR Tracker (live state — update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-17f — NN phase live, CEM paused)
- Git: local repo + remote origin github.com/notmike101/ai-plays-zombies-arent-real
  (main pushed). Commits: 9f1c793 init -> 4ec4443 launch fix -> 7af1015 logs.
- `scripts/nn_play.py` PPO+GRU (63,282 params; obs 19 feats; 49 acts = wait +
  4 battle units x 12 grid cells; charge-masked; reward 8*dfrac - 0.02/cast +
  3*win + 5*frac^1.5; GAE+clip+entropy; ckpt sessions/nn_policy.pt; history
  analysis/nn_hist.jsonl; forward returns full (T,) sequences; ppo_update
  verified synthetic 4.21->4.00/epoch).
- Training run (service NnTrain4): rounds 0-1 DONE = all-loss plateau
  (frac ~0, R -8.0x, batch loss 23.9->12.5 mostly value-head). Diagnosis:
  flat 49-way softmax + sparse signal = no gradient; scripted mortar boards die
  at ammo-cliff ~t450s.
- v2 IN PROGRESS (scripts/nn_play2.py, new file so live run isn't poisoned):
  two-headed policy (unit x cell factorized) + kill/reward shaping + PLANNING
  PHASE OWNED BY NET (tool hotkeys 1 garrison $18-270 bldg / 2 mortar $75 bldg /
  3 napalm $100 / 4 turret $90 bldg / 5 mine $15 open / 6 C4 $500 / 7 gas tower
  $90 / F upgrade; zone presets; READY = model decides; phase+money+success bit
  in obs). Deck fixed para/heli/gas/ac130 (SP meta = outer loop later).
- Boards: L1 fresh (START OVER'd, planning $3111, civ 8142):
  pids 49320 49276 49384 39160 (training) + inst6 21992 READY (spare).
  inst2 45120 idle L3 E-zone board ($69, 39% safe). Nav for fresh boards =
  scripts/launch_boards.py (updated to MAP-COMPLETE layout: NORMAL shot(705,765)
  -> START OVER shot(705,926)).
- Smoke facts: random policy + mortar board held frac 1.00 until 496 s once,
  else full-collapse runs -> cliff after mortar ammo dry (no resupply).
  R dialog: keeps placements + loadout + leftover budget (economy persists;
  START OVER = full reset). L1 = 8,142 civ, $3,111, land cap 30%.
- Verified planning-hotkey map (from cards + _place probes): see v2 list above;
  zone tool key Z UNVERIFIED (probe interrupted by R dialog on inst2).

## NEXT STEPS
1. Finish nn_play2.py (planning-phase actions, two-head policy, kill shaping);
   dry-run ppo path; syntax gate; then swap training over when NnTrain4 ends.
2. Relaunch training with 5 pids (add inst6 21992) long-run; monitor
   wins/frac/loss in analysis/nn_*.log + nn_hist.jsonl; commit logs per round.
3. Probe zone tool key (Z) on a board; add zone actions to v2 if real.
4. Escalate on wins: win L1 -> battle-end CONTINUE chain -> L2 (badges auto).
   >=35% per level is the bar; BC from best episodes if PPO slow.
5. Phase end: kill instances, port new Steam build (RE-DERIVE MEMORY RVAs!),
   re-baseline, final tracker + notes update, push.

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
