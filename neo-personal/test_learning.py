"""Learning must change decisions, retain failures safely, and never skip live checks."""
import copy
import json
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch

from experience import ExperienceMemory, MAX_HINT_BYTES
from browserhelm import BrowserHelmGateway
from gateway import rpc_error, rpc_result, tool_result


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.conf = self.root/'ovcli.conf'
        self.conf.write_text('{"url":"http://127.0.0.1:1933","api_key":"fixture-only"}')
        self.m = ExperienceMemory({'enabled': True}, self.root/'experience.sqlite', self.conf)
        self.g = BrowserHelmGateway({'provider':'ollama', 'providers':{'ollama':{'endpoint':'http://localhost:11434/v1','model':'fixture'}}}, self.root/'outputs')
        self.g.memory = self.m
        self.args = {'startUrl':'https://example.com/', 'goal':'Find documentation', 'successText':'target phrase', 'maxSteps':2}
        self.route = [{'from':'https://example.com/', 'to':'https://example.com/docs', 'label':'Documentation'}]
        self.good = {'status':'complete', 'verified':True, 'provider':'typesafe', 'browserCalls':5}
        self.state = {'url':self.args['startUrl'], 'found':False, 'links':[{'url':self.route[0]['to'], 'label':'Documentation'}]}
        self.options = {'L0':self.state['links'][0], 'BLOCKED':'Stop'}
        self.decision = {'choice':'L0', 'probability':.9, 'evidence':'fixture', 'usage':{'input_tokens':20}, 'model':'fixture'}

    def tearDown(self):
        self.m.close(); self.g.moves_pool.shutdown(); self.g.artifacts.cleanup(); self.tmp.cleanup()

    def save(self, report=None, route=None, **kwargs):
        return self.m.capture(self.args['startUrl'], self.args['goal'], self.args['successText'],
                              report or self.good, self.route if route is None else route, **kwargs)

    def choice(self):
        return self.m.choose_verified_route(self.args['startUrl'], self.args['goal'], self.args['successText'], self.state['url'], self.options)

    def navigation(self, fresh=True, complete=True):
        end = {**self.state, 'url':'https://example.com/docs', 'found':complete}
        with patch.object(self.m,'request',side_effect=TimeoutError), patch.object(self.m,'start'), \
             patch.object(self.g,'observe',side_effect=[self.state,end]), \
             patch.object(self.g,'run_browser',side_effect=['owned',{'present':fresh,'navigated':fresh}]) as run, \
             patch('decision.DecisionProvider.choose',return_value=self.decision) as choose:
            result = self.g.navigate(self.args, 1)
        return result, run.call_count, choose.call_count

    def test_second_verified_run_enables_third_run_without_provider_call(self):
        first, _, calls1 = self.navigation()
        second, _, calls2 = self.navigation()
        third, browser_calls, calls3 = self.navigation()
        self.assertEqual([calls1,calls2,calls3], [1,1,0])
        self.assertTrue(first['verified'] and second['verified'] and third['verified'])
        self.assertEqual(browser_calls,2)  # Open, then live link check plus navigation.
        self.assertEqual(third['browserCalls'],4)
        self.assertEqual(third['memory']['providerCallsAvoided'],1)
        self.assertEqual(self.m.snapshot()['reused_tasks_verified'],1)
        self.assertTrue(all(isinstance(d['elapsedSeconds'], (int, float)) for d in self.m.local_documents()))

    def test_verified_route_skips_key_access_and_advisory_recall(self):
        self.save(); self.save()
        with patch.object(self.g,'provider',side_effect=AssertionError('Unexpected provider access')) as provider, patch.object(self.m,'recall',side_effect=AssertionError('Unexpected recall')) as recall:
            result, _, calls = self.navigation()
        self.assertTrue(result['verified']); self.assertEqual(calls,0)
        provider.assert_not_called(); recall.assert_not_called()

    def test_already_satisfied_task_skips_advisory_recall(self):
        with patch.object(self.m,'start'), patch.object(self.m,'recall') as recall, patch.object(self.g,'provider') as provider, patch.object(self.g,'run_browser',return_value='owned'), patch.object(self.g,'observe',return_value={**self.state,'found':True}):
            result=self.g.navigate(self.args,1)
        self.assertTrue(result['verified']); recall.assert_not_called(); provider.assert_not_called()

    def test_cancel_during_recall_does_not_read_key_or_make_decision(self):
        def cancel(*args):
            self.g.cancelled.add(1)
            return []
        with patch.object(self.m,'start'), patch.object(self.m,'recall',side_effect=cancel), patch.object(self.g,'provider') as provider, patch.object(self.g,'run_browser',return_value='owned') as run, patch.object(self.g,'observe',return_value=self.state):
            result=self.g.navigate(self.args,1)
        self.assertEqual(result['failureCategory'],'cancelled'); self.assertEqual(run.call_count,1)
        provider.assert_not_called()

    def test_reused_choice_still_revalidates_and_failure_revokes_eligibility(self):
        self.save(); self.save()
        report, calls, decisions = self.navigation(fresh=False)
        self.assertEqual((calls,decisions),(2,0))
        self.assertFalse(report['verified']); self.assertEqual(report['failureCategory'],'stale_link')
        self.assertIsNone(self.choice())
        self.save(); self.assertIsNone(self.choice())
        self.save(); self.assertIsNotNone(self.choice())

    def test_missing_postcondition_revokes_route(self):
        self.save(); self.save()
        self.save({**self.good,'verified':False,'status':'escalate','failureCategory':'step_budget'})
        self.assertIsNone(self.choice())

    def test_validation_records_cannot_seed_reuse(self):
        self.save(test=True); self.save(test=True)
        self.save({**self.good,'provider':'validation (deterministic; no LLM)'})
        self.assertIsNone(self.choice())

    def test_matching_intent_start_and_postcondition_required(self):
        self.save(); self.save()
        self.args['goal']='Find billing information'; self.assertIsNone(self.choice())
        self.args['goal']='Find documentation'; self.args['successText']='different phrase'; self.assertIsNone(self.choice())
        self.args['successText']='target phrase'; self.args['startUrl']='https://example.com/other'; self.assertIsNone(self.choice())

    def test_live_options_must_contain_route_and_conflicts_fall_back(self):
        self.save(); self.save(); self.options={'BLOCKED':'Stop'}; self.assertIsNone(self.choice())
        self.options={'L0':self.state['links'][0], 'L1':{'url':'https://example.com/help','label':'Help'}, 'BLOCKED':'Stop'}
        other=[{**self.route[0],'to':'https://example.com/help'}]
        self.save(route=other); self.save(route=other); self.assertIsNone(self.choice())

    def test_old_successes_expire_and_duplicate_evidence_does_not_count_twice(self):
        self.save(); self.save()
        with self.m.db() as db:
            rows=db.execute('SELECT id,document FROM experiences').fetchall()
            first=json.loads(rows[0][1])
            second=json.loads(rows[1][1]); second['id']=first['id']
            db.execute('UPDATE experiences SET document=? WHERE id=?',(json.dumps(second),rows[1][0]))
        self.assertIsNone(self.choice())
        with self.m.db() as db:
            for identifier, raw in rows:
                d=json.loads(raw); d['created']=time.time()-31*86400
                db.execute('UPDATE experiences SET document=? WHERE id=?',(json.dumps(d),identifier))
        self.assertIsNone(self.choice())

    def test_sensitive_task_redaction_cannot_merge_different_intents(self):
        self.args['goal']='Find documentation password=FIRST'
        self.save(); self.save(); self.assertIsNotNone(self.choice())
        self.args['goal']='Find documentation password=SECOND'; self.assertIsNone(self.choice())

    def test_local_recall_skips_network_and_includes_failed_attempt_without_route(self):
        self.save({**self.good,'verified':False,'status':'escalate','failureCategory':'stale_link','attempts':self.route},route=[])
        with patch.object(self.m,'request') as request:
            hints=self.m.recall(self.args['startUrl'], self.args['goal'], self.args['successText'])
            request.assert_not_called()
        self.assertIn('Re-observe',hints[0]['lesson'])
        self.assertEqual(hints[0]['attempted'],self.route)
        self.assertLessEqual(len(json.dumps(hints).encode()),MAX_HINT_BYTES)

    def test_remote_hints_do_not_become_local_fast_path_evidence(self):
        self.save(); self.save()
        with self.m.db() as db:
            documents=[json.loads(r[0]) for r in db.execute('SELECT document FROM experiences')]
            db.execute('DELETE FROM experiences')
        hints=self.m.hints(documents,self.args['startUrl'],self.args['goal'],self.args['successText'])
        self.assertEqual(len(hints),2); self.assertIsNone(self.choice())

    def test_failed_memory_service_is_not_contacted_again_for_each_task(self):
        with patch.object(self.m,'request',side_effect=TimeoutError) as request:
            self.m.recall(self.args['startUrl'],self.args['goal'],self.args['successText'])
            before=request.call_count
            self.m.recall(self.args['startUrl'],self.args['goal'],self.args['successText'])
            self.assertEqual(request.call_count,before)
            self.conf.write_text('{"url":"http://127.0.0.1:1944"}')
            self.m.recall(self.args['startUrl'],self.args['goal'],self.args['successText'])
            self.assertGreater(request.call_count,before)

    def test_direct_failure_history_does_not_displace_navigation_evidence(self):
        self.save();self.save()
        for i in range(201):
            self.m.enqueue({'id':str(i),'schema':2,'source':'browserhelm','kind':'tool_outcome','created':time.time(),'verified':False})
        self.assertIsNotNone(self.choice())

    def test_disabled_memory_never_reuses_or_captures(self):
        self.save(); self.save(); self.m.initial_enabled=False
        self.assertIsNone(self.choice())
        self.assertIsNone(self.m.prior_tool_failure('run',{'code':'secret'}))
        self.assertEqual(self.save(),'not saved')

    def tool(self, status='error', arguments=None):
        request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'run','arguments':arguments or {'code':'PRIVATE-CODE person@example.com sk-PRIVATE'}}}
        response=rpc_error(request,'Timeout PRIVATE-ERROR') if status=='error' else rpc_result(request,tool_result('PRIVATE-RESULT'))
        with patch.object(self.g,'_handle',return_value=response) as call:
            result=self.g.handle(request)
        self.assertEqual(call.call_count,1)
        return result

    def test_repeated_tool_failure_informs_main_agent_without_model_or_retry(self):
        first=self.tool(); second=self.tool()
        self.assertNotIn('browserhelmLearning',first['error']['data'])
        self.assertEqual(second['error']['data']['browserhelmLearning']['priorMatchingFailures'],1)
        self.assertEqual(self.m.snapshot()['repeat_failure_hints'],1)
        self.assertEqual(self.m.snapshot()['tool_requests_seen'],2)

    def test_changed_args_and_later_accepted_request_retire_failure_hint(self):
        self.tool(); other=self.tool(arguments={'code':'different'})
        self.assertNotIn('browserhelmLearning',other['error']['data'])
        self.tool(status='ok'); later=self.tool()
        self.assertNotIn('browserhelmLearning',later['error']['data'])

    def test_history_and_synced_lesson_never_contain_request_error_or_result(self):
        self.tool(); self.tool(status='ok')
        with self.m.db() as db:
            raw=str(db.execute('SELECT * FROM tool_history').fetchall())+str(db.execute('SELECT document FROM experiences').fetchall())
        for secret in ('PRIVATE-CODE','person@example.com','sk-PRIVATE','PRIVATE-ERROR','PRIVATE-RESULT'):
            self.assertNotIn(secret,raw)
        self.assertEqual(self.m.snapshot()['pending'],2)
        self.assertFalse(any(e['verified'] for e in self.m.snapshot()['recent']))

    def test_memory_failure_does_not_change_tool_result_or_repeat_call(self):
        with patch.object(self.m,'prior_tool_failure',side_effect=OSError),patch.object(self.m,'capture_tool',side_effect=OSError):
            result=self.tool()
        self.assertEqual(result['error']['message'],'Timeout PRIVATE-ERROR')

    def test_tool_history_retention_and_endpoint_isolation(self):
        self.tool()
        self.conf.write_text('{"url":"http://127.0.0.1:1944"}')
        self.assertIsNone(self.m.prior_tool_failure('run',{'code':'PRIVATE-CODE person@example.com sk-PRIVATE'}))
        with self.m.db() as db: db.execute('UPDATE tool_history SET created=?',(time.time()-15*86400,))
        self.tool(); self.assertEqual(self.m.snapshot()['tool_requests_seen'],1)

    def test_route_reuse_does_not_report_unknown_provider_usage(self):
        self.save();self.save()
        row={'provider_calls':0,'provider_unknown':0,'provider_tokens':0}
        self.g.context.row=row
        report,_,calls=self.navigation()
        del self.g.context.row
        self.assertEqual(calls,0);self.assertEqual(row['provider_calls'],0);self.assertEqual(row['provider_unknown'],0)
        self.assertTrue(report['verified'])


if __name__=='__main__': unittest.main()
