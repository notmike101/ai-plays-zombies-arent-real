import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from server import Feed, make_server


def frame(stream, stamp, preview=False):
    return dict(schema=1, stream=stream, timestamp=stamp, worker_pid=1, game_pid=2,
                preview=preview, model_revision='abc', graph={'layers': [], 'edges': []},
                values={}, probabilities={}, selected={})


class FeedTests(unittest.TestCase):
    def setUp(self):
        (Path(__file__).parent / 'runtime').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent / 'runtime')
        self.root = Path(self.tmp.name)
        self.feed = Feed(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        (self.root / (data['stream'] + '.json')).write_text(json.dumps(data))

    def test_wait_sticky_failover_and_stale(self):
        self.assertEqual(self.feed.state(now=100)['status'], 'waiting')
        self.write(frame('one', 100))
        self.assertEqual(self.feed.state(now=101)['frame']['stream'], 'one')
        self.write(frame('two', 102))
        self.assertEqual(self.feed.state(now=103)['frame']['stream'], 'one')
        self.write(frame('two', 119))
        self.assertEqual(self.feed.state(now=120)['frame']['stream'], 'two')
        self.assertEqual(self.feed.state(now=140)['status'], 'stale')

    def test_preview_is_never_live_and_missing_selection_does_not_switch(self):
        self.write(frame('preview', 100, True))
        self.assertEqual(self.feed.state(now=101)['status'], 'waiting')
        self.assertEqual(self.feed.state(now=101, preview=True)['status'], 'preview')
        self.assertEqual(self.feed.state(now=101, stream='missing')['status'], 'waiting')

    def test_malformed_oversized_and_nonfinite_data_are_ignored(self):
        (self.root / 'bad.json').write_text('{')
        (self.root / 'big.json').write_text(' ' * (2 * 1024 * 1024 + 1))
        self.write(frame('nan', float('nan')))
        self.assertEqual(self.feed.state(now=100)['status'], 'waiting')

    def test_revision_omits_only_unchanged_graph(self):
        self.write(frame('one', 100))
        result = self.feed.state(now=101, revision='abc')
        self.assertNotIn('graph', result['frame'])
        self.assertIn('graph', self.feed.state(now=101)['frame'])

    def test_same_size_timestamp_collision_does_not_hide_new_sample(self):
        self.write(frame('one', 100))
        self.feed.state(now=101)
        path = self.root / 'one.json'
        stamp = path.stat().st_mtime_ns
        self.write(frame('one', 120))
        os.utime(path, ns=(stamp, stamp))
        self.assertEqual(self.feed.state(now=121)['status'], 'live')

    def test_old_crash_files_cannot_crowd_out_new_stream(self):
        for i in range(130):
            data = frame(f'z-old-{i:03}', 0)
            self.write(data)
            os.utime(self.root / (data['stream'] + '.json'), (1, 1))
        self.write(frame('a-new', 200))
        self.assertEqual(self.feed.state(now=201)['frame']['stream'], 'a-new')

    def test_shared_reads_and_bounded_deduplicated_history(self):
        data = frame('one', 100)
        data.update(sequence=1, phase='planning', selected={'hu': 0},
                    probabilities={'hu': [1.0]})
        data['graph']['layers'] = [{'id': 'hu', 'labels': ['wait']}]
        self.write(data)
        with patch.object(self.feed, '_read', wraps=self.feed._read) as reads:
            first = self.feed.state(now=100)
            self.feed.state(now=100.1)
            self.assertEqual(reads.call_count, 1)
        self.assertEqual(first['history'][0]['choices'][0]['label'], 'wait')
        self.assertEqual(first['history'][0]['choices'][0]['probability'], 1.0)
        self.assertEqual(len(self.feed.state(now=101)['history']), 1)
        for i in range(2, 212):
            data.update(sequence=i, timestamp=100+i)
            self.write(data)
            result = self.feed.state(now=100+i)
        self.assertLessEqual(len(self.feed.history), 200)
        self.assertEqual(len(result['history']), 50)
        self.assertEqual(result['history'][-1]['sequence'], 211)
        data.update(sequence=215, timestamp=400)
        self.write(data)
        self.assertEqual(self.feed.state(now=400)['history'][-1]['skipped'], 3)

    def test_history_follows_selection_and_preview_and_survives_file_removal(self):
        for name, preview in [('real', False), ('preview', True)]:
            data = frame(name, 100, preview)
            data['sequence'] = 1
            self.write(data)
        self.assertEqual([e['stream'] for e in self.feed.state(now=100)['history']], ['real'])
        self.assertEqual([e['stream'] for e in self.feed.state(now=101, preview=True)['history']], ['preview'])
        (self.root / 'real.json').unlink()
        result = self.feed.state(now=102, stream='real')
        self.assertEqual(result['status'], 'waiting')
        self.assertEqual([e['stream'] for e in result['history']], ['real'])
        self.assertEqual(self.feed.state(now=103, stream='preview')['history'], [])

    def test_sse_reconnect_sends_graph_and_history_and_observes_updates(self):
        data = frame('one', time.time())
        data['sequence'] = 1
        self.write(data)
        server = make_server('127.0.0.1', 0, self.feed)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/api/events'

        def receive(response):
            while True:
                line = response.readline()
                if not line:
                    self.fail('SSE ended before a state event')
                if line.startswith(b'data: '):
                    return json.loads(line[6:])

        try:
            with urlopen(url, timeout=4) as response:
                self.assertEqual(response.headers.get_content_type(), 'text/event-stream')
                first = receive(response)
                self.assertIn('graph', first['frame'])
                self.assertEqual(first['history'][0]['sequence'], 1)
                data.update(timestamp=time.time(), sequence=2)
                self.write(data)
                for _ in range(5):
                    changed = receive(response)
                    if changed['frame']['sequence'] == 2:
                        break
                self.assertEqual(changed['frame']['sequence'], 2)
                self.assertNotIn('graph', changed['frame'])
            with urlopen(url, timeout=4) as response:
                resumed = receive(response)
                self.assertIn('graph', resumed['frame'])
                self.assertEqual([e['sequence'] for e in resumed['history']], [1, 2])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertFalse(server.sampler.is_alive())

    def test_sampler_captures_without_viewers_and_survives_bad_summary(self):
        data = frame('bad', time.time())
        data.update(sequence=1, graph={'layers': None})
        self.write(data)
        server = make_server('127.0.0.1', 0, self.feed)
        try:
            good = frame('good', time.time())
            good['sequence'] = 1
            self.write(good)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                with self.feed.lock:
                    captured = [e['stream'] for e in self.feed.history]
                if 'good' in captured:
                    break
                time.sleep(.02)
            self.assertIn('good', captured)
            self.assertTrue(server.sampler.is_alive())
        finally:
            server.server_close()

    def test_stream_capacity_is_bounded_and_released(self):
        server = make_server('127.0.0.1', 0, self.feed)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/api/events'
        try:
            acquired = 0
            while server.stream_slots.acquire(blocking=False):
                acquired += 1
            self.assertLessEqual(acquired, 16)
            with self.assertRaises(HTTPError) as error:
                urlopen(url, timeout=3)
            self.assertEqual(error.exception.code, 503)
            error.exception.close()
            server.stream_slots.release()
            with urlopen(url, timeout=3) as response:
                self.assertEqual(response.headers.get_content_type(), 'text/event-stream')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_allowlist(self):
        server = make_server('127.0.0.1', 0, self.feed)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/api/state') as response:
                self.assertEqual(json.load(response)['status'], 'waiting')
            for path in ['/observer.py', '/../scripts/nn_play2.py', '/runtime/one.json', '/%2e%2e/AGENTS.md']:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    (Path(__file__).parent / 'runtime').mkdir(exist_ok=True)
    unittest.main()
