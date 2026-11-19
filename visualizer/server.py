"""Read-only, dependency-free HTTP service for the local policy observer."""
import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import tomllib
from urllib.parse import parse_qs, urlsplit
import observatory
from learning import read_results

ROOT = Path(__file__).resolve().parent
FRESH_SECONDS = 15
SAMPLE_SECONDS = .2
PUBLIC = {'/': ('observatory.html', 'text/html'), '/legacy': ('index.html', 'text/html'),
          '/style.css': ('style.css', 'text/css'), '/app.js': ('app.js', 'text/javascript'),
          '/graph.js': ('graph.js', 'text/javascript'), '/observatory.css': ('observatory.css', 'text/css'),
          '/observatory.js': ('observatory.js', 'text/javascript')}


def decode_frame(raw, cached=None):
    def decode(data):
        return json.loads(data, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if cached:
        previous, data = cached
        if previous == raw:
            return data
        # The observer appends its cached graph as the final field of compact JSON.
        # Verify the entire suffix before reusing the decoded labels and edges.
        old = previous.find(b',"graph":')
        new = raw.find(b',"graph":')
        if (old >= 0 and new >= 0 and 'graph' in data
                and memoryview(previous)[old:] == memoryview(raw)[new:]):
            try:
                return {**decode(raw[:new] + b'}'), 'graph': data['graph']}
            except (TypeError, ValueError):
                pass
    return decode(raw)


class Feed:
    def __init__(self, directory=ROOT / 'runtime'):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.active = {False: None, True: None}
        self.frames = []
        self.sampled_at = float('-inf')
        self.history = deque(maxlen=200)
        self.seen = {}
        self.decoded = {}
        self.samples = deque(maxlen=200)
        self.metadata = {}

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
                key = (stream, frame.get('model_revision'))
                meta = self.metadata.get(key)
                if meta is None:
                    meta = self.metadata[key] = observatory.metadata(frame)
                sample = observatory.decision(frame, meta, self.history[-1]['skipped'])
                self.samples.append((sample, meta))
            except (KeyError, TypeError, IndexError, AttributeError, ValueError):
                # A malformed optional summary must not stop other workers' telemetry.
                continue
        present.update(entry['stream'] for entry in self.history)
        self.seen = {key: value for key, value in self.seen.items() if key in present}
        kept = {(sample['stream'], sample['model_revision']) for sample, _ in self.samples}
        self.metadata = {key: value for key, value in self.metadata.items() if key in kept}

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
                if stat.st_size > 8 * 1024 * 1024 or stat.st_mtime < now - 125:
                    continue
                raw = path.read_bytes()
                cached = self.decoded.get(path)
                data = decode_frame(raw, cached)
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

    def observatory(self, *, now=None, preview=False, stream=None):
        with self.lock:
            state = self.state(now=now, preview=preview, stream=stream)
            frame = state.pop('frame') or {}
            current = stream or frame.get('stream')
            matching = []
            streams = {entry['id']: entry for entry in state['streams']}
            archived = {}
            for sample, meta in self.samples:
                if bool(sample['preview']) != preview:
                    continue
                key = sample['stream']
                if key not in streams:
                    archived[key] = {'id': key, 'game_pid': sample['game_pid'],
                                     'worker_pid': sample['worker_pid'], 'archived': True}
                if current == key:
                    matching.append((sample, meta))
            latest, meta = matching[-1] if matching else (None, None)
            state.update(version=1, stream=current, sample=latest, metadata=meta,
                         history=[observatory.summary(sample) for sample, _ in matching[-50:]],
                         error=frame.get('error'), streams=[*streams.values(), *list(archived.values())[-24:]])
            return state

    def decision(self, stream, sequence, preview):
        with self.lock:
            for sample, meta in reversed(self.samples):
                if (sample['stream'], sample['sequence'], bool(sample['preview'])) == (stream, sequence, preview):
                    return {'version': 1, 'sample': sample, 'metadata': meta}
        return None

    def weights(self, stream, sequence, preview, matrix, row, column):
        retained = self.decision(stream, sequence, preview)
        if retained:
            return observatory.weight_tile(self.directory, retained['sample'], retained['metadata'],
                                           matrix, row, column)
        return None


def make_server(host, port, feed=None, learning_directory=ROOT.parent / 'analysis', *, learning_host=''):
    feed = feed or Feed()
    hostname = socket.gethostname().lower()
    learning_host = learning_host.strip().lower()
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
            compact = args.get('view') == ['observatory']
            preview = args.get('preview') == ['1']
            stream = args.get('stream', [None])[0]
            sent_history = set()
            last_sample = None
            try:
                self.wfile.write(b'retry: 1000\n\n')
                self.wfile.flush()
                while not self.server.stopped.is_set():
                    with self.server.sample_ready:
                        generation = self.server.generation
                    result = (feed.observatory(preview=preview, stream=stream) if compact
                              else feed.state(preview=preview, stream=stream, revision=revision))
                    frame = (result.get('sample') if compact else result['frame']) or {}
                    current = (result['status'], frame.get('stream'), frame.get('sequence'),
                               frame.get('timestamp'), frame.get('model_revision'),
                               tuple((s['id'], s.get('age', 121) > FRESH_SECONDS)
                                     for s in result['streams']))
                    clock = time.monotonic()
                    if current != signature or clock - sent_at >= 1:
                        # Idle updates keep sample age honest and detect broken connections.
                        if compact:
                            sample_id = (result['stream'], frame.get('model_revision'), frame.get('sequence'))
                            reset = last_sample is None or last_sample[0] != sample_id[0]
                            if not reset and last_sample[:2] == sample_id[:2]:
                                result['metadata'] = None
                            if last_sample == sample_id:
                                result['sample'] = None
                            history_key = tuple(e['sequence'] for e in result['history'])
                            result['history'] = [e for e in result['history']
                                                 if reset or e['sequence'] not in sent_history]
                            result['history_reset'] = reset
                            result['oldest_sequence'] = history_key[0] if history_key else None
                            sent_history = set(history_key)
                            last_sample = sample_id
                        else:
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
            if url.path in ('/api/weights', '/api/learning'):
                hosts = ('localhost', '127.0.0.1')
                weights = url.path == '/api/weights'
                if not weights:
                    hosts += (hostname, self.connection.getsockname()[0])
                allowed = {*hosts, *(f'{name}:{self.server.server_port}' for name in hosts)}
                if not weights and learning_host:
                    allowed.update((learning_host, f'{learning_host}:443'))
                if ((weights and self.client_address[0] != '127.0.0.1') or
                        self.headers.get('Host', '').lower() not in allowed or
                        self.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site')):
                    self.send_error(403)
                    return
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
            if url.path == '/api/learning':
                run = parse_qs(url.query).get('run', [None])[0]
                if not self.server.result_slots.acquire(blocking=False):
                    self.send_error(503, 'Results are busy; retry shortly')
                    return
                try:
                    result = read_results(learning_directory, run)
                    body, mime = json.dumps(result, allow_nan=False, separators=(',', ':')).encode(), 'application/json'
                finally:
                    self.server.result_slots.release()
            elif url.path in ('/api/decision', '/api/weights'):
                args = parse_qs(url.query)
                def get(name, default=''):
                    return args.get(name, [default])[0]
                try:
                    identity = (get('stream'), int(get('sequence')), get('preview') == '1')
                    result = (feed.decision(*identity) if url.path == '/api/decision' else
                              feed.weights(*identity, get('matrix'), int(get('row', '0')),
                                           int(get('column', '0'))))
                except ValueError:
                    self.send_error(400)
                    return
                if result is None:
                    self.send_error(404)
                    return
                body, mime = json.dumps(result, allow_nan=False, separators=(',', ':')).encode(), 'application/json'
            elif url.path == '/api/state':
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
    server.result_slots = threading.BoundedSemaphore(2)
    server.sampler = threading.Thread(target=server.sample, daemon=True, name='telemetry-sampler')
    server.sampler.start()
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--preview', action='store_true', help='Run a separate synthetic PyTorch preview process')
    args = parser.parse_args()
    config_path = ROOT.parent / 'zar.local.toml'
    config = tomllib.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {}
    server = make_server(args.host, args.port,
                         learning_host=config.get('visualizer', {}).get('learning_host', ''))
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
