"""Offline checks for the experimental cell scorer used in live comparisons."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import torch
from compare_spatial import SpatialPolicy, collect_pairs, trainer


class SpatialTargetTest(unittest.TestCase):
    def test_transient_failure_repeats_only_its_matched_pair(self):
        jobs = [('copy', 'arm', None, 1, str(i)) for i in range(4)]
        pool = Mock()
        pool.map.side_effect = [[{}, {}, {'err':'Timed out waiting for UI frames'}, {}],
                                [{'ok':1}, {'ok':2}]]
        with TemporaryDirectory() as directory:
            self.assertEqual(collect_pairs(pool, jobs, Path(directory)), [{}, {}, {'ok':1}, {'ok':2}])
        self.assertEqual(pool.map.call_args.args[1], jobs[2:])

    def test_swapping_cells_swaps_every_tools_scores(self):
        model = SpatialPolicy()
        x = torch.randn(2, 3, trainer.NOBS)
        altered = x.clone()
        cells = altered[..., model.first:model.first+5*trainer.NC].unflatten(-1, (5, trainer.NC))
        cells[..., [4, 12]] = cells[..., [12, 4]]
        _, scores, values, _ = model(x)
        new = model(altered)[1].unflatten(-1, (trainer.NU, trainer.NC))
        old = scores.unflatten(-1, (trainer.NU, trainer.NC))
        torch.testing.assert_close(new[..., 4], old[..., 12])
        torch.testing.assert_close(new[..., 12], old[..., 4])
        (scores.square().mean()+values.square().mean()).backward()
        self.assertGreater(float(model.cell.weight.grad.abs().sum()), 0)
