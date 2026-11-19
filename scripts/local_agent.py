"""Local operator entry point. No game attachment or input during status/check."""
import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'sessions/nn_policy4.pt'
HISTORY = ROOT / 'analysis/nn_hist4.jsonl'
LOCK = ROOT / 'analysis/nn3_operator.lock'


def script_role(command, cwd, root=ROOT):
    scripts = {'scripts/train_run.py': 'launcher', 'scripts/nn_play2.py': 'trainer',
               'visualizer/server.py': 'visualizer', 'visualizer/demo.py': 'preview',
               'scripts/local_agent.py': 'operator', 'scripts/compare_spatial.py': 'operator',
               'scripts/team_search.py': 'operator'}
    for arg in command[1:]:
        if arg.endswith('.py'):
            path = Path(arg)
            path = (Path(cwd) / path).resolve()
            for relative, role in scripts.items():
                if path == (root / relative).resolve():
                    return role if relative != 'scripts/local_agent.py' or 'train' in command else None
            return None
    return None


def inventory():
    import psutil
    rows = []
    for p in psutil.process_iter(['pid', 'exe', 'cmdline', 'create_time']):
        try:
            a = p.info
            exe = Path(a['exe'] or '')
            role = None
            if exe.name.lower() == 'zombies-arent-real.exe' and exe.parent.parent == ROOT/'game-copies':
                role = 'game'
            elif exe.name.lower() in ('python.exe', 'pythonw.exe'):
                role = script_role(a['cmdline'] or [], p.cwd())
            if role:
                rows.append(dict(role=role, **a, cwd=p.cwd(), priority=p.nice(),
                                 cpus=p.cpu_affinity()))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows


def recent_history(path=HISTORY, limit=65536):
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            start = max(0, f.tell()-limit)
            f.seek(start)
            if start:
                f.readline()
            lines = f.read(limit).decode('utf-8', errors='replace').splitlines()
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            pass
    return rows[-4:]


def owned_copy(name):
    if not re.fullmatch(r'inst\d+', name):
        raise ValueError('Copy must be an owned instN directory')
    path = ROOT/'game-copies'/name
    if path.resolve().parent != (ROOT/'game-copies').resolve():
        raise ValueError('Owned copy resolves outside game-copies')
    return path


def source_constant(file, name):
    for node in ast.parse(file.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name
                                               for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f'Cannot read {name} from {file}; update operator check')


def inspect_checkpoint(path=MODEL):
    if not path.is_file():
        raise ValueError(f'Checkpoint missing: {path}; recover it before resume (never random)')
    import torch
    import nn_play2 as train
    c = torch.load(path, map_location='cpu', weights_only=True)
    if c.get('schema') != train.checkpoint_schema():
        raise ValueError('Checkpoint schema differs from trainer; do not bypass compatibility')
    if not c.get('optimizer', {}).get('state'):
        raise ValueError('Checkpoint has no initialized optimizer; cannot resume Adam')
    net = train.PolicyNet2()
    net.load_state_dict(c['policy'])
    if not all(torch.isfinite(p).all().item() for p in net.parameters()):
        raise ValueError('Checkpoint contains non-finite policy weights')
    optimizer = torch.optim.Adam(net.parameters())
    optimizer.load_state_dict(c['optimizer'])
    return dict(path=str(path), run_id=c.get('run_id'), policy_id=train.policy_id(net), schema=c['schema']['version'],
                inputs=len(c['schema']['inputs']), learning=c.get('learning'),
                optimizer_states=len(c['optimizer']['state']))


def planning_roster(settings):
    from game_mechanics import UNITS
    match=re.search(r'^roster_plan[ \t]*=[ \t]*([^\r\n]*)$',settings,re.M)
    roster=match[1].split() if match else []
    if len(roster)!=7 or any(name not in (*UNITS,'-') for name in roster):
        raise ValueError('Invalid planning roster; expected seven supported unit/empty slots')
    return roster


