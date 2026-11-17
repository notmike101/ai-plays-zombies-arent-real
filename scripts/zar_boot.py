"""Screenshot-free boot for owned game-copies/instN; never touches the install.

boot(copy_dir, ('campaign', 'stage1')) starts a fresh normal Boston L1.
boot(copy_dir, ('campaign', 'continue')) resumes the saved world then retries
to planning if necessary. Unsupported destinations fail before launch.
The caller owns successful processes; failures always kill their new process.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

import psutil

from env_zar import ZAREnv, ZAREnvError
from zar_input import VirtualInput, window_of_pid, user32

ROOT = Path(__file__).resolve().parents[1]
COPIES = ROOT / 'game-copies'
EXE = 'zombies-arent-real.exe'
_ENV_ATTACH_LOCK = threading.Lock()


def copy_path(copy_dir):
    path = Path(copy_dir).resolve()
    if path.parent != COPIES or not re.fullmatch(r'inst\d+', path.name):
        raise ValueError(f'Expected {COPIES}/instN, got {path}')
    return path


def copy_processes(copy_dir):
    path = copy_path(copy_dir)
    out = []
    for process in psutil.process_iter(['name', 'exe']):
        if (process.info['name'] or '').lower() != EXE:
            continue
        if process.info['exe'] and Path(process.info['exe']).resolve().parent == path:
            out.append(process)
    return out


def stop(env):
    """Close only this verified copy process and its local observation handles."""
    try:
        process = psutil.Process(env.pid)
        copy_path(Path(process.exe()).parent)
        process.kill()
        process.wait(15)
    except psutil.NoSuchProcess:
        pass
    finally:
        env.vi.close()
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(env.h))
        (ROOT / 'sessions' / f'.zarvi_{env.pid}').unlink(missing_ok=True)


def click_fraction(vi, x, y):
    rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(vi.hwnd, ctypes.byref(rect)) or rect.right <= 0 or rect.bottom <= 0:
        raise ZAREnvError(f'Invalid client rect: {vi.diagnostics()}')
    vi.move_to(round(x * rect.right), round(y * rect.bottom))
    time.sleep(0.2)
    vi.click(hold=0.15)
    time.sleep(1.5)


def boot(copy_dir, dest=('campaign', 'stage1')):
    """Launch, inject once, navigate with client fractions, verify planning.

    Busy copies are refused. Boot waits 75 s for the welcome service, then
    uses bounded menu/dialog steps. No screenshots, console or physical input.
    """
    path = copy_path(copy_dir)
    if tuple(dest) not in (('campaign', 'stage1'), ('campaign', 'continue')):
        raise ValueError(f'Unsupported destination {dest!r}; use campaign/stage1 or campaign/continue')
    if copy_processes(path):
        raise ZAREnvError(f'{path.name} already has a game; refusing to take ownership')
    if (path / 'steam_appid.txt').read_text().strip() != '5185890':
        raise ZAREnvError(f'Incorrect steam_appid.txt in {path}')
    settings = (path / 'steam_cloud/settings.ini').read_text()
    if not re.search(r'^difficulty\s*=\s*normal\s*$', settings, re.M):
        raise ZAREnvError(f'{path.name} must use normal difficulty')
    started = time.monotonic()
    process = subprocess.Popen([str(path / EXE)], cwd=path,
                               creationflags=subprocess.DETACHED_PROCESS,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    vi = env = None
    step = 'window'
    print(f'{path.name} launched pid={process.pid}', flush=True)
    try:
        while not window_of_pid(process.pid):
            if process.poll() is not None or time.monotonic() - started > 90:
                raise ZAREnvError('Window did not appear within 90 s')
            time.sleep(0.5)
        step = 'injection'
        vi = VirtualInput(process.pid)
        vi.enable()
        tick = vi.diagnostics()['pump_ticks']
        time.sleep(0.1)
        if vi.patches() < 4 or vi.diagnostics()['pump_ticks'] == tick:
            raise ZAREnvError('Virtual-input hooks/pump unavailable')
        step = 'welcome'
        time.sleep(max(0, 75 - (time.monotonic() - started)))
        click_fraction(vi, .4245, .844)
        step = 'campaign'
        click_fraction(vi, .207, .368)
        # memscan.module_base installs a per-call ctypes Structure signature.
        # Serialize attachments so concurrent copies cannot replace that type.
        with _ENV_ATTACH_LOCK:
            env = ZAREnv(process.pid)
        # Boston is the persisted/default first campaign. Verify its identity below.
        step = dest[1]
        target = (.451, .738) if dest[1] == 'stage1' else (.446, .813)
        click_fraction(vi, *target)
        if not env.obs()['civ']:
            vi.key_press(0x0D, sc=28, hold=.15)
        time.sleep(5)
        if not env.obs()['civ']:
            # Only attempt ESC when the first start did not enter a world: an
            # unconditional ESC backs out of an unobstructed campaign page.
            step = 'dismiss campaign dialog'
            vi.key_press(0x1B, sc=1, hold=.15)
            time.sleep(1)
            click_fraction(vi, *target)
            if not env.obs()['civ']:
                vi.key_press(0x0D, sc=28, hold=.15)
            time.sleep(5)
        step = 'verify world'
        dump = env.dump()
        if not dump and env.obs()['civ']:
            # A world counter plus a silent dump can mean a modal owns input.
            vi.key_press(0x1B, sc=1, hold=.15)
            time.sleep(1.1)
            dump = env.dump()
        if dest[1] == 'continue' and dump and dump.get('where', {}).get('phase') != 'planning':
            env.to_planning()
            time.sleep(1.1)
            dump = env.dump()
        where = dump.get('where', {}) if dump else {}
        if (where.get('phase') != 'planning' or where.get('campaign') != 'Boston, MA'
                or where.get('hardcore') != 'false' or where.get('ultra_hardcore') != 'false'):
            raise ZAREnvError(f'World mismatch: {where}; obs={env.obs()}')
        if dest[1] == 'stage1' and (where.get('stage') != '0 (stage 1 of 5)'
                or float(dump['economy']['money']) != 3111 or env.obs()['civ'] <= 5000):
            raise ZAREnvError(f'Fresh L1 mismatch: {where}; economy={dump.get("economy")}')
        vi.close()
        print(f'{path.name} READY pid={process.pid} obs={env.obs()}', flush=True)
        return env
    except BaseException as error:
        debug = vi.diagnostics() if vi is not None and vi.buf is not None and vi.view else {}
        if env is not None:
            stop(env)
        elif process.poll() is None:
            process.kill()
            process.wait(timeout=15)
        if vi is not None:
            vi.close()
        (ROOT / 'sessions' / f'.zarvi_{process.pid}').unlink(missing_ok=True)
        raise ZAREnvError(f'{path.name} failed at {step}: {error}; section={debug}') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('copies', nargs='*', default=['inst1', 'inst2', 'inst3', 'inst4'])
    args = parser.parse_args()
    paths = [copy_path(COPIES / name) for name in args.copies]
    if len(set(paths)) != len(paths):
        parser.error('Copies must be distinct')
    for path in paths:
        if not path.exists():
            shutil.copytree(COPIES / 'inst4', path,
                            ignore=shutil.ignore_patterns('debug_dumps', '*.log'))
    envs, failed = [], False
    try:
        with ThreadPoolExecutor(max_workers=len(paths)) as pool:
            futures = {pool.submit(boot, path): path for path in paths}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    envs.append(future.result())
                    print(f'PASS {path.name} boot', flush=True)
                except Exception as error:
                    failed = True
                    print(f'FAIL {path.name} {error}', flush=True)
        # All successful worlds must still coexist in planning at the barrier.
        for env in envs:
            if env.phase_now() != 'planning':
                failed = True
                print(f'FAIL {env.pid} simultaneous planning barrier', flush=True)
        print(f'{"FAIL" if failed else "PASS"} simultaneous planning: {len(envs)}/{len(paths)}', flush=True)
    finally:
        for env in envs:
            stop(env)
        remaining = [p.pid for path in paths for p in copy_processes(path)]
        print(f'{"FAIL" if remaining else "PASS"} cleanup remaining={remaining}', flush=True)
        failed |= bool(remaining)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
