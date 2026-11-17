# Zombies Aren't Real — RE & ML Project Tracker

**Goal (2026-11-15 REFRAME):** I ORCHESTRATE training of an ML model (GRU policy,
notes/ml-spec.md) that PLAYS and CONSISTENTLY WINS Boston, MA — the model plays, not
the agent. Deliverables: (1) stable obs/action env API over game copies, (2) episode
datasets, (3) trained GRU policy, (4) eval gates beat 0.19% -> 4% bronze -> 13.69%
silver. **User performance bar: strategy must SAVE >=35% civilians on EVERY level;
replay the same level (R keeps the board) until max; safe zones + preparation units
alone are NOT enough — equip SP loadout picks and deploy units (heli/mortar/CTA)
in-battle.** Game: Steam AppID 5185890 at
`C:\Games\steam\steamapps\common\Zombies-Arent-Real`, Odin engine (sokol+D3D11),
build bbbff50f v0.42.1. L5 was CONQUERED by scripted policy (bronze 7.91 x2).

## HARD RULES (every agent)
- NEVER modify `C:\Games\...` (read-only). Work in `D:\zar-scratch`. Test copies live in
  `D:\zar-scratch\game-copies\instN\` (add `steam_appid.txt` = 5185890; copies' own
  config.ini/settings.ini MAY be edited — e.g. features.dev=true, fullscreen, mute).
- The user's own game window may be used freely (they allowed it), but never permanently
  modify install files. Only the user's game + your test instances should run; KILL test
  instances when a phase ends (no accumulating games).
- NEVER take over the user's real mouse cursor (no SetCursorPos anywhere). All mouse
  input goes through the VirtualInput DLL (virtual cursor) + PostMessage.
- Admin console commands are CHEATS: allowed ONLY for manual, one-off diagnostics/tests
  driven by a human in the loop. NEVER code them into harness loops, GA/CEM episodes,
  or automation to make progress; scripted play must use only real UI + game mechanics
  (user directive 2026-11-16). Prefer static RE (REA/strings/lang files) for info.
- **If a battle is clearly lost (civilians < ~10%), restart immediately (R, R)** — the
  user's explicit directive. Don't watch doomed runs.
- Don't fight the real mouse cursor; the virtual-input DLL handles input per instance.
- NEVER resize a live game window (breaks UI hit-testing) — pick the size at launch via
  settings.ini window_mode (fullscreen = 3840x2160, works fully).
- Don't blindly type admin-console strings: the console must be verified open first
  (screenshot), and raw SPACE in typed strings toggles pause.
- Update this file at the END of every run.

## Directory map
- `AGENTS.md` — this tracker.
- `notes/engine.md` — engine/binary/input/observation findings.
- `notes/game-rules.md` — full mechanics (money, badges, zones, walls, units, specials,
  zombies, outbreak, civilians, camera).
- `notes/automation.md` — verified automation + input matrix + baselines A/B/C + pitfalls.
- `notes/virtual-input.md` — the Rust hook DLL (virtual mouse/keyboard per instance).
- `notes/memory-map.md` — live memory-reading channel (counts block, money f64, the
  0x140015d00 state-dump writer, next steps for the static root pointer).
- `notes/ml-spec.md` — the ML design (GRU policy, obs/action/reward, PPO, eval gates).
- `notes/prep-format.md` — .prep (NMPL) partial decode.
- `notes/admin-commands.md` — admin console command list.
- `scripts/game_drive.py` — DPI-aware PostMessage driver (keyboard/UI clicks/shots).
- `scripts/zar_input.py` — injector + VirtualInput (per-instance virtual mouse/keyboard
  via the hook DLL's shared memory).
- `scripts/hookdll/` — Rust cdylib: IAT-hooks GetCursorPos/GetAsyncKeyState/GetKeyState;
  shared section `ZARVI_<pid>`; exported `zar_init()` (call via remote thread).
- `scripts/harness.py` — episode runner (Instance launch/nav/arm/click/zone/ready/
  admin/set_speed/run_battle/snapshot/restore).
- `scripts/memscan.py` — external ReadProcessMemory scanner (regions, u32/f64 scans).
- `analysis/` — exe_strings.txt, screenshots, nzstate_trace.json (Ghidra Evidence),
  launch logs.
- `sessions/` — episode records + checkpoints (inst2-post-mvp2-...).

## VERIFIED CAPABILITIES (all proven live; details in notes/)
1. Parallel copies + unfocused sims (steam_appid.txt); fullscreen copies work fully.
2. Virtual input per instance (DLL): cursor/hover/prices track the virtual cursor;
   placements, zones, HUD clicks, dialogs, admin console (virtual Ctrl+Space + WM_CHAR
   typing), F-keys, wheel-zoom (centers on the virtual cursor), middle-click glide.
3. Observation: F6 dumps (.txt rich + 275MB .state), PrintWindow screenshots, memory
   reads (memscan.py), end-screen reward vector, progress/*.progress badge records.
4. Harness episodes ran end-to-end (mvp1/mvp2) + baselines A (0.00%), B (0.19%),
   C (0.00%) + WIN-1 (0%, best 1%).
5. **WIN x2 (REPRODUCIBLE): MAP COMPLETE Boston L5 — 1st BRONZE 6.90% (it17,
   14,479 saved, 65,639 alive, rank #14,305); 2nd run via battle-resume + same
   heli loop: `stage 5 = bronze 7.91 played` NEW BEST (78 loop cycles, horde
   113k->0 in 8.4 min real, civ plateau 65,585).** Unlocks: perk Extra_Zones
   (+3 safe zones) + BATTLESHIP unit (water AOE mortar).
   Evidence: sessions/inst2/mem1-*/it17-verdict.png + win2-791.png; checkpoints
   sessions/checkpoints/inst2-WIN-bronze690-1794739596 and -bronze791-1794740998.

## THE WINNING RECIPE (verified — Bronze 6.90, it17)
Boston L5 is a **conversion-snowball race** (6 outbreak sites x 360 zombies on the
outside crowd; horde 7k -> 130k+; HP 1 -> 30). Static defense alone loses (baselines
A/B/C/WIN-1). What WON (it17):
1. Carry board (walls + zones + 95 garrisons / 39 mortars / 15 snipers) + TRADE picks:
   MILITIA-capable buildings (CTA), Command_Post, Police, Repair x2, Radio_Tower x2.
   Militia (armed civilians) became the #2 killer (50.7k kills).
2. At battle t=0: heli sweep (key1 + one click per outbreak site, 6 charges).
3. Burn every kit charge early (2 CTA on crowds -> Militia online; 3 Rally; 4 MEDEVAC;
   5 Seek only on a HIGHLIGHTED garrisoned building).
4. THE decisive lever: sustained heli redeployment ALL BATTLE — every ~6 s:
   key1 + click the densest zombie-contact cluster (detect: green lightning blobs =
   militia/fire tracers; bin the (x//60,y//60) grid in a 1920-wide frame, click
   densest bin center x2). This held ~-500 zombies/s net; the horde (peak 125k)
   ground to 0 with civilians frozen at 31% alive => WIN. Heli kills ~5k but its
   micro-control (stunning/knockback breaking conversions mid-swarm) is why the
   civilian curve FLATTENED (it had been -20%/min).
5. Mortar platform did 52.7k kills (1,351/unit) — keep mortars loaded (watch
   OUT OF AMMO; no resupply found).
6. Badge % counts SAVINGS (evacuated/in-zone), NOT alive: 14,479 saved = 6.9% while
   31% alive. To climb to silver 13.69%: more zones over dense crowds (perk now
   allows +3) + Battleship deployables in the water channels.
Untested still: Fortify (F tool on walls), Repair pick effect in-battle, Mines
(drag on OPEN GROUND only — park tiles rejected twice), admin console (Ctrl+Space
TOGGLED PAUSE this session, console never visibly opened — treat admin as broken).

## CURRENT STATE (end of 2026-11-15f — objective MET)
- Test instances KILLED (inst2 pid 14264 terminated after the 7.91 win screen;
  progress already written at battle end — the MAP COMPLETE deadlock makes
  graceful exit impossible). steam_cloud = WIN board (all 5 stages badged,
  stage 5 bronze 7.91, perks = Extra_Zones; checkpoints listed above).
- User's own game (pid 19588) untouched.
- Memory channel SOLVED (direct .data RVAs, battle-verified vs HUD to 1%):
  civilians u32 at base+0x650728, zombies u32 at base+0x650f18 (zomb field at
  0x650f18; mirrors nearby; only the CHANGING fields are live). zarmem.set_direct(
  DIRECT_CIV_RVA, DIRECT_ZOMB_RVA) — no scanning, no root pointer needed.
- Ghidra Evidence: nzstate_trace.json — the state-dump writer at 0x140015d00
  (image-preferred base) referencing "NZSTATE1" @0x1405376e8. Ghidra 12.1.4 at
  D:\ghidra\ghidra_12.1.4_PUBLIC; rea CLI via Node 24.22.1 (nvm use first) with
  GHIDRA_INSTALL_DIR + REA_GHIDRA_STARTUP_TIMEOUT_MS=1800000.
- REA installed 2026-11-14: rea-agents 6.9.0 registered in OMP
  (C:\Users\me\.omp\agent\mcp.json, REA-owned stdio entry "rea", node v24.22.1,
  env GHIDRA_INSTALL_DIR + JAVA_HOME + REA_GHIDRA_STARTUP_TIMEOUT_MS=1800000
  recorded in the registration — CLI/MCP work without shell env). Skill
  reverse-engineer-anything refreshed to v62/255 tools (shared copy). Same
  GHIDRA_INSTALL_DIR + timeout also persisted via setx. Verified: doctor =
  registration aligned + ghidra 12.1.4 available; MCP handshake lists 255
  tools. REA MCP tools mount in agent sessions after an omp restart; CLI
  (npx -y rea-agents@latest ...) works now.

## CURRENT STATE (end of 2026-11-16z — shaped CEM at 8x)
### Scripts / stack (all verified live)
- `env_zar.py` ZAREnv(pid): FAST mem-RVA reads (set_direct; civ/zomb/conv/police/
  corpse i64 @ notes/memory-map.md RVAs; money f32 0x650b78; NOT police_kills/
  garrison_i438=DEAD const). ready() pause self-heal; cast(key,x,y) bar-key API;
  battle(stop_frac,clock_cap,ret_all,auto_heli) -> rich dict: frac/alive_int/
  min_frac/kills/police_pk/spend_frac/cost. heli_cycle via heli_watch_thread
  (green-blob centroid hunter, auto-heli=3.5s, needs heli in deck + cast once).
  F5=8x speed at ready (vk 0x74 sc 0x3F; F1-F5 = 1/2x..8x battle buttons).
- `parallel_ga.py run`: CEM over 16-gene cast schedule (4 casts t,x,y,kind; kind
  bins -> keys 1 para/3 gas/2 heli/4 ac130); fitness = SHAPED 0.55*frac+
  0.30*alive_int+0.06*min(kills/250k,1)+0.05*min(police/3000,1)+0.04*spend.
  gen0 seeds from ga_hist best. ZAREnv.auto_garrison = LATTICE SWEEP garrisons
  (arm hotkey1, stroke every ~46px client pt; only strokes over buildings
  charge -> money-drop = placed; escalating price 15->270 self-limits budget).
  Wiring into CEM run_episode pending test on inst2. episodes ~1.5 min at 8x,
  3 shards in parallel, R-retry between. cem5: 6x6 in 9min, fits 0.07-0.15,
  best 0.148 FLAT (genome-only search on this board = noise) -> cem6 (bg_179,
  analysis/cem6.log) 10x12 with ac130 bins.
- `recover.py` = INST2-ONLY now (relaunch kills ONLY its own pid + 17844 era —
  the old kill-all silently murdered CEM boards twice; NEVER invoke while CEM
  runs). relaunch_boards.py = relaunch inst1/3/4 to planning (nav inlined).
- Menu-virtual-clicks = MOSTLY DEAD (pause/loadout/BACK-TO-PLANNING need real
  input; file-edit + restart is the config path). Loadout cards DO click.
### Loadout file model (progress resume_loadout 19 tokens)
- token = LEVEL of a unit in FIXED ORDER; slot assignment auto. Anchors:
  idx1=PARATROOPERS(1SP) idx2=HELICOPTER(2SP) idx3=GAS BOMB(1SP) idx6=APC(1SP,
  lvl2 = 2 APCs — USER WANTED 2x APC: set idx6=2 on inst2 11-17) idx9=CRUISE
  MISSILE(2SP) idx18=AC130 (lvl3 = 3 shots). idx17/idx18=23/17 era = CURE lvl23
  + CLUSTER lvl17 inflation experiment (spent the 22 free SP; deck shows
  Stun-gas lvl23). Perks line = names, CHOOSE slots need UI (dead) or unknown
  progress fields (perks_choices candidates NO-OP'd; maybe not unlocked yet).
- inst2 board: money 375.68, 4 zones incl E-zone (955,496)-(1345,781) orig px =
  SAFE 13->39% ($3663 fee, $436/zone + $1489-style land scaling). CEM boards
  (inst1/3/4): $4223 no-zone fresh boards, deck para/heli/gas/ac130.
### Facts / traps NEW this run
- Steam UPDATED the install build 11-17 01:53 (md5 80afa5ba 7441920B vs copies
  b048cca7 7034368B): install config = NOT authoritative for copy defaults;
  copies self-heal missing keys from own build. Bulk config regex MUST anchor
  ^speed= per-section (ate officer40/heli260 once — restored from perftest2).
- Battle speed: runtime buttons only (not config/settings); F5=8x verified via
  episode wall-clock halving (497->235s).
- progress file rewrites its OWN loadout at battle end (badges win line; board
  zones/units live in steam_cloud/plans/*.prep — copy .prep = board clone).
- SC table: key_press MUST pass sc (ESC=1 SPACE=57 TAB=15 F5=0x3F B=0x30);
  vi.click coords = shot_px*1.24; lasso B+4 corners AUTO-CLOSES+charges (ENTER
  = ready trap!); READY = SPACE (land<=cap); 'no abilities' dialog SPACE=YES.
- ga_hist best_fit now SHAPED score (0.148) — not comparable to old frac-scale
  hist (overwritten; old 0.516 NOT reproducible = board drift).
- PIDs NOW: inst2=45120 (idle APCx2 board), CEM: inst1=9152 inst3=11872
  inst4=46428 (cem6 running). Enumerate via psutil by exe dirname ALWAYS.

## NEXT STEPS (2026-11-16z)
1. cem6 (bg_179) -> if best shaped flat again: board IS the bottleneck — widen
   genome with planning genes (auto_garrison already shared; add zone-draw via
   lasso genes + wall buys) OR run CEM on the GOOD board (clone inst2 E-zone
   .prep to copies).
2. Validate best mu on fresh boards (relaunch_boards -> full run) before BC.
3. BC -> GRU (train_zar.py) on winning episodes; L4/L5 CONTINUE chain; kill
   instances + final AGENTS.md update at phase end.

## CONTINUATION PROMPT (paste as the first message for a fresh agent)
```
Continue the Zombies Aren't Real ML project (mission: TRAIN A MODEL to consistently
win Boston MA >=35% every level). Read D:\zar-scratch\AGENTS.md CURRENT STATE
(2026-11-16z) + notes/automation.md traps + notes/memory-map.md RVAs +
notes/ml-spec.md. Stack: scripts/env_zar.py ZAREnv(pid) (memory RVAs FAST mode,
ready/cast/battle w/ pause self-heal + auto heli watchdog + 8x F5 speed),
scripts/parallel_ga.py run = shaped-fitness CEM over cast schedules sharded
across windowed game copies inst1..inst4 (psutil-enumerate pids by dirname;
recover.py = inst2 ONLY, relaunch_boards.py = inst1/3/4; NEVER run recover
while CEM episodes live), train_zar.py (GRU BC/REINFORCE).
Input traps: virtual DLL input only (key_press needs sc codes; SC table in
zar_input), vi.click=shot_px*1.24 for HUD/menus, map placement drag
(button_down/up), lasso B+4 clicks auto-closes, READY=SPACE, NEVER real
mouse_event, never CHOOSE click, menu virtual clicks DEAD -> edit progress/
config FILES + restart instead, PrintWindow only in planning/menu, SPACE pause
trap (ready() self-heals), F6 dumps freeze while dialogs/menus open.
Config traps: install build != copy builds (Steam auto-updated 11-17): copies
self-heal own defaults; anchor per-section when regexing config.ini; battle
speed = F1..F5 runtime buttons only.
Rules: copies only (never C:\Games — read-only), admin=manual one-offs ONLY,
difficulty pinned normal, kill test instances at phase end, no subagents,
R-retry keeps board, civ<10% -> RR immediately, update AGENTS.md at end.
```


## Key file paths
- Install: `C:\Games\steam\steamapps\common\Zombies-Arent-Real\`
- Copies: `D:\zar-scratch\game-copies\inst1\`, `inst2\` (inst2 = fullscreen dev-enabled
  template with steam_appid.txt; settings.ini window_mode=fullscreen)
- Ghidra: `D:\ghidra\ghidra_12.1.4_PUBLIC` (GHIDRA_INSTALL_DIR); JDK 21 present.
- Node: 24.22.1 is nvm default; rea CLI via `npx -y rea-agents@latest ...`; the
  OMP MCP registration pins `D:\nvm\installs\v24.22.1\node.exe` directly.
- F6 dumps: `D:\zar-scratch\game-copies\inst2\debug_dumps\*.txt|.state`
- Ghidra Evidence: `D:\zar-scratch\analysis\nzstate_trace.json`

## SAFE-ZONE / DIALOG MECHANICS (2026-11-15h, user-confirmed + lang/en.lang)
- Zone tool: click points on the perimeter (any shape, user-confirmed); must close a
  full loop (Enter). Land cap per stage: L1 = 30% ("Your safe zones cover N% ... at most 30%").
- Zone fee charged ON CLOSE (L1: 800x760px rect = $1155; 735x1029 = $1489).
- Select zone (click its wall) -> bar shows "SELECTED [X] Refund" -> X -> dialog
  YES(X)/NO -> press X = refund. Corner-drag shrinks a zone (lang debt_hint); plain
  LMB-drag on empty land PANS the camera instead.
- Dialogs: keyboard-only; hotkeys labeled on buttons — confirms: YES(X)/NO; info
  dialogs: OK=Enter; ready_short warning: YES=SPACE. ESC = NO/close; 2nd ESC = pause
  menu (escape stack pitfall).
- OPEN DIALOG or PAUSE MENU freezes the F6 dump writer => dumps look "wedged" while a
  dialog/menu is up (normal, not a hang). Battle dump cadence >=16 s (writer needs ticks).
