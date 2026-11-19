# ZAR Observatory

A read-only interface for a running PyTorch GRU policy and its recorded training
results. Open **http://localhost:8765** for the observatory or **/legacy** for the
original network graph and its focused node inspector.

## What each view answers

| View | What to look for | Data |
| --- | --- | --- |
| **Monitor** | Which tool did the policy choose, where could it target, and what was in view? | Actual masked tool and selected-tool position probabilities, reported model and worker identities, and the policy's 8×6 viewport observations. Grid positions can snap to native entities during execution. Roster and perk slots have separate distributions. |
| **Neural activity** | Which inputs and hidden units were active, and which learned coefficients should I inspect? | Captured float32 inputs, previous memory, GRU output, raw logits and value. Input groups, search and 16-row pages retain the trainer's label and normalization strings. Exact signed GRU gate and head coefficients are available as 16×32 tiles when captured. |
| **Timeline** | What did the model see at an earlier decision? | Up to 50 replayable samples for the selected stream from a shared 200-sample retention window. Replay restores captured observations, distributions and recurrent state. Comparison lists changes in inputs, probabilities and hidden state where their definitions match. |
| **Learning** | How often does a policy qualify on independent boards, and what evidence supports a team change? | Recent validated schema-4 PPO history and campaign trial/holdout outputs. Filter by source, start kind and level. Inspect the incumbent and provisional team, held-out arms, PPO updates, available cast counts, selected casts, stock decreases and changed saved team parameters. |

The view freeze affects the browser. Use the process picker to inspect retained
history after a worker disappears. A stale inference can coexist with an open
connection. The legacy graph remains available for focused connectivity
inspection. Its unsigned GRU edges summarize weights across gates.

### Game view

**Game view** starts expanded under the battlefield in the Monitor. While the
panel is open and the tab is visible, it plays a live, muted 960×600 H.264
stream targeting 15 fps and 1.2 Mbit/s per viewer. The observatory starts one
Windows Graphics Capture session and one FFmpeg NVIDIA encoder for the selected
game, shared by up to four viewers. The encoder sends independent fragments
every third of a second. The server retains only the most recent fragment and
sends it as binary fragmented MP4 over a single streaming HTTP response. The
player keeps close to the buffered edge and evicts older video.

Live video requires FFmpeg with `h264_nvenc` on the host and an H.264 Media Source
decoder in the browser. If streaming is unavailable, Game view falls back to
the higher-resolution JPEG thumbnail every two seconds. Video and thumbnails
run independently of decisions and do not appear in replay. Freezing the view
holds the displayed frame and stops media requests.
Game view follows the Monitor's **Process** picker. Automatic attachment
keeps the current worker while its telemetry is fresh and switches when
another fresh stream is available. Campaign search normally publishes one
candidate stream per training generation.

