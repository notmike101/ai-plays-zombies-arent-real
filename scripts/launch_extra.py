"""Boot freshly cloned ZAR boards (inst7+): launch, inject via ZAREnv,
blind-nav menu chain to L1 planning, tile into the two free desktop slots.
Prints '<dir> <pid> READY|FAIL <stage>' per board. Never touches other pids.
Nav coords verified by relaunch_boards.py (identical windowed 1295x837).
"""
import ctypes
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


def find_new(before, dirs):
    for _ in range(40):
        cur = game_pids()
        if all(cur.get(d) and cur[d] not in before for d in dirs):
            return cur
        time.sleep(1)
    return game_pids()


def tile(pid, x, y):
    """SetWindowPos with typed args (truncated HWND shrinks to 132x37)."""
    user32 = ctypes.windll.user32
    HWND = ctypes.c_void_p
    BOOL = ctypes.c_bool

    class RECT(ctypes.Structure):
        _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long),
                    ('r', ctypes.c_long), ('b', ctypes.c_long)]

    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(
        ctypes.c_ulong)]
    user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]
    user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_uint]
    user32.IsWindowVisible.argtypes = [HWND]
    cb_t = ctypes.WINFUNCTYPE(BOOL, HWND, ctypes.c_ssize_t)
    found = []

    def cb(h, _l):
        pid_out = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid_out))
        if pid_out.value == pid and user32.IsWindowVisible(h):
            r = RECT()
            if user32.GetWindowRect(h, ctypes.byref(r)) and \
                    (r.r - r.l) > 100:
                found.append(h)
        return True

    user32.EnumWindows(cb_t(cb), 0)
    if not found:
        return False
    user32.SetWindowPos(found[0], None, x, y, 1295, 837, 0x0040)
    r = RECT()
    user32.GetWindowRect(found[0], ctypes.byref(r))
    return (r.r - r.l, r.b - r.t) == (1295, 837)


def nav(pid):
    env = ZAREnv(pid)          # self-injects once per boot (sentinel)
    vi = env.vi
    time.sleep(28)             # boot to menu
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
    c = o.get('civ') or 0
    return 'READY' if 4000 < c < 12000 else f'civ{c}'


if __name__ == '__main__':
    dirs = sys.argv[1:]
    before = set(game_pids().values())
    for d in dirs:
        launch(d)
        time.sleep(2)
    cur = find_new(before, dirs)
    for i, d in enumerate(dirs):
        pid = cur.get(d)
        if not pid:
            print(d, '-', 'FAIL no pid', flush=True)
            continue
        t = tile(pid, *SLOTS[i % len(SLOTS)])
        r = nav(pid)
        print(d, pid, r, 'tiled' if t else 'TILEFAIL', flush=True)
