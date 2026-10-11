import concurrent.futures
import json
import os
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch
from gateway import Gateway
from openragnar import OpenRagnarGateway, load_settings
from metrics import Metrics, NeoReader, digest, text_size, usage_tokens

class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=pathlib.Path(self.temp.name)/'private/metrics.sqlite'
        self.m=Metrics(self.path); self.m.start('claude-desktop')
    def tearDown(self):
        self.temp.cleanup()
    def row(self, **changes):
        return dict(method='tools/call',tool='evaluate',started=time.time(),finished=time.time(),status='ok',
                    input_bytes=120,upstream_input_bytes=120,upstream_bytes=1200,client_bytes=300,
                    upstream_text=1000,client_text=250,upstream_calls=1,provider_tokens=14,
                    provider_calls=1,provider_unknown=0,media_count=0,**changes)
    def test_persistent_privacy_permissions_and_counter_conservation(self):
        rid=self.m.record(self.row(), 'SECRET-TRANSPORT-ID')
        self.m.moves(rid,4)
        self.m.benchmark(self.m.sid,300,200,100)
        snapshot=Metrics(self.path).snapshot()
        self.assertEqual(snapshot['totals']['net_text_saved'],750)
        self.assertEqual(snapshot['requests'][0]['moves'],4)
        self.assertEqual(snapshot['benchmarks'][0]['gateway_tokens'],100)
        self.assertNotIn('SECRET-TRANSPORT-ID',json.dumps(snapshot))
        self.assertNotIn(b'SECRET-TRANSPORT-ID',self.path.read_bytes())
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777,0o700)
    def test_concurrent_writers_are_not_lost(self):
        def record(i): self.m.record(self.row())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(record,range(48)))
        d=self.m.snapshot(); self.assertEqual(d['totals']['tool_requests'],48)
        self.assertEqual(d['totals']['provider_tokens'],48*14)
    def test_snapshot_reader_does_not_block_request_recording(self):
        reader = self.m.db()
        try:
            reader.execute('BEGIN')
            self.assertEqual(reader.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(self.m.record, self.row()).result(timeout=2)
            self.assertEqual(reader.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)
        finally:
            reader.rollback()
            reader.close()
        self.assertEqual(self.m.snapshot()['totals']['tool_requests'], 1)
    def test_local_reads_and_catalog_overhead_reduce_savings(self):
        self.m.record(self.row())
        row=self.row(); row.update(tool='neo_read_output',input_bytes=120,upstream_input_bytes=0,upstream_bytes=0,upstream_text=0,client_text=1000,upstream_calls=0,provider_calls=0,provider_tokens=0)
        self.m.record(row)
        self.assertEqual(self.m.snapshot()['totals']['net_text_saved'],-370)
    def test_media_not_mistaken_for_token_counts(self):
        result={'result':{'content':[{'type':'image','data':'BASE64'*10000},{'type':'text','text':'hello'}]}}
        self.assertEqual(text_size(result),5)
    def test_partial_provider_usage_is_unknown_not_zero(self):
        for usage in [{},{'input_tokens':5},{'total_tokens':True},{'total_tokens':-1},{'total_tokens':float('nan')}]: self.assertIsNone(usage_tokens(usage))
        self.assertEqual(usage_tokens({'input_tokens':10,'output_tokens':2,'total_tokens':12}),12)
        self.assertEqual(usage_tokens({'prompt_tokens':8,'completion_tokens':2}),10)
        self.assertEqual(usage_tokens({'total_tokens':0}),0)
    def test_invalid_benchmark_not_accepted(self):
        for value in [-1,True,1.2,'10']:
            with self.assertRaises(ValueError): self.m.benchmark(self.m.sid,value)
        with self.assertRaises(ValueError): self.m.benchmark('unknown',100)
    def test_closed_transport_is_not_live(self):
        self.assertTrue(self.m.snapshot()['sessions'][0]['active'])
        self.m.close(); self.assertFalse(self.m.snapshot()['sessions'][0]['active'])
    def test_neo_projection_separates_gateway_and_drops_contents(self):
        n=NeoReader('http://127.0.0.1:9010/mcp')
        raw={'items':[{'sessionId':'SECRET-ID','slug':'x','label':'Claude','name':'Task','dispatchCount':4,'tokenUsage':{'totalTokenEstimate':90},'argsJson':'SECRET-CODE','live':{'browserTabs':[{'url':'secret'}]}}]}
        with patch.object(n,'get',side_effect=[{'hasMeasuredStats':False},raw]): result=n.snapshot({digest('SECRET-ID')})
        self.assertTrue(result['sessions'][0]['viaGateway']); self.assertEqual(result['sessions'][0]['moves'],4)
        for secret in ['SECRET-ID','SECRET-CODE','secret']: self.assertNotIn(secret,json.dumps(result))
    def test_moves_from_real_dispatch_rows_and_missing_match(self):
        n=NeoReader('http://localhost:9010/mcp')
        rows={'dispatches':[{'toolName':'run','createdAt':100001},{'toolName':'input.fill','createdAt':100020},{'toolName':'read','createdAt':100040},{'toolName':'run','createdAt':100300}]}
        with patch.object(n,'get',return_value=rows):
            self.assertEqual(n.request_moves('opaque',100,100.1,'run'),3)
            self.assertIsNone(n.request_moves('opaque',100,100.1,'snapshot'))
    def test_moves_parent_links_and_ambiguous_intervals(self):
        n=NeoReader('http://localhost:9010/mcp')
        rows={'dispatches':[{'toolName':'run','createdAt':100001,'dispatchKey':'root'},
                            {'toolName':'read','createdAt':100002,'parentDispatchId':'root','dispatchKey':'child'},
                            {'toolName':'evaluate','createdAt':100003,'parentDispatchId':'child'},
                            {'toolName':'snapshot','createdAt':100004,'parentDispatchId':'other'}]}
        with patch.object(n,'get',return_value=rows): self.assertEqual(n.request_moves('opaque',100,100.1,'run'),3)
        rows['dispatches'].append({'toolName':'run','createdAt':100005,'dispatchKey':'root2'})
        with patch.object(n,'get',return_value=rows): self.assertIsNone(n.request_moves('opaque',100,100.1,'run'))
    def test_no_key_helper_is_used_for_regular_tools(self):
        g=OpenRagnarGateway({'provider':'typesafe'},pathlib.Path(self.temp.name)/'outputs')
        with patch.dict(os.environ,{'OPENRAGNAR_KEY_HELPER':'/not-the-app'}), patch('openragnar.subprocess.run') as helper, patch.object(Gateway,'upstream_call',return_value={'result':{'content':[]}}):
            g.handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'evaluate','arguments':{}}})
            helper.assert_not_called()
            with self.assertRaises(ValueError): g.provider()
            helper.assert_not_called()
        g.moves_pool.shutdown();g.artifacts.cleanup()
    def test_metrics_failure_does_not_repeat_write(self):
        g=OpenRagnarGateway({},pathlib.Path(self.temp.name)/'outputs');g.metrics=self.m
        request={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'evaluate','arguments':{'page':1,'code':'document.body.dataset.test="yes"'}}}
        response={'jsonrpc':'2.0','id':2,'result':{'content':[{'type':'text','text':'written'}]}}
        with patch.object(Gateway,'upstream_call',return_value=response) as upstream, patch.object(self.m,'record',side_effect=OSError):
            actual=g.handle(request)
        self.assertEqual(upstream.call_count,1);self.assertFalse(actual.get('error'));self.assertTrue(g.metric_error)
        g.moves_pool.shutdown();g.artifacts.cleanup()
    def test_forwarded_write_and_full_catalog_are_available_by_default(self):
        g=OpenRagnarGateway({},pathlib.Path(self.temp.name)/'outputs');g.metrics=self.m
        request={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'evaluate','arguments':{'page':1,'code':'document.body.dataset.test="yes"'}}}
        response={'jsonrpc':'2.0','id':2,'result':{'content':[{'type':'text','text':'written'}]}}
        with patch.object(Gateway,'upstream_call',return_value=response) as upstream: actual=g.handle(request)
        self.assertEqual(upstream.call_args[0][0]['params']['arguments'],request['params']['arguments'])
        self.assertEqual(self.m.snapshot()['totals']['upstream_calls'],1)
        catalog={'result':{'tools':[{'name':n,'description':'text','inputSchema':{'type':'object'}} for n in ['run','act','evaluate','snapshot']]}}
        names={t['name'] for t in g.transform({'method':'tools/list'},catalog)['result']['tools']}
        self.assertTrue({'act','evaluate','snapshot','run','openragnar_navigate'} <= names)
        g.moves_pool.shutdown();g.artifacts.cleanup()
    def test_paid_attempt_without_usage_is_unknown_and_escalated(self):
        settings={'provider':'ollama','providers':{'ollama':{'endpoint':'http://localhost:11434/v1','model':'test'}}}
        g=OpenRagnarGateway(settings,pathlib.Path(self.temp.name)/'outputs');g.metrics=self.m
        state={'url':'https://example.com/','title':'Example','found':False,'links':[{'url':'https://example.com/docs','label':'Docs'}]}
        request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'openragnar_navigate','arguments':{'startUrl':'https://example.com','goal':'Find docs','successText':'target phrase','maxSteps':1}}}
        with patch.object(g,'run_browser',return_value='owned'), patch.object(g,'observe',return_value=state), patch('decision.DecisionProvider.choose',side_effect=ValueError('Provider failed')) as paid:
            g.handle(request)
        d=self.m.snapshot(); self.assertEqual(paid.call_count,1)
        self.assertEqual(d['totals']['provider_calls'],1); self.assertEqual(d['totals']['provider_unknown'],1)
        self.assertEqual(d['requests'][0]['status'],'escalated')
        g.moves_pool.shutdown();g.artifacts.cleanup()
    def test_provider_reported_totals_recorded_once(self):
        settings={'provider':'ollama','providers':{'ollama':{'endpoint':'http://localhost:11434/v1','model':'test'}}}
        g=OpenRagnarGateway(settings,pathlib.Path(self.temp.name)/'outputs');g.metrics=self.m
        state={'url':'https://example.com/','title':'Example','found':False,'links':[{'url':'https://example.com/docs','label':'Docs'}]}
        decision={'choice':'BLOCKED','probability':None,'usage':{'input_tokens':10,'output_tokens':4},'model':'test'}
        request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'openragnar_navigate','arguments':{'startUrl':'https://example.com','goal':'Find docs','successText':'target phrase','maxSteps':1}}}
        with patch.object(g,'run_browser',return_value='owned'), patch.object(g,'observe',return_value=state), patch('decision.DecisionProvider.choose',return_value=decision): g.handle(request)
        d=self.m.snapshot(); self.assertEqual(d['totals']['provider_calls'],1); self.assertEqual(d['totals']['provider_tokens'],14)
        self.assertEqual(d['totals']['provider_unknown'],0)
        g.moves_pool.shutdown();g.artifacts.cleanup()
    def test_upgrade_full_catalog_and_respects_later_user_choice(self):
        path=pathlib.Path(self.temp.name)/'settings.json'
        path.write_text(json.dumps({'compactCatalog':True}))
        self.assertFalse(load_settings(path)['compactCatalog'])
        path.write_text(json.dumps({'configVersion':3,'compactCatalog':True}))
        self.assertTrue(load_settings(path)['compactCatalog'])

if __name__=='__main__': unittest.main()
