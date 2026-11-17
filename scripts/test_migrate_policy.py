import copy
import unittest
import tempfile
from pathlib import Path
import torch
from torch import nn
import nn_play2 as train
from migrate_policy import migrate, migrate_file


class MigrationTests(unittest.TestCase):
    def source(self):
        old=nn.Module();old.gru=nn.GRU(332,128,1,batch_first=True)
        old.hu=nn.Linear(128,72);old.hc=nn.Linear(128,72*48);old.val=nn.Linear(128,1)
        opt=torch.optim.Adam(old.parameters())
        sum(p.sum() for p in old.parameters()).backward();opt.step()
        schema=train.checkpoint_schema()
        return old,dict(policy=old.state_dict(),optimizer=opt.state_dict(),learning=train.learning_config(),
            schema=dict(version=3,inputs=schema['inputs'][:332],tools=schema['tools'][:72],cells=schema['cells'][:72*48]),run_id='test')

    def test_preserves_recurrent_outputs_old_heads_and_adam_prefixes(self):
        old,data=self.source();before=copy.deepcopy(data);converted=migrate(data)
        new=train.PolicyNet2();new.load_state_dict(converted['policy'])
        x=torch.randn(1,3,332);expanded=torch.cat([x,torch.randn(1,3,train.NOBS-332)],-1)
        with torch.no_grad():
            a,ha=old.gru(x);b,hb=new.gru(expanded)
            # A wider matrix selects different BLAS accumulation blocks.
            torch.testing.assert_close(a,b,rtol=1e-5,atol=1e-6)
            torch.testing.assert_close(ha,hb,rtol=1e-5,atol=1e-6)
            for name,size in [('hu',72),('hc',72*48),('val',1)]:
                torch.testing.assert_close(getattr(old,name)(a),getattr(new,name)(b)[...,:size])
        for name,source in data['policy'].items():
            target=converted['policy'][name]
            torch.testing.assert_close(source,target[tuple(slice(0,n) for n in source.shape)],rtol=0,atol=0)
        for ident,state in data['optimizer']['state'].items():
            torch.testing.assert_close(state['step'],converted['optimizer']['state'][ident]['step'])
            for key in ('exp_avg','exp_avg_sq'):
                target=converted['optimizer']['state'][ident][key]
                slices=tuple(slice(0,n) for n in state[key].shape)
                torch.testing.assert_close(state[key],target[slices],rtol=0,atol=0)
                torch.testing.assert_close(state[key],before['optimizer']['state'][ident][key],rtol=0,atol=0)
        opt=torch.optim.Adam(new.parameters());opt.load_state_dict(converted['optimizer'])
        sum(p.sum() for p in new.parameters()).backward();opt.step()

    def test_reordered_meaning_or_missing_optimizer_refused(self):
        _,data=self.source();data['schema']['inputs'][0]='changed meaning'
        with self.assertRaisesRegex(ValueError,'meanings'):migrate(data)
        _,data=self.source();data.pop('optimizer')
        with self.assertRaisesRegex(ValueError,'optimizer'):migrate(data)

    def test_file_migration_preserves_source_and_refuses_existing_destination(self):
        _,data=self.source()
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'v3.pt';destination=Path(folder)/'v4.pt'
            torch.save(data,source);before=source.read_bytes()
            migrate_file(source,destination)
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(torch.load(destination,weights_only=True)['schema']['version'],4)
            saved=destination.read_bytes()
            with self.assertRaises(FileExistsError):migrate_file(source,destination)
            with self.assertRaises(FileExistsError):migrate_file(source,source)
            self.assertEqual(destination.read_bytes(),saved)

    def test_schema_cannot_hide_truncated_weights(self):
        _,data=self.source();data['policy']['hu.weight']=data['policy']['hu.weight'][:1]
        with self.assertRaisesRegex(ValueError,'tensor shape'):migrate(data)


if __name__=='__main__':unittest.main()
