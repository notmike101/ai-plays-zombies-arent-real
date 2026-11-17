# Learning audit and implementation plan — 2026-11-17

Goal: improve reliable model-controlled play and learning without scripting strategy,
changing normal difficulty, or discarding the compatible policy checkpoint.

Milestone 1: reproduce repeated geometry after undo, make tool selection idempotent,
and verify input-order regression plus actual native receipts. All _arm/cast callers
must select the requested tool, including repeated identical actions.

Milestone 2: preserve credit through planning (no game time passes), retaining the
existing battle GAE parameters and reward objective. Test long planning prefixes,
terminal/timeout boundaries and actual PPO updates. Input/action schema stays3.

Milestone 3: separate dense infection cost, terminal reward, and timeout outcomes in
history; record the learning configuration in checkpoints/history. Replace stale
current design guidance with verified observations/actions, reward math, limitations,
and the evaluation requirements. Validate offline integration and a bounded live run.

Known starting evidence: run99adb97241d2 saved4 updates/8 records, then stopped on
missing geometry receipts. Session bbbff50f-BM-1-8 shows undo followed by safe_zone
cancel, then no committed geometry. Latest policyc42691fb23e296d7 is preserved.

Open model gaps to document: fixed coarse viewport, incomplete terrain/wall/health
information, no general refund/reposition/camera controls, no proven L1-L5 success.
Do not equate configuration availability or emitted input with execution receipts.

## Planning credit milestone
Old GAE used gamma=.99 and lambda=.95 for every decision: a TD residual60
steps away was weighted(.99*.95)^60=0.0252. Planning has no simulation-time
progress. GAE now uses gamma=lambda=1 for planning and retains .99/.95 in
battle. This preserves the future signal without purchase/cast/READY bonuses.
Tests cover0/20/60-step prefixes, battle discount and truncation bootstrap, and
a real optimizer step.14 learning tests pass. Higher planning-return variance is
a tradeoff; comparative gameplay improvement still needs multi-seed evaluation.
