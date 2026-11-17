"""Deck state-model regression tests (no game): build_deck dump parsing,
_rule name variants, bind-key reading, slot_castable mask rules (locked /
pending / spent / heli free re-aim / exhausted), obs normalization,
masks_for consistency, periodic refresh. Run: python -m unittest test_deck
from scripts/."""
import os
import runpy
import tempfile
import unittest

_T = {}


def t():
    if not _T:
        _T.update(runpy.run_path(os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'nn_play2.py'), run_name='test_deck'))
    return _T


COUNTS = {
    'police_unlock_seconds': '0', 'police_arrival_seconds': '3',
    'heli_unlock_seconds': '30', 'heli_arrival_seconds': '4',
    'bomber_unlock_seconds': '15', 'bomber_arrival_seconds': '5',
    'seek_destroy_unlock_seconds': '45', 'seek_destroy_arrival_seconds': '6',
    'ac130_unlock_seconds': '90', 'ac130_arrival_seconds': '8',
    'demolition_charges': 'x',  # non-numeric must not crash _rule
    'ability_charges_per_level': '[.Police = 1, .Bomber = 2, .Heli = 1, '
                                 '.SeekDestroy = 2, .AC130 = 1]',
    'ability_charges': '[.Police = 20, .Bomber = 1, .Heli = 1]',
    'ability_cooldown': '[.Police = 0, .Bomber = 0, .Heli = 0]',
    'helicopters': '0',
}
KEYS = ['1', '2', 'T', 'G', 'V', 'B', 'N']


def dump(econ=None, counts=None, clock=None):
    return {'where': {'phase': 'playing'},
            'clock': clock or {'sim_time': '100', 'speed_mult': '8'},
            'economy': econ or {},
            'counts': COUNTS if counts is None else counts}


class FakeEnv:
    def __init__(self, d):
        self.d = d

    def copy_dir(self):
        return self.d


class BuildDeckTests(unittest.TestCase):
    def test_economy_lines_are_the_only_truth(self):
        d = dump(econ={'loadout Heli': '1', 'loadout SeekDestroy': '2',
                       'loadout AC130': '1'})
        deck = t()['build_deck'](d, KEYS)
        self.assertEqual([s['name'] for s in deck],
                         ['Heli', 'SeekDestroy', 'AC130'])  # DECK_ORDER
        self.assertEqual([s['key'] for s in deck], ['1', '2', 'T'])
        self.assertEqual([s['charges'] for s in deck], [1, 4, 1])
        self.assertEqual([s['max_charges'] for s in deck], [1, 4, 1])
        # _rule variants: SeekDestroy -> seek_destroy_*, AC130 -> ac130_*
        self.assertEqual([s['unlock'] for s in deck], [30, 45, 90])
        self.assertEqual([s['arrival'] for s in deck], [4, 6, 8])
        self.assertFalse(any(s['pending'] or s['alive'] for s in deck))
        # keys stop at the bind list end (extra slots -> None, uncastable)
        deck2 = t()['build_deck'](
            dump(econ={'loadout Police': '1', 'loadout Bomber': '1'}),
            ['1'])
        self.assertEqual([s['key'] for s in deck2], ['1', None])

    def test_no_econ_echo_means_no_deck(self):
        # kit probe 2026-11-17: SP-starved board consumed resume_loadout and
        # bought ZERO -> economy echo stays empty, ability_charges shows
        # unowned defaults; the deck MUST be empty, not fabricated.
        self.assertEqual(t()['build_deck'](dump(), KEYS), [])
        self.assertEqual(t()['build_deck'](None, KEYS), [])
        self.assertEqual(
            t()['build_deck'](dump(econ={'loadout Heli': '0'}), KEYS), [])
        self.assertEqual(
            t()['build_deck'](
                dump(econ={'loadout Bogus': '3', 'money': '3111.00'}),
                KEYS), [])

    def test_bind_keys_read_from_settings(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'steam_cloud'))
            with open(os.path.join(d, 'steam_cloud', 'settings.ini'),
                      'w') as f:
                f.write('bind_slot1 = _1\nbind_slot2 = _2\n'
                        'bind_slot7 = T\nvolume = 5\n')
            self.assertEqual(t()['load_bind_keys'](FakeEnv(d)),
                             ['1', '2', 'T'])


def slot(name='Heli', charges=1.0, mx=1.0, unlock=30.0, arrival=4.0,
         pending=False, ready_t=0.0, alive=False, key='1'):
    return {'name': name, 'lvl': 1, 'max_charges': mx, 'charges': charges,
            'unlock': unlock, 'arrival': arrival, 'pending': pending,
            'ready_t': ready_t, 'alive': alive, 'key': key}


