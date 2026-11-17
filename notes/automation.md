# Automation interface — verified 2026-11-17

## Current v3 input contract
Use only VirtualInput + PostMessage. No physical cursor input, admin-console
commands, or writes to the installed game. Work in game-copies/instN.

The handoff's absolute-RawInput-only menu claim was contradicted by isolated live
tests: raw-only events incremented raw_sent but did not move the world cursor,
purchase anything, or boot the menu chain. Posted-only clicks with the DLL virtual
cursor reached planning and bought a garrison. The old web-layer, phantom-row,
pump-lottery and dead-menu theories are withdrawn.

Two v3 defects beyond the already-fixed version gate were corrected: the client
stored screen coordinates in client fields, and raw records used the wrong ABI.
Win32 x64 mouse RAWINPUT is 48 bytes with a 24-byte header; RID_INPUT=0x10000003,
RID_HEADER=0x10000005. Tests pin these constants, layout and client coordinates.

All mouse button gestures now share ONE posted edge path. Shared buttons supply
polling hooks; the single-owner raw pump emits compatibility movement only.
GetCursorPos converts virtual client pixels to screen pixels with ClientToScreen.
Drag sends held-button moves and releases in finally. No desktop input is sent.

| Surface/action | Verified path | Evidence |
|---|---|---|
| Play Now / CAMPAIGN / START OVER | Virtual cursor + posted mouse movement/edges | Fresh L1 $3111, 8142 civilians, planning dump |
| World garrison | Key 1 + vi.click | Exactly 1 garrison, $3111 -> $3037.80 |
| Safe-zone polygon | B; press at each corner; Enter | Four segment drags: $3037.80 -> $2247.10, 22 wall records |
| Wall | Z; start press, movement, end press | Drag + endpoint click: $2247.10 -> $2189.93, walls 22 -> 23 |
| Single freehand stroke | Does not commit zone/wall in this build | Corner/end presses are required |
| Wheel | vi.wheel(+1/-1), WM_MOUSEWHEEL | Zoom .5795 -> .6374 -> .5795; world cursor unchanged |
| READY confirmation | SPACE; second SPACE only if zombies remain zero | Zombies >0; blind second SPACE can pause |
| CONTINUE from partially cleared campaign | Layout chosen from progress; virtual click | L5 planning in both 1920x1200 and 3840x2160; 209867 civilians |
| Restart confirmation | Existing env.to_planning() R loop | Planning, placements and budget retained |
| READY NO dialog button | vi.click at client fraction (.59,.567) | Covered by the acceptance suite; other dialogs use their bound keys |
| Raw-only menu/world mouse actions | Not the supported action path | Isolated tests produced no successful action |

A segment drag starts with a press, which supplies a polygon corner. Four such
segments plus Enter are a polygon, not a continuous freehand lasso. Do not add raw
wheel: posted wheel passes the anchor check. Win32 raw wheel is usButtonFlags
0x0400 plus signed usButtonData; 0x0010 is middle-button-down, not wheel.

## Native evidence for the input routing
REA/Ghidra decompiled the window procedure at 0x1404b96f0. Its WM_INPUT branch
runs only when the byte at RVA 0x68e6b9 is nonzero and processes movement, not
button or wheel flags. WM_MOUSEMOVE runs with the opposite gate. Posted button
and wheel handlers are separate. A live read of the gate returned zero.
This static control flow corroborates the isolated runtime surface audit; it is
not itself a runtime trace. Evidence IDs:
- ev_bc8fd5105c5ededb4956c0d819b6d220656752c11630d0f72dc56f6cdf7783f2 (PE imports)
- ev_74ec6864cc3252a41cb4ce894dff336311bdcc018c1f4b5e146fe0380a77f533 (raw IAT xrefs)
- ev_eceeb8e5c5bff6861e26aef51bc7529d345104781444786ac87dea164978be5a (window procedure)
Saved complete Evidence is under analysis/interface-*.json. The one-shot CLI
sessions completed and released their engines; no persistent MCP session was opened.

