import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
import numpy as np
import team_search
import nn_play2 as train
import checkpoints as cp


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root/'model.pt'
        net = train.PolicyNet2()
        opt = torch.optim.Adam(net.parameters())
        sum(p.square().sum() for p in net.parameters()).backward(); opt.step()
        train.save_checkpoint(net, opt, self.model, 'fixture')

    def snapshot(self):
        with patch.object(cp, 'source_record', return_value={'commit':'a'*40}), \
             patch.object(cp, 'HISTORY', self.root/'no-history'):
            return cp.snapshot(self.model, self.root/'exports')

    def test_snapshot_is_immutable_verified_and_idempotent(self):
        before = self.model.read_bytes()
        bundle = self.snapshot()
        first = (bundle/'manifest.json').read_bytes()
        self.assertEqual(cp.verify_bundle(bundle)['checkpoint_sha256'], cp.sha(before))
        self.assertEqual(self.snapshot(), bundle)
        self.assertEqual((bundle/'manifest.json').read_bytes(), first)
        self.assertEqual(self.model.read_bytes(), before)
        self.assertIn('not_evaluation', json.loads(first)['metrics'])
        (bundle/'nn_policy4.pt').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'): cp.verify_bundle(bundle)

    def test_import_refuses_active_writer_and_existing_destination(self):
        bundle = self.snapshot()
        target = self.root/'restored.pt'
        with patch('local_agent.inventory', return_value=[{'role':'trainer'}]):
            with self.assertRaisesRegex(ValueError, 'active'): cp.import_bundle(bundle, target)
            self.assertFalse(target.exists())
        with patch('local_agent.inventory', return_value=[]):
            cp.import_bundle(bundle, target)
            self.assertEqual(target.read_bytes(), self.model.read_bytes())
            with self.assertRaises(FileExistsError): cp.import_bundle(bundle, target)

    def test_unexpected_checkpoint_fields_cannot_be_published(self):
        data = torch.load(self.model, weights_only=True)
        data['private_notes'] = 'not for publication'
        torch.save(data, self.model)
        with self.assertRaisesRegex(ValueError, 'Unexpected'): self.snapshot()

    def test_campaign_bundle_resumes_current_team_and_changes_when_only_strategy_changes(self):
        net=train.PolicyNet2()
        train.load_pretrained(net,self.model)
        base=train.policy_id(net)
        team=team_search.random_team(np.random.default_rng(3))
        source=self.root/'coverage-team-test'/'champion.json'
        source.parent.mkdir()
        def store():
            source.write_text(json.dumps(dict(base=base,team_id=team_search.team_id(team),team=team,
                                              generation=12,private_notes='never export')))
        store()
        first=self.snapshot()
        self.assertEqual(first,self.snapshot())
        self.assertNotIn('private_notes',(first/'manifest.json').read_text())
        restored=train.PolicyNet2()
        self.assertEqual(team_search.restore_team(restored,first),team)
        self.assertEqual(train.policy_id(restored),base)
        team['idle_bias']+=1
        store()
        second=self.snapshot()
        self.assertNotEqual(first,second)
        self.assertEqual((first/'nn_policy4.pt').read_bytes(),(second/'nn_policy4.pt').read_bytes())
        team['comment']='private'
        store()
        with self.assertRaisesRegex(ValueError,'Unexpected campaign strategy fields'):self.snapshot()

    def test_published_release_is_verified_without_mutating_it(self):
        bundle = self.snapshot()
        with patch.object(cp, 'release_info', return_value={'isDraft':False,'url':'https://example.test/release'}), \
             patch.object(cp, 'download_verified', return_value=cp.verify_bundle(bundle)) as download, \
             patch.object(cp, 'gh') as gh:
            result = cp.publish(bundle)
            self.assertEqual(result['status'], 'already_published')
            download.assert_called_once()
            gh.assert_not_called()


if __name__ == '__main__': unittest.main()
