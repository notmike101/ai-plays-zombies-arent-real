import io
import struct
import unittest
from unittest.mock import patch


def box(kind, content=b''):
    return struct.pack('!I4s', 8 + len(content), kind) + content


class GameVideoTests(unittest.TestCase):
    def test_shares_one_capture_and_releases_it_when_last_viewer_leaves(self):
        from game_video import GameVideo

        class Session:
            def __init__(self, key, _):
                self.key = key
                self.clients = 0
                self.finished = False

            def stop(self):
                self.finished = True

        video = GameVideo()
        with patch('game_video.VideoSession', side_effect=Session) as create:
            session = video.open('first', 1, 42)
            for _ in range(3):
                self.assertIs(video.open('first', 1, 42), session)
            self.assertIsNone(video.open('first', 1, 42))
            self.assertIsNone(video.open('second', 2, 42))
            create.assert_called_once()
            for _ in range(3):
                video.release(session)
                self.assertFalse(session.finished)
            video.release(session)
            self.assertTrue(session.finished)
            later = video.open('second', 2, 42)
            self.assertNotEqual(later.key, session.key)
            video.close()
            self.assertTrue(later.finished)

    def test_splits_mp4_into_initialization_and_complete_fragments(self):
        from game_video import chunks

        init = box(b'ftyp') + box(b'moov', b'avcC\x01\x42\xc0\x1f')
        first = box(b'moof', b'timing') + box(b'mdat', b'frame')
        second = box(b'moof') + box(b'mdat', b'other frame')
        self.assertEqual(list(chunks(io.BytesIO(init + first + second))), [init, first, second])

    def test_refuses_unbounded_and_truncated_boxes(self):
        from game_video import chunks

        for data in (struct.pack('!I4s', 2**30, b'mdat'), box(b'ftyp')[:-1]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(chunks(io.BytesIO(data)))
