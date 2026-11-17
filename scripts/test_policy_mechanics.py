"""Mechanics schema, aggregate observations and masks without a game process."""
import unittest
from unittest.mock import Mock
import numpy as np

from native_state import WALL, EVAC, HELI, VEHICLE, MEDEVAC, PATCH
from policy_mechanics import observation, unit_names, nearest_per_cell, extra_masks, SELECTORS, Mechanics
from scripts.mechanic_contract import EXTRA_TOOLS, EXTRA_LABELS, GLOBAL_LABELS, GRID_CHANNELS


def fixture():
    units=dict(pos=np.array([[100.,100.],[200.,200.]]),kind=np.array([5,1]),
        id=np.array([10,20]),dir=np.array([[1.,0.],[0.,1.]]),hp=np.array([3.,5.]),
        timer=np.array([6.,2.]),contact=np.array([-2.,0.]),converting=np.zeros(2),ztype=np.zeros(2))
    maps={k:{} for k in ('payload','trap_kind','level','far_first','officer_kind','ai','kills','boosts')}
    maps['payload'][10]=2
    selection={k:[] for k in ('units','zones','helicopters','evac','polygon')};selection['units']=[10];selection['gate']=-1
    s=dict(units=units,unit_maps=maps,selection=selection,camera=[0.,0.,1.],
        playarea=np.array([[-1000.,-1000.],[1000.,-1000.],[1000.,1000.],[-1000.,1000.]]),
        buildings=dict(center=np.array([[100.,100.]]),destroyed=np.array([0]),
                       damage=np.array([3.]),**{'class':np.array([2])}),
        paint=dict(pos=np.empty((0,2)),kind=np.array([])))
    s.update({name:np.zeros(0,dtype) for name,dtype in [('walls',WALL),('evac',EVAC),
        ('helicopters',HELI),('vehicles',VEHICLE),('medevacs',MEDEVAC),('hazards',PATCH)]})
    return s


class MechanicsTests(unittest.TestCase):
    def test_semantic_labels_and_native_variant_receipts(self):
        s=fixture();hud={'actions':{'target_toggle':(1,2)}}
        perks=[dict(name='Extra_Zones',locked=True)]+[dict(name='-',locked=False)]*2
        values=observation(s,['Garrison']+['-']*6,perks,hud,1,False,.45,1920,1200)
        self.assertEqual(len(values),len(EXTRA_LABELS));self.assertEqual(len(set(EXTRA_LABELS)),len(EXTRA_LABELS))
        self.assertEqual(values[3:6],[1.,0.,.45]);self.assertEqual(values[11],4/42)
        self.assertEqual(values[len(GLOBAL_LABELS)+1],2/5)
        offset=len(GLOBAL_LABELS)+19+GRID_CHANNELS.index('unit FireMortar')*48
        self.assertAlmostEqual(sum(values[offset:offset+48]),np.log(2))
        self.assertEqual(values[EXTRA_LABELS.index('Native HUD target_toggle available (0/1)')],1.)
        self.assertEqual(unit_names(s['units'],s['unit_maps']).tolist(),['FireMortar',''])

    def test_masks_use_roster_native_choices_and_perk_constraints(self):
        s=fixture();st=dict(native=s,planning=True,planning_roster=['Sniper']+['-']*6,
            perks=[dict(name='Extra_Zones',locked=True),dict(name='Hot_Fire',locked=False),dict(name='-',locked=False)],
            hud={'actions':{'target_toggle':(1,2)}},build_targets=[(100,100)]*48,
            targets={k:[None]*48 for k in (*SELECTORS,'edge')})
        masks=extra_masks(st);get=lambda name:masks[EXTRA_TOOLS.index(name)]
        self.assertTrue(get('place_Sniper').any());self.assertFalse(get('place_Battleship').any())
        self.assertEqual(np.flatnonzero(get('arm_slot')).tolist(),[0])
        self.assertFalse(get('perk_Hot_Fire').any());self.assertEqual(np.flatnonzero(get('perk_clear')).tolist(),[1])
        self.assertFalse(get('panel_medevac_leave').any());self.assertTrue(get('panel_target_toggle')[0])
        self.assertFalse(get('zone_finish').any());self.assertFalse(get('select_building').any())

    def test_targets_are_visible_and_nearest_with_stable_ties(self):
        points=[(200,200),(210,200),(200,200),(-100,0)]
        targets=nearest_per_cell(points,1920,1200)
        self.assertEqual([p for p in targets if p is not None],[(210,200)])
        targets=nearest_per_cell(points,1920,1200,bounds=(190,190,220,220))
        self.assertFalse(any(p is not None for p in targets))

    def test_corner_drag_starts_at_native_corner_and_keeps_model_endpoint(self):
        m=Mechanics.__new__(Mechanics);m.env=Mock(cw=1920,ch=1200);m.controls=Mock()
        st={'targets':{'corner':[(633,336)]*48}}
        m.execute(st,'drag_corner',0)
        m.controls.gesture.assert_not_called()
        m.execute(st,'drag_corner',9)
        m.controls.cancel.assert_called_once()
        m.controls.drag_handles.assert_called_once_with((633,336),(422,336))
        self.assertNotIn('gesture_anchor',st)

    def test_pause_speed_and_gesture_sentinels_have_explicit_meanings(self):
        values=observation(fixture(),['-']*7,[dict(name='-',locked=False)]*3,
                           {'actions':{}},0,True,0,1920,1200,paused=True,speed=8)
        self.assertEqual(values[-2:],[1.,1.])
        self.assertEqual(values[EXTRA_LABELS.index('Gesture anchor cell (/ 48; -1 absent)')],-1.)


if __name__=='__main__':unittest.main()
