import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from executor import EXEC_TOOL, READ_JS, execute, read_page, validate
from openragnar import OpenRagnarGateway


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.g = OpenRagnarGateway({'provider':'ollama','providers':{'ollama':{'endpoint':'http://127.0.0.1:11434/v1','model':'fixture'}}},self.tmp.name)
        self.args = {'page':1,'goal':'Inspect page typography','allowedActions':['inspect','extract'],
                     'steps':[{'action':'inspect'},{'action':'extract','fields':[{'name':'heading','selector':'h1','read':'style'}]}],
                     'completion':{'selectorsPresent':['h1']}}
        self.state = {'url':'https://example.com/','title':'Fixture','links':[],
                      'findings':[{'action':'inspect','headings':[]},{'action':'extract','fields':[]}],
                      'checks':[{'kind':'selector','expected':'h1','present':True}], 'found':False}
        self.decision={'choice':'L0','probability':.95,'evidence':'fixture','usage':{'total_tokens':12},'model':'fixture'}

    def tearDown(self):
        self.g.moves_pool.shutdown(wait=True); self.g.artifacts.cleanup(); self.tmp.cleanup()

    def test_consecutive_reads_batched_without_model_or_key(self):
        with patch('executor.read_page',return_value=self.state) as read, patch.object(self.g,'provider',side_effect=AssertionError('model not needed')):
            result = execute(self.g,self.args,1)
        self.assertTrue(result['verified']); self.assertEqual(len(result['steps']),2)
        self.assertEqual(read.call_count,1); self.assertEqual(read.call_args[0][2],self.args['steps'])
        self.assertFalse(hasattr(self.g.context,'execution_deadline'))
        self.assertTrue(self.g.nav_lock.acquire(blocking=False)); self.g.nav_lock.release()

    def test_missing_required_check_escalates_and_optional_field_preserved(self):
        state=copy.deepcopy(self.state); state['checks'][0]['present']=False
        state['findings'][1]['fields']=[{'name':'heading','status':'missing','value':None}]
        with patch('executor.read_page',return_value=state):result=execute(self.g,self.args,1)
        self.assertFalse(result['verified']); self.assertEqual(result['failureCategory'],'verification_failed')
        self.assertIsNone(result['steps'][1]['fields'][0]['value'])

    def test_invalid_contract_never_touches_browser(self):
        cases=[{'completion':{}},{'allowedActions':['click']},{'steps':[{'action':'navigate','text':'target'}]},
               {'page':True},{'startUrl':'https://example.com'},{'steps':[{'action':'inspect','code':'delete'}]},
               {'maxSeconds':True},{'maxBrowserCalls':0},{'completion':{'textPresent':['abc']}},
               {'steps':[{'action':'extract','fields':[{'name':'x','selector':'h1','read':'innerHTML'}]}]}]
        for changes in cases:
            with self.subTest(changes=changes), patch.object(self.g,'run_browser') as run:
                with self.assertRaises(ValueError):execute(self.g,{**self.args,**changes},1)
                run.assert_not_called()

    def test_cancel_before_any_browser_call_and_after_decision(self):
        self.g.cancelled.add(1)
        with patch('executor.read_page') as read:result=execute(self.g,self.args,1)
        read.assert_not_called(); self.assertFalse(result['verified'])
        args={**self.args,'allowedActions':['navigate'],'steps':[{'action':'navigate','text':'target phrase'}],
              'completion':{'textPresent':['target phrase']}}
        state={**self.state,'findings':[],'links':[{'url':'https://example.com/docs','label':'Docs'}]}
        def choose(*_):self.g.cancelled.add(1);return self.decision
        with patch('executor.read_page',return_value=state),patch('decision.DecisionProvider.choose',side_effect=choose),patch.object(self.g,'run_browser') as run:
            result=execute(self.g,args,1)
        run.assert_not_called(); self.assertFalse(result['verified'])

    def nav_args(self):
        return {**self.args,'allowedActions':['navigate','inspect'],
                'steps':[{'action':'navigate','text':'target phrase'},{'action':'inspect'}],
                'completion':{'textPresent':['target phrase']}}

    def test_navigation_filters_links_and_requires_final_verification(self):
        before={**self.state,'findings':[],'checks':[{'present':False}],
                'links':[{'url':'https://evil.example/','label':'Leave'},{'url':'https://example.com/delete','label':'Delete'},
                         {'url':'https://example.com/docs','label':'Docs'}]}
        after={**self.state,'url':'https://example.com/docs','found':True,'findings':[]}
        final={**after,'findings':[{'action':'inspect'}],'checks':[{'present':False}]}
        with patch('executor.read_page',side_effect=[before,after,final]), patch('decision.DecisionProvider.choose',return_value=self.decision) as choose, patch.object(self.g,'run_browser',return_value={'present':True}) as run:
            result=execute(self.g,self.nav_args(),1)
        self.assertEqual(set(choose.call_args[0][1]),{'L0','BLOCKED'})
        self.assertIn('location.href===current',run.call_args[0][0])
        self.assertFalse(result['verified']); self.assertEqual(result['failureCategory'],'verification_failed')

    def test_stale_selected_link_and_unknown_dispatch_never_retry(self):
        before={**self.state,'findings':[],'links':[{'url':'https://example.com/docs','label':'Docs'}]}
        for outcome in [{'present':False},ValueError('Unknown dispatch outcome')]:
            with patch('executor.read_page',return_value=before),patch('decision.DecisionProvider.choose',return_value=self.decision),patch.object(self.g,'run_browser',side_effect=[outcome]) as run:
                result=execute(self.g,self.nav_args(),1)
            self.assertFalse(result['verified']);self.assertEqual(run.call_count,1)
            self.assertEqual(result['attempts'][0]['to'],'https://example.com/docs')

    def test_provider_failure_and_low_confidence_escalate(self):
        before={**self.state,'findings':[],'links':[{'url':'https://example.com/docs','label':'Docs'}]}
        for answer in [ValueError('provider unavailable'),{**self.decision,'probability':.1}]:
            with patch('executor.read_page',return_value=before),patch('decision.DecisionProvider.choose',side_effect=[answer]) as choose,patch.object(self.g,'run_browser') as run:
                result=execute(self.g,self.nav_args(),1)
            self.assertFalse(result['verified']);self.assertEqual(choose.call_count,1);run.assert_not_called()

    def test_vision_point_is_explicit_and_not_click(self):
        args={**self.args,'allowedActions':['locate'],'steps':[{'action':'locate','instruction':'Locate the logo'}]}
        with patch('vision.visual_act',return_value={'status':'point','verified':False,'x':10,'y':20}) as vision,patch('executor.read_page',return_value={**self.state,'findings':[]}):
            result=execute(self.g,args,1)
        self.assertTrue(result['verified']) # DOM check, not visual coordinate accuracy.
        self.assertEqual(vision.call_args[0][1]['action'],'point');self.assertTrue(vision.call_args.kwargs['lock_held'])
        self.assertFalse(result['steps'][0]['result']['verified'])

    def test_no_checks_or_extra_incomplete_findings_never_complete(self):
        for state in [{**self.state,'checks':[]},{**self.state,'findings':[]}]:
            with patch('executor.read_page',return_value=state):result=execute(self.g,self.args,1)
            self.assertFalse(result['verified'])

    def test_browser_budget_and_deadline_apply_before_dispatch(self):
        self.g.context.execution_deadline=__import__('time').monotonic()+20
        self.g.context.execution_calls=2;self.g.context.execution_call_limit=2
        with patch.object(self.g.opener,'open') as call:
            with self.assertRaisesRegex(ValueError,'browser-call'):self.g.upstream_call({'method':'tools/call'})
        call.assert_not_called()
        self.g.context.execution_deadline=0
        with patch.object(self.g.opener,'open') as call:
            with self.assertRaisesRegex(ValueError,'elapsed-time'):self.g.upstream_call({'method':'tools/call'})
        call.assert_not_called()

    def test_full_wrapper_only_and_no_artifact_path_follow(self):
        wrapper='[UNTRUSTED_PAGE_CONTENT nonce=abc123 origin=https://example.com/] data\n'+json.dumps(self.state)+'\n[END_UNTRUSTED_PAGE_CONTENT nonce=abc123]'
        for response in [{'result':{'structuredContent':{'value':self.state}}},{'result':{'content':[{'type':'text','text':wrapper}]}}]:
            with patch.object(self.g,'upstream_call',return_value=response):self.assertEqual(read_page(self.g,1,[],{}),self.state)
        for response in [{'result':{'content':[{'type':'text','text':wrapper+' truncated'}]}},{'error':{'code':404}},
                         {'result':{'structuredContent':{'writtenToFile':True,'path':'/etc/passwd'}}}]:
            with patch.object(self.g,'upstream_call',return_value=response),self.assertRaises(ValueError):read_page(self.g,1,[],{})

    def test_executor_in_catalog_and_initialization_guidance(self):
        response={'result':{'tools':[]}}
        catalog=self.g.transform({'method':'tools/list'},response)['result']['tools']
        self.assertIn(EXEC_TOOL['name'],[t['name'] for t in catalog])

    def test_verified_repeats_skip_decision_but_stale_route_revokes_reuse(self):
        from experience import ExperienceMemory
        from pathlib import Path
        conf=Path(self.tmp.name)/'ovcli.conf'
        conf.write_text('{"url":"http://127.0.0.1:1933","api_key":"fixture-only"}')
        memory=ExperienceMemory({'enabled':True},Path(self.tmp.name)/'experience.sqlite',conf)
        self.g.memory=memory
        before={**self.state,'findings':[],'links':[{'url':'https://example.com/docs','label':'Docs'}]}
        after={**self.state,'url':'https://example.com/docs','findings':[],'found':True}
        final={**after,'findings':[{'action':'inspect'}]}
        def attempt(stale=False,args=None):
            with patch.object(memory,'start'),patch('executor.read_page',side_effect=[before,after,final]),patch('decision.DecisionProvider.choose',return_value=self.decision) as choose,patch.object(self.g,'run_browser',return_value={'present':not stale}):
                report=execute(self.g,args or self.nav_args(),1)
            return report,choose.call_count
        try:
            results=[attempt() for _ in range(3)]
            self.assertEqual([calls for _,calls in results],[1,1,0])
            self.assertTrue(all(r['verified'] for r,_ in results))
            self.assertEqual(results[2][0]['memory']['providerCallsAvoided'],1)
            failure,calls=attempt(True)
            self.assertFalse(failure['verified']);self.assertEqual(calls,0)
            report,calls=attempt();self.assertEqual(calls,1)
            # A different inspection contract cannot inherit the old route shortcut.
            changed=self.nav_args();changed['completion']={'selectorsPresent':['h1']}
            report,calls=attempt(args=changed);self.assertEqual(calls,1)
        finally:memory.close()

    def test_elapsed_budget_after_observation_never_reports_completion(self):
        import time
        def expired(*_):self.g.context.execution_deadline=time.monotonic()-1;return self.state
        # The local deadline remains authoritative, so advance its clock beyond the limit.
        with patch('executor.read_page',return_value=self.state),patch('executor.time.monotonic',side_effect=[0,0,0,0,100,100,100]):
            result=execute(self.g,self.args,1)
        self.assertFalse(result['verified']);self.assertIn('budget',result['reason'])

    @unittest.skipUnless(shutil.which('node'),'Node is optional for page-script fixture')
    def test_action_schemas_match_validation_and_explain_pilot_errors(self):
        variants = {v['properties']['action']['enum'][0]: v for v in EXEC_TOOL['inputSchema']['properties']['steps']['items']['oneOf']}
        self.assertEqual(variants['navigate']['required'], ['action', 'text'])
        self.assertNotIn('instruction', variants['inspect']['properties'])
        self.assertEqual(variants['extract']['required'], ['action', 'fields'])
        for step, error in [({'action':'inspect','instruction':'look'}, 'Only locate accepts instruction'),
                            ({'action':'navigate','maxHops':2}, 'literal phrase'),
                            ({'action':'inspect','includeStyles':'false'}, 'boolean'),
                            ({'action':'extract','fields':[{'name':'style','selector':'h1','read':'style','contains':'abc'}]}, 'text field')]:
            args = {**self.args, 'allowedActions':['inspect','navigate','extract'], 'steps':[step]}
            with self.assertRaisesRegex(ValueError, error): validate(args)
        validate({**self.args, 'steps':[{'action':'inspect','includeStyles':True}]})

    def test_local_executor_help_available_before_and_after_catalog_without_upstream(self):
        request = {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'neo_help','arguments':{'topic':'openragnar_execute'}}}
        with patch.object(self.g, 'upstream_call') as upstream:
            for discovered in (False, True):
                if discovered: self.g.transform({'method':'tools/list'}, {'result':{'tools':[]}})
                result = self.g._handle(request)['result']
                self.assertFalse(result.get('isError', False))
                self.assertIn('literal phrase', result['content'][0]['text'])
                self.assertIn('"action":"navigate","text"', result['content'][0]['text'])
            upstream.assert_not_called()

    @unittest.skipUnless(shutil.which('node'), 'Node required for real observation script')
    def test_compact_inspection_and_focused_text_preserve_explicit_limits(self):
        harness = r'''let styleCalls=0;
const text='a'.repeat(2300)+' TARGET PHRASE '+ 'z'.repeat(2000);
const body={innerText:text,getClientRects:()=>[1]};
const h1={tagName:'H1',textContent:'SVG-compatible title',getClientRects:()=>[1]};
global.document={body,title:'Fixture',querySelector:s=>s==='body'?body:s==='h1'?h1:null,querySelectorAll:s=>s==='h1,h2,h3'?[h1]:[]};
global.location={href:'https://example.com/'};
global.getComputedStyle=e=>{styleCalls++;return {fontFamily:'font'.repeat(800)}};
const fn=FUNCTION;
const compact=fn({jobs:[{action:'inspect'},{action:'extract',fields:[
{name:'first',selector:'body'},{name:'focused',selector:'body',contains:'target phrase'},
{name:'absent',selector:'body',contains:'not on page'}]}],checks:{textPresent:['target phrase']},needle:''});
const before=styleCalls;
const styled=fn({jobs:[{action:'inspect',includeStyles:true}],checks:{},needle:''});
process.stdout.write(JSON.stringify({compact,styled,before,styleCalls}));'''.replace('FUNCTION', READ_JS)
        result = json.loads(subprocess.run(['node','-e',harness],capture_output=True,text=True,check=True).stdout)
        compact = result['compact']; fields = compact['findings'][1]['fields']
        self.assertEqual(result['before'], 0)
        self.assertEqual(result['styleCalls'], 2)
        self.assertNotIn('bodyStyle', compact['findings'][0])
        self.assertNotIn('style', compact['findings'][0]['headings'][0])
        self.assertEqual(compact['findings'][0]['headings'][0]['text'], 'SVG-compatible title')
        self.assertTrue(fields[0]['truncated']); self.assertEqual(fields[0]['offset'], 0)
        self.assertGreater(fields[0]['totalChars'], 1200)
        self.assertEqual(len(fields[1]['value']), 1200)
        self.assertIn('TARGET PHRASE', fields[1]['value']); self.assertGreater(fields[1]['offset'], 0)
        self.assertTrue(fields[1]['matched']); self.assertTrue(fields[1]['truncated'])
        self.assertEqual(fields[2]['status'], 'missing_text'); self.assertIsNone(fields[2]['value'])
        self.assertTrue(compact['checks'][0]['present'])
        self.assertIn('bodyStyle', result['styled']['findings'][0])

    def test_actual_script_missing_elements_and_style_guard(self):
        harness='''const h1={tagName:'H1',innerText:'Title',getClientRects:()=>[1]};
const body={innerText:'Expected phrase',getClientRects:()=>[1]};
global.document={body,title:'Fixture',querySelector:s=>s==='h1'?h1:null,querySelectorAll:s=>s==='h1,h2,h3'?[h1]:[]};
global.location={href:'https://example.com/'};global.getComputedStyle=e=>{if(!e)throw Error('missing element');return {fontFamily:'test',color:'red'}};
const fn=FUNCTION;
const result=fn({jobs:[{action:'inspect'},{action:'extract',fields:[{name:'missing',selector:'nav a',read:'style'},{name:'title',selector:'h1',read:'style'}]}],checks:{textPresent:['EXPECTED PHRASE'],selectorsPresent:['h1','nav a']},needle:''});
process.stdout.write(JSON.stringify(result));'''.replace('FUNCTION',READ_JS)
        p=subprocess.run(['node','-e',harness],capture_output=True,text=True,check=True)
        result=json.loads(p.stdout)
        self.assertEqual(result['findings'][1]['fields'][0]['status'],'missing')
        self.assertEqual(result['findings'][1]['fields'][1]['value']['fontFamily'],'test')
        self.assertEqual([x['present'] for x in result['checks']],[True,True,False])


if __name__=='__main__':unittest.main()
