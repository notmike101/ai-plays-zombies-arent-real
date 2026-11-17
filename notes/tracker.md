# ZAR Tracker (live state â€” update EVERY run; guidance lives in ../AGENTS.md)

## CURRENT STATE (2026-11-17 — isolated Python environment verified, training LIVE)
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
