"""Owned Neo fixture and matched browser-call comparison; no paid model inference."""
import copy
import json
import pathlib
import statistics
import sys
import tempfile
import time
from unittest.mock import patch
from executor import execute, read_page
from openragnar import OpenRagnarGateway, load_settings


def main():
    root=pathlib.Path(__file__).resolve().parent.parent
    settings=load_settings(pathlib.Path.home()/'Library/Application Support/OpenRagnar/settings.json')
    # Synthetic fixture stays local and never uploads to the user's memory collection.
    settings['memory']={'enabled':False}
    with tempfile.TemporaryDirectory(prefix='openragnar-executor-') as temporary:
        gateway=OpenRagnarGateway(settings,pathlib.Path(temporary)/'outputs')
        init=gateway.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
            'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'OpenRagnar executor validation','version':'fixture'}}})
        if init.get('error'):raise RuntimeError('Neo handshake failed')
        gateway.upstream_call({'jsonrpc':'2.0','method':'notifications/initialized'})
        gateway.upstream_call({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'name_session','arguments':{
            'name':'Executor validation','category':'research','summary':'Owned fixture; batching and guarded extraction'}}})
        page=gateway.run_browser('const p=await browser.open("https://example.com");return p.id;')
        checks={'textPresent':['Executor ready'],'selectorsPresent':['h1']}
        jobs=[{'action':'inspect'},{'action':'extract','fields':[
            {'name':'headingStyle','selector':'h1','read':'style'},
            {'name':'missingLink','selector':'a[data-missing]','read':'style'}]}]
        args={'page':page,'goal':'Inspect headings and a missing link safely','allowedActions':['inspect','extract'],
              'steps':jobs,'completion':checks}
        report={'workload':'Owned static DOM inspection; warm browser; deterministic reads; no main-agent timing or billed cost',
                'samples':[]}
        try:
            gateway.run_browser('const p=await browser.page(%s);await p.evaluate(()=>{document.body.innerHTML="<h1>Executor ready</h1><p>Owned validation fixture</p>"});return true;' % page)
            for mode in ['direct','executor','executor','direct','direct','executor','executor','direct','direct','executor','executor','direct']:
                begin=time.monotonic()
                if mode=='direct':
                    results=[read_page(gateway,page,[job],checks) for job in jobs]
                    verified=all(all(c['present'] for c in r['checks']) for r in results)
                    missing=results[1]['findings'][0]['fields'][1]['status']
                    calls=2
                else:
                    result=execute(gateway,args,123)
                    verified=result['verified'];calls=result['browserCalls'];missing=result['steps'][1]['fields'][1]['status']
                report['samples'].append({'mode':mode,'elapsedSeconds':time.monotonic()-begin,'browserCalls':calls,
                                         'verified':verified,'missingField':missing})
                assert verified and missing=='missing'
            # An unmet required condition escalates with partial results.
            failed=execute(gateway,{**args,'completion':{'selectorsPresent':['a[data-missing]']}},124)
            assert not failed['verified'] and failed['failureCategory']=='verification_failed'
            # A real public route uses a deterministic fixture selector to exercise the loop without fees.
            navigation={ 'startUrl':'https://docs.typesafe.ai/models','goal':'Find the API reference and inspect the heading',
                'allowedActions':['navigate','inspect','extract'],
                'steps':[{'action':'navigate','text':'floats that sum to 1','maxHops':2},{'action':'inspect'},
                         {'action':'extract','fields':[{'name':'heading','selector':'h1'}]}],
                'completion':{'textPresent':['floats that sum to 1'],'selectorsPresent':['h1']}}
            class FixtureProvider:
                kind='deterministic-validation';model='fixture-selector'
                def choose(self,state,options):
                    target=next((k for k,v in options.items() if isinstance(v,dict) and v.get('url')=='https://docs.typesafe.ai/api'),'BLOCKED')
                    return {'choice':target,'probability':1,'evidence':'fixture','usage':{},'model':self.model}
            with patch.object(gateway,'provider',return_value=FixtureProvider()):
                nav=execute(gateway,navigation,125)
            report['publicNavigation']=nav
            if nav.get('pageId'):gateway.run_browser('const p=await browser.page(%s);await p.close();return true;' % nav['pageId'])
            assert nav['verified'],nav.get('reason')
            report['summary']={mode:{'n':6,'successes':sum(s['verified'] for s in report['samples'] if s['mode']==mode),
                'medianSeconds':statistics.median(s['elapsedSeconds'] for s in report['samples'] if s['mode']==mode),
                'browserCallsPerTask':2 if mode=='direct' else 1} for mode in ['direct','executor']}
            report['limitations']='Mechanism validation only. No Claude turns/usage, paid Jev or vision comparison, cold start, or general 10x evidence.'
            (root/'dist').mkdir(exist_ok=True)
            (root/'dist/executor-validation.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({'summary':report['summary'],'navigationVerified':nav['verified'],'navigationCalls':nav['browserCalls'],'limitations':report['limitations']}))
        finally:
            gateway.run_browser('const p=await browser.page(%s);await p.close();return true;' % page)
            gateway.moves_pool.shutdown(wait=True);gateway.artifacts.cleanup()


if __name__=='__main__':main()
