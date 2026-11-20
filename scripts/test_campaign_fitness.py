import unittest

import campaign_fitness as fitness


class FreshEvidence(unittest.TestCase):
    def setUp(self):
        self.data={}
        self.a={'plan':[],'later_layouts':{'2':['zone']}}
        self.b={'plan':[],'later_layouts':{'2':['other']}}
        self.c={'plan':['another']}

    def row(self,seed,saved,stage=1,kind='fresh',attempt=0):
        return dict(stage=stage,start_kind=kind,attempt=attempt,end='won' if saved else 'timeout',
                    saved=saved,outbreak={'seed':seed},log_started=seed)

    def record(self,team,*rows,**kwargs):
        fitness.record(self.data,dict(copy='inst1',team=team,levels=rows,**kwargs))

    def test_outside_actions_reduce_search_fitness_without_changing_official_score(self):
        self.record(self.a,dict(self.row(17,.36),outside_playarea_actions=5,playarea_cost=.004))
        result=fitness.stats(self.data,self.a,1)
        self.assertEqual(result['wins'],1)
        self.assertEqual(result['mean'],.36)
        self.assertAlmostEqual(result['objective'],.34)

    def test_replication_nominates_promising_low_sample_distinct_policy(self):
        self.record(self.a,self.row(1,.41))
        self.record(self.c,self.row(2,.33))
        self.assertIs(fitness.replication_candidate(self.data,[self.a,self.c],[]),self.a)
        self.assertIs(fitness.replication_candidate(self.data,[self.a,self.c],[self.b]),self.c)
        for seed in range(3,6):
            self.record(self.c,self.row(seed,.36))
        self.assertIsNone(fitness.replication_candidate(self.data,[self.a,self.c],[self.b]))

    def test_only_uninterrupted_fresh_prefix_counts(self):
        self.record(self.a,self.row(1,.2),self.row(2,.6,kind='carry',attempt=1),
                    self.row(3,.7,2,'next_level'))
        self.record(self.a,self.row(4,.7,2,'continue'),start_stage=2)
        self.record(self.a,self.row(5,.7),arm='candidate')
        self.assertEqual(fitness.stats(self.data,self.a,1)['wins'],0)
        self.assertEqual(fitness.stats(self.data,self.a,2)['starts'],0)

    def test_pool_only_equivalent_stage_behavior_and_count_each_outbreak_once(self):
        for team in (self.a,self.b):
            self.record(team,self.row(1,.5),self.row(3,.6,2,'next_level'))
        self.assertEqual(fitness.stats(self.data,self.b,1)['starts'],1)
        self.assertEqual(fitness.stats(self.data,self.c,1)['starts'],0)
        self.assertNotEqual(fitness.prefix_id(self.a,2),fitness.prefix_id(self.b,2))
        self.assertNotEqual(fitness.prefix_id(self.c,1),fitness.prefix_id(self.c,2))
        self.assertIs(fitness.promote(self.data,self.a,self.c),self.c)
        self.record(self.b,self.row(2,.4))
        self.assertIs(fitness.promote(self.data,self.a,self.c),self.a)
        self.assertIs(fitness.promote(self.data,self.b,self.a),self.a)

    def test_consistency_beats_one_peak_and_accounts_for_failures(self):
        self.record(self.c,self.row(80,.9))
        for seed in range(5):
            self.record(self.a,self.row(seed,.36 if seed<3 else None))
        self.assertGreater(fitness.ranking(self.data,self.a),fitness.ranking(self.data,self.c))
        self.record(self.c,self.row(81,.9))
        for seed in range(20):
            self.record(self.c,self.row(seed,.1))
        self.assertIs(fitness.promote(self.data,self.c,self.a),self.a)

    def test_l1_proposals_distinguish_failed_battles_without_promoting_them(self):
        self.record(self.a, dict(self.row(1, .099), end='aborted', score=[0, 0, 0, .13]))
        self.record(self.c, dict(self.row(2, .094), end='aborted', score=[0, 0, 0, .32]))
        rank = lambda team: fitness.l1_proposal_rank(self.data, team)
        self.assertGreater(rank(self.c), rank(self.a))
        key = fitness.prefix_id(self.c, 1)
        self.data[key]['seed/2'] = self.data[key]['seed/2'][:3]
        self.assertLess(rank(self.c), rank(self.a))
        self.record(self.c, dict(self.row(2, .094), end='aborted', score=[0, 0, 0, .32]))
        self.assertGreater(rank(self.c), rank(self.a))
        self.assertEqual(fitness.stats(self.data, self.c, 1)['starts'], 1)
        self.assertIs(fitness.promote(self.data, self.c, self.a), self.a)
        self.record(self.a, dict(self.row(3, .23), score=[0, 1, .23, .19]))
        self.assertGreater(rank(self.a), rank(self.c))
        self.assertEqual(fitness.stats(self.data,self.a,1)['wins'], 0)

    def test_unscored_pause_cannot_outrank_a_scored_battle(self):
        paused = dict(self.row(11, None), score=[0, 0, 0, .5])
        scored = dict(self.row(12, .099), end='aborted', score=[0, 0, 0, .16])
        self.record(self.a, paused)
        self.record(self.c, scored)
        self.assertGreater(fitness.l1_proposal_rank(self.data, self.c),
                           fitness.l1_proposal_rank(self.data, self.a))
        self.record(self.a, dict(self.row(13, 0.), end='lost', score=[0, 0, 0, .4]))
        self.assertAlmostEqual(fitness.l1_proposal_rank(self.data, self.a)[2], .2)
        key = fitness.prefix_id(self.a, 1)
        self.data[key]['seed/11'] = self.data[key]['seed/11'][:5]
        self.assertAlmostEqual(fitness.l1_proposal_rank(self.data, self.a)[2], .2)

    def test_holdout_refuses_an_outbreak_already_used_for_discovery(self):
        rows = [dict(arm=arm, levels=[self.row(seed, saved)]) for arm, seed, saved in (
            ('candidate', 11, .39), ('candidate', 12, .42),
            ('incumbent', 19, .20), ('incumbent', 20, .18),
        )]
        self.assertTrue(fitness.holdout_passed(rows, 2, discovery_seeds={1, 2}))
        self.assertFalse(fitness.holdout_passed(rows, 2, discovery_seeds={1, 11}))
        self.assertFalse(fitness.holdout_passed(rows, 2, discovery_seeds={20}))
        rows[-1]['levels'][0].update(end='timeout', saved=None)
        self.assertFalse(fitness.holdout_passed(rows, 2))

    def test_holdout_needs_complete_arms_and_two_distinct_qualifying_outbreaks(self):
        rows=[dict(arm=arm,levels=[self.row(i,value)]) for i,(arm,value) in enumerate(
            [('candidate',.39),('incumbent',.18),('candidate',.37),('incumbent',.36)])]
        self.assertTrue(fitness.holdout_passed(rows,2))
        self.assertFalse(fitness.holdout_passed(rows[:-1],2))
        rows[2]['levels'][0]['outbreak']['seed']=0
        self.assertFalse(fitness.holdout_passed(rows,2))
