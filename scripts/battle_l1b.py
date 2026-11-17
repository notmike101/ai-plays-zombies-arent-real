"""L1 win v3: blind nav + blind zone (NO dumps in planning: planning-dump wedges
the writer); F6 only once battle runs."""
import sys, time, os, re, glob
sys.path.insert(0, r'D:\zar-scratch\scripts')
import game_drive as gd
from harness import Instance
from zar_input import VirtualInput

PID = int(sys.argv[1])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\l1v2.log'
DUMPS = r'D:\zar-scratch\game-copies\inst2\debug_dumps\*.txt'
CIV_START = 8142


def log(m):
    with open(LOG, 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + m + '\n')


inst = Instance('inst2', launch=False)
inst.pid = PID
time.sleep(18)
inst.hwnd = inst._find_hwnd()
inst.actions = []
inst.log_action = lambda *a, **k: None
vi = VirtualInput(PID, hwnd=inst.hwnd, inject=True)
HWND = inst.hwnd
log(f'start hwnd={HWND}')

_last = [time.time() - 60]


def parse(path):
    keys = ('stage', 'phase', 'paused', 'sim_time', 'civilians', 'zombies', 'money',
            'garrisons', 'turrets', 'mortars', 'snipers', 'mines', 'helicopters')
    out = {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'(\w+) = (.*)', ln.strip())
        if m and m.group(1) in keys and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def dump(wait=0.5):
    time.sleep(wait)
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


def C(x, y):
    vi.move_to(x, y)
    vi.click(x, y)


# ---- blind nav: title -> campaign -> Boston -> START OVER -> redo YES ----
K(0x20); time.sleep(1.4)        # dismiss title
K(0x0D); time.sleep(1.4)        # CAMPAIGN
K(0x0D); time.sleep(2.0)        # Boston (level list)
C(1053, 698); time.sleep(1.0)   # LEVEL 5 row select
C(1152, 968); time.sleep(1.4)   # START OVER
K(0x0D); time.sleep(9)          # redo dialog keyboard YES
log('nav done; blind zone draw')

# ---- blind zone over crowd core ----
K(0x42); time.sleep(0.4)
for x, y in [(1560, 560), (2360, 560), (2360, 1320), (1560, 1320)]:
    C(x, y); time.sleep(0.3)
K(0x0D); time.sleep(0.8)
K(0x1B)
log('zone drawn; READY')
K(0x20); time.sleep(1.6)

# ---- first dump (battle should be live; dialog => paused) ----
d = dump()
if d is None:
    log('dump1 wedge -> try Enter (close dialog) + SPACE READY')
    K(0x0D); time.sleep(1.0)
    K(0x20); time.sleep(1.6)
    d = dump()
elif d.get('phase') == 'planning':
    if d.get('paused') == 'true':
        log('0% dialog -> SPACE YES')
        K(0x20); time.sleep(1.2)
        d = dump()
    else:
        log('still planning no dialog?! one more READY try')
        K(0x20); time.sleep(1.6)
        d = dump()

GARR = [(x, 1250) for x in range(1600, 2360, 80)] + \
       [(1610, y) for y in range(620, 1250, 90)]
placed = 0
stuck = 0
prev = d
for it in range(300):
    if prev is None:
        stuck += 1
        log(f'dump wedged (stuck={stuck})')
        if stuck >= 3:
            log('ABORT stuck')
            sys.exit(2)
        K(0x20); time.sleep(2)
        prev = dump()
        continue
    stuck = 0
    phase = prev.get('phase')
    civ = int(prev.get('civilians') or 0)
    zomb = int(prev.get('zombies') or 0)
    log(f'it{it} phase={phase} paused={prev.get("paused")} civ={civ} zomb={zomb} '
        f'$={prev.get("money")} gar={prev.get("garrisons")}')
    if phase in ('won', 'lost'):
        log(f'END phase={phase} saved={100.0*civ/CIV_START:.2f}%')
        break
    if prev.get('paused') == 'true':
        log('paused -> SPACE')
        K(0x20); time.sleep(1.0)
        prev = dump()
        continue
    if civ < 0.10 * CIV_START:
        log('<10% -> R restart')
        K(0x52); time.sleep(3)
        placed = 0
        prev = dump()
        continue
    money = float(prev.get('money') or 0)
    if placed < len(GARR) and money > 150:
        x, y = GARR[placed]
        K(0x31); time.sleep(0.3)
        C(x, y)
        placed += 1
        prev = dump(wait=0.4)
        continue
    time.sleep(12)
    prev = dump()
log('done')
