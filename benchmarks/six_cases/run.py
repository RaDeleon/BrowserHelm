"""Run matched Opus High browser trials sequentially; isolate settings and memory."""
import argparse,datetime,http.server,json,os,pathlib,re,sqlite3,statistics,subprocess,sys,threading,time,uuid
from scenarios import CASES,page,verify
ROOT=pathlib.Path(__file__).resolve().parents[2]
ENGINE=ROOT/'dist/BrowserHelm.app/Contents/Resources/engine';sys.path.insert(0,str(ENGINE))
from browserhelm import BrowserHelmGateway
from version import VERSION
PYTHON=ROOT/'dist/BrowserHelm.app/Contents/Resources/runtime/bin/python3.12'
STATES={};LOCK=threading.Lock()
class Fixture(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  key=self.path.split('/')[2] if self.path.startswith('/run/') else ''
  with LOCK:s=STATES.get(key,{}).copy()
  if not s:self.send_error(404);return
  data=json.dumps({k:v for k,v in s.items() if k!='case'}).encode() if self.path.endswith('/state') else page(s['case'],key).encode()
  self.send_response(200);self.send_header('Content-Type','application/json' if self.path.endswith('/state') else 'text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_POST(self):
  key=self.path.split('/')[2];target=self.rfile.read(int(self.headers.get('Content-Length',0))).decode()
  with LOCK:
   s=STATES[key];s['count']+=1;s['target']=target;data=json.dumps({'count':s['count']}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

def parse_answer(result):
 data=result.get('structured_output')
 if isinstance(data,dict):return data
 text=result.get('result','')
 for match in re.finditer(r'\{',text):
  try:return json.JSONDecoder().raw_decode(text[match.start():])[0]
  except ValueError:pass
 return None

def summaries(rows):
 out={}
 for case in CASES:
  out[case['id']]={}
  for mode in ('neo','off','on'):
   group=[r for r in rows if r['case']==case['id'] and r['mode']==mode]
   if not group:continue
   times=sorted(r['elapsedSeconds'] for r in group)
   out[case['id']][mode]={'attempts':len(group),'successes':sum(r['verified'] for r in group),'medianSecondsAllAttempts':statistics.median(times),'maxSecondsAllAttempts':max(times),'mainAgentTurns':None if any(r.get('mainAgentTurns') is None for r in group) else sum(r['mainAgentTurns'] for r in group),'reportedApiEquivalentUSD':None if any(r.get('apiEquivalentUSD') is None for r in group) else sum(r['apiEquivalentUSD'] for r in group),'knownApiEquivalentUSD':sum(r.get('apiEquivalentUSD') or 0 for r in group),'unknownUsageAttempts':sum(r.get('mainAgentUsage') is None for r in group),'totalTaskCostUSD':None}
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repeats',type=int,default=1);ap.add_argument('--cases',default='all');ap.add_argument('--modes',default='neo,off,on');ap.add_argument('--model',default='claude-opus-5-5');ap.add_argument('--timeout',type=int,default=180);ap.add_argument('--api-equivalent-cap',type=float,default=10);ap.add_argument('--vision',choices=['local','saved'],default='local');ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
 output=args.output or ROOT/'dist/benchmarks'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');output=output.resolve();output.mkdir(parents=True,exist_ok=True)
 settings=json.loads((pathlib.Path.home()/'Library/Application Support/BrowserHelm/settings.json').read_text())
 settings.update(compactCatalog=False,configVersion=3);settings['memory']={'enabled':False}
 if args.vision=='local':settings['vision']={'enabled':True,'provider':'ollama','endpoint':'http://127.0.0.1:11434','model':'qwen3-vl:2b-instruct'}
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=server.serve_forever,daemon=True).start()
 admin=BrowserHelmGateway({'provider':'none','upstream':settings['upstream'],'delegationEnabled':False},output/'verification-outputs')
 admin.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Six-case benchmark verification','version':'1'}}});admin.upstream_call({'jsonrpc':'2.0','method':'notifications/initialized'})
 rows=[];spent=0.;stop=False;fixture_owned=[]
 selected=[c for c in CASES if args.cases=='all' or c['id'] in args.cases.split(',')]
 report={'model':args.model,'effort':'high','engineVersion':VERSION,'client':subprocess.run(['claude','--version'],capture_output=True,text=True,check=True).stdout.strip(),'agentTaskMarkers':settings.get('agentTaskMarkers',False),'vision':settings['vision'],'costBasis':'Claude client-reported API-equivalent list cost on Max, not subscription charge/allowance; unknown provider and memory costs remain unknown','limits':{'repeats':args.repeats,'perAttemptSeconds':args.timeout,'apiEquivalentCapUSD':args.api_equivalent_cap},'scope':'Controlled task-specific tool exposure; no skills/subagents; temporary fixture writes only. Not an exact Claude Desktop reproduction.','runs':rows}
 def save():
  report['summary']=summaries(rows);(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
  with (output/'results.csv').open('w') as f:
   import csv
   fields=['case','mode','repeat','phase','verified','elapsedSeconds','mainAgentTurns','mainAgentToolCalls','apiEquivalentUSD','reason'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in rows)
  (output/'progress.json').write_text(json.dumps({'completed':len(rows),'last':rows[-1]['case']+' '+rows[-1]['mode'] if rows else None,'apiEquivalentUSD':spent,'stopped':stop})+'\n')
 try:
  for repeat in range(args.repeats):
   for case in selected:
    modes=args.modes.split(',');modes=modes[repeat%len(modes):]+modes[:repeat%len(modes)]
    for mode in modes:
     if spent>=args.api_equivalent_cap:stop=True;break
     ident=uuid.uuid4().hex[:12];label='sixcase-'+ident;work=output/(case['id']+'-'+mode+'-'+str(repeat+1));work.mkdir()
     state={'count':0,'target':None};fixture_page=None;cfg=json.loads(json.dumps(settings));cfg['delegationEnabled']=mode=='on'
     learning=case['id']=='06_learning' and mode=='on'
     if learning:cfg['memory']={'enabled':True}
     (work/'settings.json').write_text(json.dumps(cfg))
     if learning:
      # Share only this exact case's local evidence across fresh Claude chats.
      common=output/'learning-on';common.mkdir(exist_ok=True)
      for filename in ('experiences.sqlite',):
       source=common/filename
       if source.exists():import shutil;shutil.copy2(source,work/filename)
     fixture_url='http://127.0.0.1:%s/run/%s'%(server.server_port,ident)
     if case['fixture']:
      with LOCK:STATES[ident]={'case':case['id'],**state}
      fixture_page=admin.run_browser('const p=await browser.open(%s);const r=await p.waitForSelector(%s,{timeout:10000});if(!r.matched)throw new Error("Fixture not ready");return p.id;'%(json.dumps(fixture_url),json.dumps('canvas' if case['id']=='04_vision' else 'h1')))
     if fixture_page:fixture_owned.append(fixture_page)
     bridge={'work':str(work),'settings':cfg,'mode':mode,'learning':learning,'clientLabel':label,'stateUrl':fixture_url+'/state' if case['fixture'] else None,'recovery':case['id']=='05_recovery'}
     (work/'bridge.json').write_text(json.dumps(bridge))
     mcp={'mcpServers':{'browser':{'type':'stdio','command':str(PYTHON),'args':['-I','-B',str(ROOT/'benchmarks/six_cases/bridge.py'),str(work/'bridge.json')]}}};(work/'mcp.json').write_text(json.dumps(mcp))
     prompt=case['task']+('\nYour owned fixture is page %s, URL %s. Use this page, not other tabs.'%(fixture_page,fixture_url) if case['fixture'] else '\nOpen only owned tabs for this public documentation task.')+'\nUse only the provided browser MCP. Return only the requested JSON. Do not use skills/subagents or access other sites/accounts. At most 16 main-agent tool calls; stop with an honest failure if blocked. Keep complex reasoning with the main model.'
     if mode=='on' and case['id'] in ('01_styles','02_navigation','06_learning'):prompt+='\nFor this delegation arm, use browserhelm_execute for the supported bounded read-only plan. Keep interpretation and recovery with Opus.'
     if mode=='on' and case['id']=='04_vision':prompt+='\nFor this delegation arm, use browserhelm_visual_act with the selected vision provider, then verify the actual fixture outcome.'
     (work/'prompt.txt').write_text(prompt)
     command=['claude','-p',prompt,'--model',args.model,'--effort','high','--restricted','--tools','','--disable-slash-commands','--setting-sources','','--strict-mcp-config','--mcp-config',str(work/'mcp.json'),'--allowedTools','mcp__browser__*','--output-format','stream-json','--verbose','--no-session-persistence','--permission-mode','dontAsk','--permission-prompts','none','--max-budget-usd','2']
     started=time.monotonic();result={};failure=None
     print('START '+case['id']+' '+mode+' repeat='+str(repeat+1),flush=True)
     with (work/'claude.jsonl').open('w') as stdout,(work/'stderr.log').open('w') as stderr:
      process=subprocess.Popen(command,stdout=stdout,stderr=stderr,cwd=work,start_new_session=True)
      while process.poll() is None and time.monotonic()-started<args.timeout:time.sleep(.25)
      if process.poll() is None:
       import signal
       os.killpg(process.pid,signal.SIGTERM);failure='Elapsed budget reached; inspect outcome'
       try:process.wait(timeout=5)
       except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
     stream=[]
     for line in (work/'claude.jsonl').read_text().splitlines():
      try:x=json.loads(line);stream.append(x)
      except ValueError:continue
      if x.get('type')=='result':result=x
     calls=[b for x in stream if x.get('type')=='assistant' for b in x.get('message',{}).get('content',[]) if b.get('type')=='tool_use']
     answer=parse_answer(result)
     own=[]
     try:
      own=admin.run_browser('const ps=await browser.pages.list();return ps.filter(p=>p.ownerLabel===%s).map(p=>({pageId:p.pageId,url:p.url}));'%json.dumps(label))
      if case['fixture']:
       with LOCK:state=STATES[ident].copy();state.pop('case',None)
      else:
       # Tab-list URL metadata can lag SPA navigation. Verify current DOM/location
       # on this attempt's owned tabs instead of filtering by cached URL first.
       if len(own)>5:raise ValueError('Too many owned tabs for bounded verification')
       observations=admin.run_browser('const out=[];for(const id of %s){const p=await browser.page(id);try{const r=await p.evaluate(()=>({url:location.href,heading:document.querySelector("h1")?.innerText,hasExplanation:document.body.innerText.includes("floats that sum to 1")}));out.push(r.value);}catch{out.push({readFailed:true});}}return out;'%json.dumps([p['pageId'] for p in own])) if own else []
       state={'publicVerified':any(isinstance(o,dict) and o.get('url','').split('#')[0].rstrip('/')=='https://docs.typesafe.ai/api' and o.get('heading')=='API reference' and o.get('hasExplanation') is True for o in observations),'observations':observations}
      outcome=verify(case['id'],answer,state)
     except Exception as e:outcome={'verified':False,'reason':'Independent verification failed: '+type(e).__name__}
     elapsed=time.monotonic()-started
     cost=result.get('total_cost_usd');spent+=cost or 0
     traces=[]
     if (work/'mcp.jsonl').exists():
      traces=[json.loads(line) for line in (work/'mcp.jsonl').read_text().splitlines()]
     provider=[]
     if (work/'metrics.sqlite').exists():
      try:
       with sqlite3.connect(work/'metrics.sqlite') as db:
        provider=[{'kind':r[0],'provider':r[1],'model':r[2],'status':r[3],'usage':json.loads(r[4]),'latencySeconds':r[5]} for r in db.execute('SELECT kind,provider,model,status,usage,latency FROM provider_usage')]
      except sqlite3.Error:pass
     row={'case':case['id'],'name':case['name'],'mode':mode,'repeat':repeat+1,'phase':'first' if repeat==0 else 'learned-repeat' if learning and repeat>=2 else 'warm-no-learning' if not learning else 'learning-acquisition','verified':outcome['verified'] and result.get('subtype')=='success','reason':failure or outcome['reason'],'elapsedSeconds':round(elapsed,3),'mainAgentTurns':result.get('num_turns'),'mainAgentToolCalls':len(calls),'toolNames':[c.get('name') for c in calls],'mainAgentUsage':result.get('usage'),'modelUsage':result.get('modelUsage'),'apiEquivalentUSD':cost,'totalTaskCostUSD':None,'providerUsage':provider,'answer':answer,'oracle':outcome,'transportErrors':sum(t['isError'] for t in traces if t.get('method')=='tools/call'),'faultInjected':any(t.get('faultInjected') for t in traces),'exitCode':process.returncode,'rawDir':str(work.relative_to(ROOT))}
     actual=next((x.get('model') for x in stream if x.get('type')=='system' and x.get('model')),None)
     row['actualModel']=actual
     if actual!=args.model:row.update(verified=False,reason='Main-agent model mismatch or unavailable')
     if case['id']=='05_recovery' and not row['faultInjected']:row.update(verified=False,reason='Recovery fault was not exercised')
     rows.append(row)
     if learning and (work/'experiences.sqlite').exists():
      import shutil
      shutil.copy2(work/'experiences.sqlite',output/'learning-on/experiences.sqlite')
     save();print('DONE '+case['id']+' '+mode+' verified='+str(row['verified'])+' seconds='+str(row['elapsedSeconds'])+' apiEquivalentUSD='+str(cost),flush=True)
     for pid in [p['pageId'] for p in own]+([fixture_page] if fixture_page else []):
      try:admin.run_browser('const p=await browser.page(%s);await p.close();return true;'%pid)
      except Exception:pass
    if stop:break
   if stop:break
 finally:
  stop=stop or spent>=args.api_equivalent_cap;save()
  for pid in fixture_owned:
   try:admin.run_browser('const p=await browser.page(%s);await p.close();return true;'%pid)
   except Exception:pass
  server.shutdown();admin.moves_pool.shutdown(wait=True);admin.artifacts.cleanup()
 print('RESULTS '+str(output/'results.json'),flush=True)
if __name__=='__main__':main()
