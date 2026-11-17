# Zero-context operator runbook

Read `../AGENTS.md` first. This is the operating procedure; `tracker.md` CURRENT
STATE supplies the latest run/log identifiers. Historical tracker sections do
not describe current processes. Commands below use PowerShell on the existing
Windows deployment. Do not copy an old PID into a stop command.

## 1. Mission, boundaries and local state

The policy must learn to save >=35% of civilians on **every** Boston level at
normal difficulty. This is still an unmet objective. Let the model choose buys,
placement, loadout, deployment and casts. Do not script winning strategies,
change difficulty, use the admin console, or drive the real mouse.

Work in `D:\zar-scratch`; never write the installed game under `C:\Games`.
Owned copies are `game-copies\instN`. Never resize a running game. Keep one
training copy until the parallel injection failure is resolved. Preserve machine
headroom; eight logical CPUs and below-normal priority are the current starting
limits, not GPU/RAM caps. Check usage after launching and reduce/stop if needed.

The current implementation and reward explanation are in `ml-spec.md`.
`nn_play2.py` is the **schema-3** trainer (332 inputs, 72 tools, 48 cells/tool).
Do not launch the legacy `nn_play.py` or load `nn_policy2.pt` into schema 3.

Required local state (not supplied by a Git clone):

- `sessions/nn_policy3.pt`: saved policy, Adam optimizer and schema/learning metadata.
- `sessions/nn_policy3.pt.previous`: previous atomic checkpoint, when available.
- `analysis/nn_hist3.jsonl`: episode outcomes and completed PPO update records.
- Owned game copies, their settings/progress, and the installed Python environment.

Same-machine new sessions reuse these files. On another machine, transfer local
artifacts separately and configure the native environment; this is not a portable
installation guide. Never force-add ignored artifacts. Back up checkpoints while
training is stopped for a consistent transfer. Resume restores saved policy and
optimizer, **not** an in-flight episode, exact RNG state or recurrent memory.

## 2. Inspect before starting anything

```powershell
Set-Location D:\zar-scratch
$zarPython = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
Get-Content notes/tracker.md -TotalCount 55
@'
import pathlib, psutil
root = pathlib.Path('D:/zar-scratch')
for p in psutil.process_iter(['pid', 'exe', 'cmdline', 'create_time']):
    try:
        a = p.info
        exe, cmd = a['exe'] or '', ' '.join(a['cmdline'] or [])
        game = str(root / 'game-copies').lower() in exe.lower()
        python = 'python' in pathlib.Path(exe).name.lower()
        if game or (python and any(s in cmd for s in
                    ('train_run.py', 'nn_play2.py', 'server.py', 'demo.py'))):
            print(a, 'cwd=', p.cwd())
            print('children=', [(c.pid, c.create_time(), c.cmdline())
                                for c in p.children(recursive=True)])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
print('CPU %', psutil.cpu_percent(interval=1),
      'available GiB', round(psutil.virtual_memory().available / 2**30, 2))
'@ | & $zarPython -B -
Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
Get-Content analysis/nn_hist3.jsonl -Tail 4
```

Read the current log path from the actual launcher's command or tracker; inspect
its last 30 lines. `nvidia-smi` gives GPU utilization/VRAM on this machine.
Check drive space too (`Get-PSDrive D`). PIDs, creation times and executable paths
must agree with this checkout. A healthy existing run should be left running:
**never create competing trainers writing the same checkpoint/history**.

Progress means new episodes and `kind: update` history rows plus saved checkpoints,
not just a running process. Boot normally takes about 95 seconds. Planning, menus
and modal dialogs can pause simulation/dumps. Stale telemetry alone is not proof
of a hang. For errors, read `automation.md`, `learning-audit.md` and the actual
traceback before retrying; do not repeatedly launch new copies.
Judge results by `saved_frac`, `end`, `scenario` and `advance`: a planning timeout
has `saved_frac=null`. Its `observed_saved_frac`/legacy `frac` may be 1.0 because
the battle never started; that is not a 100% save or a win.

## 3. Resume training only when no trainer is active

First check dependencies and the **existing** checkpoint without modifying it:

