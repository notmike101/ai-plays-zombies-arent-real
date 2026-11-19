# ZAR Tracker (live state â€” update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-18 — campaign search and crowd-forecast comparison)
- 2026-11-19 00:07 Central. Safe-zone reward now counts
  a second exposure after the same civilian reaches another intact shelter
  and that shelter is breached. Continued exposure and overlapping failures
  count once. Logs report distinct exposed civilians and total exposures.
  A regression moved a civilian across both shelters and verified two
  penalties with one shelter credit. 200 trainer and 49 visualizer tests
  passed. Seed 101851 remained active and predates the correction.
- 23:56 Central. Game view now crops to the Windows client area and encodes
  higher-quality JPEGs up to 1280×960. The owned inst13 window measured
  1924×1247 in WGC with a 1920×1200 client area. Chrome on the named tunnel
  displayed the resulting 1280×800 thumbnail for game 55004, worker 33124.
  The crop helper took 0.49 s for a 250 KiB JPEG. All 47 visualizer tests passed.
- 2026-11-19 00:04 Central. Safe-zone reward live check completed on isolated
  inst19 PID 43856 and the test copy exited. Fresh L1 recorded 1,191 uniquely
  sheltered civilians (+0.007314), one occupied penetration exposing 1,080
  civilians (-0.013265), and official 9.62% saved. That verifies the new
  components in a real game. It does not establish a survival improvement.
  Pilot: analysis/coverage-shelter-pilot.json. Scope remains L1. Active
  supervisor seed 101851 predates the new reward and adopts it next block.
  199 trainer tests, 47 visualizer Python tests and the model check passed.
- 23:51 Central. Enabled screenshot sharing on the named observatory hostname
  and made Game view expanded by default. Listener PID 27652 (create time
  1795067420.3287635). Chrome displayed a real 800×519 public thumbnail for
  inst13 PID 55080 after seed 101851 started. Campaign training was active.
- 23:46 Central. Deployed opt-in Game view on observatory PID 28384
  (create time 1795067149.3525112). The screenshot helper captured actual
  planning and battle on isolated inst20 (800×519, 57–63 KB), and local
  Chrome displayed its thumbnail. The named public hostname returned 403
  for screenshots with sharing disabled. The test game was stopped after
  verification. Campaign training remained active. Visualizer suite: 46 tests.
- 23:44 Central. Audited two matched fresh L1 game logs for
  safe-zone defense. inst14 (seed 1918897396) and inst17 (seed 3529359300)
  started with 14.6% civilians inside zones. First logged breach points
  lined up with the northern edge of the recorded refuge (local y about
  1841.54) at 51.73 and 55.23 sim seconds. Neither spent battle stock;
  early retry scores were 9.84% and 9.20%. Native wall_breach logs are
  cell events and do not identify unique lost zones or track occupants.
  Training was active. Audit did not change reward or policy.
- 23:37 Central. Expanded seed 100851 from four to six concurrent
  L1 copies. Existing training still owns inst13–16 on CPUs 0–7, and supplemental
  trials inst17–18 (PIDs 45424 and 52500) are ready on CPUs 8–11. CPUs 12–23
  remain outside training. Five-second sample at six: 7.23 GiB available RAM,
  71.3% overall CPU, 99.7% on the training group and 42.9% on the reserved group.
  Do not expand to eight at this load. The auxiliary batch ends after the two
  results, recorded in coverage-team-05e4498c6c/extra-trials.jsonl for the next
  block. Original supervisor continues automatically. 194 trainer tests passed.
- 23:33 Central. Parallel capacity check. Four active L1
  copies under seed 100851, with 9.19 GiB available RAM and 9.95 GiB free
  disk at sampling. RTX 3080 reported 3,572/10,240 MiB VRAM in use, 41% GPU
  utilization. The supervisor allows 4/6/8 copies at 8/13/16 GiB available
  startup RAM, respectively. Historical batches have completed at eight,
  with UI receipt timeouts also documented at that count. No throughput
  comparison or change to the active count in this check.
- 23:25 Central. Restarted the observatory at user request. New listener
  PID 56924 (create time 1795065909.9419098). Local SSE reported one live
  stream, and Chrome over the configured named Cloudflare hostname showed
  a live Monitor and loaded Learning. Campaign training remained active.
- 23:17 Central. Diagnosed blank public Monitor. The Cloudflare Quick Tunnel
  returned SSE headers and zero event bytes in a 12-second check. The local
  SSE feed delivered waiting updates immediately, and public Learning returned
  HTTP 200. Seed 99851 was in its held-out batch, which does not enable the
  training observer. No game, trainer, visualizer or tunnel restart was needed.
- 23:21 Central. Continuous supervisor began seed 100851 on inst13–16.
  Startup log analysis/coverage-stage-search-100851.log confirmed Boston L1
  only. A qualifying L1 win completes the copy's current assignment. The
  operator, campaign search and PPO use explicit --allow-progression for
  L2–L5. The previous block finished before the automatic handoff. Verified
  193 trainer tests and 44 visualizer Python tests.
- 23:12 Central. Learning also works through the configured public Cloudflare
  hostname. Chrome loaded campaign results, 400 PPO outcomes and 60 updates
  over HTTPS. Public weight access returned 403. The new observatory listener
  is PID 36960 (create time 1795065157.2558768), and training remained active.
  The tunnel hostname is configured in ignored zar.local.toml.
- 23:12 Central. inst13 PID 56400 (seed 99851) reached L3 through earned
  advancement. Native footers show fresh L1 win 25.87%, same-board L1
  retry win 47.53%, then L2 win 36.68%. The first L3 attempt ended at
  the early retry cutoff with 9.01% saved. The L1 retry permits later-stage
  practice; it does not count as a fresh L1 qualifier.
- 23:09 Central. Learning now works through the observatory's direct LAN
  address or host computer name. The restarted listener is PID 51628
  (create time 1795064932.9065344). Localhost and the Ethernet address both
  returned 400 PPO outcomes and 60 update rows. Weight inspection still
  requires localhost. Campaign training was active after the listener restart.
- 23:11 Central. Fresh L1 cast-timing pilot on inst19/20 completed and both
  test copies exited. Incumbent 79deb3a2929af18a saved 28.15% (outbreak
  31240610); contextual candidate 1bf19fcc39377b18 saved 23.41% (outbreak
  1909286211). Both finished below 35%, spent three confirmed missiles and had
  one rejected outside action. Candidate spent missiles at 30.8/31.5/31.97
  sim seconds; incumbent at 141.33/143.60/145.00. Keep incumbent. Broaden
  search toward smaller gains and higher activation thresholds. Pilot log:
  analysis/coverage-cast-timing-pilot/holdout.jsonl. CPU training seed 99851
  remained active and reached an L2 battle on inst13 through a carry retry.
  Next search block includes the timing experiments, bounded targets and
  persistent stage-scoped prices. 192 trainer and 44 visualizer Python tests
  passed, along with model verification and the committed graph suite.
- 23:01 Central. Audit of completed candidate-only fresh L1
  records in seed 98851 (training 1/15 qualifying, holdout 0/4) and the
  first three generations of 99851 (0/17) found no L2 battle among those
  trials. Among 34 fresh L1 games with legal cast decisions, 16 had no
  recorded stock decrease. Two L2 native map read errors in seed 98851
  included one after a qualifying fresh L1. Live training was active,
  and the current processes predate the playable-target guard. The new
  boundary behavior needs fresh results before judging its effect.
- 22:50 Central. The ZAR Observatory is deployed at localhost:8765
  (visualizer PID 13632, create time 1795063696.7385316). The original graph
  is at /legacy. Only the visualizer listener was restarted. Training was
  active with campaign operators 45832 and 53896 after deployment.
  Live L1 game 54656 / worker 53524 matched the browser replay and runtime
  frame for revision d9e6f3c6341a6d3c. The worker predated the new matrix
  capture, which passed synthetic inspection. Schema-4 steady SSE dropped
  from about 244 KB to 34 KB on the fixture. See visualizer/README.md for
  browser timings, verification steps and the remaining telemetry limits.
