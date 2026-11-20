# Why the policy passes up READY

## Legal opportunities and actual preparation

The newer-parent study 206952 had 22 planning timeouts across both phases and
arms. Every timeout included legal READY opportunities. The policy deferred
all 806 of those choices, with a decision-weighted READY probability of 0.75%.
Eight timeouts had no recorded blocker at the end. Fourteen ended in debt,
including four with excessive shelter land and four with an unfinished
gesture. A final blocker establishes that the board needed recovery at the cap.
Earlier legal decisions count separately. At each decision the mask also honors
modal dialogs, unfinished placement anchors and native polygon drafts.

All 22 timeouts had at least one native placement receipt with positive
civilian coverage during preparation, and 18 recorded a paid defensive
placement. Those receipts establish work completed at the time. A later edit,
refund or overlap can change the final board. The old timeout journals lack
final money, retained defenses and shelter occupancy. The two newer-parent
games that started each selected READY at recorded step 10. They had 0% and
24.85% native shelter coverage, $2,183 and $1,256 left, and retried with 5.00%
and 9.11% saved. Both had a deployed defense in the pre-READY snapshot.

The archived-parent study 207952 started all 32 training games and six of
eight frozen games. Both frozen timeouts included legal opportunities and
ended without a reported blocker. Across the six frozen starts, two had
positive shelter coverage (9.26% and 15.43%). Only one had an embedded defense,
a Gas Mortar on a board with 0% sheltered. The early starts at recorded steps
1, 2 and 5 included zero-coverage boards with $2,951–$3,111 left. One step-5
start did cover 15.43%, without an embedded defense. All six starts retried
below 10%. One outbreak overlapped earlier data. Both arms had zero eligible
natural finishes.

## What the logits say

Used 36 sampled READY-legal decisions from six real frozen episodes in 207952.
The recorded observation and incoming GRU state were used with the same mask,
recovered from the nonzero sampling probabilities. There were 58–74 legal
tools. Replaying each decision with the policy that generated it reproduced
the full distribution within 0.0000002 absolute probability and raw logits
within 0.000002. These are sampled decisions from actual rollouts. The alternate
checkpoints and zero-memory passes below evaluate those fixed inputs only.

| Frozen policy | READY probability | Median rank | READY probability with zero GRU memory |
| --- | ---: | ---: | ---: |
| Newer baseline | 0.50% | 20.5 | 0.83% |
| Newer cost | 0.68% | 18 | 1.06% |
| Archived baseline | 7.11% | 5 | 8.05% |
| Archived cost | 5.63% | 4 | 6.49% |

The low probabilities persist on identical observations and masks. Wall,
selection, hold and ability-purchase tools dominated different low-READY
checkpoints. Gate dominated the archived baseline. Removing incoming memory
raised READY probability somewhat in all four policies and left a large gap
between the checkpoint families. The learned relative scores are the direct
reason READY lost probability mass. The replay cannot identify which training
updates or observation features caused those scores.

## Did the delay cost help?

The newer cost policy assigned more probability to READY than its baseline
in all 36 common-state replays. In its own frozen evaluation, it averaged
0.76% per legal decision versus 0.35% for baseline. Neither started battle in
four attempts each. In the archived-parent study, the exact cost was verified
on all 16 candidate training episodes, totaling −0.436 across 218 deferrals
with zero recorded mismatches. Both arms started on every training round.
The candidate's mean READY probability was lower than baseline's after each
of the last six updates as observed in successive training batches. The final
frozen candidate averaged 5.16% versus 7.12% over legal decisions and had the
same 3/4 start rate. Candidate starts came earlier in this small frozen sample,
with zero embedded defenses on those starts. The cost did not reliably
increase readiness or produce better-prepared battles across the two parents.

## Remaining questions

Several timeout histories show real preparation and some repeated edits or
buy/refund cycles. Poor battle returns can make continued preparation attractive
to the learner. Planning truncations bootstrap the critic and expose no direct
terminal score. The model sees budget, draft and anchor state, civilian counts
and safe-zone membership by grid cell. It has no explicit aggregate civilian
shelter coverage or remaining decision budget. Which of these signals matters
requires a matched private comparison.

For a learning diagnosis, record READY odds, same-state legal competitors and
the realized planning return relative to the critic at each update. Evaluate
frozen checkpoints on fresh boards and report readiness alongside occupancy,
completed defenses, money and official outcomes. Test any new observation
signal in its own matched comparison. A change in start rate can otherwise
hide a shift toward unprepared starts.

The comparison journal now includes blocked decision counts and, at planning
timeouts, the final observed money, closed zones, walls, evacuation geometry,
defenses and civilian fraction inside the union of closed polygons. The last
measure is a planning snapshot. READY continues to use the separate native
outbreak receipt. Missing observations remain unknown. Replay and smoke
artifacts are private on D:.

In one read-only smoke run on inst19, frozen policy `980405fb8a4c1f69`
passed up READY on 40 legal decisions at 0.35% mean probability and made 20
decisions with READY blocked. It reached the cap with no recorded blocker,
$166.35, four closed zones covering 14.27% of observed civilians, 60 wall
segments, two Garrisons and one Gas Mortar. The native planning footer
corroborated $166 after rounding, two Garrisons and one Mortar. That run
confirmed real preparation and produced no official survival score. The
official outcome and qualification rules remain as described in
[the learning contract](ml-spec.md).
