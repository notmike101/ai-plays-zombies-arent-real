# Read-only telemetry streaming plan (2026-11-17)

Goal: show actual model observations and sampled decisions through a persistent
browser connection, with useful recent decision history. The user delegated
implementation choices and requested documentation and a push. No trainer controls.

Architecture: retain the observer's detached, best-effort latest JSON files.
Use Python's existing HTTP server for SSE; share a 200 ms snapshot cache across
clients and sample while the server is running. Keep 200 compact decision records
in server memory, displaying the latest 50 for the selected stream. This is sampled
telemetry, not a complete training/stdout log; server restart clears history.
SSE beats WebSocket here because all traffic is observation-only. Keeping browser
polling would work but duplicates reads and requests. No new dependencies.

Scope: server.py, test_server.py, public/app.js, index.html, style.css, browser
checks, README.md, PLAN.md, root AGENTS.md and notes/tracker.md. Trainer, observer,
features, labels and game processes remain untouched. Reuse the current checkout;
unrelated training artifacts are excluded from commits. No subagents.

## Implementation (native)
- [ ] Add failing tests for bounded/deduplicated, preview-isolated history,
  shared reads, SSE initial graph/reconnect/new samples, shutdown and allowlist.
- [ ] Implement shared sampling, bounded history and SSE with finite write timeout,
  heartbeats and clean shutdown. Preserve /api/state for diagnostics.
- [ ] Replace browser polling with EventSource; reconnect on worker/mode change,
  reject old connection callbacks, freeze only the view, show observations and
  sampled decision history with their limitations and safe text rendering.
- [ ] Run the full visualizer unittest suite, verify_model.py, test_graph.mjs,
  plus browser streaming/reconnect/pause/selection and mobile layout checks.
- [ ] Update all current guidance, mark old plan/deployment claims historical,
  review the diff, update tracker, commit each edit batch and push.

Review focus: slow/disconnected viewers cannot affect training; reconnect must
send topology; preview history must never appear live; malformed files must not
kill sampling; history and buffers must stay bounded. Sampled action is not proof
that the game executed it. Real-worker validation waits for a coordinated launch.
