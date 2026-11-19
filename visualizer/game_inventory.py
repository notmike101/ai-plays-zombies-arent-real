"""Identify owned campaign game windows without requiring policy telemetry."""
from pathlib import Path
import re
import time

import psutil

TRAINERS = {'team_search.py', 'train_run.py', 'nn_play2.py'}


class GameInventory:
    def __init__(self, root):
        self.copies = root / 'game-copies'
        self.launchers = {root / 'scripts' / name for name in TRAINERS}
        self.records = ()
        self.owned_pids = frozenset()
        self.updated = float('-inf')

    def snapshot(self):
        return self.records if time.monotonic() - self.updated < 3 else ()

    def observed_pids(self):
        return self.owned_pids if time.monotonic() - self.updated < 3 else ()

    def run(self, stopped):
        while not stopped.is_set():
            self.records = tuple(self.scan())
            self.updated = time.monotonic()
            stopped.wait(1)

    def scan(self):
        owned_pids = set()
        for process in psutil.process_iter(['name', 'exe']):
            info = process.info
            if (info['name'] or '').lower() != 'zombies-arent-real.exe' or not info['exe']:
                continue
            try:
                exe = Path(info['exe']).resolve()
                if exe.parent.parent != self.copies or not re.fullmatch(r'inst[0-9]+', exe.parent.name):
                    continue
                if not process.is_running():
                    continue
                owned_pids.add(process.pid)
                if not self.owns(process):
                    continue
                created = process.create_time()
                yield {'id': f'game:{process.pid}:{round(created * 1_000_000)}',
                       'game_pid': process.pid, 'copy': exe.parent.name, 'observed_at': time.time()}
            except (psutil.Error, OSError):
                continue
        self.owned_pids = frozenset(owned_pids)

    def owns(self, process):
        for parent in process.parents():
            try:
                for arg in parent.cmdline():
                    path = Path(arg)
                    if path.name in TRAINERS and (Path(parent.cwd()) / path).resolve() in self.launchers:
                        return True
            except (psutil.Error, OSError):
                continue
        return False
