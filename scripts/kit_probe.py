"""Kit-purchase truth: READY with resume_loadout Police lvl20 on L1, dump
battle immediately, print economy loadout lines + ability_charges.
Throwaway; deleted after report."""
import re
import runpy
import time

from env_zar import ZAREnv

t = runpy.run_path('nn_play2.py', run_name='kitprobe')
e = ZAREnv(39092)
e.to_planning()
e.set_loadout({0: 20})
d = t['ready_once'](e)
if not d:
    print('NO DUMP after ready')
else:
    econ = d['economy']
    print('phase', d['where'].get('phase'), 'sim', d['clock'].get('sim_time'))
    print('ECON:', {k: v for k, v in econ.items() if 'loadout' in k
                    or k in ('sp', 'money')})
    print('full econ keys:', list(econ))
    c = d['counts']
    print('ability_charges:', c.get('ability_charges'))
    print('helicopters:', c.get('helicopters'))
    deck = t['build_deck'](d, t['load_bind_keys'](e), {0: 20})
    print('DECK:', [(s['name'], s['charges'], s['key']) for s in deck])
