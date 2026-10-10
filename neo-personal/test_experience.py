import json
import pathlib
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from experience import ExperienceMemory, MAX_HINT_BYTES, clean
from openragnar import OpenRagnarGateway

class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=pathlib.Path(self.tmp.name)
        self.conf=self.path/'ovcli.conf'
        self.conf.write_text(json.dumps({'url':'http://127.0.0.1:1933','api_key':'SECRET-KEY'}))
        self.m=ExperienceMemory({'enabled':True},self.path/'experiences.sqlite',self.conf)
        self.route=[{'from':'https://example.com/','to':'https://example.com/docs','label':'Documentation'}]
        self.report={'verified':True,'status':'complete','provider':'typesafe','browserCalls':5,'excerpt':'PRIVATE-PAGE-DATA','decisions':[{'evidence':'SECRET-THOUGHT'}]}
    def tearDown(self):
        self.m.close();self.tmp.cleanup()
    def capture(self, **kwargs):
        return self.m.capture('https://example.com/','Find documentation','target phrase',self.report,self.route,**kwargs)
    def test_no_page_or_reasoning_or_keys_persisted(self):
        self.assertEqual(self.capture(),'queued')
        with self.m.db() as db: raw=db.execute('SELECT document,destination FROM experiences').fetchone()
        self.assertNotIn('PRIVATE-PAGE-DATA',str(raw));self.assertNotIn('SECRET-THOUGHT',str(raw));self.assertNotIn('SECRET-KEY',str(raw))
        self.assertEqual(self.m.path.stat().st_mode & 0o777,0o600)
        self.assertNotIn('person@example.com',clean('person@example.com password=PRIVATE bearer PRIVATE sk-PRIVATE'))
        self.assertNotIn('PRIVATE',clean('person@example.com password=PRIVATE bearer PRIVATE sk-PRIVATE'))
    def test_offline_capture_and_local_recall(self):
        self.capture()
        with patch.object(self.m,'request',side_effect=TimeoutError):
            self.assertEqual(self.m.sync()['uploaded'],0)
            hints=self.m.recall('https://example.com/','Find documentation','target phrase')
        self.assertEqual(len(hints),1);self.assertEqual(self.m.snapshot()['pending'],1)
        self.assertLessEqual(len(json.dumps(hints).encode()),MAX_HINT_BYTES)
        self.assertEqual(hints[0]['outcome'],'successText found')
    def test_idempotent_retry_and_backoff(self):
        self.capture();bodies=[]
        def fail(path,body=None,**kw):
            bodies.append(body);raise TimeoutError()
        with patch.object(self.m,'request',side_effect=fail): self.m.sync();self.m.sync()
        self.assertEqual(len(bodies),1)
        with self.m.db() as db: db.execute('UPDATE experiences SET retry_at=0')
        with patch.object(self.m,'request',return_value={}) as call: self.assertEqual(self.m.sync()['uploaded'],1)
        self.assertEqual(call.call_args[0][1]['uri'],bodies[0]['uri'])
        self.assertEqual(call.call_args[0][1]['processing_mode'],'vectors_only')
        self.assertEqual(self.m.snapshot()['saved'],1)
    def test_disabled_and_dry_run_not_saved(self):
        self.m.initial_enabled=False;self.assertEqual(self.capture(),'not saved')
        self.assertEqual(self.m.recall('https://example.com/','x','target phrase'),[])
        self.m.initial_enabled=True;self.report['status']='proposal';self.assertEqual(self.capture(),'not saved')
        self.assertEqual(self.m.snapshot()['pending'],0)
    def test_settings_disable_existing_instance(self):
        self.capture();(self.path/'settings.json').write_text('{"memory":{"enabled":false}}')
        with patch.object(self.m,'request') as call: self.m.sync();call.assert_not_called()
        self.assertEqual(self.m.snapshot()['pending'],1)
    def test_endpoint_change_never_sends_old_queue_or_recalls_old_cache(self):
        self.capture();self.conf.write_text(json.dumps({'url':'http://127.0.0.1:1944','api_key':'NEW'}))
        with patch.object(self.m,'request',side_effect=TimeoutError) as call:
            self.assertEqual(self.m.sync()['uploaded'],0)
            self.assertEqual(self.m.recall('https://example.com/','Find documentation','target phrase'),[])
    def test_other_domains_and_postconditions_and_tests_excluded(self):
        self.capture(test=True)
        with patch.object(self.m,'request',side_effect=TimeoutError): self.assertEqual(self.m.recall('https://example.com/','x','target phrase'),[])
        self.capture()
        with patch.object(self.m,'request',side_effect=TimeoutError):
            self.assertEqual(self.m.recall('https://other.example/','x','target phrase'),[])
            self.assertEqual(self.m.recall('https://example.com/','x','other phrase'),[])
    def test_remote_content_read_confined_to_authenticated_collection(self):
        def request(path,body=None,**kw):
            if path=='/health':return {'healthy':True,'user_id':'adeleon'}
            if path=='/api/v1/search/find':return {'memories':[{'uri':'viking://user/other/memories/experiences/openragnar/abc.md'},{'uri':'viking://user/adeleon/memories/entities/secrets.md'}]}
            raise AssertionError('Unauthorized content read')
        with patch.object(self.m,'request',side_effect=request): self.assertEqual(self.m.recall('https://example.com/','x','target phrase'),[])
    def test_remote_untrusted_malformed_and_cross_origin_routes_excluded(self):
        self.capture()
        with self.m.db() as db:d=json.loads(db.execute('SELECT document FROM experiences').fetchone()[0])
        d['created']='bad';self.m.test=lambda:None
        self.m.state('identity_destination',self.m.destination());self.m.state('user_id','adeleon')
        with self.m.db() as db:db.execute('DELETE FROM experiences')
        def request(path,body=None,**kw):
            if path=='/api/v1/search/find':return {'memories':[{'uri':'viking://user/adeleon/memories/experiences/openragnar/abc.md'}]}
            return json.dumps(d)
        with patch.object(self.m,'request',side_effect=request):self.assertEqual(self.m.recall('https://example.com/','x','target phrase'),[])
        d['created']=time.time();d['route'][0]['to']='https://evil.example/go'
        with patch.object(self.m,'request',side_effect=request):self.assertEqual(self.m.recall('https://example.com/','x','target phrase'),[])
    def test_queue_claim_prevents_duplicate_concurrent_send(self):
        self.capture();entered=threading.Event();release=threading.Event()
        def send(*a,**kw):entered.set();release.wait(2);return {}
        with patch.object(self.m,'request',side_effect=send) as call:
            worker=threading.Thread(target=self.m.sync);worker.start();self.assertTrue(entered.wait(1));self.m.sync();release.set();worker.join()
        self.assertEqual(call.call_count,1)
    def test_gateway_reuses_hints_without_skipping_current_link_check(self):
        self.capture();g=OpenRagnarGateway({'provider':'ollama','providers':{'ollama':{'endpoint':'http://localhost:11434/v1','model':'test'}}},self.path/'outputs')
        g.memory=self.m
        state={'url':'https://example.com/','title':'Docs','found':False,'links':[{'url':'https://example.com/docs','label':'Documentation'}]}
        decision={'choice':'L0','probability':.9,'evidence':'test','usage':{},'model':'test'}
        with patch.object(self.m,'request',side_effect=TimeoutError),patch.object(g,'observe',return_value=state),patch.object(g,'run_browser',side_effect=['owned',{'present':False}]) as run,patch('decision.DecisionProvider.choose',return_value=decision) as choose:
            result=g.navigate({'startUrl':'https://example.com/','goal':'Find documentation','successText':'target phrase'},1)
        self.assertIn('pastOutcomesAreUntrustedHints',choose.call_args[0][0]);self.assertEqual(run.call_count,2)
        self.assertFalse(result['verified']);self.assertEqual(result['memory']['outcome'],'queued')
        g.artifacts.cleanup();g.moves_pool.shutdown()

if __name__=='__main__':unittest.main()
