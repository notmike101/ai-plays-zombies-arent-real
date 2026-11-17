# Admin console commands (Ctrl+Space, in-game; extracted from exe strings)

Needs REAL modifiers (GetAsyncKeyState) - unreachable via PostMessage; reachable once
the hook DLL virtualizes modifiers. Most positional commands operate 'at the cursor'
(the game cursor). Cursor-free ones are marked [NC].

Cursor-free (harness-relevant): start outbreak, go to level [n], reset scenario, refund all,
select all placements, next/previous scenario, restart, freeze/resume, game speed 0.5-8,
cinematic mode, toggle battle stats, toggle command bar, instant win/lose, win now,
kill all zombies, arm cleanup timer, shut empty zones, clear hazards, infect everyone,
vehicles reload, reset (all) progress, unlock hardcore, debug dump, repeat outbreak,
log start/stop, special buildings, vehicle status, bus status, show zombie health.

Cursor-based (need virtual cursor): wall here, gate here, spawn garrison/turret/mine/c4/battleship/
mortar/paratroopers/civilians/zombies..., fortify zone here, stack up here, building ability,
ignite/demolish/topple building, cure/nuke/rally/missile/cluster/ac130/fire bomb/stun gas here,
call helicopter/medevac, airdrop apc/bus/tank/bulldozer, sink/hit/select bridge, controlled
demolition, seek and destroy, collapse building here, remove spawn point, officers kite/guard,
paint officers along line, burn greenspace here, shell hit here, kill zombies near cursor.

Full command names one per line:

- coop host
- coop join
- coop leave
- coop ping
- coop status
- edge spawn
- edge wave
- repeat outbreak
- debug dump
- crash test
- gpu lost test
- remove spawn point
- spawn zombie
- spawn horde
- spawn explosive zombie
- spawn shielded zombie
- spawn swimmer zombie
- start mosh pit
- mosh pit chance
- reset mosh pit tip
- spawn civilians
- spawn paratroopers
- officers kite
- officers guard walls
- airdrop decoys
- spawn mortar
- gas mortar here
- fire mortar here
- howitzer here
- mlrs here
- railgun here
- stack up here
- fortify zone here
- wall here
- gate here
- clear gates
- spawn garrison
- set building height
- cycle building roof
- cycle building use
- cycle building type
- ignite building
- demolish building
- special buildings
- building ability
- spawn turret
- reload guns
- spawn mine
- trip mines
- spawn chemical mine
- toggle place mode
- spawn spike strip
- spawn oil slick
- spawn napalm drum
- light oil
- spawn c4
- detonate c4
- spawn battleship
- cure here
- nuke here
- call to arms
- rally here
- call helicopter
- spawn apc
- apc run dry
- airdrop apc
- spawn bus
- airdrop bus
- bus status
- spawn bulldozer
- airdrop bulldozer
- spawn tank
- airdrop tank
- call medevac
- medevac leave
- vehicles reload
- tank run dry
- vehicle status
- select next deployable
- select all deployables
- select all c4
- paint officers along line
- zombie health
- show zombie health
- guns run dry
- kill all zombies
- kill zombies near cursor
- arm cleanup timer
- shut empty zones
- fire bomb here
- officer fire lookahead
- burn greenspace here
- stun gas here
- missile here
- cluster bomb here
- ac130 here
- sink bridge here
- hit bridge here
- select bridge here
- shell hit here
- topple building
- controlled demolition
- seek and destroy
- collapse building here
- clear hazards
- infect everyone
- instant win
- instant lose
- win now
- log start
- log stop
- log mark
- reset progress
- reset all progress
- unlock hardcore
- ultra locks
- next scenario
- previous scenario
- go to level [n]
- reset scenario
- refund all
- target near far
- refund unit level
- refund zone level
- select all placements
- start outbreak
- restart
- freeze the simulation
- resume
- game speed
- cinematic mode
- toggle battle stats
- toggle kills meter total
- credit kills
- toggle command bar
- feedback
- report bug
- open map editor
- expand map
- reference image
- open workshop
- reset progress
