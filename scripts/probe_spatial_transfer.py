"""CPU-only location transfer diagnostic. Trains temporary heads, writes no weights."""
import argparse
import time

import torch
from torch import nn

from nn_play2 import INPUT_LABELS, MODEL, NC, NOBS, NU, PolicyNet2, TOOLS, load_pretrained


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=MODEL)
    args = parser.parse_args()
    torch.set_num_threads(1)
    policy = PolicyNet2().eval()
    load_pretrained(policy, args.model)
    first = INPUT_LABELS.index('Grid civilians cell 1 (log1p count)')
    tool = TOOLS.index('mortar')
    held = torch.arange(0, 40, 4)
    seen = torch.tensor([i for i in range(40) if i % 4])
    for seed in (1, 2, 3):
        torch.manual_seed(seed)
        # Both heads see identical synthetic boards. Only the location of the
        # largest zombie cluster is supervised; this is not a gameplay reward.
        def boards(pool, count):
            target = pool[torch.randint(len(pool), (count,))]
            grid = torch.randint(0, 4, (count, 5, NC)).float().log1p()
            grid[:, 4] = 0
            grid[torch.arange(count), 1, target] = 4
            x = torch.zeros(count, 1, NOBS)
            x[:, 0, first:first+5*NC] = grid.flatten(1)
            with torch.no_grad():
                h = policy.gru(x)[0][:, 0]
            return h, grid.transpose(1, 2), target

        train = boards(seen, 384)
        tests = [boards(pool, 128) for pool in (seen, held)]
        for mode in ('dense', 'residual', 'shared'):
            head = policy.hc
            # Slice the selected tool exactly as in the conditional policy head.
            dense = nn.Linear(head.in_features, NC)
            with torch.no_grad():
                dense.weight.copy_(head.weight.reshape(NU, NC, -1)[tool])
                dense.bias.copy_(head.bias.reshape(NU, NC)[tool])
            shared = nn.Linear(5, 1, bias=False)
            nn.init.zeros_(shared.weight)
            opt = torch.optim.Adam([*dense.parameters(), *shared.parameters()], lr=.01)

            def scores(h, grid):
                logits = dense(h)
                if mode == 'shared':
                    return shared(grid[:, :40]).squeeze(-1)
                if mode == 'residual':
                    logits = logits + shared(grid).squeeze(-1)
                return logits[:, :40]

            start = time.perf_counter()
            for step in range(180):
                idx = torch.arange(32) + 32*(step % 12)
                loss = nn.functional.cross_entropy(scores(train[0][idx], train[1][idx]), train[2][idx])
                opt.zero_grad()
                loss.backward()
                opt.step()
            with torch.no_grad():
                accuracy = [float((scores(h, grid).argmax(1) == target).float().mean())
                            for h, grid, target in tests]
            print(seed, mode, 'seen/held', accuracy,
                  'seconds', round(time.perf_counter()-start, 3))


if __name__ == '__main__':
    main()
