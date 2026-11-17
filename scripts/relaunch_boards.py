"""Kill+relaunch the 3 GA boards (inst1/3/4), inject DLL, blind-nav to L3 planning.

Prints '<dir> <pid> READY|FAIL <stage>' per board. Never touches other pids.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from harness import Instance
from zar_input import VirtualInput
from env_zar import ZAREnv
OLD = [9820, 48672, 38188]
DIRS = ['inst1', 'inst3', 'inst4']
SENT = r'D:\zar-scratch\sessions\.zarvi_%d'


def kill(pids):
    for pid in pids:
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        f'Stop-Process -Id {pid} -Force -ErrorAction '
                        'SilentlyContinue'])
        try:
            os.remove(SENT % pid)
        except OSError:
            pass


def launch(d):
    wd = rf'D:\zar-scratch\game-copies\{d}'
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    f'Start-Process -FilePath '
                    f'"{wd}\\zombies-arent-real.exe" '
                    f'-WorkingDirectory "{wd}"'])


def find_new_pids(before):
    for _ in range(30):
        cur = {}
        for p in psutil.process_iter(['name', 'pid']):
            if (p.info['name'] or '').startswith('zombies'):
                try:
                    d = os.path.basename(os.path.dirname(p.exe()))
                except Exception:
                    continue
                cur[d] = p.pid
        if len([d for d in DIRS if d in cur
                and cur[d] not in before]) == 3:
            return cur
        time.sleep(1)
    return cur


def nav(pid):
    env = ZAREnv(pid)          # self-injects once per boot (sentinel)
    vi = env.vi
    time.sleep(25)                      # boot to menu
    for step, (x, y), k in [(0, (627, 821), 4), (1, (0, 0), 0),
                             (2, (424, 453), 3), (3, (866, 742), 3),
                             (4, (857, 976), 8)]:
        if x:
            vi.move_to(x, y)
            time.sleep(0.5)
            vi.click(x, y)
        if step == 1:
            vi.key_press(0x0D, sc=28)   # ENTER into menu
        time.sleep(k)
    try:
        o = env.obs()
    except Exception:
        return 'OBSFAIL'
    return 'READY' if (o.get('civ') or 0) > 90000 else f'civ{o.get("civ")}'


if __name__ == '__main__':
    before = set(OLD)
    kill(OLD)
    time.sleep(3)
    for d in DIRS:
        launch(d)
        time.sleep(2)
    time.sleep(30)
    cur = find_new_pids(before)
    for d in DIRS:
        pid = cur.get(d)
        if not pid:
            print(d, '-', 'FAIL no pid', flush=True)
            continue
        r = nav(pid)
        print(d, pid, r, flush=True)
