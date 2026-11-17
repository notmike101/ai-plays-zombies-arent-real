"""Read-only check against the current trainer model; never calls run_episode or opens a game."""
from pathlib import Path
import re
import json
import runpy
import statistics
import tempfile
import time

import torch

from observer import Observer


def main():
    root = Path(__file__).resolve().parent
    (root / 'runtime').mkdir(exist_ok=True)
    source = runpy.run_path(str(root.parent / 'scripts' / 'nn_play2.py'), run_name='visualizer_model_check')
    net = source['PolicyNet2']().eval()
    x = torch.ones(1, 1, source['NOBS'])

    def sequence():
        h = None
        output = []
        with torch.no_grad():
            for _ in range(12):
                u, c, v, h = net(x, h)
                output.append((u.clone(), c.clone(), v.clone(), h.clone(),
                               int(torch.distributions.Categorical(logits=u).sample()),
                               int(torch.distributions.Categorical(logits=c).sample())))
        return output

    rng = torch.random.get_rng_state()
    plain = sequence()
    with tempfile.TemporaryDirectory(dir=root / 'runtime') as directory:
        observer = Observer(net, 0, 'verification-only', directory=directory,
                            labels={'input': source['INPUT_LABELS'],
                                    'hu': source['TOOLS'][:source['NU']],
                                    'hc': source['CELL_LABELS']})
        try:
            torch.random.set_rng_state(rng)
            observed = sequence()
            for a, b in zip(plain, observed):
                assert all(torch.equal(i, j) for i, j in zip(a[:4], b[:4]))
                assert a[4:] == b[4:]
            frame = observer.snapshot()
            assert len(frame['values']['input']) == source['NOBS']
            assert len(frame['values']['gru']) == source['HID']
            assert len(frame['values']['hu']) == source['NU']
            assert len(frame['values']['hc']) == source['NU']*source['NC']
            assert 'label_warning' not in frame
            assert len(json.dumps(frame, separators=(',', ':')).encode()) < 8*1024*1024 - 200000, 'Keep room for masked probabilities in server frame cap'
            inp = next(l for l in frame['graph']['layers']
                       if l['id'] == 'input')
            assert inp['labels'] == source['INPUT_LABELS'], \
                'training-supplied labels must reach the published graph ' \
                'verbatim'
            assert not re.search(r'\binput \d+\b', ' '.join(inp['labels']))
            print(f"Actual PolicyNet2: {source['NOBS']} inputs, "
                  f"{frame['graph']['parameters']:,} parameters; exact outputs "
                  f"and sampled decisions match for 12 recurrent steps.")
            with torch.no_grad():
                measured = []
                for _ in range(200):
                    begin = time.perf_counter()
                    net(x)
                    observer.snapshot()
                    measured.append(time.perf_counter() - begin)
            observer.close()
            with torch.no_grad():
                baseline = []
                for _ in range(200):
                    begin = time.perf_counter()
                    net(x)
                    baseline.append(time.perf_counter() - begin)
            print(f'Warm inference median: {statistics.median(baseline)*1000:.3f} ms plain; {statistics.median(measured)*1000:.3f} ms observed including snapshot.')
            print('First topology construction, disk IO, GPU models and actual gameplay timing are not covered by this median.')
        finally:
            observer.close()


if __name__ == '__main__':
    main()
