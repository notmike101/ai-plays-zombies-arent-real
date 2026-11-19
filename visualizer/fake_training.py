"""Test-only game/clock double. No files, processes, or real input."""
from types import SimpleNamespace
import numpy as np


class FakeGame:
    fail = False

    def __init__(self, pid):
        assert pid == -1
        self.pid = pid
        self.cw, self.ch = 1920, 1200
        self.phase, self.paused = 'planning', False
        self.sim, self.calls, self.infections = 0., 0, 0
        self.keys = []
        self.vi = SimpleNamespace(key_press=self.press, click=lambda *a, **k: None)
        self.closed_log = False

    def press(self, vk, **kwargs):
        self.keys.append(vk)
        if vk == 0x20:
            if self.phase == 'planning':
                self.phase = 'playing'
            else:
                self.paused = not self.paused

    def validate_build(self):
        pass

    def to_planning(self):
        self.phase = 'planning'
        return self.obs()

    def obs(self):
        self.calls += 1
        if self.fail and self.calls == 3:
            raise RuntimeError('synthetic observation failure')
        return dict(civ=100-self.infections, zomb=10+self.infections,
                    converting=0, corpses=0, police=0, money=3111.,
                    infections=self.infections)

    def game_state(self):
        return dict(phase=self.phase, paused=self.paused, sim=self.sim,
                    mult=8., tick=int(self.sim*30))

    def dump(self):
        return {'where': {'phase': 'planning'}, 'economy': {'money': '3111'},
                'counts': {}, 'params': {}}

    def start_log(self):
        return {'wall': 100, 'session': {'stats': {'quota_base': 100}}}

    def stop_log(self):
        self.closed_log = True
        return {'phase': self.phase, 'stats': {'saved_pct': 100-self.infections}}

    def scalar(self, rva, fmt):
        assert rva == 0x667868
        return 0

    def geometry_blockers(self):
        return []

    def loadout_levels(self):
        return {}

    def battle_stock(self):
        return {}

    def roster(self):
        return ['-']*7

    def unlocked_abilities(self):
        return set()

    def spatial(self, plan):
        return dict(counts=np.zeros((5, 48)), build_targets=[None]*48)

    def retry(self):
        self.keys.extend([0x52, 0x52])

    def close(self):
        self.closed = True


class FakeClock:
    def __init__(self, game, infection_rate=0):
        self.now = 0.
        self.game = game
        self.infection_rate = infection_rate

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.game.phase == 'playing' and not self.game.paused:
            self.game.sim += seconds*8
            self.game.infections = min(100, int(self.game.sim*self.infection_rate))


class FakeMechanics:
    def __init__(self,game):
        self.game=game
        self.controls=SimpleNamespace(key_action=lambda name: game.press(113),rest_view=lambda:True)

    def refresh(self,st):
        spatial=self.game.spatial({})
        st.update(grid=spatial['counts'],build_targets=spatial['build_targets'],
                  perks=[dict(name='-',locked=False)]*3)
