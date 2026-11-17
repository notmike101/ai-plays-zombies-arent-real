"""Injector + virtual-input controller for Zombies Aren't Real.

Uses scripts/hookdll/target/release/hookdll.dll (Rust cdylib):
- injects into the game process,
- the DLL creates section "ZARVI_<pid>" and IAT-hooks GetCursorPos /
  GetAsyncKeyState / GetKeyState / GetKeyboardState,
- this module maps the section and serves virtual mouse/keyboard state.

Usage:
    vi = VirtualInput(pid)          # injects + maps
    vi.enable()
    vi.move_to(client_x, client_y)  # PHYSICAL client coords (game window is DPI-aware)
    vi.click()                      # virtual LMB press/release at the virtual cursor
    vi.key_press(vk, scan=...)      # PostMessage key + async-state bit
    vi.disable()
"""
import ctypes, ctypes.wintypes as wt, time, struct, os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

DLL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "hookdll", "target", "release", "hookdll.dll")

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT, MEM_RESERVE, MEM_RELEASE = 0x1000, 0x2000, 0x8000
PAGE_READWRITE = 0x04
INFINITE = 0xFFFFFFFF

MAGIC = 0x5A415249
OFF = dict(enabled=0x08, cx=0x0C, cy=0x10, buttons=0x14, keys=0x18,
           toggles=0x38, heartbeat=0x3C, patches=0x40, raw_hwnd=0x48, raw_sent=0x50)

VK_LBUTTON, VK_RBUTTON, VK_MBUTTON = 0x01, 0x02, 0x04
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12

WM_MOUSEMOVE, WM_KEYDOWN, WM_KEYUP = 0x200, 0x100, 0x101


def _export_rva(dll_path, name):
    """Parse a PE's export table locally; return the RVA of `name` or None."""
    import struct as _s
    with open(dll_path, "rb") as f:
        d = f.read()
    e = _s.unpack_from("<I", d, 0x3C)[0]
    if d[e:e + 4] != b"PE\0\0":
        return None
    nsections_off = e + 6
    opt_off = e + 0x18
    opt_size = _s.unpack_from("<H", d, e + 0x14)[0]
    magic = _s.unpack_from("<H", d, opt_off)[0]
    if magic != 0x20B:
        return None
    exp_rva, exp_size = _s.unpack_from("<II", d, opt_off + 0x70 + 8 * 0)
    if exp_rva == 0:
        return None
    sec_off = opt_off + opt_size
    sections = []
    for i in range(_s.unpack_from("<H", d, nsections_off)[0]):
        so = sec_off + 40 * i
        va, vsz = _s.unpack_from("<II", d, so + 12)[::-1]
        va = _s.unpack_from("<I", d, so + 12)[0]
        vsz = _s.unpack_from("<I", d, so + 8)[0]
        praw = _s.unpack_from("<I", d, so + 20)[0]
        sections.append((va, vsz, praw))

    def rva2off(rva):
        for va, vsz, praw in sections:
            if va <= rva < va + max(vsz, 1):
                return praw + (rva - va)
        return None

    eo = rva2off(exp_rva)
    if eo is None:
        return None
    nfuncs, nnames = _s.unpack_from("<II", d, eo + 20)[0], _s.unpack_from("<II", d, eo + 24)[0]
    names_rva = _s.unpack_from("<I", d, eo + 32)[0]
    no = rva2off(names_rva)
    funcs_rva = _s.unpack_from("<I", d, eo + 28)[0]
    for i in range(nnames):
        nrva = _s.unpack_from("<I", d, no + 4 * i)[0]
        fo = rva2off(nrva)
        end = d.index(b"\0", fo)
        if d[fo:end].decode() == name:
            fo_rva = _s.unpack_from("<I", d, rva2off(funcs_rva) + 4 * i)[0]
            return fo_rva
    return None


def window_of_pid(pid):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, lp):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            t = ctypes.create_unicode_buffer(128)
            user32.GetWindowTextW(hwnd, t, 128)
            if t.value:
                out.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return out[0] if out else None


def client_offset(hwnd):
    """Return (ox, oy): client origin within the window rect (physical px)."""
    wr, cr = wt.RECT(), wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    user32.GetClientRect(hwnd, ctypes.byref(cr))
    ox = ((wr.right - wr.left) - cr.right) // 2
    oy = ((wr.bottom - wr.top) - cr.bottom) - ox
    return wr.left, wr.top, ox, oy, cr.right, cr.bottom