- 22:46 Central. Timed production four-epoch CPU PPO updates
  with synthetic observations at representative historical episode lengths.
  Among 54 recent recorded battles with decision counts, median was 478.5
  and maximum 1,319. One update took 0.536 s at 478 steps and 1.629 s at
  1,319 steps (analysis/coverage-ppo-cpu-timing.log). Current campaign search
  has no PPO update. Keep it on CPU so the GPU remains available for rendering.
  The probe used the on-disk checkpoint as input and saved no weights.
- 22:43 Central. Checked GPU feasibility during active seed 99851
  on six copies. RTX 3080: 10,240 MiB total, 3,731 MiB used at sampling.
  Repo torch reports 2.15.0+cpu and CUDA unavailable. Policy is 3,096,810
  FP32 parameters (11.81 MiB). Single-observation CPU forward in a separate
  short probe was 0.169 ms median / 0.256 ms p95, compared with the 100 ms
  episode step floor. Campaign search uses a frozen GRU. Standalone PPO
  updates are the likely candidate for a separate GPU benchmark.
- 22:40 Central. Training seed 99851 advanced to generation 2 on inst13–18.
  Its workers predate the playable-target guard and the supervisor will load
  it on the next block. The guard rejects outside cast, placement and world
  targets before input, deducts .02 per attempt in PPO and charges the same
  cost in campaign ranking. Live inst20 L1 geometry classified 27 of 40
  HUD-safe targets as outside for missile, firebomb and police drop. The
  isolated copy exited after the probe. Episode tests verified both missile
  dispatch and reward/stock behavior (analysis/coverage-target-boundary-live.log).
- 22:18 Central. Verified continuous supervisor PID 49644 and enabled hold
  marker. Seed 98851 is in generation 4 of 4 on inst13–16. Three copies
  were in battle when sampled and inst13 had already logged its result.
  A candidate saved 35.47% on one fresh L1 outbreak in generation 3, then
  hit a native map read error in L2. The incumbent remains 79deb3a2929af18a.
  The supervisor will start the next block after the held-out evaluation,
  subject to its RAM and disk floors. About 10.4 GiB RAM and 10.1 GiB disk
  were free at this check. No restart was needed.
- 22:01 Central. Latest-camera fresh L1 comparison completed on full-profile
  inst19/20 with swapped copies; both pilot copies exited. Incumbent saved
  41.65% and 23.45% (one confirmed cast total). Cast-preference variant saved
  43.00% and 24.13% (six casts, all confirmed). Both qualified once in two
  distinct outbreaks; incumbent retained. Across these four L1 battles
  109/111 resting checks confirmed the boundary fit. One L2 run timed out
  after a zone took funds from 18.93 to -825.93; the other failed awaiting
  UI frames in stage 2. Evidence: analysis/coverage-cast-pilot-98851/holdout.jsonl.
  Continuous search seed 98851 launched generation 2 on four copies. Its first
  two generations supplied zero fresh qualifiers for the leading L1 policy.
- 21:45 Central. Supervisor recovered into seed 98851, four copies inst13–16
  in analysis/coverage-team-fad86c1af0. First completed incumbent battle had
  23/23 successful camera-fit checks, 9.73% at early abort. During deliberate
  repeated pan commands, live samples still saw a cropped boundary, so the
  next block also limits outward pan travel. On isolated inst12 in a real L1
  battle, one outward pan was legal, a second was masked, and the entire map
  remained visible. Vertical bounds after resting were 4.31–63.81% of the
  window (analysis/coverage-pan-boundary-live.log). Test copy stopped.
  Final prior-block pooled L1 result: 1/11 fresh qualifiers, mean 20.49%;
  held-out attempts 9.78%, 10.00%, 25.39%, no qualifiers. The first two
  sampled no cast despite 76/79 legal opportunities. Next block explores
  cast preference alone and reserves only one L1 carry-practice slot.
- 21:39 Central. The old selection block finished. Its selected variant
  scored zero qualifying wins on three fresh held-out L1 games (two early
  aborts and one below-target game win). An isolated inst12 live check moved
  the Boston boundary partially above the screen then restored the entire
  boundary in planning and battle (analysis/coverage-rest-view-live.log).
  Stage search now reserves L1 selection for L1 evidence, and standalone PPO
  separates optimizer updates and checkpoint files per stage. Old camera
  fitness is archived. Supervisor seed 97851 encountered a legacy trial
  without levels; resume now skips such rows before replaying prices.
- 21:33 Central. The eight fresh L1 attempts for the 40.35% policy prefix in
  coverage-team-d18fd6a8de yielded one qualifier and 19.74% mean saved/observed
  at abort. All eight distinct outbreaks began with 14.6% inside safe zones.
  Old selection split these by L2 genes and scored retries. Revised search
  pools fresh results, explores L1 variants, and gates promotion on a fresh
  head-to-head. The active supervisor adopts this at its next block.
- At 21:18 Central, six owned copies inst13–18 were in generation 2 of
  analysis/coverage-team-d18fd6a8de (supervisor log analysis/coverage-stage-search-96851.log).
  The latest selected team 2f70a627a7be4d51 won L1 at 40.35% and timed out
  in L2 preparation. The roster picker and negative final preparation budget
  remain the observed L2 failure modes. The budget-aware alternative is being
  evaluated. New search processes share measured prices across proposals.
  One adaptive refuge predicted 14.84% sheltered; the game logged 14.6%.
  Its three L1 wins were 16.94%, 23.27%, 36.75% (last two on retries).
