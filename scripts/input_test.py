"""Test unfocused input on a SOKOLAPP window via PostMessage with proper scan codes.
Usage: python input_test.py <hwnd>
Sends: Space (sc 0x39), screenshots before/after, diffs.
"""
import ctypes, ctypes.wintypes as wt, sys, time, struct

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x100, 0x101, 0x102
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x200, 0x201, 0x202

def grab(hwnd, w, h):
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
    return bytearray(buf.raw)

def diffcount(a, b):
    return sum(1 for i in range(0, min(len(a), len(b)), 4)
               if a[i:i+3] != b[i:i+3])

def rect_of(hwnd):
    r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top

hwnd = int(sys.argv[1], 0)
w, h = rect_of(hwnd)
print(f"hwnd={hwnd:#x} size={w}x{h}")

before = grab(hwnd, w, h)

def key(vk, sc):
    lp_down = 1 | (sc << 16)
    lp_up = 1 | (sc << 16) | (1 << 30) | (1 << 31)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lp_down)
    time.sleep(0.03)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, lp_up)

def click(x, y):
    lp = (y << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp); time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lp); time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)

key(0x20, 0x39)          # Space
time.sleep(1.0)
after = grab(hwnd, w, h)
print("diff after space:", diffcount(before, after), "pixels")

click(w // 2, h // 2)    # center click
time.sleep(1.0)
after2 = grab(hwnd, w, h)
print("diff after click:", diffcount(after, after2), "pixels")
