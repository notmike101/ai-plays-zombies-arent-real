"""Game-free checks for genome search, independent team state and outcome scoring."""
import copy
import unittest
from unittest.mock import patch
import numpy as np
import torch
import team_search as search


class SearchTests(unittest.TestCase):
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
                    result=search.rollout(('inst14',{},None,10),retries)
                expected=[(1,0,'fresh'),(2,0,'next_level'),(2,1,'carry'),(3,0,'next_level')]
                self.assertEqual([(r['stage'],r['attempt'],r['start_kind']) for r in result['levels']],expected[:count])

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

    def test_later_stage_search_preserves_earlier_policy(self):
        rng=np.random.default_rng(32)
        parent=search.random_team(rng)
        parent['later_layouts']={'2':[{'kind':'mortar'},{'kind':'garrison'}]}
        child=search.offspring(parent,parent,rng,stage=2)
        for key in ('plan','cast_bias','idle_bias','battle'):
            self.assertEqual(child[key],parent[key])
        self.assertIn('2',child['stage_battle'])

    def test_time_in_pause_adds_no_survival_credit(self):
        row=dict(advance=False,win=False,saved_frac=.1,civ0=100,
                 trail=[(0,100),(10,80),(10,80),(20,60)])
        self.assertAlmostEqual(search.score(row)[-1],14/120)
        row.update(win=True,advance=True,saved_frac=.51)
        self.assertEqual(search.score(row)[:3],[1,1,.51])
