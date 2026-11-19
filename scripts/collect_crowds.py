"""Collect camera-aligned crowd counts from owned games using the read-only game API."""
import argparse
import ctypes
from ctypes import wintypes
import time
from pathlib import Path

import numpy as np

import local_agent as operator
import memscan
from env_zar import ZAREnv, ZAREnvError
from zar_boot import window_of_pid


class CrowdReader:
    scalar = ZAREnv.scalar
    array = ZAREnv.array
    game_state = ZAREnv.game_state
    spatial = ZAREnv.spatial

    def __init__(self, pid):
        self.pid = pid
        ZAREnv.validate_build(self)
        self.base = memscan.module_base(pid)
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetClientRect(window_of_pid(pid), ctypes.byref(rect)):
            raise OSError('No client window')
        self.cw, self.ch = rect.right, rect.bottom
        self.h = memscan.open_proc(pid)
        self.frames = []

    def sample(self):
        state = self.game_state()
        if state['phase'] != 'playing' or state['paused']:
            return
        if self.frames and state['sim'] <= self.frames[-1][0] + .15:
            return
        camera = [self.scalar(rva,'<f') for rva in (0x6553ac,0x6553b0,0x6553b4)]
        grid = self.spatial({})['counts'][:3].reshape(3,6,8)
        after = [self.scalar(rva,'<f') for rva in (0x6553ac,0x6553b0,0x6553b4)]
        if np.allclose(after,camera,rtol=0,atol=.001):
            self.frames.append((state['sim'], camera, np.log1p(grid)))

    def save(self, dest):
        if self.frames:
            sim, camera, grids = zip(*self.frames)
            np.savez_compressed(dest, sim=sim, camera=camera, grids=np.asarray(grids))

    def close(self):
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.h))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes', type=float, default=30)
    args = parser.parse_args()
    if args.minutes <= 0: parser.error('Use a positive duration')
    dest=operator.ROOT/'analysis'/('coverage-crowds-'+time.strftime('%Y%m%d-%H%M%S'))
    dest.mkdir()
    print(dest, flush=True)
    readers={}
    deadline=time.monotonic()+args.minutes*60
    scan=0.
    try:
        while time.monotonic()<deadline:
            if time.monotonic()>=scan:
                games={(p['pid'],p['create_time']) for p in operator.inventory() if p['role']=='game'}
                for key in set(readers)-games:
                    reader=readers.pop(key)
                    reader.close()
                    reader.save(dest/f'{key[0]}-{int(key[1])}.npz')
                for key in games-readers.keys():
                    try:readers[key]=CrowdReader(key[0])
                    except (OSError,ValueError,ZAREnvError):pass
                scan=time.monotonic()+3
            for reader in readers.values():
                try:reader.sample()
                except (OSError,ValueError,ZAREnvError):pass
            time.sleep(.15)
    finally:
        for key, reader in readers.items():
            reader.close()
            reader.save(dest/f'{key[0]}-{int(key[1])}.npz')


if __name__=='__main__':
    main()
