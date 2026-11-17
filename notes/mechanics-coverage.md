# Mechanics coverage ledger — work in progress

This is an implementation/proof ledger, not a claim of100% coverage. Supported
EXE SHA256 is env_zar.BUILD_SHA256. Scope and acceptance are in
mechanics-coverage-plan.md. Existing model schema3 is not complete.

| Mechanic | Native evidence | Implementation / proof still needed |
| --- | --- | --- |
| All16 planning units | unlocks.ini, native planning picker, game_mechanics.UNITS | Roster selection/swap/refund and each placement/aim/paint receipt |
| All19 battle abilities | battle_order.txt, env_zar.NATIVE_ABILITIES | Existing policy actions; audit all gestures, charges and follow-up controls |
| All8 perks,3 slots | native name table0x14077e000, en.lang perk.*, Ghidra0x1400f5be0 | Copy unlocks corrected; model picks/refunds and native slot/lock observations pending |
| Money stacking/level refunds | config.ini, statpanel strings | Existing level-up; selection/level-down receipts and features pending |
| All16 SP tower upgrades/refunds | unlocks.ini, config.ini[upgrades], Ghidra0x140283d80 | Shipped hide_unit_upgrades=true disables these; conditional interface/masks needed, never claim active from unlocks alone |
| Safe-zone polygon/corners/undo/cancel | config.ini[safe_zone] | Existing rectangle only; arbitrary vertices, reshape/move/delete/land limits pending |
| Walls/gates,levels/refunds | config.ini[walls], live wall RTTI | Native wall geometry/HP observations and edit/selection receipts pending |
| Corridor/hold geometry | config.ini, existing action primitives | Width/radius/reshape/delete/undo and native observations pending |
| Selection/multiselect/move/reaim | en.lang hud.planning.*,statpanel.reaim | Actions, stable selection state and receipts pending |
| Officer behavior/paint | bind_officer_mode,bind_paint, config.ini | Planning controls and observations pending; battle orders constrained by native rules |
| Building class special picks | config.ini[building_class], statpanel.pick_ability | Choices, eligibility/classes/reach and selected-special state pending |
| C4/Napalm detonation | bind_detonate,statpanel.detonate* | Selected/all detonations, stock/charge observations pending |
| Vehicle follow-up/evac/target mode | statpanel.leave_now,target_near/far,status_* | Selection, follow-up actions and native status/health/ammo pending |
| Camera/pan/zoom/view overlays | settings bindings, native camera RVAs | Policy actions and observation transforms pending |
| Pause/speed/READY/retry/continue | native phase/clock, existing helpers | Audit timing controls and preserve curriculum/normal difficulty |
| Native combat/environment | config.ini, native entity/wall/building arrays | Health/ammo/status/range, terrain/playable boundary, hazards and carried placement coverage pending |

## Measured starting latency

Isolated inst13, actual learned policy,20 decisions, no optimization/checkpoint
writes:27.04s in the episode. The35s server sampler observed14 published frames;
median publication interval0.918s, max2.718s, median first server observation
delay0.254s. This was planning, not a battle benchmark or browser render benchmark.
Profile evidence: analysis/coverage-before-{profile.txt,result.json},
analysis/coverage-latency-before.json. Major synchronous paths:9 dumps6.36s,
one loadout change6.10s (wheel sleeps4.94s),15 arm operations5.70s. Profiler
thread accounting overlaps on free-threaded Python; do not sum cumulative rows.
Observer publication total0.098s including first topology construction. The
main slowdown is action execution/waits; server latency still needs improvement.

## Native layout evidence

Wall array at RVA656bb0 has count656bb8 and stride192. Its reflected fields
(name/byte offset):cells0,under40,cell_hp80,a120,b128,walk_first136,walk_last144,
full_hp152,level160,build_left168,build_total172,last_chew176,last_chew_slot184.
Names/offsets from PE tables0x14074ad30/0x140753010 used by F6 writer0x140015d00.
Validate runtime reads against dumps before using them as policy observations.

## Verified interface milestones (2026-11-17)

- Native picker selection:48 consecutive roster selections across16 units and
  three slots,0.28–0.64s each. App mode changes before layout is clickable;
  waiting two advancing UI frames at RVA68e590 resolves the observed race.
  Arrow scan codes need E0: Down0x150/Up0x148. Picker always starts at index0.
- Battle loadout Police/Stungas/Rally buy/refund and Missile refund verified
  against the full native19-level vector; buys0.26–0.47s. Existing trainer now
  uses this shared path instead of resetting/scrolling the picker for seconds.
- All seven optional perks selected then cleared through UI on full59-entry
  inst13. Native triples at665f71 encode(id,present,locked); home slot preserved.
- All unit placements except Battleship produced native receipts at a tested
  building/street point. Each successful placement was undone and budget restored.
  Spikes/Oil change painted terrain, not the entity list; terrain proof pending.
  One attempted Battleship location was rejected; this is not placement coverage.
- Simulation kind enum is Civilian0,Zombie1,Police2,Corpse3,Sniper4,Mortar5,
  Garrison6,Nest7,Mine8,C4=9,Battleship10. These are NOT toolbar IDs. Mortar
  payloads1/2/3/4 distinguishGas/Fire/Howitzer/MLRS; Railgun is Nest+payload5.
  Trap-kind1=ChemMine,2=Napalm. NativeState validates map occupancy and array bounds.
- Five-corner polygon with Backspace/replacement/Enter matched F6 vertices
  after adding map origin. Native legality true. Selection/refund/undo, money
  level-up and far-first target toggle observed on a garrison. Unit move attempt
  was not yet checked for actual displacement; do not count it as verified.
- Right-click with no active tool can issue a move. Shared controls check tool
  flags before canceling; use a blank-space left-click to deselect. ESC with a
  selected unit opens the menu (RVA666870), while game_state.phase still says
  planning; it is not a selection-cancel primitive.
- NativeState planning snapshot read8142 units/6532 buildings in0.74ms in one
  sample. Nearest-building benchmark6000 buildings:19.12ms→0.58ms, identical
  targets/counts including deterministic tie behavior. These are scoped timings,
  not completed worker/browser benchmarks.

The expanded controls/readers are not yet all integrated into policy schema3.
The completion ledger above remains authoritative about outstanding work.
