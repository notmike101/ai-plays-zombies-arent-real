# AI plays Zombies Aren't Real

Training and evaluation default to Boston Level 1. Campaign progression requires the explicit `--allow-progression` flag.

Train a GRU policy to save at least 35% of civilians consistently on every Boston
level at normal difficulty. The model chooses all strategy; automation supplies
observations and executes its actions. This objective has **not** been achieved.

Campaign search also trains preparation and battle specialists alongside the
GRU. Once the game copies and weights pass preflight, a release that includes
a campaign team can resume the search directly. With four idle owned copies
and a verified release downloaded to `sessions/download`, run:

```powershell
.\.venv\Scripts\python.exe -B scripts/team_search.py --copies inst13 inst14 inst15 inst16 --seed-from sessions/download --generations 4
```

Use the names of the copies you prepared. The console prints the experiment
directory. Use that directory with `--seed-from` for the following run and
`scripts/nn_report.py --search-dir <directory>` for scores.
See [checkpoint sharing](notes/checkpoint-sharing.md) and the
[operator runbook](notes/operator-runbook.md).

## Starting with no context

First-time Python setup uses **CPython 3.14 x64 on Windows**. Skip creation if this
checkout already has a working `.venv`; do not reinstall packages under running
workers. From the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

The [requirements](requirements.txt) pin the five direct dependencies, including
CPU-only PyTorch. Both launchers use `.venv` explicitly, so activation is optional
and unrelated Python installations on PATH are ignored. The environment directory
is gitignored; recreate it from these commands after moving/cloning the repository.
If `py` is unavailable, use the full path to an installed Python 3.14 x64 executable
for the first command. The environment does not install the game or recover weights.

Read [AGENTS.md](AGENTS.md), then run these from PowerShell in this checkout:

For a **new checkout**, also copy `zar.example.toml` to ignored `zar.local.toml`
and set `[game].install_dir` to your supported read-only game source. It can be
an installed game or an existing compatible owned copy. Configure the sharing
repository and identity-helper path if you will publish checkpoints. Then:

```powershell
.\local.ps1 build-input
.\local.ps1 prepare-game --copy inst1
```

The DLL build requires Rustup and MSVC C++/Windows SDK tools; see
[the source-only build guide](scripts/hookdll/README.md). Never rebuild with owned
games running. Copy preparation refuses existing destinations and unsupported
executable hashes. It copies assets, creates normal/low-graphics settings, opts
out of usage sharing, and enables the **full training unlock profile** by default:
16 units,19 abilities,16 upgrades and all8 perks (59 entries) in this supported build. It does
not copy campaign progress, buy levels, spend SP or pre-place defenses. The model
still controls strategy. See the [mechanics coverage ledger](notes/mechanics-coverage.md)
for the native controls, observations, receipts and disabled-build exceptions.

Download and import a compatible checkpoint using
[checkpoint sharing/restore](notes/checkpoint-sharing.md). The active trainer now
derives paths from its checkout; `D:\zar-scratch` is this deployment, not a required
directory on another machine. On this machine the installed game hash differs
from the supported build, so local config uses compatible `game-copies/inst4` as
the read-only source. Never bypass the build check for a different game version.

Once prerequisites exist:

```powershell
.\local.ps1 status
.\local.ps1 check
.\local.ps1 visualizer-start
```

`status` reports actual process identities and recent outcomes. Preserve an active
training run. `check` verifies dependencies, the current checkpoint/Adam state,
game build and input DLL without attaching to the game. `visualizer-start` reuses
this checkout's existing server or starts one; open http://localhost:8765.
The default copy is inst1; use `--copy instN` on check/train when the tracker names
another deployment copy. Existing copies are not silently rewritten to add unlocks.

**Only when no trainer is active and `check` passes**, resume in the background:

```powershell
.\local.ps1 train --rounds 6
```

This runs six batches of two episodes using one owned copy, existing weights and
optimizer, below-normal priority, and at most eight logical CPUs. `starting` is
not proof of successful training: inspect the returned log and a completed update.
There is no silent random-policy fallback. Run the commands with `--help` for
options; see the [operator runbook](notes/operator-runbook.md) for stopping,
verification and recovery.

Read **CURRENT STATE** in [the tracker](notes/tracker.md) as a dated handoff,
then [the model contract](notes/ml-spec.md) before changing training behavior.
The [local environment record](notes/local-environment.md) lists the interpreter,
dependencies, artifacts and contribution tools on this computer.

The working deployment is `D:\zar-scratch` on Windows. The current trainer is
`scripts/nn_play2.py`, launched through `scripts/train_run.py`. Current weights
are `sessions/nn_policy4.pt`; the filename `nn_play2.py` does not mean schema 2.
The read-only [visualizer](visualizer/README.md) normally uses port 8765.

**A Git clone alone cannot resume this model.** Current weights, their backup,
training history and owned game copies are local, ignored runtime artifacts.
Current model snapshots are available through GitHub Releases every six hours
when changed. Do not silently start random training when a checkpoint is missing.
