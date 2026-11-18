# Checkpoint sharing and restore

The user authorized GitHub Releases every six hours, only for changed checkpoints.
The active local Codex heartbeat is **Share ZAR checkpoints**, ID
`share-zar-checkpoints`. It operates while this computer/Codex local automation
environment is available; GitHub does not reach into this computer. A clone does
not install that schedule. Other operators can run the same command manually or
arrange their own explicitly authorized schedule.

Configure `[sharing]` in ignored `zar.local.toml` using `zar.example.toml`:
repository=`OWNER/REPO`, identity_helper=the installed GitHub App identity helper.
This deployment uses `notmike101/ai-plays-zombies-arent-real`, a PUBLIC repository.
Never put credentials in this file. All Git/GitHub commands use the helper;
missing permissions are errors, never personal-identity fallbacks.

```powershell
.\local.ps1 checkpoint-export
.\local.ps1 checkpoint-publish
```

Export reads one revision of atomically replaced `nn_policy4.pt`, validates it,
and writes an immutable bundle under ignored `sessions/exports/SHA256`. It never
loads state into workers or changes training. Exactly three release assets:

- `nn_policy4.pt`: policy and Adam optimizer state, schema/learning metadata.
- `manifest.json`: full SHA256, policy/run IDs, exact feature/action schema,
  reward/GAE settings, supported game hash, source-at-capture commit/file hashes,
  and available last training-batch outcomes.
- `SHA256SUMS`: checksums of the checkpoint and manifest.

No game assets, DLLs, saves/unlocks, configuration, logs or credentials publish.
Unexpected checkpoint fields cause refusal pending review. The source revision
is the checkout **at capture**, not proof of the revision that trained historical
weights; that revision is marked unknown. Batch results are not independent
evaluation of the updated model. No release claims the >=35% goal is achieved.

The checksum-derived tag is a prerelease, not the latest software release. The tool
creates a draft, uploads, downloads/verifies all assets, then publishes. Published
releases are verified and reused, never overwritten. An interrupted draft can be
retried. Relevant uncommitted source blocks new export; push the capture commit
before publishing so GitHub can create its tag. Schema4 snapshots are roughly37MB each;
changed snapshots accumulate, with no automatic deletion policy.

Compatible schema4 snapshot (2026-11-17):
[checkpoint-e9a6e7cf40a7d0b5](https://github.com/notmike101/ai-plays-zombies-arent-real/releases/tag/checkpoint-e9a6e7cf40a7d0b5).
It contains policy c30d8dd4df23b6ce and Adam after a completed update; its batch
ended in planning timeouts, not wins. Schema3 releases are incompatible with
current4. Prefer a newer verified schema4 snapshot when one is available.

## Restore in an idle checkout

Choose an explicit release and download all three assets into one directory, e.g.
`sessions/download`. Using the configured helper, equivalent download syntax is:

```powershell
node D:/github-agent/identity.mjs gh release download CHECKPOINT_TAG --repo OWNER/REPO --dir sessions/download
.\local.ps1 checkpoint-verify --bundle sessions/download
.\local.ps1 checkpoint-import --bundle sessions/download
```

Replace helper path/tag/repository with your configuration. Public assets can also
be downloaded from the release page. Verification checks hashes and exact current
schema/weights/optimizer. Checksums detect changed files, not the trustworthiness
of arbitrary publishers; choose the intended repository/release.

Import refuses active training and any existing destination checkpoint. Preserve
an old checkpoint deliberately before restore; do not delete it just to satisfy
the command. Import atomically creates the destination without overwriting it.
Then run `local.ps1 check` and resume only when game/DLL/profile checks pass.
Weights/Adam resume, but board state, exact RNG/recurrent memory and unfinished
batches do not. Game copies separately use the full-availability training profile
authorized by the user; this unlocks options, not purchases, SP or placements.

Implementation: `scripts/checkpoints.py`; tests: `scripts/test_checkpoints.py`.
CLI reference: [GitHub release commands](https://cli.github.com/manual/gh_release).
