"""Prepare a NEW owned copy; never modify the source install or an existing copy."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import stat
import tempfile

from project import ROOT, load_config, config_path

DIRECTORIES = {'art', 'assets', 'campaigns', 'fonts', 'lang', 'maps', 'mutators', 'sounds'}
FILES = {'zombies-arent-real.exe', 'steam_api64.dll', 'balance.ini', 'battle_order.txt',
         'config.ini', 'unlocks.ini', 'EULA.html', 'PRIVACY_POLICY.html'}
SETTINGS = '''# Agent copy: interface defaults only; no campaign progress or purchased units.
master_volume = 0.000
window_mode = windowed
ui_scale = 1.000
graphics = low
language = en
difficulty = normal
camera_intro = false
tutorial = false
tutorial_intro = false
height_auto = false
usage_sharing = false
usage_asked = true
low_fps_asked = true
binds_version = 5
readied_once = true
debt_hint_seen = true
mine_tip_seen = true
para_tip_seen = true
escalate_tip_seen = true
outside_tip_seen = true
restart_tips = false
roster_plan = Garrison Mortar Napalm Nest Mine C4 GasMortar
roster_battle = - - - - - - -
bind_slot1 = _1
bind_slot2 = _2
bind_slot3 = _3
bind_slot4 = _4
bind_slot5 = _5
bind_slot6 = _6
bind_slot7 = T
'''


def expected_hash():
    from local_agent import source_constant
    return source_constant(ROOT/'scripts/env_zar.py', 'BUILD_SHA256')


def is_link(path):
    return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0)
                                    & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def checked_files(source):
    if is_link(source):
        raise ValueError(f'Refusing linked source: {source}')
    files = []
    pending = [p for p in source.iterdir() if p.name in DIRECTORIES | FILES]
    while pending:
        item = pending.pop()
        if is_link(item):
            raise ValueError(f'Refusing linked game asset: {item}')
        if item.is_dir():
            pending.extend(item.iterdir())
        elif item.is_file():
            files.append(item)
    return files


def sha256(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def full_unlock_profile(source):
    """User-authorized training availability; does not buy levels or change budgets."""
    entries = set(re.findall(r'^(unit|ability|upgrade|perk)\s+(\w+)\s*(?:#.*)?$',
                             (Path(source)/'unlocks.ini').read_text(), re.M))
    if not entries:
        raise ValueError('No unlock definitions found in the supported game')
    entries.add(('perk', 'Extra_Zones'))  # Verified native perk in this supported build.
    return ('# Full-availability training profile; not a record of earned progression.\n'
            'breach_restarts = 0\n'+''.join(f'unlock = {kind} {name}\n' for kind, name in sorted(entries))).encode()


def prepare_copy(source, name, unlocks=None):
    source = Path(source)
    if not re.fullmatch(r'inst\d+', name):
        raise ValueError('Copy must be named instN')
    copies = ROOT/'game-copies'
    # An existing compatible owned copy can supply assets when the install updated.
    if (ROOT.is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(ROOT) and source.resolve().parent != copies):
        raise ValueError('Source must be an external install or an existing owned copy')
    if copies.resolve() != copies:
        raise ValueError('game-copies must not redirect outside the repository')
    target = copies/name
    if target.exists():
        raise FileExistsError(f'Refusing to overwrite {target}; choose a new copy')
    profile = Path(unlocks).read_bytes() if unlocks is not None else None
    files = checked_files(source)
    expected = expected_hash()
    if sha256(source/'zombies-arent-real.exe') != expected:
        raise ValueError('Unsupported game build; revalidate native offsets before copying')
    if profile is None: profile = full_unlock_profile(source)
    needed = sum(f.stat().st_size for f in files)
    if shutil.disk_usage(ROOT).free < needed + 2*2**30:
        raise ValueError('Not enough disk headroom for the copy plus 2 GiB reserve')
    copies.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=copies) as temp:
        stage = Path(temp)/name
        stage.mkdir()
        for file in files:
            destination = stage/file.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
        if sha256(stage/'zombies-arent-real.exe') != expected:
            raise ValueError('Game build changed during copying')
        (stage/'steam_cloud').mkdir()
        (stage/'steam_cloud/settings.ini').write_text(SETTINGS, encoding='utf-8')
        (stage/'steam_cloud/unlocks.ini').write_bytes(profile)
        (stage/'steam_appid.txt').write_text('5185890\n', encoding='ascii')
        stage.rename(target)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copy', default='inst1')
    parser.add_argument('--unlocks-from', type=Path, help='Override full availability with an explicit existing unlocks.ini')
    args = parser.parse_args()
    print(prepare_copy(config_path(load_config(), 'game', 'install_dir'), args.copy, args.unlocks_from))
