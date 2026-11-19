import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import numpy as np
import torch
from crowd_forecast import CrowdForecast, pairs
from layout_memory import apply_layout, demonstrations, fit_refuge, remaining_layout, visible_points


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

    def test_carried_objects_match_once_and_walls_can_reverse(self):
        wall=dict(kind='wall',points=[[30,40],[10,20]])
        tower=dict(kind='garrison',points=[[5,6]])
        dump={'_text':'board zone = 2 10 20 30 40 1 1\nboard garrison = 5 6 1'}
        self.assertEqual(remaining_layout([tower,wall,tower],dump),[tower])

    def test_budget_proposal_skips_before_moving_the_camera(self):
        env=Mock()
        env.scalar.return_value=0.
        env.game_state.return_value={'phase':'planning'}
        env.money.return_value=11.875
        proposal={'kind':'zone','points':[[0,0],[10,0],[0,10]],'observed_cost':909.925}
        result=apply_layout(env,[proposal])
        self.assertEqual(result[0]['result'],'below_observed_cost')
        env.vi.click.assert_not_called()
        self.assertEqual(env.scalar.call_count,2)

    def test_unchanged_picker_rejection_uses_another_free_slot(self):
        from game_controls import PickerNavigationError
        env=Mock()
        env.scalar.return_value=0.
        env.game_state.return_value={'phase':'planning'}
        env.money.side_effect=[100.,25.]
        with patch('layout_memory.Controls') as controls,patch('layout_memory.visible_points',return_value=[(5,6)]):
            ctrl=controls.return_value
            ctrl.planning_roster.return_value=['Garrison','-','Nest']
            ctrl.equip_unit.side_effect=[PickerNavigationError('picker open'),['Garrison','-','Mortar']]
            records=apply_layout(env,[dict(kind='mortar',points=[[5,6]])],occupied=['Garrison'])
            self.assertEqual([c.args for c in ctrl.equip_unit.call_args_list],[('Mortar',1),('Mortar',2)])
            self.assertEqual(records[0]['result'],'picker_rejected')
            self.assertEqual(records[1]['after'],25.)
            ctrl.place.assert_called_once_with('Mortar',(5,6))

    def test_refuge_proposal_uses_live_people_and_respects_map_bounds(self):
        actions=[dict(kind='zone',points=[[1,1],[3,1],[3,3],[1,3]])]
        people=np.tile([[8.,8.]],(2100,1))
        params=dict(aspect=1.,scale=1.,defense_weight=.1)
        changed,report=fit_refuge(actions,people,[[0,0],[10,0],[10,10],[0,10]],params)
        self.assertEqual((report['sample'],report['original_covered'],report['proposed_covered']),(2048,0.,1.))
        self.assertNotEqual(changed,actions)
        untouched,_=fit_refuge(actions,people,[[0,0],[5,0],[5,5],[0,5]],params)
        self.assertEqual(untouched,actions)
