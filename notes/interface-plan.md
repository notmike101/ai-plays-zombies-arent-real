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

Evidence so far: analysis/interface-audit-initial.log, interface-movement.log,
interface-post-only.log, interface-pe-imports.json. Raw-only events increment
raw_sent but do not move world cursor. Posted-only click purchases a garrison.
The v3 native raw record layout and command constants disagree with Win32 x64.
Inst4 retains all five badges. No trainer CLI processes found; stale copies
listed by the user were terminated, with PID 7340 retained for the audit.

Ruling: finish the supplied implementation specification directly, using the
existing checkout and API; no extra design approval is needed. Source changes
are limited to the interface. Existing unrelated logs/checkpoints stay untouched.
