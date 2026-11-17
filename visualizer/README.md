# Signal — ZAR policy observatory

A read-only visualizer for a running PyTorch GRU policy. The browser shows actual captured activations, recurrent memory, learned connections, output probabilities and the action sampled by one worker. It does not play the game, load a second gameplay policy, change checkpoints, or control training.

## Run

For a new session, start with the [operator runbook](../notes/operator-runbook.md).
It covers existing-server detection, background start/stop, process identity
checks and training resume. Read CURRENT STATE in `../notes/tracker.md` for the
latest deployment snapshot; revalidate its PIDs before using them.

For this computer, `..\local.ps1 visualizer-start` from this directory reuses or
starts the background server. `..\local.ps1 status` reports its PID/create_time;
`visualizer-stop --pid PID --created TIME` stops that verified server. These
commands do not control training. The foreground launcher below remains supported.

From PowerShell in `D:\zar-scratch`:

```powershell
.\visualizer\start.ps1
```

Open **http://localhost:8765**. The service binds to **0.0.0.0:8765**. Other machines can use this computer's LAN address if their existing network/firewall settings permit it. No firewall rules are installed.

To include a clearly labeled, separate PyTorch preview with synthetic inputs:

```powershell
.\visualizer\start.ps1 -Preview
```

Then choose **Preview** in the app. Preview never sends input to a game. The default **Live network** view only accepts real, non-preview observer streams. Closing the server with Ctrl+C also stops its preview process. Do not start a second server on the same port.

The launcher uses the existing Python installation at `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`. Override it with `-Python "C:\path\to\python.exe"`, or change the port with `-Port 8766`. The server and frontend need no installed dependencies. The observer and optional preview use the trainer's existing PyTorch installation.

WebGPU is preferred. It works on a supported browser at localhost or over trusted HTTPS. Ordinary HTTP over a LAN address uses Canvas 2D when the browser withholds WebGPU. No insecure browser flags or certificate changes are needed. `/?canvas2d=1` explicitly exercises the fallback.

## Connect real training

**The observer integration is already included in `scripts/nn_play2.py` in this checkout. An already-running, uninstrumented worker cannot provide these values.** Launch training normally; the app waits for an instrumented worker's first decision. No alternate trainer launcher or integration patch is needed.

The integration in `scripts/nn_play2.py`:

1. Imports the optional observer and feature labels.
2. Installs an observer on each episode's actual policy instance.
3. Publishes the masked probabilities and selected tool/cell immediately after the existing sampling code.
4. Removes the hooks and closes the writer in `finally`, including failed episodes.

**Coordinate any future observer/trainer changes with the training owner. Do not edit `scripts/*.py` while workers are live. Do not stop or restart another agent's workers for this visualizer.** A server/frontend-only change requires restarting the visualizer server and refreshing browsers, not restarting training.

The old standalone patch has been removed now that it is applied; do not apply it a second time. Launch training normally after integration. No alternate trainer launcher is required. Existing training behavior, checkpoints, sampling, optimization and game controls are retained. See the maintenance contract in root `AGENTS.md` before changing the model or feature meanings.

## How to read the view

- **Observations:** the actual feature vector passed to the policy. Labels identify transformed values such as log counts and normalized money; these are not raw HUD numbers.
- **Previous memory:** the hidden state passed into this decision. It is zero at the start of an episode.
- **Recurrent state:** the actual GRU output for this step.
- **Action policy / map position:** actual linear-head outputs. Probability bars beside action nodes show the masked sampling probabilities, and gold rings show the sampled choices. A chosen cell is marked unused for wait/ready. The value prediction appears beside its output node.
- **Expected return:** the value head's prediction of reward, not a win percentage or a confidence score.
- **Brightness:** absolute activation normalized within its layer. Purple denotes negative values; green positive values. Blue identifies the memory layer and GRU connection summaries.
- **Connections:** strongest weights per target (up to six), filtered by the Links control. Linear-head connections show signed weights. A GRU has three sets of gate weights, so its connections are explicitly **unsigned RMS summaries across reset/update/candidate gates**. They are not single synapses or causal attributions. Not every learned weight is drawn.