```powershell
if (!(Test-Path -LiteralPath sessions/nn_policy3.pt)) {
    throw 'Resume checkpoint missing; recover it before training.'
}
@'
import torch, numpy, psutil, pefile, PIL
c = torch.load('sessions/nn_policy3.pt', map_location='cpu', weights_only=True)
assert c['schema']['version'] == 3 and len(c['schema']['inputs']) == 332
assert c['policy'] and c['optimizer']['state'], 'Missing learned policy/Adam state'
print('Saved run:', c['run_id'], 'learning:', c.get('learning'))
'@ | & $zarPython -B -
if ($LASTEXITCODE -ne 0) { throw 'Checkpoint/dependency preflight failed' }
```

The trainer also checks exact schema compatibility. Do not bypass a mismatch.
If the main checkpoint is corrupt, stop writers, preserve that file, validate
`.previous` with the same read-only check, then explicitly restore the validated
backup. Never promote `.tmp` blindly. If both are unavailable, report that resume
is impossible; a random policy would be a separate experiment.

Use a single idle owned copy. This bounded example runs six batches of two
episodes; increase rounds deliberately for an unattended run. Inspect the copy's
existing settings before boot: low graphics, normal difficulty, supported window
size (1920x1200 or 3840x2160). Never edit the install or a live window.

```powershell
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$trainArgs = @('-B','D:\zar-scratch\scripts\train_run.py',
    '--copies','inst1','--eps','2','--rounds','6','--start','fresh',
    '--model','D:\zar-scratch\sessions\nn_policy3.pt',
    '--history','D:\zar-scratch\analysis\nn_hist3.jsonl',
    '--seed','20261140','--log',"D:\zar-scratch\analysis\nn3_$stamp.log")
$launcher = Start-Process -FilePath $zarPython -ArgumentList $trainArgs `
    -WorkingDirectory D:\zar-scratch -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "D:\zar-scratch\analysis\nn3_${stamp}_launcher.log" `
    -RedirectStandardError "D:\zar-scratch\analysis\nn3_${stamp}_launcher.err"
$launcher.PriorityClass = 'BelowNormal'
$launcher.ProcessorAffinity = [IntPtr]255  # CPUs 0-7 on this 24-logical-CPU machine
$launcher.Id
```

`--start fresh` starts a fresh L1 **board** while loading the existing model and
optimizer. It does not mean random weights. Do not pass `--random` for resume.
`--start continue` selects saved campaign progress and is not a checkpoint-resume
switch. The launcher owns/cleans games started with `--copies`; `--pids` borrows
already-planning games and does not clean them. Prefer `--copies` for normal use.

Re-run the inventory to verify inherited priority/affinity and new game/trainer
PIDs. Record launch time, seed, log paths and identities in tracker before leaving
the run. Check the first completed batch, checkpoint and resource usage. A healthy
process/first update does not prove strong play or all five levels are mastered.

## 4. Start or reuse the visualizer independently

If port 8765 already has a listener, match its PID/command/cwd to this checkout's
`visualizer/server.py`. Reuse it. An unrelated listener is a port conflict, not
permission to kill it. The visualizer is read-only; starting/stopping it does not
start/stop training or change checkpoints.

Foreground (Ctrl+C in that terminal stops server and its optional preview):

```powershell
.\visualizer\start.ps1
```

Background, only when no server owns the port:

```powershell
$server = Start-Process -FilePath $zarPython -WindowStyle Hidden -PassThru `
    -WorkingDirectory D:\zar-scratch `
    -ArgumentList @('-B','D:\zar-scratch\visualizer\server.py','--host','0.0.0.0','--port','8765')
$server.Id
```

Open `http://localhost:8765`. Default binding permits LAN access under existing
firewall rules; telemetry has no authentication. No firewall change is needed.
To test lifecycle separately, use `--host 127.0.0.1 --port 8766` after checking
that port is unused. For an intentionally synthetic preview, use `start.ps1
-Preview`; never present preview activity as live-model evidence.

Health check (wait briefly for startup, then run):

```powershell
$view = Invoke-RestMethod http://127.0.0.1:8765/api/state
$view | Select-Object status,age
$view.frame | Select-Object worker_pid,game_pid,phase,sequence,preview,model_revision
```

A connected waiting/stale display can be normal between decisions. A fresh real
frame must have `preview=false`, matching worker/game PIDs, 332 input labels and
no `label_warning`. See `../visualizer/README.md` for display semantics. The UI's
Pause freezes the display only. Restarting a server clears its sampled history;
it reconnects to existing worker files without a trainer restart. Server health
alone does not prove current live attachment or successful game actions.

## 5. Stop precisely; do not kill by process name

