import unittest
import numpy as np

from shadow_transitions import TransitionCapture, combat_context, native_launch_matches
from shadow_benchmark import chains, commands
from test_policy_mechanics import fixture


class ShadowTransitionTests(unittest.TestCase):
    def test_launch_join_uses_action_interval_and_normalized_position(self):
        event = {'sim': 30.63, 'center': {'uv': [.55, .28]}}
        transition = {'from': 0, 'receipt': {'sim': 31.1, 'pixels': [[1056., 336.]]}}
        states = [{'sim': 29.967}]
        viewport = [1920, 1200]
        self.assertTrue(native_launch_matches(event, transition, states, viewport))
        self.assertFalse(native_launch_matches(dict(event, sim=29.5), transition, states, viewport))
        self.assertFalse(native_launch_matches(dict(event, center={'uv': [.45, .28]}),
                                               transition, states, viewport))

    def test_context_excludes_offscreen_units_and_keeps_conversion_separate(self):
        native = fixture()
        native['units']['pos'] = np.array([[0., 0.], [500., 0.]])
        native['units']['converting'][0] = 1
        native['zones'] = [np.array([[0., 0.], [1., 0.], [0., 1.]])]
        context = combat_context(native, 100, 100)
        self.assertEqual(sum(context['conversion']), 1)
        self.assertEqual(sum(context['defenders'][5]), 1)
        self.assertEqual(len(context['terrain']), 48)
        self.assertEqual(sum(context['wall_midpoints']), 0)
        self.assertEqual(context['shelter_polygons'], [native['zones'][0].tolist()])
        native['zones'] = [np.zeros((257, 2))]
        self.assertIsNone(combat_context(native, 100, 100)['shelter_polygons'])

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
