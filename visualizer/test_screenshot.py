import socket
import struct
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Feed as RuntimeFeed, make_server
from screenshot import Screenshots


class Feed:
    def state(self, *, stream=None, **kwargs):
        if stream == 'live':
            return {'status': 'live', 'frame': {'game_pid': 123, 'timestamp': 45.}}
        return {'status': 'waiting', 'frame': None}


class Inventory:
    def snapshot(self):
        return ({'id': 'game:456:1000', 'game_pid': 456, 'copy': 'inst17', 'observed_at': 45.},)

    def run(self, stopped):
        stopped.wait()

    def observed_pids(self):
        return {game['game_pid'] for game in self.snapshot()}


class ScreenshotTests(unittest.TestCase):
    def test_worker_diagram_tracks_selection_timeline_and_exit(self):
        import json
        from pathlib import Path
        import tempfile

        from test_server import frame

        class Games(Inventory):
            records = ()

            def snapshot(self):
                return self.records

        inventory = Games()
        a = {'id': 'game:111:1000', 'game_pid': 111, 'copy': 'inst1'}
        b = {'id': 'game:222:1000', 'game_pid': 222, 'copy': 'inst2'}
        inventory.records = (a, b)

        with tempfile.TemporaryDirectory() as directory:
            with make_server('127.0.0.1', 0, RuntimeFeed(directory), inventory=inventory) as server:
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                address = f'http://127.0.0.1:{server.server_port}/api/events?view=observatory&workers=1'

                def wait_state(response, check):
                    for raw in response:
                        if raw.startswith(b'data: '):
                            state = json.loads(raw[6:])
                            if check(state):
                                return state
                    self.fail('No matching worker diagram state')

                try:
                    with urlopen(address, timeout=3) as response:
                        initial = wait_state(response, lambda state: 'selected_worker' in state)
                    self.assertEqual(initial['selected_worker'], a['id'])
                    self.assertEqual([node['id'] for node in initial['workers']], [a['id'], b['id']])
                    with urlopen(address + '&game=' + b['id'], timeout=3) as response:
                        selected = wait_state(response, lambda state: 'selected_worker' in state)
                        self.assertEqual(selected['selected_worker'], b['id'])
                        self.assertIsNone(selected['sample'])
                        live = dict(frame('worker-b', time.time()), game_pid=222, sequence=1)
                        path = Path(directory) / 'worker-b.json'
                        path.write_text(json.dumps(live), encoding='utf-8')
                        observed = wait_state(response, lambda state: state['status'] == 'live')
                        self.assertEqual(observed['game_view']['id'], b['id'])
                        self.assertEqual(observed['sample']['game_pid'], 222)
                        with urlopen(address, timeout=3) as automatic:
                            follow = wait_state(automatic, lambda state: 'selected_worker' in state)
                            self.assertEqual(follow['selected_worker'], b['id'])
                            self.assertEqual(follow['status'], 'live')
                        with urlopen(address + '&game=' + a['id'], timeout=3) as pinned:
                            inspect = wait_state(pinned, lambda state: 'selected_worker' in state)
                            self.assertEqual(inspect['selected_worker'], a['id'])
                            self.assertIsNone(inspect['sample'])
                        inventory.records = (a,)
                        removed = wait_state(response, lambda state: state.get('selected_worker') == a['id'])
                        self.assertEqual([node['id'] for node in removed['workers']], [a['id']])
                        path.unlink()
                        inventory.records = ()
                        wait_state(response, lambda state: state.get('selected_worker') is None)
                        inventory.records = (b,)
                        wait_state(response, lambda state: state.get('selected_worker') == b['id'])
                finally:
                    server.shutdown()
                    worker.join(timeout=2)

    def test_sse_advertises_fallback_only_for_automatic_live_source(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            with make_server('127.0.0.1', 0, RuntimeFeed(directory), inventory=Inventory()) as server:
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                address = f'http://127.0.0.1:{server.server_port}/api/events?view=observatory'
                try:
                    for suffix in ('', '&stream=manual', '&preview=1'):
                        with urlopen(address + suffix, timeout=3) as response:
                            state = next(json.loads(line[6:]) for line in response if line.startswith(b'data: '))
                        self.assertEqual(state['status'], 'waiting')
                        self.assertIsNone(state['sample'])
                        self.assertEqual(state['game_view'], None if suffix else
                                         {'id': 'game:456:1000', 'game_pid': 456, 'copy': 'inst17'})
                finally:
                    server.shutdown()
                    worker.join(timeout=2)

    def test_crops_client_using_bounds_that_match_the_capture(self):
        from screenshot import client_crop

        client = (-960, 32, 960, 1232)
        dwm = (-968, 0, 968, 1256)
        window = (-975, -7, 975, 1263)
        self.assertEqual(client_crop((1936, 1256), client, (dwm, window)), (8, 32, 1928, 1232))
        self.assertEqual(client_crop((1950, 1270), client, (dwm, window)), (15, 39, 1935, 1239))
        self.assertEqual(client_crop((1920, 1200), client, (client,)), (0, 0, 1920, 1200))
        self.assertIsNone(client_crop((1600, 1000), client, (dwm, window)))

    def test_capture_is_bounded_and_cached_by_stream_and_game(self):
        cache = Screenshots()
        started, release = threading.Event(), threading.Event()
        jpeg = b'\xff\xd8jpeg\xff\xd9'

        def capture(*args, **kwargs):
            started.set()
            release.wait(2)
            return SimpleNamespace(stdout=struct.pack('!d', time.time()) + jpeg)

        with patch('screenshot.subprocess.run', side_effect=capture) as run:
            self.assertIsNone(cache('first', 123, 45.))
            self.assertTrue(started.wait(2))
            self.assertIsNone(cache('second', 456, 45.))
            self.assertEqual(run.call_count, 1)
            release.set()
            deadline = time.monotonic() + 1
            while cache.pending and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(cache('first', 123, 45.)[1], jpeg)
            self.assertIsNone(cache('second', 123, 45.))
            self.assertIsNone(cache('first', 456, 45.))
            self.assertEqual(run.call_count, 1)

    def test_serves_only_the_selected_live_game_and_public_opt_in(self):
        for share in (False, True):
            with self.subTest(share=share):
                requests = []

                def screenshot(stream, pid, stamp):
                    requests.append((stream, pid, stamp))
                    return time.time(), b'\xff\xd8jpeg\xff\xd9'

                with make_server('127.0.0.1', 0, Feed(), learning_host='observatory.example',
                                 share_screenshots=share, screenshot=screenshot, inventory=Inventory()) as server:
                    worker = threading.Thread(target=server.serve_forever, daemon=True)
                    worker.start()
                    url = f'http://127.0.0.1:{server.server_port}/api/screenshot'
                    lan = {'Host': f'{socket.gethostname()}:{server.server_port}'}
                    public = {'Host': 'observatory.example'}
                    try:
                        for headers in ([{}, lan, public] if share else [{}, lan]):
                            with urlopen(Request(url + '?stream=live', headers=headers), timeout=3) as response:
                                self.assertEqual(response.headers.get_content_type(), 'image/jpeg')
                                self.assertIn('X-Captured-At', response.headers)
                                self.assertEqual(response.read(), b'\xff\xd8jpeg\xff\xd9')
                        denied = [('?stream=expired', {}, 404), ('?stream=live&preview=1', {}, 404),
                                  ('?stream=live', {'Sec-Fetch-Site': 'cross-site'}, 403),
                                  ('?stream=live', {'Host': 'different.example'}, 403)]
                        if not share:
                            denied.append(('?stream=live', public, 403))
                        with urlopen(url + '?stream=game:456:1000', timeout=3) as response:
                            self.assertEqual(response.read(), b'\xff\xd8jpeg\xff\xd9')
                        denied.append(('?stream=game:456:999', {}, 404))
                        for query, headers, code in denied:
                            with self.assertRaises(HTTPError) as error:
                                urlopen(Request(url + query, headers=headers), timeout=3)
                            self.assertEqual(error.exception.code, code)
                            error.exception.close()
                            with self.assertRaises(HTTPError) as error:
                                urlopen(Request(url.replace('/screenshot', '/game-video') + query, headers=headers), timeout=3)
                            self.assertEqual(error.exception.code, code)
                            error.exception.close()
                        self.assertEqual(requests, [('live', 123, 45.)] * (3 if share else 2)
                                         + [('game:456:1000', 456, 45.)])
                    finally:
                        server.shutdown()
                        worker.join(timeout=2)
