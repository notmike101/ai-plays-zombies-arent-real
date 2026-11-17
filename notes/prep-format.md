# .prep (NMPL) plan file format — partial decode

Sample: `steam_cloud/plans/Boston__MA.prep` (1577 bytes; both user's and inst2 copies —
the same file; content = the plan saved 2026-11-14 18:27, which FAILED to restore zones/units
on a fresh L5 load — only money+loadout restored. Needs verification why.)

## Header (little-endian)
```
0x00: "NMPL" magic
0x04: u32 version = 5
0x08: u32 19          <- ? (maybe carry-unit count at save time)
0x0C: u32 0
0x10: u32 2           <- ?
0x14..0x68: zeros (fixed header area, ~22 u32s)
```

## Records (map-file frame coords; live frame = map frame + map_origin (768, 3028))
A WALL-STROKE record decoded byte-exact at 0x19C:
```
f32 20.5        <- price? (walls.cost*cells? a 3.2m/2-cell wall: 0.75*2+? doesn't match directly)
f32 ax          <- 10809.291
f32 ay          <- 11617.056
f32 bx          <- 10806.716
f32 by          <- 11618.911
u32 0           <- fortify level?
u32 0           <- gate flag?
u32 3           <- stroke point count
(f32 x, f32 y) x3  <- stroke polyline: A, (10810.078,11617.312), B
```
More records follow the same shape (29.9, 34.5, 37.2 = first f32 of each — prices/lengths).
The A..B straight segment + stroke points structure matches walls ("straight-line length,
walled or not" + drawn stroke).

At 0x13E (2-byte offset drift region): repeated point pairs (10849.55, 17629.9)x2 — possibly
a degenerate zone or a zero-length wall (17629 map-frame = 14601 live — inside L5 playarea).

Trailing area ~0x500-0x560: rows of u32 = 100/200/0xb00 — counts/levels table? (looks like
per-thing level or count arrays).

## To finish the format (next session)
1. Use the hook DLL (virtual cursor) to place: one safe zone (triangle), one wall, one garrison,
   one mortar, one upgrade level → let the game autosave (leave to menu) → dump .prep.
2. Diff against the known board contents (F6 [plan] text lists every placement!) → complete schema.
3. Verify a hand-authored .prep loads on a fresh stage (READY warning % should reflect authored
   zones; F6 [plan] should list them).
4. Same for deployment recordings: deploy an ability once, dump .prep, find the [replay] rows in
   binary; then author records + features.battle_replay=true and verify re-fire.

## F6 [replay] text rows (deployment recording format, from real dumps)
```
recording = <kind> <time_s_real?> <x1> <y1> <x2> <y2> <?> <npoints> (x y) xN
```
Observed kind=0 rows with ~5m drag paths near (8770, 11577) even though NO ability was
deployed by us in that battle — meaning unclear (possibly auto-recorded something else, or
kind 0 = paratroopers and something deployed). Resolve in the controlled experiment above.
Recording times looked like REAL seconds (times 19.8-27.4 while sim_time was 9.1-23.6).
