"""L1 win attempt, fully guarded: every input step verified by an F6 dump;
dialog detector = [clock] paused true (or dump goes stale for 12s).
Memory-only (no screenshots)."""
import sys, time, os, re, glob
sys.path.insert(0, r'D:\zar-scratch\scripts')
import game_drive as gd, memscan
from harness import Instance
from zar_input import VirtualInput

PID = int(sys.argv[1])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\l1run.log'
DUMPS = r'D:\zar-scratch\game-copies\inst2\debug_dumps\*.txt'
CIV_START = 8142


def log(m):
    with open(LOG, 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + m + '\n')


inst = Instance('inst2', launch=False)
inst.pid = PID
time.sleep(20)
inst.hwnd = inst._find_hwnd()
inst.actions = []
inst.log_action = lambda *a, **k: None
vi = VirtualInput(PID, hwnd=inst.hwnd, inject=True)
HWND = inst.hwnd
log(f'start hwnd={HWND}')

_last = [0.0]


def parse(path):
    keys = ('stage', 'phase', 'paused', 'sim_time', 'tick', 'money', 'civilians',
            'zombies', 'garrisons', 'turrets', 'mortars', 'snipers', 'mines',
            'helicopters', 'wall_chews', 'zombie_deaths')
    out = {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'(\w+) = (.*)', ln.strip())
        if m and m.group(1) in keys and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def step(name, fn, wait=1.0):
    fn()
    time.sleep(wait)
    before = _last[0]
    gd.key(HWND, 0x75)
    for _ in range(6):
        time.sleep(2)
        fs = glob.glob(DUMPS)
        mt = max(os.path.getmtime(f) for f in fs)
        if mt > before + 1:
            _last[0] = mt
            p = max(fs, key=os.path.getmtime)
            d = parse(p)
            log(f"{name}: stage={d.get('stage')} phase={d.get('phase')} "
                f"paused={d.get('paused')} civ={d.get('civilians')} "
                f"zomb={d.get('zombies')} $={d.get('money')} gar={d.get('garrisons')}")
            return d
    log(f'{name}: NO NEW DUMP 12s -> wedged or dialog blocking input')
    return None


def K(vk):
    gd.key(HWND, vk)


def C(x, y, rmb=False):
    vi.move_to(x, y)
    vi.click(x, y, right=rmb)


def seq(name, *acts, wait=1.0, guard=True):
    """acts run back-to-back; one dump at the end verifies."""
    for a in acts:
        a()
        time.sleep(0.35)
    if not guard:
        return None
    return step(name, lambda: None, wait=wait)


# nav chain (mouse-dead dialogs avoided: keys+verified clicks)
K(0x20); time.sleep(1.3)
K(0x0D); time.sleep(1.3)
K(0x0D); time.sleep(1.8)
C(1053, 698); time.sleep(0.9)
C(1152, 968); time.sleep(1.2)
K(0x0D)
d = step('board', lambda: None, wait=9)
if d is None or d.get('phase') != 'planning':
    log('unexpected board; abort')
    sys.exit(1)

# zone over the crowd core (<=30% land)
d = seq('zone', lambda: K(0x42), lambda: C(1560, 560), lambda: C(2360, 560),
        lambda: C(2360, 1320), lambda: C(1560, 1320), lambda: K(0x0D), wait=1.2)
if d is None:
    sys.exit(1)
if d.get('paused') == 'true':
    log('zone draw -> dialog (too big?) ESC + REFUND ALL + smaller zone')
    step('esc', lambda: K(0x1B), wait=0.8)
    seq('refund', lambda: C(3283, 2038), lambda: K(0x42), lambda: C(1700, 700),
        lambda: C(2250, 700), lambda: C(2250, 1250), lambda: C(1700, 1250),
        lambda: K(0x0D), wait=1.2)

# READY (dialog YES via SPACE if it shows)
d = step('ready', lambda: K(0x20), wait=1.4)
if d and d.get('paused') == 'true':
    d = step('ready-yes', lambda: K(0x20), wait=1.2)

GARR = [(x, 1250) for x in range(1600, 2360, 80)] + \
       [(1610, y) for y in range(620, 1250, 90)]
placed = 0
prev = d
for it in range(150):
    if prev is None:
        log('wedged midloop; ESC + SPACE recovery attempt')
        prev = step('recover', lambda: K(0x1B), wait=1.0)
        continue
    civ = int(prev.get('civilians') or 0)
    phase = prev.get('phase')
    if phase in ('won', 'lost'):
        log(f'BATTLE ENDED phase={phase} civ={civ} ({100.0*civ/CIV_START:.1f}%)')
        break
    if prev.get('paused') == 'true':
        log('paused midbattle -> SPACE (unpause/YES)')
        prev = step('unpause', lambda: K(0x20), wait=1.0)
        continue
    if civ < 0.10 * CIV_START:
        log(f'<10% (civ={civ}) -> R restart')
        prev = step('restart', lambda: K(0x52), wait=3.0)
        placed = 0
        continue
    money = float(prev.get('money') or 0)
    gar = int(prev.get('garrisons') or 0)
    if placed < len(GARR) and money > 150:
        x, y = GARR[placed]
        prev = seq(f'garr{placed}', lambda: K(0x31), lambda: C(x, y),
                   wait=0.6, guard=True)
        if prev is not None and prev.get('paused') == 'true':
            prev = step(f'garr{placed}-unpause', lambda: K(0x20), wait=0.8)
        placed += 1
        continue
    prev = step(f'poll{it}', lambda: None, wait=8)
log('done')
