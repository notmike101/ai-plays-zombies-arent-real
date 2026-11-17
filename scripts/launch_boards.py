"""Kill + relaunch any set of ZAR game copies, inject DLL, blind-nav to campaign
planning. Usage: python scripts/launch_boards.py inst1 inst5 [dirs...]
Kills only processes whose exe lives in game-copies/<dir>. Prints '<dir> <pid>
READY|FAIL <detail>' per board (civ>90000 = planning reached)."""
import os
import subprocess
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from harness import Instance
from env_zar import ZAREnv

SENT = r'D:\zar-scratch\sessions\.zarvi_%d'


def cur_pids(dirs):
    out = {}
    for p in psutil.process_iter(['name', 'pid']):
        if (p.info['name'] or '').startswith('zombies'):
            try:
                d = os.path.basename(os.path.dirname(p.exe()))
            except Exception:
                continue
            if d in dirs:
                out[d] = p.pid
    return out


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


def nav(pid):
    env = ZAREnv(pid)          # self-injects once per boot (sentinel)
    vi = env.vi
    time.sleep(25)             # boot to menu
    # PlayNow -> ENTER -> CAMPAIGN -> NORMAL -> CONTINUE(level from file)
    for step, (x, y), k in [(0, (627, 821), 4), (1, (0, 0), 0),
                            (2, (424, 453), 3), (3, (866, 742), 3),
                            (4, (857, 976), 8)]:
        if x:
            vi.move_to(x, y)
            time.sleep(0.5)
            vi.click(x, y)
        if step == 1:
            vi.key_press(0x0D, sc=28)
        time.sleep(k)
    try:
        o = env.obs()
    except Exception:
        return 'OBSFAIL'
    return 'READY' if (o.get('civ') or 0) > 90000 else f'civ{o.get("civ")}'


if __name__ == '__main__':
    dirs = sys.argv[1:] or ['inst1', 'inst3', 'inst4']
    kill(list(cur_pids(dirs).values()))
    time.sleep(3)
    for d in dirs:
        launch(d)
        time.sleep(2)
    time.sleep(30)
    for attempt in range(3):
        cur = cur_pids(dirs)
        for d in dirs:
            pid = cur.get(d)
            if not pid:
                print(d, '-', 'FAIL no pid', flush=True)
                continue
            r = nav(pid)
            print(d, pid, r, flush=True)
        break