## Coordinates, keyboard, and state
- GetClientRect supplies physical client pixels. Menu coordinates are fractions:
  1920x1200: PlayNow (.4245,.844), CAMPAIGN (.207,.368), START OVER (.451,.738).
  3840x2160: PlayNow (.453,.709), CAMPAIGN (.16,.454), fresh-play (.286,.454).
  Partially cleared campaign: START OVER/CONTINUE are (.446,.592)/(.446,.663)
  windowed, and (.286,.356)/(.286,.394) fullscreen; difficulty rows are absent.
  English UI scale 1 is calibrated; other client sizes fail loudly. The layout
  does not scale using one universal fraction set. A completed campaign shows
  PLAY NOW in place of the start/resume pair when resume_stage is zero.
- Scan codes: SPACE=57, ENTER=28, ESC=1, R=19, F6=64. Stray SPACE toggles pause.
- F6 writes only in-world. Menu/dialog silence is not proof of a hang. Filenames
  have one-second precision; wait >=1.1 s between snapshots to avoid overwrites.
- Fresh dump phase/economy/view is acceptance truth. obs() counters can describe
  a world behind a menu. obs().money can select a stale positive mirror: measured
  2247.10 while fresh dump money and RVA 0x65d9c0 were 1573.65. Use dump economy
  for receipts. Existing env_zar.py and trainer public APIs remain unchanged.
- Normal settings are reported as difficulty=Adaptive, hardcore=false,
  ultra_hardcore=false, assist_level=0. Tests use F1 for 1x sim speed.

## Shared section and injection
ZARVI_<pid> is 0x100 bytes, magic 0x5A415249, version=3 at 0x04. Creation and
validation use one native VERSION constant; Python validates it before enabling.

| Offset | Field |
|---|---|
| 0x08 | enabled |
| 0x0C / 0x10 | signed CLIENT x / y |
| 0x14 | button bits left=1, right=2, middle=4 |
| 0x18 | keys[8], u32 bitsets |
| 0x38 | lock-key toggles |
| 0x3C | heartbeat |
| 0x40 | patch_count; 4 for this binary, GetKeyboardState is not imported |
| 0x48 | u64 raw_hwnd |
| 0x50 | raw_sent: emission count, NOT proof of consumption |
| 0x54 | primary monitor width |
| 0x58 | last abs-normalization failure: 1 metrics, 2 ClientToScreen |
| 0x5C | pump tick counter |
| 0x60 | reserved |

vi.diagnostics() returns these fields. VirtualInput(pid, inject=True) first reuses
an existing valid section. New injection acquires sessions/.zarvi_<pid> exclusively;
a failed injection requires a process restart, never reinjection. PID reuse is
checked against creation time. Remote thread waits are bounded to 15 s. Native
initialization is idempotent; external shared-state reads are volatile snapshots.
Rename the old target/release/hookdll.dll before cargo build --release, then
restart owned copies to load the new image. Never re-inject a mapped DLL.

## Boot and tests
```python
from zar_boot import boot, stop
env = boot(r'D:\zar-scratch\game-copies\inst4', ('campaign', 'stage1'))
try:
    assert env.phase_now() == 'planning'
finally:
    stop(env)
```
boot refuses foreign/busy directories and non-normal settings. It launches detached,
waits <=90 s for a window, injects once, waits until 75 s after launch, navigates,
then verifies Boston/stage/planning and fresh L1 money/civilians. It sends ENTER
only if world civilians are still zero: when START OVER enters planning directly,
an extra ENTER opens READY and blocks F6. One ESC may close a world modal before
verification is retried. Failed boots kill
their owned process and report the step plus section diagnostics. An ESC fallback
runs only after failing to enter the world: unconditional ESC backs out of a clear
campaign page. Environment attachment is serialized around the existing memscan
ctypes signature; launch and menu navigation remain concurrent.
Destinations: ('campaign','stage1') and ('campaign','continue'); other destinations
fail before launch. CONTINUE requires a partially cleared campaign (1-4 badges);
completed and zero-badge saves are rejected before launch for this destination.
Boot reads progress to choose the layout; it never changes or unlocks progress.
Continue invokes to_planning when needed. Verify live coverage in tracker.

```powershell
$zarPython = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
& $zarPython -B -m unittest discover -s scripts -p 'test_zar_*.py'
cargo test --manifest-path scripts/hookdll/Cargo.toml
& $zarPython -B scripts/test_interface.py --copy inst4 --repeat 2
& $zarPython -B scripts/zar_boot.py inst1 inst2 inst3 inst4
```
Acceptance logs: analysis/interface-<timestamp>.log, PASS/FAIL table, nonzero failure
exit. The parallel CLI checks all worlds coexist in planning, then kills its games
in finally. Missing copies are cloned from inst4 including steam_cloud. It refuses
busy copies. Neither script takes screenshots or uses console commands.

