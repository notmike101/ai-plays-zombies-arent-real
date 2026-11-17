"""Driver for unfocused automation of Zombies Aren't Real (SOKOLAPP windows).
All coordinates are window-client pixels unless noted.

Usage:
  python game_drive.py list                          # list game windows
  python game_drive.py shot <hwnd> <out.png>         # screenshot
  python game_drive.py click <hwnd> <x> <y>          # mouse click (client coords)
  python game_drive.py move <hwnd> <x> <y>           # mouse move
  python game_drive.py key <hwnd> <vk> [sc]          # key press, vk decimal/hex, scan optional
  python game_drive.py text <hwnd> <string>          # type text (WM_CHAR)
  python game_drive.py clickshot <hwnd> <x> <y> <out.png> [delay_ms]
"""
import ctypes, ctypes.wintypes as wt, sys, time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Make this process per-monitor DPI aware so window rects / client coords are PHYSICAL
# pixels matching the (DPI-aware) game window. Otherwise Windows virtualizes them.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x100, 0x101, 0x102
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP = 0x200, 0x201, 0x202, 0x204, 0x205

# scan codes for common VKs
SC = {0x20: 0x39, 0x0D: 0x1C, 0x1B: 0x01, 0x08: 0x0E, 0x09: 0x0F, 0x11: 0x1D,
      0x10: 0x2A, 0x12: 0x38, 0x25: 0x4B, 0x26: 0x48, 0x27: 0x4D, 0x28: 0x50,
      0x46: 0x21, 0x53: 0x1F, 0x57: 0x11, 0x41: 0x1E, 0x44: 0x20, 0x42: 0x30,
      0x47: 0x22, 0x5A: 0x2C, 0x58: 0x2D, 0x43: 0x2E, 0x56: 0x2F, 0x51: 0x10,
      0x45: 0x12, 0x52: 0x13, 0x54: 0x14, 0x4D: 0x32, 0x4B: 0x25, 0x48: 0x23,
      0x31: 0x02, 0x32: 0x03, 0x33: 0x04, 0x34: 0x05, 0x35: 0x06, 0x36: 0x07,
      0x37: 0x08, 0x38: 0x09, 0x39: 0x0A, 0x30: 0x0B, 0x70: 0x3B, 0x71: 0x3C,
      0x72: 0x3D, 0x73: 0x3E, 0x74: 0x3F, 0x75: 0x40, 0x76: 0x41, 0x77: 0x42,
      0x78: 0x43, 0x79: 0x44}

def grab(hwnd, w=None, h=None):
    if w is None or h is None:
        r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
    PW_RENDERFULLCONTENT = 2
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
    class BIH(ctypes.Structure):
        _fields_ = [("sz", wt.DWORD), ("w", wt.LONG), ("h", wt.LONG), ("pl", wt.WORD),
                    ("bpp", wt.WORD), ("comp", wt.DWORD), ("szimg", wt.DWORD),
                    ("xppm", wt.LONG), ("yppm", wt.LONG), ("used", wt.DWORD), ("imp", wt.DWORD)]
    class BI(ctypes.Structure):
        _fields_ = [("h", BIH), ("c", wt.DWORD * 3)]
    bmi = BI(); bmi.h.sz = ctypes.sizeof(BIH); bmi.h.w = w; bmi.h.h = -h
    bmi.h.pl = 1; bmi.h.bpp = 32; bmi.h.comp = 0
    row = w * 4
    buf = ctypes.create_string_buffer(row * h)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.SelectObject(mem, old); gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    # BGRA -> RGBA PIL image (top-down rows: no flip needed)
    from PIL import Image
    im = Image.frombytes('RGBA', (w, h), bytes(buf.raw), 'raw', 'BGRA')
    return im

def key(hwnd, vk, sc=None, mods=(False, False)):
    sc = sc if sc is not None else SC.get(vk, 0)
    ctrl, shift = mods
    lp = 1 | (sc << 16)
    lup = lp | (1 << 30) | (1 << 31)
    if ctrl: key_down(hwnd, 0x11, SC[0x11])
    if shift: key_down(hwnd, 0x10, SC[0x10])
    time.sleep(0.02)
    key_down(hwnd, vk, sc)
    time.sleep(0.04)
    key_up(hwnd, vk, sc)
    if ctrl: key_up(hwnd, 0x11, SC[0x11])
    if shift: key_up(hwnd, 0x10, SC[0x10])

def key_down(hwnd, vk, sc=0):
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 1 | (sc << 16))

def key_up(hwnd, vk, sc=0):
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 1 | (sc << 16) | (1 << 30) | (1 << 31))

def click(hwnd, x, y, right=False):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp); time.sleep(0.03)
    down, up = (WM_RBUTTONDOWN, WM_RBUTTONUP) if right else (WM_LBUTTONDOWN, WM_LBUTTONUP)
    wparam = 2 if right else 1
    user32.PostMessageW(hwnd, down, wparam, lp); time.sleep(0.05)
    user32.PostMessageW(hwnd, up, 0, lp)

def move(hwnd, x, y):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)

def text(hwnd, s):
    for ch in s:
        user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 1)
        time.sleep(0.02)

def main():
    cmd = sys.argv[1]
    if cmd == 'list':
        import subprocess
        res = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq zombies-arent-real.exe',
                              '/FO', 'CSV'], capture_output=True, text=True)
        pids = set()
        for line in res.stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].endswith('.exe'):
                try: pids.add(int(parts[1]))
                except ValueError: pass
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def cb(hwnd, lp):
            pid = wt.DWORD(); user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.IsWindowVisible(hwnd):
                t = ctypes.create_unicode_buffer(128); user32.GetWindowTextW(hwnd, t, 128)
                if t.value:
                    r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
                    print(f"pid={pid.value} hwnd={hwnd} rect=({r.left},{r.top})-({r.right},{r.bottom})")
            return True
        user32.EnumWindows(cb, 0)
    elif cmd == 'shot':
        hwnd = int(sys.argv[2], 0); grab(hwnd).save(sys.argv[3]); print('saved', sys.argv[3])
    elif cmd == 'click':
        hwnd = int(sys.argv[2], 0); click(hwnd, int(sys.argv[3]), int(sys.argv[4])); print('clicked')
    elif cmd == 'move':
        hwnd = int(sys.argv[2], 0); move(hwnd, int(sys.argv[3]), int(sys.argv[4])); print('moved')
    elif cmd == 'key':
        hwnd = int(sys.argv[2], 0)
        vk = int(sys.argv[3], 0); sc = int(sys.argv[4], 0) if len(sys.argv) > 4 else None
        key(hwnd, vk, sc); print(f'key {vk:#x} sent')
    elif cmd == 'text':
        hwnd = int(sys.argv[2], 0); text(hwnd, sys.argv[3]); print('text sent')
    elif cmd == 'clickshot':
        hwnd = int(sys.argv[2], 0)
        click(hwnd, int(sys.argv[3]), int(sys.argv[4]))
        time.sleep(int(sys.argv[6]) / 1000 if len(sys.argv) > 6 else 0.6)
        grab(hwnd).save(sys.argv[5]); print('saved', sys.argv[5])

if __name__ == '__main__':
    main()
