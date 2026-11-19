"""Player controls with bounded native receipts; never write native game memory."""
import time
from pathlib import Path

from env_zar import ZAREnvError, NATIVE_ABILITIES
from game_mechanics import UNITS, UNIT_IDS, PERKS

ABILITY_IDS = dict(zip(NATIVE_ABILITIES,
    (9, 1, 12, 11, 10, 18, 19, 23, 24, 25, 34, 35, 36, 29, 37, 38, 39, 40, 41)))
KEY_ACTIONS = {
    'officer_mode': (81,16,True), 'officer_paint': (90,44,True),
    'arm_detonation': (84,20,True), 'next_special': (70,33,True),
    'pan_up': (87,17,False), 'pan_left': (65,30,False),
    'pan_down': (83,31,False), 'pan_right': (68,32,False),
    'speed_half': (112,59,False), 'speed_1': (113,60,False),
    'speed_2': (114,61,False), 'speed_4': (115,62,False),
    'pause_toggle': (32,57,False),
    'place_click': (75,37,False), 'place_paint': (74,36,False),
}


class PickerNavigationError(ZAREnvError):
    """The picker did not reach a row and no confirmation was sent."""


def wait_until(predicate, description, timeout=.8):
    end = time.monotonic()+timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() >= end:
            raise ZAREnvError('Timed out waiting for '+description)
        time.sleep(.005)


def unit_choices(current):
    if current not in (*UNITS, '-'):
        raise ValueError('Unknown planning unit')
    return (['-'] if current != '-' else [])+[n for n in UNITS if n != current]


