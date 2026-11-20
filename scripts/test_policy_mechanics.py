"""Mechanics schema, aggregate observations and masks without a game process."""
import unittest
from unittest.mock import Mock
import numpy as np

from native_state import WALL, EVAC, HELI, VEHICLE, MEDEVAC, PATCH, MOSH
from policy_mechanics import observation, unit_names, embedded_defenses, nearest_per_cell, pan_room, extra_masks, SELECTORS, Mechanics
from scripts.mechanic_contract import EXTRA_TOOLS, EXTRA_LABELS, GLOBAL_LABELS, GRID_CHANNELS


def fixture():
    units=dict(pos=np.array([[100.,100.],[200.,200.]]),kind=np.array([5,1]),
        id=np.array([10,20]),dir=np.array([[1.,0.],[0.,1.]]),hp=np.array([3.,5.]),
        timer=np.array([6.,2.]),contact=np.array([-2.,0.]),converting=np.zeros(2),ztype=np.zeros(2))
    maps={k:{} for k in ('payload','trap_kind','level','far_first','officer_kind','ai','kills','boosts','upgrades')}
    maps['payload'][10]=2
    selection={k:[] for k in ('units','zones','helicopters','evac','polygon')};selection['units']=[10];selection['gate']=-1
    selection['building']=-1
    s=dict(units=units,unit_maps=maps,selection=selection,camera=[0.,0.,1.],
        playarea=np.array([[-1000.,-1000.],[1000.,-1000.],[1000.,1000.],[-1000.,1000.]]),
        buildings=dict(center=np.array([[100.,100.]]),destroyed=np.array([0]),
                       damage=np.array([3.]),**{'class':np.array([2])}),
        paint=dict(pos=np.empty((0,2)),kind=np.array([])),
        terrain=dict(codes=np.zeros(48,dtype=np.int16),bridges=np.zeros(48,dtype='u1')))
    s['bridges']=dict(pos=np.empty((0,2)),hp=np.array([]),full=np.array([]))
    s['fire']={name:np.zeros(48) for name in ('flags','green','burnt','oil')}
    s.update({name:np.zeros(0,dtype) for name,dtype in [('walls',WALL),('evac',EVAC),
        ('helicopters',HELI),('vehicles',VEHICLE),('medevacs',MEDEVAC),('hazards',PATCH),('mutations',MOSH)]})
    return s


