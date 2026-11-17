# Memory map & live observation channel (SOLVED 2026-11-15)

## SOLUTION (use this; battle-verified vs HUD to 1%)

## FULL STATIC FIELD SET (2026-11-16, all i64 unless noted; VA = module_base + RVA)
civilians 0x650f10 (also mirror 0x650728), zombies 0x650f18, converting 0x650f80,
police 0x650f20, corpses 0x650f28, count(civ+zomb) 0x650438,
money f32 x3 copies: 0x6563c0 / 0x65d9c0 / 0x665ef0.
Proof: the F6 state-dump writer (0x140015d00) reads these statics directly; format
string `[counts] ... %ld zombies out of %ld` @0x14053a228.
NOT a flag: 0x5f268a (bytes 130..199 observed; earlier 0x31 was coincidental '1').
Detect pause/hang from outside via zomb-delta==0 polling only.
The counts also live DIRECTLY in the module .data (no pointer chasing, no heap):
- civilians u32 at `module_base + 0x650728`
- zombies   u32 at `module_base + 0x650f18`
Multiple stale mirror copies sit near each field; the LIVE ones are those whose
value CHANGES between polls while a battle runs (differential scan over +-2KB found
civ mirrors at -0x7f0/-0x7c8/-0x748 from the zombie field + the zombie field itself).
`zarmem.SimReader.set_direct(zarmem.DIRECT_CIV_RVA, zarmem.DIRECT_ZOMB_RVA)` = exact
reads; verified through the it17 WIN battle (6.90% bronze, civ froze at 65,639 =
31.2% alive; HUD matched every poll).
Module base: `memscan.module_base(pid)` (EnumProcessModules; ASLR).

## Reading still valid
Everything below documents the heap-block channel (still works as fallback).

## What works TODAY
- **External memory reading** via ReadProcessMemory (scripts/memscan.py):
  region walker (VirtualQueryEx, committed RW/R/RX/RW pages, ≤64MB regions),
  numpy pattern search. Full-process u32 scan takes ~4-8 s.
- **The counts block layout** (verified from the .state serialization):
  `[civilians u32][0 u32][zombies u32]` adjacent — confirmed by the .state file
  (civ@28,558,356 / zomb@28,558,364 in 20261115-043738 dump) and by the live hit
  0x2245a1a06a8 = [62635][0][101507] mid-battle.
- **The money field** is a unique f64 (scannable by range, e.g. [2698.5, 2699.8] →
  exactly 1 hit: 0x2247ae27bc8 = 2699.4458 in the battle session).
- **The exact-value trick**: in PLANNING, civilians == 209,867 exactly (sandbox: also
  209,867) → scanning for that single u32 yields only ~57 candidates; one READY + a few
  seconds of battle collapse isolates THE live field (verified once: 57 → 1).

## The problem
The counts live in a **heap allocation that MOVES** on mass-death compactions:
the verified address 0x2245a1a06a8 held civ 62,635 during the battle; later the same
address read 104,443 (stale/reallocated data). Any reader must re-validate each poll:
`mid == 0` and `0 < civ <= 209867` and `zombies >= 0` and `civ+zombies <= 210,016+slack`,
and fall back to a rescan when invalid.

## The proper fix (IN PROGRESS — next agent's first task)
Find the sim-state ROOT POINTER statically with Ghidra:
- The state-dump writer is at **0x140015d00** (preferred image base; spans to
  0x1400190f9, 13.3 KB) — it references the "NZSTATE1" magic at 0x1405376e8.
  Found via rea CLI trace (analysis/nzstate_trace.json, Ghidra analysis of
  sha256 a1bd5913...).
- Decompile 0x140015d00 (rea decompile / Ghidra headless) → identify the sim-state
  struct pointer argument → trace to the caller (debugdump.odin's F6 handler) → find
  the PACKAGE GLOBAL holding the sim pointer (a static address in .data/.bss, near the
  other statics seen at 0x7ff7c0ff14e0 / 0x7ff7c1005228 — those are the outbreak
  seed/roll_seed globals).
- Runtime: read the module base (EnumProcessModules; ASLR rebase) → global address =
  base + static_offset → deref → apply struct offsets for civilians/zombies/etc.
- Ghidra was run via the rea CLI with:
  `GHIDRA_INSTALL_DIR=D:\ghidra\ghidra_12.1.4_PUBLIC`,
  `REA_GHIDRA_STARTUP_TIMEOUT_MS=1800000` (default 330 s times out on this 7 MB Odin
  exe), `npx -y rea-agents@6.9.0` under Node 24.22.1 (nvm; 22.20.0 is too old for the
  rea CLI — `nvm use 24.22.1` first; corepack shim "rea" may still point at the old
  install — use `npx`).
- The first trace attempt TIMED OUT at startup; the second (30 min deadline) COMPLETED
  and saved the Evidence (nzstate_trace.json). A Ghidra snapshot may be resumable via
  `--snapshot <path>` if a project file survived in the rea temp dir.

## Scanning recipes that worked
- u32 exact scan (planning civilians 209,867): 57 hits, 7 s.
- f64 range scan (money): exactly 1 hit.
- u32 seed scan: 2 hits — both STATIC (0x7ff7c0ff14e0, 0x7ff7c1005228: the
  outbreak_seed/roll_seed globals; the live sim struct stores the seed differently).
- The differential "dropping value" scan yields ~200k candidates (timers/arrays noise) —
  use exact-value or struct-pattern signatures instead.

## Counts block semantics (from F6 dumps)
- count = civilians + 149 carried units (+ zombies, + corpses?) — at planning:
  210,016 = 209,867 + 149.
- converting: separate counter (44 mid-battle once); zombies: rises with conversions.
- police/corpses/…: same struct per the F6 [counts] section order:
  civilians, converting, zombies, police, corpses, snipers, mortars, garrisons,
  turrets, mines, c4, battleships, helicopters, apcs, walls, levelled_buildings,
  infections, wall_chews, zombie_deaths.

## Verified schema 3 native readers (2026-11-17)
Same build hash as env_zar.BUILD_SHA256. Units: positions dynamic array0x650280
(vec2 float), kinds0x6502d0 (u8), stable tick0x6514e8. Camera x/y/zoom0x6553ac/b0/b4;
pitch/yaw0x6553d4/d8 must be zero. Client=(world-camera)*(zoom,-zoom)+client_size/2,
without another DPI divide. Buildings rectangle array0x656680 (four float32).
Plan zone coords subtract map origin0x665358/5c. Stock0x656488:39 float32 in
Stock_Item order; loadout0x655f90:19 int64 in NATIVE_ABILITIES order (env_zar.py).
Runtime receipts: Police stock40->28 after spray; Police20/Stungas1 exactly matched
session-log footer. No native writes. Building candidates can include scenery.
