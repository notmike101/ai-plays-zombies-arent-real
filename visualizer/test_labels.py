"""make_obs <-> INPUT_LABELS correspondence: widths, exact positions, crowd
padding, and observer mismatch visibility. Run from visualizer/: python -m unittest test_labels"""
import math
from pathlib import Path
import re
import runpy
import tempfile
import unittest

import torch
from torch import nn

from labels import INPUT_LABELS, validate

ROOT = Path(__file__).resolve().parent
_TR = {}


def trainer():
    if not _TR:
        _TR.update(runpy.run_path(str(ROOT.parent / 'scripts' / 'nn_play2.py'),
                                  run_name='test_labels'))
    return _TR


# One unambiguous value per feature slot, independent of make_obs internals.
PROBE_O = dict(civ=7, zomb=11, converting=13, corpses=17, police=19,
               money=2500.0)
PROBE_ST = dict(t=450, planning=True, spend_frac=0.5, sim=100.0,
                deck=[{'name': n, 'charges': c, 'max_charges': c,
                       'alive': False}
                      for n, c in (('Police', 20), ('Bomber', 1),
                                   ('Heli', 1), ('Stungas', 1))])
# blob x/y arrive from run_episode already normalized to client fractions
PROBE_BLOBS = [(0.5, 0.5, 3000), (1.0, 1.0, 6000)]
# EXPECT[i] must equal make_obs(...)[i] AND describe INPUT_LABELS[i].
EXPECT = [
    math.log1p(7), math.log1p(11), math.log1p(13), math.log1p(17),
    math.log1p(19),
    2.5,   # $2500 / 1000
    1.5,   # 450 s / 300 (uncapped at 2)
    0.75,  # civilian fraction
    2.5,   # trend 2500 k/s / 1000 (clip +-3)
    -0.25,  # slope clip +-1
    1.0, 1.0, 1.0, 1.0,  # deck slots 1-4 full charges (charges / max)
    0.5, 0.5, 0.5,   # crowd 1: 960/1920, 600/1200, 3000/6000
    1.0, 1.0, 1.0,   # crowd 2: full-scale probe
    -1.0, -1.0, -1.0, -1.0, -1.0, -1.0,  # crowd 3-4 missing sentinel
    0.5,  # extent 2/4
    4.0, 5.0, 1.0,  # prev tool, prev cell, success
    1.0,  # planning
    0.5,  # spend_frac
]
# Keyword pins: position i of the probe must belong to a label whose meaning
# matches — catches same-width reorders that element-wise tests can't see.
LABEL_PINS = {0: 'civilians', 5: 'money', 6: 'elapsed', 8: 'trend',
              9: 'slope', 10: 'deck slot 1', 13: 'deck slot 4',
              14: 'crowd 1 x', 16: 'crowd 1 weight',
              23: 'crowd 4 x', 26: 'extent', 27: 'previous tool',
              30: 'planning', 31: 'budget'}


class Tiny(nn.Module):
    def __init__(self, n=3):
        super().__init__()
        self.gru = nn.GRU(n, 4, batch_first=True)
        self.hu = nn.Linear(4, 2)

    def forward(self, x, h=None):
        y, h = self.gru(x, h)
        return self.hu(y), h


class LabelTests(unittest.TestCase):
    def probe(self, blobs=PROBE_BLOBS):
        t = trainer()
        return t['make_obs'](dict(PROBE_ST), dict(PROBE_O), 0.75, 2500.0,
                             -0.25, blobs, 4, 5, 1)

    def test_widths_agree(self):
        t = trainer()
        self.assertEqual(len(INPUT_LABELS), t['NOBS'])
        self.assertEqual(t['NOBS'], len(EXPECT))
        self.assertEqual(t['PolicyNet2']().gru.input_size, len(INPUT_LABELS))
        import demo
        self.assertEqual(demo.PreviewPolicy().gru.input_size, len(INPUT_LABELS))
        validate(nobs=t['NOBS'])  # launch gate must pass
        with self.assertRaises(ValueError):
            validate(nobs=t['NOBS'] - 1)
        with self.assertRaises(ValueError):
            validate(nobs=2, labels=['same', 'same'])

    def test_exact_label_correspondence(self):
        obs = self.probe()
        self.assertEqual(len(obs), len(EXPECT))
        for i, (got, want) in enumerate(zip(obs, EXPECT)):
            self.assertAlmostEqual(got, want, places=6,
                                   msg=f'feature {i} != {INPUT_LABELS[i]}')
        for i, pin in LABEL_PINS.items():
            self.assertIn(pin, INPUT_LABELS[i].lower(),
                          msg=f'label {i} no longer means the probed feature')

    def test_crowd_missing_partial_full(self):
        obs = self.probe(blobs=[])
        self.assertEqual(obs[14:26], [-1.0] * 12)
        self.assertEqual(obs[26], 0.0)
        obs = self.probe(blobs=[(0, 0, 0)] * 3)
        self.assertEqual(obs[23:26], [-1.0, -1.0, -1.0])
        self.assertEqual(obs[26], 0.75)
        obs = self.probe(blobs=[(min(k / 5, 1.0), 0.5, 6000) for k in range(1, 6)])
        self.assertEqual(obs[26], 1.0)  # >4 detections truncate to 4 slots

    def test_warm_start_block_copy(self):
        import os
        import tempfile
        t = trainer()
        net = t['PolicyNet2']()
        sd = net.state_dict()
        old = {k: (v[:12] if k.startswith(('hc.weight', 'hc.bias')) else
                   v[:, :22] if k == 'gru.weight_ih_l0' else
                   v[:15] if k.startswith(('hu.weight', 'hu.bias')) else
                   v.clone()) for k, v in sd.items()}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'm.pt')
            torch.save(old, p)
            net2 = t['PolicyNet2']()
            t['load_pretrained'](net2, p)
            got = net2.state_dict()
        for key, want in (('hc.weight', old['hc.weight']),
                          ('hc.bias', old['hc.bias']),
                          ('hu.weight', old['hu.weight']),
                          ('gru.weight_ih_l0', old['gru.weight_ih_l0'])):
            pre = got[key][:want.shape[0]]
            if want.ndim == 2:
                pre = pre[:, :want.shape[1]]
            self.assertTrue(torch.equal(pre, want), key)
        self.assertFalse(torch.equal(got['hc.weight'][12:],
                                     got['hc.weight'][12:13].expand_as(
                                         got['hc.weight'][12:]) * 0))

    def test_no_generic_labels_in_source_list(self):
        self.assertFalse([s for s in INPUT_LABELS
                          if re.fullmatch(r'input \d+', s)])


class ObserverMismatchTests(unittest.TestCase):
    def test_short_labels_publish_explicit_warning(self):
        from observer import Observer
        net = Tiny().eval()
        with tempfile.TemporaryDirectory() as directory:
            ob = Observer(net, 0, 'mismatch', labels={'input': ['only one']},
                          directory=directory)
            try:
                with torch.no_grad():
                    ob.net().forward(torch.ones(1, 1, 3))
                frame = ob.snapshot()
                self.assertIn('label_warning', frame)
                self.assertTrue(
                    frame['label_warning'].startswith('input labels 1/3'))
                inp = next(l for l in frame['graph']['layers']
                           if l['id'] == 'input')
                self.assertEqual(inp['labels'][1:], ['input 1', 'input 2'])
            finally:
                ob.close()


if __name__ == '__main__':
    unittest.main()
