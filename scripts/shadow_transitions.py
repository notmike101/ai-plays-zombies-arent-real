"""Bounded, observation-only battle transition capture."""


class TransitionCapture:
    def __init__(self, limit=2048):
        self.limit = limit
        self.states = []
        self.transitions = []
        self.pending = None
        self.truncated = False

    def observe(self, state, decision):
        index = len(self.states)
        if index >= self.limit:
            self.pending = None
            self.truncated = True
            return
        if self.pending is not None:
            dt = state['sim'] - self.states[-1]['sim']
            if dt >= 0:
                self.transitions.append(dict(self.pending, to=index, dt=dt))
        self.states.append(state)
        self.pending = dict(decision, **{'from': index}, receipt={'status': 'unknown'})

    def receipt(self, status, **evidence):
        if self.pending is not None:
            self.pending['receipt'] = dict(status=status, **evidence)
