# ZAR Tracker (live state â€” update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-20 — retained defense and planning exploration)

- At 13:55 Central, observed study 200952 completed round one
  and saved both private models and Adam states. Official
  training scores 2.69%, 4.51% baseline and 9.54%, 0% broader
  preparation. Zero occupied shelters or logged battle casts.
  Both arms picked READY as the first decision in one game.
  All four outbreaks have appeared in prior studies. Round two
  launched inst13 60540, inst14 68144, inst15 59896, inst16 50568.
  Exclude all earlier seen native outbreaks when auditing reserves.

- At 13:54 Central, Observatory visibility restored for private
  comparisons (f5d1ca4). Prior workers explicitly disabled policy
  telemetry and the game inventory omitted compare_spatial.py.
  Restarted only the Observatory after study 199952 finished;
  D: listener PID 21012, created 1795204440.983753, port 8765.
  Tests: 325 scripts, 61 Observatory, exact recurrent policy
  parity and graph assertions. Fresh events and all four runtime
  files verified live, with 4,889 input labels and no warning.
  Selected inst13 game 64108/worker 42260 matched a live HTTP
  200 fragmented MP4 with initialization and media data. On
  the next batch's inst13, waited for capture and verified a
  267,080-byte JPEG before that process published policy data.

- At 13:54 Central, started private study 200952 under PID
  40184 with --observe (up to 1 Hz per worker). Tests whether
  broader preparation sampling helps when both arms start from
  the original 8a691469a829158d policy and Adam, avoiding
  further training on the poor shelter-study descendants.
  Six training rounds, four frozen reserve pairs, all strategy
  chosen by the model. First games inst13 64108, inst14 72036,
  inst15 72764, inst16 72660 all verified native protocol 3
  model_only=1. Data analysis/coverage-planning-exploration-44ab24afdc,
  log analysis/coverage-planning-observed-200952-drive-d.log.
  Production checkpoint hash matched; active game count remains
  within the same four training and two reserve copy schedule.

- At 13:53 Central, READY shortfall study 199952 finished.
  Candidate received the full 0.15 cost in 10 training games,
  zero in the one occupied start and the one planning timeout.
  Both arms had just one occupied start during training (19.68%
  coverage, same native geometry, different outbreaks), both
  breached. Baseline scored 3.44% averaged over 12 training
  scores; candidate 4.79% over 11. All eight frozen attempts
  went to retry with zero coverage. Four raw scores per arm
  averaged 5.655% baseline and 6.822% penalty. Distinct fresh
  scores excluding inherited, training and prior reserve seeds
  averaged 7.86% baseline (two) and 7.05% penalty (three).
  Frozen policies 3874fddd53858923 / 38d587c37655588d. Neither
  meets the consistency gate. Keep the penalty experimental.

- At 13:41 Central, study 198952 completed eight frozen reserve
  attempts. All hit the retry floor and none counted as a natural
  finish. One baseline attempt overlapped an inherited outbreak.
  Fresh retry scores averaged 8.21% baseline (three) and 7.50%
  stronger (four). One baseline reserve attempt started with
  19.21% coverage and incurred 0.01925 breach cost. The stronger
  arm had zero occupied exposures in training and reserve games.

- Deployed 1d315d1 and launched private READY shortfall study
  199952 under PID 74588. Both arms clone 3ddf829cff3ad28a with
  private Adam state and inherited outbreak exclusions. Data
  analysis/coverage-ready-shortfall-83d3f363f6, console
  analysis/coverage-ready-shortfall-199952-drive-d.log. Four
  copies inst13 60132, inst14 51452, inst15 69096, inst16 72924
  verified protocol 3 model-only input. Six training rounds and
  four frozen reserve pairs. Production checkpoint hash matched
  and Observatory PID 12628 remained active.

- At 13:37 Central, all valid shelter defense 198952 training
  rounds completed (24 scored attempts, 23 distinct outbreaks,
  excluding the interrupted batch). Baseline averaged 6.36%
  and stronger cost 5.85%. Every board again had zero initial
  coverage and zero breach cost. No penalty effect observed.
  Half of those attempts had no recorded legal battle cast.
  Final paired checkpoint is next_round 6. Frozen evaluation
  launched with inst19 69316 and inst20 49472 under PID 1812.

- At 13:35 Central, shelter defense 198952 has four completed
  rounds and paired next_round 4. Across the original and
  resumed valid rounds (discarding the bad pair batch), 16
  training games averaged 7.29% baseline and 4.58% stronger.
  Every board had zero coverage at READY and zero breach cost.
  Arm differences still cannot be attributed to the penalty.
  Round five is live under PID 1812, inst13 21688, inst14 70168,
  inst15 22312, inst16 70704. No new interface error in the
  resumed completed rounds. Production hash matched.
- Tested a three-attempt retry around one changing native map,
  retaining strict validation of each count and header. It
  recovers a map rebuilt between reads, bounds retries and
  identifies the table RVA for a persistent mismatch. Does not
  accept inconsistent snapshots or turn failures into scores.
  Verified jointly with the READY shortfall study (324 tests).
  Combined patch analysis/coverage-portable314/tmp/ready-shortfall-and-native-retry.patch
  SHA256 7CAA5447E68A4E9952FC19ADEB274748D992391D81F7B0AC0C673FEF87634794.
  Staged only, no live changes.

- At 13:31 Central, recovered shelter study 198952 after a
  second native map-read error exhausted the pair retry. The
  original process 64444 exited at paired next_round 1. Resume
  operator 1812 used the original seed, copies, run arguments,
  both private Adam states and retained seen outbreaks. Data
  analysis/coverage-shelter-defense-1fbda1a418, console
  analysis/coverage-shelter-defense-198952-resume1-drive-d.log.
  The replayed round completed cleanly and checkpointed both
  arms at next_round 2. Baseline saved 9.20% and 8.24%; stronger
  cost 5.87% and a natural 0% loss. No occupied coverage; third
  round launched. Original interrupted attempts are retained
  and excluded from scored training aggregates.
- Staged an isolated READY shortfall comparison. With a valid
  native READY receipt, the candidate pays up to 0.15 at zero
  starting civilian coverage, tapering to zero at 5%. Either
  an empty zone or no zone gives the same penalty. Missing
  receipts get zero, and masks, official outcomes, base shelter
  credit and breach cost stay equal across arms. All 324
  isolated tests passed, applicability checked. D: patch
  analysis/coverage-portable314/tmp/ready-coverage-shortfall-study.patch
  SHA256 786514DE42CA2F0C216B9CF2988E0732E135DF599EA86763B9D7A764986FB319.
  Existing breach experiment continues before any deployment.

- At 13:29 Central, audited native starting coverage in 1,119
  scored fresh L1 archive entries deduplicated by team, view
  revision and outbreak. No zones: 39, mean 11.61%, 34 below
  10%, two wins at or above 35%. Zones with zero initial
  coverage: 60, mean 16.86%. Positive initial coverage: 1,020,
  mean 22.52%. Mixed policies, including layout replay, prevent
  causal attribution. An experimental READY penalty should use
  verified civilian coverage with a cap, rather than zone count
  or invalidating the READY action. No reward change deployed.
- Study 198952 remains live under 64444. A changing native map
  interrupted one game in round two; its existing pair retry
  started inst13 19116 and inst14 65532. No partial pair score
  assigned. Model-only input and production weights preserved.

- At 13:27 Central, shelter defense study 198952 completed its
  first PPO round. Baseline retries saved 9.47% and 5.29%;
  stronger-cost 6.25% and 9.35%. All had 0% inside at READY,
  so the breach cost stayed zero. New native evidence worked:
  one FireMortar and two Garrison placements across four boards;
  inst16 had first legal Stun Gas/Fire Bomb at 20.20 s and one
  native deployment of each. Inst15 bought both but had no
  legal cast before retry. Round two launched under 64444
  (inst13 69620, inst14 68344, inst15 57276, inst16 42020).

- At 13:26 Central, planning exploration 197952 exited normally.
  Eight held-out retries, no natural finishes, no occupied
  shelters. Six distinct fresh scores after excluding one
  inherited outbreak per arm. On those fresh scores baseline
  averaged 7.93% (three) and broader planning 9.44% (three).
  Consistency remained false for both.
- Deployed 609c680 and launched private shelter defense study
  198952 with operator PID 64444 after the idle check. Both
  arms clone c6096d6b7f2a5f82 with its private optimizer state,
  chosen because its training produced occupied shelters.
  Six training rounds on inst13-16, four frozen reserve pairs.
  Both train at the same broader planning temperature and
  READY coverage credit; the sole treatment is 0.10 vs 0.30
  occupied breach cost. Relative to 0.10, the two prior
  occupied exposures would cost 0.02100 and 0.02515 more.
  Check actual shelter coverage before attributing a result.
- New working directory analysis/coverage-shelter-defense-f137abf8b1,
  log analysis/coverage-shelter-defense-198952-drive-d.log.
  Read-only first-round model_only=1/protocol 3 verified after
  READY on inst13 70308, inst14 62256, inst15 72312, inst16
  62308. Production checkpoint hash and Observatory matched.

- At 13:22 Central, first frozen pair retried at 8.36% and 8.41%.
  Both outbreak IDs are in the inherited exclusion set and
  cannot count toward fresh consistency. Further reserves live.

- At 13:22 Central, model-only study 197952 finished training
  (16 attempts, 12 distinct native outbreaks). Baseline averaged
  4.49%, broader planning arm 6.53%. Baseline sheltered none;
  broader planning sheltered civilians in two attempts. The
  second verified zone_rect covered 12.54% at READY on outbreak
  3896770976; 1,024 were exposed at 47.23 s. No paid building
  defenses. A confirmed Airstrike was called at 47.23 s, no
  evidence of an effect before the breach. Final saved 9.84%.
  No performance established on held-out outbreaks yet. Frozen
  reserve launched under 19628, inst19 64984 and inst20 64020.
- Exact live receipts explain four misleading empty zone events
  in the last training pair: each native place safe_zone event
  with two recorded points matched only a wall decision, not
  zone_rect. Three were axis-aligned and one diagonal; zero
  occupant coverage in all four. Deliberate zone_rect actions
  had separately verified four-corner placement receipts. Do
  not mask wall actions on the basis of a safe_zone log label.
- Next breach-cost comparison staged with the same broader
  preparation sampling and same READY credit in both training
  arms. Only the occupied penetration cost differs. Records
  native building/defense state at READY and first legal cast
  times. All 322 isolated tests passed, applicability checked.
  D: analysis/coverage-portable314/tmp/shelter-defense-with-exploration.patch
  SHA256 54733E542A7F8A33A6403F1CA9BBD2F4ACFFD865FB18F6BF24608C6B6C161EAD.
  Pending current evaluation and idle boundary. Production
  checkpoint hash matched.

- At 13:18 Central, the first model-only planning comparison
  batch completed and checkpointed both arms (next_round 1).
  In inst14 outbreak 3661110275, the challenger sheltered
  10.42% at READY, recorded 857 sheltered and 855 exposed at
  the first occupied breach (38.60 s), then retried at 9.56%.
  The native four-corner placement had one matching action
  window, zone_rect decision 12. Exploration was exercised
  in 29 and 7 decisions, respectively. All four games retried;
  no performance effect established. Round two launched with
  inst13 PID 73608, inst14 68368, inst15 38052, inst16 71652.

- At 13:17 Central, deployed 2caf0a3 plus 263b1c4 at the
  verified idle boundary after operator 53348 exited naturally.
  Both training arms and histories retained. Reserve had eight
  retries across three distinct native outbreaks and no coverage
  or natural clears. Raw means 6.88% baseline / 7.02% challenger;
  unique-seed-weighted 6.88% / 6.24%. This did not establish a
  stronger policy or meet the 35% consistency gate.
- The input hook passed four Rust tests, two identical builds
  and active deployment preflight. DLL SHA256 starts 71a2d18e.
  Build artifacts, writable caches and temporary state were on
  D:. Existing Observatory PID 12628 remained live. New private
  comparison 197952 operator 19628 is on
  analysis/coverage-planning-exploration-b5efd2b133, log
  analysis/coverage-planning-tool-197952-drive-d.log. Both arms
  clone 6e4dd8f5346064da and Adam from the completed paired
  snapshot, chosen for the sole prior occupied training shelter.
  This is a new comparison with a new seed. Prior evidence and
  previously seen outbreaks are retained outside fresh scoring.
- Verified protocol 3 and native model_only=1 at offset 0x44
  on all first-round copies at READY: inst13 PID 48420, inst14
  61732, inst15 45152, inst16 71840. All were launched under
  ZAR_MODEL_ONLY_INPUT=1. The planning exploration, zone action
  receipt matching and checkpoint stop changes passed 321
  combined script tests. Production checkpoint hash matched.

- At 13:11 Central, all 32 warm training attempts in 196952
  completed across 29 distinct outbreaks. Baseline averaged 3.88%,
  challenger 5.50%. The challenger finally sampled nine shelter
  rectangle decisions in the last round. On outbreak 628407931,
  eight choices yielded 9.26% inside at READY and a 0.02778
  coverage reward. There were 759 credited civilians, zero
  observed occupied breach exposures and 9.90% saved at retry.
  It is the sole positive training coverage in this run.
  Frozen evaluation began under 53348 with inst19 PID 67188
  and inst20 PID 62600.

- At 13:10 Central, seven rounds of warm study 196952 completed
  (28 scored games, 25 distinct native outbreaks). Baseline mean
  was 4.33%, challenger 4.97%. Neither received positive READY
  coverage or selected a shelter construction corner. The final
  training round is live under 53348 (inst13 55948, inst14 67716,
  inst15 70652, inst16 64116). Read-only shared mapping checks
  found protocol 3 and model_only=0 on all four. Keep the run
  intact until the verified idle boundary.
- Staged tool-level exploration in place of further corner-only
  tuning. Candidate temperature 1.35 broadens legal planning
  tool choices during training only; PPO stores the exact rollout
  temperature for each step, and evaluation uses ordinary
  probabilities. Both keep the same terminal, READY and other
  rewards. All 318 isolated tests passed on rerun after a fixture
  temporary-directory rename error. Patch applicability passed.
  D: analysis/coverage-portable314/tmp/planning-tool-exploration.patch
  SHA256 EB611F9C2018A62E73A9BD776E3AE31E33855C6D46624EA762DF5C7856307E29.
- Staged controlled stop at a future paired checkpoint. A
  stop-after-round file in the active run directory will be
  honored after both optimizer updates, results and atomic
  paired.pt, before another batch. Test confirmed order and
  preserved states and seeds; all 317 isolated tests passed.
  D: analysis/coverage-portable314/tmp/comparison-clean-checkpoint-stop.patch
  SHA256 B97D2FEEB85173956F7A62C921BCB57F787B4C5FC36C7B258E034C21AE2D4CAE.
  Existing operator does not have this code. Neither staged
  change alters the live inputs or training process.

- At 13:06 Central, warm study 196952 had four complete training
  rounds (16 games, 15 distinct native seeds, one seed shared
  with the prior study). Baseline averaged 3.98% saved, challenger
  4.22%; four natural zero-save losses. No positive READY
  coverage or tempered choices. Verified atomic paired.pt at
  next_round 4 carries both model/Adam states and 38 known seeds.
  Fifth round is live under operator 53348 (inst13 PID 54124,
  inst14 73620, inst15 43744, inst16 71936).
- Joined two native zone placement receipts to the first-round
  episode IDs. Both were empty at READY and neither episode
  selected zone_rect, zone_begin, zone_corner or zone_finish.
  Both used wall/corridor/hold among other actions. Cause is not
  established. Retain planning-zone receipts by exact native
  timestamp, and identify only unique bracketed actions. Staged
  optional read-only trace patch in
  analysis/coverage-portable314/tmp/planning-zone-receipts-study.patch
  SHA256 A501A9D266C2414173D4EA96104E47D712C224FCC2FC5F0F60D928F1FF50A2B1.
  All 317 script tests and applicability passed.
- Model-only input 2caf0a3 is fetched on origin/main. Existing
  comparison has no controlled pause at checkpoint save and can
  immediately submit another batch. Do not interrupt an episode
  or swap live input code/DLL. Wait for natural operator exit;
  local tracker commit remains unpushed while this checkout
  runs the previous input version. Production hash matched.
- 2026-11-20: integrated opt-in model-only input. Isolated inst91
  rejected ordinary key, click and wheel messages while tagged input
  passed dialog, placement, geometry, zoom, battle and retry checks.
  Running game processes require a fresh launch to acquire the filter.

- At 13:00 Central, zone exploration study 195952 finished.
  Held-out baseline 8177193838922d68 averaged 8.835%, challenger
  1bfaec4658f51c44 averaged 7.06% (four each). All held-out
  attempts were distinct, absent from training and ended at
  retry, with zero coverage. The challenger had one verified
  Call to Arms deployment; neither policy met consistency.
- Deployed 69a0a8e and launched warm-start study 196952 under
  operator 53348 at 12:59:56. Both arms clone the higher-scoring
  private baseline 8177193838922d68 and its Adam state
  (10 slots, step 4236). Previous study used in selection;
  all 24 of its native outbreak seeds are excluded from fresh
  evaluation, plus all new training seeds. Compare eight more
  four-copy training rounds using the same READY credit, with
  broader corner sampling only in the challenger. Then four
  reserve pairs use normal sampling. No change to production
  policy or winner thresholds. Data
  analysis/coverage-zone-exploration-fa682b451e and console
  analysis/coverage-warm-zone-196952-drive-d.log. All 316 tests
  passed and both cloned policies matched in a real snapshot
  load test. Production checkpoint hash still matched.

- At 12:56 Central, the first zone exploration reserve pair retried
  at 9.52% baseline and 8.44% challenger. Both had zero coverage
  and zero tempered choices on fresh, distinct outbreaks.

- At 12:55 Central, all 16 zone exploration training attempts
  finished, each on a distinct outbreak. Baseline averaged 4.74%
  saved and challenger 5.99% (eight each). Three were native
  0% losses, 13 retries. Challenger sampled six tempered corners
  across three attempts, with zero native coverage credit. The
  only positive coverage was the first baseline game. Frozen
  evaluation launched under 74460, inst19 PID 68388 and inst20
  PID 73760. Production checkpoint hash matched.
- Native geometry receipts show repeated empty safe zones with
  two logged corners on the same horizontal line. In an audit
  of the retained two-corner placement receipts, four diagonal
  examples had positive occupancy, while four axis-aligned
  examples had zero. Five diagonal examples were also empty.
  The native log can use two corners for a valid shape, so do
  not infer a collapsed polygon from the vertex count alone.
  Match receipts by copy, session and outbreak. Active capture:
  analysis/coverage-zone-exploration-759d5bd5dc/native-zone-creation-audit.jsonl.
- Staged an isolated comparison log improvement to retain all
  planning tool counts and actual planning blockers alongside
  the native occupancy receipts. It changes only reporting.
  All 315 script tests and patch applicability passed. D: patch
  analysis/coverage-portable314/tmp/zone-planning-actions-audit.patch
  SHA256 3760E96F14739B0EFB07F54FD4BA974EC8A33B0EE418D6CEE4CB1A4BCF2B461F.
  Do not deploy until after the running operator exits.

- At 12:51 Central, zone exploration 195952 completed the first
  training round. Native outbreak 2301536718 in the baseline
  had 9.26% inside at READY and earned 0.02778 coverage credit,
  the first positive training receipt for this reward. Native
  shelter sampling credited 803 civilians after battle began;
  793 were exposed at the 52.70 s breach, and 9.97% were saved
  at retry. Other baseline saved 3.64%; challenger 8.22% and
  9.85%, all retries. Neither challenger chose a zone corner
  and there were zero tempered decisions in both. No exploration
  effect demonstrated. Round two launched (operator 74460,
  inst13 74048, inst14 51212, inst15 73312, inst16 3860).

- At 12:50 Central, READY coverage study 194952 exited normally.
  Frozen baseline averaged 3.48% saved and challenger 9.62%,
  four scored retries each on distinct outbreaks disjoint from
  training. All eight were below 10% and neither arm passed
  consistency. The sole positive coverage in all 24 attempts
  occurred in held-out outbreak 1106250354, after weights were
  frozen. 9.95% sheltered (811 civilians), verified credit
  0.02985, first occupied breach at 50.90 sim s, all 811 exposed,
  and 9.94% at retry. The game confirmed two deployments across
  the eight reserve games, both from one baseline trial.
- Deployed cbebccc at the idle boundary and launched zone
  exploration study 195952 under operator 74460. Stage data
  analysis/coverage-zone-exploration-759d5bd5dc and log
  analysis/coverage-zone-exploration-195952-drive-d.log.
  Clones original frozen policy 8a691469a829158d and runs four
  training rounds on inst13-16 plus four paired reserve rounds
  on inst19/20. Tempered corner choices only during candidate
  training. On a six-step forward-only parity check with the
  frozen production GRU, the maximum deviation from a replay
  probability ratio of 1 was 5.96e-7. Untempered probabilities
  were bit-exact, and illegal cells stayed at zero. No model
  update in that check. Production checkpoint hash matched.

- At 12:46 Central, READY coverage study 194952 completed all
  16 training attempts. All were distinct outbreaks and scored
  below 10% at retry. Baseline averaged 4.92%, challenger 5.89%.
  Nine boards had safe zones at READY (12 zones total), yet all
  16 had zero civilians sheltered at READY, zero coverage reward,
  and zero confirmed ability spends. Within the first 12 there
  were eight boards with zones. Frozen evaluation is live under
  PID 68152, inst19 PID 29880 and inst20 PID 19224.
- Staged a training-only zone exploration comparison to address
  the missing coverage signal. Both arms receive the same native
  READY credit, legal masks and PvE settings. The candidate samples
  legal zone-rectangle and polygon corner cells at temperature 1.5;
  the same per-step temperature is reused for PPO log probabilities.
  Frozen evaluations use the original sampling distribution for
  both arms. No placement is forced. All 315 isolated tests passed,
  including masked probability parity and evaluator options. Patch
  applies cleanly, not deployed. D: file
  analysis/coverage-portable314/tmp/zone-exploration-study.patch
  SHA256 E19E25D0C8958AED3CB6DF04FEBE68F04F34721B03F60C7ACFD5B138A7B0FC04.
  Judge by actual coverage activation first and official held-out
  survival before promotion. Production checkpoint hash matched.

- At 12:42 Central, READY coverage study 194952 completed its
  first PPO round and started the second (inst13 PID 58788,
  inst14 59216, inst15 33028, inst16 74268). First round baseline
  retries were 5.69% and 0.12%; challenger 9.52% and 6.42%.
  Two boards had two zones each, other two had no zones.
  All four native READY events recorded 0% coverage and the
  optional reward was zero. Native deployment lists were empty.
  Short startup brought all four copies to verified planning
  within 29 seconds of launch, with no fallback. Round wall
  time was 92.93 s versus 127.01-146.35 s for three preceding
  no-retry training rounds. This is an operational observation
  under different boards, not a controlled speed comparison.

