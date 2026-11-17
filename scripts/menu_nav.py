"""Legacy menu helpers using the safe VirtualInput/PostMessage interface.

New screenshot-free callers should use zar_boot.boot. Capture coordinates here
are window-image pixels; click_cap subtracts the actual client origin.
"""
import ctypes
import time
from ctypes import wintypes

from PIL import Image, ImageChops

from harness import grab

user32 = ctypes.windll.user32


class MenuDriver:
    """One instance's menus (windowed mode; hwnd by pid)."""

    def __init__(self, pid):
        self.pid = pid
        self.H = None
        import win32gui
        import win32process

        def cb(h, _):
            if win32gui.IsWindowVisible(h) and 'zombies' in win32gui.GetWindowText(h).lower():
                _, wp = win32process.GetWindowThreadProcessId(h)
                if wp == pid:
                    self.H = h
        win32gui.EnumWindows(cb, None)
        if not self.H:
            raise RuntimeError(f'no window for pid {pid}')

        from zar_input import VirtualInput
        self.vi = VirtualInput(pid, hwnd=self.H)
        self.vi.enable()

    # ---- low-level input --------------------------------------------------------
    def key(self, vk, sc, ext=False, n=1, gap=0.45, drain=2.0):
        lp = 1 | (sc << 16) | (0x1000000 if ext else 0)
        for _ in range(n):
            user32.PostMessageW(self.H, 0x100, vk, lp)
            time.sleep(0.05)
            user32.PostMessageW(self.H, 0x101, vk, lp | 0xC0000000)
            time.sleep(gap)
        time.sleep(drain)

    def arrow(self, direction, n=1):
        """List navigation; EXTENDED bit is mandatory (without it: dead)."""
        vk, sc = {'up': (0x26, 0x48), 'down': (0x28, 0x50)}[direction]
        self.key(vk, sc, ext=True, n=n)

    def wheel(self, steps, gap=0.5, drain=1.0):
        for _ in range(abs(steps)):
            d = 120 if steps > 0 else -120
            user32.PostMessageW(self.H, 0x020A, (d & 0xFFFF) << 16, 0)
            time.sleep(gap)
        time.sleep(drain)

    def click_cap(self, cx, cy, foreground=True):
        """Legacy signature; foreground is ignored, the physical cursor is untouched."""
        from zar_input import client_offset
        _, _, ox, oy, _, _ = client_offset(self.H)
        self.vi.click(int(cx - ox), int(cy - oy), hold=0.15)
        time.sleep(1.0)

    # ---- state readback ----------------------------------------------------------
    def shot(self):
        return grab(self.H).convert('RGB')

    @staticmethod
    def diff(a, b):
        d = ImageChops.difference(a, b).resize((194, 126)).convert('L')
        return sum(1 for px in list(d.get_flattened_data()) if px > 24)

    def panel_bright(self):
        """True when the right detail panel is shown (title band brightness)."""
        import numpy as np
        a = np.asarray(self.shot().crop((600, 230, 1100, 290)).convert('L'))
        return a.mean() > 40.0

    # ---- flows --------------------------------------------------------------------
    def pick_map(self, row_center_cap=(270, 255), tries=3):
        """Click a list row (default Boston row 1); verify the panel appears."""
        for _ in range(tries):
            if self.panel_bright():
                return True
            self.click_cap(*row_center_cap)
            time.sleep(2.0)
        return self.panel_bright()

