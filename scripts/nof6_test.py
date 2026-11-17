"""Nav to battle with zero F6; watch .data tick; on freeze, one F6 to classify hang."""
import sys, time, os, re, glob, struct
sys.path.insert(0, r'D:\zar-scratch\scripts')
import game_drive as gd, memscan
from harness import Instance
from zar_input import VirtualInput

PID = int(sys.argv[1])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\nof6.log'
def log(m):
    with open(LOG, 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + m + '\n')

inst = Instance('inst2', launch=False); inst.pid = PID
time.sleep(20)
inst.hwnd = inst._find_hwnd()
vi = VirtualInput(PID, hwnd=inst.hwnd, inject=True); inst.vi = vi
h = memscan.open_proc(PID)
base = memscan.module_base(PID)

def tick():
    d = memscan.read(h, base + 0x605f80, 0x18)
    return struct.unpack_from('<III', d, 8)[0] if d else -1

log(f'hwnd={inst.hwnd} base={base:#x}')
gd.key(inst.hwnd, 0x20); time.sleep(1.3)
gd.key(inst.hwnd, 0x0D); time.sleep(1.3)
gd.key(inst.hwnd, 0x0D); time.sleep(1.8)
vi.click(1053, 698); time.sleep(0.9)
vi.click(1152, 968); time.sleep(1.2)
gd.key(inst.hwnd, 0x0D); time.sleep(9)        # board (planning L1)
log('board ready; SPACE READY (crowd sheltered=0 -> dialog, SPACE again YES)')
gd.key(inst.hwnd, 0x20); time.sleep(1.0)
gd.key(inst.hwnd, 0x20); time.sleep(1.0)      # YES if dialog
gd.key(inst.hwnd, 0x20); time.sleep(0.5)      # undo pause (parity fixup)
log('ready sent; watching tick')
prev = tick()
frozen = 0
t_end = time.time() + 240
while time.time() < t_end:
    time.sleep(4)
    t = tick()
    d = t - prev
    prev = t
    if d == 0:
        frozen += 1
        log(f'tick={t} delta=0 x{frozen}')
    else:
        frozen = 0
        if frozen == 0 and int(time.time()) % 20 < 5:
            log(f'tick={t} delta={d}')
    if frozen >= 2:
        log('FROZEN: pressing F6 once')
        gd.key(inst.hwnd, 0x75)
        time.sleep(3)
        fs = sorted(glob.glob(r'D:\zar-scratch\game-copies\inst2\debug_dumps\*.txt'), key=os.path.getmtime)
        age = time.time() - os.path.getmtime(fs[-1])
        t2 = tick()
        import ctypes
        cpu0 = None
        log(f'F6 result: newest dump age={age:.1f}s tick_after={t2 - t}')
        if age < 10:
            def firsts(p, keys):
                out = {}
                for ln in open(p, encoding='utf-8', errors='replace'):
                    m = re.match(r'(\w+) = (.*)', ln.strip())
                    if m and m.group(1) in keys and m.group(1) not in out:
                        out[m.group(1)] = m.group(2)
                return out
            log('dump: ' + repr(firsts(fs[-1], ['phase','paused','sim_time','tick','civilians','zombies','money','stage'])))
        break
log('done')
