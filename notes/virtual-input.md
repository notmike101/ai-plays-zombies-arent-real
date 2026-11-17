# Virtual input DLL — VERIFIED WORKING (2026-11-14 late session)

## What was built
- `scripts/hookdll/` — Rust cdylib (builds with cargo, no external crates):
  - creates shared memory section `ZARVI_<pid>` (0x100 bytes),
  - IAT-patches the main exe's USER32 imports: **GetCursorPos, GetAsyncKeyState,
    GetKeyState** (3 patched; GetKeyboardState not imported by the game but hooked anyway),
  - serves virtual state while `enabled != 0`, passes through to originals otherwise,
  - exported `zar_init()` runs the setup and returns the patch count (call it via
    CreateRemoteThread after LoadLibraryW; DllMain alone proved unreliable to rely on,
    though it does also run).
  - Shared layout (little endian): magic 0x5A415249, version 1, enabled, cursor_screen_x,
    cursor_screen_y, buttons (bit0 LMB bit1 RMB bit2 MMB), keys[8] (256-bit VK down table),
    toggles (CAPS/NUM/SCROLL), heartbeat, patch_count.
- `scripts/zar_input.py` — `VirtualInput(pid, hwnd)`:
  - inject(): exact FFI argtypes (64-bit handles!), VirtualAllocEx + WriteProcessMemory +
    remote LoadLibraryW + remote zar_init(base + RVA from local PE parse via Toolhelp
    module snapshot), opens the section, exposes:
    move_to (client physical px; also posts WM_MOUSEMOVE), click (sets polled button bit
    AND posts WM_LBUTTONDOWN/UP), drag, key_press (posts message + sets async bit),
    combo_press (virtual modifiers!), enable/disable, patches().
- The first game crash was caused by remote-thread start address 0x0 (ctypes default
  c_int truncating the 64-bit LoadLibraryW address) — NOT by the hooks. All
  GetModuleHandleW/GetProcAddress/OpenProcess/etc. need `restype = c_void_p`.

## Verified on the game (Boston L5 planning, inst2, pid 35168)
1. Virtual cursor: F6-followed hover tooltips, price labels and the armed-tool crosshair
   all track the virtual cursor (GetCursorPos hook live).
2. **Virtual garrison placement succeeded**: money $27,317 → $27,047 = −$270 (the exact
   price label of the clicked building).
3. **Admin console opened via virtual Ctrl+Space** (`combo_press([VK_CONTROL], VK_SPACE)`).
4. **Console text entry works** (WM_CHAR): typed `stage size` + Enter → readout:
   `land 67.3 km2, paid 212090 civs: grant $6604 + carry $1, outbreak 6×360 @ 301m`
   (confirms outbreak math: 6 sites × 360 zombies, 301 m spawn radius on Boston L5).

## Consequences for the harness
- FULL automation of every in-game interaction is now available, unfocused, in parallel,
  with zero real-cursor movement: placements, safe-zone drawing (drag), gates, fortify,
  loadout, battle ability targeting (click/drag), admin commands (go to level n, start
  outbreak, instant win, game speed 0.5-8, repeat outbreak, reset scenario...).
- Each instance gets its own section (ZARVI_<pid>) → per-instance virtual input.
- Keep `enabled=0` (passthrough) when the user might use the instance manually.

## Admin console usage notes
- Console opens with virtual Ctrl+Space in planning/battle; typing goes through WM_CHAR;
  Enter runs; it shows command suggestions by prefix. With the game's dev features off,
  some commands may be hidden, but budget/stage-size/spawn/teleport classes are there.
- Useful cursor-free commands: `start outbreak`, `go to level n`, `reset scenario`,
  `instant win`, `game speed 8`, `repeat outbreak`, `debug dump`, `refund all`,
  `select all placements`, `kill all zombies`, `vehicle status`, `bus status`,
  `special buildings`.
- Cursor-positioned commands need a virtual move first (they use the virtual cursor).

## Open items
- .prep NMPL decode (now easy: place controlled content via virtual input, autosave via
  leave-to-menu, diff bytes) — for plan-file-level ML actions if needed.
- battle_replay authored deployments verification.
- Free Play tab navigation check (vs Campaign tab path used so far).
- JSONL session log via Shift+F6 (virtual Shift should make it reachable now).