Inst4's badges were intact (39.23, 34.31, 21.14, 13.69, 7.91). Backups before scale
are in analysis/interface-progress-backups; no badge restoration was needed.
Evidence: analysis/interface-*.log and interface-{pe-imports,raw-xrefs,raw-consumer}.json.
Final results and process inventory: notes/tracker.md.

## Historical game observations
The following preserves prior battle/mechanics evidence. Current interface guidance
above supersedes historical input claims. Console experiments below do not authorize
console use in automation or acceptance tests.

## FREE PLAY path — VERIFIED LIVE (2026-11-15, inst2 pid 10100)
Navigation (virtual input, all unfocused): globe home → click FREE PLAY → list.
The Free Play tab holds:
- **SANDBOX MODE toggle** (OFF/ON badge on the row).
- **MUTATORS** button (built-in mutator list; config-override files).
- **ADD NEW MAP** (custom-map dialog).
- **CAMPAIGN MAPS** list: all 13 campaigns; Boston highlighted with progress dots.

### Sandbox OFF (normal Free Play) vs Sandbox ON — VERIFIED states
- **Sandbox OFF**: campaign maps share the CAMPAIGN tab's progress and saved board.
  CONTINUE (LEVEL 5) on Boston resumed the *identical* stage-5 session as the Campaign
  path ($27,047 + carried loadout Police/Heli, 0 SP LEFT — same carry, same plans/*.prep).
  Progress panel shows "STATUS: 4 OF 5 CLEARED", CONTINUE HERE at 5, START OVER button.
- **Sandbox ON**: progress panel switches to the SANDBOX context — "STATUS: NOT STARTED",
  LEVEL 1 "not played", **LEVELS 2-5 UNLOCKED** (no campaign locking), button becomes
  **PLAY NOW** (plays the level row selected in the panel: click a level row, then PLAY NOW).
  Entering Boston L5 this way gives: **SANDBOX badge top-left, "$ UNLIMITED", 99999 SP LEFT,
  fresh empty board, LEVEL 5/5**, same map/civilians/4%-win banner. Sandbox progress is
  separate from campaign progress (steam_cloud/sandbox/ folders per config paths).
- Sandbox was toggled ON then back OFF live via virtual clicks; state restored to OFF.

### Menu navigation
Current interface guidance above supersedes these historical observations.

### Harness implications
- For ML episodes on Boston L5 with the REAL campaign rules: use the Campaign tab path or
  Free Play with sandbox OFF (identical state).
- For unlimited-resource exploration/imitation data: Free Play + SANDBOX ON → fresh board,
  unlimited money/SP, all units — ideal for generating expert demonstrations.
- MUTATORS on the Free Play tab enable training variants (e.g., Tough Horde) per run.

## BASELINES measured on Boston L5 (2026-11-15, inst2; fresh "reset scenario" start)
- **A: no defense** (1 stray unit, no zones): LOSS, 0.00% saved.
- **B: zone (1,860x1,733 m over the densest downtown cluster, 9% civilians sheltered) +
  6 Turrets + 1 Mortar + full free carry (95 garrisons, 15 snipers, 39 mortars) + ALL battle
  deployables spent (6 Helis, ~19 Paratrooper squads)**: LOSS, **0.19% saved**
  (SAVED 409 / 209,867; SURVIVED 13:35 sim; ZOMBIES KILLED 207,134).
  End-screen accounting: MORTAR 79,588 kills ($0.05/kill, best money-kill), HELICOPTER
  75,196 (12,533 kills/unit — best unit), GARRISON 40,252 ($0.27/kill), SNIPER 4,447,
  TURRET 4,392 ($0.12/kill), POLICE 2,915 (100 officers sent by a Police-station special
  building inside the zones), PARATROOPERS 344. Walls valued $7,756. Defenses value
  $23,873 (the carry is most of it), prep spent $4,333, unspent $2,271, loadout 31/31 SP.

### THE STRATEGIC INSIGHT (drives the ML design)
Boston L5 is a **conversion-snowball race**: 2,160 starting zombies bite civilians, each
converts in seconds, zombies go 7.7k -> 31k -> 67k -> 124k within ~10 sim minutes while
zombie HP grows 1 -> 15+. Perimeter defense + gradual attrition LOSES: the horde
out-breeds any static defense. What wins (hypothesis to verify with the ML/heuristics):
1. **Kill the initial outbreak hordes FAST** — first ~2 sim minutes decide everything
   (conversions are exponential; zombie HP is still 1-2 then).
2. Concentrate burst DPS at outbreak clusters the moment they appear (battle HUD shows
   green clusters): Helicopters (12.5k kills/unit), Mortar barrages, Paratrooper squads.
3. Zones still matter (shelter the bronze 4% line safely), but as a BACKUP for the
   survivors, not as the primary wall-attrition plan: the carried 3 zones held 3%.
4. Police-station special buildings inside zones send 100 free officers (2,915 kills).
5. Cost/kill leader board: Helicopter (SP, ~free per kill) >> Mortar ($0.05) >> Turret
   ($0.12) >> Garrison ($0.27) >> Sniper ($0.18, low volume).

### Harness gaps found during the baseline (fix before ML runs)
- Speed buttons ("1/2x..Dev 8x") — virtual clicks on them did nothing twice; use F-keys:
  F4 = 4x verified, F5 = dev speed (set 4x on first press; investigate), or admin console
  "game speed 8" in PLANNING (battle-phase console open not yet verified via virtual
  Ctrl+Space; blind typing without a confirmed console is DANGEROUS — a raw SPACE in the
  typed string toggles pause).
- Turret/Mortar tool clicks need BUILDING/open-ground hits: at zoom ~0.15 about 40% of
  blind grid clicks miss; place with pixel-detected building centroids or zoom in more.
- Ctrl+Z undo removes EVERYTHING back to episode start (24 undos wiped our zone) —
  count undo steps or snapshot before planning.
- Battle deployable slots (1..7) select fine; each click spends stock (Paratroopers x380
  count) — stock counts visible on the battle bar; cooldowns show on the slot (Heli 0:26).
- **C: carry-only (no new zone), READY immediately, Paratroopers dropped on all 4 outbreak
  clusters within the first ~15 sim seconds + 1 Heli + 2 squads via the managed loop**:
  LOSS, **0% saved (0/209,867)**, SURVIVED 9:08 sim, ZOMBIES KILLED 200,062.
  Kills: MORTAR 133,228 ($0.03/kill!), GARRISON 57,869, SNIPER 4,655, HELICOPTER 2,141,
  POLICE 2,114, PARATROOPERS 55. Walls (carried) $5,011 — all breached by the end.

### Baseline conclusions (A 0.00 / B 0.19 / C 0.00 — all losses)
- The conversion snowball beats ANY of these plans: zombies 7k -> 130k in ~2 sim minutes.
- B's extra zone (+6% sheltered) + turrets bought only 409 extra survivors (0.19%) —
  its wall was breached in ~1 sim minute by the nearby outbreak horde.
- The 3 carried zones shelter 3% and held ~9 sim minutes before falling.
- To actually WIN (>=4% alive + horde wiped), candidate strategies for the ML to explore:
  * FORTIFY the carried walls hard (F x4 = 24x HP) — expensive but the horde chews
    through level-1 walls in minutes; fortify multiplies wall survival time ~24x.
  * Kill-focused plan: more mortars ($114 each, $0.03/kill — cheapest kills) spread over
    the whole stage + heli/para stock on clusters; zones only for the final 4%.
  * Repair buildings (TRADE->REPAIR pick) inside zones heal walls 40 HP/s — pair with
    the police stations already inside the carried zones.
  * The ML agent's edge must come from DYNAMIC management: deployables on the biggest
    clusters every recharge, wall repair, and zone placement — not static layouts.
- Battle-phase admin console via virtual Ctrl+Space NOT yet verified (planning verified);
  blind typing is dangerous (raw SPACE toggles pause). Verify console state by screenshot
  before typing commands in battle.

## Additional battle findings (2026-11-15 late sessions)
- **WIN-1 (sustained helis + 10% zone + 28 turrets + carry)**: LEVEL FAILED, 0% saved
  (best 1%). Helis redeployed on cooldown killed 29.7k (4,951/unit) — mechanically the
  redeployment works, but the zones fell anyway; the horde (health 30, 28k) chewed through.
- **The user directive (strategy):** if the civilian population clearly collapses
  (< ~10%), RESTART immediately (R key: "Keeps your placements, loadout and leftover
  budget") instead of watching a doomed run. Implement in the harness: track civilians
  live (memory channel, notes/memory-map.md), RETRY at < 10%.
- **RETRY loop is productive**: breach RETRYs accrue UNLOCKS (earned "MINE FIELD" $75
  after the wall breaches; unlock order in unlocks.ini; breach_restarts_per_unlock = 2).
  RETRY keeps placements + loadout + leftover budget → iterate: read the breach marker
  flags (red rings on the walls, visible in planning), reinforce exactly there, retry.
- **Tool arming pitfalls (verified)**: after drawing a zone, KEY tool-switching (4) fails
  silently — the zone tool stays armed and further clicks draw zone corners (costly!).
  Arm tools via HUD row clicks ([B]/[2]/[4] rows) — positions on the 3840x2160 layout:
  DEPLOY column rows at x 25-530: [1] y≈1853+42n... measure per screenshot. BUILD column
  ([B] Safe Zone) at x 1147-1547, y≈1851. Verify arming by screenshot before clicking
  the map. Ctrl+Z undo removes EVERYTHING (nuclear) — prefer refunds/redo over undo.
- **Turret cost escalation**: turret price grows per copy on board (~+$15/copy: 28
  turrets cost $8,837 total). Budget placements accordingly; money can go NEGATIVE
  (debt) — READY still works, debt only matters in planning.
- **Camera control (battle, verified mechanics)**:
  - wheel-zoom centers on the GAME cursor (GetCursorPos → virtual cursor): move_to the
    target THEN wheel. lParam = SCREEN coords; wparam = delta<<16 (positive = in).
  - NEVER send wheel with a negative delta computed as `(-120)<<16 & 0xFFFFFFFF` — it
    becomes a huge unsigned wparam and wild zoom-outs happen (this looked like "camera
    hopping" to the user).
  - middle-click (WM_MBUTTONDOWN 0x207 / UP 0x208) glides the camera to center the
    clicked point (camera.glide_speed) — use it for smooth recentering.
  - Set zoom ONCE (2-4 wheel steps ≈ street level) and keep it; glide between clusters.
- **Fullscreen works**: settings.ini `window_mode = fullscreen` (in the copy) → 3840x2160
  creation-size window; menus, planning HUD, battle HUD all render and receive virtual
  clicks correctly at creation size. RESIZING a live window breaks UI hit-testing
  (0-pixel diff after clicks) — never resize after launch; pick the size at launch.
- **The user watches the game**: keep at least one instance visible; camera should
  FOLLOW the action (glide/zoom to the fight) for observability; don't let it affect play.
- **Arena note**: the sim's heap arena addresses move between launches (0x8fb… vs 0x2245…)
  and on mass-death compactions within a battle — memory readers must re-validate or use
  the static root pointer (notes/memory-map.md).

## Battle-loop ops (verified it2-it9 sessions)
- Start from planning: SPACE usually works but was IGNORED once (it8, focus?) — ROBUST:
  click READY row at physical (3648,1955) -> abilities dialog -> click YES at physical
  (1691,1157) -> click "Dev! 8x" at physical (3700,2087).
- End screen: red "LEVEL FAILED N% saved" title; detector = red-pixel count > 700 in
  preview region rows 315-360 x 800-1150 (true frame measured 1570). Progress file
  rewrites on LOSS too — mtime is NOT a win signal.
- Pause menu (ESC or stray key) ignores keys; click RESUME at physical (1348,262);
  detect via bright-logo pixels rows 30-80 x 700-1200 > 2500.
- it2 full-battle telemetry (Dev 8x ~75 s real): LOSS 1% (790 saved) NEW BEST; kills
  mortar 114k / garrison 66k / heli 20k (6 helis) / para 165 / walls 165; horde 200k+
  hp 25-30. First-strike alone is not enough; needs survivability (zones/walls/mines/
  repair) AND early horde suppression while hp=1.
- Memory reader (scripts/zarmem.py): planning calibration (u32 209867) -> ~60 candidate
  triplets; mid-battle DIFFERENTIAL prune (value MOVED since last poll) isolates the live
  block; frozen mirrors (60 copies incl. the 6 per-roll snapshots) never move; blacklist
  caught-frozen addresses; full rescan masks must exclude coord-triple garbage
  ([x][0][z] arrays pass naive masks by the millions).
- memscan.module_base(): K32EnumProcessModules + K32GetModuleInformation (Toolhelp
  MODULEENTRY32W fails ERROR_BAD_LENGTH under ctypes); find_u64 added for pointer scans.
- Xrefs to the state-dump writer 0x140015d00 (rea CLI): 0x14036298b, 0x14045fbe3,
  0x1407333f0 (analysis/xrefs_dumpwriter.json) — being decompiled for the root pointer.

## IT17 — THE WIN (2026-11-15, Boston L5 MAP COMPLETE, bronze 6.90%)
- Board: carry (walls/95 garrison/39 mortar/15 sniper) + picks Militia-capable bldgs
  (Command_Post 606, Police 453, Pharmacy/Grocery REPAIR), + $90 six turrets on
  breach-wall BUILDINGS ("TURRET: CLICK A BUILDING" — open-ground clicks rejected).
- READY (SPACE->YES), then t=0: key1 + 6 clicks on outbreak sites (one charge each);
  burned CTA (Militia online — 50.7k kills by end, #2 killer), Rally, MEDEVAC;
  Seek needs a HIGHLIGHTED garrisoned building else it STAYS ARMED and eats the next
  click (this trap cost two Dev8x attempts — RMB right-click cancels tools).
- Then THE LOOP for the whole battle (~25 min real @1x): every ~6 s green-blob
  detect (g>170,r<120,b<120 in 1920-wide frame; 60px bins; densest bin center x2 =
  physical) -> key1 + click. Net horde drain ~-500/s from 125k peak to 0.
  Civilians froze at 65,639 alive (31%) — heli swarm-control suppresses conversions
  (the -20%/min curve flattened within a minute of starting the loop).
- Result screen: MAP COMPLETE, BRONZE 6% saved NEW BEST, SAVINGS 14,479 (=6.9% =>
  badge counts SAVINGS/evac, not alive), unlocks Extra_Zones perk + BATTLESHIP.
- HUD speed buttons: 1x stayed green through every click attempt on the
  2x/4x/Dev1&X rows (physical x3714, y2051/2095/2139) — mouse speed switching
  unreliable; admin Ctrl+Space TOGGLED PAUSE (console never visibly opened).
  1x + the loop is fully winnable; skip speed entirely.
- Memory: zarmem.set_direct(DIRECT_CIV_RVA=0x650728, DIRECT_ZOMB_RVA=0x650f18) exact
  all battle (see memory-map SOLUTION).
- DEADLOCK: game wedges ("Not Responding", PrintWindow blocks) ~1-2 min after the
  multi-dialog MAP COMPLETE screen (twice). progress is already written at battle
  end -> taskkill + relaunch + nav (SPACE/Enter chain, CONTINUE resumes board).

## Replay win (2026-11-15f): REPROducible => bronze 7.91 NEW BEST
- After kill+relaunch, campaign CONTINUE AUTO-RESUMED the battle from a mid-state
  snapshot (133k civ / 113k zomb at loop t=1s); the identical 6s green-blob heli
  loop ground 113k->0 in 8.4 min real (78 cycles) with civ plateauing at 65,585;
  progress rewrote to `stage 5 = bronze 7.91 played`.
- Loop end-detection = 4 consecutive static (mean abs diff < 0.5) polls at 1920/4
  downsampling; telemetry timeline = (ts, (civ,zomb), blob-target) per cycle.
- => recipe robust across starting states; battle-resume is a usable harness
  primitive (mid-battle episode starts!). Checkpoint inst2-WIN-bronze791-1794740998;
  screen win2-791.png.

## 2026-11-16r — env_zar/ZAREnv + parallel search traps (all live-verified)
- `scripts/env_zar.py` ZAREnv(pid): obs via RVAs (see memory-map.md), ready(),
  cast(bar_key,x,y) (battle-bar hotkeys '1'-'6','T'), battle(policy) w/ early-stop.
  ZarGame restored in same file for recover.py's make_game imports.
- Historical input assumptions are superseded by the current matrix above.
- PAUSE trap: any stray SPACE at battle start toggles sim pause (counters frozen,
  cpu ~20%, looks alive). env.ready() now verifies tick movement and presses SPACE
  to self-heal; battle() presses SPACE after 3 static polls. ALWAYS gate on tick.
- PrintWindow screenshots: planning/menu states ONLY (battle deadlocks); run in a
  watchdog thread (<=18s join).
- Campaign screen: difficulty NORMAL -> CONTINUE (LEVEL 3) green button; clicking
  HARDCORE switches the panel (PLAY NOW = fresh run-from-1 w/ own progress).
  Client px for CONTINUE(LEVEL3) on inst1 windowed: (857,976).
- Cure economy: unlocks t=45s; Lv3=3 charges (SP). Spread contact p=0.5/0.5s vs
  cure cloud r20 10s => one cast cures a whole horde (cascade, 7k->0 in ~70s in
  admin tests). Legit cast timings t=48 at south sites saved 3.9% (battle4/5);
  outbreak crowds start OUTSIDE walls; battle dies ~4% with no defense (~100s).
- Mines at $15x n: single button_down/up at client px placed nothing (money
  unchanged) — needs a verified placement gesture, unresolved.
- `scripts/parallel_ga.py`: CEM over 3-cast schedule genome (t,x,y,kind),
  episodes sharded across game instances (multiprocessing; parallel across pids,
  sequential per pid); lost battles auto-return via R(retry). NOTE: each retry
  permanently shrinks civ0 (99k->80k->66k->64k observed) — frac normalized per
  episode but absolute difficulty drifts (easier crowds).

## Boot blocker diagnosis (2026-11-17)
The failed parallel probes were not a focus or long-key-hold problem. A one-off
PrintWindow capture (analysis/interface-blocking-surface.png, ignored artifact)
showed the READY confirmation over a fresh L1 board. The unconditional ENTER
following a direct START OVER had opened it. ESC restored F6 immediately.
The boot and acceptance scripts do not capture images.

## Acceptance evidence (2026-11-17)
- Final mouse implementation: interface-20261117-094110.log, two consecutive
  fresh cycles; 1 garrison, 22 polygon walls + 1 wall, exact purchase receipts,
  zero wheel-anchor drift, battle start and R recovery, cleanup after each.
- Fullscreen fresh boot: interface-fullscreen-boot.log; CONTINUE in both layouts:
  interface-continue-final.log. One-off PrintWindow captures calibrated layout
  differences; boot/test code is entirely screenshot-free.
- Eight offline Python checks and one native ABI/layout test:
  interface-unit-tests.log. No model/trainer tests are implicated by these changes.
- Four simultaneous worlds: interface-scale.log; final mixed-layout proof:
  interface-scale-final.log. Failed exploratory runs are retained and superseded
  by these named passing logs, not erased from the evidence trail.

## Training HUD overlap reproduced (2026-11-17)
Two-worker schema3 launch6d87b2cdf039 stopped with `Loadout did not open` on
inst1 after saving a valid update from inst2. Replaying policy seed20261117 on
owned inst1 PID22648 reproduced the failure. PrintWindow showed the low-safe-zone
READY confirmation, while native phase remained planning/app2. Grid row5 clicks
Y912 reach the HUD (map ends near Y846), so a geometry endpoint could hit READY.
WORLD_CELLS now masks cells40-47 for spatial actions and building availability;
existing cell meanings/weights remain unchanged. Two regression tests failed
before the fix and pass afterward. Failure screenshot: ignored
visualizer/runtime/loadout-failure.png. Known dialog was cancelled with its NO
button during diagnosis; no automatic battle start was used to hide the problem.

## Native negative money (2026-11-17)

Safe-zone placement can overdraw the planning balance. In owned inst1 session
`logs/bbbff50f-BM-1-2.jsonl`, placing a 550-cell safe zone was followed by a
planning footer with `stats.money = -734`. This is a valid game balance, not
a failed memory read. `ZAREnv.money()` preserves signed finite balances within
the existing magnitude bound; never substitute stale positive mirrors or zero.
The regression covers debt, NaN, infinity and both magnitude limits.