- At 12:40 Central, breach-cost study 193952 exited naturally.
  In the reserve, the baseline averaged 9.82% across three
  scored retries and had one planning timeout. Stronger cost
  averaged 7.54% across four scored retries. All seven scored
  outbreaks were distinct and absent from training. There were
  zero natural finishes and zero occupied exposures, including
  all 16 training games. The official consistency report failed
  both arms. Native final reserve receipts showed no zones and
  no deployments despite one Helicopter or Airstrike in stock.
  Mark the breach-cost comparison unexercised.
- Deployed the tested READY coverage patch in 02b8347 at the
  idle boundary after verifying the hashes and headroom. Private
  study 194952 launched at 12:40 under PID 68152, data
  analysis/coverage-ready-coverage-db06c78332, log
  analysis/coverage-ready-coverage-194952-drive-d.log.
  Both arms clone original policy 8a691469a829158d and Adam;
  only the challenger earns additional reward for native
  civilian coverage at verified READY, scale 0.30. Four
  training copies and two disjoint reserved copies. Model
  controls all moves. Production checkpoint hash matched.

- At 12:36 Central, the first four held-out attempts in study
  193952 were all retries below 10%, all on distinct outbreaks
  absent from training. Frozen baseline 8d56592a424c5272 scored
  9.94% and 9.56%; stronger 81ef1c9337c1581d scored 5.72% and
  5.85%. No occupied exposure or natural finish. The next
  reserved wave launched under operator 54556, inst19 PID
  71864 and inst20 PID 68184.
- Native stock audit tied final training and second reserved
  journal receipts to the same copy and outbreak in results.
  Final training four bought Fire Bomb (two) or Cruise Missile
  (two). All purchased stock was still present on retry and
  all runs ended before its earliest possible effect
  (42.0 s Fire Bomb, 32.5 s Missile). Second reserve baseline
  fired Stun Gas at 30.8 sim seconds and retried at 30.83.
  The other arm bought no battle ability in that reserve pair.
  Neither board had a zone at READY. The first reserved native
  journals had already rotated; its five selected Police drops
  are unconfirmed by this audit. Compact receipts in
  analysis/coverage-breach-cost-705d104768/native-shelter-and-stock-audit.jsonl.
- Extended the staged READY coverage comparison with native
  stock at READY and executed deployment timestamps so timing
  can be distinguished from selection. All 313 isolated tests
  and patch applicability passed again. The updated patch
  SHA256 is 70B0206FE83A331FDF39F589F79C7CC192B2615277131DC969B5205A933FD1AE.
  This supersedes the earlier staged hash and is pending idle
  deployment. Production checkpoint hash matched.

- At 12:32 Central, all 16 training trials in breach-cost study
  193952 finished. Eight baseline retries averaged 5.555% and
  eight stronger-cost retries averaged 6.461%; all were below
  10%, all had distinct recorded native outbreaks, and the
  occupied breach penalty was zero in every episode. The final
  four boards had zero civilians inside safe zones at READY even
  though two had a native safe zone. Each PPO network and Adam
  state is saved privately. Frozen evaluation launched with
  reserved inst19 PID 74728 and inst20 PID 46892 under operator
  54556. No evaluation score yet and no effect estimate for the
  breach penalty. Review the reserved results before selecting
  the next isolated comparison.

- At 12:31 Central, three training rounds in breach-cost study
  193952 completed. All 12 native-outbreak trials ended below
  10% at retry, with zero credited civilians, occupied exposures
  or breach penalties. The baseline mean was 5.98%, stronger
  cost 6.38%, six attempts each. The penalty never activated.
  Round four is live under PID 54556, copies inst13 71604,
  inst14 62388, inst15 60364 and inst16 70084.
- Tested an isolated follow-up for the missing preparation signal.
  The optional --compare-ready-coverage arm adds up to 0.30 PPO
  reward in proportion to the game-reported civilian coverage,
  once on the verified READY transition. Both arms choose their
  own layouts and use the original 0.10 breach cost and official
  outcome evaluation. Empty, failed or unverifiable READY gets
  zero additional credit. The staged patch also incorporates the
  shorter boot fallback and native comparison receipts. All 313
  isolated tests passed and git apply --check passed. D: patch
  analysis/coverage-portable314/tmp/ready-coverage-study.patch
  SHA256 A65EEFE7129DB7F83018F488C8F4E8485E85ED04F6C92F370FABCDEEFE5EFB20.
  Evaluate on the reserved copies after the current operator
  exits. Require actual evidence of coverage signal and better
  official saves before treating the reward as useful. Production
  checkpoint hash matched.

- At 12:28 Central, the second shelter-cost training round finished.
  Baseline retries scored 9.15% and 1.45%; stronger cost 4.51%
  and 6.88%. All eight scores so far are below 10% and all eight
  got zero breach penalty. Native preparation receipts show a
  safe zone built then undone on inst13 and one zone with zero
  civilians inside at READY on inst14. The third round is now
  running under PID 54556 (inst13 71952, inst14 74224, inst15
  74148, inst16 70660). Actual native speed receipts show 4 under
  both arms, the speed_2 (2x target) setting.
- Staged and tested a shorter boot with guarded standard-warmup
  fallback for future private breach comparisons, plus native
  shelter coverage at READY, selected and paid placements, and
  cast receipt summaries. All 312 isolated script tests passed,
  including the simulated fast-boot fallback. Patch applies
  cleanly (analysis/coverage-portable314/tmp/breach-comparison-boot-and-receipts.patch).
  It has not been deployed and has no live throughput measurement.
- Archived layout-free zone-population targeting trials covered a
  median 28.95% initially across 189 distinct policy/revision/seed
  rows. Their official mean was 10.77% and only two observed wins
  reached 35%. Coverage can expose the reward signal but cannot
  substitute for defending occupied shelters or for official saves.

- At 12:25 Central, shelter-cost study 193952 completed round zero
  and atomically saved the two private policies and Adam states.
  The starting policy was identical and the four native outbreaks
  were distinct. Baseline scored 1.11% and 7.65% at retry, stronger
  9.24% and 9.65%. All four had zero credited or exposed civilians
  and zero occupied-breach cost. These scores cannot measure the
  effect of the stronger penalty. A UI-frame timeout in inst15
  triggered the existing pair retry on inst15/16, which completed.
  PPO diagnostics show two updates. Operator 54556 started round
  one, inst13 PID 61264, inst14 56492, inst15 68124, inst16 74240.
  Check the second round for active shelter exposure before judging
  the reward experiment. Production checkpoint hash matched.
- Descriptive archive audit, deduplicated by team ID, view revision
  and native outbreak, across 1,119 scored fresh L1 campaign-search
  rows with shelter telemetry. In the no-zone subset, 34 of 39
  attempts scored below 10%, and two cleared 35%. In 1,011 attempts
  with occupied breach exposure, 359 were below 10% and 209 cleared
  35%. The archive includes different policy and preparation modes.
  Policy selection and scenario differences preclude a
  causal estimate. A stronger breach cost can only teach from
  rounds that encounter occupied breaches; keep inspecting whether
  the policy creates and protects meaningful shelter coverage.

- At 12:21 Central, the full footprint comparison finished with four
  fresh or repeated-seed discovery attempts per arm (four native
  outbreaks crossed between arms). Standard targeting averaged 7.39%
  saved and footprint targeting averaged 8.49%. All eight were retries,
  seven strictly below 10%, and reserved evaluation did not open.
  The zombie count reached at least the live civilian count in all eight;
  that preceded the retry floor by 35 to 76 simulated seconds in six.
  All eight had occupied shelter breaches. The forecast receipt audit
  linked 19 of 24 shots. Overlap during flight and positional mismatch
  still limit action-effect validation.
- A retrospective check of 55 local fresh L1 campaign-search attempts
  with native outbreak, official score and population-pressure receipts
  found that all 37 severe failures passed the outnumbered marker.
  Four sub-35% wins passed it too. The marker remains diagnostic and
  the official below-10% severe-failure flag adds no reward cliff.
- Deployed 00f3c6f after the footprint operator exited and 311 isolated
  script tests passed. Private real-game PPO study 193952 is running
  from frozen base 8a691469a829158d under PID 54556, with results under
  analysis/coverage-breach-cost-705d104768. Compare existing 0.10 and
  experimental 0.30 occupied-exposure costs at the same fixed speed for
  16 training games on inst13-16 and eight frozen attempts on reserved
  inst19/20. Both arms use native unlock timing and the same continuous
  saved-fraction reward. Official evaluation, Observatory and the
  production checkpoint (SHA256 starts 0B23B6A7) are unchanged.
  Assess actual occupied exposure, severe failures and official scores
  before deciding whether the stronger penalty is worth a larger test.

- At 12:15 Central, footprint study 192952 first wave finished.
  Standard 5.51% mean, footprint 9.45% mean (two games each,
  all retries; no 35% result). Direct civilian deaths 217 versus 65.
  Four different outbreaks and 2 games per arm make that
  descriptive, not causal. Crossed wave is playing under
  74284 (inst13 PID 69892, inst14 69500, inst15 10284, inst16 63160).
- The first actual footprint receipt report linked 11 of 12
  confirmed shots to impacts by game clock and position.
  One decision center differed by about 6.6 m from its eventual
  native impact, above the fixed 5 m join limit; left unmatched.
  Six linked shots had an earlier nearby impact during their
  flight. Those need separate analysis. Example: 134 civilians
  observed in the footprint of a follow-up, one directly hit
  after the previous blast killed 145 at the same point.
  Without earlier overlap the point-count baseline had lower
  pilot error than zero for both populations, but there were
  only five such linked shots, with no held-out validation.
- Native timed receipts showed twelve pre-unlock selections
  from 29.5 to 30 s, eleven with no stock spend. The one that
  spent stock launched after 30 s during input dispatch. The
  existing mask deliberately led the verified unlock by 0.5 s.
  Staged stricter native unlock timing with a separate view
  revision (analysis/coverage-portable314/tmp/native-ability-unlock.patch).
  All 308 isolated script tests passed, including 29.999 s
  locked and 30.0 s available. Patch applicability verified;
  no change to live masks until this experiment is finished.

- At 12:10 Central, timing study 191952 finished: standard
  ce5b191516c37f99 13.37% mean / 27.00% best, preference
  15980ab215b7253e 11.08% mean / 15.05% best, four scored
  games each. Direct civilian deaths 264 versus 24; only
  two outbreaks matched across arms and neither comparison
  qualified. Do not infer impact or survival improvement
  from the aggregate casualty difference.
- Footprint experiment 192952 deployed at idle in 6e1fa09
  (308 isolated tests), live D: operator 74284, directory
  analysis/coverage-team-bdb2b04ae6. Reference ce5b191516c37f99
  selected by the predeclared highest recorded Missile score,
  challenger e2955a9ae8ff256d. Timing preference identical.
  All four copies reached READY (inst13 PID 74476, inst14
  31920, inst15 66316, inst16 31000). Native logs contain
  confirmed impacts on three copies so far. Compact capture
  analysis/coverage-team-bdb2b04ae6/missile-footprint-native-audit.json.
  No official footprint scores yet. Production hash and
  Observatory PID 12628 matched.
- Prepared read-only receipt comparison
  analysis/coverage-portable314/tmp/report-missile-footprints.py.
  It requires matching stock/launch counts, a unique impact in
  both native clock and world coordinates, and a complete log
  before scoring current-count and zero baselines. Ten native
  launches in the crossed timing wave were uniquely matched
  to ten impacts using the exact logged launch coordinates
  and the same tolerances. Current perception versus impact
  errors will require the new recorded decision fields.

- At 12:06 Central, crossed timing wave had six official scores.
  Preference cleared at 10.54% on matched outbreak 429480045
  versus 7.59% standard in wave one. Crossed standard retried
  at 8.89% on a new inst14 seed, so that board is not a native
  matched pair. Two results still pending. Operator 70860 live.
- Added bounded observation receipts to the queued footprint run.
  Both arms record the selected Missile target's native civilian
  and zombie counts, occupied perimeter overlap, decision clock,
  world position and stock before/after, with separately logged
  impact coordinates, direct kills and truncation status. They
  use exactly the same observation calculation as the candidate
  preference. Missing context stays unknown. New patch
  analysis/coverage-portable314/tmp/missile-footprint-observations.patch
  passes all 308 isolated script tests and applies cleanly. It
  keeps the same experiment, masking and rewards. Only the
  waiting helper was replaced, now PID 69248 waiting on exact
  operator 70860. Handoff log
  analysis/coverage-missile-observations-handoff.log. The
  current runtime was left intact.

- At 12:03 Central, 191952 first timing wave finished. Standard
  ce5b191516c37f99 scored 7.59% at retry and 27.00% on a clear
  (mean 17.30%); in-flight preference 15980ab215b7253e scored
  9.57% at retry and 15.05% on a clear (mean 12.31%). All native
  seeds matched the corresponding prior loadout discovery runs;
  these are comparison samples and not fresh held-out evidence.
  Joined all twelve missile launches to native impacts within
  0.12 s of the configured 2.5 s flight. All eight subsequent
  launches across both arms happened after the previous impact.
  Direct civilian losses were 130 for the two standard games and
  18 for the two preference games. Outcomes and damage are still
  confounded by different outbreaks between arms in one wave,
  and this wave does not show an in-flight repeat reduction.
- Crossed timing wave two reached all four boards under 70860
  (inst13 PID 9792, inst14 69268, inst15 14364, inst16 62572).
  Fresh native evidence captured in the existing small D: audit.
  Footprint handoff 72724 remains waiting. No above-35% result
  in this comparison.

- At 11:58 Central, completed the 190952 loadout comparison.
  All eight fresh discovery starts retried, four per arm across
  eight distinct observed native seeds. Police averaged 9.92%,
  Missile 9.44%; the latter confirmed 467 direct civilian
  deaths across the four games. No reservation or promotion.
- Missile follow-up 191952 is live on D: operator 70860, frozen base
  8a691469a829158d, notes from analysis/coverage-team-c1a394012d,
  deployed 3049ef9. All four games reached READY and independently
  bought Missile level 1 with zero spare SP (inst13 PID 57940,
  inst14 14780, inst15 67136, inst16 70408). Comparison standard
  ce5b191516c37f99 versus in-flight preference 15980ab215b7253e.
  Native launch/impact capture checks matched the prior discovery
  outbreak seeds on all four copies. Both arms had spaced first
  launches at the observation, and the new timing effect still
  needs final evidence. Raw observations preserved in
  analysis/coverage-team-c1a394012d/missile-followup-native-audit.json.
- Verified the footprint patch applies cleanly to the deployed
  timing source. One-time D: handoff PID 72724 is waiting for exact
  operator 70860. It will deploy the tested 308-test footprint
  comparison (192952) at the idle boundary from the strongest
  scored Missile discovery policy with its timing preference
  fixed across arms. Handoff log
  analysis/coverage-missile-footprint-handoff.log. Production hash
  and Observatory PID 12628 verified. No current official
  timing-comparison scores or held-out qualification.

- At 11:51 Central, crossed Missile inst13 outbreak 429480045
  finalized at 9.38% at retry. It launched at 43.43, 51.87 and
  74.73 sim seconds, so timing varied without a new rule. Its
  first direct impact killed no civilians but the official
  campaign receipt confirmed and assigned 223 Missile civilian
  deaths across the episode. Spacing alone did not remove the
  targeting failure. Operator 71708 and queued follow-up 70252
  remained live; three other crossed results were pending.
- Staged a separate missile-footprint experiment in
  analysis/coverage-portable314/tmp/missile-footprint-study.patch,
  based on the pending missile-followup patch. It uses the native
  current civilian/zombie counts inside each legal candidate blast
  circle in place of the corresponding coarse-grid inputs to the
  existing learned Missile target score. A fixed 2-logit soft
  preference discourages overlap with an occupied intact shelter
  perimeter. No masks, actions, timing weights, training rewards
  or official scores change. The reference and candidate keep the
  same timing preference. Native config echo verified 56 m as the
  radius. 308 isolated script tests passed, including exact-radius
  populations, only-Missile-cell score changes, and held-out
  control pairing. It is a current-state geometry estimate, with
  no validation of occupants at impact or survival benefit yet.
  Not deployed during current or queued follow-up study.

- At 11:48 Central, 190952 first wave is scored: Police controls
  9.89% and 9.86% (mean 9.875%), Missile 9.37% and 9.91% (mean
  9.64%). All retries. The crossed wave is live under 71708
  on inst13 PID 29984, inst14 72052, inst15 71764 and inst16
  71524. Inst13's Missile arm had one native impact killing 21
  zombies and no civilians as of sim 45.93, rather than a
  repeated salvo at that check. Do not count a battle snapshot
  as a score. Handoff 70252 remains waiting.
- Offline blast-footprint geometry replay on the two finished
  Missile trials found their first confirmed impact centers
  37.60 m and 53.20 m from the nearest planned shelter perimeter,
  within the native 56 m blast radius. Both also had a subsequent
  native wall-cell break inside that radius. A conservative
  geometry feature could have flagged the overlap. A bounded
  NumPy probe for 40 legal-grid footprints, 8,142 fixture
  entities and 62 segments took 2.09-3.84 ms (median 2.49 ms)
  on this PC. This measures the feature calculation only.
  It predicts current geometric overlap, not who will be
  inside the blast after flight or a causal effect. The live
  targeting policy and reward remain unchanged.

- At 11:46 Central, wave-one Missile candidate ce5b191516c37f99
  retried at 9.37% (inst14/outbreak 3813848280) and 9.91%
  (inst16/1595816018). Native journals record 3 impacts at the
  identical aim point on each board. Inst14 impacts killed 58
  civilians, 2 officers and 0 zombies; current reward correctly
  assigned all 58 civilian deaths (-0.00712). Inst16 killed 66
  zombies and no civilians. On both boards the first native
  wall-cell break event followed the first impact by 0.03 sim
  seconds, with all eight reported sample points within its 56 m
  radius. These observations corroborate wall-damage risk but
  are not an independently isolated attribution of every wall
  cell. Details retained in
  analysis/coverage-team-7ff3782543/loadout-native-audit.json.
- First Police control scored 9.89%; second control inst15 PID
  61660 still active under operator 71708. On inst13 all seven
  dispatch receipts joined stock deltas to native Police drops.
  Dispatch was 504-543 ms, native holds 0.102-0.490 s including
  a stock exhaustion event. The earlier 1.48-2.31 s behavior is
  still unexplained and did not recur in this session.
- Staged missile-followup-study.patch for a crossed comparison
  on the same frozen Missile-capable discovery policy. It uses the
  existing reversible -10 follow-up preference while its last
  missile is in flight; native masks and target scoring remain
  available. Readiness, launch evidence, actual score and
  checkpoint identity are required, and reserved evaluation
  retains the same control. All 305 script tests passed in
  isolation. Handoff PID 70252 is waiting for exact operator
  71708 before deployment and launch of 191952; log
  analysis/coverage-missile-followup-handoff.log. No changes
  to the live game, saved metrics or production checkpoint.

- At 11:42 Central, Police path study 189952 had finished all eight
  discovery games. Endpoint was 15.63% average, peak 32.99%;
  path 11.72% average, peak 17.02%. The three outbreaks played by
  both arms all retried at 9.70-10.00%. The two higher clears
  came from different inst14 outbreaks, so the raw means do not
  establish targeting superiority. No reserved qualification.
- Handoff worked at the idle boundary. Commit 02bcfe8 launched
  experiment 190952 on D: operator 71708, directory
  analysis/coverage-team-7ff3782543, log
  analysis/coverage-layout-free-190952-drive-d.log. All four
  discovery boards verified (inst13 PID 63684, inst14 43636,
  inst15 61660, inst16 67564). Frozen base 8a691469a829158d,
  endpoint bf3fc52369fc3746 versus Missile preference
  ce5b191516c37f99. The native game confirmed Police purchases
  with 1 SP left on inst13/15 and Missile purchases with 0 SP
  left on inst14/16. Each Missile candidate launched all three
  charges between 30.10 and 30.40 sim seconds, before its first
  nominal 2.5 s flight would finish. Capture verifies execution
  of the model-selected buy and casts, not the causal impact of
  individual shots. Checkout checkpoint hash matched and
  Observatory PID 12628 remained live. No successor scores yet.

- At 11:36 Central, staged and verified a crossed native-evidenced
  loadout comparison, analysis/coverage-portable314/tmp/loadout-neighbors-study.patch.
  It compares exactly one changed purchase preference from discovery
  receipts, retains the actual frozen discovery control in reserve,
  and includes the bounded Police dispatch timing diagnostics. The
  actual 189952 journals support changing Police to Missile on either
  arm. Both paid Police level 1 and kept 1 SP; native catalog says
  Missile costs 2 SP and first effect 32.5 sim seconds. The observed
  discovery breaches at 54.37 and 61.00 s provide eligibility only.
  Endpoint control bf3fc52369fc3746 yields ce5b191516c37f99; path
  control 847df0f375da30cf yields ba6edad2a6f074b0. No other policy
  field differs, and the game still decides payment, ownership, and
  delivery. All 304 script tests passed and patch applicability verified.
- Queued experiment 190952 via handoff PID 69928, waiting on exact
  active operator 70324. The child uses the portable Python for hash
  validation and the same idle/clean checkout/checkpoint guards.
  Handoff log analysis/coverage-loadout-study-handoff.log. The active
  Police study has five official scores so far; the newest was a
  9.95% retry for path on matched outbreak 2413602735. No live
  source changed and successor launch still pending.

- At 11:33 Central, first Police trial wave finished. Endpoint
  bf3fc52369fc3746 retried at 10.00% and 9.70%, mean 9.85%.
  Path 847df0f375da30cf cleared one outbreak at 17.02% and
  retried at 10.00%, mean 13.51%. Four distinct native seeds,
  identical READY layout ID 418150907bbd395c, 1 spare SP each.
  All four native trail counts match stock-confirmed cast counts.
  All four exposed at least 2,355 civilians. The 17.02% game
  reduced the native zombie count from 2,599 to 2,334 in its
  20 s occupied-breach window. Descriptive results, no 35% win.
  Crossed wave two is live on inst13 PID 6696, inst14 PID 28444,
  inst15 PID 69868 and inst16 PID 62036 under operator 70324.
- Tested the unmodified virtual drag timing with fake mouse
  edges/movement, same below-normal priority and CPU set as the
  live operator, 16 calls. Button hold was 452.90-473.24 ms
  (median 457.59 ms); largest step 60.41 ms. This isolates Python
  timer waits from native processing and does not reproduce
  native first holds of 1.48-2.31 s. Staged bounded Police
  dispatch timestamps with stock and native release timestamps
  in analysis/coverage-portable314/tmp/police-dispatch-timing.patch.
  No change to actual gestures, policy choices or rewards. All
  303 script tests passed against isolated candidate source.
  Applicability verified, pending the live operator's exit.

- At 11:30 Central, all four 189952 boards were actively playing.
  Native planning receipts on each confirm Police level 1 with one
  skill point remaining. First Police sprays delivered 12-15 of the
  20 available officers; native reported first hold durations
  1.483-2.311 wall seconds at normal speed. The input driver requests
  nine 50 ms intervals after button-down. These are separate clocks
  and evidence of variable dose in both arms; cause unverified.
  Each board had delivered all 20 by sim 67.27 seconds, over 2-4
  confirmed sprays. Capture includes stock deployment counts, native
  hold time, actual trails and crowd/recovery snapshots in
  analysis/coverage-team-0f2ee96984/police-native-audit.json.
