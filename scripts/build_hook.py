"""Build/test the source-only hook twice, verify deterministic output, then deploy."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

from project import ROOT

CRATE = ROOT/'scripts/hookdll'
TARGET = 'x86_64-pc-windows-msvc'


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def rust_flags(stage):
    return [f'--remap-path-prefix={stage}=/zar-build', '-C', 'link-arg=/Brepro',
            '-C', 'link-arg=/PDBALTPATH:hookdll.pdb']


def assert_idle():
    from local_agent import inventory
    if any(p['role'] == 'game' for p in inventory()):
        raise ValueError('Refusing DLL deployment with a running game; stop owned copies first')


def build():
    assert_idle()
    with (CRATE/'rust-toolchain.toml').open('rb') as f:
        toolchain = tomllib.load(f)['toolchain']['channel']
    compiler = subprocess.run(['rustc', f'+{toolchain}', '--version', '--verbose'],
                              check=True, capture_output=True, text=True).stdout.strip()
    cargo = subprocess.run(['cargo', f'+{toolchain}', '--version'], check=True,
                           capture_output=True, text=True).stdout.strip()
    target = CRATE/'target'
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-build-', dir=target) as tmp:
        outputs = []
        for number in (1, 2):
            stage = Path(tmp)/str(number)
            source = stage/'crate'
            shutil.copytree(CRATE/'src', source/'src')
            for name in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml'):
                shutil.copy2(CRATE/name, source/name)
            env = os.environ.copy()
            env.pop('RUSTFLAGS', None)
            env['CARGO_ENCODED_RUSTFLAGS'] = '\x1f'.join(rust_flags(str(stage)))
            env['CARGO_TARGET_DIR'] = str(stage/'target')
            command = ['cargo', f'+{toolchain}', '--locked', '--manifest-path', str(source/'Cargo.toml'),
                       '--target', TARGET, '--release']
            if number == 1:
                subprocess.run(command[:2]+['test']+command[2:], cwd=source, env=env, check=True)
            subprocess.run(command[:2]+['build']+command[2:], cwd=source, env=env, check=True)
            outputs.append(stage/'target'/TARGET/'release/hookdll.dll')
        hashes = [digest(p) for p in outputs]
        if hashes[0] != hashes[1]:
            raise ValueError('Clean DLL builds differ; no deployment performed')
        import pefile
        with pefile.PE(str(outputs[0])) as pe:
            if pe.FILE_HEADER.Machine != 0x8664 or b'zar_init' not in {s.name for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}:
                raise ValueError('DLL x64/export validation failed')
            linker = f'{pe.OPTIONAL_HEADER.MajorLinkerVersion}.{pe.OPTIONAL_HEADER.MinorLinkerVersion}'
        assert_idle()
        destination = target/'release/hookdll.dll'
        destination.parent.mkdir(exist_ok=True)
        staged = destination.with_suffix('.dll.tmp')
        shutil.copy2(outputs[0], staged)
        os.replace(staged, destination)
        sources = {str(p.relative_to(CRATE)): digest(p) for p in
                   [CRATE/'Cargo.toml', CRATE/'Cargo.lock', CRATE/'rust-toolchain.toml', *sorted((CRATE/'src').rglob('*.rs'))]}
        manifest = dict(sha256=hashes[0], target=TARGET, toolchain=toolchain, rustc=compiler,
                        cargo=cargo, pe_linker_version=linker, sources=sources,
                        flags=rust_flags('<staging>'), matching_clean_builds=2)
        (target/'release/build-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        return manifest


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
