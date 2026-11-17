# Portable deployment and checkpoint sharing plan

User authorized implementation, scoped live checks and six-hourly GitHub Release
snapshots when weights change. Execute inline; no subagents. Preserve unrelated
dirty policy2/history2 files. Do not modify the installed game or commit DLLs.

## Milestones
- [x] Paths/config/copies: stop the owned trainer after recording its last saved
  checkpoint, derive active module roots from __file__, add ignored zar.local.toml
  plus an example, prepare new owned copies from the configured read-only install.
  Refuse overwrite/traversal/reparse links/unsupported builds. Copy no user progress
  or identity/log/cache data. Apply calibrated normal/low-graphics settings only to
  new copies. Test temp fixtures and import a relocated source tree.
- [x] DLL: pin Rust/target and locked Cargo build; build/test in staging, validate
  x64/export contract, record source/compiler/flags/output hash. Verify two clean
  builds match with the current linker. Refuse deployment while owned games run.
  Commit source/toolchain/build instructions only, never generated DLL/PDB/targets.
- [x] Checkpoints: capture a single atomic checkpoint revision into a local bundle,
  validate schema/weights/optimizer and checksum, record source revision honestly,
  publish idempotent versioned GitHub Release assets through the identity helper.
  Provide verified import without overwriting active/existing model files. Run one
  real publication/download validation, then schedule every6h using Codex automation.
- [ ] Handoff: README/AGENTS/config/build/sharing instructions and tracker updated;
  run offline suites, a tight owned-copy live check, resume existing weights/Adam
  under .venv with headroom and verify a fresh update/frame. Commit/push milestones.

## Decisions/evidence
- Use TOML (stdlib parser), no new Python dependencies. Repository-relative runtime
  paths stay predictable; only the source install and contribution helper need local
  machine configuration. No game files, user saves or DLLs enter checkpoint releases.
- Sharing goes to the existing PUBLIC repository, as explicitly selected by user.
  Only validated model+optimizer, compatibility metadata and selected metrics publish.
  Six-hour schedule creates a release only if the checkpoint bytes changed.
- Previous trainer stopped safely at saved update46 (policy e9c9e765b8f64cf9);
  launcher/game cleanup verified before source edits. Original visualizer preserved.
  Four portability tests and15 operator tests pass, including relocated imports
  from a directory with spaces. No schema/reward changes.
- Actual installed EXE hash differs from supported a1bd5913...; copy guard correctly
  refused it. Local config uses compatible game-copies/inst4 as read-only asset
  source instead. New copies still exclude all progress/identity/runtime data.
  Other game builds require separate native-offset validation, not a bypass.
- Configured prepare-game created fresh inst10 successfully. Source inst4 untouched.
- DLL Rust1.96.0/MSVC linker14.44: one ABI unit test and two Python build tests pass;
  two independent clean builds matched SHA256
  2d2f160e53c26c521984727c922e7629bd6718e5010642d23f9db49bdcd8d848.
  Deployed only while no owned game was running; outputs remain ignored.
- User clarified fresh training copies must have everything available. Default
  preparation now enables all16 units/19 abilities/16 upgrades plus Extra_Zones;
  preflight rejects incomplete profiles. This does not buy levels, spend SP,
  change normal difficulty or pre-place units. Policy action coverage remains
  incomplete and is explicitly documented.
- Published/download-verified checkpoint-35a8148ff8948406; repeat publication
  returned already_published without modifying the release. Active local Codex
  heartbeat share-zar-checkpoints runs every6h when this environment is available.
- First native probes exposed a distinct unplayed campaign panel. PrintWindow
  captures analysis/portable-menu-*.png show its PLAY NOW at(.446,.610) on1920x1200.
  Corrected navigation reached Boston L1/8142 civilians/$3111 with inst12 and the
  rebuilt DLL. Initial fixture probe had a bytes/text assertion error after boot;
  cleanup succeeded and the corrected read-only policy probe was rerun.
- Offline milestone:81 Python trainer/operator/interface tests +35 visualizer
  tests PASS,12 recurrent-step parity PASS,Node graph PASS. Added one further
  missing-copy CLI boundary test; seven boot tests PASS after that change.
  Unrelated legacy nn_hist2 whitespace dirt was not changed by diff checks.
