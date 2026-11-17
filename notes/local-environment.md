# Existing local environment

This record supports a new agent on the user's computer. Do not reinstall a
working environment just because a session is new. The operator commands verify
the current state; this file records what was observed on 2026-11-17.

| Item | Verified location/version |
| --- | --- |
| Deployment | `D:\zar-scratch` |
| OS/interface | Windows, x64 native game/input DLL |
| Python | `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`, 3.14.4 |
| PyTorch | `2.15.0+cpu` |
| NumPy | `2.4.6` |
| psutil | `7.2.2` |
| pefile | `2024.8.26` |
| Pillow | `12.3.0` |
| Current model | `sessions/nn_policy3.pt` (+ `.previous` backup) |
| Current history | `analysis/nn_hist3.jsonl` |
| Input DLL | `scripts/hookdll/target/release/hookdll.dll` |
| Game copies | `game-copies/instN` (start with inst1) |
| Git/GitHub helper | `D:/github-agent/identity.mjs`, invoked with Node |

These are observed package versions, not a tested clean-install lockfile. No
new-machine installer or checkpoint download is provided. The current model,
owned game copies, DLL build output and runtime history are ignored artifacts;
they are available on this computer but not supplied by a clone. Old tracked
`nn_policy.pt`/`nn_policy2.pt` are incompatible with the current schema.

`local.ps1` explicitly selects the known interpreter, regardless of PATH. It runs
`scripts/local_agent.py`; that tool derives its own root and checks that the
trainer agrees before allowing training. The underlying live trainer still has
a fixed deployment path. Use the existing deployment; do not copy only scripts
elsewhere and assume they use that directory's checkpoints.

## If a check fails

- **Python/dependencies missing:** inspect the reported path and versions. Locate
  the existing environment first; do not change packages under active workers.
  Reconstructing a deleted environment needs a separate tested setup change.
- **Checkpoint missing/incompatible:** stop writers before recovery. Preserve the
  failed file, validate `.previous` using `inspect_checkpoint` from
  `scripts/local_agent.py`, then restore that validated backup explicitly. The
  helper never restores files automatically. Never replace it with legacy weights,
  `.tmp`, or random initialization to make a resume command succeed.
- **Game copy absent:** use an existing idle owned copy (`--copy instN`). Do not
  clone over a live copy. Preparation and copy settings are in `automation.md`;
  the installed game under `C:\Games` remains read-only.
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
$zarPython = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
& $zarPython -B -m unittest discover -s scripts -p test_local_agent.py
```

For other changes, use the relevant checks in AGENTS.md and existing tests. Do
not indiscriminately execute historical probe scripts or discover every script
as a test: some old probes are interactive/native diagnostics. Current model
semantics and remaining learning gaps are in `ml-spec.md`; previous evidence is
in `learning-audit.md` and `training-improvements.md`.
