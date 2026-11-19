# Zero-context operator runbook

Read `../AGENTS.md` first. This guide operates a Windows checkout (this deployment
is `D:\zar-scratch`). CURRENT STATE in `tracker.md` is a dated handoff; always inspect
actual processes. `local-environment.md` records dependencies and recovery steps.
Both launchers now default to `.venv\Scripts\python.exe`; follow README.md for
first-time setup. Existing workers retain their original interpreter until their
next normal restart. Never recreate/update an environment while it has workers.
For a new checkout, configure zar.local.toml, run build-input and prepare-game,
then import a verified checkpoint as described in README.md. Fresh copies use
full availability as requested: unlocked options, but no purchases or placements.
The policy may persist any valid seven-slot planning roster; preflight accepts
known units and empty slots rather than requiring the original starting kit.
For sharing/restore use notes/checkpoint-sharing.md; the six-hour local automation
publishes changed snapshots only and never restarts training.

## 1. Inspect and check

```powershell
Set-Location D:\zar-scratch
.\local.ps1 status
.\local.ps1 check
```

`status` reports this checkout's launchers/trainers/games/visualizer, PID creation
times, commands, CPU affinity/priority, available RAM/disk and recent history.
It reports the owner of port8765 even if that owner is foreign. It does not attach
to a game or send input. `check` loads a CPU copy of the checkpoint for exact
schema, weight and optimizer validation, checks dependencies, hashes inst1's game
executable, and inspects the DLL. It never changes the checkpoint or games.
Use `check --copy instN` for another existing copy.
On this deployment, use `check --copy inst14` and `train --copy inst14` for the
new full-availability copy. The legacy inst1 profile lacks upgrades and now fails
preflight deliberately. A fresh clone's prepared inst1 has the complete profile.

If `training_active=true`, inspect the log from its actual command or tracker and
preserve healthy training. New history rows with `kind=update` establish saved
PPO updates; a running process alone does not. Judge outcomes by `saved_frac`,
`end`, `scenario` and `advance`. Planning timeouts have `saved_frac=null`; their
observed/legacy fraction may be1.0 because the battle never started, not a win.

Boot normally takes about95 seconds. Planning/dialogs can pause simulation and
dumps. Stale telemetry alone is not a hang. Read the actual traceback and
`automation.md` before retrying errors. Do not launch competing copies blindly.

## 2. Resume only when idle

```powershell
.\local.ps1 train --rounds 6
```

Defaults: inst1, two episodes per batch, seed20261140, six batches, fresh L1 board,
existing schema4 policy **and Adam state**, hidden background execution. Change
the duration deliberately (for example `--rounds 200`); `--copy instN` and `--seed`
are supported. `--foreground` stays attached to the terminal. Neither mode
silently creates a random policy. Run `local.ps1 --help` for all options.

The command preflights, refuses existing training or a busy copy, and takes an
OS-released lock while the foreground operator owns its run. It applies
below-normal priority and at most8 CPUs (at most half the initially available
logical CPUs) **before** launching the existing `train_run.py`. It refuses startup
below4GiB available RAM or2GiB free disk. These are startup safeguards, not
continuous CPU/GPU/RAM quotas. Repeat --extra-copy instN for up to eight distinct
prepared copies. They share the CPU cap and one optimizer. Startup requires
4, 6, 8 or 10 GiB available RAM for one through four copies, and 12 GiB for
five through eight copies.
With --episodes-per-copy 1, each copy supplies one episode per update. Updates
still wait for the slowest copy. The defaults are one copy and two sequential
episodes per copy.

The immediate result says `starting` and gives the background operator's PID/log.
That is a spawn acknowledgement, not boot success. Read that log; it prints the
underlying trainer command and training-log path. Run `status` again to confirm
launchers, game, trainer and inherited CPU/priority. Verify the first completed
batch and resource headroom (`nvidia-smi` for GPU, Task Manager if needed).
Record identities, log paths and evidence in tracker before leaving a long run.

Resume restores the last saved policy/optimizer, not an unfinished battle, exact
RNG state or recurrent memory. Fresh L1 refers to the **board**, not the weights.
The launcher owns and cleans its `--copies` games on exit. Lower-level `--pids`
borrows games and does not clean them; it is not the normal operating path.

## 3. Start/reuse the visualizer

```powershell
.\local.ps1 visualizer-start
```