class MaskTests(unittest.TestCase):
    def setUp(self):
        tt = t()
        self.sc, self.frac = tt['slot_castable'], tt['slot_castable_frac']
        self.masks, self.st_b = tt['masks_for'], tt['ABILITY_U']['Heli']

    def test_unlock_boundary(self):
        s = slot()
        self.assertFalse(self.sc({'sim': 10}, s))          # locked
        self.assertFalse(self.sc({'sim': 29.4}, s))        # -0.5 s margin
        self.assertTrue(self.sc({'sim': 29.5}, s))
        self.assertTrue(self.sc({'sim': 100}, s))

    def test_pending_blocks_until_ready(self):
        s = slot(pending=True, ready_t=40, charges=0)
        self.assertFalse(self.sc({'sim': 39}, s))
        # at ready_t the loop flips pending->alive together (advance block);
        # a cleared-but-dead heli with 0 charges stays masked:
        self.assertFalse(self.sc({'sim': 40}, dict(s, pending=False)))
        self.assertTrue(self.sc({'sim': 40}, dict(s, pending=False,
                                                  alive=True)))

    def test_spent_vs_heli_free_reaim(self):
        self.assertFalse(self.sc({'sim': 100}, slot(name='Bomber',
                                                    charges=0, alive=True)))
        self.assertFalse(self.sc({'sim': 100}, slot(charges=0)))
        self.assertTrue(self.sc({'sim': 100}, slot(charges=0, alive=True)))

    def test_frac_never_exceeds_one(self):
        st = {'sim': 100}
        self.assertAlmostEqual(self.frac(st, slot(charges=1)), 1.0)
        self.assertAlmostEqual(self.frac(st, slot(charges=0, alive=True)),
                               1.0)
        p = slot(name='Police', charges=19, mx=20)
        self.assertAlmostEqual(self.frac(st, p), 0.95)
        self.assertAlmostEqual(
            self.frac(st, slot(charges=1, alive=True)), 1.0)  # alive add
        #   caps at max, never >1

    def test_masks_for_battle_and_planning(self):
        heli = slot()
        st = {'planning': True, 'sim': 0}
        mu, mc = self.masks(st)
        self.assertEqual(mu[self.st_b], 0)      # no battle casts in planning
        self.assertEqual(mu[0], 1)              # wait legal in both phases
        st = {'planning': False, 'sim': 100, 'deck': [heli]}
        mu, mc = self.masks(st)
        self.assertEqual(mu[0], 1)              # wait always legal
        self.assertEqual(mu[self.st_b], 1)
        st['deck'] = [slot(charges=0)]          # exhausted -> masked again
        mu, _ = self.masks(st)
        self.assertEqual(mu[self.st_b], 0)
        self.assertEqual(mc.sum(), 48)


class RefreshTests(unittest.TestCase):
    def test_sim_resync_and_heli_truth(self):
        st = {'sim': 12.0, 'mult': 8.0,
              'deck': [slot(alive=True, pending=True, ready_t=999)]}
        t()['refresh_battle_state'](st, dump())
        self.assertEqual(st['sim'], 100.0)      # dump clock is truth
        self.assertFalse(st['deck'][0]['alive'])  # helicopters = 0
        st['sim'] = 0
        t()['refresh_battle_state'](
            st, dump(counts=dict(COUNTS, helicopters='2')))
        self.assertTrue(st['deck'][0]['alive'])
        self.assertFalse(st['deck'][0]['pending'])
        t()['refresh_battle_state'](st, None)   # missing dump: no crash
        self.assertEqual(st['sim'], 100.0)

    def test_charges_synced_from_dump(self):
        st = {'sim': 10, 'mult': 1, 'deck': [slot(name='Police', mx=20,
                                                  charges=3, unlock=0)]}
        t()['refresh_battle_state'](st, dump())
        self.assertEqual(st['deck'][0]['charges'], 20)
        # capped at max even if the dump line says more
        st['deck'][0]['charges'] = 3
        st['deck'][0]['max_charges'] = 5
        t()['refresh_battle_state'](st, dump())
        self.assertEqual(st['deck'][0]['charges'], 5)

    def test_game_cooldown_blocks_exact_window(self):
        st = {'sim': 100, 'mult': 1,
              'deck': [slot(name='Bomber', charges=1, unlock=0)]}
        t()['refresh_battle_state'](st, dump(counts=dict(
            COUNTS, ability_cooldown='[.Bomber = 12]')))
        s = st['deck'][0]
        self.assertTrue(s['pending'])
        self.assertEqual(s['ready_t'], 112)
        self.assertFalse(t()['slot_castable']({'sim': 111}, s))
        self.assertTrue(t()['slot_castable']({'sim': 112},
                                             dict(s, pending=False)))
        # HELI cooldown ignored (free re-aim while flying)
        st = {'sim': 100, 'mult': 1, 'deck': [slot(charges=0, unlock=0)]}
        t()['refresh_battle_state'](st, dump(counts=dict(
            COUNTS, ability_charges='[.Heli = 0]',
            ability_cooldown='[.Heli = 8]', helicopters='1')))
        self.assertTrue(t()['slot_castable'](st, st['deck'][0]))


class SetLoadoutTests(unittest.TestCase):
    def _env(self, body):
        import env_zar
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        os.makedirs(os.path.join(d.name, 'steam_cloud', 'progress'))
        with open(os.path.join(d.name, 'steam_cloud', 'progress',
                               'Boston__MA.progress'), 'w') as f:
            f.write(body)
        e = env_zar.ZAREnv.__new__(env_zar.ZAREnv)
        e.copy_dir = lambda: d.name
        return e, os.path.join(d.name, 'steam_cloud', 'progress',
                               'Boston__MA.progress')

    def test_missing_line_reappended(self):
        # after a WIN screen the game drops the line (2026-11-17 IndexError)
        e, p = self._env('some_key = 1\n')
        new = e.set_loadout({0: 1})
        self.assertEqual(new, 'resume_loadout = ' +
                         ' '.join(['1'] + ['0'] * 18))
        with open(p) as f:
            txt = f.read()
        self.assertIn(new, txt)
        self.assertIn('some_key = 1', txt)

    def test_existing_line_edited_and_padded(self):
        e, p = self._env('resume_loadout = 2 3\nother = x\n')
        new = e.set_loadout({2: 5})
        toks = new.split('=')[1].split()
        self.assertEqual(toks[:3], ['2', '3', '5'])
        self.assertEqual(len(toks), 19)
        with open(p) as f:
            txt = f.read()
        self.assertIn(new, txt)
        self.assertIn('other = x', txt)


if __name__ == '__main__':
    unittest.main()