The graph fills the window beneath a compact control bar. Click or tap a node to open the collapsed Inspector, pin its value and isolate its strongest displayed connections. With the Inspector open, hover or use its node selector to inspect other nodes after clearing the pin. The Inspector includes every action probability, worker details and the selected node's activation, incoming weights and policy probability (including map-position nodes).

On mobile, pinch to zoom around your fingers and drag with one finger to pan. The +/− buttons also zoom; Fit restores the overview. Magnification reaches 12× so dense nodes and labels can be read on narrow screens. The mobile Inspector spans the available width and scrolls independently to expose all details, including in landscape. Tap Inspector again to close it. On desktop, the mouse wheel zooms around the cursor. Pause freezes only the view; inference continues. Dense graph labels appear as you zoom in.

Automatic attachment stays on the selected fresh stream. After 15 seconds without a sample, it switches to another fresh stream if one exists; otherwise it labels the retained frame stale. A paused game or slow inference can therefore look stale without the process having crashed. Streams older than 120 seconds are omitted. Manual selection holds the requested stream rather than silently switching.

The browser holds one **server-sent events (SSE)** connection to `/api/events` using native `EventSource`; it does not poll. A disconnected connection automatically retries with a one-second retry interval. Mode/worker changes close the old connection; every new connection receives current topology. Idle updates arrive about once per second so sample age and connection health stay visible. The graph redraws only for new samples or view changes. A connected but stale worker is distinct from an offline server.

The server samples the existing observer files through one shared **200 ms cache** for all viewers, including while no browser is open. There is no network dependency in inference. This replaces repeated HTTP requests/file reads; it does not increase model decision frequency or promise lower end-to-end latency than the former 50 ms polling. The observer still publishes at most five snapshots/second. Actual values remain still between decisions.

The Inspector now lists **Current observations** with their exact feature labels and formatted values, plus **Recent sampled decisions** with timestamps, phase, published sequence, chosen head labels and probabilities. A sampled choice is not proof that the game executed it. Cell choices may be unused for wait/ready. Pause freezes the graph, input list and decision log while telemetry collection continues; Resume displays the latest retained state.

History is **bounded, in-memory sampled telemetry**: the server retains 200 compact records total across all workers/modes and returns the latest 50 for the selected stream. Reconnecting replaces the displayed list from that retained history, avoiding duplicates. History survives observer file removal for a manually selected stream, but is cleared by a server restart and older entries are evicted. Preview records never appear in Live. Published sequence gaps are shown when detectable; the observer's own dropped/throttled samples are not recoverable. This is neither trainer stdout nor a durable, complete event journal. Original trainer logs remain in their existing locations.

The stream supports at most 16 active viewers per server, with a three-second socket write timeout; excess connections get HTTP 503. Slow viewers cannot queue unlimited frames or block training. Browser per-origin connection limits may be lower. No commands, training controls, observation injection, or checkpoint/reward changes are accepted.

## Model changes and limits

Dimensions, head names, weights and values come from the running model. Each episode reports its own model revision, derived from full parameter values. Normal in-place parameter updates and checkpoint loads refresh the graph; later worker instances publish their current weights automatically. This observes the weights the worker actually uses, which may lag the trainer's newest checkpoint until its next episode.

Supported topology: **one single-layer, unidirectional GRU directly feeding one or more linear heads**, as in the current schema-3 policy. Different widths and output sizes are discovered. New module types need an observer adapter; unsupported structures report an error rather than inventing a graph. Functional transformations between those modules are not inferred. Feature/action meaning cannot be deduced from tensor dimensions: the training owner must maintain the supplied labels when changing feature order or semantics. `labels.py` documents the current 332-feature order; the label tests and `verify_model.py` enforce the trainer contract.

Observer hooks capture only single-step, gradient-disabled forward passes. PPO sequence updates and gradients are not visualized. It never consumes random numbers or modifies tensors. Copies are detached, and outputs are copied before the trainer can mask them in place. A single-slot queue writes latest-only JSON in a background thread, capped at five frames/second. Disk/serialization failure drops the frame rather than interrupting the decision loop. Current decisions occur much less frequently than that cap.

