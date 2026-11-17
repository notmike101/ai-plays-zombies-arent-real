# Current schema3 implementation (2026-11-17)

The historical design below is superseded where it differs from scripts/nn_play2.py.
Current:332 observations,128-unit single-layer GRU,72 tool logits and72x48
conditional position logits plus value. Native grid carries civilian/zombie/
defender/building/zone observations; per-ability levels, stock and arrival state,
SP and geometry anchors are explicit. Model-selected loadout uses UI receipts.
Reward is -new infections / initial civilians +5*actual terminal saved fraction.
No purchase/cast bonus or per-step floor. Planning/battle caps bootstrap instead
of forcing an action or treating alive civilians as a win. Unknown terminal
outcomes are excluded. Native stock, not config defaults, controls availability.
Schema metadata rejects old checkpoints; sessions/nn_policy2.pt is preserved.
See training-improvements.md for tested behavior, launch commands and limits.

# ML spec — learning to play Boston L5 (draft v2, 2026-11-15)

## UPDATE after baselines + WIN-1 (read first)
All naive plans LOSE to the conversion snowball (A 0.00, B 0.19, C 0.00, WIN-1 0%/best 1%).
The policy must learn DYNAMIC play: first-strike helis at t=0 (HP=1 one-shot window),
heli redeployment every 26 s recharge on the biggest cluster, fortify on threatened wall
segments, Repair picks, mine fields at breach points, and EARLY RESTART of doomed runs
(user directive: <10% civilians = failure → R RETRY). The RETRY-iterate loop (breach
markers persist in planning; RETRY keeps the board) is the primary search mechanism.
The reward shaping should reflect this: survival time of zones, conversions prevented
early, and the terminal saved_pct.


## Problem framing
Two coupled decision phases per episode:
1. **Planning** (no zombies): spend $6,605 (+ carry already on board) on safe zones,
   walls, fortify, Turrets/Mortars/Snipers/Garrisons, building-class ability picks.
   One-shot spatial layout problem, but order matters for undo/branching.
2. **Battle** (deterministic sim, 30 ticks/sim-s): deploy SP-bought abilities (Police
   paratroopers x19 squads, Heli x6 with 26 s recharge) on the live horde; optionally
   place walls/gates mid-battle. A dynamic resource-allocation problem under the
   conversion snowball.

The game is tick-deterministic with per-stage saved outbreak seeds (steam_cloud/outbreaks/)
=> identical (plan, actions) reproduce identical outcomes; "repeat outbreak" admin command
re-rolls the same outbreak for counterfactuals.

## Observation (per decision)
- **Spatial**: downsampled screenshot grid (~64x45 RGB at zoom-out, or 3 channels:
  civilians-white density, zombie-green density, zone/wall masks). At planning time the
  crowd is the signal (white dots); in battle the zombie glow is the signal.
- **Scalars**: money, civilians-safe %, zones used/11, land cap %, civilians-left %,
  zombies count, zombie health, SP stock per ability, cooldowns, sim_time, tick.
  Source: screenshot OCR of the HUD/STATS panel + F6 .txt dumps (rich but 275 MB .state
  side-file — parse .txt only; dump sparingly) + admin console readouts.
- **Map priors** (precomputed once per map/stage): building footprints + heights,
  special-building classes (from map data), play-area polygon, walkable land.

## Action space
- Planning: {arm tool garrison|mortar|sniper|turret|zone|fortify|gate} x {client x, y}
  (+ Enter for zone close). Verified automatable via the virtual-input DLL.
- Battle: {deploy slot 1..7} x {client x, y} (+ timing = decision step index). Verified.
- Episode control: READY, speed F4/F5, retry.

## Reward
- Terminal: saved_pct (the game's own metric; badge lines bronze 4% / silver 13% /
  diamond 28% / sapphire 41% on L5) -> shaped reward: saved_pct/100, +badge bonuses,
  strong penalty for wipe (saved 0). progress/*.progress + end-screen are the source.
- Shaping (optional): per-battle-step delta of civilians-left % (the STATS panel gives
  it live), kills per SP spent (end screen per-unit kills vs SP value).

## Architecture (candidate)
- **GRU policy** (user's suggestion): inputs = CNN encoder over the spatial grid +
  scalars MLP -> GRU over decision steps -> heads: {tool/type (softmax), x, y (Gaussian
  or discretized 32x32 grid), stop}. Handles the sequential placement/deployment nature
  and partial observability (hidden outbreak sites) naturally.
- Alternative: small transformer over (state, action) history; or ConvNet + pointer
  network for precise coordinates. Start GRU — cheapest to iterate.
- Value head for PPO.

## Training loop
1. Harness episode (scripts/harness.py + zar_input VirtualInput): restore checkpoint
   steam_cloud snapshot -> load Boston L5 -> (planning actions) -> READY -> speed 4x ->
   battle actions each ~2 s poll (deployables on detected clusters) -> end -> reward.
2. Parallel: N copies (inst1..instN), each with own VirtualInput + steam_cloud; sims run
   unfocused; the user's game stays foreground for observation.
3. Determinism: same seed + plan + actions = same battle; vary plans across episodes.
4. Initial data: baseline episodes A/B/C recorded; sandbox mode ($ UNLIMITED, 99999 SP,
   all units) for exploration data without budget pressure.
5. RL: PPO with the real game as env (slow but exact); frame the battle phase as a
   semi-MDP (decision every ~2 s real / 8 sim s).

## Eval gates
- Beat baseline B (0.19%) -> beat bronze (4% = win) -> silver 13.69% (the save's stage-4
  best) -> diamond 28%+.
- Regression check: every harness change re-runs baseline B (deterministic).

## Known harness gaps to fix before training
- Speed: F4=4x verified; F5 behavior (expected 8x) needs one more test; button clicks
  unreliable. Battle-phase admin console (virtual Ctrl+Space) unverified — verify with
  screenshot before any typed command (raw SPACE in typed strings toggles pause!).
- Placement precision: pixel-detect building centroids for Turret/Garrison; open-ground
  for Mortar; zoom-in helps.
- Ctrl+Z undo wipes the whole board — never rely on undo; snapshot before planning.
- One transient freeze seen during a globe transition — add hang detection
  (SendMessageTimeout) + relaunch to the harness.
- .prep NMPL decode (notes/prep-format.md) would enable file-level plans (no clicks);
  optional optimization after the UI-driven loop works.
