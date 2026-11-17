"""Optional, inference-only telemetry. Never controls the game or samples actions."""
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time
import uuid
import weakref

import torch
from torch import nn

RUNTIME = Path(__file__).resolve().parent / 'runtime'


def vector(tensor):
    return tensor.detach().reshape(-1, tensor.shape[-1])[-1].cpu().tolist()


class Observer:
    def __init__(self, net, game_pid, episode='', *, labels=None, directory=RUNTIME):
        self.directory = Path(directory)
        self.stream = f'{os.getpid()}-{uuid.uuid4().hex[:12]}'
        self.game_pid = int(game_pid)
        self.episode = str(episode)
        self.labels = labels or {}
        self.net = weakref.ref(net)
        self.values = {}
        self.error = None
        self.label_warning = None
        self._hooks = []
        self._queue = queue.Queue(maxsize=1)
        self._thread = None
        self._closed = False
        self._versions = None
        self._graph = None
        self._revision = None
        self._last_publish = 0
        self.sequence = 0
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._thread = threading.Thread(target=self._write_loop, daemon=True, name='policy-telemetry')
            self._thread.start()
            children = dict(net.named_children())
            self.gru_name, self.gru = next((n, m) for n, m in children.items() if isinstance(m, nn.GRU))
            self.heads = {n: m for n, m in children.items() if isinstance(m, nn.Linear)}
            if (len(children) != len(self.heads) + 1 or not self.heads or
                    self.gru.num_layers != 1 or self.gru.bidirectional or
                    any(m.in_features != self.gru.hidden_size for m in self.heads.values())):
                raise ValueError('expected one unidirectional GRU and direct linear heads')
            self._hooks.append(self.gru.register_forward_hook(self._capture_gru))
            for name, head in self.heads.items():
                self._hooks.append(head.register_forward_hook(self._capture_head(name)))
        except Exception as exc:
            self.error = f'Unsupported or unavailable observer: {type(exc).__name__}: {exc}'
            if self._thread is not None and not self._thread.is_alive():
                self._thread = None
            for hook in self._hooks:
                hook.remove()
            self._hooks.clear()

    def _capture_gru(self, module, args, output):
        if torch.is_grad_enabled() or self._closed:
            return
        try:
            x = args[0]
            if x.numel() != module.input_size:
                self.values = {}  # Training sequences are not a single live decision.
                return
            previous = args[1] if len(args) > 1 else None
            self.values = {'input': vector(x), 'memory': vector(previous) if previous is not None
                           else [0.0] * module.hidden_size, self.gru_name: vector(output[0])}
        except Exception as exc:
            self.error = f'Capture unavailable: {exc}'

    def _capture_head(self, name):
        def capture(module, args, output):
            if torch.is_grad_enabled() or self._closed or not self.values:
                return
            try:
                # Copy now: the trainer masks logits in place after forward returns.
                self.values[name] = vector(output)
            except Exception as exc:
                self.error = f'Capture unavailable: {exc}'
        return capture

    def _topology(self):
        net = self.net()
        if net is None:
            raise ValueError('model was released')
        versions = tuple((name, p._version, tuple(p.shape)) for name, p in net.named_parameters())
        if versions == self._versions:
            return
        layers, edges = [], []
        def layer(name, size, kind):
            labels = self.labels.get(name, [])
            if name == 'input' and len(labels) < size:
                self.label_warning = (f'{name} labels {len(labels)}/{size} '
                                      '(generic names published)')
            layers.append({'id': name, 'size': size, 'kind': kind,
                           'labels': [str(labels[i]) if i < len(labels) else f'{name} {i}' for i in range(size)]})
        def connect(source, target, weights, kind):
            weights = weights.detach().cpu()
            count = min(6, weights.shape[1])
            indices = weights.abs().topk(count, dim=1).indices
            for row in range(weights.shape[0]):
                for col in indices[row].tolist():
                    edges.append({'from': f'{source}:{col}', 'to': f'{target}:{row}',
                                  'weight': float(weights[row, col]), 'kind': kind})
        g = self.gru
        layer('input', g.input_size, 'input')
        layer('memory', g.hidden_size, 'memory')
        layer(self.gru_name, g.hidden_size, 'gru')
        # These are unsigned RMS summaries, not a fictitious single GRU weight.
        for source, weights in [('input', g.weight_ih_l0), ('memory', g.weight_hh_l0)]:
            aggregate = weights.detach().reshape(3, g.hidden_size, -1).square().mean(0).sqrt()
            connect(source, self.gru_name, aggregate, 'gate-rms')
        for name, head in self.heads.items():
            layer(name, head.out_features, 'value' if head.out_features == 1 else 'policy')
            connect(self.gru_name, name, head.weight, 'linear')
        graph = {'layers': layers, 'edges': edges, 'parameters': sum(p.numel() for p in net.parameters()),
                 'edge_note': 'Top 6 weights per target. GRU edges: unsigned RMS across reset/update/candidate gates. Linear edges: signed weights.'}
        # Hash full weights, so different episodes with equal shapes cannot share stale topology.
        digest = hashlib.sha256()
        for p in net.parameters():
            digest.update(p.detach().cpu().float().numpy().tobytes())
        digest.update(json.dumps(layers, sort_keys=True).encode())
        self._revision = digest.hexdigest()[:16]
        self._versions, self._graph = versions, graph

    def snapshot(self, *, probabilities=None, selected=None, phase='unknown', preview=False):
        if self._closed:
            return None
        base = {'schema': 1, 'stream': self.stream, 'worker_pid': os.getpid(),
                'game_pid': self.game_pid, 'episode': self.episode, 'timestamp': time.time(),
                'phase': str(phase), 'preview': bool(preview), 'sequence': self.sequence}
        if self.error:
            return {**base, 'error': self.error}
        if not self.values:
            return None
        self._topology()
        frame = {**base, 'model_revision': self._revision,
                 'graph': self._graph, 'values': dict(self.values),
                 'probabilities': {k: vector(v)
                                   for k, v in (probabilities or {}).items()},
                 'selected': {k: int(v) for k, v in (selected or {}).items()}}
        if self.label_warning:
            frame['label_warning'] = self.label_warning
        return frame

    def publish(self, **kwargs):
        """Best effort, <=5 Hz, latest frame only. Failure never propagates to training."""
        if self._closed or time.monotonic() - self._last_publish < .2:
            return False
        try:
            frame = self.snapshot(**kwargs)
            if frame is None or self._thread is None:
                return False
            self.sequence += 1
            self._last_publish = time.monotonic()
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(frame)
            return True
        except Exception:
            return False

    def _write_loop(self):
        destination = self.directory / f'{self.stream}.json'
        temporary = self.directory / f'{self.stream}.tmp'
        while True:
            frame = self._queue.get()
            if frame is None:
                break
            try:
                data = json.dumps(frame, allow_nan=False, separators=(',', ':'))
                temporary.write_text(data, encoding='utf-8')
                os.replace(temporary, destination)
            except (OSError, ValueError, TypeError):
                pass
        for path in (temporary, destination):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        for hook in self._hooks:
            hook.remove()
        self._hooks.clear()
        if self._thread is not None:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(None)
            self._thread.join(timeout=1)
