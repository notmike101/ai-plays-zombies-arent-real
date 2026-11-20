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
The shared affinity budget starts at eight logical CPUs, grows by two per
copy above four, and uses at most half the host's logical CPUs. On this
machine six copies share twelve logical CPUs at below-normal priority.
The continuous local L1 supervisor prefers six copies at 12.5 GiB available RAM
and attempts eight at 16 GiB. Below the six-copy floor it falls back to four
at 10.5 GiB available RAM. All three modes require 3 GiB free disk.
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
live outcomes. The frozen GRU supplies action preferences to both phases. A greedy GRU runs in the first generation. Rank candidates using fresh,
uninterrupted campaign attempts. Pool identical stage policy prefixes across
later-stage variants and deduplicate native outbreak seeds. Search favors
consecutive stages with at least two qualifying outbreaks, then the Wilson
lower score for qualifying rate, then the mean saved fraction. An incomplete
attempt contributes zero to this search mean. Technical failures without a
trajectory are reported separately. The score guides search and does not
establish generalization.

Each generation reserves fresh slots for repeat evaluation and L1 variation.
For adaptive refuges, one proposal varies size alone while holding battle
behavior fixed. A resumed block inherits the prior fitness ledger, incumbent,
and provisional leader. Finals evaluate a frozen challenger against the
starting incumbent (greedy GRU on cold start). Copies have paired policy seeds
and independently drawn native outbreaks. Promotion requires two qualifying
training outbreaks and, on equally sized fresh evaluation arms, at least two
qualifying outbreaks, more qualifying wins and greater total saved at the first
stage where policies differ. Earlier failures score zero at that stage.
Keep the incumbent when evidence is insufficient. On cold start a block may
produce only a provisional leader. Blocks with at least six copies dedicate a slot to promising distinct L1
prefixes with fewer than four measured starts. Promotion-eligible challengers
receive at least six held-out games per arm with assignments rotated between
copies. Held-out outcomes gate promotion and never enter search fitness. A new holdout is needed for any later performance claim.

Pass `--continue-layout-free <search-directory>` to seed a new Boston L1
discovery block with a verified provisional proposal and its frozen GRU.
One variant shifts a single spatial preference by one grid cell while keeping
the rest of the proposal fixed. The normal promotion gate still applies.
Pass `--holdout-copies inst17 inst18 inst19 inst20` to reserve an even set of
owned copies separate from `--copies`. Preserve `fitness.json`, `trials.jsonl`
and `holdout.jsonl` when resuming. The fitness ledger carries the known
outbreak seeds forward, and holdout rows flag overlap with earlier exposure.
Promotion requires zero overlap and valid saved fractions for both arms.

**Default scope is L1.** A qualifying win counts and completes the copy's L1
assignment. Campaign search, standalone PPO and the operator launcher require
`--allow-progression` to enter L2–L5. With explicit authorization, append the
flag to `team_search.py` or use `.\local.ps1 train --allow-progression`.
`train_run.py --start continue` also requires this flag. The ordinary continuous
supervisor runs L1 by default.

In opted-in campaigns, when a copy reached a later stage during the preceding generation,
some candidates can practice there via the game's CONTINUE menu. The trainer
verifies the live stage before acting and records `start_stage` and
`start_kind=continue`. More than half of each generation starts fresh.
Practice scores can nominate a specialist for a fresh campaign trial. They
never enter campaign rankings or held-out results.

Campaign discovery and frozen evaluation truncate an episode after 45 wall
seconds continuously paused. Resuming resets the timer. The model keeps
control of the pause key. Ordinary PPO retains its existing battle deadline.
A timeout records an incomplete outcome and its `timeout_reason`.

