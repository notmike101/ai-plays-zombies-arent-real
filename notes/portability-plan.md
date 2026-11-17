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
- [ ] DLL: pin Rust/target and locked Cargo build; build/test in staging, validate
  x64/export contract, record source/compiler/flags/output hash. Verify two clean
  builds match with the current linker. Refuse deployment while owned games run.
  Commit source/toolchain/build instructions only, never generated DLL/PDB/targets.
- [ ] Checkpoints: capture a single atomic checkpoint revision into a local bundle,
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
