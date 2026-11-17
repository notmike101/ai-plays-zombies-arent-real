# Mechanics coverage ledger â€” work in progress

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
  three slots,0.28â€“0.64s each. App mode changes before layout is clickable;
  waiting two advancing UI frames at RVA68e590 resolves the observed race.
  Arrow scan codes need E0: Down0x150/Up0x148. Picker always starts at index0.
- Battle loadout Police/Stungas/Rally buy/refund and Missile refund verified
  against the full native19-level vector; buys0.26â€“0.47s. Existing trainer now
  uses this shared path instead of resetting/scrolling the picker for seconds.
- All seven optional perks selected then cleared through UI on full59-entry
  inst13. Native triples at665f71 encode(id,present,locked); home slot preserved.
- All16 unit placements now have native receipts. Battleship click at client
  (1030,85) cost750 and produced simulation kind10; undo restored its budget.
  Spikes/Oil paint map6509c8 stores signed32-bit cell x/y in a64-bit key,
  values1/2 respectively, cell center=(coordinate+.5)*4 native metres. Five
  painted cells cost5; Shift erase cleared them and refunded5 for both tools.
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
  sample. Nearest-building benchmark6000 buildings:19.12msâ†’0.58ms, identical
  targets/counts including deterministic tie behavior. These are scoped timings,
  not completed worker/browser benchmarks.

The expanded controls/readers are not yet all integrated into policy schema3.
The completion ledger above remains authoritative about outstanding work.

## Visualizer delivery milestone

37 Python tests passed; actual schema3 policy/observer outputs and sampled actions
matched over12 recurrent steps. Warm median forward0.107ms, with capture+snapshot
0.227ms (not gameplay throughput). SSE sampler now wakes viewers immediately;
unchanged JSON bytes and immutable topology reuse parsing/serialization, input
rows persist. Stream/reconnect/pause/isolation and mobile WebGPU/Canvas2D tests
passed on isolated8766 preview; test processes cleaned. Production22604 still
needs coordinated restart. Actual worker/browser after-latency remains pending.

NativeState now includes paint, stable selected IDs, draft polygon, building
classes/abilities/area/centers, wall cell HP, officer AI/boosts/roof/kills and
hazard patches. Five layout/parser tests passed and the expanded snapshot read
in1.34ms on inst13. Native unit field `hp` is overloaded: gun units use it for
magazines remaining; contact encodes rounds used/reload state. Do not label it
uniformly as health. Sniper placement drag and Shift+RMB changed native direction.
Garrison RMB move attempts still did not change position; unresolved.

## Passive native HUD milestone

Pinned world-panel builder call at RVA36a570 is observed once per draw, preserving
its original execution/result. Live selected-garrison panel matched native button
positions; target toggle, level up and one-level refund each changed native state
in0.094-0.100s. Empty selection yields valid=false. HUD reader rejects menu/stale
frames and unknown layouts;4 parser/seqlock tests,9 control tests,7 boot tests pass.
Rust3 tests and two identical clean release builds passed (DLL stays ignored).
Panel coordinates derive from actual rectangles, including wrapped descriptions.
SP upgrade buttons remain absent under shipped hide_unit_upgrades=true.

An existing progress file containing only version/resume/perks is still unplayed.
Boot now chooses its menu by actual stage scores, not file existence. Live inst13
reboot reproduced failure with old predicate and passed with corrected layout.

Native control follow-up: corridor/hold each produced an EVAC record, with
selection at65c520. Pan changed camera x; wheel changed zoom/anchor. A four-corner
zone produced8 physical wall segments; HUD level-up/refund changed levels1->2->1.
Selection corrections from native selcycle and live edge selection:65c4f8 contains
zone indices,65c4e0/65c4e8 are selected zone/edge (NOT helicopter/vehicle indices).
65c4b8 was subsequently resolved as selected HELICOPTER indices (437850/437f60),
not standalone walls. NativeState and schema labels now use that verified meaning. Gate placement on the tested zone
edge did not produce a gate, and roof-unit RMB moves still need investigation.

