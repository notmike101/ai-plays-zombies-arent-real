"""Start battle (R/READY/YES) on running game, verify ticking, cast cure, on hang capture thread stacks via Frida -> analysis/frh_stacks.txt."""
import sys, time, struct, json
sys.path.insert(0, 'scripts')
from recover import make_game
from zar_input import VirtualInput
from memscan import module_base, open_proc, read
from zarmem import admin_command
import psutil

PID = int(sys.argv[1]) if len(sys.argv) > 1 else None
g = make_game(PID, False)
base = module_base(PID); h = open_proc(PID); p = psutil.Process(PID)

def gv(r):
    d = read(h, base + r, 8)
    return struct.unpack('<q', d)[0] if d and len(d) == 8 else None

vi = VirtualInput(PID, g.hwnd)
vi.inject(); time.sleep(0.8); vi.enable(); time.sleep(0.4)
if (gv(0x650f18) or 0) == 0:
    vi.key_press(0x20, sc=57); time.sleep(2.6)      # READY
    vi.key_press(0x20, sc=57); time.sleep(2.0)      # YES
for i in range(12):
    z1 = gv(0x650f18); time.sleep(3); z2 = gv(0x650f18)
    print('zomb', z1, '->', z2, 'cpu', round(p.cpu_percent(), 1), flush=True)
    if z2 > z1 + 500:
        break
vi.move_to(749, 260); time.sleep(0.3)
admin_command(g.hwnd, 'cure here')
print('CAST sent', flush=True)
z0 = gv(0x650f18)
time.sleep(30)
z1 = gv(0x650f18)
print('frozen check', z0, '->', z1, flush=True)

import frida
JS = r"""
function mods() {}
var out = [];
var ts = Process.enumerateThreads();
for (var i = 0; i < ts.length; i++) {
  var t = ts[i];
  if (t.state !== 'running' && t.state !== 'blocked') continue;
  var bt;
  try { bt = Thread.backtrace(t.context, Backtracer.FUZZY); } catch (e) { bt = []; }
  if (!bt.length) { try { bt = Thread.backtrace(t.context, Backtracer.ACCURATE); } catch (e2) { bt = []; } }
  var lines = bt.slice(0, 16).map(function (a) {
    var mm = Process.findModuleByAddress(a);
    return a.toString() + (mm ? (' ' + mm.name + '+0x' + a.sub(mm.base).toString(16)) : '');
  });
  out.push('THREAD ' + t.id + ' ' + t.state + '\n' + lines.join('\n'));
}
send(out.join('\n===\n'));
"""
sess = frida.attach(PID)
got = {}
sc = sess.create_script(JS)
sc.on('message', lambda m, d: got.setdefault('stacks', m.get('payload')))
sc.load()
time.sleep(8)
open('analysis/frh_stacks.txt', 'w').write(str(got.get('stacks')))
print('STACKS WRITTEN', flush=True)
try: sess.detach()
except Exception: pass
