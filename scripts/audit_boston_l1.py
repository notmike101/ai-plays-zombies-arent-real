"""Read-only Boston L1 audit counts from the local native experiment journals."""
import collections
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "analysis"


def records(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def audit():
    wins = []
    for path in ROOT.glob("coverage-team-*/trials.jsonl"):
        for trial in records(path):
            for level in trial.get("levels", []):
                seed = (level.get("outbreak") or {}).get("seed")
                if (level.get("stage") == 1 and level.get("campaign") == "Boston, MA"
                        and level.get("start_kind") == "fresh" and type(seed) is int
                        and level.get("end") == "won" and (level.get("saved") or 0) >= .30):
                    wins.append((seed, bool(trial.get("layout_receipts")), level["saved"]))
    print("30% discoveries, distinct outbreaks, layout receipts:", len(wins),
          len({seed for seed, _, _ in wins}), sum(replay for _, replay, _ in wins))
    print("No-receipt scores:", sorted(score for _, replay, score in wins if not replay))
    reserve = []
    for path in ROOT.glob("coverage-team-*/holdout.jsonl"):
        for trial in records(path):
            if trial.get("team_id") == "bf3fc52369fc3746":
                reserve.extend(level for level in trial["levels"] if level.get("stage") == 1)
    print("Structured team reserve outcomes:", dict(collections.Counter(r["end"] for r in reserve)))
    print("Distinct reserve outbreaks:", len({r["outbreak"]["seed"] for r in reserve
          if type((r.get("outbreak") or {}).get("seed")) is int}))
    training = []
    for cohort in ("battle-boundary-63a02e027d", "battle-boundary-3ad2ea83d9",
                   "opening-timing-9f45ac368a", "recurrent-capacity-551f9d64f2"):
        rows = list(records(ROOT / ("coverage-" + cohort) / "results.jsonl"))
        evaluation = [r for r in rows if r["phase"] == "evaluation"]
        print(cohort, "frozen attempts", dict(collections.Counter(r["end"] for r in evaluation)))
        training.extend(r for r in rows if r["phase"] == "train"
                        and ("capacity" not in cohort or r["round"] <= 2))
    for end in sorted({r["end"] for r in training}):
        group = [r for r in training if r["end"] == end]
        rewards = [sum(r["experiment_signal"]["reward_components"].values()) for r in group]
        print(end, len(group), "median reward", statistics.median(rewards))
    print("Occupied starts", sum((r["sheltered_pct_at_ready"] or 0) > 0 for r in training))
    print("Confirmed spend starts", sum((r["confirmed_spends"] or 0) > 0 for r in training))
    print("Nonempty deployment logs", sum(bool(r["logged_deployments"]) for r in training))
    print("Timeout READY declines", sum(r["ready_choices"]["declined_steps"]
          for r in training if r["end"] == "timeout"))
    print("12s residual multiplier", (.99 * .95) ** 120)


if __name__ == "__main__":
    audit()
