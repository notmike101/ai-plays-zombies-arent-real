"""A real PyTorch policy with synthetic inputs, explicitly tagged preview. No game imports."""
import argparse
import math
import time

import torch
from torch import nn

from observer import Observer
from labels import INPUT_LABELS, validate
TOOLS = ['wait', 'ready', 'napalm', 'mortar', 'sniper', 'turret', 'mine', 'c4',
         'gas_mortar', 'upgrade_unit', 'zone_rect', 'para', 'heli', 'gas_bomb', 'ac130']
NOBS = len(INPUT_LABELS)  # preview width follows the shared label list
validate(nobs=NOBS)


class PreviewPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(NOBS, 128, batch_first=True)
        self.hu = nn.Linear(128, 15)
        self.hc = nn.Linear(128, 12)
        self.val = nn.Linear(128, 1)

    def forward(self, x, h=None):
        y, h = self.gru(x, h)
        return self.hu(y), self.hc(y), self.val(y), h


def run(duration=0):
    torch.set_num_threads(1)
    torch.manual_seed(5185890)
    net = PreviewPolicy().eval()
    observer = Observer(net, 0, 'synthetic-preview', labels={'input': INPUT_LABELS, 'hu': TOOLS,
                                                          'hc': [f'Cell {i + 1}' for i in range(12)]})
    h, step, start = None, 0, time.monotonic()
    try:
        while not duration or time.monotonic() - start < duration:
            x = torch.tensor([[[math.sin(step * .18 + i * .63) * 2 for i in range(NOBS)]]])
            with torch.no_grad():
                u, c, _, h = net(x, h)
                du, dc = torch.distributions.Categorical(logits=u), torch.distributions.Categorical(logits=c)
                selected = {'hu': int(du.sample()), 'hc': int(dc.sample())}
                observer.publish(probabilities={'hu': du.probs, 'hc': dc.probs}, selected=selected,
                                 phase='synthetic', preview=True)
            step += 1
            time.sleep(.6)
    finally:
        observer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=0, help='Seconds, or zero until interrupted')
    run(parser.parse_args().duration)
