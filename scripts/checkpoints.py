"""Immutable checkpoint bundles and idempotent, verified GitHub Release publication."""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from project import ROOT, load_config, config_path

MODEL = ROOT/'sessions/nn_policy4.pt'
HISTORY = ROOT/'analysis/nn_hist4.jsonl'
EXPORTS = ROOT/'sessions/exports'
ASSETS = ('nn_policy4.pt', 'manifest.json', 'SHA256SUMS')


def sha(data): return hashlib.sha256(data).hexdigest()


def helper(command, *args, check=True):
    helper_path = config_path(load_config(), 'sharing', 'identity_helper')
    if not helper_path.is_file(): raise ValueError('Configured identity helper is missing')
    result = subprocess.run(['node', str(helper_path), command, *map(str, args)],
                            cwd=ROOT, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def repository():
    repo = load_config().get('sharing', {}).get('repository', '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo): raise ValueError('Set sharing.repository to OWNER/REPO')
    return repo


def gh(*args, check=True):
    return helper('gh', *args, '--repo', repository(), check=check)


def source_record():
    # Runtime policy2/history2 dirt does not make the active trainer source dirty.
    paths = ['scripts', 'visualizer/*.py', 'requirements.txt']
    dirty = helper('git', 'status', '--porcelain', '--', *paths).stdout.strip()
    if dirty: raise ValueError('Commit relevant source changes before exporting: '+dirty)
    return dict(commit=helper('git', 'rev-parse', 'HEAD').stdout.strip(),
                meaning='Checkout at capture, NOT verified training revision of these weights',
                files={str(p.relative_to(ROOT)).replace('\\', '/'): sha(p.read_bytes()) for p in
                       [ROOT/'scripts/nn_play2.py', ROOT/'scripts/env_zar.py', ROOT/'scripts/spatial.py',
                        ROOT/'scripts/zar_input.py', ROOT/'scripts/native_state.py',
                        ROOT/'scripts/native_hud.py', ROOT/'scripts/game_controls.py',
                        ROOT/'scripts/game_mechanics.py', ROOT/'scripts/mechanic_contract.py',
                        ROOT/'scripts/team_search.py', ROOT/'scripts/layout_memory.py',
                        ROOT/'scripts/crowd_forecast.py',
                        ROOT/'scripts/policy_mechanics.py', ROOT/'visualizer/labels.py']})


def checkpoint_fields(raw):
    import torch
    data = torch.load(io.BytesIO(raw), map_location='cpu', weights_only=True)
    allowed = {'policy', 'optimizer', 'schema', 'learning', 'run_id'}
    if not isinstance(data, dict) or set(data)-allowed:
        raise ValueError('Unexpected checkpoint fields; review before publication')
    return data


def metrics(info):
    result = dict(not_evaluation=True, available=False)
    try:
        with HISTORY.open('rb') as f:
            f.seek(0, 2); start = max(0, f.tell()-2**20); f.seek(start)
            if start: f.readline()
            lines = f.read().decode('utf-8').splitlines()
    except FileNotFoundError: return result
    rows = []
    for line in lines:
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: continue
    update = next((r for r in reversed(rows) if r.get('kind') == 'update'
                   and r.get('run_id') == info['run_id'] and r.get('checkpoint_id') == info['policy_id']), None)
    if update:
        episodes = [r for r in rows if r.get('kind') == 'episode' and
                    (r.get('run_id'), r.get('round')) == (update['run_id'], update['round'])]
        result.update(available=True, round=update['round'],
                      meaning='Training batch consumed by this update, not evaluation of the updated policy',
                      episodes=[{k:r.get(k) for k in ('scenario', 'start_kind', 'end', 'saved_frac', 'win')}
                                for r in episodes])
    return result


def verify_bundle(bundle):
    from local_agent import inspect_checkpoint
    bundle = Path(bundle)
    sums = dict(line.split('  ', 1)[::-1] for line in (bundle/'SHA256SUMS').read_text().splitlines())
    if set(sums) != {'nn_policy4.pt', 'manifest.json'}:
        raise ValueError('Unexpected checksum file entries')
    for name, digest in sums.items():
        if sha((bundle/name).read_bytes()) != digest: raise ValueError(f'{name} checksum mismatch')
    manifest = json.loads((bundle/'manifest.json').read_text())
    if manifest['checkpoint_sha256'] != sums['nn_policy4.pt']:
        raise ValueError('Checkpoint checksum differs from manifest')
    checkpoint_fields((bundle/'nn_policy4.pt').read_bytes())
    info = inspect_checkpoint(bundle/'nn_policy4.pt')
    if info['policy_id'] != manifest['policy_id']:
        raise ValueError('Policy identity differs from manifest')
    if 'campaign_team' in manifest:
        from team_search import checkpoint_team
        record=manifest['campaign_team']
        if checkpoint_team(record,info['policy_id'])!=record:
            raise ValueError('Unexpected campaign checkpoint fields')
        if manifest.get('bundle_id')!=bundle_id(sums['nn_policy4.pt'],record):
            raise ValueError('Campaign bundle identity mismatch')
    elif manifest.get('bundle_id',sums['nn_policy4.pt'])!=sums['nn_policy4.pt']:
        raise ValueError('Bundle identity mismatch')
    return manifest


def bundle_id(digest,record):
    if record is None:return digest
    return sha(digest.encode()+json.dumps(record,sort_keys=True,separators=(',',':')).encode())


def latest_team(directory,base):
    from team_search import checkpoint_team
    paths=sorted(Path(directory).glob('coverage-team-*/champion.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    for path in paths:
        if path.stat().st_size>2**20:raise ValueError('Oversized campaign checkpoint')
        record=json.loads(path.read_text())
        if record.get('base')==base:return checkpoint_team(record,base)
    return None


def snapshot(model=MODEL, exports=EXPORTS):
    from local_agent import inspect_checkpoint, source_constant
    # Trainer atomically replaces this path. Read one opened revision, never .tmp/.previous.
    raw = Path(model).read_bytes()
    data = checkpoint_fields(raw)
    digest = sha(raw)
    exports = Path(exports)
    exports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=exports) as temp:
        stage = Path(temp)/'bundle'; stage.mkdir()
        (stage/'nn_policy4.pt').write_bytes(raw)
        info = inspect_checkpoint(stage/'nn_policy4.pt')
        record=latest_team(HISTORY.parent,info['policy_id'])
        identity=bundle_id(digest,record)
        target=exports/identity
        if target.exists():
            verify_bundle(target)
            return target
        manifest = dict(format=1, captured_at=datetime.now(timezone.utc).isoformat(),
                        checkpoint_sha256=digest, policy_id=info['policy_id'], run_id=info['run_id'],
                        schema=data['schema'], learning=data.get('learning'),
                        supported_game_sha256=source_constant(ROOT/'scripts/game_mechanics.py', 'BUILD_SHA256'),
                        source_at_capture=source_record(), training_source_revision=None,
                        metrics=metrics(info),
                        limitations=['Not a complete campaign/board/RNG snapshot',
                                     'No claim of >=35% saved consistently; objective unmet'])
        if record:manifest.update(format=2,campaign_team=record,bundle_id=identity)
        (stage/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        (stage/'SHA256SUMS').write_text(''.join(f'{sha((stage/name).read_bytes())}  {name}\n'
                                            for name in ASSETS[:2]), encoding='ascii')
        verify_bundle(stage)
        stage.rename(target)
    return target


def import_bundle(bundle, destination=MODEL):
    from local_agent import inventory
    if any(r['role'] in ('operator', 'launcher', 'trainer') for r in inventory()):
        raise ValueError('Training is active; refuse checkpoint import')
    destination = Path(destination)
    if destination.exists(): raise FileExistsError('Preserve/move the existing checkpoint before import')
    manifest = verify_bundle(bundle)
    raw = (Path(bundle)/'nn_policy4.pt').read_bytes()
    if sha(raw) != manifest['checkpoint_sha256']: raise ValueError('Bundle changed during import')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        except BaseException:
            f.close(); temp.unlink(); raise
    try:
        os.link(temp, destination)  # Atomic creation, refuses an existing destination even in a race.
    finally:
        temp.unlink(missing_ok=True)
    return manifest


def release_info(tag):
    result = gh('release', 'view', tag, '--json', 'isDraft,url', check=False)
    if result.returncode == 0: return json.loads(result.stdout)
    if 'release not found' in result.stderr.lower(): return None
    raise RuntimeError(result.stderr.strip() or 'Could not inspect release')


def download_verified(tag, digest):
    EXPORTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.verify-release-', dir=EXPORTS) as temp:
        args = ['release', 'download', tag, '--dir', temp]
        for asset in ASSETS: args += ['--pattern', asset]
        gh(*args)
        manifest = verify_bundle(Path(temp))
        if manifest.get('bundle_id',manifest['checkpoint_sha256']) != digest:
            raise ValueError('Remote checkpoint differs from local snapshot')
        return manifest


def publish(bundle):
    bundle = Path(bundle)
    manifest = verify_bundle(bundle)
    digest = manifest.get('bundle_id',manifest['checkpoint_sha256'])
    tag = 'checkpoint-'+digest[:16]
    existing = release_info(tag)
    if existing and not existing['isDraft']:
        download_verified(tag, digest)
        return dict(status='already_published', tag=tag, url=existing['url'])
    if not existing:
        notes = bundle/'release-notes.md'
        team_note=(f"Campaign team `{manifest['campaign_team']['team_id']}` is included in manifest.json.\n\n"
                   if 'campaign_team' in manifest else '')
        notes.write_text(f"Schema-{manifest['schema']['version']} policy and Adam state `{manifest['policy_id']}`.\n\n"+team_note+
                         "Experimental training snapshot; the >=35% campaign objective is unmet. "
                         "Manifest metrics describe training, not an independent evaluation.\n\n"
                         "Verify SHA256SUMS and exact schema before import. Includes no game files, "
                         "user saves, logs or input DLL. Source tag identifies the checkout at capture; "
                         "the original training source revision is not known.\n", encoding='utf-8')
        gh('release', 'create', tag, '--draft', '--prerelease', '--latest=false',
           '--target', manifest['source_at_capture']['commit'], '--title', f'Checkpoint {manifest["policy_id"]}',
           '--notes-file', notes)
    gh('release', 'upload', tag, *(bundle/name for name in ASSETS), '--clobber')
    download_verified(tag, digest)  # Validate server bytes before making the draft public.
    gh('release', 'edit', tag, '--draft=false', '--prerelease', '--latest=false')
    published = release_info(tag)
    if not published or published['isDraft']: raise ValueError('Release publication was not confirmed')
    return dict(status='published', tag=tag, url=published['url'])
