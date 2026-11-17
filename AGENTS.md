# Zombies Aren't Real — Agent Guidance (READ FIRST, EVERY RUN)

Mission: train an ML model (GRU policy) that becomes a god-tier player of Boston,
MA — it must SAVE >=35% civilians on EVERY level, consistently. The MODEL plays and
owns ALL strategy (unit buys, safe zones, placement, deployment, in-battle casts).
I FACILITATE: unblock the learner, keep episodes flowing, monitor progress. Never
hand-script strategy the model should learn. Curriculum L1->L5 (START OVER restarts
the campaign; badges persist as BEST; R restart keeps board + leftover budget).

## Process rules (every turn)
- TRACKER: live state, evidence, PIDs and next steps live in `notes/tracker.md`.
  Read it at the START of a run; UPDATE it at the END of every run (replace
  CURRENT STATE; keep entries dated). This AGENTS.md stays guidance-only — never
  log progress here.
- GIT: local repo at `D:\zar-scratch` with GitHub remote
  `https://github.com/notmike101/ai-plays-zombies-arent-real`. Commit EVERY file
  update IMMEDIATELY, ALWAYS Conventional Commits (`feat:`/`fix:`/`chore:`/
  `docs:`/`test:`); push at milestones. Never force-add gitignored artifacts.
- Update `notes/*` (not this file) with new verified mechanics/traps as found.
- No subagents. Kill test instances at phase end. Update tracker before yielding
  a long run.

## Hard rules (safety + fairness)
- NEVER modify `C:\Games\...` (read-only install). Work only in `D:\zar-scratch`
  copies (`game-copies\instN\`, each with `steam_appid.txt`=5185890; copies' own
  ini files MAY be edited). NEVER write the user's game install.
- Admin console = CHEAT: manual one-off human-driven diagnostics ONLY. NEVER in
  training/automation loops.
- Difficulty stays pinned (normal) — no difficulty farming for scores.
- Input: virtual-input DLL + PostMessage ONLY. NEVER the real mouse
  (no SetCursorPos/mouse_event), never take over the user's cursor. NEVER resize
  a live game window (pick size via settings.ini before launch).
- Lost battle (civ <= ~10%) => press R,R immediately (user directive) — never
  watch doomed runs. OPEN DIALOG/menu pauses the sim + dump writer: that's state,
  not a hang.
- Extra game instances are allowed to speed training, but leave CPU/GPU/RAM
  headroom on the user's machine; enumerate pids via psutil by exe dirname.
- Screenshots/observations: PrintWindow works in planning/menu only.

## Where things live
- `notes/tracker.md` — CURRENT STATE, NEXT STEPS, PIDs, evidence index.
- `notes/ml-spec.md` — model design; `scripts/nn_play.py` — PPO trainer (train /
  play / greedy modes; checkpoint `sessions/nn_policy.pt`; logs
  `analysis/nn_*.log|jsonl`).
- `scripts/env_zar.py` — ZAREnv(pid): memory-RVA observation + ready()/cast/place
  primitives; `scripts/zar_input.py` + `scripts/hookdll/` — virtual input.
- `scripts/launch_boards.py <instN...>` — kill/relaunch/nav boards to planning.
- `notes/automation.md` — verified input matrix + traps; `notes/memory-map.md` —
  RVAs; `notes/game-rules.md` — mechanics; `notes/engine.md` — binary notes.

## Standing input traps (detail in notes/automation.md)
- `key_press` needs scan codes (zar_input SC table); READY = SPACE (stray SPACE =
  pause trap); placements = `vi.click` (CLICK MODE; drags dead in current build);
  menu clicks = raw screenshot px; NEVER click CHOOSE; edit progress/config FILES
  + restart instead of dead menu paths; never edit `scripts/*.py` while trainer
  workers are live (they reimport per episode); F6 dumps freeze while dialogs open.

## Phase-end checklist
1. Tracker + notes updated with verified findings; lessons learned -> notes.
2. All uncommitted work committed (conventional).
3. Kill test instances (enumerate via psutil dirname).