Schema4 integration staging: mechanic_contract.py and policy_mechanics.py define
99 appended actions and1991 appended observations (native per-unit variants,
selected-unit state, roster/perks, camera, geometry, building classes, hazards,
vehicles and HUD affordances). Three offline semantic/mask/target tests passed.
A live refresh on inst13 succeeded. These modules are not yet wired into training;
no schema/checkpoint migration has run, and terrain/follow-up proofs remain pending.

Native RMB handler448c30 and translation437850 resolve the roof-movement question:
planning movement applies to officers and helicopters only. Roof guns stay anchored;
Shift+RMB re-aim is separate. Battle direct commands are rejected by the native game.
Officer paint428ab0 likewise explicitly refuses outbreak. Policy masks reflect these
phase restrictions. Native playable polygon6652e0 includes curved/interpolated edges;
read it directly instead of assuming the campaign file straight-edge shape.

## Schema4 integrated milestone

171 tools and2376 inputs now run through the policy. Native snapshots replace
per-edit F6 dumps; geometry debt is model-recoverable with native READY gating.
The gate hotkey used an incorrect C scan code; corrected G scan34 produced a
native gate0->1 and selection/refund1->0. Roof guns do not support RMB movement.
Live20-decision evaluation completed in7.03s (baseline27.04s with different
actions/board; not controlled A/B), no optimization/checkpoint writes.
Full offline suites:112 script tests and37 visualizer tests pass.
Observer/plain outputs and sampled actions match over12 recurrent steps; warm
median0.152ms plain and0.355ms with observation. Live server/browser latency
remains to be measured. Migration is explicit/new-path-only; production
checkpoint3 is preserved and has not yet been migrated. Remaining terrain,
editing and ability proofs are pending.

## Geometry, timing and live viewer proof

Schema4 now179 tools/2378 inputs. Added snapped corner/edge edits and helicopter,
vehicle and medevac selectors. Native polygon right-edge insert4->5 vertices,
right-corner removal5->4, corner drag displacement and undo restoration passed.
Frame-receipted endpoint drags (not timed paint strokes) changed corner/corridor/hold
native geometry in0.050-0.055s; paint and battle casting retain their durations.
Selected HUD bounds mask world targets so an intended placement cannot click a panel.
Native speed keys F1-F4 set half-tick counts1/2/4/8, meaning0.5/1/2/4 times real
time. Removed automatic F5 developer-speed activation. Begin at1x; policy controls
normal speed/pause and observes pause/speed. Pause still has bounded wall timeout.
Native handler2f5a50 identifies panel3e0 as MEDEVAC departure, not bus departure;
3d0 must equal action enum8 for detonation. Corrected names/parser and tests.

116 offline script tests,37 visualizer tests,12-step observer parity and graph
checks passed. Current-model browser SSE/reconnect/pause/isolation and mobile
WebGPU/Canvas2D tests passed on isolated8766; preview/server cleaned.
Production visualizer restarted via guarded operator:6716(created1794957272.1076765).
Real evaluation worker31612/game49076:40 decisions14.64s, no optimization/saves;
2378 labels and actual sampled actions reached browser, no label warning. First
10 samples: first capture->receive584ms plus165ms two-animation-frame display
probe; subsequent122-388ms receive and42-77ms display. This is scoped planning
evidence, not battle or worst-case latency. Observer samples at most5Hz; model
can decide between samples. Exact evidence remains analysis/coverage-latency-live.json
and coverage-real-latency.js / Playwright output.

## Terrain, later-stage scale and building-special proof

Schema4 now181 tools/2485 inputs. New native terrain code/bridge-bit samples,
selected building class/ability/officer subtype/damage/area/height, and unit SP
upgrade levels are labeled. Native code4 is water (known battleship placement and
bridge-collapse39fd20); other unverified code meanings stay numeric. Bridge
bitset and cell dimensions come from reflected building-grid structure7760b0.
Building height lower16 bits are decimetres (native21e70).

Inst13 resumed the existing normal saved post-mvp2 L5 profile solely as a
diagnostic fixture; source save is untouched and no result is training/evaluation
evidence. Normal settings are named Adaptive in the native dump. No sandbox,
admin commands, difficulty change or budget modification. Model/trainer stopped.
The L5 map has10013x9157 terrain cells,188695 buildings and209867 civilians.
Reading the whole terrain grid was rejected; the reader now reads just48 cell
codes and bridge bits, with pointer/count bounds. Native map values of20/56 bytes
use cache-line groups, not packed arrays; boost activation exposed/fixed that
layout and tests cover padding. Live speed multiplier0.625 and range1.4 match
building selections; an absent bonus means multiplier1.

