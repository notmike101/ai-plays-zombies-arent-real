"""Expert-trajectory logging for the winning scripted policy (it17 recipe).

The battle loop used to WIN Boston L5 (bronze 6.90, AGENTS.md "WINNING RECIPE")
is scripted, not learned. This module records its (state, action) stream in the
observation/action schema of notes/ml-spec.md so the GRU policy can be trained
to imitate it, then improve via PPO (reward = terminal saved_pct from the
progress file; badge lines bronze 4 / silver 13.69 / diamond 28).

Episode file: expert_ep_YYYYmmdd-HHMMSS.jsonl, one JSON per line:
  {"t": "meta",  "pid":, "map": "Boston__MA", "stage": 5, "start": [civ, zomb]}
  {"t": "step",  "ts": real_epoch, "sim_gap": s_since_prev,
                "civ":, "zomb":,                          # zarmem direct mode
                "obs_grid": [[r,g,b] x 64x45],            # optional, if frame given
                "action": {"slot": 1, "x":, "y":} | null} # heli deploy click
  {"t": "end",   "civ":, "zomb":, "saved_pct": float|None}

State source is exact (module .data RVAs, see notes/memory-map.md SOLUTION);
the grid is a PrintWindow frame resized to 64x45 — the CNN-lite input ml-spec
proposes. Action = the scripted heli click on the densest green blob
(zombie-contact cluster); null when no cluster / heli recharging (a "wait").
"""
import json
import time
import numpy as np


class ExpertLogger:
    def __init__(self, path, pid, start_civ_zomb, map_name="Boston__MA", stage=5):
        self.path = path
        self.f = open(path, "w", encoding="utf-8")
        self._write({"t": "meta", "pid": pid, "map": map_name, "stage": stage,
                     "start": list(start_civ_zomb), "ts": time.time()})
        self._prev_ts = time.time()

    @staticmethod
    def grid(img_small):
        """img_small: PIL RGB at any size -> 64x45 int list for the JSONL record."""
        g = np.asarray(img_small.convert("RGB").resize((64, 45)), dtype=np.uint8)
        return g.tolist()

    def step(self, civ_zomb, img_small, action):
        """img_small may be None (telemetry-only episodes: obs_grid omitted)."""
        now = time.time()
        rec = {"t": "step", "ts": now, "sim_gap": round(now - self._prev_ts, 2),
               "civ": civ_zomb[0], "zomb": civ_zomb[1],
               "action": action}
        if img_small is not None:
            rec["obs_grid"] = self.grid(img_small)
        self._write(rec)
        self._prev_ts = now

    def end(self, civ_zomb, saved_pct=None):
        self._write({"t": "end", "civ": civ_zomb[0], "zomb": civ_zomb[1],
                     "saved_pct": saved_pct, "ts": time.time()})
        self.f.close()

    def _write(self, rec):
        self.f.write(json.dumps(rec) + "\n")
        self.f.flush()


def load_episode(path):
    """Returns (meta, steps, end) for training."""
    meta, steps, end = None, [], None
    for ln in open(path, encoding="utf-8"):
        r = json.loads(ln)
        if r["t"] == "meta":
            meta = r
        elif r["t"] == "step":
            steps.append(r)
        else:
            end = r
    return meta, steps, end


if __name__ == "__main__":
    # self-check: with grid + telemetry-only steps
    from PIL import Image
    import tempfile
    p = tempfile.mktemp(suffix=".jsonl")
    im = Image.new("RGB", (1920, 1080), (10, 200, 30))
    lg = ExpertLogger(p, 0, (209867, 3000))
    lg.step((150000, 60000), im, {"slot": 1, "x": 1200, "y": 900})
    lg.step((140000, 61000), None, None)
    lg.end((130000, 0), saved_pct=6.9)
    meta, steps, end = load_episode(p)
    assert meta["pid"] == 0 and len(steps) == 2 and end["saved_pct"] == 6.9
    assert len(steps[0]["obs_grid"]) == 45 and len(steps[0]["obs_grid"][0]) == 64
    assert "obs_grid" not in steps[1]
    print("OK", p)