def preflight(copy='inst1'):
    checks, errors = {}, []

    def check(name, fn):
        try:
            checks[name] = fn()
        except Exception as e:
            errors.append(f'{name}: {e}')

    if sys.platform != 'win32':
        errors.append('Live training requires this Windows deployment')
    for package, module in [('torch', 'torch'), ('numpy', 'numpy'), ('psutil', 'psutil'),
                            ('pefile', 'pefile'), ('Pillow', 'PIL')]:
        def dependency(package=package, module=module):
            importlib.import_module(module)
            return importlib.metadata.version(package)
        check(package, dependency)
    check('checkpoint', inspect_checkpoint)

    def game():
        path = owned_copy(copy)
        with (path/'zombies-arent-real.exe').open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != source_constant(ROOT/'scripts/game_mechanics.py', 'BUILD_SHA256'):
            raise ValueError('Unsupported game executable; offsets need revalidation')
        if (path/'steam_appid.txt').read_text().strip() != '5185890':
            raise ValueError('Wrong steam_appid.txt')
        settings = (path/'steam_cloud/settings.ini').read_text()
        if not re.search(r'^difficulty\s*=\s*normal\s*$', settings, re.M):
            raise ValueError('Owned copy must use normal difficulty')
        planning_roster(settings)  # The policy can persist a different valid roster.
        from prepare_game import full_unlock_profile
        unlocks = (path/'steam_cloud/unlocks.ini').read_text()
        wanted = set(re.findall(r'^unlock\s*=\s*(\w+\s+\w+)\s*$', full_unlock_profile(path).decode(), re.M))
        actual = set(re.findall(r'^unlock\s*=\s*(\w+\s+\w+)\s*$', unlocks, re.M))
        if wanted-actual:
            raise ValueError('Incomplete training availability; prepare a new full-availability copy: '+', '.join(sorted(wanted-actual)))
        return dict(copy=copy, sha256=digest)
    check('game', game)

    def dll():
        import pefile
        path = ROOT/'scripts/hookdll/target/release/hookdll.dll'
        with pefile.PE(str(path)) as pe:
            if pe.FILE_HEADER.Machine != 0x8664:
                raise ValueError('Input DLL must be x64')
            names = {x.name for x in pe.DIRECTORY_ENTRY_EXPORT.symbols}
            if b'zar_init' not in names:
                raise ValueError('Input DLL is missing zar_init')
        return str(path)
    check('input_dll', dll)
    return dict(ok=not errors, checks=checks, errors=errors)


def status():
    import psutil
    rows = inventory()
    return dict(root=str(ROOT), python=sys.executable, processes=rows,
                training_active=any(r['role'] in ('operator', 'launcher', 'trainer') for r in rows),
                checkpoint_exists=MODEL.is_file(), history=recent_history(),
                available_ram_gib=round(psutil.virtual_memory().available/2**30, 2),
                disk_free_gib=round(shutil.disk_usage(ROOT).free/2**30, 2),
                visualizer=listener(8765),
                next_step='Preserve active training; otherwise run check before train. '
                          'See notes/operator-runbook.md. History is a snapshot, not monitoring.')


def require_idle(rows, copy, self_pid=None, parent_pid=None, ancestor_pids=()):
    for row in rows:
        if row['pid'] == self_pid:
            continue
        if row['role'] == 'operator' and (row['pid'] == parent_pid or row['pid'] in ancestor_pids):
            continue  # Windows venv redirectors and our background-launch ancestors.
        if row['role'] in ('operator', 'launcher', 'trainer'):
            raise ValueError(f"Training already active: {row['role']} PID {row['pid']}; reuse it")
    for row in rows:
        if row['role'] == 'game' and Path(row['exe']).parent == owned_copy(copy):
            raise ValueError(f"{copy} already running as PID {row['pid']}; do not take over")


