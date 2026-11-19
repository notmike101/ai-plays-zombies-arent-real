import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Feed, make_server
from test_server import frame


class ObservatoryTests(unittest.TestCase):
    def test_compact_sse_reconnect_restores_only_selected_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = Feed(root)

            def publish(stream, sequence, preview=False):
                data = frame(stream, time.time(), preview)
                data.update(sequence=sequence, model_revision='rev' + str(sequence))
                pending = root / 'frame.tmp'
                pending.write_text(json.dumps(data))
                pending.replace(root / (stream + '.json'))

            publish('one', 1)
            publish('two', 1)
            publish('preview', 1, True)
            with make_server('127.0.0.1', 0, feed, learning_directory=root,
                             learning_host='observatory.example') as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                address = f'http://127.0.0.1:{server.server_port}'
                url = address + '/api/events?view=observatory&stream=one'

                def read_event(connection):
                    for line in connection:
                        if line.startswith(b'data: '):
                            return json.loads(line[6:])
                    self.fail('SSE ended before a sample arrived')

                try:
                    with urlopen(url, timeout=4) as source:
                        first = read_event(source)
                        self.assertEqual(first['sample']['stream'], 'one')
                        self.assertTrue(first['history_reset'])
                        self.assertEqual({s['id'] for s in first['streams']}, {'one', 'two'})
                        self.assertNotIn('graph', first['sample'])
                        publish('one', 4)
                        new = read_event(source)
                        self.assertEqual(new['sample']['model_revision'], 'rev4')
                        self.assertIsNotNone(new['metadata'])
                        self.assertEqual([(row['sequence'], row['skipped']) for row in new['history']], [(4, 2)])
                    with urlopen(url, timeout=4) as source:
                        reconnected = read_event(source)
                        self.assertEqual([row['sequence'] for row in reconnected['history']], [1, 4])
                    learning = address + '/api/learning'
                    lan_headers = {'Host': f'{socket.gethostname()}:{server.server_port}',
                                   'Sec-Fetch-Site': 'same-origin'}
                    with urlopen(Request(learning, headers=lan_headers), timeout=4) as response:
                        self.assertEqual(json.load(response)['version'], 1)
                    public_headers = {'Host': 'observatory.example', 'Sec-Fetch-Site': 'same-origin'}
                    with urlopen(Request(learning, headers=public_headers), timeout=4) as response:
                        self.assertEqual(json.load(response)['version'], 1)
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(Request(learning, headers={'Host': 'remote.test'}), timeout=4)
                    self.assertEqual(denied.exception.code, 403)
                    denied.exception.close()
                    for path, headers in [
                        ('/api/learning', {**lan_headers, 'Sec-Fetch-Site': 'cross-site'}),
                        ('/api/learning', {**public_headers, 'Sec-Fetch-Site': 'cross-site'}),
                        ('/api/weights?stream=one&sequence=1', lan_headers),
                        ('/api/weights?stream=one&sequence=1', public_headers),
                    ]:
                        with self.assertRaises(HTTPError) as denied:
                            urlopen(Request(address + path, headers=headers), timeout=4)
                        self.assertEqual(denied.exception.code, 403)
                        denied.exception.close()
                    with self.assertRaises(HTTPError) as missing:
                        urlopen(address + '/api/decision?stream=one&sequence=2', timeout=4)
                    self.assertEqual(missing.exception.code, 404)
                    missing.exception.close()
                finally:
                    server.shutdown()
                    thread.join(timeout=2)

    def test_observer_wire_reuses_topology_only_when_exact_suffix_matches(self):
        from server import decode_frame
        first = b'{"sequence":1,"graph":{"layers":[]}}'
        second = b'{"sequence":2,"graph":{"layers":[]}}'
        third = b'{"sequence":3,"graph":{"layers":[1]}}'
        a = decode_frame(first)
        b = decode_frame(second, (first, a))
        c = decode_frame(third, (second, b))
        self.assertEqual(b['sequence'], 2)
        self.assertIs(a['graph'], b['graph'])
        self.assertEqual(c['graph']['layers'], [1])

    def test_replay_keeps_real_values_per_revision_and_excludes_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = Feed(root)
            for seq, tool in [(1, 'wait'), (4, 'garrison')]:
                data = frame('worker', 100 + seq)
                data.update(sequence=seq, model_revision=str(seq), episode='search/7/L2/a0',
                            values={'input': [seq], 'gru': [.125], 'memory': [-.25],
                                    'hu': [.25], 'hc': [float(i) for i in range(48)]},
                            probabilities={'hu': [1.], 'hc': [0.] * 47 + [1.]},
                            selected={'hu': 0, 'hc': 47})
                data['graph']['layers'] = [{'id': 'input', 'labels': ['feature']},
                                          {'id': 'hu', 'labels': [tool]}]
                (root / 'worker.json').write_text(json.dumps(data))
                feed.state(now=100 + seq)
            state = feed.observatory(now=104)
            self.assertEqual(state['version'], 1)
            self.assertEqual([row['skipped'] for row in state['history']], [0, 2])
            first = feed.decision('worker', 1, False)
            second = feed.decision('worker', 4, False)
            self.assertEqual(first['sample']['input'], [1])
            self.assertEqual(first['sample']['position_kind'], None)
            self.assertEqual(second['sample']['position_kind'], 'battlefield')
            self.assertEqual(second['sample']['location_probabilities'][47], 1.)
            self.assertEqual(second['sample']['hidden'], [.125])
            self.assertEqual(second['sample']['stage'], 2)
            self.assertEqual(first['metadata']['tools'], ['wait'])
            self.assertIsNone(feed.decision('worker', 1, True))
            self.assertIsNone(feed.decision('worker', 2, False))

    def test_weights_are_revision_scoped_and_sliced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = Feed(root)
            data = frame('1-0123456789ab', 101, True)
            data.update(sequence=1, model_revision='0123456789abcdef')
            data['graph']['matrices'] = {'input_reset': [2, 3, 0]}
            stream = data['stream']
            (root / f'{stream}.json').write_text(json.dumps(data))
            (root / f"{stream}-{data['model_revision']}.weights").write_bytes(
                struct.pack('<6f', 0, 1, 2, 3, 4, 5))
            feed.state(now=101, preview=True)
            self.assertEqual(feed.weights(stream, 1, True, 'input_reset', 0, 1)['values'],
                             [[1., 2.], [4., 5.]])
            self.assertIsNone(feed.weights(stream, 1, False, 'input_reset', 0, 1))
            self.assertIsNone(feed.weights(stream, 1, True, '../input_reset', 0, 0))

    def test_learning_uses_native_outcomes_and_keeps_trial_provenance(self):
        from learning import read_results
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / 'coverage-team-012345abcd'
            run.mkdir()
            (root / 'nn_hist4.jsonl').write_text(
                '{"kind":"episode","end":"timeout","observed_saved_frac":1,"saved_frac":1,"win":true}\n'
                '{"kind":"update","scenario":2,"loss":0.1}\n'
                '{partial')
            levels = [{'stage': 1, 'saved': .42, 'end': 'won', 'win': True, 'start_kind': 'fresh',
                       'actions': [[1, 0]], 'battle_actions': {'cast_sampled': 1, 'stock_decreased': 0}}]
            for file in ('trials.jsonl', 'holdout.jsonl'):
                (run / file).write_text(json.dumps({'levels': levels, 'team_id': 'a', 'arm': 'candidate'}) + '\n')
            (run / 'champion.json').write_text(json.dumps({
                'team_id': 'b', 'fresh_stages': [{'starts': 8, 'wins': 2, 'lower': .07, 'mean': .25}],
                'holdout_stage': 1}))
            results = read_results(root)
            self.assertIsNone(results['ppo'][0]['saved'])
            self.assertFalse(results['ppo'][0]['qualifies'])
            self.assertEqual(results['updates'][0]['scenario'], 2)
            campaign = results['campaigns'][0]
            self.assertEqual([row['cohort'] for row in campaign['outcomes']], ['Training trial', 'Held-out'])
            self.assertTrue(campaign['outcomes'][0]['qualifies'])
            self.assertNotIn('actions', campaign['outcomes'][0])
            self.assertEqual(campaign['incumbent']['holdout_stage'], 1)
