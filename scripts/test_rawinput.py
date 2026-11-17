"""DLL v2 raw-input pump test (2026-11-17): reboot inst7 windowed, inject v2,
boot to title, then verify raw_sent increments + title-menu click response."""
import os
import subprocess
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from zar_input import VirtualInput, window_of_pid
from win_probe import screenshot

WD = r'D:\zar-scratch\game-copies\inst7'
OUT = r'D:\zar-scratch\analysis'


def gpid():
    for p in psutil.process_iter(['name', 'pid']):
        if (p.info['name'] or '').startswith('zombies'):
            try:
                if os.path.basename(os.path.dirname(p.exe())) == 'inst7':
                    return p.pid
            except Exception:
                pass
    return None


# 1. kill current inst7 + known strays (old inst7 17068, stray inst1 30232)
cur = gpid()
for pid in [17068, 30232] + ([cur] if cur else []):
    try:
        psutil.Process(pid).kill()
        print('killed', pid, flush=True)
    except Exception as e:
        print('skip', pid, e, flush=True)
time.sleep(2)

subprocess.run(['powershell', '-NoProfile', '-Command',
                f'Start-Process -FilePath "{WD}\\zombies-arent-real.exe" '
                f'-WorkingDirectory "{WD}"'])
pid = None
for _ in range(60):
    pid = gpid()
    if pid:
        break
    time.sleep(1)
print('inst7 pid', pid, flush=True)
assert pid

hwnd = None
for _ in range(90):
    try:
        hwnd = window_of_pid(pid)
    except Exception:
        pass
    if hwnd:
        break
    time.sleep(1)
print('hwnd', hwnd, flush=True)
assert hwnd

vi = VirtualInput(pid, hwnd=hwnd)
time.sleep(1.0)
print('patches', vi.patches(), 'raw_sent0', vi.raw_sent(), flush=True)

time.sleep(22)  # boot to title/splash
vi.key_press(0x20)  # SPACE: dismiss boot onboarding splash
time.sleep(1.5)
p0 = os.path.join(OUT, 'raw-boot.png')
screenshot(hwnd, p0)
print('shot0', p0, flush=True)

vi.enable()
n0 = vi.raw_sent()
for x, y in [(200, 300), (280, 430), (337, 503)]:
    vi.move_to(x, y)
    time.sleep(0.2)
time.sleep(0.4)
n1 = vi.raw_sent()
screenshot(hwnd, os.path.join(OUT, 'raw-hover.png'))
vi.click(337, 503, hold=0.12)
time.sleep(1.5)
n2 = vi.raw_sent()
screenshot(hwnd, os.path.join(OUT, 'raw-click.png'))
print('raw_sent moves +%d click +%d patches=%d' % (n1 - n0, n2 - n1, vi.patches()),
      flush=True)