Open `http://localhost:8765`. The command reuses a matching server from this
checkout, starts a hidden server if absent, and refuses a foreign port owner.
Reused means the process/listener was identified; verify HTTP/live data separately.
The server normally binds0.0.0.0 (LAN-accessible under existing firewall rules,
without authentication). For a separate test use an unused port and loopback:

```powershell
.\local.ps1 visualizer-start --port 8766 --host 127.0.0.1
```

The command reports its PID/create_time. A custom-port server also appears in
`status`'s process list. Server logs are ignored `analysis/nn3_visualizer_PORT.log`.
On Windows, a venv redirector and its actual Python child can both appear; this
does not necessarily mean two servers. The start result identifies the listener.
These commands never start a synthetic preview or change training. The separate
`visualizer/start.ps1 -Preview` remains available for explicitly synthetic UI
tests; see `../visualizer/README.md`. Foreground Ctrl+C closes that server/preview.

```powershell
$view = Invoke-RestMethod http://127.0.0.1:8765/api/state
$view | Select-Object status,age
$view.frame | Select-Object worker_pid,game_pid,phase,sequence,preview,model_revision
```

A fresh real frame has `preview=false`, the actual worker/game PIDs,4889 input
labels and no `label_warning`. The worker PID must belong to the trainer's child
process tree (inspect with psutil if needed). Pausing the UI pauses only the view.
Restarting the server clears sampled history, then reconnects to worker files;
no trainer restart is needed. HTTP health is not proof of executed game actions.

## 4. Stop an identified process

Let bounded training finish when possible. There is no cooperative "stop after
this batch" command. A forced stop loses unfinished batch data; the last atomic
checkpoint remains the resume point. Never stop only the background operator or
launcher: its children could continue running.

Run `status` immediately before stopping. Use the actual **trainer** identity for
training, or **visualizer** identity for its server. Substitute the PID and full
create_time in these examples; do not use historical tracker values:

```powershell
.\local.ps1 train-stop --pid TRAINER_PID --created CREATE_TIME
.\local.ps1 visualizer-stop --pid SERVER_PID --created CREATE_TIME
```

The placeholders deliberately fail until replaced. Stop verifies creation time,
script path and checkout, validates descendants, then stops only the identified
process and captured Python/console-host children. Unknown children or changed
identity cause refusal. Never use a process-name wildcard such as "kill python".

After `train-stop`, allow the existing launcher to clean its owned game, then
run `status` to confirm trainer/workers/launcher/game exited. The stop command's
success confirms its targeted process tree, not launcher/game cleanup. If the
launcher had already disappeared or cleanup fails, enumerate residual games by
exact exe directory and creation time; stop only the verified owned copy. Report
ambiguity instead of guessing. Borrowed games belong to their original owner.

After `visualizer-stop`, verify the listener and any owned preview are gone;
training should continue unchanged. Do not delete runtime files to stop processes.

## 5. Exit codes and failures

Checks/status and action results print JSON; foreground training also streams
launcher output. Exit0 means the requested check/action succeeded; `starting`
still needs later verification. Exit1 means a failed check/action with an error;
exit2 means invalid arguments. Never ignore a nonzero exit and assume success.
Preflight reports individual failures. Recovery guidance is in
`local-environment.md`; the tool does not download, reinstall or restore anything.
The duplicate-training guard also detects older direct launchers on this checkout.
Its lock coordinates operator commands; bypassing the wrapper forfeits that lock.

## 6. Mission and handoff

Save >=35% civilians on every Boston level consistently, at normal difficulty.
The model owns strategy. Never script buys/placement/casts, use the admin console,
touch the real mouse, modify the installed game, or resize a live window. The
objective is unmet. Read `ml-spec.md` before changing observations/actions/rewards.

After work, update CURRENT STATE in tracker with dated evidence, identities, log
paths, completed updates, resource samples, uncertainties and next steps. Stop
temporary test instances while preserving intended training. Commit only your
named changes with Conventional Commits through
`node D:/github-agent/identity.mjs git ...`; push milestones. Preserve unrelated
dirty files and ignored artifacts. Read `local-environment.md` for safe test
commands; AGENTS.md has the required model/visualizer maintenance checks.

Minimal prompt for a new agent:

> Work in D:\zar-scratch. Read AGENTS.md and follow notes/operator-runbook.md.
> Train the existing model with resource headroom, preserve a healthy active run,
> keep the visualizer available, and improve the repository with tested changes.
> Update the tracker and commit milestones. Never silently start random training.

