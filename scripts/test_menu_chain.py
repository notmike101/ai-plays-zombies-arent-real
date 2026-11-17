"""Reboot inst7 (welcome_seen now set) and blind-test the old menu chain."""
import os
import subprocess
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from PIL import Image, ImageChops, ImageStat
from zar_input import VirtualInput, window_of_pid
from win_probe import screenshot

WD = r'D:\zar-scratch\game-copies\inst7'


def gpid():
    for p in psutil.process_iter(['name', 'pid']):
        if (p.info['name'] or '').startswith('zombies'):
            try:
                if 'inst7' in p.exe():
                    return p.pid
            except Exception:
                pass
    return None


old = gpid()
if old:
    psutil.Process(old).kill()
    print('killed', old, flush=True)
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
hwnd = None
for _ in range(90):
    try:
        hwnd = window_of_pid(pid)
    except Exception:
        pass
    if hwnd:
        break
    time.sleep(1)
print('pid', pid, 'hwnd', hwnd, flush=True)
vi = VirtualInput(pid, hwnd=hwnd)
print('patches', vi.patches(), flush=True)
time.sleep(22)

prev = None


def step(tag, act=None):
    global prev
    if act:
        act()
    time.sleep(1.8)
    p = rf'D:\zar-scratch\analysis\m-{tag}.png'
    screenshot(hwnd, p)
    im0 = Image.open(p)
    im1 = im0.convert('L')
    im1.resize((im1.width // 3, im1.height // 3)).save(p)
    d = 0.0
    if prev:
        m = ImageChops.difference(Image.open(prev), Image.open(p))
        m = m.point(lambda v: 255 if v > 40 else 0)
        d = ImageStat.Stat(m).mean[0]
    print(tag, 'diff', round(d, 2), flush=True)
    prev = p


step('0-boot')
step('1-playnow', lambda: vi.click(627, 821, hold=0.12))
step('2-enter', lambda: vi.key_press(0x0D))
step('3-campaign', lambda: vi.click(424, 453, hold=0.12))
step('4-normal', lambda: vi.click(705, 765, hold=0.12))
step('5-start', lambda: vi.click(705, 926, hold=0.12))
