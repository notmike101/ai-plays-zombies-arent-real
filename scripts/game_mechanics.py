"""Named mechanics of the SHA-pinned native build; keep native names, not UI labels."""

# Native perk-name table at VA0x14077e000, corroborated by en.lang/config.ini.
PERKS = ('Extra_Zones', 'Flammable_Gas', 'Fall_Gas', 'Officer_Blast',
         'Weak_Bridges', 'Blast_Gas', 'Hot_Fire', 'Quick_Deploy')

# Planning picker order, verified against the native loadout UI.
UNITS = ('Garrison', 'Sniper', 'Mortar', 'Nest', 'Mine', 'C4', 'Battleship',
         'GasMortar', 'FireMortar', 'Railgun', 'Howitzer', 'MLRS', 'ChemMine',
         'Spikes', 'Oil', 'Napalm')
UNIT_IDS = dict(zip(UNITS, (4, 2, 3, 5, 6, 7, 20, 21, 22, 28, 26, 27, 30, 31, 32, 33)))
