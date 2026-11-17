"""v5 L1 campaign runner — memory-only (F6 dump), dialog rules:
info OK=Enter, confirm YES=X, ready_short YES=SPACE; wedge=dump frozen (dialog/pause).
Loop: clear dialogs -> READY -> battle watch (turrets on breach side) -> <10% R retry.
Win detection: phase won/lost in dump."""
import sys, time, glob, os, re
sys.path.insert(0, r'D:\zar-scratch\scripts')
import game_drive as gd
from harness import Instance
from zar_input import VirtualInput

PID = int(sys.argv[1])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\run5.log'
DUMPS = r'D:\zar-scratch\game-copies\inst2\debug_dumps\*.txt'
CIV0 = 8142


def log(m):
    with open(LOG, 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + m + '\n')


inst = Instance('inst2', launch=False)
inst.pid = PID
inst.hwnd = inst._find_hwnd()
inst.actions = []
inst.log_action = lambda *a, **k: None
vi = VirtualInput(PID, hwnd=inst.hwnd, inject=False)
HWND = inst.hwnd
_last = [time.time() - 60]

KEYS = ('phase', 'paused', 'sim_time', 'tick', 'civilians', 'zombies', 'money',
        'garrisons', 'turrets', 'snipers', 'mortars', 'camera_center', 'camera_zoom')


def parse(p):
    out = {}
    zones = []
    for ln in open(p, encoding='utf-8', errors='replace'):
        s = ln.strip()
        m = re.match(r'(\w+) = (.*)', s)
        if m and m.group(1) in KEYS and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
        elif s.startswith('board zone'):
            nums = [float(v) for v in re.findall(r'-?\d+\.?\d*', s)]
            zones.append(nums)
    out['zones'] = zones
    return out


def dump():
    gd.key(HWND, 0x75)
    for _ in range(8):
        time.sleep(2)
        fs = glob.glob(DUMPS)
        mt = max(os.path.getmtime(f) for f in fs)
        if mt > _last[0] + 1:
            _last[0] = mt
            return parse(max(fs, key=os.path.getmtime))
    return None


def K(vk):
    gd.key(HWND, vk)


def screen_pt(lx, ly, d):
    cc = d.get('camera_center')
    if not cc:
        return None
    cx, cy = [float(v) for v in cc.split()]
    z = float(d.get('camera_zoom') or 1)
    return (int(1920 + (lx - cx) * z * 1.6), int(1080 + (ly - cy) * z * 1.6))


def place_units(d, vk, pts):
    K(vk)
    time.sleep(0.35)
    for lx, ly in pts:
        sp = screen_pt(lx, ly, d)
        if not sp:
            return
        vi.move_to(*sp); time.sleep(0.25)
        vi.click(*sp); time.sleep(0.8)


def clear_dialogs(maxn=3):
    """probe-close: Enter (info OK); recheck; X (confirm YES); SPACE last."""
    for vk in (0x0D, 0x0D, 0x58, 0x20):
        d = dump()
        if d is not None:
            return d
        K(vk); time.sleep(1.2)
    return dump()


log(f'v5 start pid={PID}')
d = clear_dialogs()
for cycle in range(30):
    if d is None:
        log(f'c{cycle} wedged -> clear_dialogs')
        time.sleep(8)
        d = clear_dialogs()
        continue
    ph = d.get('phase')
    civ = int(d.get('civilians') or 0)
    zz = int(d.get('zombies') or 0)
    log(f'c{cycle} ph={ph} paused={d.get("paused")} civ={civ} z={zz} '
        f'$={d.get("money")} t={d.get("sim_time")}')
    if ph == 'planning':
        z = d.get('zones') or []
        log(f'c{cycle} PLANNING zones={len(z)} $={d.get("money")}')
        if d.get('paused') == 'true':
            K(0x20); time.sleep(1.2)     # dialog-safe resume
            d = dump()
            continue
        K(0x20); time.sleep(1.5)         # READY
        K(0x34); K(0x34); time.sleep(0.8)  # speed 4x
        d = clear_dialogs()
        continue
    if d.get('paused') == 'true':
        K(0x20); time.sleep(1.2)
        d = dump()
        continue
    if ph in ('won', 'lost'):
        log(f'END {ph} saved={100.0*civ/CIV0:.2f}%')
        break
    money = float(d.get('money') or 0)
    if money > 200 and civ > 0.30 * CIV0:
        zs = d.get('zones') or []
        if zs:
            zn = zs[0]
            pts_map = list(zip(zn[1::2], zn[2::2]))
            if len(pts_map) >= 3:
                xs = [p[0] for p in pts_map]
                ys = [p[1] for p in pts_map]
                y_in = max(ys) - 40.0
                x_lo, x_hi = min(xs) + 60.0, max(xs) - 60.0
                live = [(x - 9006.0 + 10210.0, y - 10210.0 + 9006.0)
                        for x, y in [(x_lo + i * (x_hi - x_lo) / 4, y_in)
                                     for i in range(5)]]
                place_units(d, 0x35, live)   # [5] Turret
                d = dump()
                continue
    if civ < 0.10 * CIV0:
        log('R retry')
        K(0x52); time.sleep(2.5)
        d = clear_dialogs()
        continue
    time.sleep(16)
    d = dump()
log('v5 done')