- Published [checkpoint-ce43be030aab16a5](https://github.com/notmike101/ai-plays-zombies-arent-real/releases/tag/checkpoint-ce43be030aab16a5).
  Verified remote bytes and local restore of GRU 8a691469a829158d plus team
  2f70a627a7be4d51. The local six-hour sharing heartbeat was paused when
  checked. The user confirmed that it should stay paused. A second manual
  publication check downloaded and verified the existing release and returned
  `already_published` for the same bundle. Training remained active.
  New campaign processes also observe one candidate per generation. Synthetic
  SSE/reconnect, WebGPU/Canvas and mobile tests passed; verify the live
  composite stream at the next supervisor launch.
- At 20:20 Central, four copies (inst13–16) were training stage-specific
  layouts in analysis/coverage-team-674d66ed24. Check the operator for live
  PIDs. The ongoing supervisor is analysis/coverage-campaign-supervisor.ps1
  (hold marker analysis/coverage-supervise-hold); it carries forward the last
  champion and checks available RAM/disk before starting another block.
- Frozen CNN crossover finished: analysis/coverage-team-cda1c7a4b1.
  Current-count L1 wins saved 13.76%, 22.23%, 45.50%, 45.09%. The last two
  respectively early-retried L2 at 4.80% and 9.95%. CNN L1 won at 20.72%
  and 13.08%, early-retried at 9.51%, and lost one observation to a native
  snapshot race. Current counts remain the campaign-search default. The game
  logged Firebomb deployments even where immediate stock comparisons missed
  them. New builds retain session deploy events and synchronize geometry
  input before reading stock. Do not treat ongoing-alive percentages as wins.
- At 20:06 Central, the first layout search was finishing its held-out games
  on inst13–16. Both qualifying L1 victories recorded zero battle casts.
  Follow analysis/coverage-cnn-live.log for the paired targeting comparison
  and analysis/coverage-stage-layout-live.log for the next population. Both
  use the existing training lock. Search now records cast availability and
  stock decreases; the comparison offers the same seeded loadout purchase
  to both arms. Later-stage training can retry twice; held-out scores are
  single attempts. All 158 game-free trainer tests passed.
- Campaign search on four owned copies now uses a frozen GRU plus searched
  preparation sequences and battle target scores (base 8a691469a829158d).
  Normal fresh L1: archive-coordinate candidate 0a661f77aa805b14 won with
  43.07% saved and subsequently retried L2 at 9.93%. Candidate 14ca31b65bffd96e
  independently won L1 at 42.51% and also retried L2 at 9.93%. Other fresh
  trials won L1 below 35%; consistency remains open. These results preceded
  CNN deployment and later-stage layout adaptation. Native L2 dump confirms
  carried precise garrison locations. Results, purchased placements and seeds:
  analysis/coverage-team-ad8a484156/trials.jsonl. The archived L1 best badge is
  separate from the archived layout; only count scores from new live runs.
- CNN predicts two-sim-second future civilian/zombie grids from three count
  channels. Trained on 312 pairs from eight games, beat per-cell persistence
  for both channels on all three held-out games. Native collector and weights:
  analysis/coverage-crowds-20261118-192909. Paired gameplay comparison uses
  the same archived-layout champion and GRU with and without this forecast.
- 18:50 Central: production launch seed 20264050, eight games, four rounds,
  analysis/coverage-supervise-credit.ps1 and operator log
  analysis/nn3_operator_20261118-184409-875eb8.log. Supervisor recognizes
  isolated UI-frame timeouts and backs off worker count. Verify current PIDs.
  Revision 3 (96cd441) gives planning the full measured return. The delayed-
  outcome regression failed on revision 2 and passed on revision 3; 146 script
  tests passed. Original schema-4 policy/Adam resumed. First live update:
  eight early retries, 2,307 battle decisions, 57 with a cast available, 22
  cast actions including gesture starts, four confirmed stock decreases. Zero wins.
- At 17:27 Central the eight-copy production supervisor resumed (operator log
  analysis/nn3_operator_20261118-172747-0cddf2.log). Recheck live ownership.
- Sustained outcome: 32 training episodes per arm, eight PPO updates, then 16
  frozen evaluations per arm. Both recorded zero qualifying wins, zero
  discordant success pairs, exact one-sided p=1. Retain production dense head.
  Shared entered battle 16/16, dense 13/16 (3 planning timeouts). Every battle
  ended at early retry. Among battles, shared HUD percentages min/mean/max
  5.50/9.05/10.00, dense 0.64/8.07/9.92. Median simulated seconds to retry
  were 32.33 and 27.67 respectively. No natural battle endings in evaluation.
- Frozen decisions in battle: dense 3,238, shared 4,098. Among game logs
  matched by copy, round wall-time window and footer score/phase, 12 dense
  and 13 shared attempts recorded five and two native deploy events respectively.
  Partial log coverage; deployments exclude passive defenses.
- Evidence: original snapshot policy 01b03674c135ca3b; accepted training
  rounds 0-2 in analysis/coverage-spatial-ef2f839094 and rounds 3-7 plus
  all evaluations in analysis/coverage-spatial-92acc343c0. A clean boot
  retry resumed both Adam states from paired.pt. Earlier interrupted pilot
  coverage-spatial-3db79a6a49 had no evaluations and was excluded entirely.
  An offline interrupted/resumed update matched both sets of weights and
  Adam tensors exactly. Future trial summaries include native log header wall.
- Sustained L1 comparison protocol set before rollout: seed 87430, eight copies,
  eight PPO updates on four episodes per arm per update, then four alternating
  frozen rounds (16 paired policy seeds). Primary outcome is a confirmed game
  win with at least 35% saved. Use a one-sided exact paired sign test on
  discordant successes at 0.05 to advance the candidate to more levels.
  Treat a timeout as an unsuccessful attempt with unknown saved fraction.
  Report retry scores, survival and battle actions descriptively.
- Replayed the pre-change observer from 261e6ab and the current writer in
  separate eight-copy live batches. Both loaded policy 37379673093ca3d4 and
  its Adam state, used the same eight policy seeds, fresh L1 boards and active
  telemetry, and wrote private checkpoints. Measured boot through per-episode
  cleanup, PPO and save. Old: 234.88 s, 1,267 decisions, 258.80 sim seconds.
  Current: 229.28 s, 1,082 decisions, 242.87 sim seconds. Rates were 5.39 vs
  4.72 decisions per wall second. Episode throughput was 122.6 vs 125.6/hour.
  Different trajectories and one batch per writer preclude a causal speedup claim.
  Evidence: analysis/coverage-writer-live.log. The eight-copy production
  supervisor resumed at seed 20263410 (analysis/coverage-supervise-after-trial.ps1;
  operator log analysis/nn3_operator_20261118-152740-a751c6.log).
- Live comparison coverage-spatial-773232f51e forked policy 37379673093ca3d4.
  Each arm received four fresh Boston L1 trajectories, one PPO update, then
  eight fixed-weight evaluations with paired seeds and exchanged copies.
  Seven of eight reached battle in each arm; each had one planning timeout.
  Dense: six early retries, one loss, zero wins, HUD/terminal percentages
  min/mean/max 0/6.59/9.97, median battle 30.80 simulated seconds.
  Shared: seven early retries, zero wins, percentages 2.55/7.79/9.95,
  median battle 36.60 simulated seconds. Early retry scores precede a natural
  battle ending. Neither reached 35%. Keep the production GRU checkpoint.
  Private weights and per-episode results are in analysis/coverage-spatial-773232f51e.
- CPU transfer probe: run `.venv/Scripts/python.exe -B scripts/probe_spatial_transfer.py`.
  Three seeds, frozen checkpoint GRU, 30 training locations and 10 held-out
  locations. Dense and dense-plus-shared heads scored 0/128 held-out per seed;
  shared-only scored 128/128 each on the synthetic largest-cluster task. This
  motivates an isolated gameplay trial of shared tool-conditioned targeting.
  Hand-labeled probe targets must never be used as campaign rewards.
- Observer cached UTF-8 topology bytes and writes them directly. Alternating
  40 writes per method on a 5,117,864-byte real frame yielded identical bytes,
  median 12.68 ms before and 7.04 ms after. This measures local serialization
  and buffered file writes only. All 37 visualizer tests and graph checks passed.
- Architecture review: a tail sample of 175 revision-2 Boston L1 episodes had
  163 early retries, one loss, 11 timeouts and zero wins. Active training saved
  checkpoint 2c29005d6d100d63. The sample does not isolate a memory bottleneck.
  Keep the current GRU as the control. First compare a shared spatial encoder
  and tool-conditioned cell scoring with the same recurrent core. Measure
  confirmed saves, battle-entry rate and survival at fixed game times across
  comparable starts and experience budgets. Check delayed battle credit:
  gamma=.99 per .1 simulated seconds gives a 10-second discount of .366
  before trace decay. Test temporal attention separately if a memory diagnostic
  shows useful history beyond the GRU's reach. No architecture trial run yet.
- Trainer boot now applies its existing new-replay-companion retention guard
  (3cf5d59). Eight-copy start at 14:24:45 Central produced 24 retained .txt
  dumps and zero retained .state companions across boot and first episode setup.
  The offline boot and training-state suites passed (8 and 20 tests).
- At user request, archived 1,288 older ignored images and 189 older ignored
  binary replay companions, ~4.63 GiB total. Original relative paths, sizes and
  SHA256 are in manifest.jsonl under C:/Users/me/ZAR-archive, directories
  workspace-images-2026-11-18 and workspace-replays-before-2026-11-18.
  Verified copies before removing workspace originals. Tracked references,
  text receipts, active runtime, checkpoints and today's replay evidence kept.
- Active local supervisor analysis/coverage-supervise-20261118-zar-v4.ps1.
  Seed 20263170 run operator log analysis/nn3_operator_20261118-142445-e33e47.log;
  all eight owned copies booted and tiled. Last known saved revision-2 policy at
  check 8a78fbf74ee38406; this boot's first update pending at that moment.
  6.92 GiB D:free during battle at 14:28 Central. Revalidate identities before action.
- Latest reviewed stable cooldown cohort: ten batches, 54 aborted battles,
  four planning timeouts, zero interface errors. Median abort 32.58 game seconds,
  best 10% saved. No sustained survival improvement established.

## Prior snapshot (2026-11-18 — six-copy training continues)
- User asked to keep training until told to stop. Active local supervisor
  analysis/coverage-supervise-20261118-zar-v3.ps1 cycles fresh single-batch runs,
  tiles game windows at unchanged 1920x1200, and guards resource headroom.
  It uses up to six copies after eight-copy picker/HUD failures. Known transient
  failures trigger bounded restarts; unknown failures are surfaced for inspection.
- Starting at 13:28 Central, commits through a993d22 passed 143 script tests and
  three visualizer integration tests. Native map sampling verifies the header;
  stale HUD frames have a bounded retry. Unconfirmed picker failures are logged
  only as no-ops when native roster/perks/ability levels remain unchanged.
  That exact tool/cell waits five decisions before another retry.
- At 13:48 Central, four cooldown batches saved four updates, 22 aborted battles,
  two planning timeouts and no interface exceptions. Four episodes logged picker
  rejections; the largest repeated count of a single choice was two. The earlier
  verified no-op recovery had preserved one episode with 32 Bomber rejections.
- Latest verified checkpoint 2c0a082fb0050d44. New launch seed 20262960
  operator log analysis/nn3_operator_20261118-134801-fb3370.log. Revalidate
  current game and supervisor identities before changes. No win or improvement
  in civilian survival established. Learning revision 2 remains active.
- To hold at a clean boundary before changing live source, create the ignored
  analysis/coverage-supervise-hold file and wait for the supervisor and trainer.

## Prior snapshot (2026-11-18 — continued eight-copy training, learning revision 2)
- User asked to continue training and necessary modifications until told to stop.
  Local supervisor analysis/coverage-supervise-20261118-continuing.ps1 cycles
  fresh one-batch launches, tiles owned windows without resizing, and uses
  2–8 copies according to startup headroom. Known interface errors cause a
  bounded restart with fewer copies. Unexpected errors and resource limits stop it.
  For code edits, create ignored analysis/coverage-supervise-hold and wait for
  the current finite launcher to exit before changing live trainer modules.
- Earlier carry run saved two updates, then one native map read failed. Fresh
  baseline 44dd48abe913 saved 57067e5ab8bc3476 but reported a picker timeout.
  Commit 5f18c93 reads map segments together when bounded and rechecks the header.
- Learning revision 2 (484078e): battle GAE discount and trace now use elapsed
  simulation time. Zero-sim decisions no longer shorten credit. Exact schema4
  observations, outcome reward, weights and optimizer remain compatible.
  138 script tests, 37 visualizer tests, observer parity and graph checks passed.
- First revised launch: operator log analysis/nn3_operator_20261118-115030-b213f0.log,
  seed 20262330, inst13–20 tiled at 1920x1200. Verify live revision-2 update in
  analysis/nn_hist4.jsonl. Gameplay benefit and native race recurrence unverified.

## Prior snapshot (2026-11-18 — morning supervision complete, eight copies live)
- Supervised 08:24–11:31 Central. By the end of the final supervised batch,
  61 updates saved from 187 aborted battles and 3 planning timeouts.
  Best recorded survival 10%, no wins/advancement. Latest verified checkpoint
  1921d29a9dd3b01a. Morning median to abort ~31.2 game seconds.
- Two eight-copy batches finished, each with eight battles feeding one update.
  First took ~6.5 minutes including boot. No matched throughput experiment.
  Resource guards allow up to eight distinct preflighted copies, and preserve
  the shared eight-CPU cap. One episode per copy per batch was used at scale.
- User requested the games remain available to observe. Started an additional
  finite three-batch run at 11:33 Central, seed 20262260, inst13–20. All booted
  and were moved to a desktop-wide four-column/two-row overlapping grid,
  with 1920x1200 client size verified and no live resize. Resource sample after
  boot: 9.17 GiB RAM available, 8.01 GiB free disk, GPU 45%, 3860/10240 MiB VRAM.
- Operator log analysis/nn3_operator_20261118-113306-07c3fc.log; trainer log
  analysis/nn3_20261118-113311-774bb7.log. The local supervisor has exited; the
  finite extra run will finish normally. Revalidate process identities before
  interacting. Ignored analysis/coverage-tile-training.py can lay out the
  current owned game windows again, preserving dimensions.
- Native zoom evidence and decision-time discount hypothesis are below. Fresh
  launch restores a wide planning view; model controls subsequent zoom. The
  final three-batch run can carry close zoom after retry. No causal comparison
  of fresh vs carried boards or proof of improvement in survivability.

## Prior snapshot (2026-11-18 — morning training and four-copy trial)
- User requested further supervision, about 08:24–11:24 Central. Training resumed
  from ce8f55232bad6291. Two-copy run with two episodes per copy produced 24
  aborted battles and 6 updates in about 22 minutes. First one-episode-per-copy
  trial produced 24 aborted battles and 12 updates in about 24 minutes. Median
  game seconds to abort fell from 31.55 to 28.55; no causal comparison.
- 10% is the early abort threshold vicinity, not a win. Samples mostly record
  roughly 90% infections at abort. Earlier 11/44 versus later 50/52 episodes
  reached battle, but differing seeds and board carry prevent attribution.
- In one observed episode on each of inst13/inst14, game logs show 46/41
  pause-resume cycles and 2/1 deployments. Decision-based battle discount may
  distort credit for such timing actions; causal effects are untested.
- Four-copy guarded launch eec96b6 booted inst13/14/15/16, all sharing eight
  CPU slots, with 10.13 GiB RAM available and GPU 40% (point-in-time). Run
  0400c917186d operator log analysis/nn3_operator_20261118-101728-6044e8.log.
- Native logs showed all four first plans at zoom .5795; retries began at
  1.1292–2.6627 after the model zoomed in during battle. Second battles reached
  native zoom 8. The ignored local supervisor analysis/coverage-supervise-20261118-fresh.ps1
  waits for a clean exit then uses one batch per fresh launch until 11:24.
  No scripted camera actions. Check the board and checkpoint again at cutoff.

## Prior snapshot (2026-11-18 — three-hour training supervision complete)
- Supervised about 22:15–01:15 Central. At cutoff, the history recorded 67 saved
  PPO updates, 111 battles with aborted outcomes, 62 planning timeouts, and
  one native-read error. Best observed score 10% saved; no level advancement.
- Two-copy portion contributed 20 saved updates, 58 battles and 22 planning
  timeouts. This verifies shared updates from distinct game copies, not a
  controlled throughput comparison. Use local.ps1 train --copy inst14
  --extra-copy inst13 --rounds 6 to reproduce when idle.
- Latest verified checkpoint at cutoff 1013cc2dfe89e38f, run 53d3dd11419d,
  round 1. The last finite six-batch two-copy run was still active and can
  finish normally. Games 27232 and 34832, trainer identities via status.
  Operator log analysis/nn3_operator_20261118-010446-1dd8b3.log.
- The temporary local supervisor exited cleanly at 01:15 and will launch no
  further runs. Last sample 11.46 GiB available RAM and 9.71 GiB free disk.
  Both copies share the eight-CPU cap. Revalidate before intervening.

## Prior snapshot (2026-11-18 — two-copy training verified)
- Guarded parallel launch commit 8962417. Run 9b64abc585d8 booted inst13 PID 8908
  and inst14 PID 12620. Both produced battle episodes in the first batch and saved
  PPO checkpoint 7db4fd7372d5b1f2. In batch 1, inst13 supplied two battles while
  inst14 timed out twice; PPO saved 52926148d65dc039. No throughput A/B measured.
- Parallel operator log analysis/nn3_operator_20261117-235544-f6f118.log; trainer
  log analysis/nn3_20261117-235548-c6df3c.log. Local ignored supervisor
  analysis/coverage-supervise-parallel-20261118.ps1 checks until 01:15 Central.
  It only starts another finite two-copy run after a clean exit.
- A single-copy battle stopped on native tick races. Commit cb6c1f2 moved the
  tick check earlier and increased bounded read retries from 5 to 12.
  Native reader tests (11) and two-copy operator tests (16) passed.
- Revalidate PIDs with local.ps1 status before acting.

## Prior snapshot (2026-11-17 — supervised training on inst14)
- At about 22:15 local, started 360 batches, two episodes per batch, seed 20261169,
  from saved policy d1c3c6c59e43a31d. Game 33244 reached verified planning.
  Operator log analysis/nn3_operator_20261117-221502-1ffbf2.log; trainer log
  analysis/nn3_20261117-221505-5382b5.log. Revalidate identities via local.ps1 status.
- Prior run fbda0049da2f timed out over budget with a modal open. The modal
  prevented the next episode's initial F6 dump. Commit fb54d2e allows one
  additional model decision to resolve a modal at the planning limit.
  Script suite (136 tests) and visualizer integration (3 tests) passed.
- Supervision uses the ignored local script analysis/coverage-supervise-20261117.ps1
  through 01:15 Central on November 18. It runs one finite batch session at a time,
  restarting with a fresh board and preserved checkpoint after six consecutive
  planning timeouts sharing a land or budget blocker. A matching known modal
  start failure can be retried. Unexpected failures stop supervision for inspection.
- First supervised restarts validated in logs. Through about 22:42 Central, the
  session saved 23 updates across five runs. Thirteen attempts reached battle,
  with best saved fraction 10%. Timeouts repeatedly involved budget debt.
  No campaign advancement observed. Check current identities before intervention.


## Prior snapshot (2026-11-17 — planning timeout diagnostics added)
- Training idle at check. Latest inspected run a0edb1da145e saved six PPO updates
  and had 12 planning timeouts. Last checkpoint c07d20bcea16a40b.
- Planning timeout history now separates land, budget, and UI blockers.
  Training-state (18) and visualizer integration (3) tests passed.
  Live diagnostic output is unverified. Reward and schema remain compatible.
- Revalidate previous process observations below before acting.

## Prior snapshot (2026-11-17 — post-fix battle update saved)
- Scheduled sharing check 2026-11-18 03:02 UTC (2026-11-17 local): published
  checkpoint-8cd35915e548c51c, policyb3cb363529189588, runb5ffb8d56db5.
  URL: https://github.com/notmike101/ai-plays-zombies-arent-real/releases/tag/checkpoint-8cd35915e548c51c
  checkpoint-publish downloaded and verified remote checkpoint/manifest/checksums
  before publishing; command returned ok=true,status=published. Only this tracker
  was edited. Training/visualizer state was not rechecked or changed by sharing;
  live-state facts below remain their previously dated observations. No new claim
  about gameplay strength or continuous monitoring.
- Normal-campaign mechanic catalog integrated:185 tools/4889 inputs,all16 units,
  19 abilities,8 perks,editing/HUD/environment controls. Coverage/proofs and native
  disabled/conditional branches: notes/mechanics-coverage.md. This is interface
  coverage,not exhaustive combinations or evidence of the35% objective.
-135 script tests,37 visualizer tests,12-step exact observer/policy parity,Node
  graph,4889-input browser SSE/reconnect/pause/isolation and mobile WebGPU/Canvas2D
  passed. Final12 fixed-policy diagnostic rollouts completed:4 battle (normal2x/4x),
  8 planning timeouts,no interface exception. No optimizer/checkpoint writes there.
- LIVE production runb5ffb8d56db5,inst14 game33804(created1794962209.28102),
  trainer36516(1794962298.8164513),worker28984(1794962300.9953175),launcher8156
  (1794962209.0816593),operator38968(1794962205.2084763). Venv redirectors23604,
  13192,33360 also appear. Revalidate via local.ps1 status. One game,below-normal,
  CPU0-7,200 batches of2,seed20261153. Round0 completed:aborted battle6.31% saved atsim74.60s,then
  planning timeout. PPO saved bf985cae9aa3606b. Last sample:r1/ep0 planning,
  sequence31,real4889-label frame,no warning,ancestry verified.
- Operator log analysis/nn3_operator_20261117-183645-a7dd17.log;
  trainer log analysis/nn3_20261117-183649-f8d399.log;history analysis/nn_hist4.jsonl.
  Ten saved schema4 updates verified across these runs; source policy
  c30d8dd4df23b6ce/Adam was resumed and latest is bf985cae9aa3606b. Earlier training batches timed out in planning,
  saved_frac=null,reward0. These are not wins. Track actual battle results/updates.
- Earlier failures:select_add while armed fixed by shared disarm; old fixed-roster
  preflight now accepts known seven-slot rosters/empty slots. Native armed->add/
  move/reaim and click/paint transitions passed. A whole-world tick guard failed at
  accelerated battle speed: now only parallel unit arrays require matching ticks;
  independent systems retain bounded validated reads and may span ticks.
- One missing initial F6 dump did not reproduce in12 follow-up rollouts. Added one
  bounded retry only in an unobstructed game world; blocked UI is not dismissed.
  Live fault injection dropped first request and recovered on second. Persistent
  failures still stop and now report phase/modal/menu state. Cause of the original
  one-off miss remains unconfirmed; retain this limitation when assessing reliability.
- sessions/nn_policy4.pt retains weights and10 Adam states. Source3 SHA256
  c78e1635664667f32153479d6cf0ea33e12dfb6c5a8143a58490cd37609fa6f0 is preserved.
  Migration explicitly corrects false +alive-helicopter stock semantics. Superseded
  initial migration is ignored sessions/nn_policy4.pt.pre-stock-correction.
- Visualizer6716(created1794957272.1076765),port8765 reused. Final-size browser
  worker44888/game40284 inputs/actions matched10frames. Warm forward~0.2ms/plain,
  ~0.5ms/observed;60 planning decisions14.24-14.46s. Browser receive133-375ms,
  median274;two-RAF display248-667ms,median378. Viewer<=5Hz; action mix/load mean
  these are scoped measurements,not a controlled before/after speedup claim.
- Compatible checkpoint-e9a6e7cf40a7d0b5 published,remote assets downloaded/verified;
  policyc30d8dd4df23b6ce and Adam. Six-hour changed-only sharing remains active.
  See notes/checkpoint-sharing.md. No game assets/DLL/saves/logs publish.
- Latest resource sample:10.6% systemCPU,11.6GiB available RAM; preceding GPU0%,
  2960/10240MiB VRAM. Startup guards are not continuous quotas. Keep one game.
- All owned diagnostic games,preview8766 and browser test sessions closed. Final
  diagnostic37776 was verified gone. inst13 remains a diagnostic copy,fresh L1;
  imported L5 fixture was never used for learning. Original progress backup:
  analysis/coverage-inst13-before-l5.progress. Installed game remained read-only.
- All source/docs changes committed conventionally and pushed at milestones.
  Preserve unrelated policy2/history2 dirt and old untracked analysis files.
  External Ghidra Java2316/45920 belong elsewhere. No subagents used.

## Prior snapshot (2026-11-17 — isolated Python environment verified, training LIVE)
- New .venv created with Python3.14.4 x64, include-system-site-packages=false;
  installed requirements.txt (torch2.15.0+cpu,numpy2.4.6,psutil7.2.2,
  pefile2024.8.26,Pillow12.3.0). Direct dependencies pinned, transitives resolved
  by pip. pip check PASS. .venv is ignored; README explains recreation.
- local.ps1 and visualizer/start.ps1 default to .venv\Scripts\python.exe; no
  activation or user-specific interpreter path needed for future launches.
  Existing trainer/server remain on their original global Python, untouched.
  Windows venv redirector ownership fixed/tested in local_agent.py: child owns
  socket, Python children may use either venv or base exe, own operator ancestors
  are not competing trainers. Unknown process/identity checks remain enforced.
- Validation:97 Python tests PASS (15 operator,47 trainer,35 visualizer),12-step
  exact policy/observer parity and sampled decisions,Node graph PASS. Actual venv
  checkpoint/game preflight PASS. Both visualizer launchers started/served/stopped
  isolated servers; all test server/redirector/shell processes cleaned,8766 closed.
  Initial redirector test failure reproduced then fixed; no extra game was booted.
- Production identities unchanged: launcher25848(created1794944254.8318655),
  trainer28856(1794944344.6409335),worker31408,inst1 game22828(1794944255.099634),
  visualizer22604(1794931712.9690397) on8765. Revalidate before acting.
- Run b39316bdad21 latest observed update round43 checkpointed8a80ca2ff1ea9e;
  last battles7.59% and9.76% saved, both aborted. Objective remains unmet.
  Fresh battle frame sequence44,worker31408/game22828,age0.77s,preview=false,
  332 labels,no label warning. Logs remain analysis/nn3_learning_audit_20261117.log
  and its launcher log/.err. RAM14.46GiB available,D:12.32GiB free at final sample.
- Next session: local.ps1 status -> check; preserve active training; reuse
  visualizer-start. Next normal train launch uses .venv automatically. Never
  reinstall/recreate an environment while workers use it. No continuous monitoring
  after this chat. No live training restart under .venv was performed; offline PPO
  and checkpoint validation passed. Deployment still Windows/D:\zar-scratch with
  local supported game copies/input DLL/checkpoint and local contribution helper.
- README,AGENTS,operator-runbook and local-environment now document setup and
  remaining portability limits. Evidence: notes/local-agent-plan.md. Existing
  unrelated policy2/history2 and old untracked artifacts remain untouched.

## Prior snapshot (2026-11-17 — guarded local agent commands deployed, training LIVE)
- New entry point: .\local.ps1 status/check/train/visualizer-start/train-stop/
  visualizer-stop. README+AGENTS direct new agents to these commands; runbook
  shortened around them. notes/local-environment.md records known Python,
  packages, local artifacts, contribution helper and recovery. Implementation
  evidence/decisions: notes/local-agent-plan.md.
- Existing production run b39316bdad21 left running, unchanged identities:
  launcher25848(created1794944254.8318655),trainer28856(1794944344.6409335),
  worker31408,game22828 inst1(1794944255.099634). Seed20261140,eps2,rounds200;
  below-normal,CPU0-7,normal difficulty,low graphics. Revalidate PIDs before use.
- Latest observed update round33 checkpoint18675e77dfb089fb. Last pair: planning
  timeout(saved=null), aborted battle8.74% saved. Model objective remains unmet.
  Logs remain analysis/nn3_learning_audit_20261117.log and launcher log/.err.
- Production visualizer22604(created1794931712.9690397),port8765 reused normally.
  Fresh real frame worker31408/game22828,planning,sequence12,age1.44s;332 input
  labels,no label warning,preview=false. Worker ancestry matched trainer28856.
- Validation:13 offline operator tests PASS. Read-only actual preflight PASS for
  exact schema3, learned weights+10 Adam states, dependencies, supported inst1
  executable hash and x64 DLL/export. Actual duplicate-training call refused.
  Isolated server29688 on127.0.0.1:8766 started/reused/served HTTP/rejected stale
  identity/stopped; port closed. Production process identities remained unchanged.
  PowerShell wrapper/check/reuse, documentation syntax and links PASS. Disposable
  process verified below-normal and CPUs0-7. All temporary test processes cleaned;
  no extra game or preview launched. Tests never target live games for control.
- Latest headroom sample:CPU8.8%,GPU38%,RAM14.33GiB available,
  VRAM3215/10240MiB,D:13.09GiB free. Samples are not continuous resource guarantees.
  New wrapper uses one copy, at most8/half available CPUs, below-normal priority,
  minimum4GiB available RAM/2GiB disk at launch; no continuous GPU/RAM cap.
- No changes to loaded trainer/environment/observer modules or reward/schema.
  No real train-stop/restart test while the original run is healthy; wrapper launch
  and limits ordering tested with fakes. No Qwen trial or portable-install claim.
  Wrapper refuses a different checkout while trainer ROOT remains hard-coded.
- Next session: status -> check -> preserve healthy run; visualizer-start reuses
  server. If idle, train --rounds N resumes existing weights/Adam; inspect operator
  log and first completed update. Stop requires fresh PID+create_time. Review
  ml-spec before model changes; outstanding observation/action/parallel-injection
  gaps remain. No claim of continuous monitoring after this chat.
- Existing unrelated policy2/history2 modifications and older untracked run
  artifacts remain untouched. New runtime operator logs/lock are ignored.

## Prior snapshot (2026-11-17 — zero-context handoff verified, training LIVE)
- Fresh-clone review (2026-11-17): recommendations only; no runtime/source
  changes. Confirmed hard-coded trainer/env root, no Python dependency manifest,
  source-only Rust hook DLL, tracked legacy checkpoints versus ignored schema3.
  Proposed next milestone: portable paths+locked setup+read-only preflight,
  followed by game-copy setup and a versioned compatible checkpoint package.
  Existing synthetic preview/fake-game fixtures can support game-free onboarding.
  Runtime observations below remain the previous handoff's samples; not rechecked
  during this documentation review. Clean-environment install remains untested.
- Entry points: root README.md -> AGENTS.md -> notes/operator-runbook.md ->
  this CURRENT STATE -> notes/ml-spec.md. Runbook has checkpoint preflight,
  resource-limited resume, server reuse/start/stop, guarded process cleanup and
  a new-session prompt. Current weights/copies are local, not supplied by Git.
- Documentation-only validation: all7 PowerShell blocks parse; all3 embedded
  Python blocks parse. Actual dependency/checkpoint preflight PASS. Isolated
  hidden server on127.0.0.1:8766 served /api/state; documented guarded stop PASS,
  test PID16748 exited and port closed. Initial guard rejected Windows conhost;
  corrected to allow only the same Python exe or system32/conhost descendants.
  No test game or preview was launched. Actual training stop was NOT exercised.
- Production server22604 (created1794931712.9690397) remained on8765. Fresh real
  worker31408/game22828 battle frame sequence47:332 input labels,no label warning,
  preview=false. Training/game/server identities unchanged across lifecycle test.
  No Qwen/new-agent trial was run; this is a tested runbook, not a model guarantee.
- Prior run99adb97241d2 ended after4 updates/8 records (6 aborted battles,1 timeout,
  1 interface error); launcher/game cleaned. Latest checkpointc42691fb23e296d7.
- Root cause reproduced: undo leaves safe-zone tool selected; its hotkey toggles
  it off. Fix542f54f makes _arm/cast cancel then reselect. Live repeated-zone proof.
- Learning fix7a5f2bf preserves battle credit across planning with gamma=lambda1;
  battle remains .99/.95. No reward bonuses or model architecture/schema changes.
- Reporting8bb6904 records reward components and learning revision; timeout saved
  is null with separate observed snapshot. Updated ml-spec explicitly lists gaps.
- Tests:82 core Python+additional input checks PASS,12-step observer parity and
  Node graph PASS. Live30-decision rollout+isolated PPO PASS, user checkpoints
  byte-identical; probe26456 cleaned. See notes/learning-audit.md.
- Active runb39316bdad21: launcher25848,trainer28856,worker31408,game22828(inst1).
  Resumed schema3 policy/Adam; seed20261140,eps2,rounds200. BELOW_NORMAL,CPU0-7,
  low graphics,normal difficulty. Latest observed:8 updates through round7;
  checkpoint842fdf1aff8a0d80. Latest pair: planning timeout(saved=null), aborted
  battle9.90% saved. Objective remains unmet. Checkpoint preflight confirmed
  saved policy+nonempty Adam state, schema3, learning revision1.
  Creation times: launcher1794944254.8318655,trainer1794944344.6409335,
  worker1794944347.6272433,game1794944255.099634. Revalidate before using any PID.
- Latest headroom sample:CPU16.8%,GPU37%,RAM14.10GiB available,
  VRAM3253/10240MiB,D:13.20GiB free. Samples are not hard GPU/RAM caps.
- Logs: analysis/nn3_learning_audit_20261117.log and
  nn3_learning_audit_launcher_20261117.log/.err. Native replay cleanup remains active.
- Training left running with per-batch checkpoints and launcher cleanup on exit.
  No claim of continuous monitoring after this chat. Next review later outcomes.
  Unresolved: exact recurrent continuation, richer carried-board state, missing
  refund/repair/reposition/detonation/camera actions, parallel injection failure,
  and consistent fresh-board >=35% outcomes on all5 levels.

## Prior snapshot (2026-11-17 — training improvements complete)
- All four implementation milestones completed. Latest code092552d; earlier
  milestones a20786a/5dd479f/804fdd9/e3e042e; regular conventional commits.
- Final77 Python tests PASS; model parity12 recurrent steps and Node graph PASS.
  Browser SSE/reconnect/pause/preview-isolation and WebGPU/Canvas2D mobile PASS.
- Owned live inst9 PID12724/worker10300:8 sampled decisions, actual saved1.95%,
  aborted promptly, one PPO update changed weights and saved validation-policy.pt.
  This proves functionality, not strong play. No long training run is active.
- Separate12-decision greedy carry evaluation: planning timeout, zero terminal
  reward; validation and original checkpoints byte-identical before/after eval.
- User policy2 SHA bd97460bfefa468c0c3564936cf9fcd74d390cf2c4d33bcccc34716e7df230ed
  remains unchanged. sessions/nn_policy3.pt does not yet exist; new schema needs
  fresh training. Smoke weights only: visualizer/runtime/validation-policy.pt.
- All owned game copies, validation workers, preview8440 and test browser closed.
  Final psutil inventory: no game-copy PIDs. Existing visualizer server retained.
- Pre-existing policy2/history2 changes and analysis run artifacts are untouched.
- Full evidence, commands and limits: notes/training-improvements.md. Runtime
  captures remain ignored under visualizer/runtime, including browser/mobile logs.
- Follow-up work: sustained training and fresh-board multi-seed L1-L5 evaluation;
  no claim yet of consistently saving35%. Full wall/obstacle/health encoding and
  exhaustive live testing of every ability remain outside the verified subset.

## Prior snapshot (2026-11-17u â€” kit8 PPO run live on 5 fresh boards)
- RUN: train_run.py --copies inst1 inst2 inst4 inst5 inst8 --eps 2 --rounds 14
  -> analysis/nn2_train_kit8.log (bg_246). Boards = zar_boot fresh L1 (planning
  barrier PASS before trainer). Warm start = kit6 checkpoint (committed parent).
- PROVEN THIS RUN (pids 12612/47012 probes, killed): zar_boot fresh-boot works
  (~95 s to planning incl 75 s welcome); scripted garrison drags spend REAL money
  ($58-63/unit, receipts ok); L1 naked+3-garrison board = TOTAL loss ~5 s wall at
  8x (zomb 1447->8033 vs civ 8142); R-loop PERSISTS purchases+budget across losses
  (money 2935.80 + garrisons present in post-R dump) -> accumulation legit; kit
  {0:1} Police buys NOTHING on fresh L1 (SP-starved, DECK EMPTY expected early).
- NEW TELEMETRY (b470a84): hist rows now carry nbuy/ndeck/spend. First smoke row
  (pid 45772 r0): nbuy 5, spend $735.60, ndeck 0 -> random policy DOES build.
- kit5/6 post-mortem: t=6 wall + money-stuck-3111 ERR lines = modal-wedged boards
  wasting episodes (pre-zar_boot boards); accumulation was UNMEASURABLE then.
- Monitoring: after ~3 rounds check kit8 log for battle lengthening (t>6) and
  hist nbuy/spend growth = accumulation; if round 13 meanfrac still 0 with
  spend>0, escalate: reward/curriculum change (skill: score mid-state, boards
  carry via R). BC-warm start still queued after defense signal exists.
- Visualizer server 22604 up; stale preview demo killed; no other agents' workers.
- Live follow-up PASS: isolated inst9 normal Boston L1, game PID 38408 and
  evaluation worker 10824, current checkpoint. Captured 15 planning frames;
  browser LIVE, 32 displayed inputs, sampled action and history verified against
  SSE and the corresponding worker file. Initial civilian/money features matched
  actual game counters. No source changes required. Details: visualizer-live-check.md.
- Both test PIDs stopped; no game-copy processes remain. Checkpoint SHA-256
  unchanged. Browser returned to Connected / WAITING FOR WORKER / zero inputs.
  Normal server 22604 remains available. This proves planning attachment, not a
  full battle. Recursive deletion of the new inst9 copy was blocked by automatic
  approval review ("blocked by policy"); idle files remain, no bypass attempted.
- User clarified observation-only visualizer, delegated implementation choices,
  and authorized guidance updates and push. Implementation through e5da13d pushed
  to origin/main; final tracker/plan completion accompanies it in the next commit.
- Browser uses persistent SSE /api/events; /api/state remains diagnostic. One
  shared 200 ms file cache serves all clients, sampled even without viewers.
  Server retains 200 compact decision summaries globally, displays latest 50 for
  the selected stream, replays retained list on reconnect, resets on restart.
  Inputs/outputs remain actual observer data. This is sampled history, not durable
  trainer stdout or complete decisions, and never proof of game action execution.
- Current observation values and decision history are in the Inspector; Pause
  freezes the view only. Preview isolation, reconnect topology and idle status
  are maintained. At most 16 SSE viewers, with 3-second socket write timeout.
- Full visualizer suite: 35 tests PASS (including new stream/history tests).
  Existing eight fake-game integration/watchdog failures were caused by missing
  newer loadout interfaces; fixtures updated, original assertions preserved.
- verify_model.py PASS: actual PolicyNet2, 32 inputs / 72,915 parameters; exact
  outputs and sampled decisions for 12 recurrent steps. Warm CPU medians 0.085 ms
  plain / 0.160 ms observed (not end-to-end latency or game performance).
- Node graph assertions and JS syntax PASS. Chromium SSE/no-polling, reconnect,
  pause/resume, worker switch, 32 displayed inputs and preview isolation PASS.
  WebGPU/Canvas 2D and mobile portrait/landscape/touch checks PASS; physical mobile
  devices untested. Self-review performed without subagents, per repo rule.
- Normal visualizer server PID 22604, port 8765, deployed from D:/zar-scratch.
  Old server 5624 replaced; test server 29832 and synthetic preview 45212 stopped.
  Final browser smoke: WAITING FOR WORKER via SSE, no decision history. No game
  processes found by psutil executable-directory inventory. No trainer/observer
  source, policy, game process, game install or real input was changed.
- Evidence (ignored): visualizer/runtime/stream-python-check.log,
  stream-browser-check.log, stream-mobile-check.log, stream-decision-log.png,
  stream-mobile-artifacts/ and stream-browser-artifacts/. Unrelated training
  logs/checkpoint changes remain unstaged. Server log/error files are runtime-only.

## Prior verified state (2026-11-17 â€” deterministic interface complete)
- Interface only: no ML/trainer source changes, subagents, console commands,
  physical cursor input or game-install writes. Unrelated training artifacts
  remain uncommitted and untouched by this work.
- v3 client-coordinate/Win32 ABI defects fixed. Mouse actions use VirtualInput
  polling/cursor plus one posted edge sequence. Raw-only claims were contradicted
  by isolated tests and REA/Ghidra WndProc analysis; raw is movement compatibility.
- TWO consecutive final mouse acceptance cycles PASS:
  analysis/interface-20261117-094110.log (PIDs 25820, 5804, both killed).
  Each: fresh L1 $3111/8142 civilians, READY NO click, exactly one garrison,
  22 polygon walls + one wall, zoom +/-1 with zero anchor drift, battle, R retry.
- FINAL FOUR-COPY mixed-layout proof PASS: analysis/interface-scale-final.log.
  inst1 30368 (unfinished campaign START OVER), inst2 43040, inst3 9604
  (3840x2160 fullscreen), inst4 17872; all four coexisted in planning at $3111.
  All four killed. Temporary inst1 progress and inst3 settings restored.
- CONTINUE API PASS in windowed/fullscreen: analysis/interface-continue-final.log.
  PIDs 11212/7560 resumed L5 planning with 209867 civilians, then were killed.
  Uses a temporary existing unfinished checkpoint; original progress restored.
- Eight offline Python checks + one native ABI/layout check PASS:
  analysis/interface-unit-tests.log. Scoped git diff whitespace check is clean.
- All game processes now absent (including stale copies named in the handoff).
  Final inventory, DLL hash, settings restoration and badges: analysis/interface-cleanup.json.
  inst1..4 retain badges 39.23/34.31/21.14/13.69/7.91; no badge repair was needed.
- Limits: English/UI scale 1, calibrated clients 1920x1200 or 3840x2160. Boston
  fresh stage1 and CONTINUE for partially cleared campaigns (1-4 badges) only.
  Other destinations/sizes fail loudly. Zero-badge/completed CONTINUE is rejected.
  Fresh dump economy is authoritative; unchanged env.money can read a stale mirror.

## NEXT STEPS
- Open/refresh http://localhost:8765. Real attachment has now been verified once;
  the server waits because the isolated test worker was deliberately cleaned up.
  Continue checking fresh real frames/labels after future integration changes.
- Use AGENTS.md and visualizer/README.md for current streaming maintenance;
  older PLAN.md polling/integration-branch sections are explicitly historical.
- No interface acceptance work outstanding. Future build/layout changes require
  calibration and fresh live checks; source/menu matrix is notes/automation.md.
- Reuse scripts/zar_boot.py for owned copies. Successful API callers own cleanup;
  the CLI and acceptance test clean up automatically. No games are left running.

## VERIFIED CAPABILITIES (condensed; details notes/automation.md)
1. Parallel unfocused copies; virtual input per instance (DLL): clicks, keys,
   wheel, admin console, HUD/menu clicks, dialogs; PrintWindow shots (planning).
2. Memory channel: civ base+0x650f10 zomb+0x650f18 police+0x650f20
   corpses+0x650f28 conv+0x650f80 (i64), money f32 0x6563c0/0x65d9c0/0x665ef0
   (env_zar set_direct; battle-verified vs HUD to 1%).
3. F5 = 8x battle speed (vk 0x74 sc 0x3F). heli watchdog hot_spot() = green
   blob hunter (2-tuple px ints).
4. Episodes: harness + CEM legacy baselines A/B/C ~0-0.19%; scripted L5 WIN x2
   bronze 6.90/7.91 (sessions/checkpoints/inst2-WIN-*). Badges: L1 39% emerald,
   L2 34% diamond, L3 21% silver, L4 13.69 silver, L5 7.91 bronze.
5. Board clone = copy steam_cloud/plans/*.prep; progress resume_* file edits.

## THE SCRIPTED L5 RECIPE (reference dataset for BC; bronze 6.90 it17)
Conversion-snowball race. Won via: carry board (95 garrisons/39 mortars/15
snipers + CTA/Command_Post/Police/Repair/Radio trades -> Militia #2 killer
50.7k), t=0 heli sweep of 6 outbreak sites, burn kit early, then heli
redeploy every ~6 s onto densest contact cluster ALL BATTLE (micro-control
stops conversions; civ curve flattened at 31% alive); mortars 52.7k kills
until ammo dry. Badge % counts SAVINGS (in-zone/evac), not alive. Zones over
dense crowds + Battleship water AOE = path to silver. (notes/game-rules.md)

## SAFE-ZONE / DIALOG MECHANICS (user-confirmed + en.lang)
- Zone tool: click perimeter points, close loop with Enter; fee ON CLOSE
  (L1 800x760px = $1155); land cap L1 30%. Select zone wall -> X -> YES(X)
  refunds. Dialogs accept virtual posted clicks or keys: YES(X)/NO, OK=Enter, ready-short YES=SPACE,
  ESC=NO (2nd ESC=pause). F6 writer frozen while dialog/menu up.

## EVIDENCE / PATHS
- Screenshots: analysis/*.png (gitignored): win2-791.png, deck_probe4.png,
  after_startover2.png (MAP COMPLETE campaign screen), epfail_<pid>.png.
- Ghidra Evidence: analysis/nzstate_trace.json (state-dump writer
  0x140015d00, "NZSTATE1" @0x1405376e8); Ghidra 12.1.4 D:\ghidra; REA MCP
  registered (omp restart needed for tools).
- Old dead pids: [9820,48672,38188,19400,48508,37400,26868,30508,20944,46284,
  24980,23776,49320-old etc]; user game pid 19588-era = user's own (untouched).

## HISTORY (dated run summaries)
- 2026-11-17: User-requested live attachment proof passed on isolated inst9 with
  actual checkpoint inference and browser SSE. Fifteen planning frames captured,
  exact values/actions checked, checkpoint unchanged, test processes stopped.
- 2026-11-17: Deployed read-only SSE, shared snapshot sampling, readable inputs
  and bounded sampled decision history. Tests and docs updated, changes pushed;
  no trainer/observer or gameplay changes. Synthetic preview cleaned up.
- 2026-11-17: Assessed persistent telemetry and log streaming from current
  observer/server/browser source; discussed SSE versus bidirectional WebSocket.
  Product code unchanged; no live latency measurements or game tests performed.
- 2026-11-15: L5 RE + scripted WIN x2 bronze (RE phase complete).
- 2026-11-16: env_zar memory channel FAST mode, parallel CEM, F5 speed,
  loadout file model, 4-board L3 farm; CEM plateaued (board-bound).
- 2026-11-17: Steam updated install (copies stale; port + RVA re-derive pending).
  NN pivot per user: curriculum L1->L5 via START OVER; nn_play PPO live;
  deck decode: battle row = fixed SP deck para/heli/gas/ac130 (no cure card in
  build); planning cards = money buys; extra-safe-zones perk active.
  Git repo created + GitHub remote pushed. AGENTS.md split (guidance vs tracker).

## Prior tracker snapshot (before interface task)

## CURRENT STATE (2026-11-17t â€” SP-honest deck model, kit5 trainer live)
- Git HEAD 888b1a8 UNPUSHED (deck model + env_zar dump channel + hookdll v2 +
  probe/test scripts; shim git only). Tests 17/17 green
  (scripts/test_deck.py 11 + visualizer/test_labels.py 6).
- DECK MODEL (nn_play2): deck built ONLY from battle-dump [economy]
  'loadout <Name> = lvl' echo = what SP actually bought. KIT TRUTH (probe
  2026-11-17, kit_probe.py): SP-starved L1 board CONSUMES resume_loadout and
  buys ZERO (economy echo empty); ability_charges shows UNOWNED defaults
  (.Police = 1) and loadout_police_cost = 1/level; R-retry boards NEVER earn
  SP (6/6 EMPTY on the once-won board) -> SP comes from SAVINGS (sp_base=1 +
  sp_per_root_10k=1 per 10k saved) -> decks exist only after good outcomes
  (it17 L5 kit proves purchases at scale). Deck keys READ from settings.ini
  bind_slot1..7 ('_1'->'1', T). Charges + *_unlock/_arrival_seconds from the
  [counts] rules echo; refresh_battle_state re-syncs charges + game
  ability_cooldown -> exact blocked window (HELI exempt: free re-aim while
  flying, counts.helicopters = liveness truth). ready_once verifies
  phase='playing' via F6 dump (memory counters LIE on lost screens).
- L1 reality: civ0 8142 naked board dies ~6 s wall @8x -> early-loss break
  (civ==0 bt>6). Win is possible (kit2 hist: one r3 win frac 1.0) â€” trainer
  must find defense; battle mask when deck EMPTY = wait-only HONESTLY (old
  code cast phantom abilities for reward: fixed).
- Dump channel (env_zar.dump/phase_now): raw debug_dumps txt = plain
  '[section]' headers, parses to build/where/clock/view/economy/counts;
  analysis/dump-plan-44716.txt copy was re-formatted to '== [x] ==' by the
  earlier session (live files differ).
- Trainer RUNNING: TrainerKit5 = train --pids 39092,10428,29948,17224
  --eps 2 --rounds 14 > analysis/nn2_train_kit5.log (started ~04:10).
  kit2 (01:06, pre-fix) = all frac 0 + UNPAUSE flood: superseded.
- Instances idle/live: 39092 10428 29948 17224 (inst4/5/6/8, L1) in trainer;
  44716 inst3 lost screen; 3588 inst7 wedged welcome page (kill at end).
  NO Subagents rule stands (this run).
## NEXT STEPS
1. Monitor kit5 log: planning defense quality (money receipts), early-loss
   breaks ~6-9 s, one L1 win -> SP>0 -> DECK lines become non-EMPTY = the
   final live proof of purchase+cast (todo item 5's tail).
2. Deck-live proof audit: 'DECK <pid>: <name>xN@key' lines vs economy echo;
   kills Paratrooper/Heli counters move after casts.
3. BC from winners + it17 recipe -> PPO warm start (ml-spec gates 4/13.69/35%).
4. Phase end: kill instances (incl 3588/44716), update tracker + push.
