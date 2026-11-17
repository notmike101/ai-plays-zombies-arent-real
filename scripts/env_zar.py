"""ZAR RL environment: Zombies Aren't Real campaign battle as a gym-like loop.

Observation  : exact live counters via module statics (no screenshots, no OCR):
               civilians, zombies, converting, corpses, police, money(f32), wall-carry total.
Actions      : virtual-input primitives only (DLL section + PostMessage; game ignores real mouse):
               select battle-bar deployable (hotkey), click at client-px to cast, keys.
Episode      : planning -> set_loadout(file edit) -> READY -> dialog SPACE(YES) -> battle ticks
               -> terminal when horde wiped (win) or civilians below stop line / lost screen.
Rules        : only legit resources: money + SP loadout levels (file-edited resume_loadout —
               equivalent to clicking +/− on the LOADOUT screen; assignments default by unlock
               order: battle slot idx17=slot3, idx18=slot4(Cure) on this save).

Client px mapping for windowed captures: png(1942x1256) minus (11,40).
"""
import os
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
PROGRESS = r'game-copies/inst2/steam_cloud/progress/Boston__MA.progress'


class ZAREnvError(RuntimeError):
    pass


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
        for rva in MONEY_F32_RVAS:
            d = memscan.read(self.h, self.base + rva, 4)
            if d and len(d) == 4:
                v = struct.unpack('<f', d)[0]
                if 0 < v < 1e7:
                    return v
        return None

    def obs(self):
        return dict(civ=self._gv('civ'), zomb=self._gv('zomb'),
                    converting=self._gv('converting'), corpses=self._gv('corpses'),
                    police=self._gv('police'), money=self.money())

    # ---------------- episode setup ----------------
    @staticmethod
    def set_loadout(idx_levels):
        """Edit resume_loadout ints (idx15..21 = battle keys 1..6,T; value = level).
        Game assigns default abilities by unlock order when a level appears."""
        s = open(PROGRESS).read()
        line = [l for l in s.split('\n') if l.startswith('resume_loadout')][0]
        tok = line.split('=')[1].split()
        for i, v in idx_levels.items():
            tok[i] = str(v)
        new = 'resume_loadout = ' + ' '.join(tok)
        open(PROGRESS, 'w').write(s.replace(line, new))
        return new

    @staticmethod
    def launch():
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recover.py')],
                             capture_output=True, text=True, timeout=240).stdout
        if 'RECOVERED' not in out:
            raise ZAREnvError('recover failed: ' + out[-200:])
        return int(out.split('RECOVERED pid ')[1].split()[0])

    def ready(self):
        """READY + YES; self-heal: recover to planning if needed, verify tick,
        press SPACE if the sim is frozen (stray-SPACE pause)."""
        for _ in range(4):
            o = self.obs()
            if o['zomb'] > 0:            # any live/lost battle: R-restart to
                for _y in range(4):      # planning ("Restart this level?
                    self.vi.key_press(0x52, sc=19, hold=0.25)
                    time.sleep(4.0)
                    o2 = self.obs()
                    # planning: horde gone AND money visible (menu has none)
                    if o2['zomb'] == 0 and (o2['civ'] or 0) > 0 \
                            and o2.get('money') is not None:
                        break
                continue
            if o['zomb'] > 0:
                break                            # battle already underway
            self.vi.key_press(0x20, sc=57); time.sleep(1.2)   # READY
            self.vi.key_press(0x20, sc=57); time.sleep(3.0)   # dialog SPACE=YES
            if self.obs()['zomb'] > 0:
                break
        prev = self.obs(); frozen = 0
        for _ in range(6):
            time.sleep(2.2)
            o = self.obs()
            moved = (o['zomb'] != prev['zomb']) or (o['civ'] != prev['civ']) or (o['converting'] != prev['converting'])
            if moved or o['zomb'] > 0:
                return o
            frozen += 1
            if frozen >= 2:
                print('[ready] frozen -> SPACE', flush=True)
                self.vi.key_press(0x20, sc=57)
                frozen = 0
            prev = o
        return self.obs()

    def to_planning(self, max_r=10):
        """R-loop back to PLANNING without starting a new battle (v2 episodes:
        the NET decides when to READY). Frozen counters = wedge: escalate
        SPACE (unpause) + ENTER (dismiss OK/loss) before R (verified seq).
        Menu/dead states raise."""
        last = None
        lost = 0
        for _ in range(max_r):
            o = self.obs()
            if (o['civ'] or 0) > 0 and (o['zomb'] or 0) == 0 \
                    and o.get('money') is not None:
                return o
            sig = (o['civ'], o['zomb'])
            if (o['zomb'] or 0) > 0:
                if sig == last:      # pause-modal: unpause, close menu,
                    self.vi.key_press(0x20, sc=57, hold=0.25)   # dismiss,
                    time.sleep(1.2)  # then double-R below
                    self.vi.key_press(0x1B, sc=1, hold=0.25)    # ESC menu
                    time.sleep(1.2)
                    self.vi.key_press(0x0D, sc=28, hold=0.25)
                    time.sleep(1.2)
                # 1st R opens 'Restart this level? YES(R)/NO', 2nd R = YES
                self.vi.key_press(0x52, sc=19, hold=0.25)
                time.sleep(2.5)
                self.vi.key_press(0x52, sc=19, hold=0.25)
            elif (o['civ'] or 0) == 0 and o.get('money') is None:
                if lost < 3:         # retry level = KEEPS placements+budget
                    self.vi.key_press(0x52, sc=19, hold=0.25)
                    time.sleep(2.5)  # (START OVER wipes: last resort only)
                    self.vi.key_press(0x52, sc=19, hold=0.25)
                else:
                    self.vi.key_press(0x0D, sc=28, hold=0.25)   # START OVER
                lost += 1
            last = sig
            time.sleep(4.0)
        o = self.obs()
        if (o['civ'] or 0) > 0 and (o['zomb'] or 0) == 0 \
                and o.get('money') is not None:
            return o
        raise ZAREnvError('not planning: %s' % o)


    # ---------------- actions ----------------
    def cast(self, bar_key, cx, cy):
        """Select battle-bar deployable (hotkey char) and click at client px."""
        vk = {'1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35, '6': 0x36, 'T': 0x54}[bar_key]
        sc = {'1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, 'T': 20}[bar_key]
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