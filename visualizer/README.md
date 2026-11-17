# Signal — ZAR policy observatory

A read-only visualizer for a running PyTorch GRU policy. The browser shows actual captured activations, recurrent memory, learned connections, output probabilities and the action sampled by one worker. It does not play the game, load a second gameplay policy, change checkpoints, or control training.

## Run

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

**The observer integration is included in this branch's `scripts/nn_play2.py`. An already-running, uninstrumented worker cannot provide these values.** The app will wait until a worker launched with this version makes its first decision. The active `D:\zar-scratch` checkout was deliberately left unchanged while its training processes were live; bring this branch into that checkout at the training owner's next safe restart.

The 22-line integration in `scripts/nn_play2.py`:

1. Imports the optional observer and feature labels.
2. Installs an observer on each episode's actual policy instance.
3. Publishes the masked probabilities and selected tool/cell immediately after the existing sampling code.
4. Removes the hooks and closes the writer in `finally`, including failed episodes.

**The user authorized the integration. Bring it into the active checkout only during trainer downtime coordinated with the agent running training. Do not edit `scripts/*.py` while workers are live. Do not stop or restart another agent's workers for this visualizer.** Preserve the training agent's newer changes when integrating the branch.

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

The browser checks for new telemetry 50 ms after each completed request and redraws only when the sample, worker or model revision changes. Requests never overlap; an unavailable server is retried after one second. This reduces display delay without changing the model's decision rate. The current trainer makes battle decisions about every 2.5 seconds, so the graph holds the actual last values between decisions instead of generating artificial activity. The observer still caps publication at five frames/second.

## Model changes and limits

Dimensions, head names, weights and values come from the running model. Each episode reports its own model revision, derived from full parameter values. Normal in-place parameter updates and checkpoint loads refresh the graph; later worker instances publish their current weights automatically. This observes the weights the worker actually uses, which may lag the trainer's newest checkpoint until its next episode.

Supported topology: **one single-layer, unidirectional GRU directly feeding one or more linear heads**, as in the current v1/v2 policies. Different widths and output sizes are discovered. New module types need an observer adapter; unsupported structures report an error rather than inventing a graph. Functional transformations between those modules are not inferred. Feature/action meaning cannot be deduced from tensor dimensions: the training owner must maintain the supplied labels when changing feature order or semantics. `labels.py` documents the current 22-feature order.

Observer hooks capture only single-step, gradient-disabled forward passes. PPO sequence updates and gradients are not visualized. It never consumes random numbers or modifies tensors. Copies are detached, and outputs are copied before the trainer can mask them in place. A single-slot queue writes latest-only JSON in a background thread, capped at five frames/second. Disk/serialization failure drops the frame rather than interrupting the decision loop. Current decisions occur much less frequently than that cap.

All telemetry, logs and local screenshots stay in ignored `visualizer/runtime/`. Normal observer shutdown removes its own frame file; abrupt termination can leave a stale file that the server ages out. The server serves only four explicit frontend files and `/api/state`; it does not expose source files, checkpoints, directory listings or control endpoints. Anyone who can reach this port can view the telemetry; there is no login or TLS termination built in.

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
npx --yes --package @playwright/cli playwright-cli -s=zar-mobile run-code --filename=test_mobile.js
npx --yes --package @playwright/cli playwright-cli -s=zar-mobile close
```

The browser check sends multi-touch events, verifies pinch anchoring, pinch-to-pan transitions, cancellation, tap inspection, zoom controls, complete action probabilities and scroll access at 320×568, 390×844 and 844×390. It covers WebGPU (when available), forced Canvas 2D and desktop mouse interaction. It uses the separate preview model and never controls a game. Screenshots go to ignored `runtime/`. Browser emulation does not replace testing on physical iOS/Android devices.

The model check imports the current trainer source without running its main function or opening a game. It checks exact recurrent outputs and sampled decisions, then reports a warm CPU inference benchmark. It does not establish end-to-end gameplay overhead.

Verified on 2026-11-16 before trainer integration: 16 Python tests; Node graph/layout/filter/clear assertions; the current 61,980-parameter PolicyNet2 gives identical outputs and sampled decisions for 12 recurrent steps. One warm CPU run measured median 0.074 ms plain versus 0.122 ms observed including snapshot creation, excluding first topology extraction and background disk writes. Edge displayed the WebGPU graph and Canvas 2D fallback, live synthetic updates, node inspection, pause/resume and waiting state. The responsive view was checked at a 390-pixel viewport. Two additional integration tests now exercise the real episode function against a fake game, checking captured decisions, unchanged results and cleanup on success/failure. Real-game attachment awaits deployment at a safe trainer restart.

## Collaboration handoff

The original application is confined to `visualizer`. The user subsequently authorized the 22-line trainer integration and root `AGENTS.md` maintenance guidance. Those changes were made on `codex/visualizer-integration` in `D:\worktrees\zar-visualizer-integration`, preserving the active checkout and the other agent's uncommitted work. Training's dirty logs/checkpoints were not staged. No game processes were launched, stopped, resized or controlled. Root `notes/tracker.md` was read but not edited because that file remains outside the authorized edit scope. This README and PLAN.md hold this work's handoff.
