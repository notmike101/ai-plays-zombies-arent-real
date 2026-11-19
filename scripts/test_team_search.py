"""Game-free checks for genome search, independent team state and outcome scoring."""
import copy
import unittest
from unittest.mock import patch
from concurrent.futures import Future
import numpy as np
import torch
import team_search as search


class SearchTests(unittest.TestCase):
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
            args=['nn_play2','train','--pids','123','--model',str(base),'--history',str(hist),'--rounds','2']
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
        self.assertTrue(np.all(np.asarray(child['cast_bias'])>team['cast_bias']))
        child['cast_bias']=team['cast_bias']
        self.assertEqual(team,child)
        first['start_kind']='carry'
        self.assertIsNone(search.cast_candidate(trial,rng))
        first.update(start_kind='next_level',stage=2)
        self.assertIsNone(search.cast_candidate(trial,rng))

    def test_refuge_size_trial_keeps_other_decisions_fixed(self):
        parent=dict(refuge=dict(scale=1.,aspect=.8,defense_weight=.16),plan=[1])
        candidate=search.l1_candidate(parent,np.random.default_rng(7))
        self.assertNotEqual(candidate['refuge']['scale'],parent['refuge']['scale'])
        candidate['refuge']['scale']=1.
        self.assertEqual(parent,candidate)

    def test_completed_results_keep_their_copy_and_error_when_workers_finish_out_of_order(self):
        a,b=Future(),Future()
        a.set_result({'copy':'a'})
        b.set_exception(RuntimeError('no board'))
        jobs=[('a',{},None,10),('b',{},None,11)]
        with patch.object(search,'as_completed',return_value=[b,a]),patch.object(search,'ProcessPoolExecutor') as pool:
            pool.submit.side_effect=[a,b]
            completed=list(search.completed_rollouts(pool,jobs,[1,2],2,True))
        self.assertEqual(completed[0][0],jobs[1])
        self.assertEqual(completed[0][2]['failed_stage'],2)
        self.assertEqual(completed[0][2]['error'],'no board')
        self.assertEqual(completed[1][2],{'copy':'a'})
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
            mismatch=search.rollout(('inst14',{},None,10),start_stage=2)
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
            result=search.rollout(('inst13',{},team,10))
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
            result=search.rollout(('inst14',{},None,10),2,training=True)
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