class VirtualInput:
    def __init__(self, pid, hwnd=None, inject=True):
        self.pid = pid
        self.hwnd = hwnd or window_of_pid(pid)
        if not self.hwnd:
            raise RuntimeError(f"no window for pid {pid}")
        self.section = None
        self.view = None
        self.buf = None
        self.enabled = False
        self._hb = 0
        if inject:
            self.inject()
        else:
            self.open_section()  # DLL already loaded in this process

    # ---- injection ---------------------------------------------------------------
    def inject(self):
        if not os.path.exists(DLL_PATH):
            raise FileNotFoundError(DLL_PATH)
        # exact FFI types (default c_int truncates 64-bit handles/addresses!)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetProcAddress.restype = ctypes.c_void_p
        kernel32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint, ctypes.c_uint]
        hproc = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not hproc:
            raise OSError(f"OpenProcess failed: {ctypes.GetLastError()}")
        try:
            kernel32.VirtualAllocEx.restype = ctypes.c_void_p
            kernel32.VirtualAllocEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                ctypes.c_size_t, ctypes.c_uint, ctypes.c_uint]
            kernel32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                    ctypes.c_char_p, ctypes.c_size_t,
                                                    ctypes.POINTER(ctypes.c_size_t)]
            kernel32.CreateRemoteThread.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                    ctypes.c_size_t, ctypes.c_void_p,
                                                    ctypes.c_void_p, ctypes.c_uint,
                                                    ctypes.POINTER(ctypes.c_ulong)]
            path = os.path.abspath(DLL_PATH).encode("utf-16-le") + b"\0\0"
            addr = kernel32.VirtualAllocEx(hproc, None, len(path),
                                           MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            if not addr:
                raise OSError(f"VirtualAllocEx failed: {ctypes.GetLastError()}")
            written = ctypes.c_size_t(0)
            if not kernel32.WriteProcessMemory(hproc, addr, path, len(path),
                                               ctypes.byref(written)):
                raise OSError(f"WriteProcessMemory failed: {ctypes.GetLastError()}")
            k32 = kernel32.GetModuleHandleW("kernel32.dll")
            loadlib = kernel32.GetProcAddress(k32, b"LoadLibraryW")
            tid = ctypes.c_ulong(0)
            thread = kernel32.CreateRemoteThread(hproc, None, 0, ctypes.c_void_p(loadlib),
                                                 ctypes.c_void_p(addr), 0,
                                                 ctypes.byref(tid))
            if not thread:
                raise OSError(f"CreateRemoteThread failed: {ctypes.GetLastError()}")
            kernel32.WaitForSingleObject(thread, INFINITE)
            exit_code = ctypes.c_ulong(0)
            kernel32.GetExitCodeThread(thread, ctypes.byref(exit_code))
            kernel32.CloseHandle(thread)
            self.load_exit = exit_code.value
            if self.load_exit == 0:
                raise OSError("remote LoadLibraryW failed (exit 0)")

            # call zar_init (export) via remote thread: base from module snapshot
            # (GetExitCodeThread truncates the 64-bit HMODULE, so don't trust it)
            base = self._remote_module_base(hproc, "hookdll.dll")
            rva = _export_rva(DLL_PATH, "zar_init")
            if base is None or rva is None:
                raise OSError(f"hookdll base ({base}) or zar_init RVA ({rva}) not found")
            init_addr = base + rva
            thread2 = kernel32.CreateRemoteThread(hproc, None, 0, ctypes.c_void_p(init_addr),
                                                  None, 0, ctypes.byref(tid))
            if not thread2:
                raise OSError(f"CreateRemoteThread(zar_init) failed: {ctypes.GetLastError()}")
            kernel32.WaitForSingleObject(thread2, INFINITE)
            kernel32.GetExitCodeThread(thread2, ctypes.byref(exit_code))
            kernel32.CloseHandle(thread2)
            self.init_patches = exit_code.value
        finally:
            kernel32.CloseHandle(hproc)
        self.open_section()

    def _remote_module_base(self, hproc, modname):
        TH32CS_SNAPMODULE = 0x8
        TH32CS_SNAPMODULE32 = 0x10

        class MODULEENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", ctypes.c_ulong), ("th32ModuleID", ctypes.c_ulong),
                        ("th32ProcessID", ctypes.c_ulong), ("GlblcntUsage", ctypes.c_ulong),
                        ("ProccntUsage", ctypes.c_ulong), ("modBaseAddr", ctypes.c_void_p),
                        ("modBaseSize", ctypes.c_ulong), ("hModule", ctypes.c_void_p),
                        ("szModule", ctypes.c_wchar * 256),
                        ("szExePath", ctypes.c_wchar * 260)]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32,
                                                 self.pid)
        if snap == -1 or snap is None:
            return None
        try:
            me = MODULEENTRY32W()
            me.dwSize = ctypes.sizeof(MODULEENTRY32W)
            ok = kernel32.Module32FirstW(snap, ctypes.byref(me))
            while ok:
                if me.szModule.lower() == modname.lower():
                    return me.modBaseAddr
                ok = kernel32.Module32NextW(snap, ctypes.byref(me))
        finally:
            kernel32.CloseHandle(snap)
        return None

    def open_section(self):
        name = f"ZARVI_{self.pid}".encode()
        kernel32.OpenFileMappingA.restype = ctypes.c_void_p
        kernel32.OpenFileMappingA.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_char_p]
        kernel32.MapViewOfFile.restype = ctypes.c_void_p
        kernel32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                                           ctypes.c_uint, ctypes.c_size_t]
        hmap = kernel32.OpenFileMappingA(0xF001F, False, name)  # FILE_MAP_ALL_ACCESS
        if not hmap:
            raise OSError(f"OpenFileMappingA failed: {ctypes.GetLastError()} "
                          f"(DLL loaded? patches={self._patch_count_hint()})")
        view = kernel32.MapViewOfFile(hmap, 0xF001F, 0, 0, 0x100)
        if not view:
            raise OSError("MapViewOfFile failed")
        self.section = hmap
        self.view = view
        self.buf = (ctypes.c_char * 0x100).from_address(view)
        magic = struct.unpack_from("<I", self.buf, 0)[0]
        if magic != MAGIC:
            raise RuntimeError(f"bad magic {magic:#x}")
        # raw-input pump: where to post WM_INPUT (DLL v2+; older DLLs ignore it)
        self._w64(OFF["raw_hwnd"], int(self.hwnd))

    def _patch_count_hint(self):
        return "unknown"

    # ---- low-level ---------------------------------------------------------------
    def _w32(self, off, val):
        struct.pack_into("<I", self.buf, off, val & 0xFFFFFFFF)

    def _wi32(self, off, val):
        struct.pack_into("<i", self.buf, off, val)

    def _w64(self, off, val):
        struct.pack_into("<Q", self.buf, off, val & 0xFFFFFFFFFFFFFFFF)

    def _heartbeat(self):
        self._hb = (self._hb + 1) & 0xFFFFFFFF
        self._w32(OFF["heartbeat"], self._hb)

    def _origin(self):
        return client_offset(self.hwnd)

    # ---- enable / disable ----------------------------------------------------------
    def enable(self):
        self._w32(OFF["enabled"], 1)
        self.enabled = True
        self._heartbeat()

    def disable(self):
        self._w32(OFF["enabled"], 0)
        self.enabled = False

    def patches(self):
        return struct.unpack_from("<I", self.buf, OFF["patches"])[0]

    def raw_sent(self):
        return struct.unpack_from("<I", self.buf, OFF["raw_sent"])[0]

    # ---- virtual mouse ---------------------------------------------------------------
    def move_to(self, cx, cy, post=True):
        """Virtual cursor to client coords (physical px). Also posts WM_MOUSEMOVE so
        the message-driven mouse path agrees."""
        self._last_cx, self._last_cy = cx, cy
        sl, st, ox, oy, cw, ch = self._origin()
        self._wi32(OFF["cx"], sl + ox + cx)
        self._wi32(OFF["cy"], st + oy + cy)
        if post:
            lp = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
            user32.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, lp)
        self._heartbeat()

    def _buttons_write(self):
        pass  # buttons are written by callers directly

    def click(self, cx=None, cy=None, hold=0.08, right=False):
        """Virtual press+release: serves the polled GetAsyncKeyState bit AND posts the
        WM_LBUTTONDOWN/UP messages so message-driven UI sees it too."""
        if cx is not None:
            self.move_to(cx, cy)
        b = OFF["buttons"]
        btn = (1 << 1) if right else 1
        cur = struct.unpack_from("<I", self.buf, b)[0]
        self._w32(b, cur | btn)
        self._heartbeat()
        # post the message path as well (UI hit-testing is message-driven)
        lp = ((self._last_cy & 0xFFFF) << 16) | (self._last_cx & 0xFFFF)
        wp = 2 if right else 1  # MK_RBUTTON / MK_LBUTTON
        down_msg, up_msg = (0x204, 0x205) if right else (0x201, 0x202)
        user32.PostMessageW(self.hwnd, down_msg, wp, lp)
        time.sleep(hold)  # several sim frames at 30Hz+
        user32.PostMessageW(self.hwnd, up_msg, 0, lp)
        self._w32(b, cur)
        self._heartbeat()

    def button_down(self, btn=1):
        cur = struct.unpack_from("<I", self.buf, OFF["buttons"])[0]
        self._w32(OFF["buttons"], cur | btn)
        self._heartbeat()

    def button_up(self, btn=1):
        cur = struct.unpack_from("<I", self.buf, OFF["buttons"])[0]
        self._w32(OFF["buttons"], cur & ~btn)
        self._heartbeat()

    def drag(self, x1, y1, x2, y2, steps=8, hold=0.05):
        """Virtual drag for zone drawing / deployable drags."""
        self.move_to(x1, y1)
        time.sleep(hold)
        self.button_down()
        time.sleep(hold)
        for i in range(1, steps + 1):
            x = x1 + (x2 - x1) * i // steps
            y = y1 + (y2 - y1) * i // steps
            self.move_to(x, y)
            time.sleep(hold)
        self.button_up()
        self._heartbeat()

    # ---- virtual keyboard --------------------------------------------------------------
    def key_down(self, vk, sc=0, post=True, async_bit=True):
        if post:
            user32.PostMessageW(self.hwnd, WM_KEYDOWN, vk, 1 | (sc << 16))
        if async_bit:
            word = OFF["keys"] + (vk >> 5) * 4
            cur = struct.unpack_from("<I", self.buf, word)[0]
            self._w32(word, cur | (1 << (vk & 31)))
            self._heartbeat()

    def key_up(self, vk, sc=0, post=True, async_bit=True):
        if post:
            user32.PostMessageW(self.hwnd, WM_KEYUP, vk,
                                1 | (sc << 16) | (1 << 30) | (1 << 31))
        if async_bit:
            word = OFF["keys"] + (vk >> 5) * 4
            cur = struct.unpack_from("<I", self.buf, word)[0]
            self._w32(word, cur & ~(1 << (vk & 31)))
            self._heartbeat()

    def key_press(self, vk, sc=0, hold=0.05):
        self.key_down(vk, sc)
        time.sleep(hold)
        self.key_up(vk, sc)

    def combo_press(self, mods, vk, sc=0, hold=0.12):
        """mods: list of VKs held via async bits (Ctrl/Shift/Alt)."""
        for m in mods:
            self.key_down(m, post=False)
        time.sleep(0.05)
        self.key_press(vk, sc, hold)
        for m in mods:
            self.key_up(m, post=False)

    def close(self):
        try:
            if self.view:
                kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
                kernel32.UnmapViewOfFile(self.view)
                self.view = None
            if self.section:
                kernel32.CloseHandle(self.section)
                self.section = None
        except Exception:
            pass


