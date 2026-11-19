# Shadow combat dynamics

The shadow model is an offline prediction experiment. The trainer, official
saved fractions, checkpoints, and Observatory do not consume its outputs.

## State and transition contract

A minimum candidate state for two-second crowd prediction is the camera-aligned
civilian, zombie and defender grids, total populations, simulation clock and
elapsed time. A combat-effect model also needs local infection/conversion state,
defenses and shelter geometry, terrain and hazards, ability stock/cooldowns,
gesture state, exact target geometry, and unresolved projectiles with type,
location and time to impact. Recent crowd movement or a short history is needed
where two frames with the same counts have different trends. The benchmark
tests only a subset of this state. It does not establish that the subset is
sufficient. Capture records population, stock, timing, and the observed grid
including building counts and shelter occupancy. Terrain, detailed static
defenses and authoritative in-flight entities remain gaps.
Opt-in context now retains defender-kind and local conversion counts,
wall midpoints, bounded shelter polygons, sampled terrain/bridges/fire,
hazard and mutation centers, and live helicopter positions. A null shelter
polygon list means the vertex budget was exceeded. These fields reuse the
native policy snapshot. Hazard centers do not describe affected footprints,
and helicopter positions and cooldown estimates do not track missile flight.

Opt-in `team_search.py --capture-shadow` exports schema 2 beside existing
samples. One episode identifies the copy, PID and process birth time, native
session and outbreak, board/map, policy weights and team, viewport and tool
ordering. Each state carries the camera and native tick. Camera-local grids
are not world-coordinate grids. The next decision's state is the resulting
state after elapsed simulation time. Automatic camera work can occur between
them, so readers must reject changed coordinate frames. Tail decisions without
a successor are explicit, zero elapsed time is retained, and caps are reported.

Each transition records the selected tool/cell, legal tool indices, the legal
conditional cell mask for the selected tool, and conditional cell masks for all
available combat tools. Unavailable combat actions are absent from those masks.
An available but unselected action did not execute. For casts, a gesture start
is distinct from an emitted attempt. A stock decrease confirms a spend. No
observed decrease is an unconfirmed attempt, and an outside-playable target is
an explicit rejection. Record dispatched pixel endpoints separately from the
selected cell. Native deployment timestamps and names supplement stock evidence;
neither by itself establishes impact geometry, kills or civilian survival.

## Bounded collection

At an idle launch boundary, run a bounded ordinary campaign search with
`--capture-shadow`. Keep the frozen base, normal game and reward receipts, and
use the existing model-controlled candidate search for timing, targeting and
reserve/decline variation. Capture regular and held-out waves. Check coverage by
outbreak, legal opportunities, target regions and actual receipts before
allocating further games. A completed three-shot salvo supplies one episode
of evidence, not three independent experiments. If a useful cast always occurs
at the same time, vary model proposal candidates or keep action effects unknown.
Future validation needs distinct outcomes for different legal commands in
comparable states, including legal waits. Deduplicate outbreak seeds and hold
out copies, entire outbreaks and policy variants before promoting predictions.

## 2026-11-19 retrospective benchmark

Run `scripts/shadow_benchmark.py <speed-comparison.jsonl> <forecast.pt>` using
the repository Python. The archived dataset has only coarse snapshots and
confirmed missile spends, so the experiment uses an actual future receipt
schedule as input. This is retrospective conditioning, with no knowledge of
counterfactuals. The cell is a screen selection and is only a proxy for the
impact. The archived CNN is an external baseline and keeps global totals
at persistence, since it has no global head. The new models hold out copies:
train inst13–15, calibrate inst16, test inst17–18. One of 24 battles lacked
one-to-one receipt/time correspondence and was excluded. No checkpoint is saved.

| Approx. horizon | Held-out windows | Persistence civilian / zombie total MAE | State-only MAE | Conditioned MAE | Conditioned zombie cell MAE | Conditioned hotspot regret |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 s | 181 | 80 / 105 | 48 / 81 | 57 / 79 | 5.10 | 2.10% |
| 4 s | 109 | 156 / 217 | 85 / 151 | 105 / 151 | 10.25 | 3.23% |
| 6 s | 83 | 229 / 329 | 127 / 209 | 146 / 233 | 12.97 | 6.25% |

One-step civilian cell errors were 5.27 persistence, 30.56 archived CNN,
6.85 state-only, and 6.53 conditioned. Zombie cell errors were 5.58, 34.01,
5.41 and 5.10. Hotspot regret is the fraction of the future peak zombie count
missed by selecting the predicted peak cell. It measures concentration,
not whether casting there helps. Of 181 one-step windows, only four contained
a confirmed new deployment. On these four, the conditioned global civilian
error was 97 versus 77 state-only. The test predicts population levels,
not official saved percentages or an attributable intervention effect.
On the same 83 complete three-step chains, conditioned civilian total MAE
grew 63 → 112 → 146, and zombie total MAE grew 78 → 155 → 233.

The calibration copy's worst civilian and zombie total errors were 597 and
718 after one step, rising to 1,118 and 1,578 after three. All held-out total
errors fell within these wide envelopes in this sample. A single calibration
copy and correlated windows cannot support a coverage guarantee. Decision
use is refused. Also refuse unaligned views, unseen actions or timings,
incomplete receipts, unsupported maps/conditions and horizons outside
validation. A usable gate will need calibrated errors on independent episodes
and action support, not just average count accuracy.

At idle priority with one CPU thread, the in-memory benchmark processed about
3,600–3,900 windows/s individually and 24,700–31,500/s at batch 64 across
two runs. The timed path covers
array conversion, feature and action-map preparation, forward pass and scoring.
It excludes parsing, window selection and live capture. The live six-copy
comparison delivered 83.5 scored battles/hour at 2×. These are different units;
the shadow throughput does not imply that valid simulated battles or PPO
trajectories are available at that rate.
