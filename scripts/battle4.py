"""Battle watcher v4: F6 dump every 18 s; dialog-aware (Enter=OK on info, X=YES on
confirms, SPACE=YES only for ready_short). No screenshots: dump [plan]/[where] geometry."""
import sys, time, glob, os, re
sys.path.insert(0, r'D:\zar-scratch\scripts')
import game_drive as gd
from harness import Instance
from zar_input import VirtualInput

PID = int(sys.argv[1])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\battle4.log'
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


def parse(p):
    keys = ('phase', 'paused', 'sim_time', 'tick', 'civilians', 'zombies', 'money',
            'garrisons', 'turrets', 'snipers', 'mortars', 'camera_center',
            'camera_zoom', 'app_mode')
    out = {}
    for ln in open(p, encoding='utf-8', errors='replace'):
        m = re.match(r'(\w+) = (.*)', ln.strip())
        if m and m.group(1) in keys and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
        elif ln.strip() == '[plan]':
            out['inplan'] = True
        elif ln.startswith('[') and out.get('inplan') and 'ready zone' not in out:
            pass
        if ln.startswith('ready zone'):
            out['ready zone'] = ln.strip()
        if ln.startswith('board zone'):
            out['board zone'] = ln.strip()
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


log(f'watch pid={PID}')
K(0x20)                      # READY
time.sleep(2)
d = dump()
wedges = 0
for it in range(400):
    if d is None:
        wedges += 1
        log(f'it{it} DIALOG/up (wedge#{wedges}) -> Enter')
        K(0x0D)
        time.sleep(1.5)
        d = dump()
        continue
    wedges = 0
    ph = d.get('phase')
    civ = int(d.get('civilians') or 0)
    z = int(d.get('zombies') or 0)
    log(f'it{it} ph={ph} paused={d.get("paused")} civ={civ} z={z} '
        f'$={d.get("money")} gar={d.get("garrisons")} t={d.get("sim_time")}')
    if ph in ('won', 'lost'):
        log(f'END {ph} saved={100.0*civ/CIV0:.2f}%')
        break
    if d.get('paused') == 'true':
        K(0x20); time.sleep(1.2)
        d = dump()
        continue
    if civ < 0.10 * CIV0:
        log('R restart')
        K(0x52); time.sleep(3)
        d = dump()
        continue
    time.sleep(16)
    d = dump()
log('done')
