# AI plays Zombies Aren't Real

Train a GRU policy to save at least 35% of civilians consistently on every Boston
level at normal difficulty. The model chooses all strategy; automation supplies
observations and executes its actions. This objective has **not** been achieved.

## Starting with no context

1. Read [AGENTS.md](AGENTS.md) for mandatory operating rules.
2. Follow the [operator runbook](notes/operator-runbook.md) to inspect, resume or
   stop training and start/stop the visualizer.
3. Read **CURRENT STATE** in [the tracker](notes/tracker.md); verify processes
   again before acting. Older snapshots are historical.
4. Read [the model contract](notes/ml-spec.md) for observations, actions, rewards
   and known learning limitations.

The working deployment is `D:\zar-scratch` on Windows. The current trainer is
`scripts/nn_play2.py`, launched through `scripts/train_run.py`. Current weights
are `sessions/nn_policy3.pt`; the filename `nn_play2.py` does not mean schema 2.
The read-only [visualizer](visualizer/README.md) normally uses port 8765.

**A Git clone alone cannot resume this model.** Current weights, their backup,
training history and owned game copies are local, ignored runtime artifacts.
Do not silently start from random weights when a resume checkpoint is missing.
