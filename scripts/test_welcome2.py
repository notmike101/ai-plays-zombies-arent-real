"""Welcome-page dismissal sweep: keys, wheel, foreground SendMessage click."""
import ctypes
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from PIL import Image, ImageChops
from zar_input import VirtualInput, window_of_pid
from win_probe import screenshot

user32 = ctypes.windll.user32
user32.SendMessageW.restype = ctypes.c_long
user32.SendMessageW.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_void_p]

pid = None
for p in psutil.process_iter(['name', 'pid']):
    if (p.info['name'] or '').startswith('zombies'):
        try:
            if 'inst7' in p.exe():
                pid = p.pid
        except Exception:
            pass
hwnd = window_of_pid(pid)
vi = VirtualInput(pid, hwnd=hwnd, inject=False)
print('pid', pid, 'hwnd', hwnd)


def shot(tag):
    p = rf'D:\zar-scratch\analysis\w2-{tag}.png'
    screenshot(hwnd, p)
    im = Image.open(p).convert('RGB')
    im.resize((im.width // 2, im.height // 2)).save(p)
    return p


def diff(a, b):
    d = ImageChops.difference(Image.open(a), Image.open(b))
    return sum(d.histogram()[256:])  # non-black pixels


base = shot('a')
print('base', base)

# 1) keys
for name, vk in (('space', 0x20), ('enter', 0x0D), ('esc', 0x1B)):
    vi.key_press(vk)
    time.sleep(1.2)
    p = shot('k-' + name)
    print(name, 'diff', diff(base, p), flush=True)
    if diff(base, p) > 5000:
        base = p
        break

# 2) real foreground + SendMessage mouse click on Play Now (772,94) client
user32.SetForegroundWindow(hwnd)
time.sleep(0.4)


def smclick(cx, cy):
    lp = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
    user32.PostMessageW(hwnd, 0x0200, 0, lp)      # WM_MOUSEMOVE
    time.sleep(0.3)
    user32.SendMessageW(hwnd, 0x0201, 1, lp)      # WM_LBUTTONDOWN
    time.sleep(0.12)
    user32.SendMessageW(hwnd, 0x0202, 0, lp)      # WM_LBUTTONUP


smclick(772, 94)
time.sleep(2.0)
p = shot('sm')
print('smclick diff', diff(base, p), flush=True)