@contextmanager
def training_lock(path):
    import msvcrt
    with path.open('a+b') as f:
        if f.tell() == 0:
            f.write(b'0')
            f.flush()
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            raise ValueError('Another local operator holds the training lock') from e
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def limit_resources(copy_count=1):
    import psutil
    ram_gib = min(12, 4 + 2*(copy_count-1))
    if psutil.virtual_memory().available < ram_gib*2**30 or shutil.disk_usage(ROOT).free < 2*2**30:
        raise ValueError(f'Insufficient headroom: need {ram_gib} GiB available RAM and 2 GiB free disk')
    p = psutil.Process()
    cpus = p.cpu_affinity()
    p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    p.cpu_affinity(cpus[:min(8, max(1, len(cpus)//2))])


def train(args):
    import psutil
    extra_copies = getattr(args, 'extra_copy', None) or []
    copies = [args.copy, *extra_copies]
    if len(copies) > 8:
        raise ValueError('Parallel training is limited to eight game copies')
    if len(set(copies)) != len(copies):
        raise ValueError('Parallel training requires distinct game copies')
    episodes = getattr(args, 'episodes_per_copy', 2)
    if episodes < 1:
        raise ValueError('Episodes per copy must be positive')
    if args.rounds < 1:
        raise ValueError('Rounds must be positive')
    ancestors = [p.pid for p in psutil.Process().parents()]
    processes = inventory()
    for copy in copies:
        require_idle(processes, copy, os.getpid(), ancestor_pids=ancestors)
        report = preflight(copy)
        if not report['ok']:
            raise ValueError(f"{copy}: " + '; '.join(report['errors']))
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    if not args.foreground:
        log = ROOT / f'analysis/nn3_operator_{stamp}.log'
        command = [sys.executable, '-B', str(Path(__file__).resolve()), 'train',
                   '--foreground', '--copy', args.copy, '--rounds', str(args.rounds),
                   '--seed', str(args.seed)]
        if getattr(args, 'allow_progression', False):
            command.append('--allow-progression')
        if episodes != 2:
            command.extend(['--episodes-per-copy', str(episodes)])
        for copy in extra_copies:
            command.extend(['--extra-copy', copy])
        with log.open('w') as f:
            p = subprocess.Popen(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        return dict(ok=True, status='starting', pid=p.pid, log=str(log),
                    next_step='Read this log and run status. Starting is not proof of a completed update.')
    with training_lock(LOCK):
        processes = inventory()
        for copy in copies:
            require_idle(processes, copy, os.getpid(), ancestor_pids=ancestors)
        limit_resources(len(copies))  # Applied before the launcher can spawn any game or worker.
        command = [sys.executable, '-B', str(ROOT/'scripts/train_run.py'),
                   '--copies', *copies, '--eps', str(episodes), '--rounds', str(args.rounds),
                   '--seed', str(args.seed), '--start', 'fresh', '--model', str(MODEL),
                   '--history', str(HISTORY), '--log', str(ROOT/f'analysis/nn3_{stamp}.log')]
        if getattr(args, 'allow_progression', False):
            command.append('--allow-progression')
        print(json.dumps(dict(status='launching', command=command)), flush=True)
        rc = subprocess.call(command, cwd=ROOT)
        return dict(ok=rc == 0, status='finished', returncode=rc)


def listener(port):
    import psutil
    owners = {c.pid for c in psutil.net_connections(kind='tcp')
              if c.status == psutil.CONN_LISTEN and c.laddr.port == port}
    if not owners:
        return None
    if len(owners) != 1 or None in owners:
        raise ValueError(f'Port {port} has ambiguous owners: {owners}')
    p = psutil.Process(owners.pop())
    return dict(pid=p.pid, create_time=p.create_time(), command=p.cmdline(),
                role=script_role(p.cmdline(), p.cwd()), port=port)


def start_visualizer(port, host):
    current = listener(port)
    if current:
        if current['role'] != 'visualizer':
            raise ValueError(f'Port {port} belongs to another process; refusing to replace it')
        return dict(ok=True, status='already_running', **current)
    log = ROOT/f'analysis/nn3_visualizer_{port}.log'
    with log.open('w') as f:
        p = subprocess.Popen([sys.executable, '-B', str(ROOT/'visualizer/server.py'),
                              '--host', host, '--port', str(port)], cwd=ROOT, stdout=f, stderr=f,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    import psutil
    launched = psutil.Process(p.pid)
    created = launched.create_time()
    for _ in range(40):
        if p.poll() is not None:
            raise ValueError(f'Visualizer exited; inspect {log}')
        current = listener(port)
        owned = {p.pid, *(c.pid for c in launched.children(recursive=True))}
        if current and current['pid'] in owned and current['role'] == 'visualizer':
            return dict(ok=True, status='listening', **current,
                        url=f'http://localhost:{port}', log=str(log))
        time.sleep(.1)
    # Do not leave an unconfirmed server behind after reporting failure.
    stop_process(p.pid, created, 'visualizer')
    raise ValueError(f'Visualizer did not bind within 4 seconds; inspect {log}')


def stop_process(pid, created, role):
    import psutil
    p = psutil.Process(pid)
    if not math.isfinite(created) or abs(p.create_time()-created) >= .01:
        raise ValueError('Process identity changed; run status again')
    if script_role(p.cmdline(), p.cwd()) != role:
        raise ValueError('Wrong script/checkout; refusing to stop it')
    children = p.children(recursive=True)
    allowed = {Path(p.exe()).resolve(), Path(sys.executable).resolve(),
               Path(sys._base_executable).resolve(),
               (Path(os.environ['SystemRoot'])/'System32/conhost.exe').resolve()}
    if any(Path(c.exe()).resolve() not in allowed for c in children):
        raise ValueError('Unexpected child process; inspect before stopping')
    p.kill()
    for child in children:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs([p, *children], timeout=15)
    if alive:
        raise ValueError(f'Processes remain: {[p.pid for p in alive]}')
    return dict(ok=True, status='stopped', pid=pid,
                next_step='Run status to verify launcher/game cleanup. Unsaved training batch is lost.'
                          if role == 'trainer' else 'Visualizer stopped; training is independent.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'check', 'prepare-game', 'build-input', 'train', 'train-stop',
                                           'visualizer-start', 'visualizer-stop', 'checkpoint-export',
                                           'checkpoint-publish', 'checkpoint-verify', 'checkpoint-import'])
    parser.add_argument('--copy', default='inst1')
    parser.add_argument('--extra-copy', action='append', help='Additional owned game copy, up to eight copies total')
    parser.add_argument('--episodes-per-copy', type=int, default=2,
                        help='Sequential episodes per game per update (default: 2)')
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--allow-progression', action='store_true', help='Explicitly allow Boston L2–L5')
    parser.add_argument('--seed', type=int, default=20261140)
    parser.add_argument('--foreground', action='store_true', help='Keep training attached to this terminal')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', choices=['0.0.0.0', '127.0.0.1'], default='0.0.0.0')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--created', type=float, help='Exact create_time from current status output')
    parser.add_argument('--bundle', type=Path, help='Directory containing checkpoint, manifest and SHA256SUMS')
    args = parser.parse_args()
    if args.extra_copy and args.command != 'train':
        parser.error('--extra-copy applies only to train')
    if args.command.endswith('-stop') and (not args.pid or args.created is None):
        parser.error('Stop requires --pid and --created from a fresh status result')
    if args.command in ('checkpoint-verify', 'checkpoint-import') and args.bundle is None:
        parser.error('Checkpoint verify/import requires --bundle')
    try:
        if args.command.startswith('checkpoint-'):
            from checkpoints import snapshot, publish, verify_bundle, import_bundle
            if args.command == 'checkpoint-export': result = dict(ok=True, bundle=str(snapshot()))
            elif args.command == 'checkpoint-publish': result = dict(ok=True, **publish(snapshot()))
            elif args.command == 'checkpoint-verify': result = dict(ok=True, manifest=verify_bundle(args.bundle))
            else: result = dict(ok=True, manifest=import_bundle(args.bundle))
        elif args.command == 'status':
            result = status()
        elif args.command == 'check':
            result = preflight(args.copy)
        elif args.command == 'prepare-game':
            from prepare_game import prepare_copy
            from project import load_config, config_path
            result = dict(ok=True, copy=str(prepare_copy(config_path(load_config(), 'game', 'install_dir'), args.copy)))
        elif args.command == 'build-input':
            from build_hook import build
            result = dict(ok=True, build=build())
        elif args.command == 'train':
            result = train(args)
        elif args.command == 'visualizer-start':
            result = start_visualizer(args.port, args.host)
        else:
            result = stop_process(args.pid, args.created,
                                  'trainer' if args.command == 'train-stop' else 'visualizer')
        print(json.dumps(result, indent=2))
        return 0 if result.get('ok', True) else 1
    except Exception as e:
        print(json.dumps(dict(ok=False, error=str(e))), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