All11 selectable building abilities produced their exact native IDs: Armory
2/3/4/15, Civic5/6/7/14, Trade10/11/12. Whole-footprint zones and roof units
were supplied as isolated test prerequisites. Native eligibility remained in
force; the policy must choose these prerequisites during learning.
K/J placement mode receipts alternated1/0/1/0 after normal boot.
L5 steady mechanics refresh213-227ms ->82-84ms after bounded terrain samples,
linear nearest-target selection, equivalent axis binning, cached unchanged
building/playarea membership and avoiding civilian string classification.
122 script tests,37 visualizer tests,12-step observer parity and graph PASS.
Complete ability/follow-up proofs and final migrated training resume still pending.


## Combat and transport state milestone

Schema4 now4261 inputs/181 actions. Added37 spatial mean channels for wall
HP/breach fraction/level/build progress, evac width/radius/suppression,
helicopter ammo/cooldown/damage/rearm/target, vehicle kind/ammo/damage/route/
passengers/return state, medevac phase/passengers/damage/departure order, and
hazard kind/radius/expiry. Labels specify normalization and0-empty semantics.
Native arrays remain read-only; policy gets status, not scripted reactions.
123 script tests and37 visualizer tests pass, including nonzero wall/medevac
normalization probes. Exact observer/plain outputs and sampled actions match
for12 recurrent steps; warm medians0.209ms plain/0.473ms observed.
Live diagnostic receipts: Police,CallArms,Rally,Medevac,Heli,Stungas,Firebomb,
Missile,Bomber,Cluster consumed native stock. Demolition needs a tall eligible
building; vehicle drops require valid open ground. Those proofs and medevac
queued departure remain pending; mere clicks are not success evidence.


Quick Deploy now applies the shipped/config-echo unlock reduction to the actual
equipped perk when constructing the battle deck. Abilities without a bound key
stay masked. Both old and new two-step geometry gestures can be canceled by the
policy; cancellation clears the saved anchor as well as the native tool.
Regression tests cover reduced unlock time, missing binding and cancelability;
125 script tests pass. No reward or optimizer changes in this milestone.


## Modal recovery and remaining battle receipts

L5's first mutation tutorial at sim45.03 opened the native modal at667868,
freezing the simulation while game_state.paused remained false. PrintWindow
showed the informational Zombies Are Mutating dialog; Enter cleared it and
simulation resumed. Schema4 now4262 inputs/183 tools: dialog state plus guarded
confirm/cancel actions. While modal, masks expose only those two actions and
HUD reads skip the obscured panel. No blind SPACE/ESC watchdog is introduced.
126 script tests and37 visualizer tests pass; observer parity and graph pass.
The fake-game integration now supplies the same perk contract as real refresh.
Demolition on a240.8m tall building, SeekDestroy on a garrison, Cure, Tank,
AC130 and Nuke each consumed native stock in scoped normal L5 diagnostics.


## Context-sensitive corridor and detonation controls

All19 battle abilities now have successful stock receipts, including APC, Bus
and Dozer on valid open ground. Medevac Leave Now changed ordered0->1 after the
queued simulation action was consumed. Both Civic officer subtype buttons
changed the selected building's native officer_kind to1/0.
Corridor Q + wheel grows native full width150->165m, and the resulting EVAC
record has half_width82.5. Hold E + wheel zooms instead. Added explicit corridor
wider/narrower actions, armed-tool/width observations, and blocked camera wheel
zoom while corridor is armed. Raw drag completes the armed corridor at that width.
C4 selected-panel detonation removed the selected native ID. Shift+T ARMS a
click-near-charge tool; it is not a global detonation command. Renamed the new
unreleased action arm_detonation. Armed click removed the remaining3 charges;
no incorrect Detonate All promise remains. Native multiselection/panel handles
selected groups. Schema4:4265 inputs/185 tools.127 script tests,37 visualizer
tests,12-step observer parity and graph pass. Live mechanics refresh passed.
