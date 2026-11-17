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
