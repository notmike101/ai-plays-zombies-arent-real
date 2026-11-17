"""Ground-truth the SP deck + heli rules on a live board (todo: heli mask fix).
Logs [economy]/[clock]/[counts] around casts to analysis/heli_probe.jsonl."""
import json
import sys
import time

sys.path.insert(0, r'D:\zar-scratch\scripts')
from env_zar import ZAREnv

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 44716
OUT = r'D:\zar-scratch\analysis\heli_probe.jsonl'
fh = open(OUT, 'w')


def log(tag, e, extra=None):
    d = e.dump()
    if d is None:
        row = {'tag': tag, 'nodump': True, 'real': round(time.time(), 1)}
    else:
        c, w, cl, ec = (d.get('counts', {}), d.get('where', {}),
                        d.get('clock', {}), d.get('economy', {}))
        row = {'tag': tag, 'real': round(time.time(), 1),
               'phase': w.get('phase'), 'sim': cl.get('sim_time'),
               'speed': cl.get('speed_mult'), 'paused': cl.get('paused'),
               'civ': c.get('civilians'), 'zomb': c.get('zombies'),
               'heli': c.get('helicopters'), 'kheli': c.get('kills Heli'),
               'money': ec.get('money'),
               'econ': {k: v for k, v in ec.items() if k != 'money'}}
    if extra:
        row.update(extra)
    fh.write(json.dumps(row) + '\n')
    fh.flush()
    print(json.dumps(row)[:220], flush=True)
    return d


e = ZAREnv(PID)
log('pre', e)
e.to_planning()
assert e.phase_now() == 'planning'
log('planning', e)
e.vi.key_press(0x70, sc=59)                     # F1 speed1 (slow, timing)
e.vi.key_press(0x20, sc=57, hold=0.25)          # READY
time.sleep(3.0)
e.vi.key_press(0x20, sc=57, hold=0.25)          # dialog YES
time.sleep(3.0)
for _ in range(10):
    d = log('wait-battle', e)
    if d and d['where'].get('phase') == 'battle':
        break
    e.vi.key_press(0x20, sc=57, hold=0.25)
    time.sleep(2.0)
t_end = time.time() + 40
first_cast = False
while time.time() < t_end:
    d = log('poll', e)
    sim = float(d['clock'].get('sim_time', 0)) if d else 0
    if sim >= 8 and not first_cast:             # LOCKED cast (t<30)
        e.cast('1', int(e.cw * 0.5), int(e.ch * 0.45))
        log('cast-heli-locked', e)
        first_cast = True
    time.sleep(3.0)

# unlocked cast
e.cast('1', int(e.cw * 0.5), int(e.ch * 0.45))
log('cast-heli-open', e)
for i in range(6):                              # watch arrival + operation
    time.sleep(3.5)
    log(f'after-open-{i}', e)
# redeploy while alive
e.cast('1', int(e.cw * 0.3), int(e.ch * 0.6))
log('cast-heli-redeploy', e)
for i in range(6):
    time.sleep(3.5)
    log(f'after-redeploy-{i}', e)
# second redeploy (charge semantics probe)
e.cast('1', int(e.cw * 0.7), int(e.ch * 0.4))
log('cast-heli-redeploy2', e)
for i in range(8):
    time.sleep(3.5)
    log(f'after-redeploy2-{i}', e)
log('final', e)
print('saved', OUT)