- The inst16 37.43 s trail contains a transient (1189,-35) client
  position and a 1.8 km world-coordinate jump. Its native drop
  bounds remained close to the intended line. Preserve actual
  deployment bounds and count alongside trail; do not use unfiltered
  cursor-trail length as officer placement evidence. First-wave
  wall-break recovery ratios are descriptive only. No official
  first-wave score yet and no changes to active input/runtime.

- At 11:27 Central, Police line comparison 189952 was live on D:
  under operator 70324, directory analysis/coverage-team-0f2ee96984,
  frozen base 8a691469a829158d, with all four copies at verified
  planning boards (inst13 PID 44644, inst14 42164, inst15 61072,
  inst16 68436). Same preparation policy, crossed endpoint versus
  path scoring. Reserves remain inst19 and inst20. Runtime commit
  f4ab65d contains the 302-test verified combined source. Log
  analysis/coverage-layout-free-189952-drive-d.log. Headroom at the
  idle boundary 14.79 GiB RAM and 18.92 GiB D:. Production hash
  matched and Observatory PID 12628 remained live.
- Previous operator 71620 finished normally. The sixth candidate
  cleared at 11.97% on repeated outbreak 2033973644. All six
  reserved candidate attempts used two distinct outbreaks; five
  scores averaged 10.36%, one timeout, and the two first distinct
  scores were retries averaging 9.96%. No eligible natural finish
  or promotion. From the actual pair timings there were 39.57
  minutes after the first ineligible pair. The automatic handoff
  stopped before applying changes because its PowerShell instance
  lacked Get-FileHash; the same checked deployment succeeded in the
  working shell after confirming the operator was idle. No restart
  of the old operator and no changes to the production checkpoint.

- At 11:19:43 Central, wave five finalized at 9.90% officially
  saved at retry on repeated candidate outbreak 249701763. The exact
  session join confirmed the first occupied breach at 50.10 sim
  seconds, sufficiently close to the first wall-cell break that
  both chose the same 2,144-to-2,740 zombie snapshots. Wave six, the
  final scheduled pair, launched under 71620 (inst19 PID 11924,
  inst20 PID 40036). No new eligible completion. The tested handoff
  remains waiting on native shutdown.

- At 11:19 Central, verified a change to avoid spending live game
  time on promotion-only waves after the frozen comparison is already
  ineligible. After a completed paired wave, the same existing
  eligibility function checks missing evidence, overlap and repeats.
  An irreversible failure retains both arms' existing journals and
  ends additional reserved waves. Complete valid comparisons must
  still pass the original wins and saved-fraction checks. The actual
  188952 reference timeout on a known outbreak would have stopped
  after wave one, avoiding five further scheduled pairs.
- All 302 script tests passed against combined candidate source,
  including complete six-wave valid comparison and one-wave invalid
  reference regression, with clean patch applicability. Replaced
  only the waiting handoff with PID 41040, still waiting on exact
  71620. New staged patch analysis/coverage-portable314/tmp/police-study-with-holdout-stop.patch
  and handoff log analysis/coverage-police-study-handoff.log. The
  current games and source were left in place. Reserve candidate
  inst19 PID 35092 remained live on the repeated outbreak. No new
  official result at this check.

- At 11:17 Central, preserved compact native crowd snapshots for
  reserve wave five in analysis/coverage-team-c81131e97f/police-native-audit.json
  (40,215 bytes total). Candidate inst19 PID 35092 still plays repeated
  outbreak 249701763, exact native session header 1795194822621. The
  first wall-cell break was at 49.70 sim seconds. At 50.47 and 70.47
  sim seconds the native zombie counts were 2,144 and 2,740 (+27.8%),
  and living civilian counts were 4,524 and 3,254. This window uses a
  physical wall-cell break, not a proven occupied-zone penetration or
  a terminal score. The retained data can later join a campaign result
  by copy, exact header and outbreak and recompute an occupied-breach
  window. The reference again paused indefinitely on 1067415937.
  Operator 71620 and handoff 71480 remain live. Production hash matched.

- At 11:13 Central, wave four candidate retried at 9.99% on repeated
  outbreak 2033973644. It adds no fresh result. Wave five launched
  (inst19 PID 35092, inst20 PID 66200) under operator 71620. The combined
  study handoff PID 71480 is still waiting.
- Audited breach recovery against archived real game outcomes. For the
  older fixed-layout 230c8ceb72a1b1a3 discovery cohort, the 72 distinct
  >=35% games exposed a median of 2,202.5 sheltered civilians and the
  35 below-target games exposed a median of 2,121. A 49.79% clear
  recorded 2,224 exposures. Breach exposure alone is not sufficient
  to rank across these strategies. In 24 aligned archived
  speed/outbreak crowd windows, the median ratio of zombies 20 sim
  seconds after the first occupied breach to zombies at breach was
  0.695 for five qualifying normal-speed runs versus 0.827 for seven
  below-target runs. At half speed it was 0.524 in one qualifying
  run versus 0.634 for eleven below target. This is observational
  and does not isolate a Missile effect. Compare both exposure
  and post-breach pressure relief on future live trials before
  strengthening the breach-only reward. No changes to reward or
  active policy.

- At 11:11 Central, combined the Police path trial, matched reserve
  reference and native loadout receipt changes in one staged patch,
  analysis/coverage-portable314/tmp/police-and-loadout-study.patch.
  Ran all 301 script tests against the combined source and verified
  applicability. The 189952 crossed experiment still compares the
  same two frozen policies and prepares no new loadout strategy during
  its paired waves. Both arms collect opening offers and native
  remaining SP so a later discovery batch can test one purchase
  preference with actual budget evidence. The selection and reward
  of the paired study stay as designed.
- Replaced only the waiting handoff helper: PID 71480 now waits for
  the same exact operator PID 71620 to finish. New handoff log
  analysis/coverage-police-loadout-handoff.log. The prior wait-only
  PID 68120 is gone. Verified the current campaign operator and
  inst20 PID 34288 remain live and the tracked runtime files still
  match HEAD. Fourth-wave reference retried again at 9.94% on
  previously seen outbreak 694232781. No new eligible candidate score.

- At 11:09 Central, reserved wave three completed with a battle-clock
  timeout on repeated candidate outbreak 249701763. No official score.
  Wave four is live on inst20 PID 34288 and inst19 PID 69716. Both
  again emitted the wave-two outbreak IDs. Operator PID 71620 and the
  queued Police study handoff PID 68120 remain live.
- Strengthened staged loadout-before-breach.patch to require a
  session-bound native planning purchase receipt before READY for its
  remaining skill budget. No reconstruction from local deltas, and
  missing, invalid, post-READY or cross-session evidence remains
  unknown. All 300 script tests passed against isolated source,
  joint applicability passed, and the staged parser read native
  inst20 session 1795194483119: one SP remains, 20 paratroopers
  in stock. On an observational dry run using that receipt and the
  prior same-outbreak 55.43 s occupied breach, the staged mutation
  could propose CallArms, Demolition, Firebomb, Heli, Missile, Rally,
  SeekDestroy and Stungas. Bomber's first effect came too late.
  This check made no trained weights, live input, or changes to
  reserve eligibility. The live and queued experiments are preserved.

- At 11:05 Central, verified why correcting the opening catalog alone
  does not restore Missile exploration: starter substitutions require
  both an earlier effect and no greater cost than the current purchase.
  The Police-only policy's existing preference costs 1 SP and has an
  8 s first effect. Staged an evidence-gated alternative in
  analysis/coverage-portable314/tmp/loadout-before-breach.patch. It
  records remaining SP from confirmed native purchases at READY,
  consistently reads Missile/Nuke effect timing, and in the absence
  of an earlier proposal lets search consider a one-purchase
  replacement that fits the confirmed budget and can take effect
  before the previously observed occupied breach. Never forces the
  purchase or bypasses native legality. This supersedes the isolated
  timing-only patch. Fixture proposes Missile at 2 SP/32.5 s with a
  recorded spare SP and 49.9 s breach, and refuses unknown budget,
  insufficient SP, unknown breach, or arrival at/after breach.
  All 299 script tests passed against isolated candidate source.
  Both staged study patches pass joint applicability. Nothing
  changed in the live operator or the queued Police study.
- The third reserved candidate battle is still active under 71620.
  Its latest journal matched prior outbreak 249701763. The native
  in-battle snapshot is not an official score or a new eligible game.

- At 11:03 Central, preflight passed for all six next-study copies
  inst13-16 and inst19-20. The current candidate is still playing the
  repeated outbreak on inst19 PID 69796. Handoff PID 68120 remains
  waiting for the exact operator 71620.
- Explained the missing Cruise Missile entry in starter ability evidence.
  The normal owned inst19 dump has a 2 SP purchase cost, 30 s unlock
  and 2.5 s flight, with no arrival_seconds field. The opening-offer
  reader skipped it despite verified unlock and affordability. Native
  Nuke timing analogously uses delay_seconds but exceeds the L1
  starting budget at 15 SP. The staged opening-loadout-timing.patch
  records those native timing fields with the same unlock and cost
  checks. All 29 focused training tests passed and replay of the actual
  dump returned Police 1 SP/8 s and Missile 2 SP/32.5 s. Both D: patches
  pass the joint applicability check. The fix concerns evidence and
  search suggestions; the current game masks, prices, actions and
  queued Police-path study remain unchanged.

- At 10:59 Central, reserved wave three repeated the wave-one native
  outbreak seeds on both copies. The GRU reference on inst20 again
  timed out continuously paused on 1067415937, this time at 8.97 sim
  seconds. Frozen candidate inst19 PID 69796 was still playing on
  249701763. Any score there is a same-outbreak repeat and cannot
  add a fresh held-out sample. Existing operator 71620 remains live
  and the Police path handoff PID 68120 is still waiting.
- Cross-run audit grouped candidates by frozen team, GRU base and
  recorded view revision, screening for fresh L1, known end-game
  scores, duplicate seeds and overlaps with 1,042 archived discovery
  seeds. Among 15 layout-free cohorts (34 attempts), only one
  eligible natural finish was found and it saved 0%. From the older
  layout-replay runs, team 230c8ceb72a1b1a3 on the recorded v2
  overview averaged 36.28% in 33 distinct completed games screened
  against discovery. Its first three ten-game blocks of eligible
  completions averaged 36.50%, 36.88% and 34.79%. This is a
  descriptive archive audit and cannot qualify the autonomous policy.
  Reserve rotation is insufficient when the fitted preparation policy
  reproduces native outbreak seeds. A future consistency candidate
  needs to generalize across more actual fresh preparation results.

- At 10:56 Central, the second fresh reserved candidate outbreak
  (2033973644, inst20) ended at 10.00% officially saved at retry,
  234.12 simulated seconds, with seven stock-confirmed Police drops.
  Both occupied shelters were penetrated and 2,362 of 2,365 sheltered
  civilians were exposed. Frozen bf3fc52369fc3746 now averages 9.96%
  across two eligible reserved retries, with zero natural completions
  for the consistency gate. Reserved wave three launched (inst19 PID
  69796, inst20 PID 57840) with operator 71620 still live.
- One-time local handoff PID 68120 is waiting for the exact active
  operator to exit naturally. It verifies the idle machine, at least
  10.5 GiB RAM and 3 GiB D: space, frozen policy/checkpoint fingerprints,
  a clean tracked checkout and the staged patch hash before applying
  and committing the Police path comparison. It then launches seed
  189952 on discovery inst13-16 with separate reserves inst19-20.
  Handoff log analysis/coverage-police-line-handoff.log, study
  analysis/coverage-layout-free-189952-drive-d.log. Current checkpoint
  hash matched. Handoff confirmed waiting, study launch still pending.

- At 10:54 Central, reserved wave two remained live under operator
  71620 (inst20 PID 68420, outbreak 2033973644). Captured compact native
  deployment trails, shelter placements and wall-cell breach locations
  before the game rotates its journal. D: artifact
  analysis/coverage-team-c81131e97f/police-native-audit.json is keyed
  by copy and journal header, and holds events only, with no outcome
  inferred from snapshots. On this board the fourth Police drag passed
  within 61 m of the first subsequent native wall-cell breach, while its
  last recorded trail point was 650 m away. An existing Garrison
  placement was 72 m from that breach. Geometry alone does not explain
  damage or confirm where the officers moved after landing.
- Validated the actual next Police comparison policies against the staged
  source and resumed base 8a691469a829158d: endpoint bf3fc52369fc3746 and
  path 847df0f375da30cf differ only in police_line_targeting and share
  all eight preparation genes. No layout replay. The current reserved
  candidate is still playing; its snapshot is excluded from official
  performance. Deploy the tested patch only once the operator is idle.

- At 10:50 Central, the 188952 comparison had nine scored discovery or
  eligible reserved rows for the two frozen policy arms on READY layout
  418150907bbd395c, including repeated outbreaks in the crossed discovery
  design. First deployment times overlapped between the two 35% clears
  (4.03-11.83 sim seconds) and seven retries (0.87-14.33). First occupied
  breach times also overlapped (52.97-57.70 vs. 49.87-60.57 seconds).
  Breach exposure differed (1,588-1,606 vs. 2,265-2,365 civilians).
  This is a small descriptive check, with no causal claim. Reserve wave
  two remains live under operator 71620, candidate inst20 PID 68420.
  Its GRU reference retried at 9.94% on previously seen outbreak 694232781.
- Native Police deployment receipts log officer counts along the drag
  path. The reserved inst20 first drop had four officers delivered along
  the route, with an interior native center. The model currently scores
  the end cell only. Staged an optional two-arm police-line trial in
  analysis/coverage-portable314/tmp/police-line-study.patch, including
  the earlier reserve reference correction. The candidate scores nine
  sampled positions along each legal drag using the existing battle
  weights. It changes only the Police endpoint preference while a
  Police gesture is pending, and logs the confirmed native trail bounds.
  Same frozen starting policy, legal masks, execution and rewards.
  All 298 script tests passed against the isolated candidate source,
  including Firebomb parity and full game-free pairing for both studies.
  The patch applies cleanly and waits for the existing run to finish.
  Production hash matched.

- At 10:46 Central, frozen candidate bf3fc52369fc3746 scored 9.92% at
  retry on its first eligible reserved outbreak (249701763, inst19).
  Same READY layout 418150907bbd395c and Police deck as discovery.
  Seven confirmed drops began at 0.87 sim seconds. Occupied breaches
  first appeared at 49.87 sim seconds and exposed 2,354 civilians,
  versus 1,588 and 1,606 on the two discovery clears. This official
  retry is a severe loss. The three-block consistency check requires
  natural terminal games and treats a retry as an incomplete attempt.
  Reserved wave two started under operator PID 71620.
- Staged an opening-cast-only holdout fix in ignored
  analysis/coverage-portable314/tmp/opening-cast-reference.patch. The
  experiment will use its own frozen unbiased discovery policy as
  the reserved reference and record its policy ID. The unchanged
  discovery qualification and holdout rules still gate promotion.
  Verified a game-free two-wave discovery and six-pair reserve
  regression, all 82 campaign tests, and patch applicability. Pending
  the normal idle boundary. No changes to the running process, game
  settings, checkpoint, reward, or official evaluation data.

- At 10:39 Central, seed 188952 finished the crossed discovery comparison.
  Frozen opening-bias bf3fc52369fc3746 posted official clears of 39.89%
  (outbreak 162782703) and 38.74% (2949929277). Its other official retry
  scores were 9.96% and 10.00%, for a four-game mean of 24.65%.
  Reference 75de0cafd4052843 averaged 9.86% across four retries. The eight
  games covered five distinct native outbreak seeds and used READY layout ID
  418150907bbd395c. On matched outbreak 2949929277 the challenger first
  deployed at 11.83 sim seconds versus the reference's 4.80; the result
  does not establish a benefit from earlier deployments. Both arms used
  Police paratroopers. The two distinct qualifying clears triggered reserved
  evaluation on inst19 and inst20 under the same operator PID 71620.
  No held-out result or promotion yet. The goal requires three consecutive
  blocks of ten distinct scored held-out outbreaks at a mean of at least
  35% per block, with one frozen policy.
- At 10:44 Central, reserved inst19 was still playing on native outbreak
  249701763, absent from 1,344 distinct archived outbreak IDs checked across
  discovery and reserved campaign journals. Its live snapshot is not an
  official result. The bare GRU reference on inst20 timed out from a
  continuous pause at 9.17 simulated seconds, with no official score; its
  outbreak 1067415937 also appeared in a prior reserved run, and the evaluator
  flagged it as overlap. This rules out promotion from the scheduled six
  pairs under the current strict complete-pair test. Remaining candidate
  scores can still establish standalone held-out performance when fresh and
  complete. Keep the process running. Future opening-bias comparisons need
  the actual discovery control as their reference if testing the bias alone.
- Retrospective discovery audit retained the latest scored L1 row per native
  outbreak. All 29 distinct outcomes with detailed READY receipts recorded
  at least one occupied zone breach and opened with Police paratroopers.
  Older archived builds/layout-replay policies often opened with Cruise
  Missile, including the best archived runs. This comparison is descriptive:
  layouts, decks, action policies and runtime revisions differ. The current
  winner's observed starter offers did not include Cruise Missile.

- At 10:27 Central, verified separate collapse diagnostics and retry gates
  with both PopulationPressureTests passing. A first observed zombie/civilian
  tie is a warning. A native clear in seed 187952 was first outnumbered at
  63.57 sim seconds and ended at 10.37% saved. In the finished discovery
  block, 10 of 15 scored games fell below 10% officially saved, four were
  native clears, and the mean was 11.02%. One planning timeout was unscored.
  No candidate qualified for reserved evaluation. Across blocks, the retained
  75de0cafd4052843 averaged 18.25% on six distinct discovery outbreaks.
- Isolated inst17 debt recovery retest with frozen b041d52f8070f2b2 and
  seed 187954 reduced Cancel decisions from 28 to 12 after six cooldowns.
  The policy switched mainly to gates and ability purchases/refunds and
  still ended $401 over budget. See analysis/coverage-debt-cancel-retest-188952.json.
- Commit f85e52b passed 297 script tests, 60 Observatory tests, model parity
  and graph assertions. Opening-cast comparison seed 188952 started at
  10:25 Central with operator PID 71620, directory analysis/coverage-team-c81131e97f,
  log analysis/coverage-layout-free-188952-drive-d.log. Verified all four copies
  reached their planning boards (inst13 PID 67608, inst14 57792, inst17 70268,
  inst18 37264). Discovery results pending. Production checkpoint hash matched
  and Observatory PID 12628 remained live.

- At 10:19 Central seed 187952 finished its third wave and
  opened the fourth with the same operator PID 17560. Retained
  75de0cafd4052843 retried at 8.65% on outbreak 2949929277;
  its five scored discovery games now average 19.91%. The
  READY layout ID 418150907bbd395c repeated. First native
  Police delivery occurred at 12.30 seconds, close to the
  13.53 seconds of the 21.19% clear. The new candidates
  scored 3.11%, 10.37%, and 11.26%; no qualification.
- Checked launch receipts on the 8.65% run: eight sampled
  Police decisions resolved into four two-point gestures,
  four native spray starts and four stock decreases. The
  recorded deliveries followed spray start by 0.74-1.20 sim
  seconds. The selected count includes anchors; it does
  not show four rejected casts. Keep opening-timing reports
  tied to confirmed native deployment.
- Scoped the delayed recovery smoke retest to existing inst17,
  exact frozen candidate b041d52f8070f2b2 and the saved policy
  RNG seed 187954. The recorded initial planning roster still
  matches that copy. The game-free runner compiles, checks the
  established production hash, takes the operator lock, and
  records the live outcome in an isolated D: report. It is
  pending the idle boundary, separate from any performance claim.

- At 10:11 Central seed 187952 completed wave two. Frozen
  75de0cafd4052843 cleared outbreak 264985974 at 21.19%; it now
  averages 22.72% over 29.17%, 9.33%, 31.20%, and 21.19% on
  four distinct outbreaks. The current 31.20% and 21.19%
  clears share visible READY layout ID 418150907bbd395c.
  A different Battleship/hold proposal had the same ID and
  retried at 7.47% despite its first confirmed deployment at
  2.43 sim seconds. The other wave-two variants scored 8.65%
  and 10.00%. No qualifying outcome. Wave three reached READY
  on four copies under operator PID 17560. Observatory running
  and production checkpoint hash matched.
- The retained policy's confirmed first deployments were at 4.07,
  35.07, 1.63 and 13.53 seconds across those four trials. This
  makes a timing-only comparison worth testing; repeated poor
  outcomes after early deployments rule out treating timing
  alone as success. The staged optional policy preference
  fades through the first 30 sim seconds and ends after its
  first native stock spend. Existing masks govern selection
  and targets. Game-free crossed assignments confirmed that
  only the opening tool preference differs between arms.
  The timing and debt-cancel changes passed 109 focused script
  tests together in memory. The debt version changes the view
  revision to keep prior official scores separate. No edits to
  live code, checkpoint, rewards or qualification rules.

- At 10:03 Central the retained frozen policy 75de0cafd4052843
  cleared a third distinct outbreak, 1516456864 on inst13, with
  31.20% officially saved. It reached READY with one hold, 19
  Garrisons (nine inside occupied shelter), a Police deck and
  native layout fingerprint 418150907bbd395c. Live sampled
  decisions never recorded being outnumbered in this episode.
  The three frozen results now are 29.17%, 9.33%, and 31.20%,
  averaging 23.23%. They remain discovery results below 35%.
  Wave two has started under D: operator PID 17560.
- Wave-one different candidates scored 9.54% and 9.74%; their
  shipped layout identities and severe-outcome diagnostics are
  present. They were first outnumbered at 39.43 and 37.30 simulated
  seconds, then reached the living-population retry floor at 79.60
  and 113.50 seconds. Howitzer/hold timed out in planning at
  native debt $401 after 28 Cancel selections in 60 steps.
  A game-free episode reproduced the loop and verified a staged
  cooldown after two consecutive Cancels at unchanged debt with
  no pending gesture. With normal masks otherwise intact the
  policy chose Undo in the fixture, cleared the debt, then regained
  Cancel. No live source edits or automatic layout rollback.
  The repair fixture and 28 focused script tests passed.

- Seed 187952 launched at 09:57 Central on D:, operator PID 17560,
  output `analysis/coverage-team-5a1475dfe3`, log
  `analysis/coverage-layout-free-187952-drive-d.log`. Four discovery
  copies inst13,14,17,18; reserves inst19/20. Launch headroom 15.16
  GiB RAM and 18.92 GiB disk. Commit 0bfd827 continues from the actual
  provisional 75de0cafd4052843. The preparation sampler can evolve
  earlier unit/support variants and excludes previously scored
  prefixes from new candidate slots. The exact-source game-free
  fixture scheduled 12 new combinations, retaining independent
  reference slots. Native pre-READY records now include a visible
  layout ID. Battle diagnostics record the first outnumbered and
  retry-floor times, and mark known scores below 10% separately.
  All 295 script and 60 Observatory tests, parity and graph assertions
  passed. Retry criteria, official scores and rewards are preserved.
