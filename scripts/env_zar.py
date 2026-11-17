"""ZAR environment: native observations and VirtualInput/PostMessage actions.

The trainer uses validated native phase, economy, spatial and resource readers;
loadout changes go through the calibrated UI and require native level receipts.
Historical screenshot/file-loadout helpers remain for older diagnostic scripts.
"""
import os
import hashlib
import math
import re
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memscan
from zar_input import VirtualInput

BASE_RVA = dict(civ=0x650f10, zomb=0x650f18, police=0x650f20, corpses=0x650f28,
                count=0x650438, converting=0x650f80)
MONEY_F32_RVAS = (0x6563c0, 0x65d9c0, 0x665ef0)
BUILD_SHA256 = 'a1bd5913ed3905aaaadfb5a14781004d28990f433ff1621c658c10f1795469d2'
NATIVE_ABILITIES = ['Bomber', 'Police', 'Heli', 'Stungas', 'Firebomb', 'CallArms',
                    'APC', 'Rally', 'Bus', 'Missile', 'Medevac', 'Dozer', 'Tank',
                    'Cure', 'Nuke', 'Demolition', 'SeekDestroy', 'Cluster', 'AC130']
STOCK_NAMES = ['Police', 'Garrison', 'Nest', 'Mine', 'C4', 'Sniper', 'Mortar',
               'Heli', 'Bomber', 'Firebomb', 'Stungas', 'Corridor', 'Hold', 'Decoy',
               'CallArms', 'Wall', 'APC', 'Battleship', 'GasMortar', 'FireMortar',
               'Rally', 'Bus', 'Missile', 'Howitzer', 'MLRS', 'Railgun', 'Cure',
               'ChemMine', 'Spikes', 'Oil', 'Napalm', 'Medevac', 'Dozer', 'Tank',
               'Nuke', 'Demolition', 'SeekDestroy', 'Cluster', 'AC130']
PROGRESS = r'game-copies/inst2/steam_cloud/progress/Boston__MA.progress'


class ZAREnvError(RuntimeError):
    pass


def read_session(path, started_ms):
    """Only complete records from this logging session; stale files are unknown."""
    try:
        rows = []
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    break
        if not rows or rows[0].get('ev') != 'header' or rows[0].get('wall', 0) < started_ms:
            return None
        return {'header': rows[0],
                'footer': next((r for r in reversed(rows) if r.get('ev') == 'footer'), None),
                'latest': next((r for r in reversed(rows) if 'stats' in r), None)}
    except (OSError, ValueError):
        return None


