"""Live browser + OpenViking smoke. Deterministic observed-link selector, no LLM call."""
import json
import pathlib
import tempfile
import time
from unittest.mock import patch
from experience import ExperienceMemory
from browserhelm import BrowserHelmGateway

class ValidationSelector:
    kind='validation (deterministic; no LLM)'
    def choose(self, state, options):
        choice=next((key for key,value in options.items() if isinstance(value,dict) and value.get('url','').rstrip('/')=='https://docs.typesafe.ai/api'), 'BLOCKED')
        return {'choice':choice,'probability':None,'evidence':'deterministic public API-link validation','usage':{},'model':'no model','latencySeconds':0}

root=pathlib.Path(__file__).resolve().parent.parent
support=pathlib.Path.home()/'Library/Application Support/BrowserHelm'
settings=json.loads((support/'settings.json').read_text())
g=BrowserHelmGateway(settings,support/'outputs')
g.memory=ExperienceMemory(settings.get('memory',{}),support/'experiences.sqlite')
args={'startUrl':'https://docs.typesafe.ai/models','goal':'BrowserHelm validation: find the API reference describing choice-answer probabilities','successText':'floats that sum to 1','maxSteps':2}
page=None
try:
    init=g.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'BrowserHelm memory validation','version':'0.4.0'}}})
    assert 'error' not in init,init
    g.handle({'jsonrpc':'2.0','method':'notifications/initialized'})
    with patch.object(g,'provider',return_value=ValidationSelector()):
        report=g.navigate(args,'validation')
    page=report.get('pageId')
    assert report['verified'] is True,report
    assert report['memory']['outcome']=='queued',report
    g.memory.sync(limit=5)
    with g.memory.db() as db:
        identifier,document,synced=db.execute('SELECT id,document,synced FROM experiences ORDER BY created DESC LIMIT 1').fetchone()
    assert synced is not None
    import urllib.parse
    remote=g.memory.request('/api/v1/content/read?'+urllib.parse.urlencode({'uri':g.memory.root+'/'+identifier+'.md'}))
    assert json.loads(remote)==json.loads(document)
    # Empty local cache: this recall must come from the actual OpenViking server.
    with tempfile.TemporaryDirectory() as tmp:
        memory=ExperienceMemory({'enabled':True},pathlib.Path(tmp)/'experiences.sqlite')
        memory.test()
        hints=[]
        # Upload acceptance precedes indexing. Retry only retrieval, never browser actions.
        for attempt in range(5):
            hints=memory.recall('https://docs.typesafe.ai/models',args['goal'],args['successText'])
            if hints:break
            time.sleep(1)
        assert hints and any(h['outcome']=='successText found' for h in hints),hints
    result={'version':'0.4.0','browserPostconditionVerified':True,'remoteWriteReadback':True,
            'remoteRecallWithoutLocalCache':True,'recalledHints':len(hints),
            'browserCalls':report['browserCalls'],'providerCalled':False,
            'selector':'deterministic validation against current observed links; not a live Jev test'}
    (root/'dist/memory-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
finally:
    if page:
        try:g.run_browser('const p=await browser.page(%s); await p.close(); return true;'%json.dumps(page))
        except Exception:pass
    if g.memory:g.memory.close()
    g.moves_pool.shutdown(wait=True);g.artifacts.cleanup()
