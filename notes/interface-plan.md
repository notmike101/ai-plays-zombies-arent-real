# Deterministic interface implementation — 2026-11-17

Scope is the user's six-step interface specification; no model/trainer edits,
physical input, console commands, installation writes, or subagents.

1. Audit raw-only and posted-only input against money, counts and F6 cursor/camera.
   Pin the native RAWINPUT ABI and client coordinate contract in small tests;
   fix shared input once and retain all public signatures. Audit dialogs, wall
   and zone gestures, and wheel anchoring. Commit each coherent change.
2. Add `scripts/zar_boot.py`: copy-path validation, detached launch, once-only
   injection, fractional menu coordinates, bounded waits, planning verification,
   diagnostics on failure and owned-process cleanup. Reuse ZAREnv unchanged.
3. Add `scripts/test_interface.py`: fresh L1, garrison, zone/wall, wheel anchor,
   battle start and retry assertions, PASS/FAIL output and analysis logs.
4. Run two consecutive fresh-boot tests and one four-copy concurrent boot;
   preserve progress backups and kill all test games in finally blocks.
5. Update guidance/menu matrix and tracker with verified facts and limitations.

Delivered: unified posted input, corrected native v3 ABI and cursor coordinates,
bounded once-only injection, screenshot-free boot, live acceptance, and docs.
Two consecutive fresh acceptance runs: analysis/interface-20261117-094110.log.
Four-copy proof: analysis/interface-scale.log (a final mixed-layout repeat is in
analysis/interface-scale-final.log). Fullscreen: interface-fullscreen-boot.log.
CONTINUE windowed/fullscreen: interface-continue-final.log. REA/Ghidra evidence:
interface-{pe-imports,raw-xrefs,raw-consumer}.json. Final process state is in tracker.

Ruling: finish the supplied implementation specification directly, using the
existing checkout and API; no extra design approval is needed. Source changes
are limited to the interface. Existing unrelated logs/checkpoints stay untouched.
