# Normal-campaign mechanics coverage

Current interface: schema4,4889 inputs,185 actions,48 spatial cells. Scope is the
pinned native build and normal Boston campaign described in mechanics-coverage-plan.md.
Every catalog category below has an observation and model control path where the
game offers one. This is mechanic/interface coverage, not proof of strong play or
exhaustive coverage of every combination, location and timing. The8x6 viewport
representation remains approximate; pan/zoom and native target snapping help.

| Mechanic | Implementation and verification |
| --- | --- |
| All16 planning units | Roster equip/clear, click/drag/paint/erase, native variant counts;48 consecutive picker selections and every placement have live receipts. |
| All19 battle abilities | Buy/refund, real binding/stock/unlock/arrival, click/drag and target masks; every ability consumed stock in scoped live trials. Seek snaps to garrison; Demolition starts on eligible buildings. |
| All8 perks | Home slot is campaign-owned; all7 optional perks selected/cleared live. Native slot locks observed. Quick Deploy reduced heli unlock30s to20.1s, stock consumed at20.37s. |
| Money levels/refunds/targeting | Native selected-panel availability and individual state; garrison up/down/far-first and wall1->2->1 verified. |
| All16 SP tower upgrades | Four native buy/refund rows per eligible unit and native levels observed. Shipped hide_unit_upgrades=true disables the UI; actions stay masked. Conditional branch tested offline, not falsely reported as a normal live feature. |
| Safe zones and editing | Arbitrary vertices/back/finish/cancel, drag corner/edge, insert/remove, selected refund/undo, native legality/land limits. Live5-vertex construction, insertion/removal, drag and undo receipts. |
| Walls/gates | Native geometry, cell health/breaches, construction/level, selection/refund. Live gate0->1->0 and wall level receipts. |
| Corridors/holds | Endpoint geometry, selection/refund/undo, native width/radius/attraction/suppression. Live EVAC records; corridor width150->165 gives half-width82.5. Context-sensitive wheel masks prevent accidental zoom. |
| Selection/movement/aim | Unit/building/wall/gate/evac/corner/aircraft/vehicle selectors, additive/box selection, native selected IDs, Shift-RMB aim. Sniper aim verified. Native planning movement supports officers/helis only; roof guns and battle direct orders are rejected and masked. |
| Officer mode/paint | Selected-officer planning-only commands and AI/boost/subtype observations. Native code restricts outbreak orders. These conditional planning commands have offline dispatch/mask checks; normal deployment produces officers during battle. |
| Building specials | All11 native choice buttons and both officer subtypes have live receipts; class/height/area/damage/selected ability and boosts observed. |
| C4/Napalm | Selected-panel and armed click-near detonation; live ID removal and ignition receipts. Shift+T arms a tool, not global detonation. |
| Aircraft/vehicles/evac | Native health/ammo/rearm/routing/targets/passenger state. Medevac departure ordered0->1 live. Existing helicopter grants no free cast; autonomous rearm/hunting remain game-owned. |
| Camera and timing | Pan/zoom transforms, native paused/speed, normal.5/1/2/4 controls verified. No developer8x. READY requires native legality; retry/continue retain curriculum and doomed-run abort rules. |
| Modal dialogs | Native modal flag masks world input and exposes confirm/cancel. Live mutation tutorial confirm resumed simulation; cancel dispatch tested offline. |
| Combat/environment | Unit variants/zombie types, magazines/reload/boosts, walls/buildings, terrain/playable boundary, bridge span health, sparse fire/oil/burnt masks, hazard patches and mutation sites. Live fire flags1->3/burnt0->1, natural mutation and bridge816->616/collapse receipts. |

No supported normal-campaign catalog category remains without an interface path.
Unavailable native controls stay explicitly conditional. Cosmetic overlays/3D tilt,
external/social UI, admin/debug controls and changing difficulty are outside the
policy scope. Native geometry/height/class information supplies gameplay facts.

Final offline milestone:132 script tests,37 visualizer Python tests, exact policy/
observer outputs and sampled actions over12 recurrent steps,Node graph checks.
Final4889-input browser preview passed SSE/reconnect/pause/isolation,WebGPU and
Canvas2D touch/desktop checks. Preview and diagnostic game processes were cleaned.
Migrated schema3 weights and10 Adam states into a new policy4 file; original3 is
preserved. Deployment/update evidence belongs in tracker.md.

## Historical milestone evidence

Entries below are chronological. Their intermediate schema widths and pending
items describe that milestone only; the current table above supersedes them.

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

At this early milestone the expanded controls were not yet integrated. Later
schema4 milestones below and the current table supersede those pending items.

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


## Fire spread and mutation observations

