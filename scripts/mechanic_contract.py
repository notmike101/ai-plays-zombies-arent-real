"""Schema4 additions. Existing schema3 feature/action prefixes stay unchanged."""
from scripts.game_mechanics import UNITS, PERKS

MISSING_UNITS = ('Sniper','Battleship','FireMortar','Railgun','Howitzer','MLRS','ChemMine','Spikes','Oil')
PANEL_ACTIONS = ('level_up','refund_level','target_toggle','detonate','vehicle_leave',
    'upgrades_page','upgrades_back') + tuple(f'building_{i}' for i in (2,3,4,5,6,7,10,11,12,14,15)) + (
    'building_officer_0','building_officer_1') + tuple(
    f'upgrade_{direction}_{i}' for direction in ('buy','refund') for i in range(4))
EXTRA_TOOLS = [f'place_{name}' for name in MISSING_UNITS] + [
    f'equip_{name}' for name in (*UNITS,'clear')] + [f'perk_{name}' for name in (*PERKS,'clear')] + [
    'select_unit','select_building','select_wall','select_gate','select_evac','select_corner',
    'select_add','select_box','move_selection','reaim_selection',
    'arm_slot','click_world','drag_world','shift_drag_world','right_click_world',
    'zone_begin','zone_corner','zone_finish','zone_back','cancel_tool','refund_selection','undo',
    'officer_mode','officer_paint','detonate_all','next_special',
    'pan_up','pan_left','pan_down','pan_right','zoom_in','zoom_out',
    'speed_half','speed_1','speed_2','speed_4'] + [f'panel_{name}' for name in PANEL_ACTIONS]

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
    'range boost','cooldown boost','reload boost','magazine boost','blast boost')
EXTRA_LABELS = GLOBAL_LABELS + [f'Selected unit {field}' for field in SELECTED_FIELDS] + [
    f'Native grid {channel} cell {i+1} (log1p count)' for channel in GRID_CHANNELS for i in range(48)] + [
    f'Native HUD {name} available (0/1)' for name in PANEL_ACTIONS]
EXTRA_LABELS += [f'Grid play area cell {i+1} (center inside: 0/1)' for i in range(48)] + [
    'Gesture anchor tool (extra tool index / 128; -1 absent)',
    'Gesture anchor cell (/ 48; -1 absent)',
    'Armed generic placement (native tool ID / 42)',
    'Armed sniper placement (0/1)','Armed turret placement (0/1)']


def extra_cell_label(tool, cell):
    if tool.startswith('equip_') or tool == 'arm_slot': return f'{tool}: planning slot {cell+1}'
    if tool.startswith('perk_'): return f'{tool}: perk slot {cell+1}'
    return f'{tool}: cell {cell+1}'
