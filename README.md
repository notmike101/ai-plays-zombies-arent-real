# AI plays Zombies Aren't Real

Train a GRU policy to save at least 35% of civilians consistently on every Boston
level at normal difficulty. The model chooses all strategy; automation supplies
observations and executes its actions. This objective has **not** been achieved.

## Starting with no context

Read [AGENTS.md](AGENTS.md), then run these from PowerShell in this checkout:

```powershell
.\local.ps1 status
.\local.ps1 check
.\local.ps1 visualizer-start
```

`status` reports actual process identities and recent outcomes. Preserve an active
training run. `check` verifies dependencies, the current checkpoint/Adam state,
game build and input DLL without attaching to the game. `visualizer-start` reuses
this checkout's existing server or starts one; open http://localhost:8765.

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
are `sessions/nn_policy3.pt`; the filename `nn_play2.py` does not mean schema 2.
The read-only [visualizer](visualizer/README.md) normally uses port 8765.

**A Git clone alone cannot resume this model.** Current weights, their backup,
training history and owned game copies are local, ignored runtime artifacts.
Do not silently start from random weights when a resume checkpoint is missing.
