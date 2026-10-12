"""Isolated stdio MCP capture bridge for matched Claude browser tests."""
import json,os,pathlib,subprocess,sys,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
ENGINE=ROOT/'dist/BrowserHelm.app/Contents/Resources/engine'
sys.path.insert(0,str(ENGINE))
from gateway import Gateway,encode,rpc_result,tool_result
from browserhelm import BrowserHelmGateway
from experience import ExperienceMemory

COMMON={'run','evaluate','snapshot','screenshot','read','grep','name_session'}
EXTRA={'browserhelm_execute','browserhelm_navigate','browserhelm_visual_act','browserhelm_status','browserhelm_task','neo_help','neo_read_output'}
class LocalMemory(ExperienceMemory):
 def start(self):pass
 def destination(self):return 'isolated-six-case-benchmark'
 def request(self,*args,**kwargs):raise TimeoutError('No benchmark upload or remote recall')
class BenchmarkGateway(BrowserHelmGateway):
 def read_provider_key(self,kind):
  try:
   r=subprocess.run(['/Applications/BrowserHelm.app/Contents/MacOS/BrowserHelm','--provider-key',kind],capture_output=True,timeout=20,check=True)
   key=r.stdout.decode()
   if not key or len(key)>4096 or '\n' in key or '\r' in key:raise ValueError()
   return key
  except Exception:raise ValueError('Benchmark provider credential unavailable; no retry') from None

config=json.loads(pathlib.Path(sys.argv[1]).read_text());work=pathlib.Path(config['work']);settings=config['settings'];mode=config['mode']
g=Gateway(settings['upstream'],work/'outputs',profile='original') if mode=='neo' else BenchmarkGateway(settings,work/'outputs')
if mode!='neo':
 g.settings_path=work/'settings.json';g.enable_metrics(work/'metrics.sqlite')
 if config.get('learning'):g.memory=LocalMemory(settings['memory'],work/'experiences.sqlite')
trace=(work/'mcp.jsonl').open('a',buffering=1);fault=False

def state():
 if not config.get('stateUrl'):return {}
 try:
  with urllib.request.urlopen(config['stateUrl'],timeout=2) as r:return json.load(r)
 except Exception:return {}
try:
 for line in sys.stdin:
  try:request=json.loads(line)
  except ValueError:continue
  injected=False
  if request.get('method')=='initialize':request['params']['clientInfo']['name']=config['clientLabel']
  started=time.time();before=state() if config.get('recovery') else {};name=request.get('params',{}).get('name','')
  if request.get('method')=='tools/call' and name not in COMMON|EXTRA:
   response=rpc_result(request,tool_result('Tool unavailable in this controlled benchmark',True))
  else:response=g.handle(request)
  after=state() if config.get('recovery') else {}
  if config.get('recovery') and not fault and after.get('count',0)>before.get('count',0):
   fault=True;injected=True;response=rpc_result(request,tool_result('Injected transport failure after dispatch: outcome unknown. Inspect current request state before retrying; do not submit twice.',True))
  if request.get('method')=='tools/list' and response and response.get('result',{}).get('tools'):
   response['result']['tools']=[t for t in response['result']['tools'] if t['name'] in COMMON|(EXTRA if mode!='neo' else set())]
  if request.get('method')=='initialize' and response and 'result' in response:
   response['result']['instructions']=response['result'].get('instructions','')+'\nControlled benchmark: operate only the page ID/URLs in the task or tabs you open for its public docs. No other tabs, accounts, downloads, CDP, purchases or real website writes. Close no tabs during the task. No skills or subagents. Return a compact JSON answer.'
  trace.write(json.dumps({'started':started,'finished':time.time(),'method':request.get('method'),'tool':name,'inputBytes':len(encode(request)),'outputBytes':len(encode(response)) if response else 0,'isError':bool(response and (response.get('error') or response.get('result',{}).get('isError'))),'faultInjected':injected,'arguments':request.get('params',{}).get('arguments',{})},ensure_ascii=False)+'\n')
  if response is not None:print(json.dumps(response,ensure_ascii=False),flush=True)
finally:
 if getattr(g,'metrics',None):g.metrics.close()
 if getattr(g,'memory',None):g.memory.close()
 if hasattr(g,'moves_pool'):g.moves_pool.shutdown(wait=True)
 trace.close();g.artifacts.cleanup()