The command holds the operator lock and writes its base weights, tested
genomes, action sequences, native log identifiers, champion and held-out
results to an ignored `analysis/coverage-team-*` directory. One candidate
worker per training generation publishes its decisions to the normal live
visualizer. Look for `search/<seed>/L<stage>/a<attempt>`. Layout construction
precedes the first sampled decision. The held-out and CNN comparisons run
without the observer.
A scoped auxiliary L1 test can save fresh search trials under
`extra-trials.jsonl` in the parent search directory. Use the same frozen base
and view revision, distinct idle owned copies and reserved CPUs. The next
search block imports completed supplemental trials alongside ordinary trials.
Keep formal holdout results in the separate holdout file.

Run `.venv/Scripts/python.exe -B scripts/nn_report.py --search-dir analysis/<search-directory>`
to count official game wins, qualifying wins, incomplete attempts and errors
by team, stage, starting board and experiment. This also works during a run.
Workers append results as they finish. A long campaign on one copy does not
delay reporting completed trials from the others.
If a later board fails to initialize or loses observation, previously confirmed
stage outcomes remain in its trial. The failed attempt gets an error and no
saved percentage. Older records may lack the attempted stage.
An unconfirmed game exit appears as `cleanup_error` and preserves completed
scores. Verify the process with `local.ps1 status`; a busy copy refuses a
new boot. Native snapshot errors report tick races or mismatched array lengths.
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

At an idle, coordinated launch boundary, add
`--compare-speed --generations 4` to team search with a saved champion and
4–8 preflighted copies. Waves run 1×, 2×, 2×, 1× with the same copies, frozen
champion and paired policy seeds. The game still chooses outbreak seeds.
Both arms mask policy speed controls and check native battle speed. Results
go to `speed-comparison.jsonl` without promoting any teams. Compare fresh
scored trials per wall hour, qualifying wins, timeouts and confirmed spends.
Use the spread of worker finish times within each wave to estimate the time
lost waiting for other copies.

Add `--capture-shadow` to a bounded search or speed experiment to record
camera-tagged crowd grids and confirmed stock spends under the native
session header. Keep these files local. The cell identifies the policy's
selection. Check camera alignment and corroborate spends with native
deployment events before attributing outcomes. Preserve held-out outbreak
sessions and include opportunities where legal casts were available and the
model waited. Treat the data as observational.

Later-stage candidates project the recorded layout through the current
stage's camera and map origin, skip structures already carried, and issue
purchases through the normal roster. Each stage's `unmatched_layout` lists
proposed coordinates absent from the game's post-placement board dump.
Structures match one-to-one within two world units on each axis. Inspect
both this list and the budget receipts when diagnosing missing defenses.
Layout purchases prefer empty roster slots. If a picker rejects a slot and
the native roster confirms nothing changed, the planner tries another free
slot and records the rejection. It preserves occupied defense types.
If a receipt shows an overdraft, new candidates share the lowest observed
price for that exact stage, type and geometry. The original elite keeps its
tested policy. When funds fall below a candidate's estimate,
the child ends its recorded layout at the preceding action. The original
candidate remains eligible for comparison. Fresh campaign play determines
whether the revised plan works.
Preparation candidates can learn which legal recovery action to prefer when
READY is blocked. The game receives only the action chosen by the current
policy. A verified later-stage planning timeout also allows CONTINUE practice
on that copy, with its existing board and balance.
Search can take up to two additional normal retries after a below-target
L1 win, or a later-stage loss or below-target win. Reusing a successful
preparation gives later-stage policies more training opportunities. Rankings
favor first-attempt qualifications among teams reaching the same depth. Set
`--stage-retries 0` for a single-attempt search. Held-out games always use
one attempt per stage. Inspect `attempt` and `start_kind` in the stage record.
Search offspring can reorder, translate, omit or add a nearby copy of a
placement. It can also move one type to the front of the purchase order or
reduce its count to free budget for other placements. Polygons can translate
or change size around their center. The post-game `outbreak` receipt records
the native outbreak seed, zone count and percentage sheltered at READY. This
percentage is a diagnostic. Actual game outcomes drive selection.
One fresh candidate also fits a refuge to the current planning board. It
samples at most 2,048 visible-to-the-policy civilian positions across the
map and compares translated polygons and rectangles against the population
and planned defenses. Scale, aspect ratio and defense weight evolve. The
stage record's `refuge` contains its predicted coverage and coordinates;
compare those against the game-reported outbreak and saved percentages.
Battle search can vary the four pan directions and can learn different pause
preferences while running and while paused. Older champions retain their
original camera and pause behavior.

