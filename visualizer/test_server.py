import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
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
