"""Live sim-state reader for Zombies Aren't Real (no OCR, no injection).

The counts block lives in the sim heap with layout [civilians u32][u32 0][zombies u32]
(verified from the .state dump + live hit 0x2245a1a06a8 = [62635][0][101507]). The heap
allocation MOVES on mass-death compactions, so every poll re-validates and falls back to
a rescan. When the static root pointer is known (from Ghidra: module global -> sim struct),
set_static() switches to exact dereference-based reads and all scanning stops.

Usage:
  r = SimReader(pid)
  r.calibrate_planning()        # in PLANNING: civ == 209867 exactly
  r.prune()                     # call each poll early in battle until 1 survivor -> locked
  civ, zomb = r.read()          # works in any mode; None when not (yet) readable
  r.set_static(base, goff, coff, zoff)   # static-root mode (preferred)
"""
import struct
import sys
import ctypes

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import memscan

CIV_TOTAL = 209867          # Boston L5 civilians at planning (paid crowd)
CIV_BLOCK_BASE = 210016     # 209,867 civilians + 149 carried units (planning total)
MAX_CIV = CIV_TOTAL
SUM_SLACK = 8192            # police/converted-outside-crowd tolerance
MAX_ZOMB = 300000

DIRECT_CIV_RVA = 0x650728   # battle-verified live civilians (mirror block 0x650720..)
DIRECT_ZOMB_RVA = 0x650f18  # battle-verified live zombies


CONSOLE_FLAG_RVA = 0x5f268a      # u8: nonzero = admin console open (WM_KEYDOWN ctrl+space verified)


def console_open(hwnd, open_it=True):
    """Toggle/ensure the admin console with a REAL WM_KEYDOWN ctrl+space (the DLL
    async-bit combo is not seen by sokol; this exact message pair is verified)."""
    u = ctypes.windll.user32
    import time as _t
    u.PostMessageW(hwnd, 0x100, 0x11, 0x001D0001)
    u.PostMessageW(hwnd, 0x100, 0x20, 0x00390001)
    _t.sleep(0.2)
    u.PostMessageW(hwnd, 0x101, 0x20, 0xC0390001)
    u.PostMessageW(hwnd, 0x101, 0x11, 0xC01D0001)


def admin_command(hwnd, command, wait=0.6):
    """Open console (WM ctrl+space), type via WM_CHAR, Enter runs+closes."""
    import time as _t
    u = ctypes.windll.user32
    console_open(hwnd)
    _t.sleep(wait)
    for ch in command:
        u.PostMessageW(hwnd, 0x102, ord(ch), 1)
        _t.sleep(0.02)
    _t.sleep(0.25)
    u.PostMessageW(hwnd, 0x100, 0x0D, 0x001C0001)
    u.PostMessageW(hwnd, 0x101, 0x0D, 0xC01C0001)
    _t.sleep(0.5)


def validate_triplet(h, addr, last=None):
    """Return (civ, zomb) when addr holds a plausible [civ][0][zomb] block else None.

    last: optional previous (civ, zomb) for rate sanity; a live block never jumps
    more than max(2000, 25% of civ) between consecutive polls at 5-10 s spacing."""
    d = memscan.read(h, addr, 12)
    if not d or len(d) < 12:
        return None
    civ, mid, zomb = struct.unpack("<III", d)
    if mid != 0:
        return None
    if not (0 < civ <= MAX_CIV):
        return None
    if zomb > MAX_ZOMB:
        return None
    if civ + zomb > CIV_BLOCK_BASE + SUM_SLACK:
        return None
    if last is not None:
        dc = abs(int(civ) - int(last[0]))
        if dc > max(2000, 0.25 * max(last[0], 1)):
            return None
    return (civ, zomb)


