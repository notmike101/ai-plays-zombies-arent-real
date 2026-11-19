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

    def test_practice_continues_only_the_requested_stage_and_labels_it(self):
        row=dict(scenario=2,end='aborted',saved_frac=.09,advance=False,win=False,
                 campaign='Boston',board_id='b',board={'scenario_count':5},sim=80,
                 trail=[],civ0=100,us=[],cs=[],log_started=True,battle_actions={})
        with patch.object(search.zar_boot,'boot') as boot, patch.object(search.zar_boot,'stop'), \
             patch.object(search.operator,'owned_copy',return_value='copy'), patch.object(search.tr,'run_episode',return_value=row) as run:
            env=boot.return_value
            env.dump.return_value={'where':{'stage':'1 (stage 2 of 5)'}}
            result=search.rollout(('inst14',{},None,10),start_stage=2)
            self.assertEqual(result['levels'][0]['start_kind'],'continue')
            boot.assert_called_once_with('copy',('campaign','continue'),discard_dump_states=True)
            env.dump.return_value={'where':{'stage':'0 (stage 1 of 5)'}}
            with self.assertRaisesRegex(RuntimeError,'Expected live Boston stage 2'):
                search.rollout(('inst14',{},None,10),start_stage=2)
            run.assert_called_once()

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

    def test_later_stage_search_preserves_earlier_policy(self):
        rng=np.random.default_rng(32)
        parent=search.random_team(rng)
        parent['later_layouts']={'2':[{'kind':'mortar','points':[[12,5]]},
                                     {'kind':'garrison','points':[[20,15]]}]}
        child=search.offspring(parent,parent,rng,stage=2)
        for key in ('plan','cast_bias','idle_bias','battle'):
            self.assertEqual(child[key],parent[key])
        self.assertIn('2',child['stage_battle'])

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

    def test_time_in_pause_adds_no_survival_credit(self):
        row=dict(advance=False,win=False,saved_frac=.1,civ0=100,
                 trail=[(0,100),(10,80),(10,80),(20,60)])
        self.assertAlmostEqual(search.score(row)[-1],14/120)
        row.update(win=True,advance=True,saved_frac=.51)
        self.assertEqual(search.score(row)[:3],[1,1,.51])
