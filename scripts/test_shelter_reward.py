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

    def test_initial_contamination_and_no_zone_give_no_points(self):
        shelter=Shelter(10)
        initial=self.snapshot([(1,(25,25))],[(20,20),(21,21),(22,22)])
        self.assertEqual(shelter.observe(initial,0.),0.)
        self.assertEqual(shelter.observe(initial,.5),0.)
        self.assertEqual(shelter.observe(self.snapshot([(1,(25,25))],zones=[]),1.),0.)
        self.assertEqual(shelter.occupied_breaches,0)
