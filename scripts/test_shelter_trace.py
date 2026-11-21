"""Focused tests for the opt-in passive Shelter threat trace."""
import hashlib
import unittest

import numpy as np
import torch

import shelter_reward
from shelter_reward import Shelter


class ShelterTraceTests(unittest.TestCase):
    def snapshot(self, civilians, zombies=(), zones=None, tick=7):
        zone = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
        return dict(tick=tick,
                    zones=[zone] if zones is None else zones,
                    units=dict(kind=np.asarray([0] * len(civilians) + [1] * len(zombies)),
                               id=np.asarray([ident for ident, _ in civilians]
                                             + list(range(1000, 1000 + len(zombies)))),
                               pos=np.asarray([point for _, point in civilians]
                                              + list(zombies)).reshape(-1, 2)))

    def sequence(self, trace, duration_rate=None):
        shelter = Shelter(10, duration_rate=duration_rate, trace=trace)
        inside = [(1, (25, 25)), (2, (30, 30))]
        steps = [(self.snapshot(inside), 0.),
                 (self.snapshot(inside, [(110, 50)]), .5),
                 (self.snapshot(inside, [(110, 50), (170, 50), (20, 120)]), 1.),
                 (self.snapshot(inside, [(25, 50), (30, 55), (50, 60)]), 1.5),
                 (self.snapshot(inside, [(25, 50), (30, 55), (50, 60)]), 2.)]
        return shelter, [shelter.observe(snapshot, sim) for snapshot, sim in steps]

    def test_disabled_by_default_and_stamp_is_inert(self):
        shelter = Shelter(10)
        self.assertIs(shelter.trace, False)
        shelter.observe(self.snapshot([(1, (25, 25))]), 0.)
        shelter.stamp(0, 'Garrison', 5, ['Garrison'], {})
        self.assertEqual(shelter.zone_samples, [])
        self.assertEqual(shelter.breach_rows, [])
        self.assertEqual(shelter.trace_gaps, [])

    def test_enabled_matches_disabled_rewards_state_and_rng_stream(self):
        plain, rewards = self.sequence(False)
        traced, traced_rewards = self.sequence(True)
        self.assertEqual(rewards, traced_rewards)
        for attribute in ('presence_credit', 'breach_penalty', 'occupied_breaches',
                          'first_occupied_breach', 'occupant_seconds', 'duration_credit'):
            self.assertEqual(getattr(plain, attribute), getattr(traced, attribute))
        for attribute in ('breached', 'credited', 'exposed', 'active_exposure'):
            self.assertEqual(getattr(plain, attribute), getattr(traced, attribute))
        self.assertEqual(len(plain.protected), len(traced.protected))
        cells = np.array([[100., 10.], [50., 50.]])
        self.assertEqual(plain.perimeter(cells).tolist(), traced.perimeter(cells).tolist())
        self.assertTrue(len(traced.zone_samples) == 5 and plain.zone_samples == [])
        torch.manual_seed(5)
        before = torch.rand(6)
        self.sequence(True, duration_rate=.01)
        after = torch.rand(6)
        torch.manual_seed(5)
        plain_before = torch.rand(6)
        self.sequence(False, duration_rate=.01)
        plain_after = torch.rand(6)
        self.assertTrue(torch.equal(before, plain_before))
        self.assertTrue(torch.equal(after, plain_after))

    def test_sample_rows_record_threat_rings_and_stamp_once_per_sample(self):
        shelter = Shelter(10, trace=True)
        shelter.observe(self.snapshot([(1, (25, 25)), (2, (30, 30))],
                                      [(110, 50), (170, 50)]), 0.)
        self.assertEqual(len(shelter.zone_samples), 1)
        row = shelter.zone_samples[0]
        self.assertEqual((row['sim'], row['tick'], row['decision']), (0., 7, None))
        zone = row['zones'][0]
        self.assertEqual(zone['zone'], hashlib.sha1(
            np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
            .tobytes()).hexdigest()[:12])
        self.assertEqual(zone['occupants'], 2)
        self.assertEqual(zone['zombies_inside'], 0)
        self.assertEqual((zone['zombies_within_30m'], zone['zombies_within_60m'],
                          zone['zombies_within_120m']), (1, 1, 2))
        self.assertAlmostEqual(zone['nearest_outside_metres'], 10.)
        self.assertEqual(zone['breached'], 0)
        shelter.stamp(3, 'Helicopter', 42, ['Garrison', 'Helicopter'], {'Helicopter': 2})
        self.assertEqual(row['decision'], 3)
        self.assertEqual(row['selected_tool'], 'Helicopter')
        self.assertEqual(row['selected_cell'], 42)
        self.assertEqual(row['legal_casts'], ['Garrison', 'Helicopter'])
        self.assertEqual(row['stock'], {'Helicopter': 2.0})
        shelter.observe(self.snapshot([(1, (25, 25))]), .5)
        shelter.observe(self.snapshot([(1, (25, 25))]), 1.)
        shelter.stamp(9, 'Wait', 0, [], {'SeekDestroy': 1})
        stamped = [sample for sample in shelter.zone_samples if sample['decision'] == 9]
        self.assertEqual(len(stamped), 2)
        self.assertEqual(row['decision'], 3)

    def test_first_observed_breach_row_is_reserved_once_per_zone(self):
        shelter = Shelter(10, trace=True)
        inside = [(1, (25, 25))]
        shelter.observe(self.snapshot(inside), 0.)
        shelter.observe(self.snapshot(inside, [(25, 50), (30, 55), (50, 60)]), .5)
        self.assertEqual(len(shelter.breach_rows), 1)
        breach = shelter.breach_rows[0]
        self.assertEqual((breach['sim'], breach['tick'], breach['breach']), (.5, 7, 1))
        self.assertEqual(breach['occupants_at_first_observed_breach'], 1)
        self.assertEqual(breach['zone'], shelter.zone_samples[1]['zones'][0]['zone'])
        shelter.observe(self.snapshot(inside, [(25, 50), (30, 55), (50, 60)]), 1.)
        self.assertEqual(len(shelter.breach_rows), 1)
        self.assertEqual(shelter.zone_samples[-1]['zones'][0]['breached'], 1)

    def test_periodic_rows_are_capped_and_drops_are_counted(self):
        shelter = Shelter(10, trace=True)
        snapshot = self.snapshot([])
        for step in range(shelter_reward.ZONE_TRACE_LIMIT + 5):
            shelter.observe(snapshot, step * .5)
        self.assertEqual(len(shelter.zone_samples), shelter_reward.ZONE_TRACE_LIMIT)
        self.assertEqual(shelter.trace_dropped, 5)

    def test_gaps_are_recorded_for_spacing_and_missing_snapshots(self):
        shelter = Shelter(10, trace=True)
        snapshot = self.snapshot([(1, (25, 25))])
        shelter.observe(snapshot, 0.)
        shelter.observe(snapshot, 3.)
        self.assertEqual(shelter.trace_gaps[0],
                         dict(kind='gap', reason='sample_spacing',
                              last_observed_sim=0., resumed_sim=3.))
        shelter.observe({}, 3.5)
        shelter.observe(snapshot, 4.)
        self.assertEqual(len(shelter.trace_gaps), 2)
        self.assertEqual(shelter.trace_gaps[1],
                         dict(kind='gap', reason='missing_native_snapshot',
                              last_observed_sim=3., resumed_sim=None))
        self.assertEqual(shelter.trace_gap_dropped, 0)


if __name__ == '__main__':
    unittest.main()
