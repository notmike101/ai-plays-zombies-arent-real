import unittest

from shadow_transitions import TransitionCapture
from shadow_benchmark import chains, commands


class ShadowTransitionTests(unittest.TestCase):
    def test_rollout_pairs_reject_an_intervening_camera_change(self):
        frames = [{'sim': t, 'camera': [0, y, 1]} for t, y in [(0, 0), (1, 2), (2, 0), (4, 0)]]
        self.assertEqual(list(chains({'frames': frames, 'casts': []}, 2)), [])

    def test_receipts_separate_inflight_from_future_casts(self):
        action = commands([{'sim': 1, 'cell': 7}, {'sim': 3, 'cell': 7},
                           {'sim': 5, 'cell': 7}], 2, 4)
        self.assertEqual(action.reshape(2, 48)[:, 7].tolist(), [1, 1])
        self.assertEqual(action.sum(), 2)

    def test_receipt_and_elapsed_time_bind_to_the_previous_decision(self):
        capture = TransitionCapture(limit=3)
        capture.observe({'sim': 1.0}, {'tool': 'missile'})
        capture.receipt('confirmed', spent=1)
        capture.observe({'sim': 1.5}, {'tool': 'wait'})
        capture.receipt('not_applicable')
        capture.observe({'sim': 2.0}, {'tool': 'missile'})
        capture.observe({'sim': 2.5}, {'tool': 'wait'})
        self.assertTrue(capture.truncated)
        self.assertEqual(len(capture.transitions), 2)
        first = capture.transitions[0]
        self.assertEqual((first['from'], first['to'], first['dt']), (0, 1, .5))
        self.assertEqual(first['receipt'], {'status': 'confirmed', 'spent': 1})

    def test_clock_reset_cannot_connect_two_outbreaks(self):
        capture = TransitionCapture()
        capture.observe({'sim': 2.0}, {})
        capture.observe({'sim': 0.0}, {})
        capture.observe({'sim': .5}, {})
        self.assertEqual([x['from'] for x in capture.transitions], [1])
