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
                                   ('Heli', 0), ('Stungas', 1))])
PROBE_ST['deck'][2].update(alive=True, max_charges=1)
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
    1.0, 1.0, 0.0, 1.0,  # deck slots 1-4 full charges (charges / max)
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
              9: 'slope', 10: 'deck slot 1', 13: 'deck slot 4', 12: 'charges / max', 279: 'charges / max',
              14: 'crowd 1 x', 16: 'crowd 1 weight',
              23: 'crowd 4 x', 26: 'extent', 27: 'previous tool',
              30: 'planning', 31: 'budget'}

EXPECT += [0.0]*240
for i in range(19):
    EXPECT += [0., 1. if i < 4 and i != 2 else 0., 0.]
EXPECT += [0., -1., -1.]
from scripts.mechanic_contract import EXTRA_LABELS
EXPECT += [0.]*len(EXTRA_LABELS)
LABEL_PINS.update({32: 'grid civilians cell 1', 80: 'grid zombies cell 1',
                   128: 'grid defenders cell 1', 176: 'grid buildings cell 1',
                   224: 'grid safe zone cell 1', 272: 'police loadout',
                   273: 'police castable', 274: 'police pending',
                   329: 'unspent skill', 330: 'anchor tool', 331: 'anchor cell'})
LABEL_PINS.update({332:'camera x',335:'placement paint',336:'ready land',
    343:'planning slot 1',356:'selected unit kind',
    332+EXTRA_LABELS.index('Armed turret placement (0/1)'):'armed turret',
    332+EXTRA_LABELS.index('Simulation paused (0/1)'):'simulation paused',
    332+EXTRA_LABELS.index('Simulation speed (native half ticks / 8)'):'simulation speed',
    332+EXTRA_LABELS.index('Selected unit SP upgrade 4 (native level / 4)'):'selected unit sp upgrade 4',
    332+EXTRA_LABELS.index('Modal dialog open (0/1)'):'modal dialog open',
    332+len(EXTRA_LABELS)-1:'grid fire oil subcell fraction'})


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

    def test_spatial_loadout_and_anchor_semantics(self):
        import numpy as np
        t = trainer()
        st = dict(PROBE_ST, grid=np.arange(240).reshape(5,48),
                  loadout={n: i+1 for i,n in enumerate(t['DECK_ORDER'])},
                  sp=2, anchor=(15,47))
        obs = t['make_obs'](st, PROBE_O, .75, 0, 0, [], 0, 0, 0)
        np.testing.assert_allclose(obs[32:224], np.log1p(np.arange(192)))
        np.testing.assert_allclose(obs[224:272], np.arange(192,240))
        np.testing.assert_allclose(obs[272:329:3], np.arange(1,20)/10.)
        np.testing.assert_allclose(obs[329:332], [.2,15/72,47/48])

    def test_crowd_missing_partial_full(self):
        obs = self.probe(blobs=[])
        self.assertEqual(obs[14:26], [-1.0] * 12)
        self.assertEqual(obs[26], 0.0)
        obs = self.probe(blobs=[(0, 0, 0)] * 3)
        self.assertEqual(obs[23:26], [-1.0, -1.0, -1.0])
        self.assertEqual(obs[26], 0.75)
        obs = self.probe(blobs=[(min(k / 5, 1.0), 0.5, 6000) for k in range(1, 6)])
        self.assertEqual(obs[26], 1.0)  # >4 detections truncate to 4 slots

    def test_old_checkpoint_is_rejected_without_reinterpreting_columns(self):
        t = trainer()
        net = t['PolicyNet2']()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'old.pt'
            torch.save(net.state_dict(), p)
            with self.assertRaisesRegex(ValueError, 'Incompatible checkpoint'):
                t['load_pretrained'](net, p)

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
