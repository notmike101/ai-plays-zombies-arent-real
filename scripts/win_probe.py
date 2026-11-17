"""Win32 probe: find game windows, screenshot them, test unfocused PostMessage input.
Run:  python D:\\zar-scratch\\scripts\\win_probe.py <pid> <command>
Commands: list, shot <pid> <outfile>, sendkey <pid> <vk>, sendclick <pid> x y, poke <pid> <msg> <wp> <lp>
"""
import ctypes, ctypes.wintypes as wt, sys, time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

def windows_by_pid(pid):
    out = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        pidbuf = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pidbuf))
        if pidbuf.value == pid:
            out.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return out

def window_info(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    visible = user32.IsWindowVisible(hwnd)
    return dict(hwnd=hwnd, title=buf.value, cls=cls.value,
                rect=(rect.left, rect.top, rect.right, rect.bottom), visible=bool(visible))

def screenshot(hwnd, path):
    PW_RENDERFULLCONTENT = 0x00000002
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
    # BMP header
    import struct
    row = w * 4
    img_size = row * h
    header = struct.pack('<2sI', b'BM', 14 + 40 + img_size) + struct.pack(
        '<HHIIIIHH', 0, 0, 14 + 40, 40, w, h, 1, 32) + struct.pack(
        '<IIIIII', 0, img_size, 0, 0, 0, 0)
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                    ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]
    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    pixels = ctypes.create_string_buffer(row * h)
    got = gdi32.GetDIBits(mem, bmp, 0, h, pixels, ctypes.byref(bmi), 0)
    with open(path, 'wb') as f:
        f.write(header)
        f.write(pixels.raw)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem); user32.ReleaseDC(hwnd, hdc)
    return ok, got, w, h

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'list':
        # list all top-level windows of zombies processes
        import subprocess
        pids = set()
        res = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq zombies-arent-real.exe',
                              '/FO', 'CSV'], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].endswith('.exe'):
                try: pids.add(int(parts[1]))
                except ValueError: pass
        for pid in sorted(pids):
            for hwnd in windows_by_pid(pid):
                info = window_info(hwnd)
                if info['visible'] or info['title']:
                    print(pid, info)
    elif cmd == 'shot':
        hwnd = int(sys.argv[2]); path = sys.argv[3]
        print(screenshot(hwnd, path))
    elif cmd == 'sendkey':
        hwnd = int(sys.argv[2]); vk = int(sys.argv[3], 0)
        user32.PostMessageW(hwnd, 0x100, vk, 0)  # WM_KEYDOWN
        time.sleep(0.05)
        user32.PostMessageW(hwnd, 0x101, vk, 0xC0000000)  # WM_KEYUP
        print('sent', hex(vk))
    elif cmd == 'sendclick':
        hwnd = int(sys.argv[2]); x = int(sys.argv[3]); y = int(sys.argv[4])
        lp = (y << 16) | x
        user32.PostMessageW(hwnd, 0x200, 0, lp)  # WM_MOUSEMOVE
        time.sleep(0.02)
        user32.PostMessageW(hwnd, 0x201, 1, lp)  # WM_LBUTTONDOWN MK_LBUTTON
        time.sleep(0.05)
        user32.PostMessageW(hwnd, 0x202, 0, lp)  # WM_LBUTTONUP
        print('clicked', x, y)

if __name__ == '__main__':
    main()
