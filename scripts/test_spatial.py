import unittest
import numpy as np
import spatial


class SpatialTests(unittest.TestCase):
    def test_world_y_projects_up_and_dpi_is_not_applied_twice(self):
        px = spatial.project(np.array([[1829.2, 1972.4]]), (1631., 1318.6, .5795), 1920, 1200)
        np.testing.assert_allclose(px[0], [1074.8569, 221.1229], atol=.01)

    def test_carry_units_and_civilians_are_distinct(self):
        cells = np.array([[960., 600.], [970., 600.], [960., 600.]])
        result = spatial.features(cells, np.array([0, 1, 6]),
                                  np.array([[950., 590., 980., 610.]]), [], 1920, 1200)
        self.assertEqual(result['counts'][0].sum(), 1)
        self.assertEqual(result['counts'][1].sum(), 1)
        self.assertEqual(result['counts'][2].sum(), 1)
        self.assertEqual(sum(p is not None for p in result['build_targets']), 1)

    def test_zone_coverage_and_offscreen_points(self):
        zone = [[800., 300.], [1200., 300.], [1200., 800.], [800., 800.]]
        result = spatial.features(np.array([[-500., -500.]]), np.array([0]),
                                  np.empty((0, 4)), [zone], 1920, 1200)
        self.assertEqual(result['counts'][0].sum(), 0)
        self.assertGreater(result['counts'][4].sum(), 0)


if __name__ == '__main__':
    unittest.main()
