"""Probe welcome-page click: hover + click Play Now on inst7 (pid auto)."""
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from PIL import Image
from zar_input import VirtualInput, window_of_pid
from win_probe import screenshot

pid = None
for p in psutil.process_iter(['name', 'pid']):
    if (p.info['name'] or '').startswith('zombies'):
        try:
            if 'inst7' in p.exe():
                pid = p.pid
        except Exception:
            pass
print('pid', pid)
hwnd = window_of_pid(pid)
vi = VirtualInput(pid, hwnd=hwnd, inject=False)
sl, st, ox, oy, cw, ch = vi._origin()
print('origin', (sl, st, ox, oy, cw, ch))
vi.enable()


def shot(tag):
    p = rf'D:\zar-scratch\analysis\w-{tag}.png'
    screenshot(hwnd, p)
    im = Image.open(p)
    im.resize((im.width // 2, im.height // 2)).save(p)
    return p


# Play Now center in window px was (783,139) of 1942x1256 window
cx, cy = 783 - ox, 139 - oy
print('client target', cx, cy)
vi.move_to(cx - 40, cy - 30)
time.sleep(0.3)
vi.move_to(cx, cy)
time.sleep(0.5)
print(shot('hover'))
vi.click(cx, cy, hold=0.12)
time.sleep(2.0)
print(shot('click'))
