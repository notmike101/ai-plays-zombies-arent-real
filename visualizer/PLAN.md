# Live policy visualizer — design and implementation plan

Goal: show actual inference activity and sampled decisions for one automatically selected ZAR worker in a dark browser canvas, served on 0.0.0.0:8765.

Architecture: optional PyTorch layer observers copy detached inference values into a bounded background writer. Atomic, latest-only JSON files stay in visualizer/runtime. A standard-library Python HTTP server selects one fresh stream and serves the UI and a read-only state endpoint. Native WebGPU renders the graph, with Canvas 2D fallback. No extra frontend dependencies.

Approaches: a launcher would preserve source isolation but require every future launch to use it and intercept sampling. Explicit observer calls are clearer and capture the actual selected action. The user delegated this choice; use explicit calls, preparing their exact patch here for separate permission before touching scripts. No live-worker restart or source edit is authorized yet.

Scope: all new files, plans, tests, logs, screenshots and runtime data remain in visualizer. Do not change root notes/tracker.md because the user's narrower directory restriction takes precedence. Do not alter branches or stage other agents' work. No subagents or game instances. Commit only explicitly named visualizer files and push milestones using the GitHub identity helper.

Display: inputs → GRU hidden state → actual linear output heads; recurrent memory connections are represented separately. GRU edges represent RMS magnitude across three gate weights (unsigned aggregate), linear edges are signed weights. Show this simplification explicitly. Node values are actual captured tensors, not simulated propagation. Show exact policy probabilities and sampled action separately. Hover/pin for values and incoming edges; edge-density filter, pause view, fit and zoom. A labeled synthetic preview is available only on request.

Model evolution: derive dimensions and module names from the observed model; refresh topology when parameter versions change. Support one GRU followed directly by linear heads (current v1/v2). Unknown architectures report unsupported rather than inventing connections. Labels use trainer-provided names with generic fallback. Observer failure must not fail training.

Networking: bind 0.0.0.0, serve only an explicit public-file allowlist and read-only telemetry; no game control, directory browsing or checkpoint downloads. WebGPU on localhost/HTTPS; Canvas fallback on insecure LAN origins. No firewall or certificate changes.

## Execution (native, no delegation)

- [x] Observer tests first: actual values, no RNG/output/gradient change, bounded writer, parameter refresh, unsupported model, cleanup. Implement observer.py and test_observer.py.
- [x] Server tests first: sticky selection, stale data, failover, malformed files, endpoint allowlist. Implement server.py and test_server.py.
- [x] Implement public/index.html, style.css, graph.js and app.js. Test graph construction with Node assertions; browser-test live synthetic telemetry, WebGPU/fallback, pause, selection, responsive layout, waiting state.
- [x] Write README, start.ps1 and reviewable integration.patch. Test against the current trainer source without applying it. Measure observer overhead using isolated synthetic inference only.
- [x] Review diff and rerun meaningful checks. Commit/push visualizer milestones; leave server available with real-game integration explicitly pending permission.

## Review focus

- Training continues if telemetry cannot be written or model is unsupported.
- No additional RNG use or graph mutation in observer, including during training.
- Replaced worker/episode/model does not retain stale topology or prior memory.
- Disconnected streams are labeled stale; preview never masquerades as live gameplay.
- HTTP paths cannot expose runtime files, source, checkpoints or parent directories.

## Evidence ledger

2026-11-16: inspected active nn_play2.py and running five-worker trainer. Current implementation is GRU(22,128), heads hu(15), hc(12), val(1). Existing dirty files belong to training. System python resolves to an unusable Inkscape interpreter; use C:/Users/me/AppData/Local/Python/pythoncore-3.14-64/python.exe (torch 2.15.0+cpu).

2026-11-16 completion evidence: 16 Python tests pass; Node assertions pass. Actual PolicyNet2 has 61,980 parameters and matched exact outputs and sampled actions for 12 recurrent steps. Warm median plain 0.074 ms versus observed + snapshot 0.122 ms in one isolated run. Edge verified WebGPU and forced Canvas 2D, preview updates, node inspection, pause/resume, clear waiting state, and compact viewport without horizontal document overflow.

Review fixes: removed filesystem timestamp cache after a reproducible collision; clear the GPU framebuffer when disconnected; ignore responses from a previous view selection; report unsupported models; tolerate thread startup failure; prefer newest streams over accumulated crash files. Regression tests cover the backend/renderer failures. No subagents were used, per project guidance; review was performed in this session.

Ruling: retain the current checkout and branch, stage/commit only visualizer paths, and keep handoff notes here instead of root notes/tracker.md — avoids changing the other agent's branch or violating the user's directory boundary. No new worktree or external edits were needed.

Pending: user permission for the prepared 22-line addition to scripts/nn_play2.py, followed by application at a safe training-owner-controlled restart and real-game attachment validation. No trainer was stopped or edited. No game test instances were created. The app defaults to waiting; preview is explicitly synthetic.