class Controls:
    def __init__(self, env):
        self.env = env
        env.validate_build()

    def frames(self, count=2):
        frame = self.env.scalar(0x68e590, '<Q')
        wait_until(lambda: self.env.scalar(0x68e590, '<Q') >= frame+count, 'UI frames', timeout=2.)

    def tool_active(self):
        # Discriminator bytes (e.g. corridor vs hold) persist after cancellation.
        return any(self.env.scalar(rva,'<B') for rva in (
            0x667060,0x65c488,0x65d2e1,0x65d2e2,0x65d309,0x65d30b,
            0x65d368,0x65d369,0x65cc80,0x65ddb8,0x65ddb9,
            0x6651e0,0x6651e2,0x665161,0x6651f0,0x6651f1,
            0x65d458,0x665162,0x660fd1,0x665038,0x6650c8,
            0x6650e0,0x65d30c,0x65d260,0x65d418))

    def disarm(self):
        if self.tool_active():
            self.env.vi.click(30, 60, right=True)
            self.frames()
    def cancel(self):
        self.disarm()
        # A right-click with no tool moves selected units; deselect on empty HUD space.
        self.env.vi.click(30, 60)
        self.frames()

    def arm(self, vk, sc):
        self.disarm()
        self.env.vi.key_press(vk, sc=sc)
        self.frames()

    def place(self, name, point, end=None, erase=False):
        roster = self.planning_roster()
        if name not in roster:
            raise ValueError('Unit must be equipped before placement')
        if erase and name not in ('Spikes', 'Oil'):
            raise ValueError('Only painted spikes/oil support Shift erase')
        slot = roster.index(name)
        vk, sc = [(49,2),(50,3),(51,4),(52,5),(53,6),(54,7),(84,20)][slot]
        self.arm(vk, sc)
        vi = self.env.vi
        if erase: vi.key_down(16, sc=42)
        try:
            if end is None: vi.click(*point)
            else: vi.drag(*point, *end)
        finally:
            if erase: vi.key_up(16, sc=42)
        self.frames()

    def select(self, point, end=None, additive=False):
        if not additive:
            self.cancel()
        else:
            self.disarm()
        vi = self.env.vi
        if additive: vi.key_down(16, sc=42)
        try:
            if end is None: vi.click(*point)
            else: self.drag_handles(point,end)
        finally:
            if additive: vi.key_up(16, sc=42)
        self.frames()

    def drag_handles(self, point, end):
        """Endpoint geometry needs consumed edges, not a timed paint stroke."""
        vi=self.env.vi
        vi.move_to(*point);self.frames(1)
        vi.button_down()
        try:
            self.frames()
            vi.move_to(*end);self.frames()
        finally:
            vi.button_up()
        self.frames(1)

    def move_selection(self, point, reaim=False):
        self.disarm()
        vi = self.env.vi
        if reaim: vi.key_down(16, sc=42)
        try: vi.click(*point, right=True)
        finally:
            if reaim: vi.key_up(16, sc=42)
        self.frames()

    def polygon_corner(self, point, begin=False):
        if begin: self.arm(66,48)
        elif self.env.scalar(0x65c488,'<B') != 1:
            raise ZAREnvError('No active safe-zone polygon')
        self.env.vi.click(*point)
        self.frames()

    def polygon_finish(self):
        if self.env.scalar(0x65c488,'<B') != 1:
            raise ZAREnvError('No active safe-zone polygon')
        self.env.vi.key_press(13,sc=28)
        self.frames()

    def polygon_back(self):
        if self.env.scalar(0x65c488,'<B') != 1:
            raise ZAREnvError('No active safe-zone polygon')
        self.env.vi.key_press(8,sc=14)
        self.frames()

    def refund(self, point=None):
        if point is not None: self.env.vi.move_to(*point)
        self.env.vi.key_press(88,sc=45)
        self.frames()
        if self.env.scalar(0x667868,'<B'):
            self.env.vi.key_press(13,sc=28)
            self.frames()

    def undo(self):
        self.env.vi.combo_press([17],90,sc=44)
        self.frames()

    def panel_action(self, name):
        from native_hud import read_panel
        panel = read_panel(self.env)
        if name not in panel['actions']:
            raise ZAREnvError('Unavailable native HUD action: '+name)
        self.env.vi.click(*panel['actions'][name])
        self.frames()

    def dialog(self, confirm):
        if not self.env.scalar(0x667868,'<B'):
            raise ZAREnvError('No active modal dialog')
        self.env.vi.key_press(13 if confirm else 27,sc=28 if confirm else 1)
        self.frames()
        wait_until(lambda:not self.env.scalar(0x667868,'<B'),'dialog closed')

    def key_action(self, name):
        vk,sc,shift = KEY_ACTIONS[name]
        vi = self.env.vi
        if shift: vi.key_down(16,sc=42)
        try: vi.key_press(vk,sc=sc,hold=.15 if name.startswith('pan_') else .05)
        finally:
            if shift: vi.key_up(16,sc=42)
        self.frames()
        if name in ('place_click','place_paint'):
            wait_until(lambda:self.env.scalar(0x665160,'<B')==int(name=='place_paint'),
                       'placement mode receipt')

    def gesture(self, point, end=None, shift=False, right=False):
        """Continue an armed tool or edit a native handle; selection is preserved."""
        vi = self.env.vi
        if shift: vi.key_down(16,sc=42)
        try:
            if end is None: vi.click(*point,right=right)
            elif right: raise ValueError('Right drag is not a gameplay gesture')
            else: vi.drag(*point,*end)
        finally:
            if shift: vi.key_up(16,sc=42)
        self.frames()

    def zoom(self, steps, point):
        if steps not in (-1,1): raise ValueError('Expected one zoom step')
        self.env.vi.wheel(steps,*point,gap=0)
        self.frames()

    def planning_roster(self):
        names = {value: key for key, value in UNIT_IDS.items()} | {0: '-'}
        try:
            return [names[self.env.scalar(0x656228+i, '<B')] for i in range(7)]
        except KeyError as exc:
            raise ZAREnvError('Unknown native planning roster entry') from exc

    def battle_roster(self):
        names = {value: key for key, value in ABILITY_IDS.items()} | {0: '-'}
        try:
            return [names[self.env.scalar(0x65622f+i, '<B')] for i in range(7)]
        except KeyError as exc:
            raise ZAREnvError('Unknown native battle roster entry') from exc

    def perks(self):
        result = []
        for i in range(3):
            ident, present, locked = [self.env.scalar(0x665f71+3*i+j, '<B') for j in range(3)]
            if ident >= len(PERKS) or present > 1 or locked > 1:
                raise ZAREnvError('Invalid native perk slot')
            result.append(dict(name=PERKS[ident] if present else '-', locked=bool(locked)))
        return result

    def open_loadout(self):
        e = self.env
        if (e.cw, e.ch) != (1920, 1200):
            raise ZAREnvError('Loadout controls require calibrated1920x1200')
        if e.game_state()['phase'] != 'planning':
            raise ZAREnvError('Loadout requires planning')
        e.vi.key_press(9, sc=15)
        wait_until(lambda: e.scalar(0x6553e8, '<I') == 1, 'loadout open')
        # App mode changes before the loadout's first layout/hit-test frame.
        self.frames()

    def close_loadout(self):
        e = self.env
        if e.scalar(0x6560f0, '<B'):
            e.vi.key_press(27, sc=1)
            wait_until(lambda: not e.scalar(0x6560f0, '<B'), 'picker closed')
        if e.scalar(0x6553e8, '<I') == 1:
            e.vi.key_press(9, sc=15)
        wait_until(lambda: e.scalar(0x6553e8, '<I') == 2, 'world restored')

    def pick(self, index):
        e = self.env
        try:
            wait_until(lambda: e.scalar(0x6560f0, '<B'), 'picker open')
        except ZAREnvError as exc:
            raise PickerNavigationError('Timed out waiting for picker open') from exc
        e.vi.move_to(30, 30)
        self.frames()
        current = e.scalar(0x656100, '<q')
        if not 0 <= current <= 72 or not 0 <= index <= 72:
            raise ZAREnvError('Invalid picker index')
        direction = 1 if index > current else -1
        vk, sc = (0x28, 0x150) if direction > 0 else (0x26, 0x148)
        while current != index:
            expected = current + direction
            for hold in (.05, .075):
                # Arrow keys use E0 extended scan codes.
                e.vi.key_press(vk, sc=sc, hold=hold)
                self.frames()
                try:
                    wait_until(lambda: e.scalar(0x656100, '<q') != current, 'picker selection')
                except ZAREnvError:
                    if not e.scalar(0x6560f0, '<B'):
                        raise ZAREnvError('Picker closed during arrow selection')
                actual = e.scalar(0x656100, '<q')
                if actual == expected:
                    break
                if actual != current:
                    raise PickerNavigationError(f'Picker selection moved from {current} to {actual}, expected {expected}')
            else:
                raise PickerNavigationError(f'Timed out waiting for picker selection {current} -> {expected} (target {index})')
            current = expected
        e.vi.key_press(13, sc=28)
        wait_until(lambda: not e.scalar(0x6560f0, '<B'), 'picker accepted')

    def equip_unit(self, name, slot):
        if name not in (*UNITS, '-') or not isinstance(slot, int) or not 0 <= slot < 7:
            raise ValueError('Expected a planning unit and slot0..6')
        e = self.env
        before = self.planning_roster()
        if before[slot] == name:
            return before
        choices = unit_choices(before[slot])
        self.open_loadout()
        try:
            e.vi.click(160+266*slot, 300)
            self.pick(choices.index(name))
            # Replacing an equipped unit may ask to refund its placements.
            if e.scalar(0x667868, '<B'):
                e.vi.key_press(13, sc=28)
                wait_until(lambda: not e.scalar(0x667868, '<B'), 'unequip confirmation')
            wait_until(lambda: self.planning_roster()[slot] == name, 'planning roster receipt')
            return self.planning_roster()
        finally:
            self.close_loadout()

    def change_loadout(self, name, delta):
        e = self.env
        if name not in NATIVE_ABILITIES or delta not in (-1, 1):
            raise ValueError('Expected native ability and one level change')
        before = e.loadout_levels()
        roster = self.battle_roster()
        if delta < 0 and before[name] == 0:
            raise ValueError('Cannot refund an unpurchased ability')
        if name in roster and before[name] > 0:
            slot = roster.index(name)
        else:
            slot = next((i for i, n in enumerate(roster) if before.get(n, 0) == 0), None)
            if slot is None:
                raise ValueError('No free battle roster slot')
        self.open_loadout()
        try:
            if name in roster and before[name] > 0:
                e.vi.click((244 if delta > 0 else 80)+266*slot, 794)
            else:
                order = [s.strip() for s in (Path(e.copy_dir())/'battle_order.txt').read_text().splitlines()
                         if s.strip() and not s.startswith('#')]
                if set(order) != set(NATIVE_ABILITIES) or len(order) != 19:
                    raise ZAREnvError('Invalid native battle picker order')
                unlocked = e.unlocked_abilities()
                order = [n for n in order if n in unlocked]+[n for n in order if n not in unlocked]
                current = roster[slot]
                choices = (['-'] if current != '-' else [])+[n for n in order if n != current]
                e.vi.click(160+266*slot, 680)
                self.pick(choices.index(name))
            expected = dict(before)
            expected[name] += delta
            wait_until(lambda: e.loadout_levels() == expected, 'loadout level receipt')
            return expected
        finally:
            self.close_loadout()

    def equip_perk(self, name, slot):
        if name not in (*PERKS, '-') or not isinstance(slot, int) or not 0 <= slot < 3:
            raise ValueError('Expected native perk and slot0..2')
        before = self.perks()
        if before[slot]['name'] == name:
            return before
        if before[slot]['locked'] or slot == 0:
            raise ValueError('Campaign perk slot is locked')
        choices = (['-'] if before[slot]['name'] != '-' else [])+[
            n for n in PERKS if n not in [p['name'] for p in before]]
        if name not in choices:
            raise ValueError('Perk already equipped in another slot')
        self.open_loadout()
        try:
            self.env.vi.click(330+620*slot, 950)
            self.pick(choices.index(name))
            wait_until(lambda: self.perks()[slot]['name'] == name, 'perk slot receipt')
            return self.perks()
        finally:
            self.close_loadout()
