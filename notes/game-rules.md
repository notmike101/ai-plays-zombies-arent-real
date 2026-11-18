# Game rules (from config.ini — the game's own design doc)

## The loop
1. **Planning** (no zombies exist, game opens paused): draw safe zones (B), standalone walls (Z),
   gates (G), fortify (F), place units (1-7 loadout keys / planning bar), evac zones (E/Q corridor/hold),
   buy tower upgrades with SP. Money is spent here only.
2. **READY (Space)** → outbreak: rolls `spawns` sites on random civilians OUTSIDE all zones
   (hidden until it starts), lays `zombies_per_spawn` zombies each. New roll every READY (stored
   as seed file). Warning dialog if zones shelter < bronze share.
3. **Battle**: zombies hunt (flock/scent/flow fields), bite civilians (they turn), chew walls
   (per-cell HP), player deploys battle abilities bought with SP. Normal policy speeds1/2x,1x,2x,4x; developer8x is excluded.
4. **End**: horde wiped → badge by % civilians alive. Bronze (4% default) = win line; run lost
   outright only when EVERY civilian is dead. Stalled-horde cleanup timer (10s quiet + 30s
   countdown → remaining zombies die = win).

## Boston, MA campaign (`campaigns/Boston_MA.cmp`)
- Map `custom_us_boston_d13ba0.map` (36 MB, Boston harbor area incl. airport/islands).
- 5 stages, NESTING play areas (each contains the previous): stage polygons in the .cmp.
- Civilians per stage: 8128 / 25746 / 101119 / 201321 / 211128 (money+SP follow the crowd; actual
  seeded crowd for L5 measured at 203,426 civilians + outbreak).
- land_km2 = 67.33, origin_lon/lat, map_mx/my (geo transform).
- Stage 5 (Level 5): big polygon covering central Boston + harbor + airport. Money ≈ $6,602 fresh
  (money_base 1000 + grant ~5,602), plus carried money (user save had $27,317 carried) and carried
  placements from earlier stages.
- Boston's own perk: **EXTRA SAFE ZONES** (+3 zones, campaign_extra_zones = Boston_MA).
- Win line: bronze 4% default (badges rise per stage for higher tiers).

## Money & SP (defaults)
- Stage money = money_base(1000) + money_grant_max(6000) × C/(C+15000). Boston L5 ≈ $6,602 fresh.
- SP = 1 + 1×sqrt(min(C,20000)/10000) + 9×(sqrt(C/10000)−sqrt(2)). Boston L5 ≈ 31 SP.
- Unspent money carries to next stage + unspent_bonus_percent (0 default) — save your money!
- Won stage adds that stage's money at READY + bonus on top of next stage's grant.

## Safe zones & walls ([safe_zone], [walls])
- Lasso tool (B): priced walls.cost ($0.75) per 2m cell of outline + land_cost ($0.5) × sqrt(land m²)
  per safe area + start_fee $100/zone. Zone count limit: free_zones(4) + 1/level past first (L5: 8)
  + perk (Boston: +3 → 11 zones max!). Land cap: zones ≤ ~12-30% of stage land (interpolated by
  sqrt(land), 67 km² → close to large cap 12%).
- Walls: 1200 HP/cell (fortify ×3/6/12/24 per level, 4 levels max), 1 HP/s per chewing zombie
  + pressure (crowd behind front row pushes: +0.05 HP/s per nearby zombie up to 60). Breach radius 3m.
- Zombies can't enter zones until breach; civilians outside walk IN through walls (one-way) —
  a civilian outside near a gate (80m lure radius) runs to it. Civilians inside don't panic while
  their region holds; once breached, they panic and flee.
- Gates ($50, 20m) let civilians cross; officers pass; zombies chew them like wall.

## Units (planning placements, money) — full training availability
- Garrison (holds a building; reach/price scale with building width), Sniper, Mortar, Nest(Turret),
  Mine, C4, Battleship, GasMortar, FireMortar, Railgun, Howitzer, MLRS, ChemMine,
  Spikes, Oil, Napalm. Full order in unlocks.ini section of notes.
- Cost increase: each copy on board +cost_increase to next price; refund returns dearest step.
- Special buildings ([building_class]): fuel (gas stations explode — chain!), armory (reload
  faster/speed/range/command post), civic (police officers/militia/broadcast/radio tower +50% range),
  medic (officers survive first bite), airlift (airport evacuates civilians = saved), evacuate
  (train/metro/bus stations evacuate), trade (money discount 20% in 300m/reduced cost/repair walls).
  MUST be wholly inside zones. Density cap: 2 largest per 1km cell.
- Trade/Budget discounts stack +10% per extra building.

## Battle abilities (SP; loadout 1-7 slots)
Police (paratroopers, 19 SP-stock in user save), Bomber, Heli, Stungas, Firebomb, CallArms, APC,
Rally, Bus, Missile, Medevac, Dozer, Tank, Cure, Nuke, Demolition, SeekDestroy, Cluster, AC130.
Levels make recharges faster. Deploy = arm via slot key, then click/drag at position (mouse needed —
virtual DLL/PostMessage only in training; never author battle replay strategy).

## Zombies
- hp 1→30 growth (3/min after 60s delay), speed 26±12 u/s, civilians flee at ~half zombie speed
  (85% at 12-14, 15% at 14-16 u/s → most zombies catch most civilians).
- spacing 1m; flow/scent/flock fields; LOD far-zombie steps; pile rest.
- Mosh pits (15s checks, 20% on last stage, max 4 live): zombies stop & churn 10s then turn
  explosive/shielded/giant/swimmer (weights 2/1/0/2). Explosive = wall breaker (10% wall hp per
  blast), shielded = -3 per hit, giant = merge 10 (hp ×9), swimmer = crosses water.
- Outbreak sites: spawns = 2.15 × land_km2^0.25 → Boston L5 (67.33 km²) ≈ 2.15 × 2.86 ≈ 6 sites
  (verified: 6 sites observed). 200 zombies/site (+40/campaign level past first: L5 = +160 → 360/site,
  2,160 total; measured 8,601 at tick 273 — hmm, more than 2,160; recheck: zombies_per_spawn_per_level
  applies per campaign level; maybe spawns differ — verify from a dump).
- Infection: touch radius 3m, 0.1s pause, then convert (green). Corpses raise danger; panic spreads.

## Civilians
- Seeded per building footprint (0.02 /m²), cap 3150/km² of last-stage land.
- Panic: 0..1 level, danger grid (40m cells) raises it; at 0.5 they flee (half zombie speed),
  spread danger, jitter. Calm walk 3 u/s.
- Safe zone walls are one-way for civilians: outside→in freely, inside stays.

## Camera/zoom
- zoom 0.05..8 px per world unit; WASD pan; Shift+W/S zoom; middle-drag pan; Alt+middle tilt/turn 3D;
  fov 35° perspective with 3D buildings (heights from OSM), shadows; Civilians/zombies are dots
  (6 world units, min 1px / max 6px on screen).

## HUD/admin
- Ctrl+Space admin console (in-game only, needs GetKeyState modifiers — unreachable via PostMessage;
  training must never use the console or physical input).
- HUD: STATS panel (civilians left, zombies, kills), battle bar bottom, loadout TAB, retry R.

## Unlock progression (steam_cloud/unlocks.ini, global)
- This save has: Police, Sniper, Mortar, Garrison, Nest, Bomber, Stungas, Heli (+breach_restarts=1).
- Unlock sources: first win of every scenario, 2 retrys-after-breach each.
- Sandbox (Free Play switch) = everything unlocked + unlimited money/stock (can't be set by mods).
