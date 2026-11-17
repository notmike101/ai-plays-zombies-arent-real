"""Schema4 additions. Existing schema3 feature/action prefixes stay unchanged."""
from scripts.game_mechanics import UNITS, PERKS

MISSING_UNITS = ('Sniper','Battleship','FireMortar','Railgun','Howitzer','MLRS','ChemMine','Spikes','Oil')
PANEL_ACTIONS = ('level_up','refund_level','target_toggle','detonate','medevac_leave',
    'upgrades_page','upgrades_back') + tuple(f'building_{i}' for i in (2,3,4,5,6,7,10,11,12,14,15)) + (
    'building_officer_0','building_officer_1') + tuple(
    f'upgrade_{direction}_{i}' for direction in ('buy','refund') for i in range(4))
EXTRA_TOOLS = [f'place_{name}' for name in MISSING_UNITS] + [
    f'equip_{name}' for name in (*UNITS,'clear')] + [f'perk_{name}' for name in (*PERKS,'clear')] + [
    'select_unit','select_building','select_wall','select_gate','select_evac','select_corner',
    'select_add','select_box','move_selection','reaim_selection',
    'arm_slot','click_world','drag_world','shift_drag_world','right_click_world',
    'zone_begin','zone_corner','zone_finish','zone_back','cancel_tool','refund_selection','undo',
    'officer_mode','officer_paint','arm_detonation','next_special',
    'pan_up','pan_left','pan_down','pan_right','zoom_in','zoom_out',
    'speed_half','speed_1','speed_2','speed_4'] + [f'panel_{name}' for name in PANEL_ACTIONS]
EXTRA_TOOLS += ['select_helicopter','select_vehicle','select_medevac',
    'drag_corner','drag_edge','insert_corner','remove_corner','pause_toggle']
EXTRA_TOOLS += ['place_click','place_paint','dialog_confirm','dialog_cancel','corridor_wider','corridor_narrower']

# Counts retain multiplicity; selected entities expose individual state below.
GRID_CHANNELS = tuple(f'unit {name}' for name in UNITS if name not in ('Spikes','Oil')) + (
    'spike cells','oil cells') + tuple(f'building class {i}' for i in range(1,8)) + (
    'damaged buildings','walls','corridors','holds','helicopters','medevacs','vehicles',
    'hazards','selected units') + tuple(f'zombie type {i}' for i in range(8))
GLOBAL_LABELS = ['Camera X (native m / 10000)','Camera Y (native m / 10000)',
    'Camera zoom (pixels per m / 8)','Placement paint mode (0/1)',
    'READY land and budget legal (0/1)','Land covered (fraction)',
    'Draft polygon vertices (log1p count)','Selected units (log1p count)',
    'Selected zones (log1p count)','Selected helicopters (log1p count)','Selected evac zones (log1p count)']
GLOBAL_LABELS += [f'Planning slot {i+1} (native tool ID / 42)' for i in range(7)]
GLOBAL_LABELS += [f'Perk slot {i+1} {field}' for i in range(3)
                  for field in ('(native ID+1 / 8; 0 empty)','locked (0/1)')]
SELECTED_FIELDS = ('kind / 10','payload / 5','trap kind / 2','level / 4',
    'hp or magazine stock (log1p nonnegative)','rounds used or reload state / 100',
    'timer / 60','direction X','direction Y','far first (0/1)','officer kind / 2',
    'officer AI mode / 8','kills (log1p count)','converting (0/1)',
    'range multiplier (1 unmodified)','cooldown multiplier (1 unmodified)',
    'reload multiplier (1 unmodified)','magazine multiplier (1 unmodified)',
    'blast multiplier (1 unmodified)')
EXTRA_LABELS = GLOBAL_LABELS + [f'Selected unit {field}' for field in SELECTED_FIELDS] + [
    f'Native grid {channel} cell {i+1} (log1p count)' for channel in GRID_CHANNELS for i in range(48)] + [
    f'Native HUD {name} available (0/1)' for name in PANEL_ACTIONS]
EXTRA_LABELS += [f'Grid play area cell {i+1} (center inside: 0/1)' for i in range(48)] + [
    'Gesture anchor tool (extra tool index / 128; -1 absent)',
    'Gesture anchor cell (/ 48; -1 absent)',
    'Armed generic placement (native tool ID / 42)',
    'Armed sniper placement (0/1)','Armed turret placement (0/1)']
EXTRA_LABELS += ['Simulation paused (0/1)','Simulation speed (native half ticks / 8)']
EXTRA_LABELS += [f'Grid terrain cell {i+1} {field}' for field in (
    '(native code / 5; -1 outside storage)','bridge bit (0/1)') for i in range(48)]
EXTRA_LABELS += ['Selected building present (0/1)','Selected building class / 7',
    'Selected building ability / 15','Selected building officer kind / 2',
    'Selected building damage / maximum HP','Selected building area (log1p m2)',
    'Selected building height (native decimetres / 1000)']
EXTRA_LABELS += [f'Selected unit SP upgrade {i+1} (native level / 4)' for i in range(4)]


STATE_CHANNELS = ('wall HP fraction','wall breached cell fraction','wall level / 4','wall construction remaining / 60',
    'evac width / 1000','evac radius / 1000','evac attraction radius / 1000','evac hold suppressed',
    'helicopter magazine log1p','helicopter cooldown / 60','helicopter damage log1p','helicopter leaving',
    'helicopter rearm remaining / 60','helicopter mode / 8','helicopter target X / 10000','helicopter target Y / 10000',
    'vehicle kind / 4','vehicle magazine log1p','vehicle damage log1p','vehicle returning','vehicle parked',
    'vehicle rearm remaining / 60','vehicle leaving','vehicle carried log1p','vehicle landed log1p',
    'vehicle routing','vehicle plowing','vehicle goal X / 10000','vehicle goal Y / 10000',
    'medevac phase / 8','medevac carried log1p','medevac landed log1p','medevac damage log1p','medevac departure ordered',
    'hazard kind / 8','hazard radius / 1000','hazard expiry sim time / 600')
EXTRA_LABELS += [f'Native state {name} cell {i+1} (mean; 0 empty)' for name in STATE_CHANNELS for i in range(48)]

EXTRA_LABELS += ['Modal dialog open (0/1)','Corridor tool armed (0/1)',
    'Hold tool armed (0/1)','Corridor full width (native m / 1000)']


def extra_cell_label(tool, cell):
    if tool.startswith('equip_') or tool == 'arm_slot': return f'{tool}: planning slot {cell+1}'
    if tool.startswith('perk_'): return f'{tool}: perk slot {cell+1}'
    return f'{tool}: cell {cell+1}'