class ZAREnv:
    def __init__(self, pid, root=r'D:\zar-scratch'):
        self.root = root
        self.pid = pid
        self.base = memscan.module_base(pid)
        self.h = memscan.open_proc(pid)
        from harness import Instance
        inst = Instance('inst2', launch=False)
        inst.pid = pid
        self.hwnd = inst._find_hwnd()
        if not self.hwnd:
            raise ZAREnvError('no window')
        sent = os.path.join(root, 'sessions', '.zarvi_%d' % pid)
        inject = not os.path.exists(sent)
        self.vi = VirtualInput(pid, hwnd=self.hwnd, inject=inject)
        if inject:
            open(sent, 'w').write('ok')
        if not self.vi.enabled:
            self.vi.enable()
            time.sleep(0.4)
        import ctypes
        r = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetClientRect(self.hwnd, ctypes.byref(r))
        self.cw, self.ch = r.right, r.bottom

    # ---------------- observation ----------------
    def _gv(self, key):
        d = memscan.read(self.h, self.base + BASE_RVA[key], 8)
        return struct.unpack('<q', d)[0] if d and len(d) == 8 else None

    def money(self):
        # The dump writer reads this field; the other positive mirrors can be stale.
        d = memscan.read(self.h, self.base + 0x65d9c0, 4)
        if d and len(d) == 4:
            v = struct.unpack('<f', d)[0]
            if math.isfinite(v) and 0 <= v < 1e7:
                return v
        return None

    def validate_build(self):
        import psutil
        with open(psutil.Process(self.pid).exe(), 'rb') as fh:
            if hashlib.file_digest(fh, 'sha256').hexdigest() != BUILD_SHA256:
                raise ZAREnvError('Unsupported game build: revalidate memory offsets')

    def scalar(self, rva, fmt):
        size = struct.calcsize(fmt)
        data = memscan.read(self.h, self.base + rva, size)
        if data is None or len(data) != size:
            raise ZAREnvError(f'Missing memory at {rva:#x}')
        return struct.unpack(fmt, data)[0]

    def game_state(self):
        """Read fields used by the matching-build F6 writer, without dumping."""
        app = self.scalar(0x6553e8, '<I')
        phase = self.scalar(0x65d9c8, '<I')
        if app != 2 or phase > 3:
            raise ZAREnvError(f'Not in a game world: app={app}, phase={phase}')
        return dict(phase=('planning', 'playing', 'won', 'lost')[phase],
                    sim=self.scalar(0x675d28, '<f'),
                    tick=self.scalar(0x6514e8, '<q'),
                    paused=bool(self.scalar(0x665fa2, '<B')),
                    mult=self.scalar(0x666868, '<q'))

    def start_log(self):
        """The game's documented Shift+F6 observer log, not the admin console."""
        self.vi.key_press(0x76, sc=65)
        self.log_started = int(time.time() * 1000)
        self.vi.key_down(0x10, sc=42)
        try:
            self.vi.key_press(0x75, sc=64)
        finally:
            self.vi.key_up(0x10, sc=42)
        for _ in range(20):
            for path in (Path(self.copy_dir()) / 'logs').glob('*.jsonl'):
                data = read_session(path, self.log_started)
                if data:
                    self.log_path = path
                    return data['header']
            time.sleep(.05)
        raise ZAREnvError('No fresh session-log header')

    def stop_log(self):
        self.vi.key_press(0x76, sc=65)
        for _ in range(20):
            data = read_session(self.log_path, self.log_started)
            if data and data['footer']:
                return data['footer']
            time.sleep(.05)
        return None

    def retry(self):
        self.vi.key_press(0x52, sc=19)
        time.sleep(.15)
        self.vi.key_press(0x52, sc=19)

    def loadout_levels(self):
        return {name: self.scalar(0x655f90 + i * 8, '<q') for i, name in enumerate(NATIVE_ABILITIES)}

    def battle_stock(self):
        stock = {name: self.scalar(0x656488+i*4, '<f') for i, name in enumerate(STOCK_NAMES)}
        if any(not math.isfinite(v) or v < 0 for v in stock.values()):
            raise ZAREnvError('Invalid battle stock')
        return stock

    def roster(self):
        settings = (Path(self.copy_dir()) / 'steam_cloud/settings.ini').read_text()
        match = re.search(r'^roster_battle\s*=\s*(.*)$', settings, re.M)
        if not match or len(match[1].split()) != 7:
            raise ZAREnvError('Missing seven-slot battle roster')
        return match[1].split()

    def change_loadout(self, name, delta):
        """One model-selected level change through the calibrated loadout UI."""
        if (self.cw, self.ch) != (1920, 1200) or delta not in (-1, 1):
            raise ZAREnvError('Loadout gestures require calibrated 1920x1200 client')
        before = self.loadout_levels()
        roster = self.roster()
        self.vi.key_press(9, sc=15)
        time.sleep(.2)
        if self.scalar(0x6553e8, '<I') != 1:
            raise ZAREnvError('Loadout did not open')
        try:
            if name in roster and before[name] > 0:
                slot = roster.index(name)
                self.vi.click((244 if delta > 0 else 80) + 266*slot, 794)
            elif delta > 0:
                slot = next(i for i, n in enumerate(roster) if before.get(n, 0) == 0)
                order = [s.strip() for s in (Path(self.copy_dir())/'battle_order.txt').read_text().splitlines()
                         if s.strip() and not s.startswith('#')]
                unlocked = self.unlocked_abilities()
                order = [n for n in order if n in unlocked] + [n for n in order if n not in unlocked]
                index = order.index(name)
                self.vi.click(160+266*slot, 680)
                time.sleep(.2)
                self.vi.wheel(30, 600, 600)
                # Eight rows fit at this calibrated size, including the bottom row.
                scroll = min(index, max(0, len(order)-8))
                if scroll:
                    self.vi.wheel(-scroll, 600, 600)
                self.vi.click(600, 180+120*(index-scroll))
            time.sleep(.2)
        finally:
            # Close a remaining picker, then the loadout, without backing out of play.
            self.vi.key_press(0x1B, sc=1)
            time.sleep(.1)
            if self.scalar(0x6553e8, '<I') == 1:
                self.vi.key_press(9, sc=15)
            time.sleep(.2)
        self.game_state()
        after = self.loadout_levels()
        expected = dict(before)
        expected[name] += delta
        if after != expected:
            raise ZAREnvError(f'Loadout receipt mismatch for {name} {delta:+d}')
        return after

    def unlocked_abilities(self):
        text = (Path(self.copy_dir())/'steam_cloud/unlocks.ini').read_text()
        return set(re.findall(r'^unlock\s*=\s*ability\s+(\w+)', text, re.M))

    def array(self, rva, dtype, limit=500000):
        import numpy as np
        pointer = self.scalar(rva, '<Q')
        count = self.scalar(rva+8, '<q')
        if not 0 <= count <= limit or count and not pointer:
            raise ZAREnvError(f'Invalid array at {rva:#x}: {count}')
        size = np.dtype(dtype).itemsize * count
        data = memscan.read(self.h, pointer, size) if size else b''
        if data is None or len(data) != size:
            raise ZAREnvError(f'Incomplete array at {rva:#x}')
        return np.frombuffer(data, dtype=dtype).copy()

    def spatial(self, plan):
        import numpy as np
        from spatial import project, features
        for _ in range(5):
            tick = self.scalar(0x6514e8, '<q')
            points = self.array(0x650280, np.dtype(('<f4', 2)))
            kinds = self.array(0x6502d0, 'u1')
            if len(points) == len(kinds) and tick == self.scalar(0x6514e8, '<q'):
                break
        else:
            raise ZAREnvError('Unit snapshot changed during read')
        camera = [self.scalar(rva, '<f') for rva in (0x6553ac, 0x6553b0, 0x6553b4)]
        if self.scalar(0x6553d4, '<f') != 0 or self.scalar(0x6553d8, '<f') != 0:
            raise ZAREnvError('Spatial projection requires top-down unrotated camera')
        if not np.isfinite(points).all() or not all(map(math.isfinite, camera)) or camera[2] <= 0:
            raise ZAREnvError('Invalid spatial coordinates')
        rectangles = self.array(0x656680, np.dtype(('<f4', 4)))
        origin = np.array([self.scalar(0x665358, '<f'), self.scalar(0x66535c, '<f')])
        zones = []
        for line in plan.get('_text', '').splitlines():
            if line.startswith('board zone = '):
                fields = line.split('=', 1)[1].split()
                n = int(fields[0])
                vertices = np.asarray(list(map(float, fields[1:1+2*n]))).reshape(n, 2)-origin
                zones.append(project(vertices, camera, self.cw, self.ch))
        return features(project(points, camera, self.cw, self.ch), kinds,
                        project(rectangles.reshape(-1, 2), camera, self.cw, self.ch).reshape(-1, 4),
                        zones, self.cw, self.ch)

    def close(self):
        """Release this attachment without stopping the caller's game."""
        self.vi.close()
        import ctypes
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.h))

    def obs(self):
        return dict(civ=self._gv('civ'), zomb=self._gv('zomb'),
                    converting=self._gv('converting'), corpses=self._gv('corpses'),
                    police=self._gv('police'), money=self.money(),
                    infections=self.scalar(0x651098, '<q'))

    # ---------------- F6 state-dump channel ----------------
    def copy_dir(self):
        import psutil
        return os.path.dirname(psutil.Process(self.pid).exe())

    def dump_parse(text):
        out = {'_text': text}
        sec = out
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            header = re.match(r'^\[([a-z_]+)\]', s)
            if header:
                sec = out.setdefault(header[1], {})
                continue
            if '=' in s:
                k, v = s.split('=', 1)
                sec[k.strip()] = v.strip()
        return out

    def dump(self, wait_s=3.5):
        """Press F6, wait for the NEW debug_dumps txt, parse sections.
        Returns None when the writer never ran (menu/title/workshop)."""
        d = os.path.join(self.copy_dir(), 'debug_dumps')
        # Timestamped names have one-second precision; overwrites also count.
        def stamps():
            return {f: (os.stat(os.path.join(d, f)).st_mtime_ns,
                        os.stat(os.path.join(d, f)).st_size)
                    for f in os.listdir(d) if f.endswith('.txt')} if os.path.isdir(d) else {}
        before = stamps()
        self.vi.key_press(0x75, sc=64, hold=0.1)
        t0 = time.time()
        while time.time() - t0 < wait_s:
            time.sleep(0.35)
            if not os.path.isdir(d):
                continue
            new = sorted(f for f, stamp in stamps().items() if before.get(f) != stamp)
            if new:
                p = os.path.join(d, new[-1])
                time.sleep(0.25)          # let the writer flush
                with open(p, encoding='utf-8', errors='ignore') as fh:
                    txt = fh.read()
                return ZAREnv.dump_parse(txt)
        return None

    def phase_now(self):
        """DUMP truth for game phase: memory counters can look 'planning'
        while the LOST screen still owns input (verified 2026-11-17)."""
        d = self.dump()
        if not d:
            return None
        return d.get('where', {}).get('phase')

    # ---------------- episode setup ----------------
    def set_loadout(self, idx_levels):
        """Edit resume_loadout ints (19 per-ability levels in battle_order
        file order). The game reads the file at READY, greedily buys the
        list up to the board's SP and CONSUMES the deck at battle start ->
        re-set every episode before READY. After a WIN screen the game
        DROPS the line entirely (probe 2026-11-17: IndexError) -> re-append
        it as 19 zeros when missing. Instance-bound: each copy has its own
        save."""
        path = os.path.join(self.copy_dir(), 'steam_cloud', 'progress',
                            'Boston__MA.progress')
        with open(path, encoding='utf-8', errors='ignore') as fh:
            s = fh.read()
        hit = [l for l in s.split('\n') if l.startswith('resume_loadout')]
        tok = (hit[0].split('=')[1].split()[:19] if hit else [])
        tok = (tok + ['0'] * 19)[:19]
        for i, v in idx_levels.items():
            tok[i] = str(v)
        new = 'resume_loadout = ' + ' '.join(tok)
        s = (s.replace(hit[0], new) if hit
             else s.rstrip('\n') + '\n' + new + '\n')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(s)
        return new

    @staticmethod
    def launch():
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recover.py')],
                             capture_output=True, text=True, timeout=240).stdout
        if 'RECOVERED' not in out:
            raise ZAREnvError('recover failed: ' + out[-200:])
        return int(out.split('RECOVERED pid ')[1].split()[0])

    def ready(self):
        """READY + YES; DUMP phase is truth: planning -> SPACE(S) until
        phase becomes 'playing' (BATTLE phase's phase string); lost screen
        -> R-loop first. Self-heal stray-SPACE pause."""
        if self.phase_now() == 'lost':
            self.to_planning()
        for _ in range(5):
            p = self.phase_now()
            if p == 'playing':
                break
            if p == 'planning':
                self.vi.key_press(0x20, sc=57, hold=0.25)
                time.sleep(2.5)
                self.vi.key_press(0x20, sc=57, hold=0.25)
                time.sleep(3.0)
            else:
                self.to_planning()
        prev = self.obs()
        frozen = 0
        for _ in range(6):
            time.sleep(2.2)
            o = self.obs()
            moved = (o['zomb'] != prev['zomb']) or (o['civ'] != prev['civ']) \
                or (o['converting'] != prev['converting'])
            if moved or o['zomb'] > 0:
                return o
            frozen += 1
            if frozen >= 2:
                print('[ready] frozen -> SPACE', flush=True)
                self.vi.key_press(0x20, sc=57)
                frozen = 0
            prev = o
        return self.obs()

    def to_planning(self, max_r=12):
        """Enter planning from a confirmed phase; never diagnose pauses from counters."""
        for _ in range(max_r):
            state = self.game_state()
            if state['phase'] == 'planning':
                return self.obs()
            if state['phase'] == 'won':
                self.vi.key_press(0x0D, sc=28)  # campaign CONTINUE
            else:
                self.retry()
            time.sleep(.5)
        raise ZAREnvError('Could not confirm planning after retry/continue')

    # ---------------- actions ----------------
    def cast(self, bar_key, cx, cy):
        """Select battle-bar deployable (hotkey char) and click at client px."""
        import ctypes
        if len(bar_key) != 1 or not bar_key.isascii() or not bar_key.isalnum():
            raise ZAREnvError(f'Unsupported battle binding {bar_key!r}')
        vk = ord(bar_key.upper())
        sc = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        self.vi.key_press(vk, sc=sc)
        time.sleep(0.2)
        self.vi.move_to(cx, cy)
        time.sleep(0.15)
        self.vi.click(cx, cy)
        time.sleep(0.2)

    # ---------------- planning actions (pre-READY) ----------------
    # PLACEMENTS ARE CLICK-DRIVEN in the game's CLICK MODE (HUD bottom-right
    # "Click mode" active by default): drags/strokes are REJECTED (verified
    # 2026-11-17: drag = 0 charge anywhere; armed CLICK shows "CLICK A
    # BUILDING TO PLACE IT" rejection text = input landed). (x,y) are client
    # PHYSICAL px (GetClientRect, e.g. 1920x1200 for the windowed copies).
    def _arm(self, vk, sc):
        self.vi.key_press(vk, sc=sc)
        time.sleep(0.2)

    def _place(self, vk, sc, x, y):
        self._arm(vk, sc)
        self.vi.move_to(int(x), int(y))
        time.sleep(0.15)
        self.vi.click()
        time.sleep(0.45)
        return (self.obs().get('money') or 0)

    def mine_field(self, x, y, out=90):
        """Mine field (hotkey 5, $15): single click on open ground."""
        return self._place(0x35, 6, x, y)

    def turret(self, x, y):
        """Turret (hotkey 4, $90): click on a building."""
        return self._place(0x34, 5, x, y)

    def garrison(self, x, y):
        """Mortar (hotkey 2, $75 escalating): click on a building."""
        return self._place(0x32, 3, x, y)

    def upgrade(self, x, y):
        """F = UPGRADE UNITS: click over a unit/price tag."""
        return self._place(0x46, 33, x, y)

    def auto_place(self, vk, sc, budget_frac=0.6, max_n=200):
        """Arm a tool; valid targets GLOW YELLOW. Screenshot -> cluster yellow
        px (64px bins, densest first) -> CLICK glow centers until budget gone.
        Returns count placed (money-drop verified)."""
        from harness import grab
        import numpy as _np
        m0 = self.obs()['money'] or 0.0
        floor = m0 * (1.0 - budget_frac)
        self._arm(vk, sc)
        placed = 0
        for _round in range(12):
            img = _np.asarray(grab(self.hwnd).convert('RGB')).astype(int)
            r, g, b = img[..., 0], img[..., 1], img[..., 2]
            mask = (r > 150) & (r - b > 70) & (g - b > 50) & (g > 110)
            mask[int(self.ch * 0.82):, :] = False          # HUD strip
            ys, xs = _np.nonzero(mask)
            if len(xs) < 40:
                break
            bins = {}
            for x, y in zip(xs // 64, ys // 64):
                bins.setdefault((x, y), []).append((x * 64, y * 64))
            for _, pts in sorted(bins.items(), key=lambda kv: -len(kv[1])):
                m = self.obs()['money'] or 0.0
                if m <= floor or placed >= max_n:
                    return placed
                cx = min(int(_np.mean([p[0] for p in pts])) + 32 - 11,
                         self.cw - 30)
                cy = min(int(_np.mean([p[1] for p in pts])) + 32 - 48,
                         int(self.ch * 0.8))
                self.vi.move_to(cx, cy)
                time.sleep(0.1)
                self.vi.click(hold=0.05)
                time.sleep(0.1)
                m2 = self.obs()['money'] or 0.0
                if m2 < m - 0.5:
                    placed += 1
                    self._arm(vk, sc)   # tool disarms after placing
        return placed

    def auto_garrison(self, budget_frac=0.6, max_n=200):
        """Mortar barrage onto every glowing valid building."""
        return self.auto_place(0x32, 3, budget_frac, max_n)

    # ---------------- battle loop ----------------
    def poll(self, dt=4.0):
        return self.obs()

    def hot_spot(self):
        """Densest combat blob (green militia/fire tracers, fallback bright
        flash dots) -> LOGICAL client px (DPI-scale aware), or None."""
        from harness import grab
        import numpy as _np
        img = _np.asarray(grab(self.hwnd).convert('RGB')).astype(int)
        sx = img.shape[1] / max(self.cw, 1)
        sy = img.shape[0] / max(self.ch, 1)
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        m = (g > 140) & (g - r > 50) & (g - b > 40)
        if int(m.sum()) < 60:
            lum = img.mean(axis=2)
            m = lum > 225
        m[:int(130 * sy), :] = False
        m[int(img.shape[0] * 0.80):, :] = False
        ys, xs = _np.nonzero(m)
        if len(xs) < 40:
            return None
        bins = {}
        for x, y in zip(xs // 60, ys // 60):
            bins[(x, y)] = bins.get((x, y), 0) + 1
        (bx, by), _n = max(bins.items(), key=lambda kv: kv[1])
        return (int(min((bx * 60 + 30) / sx, self.cw - 30)),
                int(min((by * 60 + 30) / sy, self.ch * 0.78)))

    def crowd_topk(self, k=4):
        """Player-view segmentation (ONE grab, like hot_spot): fire-tracer
        green UNION zombie-body green binned to 60 px cells ->
        ([(client_x, client_y, px_n)][:k], total_px). Where the crowd IS."""
        from harness import grab
        import numpy as _np
        img = _np.asarray(grab(self.hwnd).convert('RGB')).astype(int)
        sx = img.shape[1] / max(self.cw, 1)
        sy = img.shape[0] / max(self.ch, 1)
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        m = (((g > 140) & (g - r > 50) & (g - b > 40)) |
             ((g > r + 8) & (g > b + 8) & (g > 40) & (g < 110)))
        m[:int(130 * sy), :] = False
        m[int(img.shape[0] * 0.80):, :] = False
        ys, xs = _np.nonzero(m)
        if len(xs) < 30:
            return [], 0
        bins = {}
        for x, y in zip(xs // 60, ys // 60):
            bins[(x, y)] = bins.get((x, y), 0) + 1
        top = sorted(bins.items(), key=lambda kv: -kv[1])[:k]
        out = [(int(min((bx * 60 + 30) / sx, self.cw - 30)),
                int(min((by * 60 + 30) / sy, self.ch * 0.78)), n)
               for (bx, by), n in top]
        return out, len(xs)

    def battle(self, policy, max_s=900, stop_frac=0.05, log=None,
               score_t=None, auto_heli=0.0, heli_key='2'):
        """Run battle; policy(obs, t) -> ('cast', key, x, y) | None.
        Terminal: zomb==0 -> win; civ <= stop_frac*civ0 or t>max_s -> lose.
        score_t: end episode at that t and score frac = civ/civ0 at that moment
        (gradient fitness; the death-spiral wall truncates plain end-frac).
        Shaped stats (all returns): alive_int = time-weighted mean civ frac
        (survivability-throughout), min_frac, kills (sum of zomb decrements,
        horde management), police_pk (armed-civ/militia peak = special
        buildings + CTA online). Returns dict(win, civ_end, civ0, frac, t,
        alive_int, min_frac, kills, police_pk)."""
        o0 = self.poll()
        civ0 = o0['civ'] or 1
        t0 = time.time()
        prev = o0; frozen = 0; fought = o0['zomb'] > 0
        acc_w = 0.0; acc_f = 0.0; min_frac = 1.0
        kills = 0; police_pk = 0
        pz = o0['zomb'] or 0
        pt = t0
        m0 = None; mend = None; last_heli = -9e9
        def res(win, civ, t, **kw):
            spend = 0.0
            if m0 and m0 > 0:
                spend = max(0.0, min(1.0, 1.0 - (mend or 0.0) / m0))
            return dict(win=win, civ_end=civ, civ0=civ0,
                        frac=None if civ is None else civ / civ0, t=t,
                        alive_int=acc_w / max(acc_f, 1e-6),
                        min_frac=min_frac, kills=kills, police_pk=police_pk,
                        spend_frac=spend, **kw)
        while True:
            t = time.time() - t0
            o = self.poll()
            if log:
                log.append((round(t), o))
            if o.get('money') is not None:
                if m0 is None:
                    m0 = o['money']
                mend = o['money']
            if o['civ'] is not None:
                dt = max(t - pt, 1e-6)
                f = o['civ'] / civ0
                acc_w += dt * f
                acc_f += dt
                min_frac = min(min_frac, f)
            if o['zomb'] is not None and pz:
                kills += max(pz - o['zomb'], 0)
            if o['zomb'] is not None:
                pz = o['zomb']
            if o.get('police'):
                police_pk = max(police_pk, o['police'])
            pt = t
            if o['zomb'] > 0:
                fought = True
            if o['zomb'] == 0 and t > 20 and fought:
                return res(True, o['civ'], t)
            if not fought and t > 150:
                return res(False, o['civ'], t, invalid=True)
            if o['civ'] is not None and o['civ'] <= stop_frac * civ0:
                return res(False, o['civ'], t)
            if score_t is not None and t >= score_t:
                return res(False, o['civ'], t, scored_at=score_t)
            if t > max_s:
                return res(False, o['civ'], t)
            if o['zomb'] > 0 and o == prev:
                frozen += 1
                if frozen == 3:
                    print('[battle] frozen -> SPACE', flush=True)
                    self.vi.key_press(0x20, sc=57)
                    frozen = 0
            else:
                frozen = 0
            prev = o
            a = policy(o, t)
            if a and a[0] == 'cast':
                self.cast(a[1], a[2], a[3])
            if auto_heli > 0 and t - last_heli >= auto_heli:
                spot = self.hot_spot()
                if spot:
                    self.cast(heli_key, spot[0], spot[1])
                last_heli = t
            time.sleep(2.5)



class ZarGame:
    """Reconstructed lightweight handle (recover.py/harness contract)."""

    def __init__(self, pid, hwnd, vi, log_path=None):
        self.pid = pid
        self.hwnd = hwnd
        self.vi = vi
        self.log_path = log_path
        self.base = memscan.module_base(pid)
        self.h = memscan.open_proc(pid)

    def _i64(self, key):
        d = memscan.read(self.h, self.base + BASE_RVA[key], 8)
        return struct.unpack('<q', d)[0] if d and len(d) == 8 else None

    def observe(self):
        civ = self._i64('civ')
        zomb = self._i64('zomb')
        if civ is None:
            return None
        money = None
        for rva in MONEY_F32_RVAS:
            d = memscan.read(self.h, self.base + rva, 4)
            if d and len(d) == 4:
                v = struct.unpack('<f', d)[0]
                if 0 < v < 1e7:
                    money = round(v, 2)
                    break
        if civ == 0 and zomb == 0:
            phase = 'menu'
        elif zomb == 0:
            phase = 'planning'
        else:
            phase = 'battle'
        return dict(phase=phase, civ=civ, zomb=zomb, money=money,
                    zones=[0] * (4 if phase == 'planning' else 0))

    def key(self, vk, tag=None):
        import ctypes
        sc = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        self.vi.key_press(vk, sc=sc)

    def click_screen(self, x, y, tag=None):
        self.vi.move_to(x, y)
        time.sleep(0.18)
        self.vi.click(x, y)
