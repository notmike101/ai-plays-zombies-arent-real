import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

import torch
from torch import nn

from observatory import metadata, weight_tile
from observer import Observer


class Policy(nn.Module):
    def __init__(self, width=8):
        super().__init__()
        self.gru = nn.GRU(3, width, batch_first=True)
        self.hu = nn.Linear(width, 4)
        self.hc = nn.Linear(width, 2)
        self.val = nn.Linear(width, 1)

    def forward(self, x, h=None):
        y, h = self.gru(x, h)
        return self.hu(y), self.hc(y), self.val(y), h


class ObserverTests(unittest.TestCase):
    def test_campaign_combined_logits_have_no_fictitious_direct_edges(self):
        class Campaign(Policy):
            campaign_team_id='a'
            campaign_forecast_id='cnn'
            def forward(self,x,h=None):
                u,c,v,h=super().forward(x,h)
                return u+17,c-11,v,h
        net=Campaign().eval()
        revisions=[]
        for identity in ('a','b'):
            net.campaign_team_id=identity
            obs=Observer(net,321,directory=self.tmp.name)
            try:
                with torch.no_grad():u,c,_,_=net(torch.ones(1,1,3))
                frame=obs.snapshot()
                self.assertEqual(frame['values']['hu'],u.flatten().tolist())
                self.assertEqual(frame['values']['hc'],c.flatten().tolist())
                self.assertIn('CNN',frame['graph']['architecture'])
                self.assertFalse(any(e['to'].startswith(('hu:','hc:')) for e in frame['graph']['edges']))
                revisions.append(frame['model_revision'])
            finally:obs.close()
        self.assertNotEqual(*revisions)
    def setUp(self):
        (Path(__file__).parent / 'runtime').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent / 'runtime')
        self.net = Policy().eval()
        self.observer = Observer(self.net, 123, 'round-test', directory=self.tmp.name)

    def tearDown(self):
        self.observer.close()
        self.tmp.cleanup()

    def test_exact_activations_and_no_rng_or_output_change(self):
        x = torch.ones(1, 1, 3)
        state = torch.random.get_rng_state().clone()
        with torch.no_grad():
            u, c, v, h = self.net(x)
        frame = self.observer.snapshot(probabilities={'hu': u.softmax(-1)}, selected={'hu': 2})
        self.assertTrue(torch.equal(state, torch.random.get_rng_state()))
        self.assertEqual(frame['values']['input'], [1, 1, 1])
        self.assertEqual(frame['values']['gru'], h.flatten().tolist())
        self.assertEqual(frame['values']['hu'], u.flatten().tolist())
        self.assertEqual(frame['values']['memory'], [0] * 8)
        self.assertEqual(frame['selected'], {'hu': 2})
        # float32 softmax sums land within ~6e-8 of 1; 7 places is unsatisfiable
        self.assertAlmostEqual(sum(frame['probabilities']['hu']), 1, places=5)
        self.observer.close()
        with torch.no_grad():
            plain = self.net(x)
        for a, b in zip((u, c, v, h), plain):
            self.assertTrue(torch.equal(a, b))

    def test_recurrent_input_and_weight_refresh(self):
        with torch.no_grad():
            *_, h = self.net(torch.ones(1, 1, 3))
            self.net(torch.zeros(1, 1, 3), h)
        a = self.observer.snapshot()
        self.assertEqual(a['values']['memory'], h.flatten().tolist())
        with torch.no_grad():
            self.net.hu.weight.add_(1)
        b = self.observer.snapshot()
        self.assertNotEqual(a['model_revision'], b['model_revision'])
        self.assertNotEqual(a['graph']['edges'], b['graph']['edges'])

    def test_training_forward_does_not_capture_or_change_gradients(self):
        x = torch.ones(1, 1, 3, requires_grad=True)
        self.net(x)[0].sum().backward()
        self.assertIsNone(self.observer.snapshot())
        self.assertIsNotNone(x.grad)

    def test_atomic_publish_and_cleanup(self):
        with torch.no_grad():
            self.net(torch.ones(1, 1, 3))
        self.assertTrue(self.observer.publish(selected={'hu': 1}, phase='planning'))
        deadline = time.monotonic() + 3
        files = []
        while time.monotonic() < deadline:
            files = list(Path(self.tmp.name).glob('*.json'))
            if files:
                break
            time.sleep(.02)
        self.assertEqual(len(files), 1)
        data = json.loads(files[0].read_text())
        self.assertEqual(data['game_pid'], 123)
        self.assertEqual(data['phase'], 'planning')
        self.assertEqual(data['decision'], 1)
        self.assertIsNone(data['decision_interval_ms'])
        self.assertEqual(self.observer._queue.maxsize, 1)
        directory = Path(self.tmp.name)
        for key, expected in {
            'input_reset': self.net.gru.weight_ih_l0[:8],
            'input_update': self.net.gru.weight_ih_l0[8:16],
            'memory_candidate': self.net.gru.weight_hh_l0[16:24],
            'hu.weight': self.net.hu.weight,
        }.items():
            with self.subTest(key=key):
                tile = weight_tile(directory, data, metadata(data), key, 0, 0)
                self.assertEqual(tile['values'], expected.detach().tolist())
        self.observer.close()
        self.assertFalse(self.net.gru._forward_hooks)
        self.assertFalse(list(directory.glob('*.weights')))

    def test_feed_attaches_to_published_standby_after_primary_closes(self):
        from server import Feed

        net = Policy().eval()
        standby = Observer(net, 77, directory=self.tmp.name, interval=1.)
        feed = Feed(self.tmp.name)

        def wait_for_stream(pid):
            for _ in range(125):
                state = feed.state()
                if state['frame'] and state['frame']['game_pid'] == pid:
                    self.assertEqual(state['status'], 'live')
                    return
                time.sleep(.025)
            self.fail(f'Feed did not attach to game {pid}')

        try:
            with torch.no_grad():
                self.net(torch.ones(1, 1, 3))
                self.assertTrue(self.observer.publish())
                wait_for_stream(123)
                net(torch.ones(1, 1, 3) * 2)
                self.assertTrue(standby.publish())
                self.observer.close()
            wait_for_stream(77)
        finally:
            standby.close()

    def test_standby_observer_only_copies_vectors_when_due(self):
        net = Policy().eval()
        standby = Observer(net, 77, directory=self.tmp.name, interval=1.)
        try:
            for tick, value, due in [(10., 1., True), (10.25, 2., False), (11., 3., True)]:
                with torch.no_grad(), patch('observer.time.monotonic', return_value=tick):
                    net(torch.full((1, 1, 3), value))
                    self.assertEqual(standby.values.get('input'), [value] * 3 if due else None)
                    self.assertEqual(standby.publish(), due)
            self.assertEqual(standby.decision, 3)
        finally:
            standby.close()

    def test_decision_counter_includes_throttled_decisions(self):
        with torch.no_grad():
            self.net(torch.ones(1, 1, 3))
        with patch('observer.time.monotonic', return_value=10.):
            self.assertTrue(self.observer.publish())
        with patch('observer.time.monotonic', return_value=10.01):
            self.assertFalse(self.observer.publish())
        with patch('observer.time.monotonic', return_value=10.25):
            self.assertTrue(self.observer.publish())
        self.assertEqual(self.observer.decision, 3)
        self.assertEqual(self.observer.sequence, 2)

    def test_write_failure_does_not_break_inference(self):
        self.observer.directory = Path(self.tmp.name) / 'missing' / 'child'
        with torch.no_grad():
            self.net(torch.ones(1, 1, 3))
        self.observer.publish()
        time.sleep(.1)
        with torch.no_grad():
            self.assertEqual(self.net(torch.ones(1, 1, 3))[0].shape[-1], 4)

    def test_unsupported_model_reports_error(self):
        other = Observer(nn.Linear(3, 4), 123, 'unsupported', directory=self.tmp.name)
        try:
            frame = other.snapshot()
            self.assertIn('unsupported', frame['error'].lower())
            self.assertNotIn('graph', frame)
            self.assertTrue(other.publish())
        finally:
            other.close()

    def test_snapshot_does_not_retain_masked_output_alias(self):
        with torch.no_grad():
            u, *_ = self.net(torch.ones(1, 1, 3))
            expected = u.flatten().tolist()
            u.fill_(-1e9)
        self.assertEqual(self.observer.snapshot()['values']['hu'], expected)

    def test_changed_dimensions_rebuild_graph(self):
        net = Policy(width=12).eval()
        other = Observer(net, 124, 'new-model', directory=self.tmp.name)
        try:
            with torch.no_grad():
                net(torch.ones(1, 1, 3))
            graph = other.snapshot()['graph']
            self.assertEqual(next(l['size'] for l in graph['layers'] if l['id'] == 'gru'), 12)
        finally:
            other.close()

    def test_thread_start_failure_is_safe_to_close(self):
        with patch('observer.threading.Thread.start', side_effect=RuntimeError('threads unavailable')):
            other = Observer(self.net, 124, 'failure', directory=self.tmp.name)
        self.assertFalse(other.publish())
        other.close()


if __name__ == '__main__':
    (Path(__file__).parent / 'runtime').mkdir(exist_ok=True)
    unittest.main()