Parallel entity observations read the nine native array headers together,
then the payloads, and require equal lengths and a matching simulation tick.
Repeated consistency failures briefly yield to the next game update; a
persistent failure is an incomplete trial. The other world systems are
sampled independently.

### Playable target boundary

The trainer checks cast, placement and world-action targets against the projected
native playable polygon before issuing input. An outside target is rejected and
costs .02 in PPO reward. Logs include `outside_playarea_actions` and the separate
reward component. Campaign search rejects outside layout points and deducts the
same cost from its ranking objective, converted to saved-fraction units. Official
saved percentages and qualifying wins come from the game footer.

### Camera and stage isolation

The episode controller fits the playable polygon into the world area above the HUD. It uses virtual WASD and wheel input before sampling the next policy observation. Explicit camera actions open a two-second excursion. Active gestures and dialogs defer restoration. Battle records include successful fits and view checks. A changed camera contract starts a new fitness ledger because it changes spatial inputs.

L1 parents are ranked solely on fresh L1 outcomes. A later-stage change must preserve all earlier decisions and beat its reference at the first changed stage. In standalone PPO, Boston L1 continues in the configured model file. An earned later stage starts with the current L1 weights once and its own fresh Adam optimizer. Subsequent updates and evaluation use the sibling checkpoint (e.g. nn_policy4.L2.pt). Local sidecars are required to resume those PPO specialists; the campaign search release carries the frozen GRU and stage strategy overrides. Historic L1 weights retain their original training history.

Fresh L1 games with ten or more legal cast decisions and zero sampled casts can nominate a challenger with only its cast preference changed. Native legality masks still apply. Only game outcomes enter fitness.

With progression enabled, at most one fresh search copy per generation spends additional attempts on below-target L1 wins to reach later stages for practice. The others finish their fresh trial immediately. Pans shorten as the visible playable boundary approaches the HUD or window edge.

Campaign search can test a cast-timing adjustment when a candidate repeatedly sees legal casts and samples none. The adjustment scores each available ability using its best eligible cell, zombie and civilian counts, and a candidate-specific gain and threshold. It changes ability choice while keeping the existing target preferences. The frozen incumbent remains the comparison arm. The local fitness ledger also retains known overdraft prices by stage, tool and geometry so a block with no L2 starts does not erase useful L2 preparation receipts.

Battle records include unique civilians credited for shelter, unique civilians exposed, total exposure events and occupied breach counts. Campaign search applies the two reward components only to its auxiliary objective. Candidate cast preferences can favor local zombie pressure near occupied, intact shelter perimeters. Actual saved percentages, qualifying win counts and held-out promotion use official outcomes.

Special-building experiments spend at most six planning decisions favoring plausible special buildings already enclosed by the chosen refuge and then any game-enabled numeric special actions. The probe keeps the same zone proposal as its parent. Numeric activation receipts are logged by building index, with a .01 reward up to three buildings in search and PPO. Compare survival using the original 35% gate and held-out results.

Controlled L1 defense proposals can retain a missile while occupied shelters face little local pressure, then favor shots near a threatened occupied perimeter. A separate placement proposal relocates one garrison to an unused building inside the existing refuge. Game receipts distinguish a proposed relocation from a purchase. Record native deploy times, first occupied breach, civilians exposed, and official saved fraction.

A follow-up timing proposal reads the native missile flight time and lowers the missile preference while a stock-confirmed shot is still in flight. The game can still accept simultaneous launches, and the action remains legal. Existing policy bundles lack the optional trait and preserve their logits.
