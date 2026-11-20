"""Game-free checks for genome search, independent team state and outcome scoring."""
import copy
import unittest
from unittest.mock import call, patch
from concurrent.futures import Future
import numpy as np
import torch
import team_search as search


class SearchTests(unittest.TestCase):
    def test_layout_free_continuations_reuse_local_immutable_base(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        weights = {'weight': torch.tensor([1., 2.])}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior, resumed, fallback = (root / f'coverage-team-{name}'
                                        for name in ('prior', 'resumed', 'fallback'))
            for directory in (prior, resumed, fallback):
                directory.mkdir()
            search.save_frozen_base(prior, weights, None)
            search.save_frozen_base(resumed, weights, prior)
            self.assertTrue((prior / 'base.pt').samefile(resumed / 'base.pt'))
            with patch.object(search.os, 'link', side_effect=OSError):
                search.save_frozen_base(fallback, weights, prior)
            self.assertFalse((prior / 'base.pt').samefile(fallback / 'base.pt'))
            restored = torch.load(fallback / 'base.pt', weights_only=True)
            torch.testing.assert_close(restored, weights)

    def test_explicit_holdout_copies_must_be_disjoint_and_paired(self):
        from contextlib import redirect_stderr
        from io import StringIO

        base = ['team_search.py', '--copies', 'inst13', 'inst14', 'inst15', 'inst16',
                '--holdout-copies']
        for copies in (['inst13', 'inst17'], ['inst17', 'inst18', 'inst19']):
            errors = StringIO()
            with (self.subTest(copies=copies), patch('sys.argv', base + copies),
                  redirect_stderr(errors), patch.object(search.operator, 'training_lock') as lock):
                with self.assertRaises(SystemExit):
                    search.main()
                self.assertIn('distinct, paired holdout copies disjoint from training', errors.getvalue())
                lock.assert_not_called()

    def test_defense_duration_extends_only_a_paid_preference_within_planning_cap(self):
        rng = np.random.default_rng(77)
        parent = search.random_team(rng)
        garrison, mortar = (search.tr.TOOLS.index(name) for name in ('garrison', 'mortar'))
        parent['plan'] = [
            dict(search.gene(rng), family=0, tool=garrison, duration=2),
            dict(search.gene(rng), family=0, tool=mortar, duration=search.tr.PLAN_STEPS-4),
        ]
        before = copy.deepcopy(parent)
        trial = dict(team=parent, levels=[dict(paid_buildings={'Garrison': 1})])
        child = search.defense_duration_candidate(trial, rng)
        self.assertEqual(parent, before)
        self.assertEqual(child['plan'][0]['duration'], 4)
        child['plan'][0]['duration'] = 2
        self.assertEqual(child, parent)
        parent['plan'][1]['duration'] = search.tr.PLAN_STEPS-2
        self.assertIsNone(search.defense_duration_candidate(trial, rng))
        parent['plan'][1]['duration'] = 2
        trial['levels'][0]['paid_buildings'] = {'Garrison': 0}
        self.assertIsNone(search.defense_duration_candidate(trial, rng))

    def test_defense_evidence_requires_paid_build_and_native_ready_units(self):
        rng = np.random.default_rng(39)
        team = search.random_team(rng)
        level = dict(stage=1, start_kind='fresh', attempt=0, end='aborted', saved=.09,
                     outbreak={'seed': 21},
                     paid_buildings={'Garrison': 1}, ready_stats={'garrisons': 1})
        trial = dict(team=team, levels=[level])
        self.assertTrue(search.has_defense_evidence(trial))
        for partial in ({'ready_stats': {'garrisons': 0}}, {'paid_buildings': {}},
                        {'saved': None}, {'start_kind': 'carry'}):
            self.assertFalse(search.has_defense_evidence(dict(trial, levels=[dict(level, **partial)])))
        self.assertFalse(search.has_defense_evidence(dict(trial, arm='candidate')))

    def test_defense_spacing_changes_only_the_confirmed_garrison_preference(self):
        rng = np.random.default_rng(29)
        parent = search.random_team(rng)
        parent['plan'] = [dict(search.gene(rng), family=0,
                              tool=search.tr.TOOLS.index('garrison'), duration=2)]
        level = dict(stage=1, start_kind='fresh', saved=.09, outbreak={'seed': 77},
                     ready_stats={'garrisons': 4}, paid_buildings={'Garrison': 3})
        trial = dict(team=parent, levels=[level])
        variant = search.defense_spacing_candidate(trial, rng)
        original = parent['plan'][0]['weights'][2]
        self.assertLess(variant['plan'][0]['weights'][2], original)
        variant['plan'][0]['weights'][2] = original
        self.assertEqual(variant, parent)
        level['paid_buildings']['Garrison'] = 1
        self.assertIsNone(search.defense_spacing_candidate(trial, rng))

    def test_shelter_order_mutation_preserves_coverage_weight_and_all_other_preferences(self):
        rng = np.random.default_rng(12)
        parent = dict(search.random_team(rng), garrison_coverage=10.)
        buy = dict(search.gene(rng), family=2, tool=search.tr.TOOLS.index('buy_Demolition'))
        place = dict(search.gene(rng), family=0, tool=search.tr.TOOLS.index('garrison'))
        view = dict(search.gene(rng), family=5, tool=search.tr.TOOLS.index('pan_left'))
        rectangle = dict(search.gene(rng), family=1, tool=10)
        parent['plan'] = [buy, place, view, rectangle]
        variant = search.shelter_order_candidate(parent)
        self.assertEqual(variant, dict(parent, plan=[buy, rectangle, place, view]))
        self.assertEqual(parent['plan'], [buy, place, view, rectangle])
        self.assertIsNone(search.shelter_order_candidate(variant))
        self.assertIsNone(search.shelter_order_candidate(dict(parent, garrison_coverage=0.)))

    def test_garrison_coverage_changes_only_its_placement_cell_logits(self):
        rng = np.random.default_rng(17)
        parent = search.random_team(rng)
        parent['plan'] = []
        trial = dict(team=parent, levels=[dict(stage=1, start_kind='fresh', saved=.09,
                    outbreak={'seed': 88, 'safe_zones': 2}, paid_buildings={'Garrison': 1},
                    ready_stats={'garrisons': 1})])
        variant = search.defense_coverage_candidate(trial, rng)
        self.assertEqual({k: v for k, v in variant.items() if k != 'garrison_coverage'}, parent)
        frozen = dict(base='base', team_id=search.team_id(variant), team=variant)
        self.assertEqual(search.checkpoint_team(frozen, 'base')['team'], variant)
        model = search.TeamPolicy(variant)
        tool = search.tr.TOOLS.index('garrison')
        tools = np.zeros(search.tr.NU)
        tools[tool] = 1
        box = np.array([[0, 0], [40, 0], [40, 40], [0, 40]])
        state = dict(planning=True, rules={'garrison_range_max': '50'},
                     native=dict(camera=[0., 0., 1.], zones=[box, box + [400, 0]],
                                 units=dict(kind=np.array([6]), pos=np.array([[20, 20]]))),
                     build_targets=[(520, 480), (920, 480)] + [None] * (search.tr.NC - 2))
        model.set_garrison_coverage(state, tools, np.ones(search.tr.NC), 1000, 1000)
        torch.testing.assert_close(model.garrison_coverage_cells[:2], torch.tensor([0., .5]))
        x = torch.zeros(1, 1, search.tr.NOBS)
        x[..., search.tr.PLANNING_INDEX] = 1
        def base(*args):
            return torch.zeros(1, 1, search.tr.NU), torch.zeros(search.tr.NU * search.tr.NC), None, None
        with patch.object(search.tr.PolicyNet2, 'forward', side_effect=base):
            plain = search.TeamPolicy(parent)(x)
            result = model(x)
        torch.testing.assert_close(result[0], plain[0])
        diff = (result[1] - plain[1]).reshape(search.tr.NU, search.tr.NC)
        self.assertAlmostEqual(diff[tool, 1].item(), variant['garrison_coverage'] * .5, places=5)
        self.assertEqual(int(torch.count_nonzero(diff)), 1)

    def test_garrison_coverage_uses_footprint_for_candidates_and_existing_defenders(self):
        rng = np.random.default_rng(16)
        team = dict(search.random_team(rng), garrison_coverage=10., garrison_building_range=True)
        frozen = dict(base='base', team_id=search.team_id(team), team=team)
        self.assertEqual(search.checkpoint_team(frozen, 'base')['team'], team)
        model = search.TeamPolicy(team)
        tools = np.zeros(search.tr.NU)
        tools[search.GARRISON] = 1
        box = np.array([[0, 0], [40, 0], [40, 40], [0, 40]])
        state = dict(planning=True, rules={'garrison_range_base': '0',
                                         'garrison_range_per_meter': '1',
                                         'garrison_range_max': '50'},
                     native=dict(camera=[0., 0., 1.], zones=[box, box + [400, 0]],
                                 units=dict(kind=np.array([6]), pos=np.array([[20, 20]])),
                                 buildings=dict(center=np.array([[20, 20]]), area=np.array([1.]))),
                     build_targets=[(520, 480), (920, 480)] + [None] * (search.tr.NC - 2),
                     build_areas=[1600., 1.] + [0.] * (search.tr.NC - 2))
        model.set_garrison_coverage(state, tools, np.ones(search.tr.NC), 1000, 1000)
        torch.testing.assert_close(model.garrison_coverage_cells[:2], torch.tensor([.5, 0.]))

    def test_early_garrison_coverage_uses_only_occupied_zones_when_delay_applies(self):
        rng = np.random.default_rng(44)
        team = dict(search.random_team(rng), garrison_coverage=10.,
                    garrison_building_range=True, garrison_early_coverage=True)
        model = search.TeamPolicy(team)
        frozen = dict(base='base', team_id=search.team_id(team), team=team)
        self.assertEqual(search.checkpoint_team(frozen, 'base')['team'], team)
        tools = np.zeros(search.tr.NU)
        tools[search.GARRISON] = 1
        box = np.array([[0, 0], [40, 0], [40, 40], [0, 40]])
        rules = {'garrison_range_base': '0', 'garrison_range_per_meter': '1',
                 'garrison_range_max': '50', 'safezone_outside_first_shot_seconds': '12'}
        state = dict(planning=True, rules=rules,
                     native=dict(camera=[0., 0., 1.], zones=[box, box + [400, 0]],
                                 units=dict(kind=np.array([0]), pos=np.array([[20, 20]])),
                                 buildings=dict(center=np.array([[20, 20]]), area=np.array([1600.]))),
                     build_targets=[(520, 480), (920, 480)] + [None] * (search.tr.NC - 2),
                     build_areas=[1600., 1600.] + [0.] * (search.tr.NC - 2))
        model.set_garrison_coverage(state, tools, np.ones(search.tr.NC), 1000, 1000)
        torch.testing.assert_close(model.garrison_coverage_cells[:2], torch.tensor([.5, 0.]))
        rules['safezone_outside_first_shot_seconds'] = '0'
        model.set_garrison_coverage(state, tools, np.ones(search.tr.NC), 1000, 1000)
        torch.testing.assert_close(model.garrison_coverage_cells[:2], torch.tensor([.5, .5]))

    def test_planning_masks_direct_and_snapped_executed_points(self):
        tr = search.tr
        boundary = np.array([[200, 100], [800, 100], [800, 600], [200, 600]])
        targets = [None] * tr.NC
        targets[8] = (300, 300)  # Cell centre lies outside, snapped target is legal.
        targets[11] = (100, 300)  # Cell centre is legal, snapped target lies outside.
        st = dict(planning=True, build_targets=targets, playarea_boundary=boundary)
        masks = tr.planning_geometry_masks(st, 1000, 1000)
        for name in ('place_Oil', 'place_Spikes', 'gate', 'garrison', 'place_Railgun'):
            tool = tr.TOOLS.index(name)
            for cell in (8, 11):
                self.assertEqual(bool(masks[tool][cell]),
                                 not tr.outside_playarea(st, tool, cell, 1000, 1000))
        oil = tr.TOOLS.index('place_Oil')
        self.assertFalse(masks[oil][8])
        self.assertTrue(masks[oil][11])
        self.assertTrue(masks[search.GARRISON][8])
        self.assertFalse(masks[search.GARRISON][11])
        self.assertNotIn(tr.TOOLS.index('ready'), masks)
        self.assertNotIn(tr.TOOLS.index('place_paint'), masks)

    def test_zone_population_counts_only_new_civilians_in_legal_rectangles(self):
        rng = np.random.default_rng(43)
        team = dict(search.random_team(rng), zone_population=9.)
        frozen = dict(base='base', team_id=search.team_id(team), team=team)
        self.assertEqual(search.checkpoint_team(frozen, 'base')['team'], team)
        model = search.TeamPolicy(team)
        tool = search.ZONE_RECT
        tools = np.zeros(search.tr.NU)
        tools[tool] = 1
        mask = np.zeros(search.tr.NC)
        mask[9] = 1
        positions = np.array([[-375, 330], [-315, 270], [-480, 380], [-315, 270]])
        old_zone = np.array([[-390, 310], [-360, 310], [-360, 350], [-390, 350]])
        state = dict(planning=True, anchor=(tool, 0), geometry_cells={tool: mask},
                     native=dict(camera=[0., 0., 1.], zones=[old_zone],
                                 units=dict(kind=np.array([0, 0, 0, 1]), pos=positions)))
        model.set_zone_population(state, tools, np.ones(search.tr.NC), 1000, 1000)
        self.assertAlmostEqual(model.zone_population_cells[9].item(), 1./3)
        self.assertEqual(int(torch.count_nonzero(model.zone_population_cells)), 1)
        state['anchor'] = None
        model.set_zone_population(state, tools, np.ones(search.tr.NC), 1000, 1000)
        self.assertFalse(model.zone_population_cells.any())

    def test_zone_anchor_lookahead_counts_only_complete_legal_rectangles(self):
        rng = np.random.default_rng(50)
        team = dict(search.random_team(rng), zone_population=9., zone_anchor_lookahead=True)
        model = search.TeamPolicy(team)
        tool = search.ZONE_RECT
        tools = np.zeros(search.tr.NU)
        tools[tool] = 1
        mask = np.zeros(search.tr.NC)
        mask[[0, 1, 8, 9]] = 1
        native = dict(camera=[0., 0., 1.], zones=[],
                      units=dict(kind=np.array([0]), pos=np.array([[-350, 290]])))
        state = dict(planning=True, geometry_cells={tool: mask}, native=native)
        model.set_zone_population(state, tools, np.ones(search.tr.NC), 1000, 1000)
        torch.testing.assert_close(model.zone_population_cells[[0, 1, 8, 9]], torch.ones(4))
        mask[8] = 0
        model.set_zone_population(state, tools, np.ones(search.tr.NC), 1000, 1000)
        self.assertFalse(model.zone_population_cells.any())

    def test_planning_scale_changes_tool_preferences_without_changing_battle(self):
        rng = np.random.default_rng(43)
        parent = search.random_team(rng)
        garrison, ready = (search.tr.TOOLS.index(tool) for tool in ('garrison', 'ready'))
        parent['plan'] = [dict(search.gene(rng), family=0, tool=garrison, duration=1)]
        scaled = dict(parent, planning_logit_scale=.5)
        record = dict(base='base', team_id=search.team_id(scaled), team=scaled)
        self.assertEqual(search.checkpoint_team(record, 'base')['team'], scaled)
        raw = torch.zeros(1, 1, search.tr.NU)
        raw[..., ready] = 20.
        cells = torch.zeros(1, 1, search.tr.NU * search.tr.NC)
        def forward(*args):
            return raw.clone(), cells.clone(), None, None
        x = torch.zeros(1, 1, search.tr.NOBS)
        original, modified = search.TeamPolicy(parent), search.TeamPolicy(scaled)
        with torch.no_grad(), patch.object(search.tr.PolicyNet2, 'forward', side_effect=forward):
            x[..., search.tr.PLANNING_INDEX] = 1
            self.assertEqual(int(original(x)[0].argmax()), ready)
            self.assertEqual(int(modified(x)[0].argmax()), garrison)
            x[..., search.tr.PLANNING_INDEX] = 0
            torch.testing.assert_close(original(x)[0], modified(x)[0])

    def test_zone_cell_sampling_is_frozen_masked_and_separate_from_battle_rng(self):
        parent = search.random_team(np.random.default_rng(4))
        candidate = dict(parent, sample_zone_geometry=True)
        self.assertNotEqual(search.team_id(candidate), search.team_id(parent))
        record = dict(base='base', team_id=search.team_id(candidate), team=candidate)
        self.assertEqual(search.checkpoint_team(record, 'base')['team'], candidate)
        logits = torch.zeros((search.tr.NU, search.tr.NC))
        mask = np.zeros(search.tr.NC)
        mask[[3, 7]] = 1
        dist = search.tr.cell_distribution(logits, search.ZONE_RECT, mask)
        state = torch.random.get_rng_state().clone()
        def choices():
            generator = torch.Generator().manual_seed(45)
            return [search.tr.select_policy_cell(dist, True, generator) for _ in range(16)]
        selected = choices()
        self.assertEqual(selected, choices())
        self.assertEqual(set(selected), {3, 7})
        self.assertEqual(search.tr.select_policy_cell(dist, True), 3)
        self.assertTrue(torch.equal(state, torch.random.get_rng_state()))

    def test_planning_scale_neighbors_require_a_native_clear_and_change_only_scale(self):
        rng = np.random.default_rng(79)
        parent = dict(search.random_team(rng), planning_logit_scale=.41)
        prefix = search.fitness.prefix_id(parent, 1)
        self.assertEqual(search.planning_scale_neighbors(parent, {}), [])
        self.assertEqual(search.planning_scale_neighbors(
            parent, {prefix: {'seed/7': [False, .25, 0., False]}}), [])
        evidence = {prefix: {'seed/7': [False, .2482, 0., True]}}
        low, high = search.planning_scale_neighbors(parent, evidence)
        self.assertAlmostEqual(low['planning_logit_scale'], .31)
        self.assertAlmostEqual(high['planning_logit_scale'], .51)
        self.assertEqual(dict(low, planning_logit_scale=.41), parent)
        self.assertEqual(dict(high, planning_logit_scale=.41), parent)
        evidence[search.fitness.prefix_id(low, 1)] = {}
        self.assertEqual(search.planning_scale_neighbors(parent, evidence), [high])

    def test_placement_mode_preference_precedes_first_build_and_preserves_other_genes(self):
        rng = np.random.default_rng(4)
        parent = search.random_team(rng)
        buy = dict(search.gene(rng), tool=search.tr.TOOLS.index('buy_Demolition'), family=2)
        build = dict(search.gene(rng), tool=search.GARRISON, family=0)
        parent['plan'] = [buy, build]
        for tool in search.PLACEMENT_MODES:
            child = search.placement_mode_candidate(parent, rng, tool)
            preference = child['plan'].pop(1)
            self.assertEqual(preference['tool'], tool)
            self.assertEqual(preference['duration'], 1)
            self.assertEqual(child, parent)

    def test_speed_probe_uses_failed_cast_evidence_and_changes_only_max_speed_logit(self):
        parent = search.random_team(np.random.default_rng(5))
        trial = dict(team=parent, levels=[dict(stage=1, start_kind='fresh', saved=.04,
                    outbreak={'seed': 77}, paid_buildings={'Garrison': 2},
                    ready_stats={'garrisons': 21}, ready_paint_mode=True,
                    ready_loadout={'Demolition': 20.},
                    battle_actions={'cast_available': 1, 'stock_decreased': 0},
                    actions=[(search.FAST_SPEED, 0)])])
        candidate = search.speed_probe(trial)
        self.assertEqual(candidate, dict(parent, speed4_penalty=3.))
        record = dict(base='base', team_id=search.team_id(candidate), team=candidate)
        self.assertEqual(search.checkpoint_team(record, 'base')['team'], candidate)
        trial['levels'][0]['battle_actions']['stock_decreased'] = 1
        self.assertIsNone(search.speed_probe(trial))
        x = torch.zeros(1, 1, search.tr.NOBS)
        def base(*args):
            return torch.zeros(1, 1, search.tr.NU), torch.zeros(search.tr.NU * search.tr.NC), None, None
        with patch.object(search.tr.PolicyNet2, 'forward', side_effect=base):
            before = search.TeamPolicy(parent)(x)[0]
            after = search.TeamPolicy(candidate)(x)[0]
        difference = (after - before).flatten()
        self.assertEqual(int(torch.count_nonzero(difference)), 1)
        self.assertEqual(difference[search.FAST_SPEED].item(), -3.)

    def test_shelter_cast_pair_requires_real_breach_and_a_confirmed_salvo(self):
        rng = np.random.default_rng(6)
        parent = search.random_team(rng)
        battle = dict(cast_available=20, cast_sampled=3, stock_decreased=3,
                      logged_deployments=['demolition']*3, deploy_sim_seconds=[20., 20.4, 21.])
        level = dict(stage=1, start_kind='fresh', saved=.09, ready_paint_mode=True,
                     shelter={'exposed_civilians': 0}, battle_actions=battle)
        trial = dict(team=parent, levels=[level])
        defenders = {'example': trial}
        self.assertIsNone(search.shelter_cast_pair(defenders, {}, rng))
        level['shelter']['exposed_civilians'] = 50
        battle['stock_decreased'] = 0
        self.assertIsNone(search.shelter_cast_pair(defenders, {}, rng))
        battle['stock_decreased'] = 3
        reference, challenger = search.shelter_cast_pair(defenders, {}, rng)
        self.assertIn('cast_timing', reference)
        self.assertGreater(challenger['shelter_defense'], 0)
        del challenger['shelter_defense']
        self.assertEqual(challenger, reference)
        self.assertNotIn('cast_timing', parent)

    def test_goal_margin_prioritizes_survival_above_target_without_rescoring_outcome(self):
        row = dict(advance=False, win=False, saved_frac=.1, civ0=100)
        sustained_below = dict(row, trail=[(30, 90), (120, 32)])
        holds_target = dict(row, trail=[(30, 90), (77, 55), (91, 5)])
        self.assertGreater(search.score(sustained_below)[3], search.score(holds_target)[3])
        self.assertGreater(search.score(holds_target, goal_margin=True)[3],
                           search.score(sustained_below, goal_margin=True)[3])
        row.update(advance=True, win=True, saved_frac=.41, trail=[(5, 100)])
        self.assertEqual(search.score(row, goal_margin=True)[:3], [1, 1, .41])

    def test_placement_neighbors_replace_only_a_preference_missing_from_all_rosters(self):
        rng = np.random.default_rng(28)
        parent = search.random_team(rng)
        template = dict(family=0, duration=4, x=3, y=2, dx=0, dy=0, weights=[0.] * 5)
        original = search.tr.TOOLS.index('place_ChemMine')
        parent['plan'] = [dict(template, tool=search.GARRISON), dict(template, tool=original)]
        rosters = [('Garrison', 'Mortar', 'Oil', 'Mine'), ('Garrison', 'Mortar', 'Oil', 'C4')]
        children = search.available_placement_neighbors(parent, rosters, rng)
        self.assertEqual({search.tr.PLACEMENTS[c['plan'][1]['tool']] for c in children}, {'Mortar', 'Oil'})
        for child in children:
            restored = [child['plan'][0], dict(child['plan'][1], tool=original)]
            self.assertEqual(dict(child, plan=restored), parent)
        self.assertEqual(search.available_placement_neighbors(parent, [(*r, 'ChemMine') for r in rosters], rng), [])
        self.assertEqual(search.available_placement_neighbors(parent, [rosters[0], ('Garrison',)], rng), [])

    def test_fitted_pair_retest_restores_exact_weights_and_all_fit_exposure(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        reference = dict(search.random_team(np.random.default_rng(20)), sample_battle=True,
                         cast_target_mode='greedy')
        candidate = copy.deepcopy(reference)
        candidate['battle'][0][0] += .01
        fit = dict(candidate=search.team_id(candidate), reference=search.team_id(reference),
                   team=candidate, scored_seeds=[13])
        rows = [dict(generation=1, team=reference, team_id=fit['reference']),
                dict(copy='inst13', generation=0,
                     levels=[dict(stage=1, start_kind='fresh', outbreak=dict(seed=24))]),
                dict(copy='inst14', generation=0,
                     levels=[dict(stage=1, start_kind='fresh', outbreak=dict(seed=35))])]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'target-fit.json').write_text(json.dumps(fit))
            (root/'trials.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            self.assertEqual(search.restore_fitted_pair(root, 'base'), ((reference, candidate), {13, 24, 35}))
            fit['fit_copies'] = ['inst13']
            (root/'provisional.json').write_text(json.dumps(dict(team_id=fit['candidate'])))
            (root/'target-fit.json').write_text(json.dumps(dict(folds=[fit])))
            self.assertEqual(search.restore_fitted_pair(root, 'base'), ((reference, candidate), {13, 24}))
            fit['team']['idle_bias'] += 1.
            fit['candidate'] = search.team_id(fit['team'])
            (root/'target-fit.json').write_text(json.dumps(fit))
            with self.assertRaisesRegex(ValueError, 'differ only'):
                search.restore_fitted_pair(root, 'base')

    def test_target_comparison_excludes_each_comparison_copy_from_its_fit(self):
        parent = dict(search.random_team(np.random.default_rng(19)), sample_battle=True, cast_target_mode='sample')
        copies = dict(inst13=0, inst16=0, inst14=1, inst15=1)
        trials = [dict(copy=copy, levels=[dict(stage=1, start_kind='fresh', saved=saved, end='aborted',
                    outbreak=dict(seed=i+10), battle_actions=dict(
                        cast_target_gradients=[[i, 0, 0, 0, 0]] * len(search.CASTS)))])
                  for i, (copy, saved) in enumerate(zip(copies, (.10, .12, .13, .09)))]
        fits = search.target_comparison_fits(parent, trials, copies, 'greedy')
        for fold, expected in ((0, [12, 13]), (1, [10, 11])):
            (reference, challenger), report = fits[fold]
            self.assertEqual(report['scored_seeds'], expected)
            self.assertEqual(report['exposed_seeds'], expected)
            self.assertTrue(set(report['fit_copies']).isdisjoint(report['comparison_copies']))
            self.assertGreater(report['step_norm'], 0.)
            self.assertEqual(dict(challenger, battle=reference['battle']), reference)
            self.assertEqual(reference['cast_target_mode'], 'greedy')
        self.assertNotEqual(fits[0][1]['candidate'], fits[1][1]['candidate'])

    def test_live_tool_gradient_learns_cast_vs_wait_without_changing_targets(self):
        parent = search.random_team(np.random.default_rng(23))
        tool = search.FIREBOMB
        row = search.FIREBOMB_ROW
        alternate = copy.deepcopy(parent)
        alternate['cast_bias'][row] += .5
        model = search.TeamPolicy(parent, collect_cast_tool_gradients=True, alternate_team=alternate)
        mask = torch.zeros(search.tr.NU, dtype=torch.bool)
        mask[[0, tool]] = True
        bias = model.bias.clone().requires_grad_()
        logits = torch.zeros(search.tr.NU)
        logits[search.CASTS] = bias
        dist = torch.distributions.Categorical(logits=logits.masked_fill(~mask, -torch.inf))
        dist.log_prob(torch.tensor(0)).backward()
        model.record_cast_tool_gradient(0, dist.probs.detach())
        torch.testing.assert_close(model.cast_tool_gradients, bias.grad)
        self.assertLess(model.cast_tool_gradients[row], 0.)
        with torch.no_grad():
            self.assertGreater(model.alternate_tool_distance(dist), 0.)
        rows = [dict(copy=f'inst{i}', levels=[dict(stage=1, start_kind='fresh', end='aborted',
                     saved=.1 + i*.01, outbreak=dict(seed=i), battle_actions=dict(
                         cast_tool_gradients=(i*model.cast_tool_gradients).tolist()))])
                for i in (1, 2)]
        child, report = search.live_cast_update(parent, rows, learn_tools=True)
        self.assertEqual(report['learned_field'], 'cast_bias')
        self.assertGreater(report['step_norm'], 0.)
        self.assertEqual(dict(child, cast_bias=parent['cast_bias']), parent)

    def test_alternate_cast_audit_recomputes_argmax_with_the_same_legal_mask(self):
        parent = search.random_team(np.random.default_rng(21))
        row = search.FIREBOMB_ROW
        parent['battle'][row] = [0.] * 5
        alternate = copy.deepcopy(parent['battle'])
        alternate[row][0] = 1.
        model = search.TeamPolicy(parent, alternate_team=dict(parent, battle=alternate))
        model.cast_grid = torch.zeros(5, search.tr.NC)
        model.cast_grid[0, :3] = torch.tensor([0., 2., 100.])
        logits = torch.full((search.tr.NC,), -torch.inf)
        logits[:2] = torch.tensor([1., 0.])
        dist = torch.distributions.Categorical(logits=logits)
        legal = np.zeros(search.tr.NC)
        legal[:2] = 1.
        self.assertEqual(int(dist.probs.argmax()), 0)
        self.assertEqual(model.alternate_cast_argmax(search.FIREBOMB, dist, legal), 1)

    def test_live_cast_gradient_matches_autodiff_on_legal_cells(self):
        model = search.TeamPolicy(search.random_team(np.random.default_rng(42)), collect_cast_gradients=True)
        tool = search.FIREBOMB
        row = search.FIREBOMB_ROW
        model.cast_grid = torch.arange(5 * search.tr.NC).reshape(5, -1).float() / 100.
        weights = model.battle[row].clone().requires_grad_()
        mask = torch.arange(search.tr.NC) < 3
        logits = (weights @ model.cast_grid).masked_fill(~mask, -torch.inf)
        dist = torch.distributions.Categorical(logits=logits)
        cell = 1
        dist.log_prob(torch.tensor(cell)).backward()
        model.record_cast_gradient(tool, cell, dist.probs.detach())
        torch.testing.assert_close(model.cast_gradients[row], weights.grad)
        self.assertEqual(int(torch.count_nonzero(model.cast_gradients[:row])), 0)

    def test_live_cast_update_uses_distinct_scored_real_outcomes(self):
        parent = search.random_team(np.random.default_rng(42))
        gradient = np.zeros((len(search.CASTS), 5))
        gradient[search.FIREBOMB_ROW, 0] = 1.
        def trial(copy, seed, saved, end, values):
            return dict(copy=copy, levels=[dict(stage=1, start_kind='fresh', outbreak=dict(seed=seed),
                saved=saved, end=end, battle_actions=dict(cast_target_gradients=values.tolist()))])
        rows = [trial('inst13', 1, .4, 'won', gradient),
                trial('inst14', 2, .1, 'aborted', -gradient),
                trial('inst15', 1, .9, 'won', -gradient),
                trial('inst16', 3, None, 'timeout', gradient)]
        child, report = search.live_cast_update(parent, rows)
        self.assertEqual(report['scored_seeds'], [1, 2])
        self.assertAlmostEqual(report['step_norm'], .15)
        self.assertAlmostEqual(child['battle'][search.FIREBOMB_ROW][0],
                               parent['battle'][search.FIREBOMB_ROW][0] + .15)
        self.assertEqual(dict(child, battle=parent['battle']), parent)
        self.assertIs(search.live_cast_update(parent, rows[:1])[0], parent)
        evidence = {}
        search.fitness.record(evidence, dict(rows[0], team=child, target_fit_overlap=True))
        self.assertEqual(evidence, {})

    def test_defense_neighbors_only_replace_a_preference_with_shared_buildings(self):
        rng = np.random.default_rng(73)
        parent = search.random_team(rng)
        absent = search.tr.TOOLS.index('place_ChemMine')
        parent['plan'] = [dict(search.gene(rng), family=0, tool=absent)]
        rosters = [('Garrison', 'GasMortar', 'MLRS', 'Oil'),
                   ('Garrison', 'GasMortar', 'MLRS', 'Oil', 'Sniper')]
        children = search.available_placement_neighbors(parent, rosters, rng, buildings_only=True)
        self.assertEqual({search.tr.PLACEMENTS[t['plan'][0]['tool']] for t in children},
                         {'GasMortar', 'MLRS'})
        for child in children:
            original = dict(child, plan=[dict(child['plan'][0], tool=absent)])
            self.assertEqual(original, parent)

    def test_preparation_search_can_continue_from_a_unit_and_support_variant(self):
        from collections import Counter

        rng = np.random.default_rng(121)
        parent = search.random_team(rng)
        step = search.gene(rng)
        sniper = search.tr.TOOLS.index('place_Sniper')
        hold = search.tr.TOOLS.index('hold')
        wall = search.tr.TOOLS.index('wall')
        parent['plan'] = [dict(step, family=1, tool=search.ZONE_RECT),
                          dict(step, family=0, tool=sniper),
                          dict(step, family=1, tool=hold, duration=1),
                          dict(step, family=1, tool=wall, duration=6)]
        variants = list(search.preparation_variants(parent, ('Garrison', 'Sniper', 'Oil'), Counter(), rng))
        self.assertTrue(variants)
        self.assertTrue(any(not combination[2] for _, combination in variants))
        for team, (unit, _, after) in variants:
            self.assertNotEqual(team, parent)
            self.assertEqual(team['plan'][-1], parent['plan'][-1])
            tools = [gene['tool'] for gene in team['plan'][:-1]]
            self.assertEqual(tools.index(unit) > tools.index(search.ZONE_RECT), after)
            self.assertEqual(dict(team, plan=parent['plan']), parent)

    def test_preparation_variants_rotate_role_combinations_and_preserve_battle(self):
        from collections import Counter

        rng = np.random.default_rng(73)
        parent = search.random_team(rng)
        absent = search.tr.TOOLS.index('place_ChemMine')
        step = dict(search.gene(rng), family=0, tool=absent)
        zone = dict(step, family=1, tool=search.ZONE_RECT)
        parent['plan'] = [step, step, zone]
        roster = ('Garrison', 'Oil', 'Sniper', 'Nest')
        variants = list(search.preparation_variants(parent, roster, Counter(), rng))
        self.assertEqual(len(variants), 24)
        self.assertEqual(len({search.team_id(t) for t, _ in variants}), 24)
        for team, (unit, support, after) in variants:
            self.assertIn(search.tr.PLACEMENTS[unit], ('Oil', 'Sniper', 'Nest'))
            self.assertEqual(dict(team, plan=parent['plan']), parent)
            self.assertEqual(sum(g['duration'] for g in team['plan']), sum(g['duration'] for g in parent['plan']))
            tools = [g['tool'] for g in team['plan']]
            self.assertGreater(tools.index(support), tools.index(search.ZONE_RECT))
            self.assertEqual(tools.index(unit) > tools.index(search.ZONE_RECT), after)
        first = variants[0][1]
        usage = Counter({first: 1, first[0]: 1, first[1]: 1})
        _, replacement = next(search.preparation_variants(parent, roster, usage, rng))
        self.assertNotEqual(replacement[0], first[0])
        self.assertNotEqual(replacement[1], first[1])

    def test_garrison_sampling_preserves_legal_cells_and_policy_identity(self):
        mask = torch.zeros(search.tr.NC, dtype=torch.bool)
        mask[[0, 5]] = True
        ranked = torch.zeros(search.tr.NC)
        ranked[0] = 1.
        dist = search.tr.exploration_distribution(ranked, mask, 0.25)
        self.assertEqual(dist.probs.nonzero().flatten().tolist(), [0, 5])
        self.assertEqual(float(dist.probs[0]), .875)
        self.assertEqual(float(dist.probs[5]), .125)
        parent = search.random_team(np.random.default_rng(11))
        child = dict(parent, sample_garrison_sites=True)
        self.assertNotEqual(search.team_id(parent), search.team_id(child))
        search.checkpoint_team(dict(team=child, team_id=search.team_id(child), base='base'), 'base')

    def test_loadout_sampling_is_legal_ranked_and_replayable(self):
        tr = search.tr
        start = tr.BUY_TOOLS.start
        legal = np.zeros(tr.NU, dtype=np.uint8)
        legal[[0, start, start + 1]] = 1
        logits = torch.full((tr.NU,), 100.)
        logits[start:start+2] = torch.tensor([1., 0.])
        distribution = tr.loadout_distribution(logits, legal)
        self.assertEqual(distribution.probs.nonzero().flatten().tolist(), [start, start + 1])
        self.assertGreater(distribution.probs[start], distribution.probs[start + 1])
        state = torch.random.get_rng_state()
        draws = [torch.multinomial(distribution.probs, 20, replacement=True,
                                  generator=torch.Generator().manual_seed(13)).tolist()
                 for _ in range(2)]
        self.assertEqual(draws[0], draws[1])
        self.assertEqual(set(draws[0]), {start, start + 1})
        torch.testing.assert_close(torch.random.get_rng_state(), state)
        parent = search.random_team(np.random.default_rng(11))
        child = dict(parent, sample_loadout=True)
        self.assertNotEqual(search.team_id(parent), search.team_id(child))
        search.checkpoint_team(dict(team=child, team_id=search.team_id(child), base='base'), 'base')
        child['sample_loadout'] = False
        with self.assertRaisesRegex(ValueError, 'Invalid sampling flag: sample_loadout'):
            search.checkpoint_team(dict(team=child, team_id=search.team_id(child), base='base'), 'base')

    def test_opening_cast_preference_fades_and_ends_on_first_confirmed_spend(self):
        parent = search.random_team(np.random.default_rng(117))
        baseline = search.TeamPolicy(parent)
        child = dict(parent, opening_cast_bias=2.)
        probe = search.TeamPolicy(child)
        probe.load_state_dict(baseline.state_dict())
        search.checkpoint_team(dict(team=child, team_id=search.team_id(child), base='base'), 'base')
        x = torch.zeros(1, 1, search.tr.NOBS)
        mask = torch.ones(search.tr.NU)
        expected = torch.zeros(search.tr.NU)
        with torch.no_grad():
            for sim, confirmed, bonus in ((0., False, 2.), (15., False, 1.),
                                          (15., True, 0.), (45., False, 0.)):
                probe.set_cast_targets(dict(planning=False, sim=sim, first_cast_confirmed=confirmed),
                                       mask, None, 1920, 1200)
                lu, cells, _, _ = probe(x)
                original, original_cells, _, _ = baseline(x)
                expected[search.CASTS] = bonus
                torch.testing.assert_close((lu-original).flatten(), expected)
                torch.testing.assert_close(cells, original_cells)

    def test_cast_target_modes_preserve_tool_sampling_identity(self):
        parent = dict(search.random_team(np.random.default_rng(11)), sample_battle=True)
        teams = [dict(parent, cast_target_mode=mode) for mode in ('sample', 'greedy')]
        for team in teams:
            team_id = search.team_id(team)
            search.checkpoint_team(dict(team=team, team_id=team_id, base='base'), 'base')
            disabled = search.battle_sampling_candidate(team)
            self.assertNotIn('cast_target_mode', disabled)
            self.assertNotIn('sample_battle', disabled)
        self.assertNotEqual(search.team_id(teams[0]), search.team_id(teams[1]))
        dist = torch.distributions.Categorical(probs=torch.tensor([0.1, 0., 0.9]))
        state = torch.random.get_rng_state()
        self.assertEqual(search.tr.select_policy_cell(dist, True), 2)
        sampled = [search.tr.select_policy_cell(dist, False, torch.Generator().manual_seed(i))
                   for i in range(40)]
        self.assertEqual(set(sampled), {0, 2})
        torch.testing.assert_close(torch.random.get_rng_state(), state)

    def test_spray_line_changes_only_its_tool_endpoint_scores(self):
        for tool, flag in [(search.FIREBOMB, 'firebomb_line_targeting'), (search.POLICE, 'police_line_targeting')]:
            with self.subTest(tool=tool):
                self.check_line_scores(tool, flag)

    def check_line_scores(self, tool, flag):
        tr = search.tr
        parent = search.random_team(np.random.default_rng(41))
        parent['battle'] = [[0., 1., 0., 0., 0.] for _ in search.CASTS]
        line = dict(parent, **{flag: True})
        reference, model = search.TeamPolicy(parent), search.TeamPolicy(line)
        tools = np.zeros(tr.NU)
        tools[tool] = 1
        st = dict(planning=False, anchor=(tool, 8))
        for policy in (reference, model):
            policy.set_cast_targets(st, tools, np.ones(tr.NC), 1000, 1000)
        x = torch.zeros(1, 1, tr.NOBS)
        x[..., search.GRID_START + tr.NC + 10] = 8.  # Crowd between cells 8 and 12.
        def base_scores(*args):
            return torch.zeros(1,1,tr.NU), torch.zeros(1,1,tr.NU*tr.NC), None, None
        with torch.no_grad(), patch.object(tr.PolicyNet2, 'forward', side_effect=base_scores):
            base_tools, base, _, _ = reference(x)
            new_tools, new, _, _ = model(x)
        expected, actual = base.reshape(tr.NU, tr.NC), new.reshape(tr.NU, tr.NC)
        self.assertEqual(expected[tool, 12], 0.)
        self.assertGreater(actual[tool, 12], 0.)
        expected[tool] = actual[tool]
        torch.testing.assert_close(expected, actual)
        torch.testing.assert_close(base_tools, new_tools)
        model.set_cast_targets(dict(planning=False, anchor=(search.MISSILE, 8)),
                               tools, np.ones(tr.NC), 1000, 1000)
        self.assertIsNone(model.cast_line)

    def test_firebomb_neighbors_change_only_its_target_preferences(self):
        rng = np.random.default_rng(41)
        parent = search.random_team(rng)
        row = search.FIREBOMB_ROW
        lower, upper = search.battle_neighbors(parent, rng, row)
        self.assertNotEqual(lower['battle'][row], parent['battle'][row])
        np.testing.assert_allclose((np.asarray(lower['battle'][row]) + upper['battle'][row]) / 2.,
                                   parent['battle'][row], atol=1e-12)
        for child in (lower, upper):
            self.assertEqual(child['battle'][:row], parent['battle'][:row])
            self.assertEqual(child['battle'][row+1:], parent['battle'][row+1:])
            self.assertEqual(dict(child, battle=parent['battle']), parent)

    def test_battle_neighbors_mirror_only_cast_scores(self):
        rng = np.random.default_rng(28)
        parent = search.random_team(rng)
        lower, upper = search.battle_neighbors(parent, rng)
        for key in ('battle', 'cast_bias'):
            low, high = np.asarray(lower[key]), np.asarray(upper[key])
            np.testing.assert_allclose((low + high) / 2., parent[key], atol=1e-12)
            self.assertTrue(np.any(low != high))
        self.assertNotEqual(search.team_id(lower), search.team_id(upper))
        for child in (lower, upper):
            unchanged = dict(child, battle=parent['battle'], cast_bias=parent['cast_bias'])
            self.assertEqual(unchanged, parent)

    def test_battle_sampling_is_a_distinct_frozen_policy(self):
        parent = search.random_team(np.random.default_rng(4))
        candidate = search.battle_sampling_candidate(parent)
        self.assertEqual(candidate, dict(parent, sample_battle=True))
        self.assertNotEqual(search.team_id(candidate), search.team_id(parent))
        self.assertEqual(search.battle_sampling_candidate(candidate), parent)
        record = dict(base='base', team_id=search.team_id(candidate), team=candidate)
        self.assertEqual(search.checkpoint_team(record, 'base')['team'], candidate)
        candidate['sample_battle'] = 1
        record['team_id'] = search.team_id(candidate)
        with self.assertRaisesRegex(ValueError, 'battle sampling'):
            search.checkpoint_team(record, 'base')

    def test_defense_variant_inserts_a_learned_preference_without_losing_the_plan(self):
        rng = np.random.default_rng(23)
        parent = search.random_team(rng)
        before = copy.deepcopy(parent)
        child = search.defense_placement_candidate(parent, rng)
        self.assertEqual(parent, before)
        self.assertTrue(child['keep_plan_through_gestures'])
        record = dict(base='base', team_id=search.team_id(child), team=child)
        self.assertEqual(search.checkpoint_team(record, 'base')['team'], child)
        for index, extra in enumerate(child['plan'][1:], start=1):
            remaining = child['plan'][:index-1] + child['plan'][index+1:]
            if remaining == parent['plan'] and extra['family'] == 0:
                equip = child['plan'][index-1]
                self.assertEqual(equip['family'], 3)
                self.assertEqual(equip['duration'], 1)
                self.assertEqual(search.tr.TOOLS[equip['tool']], 'equip_' + search.tr.PLACEMENTS[extra['tool']])
                self.assertEqual(extra['duration'], 2)
                child['plan'] = remaining
                child.pop('keep_plan_through_gestures')
                self.assertEqual(child, parent)
                break
        else:
            self.fail('The added equip and placement choices changed the previous plan')

    def test_new_defender_policy_preserves_its_next_preference_in_masked_gestures(self):
        rng = np.random.default_rng(19)
        parent = search.random_team(rng)
        defender = search.defense_placement_candidate(parent, rng)
        current, legacy = search.TeamPolicy(defender), search.TeamPolicy(parent)
        x = torch.zeros(1, 1, search.tr.NOBS)
        x[..., search.tr.PLANNING_INDEX] = 1
        masks = [search.tr.INPUT_LABELS.index(label) for label in (
            'Geometry anchor cell (/ 48; -1 absent)',
            'Gesture anchor cell (/ 48; -1 absent)',
            'Modal dialog open (0/1)',
        )]
        x[..., masks[:2]] = -1
        with torch.no_grad():
            current(x)
            self.assertEqual(current.index, 1)
            for i, mask in enumerate(masks):
                x[..., mask] = 1 if i == 2 else 0
                current(x)
                self.assertEqual(current.index, 1)
                x[..., mask] = 0 if i == 2 else -1
            current(x)
            self.assertEqual(current.index, 2)
            x[..., masks[0]] = 0
            legacy(x)
            self.assertEqual(legacy.index, 1)

    def test_pause_variant_preserves_the_plan_that_executed_a_cast(self):
        rng = np.random.default_rng(17)
        parent = search.random_team(rng)
        parent['camera_pause'] = [1, 2, 3, 4, 5, 6]
        trial = dict(team=parent, levels=[dict(timeout_reason='continuous_pause',
                                               battle_actions={'stock_decreased': 1})])
        before = copy.deepcopy(parent)
        child = search.pause_variant(trial, rng)
        self.assertEqual(parent, before)
        self.assertEqual(child['camera_pause'][:4], parent['camera_pause'][:4])
        self.assertNotEqual(child['camera_pause'][4:], parent['camera_pause'][4:])
        child['camera_pause'] = parent['camera_pause']
        self.assertEqual(child, parent)
        trial['levels'][0]['battle_actions']['stock_decreased'] = 0
        self.assertIsNone(search.pause_variant(trial, rng))

    def test_spatial_proposal_varies_one_anchor_and_preserves_its_actions(self):
        rng = np.random.default_rng(57)
        parent = search.random_team(rng)
        parent['plan'] = [
            dict(search.gene(rng), family=1, tool=search.tr.TOOLS.index('zone_rect'), x=0, y=4),
            dict(search.gene(rng), family=2, tool=search.tr.TOOLS.index('buy_Missile'), x=7, y=0),
        ]
        before = copy.deepcopy(parent)
        child = search.nearby_plan_candidate(parent, rng)
        self.assertEqual(parent, before)
        x, y = (child['plan'][0][key] for key in ('x', 'y'))
        self.assertIn((x, y), ((1, 4), (0, 3)))
        child['plan'][0].update(x=0, y=4)
        self.assertEqual(child, before)
        parent['plan'] = parent['plan'][1:]
        self.assertIsNone(search.nearby_plan_candidate(parent, rng))

    def test_layout_free_resume_checks_policy_identity_and_rejects_replay(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock

        net = Mock()
        team = search.random_team(np.random.default_rng(17))
        with (tempfile.TemporaryDirectory() as temp,
              patch.object(search.torch, 'load', return_value={'weights': 1}) as load,
              patch.object(search.tr, 'policy_id', return_value='base')):
            source = Path(temp)
            record = source / 'provisional.json'

            def write_proposal(candidate, base='base'):
                record.write_text(json.dumps(dict(team=candidate, team_id=search.team_id(candidate), base=base)))

            write_proposal(team)
            self.assertEqual(search.restore_layout_free_proposal(net, source), team)
            load.assert_called_once_with(source / 'base.pt', weights_only=True)
            net.load_state_dict.assert_called_once_with({'weights': 1})
            write_proposal(team, base='wrong')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                search.restore_layout_free_proposal(net, source)
            write_proposal(dict(team, layout=[dict(kind='gate', points=[[10, 10]])]))
            with self.assertRaisesRegex(ValueError, 'layout replay'):
                search.restore_layout_free_proposal(net, source)

    def test_shadow_arms_vary_only_one_missile_preference(self):
        parent = search.random_team(np.random.default_rng(3))
        arms = search.shadow_variants(parent)
        self.assertEqual(arms['control'], parent)
        for name, key in [('timing', 'cast_bias'), ('civilian_avoidance', 'battle')]:
            candidate = arms[name]
            self.assertEqual({k for k in parent if candidate[k] != parent[k]}, {key})
            self.assertEqual([i for i, (a, b) in enumerate(zip(parent[key], candidate[key])) if a != b],
                             [search.MISSILE_ROW])
        weights = arms['civilian_avoidance']['battle'][search.MISSILE_ROW]
        original = parent['battle'][search.MISSILE_ROW]
        self.assertEqual(weights[0], original[0] - 2.)
        self.assertEqual(weights[1:], original[1:])

    def test_experiment_options_and_capture_are_opt_in(self):
        row = dict(scenario=1, end='won', saved_frac=.43, advance=True, win=True,
                   campaign='Boston', board_id='b', board={'scenario': 1}, sim=100,
                   trail=[], civ0=100, us=[], cs=[], log_started=1, battle_actions={},
                   shadow={'session': 1, 'frames': [], 'casts': []})
        with patch.object(search.zar_boot, 'boot'), patch.object(search.zar_boot, 'stop'), \
                patch.object(search.operator, 'owned_copy'), \
                patch.object(search.tr, 'run_episode', return_value=row) as run:
            regular = search.rollout(('inst13', {}, None, 10))
            self.assertNotIn('shadow', regular['levels'][0])
            self.assertNotIn('fixed_speed', run.call_args.args[0][4])
            experiment = search.rollout(('inst13', {}, None, 10),
                                        fixed_speed='speed_2', capture_shadow=True)
        self.assertEqual(run.call_args.args[0][4]['fixed_speed'], 'speed_2')
        self.assertTrue(run.call_args.args[0][4]['capture_shadow'])
        self.assertEqual(experiment['levels'][0]['shadow'], dict(row['shadow'], copy='inst13', team=None))

    def test_click_start_records_the_game_reported_planning_roster(self):
        with (patch.object(search.operator, 'owned_copy'),
              patch.object(search.zar_boot, 'boot') as boot,
              patch.object(search.zar_boot, 'stop'),
              patch.object(search, 'Controls') as controls,
              patch.object(search.tr, 'run_episode', return_value={'err': 'end fixture'})):
            controls.return_value.planning_roster.return_value = ['Garrison', 'Mortar']
            result = search.rollout(('inst13', {}, None, 10), click_start=True)
        controls.assert_called_once_with(boot.return_value)
        self.assertEqual(result['initial_planning_roster'], ['Garrison', 'Mortar'])

    def test_failed_fast_boot_retries_with_the_standard_warmup(self):
        with (patch.object(search.operator, 'owned_copy', return_value='copy'),
              patch.object(search.zar_boot, 'boot',
                           side_effect=[search.zar_boot.ZAREnvError('no board'),
                                        RuntimeError('still no board')]) as boot):
            result = search.rollout(('inst13', {}, None, 10), fast_boot=True)
        self.assertEqual(result['error'], 'still no board')
        self.assertFalse(result['timing']['fast_boot'])
        self.assertEqual(boot.call_args_list, [
            call('copy', ('campaign', 'stage1'), discard_dump_states=True, welcome_wait=15),
            call('copy', ('campaign', 'stage1'), discard_dump_states=True),
        ])

    def test_rollout_preserves_action_context_without_scoring_a_failed_receipt(self):
        tool = search.tr.TOOLS.index('pause_toggle')
        row = dict(err='Timed out waiting for UI frames', last_tool=tool, last_cell=0, phase='playing')
        with (patch.object(search.operator, 'owned_copy', return_value='copy'),
              patch.object(search.zar_boot, 'boot'), patch.object(search.zar_boot, 'stop'),
              patch.object(search.tr, 'run_episode', return_value=row)):
            result = search.rollout(('inst13', {}, None, 10))
        self.assertEqual(result['levels'], [])
        self.assertEqual(result['error'], row['err'])
        self.assertEqual(result['failed_action'], dict(tool='pause_toggle', cell=0, phase='playing'))

    def test_failed_boot_still_records_worker_lifetime(self):
        with patch.object(search.operator, 'owned_copy'), patch.object(
            search.zar_boot, 'boot', side_effect=RuntimeError('no board')
        ):
            result = search.rollout(('inst13', {}, None, 10))
        self.assertEqual(result['error'], 'no board')
        timing = result['timing']
        self.assertLessEqual(timing['started'], timing['finished'])
        self.assertNotIn('board_ready', timing)

    def test_ppo_later_stage_update_preserves_l1_weights_and_optimizer(self):
        import json
        from pathlib import Path
        import tempfile
        tr=search.tr
        def row(stage):
            return dict(pid=123,scenario=stage,obs=[1],advance=False,end='won',saved_frac=.2,R=1.)
        def update(net,episodes,opt):
            self.assertEqual(len({r['scenario'] for r in episodes}),1)
            opt.zero_grad()
            next(net.parameters()).sum().backward()
            opt.step()
            return {}
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)/'base.pt'
            hist=Path(directory)/'history'
            net=tr.PolicyNet2()
            optimizer=torch.optim.Adam(net.parameters(),lr=3e-4)
            tr.save_checkpoint(net,optimizer,base,'base')
            before=base.read_bytes()
            args=['nn_play2','train','--pids','123','--model',str(base),'--history',str(hist),'--rounds','2','--allow-progression']
            with patch('sys.argv',args),patch.object(tr.mp,'Pool') as pool,patch.object(tr,'ppo_update',side_effect=update),patch.object(tr,'valid_trajectory',return_value=True):
                pool.return_value.__enter__.return_value.map.return_value=[[row(2)]]
                tr.main()
            self.assertEqual(base.read_bytes(),before)
            specialist=torch.load(tr.stage_model_path(base,2),weights_only=True)
            self.assertEqual(next(iter(specialist['optimizer']['state'].values()))['step'].item(),2)
            updates=[json.loads(line) for line in hist.read_text().splitlines()]
            self.assertEqual(updates[1]['checkpoint_id'],updates[2]['checkpoint_id'])

    def test_cast_experiment_uses_first_fresh_l1_and_changes_only_cast_preference(self):
        rng=np.random.default_rng(7)
        team=search.random_team(rng)
        first=dict(stage=1,start_kind='fresh',battle_actions=dict(cast_available=16,cast_sampled=0))
        trial=dict(team=team,levels=[first])
        child=search.cast_candidate(trial,rng)
        self.assertGreater(child.pop('cast_timing')[0],0)
        self.assertEqual(team,child)
        first['start_kind']='carry'
        self.assertIsNone(search.cast_candidate(trial,rng))
        first.update(start_kind='next_level',stage=2)
        self.assertIsNone(search.cast_candidate(trial,rng))

    def test_cast_timing_explores_confirmed_rapid_casts_after_a_scored_loss(self):
        rng = np.random.default_rng(47)
        team = search.random_team(rng)
        actions = dict(cast_available=15, cast_sampled=15, stock_decreased=4,
                       logged_deployments=['demolition']*3+['fire_bomb'],
                       deploy_sim_seconds=[21.27, 22.1, 23.17, 30.7])
        row = dict(stage=1, start_kind='fresh', saved=.0544, battle_actions=actions)
        trial = dict(team=team, levels=[row])
        child = search.cast_candidate(trial, rng)
        child.pop('cast_timing')
        self.assertEqual(child, team)
        row['saved'] = None
        self.assertIsNone(search.cast_candidate(trial, rng))
        row['saved'] = .0544
        actions['stock_decreased'] = 2
        self.assertIsNone(search.cast_candidate(trial, rng))
        actions['stock_decreased'] = 4
        actions['deploy_sim_seconds'][2] = 29
        self.assertIsNone(search.cast_candidate(trial, rng))

    def test_contextual_cast_timing_responds_only_to_legal_cells(self):
        team=search.random_team(np.random.default_rng(7))
        base=search.TeamPolicy(team)
        model=search.TeamPolicy(dict(team,cast_timing=[4.,1.]))
        model.load_state_dict(base.state_dict())
        tool=search.tr.ABILITY_U['Missile']
        tools=np.zeros(search.tr.NU)
        tools[tool]=1
        st=dict(planning=False,playarea_boundary=[(0,0),(500,0),(500,1000),(0,1000)])
        x=torch.zeros(1,1,search.tr.NOBS)
        zombies=search.GRID_START+search.tr.NC
        x[...,zombies+7]=8.  # Dense crowd beyond the playable boundary.
        model.set_cast_targets(st,tools,np.ones(search.tr.NC),1920,1200)
        with torch.no_grad():
            def adjustment():
                return (model(x)[0]-base(x)[0]).flatten()
            low=adjustment()
            self.assertLess(low[tool],0.)
            self.assertEqual(low[search.tr.ABILITY_U['Nuke']],0.)
            x[...,zombies]=5.
            self.assertGreater(adjustment()[tool],0.)
            x[...,search.GRID_START]=8.
            self.assertLess(adjustment()[tool],0.)
            model.set_cast_targets(dict(st,anchor=(tool,0)),tools,np.ones(search.tr.NC),1920,1200)
            self.assertEqual(adjustment()[tool],0.)

    def test_occupied_perimeter_increases_pressure_at_legal_cast_target(self):
        from shelter_reward import Shelter
        team=search.random_team(np.random.default_rng(7))
        base=search.TeamPolicy(dict(team,cast_timing=[2.,3.]))
        defended=search.TeamPolicy(dict(team,cast_timing=[2.,3.],shelter_defense=2.))
        defended.load_state_dict(base.state_dict())
        tool=search.tr.ABILITY_U['Missile']
        tools=np.zeros(search.tr.NU)
        tools[tool]=1
        width,height=1920,1200
        camera=[width/2,-height/2,1.]
        x,y=search.tr.cell_of_px(0,width,height)
        zone=np.asarray([[x,-y],[x+40,-y],[x+40,-y+40],[x,-y+40]],dtype=np.float32)
        shelter=Shelter(10)
        shelter.observe(dict(zones=[zone],units=dict(kind=np.array([0]),id=np.array([1]),
                                      pos=np.array([[x+20,-y+20]]))),0.)
        st=dict(planning=False,playarea_boundary=[(0,0),(500,0),(500,1000),(0,1000)],
                shelter=shelter,native={'camera':camera})
        for policy in (base,defended):
            policy.set_cast_targets(st,tools,np.ones(search.tr.NC),width,height)
        obs=torch.zeros(1,1,search.tr.NOBS)
        obs[...,search.GRID_START+search.tr.NC:search.GRID_START+2*search.tr.NC]=3.
        with torch.no_grad():
            old_tools,old_cells,*_=base(obs)
            new_tools,new_cells,*_=defended(obs)
        self.assertGreater(new_tools.flatten()[tool],old_tools.flatten()[tool])
        boost=(new_cells-old_cells).reshape(search.tr.NU,search.tr.NC)
        self.assertGreater(boost[tool,0],0.)
        self.assertEqual(boost[tool,7],0.)
        self.assertEqual(boost[search.tr.ABILITY_U['Nuke'],0],0.)

    def test_special_probe_only_suggests_enclosed_building_and_enabled_choice(self):
        team=search.random_team(np.random.default_rng(8))
        team.update(plan=[],special_probe=20.)
        policy=search.TeamPolicy(team)
        buildings=dict(center=np.array([[100,100],[300,100],[500,100]]),
                       rect=np.array([[80,80,120,120],[280,80,320,120],[480,80,520,120]]),
                       **{'class':np.ones(3),'destroyed':np.zeros(3),'ability':np.zeros(3)})
        camera=[960.,-600.,1.]
        zone=np.array([[70,70],[310,70],[310,130],[70,130]])
        st=dict(planning=True,hud={'actions':{}},targets={'building':[(100,-100),(300,-100),(500,-100)]},
                native=dict(camera=camera,zones=[zone],buildings=buildings,selection={'building':-1}))
        policy.set_special_probe(st,1920,1200)
        self.assertEqual(policy.special_cells,[0])
        st['native']['selection']['building']=0
        st['hud']['actions']={'building_5':(1600,200),'next_special':(1600,250)}
        policy.set_special_probe(st,1920,1200)
        self.assertEqual(policy.special_tools,[search.BUILDING_SPECIALS['building_5']])
        self.assertEqual(policy.special_cells,[])
        st['hud']['actions']={}
        policy.set_special_probe(st,1920,1200)
        self.assertEqual(policy.special_cells,[])

    def test_paired_cast_comparisons_keep_their_discovery_controls_in_reserve(self):
        for mode, change in [('early-first-cast', {'opening_cast_bias': 2.}),
                             ('police-line', {'police_line_targeting': True})]:
            with self.subTest(mode=mode):
                self.check_cast_comparison(mode, change)

    def test_missile_local_population_is_measured_within_native_radius(self):
        units = dict(pos=np.array([[0., 1.], [7., 0.], [10., 0.], [11., 0.], [4., 1.]]),
                     kind=np.array([0, 1, 0, 0, 2]))
        st = dict(native=dict(camera=[0.,0.,1.], units=units), rules={'missile_blast_radius': 10.})
        world, count, risk = search.tr.missile_target_context(st, [(50,50),(65,50)], 100, 100)
        np.testing.assert_allclose(world, [[0.,0.],[15.,0.]])
        np.testing.assert_array_equal(count, [[2,2],[1,1]])
        self.assertIsNone(risk)
        st['rules'].pop('missile_blast_radius')
        self.assertIsNone(search.tr.missile_target_context(st, [(50,50)], 100, 100))

    def test_missile_footprint_changes_only_the_missile_target_preference(self):
        tr = search.tr
        parent = search.random_team(np.random.default_rng(41))
        parent['battle'] = [[-1., 1., 0., 0., 0.] for _ in search.CASTS]
        reference = search.TeamPolicy(parent)
        model = search.TeamPolicy(dict(parent, missile_footprint=True))
        shelf = tr.Shelter(100)
        px_target = np.array(tr.cell_of_px(8, 1000, 1000), dtype=np.float32)
        world = (px_target - [500, 500]) * [1., -1.]
        shelf.protected = [(world + [[-20., -10.], [20., -10.], [20., 10.], [-20., 10.]], 1.)]
        native = dict(camera=[0., 0., 1.], units=dict(pos=np.array([world]), kind=np.array([0])))
        st = dict(planning=False, sim=31., native=native, shelter=shelf,
                  rules={'missile_blast_radius': 56.},
                  playarea_boundary=[(0,0),(999,0),(999,999),(0,999)])
        tools = np.zeros(tr.NU)
        tools[search.MISSILE] = 1
        for policy in (reference, model):
            policy.set_cast_targets(st, tools, np.ones(tr.NC), 1000, 1000)
        torch.testing.assert_close(reference.cast_targets, model.cast_targets)
        self.assertTrue(model.missile_wall_risk[8])
        x = torch.zeros(1, 1, tr.NOBS)
        with torch.no_grad(), patch.object(tr.PolicyNet2, 'forward',
            side_effect=lambda *args: (torch.zeros(1, 1, tr.NU), torch.zeros(1, 1, tr.NU*tr.NC), None, None)):
            a_tool, a_cell, _, _ = reference(x)
            b_tool, b_cell, _, _ = model(x)
        a_cell, b_cell = a_cell.reshape(tr.NU,tr.NC), b_cell.reshape(tr.NU,tr.NC)
        self.assertLess(float(b_cell[search.MISSILE,8]), float(a_cell[search.MISSILE,8]))
        a_cell[search.MISSILE] = b_cell[search.MISSILE]
        torch.testing.assert_close(a_cell, b_cell)
        torch.testing.assert_close(a_tool, b_tool)

    def test_missile_footprint_comparison_uses_confirmed_discovery_arm(self):
        self.check_cast_comparison('missile-footprint', {'missile_footprint': True})

    def test_missile_followup_comparison_uses_confirmed_discovery_arm(self):
        self.check_cast_comparison('missile-followup', {'missile_followup': 10.})

    def test_evidenced_loadout_comparison_keeps_its_control_in_reserve(self):
        self.check_cast_comparison('loadout', {})

    def test_qualified_holdout_ends_after_an_ineligible_comparison_wave(self):
        self.check_cast_comparison('police-line', {'police_line_targeting': True}, invalid_reference=True)

    def check_cast_comparison(self, mode, change, *, invalid_reference=False):
        import json
        from contextlib import ExitStack, nullcontext
        from pathlib import Path
        from tempfile import TemporaryDirectory

        baseline = search.random_team(np.random.default_rng(42))
        challenger = dict(baseline, **change)
        comparison_args = ['--battle-neighbors', mode]
        if mode == 'loadout':
            police = search.tr.TOOLS.index('buy_Police')
            missile = search.tr.TOOLS.index('buy_Missile')
            purchase = dict(baseline['plan'][0], family=2, tool=police, duration=1)
            baseline['plan'][0] = purchase
            challenger['plan'] = [dict(purchase, tool=missile), *baseline['plan'][1:]]
            comparison_args = ['--loadout-neighbors', 'Missile']
        seed = iter(range(100, 200))

        def completed(pool, jobs, *args, **kwargs):
            for job in jobs:
                tested = job[2]
                outcome = .42 if tested == challenger else .24
                level = dict(stage=1, end='won', saved=outcome, start_kind='fresh',
                             outbreak={'seed': next(seed)}, sim=120.)
                if invalid_reference and job[0] in ('e', 'f') and tested == baseline:
                    level.update(end='timeout', saved=None)
                yield job, 1, dict(copy=job[0], levels=[level])

        with TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            (root / 'analysis').mkdir()
            resume = root / 'resume'
            if mode in ('loadout', 'missile-followup', 'missile-footprint'):
                resume.mkdir()
                discovery = dict(stage=1, end='aborted', saved=.099, start_kind='fresh',
                                 outbreak={'seed': 40}, ready_loadout={'Police': 8.},
                                 ready_loadout_sp=1., shelter={'first_occupied_breach': 52.},
                                 opening_loadout={'Police': {'cost': 1., 'first_effect': 8.},
                                                  'Missile': {'cost': 2., 'first_effect': 32.5}})
                revision = ('playable-overview-v3-bounded-targets-shelter-v2-specials-v1-retries-v2-verified-ready-v1-native-unlock-v1'
                            '-placement-feedback-v4-debt-cancel-v1-click-start-v1')
                prior = dict(copy='a', team=baseline, team_id=search.team_id(baseline),
                             view_revision=revision, levels=[discovery])
                if mode in ('missile-followup', 'missile-footprint'):
                    discovery.update(ready_loadout={'Missile': 32.5},
                                     battle_actions={'logged_deployments': ['cruise_missile'] * 3})
                (resume / 'trials.jsonl').write_text(json.dumps(prior) + '\n')
            args = ['team_search.py', '--continue-layout-free', str(resume),
                    *comparison_args, '--click-start',
                    '--generations', '2', '--qualified-holdout-only',
                    '--copies', 'a', 'b', 'c', 'd', '--holdout-copies', 'e', 'f']
            stack.enter_context(patch('sys.argv', args))
            stack.enter_context(patch.object(search.operator, 'ROOT', root))
            for name, result in [('training_lock', nullcontext()), ('preflight', {'ok': True}),
                                 ('inventory', []), ('require_idle', None), ('limit_resources', None)]:
                stack.enter_context(patch.object(search.operator, name, return_value=result))
            restored = baseline if mode == 'loadout' else challenger
            stack.enter_context(patch.object(search, 'restore_layout_free_proposal', return_value=restored))
            stack.enter_context(patch.object(search, 'save_frozen_base'))
            stack.enter_context(patch.object(search, 'ProcessPoolExecutor'))
            stack.enter_context(patch.object(search, 'completed_rollouts', side_effect=completed))
            search.main()
            output = next((root / 'analysis').iterdir())
            rows = [json.loads(line) for line in (output / 'holdout.jsonl').read_text().splitlines()]
            waves = 1 if invalid_reference else 6
            for arm, team in [('candidate', challenger), ('incumbent', baseline)]:
                self.assertEqual([row['team_id'] for row in rows if row['arm'] == arm],
                                 [search.team_id(team)] * waves)
            if invalid_reference:
                self.assertFalse((output / 'champion.json').exists())
                return
            champion = json.loads((output / 'champion.json').read_text())
            self.assertEqual(champion['holdout_opponent'], search.team_id(baseline))

    def test_holdout_rotates_frozen_arms_and_preserves_paired_policy_seeds(self):
        copies=['a','b','c','d']
        a,b={},{'incumbent':True}
        before,first=search.holdout_assignments(copies,None,a,b,100,0)
        after,second=search.holdout_assignments(copies,None,a,b,100,1)
        self.assertEqual(before[0][3],before[1][3])
        self.assertLess(max(job[3] for job in before),min(job[3] for job in after))
        self.assertTrue(all(first[copy]!=second[copy] for copy in copies))
        self.assertEqual([job[2] for job in before],[a,b,a,b])
        self.assertEqual([job[2] for job in after],[b,a,b,a])

    def test_verified_missile_flight_changes_logits_without_masking_the_cast(self):
        team=search.random_team(np.random.default_rng(7))
        model=search.TeamPolicy(dict(team,missile_followup=10.))
        slot=search.tr._slot('Missile',1,{},{
            'missile_flight_seconds':'2.5','missile_unlock_seconds':'30'},['1'],0)
        slot.update(charges=2,last_cast_t=31.)
        st=dict(planning=False,sim=33.,deck=[slot],
                playarea_boundary=[(0,0),(500,0),(500,1000),(0,1000)])
        obs=torch.zeros(1,1,search.tr.NOBS)
        tools,cells=search.tr.masks_for(st)
        self.assertTrue(tools[search.MISSILE])
        model.set_cast_targets(st,tools,cells,1920,1200)
        self.assertTrue(model.missile_in_flight)
        with torch.no_grad():
            pending=model(obs)[0]
            st['sim']=33.5
            model.set_cast_targets(st,tools,cells,1920,1200)
            self.assertFalse(model.missile_in_flight)
            resolved=model(obs)[0]
        self.assertAlmostEqual((resolved-pending).flatten()[search.MISSILE].item(),10.,places=5)

    def test_missile_reserve_depends_on_local_pressure_and_remaining_stock(self):
        team=search.random_team(np.random.default_rng(7))
        base=search.TeamPolicy(team)
        candidate=search.TeamPolicy(dict(team,missile_reserve=4.))
        candidate.load_state_dict(base.state_dict())
        candidate.shelter_perimeter[0]=1.
        candidate.cast_targets[search.MISSILE_ROW,0]=True
        obs=torch.zeros(1,1,search.tr.NOBS)

        def difference():
            with torch.no_grad():
                old_tools,old_cells,*_=base(obs)
                new_tools,new_cells,*_=candidate(obs)
            return (new_tools-old_tools).flatten()[search.MISSILE], (
                new_cells-old_cells).reshape(search.tr.NU,search.tr.NC)[search.MISSILE]
        candidate.missile_charges=1.
        self.assertAlmostEqual(difference()[0].item(),-4.,places=5)
        candidate.missile_charges=2.
        self.assertAlmostEqual(difference()[0].item(),-2.,places=5)
        obs[...,search.GRID_START+search.tr.NC]=12.
        delta,cells=difference()
        self.assertGreater(delta,-.01)
        self.assertGreater(cells[0],3.9)
        self.assertEqual(cells[1],0.)

    def test_refuge_size_trial_keeps_other_decisions_fixed(self):
        parent=dict(refuge=dict(scale=1.,aspect=.8,defense_weight=.16),plan=[1])
        candidate=search.l1_candidate(parent,np.random.default_rng(7))
        self.assertNotEqual(candidate['refuge']['scale'],parent['refuge']['scale'])
        candidate['refuge']['scale']=1.
        self.assertEqual(parent,candidate)

    def test_batch_headroom_refusal_does_not_submit_any_game(self):
        jobs = [('a', {}, None, 10), ('b', {}, None, 11)]
        with (patch.object(search.operator, 'require_resource_headroom',
                           side_effect=ValueError('Insufficient headroom')) as check,
              patch.object(search, 'as_completed', return_value=[]),
              patch.object(search, 'ProcessPoolExecutor') as pool):
            with self.assertRaisesRegex(ValueError, 'headroom'):
                list(search.completed_rollouts(pool, jobs))
            check.assert_called_once_with(len(jobs))
            pool.submit.assert_not_called()

    def test_completed_results_keep_their_copy_and_error_when_workers_finish_out_of_order(self):
        a,b=Future(),Future()
        a.set_result({'copy':'a'})
        b.set_exception(RuntimeError('no board'))
        jobs=[('a',{},None,10),('b',{},None,11)]
        with (patch.object(search.operator, 'require_resource_headroom'),
              patch.object(search, 'as_completed', return_value=[b, a]),
              patch.object(search, 'ProcessPoolExecutor') as pool):
            pool.submit.side_effect=[a,b]
            completed=list(search.completed_rollouts(pool,jobs,[1,2],2,True))
        self.assertEqual(completed[0][0],jobs[1])
        self.assertEqual(completed[0][2]['failed_stage'],2)
        self.assertEqual(completed[0][2]['error'],'no board')
        self.assertEqual(completed[1][2],{'copy':'a'})
    def test_every_campaign_worker_publishes_at_its_assigned_rate(self):
        jobs = [('baseline', {}, None, 10), ('candidate', {}, {'plan': []}, 11),
                ('other', {}, None, 12)]
        for training, expected in ((True, [.2, 1.]), (False, [1., 1.])):
            with (self.subTest(training=training),
                  patch.object(search.operator, 'require_resource_headroom'),
                  patch.object(search, 'ProcessPoolExecutor') as pool):
                futures = [Future() for _ in jobs]
                for future in futures:
                    future.set_result({})
                pool.submit.side_effect = futures
                list(search.completed_rollouts(pool, jobs, training=training))
                selected = {call.args[1][0]: call.kwargs['observer_interval']
                            for call in pool.submit.call_args_list if call.kwargs['observe']}
                self.assertEqual(selected, {'candidate': expected[0], 'baseline': expected[1], 'other': expected[1]})

    def test_default_rollout_and_ppo_batch_stop_on_qualifying_l1_win(self):
        row=dict(scenario=1,end='won',saved_frac=.43,advance=True,win=True,
                 campaign='Boston',board_id='b',board={'scenario':1,'scenario_count':5},
                 sim=100,trail=[],civ0=100,us=[],cs=[],log_started=True,battle_actions={})
        with patch.object(search.zar_boot,'boot'),patch.object(search.zar_boot,'stop'),              patch.object(search.operator,'owned_copy'),patch.object(search.tr,'run_episode',return_value=row) as run:
            row['ready_stats'] = dict(money=2100, stock=dict(mortar=1))
            row['ready_paint_tiles'] = dict(spikes=45, oil=0)
            row['paid_buildings'] = dict(Garrison=1)
            row['unconfirmed_buildings'] = dict(Garrison=2)
            row['building_receipts'] = [dict(decision=4, tool='garrison', cell=19, spend=85.2)]
            result=search.rollout(('inst13',{},None,10))
            self.assertEqual([level['stage'] for level in result['levels']],[1])
            self.assertEqual(result['levels'][0]['ready_stats'], row['ready_stats'])
            self.assertEqual(result['levels'][0]['ready_paint_tiles'], row['ready_paint_tiles'])
            self.assertEqual(result['levels'][0]['paid_buildings'], dict(Garrison=1))
            self.assertEqual(result['levels'][0]['unconfirmed_buildings'], dict(Garrison=2))
            self.assertEqual(result['levels'][0]['building_receipts'], row['building_receipts'])
            self.assertTrue(run.call_args.args[0][4]['placement_feedback'])
            worker = result['timing']
            episode = result['levels'][0]['timing']
            stamps = [worker['started'], worker['board_ready'], episode['started'],
                      episode['finished'], worker['finished']]
            self.assertEqual(stamps, sorted(stamps))
            self.assertIsNone(episode['battle_started'])
            self.assertEqual(run.call_args.args[0][4]['paused_seconds'], 45)
            run.assert_called_once()
            run.reset_mock()
            jobs=[(123,{},False,'test',{})]*2
            self.assertEqual(search.tr.run_batch(jobs),[row])
            run.assert_called_once()
            with self.assertRaisesRegex(ValueError,'explicit campaign progression'):
                search.rollout(('inst13',{},None,10),start_stage=2)

    def test_later_retries_are_training_only_and_keep_stage_identity(self):
        for retries,count in [(0,2),(2,4)]:
            with self.subTest(retries=retries):
                rows=[dict(scenario=stage,end=end,saved_frac=saved,bootstrap=0.,
                           advance=end=='won',win=end=='won',campaign='Boston',board_id='b',
                           board={'scenario_count':5},sim=10,trail=[],civ0=100,
                           us=[],cs=[],log_started=True,battle_actions={})
                      for stage,end,saved in [(1,'won',.4),(2,'aborted',.1),
                                               (2,'won',.36),(3,'timeout',None)]]
                with patch.object(search.zar_boot,'boot'), patch.object(search.zar_boot,'stop'), \
                     patch.object(search.operator,'owned_copy'), patch.object(search.tr,'run_episode',side_effect=rows):
                    result=search.rollout(('inst14',{},None,10),retries,allow_progression=True)
                expected=[(1,0,'fresh'),(2,0,'next_level'),(2,1,'carry'),(3,0,'next_level')]
                self.assertEqual([(r['stage'],r['attempt'],r['start_kind']) for r in result['levels']],expected[:count])

    def test_early_loadout_changes_only_one_affordable_purchased_preference(self):
        rng = np.random.default_rng(17)
        team = search.random_team(rng)
        team['plan'][0].update(family=2, tool=search.tr.TOOLS.index('buy_Demolition'))
        options = {
            'Demolition': {'cost': 1., 'first_effect': 20.},
            'Police': {'cost': 1., 'first_effect': 8.},
            'CallArms': {'cost': 2., 'first_effect': 0.},
            'Firebomb': {'cost': 1., 'first_effect': 42.},
        }
        row = dict(stage=1, start_kind='fresh', saved=.0916, outbreak={'seed': 123},
                   opening_loadout=options, ready_loadout={'Demolition': 20., 'Firebomb': 42.})
        trial = dict(team=team, levels=[row])
        variant = search.early_loadout_candidate(trial, rng)
        self.assertIsNotNone(variant)
        self.assertEqual(search.tr.TOOLS[variant['plan'][0]['tool']], 'buy_Police')
        variant['plan'][0]['tool'] = team['plan'][0]['tool']
        self.assertEqual(variant, team)
        row['ready_loadout']['Police'] = 8.
        self.assertIsNone(search.early_loadout_candidate(trial, rng))
        row['ready_loadout'].pop('Police')
        row['saved'] = None
        self.assertIsNone(search.early_loadout_candidate(trial, rng))

    def test_loadout_explores_an_affordable_replacement_before_first_breach(self):
        rng = np.random.default_rng(19)
        team = search.random_team(rng)
        police, missile = [search.tr.TOOLS.index('buy_' + name) for name in ('Police', 'Missile')]
        team['plan'] = [dict(search.gene(rng), tool=police, family=2, duration=1)]
        row = dict(stage=1, start_kind='fresh', saved=.10, outbreak={'seed': 19},
                   ready_loadout={'Police': 8.}, ready_loadout_sp=1.,
                   opening_loadout={'Police': {'cost': 1., 'first_effect': 8.},
                                    'Missile': {'cost': 2., 'first_effect': 32.5},
                                    'Bomber': {'cost': 2., 'first_effect': 60.}},
                   shelter={'first_occupied_breach': 49.9})
        trial = dict(team=team, levels=[row])
        candidate = search.early_loadout_candidate(trial, rng)
        self.assertEqual(candidate, dict(team, plan=[dict(team['plan'][0], tool=missile)]))

        for mutation in (dict(ready_loadout_sp=0.), dict(ready_loadout_sp=None),
                         dict(shelter={'first_occupied_breach': 32.5}), dict(shelter={})):
            with self.subTest(mutation=mutation):
                self.assertIsNone(search.early_loadout_candidate(
                    dict(trial, levels=[dict(row, **mutation)]), rng))
        self.assertEqual(team['plan'][0]['tool'], police)

    def test_loadout_proposal_is_reproducible_and_preserves_champion(self):
        rng=np.random.default_rng(23)
        parent=search.random_team(rng)
        before=copy.deepcopy(parent)
        candidate=search.loadout_candidate(parent,np.random.default_rng(11))
        self.assertEqual(candidate,search.loadout_candidate(parent,np.random.default_rng(11)))
        self.assertEqual(before,parent)
        self.assertEqual(candidate['plan'][1:],parent['plan'])
        pick=candidate['plan'][0]
        self.assertTrue(search.tr.TOOLS[pick['tool']].startswith('buy_'))
        self.assertEqual(pick['duration'],1)

    def test_practice_continues_only_the_requested_stage_and_labels_it(self):
        row=dict(scenario=2,end='aborted',saved_frac=.09,advance=False,win=False,
                 campaign='Boston',board_id='b',board={'scenario_count':5},sim=80,
                 trail=[],civ0=100,us=[],cs=[],log_started=True,battle_actions={})
        with patch.object(search.zar_boot,'boot') as boot, patch.object(search.zar_boot,'stop'), \
             patch.object(search.operator,'owned_copy',return_value='copy'), patch.object(search.tr,'run_episode',return_value=row) as run:
            env=boot.return_value
            env.dump.return_value={'where':{'stage':'1 (stage 2 of 5)'}}
            result=search.rollout(('inst14',{},None,10),start_stage=2,allow_progression=True)
            self.assertEqual(result['levels'][0]['start_kind'],'continue')
            boot.assert_called_once_with('copy',('campaign','continue'),discard_dump_states=True)
            env.dump.return_value={'where':{'stage':'0 (stage 1 of 5)'}}
            mismatch=search.rollout(('inst14',{},None,10),start_stage=2,allow_progression=True)
            self.assertIn('Expected live Boston stage 2',mismatch['error'])
            self.assertEqual(mismatch['failed_stage'],2)
            run.assert_called_once()

    def test_preparation_failure_retains_the_preceding_qualifying_win(self):
        row=dict(scenario=1,end='won',saved_frac=.43,advance=True,win=True,
                 campaign='Boston',board_id='b',board={'scenario_count':5},sim=100,
                 trail=[],civ0=100,us=[],cs=[],log_started=True,battle_actions={})
        with patch.object(search.zar_boot,'boot') as boot,patch.object(search.zar_boot,'stop') as stop, \
             patch.object(search.operator,'owned_copy'),patch.object(search.tr,'run_episode',return_value=row):
            boot.return_value.dump.side_effect=RuntimeError('lost planning receipt')
            team={'later_layouts':{'2':[{'kind':'mortar','points':[[10,20]]}]}}
            result=search.rollout(('inst13',{},team,10),allow_progression=True)
            self.assertEqual(result['levels'][0]['saved'],.43)
            self.assertEqual(result['failed_stage'],2)
            self.assertEqual(result['error'],'lost planning receipt')
            stop.assert_called_once_with(boot.return_value)

    def test_slow_process_exit_does_not_erase_a_confirmed_score(self):
        row=dict(scenario=1,end='won',saved_frac=.22,advance=False,win=True,
                 campaign='Boston',board_id='b',board={'scenario_count':5},sim=100,
                 trail=[],civ0=100,us=[],cs=[],log_started=True,battle_actions={})
        with patch.object(search.zar_boot,'boot'),patch.object(search.zar_boot,'stop',side_effect=search.psutil.TimeoutExpired(30)), \
             patch.object(search.operator,'owned_copy'),patch.object(search.tr,'run_episode',return_value=row):
            result=search.rollout(('inst13',{},None,10))
            self.assertIn('cleanup_error',result)
            self.assertEqual(result['levels'][0]['saved'],.22)

    def test_training_reuses_an_actual_below_target_l1_win_to_reach_l2(self):
        row=dict(scenario=1,end='won',saved_frac=.24,advance=False,win=True,
                 campaign='Boston',board_id='b',board={'scenario_count':5},sim=100,
                 trail=[],civ0=100,us=[],cs=[],log_started=True,battle_actions={})
        rows=[row,dict(row,saved_frac=.4,advance=True),dict(row,scenario=2,end='timeout',
                                                           saved_frac=None,win=False,bootstrap=0.)]
        with patch.object(search.zar_boot,'boot'),patch.object(search.zar_boot,'stop'), \
             patch.object(search.operator,'owned_copy'),patch.object(search.tr,'run_episode',side_effect=rows):
            result=search.rollout(('inst14',{},None,10),2,training=True,practice_retry=True,allow_progression=True)
        self.assertEqual([(r['stage'],r['start_kind']) for r in result['levels']],
                         [(1,'fresh'),(1,'carry'),(2,'next_level')])

    def test_tool_and_cell_heads_keep_the_trainer_contract(self):
        candidate=search.random_team(np.random.default_rng(4))
        net=search.TeamPolicy(candidate)
        obs=torch.zeros(1,1,search.tr.NOBS)
        with torch.no_grad():
            net(obs)
            self.assertEqual(net.index,0)
            obs[...,search.tr.PLANNING_INDEX]=1
            u,c,value,h=net(obs)
            self.assertEqual(net.index,1)
            self.assertEqual(tuple(c.shape),(1,1,search.tr.NU*search.tr.NC))
            self.assertTrue(torch.isfinite(c).all())
            for _ in range(len(net.steps)):
                u,c,value,h=net(obs,h)
            self.assertEqual(int(u.argmax()),search.tr.TOOLS.index('ready'))

    def test_recombination_keeps_parent_and_donor_intact(self):
        rng=np.random.default_rng(9)
        parent,donor=search.random_team(rng),search.random_team(rng)
        before=copy.deepcopy([parent,donor])
        child=search.offspring(parent,donor,rng)
        self.assertNotEqual(child,parent)
        self.assertEqual([parent,donor],before)

    def test_legacy_battle_controls_and_pause_state(self):
        team=search.random_team(np.random.default_rng(7))
        del team['camera_pause']
        old=search.TeamPolicy(team)
        changed=search.TeamPolicy(dict(team,camera_pause=[1.,2.,3.,4.,5.,6.]))
        changed.load_state_dict(old.state_dict())
        with torch.no_grad():
            obs=torch.zeros(1,1,search.tr.NOBS)
            for paused in (0,1):
                obs[...,search.PAUSED]=paused
                diff=(changed(obs)[0]-old(obs)[0]).flatten()
                torch.testing.assert_close(diff[search.PAN],torch.arange(1.,5.))
                self.assertAlmostEqual(diff[search.PAUSE].item(),5.+paused,places=5)

    def test_candidate_repair_preference_applies_only_to_blocked_planning(self):
        team=search.random_team(np.random.default_rng(13))
        team['plan']=[]
        tool=team.pop('blocked_tool')
        base=search.TeamPolicy(team)
        repair=search.TeamPolicy(dict(team,blocked_tool=tool))
        repair.load_state_dict(base.state_dict())
        with torch.no_grad():
            x=torch.zeros(1,1,search.tr.NOBS)
            for planning,legal,expected in [(1,0,12.),(1,1,0.),(0,0,0.)]:
                x[...,search.tr.PLANNING_INDEX]=planning
                x[...,search.READY_LEGAL]=legal
                diff=(repair(x)[0]-base(x)[0]).flatten()
                self.assertAlmostEqual(diff[tool].item(),expected,places=4)

    def test_later_stage_without_archived_layout_cannot_mutate_l1(self):
        rng=np.random.default_rng(32)
        parent=search.random_team(rng)
        child=search.offspring(parent,parent,rng,stage=2)
        overrides=child.pop('stage_battle')
        self.assertIn('2',overrides)
        self.assertEqual(parent,child)

    def test_later_stage_search_preserves_earlier_policy(self):
        rng=np.random.default_rng(32)
        parent=search.random_team(rng)
        parent['later_layouts']={'2':[{'kind':'mortar','points':[[12,5]]},
                                     {'kind':'garrison','points':[[20,15]]}]}
        child=search.offspring(parent,parent,rng,stage=2)
        for key in ('plan','cast_bias','idle_bias','battle'):
            self.assertEqual(child[key],parent[key])
        self.assertIn('2',child['stage_battle'])

    def test_budget_candidate_learns_only_from_identified_overdraft(self):
        team={'later_layouts':{'2':[{'kind':'zone','points':[[0,1],[2,3],[4,1]]}]}}
        loss={'kind':'zone','before':11.875,'after':-898.05}
        stages=[dict(stage=2,layout_receipts=[loss])]
        child=search.budget_candidate(team,stages)
        self.assertAlmostEqual(child['later_layouts']['2'][0]['observed_cost'],909.925)
        self.assertNotIn('observed_cost',team['later_layouts']['2'][0])
        team['later_layouts']['2'].append({'kind':'zone','points':[[5,6],[7,8],[9,6]]})
        self.assertIsNone(search.budget_candidate(team,stages))
        loss['world_points']=team['later_layouts']['2'][1]['points']
        child=search.budget_candidate(team,stages)
        self.assertNotIn('observed_cost',child['later_layouts']['2'][0])
        self.assertIn('observed_cost',child['later_layouts']['2'][1])

    def test_cost_observed_by_another_team_transfers_only_to_matching_stage_and_placement(self):
        action={'kind':'zone','points':[[0,0],[1,1],[2,0]]}
        parent={'layout':[action],'later_layouts':{'2':[action]}}
        prices={}
        search.budget_candidate(parent,[dict(stage=2,layout_receipts=[dict(kind='zone',before=20,after=-80)])],prices)
        team={'layout':[action],'later_layouts':{'2':[dict(kind='wall',points=[[0,0],[2,0]]),action]}}
        prices=search.json.loads(search.json.dumps(prices))
        child=search.budget_candidate(team,[],prices)
        self.assertEqual(child['later_layouts']['2'][1]['observed_cost'],100)
        self.assertNotIn('observed_cost',child['layout'][0])
        self.assertNotIn('observed_cost',child['later_layouts']['2'][0])

    def test_layout_search_can_learn_new_coordinates_without_distorting_shapes(self):
        original=[dict(kind='wall',points=[[0,0],[15,20]]), dict(kind='mortar',points=[[80,50]])]
        sizes=set()
        moved=False
        for seed in range(64):
            layout=copy.deepcopy(original)
            search.vary_layout(layout,np.random.default_rng(seed))
            sizes.add(len(layout))
            for item in layout:
                if item['kind']=='wall':
                    np.testing.assert_allclose(np.diff(item['points'],axis=0),[[15,20]])
                    moved |= item['points']!=original[0]['points']
        self.assertEqual(sizes,{1,2,3})
        self.assertTrue(moved)

    def test_search_can_change_bulk_purchase_allocation(self):
        original=[dict(kind=k,points=[[i,0]]) for i,k in enumerate(['wall','mortar']*10)]
        outcomes=[]
        for seed in range(64):
            layout=copy.deepcopy(original)
            search.vary_layout(layout,np.random.default_rng(seed))
            outcomes.append([a['kind'] for a in layout])
        self.assertTrue(any(len(o)<17 for o in outcomes))
        self.assertTrue(any(len(set(o[:10]))==1 for o in outcomes))

    def test_zone_scaling_explores_both_sizes_about_the_same_center(self):
        zone={'kind':'zone','observed_cost':100,'points':[[0,0],[10,0],[10,10],[0,10]]}
        widths=[]
        for seed in range(128):
            layout=[copy.deepcopy(zone)]
            search.vary_layout(layout,np.random.default_rng(seed))
            if not np.isclose(np.ptp(np.asarray(layout[0]['points'])[:,0]),10):
                points=np.asarray(layout[0]['points'])
                np.testing.assert_allclose(points.mean(axis=0),[5,5])
                widths.append(np.ptp(points[:,0]))
        self.assertLess(min(widths),10)
        self.assertGreater(max(widths),10)

    def test_time_in_pause_adds_no_survival_credit(self):
        row=dict(advance=False,win=False,saved_frac=.1,civ0=100,
                 trail=[(0,100),(10,80),(10,80),(20,60)])
        self.assertAlmostEqual(search.score(row)[-1],14/120)
        row.update(win=True,advance=True,saved_frac=.51)
        self.assertEqual(search.score(row)[:3],[1,1,.51])
