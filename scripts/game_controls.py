"""Player controls with bounded native receipts; never write native game memory."""
import time
from pathlib import Path

from env_zar import ZAREnvError, NATIVE_ABILITIES
from game_mechanics import UNITS, UNIT_IDS, PERKS

ABILITY_IDS = dict(zip(NATIVE_ABILITIES,
    (9, 1, 12, 11, 10, 18, 19, 23, 24, 25, 34, 35, 36, 29, 37, 38, 39, 40, 41)))


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
        frame = e.scalar(0x68e590, '<Q')
        wait_until(lambda: e.scalar(0x68e590, '<Q') >= frame+2, 'loadout layout')

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
