"""Game-free checks for the bounded zone-lookahead probe: shared scoring,
bit-identical counterfactual replay (including nonconstant plan offsets),
zero side effects on policy state or RNG, and the private registration."""
import copy
import os
from pathlib import Path
import random
import unittest

import numpy as np
import torch

os.chdir(Path(__file__).resolve().parent.parent)

import nn_play2 as trainer
import team_search as search
import team_zone_probe as probe


def fixture_state(lookahead_cells=(0, 1, 8, 9, 16, 17),
                  positions=((-350, 290), (350, -290))):
    mask = np.zeros(trainer.NC)
    mask[list(lookahead_cells)] = 1
    native = dict(camera=[0., 0., 1.], zones=[],
                  units=dict(kind=np.array([0] * len(positions)),
                             pos=np.array([list(point) for point in positions])))
    return dict(planning=True, geometry_cells={search.ZONE_RECT: mask}, native=native), mask


def fixture_team(rng):
    team = dict(search.random_team(rng), zone_population=9., zone_anchor_lookahead=False,
                garrison_coverage=0., special_probe=0.)
    team['plan'] = [dict(search.gene(rng), family=0, tool=search.ZONE_RECT, duration=2,
                         weights=[0.3, -0.2, 0.4, -0.1, 0.05])]
    return team


def fixture_weights():
    torch.manual_seed(3)
    return {name: value.clone() for name, value in trainer.PolicyNet2().state_dict().items()}


def fixture_obs():
    x = torch.zeros(1, 1, trainer.NOBS)
    x[0, 0, trainer.PLANNING_INDEX] = 1.
    x[0, 0, search.GRID_START:search.GRID_START + 5 * trainer.NC] = (
        torch.linspace(-0.3, 0.7, 5 * trainer.NC))
    return x


