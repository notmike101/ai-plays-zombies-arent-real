"""Bounded owned-copy training/evaluation smoke; output never uses MODEL/HIST."""
import argparse
import hashlib
import json
from pathlib import Path

import torch
import nn_play2 as trainer
import zar_boot


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--copy', default='inst9')
    ap.add_argument('--train', action='store_true')
    ap.add_argument('--steps', type=int, default=6)
    ap.add_argument('--seconds', type=float, default=8)
    args = ap.parse_args()
    if not 1 <= args.steps <= 60 or not 0 < args.seconds <= 30:
        ap.error('Validation scope: 1..60 planning steps and at most 30 battle seconds')
    root = Path(trainer.ROOT) / 'visualizer/runtime'
    root.mkdir(exist_ok=True)
    original = Path(trainer.MODEL).read_bytes() if Path(trainer.MODEL).exists() else None
    torch.manual_seed(42)
    net = trainer.PolicyNet2()
    env = None
    try:
        env = zar_boot.boot(zar_boot.COPIES / args.copy)
        tr = trainer.run_episode((env.pid, net.state_dict(), False, 'validation',
                                  dict(plan_steps=args.steps, battle_seconds=args.seconds)))
        report = {k: v for k, v in tr.items() if k not in
                  ('obs', 'masks', 'ulps', 'clps', 'trail')}
        if 'err' in tr:
            raise RuntimeError(tr['err'])
        assert trainer.valid_trajectory(tr), report
        if args.train:
            opt = torch.optim.Adam(net.parameters(), lr=3e-4)
            trainer.ppo_update(net, [tr], opt, epochs=1)
            trainer.save_checkpoint(net, opt, root / 'validation-policy.pt', 'validation')
        report['training_update'] = args.train
        (root / 'validation-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if env:
            zar_boot.stop(env)
        after = Path(trainer.MODEL).read_bytes() if Path(trainer.MODEL).exists() else None
        assert original == after, 'User checkpoint changed during validation'
        if after:
            print('User checkpoint preserved:', hashlib.sha256(after).hexdigest())


if __name__ == '__main__':
    main()