Let a bounded training run finish when possible. There is currently no cooperative
"stop after this batch" command. Forced stop loses the unfinished batch; the last
atomically saved checkpoint remains the resume point. Killing only the launcher
can leave the trainer/worker/game running.

For a background visualizer, target the verified **server** PID. For training,
target the verified **nn_play2.py trainer** PID, not the launcher. First repeat
the inventory and copy that process's PID and creation time into this block.
Choose the matching expected script. The placeholders intentionally fail until
replaced; do not use a historical tracker PID. This is a destructive stop command,
not a health check:

```powershell
@'
import os, pathlib, psutil
target_pid = 0                 # Replace with CURRENT server or trainer PID
created = 0.0                  # Replace with its CURRENT create_time
expected = pathlib.Path('D:/zar-scratch/visualizer/server.py')
# For training instead: expected = pathlib.Path('D:/zar-scratch/scripts/nn_play2.py')
p = psutil.Process(target_pid)
assert abs(p.create_time() - created) < .01, 'PID identity changed'
assert any(pathlib.Path(a).resolve() == expected.resolve() for a in p.cmdline()[1:]
           if a.endswith('.py')), 'Wrong script'
children = p.children(recursive=True)
allowed = {pathlib.Path(p.exe()).resolve(),
           (pathlib.Path(os.environ['SystemRoot']) / 'System32/conhost.exe').resolve()}
assert all(pathlib.Path(c.exe()).resolve() in allowed for c in children), \
    'Unexpected child; inspect manually'
p.kill()                       # Stop parent first so it cannot create more workers
for c in children:
    try:
        c.kill()               # Captured psutil objects guard against PID reuse
    except psutil.NoSuchProcess:
        pass
_, alive = psutil.wait_procs([p, *children], timeout=15)
assert not alive, [c.pid for c in alive]
'@ | & $zarPython -B -
if ($LASTEXITCODE -ne 0) { throw 'Stop failed; inspect before further action' }
```

For training, allow the launcher to observe trainer exit and clean its owned
games. Repeat the inventory to verify launcher, workers and owned game actually
exited. If cleanup failed or the launcher was already gone, match each residual
game by **exe directory**, PID and creation time, then stop only that owned copy.
Do not kill an unrelated game or another owner's worker. Borrowed `--pids` games
require explicit cleanup by their owner. If any process is unidentifiable, report
the ambiguity rather than guessing. Never use `Stop-Process -Name python`.

Captured children can include Windows' console host and Python workers/preview.
For the visualizer, force stopping just the server can orphan its optional
synthetic preview. Verify its listener and preview
are gone. Training should remain unchanged. Do not delete runtime files to stop
processes; abruptly orphaned telemetry ages out on its own.

## 6. Evidence, maintenance and next-session prompt

After work, replace CURRENT STATE in tracker with dated observed state, run IDs,
PIDs/creation times, checkpoint/update evidence, resource samples, remaining
uncertainties and next steps. Stop temporary test instances; preserve intended
training. Commit only your changes through the identity helper, with Conventional
Commits; push at milestones. Do not include ignored checkpoints/logs or unrelated
pre-existing dirty files.

Use `node D:/github-agent/identity.mjs git ...` for **all** Git commands and the
same helper with `gh` for GitHub. For example, after staging only your named files:
`node D:/github-agent/identity.mjs git commit -m "docs: update operator handoff"`,
then `node D:/github-agent/identity.mjs git push`. The helper supplies contribution
identity; do not bypass it with personal credentials or amend unrelated history.

For model/feature/telemetry changes, run the checks required by AGENTS.md. Tests,
live validation and remaining learning gaps are recorded in `learning-audit.md`
and `training-improvements.md`. Do not change live trainer source for operational
documentation or visualizer maintenance. No dependency reinstall is needed on
the existing working machine.

Suggested prompt for a new agent:

> Work in D:\zar-scratch. Read AGENTS.md, notes/operator-runbook.md and only the
> CURRENT STATE of notes/tracker.md first, then notes/ml-spec.md. Verify actual
> process identities and checkpoint availability. Preserve a healthy existing
> training run; otherwise resume schema-3 weights/Adam with one owned copy and
> resource headroom. Reuse or start the read-only visualizer on port 8765. Never
> start random training because a checkpoint is missing, script strategy, or
> touch the installed game/real mouse. Verify a completed update and fresh live
> telemetry, update tracker, and commit your documentation changes. Report limits
> honestly; the >=35% goal is not yet achieved.
