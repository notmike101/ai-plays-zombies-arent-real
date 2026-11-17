"""Raw stdio JSON-RPC probe of the REA MCP server (no OMP client timeout, no kernel hold).

Spawns the registered rea.mjs mcp process, opens the exe, then runs an adaptive
query chain (xrefs -> decompile holding functions) and appends every result as a
JSON line to analysis/rea_out.jsonl. Commands list comes from argv JSON:
  python rea_probe.py '[{"t":"xrefs","address":"0x.."},
                        {"t":"decompile_xrefs","address":"0x.."},
                        {"t":"strings","pattern":".."}]'
"""
import json
import os
import subprocess
import sys
import threading
import time

NODE = r'D:\nvm\installs\v24.22.1\node.exe'
REA = (r'C:\Users\me\AppData\Local\npm-cache\_npx\af752b90495482d7'
       r'\node_modules\rea-agents\scripts\rea.mjs')
ENV = dict(os.environ,
           GHIDRA_INSTALL_DIR=r'D:\ghidra\ghidra_12.1.4_PUBLIC',
           JAVA_HOME=r'C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\\',
           REA_GHIDRA_STARTUP_TIMEOUT_MS='1800000',
           REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS='240')
EXE = r'D:\zar-scratch\game-copies\inst2\zombies-arent-real.exe'
OUT = r'D:\zar-scratch\analysis\rea_out.jsonl'

p = subprocess.Popen([NODE, REA, 'mcp'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     env=ENV, text=True, encoding='utf-8', bufsize=1)
_lock = threading.Lock()
_id = [0]


def send(method, params=None, notify=False):
    m = {'jsonrpc': '2.0', 'method': method}
    if params is not None:
        m['params'] = params
    if not notify:
        _id[0] += 1
        m['id'] = _id[0]
    with _lock:
        p.stdin.write(json.dumps(m) + '\n')
        p.stdin.flush()
    return m.get('id')


def recv(want_id, timeout=3000):
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = p.stdout.readline()
        if not line:
            return {'error': 'EOF'}
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        if j.get('id') == want_id:
            return j
    return {'error': 'timeout'}


def call(method, params, tag):
    i = send(method, params)
    j = recv(i)
    with open(OUT, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps({'tag': tag, 'resp': j}) + '\n')
    print(f'DONE {tag}', flush=True)
    return j


def tool(name, args, tag):
    return call('tools/call', {'name': name, 'arguments': args}, tag)


def main():
    cmds = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    i = send('initialize', {'protocolVersion': '2024-11-05',
                            'capabilities': {},
                            'clientInfo': {'name': 'probe', 'version': '1'}})
    recv(i, 120)
    send('notifications/initialized', {}, notify=True)
    tool('open_binary', {'path': EXE}, 'open')
    for c in cmds:
        t = c.get('t')
        if t == 'xrefs':
            tool('xrefs', {'address': c['address']}, f"xrefs@{c['address']}")
        elif t == 'decompile':
            tool('decompile', {'address': c['address']},
                 f"decomp@{c['address']}")
        elif t == 'decompile_xrefs':
            j = tool('xrefs', {'address': c['address']},
                     f"xrefs@{c['address']}")
            txt = json.dumps(j)
            addrs = set()
            import re
            for m in re.finditer(r'0x14[0-9a-f]{6,8}', txt):
                a = m.group(0)
                if a.lower() != c['address'].lower():
                    addrs.add(a)
            for a in sorted(addrs):
                tool('procedure_address', {'symbol_or_address': a},
                     f'proc@{a}')
                tool('decompile', {'address': a}, f'decomp@{a}')
        elif t == 'strings':
            tool('search_strings', {'pattern': c['pattern'],
                                    'mode': 'literal'},
                 f"str@{c['pattern'][:24]}")
    print('ALLDONE', flush=True)
    p.kill()


if __name__ == '__main__':
    main()
