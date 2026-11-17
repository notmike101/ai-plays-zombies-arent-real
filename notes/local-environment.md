# Existing local environment

The repository now has an isolated `.venv` created from `requirements.txt` and
validated on 2026-11-17. Do not reinstall a working environment just because a
session is new. The operator commands verify the current state.

## Create the Python environment

Install CPython3.14 x64 for Windows, then run from the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\local.ps1 check
```

No activation is necessary. A full path to Python3.14 can replace `py -3.14`.
Do not trust a bare `python` on PATH: on this machine it points to Inkscape.
The venv uses `include-system-site-packages=false`; required packages are installed
inside it. CPU-only PyTorch comes from its official CPU package index. Direct
dependencies are pinned; their transitive dependencies are resolved by pip, so
this is not a complete transitive lockfile. `.venv` is ignored, not distributed;
recreate it at the destination rather than copying/moving the interpreter folder.

Do not recreate/update an environment that active workers use. Normal launches
use the venv. Active trainer/environment paths derive from their source checkout;
there is no required D: drive or user-specific Python path. Windows x64 and the
verified native game build are still required. See tracker.md for live processes.

| Item | Verified location/version |
| --- | --- |
| Deployment | `D:\zar-scratch` |
| OS/interface | Windows, x64 native game/input DLL |
| Repository Python | `.venv\Scripts\python.exe`, CPython3.14.4 x64 |
| Original visualizer Python | `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe` |
| PyTorch | `2.15.0+cpu` |
| NumPy | `2.4.6` |
| psutil | `7.2.2` |
| pefile | `2024.8.26` |
| Pillow | `12.3.0` |
| Current model | `sessions/nn_policy3.pt` (+ `.previous` backup) |
| Current history | `analysis/nn_hist3.jsonl` |
| Input DLL | `scripts/hookdll/target/release/hookdll.dll` |
| Game copies | `game-copies/instN` (new clone: inst1; current full profile: inst12) |
| Git/GitHub helper | `D:/github-agent/identity.mjs`, invoked with Node |

These direct package versions were installed into a new isolated environment and
tested. No native-game installer is provided. Current checkpoints are published
as GitHub Release assets: see [sharing and restore](checkpoint-sharing.md).
The model, owned game copies, DLL build output and runtime history are ignored
artifacts. Old tracked `nn_policy.pt`/`nn_policy2.pt` are incompatible with the
current schema; do not use them as a fallback.

`local.ps1` explicitly selects `.venv\Scripts\python.exe`, regardless of PATH. It runs
`scripts/local_agent.py`; that tool derives its own root and checks that the
trainer agrees before allowing training. Copy `zar.example.toml` to ignored
`zar.local.toml`, set the read-only game asset source and GitHub App helper paths,
then run `local.ps1 build-input` and `local.ps1 prepare-game --copy instN`.
See the root README for order/prerequisites. Full availability is the default:
all unit/ability/upgrade unlocks plus Extra_Zones, without purchased items, SP
or campaign progress. Old copies with incomplete profiles fail preflight; select
a newly prepared copy explicitly rather than overwriting an existing one.

The installed EXE on this computer differs from the supported hash. Local config
therefore uses compatible `game-copies/inst4` as its read-only asset source.
Do not bypass build validation to accept another game version.

## If a check fails

- **Python/dependencies missing:** inspect the reported path and versions; use
  the setup commands above only when that environment has no active workers.
  If the installed base Python is removed, recreate the venv with a supported
  installed interpreter; a venv still depends on its base Python runtime.
- **Checkpoint missing/incompatible:** stop writers before recovery. Preserve the
  failed file, validate `.previous` using `inspect_checkpoint` from
  `scripts/local_agent.py`, then restore that validated backup explicitly. The
  helper never restores files automatically. Never replace it with legacy weights,
  `.tmp`, or random initialization to make a resume command succeed.
- **Game copy absent:** configure the source and run `local.ps1 prepare-game
  --copy instN` for a new name. Existing copies are never overwritten. The source
  and installed game under `C:\Games` remain read-only.
- **Wrong executable hash:** stop; memory offsets depend on the supported build.
  Do not remove the build check. Verified hash lives in `env_zar.BUILD_SHA256`.
- **DLL missing/invalid:** source and Cargo.lock are in `scripts/hookdll`;
  `automation.md` documents the build. Stop owned users before rebuilding a mapped
  DLL; never reinject into an already hooked game. Preflight checks x64/export
  structure; the actual boot validates live protocol/hooks separately.
- **Active trainer/busy copy:** preserve it and inspect its logs. A stale visualizer
  alone is not evidence of a hung trainer. Stop only identified owned processes.
- **Contribution helper unavailable:** report the missing local prerequisite.
  Do not silently substitute personal credentials or a different Git identity.

## Working on code

Use `node D:/github-agent/identity.mjs git ...` and `... gh ...`. Inspect status
before edits; preserve unrelated dirty files. Commit named files conventionally
and push at milestones. Keep runtime logs/checkpoints ignored. Never edit live
trainer modules while workers are using them; coordinate a stop/restart when a
trainer change is necessary. Documentation/operator-only changes can coexist with
the current run.

Focused operator regression checks (no live PIDs or game control):

```powershell
$zarPython = (Resolve-Path .venv\Scripts\python.exe).Path
& $zarPython -B -m unittest discover -s scripts -p test_local_agent.py
```

For other changes, use the relevant checks in AGENTS.md and existing tests. Do
not indiscriminately execute historical probe scripts or discover every script
as a test: some old probes are interactive/native diagnostics. Current model
semantics and remaining learning gaps are in `ml-spec.md`; previous evidence is
in `learning-audit.md` and `training-improvements.md`.