- Seed 186952 finished at 09:56. Fifteen scored games across 16
  attempts on 15 distinct native outbreaks averaged 10.92%, with
  12 scores below 10% and one timeout outside the mean. There
  were three native clears, none at 35%. Frozen policy 75de0cafd4052843
  scored 29.17% and 9.33% on two native outbreaks, mean 19.25%.
  Fire Mortar/corridor cleared at 15.77%, with five Fire Mortars
  at READY, two inside occupied shelter. Neither qualified for
  reserved evaluation or promotion. Production hash unchanged.

- At 09:48 Central on seed 186952, third-wave candidate 75de0cafd4052843
  cleared at 29.17% on outbreak 1841216589. It had one native hold
  and 19 Garrisons, including nine inside occupied shelters, and no
  confirmed Napalm. Candidate 9b0db969a4f77092 retried at 9.97% on
  outbreak 2062905415. The two session journals agree on all 24
  recorded placement events and their world geometry; their policy
  identities, outbreaks, and battle choices differ. A visible layout
  signature complements the native seed record and cannot establish
  seed identity. The Sniper option deployed two, one in occupied
  shelter, with 137 Sniper kills by 50.5 simulated seconds and 9.96%
  at retry. No 35% qualification. Operator PID 44548 is still live.
- A continuation regression fixture covers evolving a frozen parent
  whose earlier unequipped placement slot has already become a support
  preference. Tested with actual frozen winner 75de0cafd4052843: twelve
  more distinct unit/support proposals on existing rosters, preserving
  all battle weights and excluding the unchanged parent. It remains in
  memory pending the live trial boundary.
- On 88 retained sub-10% retry journals with an observed ratio crossing,
  the first sampled outnumbered observation was a median 11.55 sim
  seconds before the footer; 24 showed at least 35% saved at that time.
  A sample selected for known losses cannot measure false-positive rates.
  On ten logs with a pre-footer native snapshot at or below 10%, the
  median remaining wall-clock interval was 0.77 seconds. No case for
  an aggressive ratio-based retry from these data.

- At 09:40 Central, verified the retry guard: a playing board
  needs at most 10% living civilians and either at least 90% infected
  or a fresh episode-bound official snapshot at or below 10%.
  This protects evacuation outcomes. A raw outnumbered cutoff would
  trigger far earlier: wave-one logs showed ties or more zombies
  than civilians with 39.14%-48.43% on native live snapshots.
  An in-memory regression fixture records first outnumbered time,
  first live retry-floor time, and official scores below 10% as
  separate diagnostics. Timeouts and unknown scores stay unknown.
  No retry, reward, or production checkpoint changes are deployed.
- Seed 186952 completed two waves, eight distinct outbreak seeds.
  Wave-zero controls cleared at 10.62%; Spikes/corridor, Gas Mortar/hold
  and Oil scored 8.44%, 9.94%, and 9.74% at retry. All three prepared
  alternatives entered with Police only; the reference had Firebomb
  as well. Same battle logits allow different loadout decisions after
  planning changes. Native pre-breach snapshots on the alternatives
  already showed 31.50%, 33.28%, and 53.10% saved; losses began before
  the occupied breaches and continued afterward.
  Wave one recorded a native gate and six MLRS (two in occupied
  shelter), two Railguns, and two C4 placements across its three
  candidates. Scores were 7.80%, 9.99%, and 9.86%, reference 9.00%.
  Wave two launched with the same operator PID 44548. No 35% result.

- Preparation evaluation clarification at 09:34 Central: the game
  recalculates the outbreak seed when placement changes. A different
  seed in a preparation comparison is part of the full policy's result.
  Compare whole frozen policies across fresh boards and prespecified
  policy RNG seeds. Native seed matching can aid battle-only comparisons
  with the same preparation. Preserve evaluation deduplication and
  training-exposure checks. Runbook updated in 86edac5. An in-memory
  pre-READY geometry signature test ignores reorderings and changes
  when a placement moves; a read-only live probe confirmed execution
  on two owned copies. The telemetry is diagnostic and is not deployed.
- Seed 186952 first scored results: Spikes + corridor 8.44%, initial
  occupied breach at 50.93 simulated seconds; Gas Mortar + hold 9.94%,
  breach at 61.20 seconds. Both combinations appear in the saved
  proposal and native-receipt fields. Reference and Oil results
  still pending at 09:34, operator PID 44548 and Observatory running.

- At 09:30:56 Central all four seed 186952 games had reached
  battle. A read-only native sample at 2.9-5.1 sim seconds verified
  inst14 had an evacuation corridor and 45 Spikes tiles; inst17
  had one hold and two Gas Mortars; inst18 had 36 Oil tiles.
  The reference on inst13 had none of those structures or paint.
  In-occupied-shelter Garrison counts were 9, 9, 7 and 9 for
  inst13, 14, 17 and 18 respectively. Both Gas Mortars were
  outside occupied shelters at the sample. No completed results
  from the new block yet. No reward change or reserve evaluation.

- Seed 186952 launched at 09:30 Central on D:, operator PID 44548,
  output `analysis/coverage-team-9b44e71750`, log
  `analysis/coverage-layout-free-186952-drive-d.log`. Four waves on
  inst13, inst14, inst17, inst18; inst19/20 remain separate reserves.
  Launch headroom 14.89 GiB RAM and 18.92 GiB free disk. Commit 2e54583
  tests 12 distinct proposal combinations plus a rotating retained
  reference. The game-free fixture using the exact launch seed and
  present rosters covered 12 unit types and walls, gates, corridors
  and holds. Proposals differ only in preparation preferences.
  Actual native READY receipts and official outcomes remain separate.
  All 291 script and 60 Observatory tests, model parity and graph
  assertions passed. Production checkpoint SHA-256 matched.
- Seed 185952 ended at 09:29. Garrison site sampling scored 9.75%,
  8.84%, and one native clear at 17.51%, with one timeout excluded
  from the 12.03% scored mean. The four reference scores averaged
  7.04%; no native clear. All eight outbreak seeds differed. Ready
  sampled sites yielded 16 or 21 Garrisons, seven or nine inside
  occupied shelters. References all had 21 and nine. No qualifier
  or promotion; the provisional parent remains 922f9e1dcd8205c2.

- A game-free private PPO comparison fixture at 09:23 varied the
  occupied breach charge from 0.10 to 0.30 per exposure fraction and
  verified exactly threefold penalties with the same occupants and
  first-breach time, no double charges, and unchanged shelter credit.
  The opt-in comparison is in memory only. Test it after diversified
  preparation provides enough variation in actual defense and exposure.
  Neither active rewards nor the production checkpoint changed.

- Shelter-penalty audit at 09:22 Central. All eight seed 184952
  boards had an occupied penetration at 53.40-62.77 simulated seconds.
  They recorded 1,872-2,361 exposed civilians over the episode. The
  current 0.10 exposure coefficient contributed -0.0230 to -0.0290
  in reward, or 0.46-0.58 percentage points divided by the terminal
  score scale. It is not the infection or final-outcome penalty.
  In the no-win branch of L1 discovery, the survival integral ranks
  before the shelter-adjusted objective. A game-free rescore using an
  additional 2x exposure charge did not change the order of the three
  failed-arm means in seed 184952 or seed 182952. Existing data
  therefore does not show that scaling the term alone would affect
  these selections. No default reward or official evaluation change.
- Seed 185952 reached READY on four crossed-wave copies at 09:22.
  Generation 0 scored 7.66%, 4.72%, and 9.75%, plus one sampled-arm
  timeout without a terminal official score. The operator and
  Observatory remain active. The broader preparation fixture now
  verifies 12 distinct combinations using 12 available unit types
  and each of wall, gate, corridor, and hold over four waves, without
  modifying battle weights or producing a preset layout.

- Seed 185952 launched at 09:11 Central on D:, operator PID 72040,
  directory `analysis/coverage-team-0ce9d6bea2`, log
  `analysis/coverage-layout-free-185952-drive-d.log`. Uses the same
  four discovery copies and separate reserves, with 14.40 GiB RAM
  and 18.92 GiB disk available at launch. Commit e162fdb tests sampling
  legal sites after the policy chooses Garrison (25% uniform mix);
  the policy stays in control of building type and timing. Records
  verified pre-READY embedded payloads and occupancy. 289 script and
  60 Observatory tests, parity, graph and crossed assignment passed.
  Live receipts show 21 Garrisons with nine in occupied shelters on
  control inst15, and 16 with seven on sampled inst16. First scored
  results were 7.66% and 9.75% on different native outbreaks.
- Seed 184952 ended at 09:10. The eight games used eight different
  native outbreaks. The model built three MLRS on both of that
  candidate's trials, and two Gas Mortars on both trials of the other.
  MLRS scored 4.85% and 7.15%, Gas Mortar 9.75% and 7.77%. The
  Garrison reference averaged 10.27%, with a native clear at 26.70%.
  The MLRS kill counters were 2,678 and 2,832. These results
  demonstrate placement and activity, without isolating a causal
  survival effect. No discovery policy qualified.
- Wider preparation exploration is regression-tested in memory on D:
  using four existing idle-or-owned rosters and four mock waves. It
  proposes a less-explored equipped unit alongside a wall, gate,
  corridor or hold, varying order around the shelter preference.
  Twelve distinct combinations were scheduled without changing any
  battle weights. It retains a rotating reference trial and official
  survival selection. Actual traps, barriers and evacuation geometry
  will have separate native READY receipts. Neither the code nor any
  reward has been changed during the ongoing site comparison.

- At 08:59 Central, read-only live native state on seed 184952
  confirmed three MLRS on inst16 and two Gas Mortars on inst18 at
  53.17 and 52.23 simulated seconds respectively. None of those units
  were inside an occupied shelter at the sampled time. The trial
  recorded two paid gestures for each unit type; a paint gesture can
  create several entities. MLRS retried at 4.85%, Gas Mortar at 9.75%.
  The first completed control retried at 4.03%. These scores were
  on different native outbreaks. The active trial remains PID 24440.
  A regression-tested in-memory change records payload-resolved
  embedded unit counts and their occupancy at READY in future ledgers.
  It distinguishes unit counts from paid gestures and makes no change
  to observations, rewards or live code during this run.

- Seed 184952 started at 08:57 Central on D:, operator PID 24440,
  output `analysis/coverage-team-858f2e225f`, with log
  `analysis/coverage-layout-free-184952-drive-d.log`. Full-availability
  inst15-18 share MLRS and Gas Mortar. Each preference is compared with
  frozen reference 922f9e1dcd8205c2 on two crossed copies. The policy
  chooses the actual tools and sites using native masks. inst19/20 remain
  reserved. Launch headroom 13.84 GiB RAM and 18.93 GiB disk, production hash
  matched. Commit 5555b89. 287 script tests and crossed scheduling
  fixtures passed, including the saved-fit retest path.
- Seed 183952 ended at 08:56. Purchase sampling produced a Firebomb-only
  deck in two of four games; all four reference games entered with
  Police and Firebomb. Sampling saved 7.96% on average versus 9.23%
  across the reference. The two native matched outbreaks both kept the
  same deck in both arms and had lower sampled-arm scores; the altered
  decks had no matched reference outbreak. No qualification.
- The prior 48 model-built scored starts left $82 in 45, $211 in one
  and $220 in two, out of $3,111. They used 92.93%-97.36% of their money
  and each had 28.95% initially sheltered. Use defense diversity for
  choosing experiments first. Raw spend would reward a behavior
  already common. The owned config specifies a 12-second first-shot
  delay outside occupied shelter for eligible guns. The earlier
  first-shot preference comparison produced no survival evidence. Any
  shelter-defense credit needs verified effective coverage or impact
  with a bounded ablation before use. No reward change in this run.

- At 08:53 Central seed 183952 completed the first purchase wave. The
  model sampled Firebomb twice instead of Police then Firebomb on one
  board and reached battle with Firebomb alone. Its official score was
  8.95%. The other sampled board kept both abilities and scored 7.82%.
  The reference boards scored 9.17% and 10.03%. All four native
  outbreaks differed. The second crossed wave is live under PID 67752.
- Embedded-defense audit of the same 48 recent scored starts: Garrison
  began equipped on all 48. Mortar and Sniper each began equipped on 11
  and neither was selected. Fire Mortar, Gas Mortar, Howitzer and MLRS
  were also equipped on subsets. The current plan's early Chemical Mine
  preferences are masked on all four discovery copies, leaving a broad
  placement bias and its explicit later Garrison preference. Native
  receipts show two distinct paid Garrison sequences, one repeated
  45 times. All 285 unconfirmed Garrison gestures in 714 attempts
  revisited a target already paid for at the same view. This documents
  repeated decisions, not a validated placement-legality rule.
- Four idle-or-currently-owned full-availability copies inst15-18
  share Gas Mortar and MLRS in their existing initial rosters. A
  game-free fixture on D: verified a proposed two-wave comparison that
  changes one unequipped preference to each of those shared embedded
  units. The opposite wave swaps control and candidate within each pair.
  Existing masks, spends, and official evaluation apply. A fixture also
  verified the saved-fit retest with the renamed arm variable. These
  changes are staged in memory until the active purchase trial stops.

- Seed 183952 started at 08:46 Central on D:, operator PID 67752,
  output `analysis/coverage-team-6625fd1484` and log
  `analysis/coverage-layout-free-183952-drive-d.log`. Four discovery copies
  and two separate reserves. Launch headroom was 13.55 GiB RAM and
  18.93 GiB free disk. Commit 45304f1 adds one opt-in comparison: once
  the model decides on a purchase, choose among legal purchases with an
  equal mixture of model probabilities and uniform exploration. A private
  generator preserves battle RNG and the usual masks and receipts remain
  in force. The paired arms differ only by this flag and swap copies in
  wave two. The scheduling fixture, 286 script tests, 60 Observatory
  tests, model parity and graph check passed. Production hash matched.
- Seed 182952 completed eight fit-independent comparisons on four
  matched native outbreaks. Learned cast-tool biases averaged 8.99%
  officially saved across four results versus 9.83% for the reference.
  Both had the same Police and Firebomb loadout. No policy reached 35%
  and no reserve evaluation ran. The mean tool-probability distance
  across 4,238 same-state checks was 0.00000466, so this update barely
  changed the distribution. The best official score was 12.91%, a
  native clear by the reference.
- L1 regression audit: the documented 1x/2x benchmark replayed a saved
  formation before battle on every board. Across 24 trials it had 21
  scores at or above 30%, and arm means of 32.24% and 35.90%. Of 411
  fresh native-seeded scores at or above 30% across search ledgers, 410
  recorded layout replay receipts. The sole exception was the 34.98%
  fitting-outbreak result from seed 179952. The recent model-led
  comparison set of 48 scored fresh starts (19 outbreak seeds, excludes
  flagged fit overlaps and seed 182952) averaged 11.46%, with all 48
  using Police and Firebomb and no scores at or above 30%.
  The old 2x layouts recorded a zone, gates, walls, a corridor and
  Garrisons. The latest model-built boards began with 28.95% sheltered
  versus 25.30% in the old benchmark, and their first occupied breaches
  occurred later. Setup and battle conditions both differed, so the
  results identify a change in evaluation conditions and do not isolate
  the effect of the layout or prove regression of a fixed policy.

- D: storage audit at 08:40 Central found 18.77 GiB free. The owned game
  copies account for 3.59 GiB, including 2.70 GiB of game assets and
  547 MiB of text dumps. Analysis accounts for 1.63 GiB when counting
  each file once. All 94 frozen search bases are hard links to one
  11.82 MiB file, so their apparent 1.07 GiB duplication is already
  avoided. The 655 MiB verified replay archive preserves the prior
  5.41 GiB reduction. The legacy input DLL debug compiler cache is
  9.35 MiB. Automatic execution review blocked its removal, so the
  cache remains present. If more room is required, first inventory idle
  game copies for retirement, preserve their logs and saves, and keep
  the four trial and two reserve copies. Archive old text evidence
  separately only with verified restoration. No source installation
  or C: worktree access.
- The active seed 182952 completed its four fitting games at 7.01%,
  8.76%, 9.33% and 9.99% saved on retries. The first crossed comparison
  wave reached READY on all four copies at 08:40. PID 40204 and
  Observatory PID 12628 remained active. The production checkpoint and
  release input DLL SHA-256 matched. No new experiments were started
  for the storage audit.

- Seed 182952 started at 08:32 Central on D:, trainer PID 40204,
  output `analysis/coverage-team-5cc246e6ce`, and log
  `analysis/coverage-layout-free-182952-drive-d.log`. Launch headroom
  was 12.63 GiB RAM and 18.93 GiB disk. Commit d3b08fc applies the
  same bounded real-outcome update to the cast-tool logit biases
  only. A sampled wait or other non-cast decision contributes the
  negative probability of each legal cast, while selected casts
  contribute their positive score gradient. Preparation and target
  ranking stay fixed to provisional parent 922f9e1dcd8205c2.
  Opposite copy pairs again evaluate separate fits. On comparison
  decisions the same-state audit measures changes in the masked
  tool distribution. No synthetic simulation or production PPO.
  Autodiff and assignment fixtures passed. All 285 script and 60
  Observatory tests passed. Production hash matched.
- Seed 181952 finished at 08:31 with eight scored fit-independent
  comparisons across four matched outbreaks and no reserved evaluation.
  Candidate 922f9e1dcd8205c2 scored 29.75% on 3710795766 versus
  reference 8.84%, and 8.63% on 59754920 versus reference 11.99%.
  Candidate 785412d13768986f scored 6.08% versus 8.38% and
  9.63% versus 9.62%. The two learned target matrices changed the
  highest-scoring legal target on only 2 of 96 audited decisions.
  The 29.75% clear had 0 differences among 12 decisions, so the
  observed high score does not establish a benefit from the target
  update. The 35% consistency requirement remains open.

- Seed 181952 started at 08:12 Central on D:, trainer PID 29440,
  output `analysis/coverage-team-97205dff9e`, and log
  `analysis/coverage-layout-free-181952-drive-d.log`. Launch headroom
  was 12.82 GiB RAM and 18.93 GiB disk. Commit 9988b6a uses the real
  outcome gradient unchanged, fits two updates on separate copy pairs,
  and evaluates each on the opposite pair in two swapped waves. Copies
  inst13/inst16 and inst14/inst15 each provide a two-copy fit and the
  other fit's comparison. Native seed overlap remains excluded for
  each fit. The counterfactual rank audit recomputes the other arm's
  highest-scoring target on the same actual observation and legal
  mask, without any gameplay input or prediction of action outcomes.
  Reserved copies inst19/20 remain separate. The fixture verified
  assignments and matching policy seeds after swapping. All 284 script
  and 60 Observatory tests passed. Production hash matched.
- Seed 180952 finished at 08:11 with four scored, fit-independent
  battles on two native outbreaks and no reserved evaluation.
  On 2340624381 the candidate retried at 9.87% and the reference at
  6.84%. On 907435050 the candidate retried at 4.86% and the reference
  cleared at 28.63%. The candidate averaged 7.37%, reference 17.74%.
  Both arms started every battle with 21 Garrisons and logged 30
  Firebomb impacts each. The same-copy, same-seed crossover did not
  reproduce the candidate's fitting-outbreak peak. The exact reference
  f0fbb68332c444bb leads the next fit.

- Seed 180952 started at 07:58 Central on D:, trainer PID 35000,
  output `analysis/coverage-team-aa709acd93`, and log
  `analysis/coverage-layout-free-180952-drive-d.log`. Launch headroom
  was 12.78 GiB RAM and 18.94 GiB disk. Commit 1310ca3 restores exact
  frozen reference f0fbb68332c444bb and candidate 2a29db14a2a96fd9
  from the saved fit and trial ledger. Both run on each of inst17 and
  inst18, which the fit did not use. Match the policy seed on both
  copies and both waves. Exclude all fit outbreaks from comparison
  fitness even when a fit episode was incomplete. inst19 and inst20
  are reserved for the promotion gate. No new copies were created.
  The restore and assignment fixture passed. All 282 script tests
  passed and the production checkpoint hash matched.
- Seed 179952 finished at 07:57. The frozen learned candidate cleared
  with **34.98% officially saved** in 131.9 simulated seconds on
  outbreak 1723230497 and retried at 7.27% on 3811417467. Both
  outbreaks were used during fitting. The reference cleared at 25.42%
  on fit outbreak 2374956122 and retried at 9.97% on independent
  outbreak 59754920. Three of four comparison battles therefore had
  fit overlap, leaving zero independent candidate outcomes. The
  34.98% score counts as an observed real-game peak below the target.
  Reserved evaluation was deferred. Retest preserves the exact policy
  underlying the peak while separating the game copies.

- Seed 179952 started at 07:41 Central on D:, trainer PID 67192,
  output `analysis/coverage-team-d6931e4e15`, and log
  `analysis/coverage-layout-free-179952-drive-d.log`. Launch headroom
  was 12.80 GiB RAM and 18.94 GiB disk. Commit cf50c30 fits the cast
  cell-score rows to official outcomes from sampled real-game targets.
  It reads the signed score gradient at each chosen legal target,
  weights each scored episode by its leave-one-out outcome baseline,
  deduplicates fit outbreaks, and caps the update norm at 0.5.
  Only the cast cell-score matrix can change. The fit phase samples
  targets; the following comparison tests both frozen arms with the
  parent f0fbb68332c444bb's top-ranked-target mode. Repeated fit
  outbreaks are flagged and excluded from comparison fitness. No
  synthetic outcomes or changes to production PPO. The gradient
  matched autodiff and the fixture crossed the fit/evaluation boundary.
  All 281 script and 60 Observatory tests passed. Production hash matched.
- At 07:49, the live fit completed with four distinct scored
  outbreaks and 52 sampled ability target decisions. Official scores
  were 8.46%, 9.25%, 9.83%, and a 10.70% clear. It learned candidate
  2a29db14a2a96fd9 with update norm 0.0117941. The retained report
  `analysis/coverage-team-d6931e4e15/target-fit.json` matches the
  actual difference from frozen reference f0fbb68332c444bb.
  Exactly ten coefficients changed, all in the target matrix.
  Both frozen arms reached planning on all four copies in wave two.
  Official comparison results are pending.

- Seed 178952 finished at 07:40 with eight scored battles, one native
  clear at 29.17%, and no reserved evaluation. Sampled target mode
  averaged 9.33% across four distinct outbreaks and picked 15 of 50
  ability targets away from the argmax. Top-ranked mode averaged
  12.03% across four distinct outbreaks and picked all 69 at the
  argmax. On the three shared outbreaks, sampled versus top-ranked
  saved fractions were 9.26% vs 4.58%, 9.59% vs 5.47%, and 9.97% vs
  8.88%. The single 29.17% clear on 953610303 drove the higher
  top-ranked mean and does not establish consistency.

