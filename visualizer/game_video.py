"""Share one bounded hardware-encoded game stream across its viewers."""
from pathlib import Path
import struct
import subprocess
import sys
import threading

MAX_BOX = 512 * 1024


def chunks(source):
    init = b''
    fragment = None
    while prefix := source.read(8):
        if len(prefix) != 8:
            raise ValueError('Incomplete MP4 box header')
        size, kind = struct.unpack('!I4s', prefix)
        if not 8 <= size <= MAX_BOX:
            raise ValueError('MP4 box outside size limit')
        payload = source.read(size - 8)
        if len(payload) != size - 8:
            raise ValueError('Incomplete MP4 box')
        data = prefix + payload
        if kind == b'ftyp':
            init = data
        elif kind == b'moov':
            yield init + data
        elif kind == b'moof':
            fragment = data
        elif kind == b'mdat' and fragment is not None:
            yield fragment + data
            fragment = None


class VideoSession:
    def __init__(self, key, timestamp):
        self.key = key
        self.clients = 0
        self.ready = threading.Condition()
        self.init = b''
        self.latest = b''
        self.sequence = 0
        self.finished = False
        helper = Path(__file__).with_name('screenshot.py')
        self.process = subprocess.Popen(
            [sys.executable, '-B', str(helper), str(key[1]), str(timestamp), '--video'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0),
        )
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        try:
            with self.process.stdout as source:
                items = chunks(source)
                init = next(items, b'')
                for data in items:
                    with self.ready:
                        self.init = init
                        self.latest = data
                        self.sequence += 1
                        self.ready.notify_all()
        except (OSError, ValueError):
            pass
        finally:
            self.stop()

    def stop(self):
        with self.ready:
            if self.finished:
                return
            self.finished = True
            self.ready.notify_all()
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass

    def next(self, sequence, timeout):
        with self.ready:
            self.ready.wait_for(lambda: self.finished or self.sequence > sequence, timeout)
            if not self.finished and self.sequence > sequence:
                return self.sequence, self.latest
        return None


class GameVideo:
    def __init__(self):
        self.lock = threading.Lock()
        self.session = None

    def open(self, stream, pid, timestamp):
        key = stream, pid
        with self.lock:
            if self.session is None or self.session.finished:
                self.session = VideoSession(key, timestamp)
            if self.session.key != key or self.session.clients >= 4:
                return None
            self.session.clients += 1
            return self.session

    def release(self, session):
        with self.lock:
            session.clients -= 1
            if not session.clients:
                session.stop()

    def close(self):
        with self.lock:
            if self.session:
                self.session.stop()
