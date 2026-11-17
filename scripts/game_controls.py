"""Player controls with bounded native receipts; never write native game memory."""
import time

from env_zar import ZAREnvError
from game_mechanics import UNITS, UNIT_IDS


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

    def planning_roster(self):
        names = {value: key for key, value in UNIT_IDS.items()} | {0: '-'}
        try:
            return [names[self.env.scalar(0x656228+i, '<B')] for i in range(7)]
        except KeyError as exc:
            raise ZAREnvError('Unknown native planning roster entry') from exc

    def open_loadout(self):
        e = self.env
        if (e.cw, e.ch) != (1920, 1200):
            raise ZAREnvError('Loadout controls require calibrated1920x1200')
        if e.game_state()['phase'] != 'planning':
            raise ZAREnvError('Loadout requires planning')
        e.vi.key_press(9, sc=15)
        wait_until(lambda: e.scalar(0x6553e8, '<I') == 1, 'loadout open')

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
        wait_until(lambda: e.scalar(0x6560f0, '<B'), 'picker open')
        e.vi.move_to(30, 30)
        current = e.scalar(0x656100, '<q')
        if not 0 <= current <= 72 or not 0 <= index <= 72:
            raise ZAREnvError('Invalid picker index')
        direction = 1 if index > current else -1
        while current != index:
            # Arrow keys are E0 extended scan codes, not numpad2/numpad8.
            e.vi.key_press(0x28 if direction > 0 else 0x26,
                           sc=0x150 if direction > 0 else 0x148, hold=.025)
            current += direction
            wait_until(lambda: e.scalar(0x656100, '<q') == current, 'picker selection')
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
