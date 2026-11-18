"""Offline checks for the experimental cell scorer used in live comparisons."""
import unittest
import torch
from compare_spatial import SpatialPolicy, trainer


class SpatialTargetTest(unittest.TestCase):
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
