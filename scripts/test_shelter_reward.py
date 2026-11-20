import unittest
import numpy as np

from shelter_reward import Shelter


class ShelterTests(unittest.TestCase):
    def snapshot(self, civilians, zombies=(), zones=None):
        zone = np.array([[0,0],[100,0],[100,100],[0,100]],dtype=np.float32)
        return dict(zones=[zone] if zones is None else zones,
                    units=dict(kind=np.array([0]*len(civilians)+[1]*len(zombies)),
                               id=np.array([key for key,_ in civilians]+[100+i for i in range(len(zombies))]),
                               pos=np.asarray([point for _,point in civilians]+list(zombies)).reshape(-1,2)))

    def test_only_sustained_shelter_is_credited_and_credit_survives_departure(self):
        shelter=Shelter(10)
        full=self.snapshot([(1,(25,25)),(2,(30,30)),(3,(120,120))])
        self.assertEqual(shelter.observe(full,0.),0.)
        self.assertAlmostEqual(shelter.observe(full,.5),.01)
        self.assertEqual(shelter.observe(full,1.),0.)
        emptied=self.snapshot([],[(20,20),(21,21),(22,22)])
        self.assertEqual(shelter.observe(emptied,1.5),0.)
        self.assertEqual(shelter.occupied_breaches,0)
        self.assertEqual(len(shelter.credited),2)

    def test_first_occupied_breach_is_charged_once_and_pressure_matches_near_edge(self):
        shelter=Shelter(10)
        civilians=[(1,(25,25)),(2,(30,30)),(3,(120,120))]
        shelter.observe(self.snapshot(civilians),0.)
        self.assertEqual(shelter.perimeter(np.array([[100.,10.],[450.,10.]])).tolist(),[1.,0.])
        invaded=self.snapshot(civilians,[(20,20),(21,21),(22,22)])
        self.assertAlmostEqual(shelter.observe(invaded,.5),-.02)
        self.assertEqual(shelter.observe(invaded,1.),0.)
        self.assertEqual(shelter.occupied_breaches,1)
        self.assertEqual(shelter.perimeter(np.array([[100.,10.]])).tolist(),[0.])

    def test_stronger_cost_changes_only_the_breach_reward(self):
        baseline, stronger = Shelter(10), Shelter(10, breach_cost=.30)
        civilians = [(1, (25, 25)), (2, (30, 30)), (3, (120, 120))]
        intact = self.snapshot(civilians)
        breached = self.snapshot(civilians, [(20, 20), (21, 21), (22, 22)])
        for shelter in (baseline, stronger):
            self.assertEqual(shelter.observe(intact, 0.), 0.)
            self.assertAlmostEqual(shelter.observe(intact, .5), .01)
            self.assertAlmostEqual(shelter.observe(breached, 1.), -shelter.breach_cost * .2)
            self.assertEqual(shelter.observe(breached, 1.5), 0.)
            self.assertEqual(shelter.exposed, {1, 2})
            self.assertEqual(shelter.first_occupied_breach, 1.)
        self.assertAlmostEqual(stronger.breach_penalty, 3 * baseline.breach_penalty)

    def test_overlapping_shelters_do_not_double_charge_the_same_person(self):
        shelter=Shelter(10)
        zone=self.snapshot([])['zones'][0]
        zones=[zone,zone+5.]
        civilians=[(1,(25,25))]
        shelter.observe(self.snapshot(civilians,zones=zones),0.)
        near_first_only=[(2,2),(3,3),(4,4)]
        self.assertAlmostEqual(shelter.observe(self.snapshot(civilians,near_first_only,zones),.5),-.005)
        near_second_only=[(101,101),(102,102),(103,103)]
        self.assertEqual(shelter.observe(self.snapshot(civilians,near_second_only,zones),1.),0.)
        self.assertEqual(len(shelter.exposed),1)
        self.assertEqual(shelter.occupied_breaches,2)

    def test_civilian_reaching_another_intact_shelter_can_be_exposed_again(self):
        shelter=Shelter(10)
        first=self.snapshot([])['zones'][0]
        zones=[first,first+[120,0]]
        start=[(1,(25,25))]
        first_breach=[(20,20),(21,21),(22,22)]
        shelter.observe(self.snapshot(start,zones=zones),0.)
        self.assertAlmostEqual(shelter.observe(self.snapshot(start,zones=zones),.5),.005)
        self.assertAlmostEqual(shelter.observe(self.snapshot(start,first_breach,zones),1.),-.01)
        self.assertEqual(shelter.observe(self.snapshot([(1,(110,25))],first_breach,zones),1.5),0.)
        second=[(1,(145,25))]
        self.assertEqual(shelter.observe(self.snapshot(second,first_breach,zones),2.),0.)
        self.assertEqual(shelter.observe(self.snapshot(second,first_breach,zones),2.5),0.)
        second_breach=[(140,20),(141,21),(142,22)]
        self.assertAlmostEqual(shelter.observe(self.snapshot(second,first_breach+second_breach,zones),3.),-.01)
        self.assertEqual(shelter.breach_exposures,2)
        self.assertEqual(len(shelter.credited),1)
        self.assertEqual(len(shelter.exposed),1)

    def test_initial_contamination_and_no_zone_give_no_points(self):
        shelter=Shelter(10)
        initial=self.snapshot([(1,(25,25))],[(20,20),(21,21),(22,22)])
        self.assertEqual(shelter.observe(initial,0.),0.)
        self.assertEqual(shelter.observe(initial,.5),0.)
        self.assertEqual(shelter.observe(self.snapshot([(1,(25,25))],zones=[]),1.),0.)
        self.assertEqual(shelter.occupied_breaches,0)

    def test_duration_counts_unique_occupants_and_stops_at_breach(self):
        shelter = Shelter(10, duration_rate=.01)
        zone = self.snapshot([])['zones'][0]
        zones = [zone, zone+5]
        full = self.snapshot([(1, (25, 25)), (2, (35, 35))], zones=zones)
        self.assertEqual(shelter.observe(full, 0.), 0.)
        self.assertAlmostEqual(shelter.observe(full, .5), .011)
        self.assertEqual(shelter.observe(full, .5), 0.)
        partial = self.snapshot([(2, (35, 35))], zones=zones)
        self.assertAlmostEqual(shelter.observe(partial, 1.), .0005)
        invaded = self.snapshot([(2, (35, 35))], [(20, 20), (21, 21), (22, 22)], zones=zones)
        self.assertAlmostEqual(shelter.observe(invaded, 1.5), -.01)
        self.assertEqual(shelter.occupant_seconds, 1.5)
        self.assertAlmostEqual(shelter.duration_credit, .0015)

    def test_duration_skips_gaps_missing_samples_and_caps_reward(self):
        shelter = Shelter(1, duration_rate=.01)
        full = self.snapshot([(1, (25, 25))])
        shelter.observe(full, 0.)
        shelter.observe(full, 2.)
        shelter.observe(None, 2.25)
        shelter.observe(full, 2.5)
        self.assertEqual(shelter.duration_intervals, 0)
        for step in range(1, 81):
            shelter.observe(full, 2.5+step*.5)
        self.assertEqual(shelter.occupant_seconds, 40.)
        self.assertAlmostEqual(shelter.duration_credit, .30)
        self.assertEqual(shelter.duration_basis, 30.)