# scan codes (subset) — reuse from game_drive
SC = {0x20: 0x39, 0x0D: 0x1C, 0x1B: 0x01, 0x11: 0x1D, 0x10: 0x2A, 0x12: 0x38,
      0x46: 0x21, 0x53: 0x1F, 0x57: 0x11, 0x41: 0x1E, 0x44: 0x20, 0x42: 0x30,
      0x47: 0x22, 0x5A: 0x2C, 0x58: 0x2D, 0x43: 0x2E, 0x56: 0x2F, 0x51: 0x10,
      0x45: 0x12, 0x52: 0x13, 0x54: 0x14, 0x4D: 0x32, 0x4B: 0x25, 0x48: 0x23,
      0x31: 0x02, 0x32: 0x03, 0x33: 0x04, 0x34: 0x05, 0x35: 0x06, 0x36: 0x07,
      0x37: 0x08, 0x38: 0x09, 0x39: 0x0A, 0x30: 0x0B,
      0x70: 0x3B, 0x71: 0x3C, 0x72: 0x3D, 0x73: 0x3E, 0x74: 0x3F, 0x75: 0x40,
      0x76: 0x41, 0x77: 0x42, 0x78: 0x43, 0x79: 0x44, 0xC0: 0x29}

if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1])
    vi = VirtualInput(pid)
    print("injected; IAT patches:", vi.patches())