On Windows, install the optional Graphics Capture dependencies into the
ignored runtime directory. The repository's Python environment supplies
NumPy and psutil. This command leaves the trainer's environment alone.

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: --no-deps --target visualizer/runtime/screenshot-deps -r visualizer/screenshot-requirements.txt
```

The helper verifies the process and its window handle against a live stream and
a repository-owned game copy. A disposable subprocess crops a Windows Graphics
Capture frame to the game client area and returns a JPEG up to 1280×960,
subject to a 512 KiB cap. The observatory
keeps one image in memory and limits capture to one subprocess globally. The
helper cannot delay the policy worker. Minimized or unavailable windows show a
waiting message. There is no desktop or PrintWindow fallback.

Game view is available through localhost and the direct LAN listener. To
share game video and thumbnails publicly, explicitly set `share_screenshots = true` under
`[visualizer]` alongside `learning_host` in `zar.local.toml`, then restart
the observatory. Viewers who can reach that hostname can see the game
video whenever Game view is open.

## Data and access

- The Python observer stays attached to the actual forward pass and publishes
  after mask application and action selection. The no-gradient hooks copy
  values before in-place modification. A single background writer records the
  latest frame and writes a revision-scoped float32 weight file once per
  revision using detached parameter bytes already copied for identity hashing.
  The writer records the exact weight ID, campaign team and forecast identity.
  Existing workers pick up those fields on their next normal launch.
- The server samples the runtime directory every 200 ms. When the inline
  legacy topology bytes match, the server reuses the decoded topology and
  parses the changed prefix. The observatory uses one versioned SSE stream,
  sends labels once per stream revision, sends the selected tool's conditional
  row, and streams incremental history summaries. The legacy feed and
  diagnostic `/api/state` remain available.
- Replay is keyed by observer stream, sequence and mode. Sequence gaps identify
  missed publications. Observer throttling and queue drops also limit coverage.
  Retention is in memory and resets with the server. Observed decisions tell
  what the policy chose. Existing observer frames lack per-decision attempts
  and native confirmations. Learning shows recorded episode-level aggregates.
- Learning is available through the LAN address or computer name. To share it
  over HTTPS, set `[visualizer]` → `learning_host` in the ignored
  `zar.local.toml` to the exact public hostname and restart the visualizer.
  Anyone with access through that hostname can read the Learning results.
  Update the setting if a Cloudflare Quick Tunnel rotates. Weight
  tiles require **localhost** access on the host. These endpoints serve only
  retained matrix slices and fixed result projections. Checkpoints and
  arbitrary paths are outside the HTTP allowlist. Weights are available during
  the episode and removed on normal observer close. Older workers can still
  provide activation replay. Campaign stage comes from the existing campaign
  episode tag. Older standalone PPO frames lack a live stage field.
- Cloudflare Quick Tunnels support the Learning requests. The live Monitor
  requires Server-Sent Events, which Quick Tunnels do not support. Public live
  viewing requires an SSE-capable tunnel, such as a named Cloudflare Tunnel.
  [Quick Tunnel limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
- Learning reads up to the last 4 MiB per recognized result file, 400 PPO
  outcomes, 60 PPO updates, the 16 most recently written campaign runs, and 400
  outcomes per selected run. Champion statistics use the search's fresh-board
  evidence. Raw trial counts can include repeats. Timeout snapshots are
  omitted from official save scores. Aborted readings appear as retry scores.
  Older outputs omit explicit lineage. Team comparison lists saved parameter
  differences. Promotion evidence appears when the champion and held-out
  results record it.
- Offline sensitivity was evaluated and deferred. An isolated replay would
  need the hidden state, exact revision, target masks and the campaign
  specialist's mutable planning and forecast state. Existing telemetry lacks
  a reproducible snapshot of that composite state. Weight inspection and
  decision comparison use captured data only.

## Acceptance and benchmark

The Playwright suite is `test_observatory_browser.js`. The connected worker
check is `verify_live_observatory.js`. Run the former with synthetic preview
and the latter against the deployed server during a coordinated normal worker
launch. The legacy transport and mobile suites target `/legacy`.

Measured on this host in Chromium at 1440×900 with a recorded schema-4 fixture
of 4,889 inputs, 8,880 conditional logits and 55,932 legacy edges. The graph used
Canvas 2D. Render timings measure synchronous SSE handler work minus JSON
parsing. Browser paint and GPU execution are outside these timings. Heap is
JavaScript heap after garbage collection.

| Metric | Original graph | Monitor | Neural activity |
| --- | ---: | ---: | ---: |
| First browser SSE payload | 5.13 MB | 0.37 MB | 0.39 MB |
| Steady SSE payload | 244 KB | 34 KB | 34 KB |
| Typical steady JSON parse | 0.4 ms | 0.1 ms | below 0.1 ms |
| Typical steady render handler | 48.2 ms | 0.4 ms | 1.2 ms |
| JavaScript heap | 7.23 MB | 2.09 MB | 3.04 MB |
| Select options | 14,217 | 18 | 27 |

The server measured 3.52 ms for steady legacy serialization and 0.42 ms for
compact serialization. Parsing the 5.12 MB observer file took 44.57 ms with
a full decode and 10.88 ms with byte-verified graph reuse. Peak traced decode
allocations fell from 27.1 MB to 1.24 MB. These are fixture measurements during
active training. First attach size varies with retained history. Reproduce
with `python -B visualizer/benchmark_observatory.py <recorded-frame> --serve`
and run `visualizer/benchmark_observatory.js` in Playwright on the isolated
loopback fixture server. In a second local SSE run, request-to-first-payload
time was 133 ms for the legacy feed and 3.1 ms for the compact feed. This
comparison includes server encoding and loopback delivery and uses warm
server caches with different retained history lengths.

The browser replay matched a live Boston L1 worker's `buy Rally` decision
(game 54656, worker 53524, revision `d9e6f3c6341a6d3c`, sequence 0). The running
worker predated matrix capture. A subsequent `pan_left` sample from that worker
matched the original runtime JSON for the full input, previous memory, hidden
output, tool logits, tool probabilities and actual selection. Raw matrix
inspection and interactive comparison were exercised in preview.

## Run

During campaign team search, one candidate publishes its GRU state, final
combined logits, masked probabilities and selected actions. The architecture
label identifies the preparation and battle specialists. The graph draws
the GRU and value connections. The specialist scoring functions contribute
to the displayed logits and have no drawn edges. The worker is quiet during
layout construction and after its own game finishes. Other games can still
be running.

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

Then choose **Synthetic preview** in the source selector. The default **Live**
source accepts real observer streams. Closing the server with Ctrl+C also stops
its preview process.

The launcher defaults to the repository's `.venv\Scripts\python.exe`; follow
the root README to create it from `requirements.txt`. Override it with
`-Python "C:\path\to\python.exe"`, or change the port with `-Port 8766`.
The server/frontend use the Python standard library; the observer and optional
preview use PyTorch from the selected environment. Existing processes keep their
original interpreter until restarted normally.

The observatory uses Canvas 2D for heatmaps and standard DOM controls. The
legacy graph prefers WebGPU on localhost or trusted HTTPS and supports Canvas
2D over ordinary HTTP. `/legacy?canvas2d=1` explicitly exercises the fallback.

## Connect real training

**The observer integration is already included in `scripts/nn_play2.py` in this checkout. An already-running, uninstrumented worker cannot provide these values.** Launch training normally; the app waits for an instrumented worker's first decision. No alternate trainer launcher or integration patch is needed.

The integration in `scripts/nn_play2.py`:

1. Imports the optional observer and feature labels.
2. Installs an observer on each episode's actual policy instance.
3. Publishes the masked probabilities and selected tool/cell immediately after the existing sampling code.
4. Removes the hooks and closes the writer in `finally`, including failed episodes.

**Coordinate any future observer/trainer changes with the training owner. Do not edit `scripts/*.py` while workers are live. Do not stop or restart another agent's workers for this visualizer.** A server/frontend-only change requires restarting the visualizer server and refreshing browsers, not restarting training.

The old standalone patch has been removed now that it is applied; do not apply it a second time. Launch training normally after integration. No alternate trainer launcher is required. Existing training behavior, checkpoints, sampling, optimization and game controls are retained. See the maintenance contract in root `AGENTS.md` before changing the model or feature meanings.

## How to read the legacy graph

- **Observations:** the actual feature vector passed to the policy. Labels identify transformed values such as log counts and normalized money; these are not raw HUD numbers.
- **Previous memory:** the hidden state passed into this decision. It is zero at the start of an episode.
- **Recurrent state:** the actual GRU output for this step.
- **Action policy / map position:** actual linear-head outputs. Probability bars beside action nodes show the masked sampling probabilities, and gold rings show the sampled choices. A chosen cell is marked unused for wait/ready. The value prediction appears beside its output node.
- **Expected return:** the value head's prediction of reward, not a win percentage or a confidence score.
- **Brightness:** absolute activation normalized within its layer. Purple denotes negative values; green positive values. Blue identifies the memory layer and GRU connection summaries.
- **Connections:** strongest weights per target (up to six), filtered by the Links control. Linear-head connections show signed weights. A GRU has three sets of gate weights, so its connections are explicitly **unsigned RMS summaries across reset/update/candidate gates**. They are not single synapses or causal attributions. Not every learned weight is drawn.

The graph fills the window beneath a compact control bar. Click or tap a node to open the collapsed Inspector, pin its value and isolate its strongest displayed connections. With the Inspector open, hover or use its node selector to inspect other nodes after clearing the pin. The Inspector includes every action probability, worker details and the selected node's activation, incoming weights and policy probability (including map-position nodes).

On mobile, pinch to zoom around your fingers and drag with one finger to pan. The +/− buttons also zoom; Fit restores the overview. Magnification reaches 12× so dense nodes and labels can be read on narrow screens. The mobile Inspector spans the available width and scrolls independently to expose all details, including in landscape. Tap Inspector again to close it. On desktop, the mouse wheel zooms around the cursor. Pause freezes only the view; inference continues. Dense graph labels appear as you zoom in.

Automatic attachment stays on a healthy, fresh stream. It switches to another
fresh, healthy stream when the selected stream disappears, reports an observer
error, or goes 15 seconds without a sample. A paused game or slow inference can
look stale. Streams older than 120 seconds are omitted. Manual selection holds
the requested stream. Campaign search usually observes one candidate per
training generation, so automatic handoff needs another instrumented worker
before it can resume live viewing.

The browser holds one **server-sent events (SSE)** connection to `/api/events` using native `EventSource`; it does not poll. A disconnected connection automatically retries with a one-second retry interval. Mode/worker changes close the old connection; every new connection receives current topology. Idle updates arrive about once per second so sample age and connection health stay visible. The graph redraws only for new samples or view changes. A connected but stale worker is distinct from an offline server.

The server samples the existing observer files through one shared **200 ms cache** for all viewers, including while no browser is open. There is no network dependency in inference. This replaces repeated HTTP requests/file reads; it does not increase model decision frequency or promise lower end-to-end latency than the former 50 ms polling. The observer still publishes at most five snapshots/second. Actual values remain still between decisions.

The sampler wakes SSE viewers immediately after each sample, avoiding a second
200 ms polling interval per viewer. Unchanged file bytes reuse decoded JSON;
byte comparison deliberately catches same-size writes with unchanged timestamps.
The writer serializes immutable topology once per revision, and the input table
reuses its rows. The footer separates published sample number from decision
number and reports the interval between the worker's consecutive publish calls.
That interval includes game actions and observation work, not just neural-network
inference. Sample age measures telemetry freshness; it is not inference duration.

The Inspector now lists **Current observations** with their exact feature labels and formatted values, plus **Recent sampled decisions** with timestamps, phase, published sequence, chosen head labels and probabilities. A sampled choice is not proof that the game executed it. Cell choices may be unused for wait/ready. Pause freezes the graph, input list and decision log while telemetry collection continues; Resume displays the latest retained state.

History is **bounded, in-memory sampled telemetry**: the server retains 200 compact records total across all workers/modes and returns the latest 50 for the selected stream. Reconnecting replaces the displayed list from that retained history, avoiding duplicates. History survives observer file removal for a manually selected stream, but is cleared by a server restart and older entries are evicted. Preview records never appear in Live. Published sequence gaps are shown when detectable; the observer's own dropped/throttled samples are not recoverable. This is neither trainer stdout nor a durable, complete event journal. Original trainer logs remain in their existing locations.

The stream supports at most 16 active viewers per server, with a three-second socket write timeout; excess connections get HTTP 503. Slow viewers cannot queue unlimited frames or block training. Browser per-origin connection limits may be lower. No commands, training controls, observation injection, or checkpoint/reward changes are accepted.

## Model changes and limits

Dimensions, head names, weights and values come from the running model. Each episode reports its own model revision, derived from full parameter values. Normal in-place parameter updates and checkpoint loads refresh the graph; later worker instances publish their current weights automatically. This observes the weights the worker actually uses, which may lag the trainer's newest checkpoint until its next episode.

Supported topology: **one single-layer, unidirectional GRU directly feeding one or more linear heads**, as in the current schema-4 policy. Different widths and output sizes are discovered. New module types need an observer adapter; unsupported structures report an error rather than inventing a graph. Functional transformations between those modules are not inferred. Feature/action meaning cannot be deduced from tensor dimensions: the training owner must maintain the supplied labels when changing feature order or semantics. `labels.py` documents the current 2485-feature order; the label tests and `verify_model.py` enforce the trainer contract.

Observer hooks capture only single-step, gradient-disabled forward passes. PPO sequence updates and gradients are not visualized. It never consumes random numbers or modifies tensors. Copies are detached, and outputs are copied before the trainer can mask them in place. A single-slot queue writes latest-only JSON in a background thread, capped at five frames/second. Disk/serialization failure drops the frame rather than interrupting the decision loop. Current decisions occur much less frequently than that cap.

Observer snapshots and local test screenshots stay in ignored `visualizer/runtime/`; recent decision history lives only in server memory. Normal observer shutdown removes its own frame file; abrupt termination can leave a stale file that the server ages out. The server serves only four explicit frontend files, `/api/events`, and the cached `/api/state` diagnostic endpoint; it does not expose source files, trainer log files, checkpoints, directory listings or control endpoints. Anyone who can reach this port can view the telemetry; there is no login or TLS termination built in.

## Checks

Use the repository environment explicitly:

```powershell
$python = (Resolve-Path .venv\Scripts\python.exe).Path
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

The current schema-4 policy has 2,148,390 parameters. Current validation records
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

That historical model supplied332 inputs and72x48 conditional cell outputs. The cell head
is still a direct linear head: raw outputs show all tool/cell logits, while
probabilities are zero outside the sampled tool row; selected hc is tool*48+cell.
Input and large output layers use compact grids. Select a node or use Inspector
for its full label/value. Telemetry remains observation-only. Real attachment
and browser332-input check passed; subsequent grid-layout tests used explicit
synthetic data, plus the transport/mobile suites. See
[training improvements](../notes/training-improvements.md).

Schema4 expanded-mechanics validation and measured live browser timings are in
[mechanics coverage](../notes/mechanics-coverage.md). It supplies4889
inputs and185x48 cell logits. Older332-input records above are historical.
Final-width preview checks passed transport/reconnect/pause/isolation and both
WebGPU/Canvas2D mobile interactions. Actual worker44888/game40284 supplied4889
correct labels and matching browser inputs/actions in a scoped live sample.

The final CPU policy check measured0.198ms median forward,0.453ms with observer
capture. Two live60-decision planning rollouts took14.46s and14.24s (about4.2
decisions/sec; action mix matters). Ten sampled live frames reached the browser
in133-375ms,median274ms; a two-animation-frame display check measured248-667ms,
median378ms from capture. The first topology/render is slower. These measurements
include local machine load and are not a controlled before/after benchmark.
The viewer samples up to5Hz and cannot show every faster decision; sampled
history is not a complete action log.
