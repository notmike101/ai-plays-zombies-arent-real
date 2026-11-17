"""Read-only, dependency-free HTTP service for the local policy observer."""
import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
FRESH_SECONDS = 15
SAMPLE_SECONDS = .2
PUBLIC = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
          '/app.js': ('app.js', 'text/javascript'), '/graph.js': ('graph.js', 'text/javascript')}


class Feed:
    def __init__(self, directory=ROOT / 'runtime'):
        self.directory = Path(directory)
        self.lock = threading.Lock()
        self.active = {False: None, True: None}
        self.frames = []
        self.sampled_at = float('-inf')
        self.history = deque(maxlen=200)
        self.seen = {}
        self.decoded = {}

    def _refresh(self, now):
        if 0 <= now - self.sampled_at < SAMPLE_SECONDS:
            return
        self.frames = self._read(now)
        self.sampled_at = now
        present = set()
        for frame in sorted(self.frames, key=lambda f: f['timestamp']):
            stream = frame['stream']
            present.add(stream)
            sequence = frame.get('sequence')
            if 'error' in frame or not isinstance(sequence, int) or sequence < 0:
                continue
            previous = self.seen.get(stream)
            if previous is not None and sequence <= previous:
                continue
            self.seen[stream] = sequence
            try:
                layers = {layer['id']: layer for layer in frame['graph']['layers']}
                choices = []
                for head, index in list(frame['selected'].items())[:16]:
                    labels = layers.get(head, {}).get('labels', [])
                    probabilities = frame['probabilities'].get(head, [])
                    if not isinstance(index, int) or index < 0:
                        continue
                    choices.append({'head': str(head)[:64], 'index': index,
                                    'label': str(labels[index] if index < len(labels) else f'{head} {index}')[:256],
                                    'probability': probabilities[index] if index < len(probabilities) else None})
                self.history.append({
                    'stream': stream, 'sequence': sequence, 'timestamp': frame['timestamp'],
                    'preview': bool(frame.get('preview')), 'worker_pid': frame.get('worker_pid'),
                    'game_pid': frame.get('game_pid'), 'episode': str(frame.get('episode', ''))[:128],
                    'phase': str(frame.get('phase', 'unknown'))[:64], 'choices': choices,
                    'skipped': max(0, sequence - previous - 1) if previous is not None else 0})
            except (KeyError, TypeError, IndexError, AttributeError):
                # A malformed optional summary must not stop other workers' telemetry.
                continue
        self.seen = {key: value for key, value in self.seen.items() if key in present}

    def _read(self, now):
        frames = []
        decoded = {}
        paths = []
        for path in self.directory.glob('*.json'):
            try:
                paths.append((path.stat().st_mtime_ns, path))
            except OSError:
                continue
        # Abandoned crash files are bounded on read; normal observers remove their own files.
        paths.sort(key=lambda entry: entry[0], reverse=True)
        for _, path in paths[:32]:
            try:
                stat = path.stat()
                if stat.st_size > 8 * 1024 * 1024:
                    continue
                raw = path.read_bytes()
                cached = self.decoded.get(path)
                if cached is not None and cached[0] == raw:
                    data = cached[1]
                else:
                    data = json.loads(raw,
                                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                if (not isinstance(data, dict) or data.get('schema') != 1 or
                        not isinstance(data.get('stream'), str) or len(data['stream']) > 128 or
                        not isinstance(data.get('timestamp'), (int, float)) or
                        not math.isfinite(data['timestamp'])):
                    continue
                if 'error' not in data and not all(isinstance(data.get(key), dict)
                                                   for key in ('graph', 'values', 'probabilities', 'selected')):
                    continue
                if -5 <= now - data['timestamp'] <= 120:
                    frames.append(data)
                    decoded[path] = (raw, data)
            except (OSError, ValueError, TypeError):
                continue
        self.decoded = decoded
        return frames

    def state(self, *, now=None, preview=False, stream=None, revision=None):
        now = time.time() if now is None else now
        with self.lock:
            self._refresh(now)
            frames = [f for f in self.frames if bool(f.get('preview')) == preview]
            frames.sort(key=lambda f: (f['timestamp'], f['stream']))
            available = {f['stream']: f for f in frames}
            fresh = [f for f in frames if now - f['timestamp'] <= FRESH_SECONDS]
            chosen = available.get(stream or self.active[preview])
            if not stream and (chosen is None or now - chosen['timestamp'] > FRESH_SECONDS):
                chosen = fresh[0] if fresh else chosen or (frames[-1] if frames else None)
                self.active[preview] = chosen['stream'] if chosen else None
            streams = [{'id': f['stream'], 'game_pid': f.get('game_pid'),
                        'worker_pid': f.get('worker_pid'), 'age': max(0, now - f['timestamp'])} for f in frames]
            history_stream = stream or (chosen['stream'] if chosen else self.active[preview])
            history = [entry for entry in self.history
                       if entry['stream'] == history_stream and entry['preview'] == preview][-50:]
            if chosen is None:
                return {'status': 'waiting', 'frame': None, 'streams': streams, 'history': history}
            age = max(0, now - chosen['timestamp'])
            status = 'stale' if age > FRESH_SECONDS else 'error' if 'error' in chosen else 'preview' if preview else 'live'
            frame = dict(chosen)
            if revision == frame.get('model_revision'):
                frame.pop('graph', None)
            return {'status': status, 'age': age, 'frame': frame, 'streams': streams, 'history': history}


def make_server(host, port, feed=None):
    feed = feed or Feed()
    class Handler(BaseHTTPRequestHandler):
        def events(self, args):
            self.connection.settimeout(3)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            revision, signature, history_signature = None, None, None
            sent_at = 0
            try:
                self.wfile.write(b'retry: 1000\n\n')
                self.wfile.flush()
                while not self.server.stopped.is_set():
                    with self.server.sample_ready:
                        generation = self.server.generation
                    result = feed.state(preview=args.get('preview') == ['1'],
                                        stream=args.get('stream', [None])[0], revision=revision)
                    frame = result['frame'] or {}
                    current = (result['status'], frame.get('stream'), frame.get('sequence'),
                               frame.get('timestamp'), frame.get('model_revision'),
                               tuple((s['id'], s['age'] > FRESH_SECONDS) for s in result['streams']))
                    clock = time.monotonic()
                    if current != signature or clock - sent_at >= 1:
                        # Idle updates keep sample age honest and detect broken connections.
                        history_key = tuple((e['stream'], e['sequence']) for e in result['history'])
                        if history_key == history_signature:
                            result['history'] = None
                        body = json.dumps(result, allow_nan=False, separators=(',', ':')).encode()
                        self.wfile.write(b'event: state\ndata: ' + body + b'\n\n')
                        self.wfile.flush()
                        revision = frame.get('model_revision')
                        signature, history_signature, sent_at = current, history_key, clock
                    with self.server.sample_ready:
                        self.server.sample_ready.wait_for(lambda:
                            self.server.generation != generation or self.server.stopped.is_set(), timeout=1)
            except (OSError, ValueError):
                pass

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/api/events':
                if not self.server.stream_slots.acquire(blocking=False):
                    self.send_error(503, 'Too many telemetry viewers; retry shortly')
                    return
                try:
                    self.events(parse_qs(url.query))
                except OSError:
                    pass
                finally:
                    self.server.stream_slots.release()
                return
            if url.path == '/api/state':
                args = parse_qs(url.query)
                result = feed.state(preview=args.get('preview') == ['1'],
                                    stream=args.get('stream', [None])[0],
                                    revision=args.get('revision', [None])[0])
                body, mime = json.dumps(result, allow_nan=False).encode(), 'application/json'
            elif url.path in PUBLIC:
                name, mime = PUBLIC[url.path]
                try:
                    body = (ROOT / 'public' / name).read_bytes()
                except FileNotFoundError:
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass

        def log_message(self, fmt, *args):
            if args and str(args[1]) != '200':
                super().log_message(fmt, *args)
    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def sample(self):
            while not self.stopped.is_set():
                feed.state()
                with self.sample_ready:
                    self.generation += 1
                    self.sample_ready.notify_all()
                self.stopped.wait(SAMPLE_SECONDS)

        def server_close(self):
            self.stopped.set()
            with self.sample_ready:
                self.sample_ready.notify_all()
            self.sampler.join(timeout=4)
            super().server_close()

    server = Server((host, port), Handler)
    server.stopped = threading.Event()
    server.sample_ready = threading.Condition()
    server.generation = 0
    server.stream_slots = threading.BoundedSemaphore(16)
    server.sampler = threading.Thread(target=server.sample, daemon=True, name='telemetry-sampler')
    server.sampler.start()
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--preview', action='store_true', help='Run a separate synthetic PyTorch preview process')
    args = parser.parse_args()
    server = make_server(args.host, args.port)
    print(f'Policy visualizer listening on {args.host}:{server.server_port}', flush=True)
    print(f'Open http://localhost:{server.server_port}', flush=True)
    preview_process = None
    try:
        if args.preview:
            preview_process = subprocess.Popen([sys.executable, '-B', str(ROOT / 'demo.py')],
                                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if preview_process is not None:
            preview_process.terminate()
            preview_process.wait(timeout=5)
