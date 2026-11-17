"""Read-only, dependency-free HTTP service for the local policy observer."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
FRESH_SECONDS = 15
PUBLIC = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
          '/app.js': ('app.js', 'text/javascript'), '/graph.js': ('graph.js', 'text/javascript')}


class Feed:
    def __init__(self, directory=ROOT / 'runtime'):
        self.directory = Path(directory)
        self.lock = threading.Lock()
        self.active = {False: None, True: None}
        self.cache = {}

    def _read(self, now):
        frames, seen = [], set()
        paths = list(self.directory.glob('*.json'))
        # Abandoned crash files are bounded on read; normal observers remove their own files.
        paths.sort(key=lambda p: p.name)
        for path in paths[-128:]:
            try:
                stat = path.stat()
                if stat.st_size > 2 * 1024 * 1024:
                    continue
                signature = (stat.st_mtime_ns, stat.st_size)
                seen.add(path)
                cached = self.cache.get(path)
                if cached and cached[0] == signature:
                    data = cached[1]
                else:
                    data = json.loads(path.read_text(encoding='utf-8'),
                                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                    if (not isinstance(data, dict) or data.get('schema') != 1 or
                            not isinstance(data.get('stream'), str) or
                            not isinstance(data.get('timestamp'), (int, float)) or
                            not math.isfinite(data['timestamp'])):
                        continue
                    if 'error' not in data and not all(isinstance(data.get(key), dict)
                                                       for key in ('graph', 'values', 'probabilities', 'selected')):
                        continue
                    self.cache[path] = (signature, data)
                if -5 <= now - data['timestamp'] <= 120:
                    frames.append(data)
            except (OSError, ValueError, TypeError):
                continue
        self.cache = {p: value for p, value in self.cache.items() if p in seen}
        return frames

    def state(self, *, now=None, preview=False, stream=None, revision=None):
        now = time.time() if now is None else now
        with self.lock:
            frames = [f for f in self._read(now) if bool(f.get('preview')) == preview]
            frames.sort(key=lambda f: (f['timestamp'], f['stream']))
            available = {f['stream']: f for f in frames}
            fresh = [f for f in frames if now - f['timestamp'] <= FRESH_SECONDS]
            chosen = available.get(stream or self.active[preview])
            if not stream and (chosen is None or now - chosen['timestamp'] > FRESH_SECONDS):
                chosen = fresh[0] if fresh else chosen or (frames[-1] if frames else None)
                self.active[preview] = chosen['stream'] if chosen else None
            streams = [{'id': f['stream'], 'game_pid': f.get('game_pid'),
                        'worker_pid': f.get('worker_pid'), 'age': max(0, now - f['timestamp'])} for f in frames]
            if chosen is None:
                return {'status': 'waiting', 'frame': None, 'streams': streams}
            age = max(0, now - chosen['timestamp'])
            status = 'stale' if age > FRESH_SECONDS else 'error' if 'error' in chosen else 'preview' if preview else 'live'
            frame = dict(chosen)
            if revision == frame.get('model_revision'):
                frame.pop('graph', None)
            return {'status': status, 'age': age, 'frame': frame, 'streams': streams}


def make_server(host, port, feed=None):
    feed = feed or Feed()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
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
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, fmt, *args):
            if args and str(args[1]) != '200':
                super().log_message(fmt, *args)
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.host, args.port)
    print(f'Policy visualizer listening on {args.host}:{server.server_port}', flush=True)
    print(f'Open http://localhost:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