Fire_Spread native root654f40 has8m cells and sparse32x32 pointer tiles. Reflected
tile size1c10: state bytes0, green/burnt/oil1024-element u16 masks at400/c00/1400.
The reader samples only the48 policy points and caches each touched tile within
that snapshot. Native ignition162790 sets state bit2 and the burnt subcell mask.
Live Napalm on green ground: flags1->3, green1, burnt0->1. Both C4 and Napalm
selected-panel detonations have native receipts. No game memory writes.
Mosh_Pit reflected type775860:40-byte records at6511f0, position/radius/start/
until/members/kind offsets0/8/12/16/24/32. Natural L5 mutation observed atsim15.07,
center(14009.38,11041.36),radius15,until25.00,members7,kind1. Finite live policy
observations include its location, size, population and completion time.
Schema4 now4745 inputs/185 tools.128 script tests,37 visualizer tests,12-step
observer parity and graph pass. Sparse-fire tests cover null tiles, partial masks
and bounded reads. The new REA inquiry completed and its owned engine was cleaned;
pre-existing external Ghidra/OMP sessions were left untouched.


Targeted battle cells now snap Seek & Destroy to actual garrisons and Demolition's
first point to an eligible tall/slender building, using the native configuration
height/slenderness rules. The model still picks the cell and demolition direction.
Cells without such targets are masked; the second drag point remains free world
geometry. Live L5 refresh produced3 garrison cells and11 candidate demolition
cells.129 script tests and37 visualizer tests pass, including target-vs-direction
masking. Other casts keep model-selected world points and native legality checks.


Bridge damage records at656b38 are24-byte triples of signed64-bit key/hp/full,
not floats. The key is the minimum native terrain cell of the span (bridgesel
02cb20);049940/054b90 use the same record for the HUD health display. Untouched
spans have no record. Added spatial presence,clamped HP/full and log1p full HP at
the span's anchor cell, alongside the existing sampled bridge bits. C4 live test
recorded full816/current616 and multiple nonpositive/collapsed spans; the new
reader/finite observation path passed on those records. Test pins native-cell
projection, negative damaged HP and invalid key rejection. Schema4 now4889 inputs/
185 tools,3,096,810 parameters.130 script tests,37 visualizer tests,observer parity
and graph pass. Warm medians0.246ms plain/0.620ms observed in this check.

## Helicopter stock correction

Quick Deploy live receipt: helicopter stock1->0 at sim20.37 (base unlock30,
33% perk reduction). Repeating its slot after arrival with stock0 neither changed
the target nor set an order. Native cast branch445a60 calls436ec0 before creating
a new aircraft through0b9710; there is no free re-aim in that branch. Removed the
inherited +alive availability bonus and zero-stock cast allowance. Regression
tests now require spent live helicopters to stay masked. Labels/probes and the
explicit schema3 migration recognize this documented semantic correction.
130 script tests,37 visualizer tests,12-step observer parity and graph tests pass.

Final mask audit corrected click/paint mode dispatch: their `place_` prefix had
incorrectly subjected them to roster membership. Planning enables both at cell0;
battle masks both. Regression reproduced failure before the fix. Owned launch
was stopped before continuing deployment; diagnostic inst13 is closed. Final
4889-input preview passed SSE/reconnect/pause/isolation and both WebGPU/Canvas2D
mobile interaction suites; preview processes were cleaned.

## Live rollout transition correction

The first production run saved four schema4 updates, then stopped safely when
select_add followed an armed placement. Shared Controls.disarm now cancels only
an active tool before additive selection or move/reaim, preserving selection.
It also serves ordinary cancel/arm, preventing divergent cancellation behavior.
The regression reproduces the exception before the fix and checks exact click
order/modifier release for all three paths. Native-mode transitions are input
plumbing; target choices and strategy remain policy-owned.

Final-width real attachment: worker44888/game40284,4889 labels,3,096,810 parameters,
no label warning, actual selected tools and normalized input0 matched browser
values in10 samples. Evidence: analysis/coverage-browser-final.json. Capture-to-
browser133-375ms (median274); capture-to-two-RAF display248-667ms (median378).
Warm forward0.198ms/plain,0.453ms/observed. First two production60-decision
planning rollouts14.46/14.24s; both timed out before battle, not successful play.

Resume preflight now accepts every known seven-slot roster, including empty slots.
A policy-selected Battleship/Oil/Mine/Garrison/ChemMine/Mortar/GasMortar roster
reproduced the old fixed-kit refusal; actual preflight passed after correction.

Post-fix native check: owned inst13 PID31520 booted to fresh L1. Armed placement
then additive selection, move and re-aim each returned to selection mode; both
placement-mode keys produced native receipts. Test game was closed in finally.
Post-fix production run2eb2247938d5 resumed policy3360e4ef2f89f803/Adam on inst14
and saved updates. Current outcomes/PIDs are in tracker; no battle success claim.

Battle-speed diagnostic reached playing at normal2x and reproduced Native snapshot
changed during read. Whole-world same-tick validation was too broad after adding
sparse terrain/fire reads. Unit SoA arrays retain the equal-count/same-tick guard;
independent systems retain bounds/map occupancy checks and retries, but may span
ticks. Observations are explicitly sampled, not an atomic whole-world snapshot.
Regression advances time after units (allowed), and during units (must retry).
The separate initial-dump failure remains under investigation.
