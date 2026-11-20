"""Game-free checks for genome search, independent team state and outcome scoring."""
import copy
import unittest
from unittest.mock import patch
from concurrent.futures import Future
import numpy as np
import torch
import team_search as search


class SearchTests(unittest.TestCase):
    def test_shadow_arms_vary_only_one_missile_preference(self):
        parent = search.random_team(np.random.default_rng(3))
        arms = search.shadow_variants(parent, np.random.default_rng(4))
        self.assertEqual(arms['control'], parent)
        for name, key in [('timing', 'cast_bias'), ('targeting', 'battle')]:
            candidate = arms[name]
            self.assertEqual({k for k in parent if candidate[k] != parent[k]}, {key})
            self.assertEqual([i for i, (a, b) in enumerate(zip(parent[key], candidate[key])) if a != b],
                             [search.MISSILE_ROW])

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
    def test_every_campaign_worker_publishes_at_its_assigned_rate(self):
        jobs = [('baseline', {}, None, 10), ('candidate', {}, {'plan': []}, 11),
                ('other', {}, None, 12)]
        for training, expected in ((True, [.2, 1.]), (False, [1., 1.])):
            with self.subTest(training=training), patch.object(search, 'ProcessPoolExecutor') as pool:
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
            result=search.rollout(('inst13',{},None,10))
            self.assertEqual([level['stage'] for level in result['levels']],[1])
            worker = result['timing']
            episode = result['levels'][0]['timing']
            stamps = [worker['started'], worker['board_ready'], episode['started'],
                      episode['finished'], worker['finished']]
            self.assertEqual(stamps, sorted(stamps))
            self.assertIsNone(episode['battle_started'])
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
