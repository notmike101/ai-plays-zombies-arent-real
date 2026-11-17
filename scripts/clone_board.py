"""Clone inst2's L3 board (plans/*.prep + progress money/loadout) into copies.
Board files are only read at level-start, so target instances must be
RELAUNCHED (recover/relaunch_boards) afterwards to pick up the new board.
Usage: python scripts/clone_board.py inst1 inst3 inst4
"""
import sys, os, glob, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GC = os.path.join(HERE, '..', 'game-copies')


def main():
    src = os.path.join(GC, 'inst2')
    prep = glob.glob(os.path.join(src, 'steam_cloud', 'plans', '*.prep'))[0]
    prog = glob.glob(os.path.join(src, 'steam_cloud', 'progress',
                                  '*.progress'))[0]
    body = open(prog).read()
    keep = {}
    for line in body.split('\n'):
        for k in ('board_money', 'resume_money', 'resume_loadout', 'perks'):
            if line.startswith(k):
                keep[k] = line
    for dst_name in sys.argv[1:]:
        d = os.path.join(GC, dst_name)
        shutil.copy(prep, glob.glob(os.path.join(d, 'steam_cloud', 'plans',
                                                 '*.prep'))[0])
        tf = glob.glob(os.path.join(d, 'steam_cloud', 'progress',
                                    '*.progress'))[0]
        t = open(tf).read()
        out = []
        for line in t.split('\n'):
            key = line.split('=')[0].strip()
            out.append(keep.get(key, line) if key in keep else line)
        open(tf, 'w').write('\n'.join(out))
        print('cloned board ->', dst_name, flush=True)


if __name__ == '__main__':
    main()
