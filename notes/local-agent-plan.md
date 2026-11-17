# Local agent operation plan

Goal: a new agent on this computer can inspect the repository, safely resume the
existing learner and manage its visualizer using repository instructions alone.
Execute inline; no subagents. User authorized implementation and scoped tests.

Design: add one operator CLI and a PowerShell entry point. Reuse the current
launcher, checkpoint schema and visualizer server. Do not edit loaded trainer,
environment or observer modules, change rewards, or restart the healthy run.
This is the existing Windows deployment, not a portable distribution project.

## Milestones

- [x] Read-only status/check: `scripts/local_agent.py`, `scripts/test_local_agent.py`.
  Inventory verified script paths/PIDs/creation times, resources, latest history,
  dependencies, supported owned copy/DLL and exact checkpoint compatibility.
  Test missing/wrong checkpoint, foreign process paths and malformed history.
- [x] Guarded lifecycle: same CLI plus `local.ps1`. Resume existing weights only,
  refuse concurrent trainers, serialize wrapper launches, apply CPU/priority
  limits before spawning the existing launcher. Reuse matching visualizer;
  refuse foreign port owners. Stop only an explicitly identified server/trainer,
  verify identity and descendants; let launcher clean owned games.
  Test refusal paths and launch arguments with fakes; test actual visualizer
  start/reuse/stop on an unused loopback port without preview or game control.
- [x] Handoff: README/AGENTS/runbook and local environment record. Make commands
  the first entry point, distinguish healthy existing runs from new launches,
  document exit codes and recovery, and record evidence in tracker.

For each milestone: run failing regression tests first, implement, run focused
checks, commit conventionally. Preserve unrelated dirty artifacts. Push milestones.
Final validation includes live read-only check and untouched production identities;
actual training launch/stop is tested with fakes while the real learner is active.

## Decisions and evidence

### Follow-up: isolated Python environment (authorized 2026-11-17)
- Add requirements.txt for the five verified runtime dependencies, using CPU-only
  PyTorch; create an isolated .venv without modifying the active global environment.
- Switch local.ps1 and visualizer/start.ps1 defaults to repository .venv. Validate
  interpreter selection, pip consistency, offline regressions/checkpoint parity,
  read-only preflight and isolated visualizer lifecycle under the new interpreter.
- Update setup/recovery instructions and AGENTS/tracker. Keep trainer paths/game
  artifacts explicitly local; this does not claim full game-install portability.
- Completed: new isolated CPython3.14.4 .venv installed from requirements.txt;
  pip check and package-location checks passed (no system-site-packages). Launchers
  select .venv; original active processes remain on their previous interpreter.
- Windows venv redirectors exposed a real lifecycle bug: socket owner is the base
  Python child, not Popen's redirector PID. Tests first reproduced it; operator now
  recognizes owned descendants, interpreter children and its own operator ancestry.
  Initial failed test server31544/redirector23040 cleaned explicitly by identity.
- Final evidence:15 operator+47 trainer+35 visualizer tests=97 passed in .venv;
  12-step model/observer output and sampled-decision parity, Node graph pass.
  Actual preflight and both visualizer launchers passed under .venv. Isolated
  server8812/redirector11276 stopped; foreground-launch server/shell also cleaned.
  Duplicate train call still refuses original global-Python run. Port8766 closed.
  Direct dependency pins are not a complete transitive lockfile. No live trainer
  restart or new game launch was needed; native/deployment portability is unchanged.

- Reuse `D:\zar-scratch` and its existing Python/artifacts. Refuse a different
  checkout while trainer ROOT remains hard-coded, rather than loading another
  checkout's model silently. Portable paths/releases are deferred deliberately.
- No dependency reinstall, checkpoint publication or extra game copy is needed.
- Milestone 1: five offline tests passed after the expected missing-module failure;
  actual read-only preflight passed for schema3/Adam, inst1 executable and x64 DLL.
- Milestone 2: eleven tests pass, including lock contention, explicit resume paths,
  process identity refusal and resource-limit ordering. Actual duplicate start was
  rejected. Isolated server29688 on8766 started/reused/served HTTP/stopped; stale
  creation time refused without stopping it. Production identities unchanged.
  Parent-launch race and NaN creation time are covered. No live training stop.
- Final:13 focused tests pass, including background-launch options and resource
  refusal. Actual PowerShell entry point preflight/reuse pass; documented blocks
  parse and Markdown entry links resolve. Disposable process verified below-normal
  priority and CPUs0-7. Production run reached round33 with a fresh332-input frame;
  no trainer module edits, checkpoint writes by validation, or extra game boots.
- Limits: no Qwen/new-agent trial, clean-machine install or real training stop/start
  under the wrapper. Launcher arguments/resource ordering are tested with fakes;
  the existing live run remains owned by its original launcher. No portability claim.
