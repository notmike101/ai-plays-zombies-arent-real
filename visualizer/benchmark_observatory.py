"""Loopback-only benchmark of both views against the same recorded frame."""
import argparse
import json
from pathlib import Path
import statistics
import tempfile
import threading
import time
import tracemalloc
from urllib.request import urlopen

from server import Feed, decode_frame, make_server


def measure(fn, iterations=14):
    durations = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        durations.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(durations), 3)


def peak(fn):
    tracemalloc.start()
    fn()
    _, size = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return size


def wire(data):
    return json.dumps(data, separators=(',', ':'), allow_nan=False).encode()


def run(path, port, serve):
    captured = json.loads(path.read_bytes())
    captured.update(sequence=0, stream='benchmark', episode='recorded schema-4 benchmark fixture',
                    preview=False, timestamp=time.time())
    graph = captured.pop('graph')
    suffix = b',"graph":' + wire(graph) + b'}'
    initial = wire(captured)[:-1] + suffix
    changed = wire({**captured, 'sequence': 1})[:-1] + suffix
    previous = decode_frame(initial)
    print(json.dumps({
        'fixture_bytes': len(initial), 'input_width': len(captured['values']['input']),
        'edge_count': len(graph['edges']), 'cell_logit_width': len(captured['values']['hc']),
        'disk_decode_median_ms': {'legacy': measure(lambda: json.loads(changed)),
                                  'cached_topology': measure(lambda: decode_frame(changed, (initial, previous)))},
        'disk_decode_peak_allocated_bytes': {'legacy': peak(lambda: json.loads(changed)),
                                             'cached_topology': peak(lambda: decode_frame(changed, (initial, previous)))},
    }), flush=True)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        feed = Feed(root)
        destination = root / 'benchmark.json'
        destination.write_bytes(initial)
        server = make_server('127.0.0.1', port, feed, learning_directory=root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def publish():
            for seq in range(1, 1000):
                if server.stopped.wait(.65):
                    return
                frame = {**captured, 'sequence': seq, 'timestamp': time.time()}
                pending = destination.with_suffix('.tmp')
                pending.write_bytes(wire(frame)[:-1] + suffix)
                try:
                    pending.replace(destination)
                except PermissionError:
                    pass  # The reader can have the previous Windows file open.

        writer = threading.Thread(target=publish, daemon=True)
        writer.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            for kind in ('legacy', 'observatory'):
                requested = time.perf_counter()
                with urlopen(url + '/api/events?view=' + kind, timeout=5) as response:
                    events = []
                    first_event = None
                    for line in response:
                        if line.startswith(b'data: '):
                            received = time.perf_counter()
                            event = json.loads(line[6:])
                            sample = event.get('sample') if kind == 'observatory' else event['frame']
                            if sample:
                                events.append(len(line) - 7)
                                if first_event is None:
                                    first_event = round(1000 * (received - requested), 3)
                            if len(events) == 3:
                                break
                steady = feed.state(revision=captured['model_revision']) if kind == 'legacy' else feed.observatory()
                if kind == 'observatory':
                    steady.update(metadata=None, history=steady['history'][-1:])
                print(json.dumps({'view': kind, 'first_sse_payload_bytes': events[0],
                                  'first_event_loopback_ms': first_event,
                                  'steady_sse_payload_bytes': events[1:],
                                  'steady_serialization_median_ms': measure(lambda: wire(steady))}), flush=True)
            if serve:
                print(f'Browser benchmark ready at {url}', flush=True)
                threading.Event().wait()
        finally:
            server.shutdown()
            server.server_close()
            writer.join(timeout=2)
            thread.join(timeout=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recorded_frame', type=Path)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--serve', action='store_true', help='Leave the fixture server up for the browser benchmark')
    args = parser.parse_args()
    run(args.recorded_frame, args.port, args.serve)