class SimReader:
    def __init__(self, pid):
        self.h = memscan.open_proc(pid)
        self.pid = pid
        self.candidates = []      # calibration candidates (planning mode)
        self.locked = None        # single verified block address
        self.last = None          # last (civ, zomb)
        self.static = None        # (module_base, global_off, civ_off, zomb_off)
        self._same = 0
        self._same_v = None
        self._black = set()       # addresses caught frozen (stale mirrors)
        self._prev = {}           # addr -> value at previous full scan
        self._cprev = {}          # candidate addr -> value at previous prune
    def restart(self):
        """After a mid-battle R (restart), sim heap is rebuilt and civ returns to
        209867 — recalibrate from scratch. Best done within the first seconds of the
        restarted battle before conversions start."""
        self._black = set()
        return self.calibrate_planning()

    # ---- direct global mode (counts live IN the module .data: base+RVA) --------------
    # Battle-verified layout: civ u32 at RVA 0x650728, zombies u32 at RVA 0x650f18
    # (0x7F0 apart, NOT adjacent; several stale mirror copies of each exist -- the
    # fields that CHANGE between polls are the live ones, verified vs HUD to 1%).
    def set_direct(self, civ_rva, zomb_rva=None):
        self._base = memscan.module_base(self.pid)
        self.direct_rva = civ_rva
        self.direct_zomb_rva = zomb_rva

    def _read_direct(self):
        if self.direct_zomb_rva is None:
            a = self._base + self.direct_rva
            civ = memscan.read_u32(self.h, a)
            mid = memscan.read_u32(self.h, a + 4)
            zomb = memscan.read_u32(self.h, a + 8)
            if civ is None or zomb is None or mid is None:
                return None
            if mid > 30000 or not (0 <= civ <= MAX_CIV) or zomb > MAX_ZOMB:
                return None
            if civ + zomb > CIV_BLOCK_BASE + SUM_SLACK:
                return None
            return (civ, zomb)
        civ = memscan.read_u32(self.h, self._base + self.direct_rva)
        zomb = memscan.read_u32(self.h, self._base + self.direct_zomb_rva)
        if civ is None or zomb is None:
            return None
        if not (0 <= civ <= MAX_CIV) or zomb > MAX_ZOMB:
            return None
        return (civ, zomb)
    # ---- static-root mode ------------------------------------------------------------
    def set_static(self, module_base, global_off, civ_off, zomb_off):
        self.static = (module_base, global_off, civ_off, zomb_off)

    def _read_static(self):
        base, goff, coff, zoff = self.static
        ptr = memscan.read_u64(self.h, base + goff)
        if not ptr or ptr < 0x10000 or ptr > 0x7FFFFFFFFFFF:
            return None
        civ = memscan.read_u32(self.h, ptr + coff)
        zomb = memscan.read_u32(self.h, ptr + (zoff if zoff is not None else coff + 8))
        if civ is None or zomb is None:
            return None
        if not (0 <= civ <= MAX_CIV) or zomb > MAX_ZOMB or civ + zomb > CIV_BLOCK_BASE + SUM_SLACK:
            return None
        return (civ, zomb)

    # ---- calibration (planning: civ == CIV_TOTAL exactly) ------------------------------
    def calibrate_planning(self):
        """Scan for [209867][0][?] triplets; returns candidate addresses (usually ~57)."""
        hits = memscan.find_u32(self.h, CIV_TOTAL)
        self.candidates = [a for a in hits if memscan.read_u32(self.h, a + 4) == 0]
        self.locked = None
        self.last = None
        self._cprev = {}
        return list(self.candidates)

    def prune(self):
        """Differential over planning candidates: lock the candidate whose value
        MOVED since the previous poll (frozen copies cannot move; only the live
        sim block drops). Call every poll while unlocked."""
        if self.locked:
            return 1
        cur = {}
        moved = []
        for a in self.candidates:
            if a in self._black:
                continue
            v = validate_triplet(self.h, a)
            if v is None:
                continue
            cur[a] = v
            pv = self._cprev.get(a)
            if pv is not None and pv != v:
                moved.append((a, v))
        self._cprev = cur
        self.candidates = list(cur)
        if moved:
            ok = [(a, v) for a, v in moved if v[1] >= 500 or v[0] < CIV_TOTAL - 200]
            if not ok:
                ok = moved
            vals = {v for _, v in ok}
            if len(vals) == 1:
                self.locked, self.last = ok[0]
                return 1
            top = max(vals)[0]
            cand = [t for t in ok if t[1][0] == top]
            if len(cand) == 1:
                self.locked, self.last = cand[0]
                return 1
            self.candidates = [a for a, _ in cand]
        return len(self.candidates)

    # ---- battle-time rescan --------------------------------------------------------------
    def scan_block(self):
        """Find the live [civ][0][zomb] block by rescan. Locks on: a live block
        (civ < total) that changed at the same address since the last scan (only the
        real one moves), continuity with the last reading, or a unique live hit."""
        raw = [(a, v) for a, v in self._scan_blocks_raw() if a not in self._black]
        if not raw:
            raw = [(a, v) for a, v in self._scan_blocks_raw(strict=False)
                   if a not in self._black]
        live = [(a, v) for a, v in raw if v[0] < CIV_TOTAL]
        self._dbg_live = len(live)
        prev = self._prev
        self._prev = {a: v for a, v in raw}
        if not live:
            return None
        if self.last is not None:
            lo = self.last[0]
            cont = [(a, v) for a, v in live
                    if v[0] <= lo and lo - v[0] <= max(20000, int(0.7 * lo))]
            livech = [(a, v) for a, v in cont if a in prev and prev[a] != v]
            pool = livech or cont
            if pool:
                pvals = {v for _, v in pool}
                if len(pvals) == 1:
                    self.locked, self.last = pool[0]
                    return self.last
                bestv = max(pvals)
                cand = [(a, v) for a, v in pool if v == bestv]
                if len(cand) == 1:
                    self.locked, self.last = cand[0]
                    return self.last
        dec = [(a, v) for a, v in live if a in prev and v[0] < prev[a][0]]
        dvals = {v for _, v in dec}
        if dec and len(dvals) == 1:
            self.locked, self.last = dec[0]
            return self.last
        if len(live) == 1:
            self.locked, self.last = live[0]
            return self.last
        return None

    def _scan_blocks_raw(self, strict=True):
        """Triplet [civ][0][zomb] (+ strict: next field = police count, small).
        Chunk overlap dedups boundary hits."""
        out = {}
        for base, size in memscan.iter_regions(self.h):
            off = 0
            step = 4 * 1024 * 1024
            while off < size:
                n = min(step + 16, size - off)
                data = memscan.read(self.h, base + off, n)
                if data:
                    import numpy as np
                    arr = np.frombuffer(data[: len(data) // 4 * 4], dtype=np.uint32)
                    if len(arr) >= 4:
                        mids = arr[1:-2]
                        civs = arr[:-3]
                        zombs = arr[2:-1]
                        nxt = arr[3:]
                        s = civs + zombs
                        ok = ((mids == 0) & (civs > 500) & (civs <= MAX_CIV) &
                              (zombs <= MAX_ZOMB) & (s <= CIV_BLOCK_BASE + SUM_SLACK) &
                              (s > 8000))
                        if strict:
                            ok &= (nxt <= 20000)
                        for i in np.where(ok)[0]:
                            out[base + off + int(i) * 4] = (int(civs[i]), int(zombs[i]))
                off += step
        return list(out.items())

    # ---- the one call the loop makes ------------------------------------------------------
    def read(self):
        """Return (civ, zombies) or None. Static root preferred, then locked/cached
        address with revalidation, then candidate pruning, then full rescan."""
        if getattr(self, "direct_rva", None) is not None:
            v = self._read_direct()
            if v is not None:
                self.last = v
                return v
        if self.static:
            v = self._read_static()
            if v is not None:
                self.last = v
                return v
        if self.locked:
            v = validate_triplet(self.h, self.locked, self.last)
            if v is not None:
                if v == self._same_v:
                    self._same += 1
                    if self._same >= 4:
                        self._black.add(self.locked)
                        self.locked = None
                        self.candidates = []
                        self._same = 0
                        return None
                else:
                    self._same = 0
                    self._same_v = v
                self.last = v
                return v
            self.locked = None  # moved: fall through to rescan
        if self.candidates:
            self.prune()
            if self.locked:
                return self.last
        v = self.scan_block()
        if v is not None:
            return v
        return None


def _selfcheck():
    class FakeH:
        def __init__(self, blob, base=0x1000):
            self.blob, self.base = blob, base
    import builtins
    orig_read = memscan.read
    def fake_read(h, addr, size):
        off = addr - h.base
        if off < 0:
            return None
        return h.blob[off:off + size]
    memscan.read = fake_read
    try:
        def mk(civ, mid, zomb):
            return FakeH(struct.pack("<III", civ, mid, zomb))
        assert validate_triplet(mk(100000, 0, 50000), 0x1000) == (100000, 50000)
        assert validate_triplet(mk(100000, 7, 50000), 0x1000) is None, "mid!=0 must fail"
        assert validate_triplet(mk(300000, 0, 1), 0x1000) is None, "civ>209867 must fail"
        assert validate_triplet(mk(200000, 0, 200000), 0x1000) is None, "sum>slack must fail"
        assert validate_triplet(mk(0, 0, 5), 0x1000) is None, "civ==0 must fail"
        assert validate_triplet(mk(50000, 0, 100000), 0x1000, (99500, 99000)) is None, "rate jump must fail"
        assert validate_triplet(mk(99000, 0, 100000), 0x1000, (99500, 99000)) == (99000, 100000)
    finally:
        memscan.read = orig_read
    print("OK")


if __name__ == "__main__":
    _selfcheck()