### Comparing spatial targeting on live games

When training is idle, run
`.venv/Scripts/python.exe -B scripts/compare_spatial.py --copies inst13 inst14 inst15 inst16`
from the checkout. Choose distinct prepared copies in pairs. The command checks
both training ownership and hardware headroom. Each pair shares a policy seed
on fresh normal Boston L1 boards. By default one training round precedes two
fixed-weight evaluation rounds. Use `--train-rounds 8 --eval-rounds 4` for
eight optimizer updates followed by four evaluations per copy. Copies alternate
arms every round. The evaluation round count must be even for balanced exposure.
Both arms start from the production GRU and tool/value heads with fresh Adam
state. The candidate initializes a new cell scorer. Native game randomness
can vary between copies. Trial weights and episode records go in an ignored
`analysis/coverage-spatial-*` directory. The production checkpoint resumes
through the usual operator. The visualizer receives no frames from either trial arm.

If an interface failure interrupts a longer comparison, inspect its log and
resolve the failure. The harness retries a matched pair once for UI-frame or
stale-HUD timeouts. Each completed update atomically saves both policies and
both Adam states in `paired.pt`. Repeat the original command with
`--resume analysis/<trial-directory>/paired.pt` and identical trial arguments.
The new directory starts at the next training round. A resume during evaluation
starts the frozen evaluation block again. Use one complete evaluation block.

### Searching for complementary planning and battle policies

With idle full-availability copies, run
`.venv/Scripts/python.exe -B scripts/team_search.py --copies inst13 inst14 inst15 inst16 inst17 inst18 inst19 inst20 --generations 5`.
The search trains planning sequences and battle target scores by selection on
live outcomes. The frozen GRU supplies action preferences to both phases. One
unmodified greedy GRU runs per generation as a control. The policy still uses
the native action masks, normal difficulty, early retry and 35% curriculum gate.
Candidates earn priority for qualifying clears, then game wins and actual
winning score. For failed candidates, the tie-breaker integrates surviving
civilians over the first 120 simulated seconds, assigning zero after early
retry. It is a search heuristic. The final evaluation uses new boards with
paired policy seeds. The game controls its own randomness.

The command holds the operator lock and writes its base weights, tested
genomes, action sequences, native log identifiers, champion and held-out
results to an ignored `analysis/coverage-team-*` directory. Search runs
disable the GRU-only visualizer for both candidates and controls.
Use `--seed-from analysis/<previous-search-directory>` with a new seed to
retain the previous champion and verify its base weights. An optional
`--demonstration <Boston progress file>` supplies locally recorded stage-one
layout coordinates as candidate examples. The planner projects them through
the current camera and issues normal player actions. It records budget receipts.
Game progress files list best badges separately from layouts.

To test crowd prediction, run `scripts/collect_crowds.py --minutes 35` with
the repository Python while owned games are in battle. This observer uses
query/read handles only. Train `scripts/crowd_forecast.py <capture-directory>`
after collecting several games. It estimates civilian and zombie cell counts
two simulation seconds ahead and compares against current counts on entire
held-out games. Use the normal team search command with paired copies,
`--seed-from <champion-directory> --compare-forecast <capture-directory>/forecast.pt`
to compare current versus forecast counts on fresh games. Both arms use the
same champion with one shared, seeded loadout purchase proposal. The game
still masks illegal purchases. The exact candidate is in comparison-team.json.
Read each stage's battle_actions for cast availability, selections and stock
decreases. New runs also retain the game's `logged_deployments` from this
episode. A missing footer makes this field unknown. A game with zero casts
provides no test of targeting. Report
forecast error and actual civilian saves separately.

Later-stage candidates project the recorded layout through the current
stage's camera and map origin, skip structures already carried, and issue
purchases through the normal roster. Search can take up to two additional
normal retries after a later-stage loss or below-target win. Set
`--later-retries 0` for a single-attempt search. Held-out games always use
one attempt per stage. Inspect `attempt` and `start_kind` in the stage record.
Search offspring can reorder, translate, omit or add a nearby copy of a
placement. Translation uses world coordinates and moves a polygon's corners
together. Only actual in-game outcomes determine whether an offspring survives.
Battle search can vary the four pan directions and can learn different pause
preferences while running and while paused. Older champions retain their
original camera and pause behavior.
