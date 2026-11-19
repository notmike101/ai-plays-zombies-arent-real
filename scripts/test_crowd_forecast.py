import tempfile
import unittest
from unittest.mock import Mock
from pathlib import Path
import numpy as np
import torch
from crowd_forecast import CrowdForecast, pairs
from layout_memory import demonstrations, remaining_layout, visible_points


class CrowdModelTests(unittest.TestCase):
    def test_future_frame_uses_simulation_clock_and_matching_camera(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'trace.npz'
            grid=np.zeros((4,3,6,8),dtype='f4')
            grid[2,0]=2
            np.savez(dest,sim=[0.,1.,2.,3.],camera=[[0,0,1],[0,0,1],[0,0,1],[20,0,1]],grids=grid)
            x,y=pairs(dest)
            self.assertEqual(len(x),1)
            self.assertTrue((y[0,0]==2).all())

    def test_untrained_forecast_equals_persistence(self):
        x=torch.rand(4,3,6,8)
        torch.testing.assert_close(CrowdForecast()(x),x[:,:2])

    def test_retrieval_reads_stage_coordinates_without_importing_a_save(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'board'
            p.write_text('stage 1 = emerald 35.36 played\nhist_carry 1 zone = 3 0 0 2 0 1 1 1 1 1\nhist_carry 2 garrison = 10 12 1\n')
            with p.open('a') as f:f.write('hist_carry 5 building = Radio_Tower 10 12\n')
            stages=demonstrations(p)
            self.assertEqual(stages[1][0]['kind'],'zone')
            self.assertEqual(stages[2][0]['points'],[[10.,12.]])

    def test_carried_building_is_not_purchased_twice(self):
        keep=dict(kind='mortar',points=[[100.,150.]])
        existing=dict(kind='garrison',points=[[100.,150.]])
        self.assertEqual(remaining_layout([keep,existing],{'_text':'board garrison = 100.001 150.0 2'}),[keep])

    def test_offscreen_target_is_reprojected_after_pan(self):
        env=Mock(cw=1920,ch=1200)
        env.scalar.side_effect=[0,0,1,0,1000,0,1]
        controls=Mock()
        self.assertEqual(visible_points(env,controls,np.array([[1000.,0.]])),[(960,600)])
        controls.key_action.assert_called_once_with('pan_right')
