# ZAR Tracker (live state — update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-17g — nn_play2 PPO LIVE)
- Git: remote pushed thru 82d6eca (verified hotkeys + zone + trail + to_planning).
- nn_play2 TRAINING (service Nn2Train1, 5 pids, log analysis/nn2_train1.log):
  round0 = WINS 2/10 frac 1.00 x2, meanfrac 0.356, R spread -0.8..+15.9 (strong
  advantage variance = real gradient). Random-init policy already wins L1 via
  persistent-board economy (purchases accumulate across R-restarts).
- Wedge fixed live: 49384 paused-mid-battle (SPACE unpause + ENTER + R ->
  planning). to_planning needs unpause probe (SPACE once per iteration when
  zomb>0 unchanged) - TODO next trainer downtime. Hardcore banner on boards:
  loss wipes run -> back to L1 (self-heals via START-OVER-less R; curriculum OK).
- Trainer stack: nn_play2.py (PPO two-head UxC, verified DEPLOY/BUILD hotkey
  map from live HUD: 1 Napalm $100, 2 Mortar $79, 3 Sniper $50, 4 Turret $90,
  5 Mine $15, 6 C4 $500, T GasMortar $90, B Safe-Zone, F Upgrade, G Gate,
  Z Wall, Q Corridor, E Hold; READY=[Spc]; L3 zone cap 9 zones/44% land).
  v1 nn_play.py dead-ended (flat head, 16 all-loss eps) — history only.
- Economy facts: R keeps placements+loadout+LEFTOVER BUDGET (board invests
  grow across episodes); START OVER = full reset; L1 = 8,142 civ $3,111 cap
  30%; L3 fresh = 99,843 civ; hardcore banner: loss wipes run back to L1.
- Boards: 49320 49276 49384 39160 21992 (L1-lineage, training, hardcore runs);
  inst2 45120 idle L3 E-zone reference board ($69). Fresh-board nav =
  scripts/launch_boards.py (MAP-COMPLETE layout: NORMAL(705,765) START
  OVER(705,926)).
- Zone tool = B (VERIFIED, arms wall-start prompt; fee on close; model draws
  rect from cell c to c+4).
## NEXT STEPS
1. Monitor Nn2Train1 (analysis/nn2_train1.log): round wins/meanfrac trend +
   ppo2 loss; commit logs every couple rounds, push milestones.
2. Next trainer downtime: to_planning() unpause probe (SPACE when counters
   frozen with zomb>0); stray-SPACE pause is the recurring wedge.
3. Escalate: wins at >=35% badge; boards rotate L1->L2->... via win ENTER
   chain; keep >=35% per level bar; BC from best episodes if PPO slow.
4. Watch ammo-cliff: mortars dry (no resupply) -> kills plateau late battle;
   model must learn heli/AC130 micromanagement (feature blob exists).
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