- Seed 178952 started at 07:26 Central on D:, trainer PID 62944,
  output `analysis/coverage-team-f00bffc967`, and log
  `analysis/coverage-layout-free-178952-drive-d.log`. Launch headroom
  was 12.84 GiB RAM and 18.94 GiB disk. Commit f58aa1d compares
  selecting the model's highest-scoring legal ability target with
  sampling its legal ability targets. Both arms preserve preparation,
  weights, Firebomb endpoint scoring and stochastic selection of
  battle tools. Target sampling uses a separate seeded generator, so
  it does not advance the tool sampler. Each copy runs both arms with
  the same policy seed. The native outbreak remains game-selected.
  The trial records the number of non-argmax ability targets. The
  fixture verified arm rotation and identity. All 279 script tests
  and 60 Observatory tests passed. Production hash matched.
- Seed 177952 finished at 07:26 with two native clears below 35%,
  five scored early retries, one timeout and no reserved evaluation.
  Endpoint reference 5679a1607b5acf9e scored 9.42%, 18.18%, 9.56%
  and 21.22%, mean 14.60% across those four distinct scored outbreaks.
  Line variant ae664d95bac32a1d scored 9.08%, 8.20%, and 9.79%, mean
  9.02% across three scored outbreaks, plus one battle-clock timeout.
  All eight started with 21 native Garrisons. On the shared seeds
  3811417467 and 2374956122 the endpoint scored 9.42% and 9.56%,
  and line scoring 8.20% and 9.08%. On shared seed 1084437502 the
  endpoint cleared at 21.22% and the line arm timed out. The
  18.18% clear credited 1,697 Firebomb kills. The 21.22% clear
  credited zero despite 30 native impacts. The batch did not
  support deploying line scoring as a default.

- Seed 177952 started at 07:07 Central on D:, trainer PID 70916,
  output `analysis/coverage-team-051d1d5ded`, and log
  `analysis/coverage-layout-free-177952-drive-d.log`. Launch headroom
  was 12.84 GiB RAM and 18.94 GiB disk. Commit 6ad7d46 compares
  endpoint-only scoring with scoring 9 samples along the full Firebomb
  segment once the model selects its first endpoint. It reuses the
  same learned row weights, live camera grid and legal mask, without
  a new observation/checkpoint schema. The native ledger retains the
  requested strike line from the game deployment event and blast count.
  Compare exact reference 5679a1607b5acf9e and one flag change. Each
  owned copy runs both arms, with shared policy seeds within pairs
  and independently selected native outbreaks. No simulation training.
  All 278 script and 60 Observatory tests passed. Network-output
  verification and graph checks passed. Production hash matched.
- Seed 176952 finished at 07:06 with two native clears below 35%,
  five scored early retries, one timeout and no reserved evaluation.
  Reference 0c63192f22089b99 peaked at 29.45% on outbreak 1222059323
  after a 9.25% retry on that same seed. The game credited zero
  Firebomb kills on the 29.45% clear. Its high score and repeated
  low score remain distinct live results of the same frozen policy.
  Discovery selected 5679a1607b5acf9e, with 23.23% and 8.27% on two
  distinct seeds, mean 15.75%, and 70 and 69 Firebomb kills.
  The other variant timed out once and retried at 9.74%.
- Read-only first-wave journals showed three confirmed Firebomb
  lines of 248.5 to 829.7 metres and 30 logged impacts each, within
  20.5 metres of their line. First impact occurred 11.96-11.97 sim
  seconds after the deployment event. The fourth confirmed line
  had no bomb events before the retry. The native data motivates
  matching the spatial scores to the geometry, and gives no effect
  attribution beyond the game receipts.

- Seed 176952 started at 06:49 Central on D:, trainer PID 61696,
  output `analysis/coverage-team-ca003d1e59`, and log
  `analysis/coverage-layout-free-176952-drive-d.log`. Launch headroom
  was 12.86 GiB RAM and 18.94 GiB disk. Commit 9e01055 compares two
  mirrored changes to the Firebomb cell-score weights around frozen
  reference 0c63192f22089b99. It preserves preparation, other cast
  weights and timing preferences. Each variant runs twice on rotated
  copies; the learned reference runs four times. A fixture verified
  both waves and a regression pinned the unchanged weights. All 277
  script tests passed. Production hash matched. A compact ready paint
  receipt and session-bound kill counters are retained with the trial.
- Seed 175952 finished at 06:48 with one native clear at 13.14%,
  four scored early retries and three timeouts. No reserved evaluation.
  The unchanged policy averaged 10.96% over its two distinct scored
  outbreaks. Oil retried at 9.79% and 8.28%. Spikes had one wall-clock
  timeout and an 8.86% retry. On the shared outbreak 2993894596 Oil
  saved 9.79% and Spikes 8.86%; both started with 19 Garrisons.
  The same native map counts, 45 Spikes and 36 Oil tiles, replicated
  in wave two on different copies. Every trial recorded zero
  outside-playable-area targets. In a first-wave snapshot, 73 zombies
  were within 20 metres of Spikes, and none were within 20 metres
  of Oil in its own game. This is exposure evidence from live state.
- Game counters credited first-wave confirmed Firebomb deployments
  with 0 zombie kills for Oil, 754 for the reference and 1,405 in a
  late snapshot for Spikes. These different outbreaks and outcomes
  motivate isolating the target weights. They do not establish causal
  action value or a relationship to official civilians saved.

- Seed 175952 started at 06:32 Central on D:, trainer PID 53364,
  output `analysis/coverage-team-0afbef6ec6`, and log
  `analysis/coverage-layout-free-175952-drive-d.log`. Launch headroom
  was 12.88 GiB RAM and 18.94 GiB disk. Commit 3f4040d fixes the
  layout-free discovery mask so raw placements and gates use playable
  cell centers, and building placements use their actual snapped target.
  Rectangle/segment masks and the final outside-action guard are retained.
  This revision starts a separate fitness comparison while keeping prior
  outbreak seeds excluded from reserved evaluation. All 276 script
  tests passed. Production hash matched.
- All four owned games reached planning and started battle. Two native
  tool-arm receipts each were followed by 45 Spikes tiles on inst13
  PID 71200 and 36 Oil tiles on inst14 PID 70580. The unchanged arm
  on inst16 PID 11340 had an empty native paint map. This was verified
  through a read-only, executable-checked read of the active games'
  signed-cell paint map, with no game input sent by the diagnostic.
  Both challenger boards entered with 19 Garrisons versus 21 for the
  unchanged arm. Official survival outcomes for 175952 are pending.
- Seed 174952 finished at 06:32 with two native clears below 35%,
  five early retries, one timeout, and no reserved evaluation.
  Reference 0c63192f22089b99 cleared at 12.69% and retried at 7.57%.
  Oil 1e11f2b8b5082df1 retried at 8.78% and 9.99%. Spikes
  56afb54bcb73a384 retried at 9.94% and cleared at 11.56%. Each
  challenger selected the utility twice per board, but all eight
  utility selections were outside the playable polygon and rejected
  before game input. The results could not test either utility's effect.
  Native initial rosters confirmed both tools were equipped.

- Seed 174952 started at 06:20 Central on D:, portable trainer PID
  71516, output `analysis/coverage-team-56e293130a`, and log
  `analysis/coverage-layout-free-174952-drive-d.log`. Headroom was
  12.90 GiB RAM and 18.90 GiB disk. Commit df9024f adds two controlled
  placement-preference neighbors for the selected cast policy. It replaces
  one unequipped preference with one of the distinct tools shared by
  the four starting rosters, holding all other weights fixed. Current
  alternatives are Oil and Spikes. Both variants and both controls move
  to different owned copies in wave two. The game selects native
  outbreaks and the model retains the normal legal, budget and
  targeting decisions. The native starting roster is logged at boot.
  A fixture verified both waves and their rotation. All 275 script
  tests passed. Production hash matched.
- A read-only audit found 122 distinct scored policy/outbreak pairs
  with verified READY and no layout replay. Garrison was the only
  building with a confirmed purchase. ChemMine appeared in 240 planning
  preference entries across those rows but is absent from all four
  current discovery rosters. All recorded initial sheltered fractions
  were below 30%, and there were zero 35% outcomes. Tool preferences
  and model selections are distinct from native placement receipts.
- Seed 173952 finished at 06:19 with three native clears below 35%,
  five scored early retries, and no reserved evaluation. Both first-wave
  cast neighbors started with 21 Garrisons and cleared at 13.53% and
  12.70%. The learned reference started with 21 and retried at 9.46%.
  The selected neighbor 0c63192f22089b99 cleared at 26.93% on outbreak
  852714485 with 21 Garrisons, six Paratrooper deployments, a Firebomb,
  and first occupied breach at 63.10 sim seconds. It retried at 7.95%
  on outbreak 1222059323, the same seed as the 9.46% reference retry.
  Its mean across three distinct discovery outbreaks is 16.14%.
  The other two second-wave neighbors retried at 7.91% and 8.77%.
  Observed survival gains did not reproduce across outbreaks.

- D: storage audit at 06:04 Central found about 18.9 GiB free. Consolidated
  84 identical immutable search bases from 11 physical files to one,
  removing 123,906,770 bytes of duplicate checkpoint storage. All
  existing paths still resolve to SHA-256
  257f0c7b1af2e0209d79686827cd67df06e041a118194e5ac3b4c326c0fd9e44.
  No staging files or loose binary dumps remain in the discovery copies.
  The active game's files, production checkpoint and replay archive were
  left in place. The experiment and all cleanup operations used only D:.

- Seed 173952 started at 06:05 Central on D:, trainer PID 46724,
  output `analysis/coverage-team-01e3c233bd`, and log
  `analysis/coverage-layout-free-173952-drive-d.log`. Launch headroom
  was 12.73 GiB RAM and 18.94 GiB disk. Commit 27c1190 adds a paired
  discovery experiment. Both variants keep the frozen GRU, learned
  planning preferences, timing preferences, camera controls, and legal
  masks fixed. Only the battle tool and target score arrays receive
  mirrored perturbations. Wave one includes the unchanged learned
  policy and frozen GRU. Wave two includes two runs of the learned
  reference and its two neighboring variants. The game chooses fresh
  outbreaks. Scores below 35% remain ineligible for held-out evaluation.
  All 273 script tests passed. Production checkpoint hash matched.
- Seed 172952 finished with seven early retries at 7.74% to 9.95%
  saved and one native win at 10.76%, below the 35% gate. Discovery
  selected 11f57118209db8fe, which built 21 native Garrisons and confirmed
  eight Paratrooper deployments and one Firebomb on outbreak 2188676306.
  There was no reserved evaluation. Among the three learned first-wave
  retries, the new metric put 8123d9518f39d948 first with 0.2201
  above-target area. It scored 9.10% versus 9.63% for 3e440a24cbc6bb8f,
  which lasted longer but had lower above-target area (0.1923). The
  earlier sustained population has not translated to 35% official saves.
  The 8123 policy repeated at 9.16% on a distinct outbreak in wave two.

- Seed 172952 started at 05:50 Central on D:, portable trainer PID
  62676, output `analysis/coverage-team-7bf5ba3e92`, and log
  `analysis/coverage-layout-free-172952-drive-d.log`. Launch headroom
  12.88 GiB RAM and 18.83 GiB disk. Commit c9c63c8 adds opt-in
  `--goal-margin` for controlled L1 discovery. When no official win
  distinguishes candidates, it integrates the observed civilian fraction
  above 35% during the same first 120 sim seconds. It keeps real scores,
  wins, rewards and reserved qualification rules intact. Its comparison
  revision separates the new ranking from the existing survival-area
  ledger. All 272 script tests passed. Production hash verified.
- Seed 171952 finished at 05:49 with seven scored retries, one
  continuous-pause timeout, zero native wins and no held-out stage.
  The two painted cast policies each started with 21 Garrisons, used
  the same cast timing, and confirmed four deployments. Timing plus
  shelter targeting 3e440a24cbc6bb8f scored 9.26% after 137.4 s on seed
  87945100, with first occupied breach at 48.17 s. Timing-only
  23c29cc693c2fe9c scored 9.79% after 100.9 s on seed 1770799578, with
  first occupied breach at 54.40 s. This single pair does not establish
  an action effect. No policy qualified or advanced.
- Native snapshot approximations ranked the same pair differently.
  Ordinary survival area was 0.4518 versus 0.3765 for targeting and
  timing-only, respectively. Above-target area was 0.1993 versus
  0.2137. That exposed the existing score's preference for time spent
  below the target. New trials compute the metric from decision traces,
  while official scores always come from the real game footer.

- Seed 171952 started at 05:38 Central on D:, portable trainer PID
  49060, output `analysis/coverage-team-ffb85cf6a7`, log
  `analysis/coverage-layout-free-171952-drive-d.log`. Headroom 12.89 GiB
  RAM and 18.83 GiB disk. Preserves click start and production hash.
  Commit 50da0fd reserves two discovery slots for a matched cast pair
  after the first wave when a paint-mode parent has a native salvo and
  occupied-shelter exposure. Both have the same learned timing weights.
  One also favors legal perimeter targets based on actual occupancy
  and zombies. Exact holdout selection and rewards are unchanged. All
  271 script tests passed. Prior receipts provide an eligible pair.
- 171952 wave one returned three early retries (5.70%–7.58%) and
  one continuous-pause timeout. Confirmed wave two started at 05:44
  with four fresh owned games. Two entered battle with 21 Garrisons
  and two with eight. Per-arm result receipts are pending. Host checks
  found 18.77 GiB free on D: and 9.91 GiB RAM with four games active.
  Observatory PID 12628 remained up and checkpoint bytes matched.
- Seed 170952 finished at 05:37 with seven scored early retries, one
  incomplete gameplay-key receipt, no native wins or held-out trials.
  The paint reference 10c063b71e9f3043 spent three Demolition charges
  and one Firebomb, breached at 85.10 sim seconds, and retried at 8.95%.
  The 4x-preference challenger also confirmed four deployments before a
  gameplay key UI-frame timeout at around sim 53. Its 51.77% at footer
  is an incomplete observation. This was separate from the earlier
  automatic-camera failure. The search now carries failed tool, cell,
  and phase from the rollout, while retaining incomplete classification.
- Another painted candidate reached READY with 21 Garrisons and spent
  five charges; only 11 Garrisons remained at its 8.44% retry. A separate
  8-Garrison candidate with ten deployments scored 7.64%. The first
  occupied breaches and official losses justify testing action locations
  alongside timing. Extra placements or successful casts alone do not
  demonstrate a survival benefit. No policy reached the 35% gate.

- Seed 170952 started at 05:25 Central on D:, portable trainer PID
  69072, output `analysis/coverage-team-a4a6da9b94` and log
  `analysis/coverage-layout-free-170952-drive-d.log`. Launch headroom
  12.94 GiB RAM and 18.83 GiB free. Keeps the verified click baseline
  and pairs 10c063b71e9f3043 with a challenger whose maximum-speed
  battle-tool logit is three lower. All speeds and gameplay choices
  stay available to the model. Confirmed deployment and official saved
  fraction are the comparison outcomes. Commit 677632e.
- At 05:26 the four 170952 worlds reached verified fresh planning.
  Two boards entered with 21 Garrisons and each logged three native
  Demolition deployments near sim seconds 20–22. Neither had recorded
  a 4x transition at that read. Both battles were in progress and full
  trial receipts are pending. Host check: 10.14 GiB RAM and 18.42 GiB
  free with four games running. Observatory listener PID 12628.
- Seed 169952 drained at 05:24 with seven scored early retries and an
  incomplete UI wait, no native wins or reserved evaluation. All starts
  verified click mode. inst14 policy 10c063b71e9f3043 selected
  place_paint on its second decision, entered battle in paint mode with
  21 Garrisons and $82, and retried at 4.21%. Two other candidate
  boards began with eight. This reproduces the large opening on a
  different copy via a model choice, without a survival gain yet.
- At sim 18.83 the paint-mode policy moved from 0.5x to 4x. It started
  with three Demolition charges and one Firebomb, logged a legal cast
  choice at one decision, and confirmed no spends across 126 decisions.
  Native speed and action records identify a timing failure candidate,
  without proving that speed caused the losses.
- The incomplete parent rollout lost confirmation during the automatic
  camera overview, after releasing a pan key. Commit 655a8d4 treats a
  UI-frame timeout only at camera overview as an unfitted view. The
  caller refreshes current native geometry. Gameplay receipts and other
  errors retain their existing behavior. A mocked regression verifies
  the distinction. All 269 script tests passed and the production
  checkpoint SHA-256 matched at launch.

- Seed 169952 started at 05:16 Central on D:, portable trainer PID
  71392, output `analysis/coverage-team-beed15c93f` and log
  `analysis/coverage-layout-free-169952-drive-d.log`. Launch headroom
  12.94 GiB RAM and 18.83 GiB free. Opt-in `--click-start` configures
  each stopped owned copy to start in native click mode and checks it
  in the verified fresh planning state. New comparison revision keeps
  inherited-mode scores out of the fixed-start ledger. If evaluation
  qualifies, reserved boards use the same start. Model-selected click
  and paint preference candidates leave all subsequent gameplay actions
  with the policy. Initial and READY modes are recorded. Commit b193e42,
  all 267 script tests passed. Production checkpoint hash verified.
- Audit of 108 historical recorded layout-free candidate starts found
  all seven openings with at least ten Garrisons on inst13. Current
  read-only native states confirmed paint on inst13 and click on
  inst14–16, matching their per-copy settings. The world config and
  balance files matched. Different persisted modes confound the old
  cross-copy comparison. Historical starts lack complete mode receipts.
- Seed 168952 drained at 05:15 with eight early retries and no wins.
  Matched scales 0.3111077 and 0.5111077 reached 9.58% and 9.90% at
  retry. The higher-scale candidate entered with 21 Garrisons on the
  paint-mode copy. The lower-scale variant entered with eight on a
  click-mode copy. The bracket is inconclusive as a scale comparison.
  No policy qualified for held-out evaluation or promotion.

- Seed 168952 started at 05:05 Central on D:, portable trainer PID
  70872, output `analysis/coverage-team-61e1c86039` and log
  `analysis/coverage-layout-free-168952-drive-d.log`. Launch headroom
  12.94 GiB RAM and 18.77 GiB free. Commit 70d2596 tests previously
  untried scales 0.3111077 and 0.5111077 around frozen parent 0.4111077,
  with the same genome otherwise and the GRU reference. A verified
  native discovery clear at or above 20% triggers this local search
  only. Official qualification, saved fractions, and held-out rules
  remain intact. All 265 script tests passed. Production hash verified.
- Seed 167952 drained at 05:05 with seven early retries, one timeout,
  no native win and no reserved evaluation. All eight copies started
  without observed startup fallback. cb77350565675243 retried at
  9.31% and 8.36% on different outbreaks from its 24.82% clear. Its
  conservative discovery mean is 14.16% for three distinct seeds.
  In the first repeat it entered with eight Garrisons and $809 versus
  21 and $82 in the earlier clear. The same first Garrison action
  selected the same cell and snapped pixel, with $0 spent on the repeat
  versus $72 on the clear. Native receipt differences appeared before
  the decision sequences diverged. Cause of the placement variance
  remains unverified. Corner sampling produced a new 19.68%-sheltered
  opening and a 5.59% retry. No policy reached the 35% gate.

- Seed 167952 started at 04:55 Central on D:, portable trainer PID
  70536, output `analysis/coverage-team-b2e80f522d` and log
  `analysis/coverage-layout-free-167952-drive-d.log`. Startup headroom
  12.95 GiB RAM and 18.84 GiB free. Carries forward exact provisional
  winner cb77350565675243 to test repeatability, with a separate corner
  sampling probe. Production checkpoint hash verified. Commit 1c29bd0
  handles pointer-sized invalid game module snapshots and retries the
  documented transient Windows error, up to four total attempts.
  Seed 166952 previously needed standard boot fallback for one overflow.
  Two mocked paths cover transient and terminal snapshot failures.
  All 264 script tests passed. Causal attribution in live startup unverified.
- Seed 166952 finished at 04:54 Central, one native win and seven early
  retries. cb77350565675243 cleared the horde with 24.82% officially
  saved at 174.1 simulated seconds, outbreak 1296320277. Its only genome
  change from 6a41db6d3b08aef0 was planning tool logit scale 0.4111077.
  Native READY showed 21 Garrisons, 28.95% initially sheltered and $82.
  Three native Demolition deployments had receipts. The result is a
  provisional discovery win below 35%. Reserved evaluation was deferred.
- The matched corner-sampling candidate 18c2c42a85d4ada1 chose a new
  rectangle pair on seed 3798721150. Its starting sheltering was 18.53%,
  versus 28.95% in the parent, and official retry was 6.39%. This shows
  policy-driven layout variation, without evidence of higher survival.

- Seed 166952 started at 04:44 Central on D:, portable trainer PID
  38836, output `analysis/coverage-team-9a5dba2492` and log
  `analysis/coverage-layout-free-166952-drive-d.log`. Startup headroom
  13.04 GiB RAM and 18.84 GiB free. Two discovery waves include a
  candidate with the same learned policy as the provisional parent and
  seeded samples from its masked rectangle-corner distribution. The
  policy still selects all tools. The corner draws use a separate RNG,
  and the sampling flag is part of the frozen policy identity. All 262
  script tests passed, including mask and seed repeatability. Production
  checkpoint hash verified at launch. Commit ddb5e58.
- Audit of 87 recorded fresh layout-free candidate starts under verified
  READY found 62 at 28.95% and 22 at 19.68% initially sheltered, with
  three outside those two counts. This is a count of rows, with replayed
  native seeds possible. It motivates directly sampling legal endpoints.
- Seed 165952 drained at 04:44 with eight scored early retries and no
  wins or reserved evaluation. Matched footprint-only and early-fire
  candidates saved 8.94% and 8.68% on separate outbreaks, with first
  occupied breaches at 49.87 and 49.67 simulated seconds. Candidate
  101bae34c9515b9c had 21 Garrisons and 48.11% alive at 66.63 seconds,
  then retried at 9.99% after 155.6 seconds on seed 1296320277. No
  candidate qualified for promotion or the 35% consistency test.

- Seed 165952 started at 04:34 Central, portable D: trainer PID 53252,
  output `analysis/coverage-team-c31b6d0999` and log
  `analysis/coverage-layout-free-165952-drive-d.log`. Launch headroom
  12.94 GiB RAM and 18.84 GiB free. Two discovery waves compare the same
  learned plan, weight and building-specific reach with and without the
  occupied-shelter first-shot preference. It affects placement scores
  when the resolved outside first-shot delay is positive. Legal options
  and reward evaluation are preserved. Commit 9188555. All 261 script
  tests passed. Production checkpoint hash verified at launch.
- Seed 164952 drained at 04:34 Central with eight scored retries, no
  native wins, and no reserved evaluation. First-corner 73b85480651905dc
  moved the second rectangle. Native initial sheltering fell from 28.95%
  to 19.21%, and retry was at 9.59% on seed 1317865041. Provisional parent
  6a41db6d3b08aef0 retried at 8.24% and 8.95%, so its 10.19% native win
  remains unreplicated. No candidate reached the 35% gate. At the next
  launch all owned debug-dump directories had zero loose .state files.