def reference_scores(native, legal, anchor_cell, width, height, lookahead):
    """Independent loop scoring: exact rectangles when anchored, otherwise
    each corner credited by every complete legal pair through it."""
    scores = np.zeros(trainer.NC, dtype=np.float32)
    civilians = native['units']['pos'][native['units']['kind'] == 0]
    if not len(civilians):
        return scores
    points = search.project(civilians, native['camera'], width, height)
    sheltered = [any(trainer.inside_polygon(civilians[index:index + 1], zone)
                     for zone in native['zones'] if len(zone) >= 3)
                 for index in range(len(civilians))]
    eligible = [point for point, hidden in zip(points, sheltered) if not hidden]
    corners = set(legal)
    if anchor_cell is not None:
        pairs = [(anchor_cell, end) for end in legal]
    elif lookahead:
        pairs = []
        for a_index in range(len(legal)):
            for b_index in range(a_index + 1, len(legal)):
                a, b = legal[a_index], legal[b_index]
                if (a // 8 != b // 8 and a % 8 != b % 8
                        and a // 8 * 8 + b % 8 in corners
                        and b // 8 * 8 + a % 8 in corners):
                    pairs.append((a, b))
    else:
        pairs = []
    for first, second in pairs:
        start = trainer.cell_of_px(first, width, height)
        end = trainer.cell_of_px(second, width, height)
        low = [min(a, b) for a, b in zip(start, end)]
        high = [max(a, b) for a, b in zip(start, end)]
        covered = sum(1 for point in eligible
                      if low[0] <= point[0] <= high[0] and low[1] <= point[1] <= high[1])
        gain = covered / len(civilians)
        scores[second] = max(scores[second], gain)
        if anchor_cell is None:
            scores[first] = max(scores[first], gain)
    return scores


class ZonePopulationScoringTests(unittest.TestCase):
    def test_shared_scoring_matches_production_anchor_golden(self):
        rng = np.random.default_rng(43)
        team = dict(search.random_team(rng), zone_population=9.)
        model = search.TeamPolicy(team)
        tools = np.zeros(trainer.NU)
        tools[search.ZONE_RECT] = 1
        mask = np.zeros(trainer.NC)
        mask[9] = 1
        positions = np.array([[-375, 330], [-315, 270], [-480, 380], [-315, 270]])
        old_zone = np.array([[-390, 310], [-360, 310], [-360, 350], [-390, 350]])
        native = dict(camera=[0., 0., 1.], zones=[old_zone],
                      units=dict(kind=np.array([0, 0, 0, 1]), pos=positions))
        state = dict(planning=True, anchor=(search.ZONE_RECT, 0),
                     geometry_cells={search.ZONE_RECT: mask}, native=native)
        model.set_zone_population(state, tools, np.ones(trainer.NC), 1000, 1000)
        scores, civilians = search.zone_population_scores(native, [9], 0, 1000, 1000, False)
        torch.testing.assert_close(model.zone_population_cells,
                                   torch.from_numpy(scores), rtol=0, atol=0)
        self.assertAlmostEqual(model.zone_population_cells[9].item(), 1. / 3)
        self.assertEqual(civilians, 3)
        self.assertEqual(reference_scores(native, [9], 0, 1000, 1000, False).tolist(),
                         scores.tolist())

    def test_shared_scoring_matches_production_lookahead_golden(self):
        rng = np.random.default_rng(50)
        team = dict(search.random_team(rng), zone_population=9., zone_anchor_lookahead=True)
        model = search.TeamPolicy(team)
        tools = np.zeros(trainer.NU)
        tools[search.ZONE_RECT] = 1
        mask = np.zeros(trainer.NC)
        mask[[0, 1, 8, 9]] = 1
        native = dict(camera=[0., 0., 1.], zones=[],
                      units=dict(kind=np.array([0]), pos=np.array([[-350, 290]])))
        state = dict(planning=True, geometry_cells={search.ZONE_RECT: mask}, native=native)
        model.set_zone_population(state, tools, np.ones(trainer.NC), 1000, 1000)
        legal = list(np.flatnonzero(search.tr.cell_mask(state, search.ZONE_RECT,
                                                        np.ones(trainer.NC))))
        scores, _ = search.zone_population_scores(native, legal, None, 1000, 1000, True)
        torch.testing.assert_close(model.zone_population_cells,
                                   torch.from_numpy(scores), rtol=0, atol=0)
        torch.testing.assert_close(model.zone_population_cells[[0, 1, 8, 9]],
                                   torch.ones(4), rtol=0, atol=0)
        mask[8] = 0
        model.set_zone_population(state, tools, np.ones(trainer.NC), 1000, 1000)
        self.assertFalse(model.zone_population_cells.any())
        scores, _ = search.zone_population_scores(native, [0, 1, 9], None, 1000, 1000, True)
        self.assertFalse(scores.any())
        scores, civilians = search.zone_population_scores(native, [0, 1, 9], None,
                                                          1000, 1000, False)
        self.assertFalse(scores.any())
        self.assertEqual(civilians, 1)

    def test_shared_scoring_fuzz_matches_loop_reference(self):
        rng = np.random.default_rng(20261121)
        team = dict(search.random_team(rng), zone_population=9.)
        model = search.TeamPolicy(team)
        tools = np.zeros(trainer.NU)
        tools[search.ZONE_RECT] = 1
        for trial in range(12):
            native = dict(camera=[float(rng.uniform(-400, 400)), float(rng.uniform(-400, 400)),
                                  float(rng.uniform(.8, 1.4))],
                          zones=([np.array([[x, y], [x + 90, y + 30], [x + 20, y + 120]])
                                  for x, y in rng.uniform(-900, 900, size=(trial % 3, 2))]
                                 if trial % 4 else []),
                          units=dict(kind=rng.integers(0, 3, size=17).astype(np.int64),
                                     pos=rng.uniform(-1300, 1300, size=(17, 2))))
            mask = np.zeros(trainer.NC)
            mask[rng.choice(trainer.NC, size=int(rng.integers(10, 30)), replace=False)] = 1
            state = dict(planning=True, geometry_cells={search.ZONE_RECT: mask}, native=native)
            legal = list(np.flatnonzero(search.tr.cell_mask(state, search.ZONE_RECT,
                                                            np.ones(trainer.NC))))
            for anchor_cell, lookahead in ((None, False), (None, True),
                                           (None, True), (legal[0], False)):
                model.zone_anchor_lookahead = bool(lookahead)
                if anchor_cell is None:
                    model.set_zone_population(state, tools, np.ones(trainer.NC), 1000, 750)
                    production = model.zone_population_cells
                else:
                    production = None
                scores, civilians = search.zone_population_scores(
                    native, legal, anchor_cell, 1000, 750, lookahead)
                if production is not None:
                    torch.testing.assert_close(production, torch.from_numpy(scores),
                                               rtol=0, atol=0)
                self.assertEqual(reference_scores(native, legal, anchor_cell, 1000, 750,
                                                  bool(lookahead)).tolist(),
                                 scores.tolist())
                self.assertEqual(civilians, int((native['units']['kind'] == 0).sum()))


class CounterfactualReplayTests(unittest.TestCase):
    def arm(self, net, st):
        net.zone_probe = {'legal_cells': search.tr.cell_mask(st, search.ZONE_RECT,
                                                             np.ones(trainer.NC))}
        return net.zone_probe

    def production_zone_row(self, net, st, x, tools):
        with torch.no_grad():
            _, lc, _, _ = net(x, None)
        return lc.reshape(-1, trainer.NU, trainer.NC)[0, search.ZONE_RECT]

    def test_counterfactual_matches_production_forward_bitwise(self):
        rng = np.random.default_rng(19)
        team = fixture_team(rng)
        weights = fixture_weights()
        st, mask = fixture_state()
        x = fixture_obs()
        tools = np.zeros(trainer.NU)
        tools[search.ZONE_RECT] = 1
        first = search.TeamPolicy(dict(team))
        first.load_state_dict(weights)
        probe_view = self.arm(first, st)
        first.set_zone_population(st, tools, np.ones(trainer.NC), 1000, 1000)
        actual_row = self.production_zone_row(first, st, x, tools)
        self.assertIn('pre_zone_logits', probe_view)
        self.assertIn('plan_grid', probe_view)
        self.assertIn('plan_distance', probe_view)
        torch.testing.assert_close(
            actual_row,
            probe_view['pre_zone_logits'] + probe_view['plan_grid'] - probe_view['plan_distance'],
            rtol=0, atol=0)
        gain, counterfactual = first.zone_lookahead_counterfactual(st, 1000, 1000)
        self.assertTrue(gain.any())
        self.assertFalse(torch.equal(counterfactual, actual_row))
        second = search.TeamPolicy(dict(team, zone_anchor_lookahead=True))
        second.load_state_dict(weights)
        second.set_zone_population(st, tools, np.ones(trainer.NC), 1000, 1000)
        lookahead_row = self.production_zone_row(second, st, x, tools)
        self.assertTrue(torch.equal(counterfactual, lookahead_row))

    def test_counterfactual_matches_exhausted_plan_without_offsets(self):
        rng = np.random.default_rng(23)
        team = fixture_team(rng)
        weights = fixture_weights()
        st, mask = fixture_state()
        x = fixture_obs()
        tools = np.zeros(trainer.NU)
        tools[search.ZONE_RECT] = 1
        first = search.TeamPolicy(dict(team))
        first.load_state_dict(weights)
        first.index = len(first.steps)
        probe_view = self.arm(first, st)
        first.set_zone_population(st, tools, np.ones(trainer.NC), 1000, 1000)
        actual_row = self.production_zone_row(first, st, x, tools)
        self.assertNotIn('plan_grid', probe_view)
        gain, counterfactual = first.zone_lookahead_counterfactual(st, 1000, 1000)
        self.assertTrue(gain.any())
        second = search.TeamPolicy(dict(team, zone_anchor_lookahead=True))
        second.load_state_dict(weights)
        second.index = len(second.steps)
        second.set_zone_population(st, tools, np.ones(trainer.NC), 1000, 1000)
        self.assertTrue(torch.equal(counterfactual,
                                    self.production_zone_row(second, st, x, tools)))

    def test_row_helper_replays_and_ranks_without_mutation(self):
        rng = np.random.default_rng(29)
        team = fixture_team(rng)
        weights = fixture_weights()
        st, mask = fixture_state()
        x = fixture_obs()
        tools = np.zeros(trainer.NU)
        tools[search.ZONE_RECT] = 1
        net = search.TeamPolicy(dict(team))
        net.load_state_dict(weights)
        probe_view = self.arm(net, st)
        net.set_zone_population(st, tools, np.ones(trainer.NC), 1000, 1000)
        with torch.no_grad():
            _, lc, _, _ = net(x, None)
        reference = copy.deepcopy(st)
        torch_seed = torch.get_rng_state()
        numpy_seed = np.random.get_state()
        python_seed = random.getstate()
        plan_index, cells_snapshot = net.index, net.zone_population_cells.clone()
        row = trainer.zone_probe_row(net, lc, search.ZONE_RECT, probe_view['legal_cells'],
                                     decision=7, money=1234., st=st, width=1000, height=1000,
                                     cell=9)
        again = trainer.zone_probe_row(net, lc, search.ZONE_RECT, probe_view['legal_cells'],
                                       decision=7, money=1234., st=st, width=1000, height=1000,
                                       cell=9)
        self.assertEqual(row, again)
        self.assertEqual(net.index, plan_index)
        torch.testing.assert_close(net.zone_population_cells, cells_snapshot, rtol=0, atol=0)
        self.assertTrue(torch.equal(torch.get_rng_state(), torch_seed))
        self.assertTrue((np.random.get_state()[1] == numpy_seed[1]).all())
        self.assertEqual(random.getstate(), python_seed)
        self.assertEqual(sorted(st), sorted(reference))
        self.assertEqual(st['planning'], reference['planning'])
        np.testing.assert_array_equal(st['geometry_cells'][search.ZONE_RECT],
                                      reference['geometry_cells'][search.ZONE_RECT])
        np.testing.assert_array_equal(st['native']['units']['pos'],
                                      reference['native']['units']['pos'])
        np.testing.assert_array_equal(st['native']['units']['kind'],
                                      reference['native']['units']['kind'])
        self.assertEqual([list(zone) for zone in st['native']['zones']],
                         [list(zone) for zone in reference['native']['zones']])
        legal = list(np.flatnonzero(probe_view['legal_cells']))
        self.assertEqual(row['legal'], legal)
        self.assertEqual(row['cell'], 9)
        self.assertEqual(row['step'], 7)
        self.assertEqual(row['money'], 1234.)
        self.assertEqual(row['tool'], search.ZONE_RECT)
        actual = lc.reshape(-1, trainer.NU, trainer.NC)[0, search.ZONE_RECT]
        self.assertEqual(row['actual_logits'], actual.tolist())
        self.assertEqual(sorted(row), sorted(
            'step tool cell legal money gain actual_logits lookahead_logits '
            'actual_argmax actual_ties lookahead_argmax lookahead_ties'.split()))
        self.assertEqual(row['lookahead_logits'],
                         net.zone_lookahead_counterfactual(st, 1000, 1000)[1].tolist())
        self.assertEqual(row['actual_argmax'],
                         int(trainer.cell_distribution(lc, search.ZONE_RECT,
                                                       probe_view['legal_cells']).probs.argmax()))
        second = search.TeamPolicy(dict(team, zone_anchor_lookahead=True))
        second.load_state_dict(weights)
        second.set_zone_population(st, tools, np.ones(trainer.NC), 1000, 1000)
        with torch.no_grad():
            _, lc_b, _, _ = second(x, None)
        self.assertEqual(row['lookahead_logits'],
                         lc_b.reshape(-1, trainer.NU, trainer.NC)[0, search.ZONE_RECT].tolist())
        self.assertEqual(row['lookahead_argmax'],
                         int(trainer.cell_distribution(lc_b, search.ZONE_RECT,
                                                       probe_view['legal_cells']).probs.argmax()))
        self.assertGreaterEqual(row['actual_ties'], 1)
        self.assertGreaterEqual(row['lookahead_ties'], 1)


class RegistrationTests(unittest.TestCase):
    def test_probe_constants_match_the_registration(self):
        self.assertEqual(trainer.ZONE_PROBE_LIMIT, 24)
        self.assertEqual(trainer.ZONE_RECT_U, search.ZONE_RECT)
        self.assertEqual(probe.SEED, 346571)
        self.assertEqual(probe.COPY, 'inst19')

    def test_offline_plan_binds_frozen_incumbent_and_exclusion(self):
        import team_timing_ablation as tta
        registration = probe.plan()
        self.assertEqual(registration['incumbent'], tta.INCUMBENT_ID)
        self.assertEqual(registration['team'], tta.TEAM_ID)
        self.assertEqual(registration['base'], tta.BASE_ID)
        self.assertEqual(registration['seed'], 346571)
        self.assertEqual(registration['copy'], 'inst19')
        self.assertIsNone(registration['challenger'])
        self.assertIsNone(registration['gate'])
        self.assertEqual(registration['budget'], dict(attempts=1, replacements=0, updates=0))
        self.assertEqual(registration['probe_cap'], trainer.ZONE_PROBE_LIMIT)
        self.assertTrue(registration['prior_timing_seeds'])


if __name__ == '__main__':
    unittest.main()
