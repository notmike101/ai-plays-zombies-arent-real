"""Recover wedged instance. INPUT RULES (hard):
- VirtualInput inject=True EXACTLY ONCE per game process boot; enforced via a
  sentinel file .zarvi_<pid>. If relaunching, the sentinel for the NEW pid is absent,
  so make_game(pid, True) is correct only then. Re-injection HANGS the game.
- Real user cursor is never touched (all input = DLL virtual cursor + PostMessage).
Recovery ladder: observe -> ESC/RESUME probes -> kill+relaunch+blind nav (windowed).
"""
import sys, time, subprocess, os
sys.path.insert(0, r'D:\zar-scratch\scripts')
import psutil
from harness import Instance, grab
from zar_input import VirtualInput
from env_zar import ZarGame

LOGP = r'D:\zar-scratch\sessions\episodes\episodes.jsonl'
SENT = r'D:\zar-scratch\sessions\.zarvi_%d'


def sentinel(pid):
    return SENT % pid


def make_game(pid, inject):
    if inject and os.path.exists(sentinel(pid)):
        raise RuntimeError(f'pid {pid} already injected this boot; use inject=False')
    inst = Instance('inst2', launch=False)
    inst.pid = pid
    hwnd = inst._find_hwnd()
    inst.actions = []
    inst.log_action = lambda *a, **k: None
    vi = VirtualInput(pid, hwnd=hwnd, inject=inject)
    if inject:
        open(sentinel(pid), 'w').write('ok')
    return ZarGame(pid, hwnd, vi, log_path=LOGP)


def relaunch():
    def inst2_pids():
        out = []
        for p in psutil.process_iter(['name', 'pid']):
            if not (p.info['name'] or '').startswith('zombies'):
                continue
            try:
                d = os.path.basename(os.path.dirname(p.exe()))
            except Exception:
                continue
            if d == 'inst2':
                out.append(p.pid)
        return out
    for pid in inst2_pids():
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        f'Stop-Process -Id {pid} -Force -ErrorAction '
                        'SilentlyContinue'])
        try:
            os.remove(sentinel(pid))
        except OSError:
            pass
    time.sleep(2)
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    'Start-Process -FilePath '
                    '"D:\\zar-scratch\\game-copies\\inst2\\zombies-arent-real.exe" '
                    '-WorkingDirectory "D:\\zar-scratch\\game-copies\\inst2"'])
    time.sleep(3)
    for p in inst2_pids():
        return p
    return None


def nav(g):
    """Menu chain verified for windowed 1920x1200 client (window coords).
    Main menu -> CAMPAIGN -> Boston row -> START OVER (fresh campaign, L1)."""
    g.key(0x20); time.sleep(1.5)          # title splash dismiss
    g.key(0x0D, 'campaign'); time.sleep(2.0)
    g.click_screen(314, 215, tag='boston-row'); time.sleep(1.2)
    g.click_screen(804, 715, tag='start-over'); time.sleep(1.5)
    g.key(0x0D, 'redo-yes')
    time.sleep(9)


def recover(inject=False, pid=None):
    """Returns (game, obs). Pass current pid + inject=False for existing boot."""
    if pid:
        g = make_game(pid, inject)
        d = g.observe()
        if d:
            return g, d
        for _ in range(2):
            g.key(0x1B, 'esc')
            time.sleep(1.2)
            d = g.observe()
            if d:
                return g, d
            g.click_screen(310, 236, tag='resume')   # window pause overlay
            time.sleep(1.0)
            d = g.observe()
            if d:
                return g, d
        try:
            grab(g.hwnd).save(r'D:\zar-scratch\analysis\wedged_%d.png' % pid)
        except Exception:
            pass
    newpid = relaunch()
    time.sleep(20)
    g = make_game(newpid, True)       # fresh boot: the ONE injection
    nav(g)
    d = g.observe()
    if d is None:
        for _ in range(4):
            d = g.observe()
            if d:
                break
    return g, d


if __name__ == '__main__':
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    g, d = recover(inject=False, pid=pid)
    print('RECOVERED pid', g.pid, 'phase', d and d.get('phase'),
          'money', d and d.get('money'), 'zones',
          len(d.get('zones') or []) if d else -1)
