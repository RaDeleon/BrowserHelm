"""Public-page learning validation. No Jev/LLM calls; owned tabs and a temporary cache.

--remote also uploads one explicitly tagged validation outcome to the configured
OpenViking service and reads it back. Embedding/storage costs may apply.
"""
import argparse
import json
import pathlib
import tempfile
import urllib.parse
from unittest.mock import patch
from experience import ExperienceMemory
from browserhelm import BrowserHelmGateway
from version import VERSION


class ObservedLinkSelector:
    kind = 'custom'  # Temporary controlled evidence only; this is not an LLM.
    def __init__(self): self.calls = 0
    def choose(self, state, options):
        self.calls += 1
        choice = next((key for key, value in options.items() if isinstance(value, dict) and value.get('url','').rstrip('/')=='https://docs.typesafe.ai/api'), 'BLOCKED')
        return {'choice':choice,'probability':None,'evidence':'deterministic live validation selector',
                'usage':{},'model':'no model','latencySeconds':0}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--remote', action='store_true'); args = parser.parse_args()
    support = pathlib.Path.home()/'Library/Application Support/BrowserHelm'
    settings = json.loads((support/'settings.json').read_text())
    owned = []
    with tempfile.TemporaryDirectory(prefix='browserhelm-learning-') as tmp:
        root = pathlib.Path(tmp)
        g = BrowserHelmGateway(settings, root/'outputs')
        memory = ExperienceMemory({'enabled':True}, root/'experiences.sqlite')
        g.memory = memory
        selector = ObservedLinkSelector()
        task = {'startUrl':'https://docs.typesafe.ai/models', 'goal':'Find the API reference describing choice-answer probabilities',
                'successText':'floats that sum to 1', 'maxSteps':2}
        reports = []
        try:
            init = g.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25',
                             'capabilities':{},'clientInfo':{'name':'BrowserHelm controlled learning validation','version':VERSION}}})
            assert 'error' not in init, init
            g.handle({'jsonrpc':'2.0','method':'notifications/initialized'})
            # No background uploads; the first recall is deliberately offline.
            with patch.object(g,'provider',return_value=selector), patch.object(memory,'start'), patch.object(memory,'request',side_effect=TimeoutError):
                for attempt in range(3):
                    before = selector.calls
                    report = g.navigate(task, attempt+10)
                    if report.get('pageId'): owned.append(report['pageId'])
                    assert report['verified'] is True, report
                    reports.append({'verified':True, 'selectorCalls':selector.calls-before, 'browserCalls':report['browserCalls'],
                                    'providerCallsAvoided':report.get('memory',{}).get('providerCallsAvoided',0),
                                    'elapsedSeconds':report['elapsedSeconds']})
            assert [r['selectorCalls'] for r in reports] == [1,1,0], reports
            assert reports[-1]['providerCallsAvoided']==1
            request={'jsonrpc':'2.0','method':'tools/call','params':{'name':'run','arguments':{'code':'throw new Error("BrowserHelm controlled learning failure");'}}}
            first=g.handle({**request,'id':20}); second=g.handle({**request,'id':21})
            assert 'priorMatchingFailures' not in json.dumps(first)
            assert 'priorMatchingFailures' in json.dumps(second), second
            result={'version':VERSION,'runs':reports,'liveLinkAndTextVerification':True,'repeatFailureHint':True,
                    'providerCalled':False,'selector':'deterministic observed-link selector, not Jev',
                    'memoryCounters':{k:memory.snapshot()[k] for k in ('tasks_with_reuse','provider_calls_avoided','reused_tasks_verified','repeat_failure_hints')},
                    'remoteWriteReadback':False}
            if args.remote:
                # Controlled task evidence must not enter production reuse or hint selection.
                with memory.db() as db: db.execute('DELETE FROM experiences')
                report={**report,'provider':'validation (deterministic; no LLM)'}
                assert memory.capture(task['startUrl'],'BrowserHelm 0.4.2 controlled learning validation',task['successText'],report,
                                      [{'from':task['startUrl'],'to':'https://docs.typesafe.ai/api','label':'API reference'}],test=True)=='queued'
                memory.test(); memory.sync(limit=1)
                with memory.db() as db: identifier,raw,synced=db.execute('SELECT id,document,synced FROM experiences').fetchone()
                assert synced is not None
                remote=memory.request('/api/v1/content/read?'+urllib.parse.urlencode({'uri':memory.root+'/'+identifier+'.md'}))
                if isinstance(remote,dict):remote=remote.get('content','')
                assert json.loads(remote)==json.loads(raw)
                result['remoteWriteReadback']=True
                result['remoteRecordMarkedTest']=True
            print(json.dumps(result,indent=2))
        finally:
            for page in owned:
                try:g.run_browser('const p=await browser.page(%s); await p.close(); return true;'%json.dumps(page))
                except Exception:pass
            memory.close(); g.moves_pool.shutdown(); g.artifacts.cleanup()


if __name__=='__main__':main()
