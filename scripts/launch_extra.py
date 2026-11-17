"""Boot freshly cloned ZAR boards (inst7+): launch (skip if already
running), inject via ZAREnv, tile into free desktop slots, blind-nav the
menu chain to L1 planning. Prints '<dir> <pid> READY|FAIL <stage>' per
board. Never touches other pids. Nav coords verified by
relaunch_boards.py (identical windowed 1295x837 client).
"""
import ctypes
from ctypes.wintypes import RECT as WRECT, HWND as WHWND, BOOL as WBOOL, \
    DWORD
import os
import subprocess
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from env_zar import ZAREnv

SLOTS = [(0, 301), (1265, 301), (0, 904), (1265, 904)]


def launch(d):
    wd = rf'D:\zar-scratch\game-copies\{d}'
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    f'Start-Process -FilePath '
                    f'"{wd}\\zombies-arent-real.exe" '
                    f'-WorkingDirectory "{wd}"'])


def game_pids():
    out = {}
    for p in psutil.process_iter(['name', 'pid']):
        if (p.info['name'] or '').startswith('zombies'):
            try:
                d = os.path.basename(os.path.dirname(p.exe()))
            except Exception:
                continue
            out[d] = p.pid
    return out


def wait_pids(dirs):
    for _ in range(40):
        cur = game_pids()
        if all(d in cur for d in dirs):
            return cur
        time.sleep(1)
    return game_pids()


def tile(pid, x, y):
    """SetWindowPos with typed args (truncated HWND shrinks to 132x37).
    Uses wintypes.RECT so argtypes stay compatible with zar_input's."""
    user32 = ctypes.windll.user32
    user32.GetWindowThreadProcessId.argtypes = [WHWND, ctypes.POINTER(DWORD)]
    user32.GetWindowRect.argtypes = [WHWND, ctypes.POINTER(WRECT)]
    user32.SetWindowPos.argtypes = [WHWND, WHWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_uint]
    user32.IsWindowVisible.argtypes = [WHWND]
    cb_t = ctypes.WINFUNCTYPE(WBOOL, WHWND, ctypes.c_ssize_t)
    found = []

    def cb(h, _l):
        pid_out = DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid_out))
        if pid_out.value == pid and user32.IsWindowVisible(h):
            r = WRECT()
            if user32.GetWindowRect(h, ctypes.byref(r)) and \
                    (r.right - r.left) > 100:
                found.append(h)
        return True

    user32.EnumWindows(cb_t(cb), 0)
    if not found:
        return False
    user32.SetWindowPos(found[0], None, x, y, 1295, 837, 0x0040)
    r = WRECT()
    user32.GetWindowRect(found[0], ctypes.byref(r))
    return (r.right - r.left, r.bottom - r.top) == (1295, 837)


def nav(pid):
    env = ZAREnv(pid)          # self-injects once per boot (sentinel)
    vi = env.vi
    # L1-pinned (MAP-COMPLETE campaign screen) chain from launch_boards.py:
    # PlayNow -> ENTER -> CAMPAIGN -> NORMAL(705,765) -> START OVER(705,926)
    for step, (x, y), k in [(0, (627, 821), 4), (1, (0, 0), 0),
                            (2, (424, 453), 3), (3, (705, 765), 2),
                            (4, (705, 926), 12)]:
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
    c = o.get('civ') or 0
    return 'READY' if 4000 < c < 12000 else f'civ{c}'


if __name__ == '__main__':
    dirs = sys.argv[1:]
    cur = game_pids()
    missing = [d for d in dirs if d not in cur]
    for d in missing:
        launch(d)
        time.sleep(2)
    if missing:
        cur = wait_pids(dirs)
    for i, d in enumerate(dirs):
        pid = cur.get(d)
        if not pid:
            print(d, '-', 'FAIL no pid', flush=True)
            continue
        t = tile(pid, *SLOTS[i % len(SLOTS)])
        r = nav(pid)
        print(d, pid, r, 'tiled' if t else 'TILEFAIL', flush=True)
