"""Separate learning/freshness mechanism control. Not an Opus/Jev task benchmark."""
import json,pathlib,sys,tempfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dist/BrowserHelm.app/Contents/Resources/engine'))
from browserhelm import BrowserHelmGateway
from executor import execute
from experience import ExperienceMemory
class Memory(ExperienceMemory):
 def start(self):pass
 def destination(self):return 'six-case-learning-control'
 def request(self,*a,**k):raise TimeoutError('No remote memory traffic')
class Selector:
 kind='custom';model='deterministic-control'
 def __init__(self):self.calls=0
 def choose(self,state,options):
  self.calls+=1
  choice=next((k for k,v in options.items() if isinstance(v,dict) and v.get('url')=='https://docs.typesafe.ai/api'),'BLOCKED')
  return {'choice':choice,'probability':1,'usage':{},'model':self.model,'latencySeconds':0}
settings=json.loads((pathlib.Path.home()/'Library/Application Support/BrowserHelm/settings.json').read_text());settings['memory']={'enabled':True}
args={'startUrl':'https://docs.typesafe.ai/models','goal':'Find the API reference and read its first heading','allowedActions':['navigate','extract'],'steps':[{'action':'navigate','text':'floats that sum to 1','maxHops':2},{'action':'extract','fields':[{'name':'heading','selector':'h1'}]}],'completion':{'textPresent':['floats that sum to 1'],'selectorsPresent':['h1']},'maxSeconds':45}
rows=[];owned=[]
with tempfile.TemporaryDirectory(prefix='ragnar-sixcase-learning-') as folder:
 memory=Memory(settings['memory'],pathlib.Path(folder)/'experiences.sqlite');selector=Selector()
 for i in range(3):
  g=BrowserHelmGateway(settings,pathlib.Path(folder)/('outputs-'+str(i)));g.memory=memory
  g.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Six-case isolated learning control','version':'1'}}});g.upstream_call({'jsonrpc':'2.0','method':'notifications/initialized'})
  with patch.object(g,'provider',return_value=selector):
   before=selector.calls;r=execute(g,args,10+i)
  rows.append({'freshConnection':True,'verified':r['verified'],'elapsedSeconds':r['elapsedSeconds'],'selectorCalls':selector.calls-before,'providerCallsAvoided':r['memory']['providerCallsAvoided'],'browserCalls':r['browserCalls']})
  if r.get('pageId'):
   g.run_browser('const p=await browser.page(%s);await p.close();return true;'%r['pageId'])
  g.moves_pool.shutdown(wait=True);g.artifacts.cleanup()
 assert [r['selectorCalls'] for r in rows]==[1,1,0] and all(r['verified'] for r in rows),rows
 # Failure support invalidates the same proven edge; verify current options no longer authorize reuse.
 import hashlib
 from gateway import encode
 contract=hashlib.sha256(encode({k:v for k,v in args.items() if k not in ('page','startUrl','maxSeconds','maxBrowserCalls')})).hexdigest();goal='executor:'+contract
 route=[{'from':'https://docs.typesafe.ai/models','to':'https://docs.typesafe.ai/api','label':'API reference'}]
 memory.capture(args['startUrl'],goal,'floats that sum to 1',{'provider':'custom','verified':False,'status':'escalate','failureCategory':'stale_link','attempts':route},route)
 choice=memory.choose_verified_route(args['startUrl'],goal,'floats that sum to 1','https://docs.typesafe.ai/models',{'L0':{'url':'https://docs.typesafe.ai/api','label':'API reference'},'BLOCKED':'none'})
 assert choice is None
 memory.close()
report={'runs':rows,'staleFailureInvalidatesReuse':True,'provider':'deterministic selector; no Jev/LLM','openVikingNetworkCalls':0,'mainAgentMeasured':False,'limitations':'Controlled learning mechanism only. Fresh gateway connections; not fresh Opus chats or a matched end-to-end speed claim.'}
p=ROOT/'dist/benchmarks/learning-control.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