- Seed 164952 started at 04:23 Central on D:, portable trainer PID
  9476, output `analysis/coverage-team-8469fed87e`, log
  `analysis/coverage-layout-free-164952-drive-d.log`. Headroom at launch
  13.06 GiB RAM and 18.84 GiB disk. Two discovery waves compare the
  endpoint-only parent to one candidate that also scores the model's
  first corner by its best available legal rectangle. It uses the same
  learned weight and native action masks. No coordinates are supplied or
  forced. Commit e5105e9, all 260 script tests passed.
- Four read-only initial snapshots in the second wave of 163952 showed
  the same shape limitation. For rectangles up to 2,500 m perimeter,
  the model's repeated starting corner could enclose at most 1,605 of
  8,142 civilians (19.71%). Other legal-corner pairs reached 3,174
  (38.98%) before affordability and land-cap checks. The parent and both
  opening candidates drew identical two shelters covering 28.95%.
- Seed 163952 finished at 04:23 Central. First-wave endpoint-only
  candidate 6a41db6d3b08aef0 recorded a native win at 10.19% and 221.2
  simulated seconds on outbreak 4137464895 with 21 ready Garrisons.
  It retried on the second distinct outbreak (975879945) at 9.26%,
  with eight ready Garrisons. Both sheltered 28.95% at READY. Other
  rows were early retries. The native win is below the required 35%,
  so no reserve or promotion. The candidate leads further discovery.

- Seed 163952 started at 04:12 Central on D:, portable trainer PID
  62696, output `analysis/coverage-team-1f2e9bd275`, log
  `analysis/coverage-layout-free-163952-drive-d.log`. Launch headroom
  13.04 GiB RAM and 18.84 GiB disk. One challenger scores candidate
  rectangle endpoints using the fraction of native civilians newly
  enclosed, only after the model selects the first corner. Existing
  shelter overlap, action masks, policy sampling, and reward evaluation
  are respected. Its numeric weight is part of the frozen policy ID.
  Commit c72d5fa, 259 script tests passed.
- Isolated read-only geometry on a verified fresh planning board at
  04:10 Central. Of 36 corner pairs inside the native playable polygon,
  one pair at 2,454 m perimeter enclosed 38.98% of the 8,142 starting
  civilians. It covered 362,786 m² in geometry. A 2,951 m rectangle
  enclosed 50.36% before checking budget or the native land cap. These
  estimates show untested planning options and provide no survival or
  affordability guarantee. No zone was drawn. Verified the diagnostic
  game exited. Removed an exact 7,535,369-byte loose binary generated by
  the earlier startup probe and retained its text companion.
- Seed 162952 finished at 04:09 Central with seven scored early retries,
  one timeout, and zero wins. Matched maximum-range 1b6a39133faf666d and
  footprint-range 9758e12bbba5d890 both built three Garrisons and scored
  9.99% at retry. First occupied breaches were 48.97 and 51.63 seconds
  on different outbreaks. Parent 8ee70506ad4ff889 replicated sustained
  defense twice, scoring 9.99% at 147.4 seconds with 21 Garrisons and
  9.38% at 134.8 seconds with eight. The parent stayed provisional.
  Reserved evaluation was deferred. No held-out qualifier.
- Resolved build rules specify a 12-sim-second first-shot delay for
  defenders outside occupied shelters. Only three of eight Garrisons
  were inside on two sampled boards. Treat this as an early-response
  opportunity for future exploration, distinct from estimated reach.

- Seed 162952 started at 03:59 Central, portable D: PID 6808,
  output `analysis/coverage-team-3d9cc26e20`, log
  `analysis/coverage-layout-free-162952-drive-d.log`. Headroom was
  13.06 GiB RAM and 18.83 GiB disk. Two discovery waves pair the same
  learned preparation preferences and weight with maximum-range and
  building-specific Garrison placement scores. Fast startup is enabled
  for discovery. All 258 script tests and 60 Observatory tests passed.
- Verified the shipped Garrison rule from the owned build's config and
  rule dumps. Radius is base plus per-meter reach times square root of
  the building's native footprint, capped at 262.5 m. Native building
  radii had 10th/50th/90th percentiles of 48.9/57.8/102.4 m across 6,532
  Boston buildings. All 15 sampled existing Garrisons matched their
  building centers exactly. Their derived radii ranged 43.9–196.8 m.
  Maximum-radius percentages reported earlier are an upper bound.
  Commit 7b07cef keeps that frozen reference and scores one challenger
  with building-specific radii. On four read-only world samples, the
  leading placement cell changed on three, and the coverage update
  took 180–720 us. This estimates reach without line of sight or combat.
- Seed 161952 finished at 03:58 Central. All eight discovery boards
  reached verified fresh planning in 26.94–26.99 seconds without the
  standard startup fallback. Seven ended in scored early retries and
  one timed out, zero wins. Ordered proposal 9d506e3b7bc6a4f0 produced
  eight Garrisons on two distinct seeds, retrying at 9.33% and 9.51%
  after 108.2 and 102.1 simulated seconds. Its selected mutation,
  8ee70506ad4ff889, also had eight Garrisons and lasted 148.4 seconds
  before an 8.99% retry. It is the provisional parent, with first
  occupied breach at 48.13 seconds on seed 3029904288. No promotion or
  reserved evaluation. The 35% consistency goal remains open.

- Seed 161952 started at 03:47 Central on D:, portable trainer PID
  49128, output `analysis/coverage-team-f0b57397a0`, log
  `analysis/coverage-layout-free-161952-drive-d.log`. Startup headroom
  was 13.03 GiB RAM and 18.84 GiB free disk. Two discovery waves carry
  forward 11b3a3535032048f and use opt-in `--fast-boot` from e9e5514.
  Fast boot still verifies the full fresh normal Boston board and retries
  standard startup if the short attempt fails. Reserved evaluation uses
  standard startup. All 257 script tests passed, including fallback.
- Isolated four-copy startup probe after seed 160952 drained. Changed the
  welcome wait in memory from 75 to 15 seconds and kept every other check.
  Verified each fresh planning board at 27.81–28.94 seconds, versus
  87.09–87.12 seconds in the previous four-worker discovery wave. The
  probe stopped all its games and verified no remaining owned processes.
  The 58–59 second difference is startup only. Campaign timing is logged
  separately; no game speed, training signal or outcome definition changed.
- Seed 160952 finished at 03:44 Central with seven scored early retries,
  one timeout and no wins. The shelter-first arm replicated coverage of
  both shelters (54.2% and 34.4% nominal range) with two Garrisons. It
  scored 8.89% at retry, and its first occupied breach was at 45.77 sim
  seconds versus 48.80 for coverage-only and 43.90 for the old parent.
  Those were different outbreaks. The placement change replicated, while
  a repeatable gain in protection and official survival remains open.
- A separate mutation in wave two, 11b3a3535032048f, paid for seven
  Garrison actions and reached READY with 12 native Garrisons and $520.
  Actual survivors were 35.13% at 66.70 sim seconds, then crossed below
  35%. The official early retry was 9.29% at 142.13 seconds, on outbreak
  4071147503. The log credited Garrisons with 4,337 kills, and both
  initially occupied shelters were eventually breached. The learned
  proposal led discovery by survival area and advanced to another test.
  No promotion or reserved evaluation. The 35% goal remains open.

- Seed 160952 started at 03:33 Central, portable D: PID 44412,
  output `analysis/coverage-team-5dc8c1774d`, log
  `analysis/coverage-layout-free-160952-drive-d.log`. Headroom was
  13.07 GiB RAM and 18.85 GiB disk. Rotated discovery copies and
  continued the placement comparison without replay or synthetic training.
  Commit 91f74bb shares the completed local run's immutable base for
  layout-free continuation. Verified both paths refer to the same
  12,390,677-byte file with SHA-256 beginning `257f0c7b1af2e020`.
  All 256 script tests passed, including the fallback to a normal saved
  copy when links are unavailable. Production hash matched and the
  existing Observatory listener stayed active.
- Seed 159952 finished at 03:32 Central with eight scored early retries,
  no wins and no reserved boards launched. The ordered arm's four
  Garrison attempts followed two shelters. Three Garrisons were present
  at READY. First occupied breach was at 55.23 sim seconds versus
  47.60 for coverage-only and 44.13 for the unchanged parent. The
  respective saved-at-retry scores were 7.28%, 7.38%, and 8.07%.
  All three faced different outbreak seeds. The parent remained the
  provisional leader. Geometry and timing evidence justify replication,
  and survival improvement and the 35% goal remain unverified.

- D: storage audit at 03:25 Central found 71 search copies of the
  same frozen GRU by SHA-256. Coalesced 60 redundant files across
  61 completed search directories using D:-local hard links, keeping
  the bytes and original resume paths. Excluded the active search,
  ambiguous run directories, and production checkpoints. The shared
  bases are read-only inputs for the search. This removed 709 MiB of
  duplicate file content. D: showed 18.56 GiB free after space
  accounting caught up, with the current experiment writing concurrently.
  The previous replay archive remains intact and no loose binary dumps
  were present in inst13–20 during the audit.
- First-wave live journal check for seed 159952. Inst16 placed both
  shelters before three Garrisons. Native READY count agreed with the
  three logged placements. Max-range circles touched 100% and 65.6%
  of the two shelter perimeters, versus 54.2% and 0% in each of the
  two other candidate boards. This verifies a placement change. Wait
  for scored retries/wins and occupied-breach evidence before drawing
  conclusions about protection or survival.

- Seed 159952 started at 03:24 Central on D:, portable trainer PID
  61072, output `analysis/coverage-team-921a730bca` and log
  `analysis/coverage-layout-free-159952-drive-d.log`. Launch headroom
  was 13.11 GiB RAM and 18.16 GiB free, with the production checkpoint
  hash verified. Two discovery waves compare the original parent, its
  coverage-only variant, the same coverage weight with the shelter
  preference reordered, and the frozen GRU. Native building receipts
  now include the number of shelters present before placement. The
  GRU still owns all action and cell choices. All 255 script tests passed.
- This run uses `--qualified-holdout-only`. Reserved boards are started
  when a discovery policy satisfies the existing qualification rules.
  Four recent reserved waves took 17.2 minutes total, with 10 of 16
  outbreaks overlapping discovery and no wins. The ordinary default,
  fresh-outbreak checks, and promotion rules are unchanged.
- Seed 158952 finished at 03:22 Central with eight scored retries and
  no wins. The coverage-only variant scored 7.33% and breached at 49.47
  sim seconds. Its parent scored 6.82% and breached at 47.53 seconds on
  a different outbreak. Both placed two Garrisons and two shelters in
  the same locations. First-wave Garrison purchases preceded every
  shelter, leaving the perimeter coverage signal at zero when selecting
  those sites. The provisional leader repeated one outbreak at 8.74%
  and 8.87%. All four reserved rows overlapped discovery and were
  ineligible. The 35% consistency goal remains open.

- Seed 157952 finished at 03:09 Central. The spacing-only variant
  d67f3ddff7d01e93 reached retry at 8.52% and its first occupied
  breach was at 44.17 sim seconds. The parent retried at 8.59%
  and breached at 50.47 seconds on another outbreak. All three
  opening candidate boards sheltered 28.95% at READY. Native
  placements left one shelter perimeter entirely outside every
  Garrison's listed maximum range on all three boards. Both
  candidate reserved games reused discovery outbreaks, as did
  both references. The candidate scored 8.70% and 6.21% at retry.
  Those four rows are ineligible for promotion or fresh validation.
- The earlier-loadout variant 7e8d4bab9296a16d confirmed a second
  distinct early deployment (2.43 sim seconds) and reached retry
  at 9.31%. The first occupied breach was at 45.07 seconds. Earlier
  action access replicated, with no demonstrated survival gain.
- Read-only geometry on four live boards found snapped candidate
  sites with nominal marginal perimeter reach of 36%–48%, assuming
  maximum firing distance. The 96-point helper used about 91 us per
  48 candidates on a recorded pair of shelters. This is a distance
  estimate without terrain, line of sight, or effective damage.
  Commit e094025 gives one discovered variant that feature in the
  Garrison placement cell scores. The rest of the policy and its
  legal action choices are paired. Regression tests verify no
  changes to tool logits or other placement rows. All 254 script
  and 60 Observatory tests passed.
- Seed 158952 began at 03:09 Central on D:, portable trainer PID
  61100. Two discovery waves on inst13–16 and reserved evaluation
  on inst17, inst18, inst20, inst19. Prior
  `analysis/coverage-team-cc9c34b751`, output
  `analysis/coverage-team-3bfc36c36b`, log
  `analysis/coverage-layout-free-158952-drive-d.log`. Headroom at
  launch 13.15 GiB RAM and 18.18 GiB free. Production checkpoint
  hash matched. The 35% consistency goal remains open.

- Seed 156952 finished at 02:55 Central. The repaired sampled policy
  completed two observed pending world drags and cancelled two other
  pending gestures before its 7.57% retry. The opening wave completed
  with four scored retries and no gesture failures. Wave two added
  three scored retries and one continuous-pause timeout. No wins.
  Frozen f2cdd412763e71b9 scored 8.90% and 8.71% on two fresh
  reserved outbreaks. Both GRU reference seeds overlapped discovery.
- Earlier-loadout candidate 7e8d4bab9296a16d bought Police and
  brought 20 officers plus Firebomb into battle. Native logs
  recorded paratrooper deployments at 2.70, 11.70, 20.37 and
  28.87 seconds and Firebomb at 30.53 seconds. It finished at
  9.16% saved at 67.20 seconds, with its first occupied breach
  at 44.93 seconds. Parent f2cdd412763e71b9 first deployed at 20.87 s,
  breached at 44.80 s and ended at 9.73%. The two policies played
  on different outbreaks and brought different actual Garrison
  counts. An earlier action opportunity is verified. There is no
  measured survival advantage.
- A replay of saved discovery policies found the same defender-cell
  weight (0.257) across 20 Garrison-heavy trials examined. Commit
  f23fc6d schedules a variant only when the resumed proposal has
  confirmed Garrison investment. It changes one Garrison gene's
  defender-density weight so the search can test less clustered
  placements. The rest of the learned policy stays paired. The
  earlier-loadout probe remains available in the next wave.
  All 253 script tests passed.
- Seed 157952 started at 02:56 Central, portable D: trainer PID
  63684. Two discovery waves on inst13–16 and reserved evaluation
  on inst18, inst17, inst19, inst20. Prior
  `analysis/coverage-team-639beb8bda`; run log
  `analysis/coverage-layout-free-157952-drive-d.log`. Headroom
  13.11 GiB RAM and 18.19 GiB free on D:. Production checkpoint
  hash matched. The 35% held-out consistency goal remains open.

- Seed 155952 finished at 02:41 Central. Two opening discovery games
  crashed because the new geometry mask treated a pending native
  gesture name as a numeric tool ID. The GRU timed out, and the
  completed candidate bought 12 Garrisons, deployed four casts,
  had zero outside rejects, and ended at 9.26% at retry. The next
  discovery wave produced four retries (5.05%–9.03%) with 16 confirmed
  deployments and one outside reject total. New frozen 90ad559785f2b3b6
  scored 9.06% and 7.03% on fresh outbreaks, four confirmed deployments
  each. Both reference seeds overlapped discovery. No promotion.
- Commit 81aa8b9 fixes the gesture-name mismatch. A source-produced
  pending gesture reproduced the old crash in isolation, then passed
  the new regression for world drags, shifted drags and selection boxes.
  The tests use the same action producer as live play and a fake game.
- Prior fresh sampled-policy battles were at 80.28% and 79.24% saved
  around 19 simulated seconds, before the first confirmed cast.
  Both started with 2 SP. Native normal rules put the current
  Demolition preference at 20 seconds for unlock plus arrival and a
  same-cost alternative at 8 seconds. Commit bc87ad7 records affordable
  offers and the actual READY deck, then gives one discovery slot to a
  faster same-cost preference when a scored fresh failure supports it.
  Only one purchase preference changes. Normal action masks, policy
  choices, verified purchase receipts and official outcomes still apply.
  All 252 trainer tests and 60 Observatory tests passed. Actual GRU
  parity over 12 steps and graph assertions passed.
- Seed 156952 began 02:42 Central on D:, trainer PID 16776. Two discovery
  waves on inst13–16 and evaluation on inst17, inst18, inst20, inst19.
  Prior `analysis/coverage-team-2ffbd28f2a`; output
  `analysis/coverage-team-639beb8bda`; log
  `analysis/coverage-layout-free-156952-drive-d.log`. Startup headroom
  13.09 GiB RAM and 18.20 GiB disk, with production checkpoint hash
  matched. The 35% consistency goal remains open.

- Seed 154952 finished at 02:28 Central. The sampled candidate
  3f44400a70a7d7d9 made non-argmax legal choices in 88 of 118
  observed battle decisions and stayed greedy in all 27 planning
  observations. It still held 42.54% live at 82.5 simulated seconds
  and ended at 4.56% saved at retry. The otherwise identical greedy
  arm ended at 9.75% at 65.87 seconds on a different outbreak. Both
  spent three Demolition charges near unlock and one Firebomb.
  The sampled discovery episode rejected 84 outside choices (82
  pointer gestures and two casts). The greedy arm had 14 Firebomb
  rejections and no planning geometry rejections. A fourth attempt
  failed on an incoherent HUD frame, and the GRU control timed out.
- Fresh reserved-copy results for 3f44400a70a7d7d9 were 9.16% and
  8.89%, both at early retry, with four deployments in each. Both
  reference outbreaks overlapped discovery. Native low-save fallback
  was observed in the greedy and sampled discovery results and in
  both fresh held-out results. It recorded the trigger separately
  from each official footer score. No win, valid comparison, or promotion.
- Commit b2ade7c extends the same exact boundary filtering to known
  invalid battle clicks, drags, snapped targets and ability endpoints
  in layout-free discovery and evaluation. Raw dispatch still checks
  targets. An incoherent HUD read now lets the writer finish between
  bounded seqlock attempts. The supported build, shared mapping and
  HUD frame validity checks remain in effect. All 249 script tests
  passed. The launch still uses the original production weights.
- Seed 155952 started at 02:29 Central, portable D: trainer PID 61928.
  Two discovery generations on inst13–16 and separate evaluation on
  inst18, inst17, inst19, inst20. Prior `analysis/coverage-team-9922b10880`;
  run log `analysis/coverage-layout-free-155952-drive-d.log`. Headroom
  13.12 GiB RAM and 18.22 GiB disk. Reconfirm the new masks and HUD
  retry on live boards. The 35% held-out consistency goal remains open.

- Seed 153952 finished at 02:14 Central. Sixteen discovery results:
  14 early retries, one native loss, one planning timeout, zero wins, and
  54 confirmed stock decreases. Four legacy geometry tools accounted
  for 50 outside-boundary rejections. The frozen 8dde6252f008a630
  tried two fresh held-out outbreaks, saving 3.35% at retry and 0.00%
  at a native loss, with four confirmed deployments in each. Both GRU
  reference outbreaks reused discovery seeds. No valid comparison or promotion.
- Native planning logs from the 12-Garrison discovery board showed five
  Garrisons within 30 meters of one placement. Sampling each zone edge
  against the documented 262.5 m maximum Garrison range put 56–63% of
  perimeter samples within that upper-bound distance. This is distance
  coverage, with no allowance for line of sight, actual height-dependent
  range or combat behavior. Adding units alone did not establish coverage.
- Commit 45c2edd filters known outside-boundary geometry starts and
  endpoints in the layout-free search. The dispatch guard remains active.
  The same commit adds a low-survivor retry fallback using a recent
  official snapshot from this episode's active log. A raw alive count
  without native infection or logged save evidence cannot trigger it.
  Final scores still use the session footer, and aborted runs cannot
  qualify. New ledger revision prevents mixing the rollout interfaces.
- A read-only sample of 234 battle decisions had 145 next-special
  selections and a median top-action probability of 0.2112. Commit
  a675cbb gives resumed search one discovery slot with the same learned
  planning sequence and seeded sampling from the legal battle probability
  distributions. The sampling flag forms part of frozen policy identity
  and follows that policy into evaluation. All 247 script tests and 60
  Observatory tests passed.
- Seed 154952 began at 02:16 Central, trainer PID 27608 on the D:
  portable runtime. Discovery inst13–16, reserved evaluation inst17,
  inst18, inst20, inst19. Prior `analysis/coverage-team-036e35ad98`;
  output `analysis/coverage-team-9922b10880`; run log
  `analysis/coverage-layout-free-154952-drive-d.log`. Headroom at launch
  13.15 GiB RAM and 18.23 GiB free on D:. Production weights hash matched.
  The 35% holdout goal remains open.

- Seed 153952 generation zero finished at 01:53 Central. The timing-only
  variant 102e05013e10951e confirmed five native Garrisons and reached
  early retry at 3.76% saved. Its first three Demolition deployments were
  21.20, 21.97 and 22.77 simulated seconds. Parent 625da8b96c4639f7 used
  three at 20.30, 20.70 and 21.17 and recorded a native loss at 0.00%.
  These were different outbreaks. The variant has not demonstrated a
  break from the early three-cast burst or a survival gain.
- Variant ad30fce343e4a365 paid for four Garrisons and one Mortar before
  a planning timeout. 23 of its 60 decisions hit the existing outside
  guard, nine rectangle selections and fourteen wall/gate selections.
  Draft optional candidate masks were checked offline against every
  start/end pair and the existing dispatch guard for four native geometry
  tools on three shapes. The draft took about 68 microseconds per
  decision on a triangular boundary. No live trainer code changed.
- A read-only audit of seed 152952's last reserved copy verified the
  first native log sample under 10% at 100.03 simulated seconds and
  9.90% saved. The same episode reached retry at 154.77 simulated
  seconds and 1.69%, 109.50 wall seconds later. A draft log-bound
  fallback recognized the fresh low-save snapshot offline and rejected
  stale, future, wrong-phase, invalid-score and footer records. The
  normal policy keeps control of evacuation. An alive-count decrease
  alone still cannot establish the low-save threshold.
- Copy preflight at 01:55 Central confirmed inst1–12 each fails full
  availability. Inst12 is missing seven perks, and other copies have
  broader omissions. Existing four training and four reserved slots
  remain in use. No new copies or C: files.

- Seed 152952 finished by 01:46 Central. All four discovery episodes
  recorded explicit model READY, including all three learned candidates.
  An independent read-only trace showed rectangle drafts clearing while
  staying in planning. The candidates confirmed 11 native deployments
  (nine Demolition and two Firebomb) and finished at 5.44%, 5.80% and
  6.51% saved at early retry. GRU reference timed out from a continuous
  pause. Each learned policy spent three Demolition charges within three
  simulated seconds, starting at 20.33–21.27 s.
- On reserved fresh outbreaks, the frozen 625da8b96c4639f7 reached early
  retry at 6.26% and 1.69% saved after four confirmed deployments each.
  The slower result reached 35.1% live at 70 s before falling to 1.69%
  at 154.77 s. Both GRU references reused discovery outbreak seeds.
  No qualified comparison or promotion. The held-out results confirm the
  cast path, with no evidence yet of survival benefit from the rapid casts.
  The prolonged low-save tail merits a separate retry/evacuation audit.
