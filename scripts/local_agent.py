"""Local operator entry point. No game attachment or input during status/check."""
import argparse
import ast
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'sessions/nn_policy3.pt'
HISTORY = ROOT / 'analysis/nn_hist3.jsonl'


def script_role(command, cwd, root=ROOT):
    scripts = {'scripts/train_run.py': 'launcher', 'scripts/nn_play2.py': 'trainer',
               'visualizer/server.py': 'visualizer', 'visualizer/demo.py': 'preview',
               'scripts/local_agent.py': 'operator'}
    for arg in command[1:]:
        if arg.endswith('.py'):
            path = Path(arg)
            path = (Path(cwd) / path).resolve()
            for relative, role in scripts.items():
                if path == (root / relative).resolve():
                    return role if role != 'operator' or 'train' in command else None
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
    return dict(path=str(path), run_id=c.get('run_id'), schema=c['schema']['version'],
                inputs=len(c['schema']['inputs']), learning=c.get('learning'),
                optimizer_states=len(c['optimizer']['state']))


def preflight(copy='inst1'):
    checks, errors = {}, []

    def check(name, fn):
        try:
            checks[name] = fn()
        except Exception as e:
            errors.append(f'{name}: {e}')

    if sys.platform != 'win32':
        errors.append('Live training requires this Windows deployment')
    if ROOT != Path(source_constant(ROOT/'scripts/nn_play2.py', 'ROOT')).resolve():
        errors.append('Trainer still targets D:\\zar-scratch. Use that deployed checkout; '
                      'do not launch from a clone pointing at another checkout.')
        return dict(ok=False, checks=checks, errors=errors)
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
        if digest != source_constant(ROOT/'scripts/env_zar.py', 'BUILD_SHA256'):
            raise ValueError('Unsupported game executable; offsets need revalidation')
        if (path/'steam_appid.txt').read_text().strip() != '5185890':
            raise ValueError('Wrong steam_appid.txt')
        settings = (path/'steam_cloud/settings.ini').read_text()
        if not re.search(r'^difficulty\s*=\s*normal\s*$', settings, re.M):
            raise ValueError('Owned copy must use normal difficulty')
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
                next_step='Preserve active training; otherwise run check before train. '
                          'See notes/operator-runbook.md. History is a snapshot, not monitoring.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'check'])
    parser.add_argument('--copy', default='inst1')
    args = parser.parse_args()
    try:
        result = status() if args.command == 'status' else preflight(args.copy)
        print(json.dumps(result, indent=2))
        return 0 if result.get('ok', True) else 1
    except Exception as e:
        print(json.dumps(dict(ok=False, error=str(e))), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