class MechanicsTests(unittest.TestCase):
    def test_embedded_defenses_distinguish_payloads_and_occupied_zones(self):
        zones = [np.array([(x, 0), (x+10, 0), (x+10, 10), (x, 10)]) for x in (0, 1, 20)]
        units = dict(kind=np.array([0, 5, 5, 5, 6, 8]),
                     id=np.arange(1, 7), pos=np.array([(3, 3), (4, 4), (24, 4),
                                                      (5, 5), (12, 5), (3, 3)]))
        snapshot = dict(units=units, zones=zones,
                        unit_maps=dict(payload={2: 1, 3: 1, 4: 4}, trap_kind={}))
        self.assertEqual(embedded_defenses(snapshot),
                         {'GasMortar': {'total': 2, 'inside_occupied': 1},
                          'Garrison': {'total': 1, 'inside_occupied': 0},
                          'MLRS': {'total': 1, 'inside_occupied': 1}})

    def test_overview_only_allows_panning_back_toward_center(self):
        overview = np.array([[15, 10], [85, 10], [85, 60], [15, 60]])
        self.assertTrue(all(room <= .018 for room in pan_room(overview, 100, 100).values()))
        shifted = pan_room(overview + [0, -8], 100, 100)
        self.assertGreater(shifted['pan_up'], .018)
        self.assertLessEqual(shifted['pan_down'], .018)

    def test_panning_toward_empty_space_stops_before_losing_the_playable_map(self):
        shape=np.array([[30,-38],[70,-38],[70,25],[30,25]])
        room=pan_room(shape,100,100)
        self.assertLess(room['pan_down'],0)
        self.assertGreater(room['pan_up'],0)
        self.assertGreater(pan_room(shape+[0,48],100,100)['pan_down'],0)
        zoomed=pan_room(shape*10-[450,0],100,100)
        self.assertGreater(zoomed['pan_left'],0)
        self.assertGreater(zoomed['pan_right'],0)

    def test_special_activation_needs_matching_new_native_ability(self):
        mechanics=Mechanics.__new__(Mechanics)
        mechanics.env=Mock(cw=1920,ch=1200)
        mechanics.controls=Mock()
        mechanics.env.scalar.return_value=2
        mechanics.env.array.return_value=np.array([0,5])
        st={'native':{'selection':{'building':1},'buildings':{'ability':[0,0]}}}
        self.assertEqual(mechanics.execute(st,'panel_building_5',0),(1,5))
        self.assertIsNone(mechanics.execute(st,'panel_building_6',0))
        st['native']['buildings']['ability'][1]=5
        self.assertIsNone(mechanics.execute(st,'panel_building_5',0))
        st['native']['buildings']['ability'][1]=0
        mechanics.env.scalar.return_value=1
        self.assertIsNone(mechanics.execute(st,'panel_building_5',0))

    def test_planning_picker_rejects_without_claiming_a_roster_change(self):
        from game_controls import PickerNavigationError

        m=Mechanics.__new__(Mechanics);m.env=Mock(cw=1920,ch=1200);m.controls=Mock()
        initial=['-']*7
        m.controls.equip_unit.side_effect=PickerNavigationError('picker did not open')
        m.controls.planning_roster.return_value=initial
        self.assertIs(m.execute({'planning_roster': initial}, 'equip_Sniper', 0), False)
        m.controls.planning_roster.return_value=['Sniper']+initial[1:]
        with self.assertRaises(PickerNavigationError):
            m.execute({'planning_roster': initial}, 'equip_Sniper', 0)

    def test_building_boundary_cache_invalidates_on_geometry_change(self):
        m=Mechanics.__new__(Mechanics);m.building_membership=None
        points=np.array([[1.,1.],[4.,4.]])
        polygon=np.array([[0.,0.],[3.,0.],[3.,3.],[0.,3.]])
        first=m.building_in_playarea(points,polygon)
        self.assertEqual(first.tolist(),[True,False])
        self.assertIs(m.building_in_playarea(points.copy(),polygon.copy()),first)
        points[0]=[5.,5.]
        self.assertEqual(m.building_in_playarea(points,polygon).tolist(),[False,False])
        polygon*=2
        self.assertEqual(m.building_in_playarea(points,polygon).tolist(),[True,True])

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
        for name in ('place_click','place_paint'):self.assertEqual(np.flatnonzero(get(name)).tolist(),[0])
        st['planning']=False
        battle=extra_masks(st)
        for name in ('place_click','place_paint'):self.assertFalse(battle[EXTRA_TOOLS.index(name)].any())
        st['planning']=True
        self.assertEqual(np.flatnonzero(get('arm_slot')).tolist(),[0])
        self.assertFalse(get('perk_Hot_Fire').any());self.assertEqual(np.flatnonzero(get('perk_clear')).tolist(),[1])
        self.assertFalse(get('panel_medevac_leave').any());self.assertTrue(get('panel_target_toggle')[0])
        self.assertFalse(get('zone_finish').any());self.assertFalse(get('select_building').any())
        equip=EXTRA_TOOLS.index('equip_Sniper')
        st['picker_blocked']=[(72+equip,2)]
        self.assertEqual(np.flatnonzero(extra_masks(st)[equip]).tolist(),[0,1,3,4,5,6])
        st.update(planning=False, paused=False, speed_ticks=1)
        self.assertFalse(extra_masks(st)[EXTRA_TOOLS.index('speed_half')].any())
        self.assertTrue(extra_masks(st)[EXTRA_TOOLS.index('speed_1'),0])
        st['paused']=True
        self.assertTrue(extra_masks(st)[EXTRA_TOOLS.index('speed_half'),0])


    def test_targets_are_visible_and_nearest_with_stable_ties(self):
        points=[(200,200),(210,200),(200,200),(-100,0)]
        targets=nearest_per_cell(points,1920,1200)
        self.assertEqual([p for p in targets if p is not None],[(210,200)])
        indices=nearest_per_cell(points,1920,1200,indices=True)
        self.assertEqual([i for i in indices if i is not None],[1])
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

    def test_nonfinite_observation_names_the_native_feature(self):
        with self.assertRaisesRegex(RuntimeError, 'Corridor full width'):
            observation(fixture(), ['-']*7, [dict(name='-', locked=False)]*3,
                        {'actions': {}}, 0, True, 0, 1920, 1200,
                        evac_tool=(True, False, float('nan')))

    def test_pause_speed_and_gesture_sentinels_have_explicit_meanings(self):
        values=observation(fixture(),['-']*7,[dict(name='-',locked=False)]*3,
                           {'actions':{}},0,True,0,1920,1200,paused=True,speed=8)
        self.assertEqual(values[EXTRA_LABELS.index('Simulation paused (0/1)')],1.)
        self.assertEqual(values[EXTRA_LABELS.index('Simulation speed (native half ticks / 8)')],1.)
        self.assertEqual(values[EXTRA_LABELS.index('Gesture anchor cell (/ 48; -1 absent)')],-1.)

    def test_transport_and_wall_state_preserves_normalization_and_empty_cells(self):
        s=fixture();s['mutations']=np.zeros(1,MOSH);s['mutations']['pos']=[100,100]
        s['mutations']['until']=55.;s['mutations']['members']=99
        s['wall_hp']=[np.array([10.,0.])]
        s['walls']=np.zeros(1,WALL);s['walls']['a']=[100,100];s['walls']['b']=[120,100];s['walls']['full_hp']=20
        s['medevacs']=np.zeros(1,MEDEVAC);s['medevacs']['alive']=1;s['medevacs']['pos']=[100,100]
        s['medevacs']['carried']=23;s['medevacs']['ordered']=1
        values=observation(s,['-']*7,[dict(name='-',locked=False)]*3,{'actions':{}},0,True,0,1920,1200)
        def channel(name):
            start=EXTRA_LABELS.index(f'Native state {name} cell 1 (mean; 0 empty)')
            return values[start:start+48]
        self.assertAlmostEqual(sum(channel('wall HP fraction')),0.25)
        self.assertAlmostEqual(sum(channel('wall breached cell fraction')),0.5)
        self.assertAlmostEqual(sum(channel('medevac carried log1p')),np.log(24))
        self.assertEqual(sum(channel('medevac departure ordered')),1.)
        self.assertAlmostEqual(sum(channel('mutation completion sim time / 600')),55/600,places=6)
        self.assertAlmostEqual(sum(channel('mutation members log1p')),np.log(100))

    def test_modal_masks_block_world_actions_and_preserve_policy_confirmation(self):
        masks=extra_masks({'dialog':True})
        self.assertEqual(np.flatnonzero(masks.any(axis=1)).tolist(),
                         [EXTRA_TOOLS.index('dialog_confirm'),EXTRA_TOOLS.index('dialog_cancel')])
        self.assertEqual(masks.sum(),2)

    def test_corridor_width_observation_and_contextual_wheel(self):
        values=observation(fixture(),['-']*7,[dict(name='-',locked=False)]*3,
            {'actions':{}},0,True,0,1920,1200,evac_tool=(True,False,165.))
        i=EXTRA_LABELS.index('Corridor tool armed (0/1)')
        self.assertEqual(values[i:i+3],[1.,0.,.165])
        m=Mechanics.__new__(Mechanics);m.env=Mock(cw=1920,ch=1200);m.controls=Mock()
        m.execute({'corridor_armed':True},'corridor_wider',9)
        m.controls.arm.assert_not_called();m.controls.zoom.assert_called_once_with(1,(422,336))

    def test_terrain_codes_bridge_bits_and_outside_sentinel(self):
        s=fixture();s['terrain']['codes'][:3]=[4,0,-1];s['terrain']['bridges'][1]=1
        values=observation(s,['-']*7,[dict(name='-',locked=False)]*3,{'actions':{}},0,True,0,1920,1200)
        offset=EXTRA_LABELS.index('Grid terrain cell 1 (native code / 5; -1 outside storage)')
        self.assertEqual(values[offset:offset+3],[.8,0.,-1.])
        self.assertEqual(values[offset+49],1.)


if __name__=='__main__':unittest.main()