- Commit c2f0382 allows search to test a different timing preference when
  a scored fresh L1 trial uses three confirmed deployments of the same
  ability within three simulated seconds. It preserves the earlier
  no-cast experiment. On resume it places a timing-only variant of the
  frozen proposal in one discovery slot. Legal masks, planning genes,
  cast targets, weights, and official evaluation retain their semantics.
  All 244 script tests passed.
- Seed 153952 started at 01:47 Central, D: portable Python PID 65140.
  Discovery inst13–16, separate evaluation inst18, inst17, inst19, inst20.
  Run log `analysis/coverage-layout-free-153952-drive-d.log`; prior
  `analysis/coverage-team-e7816b8ec2`. Headroom at launch 13.18 GiB RAM
  and 18.25 GiB free on D:. Production checkpoint hash matched and
  Observatory listener stayed at PID 12628. The 35% goal remains open.

- Seed 151952 finished at 01:33 Central with 16 early-retry discovery
  results, 15 without an explicit READY, and zero wins. Candidate
  625da8b96c4639f7 paid for two Garrisons (cells 13 and 26) in its
  discovery trial and on both reserved copies, each on a different outbreak.
  All three of those battles started without the model's READY and
  had no legal cast opportunities. Results were 9.89%, 9.95% and 9.96%
  saved at retry. Both reserved GRU boards reused discovery seeds. No
  valid comparison or promotion.
- A read-only trace on inst13–16 in generation three captured the first
  rectangle clearing its native draft while staying in planning and the
  second clearing its draft immediately before battle on all four games.
  Commit 4752be3 waits for consumed corner clicks and checks the draft,
  active tool and modal before sending Enter. If a game enters battle
  without explicit policy READY, the episode fails before it can
  contribute a score or experience. Campaign ledgers now use a new
  interface revision. All 243 script tests and 59 Observatory tests
  passed. Actual GRU outputs and observer sampling matched across
  12 recurrent steps, and graph checks passed.
- Seed 152952 started at 01:34 Central on D: (PID 57040), a single
  discovery generation plus frozen evaluation on reserved inst17–20.
  Discovery uses inst13–16. Prior frozen GRU 8a691469a829158d and
  provisional policy 625da8b96c4639f7 are inputs. Startup headroom was
  13.19 GiB RAM and 18.26 GiB free on D:. Output
  `analysis/coverage-team-e7816b8ec2`, run log
  `analysis/coverage-layout-free-152952-drive-d.log`. Production checkpoint
  hash matched. Official 35% consistency remains open.

- At 01:18 Central the first four seed 151952 discovery games ended in
  early retries (9.91%, 10.00%, 9.95%, 9.97%). Extending the Garrison
  preference from two to five decisions produced two actual attempts:
  cell 35 at (893,725) had no spend, then cell 13 at (1246,338) cost $144.
  A different proposal paid $72 at the same cell 35 before a second
  attempt there went unconfirmed. Both games entered with one Garrison.
  The receipts show cell 35 can work and the longer preference has not
  increased confirmed placements or saved civilians.
- At 01:23 Central, replayed the saved decisions and phase receipts
  across 66 fresh L1 layout-free candidates with native READY records.
  In 61 games the model never selected READY; all 61 crossed into battle
  immediately after a zone_rect decision. All lacked the trainer's
  battle-start timestamp. Fourteen had native stock at READY and zero
  legal cast decisions. Of the five candidates with a recorded battle
  start, four stocked abilities and three saw legal casts. A live,
  read-only check found three Demolition charges and 10 eligible map
  buildings on each of the four wave-one boards, at 47.7–48.4 simulated
  seconds (normal unlock is 20). Five or six modeled cells had eligible
  targets before HUD exclusion. The current trainer builds the ability
  deck only after the policy's explicit READY action, so those early
  battles lack their purchased casts and normal battle timeout.
- The unsafe legacy rectangle sends four unsynchronized clicks and an
  unconditional Enter. Enter can also invoke READY without a native
  polygon draft, as previously observed in boot diagnostics. The exact
  key/gesture path still needs live before-and-after verification. Test
  frame-confirmed corners and guard Enter with native draft and dialog
  state. Reject episodes that reach battle without the model's explicit
  READY. Run the unchanged learned policy on fresh owned copies before
  using results from the corrected interface. Seed 151952 is still live
  on D: and the production checkpoint remains separate.

- D: storage cleanup at 01:14 Central. Archived 862 pre-existing binary
  replays (6,496,505,774 bytes) from the owned inst13–20 debug-dump folders.
  Verified every archived file against its SHA-256 and length before removing
  the loose originals. The archive is
  `analysis/coverage-replays-through-2026-11-19.zip` on D: (687,117,062 bytes).
  It contains original repository-relative paths and a `manifest.jsonl`
  with sizes and hashes. To restore a replay, extract its entry to the
  original path when that copy is idle. All 862 text companions remain in
  place. The working set dropped by 5.41 GiB. Free space was 18.28 GiB at
  the next launch check. No new files, archives, or game copies on C:.
  The production checkpoint hash matched and Observatory port 8765 remained
  active. The existing trainer guard still discards newly generated binary
  companions after consuming their text dumps.
- Seed 150952 finished at 01:09 Central with 16 discovery games and no wins.
  Seven paid for one native Garrison and entered battle with $1,554–$1,802.
  Two fresh reserved-copy candidate outbreaks ended in retries at 9.96%
  and 9.99%. Both reference outbreaks reused seeds (one retry, one pause
  timeout). No valid paired comparison or promotion.
- Commit e3fa390 extends one confirmed building preference by 2–5 planning
  decisions within the existing planning limits. The model still chooses
  which actions and placements to take through the usual game checks.
  The experiment records actual target, decision, view and spend for each
  paid or unconfirmed building attempt. All 242 script tests passed.
- Seed 151952 started at 01:14 Central on D: (PID 36024) using owned
  inst13–16 for discovery and inst17, inst18, inst20, inst19 for reserved
  evaluation. Startup headroom was 13.14 GiB RAM and 18.28 GiB free on D:.
  Run log `analysis/coverage-layout-free-151952-drive-d.log`. The 35%
  target remains open.
- Seed 149952 finished at 00:49 Central with 16 discovery rows and no
  wins. One launch failed in inst15 with a native pointer overflow.
  Candidates be8723e2bcd964a0, e06f1094d6776650 and 754a2792eedd5263 each
  had one paid Garrison attempt, one unconfirmed attempt, and a native
  garrison count of one at READY. Their early retries scored 9.99%,
  9.90% and 9.60%. All four reserved-copy rows reused earlier outbreak seeds.
  No promotion. The aggregate receipts alone do not show the order
  of each successful and unsuccessful placement.
- A read-only sample covered 11 live planning frames over four discovery
  games. The highest unselected Garrison probability reported in that
  sample was about 0.08%; the chosen action in that frame was over 21%.
  Commit 138c2ba preserves a defense candidate when both an actual purchase
  and a native unit at READY are recorded. It also tests a separate
  genome variant with lower inherited GRU tool-logit scale during plan
  steps. The original plan, tool masks, battle action logits and
  promotion checks retain their prior semantics. All 241 script tests passed.
- Seed 150952 started at 00:50 Central, trainer PID 60664. Discovery
  inst13–16, separate evaluation inst18, inst17, inst19, inst20. Launch
  headroom 13.19 GiB RAM and 12.88 GiB free on D:. Output
  `analysis/coverage-team-104121a04e`; run log
  `analysis/coverage-layout-free-150952-drive-d.log`.
  Read-only preflight found none of inst1–8 eligible under the existing
  game checks (inst9–12 were already rejected). Production checkpoint hash
  matched. The 35% target remains open.

- Seed 150952 completed generation zero at 00:54 Central. The retained
  defender be8723e2bcd964a0 and its planning-scale-only variant
  8acff04584ae0d51 (scale 0.5916) each paid for one Garrison, had one
  unconfirmed attempt, and had one garrison at READY. They ran on
  different native outbreaks. The two retries scored 9.85% and 10.00%,
  respectively. No wins, and no claim of a survival improvement from
  the scale change. Generation one is live.

### Placement receipts and target feedback
- Seed 148952 finished at 00:24 Central. All 16 discovery games had
  zero wins. All four reserved-copy outcomes reused earlier outbreak
  seeds and were ineligible. The two candidate retries scored 10.00% and
  9.95%, the GRU had a 9.76% retry and a continuous-pause timeout.
- A separate planning-only probe on owned inst19 reproduced the repeated
  refused click. In the same view, model cell 35 snapped to (893, 725),
  a 404 m² building; regular and longer clicks left 3,111 money and zero
  garrisons. Cell 19 snapped to (815, 471), a 612 m² building; money fell
  to 3,025.80 and the native count rose to one. The center-click control
  bought a second garrison for 73.20. The probe ended in planning and
  closed its game. The refusal's precise geometry or hit-test condition
  remains unresolved. These are interface diagnostics, outside training
  and scoring.
- Commit 404773d compares money around building attempts and records
  paid/unconfirmed counts. Layout-free L1 campaign experiments mask the
  exact unconfirmed tool/target for five decisions when the view and
  target still match. Other cells and other units stay available. A view
  or target change clears that mask. READY results now retain actual unit
  counts separately from native stock. New view revision prevents old trials
  from ranking proposals under the changed action mask. All 239 script tests
  passed. Routine PPO keeps its prior selection behavior.
- Seed 149952 started at 00:28 Central, trainer PID 63396. Verified four D:
  worker processes and discovery copies inst13–16. Evaluation copies
  inst17, inst18, inst20, inst19 remain separate. Launch headroom 13.20 GiB
  RAM and 12.89 GiB free on D:. Output `analysis/coverage-team-ce0c2d1b9b`;
  run log `analysis/coverage-layout-free-149952-drive-d.log`.
  Production checkpoint hash matched. The 35% goal remains open.

- Seed 149952 completed generation zero at 00:33 Central. Four real games,
  no wins, no attempted or paid building placements. Native READY unit
  counts were captured on all four rows. Scored retries were 9.87% for
  the GRU and 10.00%, 9.99%, and 9.92% for the candidate policies.
  Generation one is live; inst15 reported a boot-time pointer overflow
  and that row is marked failed. Other workers continue. Live target
  cooldown effectiveness is pending a real placement selection.

### Equip and placement trial
- Seed 147952 ended at 00:05 Central. All 16 discovery games had zero
  wins, defensive-unit selections, and confirmed battle stock spends.
  All four reserved-copy evaluation seeds were distinct and cleared
  the known discovery/previous-evaluation seed check. Challenger
  d0a5f58c8e3a12db early-retried at 10.00% and 9.87%; the GRU early-retried
  at 9.76% and 9.94%. No promotion.
- Commit f524195 adds one equip preference before the sampled defense
  placement preference for the same unit. An explicit genome flag
  preserves the next preference through pending gestures and dialogs;
  its presence is included in team identity. Existing genomes retain
  their original behavior. The ordinary legal-action mask governs every
  choice. Unit tests verified the paired preferences, round-trip identity
  and preservation through masked decisions. All 238 script tests passed.
- Seed 148952 started at 00:06 Central, trainer PID 9916. Verified all
  four D: Python workers and game copies inst13–16. Evaluation copies
  inst19, inst20, inst18, inst17 remain separate. Launch headroom was
  13.18 GiB RAM and 12.91 GiB free on D:. Output
  `analysis/coverage-team-78ff394d8c`; run log
  `analysis/coverage-layout-free-148952-drive-d.log` and matching error log.
  Production checkpoint hash matched. The 35% goal remains open.

- Seed 148952 generation zero completed at 00:10 Central. Defender
  f87873f2814e5ed3 selected Garrison twice on the same cell (zero-index 35).
  The native log recorded arming Garrison twice and no garrison placement
  event. READY had 1,674 left and zero garrison stock. It scored 9.99%
  at early retry. Another child also selected Garrison twice on that cell
  and had zero garrison stock at READY. This exercises placement selection
  but identifies a separate unresolved target or input-receipt issue.
  No wins in the opening generation; generation one is live.

### Placement exploration and READY receipts
- Seed 146952 finished at 23:44 Central. There were zero wins in 16
  discovery games. Proposal 3acb408aecf16f7a spent one Bomber charge and
  reached early retry on three distinct verified native outbreak seeds
  (9.90%, 9.94%, 9.96%). Frozen proposal 56671c66268d3b46 had one scored
  retry (10.00%), two reference pause timeouts and one nonfinite mechanics
  error. Three rows with outbreak identities reused prior reserved-copy
  seeds and were marked ineligible. No promotion.
- Audit of two recent layout-free blocks found no selected defensive unit
  placements in their inspected discovery episodes. One native READY event
  showed 1,815 unspent and no defensive units. Commit 6a985ac assigns an
  exploratory slot to a randomly sampled defense-placement preference
  while retaining the existing plan and ordinary legal masks. It records
  native READY money and stock with each campaign result and names up
  to four invalid mechanics features on an observation failure.
  The full script suite passed 237 tests after making a same-timestamp
  dummy dump fixture deterministic. Production checkpoint hash matched.
- Seed 147952 launched at 23:46 Central, trainer PID 31900. Verified four
  D: worker processes and discovery copies inst13–16. Reserved copies
  inst18, inst17, inst20, inst19 swap the preceding block's arm assignments.
  Older copies inst9–12 failed the full-availability preflight. Launch
  headroom was 13.11 GiB available RAM and 12.92 GiB D: free.
  Output `analysis/coverage-team-806b5aa365`, run log
  `analysis/coverage-layout-free-147952-drive-d.log` and matching error log.
  The 35% consistency goal remains open.

- Seed 147952 generation zero completed at 23:50 Central. All four
  discovery rows recorded native READY money and stock. The learned
  variants had 1,874 left and no defensive-unit selections or stock.
  One sampled defense preference was ChemMine, which was absent from
  inst16's planning roster. Its two allotted actions were both zone
  geometry, including a pending rectangle endpoint. This establishes
  two cases to address before interpreting the mutation as a defense
  experiment: roster availability and progress through masked gestures.
  No wins. Generation one remains live.

### Search with pause handling
- Seed 145952 finished at 23:22 Central with no discovery wins in 16
  games and no promotion. The frozen games ran on reserved inst17–20.
  All four outbreak seeds were distinct and absent from the three blocks
  of known prior discovery/evaluation records. Candidate 71bdb3116c014319
  early-retried at 9.95% and 9.96%. Both GRU references timed out from a
  continuous pause. Neither timeout supplied an official saved fraction.
- A one-cell placement variant 046fba76da751f39 sheltered 1,508 civilians
  on its initial attempt and spent a Bomber charge in two of three trials.
  It timed out while paused all three times. Its first timeout led the
  preliminary discovery ranking because accrued survival area survived the
  missing score. Commit 33ecec8 removes that credit for unscored attempts
  and mutates only the learned pause bias in one resumed trial when a prior
  attempt spent stock and then timed out. The original plan is preserved.
  234 total script tests passed and the targeted suite passed after the
  final numeric-type check.
- The private PPO consistency checker now stores training outbreak seeds
  in its resumable paired checkpoints and excludes matching evaluation
  rows across both arms (c7a6d63). Replaying the earlier comparison logs
  gave zero qualifying evaluations and zero recorded training-seed overlap.
- Seed 146952 launched at 23:23 Central, trainer PID 35676. Verified four
  D: worker processes and games inst13–16. inst17–20 again serve as reserved
  evaluation copies. Launch headroom was 13.14 GiB RAM and 12.91 GiB D:
  free. Output `analysis/coverage-team-4332a2b5f0` and
  `analysis/coverage-layout-free-146952-drive-d.log` with matching error log.
  The production checkpoint hash is unchanged. The 35% target is pending.

- In live seed 146952 generation zero, pause-bias proposal 3acb408aecf16f7a
  retained the rest of 046fba76da751f39 exactly. On the same outbreak seed
  and owned copy it reached the early-retry threshold at 60.33 simulated
  seconds and 9.90% saved, after one confirmed Bomber spend. Its predecessor
  timed out at 47.73 simulated seconds. The same-seed comparison is a
  discovery diagnostic. It gives no held-out survival estimate. The revised
  proposal led generation zero and generation one is in progress.

### Isolated holdout and local placement search
- Layout-free continuation 144952 finished at 22:59 Central. Across
  16 discovery games it had no wins. Proposal 71bdb3116c014319 sheltered
  1,616 civilians across multiple distinct outbreaks and had roughly
  56–62 simulated seconds in battle on the reported repeats. Shelter
  breaches followed. It confirmed no battle stock spends. Frozen retries
  on the candidate saved 10.00% and 9.99%; both GRU reference games timed
  out on the battle clock while paused. No champion was promoted.
- Audited native seed reuse. Two of four frozen rows in discovery block
  142952 reused discovery outbreak seeds. In block 144952, one of two
  candidate frozen rows reused its discovery seed. The 58.93-second repeat
  of proposal 3237e2a74318792e on inst15 also reused its outbreak seed.
  Keep these rows as diagnostics only when evaluating fresh generalization.
- Commit 29f10b6 adds separate reserved holdout copies, records known
  outbreak seeds across continued blocks, rejects overlapping outbreaks and
  missing scores at the promotion gate, and uses the same 45-second
  continuous-pause limit for both frozen arms. Discovery also tests a nearby
  placement variant using a one-cell mutation of a learned spatial choice.
  All 232 script tests passed. The production GRU file hash stayed unchanged.
- Started layout-free seed 145952 at 23:02 Central with 13.16 GiB RAM and
  12.95 GiB disk free. Verified trainer PID 28468, four D: Python workers,
  and discovery copies inst13–16. inst17–20 are reserved for the separate
  frozen check. Resumes proposal 71bdb3116c014319 without promotion. Output
  `analysis/coverage-team-70bcc8625a`. Logs
  `analysis/coverage-layout-free-145952-drive-d.log` and matching errors log.
  The 35% consistency goal remains open.

### Earlier layout-free search
- Completed phase-balance seed 143952 at 22:21 Central from 16 paired
  learning updates, with 6 fresh frozen attempts per arm. Standard averaged
  9.59% across 6 scored early retries, with 2 confirmed stock spends.
  Balanced averaged 9.62% across 4 scored early retries, had 2 planning
  timeouts and 1 confirmed spend. Neither arm won or qualified. Retry scores
  are incomplete for the 35% consistency gate. No promotion.
  Evidence: `analysis/coverage-phase-balance-6b7086fe19/results.jsonl` and
  `consistency.json` in the same directory.
- Search 142952 completed at 22:34 Central. The 16 discovery games produced
  14 early retries, 1 loss, 1 timeout, and no wins. In generation zero,
  two proposals tied at 9.96% saved on retry; the selected leader sustained
  29.6 simulated seconds versus 25.2 for the other. This exercised the new
  area ordering in a real round. Frozen proposal ef0ae8f88e081549 scored
  9.54% and 9.81% against the GRU's 9.90% and 9.87%, all early retries.
  No promotion. Both progression and layout replay were disabled.
- Added explicit layout-free continuation e986df9. It validates the provisional
  proposal and GRU identities, refuses saved layouts and loads prior evidence
  without treating the proposal as the incumbent. 229 game-free script tests
  passed. Continued as seed 144952 with 13.23 GiB available RAM and
  12.96 GiB free disk. Trainer PID 66700, four D: Python workers, games
  inst13–16. New output `analysis/coverage-team-c5f242fb3a` with
  `analysis/coverage-layout-free-144952-drive-d.log` and matching error log.
- Verified continuation generation zero completed at 22:39 Central with
  the retained proposal ef0ae8f88e081549 among the actual fresh trials.
  Two new proposals sustained 58.9 and 59.5 simulated seconds, versus
  29.6 for the retained proposal. All three early-retried below 10% saved.
  The GRU control timed out. The longer-lived proposal 3237e2a74318792e
  led by survival area. Generation one is live. These are discovery
  results, not evidence for promotion or the 35% consistency target.
- Started Boston L1-only campaign search 142952 at 22:22 Central, four
  generations, no seed champion, no demonstration, no saved-layout replay.
  Started with 13.23 GiB RAM and 12.98 GiB disk free and verified trainer
  PID 65004, four child Python processes and games inst13–16 on D:.
  Output `analysis/coverage-team-83f9f48958` and
  `analysis/coverage-layout-free-142952-drive-d.log` with matching errors log.
  Base GRU 8a691469a829158d is read-only. The population uses e9435aa
  for proposal ranking and cf9d3b7 to recheck workstation headroom before
  each game batch. 59 targeted tests passed for the latter change.
  No background handoff is queued.

### Recovery and completed PPO run
- Verified the official Python 3.14.4 x64 embeddable archive SHA-256, loaded
  it from memory, and extracted 21.8 MiB to ignored
  `analysis/coverage-portable314` on D:. Reuses the existing D: dependencies
  and directs TEMP, TMP and TMPDIR to its D: scratch folder. No ZIP was stored.
  A first launch under `.venv` inherited the C: base executable in spawned
  workers. Stopped those trial processes without a new paired update.
  The relocated runtime passed a real worker-spawn probe for executable,
  base executable, temporary directory and Torch package drive.
- Both owned copies passed preflight. The script suite passed 226 tests
  with the portable interpreter. Confirmed the saved trial is at update 12
  with 10 Adam states per arm. Started seed 143952 on D: with 12.84 GiB
  idle RAM and 13.07 GiB free disk. Verified trainer PID 10212, Python
  worker PIDs 31504 and 16924, and both owned games running from D:.
  Outputs are under `analysis/coverage-phase-balance-6b7086fe19`.
  Logs: `analysis/coverage-phase-balance-drive-d.log` and its `.err.log`.
  No automatic follow-up is armed. Production weights remain read-only
  through this comparison. No frozen evaluation has started.

- The first two resumed paired PPO updates completed on D:. The standard arm
  early-retried two battles with one confirmed stock spend across both. The
  balanced arm reached two planning timeouts. Frozen evaluation remains
  pending. The next comparison snapshot was verified present and the
  training PID remained live. No production weights were written.
- Committed e9435aa for the layout-free L1 search. On 12 prior replay-assisted
  early retries under the current camera revision, official retry scores had a
  9.30% median while simulated survival area ranged 0.229 to 0.602. This area
  now ranks failed preparation/battle proposals only in layout-free search.
  Real wins retain priority and promotion/held-out scores remain official.
  The regression covers early retry ties, win precedence and legacy duplicate
  records. All 227 script tests passed on the relocated D: runtime. The change
  does not alter the running PPO trial and has yet to be tested in live search.

### Earlier storage pause
- The user directed all project work away from C:. The D: virtual environment
  resolves its base Python executable to C:, so the private two-copy trial and
  its queued automatic handoff were stopped. The Observatory was left running.
  No owned game or trial processes remained on verification. Seed 143952
  preserved 12 paired updates in
  `analysis/coverage-phase-balance-d0d3c3594b/paired.pt` (SHA-256
  `94AF3949AEBF8E0FDB27C05D63890C4F4DB066EDAA29E6664B9CD4E67FA2CEF9`).
  The in-progress pair was interrupted; frozen evaluation has not started.
  Production weights were untouched. Resume from that snapshot only through a
  D:-based Python runtime after verifying preflight uses the owned copies.
