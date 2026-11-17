# Engine & Binary RE

## Identity
- Game: **Zombies Aren't Real** (Early Access), Steam AppID **5185890** (DLC 5488850 = globe-nuke/Satellite DLC; Supporter Pack is the DLC).
- Build: git `bbbff50f`, dev's machine paths show `C:/git/nombies/` (internal name "nombies"), built with Odin `odin-windows-amd64-dev-2026-10`.
- Binary: `zombies-arent-real.exe`, 7,034,368 bytes, PE32+ x64, SHA256 `a1bd5913ed3905aaaadfb5a14781004d28990f433ff1621c658c10f1795469d2`.
- Engine: **custom Odin engine on sokol_app + D3D11** (window class `SOKOLAPP`), `d3d11.dll` imports, steam_api64.dll (SteamAPI_InitFlat), WinHTTP (usage telemetry + custom map data), WS2_32 (co-op + Overpass).

## Input model (empirically verified)
- Keyboard: **message-driven** — PostMessage WM_KEYDOWN/WM_KEYUP with correct scan code in lParam bits 16-23 works, even unfocused. (Space, Enter, arrows, F-keys, letter keys all verified.)
- **Modifier combos (Ctrl+Space, Shift+F6) do NOT work via PostMessage** — the game polls `GetKeyState`/`GetAsyncKeyState` (both in import table) for modifiers.
- Mouse: **the game reads the REAL hardware cursor** (`GetCursorPos` imported; hover tests with PostMessage'd WM_MOUSEMOVE produced zero UI reaction; F6 dump `cursor` field tracks the user's real mouse). Raw input (`RegisterRawInputDevices`/`GetRawInputData`) also imported. → PostMessage mouse injection is dead.
- The game **pauses its sim when... NOT focus-related** — verified sim runs unfocused. The pauses we saw were sticky pauses from dialogs/dumps; **Space toggles pause/resume**.
- Window: renders UI for its creation size; **resizing the window breaks the battle HUD layout** (menus reflow but battle HUD was missing while resized; returned at original size). DON'T resize windows; launch at default and leave.

## Parallel instances (verified)
- Copy game dir → add `steam_appid.txt` containing `5185890` → exe runs beside Steam and beside other copies ("Steam: connected (leaderboards on)" on stdout).
- Each copy has its own `steam_cloud/` (saves/settings/unlocks), own `logs/`, own `debug_dumps/`.
- Exe prints startup log lines to stdout (balance.ini found, Steam connect, etc).
- Steam Cloud sync is DISABLED per user — do not rely on it; local steam_cloud folders are the saves.

## Observation channels (verified)
1. **F6 debug dump** (needs `features.dev = true` in config.ini of the COPY; balance.ini override of features.dev is ignored — dev seems gated to config.ini):
   - writes to `debug_dumps/<stamp>-<Campaign>.txt` (62 KB, human readable) + `.state` (272-285 MB, whole sim state, magic `NZSTATE1` + version byte, then binary).
   - The .txt contains: `[build]`, `[where]` (app_mode/phase/stage/map/campaign/difficulty/assist), `[clock]` (**outbreak_seed, sim_time, tick, rng, roll_seed, speed_mult, paused, horde_coordination**), `[view]` (cursor/camera), `[economy]` (money, loadout=SP stock), `[counts]` (civilians/zombies/converting/police/corpses/all unit types/infections/wall_chews/zombie_deaths + per-weapon kills), `[plan]`, `[replay]` (deployment recordings), `[walls]`, `[near_cursor]` (units near cursor w/ full row schema), `[params]` (resolved sim params for next tick), `[config]` (every resolved config key).
   - Dumps are big (275MB state each) — don't spam them; they also appear to **pause the sim while writing** (and the pause seemed sticky once — use Space to resume after a dump).
2. **PrintWindow screenshots** (PW_RENDERFULLCONTENT) work unfocused; add `PW_RENDERFULLCONTENT`=2. Top-down rows when biHeight negative; our game_drive.py grab() returns correct orientation.
3. **JSONL session log** (dev, Shift+F6) — `logs/<git>-<campaign>-<scenario>.jsonl` — NOT yet triggered (Shift modifier not PostMessage-able). Schema in exe strings: battle summary records (schema, scenario, stage, result, badge, saved_pct, placed, wall_levels, abilities, spent, upgrades, used, kills...). End-of-battle granularity (usage telemetry uses the same record: `cache/usage/queue.jsonl`).
4. **stdout log** of the process (launch lines, play_scenario events went to logs/coop-*.txt actually).
5. `.state` file (NZSTATE1) — full sim state, parseable offline (format RE pending; heavy).

## Notable game self-drivers
- **Admin console** (Ctrl+Space, in-game): ~120 commands (see exe strings; full list in notes/admin-commands.md). Includes spawn/go-to-level/instant-win/game speed/debug dump/kill all zombies/refund all/start outbreak/vehicle status... Most positional commands use the cursor; many are cursor-free.
- **Performance test** ([perftest] + perftest.odin): built-in scripted battle runner (NYC last scenario, fixed defense, camera tour) — proves the game can self-drive a battle.
- **Co-op**: `--coop-host <port>` / `--coop-join <address>:<port>` — TCP direct-link co-op, protocol 8. Guest syncs plan edits (`coop_plan_diff`/`coop_plan_edit_send`/`coop_plan_blob`) and deployments (`coop_fire`). This is a potential clean action API (RE pending).
- **battle_replay** (`features.battle_replay=true`): next battle re-fires every recorded deployment of the last battle at its recorded moment. Deployments are recorded into the plan ([replay] section, also saved with the plan). → If we author deployment records in the plan file, the game executes battle deployments for us (RE of .prep format pending).
- **Determinism**: "the sim is tick-deterministic"; outbreak seed stored per stage (`steam_cloud/outbreaks/<Campaign>-<stage>.seed`, plain integer, e.g. Boston stage 5 = `2812226150`); "repeat outbreak" admin command re-rolls the same outbreak; speed/threads don't change outcomes.

## Data files (all plain text, hot-reload ~0.5s)
- `config.ini` (321 KB, fully commented — the whole game design), `balance.ini` (playtest levers, wins over config.ini, hot-reload), mutators/*.ini (config overrides), campaigns/*.cmp (stages: playarea polygons, civilians, land_km2, origin), scenarios/*.scn (text, [override] blocks, [spawns]), `unlocks.ini` (global unlock progression), battle_order.txt + campaigns/order.txt (menu ordering), `lang/en.lang` (all UI strings + keys).
- Saves (per copy): `steam_cloud/progress/<C>.progress` (badges per stage, resume_stage, resume_money, resume_loadout, carry <unit> = x y dx dy level...), `steam_cloud/plans/<C>.prep` (binary NMPL magic — placements+carry+recordings), `steam_cloud/outbreaks/<C>-<n>.seed`, `steam_cloud/settings.ini`, `steam_cloud/unlocks.ini`, `steam_cloud/flags/`.
- Maps: `maps/*.map` binary magic `NAM1`; `maps/world.globe` (globe menu); `maps/geobake.py` (shipped; documents the OSM->map pipeline and .ztl tile format; the map builder is in-game).
