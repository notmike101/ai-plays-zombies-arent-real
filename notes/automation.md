# Automation design (VERIFIED + planned) — updated after live probe session


## UI/INPUT TRAPS (2026-11-16, all proven painfully)
- The game IGNORES real mouse entirely (raw-input): NEVER mouse_event/SetCursorPos at it;
  use the DLL virtual cursor + vi.click (PostMessage client px, png(1942x1256)−(11,40)).
- Real mouse_event left the game stuck-button-wedged twice; 100%-1core spin + PrintWindow
  hangs 15-180 s = UI thread dead. Kill+recover to fix; observation stays exact via memory.
- PrintWindow (harness.grab) deadlocks whenever the UI thread is wedged: ALWAYS wrap in a
  watchdog thread with ~12-18 s timeout; never block the pipeline on a screenshot.
- The admin console opens ONLY via virtual-modifier combo:
  vi.combo_press([VK_CONTROL], VK_SPACE, sc=57) while RUNNING; PostMessage ctrl+space is
  NOT seen (old zarmem.admin_command = hotkey-storm + pause; don't use it).
  Then type chars via WM_CHAR + Enter via WM_KEYDOWN/UP 0x0D. 'cure here [r]' etc. run.
- Keys need window ACTIVE? no — PostMessage keys work unfocused EXCEPT during loadout screen
  (READY inert) — press Tab to open LOADOUT, click BACK TO PLANNING (client 197,789) first.
- CLICKING a LOADOUT '+CHOOSE' card wedges the UI thread (popup modal vs PostMessage input):
  never click CHOOSE; set levels via progress-file resume_loadout (idx15..21 = battle keys
  1..6,T; level int). Default ability assignment by unlock order — on this save:
  slot3(idx17)=Cluster bomb, slot4(idx18)=Cure. Cure Lv2 = 5 SP/level x2 = 10 of 18 SP.

## LEGIT CURE ECONOMY (rules for the ML goal — no admin casts in real runs)
- [cure] config.ini: unlock_seconds=45 sim-s after outbreak, arrival_seconds=12, sp_cost=5
  per level (adds charges), cooldown 0 (charges finite), cost in $? per cast scales with
  cured-pile density x contact_radius^2; cloud radius 20 m; spread: spread_seconds/
  contact_radius/spread_chance/max_generations; wane_seconds burnout. All hot-reloadable
  via config.ini (copies only!) — for EXPERIMENTS; winning runs must stay in-game legit.
- Admin 'cure here 300' discovery runs killed 42k zombies in 2 min — cure cascade scales;
  the LEGIT cast = bar key '4' click on horde pixel, 2 charges at Lv2.
- Battle outcomes observable: zomb→0 = horde wiped (win check), civ = saved count; L3 crowd
  99,843; badges from progress/*.progress (L1 emerald 39.23, L2 diamond 34.31, L3 silver
  21.14, L4 silver 13.69, L5 bronze 7.91 already banked — resume_stage=3 board $4,223 13%).
## INPUT CAPABILITY MATRIX (verified on inst2, Boston L5 planning, DPI-aware driver)
| Action | Works via PostMessage? | Notes |
|---|---|---|
| Plain keys (Space/Enter/Esc/arrows/letters/F1-F12) | ✅ YES | scan code required in lParam bits 16-23; works unfocused |
| UI button clicks (pause menu, HUD buttons, dialogs) | ✅ YES | client coords in PHYSICAL pixels (DPI 150%!) |
| Mouse wheel zoom | ✅ YES | WM_MOUSEWHEEL needs SCREEN coords in lParam |
| Mouse move → game cursor (F6 [view] cursor follows exactly) | ✅ YES | camera mapping verified: cursor = center + (client−center)/zoom |
| Map tool hover effects (price labels, tooltips) | ❌ NO | follow the REAL cursor (GetCursorPos) |
| Map tool placement (garrison etc.) | ❌ NO | game polls GetAsyncKeyState(VK_LBUTTON) — posted clicks never seen |
| Modifier combos (Ctrl+Space console, Shift+F6 log) | ❌ NO | game polls real modifier state (GetAsyncKeyState) |

**ROOT CAUSE of the earlier "mouse dead" conclusion: DPI.** The desktop runs at 150% DPI.
DPI-unaware processes (our Python) get virtualized rects (1295x837) while the game's real
window is 1942x1256 physical. `game_drive.py` now calls SetProcessDpiAwarenessContext(-4)
at import — all coords are physical. ALWAYS import game_drive (it sets DPI awareness).

Coordinate helpers (client offset for a window): border_x = (winW − clientW)/2 (11 px),
top offset = winH − clientH − border_x (45 px at 150%). WM_MOUSEWHEEL lParam = screen coords.


## MENU INPUT — v0.42.1 Steam-update build (verified 2026-11-17, inst4 43876, hookdll v2)
Steam auto-updated the copies; menus moved to RAWINPUT hit-testing:
| Menu action | PostMessage | Physical SendInput (foreground) |
|---|---|---|
| Clicks (all menu buttons/rows) | ❌ DEAD | ✅ works (ABSOLUTE|VIRTUALDESK 0-65535; game must be FOREGROUND — WM_INPUT only reaches the focused app) |
| WM_MOUSEWHEEL (campaign list scroll) | ✅ works | ✅ |
| List selection arrows | ✅ ONLY with lParam bit24 EXTENDED set; UP=-1 DOWN=+1 WRAPS (e.g. 13->-2->11) | ✅ |
| TAB focus ring | ✅ moves (no activation bound: SPACE/ENTER dead) | — |
| ESC back | ✅ | ✅ |
- Coordinate transform for physical clicks from capture (PrintWindow 1942x1256 incl. chrome):
  `phys_client = cap/1.5 − (11, 37)` — python must be DPI-aware (SetProcessDPIAware) so
  ClientToScreen takes physical client px (1280? no: physical client = 1920x1200 space? see
  menu_nav.cap_to_client — verified against Boston row hit).
- Campaign list = 13 rows + phantom 0; selection ONLY by click; wheel = scroll; state
  machine is deterministic IF keys go >=0.45s apart + >=2s drain (queue latency lies).
- scripts/menu_nav.py = driver (MenuDriver.click_cap / arrow / wheel / shot+diff).
- Welcome page (EA Online, Play Now disabled ~30s) accepts pumped vi clicks when raw pump
  + foreground line up; if wedged: wheel/ESC still work.
- WORLD page: virtual crosshair renders at vi coords (GetCursorPos hook OK, armed banner
  shows); purchase clicks under the new build are UNCONFIRMED (bg test in flight).
## What this means
- Harness can fully drive: menus, level select, loadout, READY, pause/speed, F6 dumps,
  screenshots, zoom, pan? (WASD keys) — all unfocused, N instances parallel.
- Map interactions blocked on: REAL cursor (GetCursorPos) + REAL mouse buttons/modifiers
  (GetAsyncKeyState). Confirmed experimentally (garrison placement attempts failed while
  UI clicks succeeded; F6 cursor matched posted moves but hover labels didn't move).

## Paths to full map interaction (pick in order)
1. **Rust hook DLL (RECOMMENDED, toolchain verified)**: `cargo build --release` works
   (D:\zar-scratch\scripts\hookdll builds a cdylib). Write a cdylib that:
   - is injected into zombies-arent-real.exe (VirtualAllocEx + LoadLibrary shellcode via
     CreateRemoteThread — all doable from Python ctypes),
   - IAT-hooks or inline-hooks `GetCursorPos`, `GetAsyncKeyState`, `GetKeyState` (maybe
     `GetRawInputData`/`SetCursorPos`),
   - serves scripted cursor/buttons/modifiers from a named pipe or memory-mapped file,
   - lets each instance have a fully virtual mouse/keyboard → TRUE parallel automation,
     no focus stealing, no real cursor movement.
   Fallback if hooking raw input too: also fake WM_INPUT via the WndProc (sokol processes
   it if registered with RIDEV_INPUTSINK).
2. **SendInput bursts + temporary foreground** (no RE, mildly disruptive): SetForegroundWindow
   (minimize/restore dance verified works), SetCursorPos over the instance window, SendInput
   clicks/keys/modifiers, restore previous foreground. One instance at a time; cursor moves
   visibly. OK for experiments; poor for long parallel training.
3. **Co-op protocol** (--coop-host port): guest sends plan edits + deployments. Clean but
   needs full protocol RE (framing unknown).
4. **Plan-file (.prep NMPL) writes + battle_replay authored deployments**: no live input for
   placements at all. Format partially decoded (see notes/prep-format.md); needs verification
   that authored files load. Combine with (1) for battle-time actions.

## Verified game behaviors used by the harness
- Level load via keyboard: Space (skip welcome) → Enter (CAMPAIGN) → Enter (Boston selected)
  → Enter (CONTINUE LEVEL 5). Esc cancels READY dialog; N does NOT. Esc opens pause menu;
  RESUME button click works. READY confirm: Space=YES.
- Game pauses in various situations (dialogs, F6 dump write); **Space unpauses** (verified).
- Sim RUNS UNFOCUSED (verified: 123k moving pixels over 4s while user's game foreground).
- F6 dump: heavy (275MB .state) and appears to pause the sim; use sparingly in loops;
  prefer screenshots + .txt parse at low frequency.
- The user's game is PID-identifiable by window rect (2695x1602 physical = their 1797x1068
  virtual size); test instances show 1942x1256 physical (1295x837 virtual).

## Harness sketch (per instance)
```
game-copies/instN/            # own steam_cloud, config.ini (features.dev=true), maps (boston only)
scripts/game_drive.py         # keyboard/UI-click/shot driver (DPI-aware) — WORKS TODAY
scripts/hookdll/              # Rust cdylib (build verified) → virtual input per instance
scripts/inject.py             # TODO: ctypes injector (VirtualAllocEx/LoadLibrary/CreateRemoteThread)
scripts/harness.py            # TODO: episode loop: load L5 → plan (via DLL-virtual input) →
                              #       READY → speed 4x/8x → poll state → reward → next episode
sessions/<run>/               # telemetry, checkpoints, episode records
```
- Checkpoints: snapshot `steam_cloud/` (plans/progress/outbreaks/unlocks/settings) per copy +
  determinism (seed+plan+actions) + F6 .state for post-hoc analysis.
- Mute: settings.ini master_volume=0 per copy (done in inst1/inst2 templates).
- Reward: end-of-battle JSONL (schema in notes/engine.md) or F6 .txt saved_pct/counts;
  screenshots for spatial observation; .state for full detail (offline parse).

## Open questions
- Verify authored .prep loads (need one controlled plan↔bytes pair; game can't place without
  real cursor — after hook DLL, place one unit and dump .prep to get the pair).
- Whether authored [replay] deployment records are honored by features.battle_replay=true.
- Exact zombie-outbreak math: observed 8,601 zombies at tick 273 on L5 (expected ~6 sites × 360
  = 2,160) — conversions from bites inflate count; recheck semantics.
- Whether GetKeyState (sync state) works for modifiers with LONG posted holds — tested 0.35s
  hold, still failed → GetAsyncKeyState (async/global) confirmed in use. Hook DLL must cover it.

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

### Menu navigation notes (verified)
- Launch behavior varies: a fresh launch resumes the last autosaved session directly
  ("play_scenario started ... stage 4" at t=0 in logs/coop-*.txt) when the previous
  instance died mid-session; otherwise it opens the globe home.
- Pause menu: Esc in a level; MAIN MENU returns to the tab the level was entered from
  (Free Play list if entered via Free Play).
- Keyboard: Esc = BACK one menu level (verified); plain Down/Enter did NOT move the globe
  home selection reliably (menu selection appears mouse-driven there) — use virtual clicks
  with pixel-measured button positions (Read-tool image displays downscale the 1942x1256
  physical captures ~1.33x; measure on the PNG file, then subtract client offset (11,45)).
- Virtual clicks work on menu buttons (verified: SANDBOX toggle, level rows, PLAY NOW,
  CONTINUE, MAIN MENU from pause). One transient freeze occurred during a globe transition
  (window stopped pumping messages ~1 min; killed + relaunched); cause unknown — retry on
  freeze, avoid stacking rapid menu clicks.
- PrintWindow grab() blocks while the game's message loop is busy (map install/load) —
  bound observation calls with timeouts when a load may be running.

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
- HARD input rules: NEVER real mouse_event() (wedges UI; PrintWindow then hangs —
  recovery = kill + recover.py relaunch->planning ~44s). vi.click = PostMessage,
  CLIENT px = screenshot png px - (11,40), menus only. MAP placement needs
  vi.button_down/button_up (the drag() path). Clicking menu CHOOSE (loadout)
  WEDGES the game — set loadout via progress save file instead:
  resume_loadout idx17=slot3, idx18=slot4 (23=CURE, 17=Cluster, 12=MGL, 8=Farngren).
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
