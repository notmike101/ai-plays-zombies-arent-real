"""Drop Cure on the densest horde cluster. Usage: python cure_drop.py PID [slot]"""
import sys, time, glob, os
sys.path.insert(0, r'D:\zar-scratch\scripts')
from recover import make_game
from harness import grab
from zar_input import VirtualInput
import win32gui, win32api, win32con
import numpy as np
from PIL import Image

PID = int(sys.argv[1])
SLOT = sys.argv[2] if len(sys.argv) > 2 else '1'
g = make_game(PID, False)
vi = VirtualInput(PID, g.hwnd)
hwnd = g.hwnd
L, T, R, Bm = win32gui.GetWindowRect(hwnd)
W, H = R - L, Bm - T

def sc2(px, py):
    return L + px * W / 1942.0, T + py * H / 1256.0

def click(px, py, d=0.5, count=1):
    x, y = sc2(px, py)
    win32api.SetCursorPos((int(x), int(y))); time.sleep(0.15)
    for _ in range(count):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); time.sleep(0.06)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0); time.sleep(0.12)
    time.sleep(d)

# snapshot map, find dense white-dot cluster outside zones (map region rows 60-640, cols 280-1250)
png = r'D:\zar-scratch\analysis\_scan.png'
grab(hwnd).save(png)
im = np.array(Image.open(png).convert('L'))[60:640, 280:1250].astype(np.int32)
mask = im > 225
ys, xs = np.nonzero(mask)
print('bright px:', len(xs))
if len(xs) < 20:
    print('no dense horde visible - battle probably not started or camera zoomed')
    sys.exit(1)
from collections import Counter
c = Counter(((y // 30, x // 30) for y, x in zip(ys, xs)))
(gy, gx), n = c.most_common(1)[0]
px, py = 280 + gx * 30 + 15, 60 + gy * 30 + 15
print(f'cluster n={n} at png({px},{py})')

# arm Cure via battle-bar hotkey then click cluster
vk = {'1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34}[SLOT]
vi.key_press(vk, sc={'1': 2, '2': 3, '3': 4, '4': 5}[SLOT])
time.sleep(0.6)
click(px, py)   # drop target (arrives in ~12 s)
print('dropped; screenshot after 14 s')
time.sleep(14)
grab(hwnd).save(r'D:\zar-scratch\analysis\cure_after.png')
