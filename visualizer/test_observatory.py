import json
from pathlib import Path
import struct
import tempfile
import unittest

from server import Feed
from test_server import frame


class ObservatoryTests(unittest.TestCase):
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
