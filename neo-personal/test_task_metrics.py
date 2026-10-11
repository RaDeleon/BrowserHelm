import json
import tempfile
import time
import unittest
from pathlib import Path
from metrics import Metrics
from task_metrics import TOKEN_KEYS, claude_cost
from openragnar import OpenRagnarGateway

class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'metrics.sqlite'
        self.metrics=Metrics(self.path);self.metrics.start('claude-ai');self.ledger=self.metrics.tasks
    def tearDown(self): self.temp.cleanup()
    def start(self): return self.ledger.command({'action':'start','label':'Test prompt','session_id':self.metrics.sid,'model':'claude-opus-5.5','effort':'high'})['task_id']
    def record(self, tid, tool='run', events=None, status='ok'):
        now=time.time();self.metrics.record(dict(id=tool+str(now),task_id=tid,method='tools/call',tool=tool,started=now,finished=now+1,status=status,input_bytes=3,upstream_input_bytes=3,upstream_bytes=3,client_bytes=3,upstream_text=3,client_text=3,upstream_calls=1,provider_tokens=0,provider_calls=len(events or []),provider_unknown=0,media_count=0,provider_events=events or []))
    def test_one_prompt_not_one_session_and_failures_retained(self):
        first=self.start();self.record(first,status='error');self.record(first)
        self.ledger.command({'action':'finish','task_id':first,'status':'complete','verification':'independent'})
        second=self.start();self.record(second)
        rows={t['id']:t for t in self.ledger.snapshot()}
        self.assertEqual(rows[first]['tool_calls'],2);self.assertEqual(rows[first]['failures'],1)
        self.assertEqual(rows[second]['tool_calls'],1);self.assertIsNone(rows[first]['claude_cost'])
        self.assertIsNone(rows[first]['total_cost']);self.assertEqual(rows[first]['vision']['cost'],0)
    def test_reconnect_explicit_attach_no_cross_chat_guessing(self):
        tid=self.start();other=Metrics(self.path);other.start('claude-ai')
        self.assertIsNone(other.tasks.active(other.sid))
        self.ledger.command({'action':'attach','task_id':tid,'session_id':other.sid})
        self.assertEqual(other.tasks.active(other.sid),tid)
        self.ledger.command({'action':'finish','task_id':tid,'status':'failed'})
        self.assertIsNone(other.tasks.active(other.sid))
    def test_duplicate_task_and_independent_agent_claim_rejected(self):
        tid=self.start()
        with self.assertRaises(ValueError):self.start()
        with self.assertRaises(ValueError): self.ledger.command({'action':'finish','task_id':tid,'verification':'independent'},self.metrics.sid,'agent_marker')
    def test_reported_provider_cost_and_unknown_failed_cost_separate(self):
        tid=self.start();self.record(tid,events=[dict(kind='decision',provider='typesafe',model='jev-test',status='ok',usage={'input_tokens':10,'output_tokens':5,'cost':.0045}),dict(kind='vision',provider='openrouter',model='vision-test',status='error',usage={})])
        task=self.ledger.snapshot()[0]
        self.assertEqual(task['decision']['cost'],.0045);self.assertEqual(task['decision']['tokens'],15)
        self.assertIsNone(task['vision']['cost']);self.assertIsNone(task['vision']['tokens'])
        self.assertEqual(task['vision']['unknown_cost_calls'],1)
    def test_merged_usage_and_full_cost_only_with_all_categories(self):
        tid=self.start();usage={k:0 for k in TOKEN_KEYS};usage['input_tokens']=1000;usage['output_tokens']=200
        self.ledger.command({'action':'usage','task_id':tid,'usage':usage,'memory_cost':0})
        task=self.ledger.snapshot()[0];self.assertAlmostEqual(task['claude_cost'],.008);self.assertAlmostEqual(task['total_cost'],.008)
        self.ledger.command({'action':'usage','task_id':tid,'usage':{'input_tokens':1000,'output_tokens':200}})
        self.assertIsNone(self.ledger.snapshot()[0]['claude_cost'])
    def test_partial_provider_cost_keeps_known_subtotal(self):
        tid=self.start();self.record(tid,events=[dict(kind='decision',provider='typesafe',model='jev',status='ok',usage={'cost':.0045}),dict(kind='decision',provider='typesafe',model='jev',status='error',usage={})])
        task=self.ledger.snapshot()[0];self.assertIsNone(task['decision']['cost']);self.assertAlmostEqual(task['known_cost'],.0045)
    def test_provider_usage_sanitized_and_rate_estimate_labeled(self):
        tid=self.start();self.record(tid,events=[dict(kind='vision',provider='openrouter',model='vision',status='ok',usage={'prompt_tokens':100,'completion_tokens':10,'cost':float('nan'),'private':'never stored'})])
        self.ledger.command({'action':'usage','task_id':tid,'usage':{},'vision_input_rate':2,'vision_output_rate':10})
        task=self.ledger.snapshot()[0];self.assertAlmostEqual(task['vision']['cost'],.0003);self.assertEqual(task['vision']['cost_basis'],'rate_estimate')
        with self.ledger.db() as db: self.assertNotIn('private',db.execute('SELECT usage FROM provider_usage').fetchone()[0])
    def test_start_controls_and_late_reply_stay_on_original_task(self):
        tid=self.start();self.ledger.command({'action':'finish','task_id':tid});other=self.start();self.record(tid)
        self.assertEqual(next(t for t in self.ledger.snapshot() if t['id']==tid)['tool_calls'],1)
        self.assertEqual(next(t for t in self.ledger.snapshot() if t['id']==other)['tool_calls'],0)
    def test_missing_provider_event_never_means_free_cloud_call(self):
        tid=self.start();now=time.time()
        self.metrics.record(dict(id='missing',task_id=tid,method='tools/call',tool='openragnar_visual_act',started=now,finished=now,status='ok',provider_calls=1,input_bytes=3,client_text=3))
        task=self.ledger.snapshot()[0];self.assertEqual(task['vision']['calls'],1);self.assertIsNone(task['vision']['cost'])
    def test_local_api_zero_does_not_fabricate_tokens(self):
        tid=self.start();self.record(tid,events=[dict(kind='vision',provider='ollama',model='local',status='error',usage={})])
        t=self.ledger.snapshot()[0];self.assertEqual(t['vision']['cost'],0);self.assertIsNone(t['vision']['tokens'])
    def test_invalid_cost_and_tokens_rejected(self):
        tid=self.start()
        for v in [True,-1,1.2,float('nan')]:
            with self.assertRaises(ValueError):self.ledger.command({'action':'usage','task_id':tid,'usage':{'input_tokens':v}})
    def test_effort_has_no_invented_price_multiplier(self):
        usage=dict(zip(TOKEN_KEYS,[1000000,1000000,0,0,0]));self.assertEqual(claude_cost('Opus 5.5',usage),24)
    def test_gateway_markers_are_local_and_bind_call(self):
        g=OpenRagnarGateway({'provider':'none'},self.temp.name);g.enable_metrics(self.path);g.metrics.start('claude-ai')
        start=g.handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'openragnar_task','arguments':{'action':'start','label':'Explicit prompt','model':'claude-opus-5.5'}}})
        self.assertFalse(start['result'].get('isError'));self.assertIsNotNone(g.metrics.tasks.active(g.metrics.sid))
        result=g.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'openragnar_status','arguments':{}}})
        tid=g.metrics.tasks.active(g.metrics.sid);self.assertEqual(g.metrics.tasks.snapshot()[0]['tool_calls'],1)
        end=g.handle({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'openragnar_task','arguments':{'action':'finish','task_id':tid,'status':'complete','verification':'agent_reported'}}})
        self.assertFalse(end['result'].get('isError'));self.assertEqual(g.metrics.tasks.snapshot()[0]['tool_calls'],1)
        self.assertEqual(g.metrics.tasks.snapshot()[0]['tracking_calls'],2)
        g.artifacts.cleanup();g.moves_pool.shutdown()
