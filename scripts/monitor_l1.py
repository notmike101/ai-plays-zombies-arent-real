"""L1 battle monitor: localized diff-rescan of the [civ][0][zomb] heap block.
Memory-only (no screenshots). Logs to l1loop.log; restarts battle at <10% civ (R).
"""
import sys, time, struct, os
sys.path.insert(0, r'D:\zar-scratch\scripts')
import numpy as np
import memscan, game_drive as gd

PID = int(sys.argv[1]); HWND = int(sys.argv[2])
LOG = r'D:\zar-scratch\sessions\inst2\mem1-1794722735\l1loop.log'
CIV_START = 3171
h = memscan.open_proc(PID)
base = memscan.module_base(PID)


def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.strftime("%H:%M:%S")} {msg}\n')


def tick():
    d = memscan.read(h, base + 0x605f80, 0x18)
    return struct.unpack_from('<III', d, 8)[0] if d else 0


def scan(center=None, span=96 * 1024 * 1024):
    out = {}
    for b2, size in memscan.iter_regions(h):
        if size > 400 * 1024 * 1024:
            continue
        if center is not None and not (center - span < b2 < center + span):
            continue
        off = 0
        step = 4 * 1024 * 1024
        while off < size:
            n = min(step + 16, size - off)
            data = memscan.read(h, b2 + off, n)
            if data and len(data) >= 16:
                arr = np.frombuffer(data[:len(data) // 4 * 4], dtype=np.uint32)
                civs = arr[:-3]; mids = arr[1:-2]; zombs = arr[2:-1]
                ok = ((mids == 0) & (civs > 20) & (civs < 3400) &
                      (zombs > 1000) & (zombs < 400000) & (civs + zombs <= 320000))
                for i in np.where(ok)[0]:
                    out[b2 + off + int(i) * 4] = (int(civs[i]), int(zombs[i]))
            off += step
    return out


def key(vk):
    gd.key(HWND, vk)


prev = None
center = None
last_alive_reads = 0
frozen = 0
for it in range(400):
    t1 = tick()
    time.sleep(10)
    t2 = tick()
    hits = scan(center)
    live = []
    if prev is not None:
        for a, v in hits.items():
            if a in prev and prev[a] != v:
                c, z = v
                pc, pz = prev[a]
                if 0 <= pc - c <= max(600, 0.3 * pc) and abs(z - pz) < 0.6 * max(z, 1000):
                    live.append((a, v))
    if live:
        vals = {v for _, v in live}
        best = max(vals, key=lambda v: v[0])
        cand = [x for x in live if x[1] == best]
        if len(cand) == 1:
            prev = hits
            center = cand[0][0]
            civ, zomb = cand[0][1]
            log(f'it{it} LOCK civ={civ} zomb={zomb} @ {cand[0][0]:#x} tickd={t2 - t1}')
            if t2 == t1:
                frozen += 1
            else:
                frozen = 0
            if civ < 0.10 * CIV_START:
                log('  <10% -> R restart')
                key(0x52)
                time.sleep(2)
                prev = None; center = None
            if frozen >= 3:
                log('  ticks frozen x3 -> battle ended; dump tick/exit')
                sys.exit(0)
            continue
    prev = hits
    log(f'it{it} no-lock hits={len(hits)} live={len(live)} tickd={t2 - t1}')
    if t2 == t1:
        frozen += 1
        if frozen >= 3:
            log('  ticks frozen x3 (unlocked) -> assume end')
            sys.exit(0)
    else:
        frozen = 0
log('loop end')