- D: had 13.1 GiB free after the cleanup. The repository had 6.05 GiB of
  retained native state dumps. Three idle-copy samples compressed to about 11%
  of their original size and decompressed to the original SHA-256 in memory.
  Lossless archival is the main option if space becomes tight. It needs a
  verified restoration path for evidence consumers. Existing dumps, assets and
  checkpoints were kept. Removed 37 generated repository bytecode files
  (619,084 bytes). No new project data was written to C: during this cleanup.

- 2026-11-19 Central. D: fell to 0.59 GiB while no games were active,
  then recovered to 8.72 GiB. Verified a SHA-256-matching C: backup of
  the private checkpoint and results. Guarded continuation deployed at
  ced199e and resumed original seed 143952 from update 10 on inst13/14.
  New output `analysis/coverage-phase-balance-d0d3c3594b`. No C: games
  were created. Only one trial is active. Production checkpoint unchanged.
- 2026-11-19 21:49 Central. Two-copy phase-balance seed 143952 stopped
  on a transient native map observation in pair 11. Verified the private
  atomic checkpoint contains ten completed updates and both Adam states.
  Completed scored train means 9.76% standard and 9.55% balanced,
  zero qualifiers, no frozen evaluation yet. D: had 2.23 GiB free; no
  training/game processes remained. Guarded continuation PID 65268 waits
  for two idle samples with at least 3 GiB D: and 6.5 GiB RAM, then
  resumes the same paired snapshot. Staged 9080182 retries paired native
  map failures and checks headroom each round. An independent empty-cell
  mask fix is staged in eacb55d and excluded from this resumed run.
- 2026-11-19 21:24 Central. Four-copy no-replay launch was refused with
  8.44 GiB idle RAM and 4.32 GiB free disk. Started safe two-copy PPO
  143952 on inst13/14, handoff PID 64920. Sixteen updates and six frozen
  rounds per arm. Private output `analysis/coverage-phase-balance-2e887b1d6a`.
  The handoff will attempt no-replay search if idle RAM recovers to 10.5 GiB,
  then restore the production supervisor. Frozen verification now has a
  tested three-block checker in staged commit 2a896a1. Goal remains active.
- 2026-11-19 20:54 Central. Fixed-1× PPO phase-balance trial 141952
  finished: both frozen arms 0/12 qualifiers, 9.29% standard versus
  9.35% balanced mean saved. Balanced increased training stock spends
  from 4 to 10, but frozen spends fell from 5 to 1. No promotion.
  Six-copy no-replay follow-up was refused on idle RAM, regular seed
  141851 resumed on four copies. No-replay 142952 is queued again on
  four at a guarded boundary (PID 30144). Goal remains open.
- 2026-11-19 20:44 Central. Phase-balance trial completed four private
  training rounds and entered frozen evaluation. Queued no-replay campaign
  search 142952 behind it (handoff PID 20176). No seed champion or saved
  demonstration is loaded. Both experiments use six owned copies without
  overlap, and the existing production supervisor resumes after the search.
- 2026-11-19 20:34 Central. Private PPO missile-credit trial 140952 finished
  12 training and 24 frozen results. Neither arm qualified; frozen means
  9.31% baseline and 8.75% missile-credit. Zero confirmed missile civilian
  impacts across both arms, so this trial did not expose the reward contrast.
  Twelve training episodes selected 714 pause/speed controls among 5,610
  battle choices. Started phase-balance trial 141952 on six fresh copies,
  both arms fixed 1× with playback controls held steady. Four private train
  rounds and four frozen rounds in `analysis/coverage-phase-balance-673a887408`.
  Production checkpoint remains private to regular search and was not written.
- 2026-11-19 19:42 Central. Queued private six-copy PPO missile-credit
  comparison 140952 behind production seed 140851 (handoff PID 64432).
  Both arms start from identical schema-4 checkpoint and Adam state, use
  fresh boards without saved-layout replay and differ only in the impact
  reward. Two train rounds and four frozen evaluation rounds. Objective:
  three ten-game held-out L1 blocks averaging at least 35% official saved
  each, with qualification rate and incomplete outcomes reported.
- 2026-11-19 19:10 Central. Controlled shadow comparison 138952 completed
  all 18 fresh L1 scores and joined 54/54 native missile impacts across
  6,785 transitions. Control 3/6 qualifying, timing 2/6, targeting 0/6.
  The targeting arm moved from cell 12 to 20; the timing arm had the
  same median and produced no legal waits. Frozen held-out context
  predictor missed the civilian median baseline (45.11 vs 23.94 kills MAE);
  refit still missed it. Capture and shadow evaluation only. Production
  139851 resumed on six copies with no comparison operator left. See
  notes/shadow-simulator.md and analysis/coverage-shadow-arms-report.json.
- 2026-11-19 18:32 Central. Queued six-copy fixed-plan shadow comparison
  seed 138952 behind active production seed 138851. Handoff PID 55736 holds
  the supervisor marker until production exits normally, checks headroom,
  deploys the staged native combat receipts and comparison mode, and restores
  regular search after capture. Frozen predictor evaluation uses prior
  inst13–16 labels and newly captured inst17–18 outcomes.
- 2026-11-19 Central. Status audit: production seed 136851 active on six
  copies, frozen base 8a691469a829158d. Incumbent 230c8ceb72a1b1a3
  had 28 qualifying starts of 42 at 37.15% mean in the fresh search ledger.
  Recent holdout snapshot: incumbent 10/14 at 37.95% mean, challengers
  8/14 at 33.94%. Across a recent search snapshot, 44/115 qualified;
  14 timeouts included 11 continuous pauses and three planning caps.
  Seven separate worker errors were input attachment or HUD-frame failures.
  Recent evidence is Boston L1 only. No training control changes.
- 2026-11-19 14:50 Central. Completed seed 129952: 24 jobs, 22 fresh
  outbreaks, 18 official scores, nine qualifiers, four timeouts and two
  failed input attachments. Validated 11,780 transitions with no truncation.
  48 confirmed missile launches across two cells, 120 legal waits, six
  isolated aligned outcomes. Retained 48 native impact pairs; 30 met the
  stock-receipt join for an offline direct-kill predictor. Held-out
  context zombie MAE 26.83 vs training median 24.33. Keep simulation shadow
  only. See notes/shadow-simulator.md and local
  `analysis/coverage-shadow-context-report.json`.
- 2026-11-19 14:32 Central. Production seed 129851 completed normally.
  Staged capture code deployed at the idle boundary; six-copy shadow
  capture seed 129952 started on inst13–18 with frozen base 8a691469a829158d.
  Output is `analysis/coverage-team-bd8e7ef03e`. The held supervisor marker
  is restored by the handoff, which resumes from the last production search.
  A passive collector preserves native launch and impact events by session.
- 2026-11-19 Central. Added compact combat context to opt-in shadow states
  from the existing native snapshot, with no additional game reads. Includes
  local conversion, defenders by kind, wall/hazard/mutation centers, bounded
  shelter polygons, sampled terrain/bridges/fire, and live helicopter positions.
  Native missile flight and impact remain unverified. Six-copy production
  was active and inst13 preflight passed; no competing capture launched.
- 2026-11-19 Central. Added opt-in shadow transition schema 2 and evaluated
  a receipt-conditioned model offline. Existing archive admitted 23 battles;
  new fits train on inst13–15, calibrate on inst16 and test on inst17–18.
  About 3,600–3,900 single-window or 24,700–31,500 batch-64 forecasts/s on one
  idle-priority CPU thread including feature preparation and scoring.
  Conditioned civilian MAE rose from 63 to 146 on the same 83 chains.
  Only four held-out one-step
  windows contained new confirmed deployments; civilian MAE there was 97
  versus 77 state-only. All decision use is refused. See notes/shadow-simulator.md
  and local analysis/shadow-action-benchmark.json. Active search was preserved;
  schema 2 capture still needs its first live exercise at a coordinated boundary.
- 2026-11-19 Central. Audited unnecessary camera movement. Speed trial
  125952 selected pan_down 936 times and no other camera action.
  Its down-pan search bias was negative; the overview mask still allowed
  the move in viewport slack. Read-only replay of 780 captured down-pan
  frames used the validated inst13 Boston L1 boundary and 1920×1200
  viewport. The centered-overview mask blocked all 780. Focused zoom and
  panning retain their normal bounds and timed overview reset. Staged in
  `codex/centered-overview` with a new camera revision. 213 script tests,
  58 visualizer tests, model parity and graph checks passed offline.
  Production remained active. Verify a fresh live run at launch boundary.
- 2026-11-19 12:20 Central. Completed six-copy fixed-speed benchmark seed
  125952: all 24 fresh Boston L1 trials returned official scores, zero
  timeouts or errors. Frozen champion/base and copy assignments shared
  within crossover pairs; policy seeds paired, native outbreaks differ.
  1×: 64.6 scored trials per wave-hour, 1/12 qualifiers, 32.24% mean saved,
  28.79% minimum, 2.91 decisions/sim-second. 2×: 83.5/hour (+29%),
  5/12 qualifiers, 35.90% mean, 26.66% minimum, 1.73 decisions/sim-second.
  Both arms confirmed 36 spends. Median board readiness was 87 s each;
  median battle-to-return 172.5 vs 126.9 s. Wave barrier idle occupied
  18.2% vs 12.5% of available copy time. 79 host samples recorded minimum
  11.75 GiB available RAM and 14.3% median CPU load on reserved CPUs.
  Keep 2× opt-in pending broader policy validation; stock speed changes
  decision density. Resume supervisor restored the marker and launched
  production seed 126851 with eight copies under its existing RAM rule.
- Shadow capture retained 5,780 crowd frames and 72 native missile deployments
  across the same 24 fresh battles. Every battle fired a three-shot salvo;
  20 whole-salvo windows met the global-population timing filter and zero
  met the isolated single-cast timing/alignment filter. The archived CNN
  lost to persistence on both channels and hotspot ranking on all 24 new
  battles across 2,140 aligned pairs. A private refit per speed on eight
  distinct outbreaks each beat persistence on both channels on all eight
  held-out battles, but improved hotspot ranking on only two (both at 1×).
  This supports parallel offline crowd prediction, not action-effect labels
  or synthetic PPO. Collect variation in model-proposed salvo timing,
  targets and declines before fitting a decision surrogate.
  Evidence: `analysis/coverage-team-23af6f44f1/speed-comparison.jsonl`,
  `analysis/coverage-speed-shadow-report.jsonl` and
  `analysis/coverage-speed-shadow-refit.jsonl`.
- 2026-11-19 12:00 Central. Production seed 125851 drained normally.
  Deployed timing and shadow capture at `500da8e`; live six-copy fixed
  stock-speed comparison began with seed 125952, base 8a691469a829158d,
  inst13–18 and output `analysis/coverage-team-23af6f44f1`. The supervisor
  marker is held during the experiment. The handoff restores it and resumes
  regular search at seed 126851 when the comparison exits.
- 2026-11-19 Central. Staged campaign rollout timing on
  `codex/rollout-timing` at `c899c77` in an isolated checkout and pushed
  the branch. All 211 script tests passed offline. The new ledger fields
  record monotonic worker start, board readiness, episode start, battle
  start when reached, episode return and worker finish. Activate at a
  coordinated launch boundary, then measure per-copy idle time and compare
  1x with 2x at the same copy count. Live code and weights were untouched.
- 2026-11-19 Central. Throughput audit during active six-copy search, with
  inst13 preflight passing. Search 123851 recorded 24 fresh L1 starts across
  four generations, nine qualifying wins, five timeouts and one early retry.
  First native log timestamps across successive generations were 276, 347
  and 310 seconds apart. These spans include the wave barrier and other work;
  the ledger cannot isolate per-copy idle time. Keep the current search active.
- Existing crowd forecast replayed on three held-out process recordings at
  idle priority and one CPU thread while search ran. Both channels beat
  persistence on per-cell squared error in all three recordings. An offline
  densest-future-zombie-cell probe improved on two recordings and regressed
  on one. Brief batch-256 inference measured roughly 265,000 grids/s, excluding
  data loading and game interaction. Archived live comparison
  `analysis/coverage-team-cda1c7a4b1/forecast-comparison.jsonl` had two L1
  qualifiers in four control attempts and zero in four forecast attempts,
  including one forecast snapshot failure. No recorded stock decreases in
  either arm. Keep forecast experiments out of production policy updates.
  An action-conditioned shadow screen needs attributable native receipts and
  held-out outcome evidence. The first real throughput experiment is a 1x/2x
  comparison at the same copy count at a coordinated training boundary.
- 2026-11-19 Central. Pushed five pending main commits (f7f6e0a..3ddca28) through the GitHub App identity helper. Its authentication check passed. The reason for the earlier delay is unverified.
- 2026-11-19 08:30 Central. Six-copy minimum requested.
  Supplemental inst17/18 (PIDs 53148/45804) reached live L1 battle on CPUs
  8–11 while seed 121851 kept its original inst13–16 on CPUs 0–7. About
  8.2 GiB RAM remained available, with 6.4 GiB VRAM free. Transition helper
  PID 60596 repeats fresh extras if resources permit and writes their results
  alongside the active search. Old supervisor PID 49644 is draining its
  existing block. New supervisor PID 59164 uses the min-six hold marker
  and waits for idle copies, 12.5 GiB available RAM, and 3 GiB free disk.
  It chooses six copies, or eight at 16 GiB. Normal launches reserve half
  the logical CPUs for desktop use. The 204 trainer tests passed.
- 2026-11-19 08:14 Central. Checked continuous search seed
  120851 with four owned copies inst13–16, Boston L1 only. Latest leader
  43ee3ee08e4dca6d has 15 qualifying wins in 51 fresh starts and 33.07%
  mean saved in the search ledger. Supervisor hold marker is present.
  Host had about 9.1 GiB available RAM and 8.6 GiB free disk.
- 2026-11-19 08:11 Central. The checkpoint heartbeat fired
  with its scheduler set to ACTIVE despite the user's standing pause.
  Restored PAUSED through the automation manager and skipped publication.
- 2026-11-19 02:20 Central. Compacted the Observatory layout, moved Timeline
  into Monitor's Decision history, and made Game View permanently visible
  in Monitor. Isolated Chromium checks passed for responsive layout, replay,
  comparison, SSE, graph touch controls and fixture-based capture fallback.
  All 57 visualizer tests and graph assertions passed. Active campaign
  search stayed running. Default inst1 preflight still reports incomplete
  availability; inst13 preflight passed.
- 2026-11-19 02:16 Central. Merged PR #1 as 1cd20fa and pulled by fast-forward.
  Only requirements.txt changed. The active environment still imports Pillow
  12.3.0, and campaign search operators 50880 and 59348 were still running.
  Default inst1 preflight still reports the pre-existing unlock-profile issue.
- 2026-11-19 02:13 Central. Reviewed Dependabot PR #1 (Pillow 13.0.0).
  Simulated merge onto origin/main 01deff5 cleanly with only the pin change.
  Isolated CPython 3.14 x64 wheel passed screenshot conversion, PNG and menu
  image checks and all 57 visualizer tests. Recommend merge. Live game capture
  was not exercised. Active campaign search and its Python environment were untouched.
- 2026-11-19 02:12 Central. Learning now refreshes every 30 seconds while visible.
  Public Chrome observed an automatic results request and all four workers of
  search 106851 publishing decisions together. Deployed between searches.
  Regression checks passed (57 visualizer, 203 trainer, model parity and graph).
- 2026-11-19 02:10 Central. Published [checkpoint-82e4a4d891d2cb2e](https://github.com/notmike101/ai-plays-zombies-arent-real/releases/tag/checkpoint-82e4a4d891d2cb2e), policy 8a691469a829158d.
  The publisher downloaded all three release assets and verified checksums and schema before publication.
  GitHub initially rejected the target because capture commit 2351514 was local only. A fast-forward push made the exact SHA resolvable. The six-hour job now preflights the manifest's capture SHA.
- 2026-11-19 02:04 Central. Archived the six outstanding
  legacy runtime files from analysis and sessions in ignored
  analysis/coverage-legacy-cleanup-20261119, preserving relative paths
  and verifying SHA-256. Restored the committed historical nn_hist2.jsonl
  and nn_policy2.pt baselines. Active campaign seed 105851 uses its own
  search folder and base weights. Added narrow ignores for the four
  untracked legacy filenames/patterns. Training stayed active.
- 2026-11-19 02:02 Central. Backed up the uncommitted graph test rewrite
  as a restorable patch and restored the tracked test in the deployed
  checkout. Node reported Graph assertions passed; the file is clean.
- 2026-11-19 02:00 Central. Verified the tracked legacy graph regression
  passes from a clean worktree with the same graph source. The deployed
  checkout carries an uncommitted alternative test that exits during
  import because it requests exports absent from public/graph.js.
- 2026-11-19 01:52 Central. Deployed shareable Observatory tab links.
  Public Chrome verified a direct Learning link, Back/Forward, and
  one live SSE connection throughout. Learning reload remains manual
  after the first visit, unless the selected campaign run changes.
  All 57 visualizer tests and isolated UI regression checks passed.
- 2026-11-19 01:47 Central. Removed the source dropdown and Freeze view
  control from the Observatory. Default navigation opens live; explicit
  /?preview=1 retains isolated diagnostics. Public Chrome verified the
  controls were absent and Learning and Timeline loaded. All 57 visualizer
  tests and isolated browser replay, reconnect, game-view and mobile
  regressions passed. Frontend deployed through the existing listener.
- 2026-11-19 01:43 Central. Added precise cohort-mean hover tooltips
  to the Learning overview. Verified against public recorded results in
  Chrome, including edge positioning and tap/keyboard inspection.
- 2026-11-19 01:40 Central. Simplified the Learning overview to one line
  with one weighted mean per cohort and run. Public Chrome verified a
  single plotted line in each dataset and the existing outcomes chart.
  The mobile fixture verified weighted means, filters, touch and keyboard.
  The existing observatory served the frontend change directly.
- 2026-11-19 01:37 Central. Deployed Learning run-average overview on
  listener PID 12628 (create time 1795073834.2616203). Public Chrome
  loaded 10 dated campaign runs and 11 dated PPO runs and inspected
  plotted values by touch. Kept the existing outcomes chart and tables.
  Added projection tests; all 57 visualizer tests and isolated browser
  chart, stream, diagram and mobile checks passed. Results projection on
  local history took 220-235 ms across three reads and added about 4.8 KB.
  Campaign training stayed active through the observatory restart.
- 2026-11-19 01:28 Central. Hid the worker diagram on Learning.
  Public Chrome loaded existing Learning results, and the browser fixture
  verified that returning to Monitor retains the pinned worker at mobile width.
  Served the frontend update through the existing listener.
- 2026-11-19 01:16 Central. Deployed standby telemetry between campaign
  searches after 103851 ended. Supervisor launched 104851 naturally with
  operators 53672/59616. Public Chrome switched from game-only to live and
  saw two actual publishers: inst13 game 25292 / worker 57300 and inst14
  game 27560 / worker 42680. The selected planning READY, probability,
  identity, revision and first observation matched the retained server
  record (4,889 inputs). Pinned inst14 in the public diagram and used
  Follow live policy to return to inst13. Public game-only video also
  played at 960x600 on the previous held-out games. Training was not
  interrupted. Revised held-out observer coverage was tested in the suite
  and has not yet reached a fresh live held-out batch.
- 2026-11-19 01:08 Central. Fixed automatic Monitor selection so a live
  policy publisher takes precedence over a game-only node. A manually
  selected game remains pinned until it ends or Follow live policy is used.
  Restarted only the observatory via the ownership-checked launcher on
  PID 26040 (create time 1795072062.7120326). Public Chrome received the
  new SSE state and showed game-only nodes while no policy was publishing.
  56 visualizer tests, 203 trainer tests, exact model parity, graph checks
  and synthetic browser stream, diagram and mobile checks passed. Campaign
  search stayed active. Standby rollout is staged separately for an idle
  search boundary.
- 2026-11-19 00:51 Central. Deployed the active-worker diagram on
  observatory PID 10284 (create time 1795071053.233222). Public Chrome
  displayed six game nodes and played inst13 and inst14 simultaneously
  in separate viewers. Verified add/remove/automatic selection with SSE
  fixtures, mobile and keyboard selection in Chrome, and 54 visualizer
  tests in the deployed checkout. Campaign training stayed active.
- 2026-11-19 00:37 Central. Deployed game-only video fallback for automatic
  observatory attachment on listener 59624 (create time 1795070198.3777268).
  A public Chrome check rendered 960×600 live video for verified inst15
  PID 55568 while policy telemetry was waiting. When a fresh policy stream
  appears, it takes precedence. Manual selection and preview stay scoped.
  Main visualizer suite: 53 tests. Campaign training remained active.
- 2026-11-19 00:32 Central. Implemented and tested special
  activation credit at .01 each for up to three buildings. Native receipt
  requires the selected building's ability to change from zero to the exact
  enabled choice. Search can test bounded inspection after building a refuge.
  The fresh L1 inst19 pilot finished at 15.59% saved with zero selections
  and zero activations, then exited. Tests confirmed receipt, deduplication
  and cap (202 trainer, 52 visualizer). Active seed 102851 predates the
  change. Pilot: analysis/coverage-building-special-pilot.json.
- 2026-11-19 00:27 Central. Public and local traces agreed: live game 57260
  published through its episode, then the server had zero live streams
  while the public browser kept receiving waiting heartbeats. Deployed
  video busy-handoff and stalled-transfer retries on listener 56664
  (create time 1795069586.4640768), with training still active. Chrome
  verified a busy handoff retries instead of dropping straight to JPEG.
  Tested standby publishing in codex/zar-observatory-standby. The active
  campaign search still uses the single-observer implementation.
- 2026-11-19 00:15 Central. Special-building audit: native
  building class grid, selected building ability and HUD-gated special actions
  exist. The refuge placement scorer considers civilians and nearby
  defenders; it has no term for special-building activation. The first 15
  fresh candidate trials in search 05a311ab70 recorded no building selection,
  next-special or building-special panel action. Previous controlled native
  tests verified all 11 selectable special ability IDs. Training remained active.
- 2026-11-19 00:13 Central. Automatic observatory attachment skips observer
  errors if another fresh stream exists. Verified error and removal
  handoffs with fixtures and preserved manual selection. Listener PID
  49400 (create time 1795068792.149233), 51 visualizer tests passed.
  Campaign training stayed active. Campaign search still normally publishes
  one candidate at a time, so this change does not create a standby feed.
- 2026-11-19 00:09 Central. Game view now delivers shared hardware H.264
  video on observatory PID 18652 (create time 1795068261.3722775). Chrome
  through the named tunnel displayed 960×600 video from inst13 PID 56912:
  87 frames in six seconds with zero drops, 1.20 Mbit/s, ~0.20 s buffered
  lead, and 264 ms from request to playback in one warm check. A parallel
  three-second process sample measured ~17% of one CPU core for capture
  and encoding combined. Freeze and JPEG fallback passed. Closed test inst20
  after confirmation. Campaign training stayed active. Visualizer suite: 50.
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
