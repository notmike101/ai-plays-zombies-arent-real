"""Defend-the-zone micro: read zone from dump, ring turrets(4)/mortars(2)/snipers(3)
just inside walls, READY, watch to end; retry R with same board; stop at >=35% or won."""
import sys, time, glob, os, re
sys.path.insert(0, r'D:\zar-scratch\scripts')
import game_drive as gd
from harness import Instance
from zar_input import VirtualInput

PID = int(sys.argv[1])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\def1.log'
DUMPS = r'D:\zar-scratch\game-copies\inst2\debug_dumps\*.txt'
CIV0 = 8142
GOAL = 0.35


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
KEYS = ('phase', 'paused', 'sim_time', 'civilians', 'zombies', 'money',
        'camera_center', 'camera_zoom')


def parse(p):
    out = {}
    zones = []
    for ln in open(p, encoding='utf-8', errors='replace'):
        s = ln.strip()
        m = re.match(r'(\w+) = (.*)', s)
        if m and m.group(1) in KEYS and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
        elif s.startswith('board zone'):
            zones.append([float(v) for v in re.findall(r'-?\d+\.?\d*', s)])
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


def sp(d, lx, ly):
    cc = [float(v) for v in d['camera_center'].split()]
    z = float(d['camera_zoom'])
    return (int(1920 + (lx - 9006.0 + 10210.0 - cc[0]) * z * 1.6),
            int(1080 + (ly - 10210.0 + 9006.0 - cc[1]) * z * 1.6))


def place_ring(d):
    zn = d['zones'][0]
    pts = list(zip(zn[1::2], zn[2::2]))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    ins = 50.0
    ring = []
    for f in (0.2, 0.5, 0.8):
        ring.append((x0 + (x1 - x0) * f, y1 - ins))    # south
        ring.append((x0 + (x1 - x0) * f, y0 + ins))    # north
    for f in (0.3, 0.7):
        ring.append((x0 + ins, y0 + (y1 - y0) * f))    # west
        ring.append((x1 - ins, y0 + (y1 - y0) * f))    # east
    money = float(d.get('money') or 0)
    K(0x34); time.sleep(0.4)
    n = 0
    for lx, ly in ring:
        if money < 120:
            break
        sx, sy = sp(d, lx, ly)
        vi.move_to(sx, sy); time.sleep(0.25)
        vi.click(sx, sy); time.sleep(0.8)
        n += 1
        money -= 105
    log(f'ring clicked n={n}')


def clear_dialogs():
    for vk in (0x0D, 0x0D, 0x58, 0x20):
        d = dump()
        if d is not None:
            return d
        K(vk); time.sleep(1.2)
    return dump()


log(f'def1 start pid={PID}')
d = clear_dialogs()
for cyc in range(40):
    if d is None:
        d = clear_dialogs(); continue
    ph = d.get('phase')
    civ = int(d.get('civilians') or 0)
    money = float(d.get('money') or 0)
    log(f'c{cyc} ph={ph} civ={civ} z={d.get("zombies")} $={money} t={d.get("sim_time")}')
    if ph == 'planning':
        if d.get('zones') and money > 120:
            place_ring(d)
            d = dump()
            continue
        K(0x20); time.sleep(1.4)
        K(0x34); K(0x34); time.sleep(0.8)
        d = clear_dialogs()
        continue
    if d.get('paused') == 'true':
        K(0x20); time.sleep(1.2); d = dump(); continue
    if ph in ('won', 'lost'):
        pct = 100.0 * civ / CIV0
        log(f'END {ph} saved={pct:.2f}%')
        if ph == 'lost' or pct < GOAL * 100:
            log('R retry (keep iterating)')
            K(0x52); time.sleep(2.5)
            d = clear_dialogs()
            continue
        log('GOAL MET')
        break
    if civ < 0.12 * CIV0:
        log('R retry low')
        K(0x52); time.sleep(2.5)
        d = clear_dialogs()
        continue
    time.sleep(15)
    d = dump()
log('def1 done')