Observer snapshots and local test screenshots stay in ignored `visualizer/runtime/`; recent decision history lives only in server memory. Normal observer shutdown removes its own frame file; abrupt termination can leave a stale file that the server ages out. The server serves only four explicit frontend files, `/api/events`, and the cached `/api/state` diagnostic endpoint; it does not expose source files, trainer log files, checkpoints, directory listings or control endpoints. Anyone who can reach this port can view the telemetry; there is no login or TLS termination built in.

## Checks

Use the known working Python executable, not an unrelated `python` earlier on PATH:

```powershell
$python = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
& $python -B -m unittest discover -s visualizer -p 'test_*.py'
& $python -B visualizer/verify_model.py
node visualizer/test_graph.mjs
```

For touch/layout regression checks, start the server with `-Preview`, then run these from `visualizer/` with a Chromium Playwright CLI session:

```powershell
npx --yes --package @playwright/cli playwright-cli -s=zar-mobile open http://localhost:8765
npx --yes --package @playwright/cli playwright-cli -s=zar-mobile run-code --filename=test_stream.js
npx --yes --package @playwright/cli playwright-cli -s=zar-mobile run-code --filename=test_mobile.js
npx --yes --package @playwright/cli playwright-cli -s=zar-mobile close
```

The browser check sends multi-touch events, verifies pinch anchoring, pinch-to-pan transitions, cancellation, tap inspection, zoom controls, complete action probabilities and scroll access at 320×568, 390×844 and 844×390. It covers WebGPU (when available), forced Canvas 2D and desktop mouse interaction. It uses the separate preview model and never controls a game. Screenshots go to ignored `runtime/`. Browser emulation does not replace testing on physical iOS/Android devices.

`test_stream.js` checks real SSE requests (no snapshot polling), readable inputs,
new decision records, view pause/resume, worker changes, offline reconnect and
preview isolation. Run it only with synthetic preview and no real workers; its
Live check expects waiting. Stop the test preview afterwards and leave the normal
read-only server available. Server tests use temporary directories and ephemeral
loopback ports; integration/watchdog fixtures use PID -1, never real games.

The model check imports the current trainer source without running its main function or opening a game. It checks exact recurrent outputs and sampled decisions, then reports a warm CPU inference benchmark. It does not establish end-to-end gameplay overhead.

The current schema-3 policy has 632,649 parameters. Current validation records
are [training improvements](../notes/training-improvements.md) and
[the learning audit](../notes/learning-audit.md): Python checks, 12-step recurrent
observer parity, graph tests, and scoped live evidence. Historical timings for
the smaller schema-2 model are not performance measurements of this model.

## Current maintenance handoff

The [earlier live check record](../notes/visualizer-live-check.md) describes a
historical 32-input model. The schema-3 attachment evidence is in
[training improvements](../notes/training-improvements.md); subsequent fresh
332-label worker checks are recorded in `../notes/tracker.md`. These are scoped
attachment checks, not proof of complete campaign success. Check fresh frames
against current worker/game identities when verifying a new deployment.

Current guidance is root `AGENTS.md`, this README and `notes/tracker.md`.
`PLAN.md` records historical work; `notes/telemetry-plan.md` records the streaming
change. The old integration branch and original directory-only scope are historical,
not pending deployment instructions. Keep telemetry read-only, bounded and detached;
maintain label semantics with the trainer, and verify real attachment at the next
coordinated worker launch. Synthetic/fake-game checks do not prove live attachment.

## Schema3 trainer (2026-11-17)

Current model supplies332 inputs and72x48 conditional cell outputs. The cell head
is still a direct linear head: raw outputs show all tool/cell logits, while
probabilities are zero outside the sampled tool row; selected hc is tool*48+cell.
Input and large output layers use compact grids. Select a node or use Inspector
for its full label/value. Telemetry remains observation-only. Real attachment
and browser332-input check passed; subsequent grid-layout tests used explicit
synthetic data, plus the transport/mobile suites. See
[training improvements](../notes/training-improvements.md).
