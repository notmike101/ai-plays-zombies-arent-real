"""Live, screenshot-free acceptance test. Owns and always kills its test copy.

Run: python -B scripts/test_interface.py --copy inst4 --repeat 2
Logs are saved under analysis/interface-<timestamp>.log; nonzero means failure.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import json
import math
import sys
import time
import traceback

from zar_boot import ROOT, COPIES, boot, copy_processes, stop


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def check(name, condition, detail):
    print(f'{"PASS" if condition else "FAIL":4} | {name:24} | {detail}', flush=True)
    if not condition:
        raise AssertionError(name)


def snapshot(env):
    # Dump names have one-second precision; prevent an overwrite being mistaken
    # for a missing dump by the existing public env.dump implementation.
    time.sleep(1.1)
    data = env.dump()
    if not data:
        raise AssertionError(f'No fresh world dump: obs={env.obs()} section={env.vi.diagnostics()}')
    print(json.dumps({k: data.get(k) for k in ('where', 'view', 'economy')}) , flush=True)
    return data


def money(data):
    return float(data['economy']['money'])


def exercise(env):
    vi = env.vi
    initial = snapshot(env)
    check('fresh L1', env.obs()['money'] == 3111 and env.obs()['civ'] > 5000
          and money(initial) == 3111 and initial['where']['phase'] == 'planning', env.obs())
    point = lambda x, y: (round(x * env.cw), round(y * env.ch))
    # The empty board guarantees the low-shelter confirmation exists.
    vi.key_press(0x20, sc=57, hold=.15)
    time.sleep(.4)
    vi.click(*point(.59, .567), hold=.15)
    cancelled = snapshot(env)
    check('dialog NO click', cancelled['where']['phase'] == 'planning'
          and env.obs()['zomb'] == 0, 'posted click cancels READY, no battle')
    vi.key_press(0x31, sc=2)
    time.sleep(.25)
    vi.click(*point(.5, .5), hold=.15)
    placed = snapshot(env)
    check('one garrison click', money(placed) < money(initial)
          and int(placed['counts']['garrisons']) == 1,
          f'money {money(initial)} -> {money(placed)}; garrisons={placed["counts"]["garrisons"]}')

    vi.click(*point(.5, .5), right=True)
    vi.key_press(0x42, sc=48)
    time.sleep(.25)
    corners = [point(x / 1920, y / 1200) for x, y in
               [(800, 400), (1000, 400), (1000, 600), (800, 600)]]
    # This build commits corners on presses, not every held movement sample.
    # Each segment supplies its start corner; Enter closes the polygon.
    for a, b in zip(corners, corners[1:] + corners[:1]):
        vi.drag(*a, *b, steps=6, hold=.08)
        time.sleep(.2)
    vi.key_press(0x0D, sc=28)
    zone = snapshot(env)
    check('zone segment drags', money(zone) < money(placed)
          and int(zone['counts']['walls']) > int(placed['counts']['walls']),
          f'money {money(placed)} -> {money(zone)}; walls={zone["counts"]["walls"]}')

    vi.click(*point(.5, .5), right=True)
    vi.key_press(0x5A, sc=44)
    time.sleep(.25)
    vi.drag(*point(700 / 1920, 700 / 1200), *point(900 / 1920, 700 / 1200))
    vi.click(*point(900 / 1920, 700 / 1200))
    wall = snapshot(env)
    check('wall start/end gesture', money(wall) < money(zone)
          and int(wall['counts']['walls']) > int(zone['counts']['walls']),
          f'money {money(zone)} -> {money(wall)}; walls={wall["counts"]["walls"]}')

    vi.click(*point(.5, .5), right=True)
    vi.move_to(*point(1100 / 1920, 500 / 1200))
    before = snapshot(env)['view']
    vi.wheel(1)
    after = snapshot(env)['view']
    delta = math.dist(tuple(map(float, before['cursor'].split())),
                      tuple(map(float, after['cursor'].split())))
    check('wheel zoom anchor', float(after['camera_zoom']) > float(before['camera_zoom'])
          and delta < 1.0,
          f'zoom {before["camera_zoom"]} -> {after["camera_zoom"]}; anchor drift={delta:.3f}')
    vi.wheel(-1)
    restored = snapshot(env)['view']
    check('reverse wheel', abs(float(restored['camera_zoom']) - float(before['camera_zoom'])) < .001,
          f'zoom={restored["camera_zoom"]}')

    vi.key_press(0x70, sc=59)  # Normal 1x speed; inherited dev speed is not a difficulty setting.
    vi.key_press(0x20, sc=57, hold=.15)
    time.sleep(.4)
    if not env.obs()['zomb']:
        vi.key_press(0x20, sc=57, hold=.15)
    deadline = time.monotonic() + 8
    obs = env.obs()
    while not obs['zomb'] and time.monotonic() < deadline:
        time.sleep(.1)
        obs = env.obs()
    check('READY + SPACE battle', obs['zomb'] > 0, obs)
    # Exercise the existing public recovery method, not a new replacement.
    env.to_planning()
    resumed = snapshot(env)
    check('R resume to planning', resumed['where']['phase'] == 'planning'
          and env.obs()['zomb'] == 0, env.obs())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copy', default='inst4')
    parser.add_argument('--repeat', type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    path = COPIES / args.copy
    log = ROOT / 'analysis' / f'interface-{datetime.now():%Y%m%d-%H%M%S}.log'
    failed = False
    with log.open('w', encoding='utf-8') as file:
        tee = Tee(sys.stdout, file)
        with redirect_stdout(tee), redirect_stderr(tee):
            print(f'Log: {log}')
            for run in range(args.repeat):
                env = None
                print(f'\nFresh boot {run + 1}/{args.repeat}', flush=True)
                try:
                    env = boot(path)
                    exercise(env)
                except Exception:
                    failed = True
                    traceback.print_exc()
                finally:
                    if env is not None:
                        stop(env)
                    remaining = [p.pid for p in copy_processes(path)]
                    check('cleanup', not remaining, f'remaining={remaining}')
                if failed:
                    break
            print(f'\n{"FAIL" if failed else "PASS"} interface acceptance ({args.repeat} requested boots)')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
