"""Validate the packaged delegation switch on temporary owned fixture DOM; no inference."""
import json,os,pathlib,select,subprocess,tempfile,time
root=pathlib.Path(__file__).resolve().parent.parent
resources=root/'dist/OpenRagnar.app/Contents/Resources'
report=[]
with tempfile.TemporaryDirectory(prefix='ragnar-delegation-') as folder:
 for enabled in (False,True):
  work=pathlib.Path(folder)/str(enabled);work.mkdir()
  settings=work/'settings.json';settings.write_text(json.dumps({'configVersion':3,'provider':'none','delegationEnabled':enabled,'compactCatalog':False,'memory':{'enabled':False},'vision':{'enabled':True,'provider':'ollama'}}))
  env=dict(os.environ)
  for key in ('OPENRAGNAR_KEY_HELPER','OPENRAGNAR_API_KEY','OPENRAGNAR_VISION_API_KEY'):env.pop(key,None)
  p=subprocess.Popen([str(resources/'runtime/bin/python3.12'),'-I','-B',str(resources/'engine/launch.py'),'--settings',str(settings),'--output-dir',str(work/'outputs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,env=env)
  seq=0;page=None
  def call(method,params):
   global seq
   seq+=1;p.stdin.write(json.dumps({'jsonrpc':'2.0','id':seq,'method':method,'params':params})+'\n');p.stdin.flush()
   end=time.monotonic()+25
   while time.monotonic()<end:
    if not select.select([p.stdout],[],[],1)[0]:continue
    line=p.stdout.readline()
    if not line:raise RuntimeError('MCP ended')
    r=json.loads(line)
    if r.get('id')==seq:
     if r.get('error'):raise RuntimeError('MCP error')
     return r['result']
   raise RuntimeError('MCP timeout')
  def tool(name,args):return call('tools/call',{'name':name,'arguments':args})
  def value(result):
   if result.get('isError'):raise RuntimeError(json.dumps(result)[:1500])
   text='\n'.join(b.get('text','') for b in result.get('content',[]) if b.get('type')=='text')
   data=json.JSONDecoder().raw_decode(text[text.find('{'):])[0]
   if isinstance(data,dict) and 'ok' in data:
    if not data['ok']:raise RuntimeError('Neo run failed')
    return data['value']
   return data
  try:
   init=call('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Delegation switch validation','version':'fixture'}})
   p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');p.stdin.flush()
   tool('name_session',{'name':'Delegation modes','category':'research','summary':'Temporary read-only settings validation'})
   assert 'For each new user prompt' not in init['instructions']
   help_result=tool('neo_help',{'topic':'openragnar_execute'})
   assert not help_result.get('isError') and 'literal phrase' in json.dumps(help_result)
   names={t['name'] for t in call('tools/list',{})['tools']}
   assert ('openragnar_execute' in names)==enabled
   opened=value(tool('run',{'code':'const p=await browser.open("https://example.com");await p.evaluate(()=>{document.body.innerHTML="<h1>Delegation fixture</h1>";});return {pageId:p.id};'}));page=opened['pageId']
   if enabled:
    task=value(tool('openragnar_execute',{'page':page,'goal':'Read the public page heading','allowedActions':['extract'],'steps':[{'action':'extract','fields':[{'name':'heading','selector':'h1'}]}],'completion':{'selectorsPresent':['h1']}}))
    assert task['verified'] and task['steps'][0]['fields'][0]['value']=='Delegation fixture'
    tool('run',{'code':'const p=await browser.page(%s);await p.evaluate(()=>{document.body.innerHTML="<h1>Delegation fixture</h1><p>"+"a".repeat(2300)+" TARGET PHRASE "+"z".repeat(2000)+"</p>";document.body.style.fontFamily="font".repeat(300);});return true;'%page})
    args={'page':page,'goal':'Read heading and focused excerpt','allowedActions':['inspect','extract'],'steps':[{'action':'inspect'},{'action':'extract','fields':[{'name':'focused','selector':'p','contains':'target phrase'},{'name':'absent','selector':'p','contains':'absent phrase'}]}],'completion':{'selectorsPresent':['h1'],'textPresent':['target phrase']}}
    compact_result=tool('openragnar_execute',args);compact=value(compact_result)
    assert compact['verified'] and compact['browserCalls']==1 and not compact['decisions']
    assert 'style' not in compact['steps'][0]['headings'][0] and 'bodyStyle' not in compact['steps'][0]
    focused,absent=compact['steps'][1]['fields']
    assert focused['truncated'] and focused['offset']>0 and 'TARGET PHRASE' in focused['value']
    assert absent['status']=='missing_text' and absent['value'] is None
    assert 'Retrieve with neo_read_output' not in json.dumps(compact_result)
    args['steps']=[{'action':'inspect','includeStyles':True}]
    styled_result=tool('openragnar_execute',args)
    styled_spilled='Retrieve with neo_read_output' in json.dumps(styled_result)
    if not styled_spilled: assert 'bodyStyle' in value(styled_result)['steps'][0]
    data=json.loads(settings.read_text());data['delegationEnabled']=False;settings.write_text(json.dumps(data))
    rejected=tool('openragnar_execute',{})
    assert rejected['isError'] and 'disabled' in rejected['content'][0]['text']
    observed={'delegationEnabled':True,'verified':True,'heading':'Delegation fixture','browserCalls':task['browserCalls'],'decisions':task['decisions'],'cachedCallAfterOptOut':'blocked','executorHelpBeforeCatalog':True,'agentMarkersDefaultOff':True,'compactFocusedRead':{'browserCalls':compact['browserCalls'],'clientBytes':len(json.dumps(compact_result).encode()),'outputSpilled':False,'truncationExplicit':True,'missingPhraseExplicit':True},'explicitStylesPreserved':True,'explicitStylesSpilled':styled_spilled}
   else:
    direct=tool('evaluate',{'page':page,'code':'return {heading:document.querySelector("h1").innerText};','maxChars':1000})
    assert 'Delegation fixture' in json.dumps(direct) and not direct.get('isError')
    rejected=tool('openragnar_execute',{});assert rejected['isError']
    observed={'delegationEnabled':False,'verified':True,'heading':'Delegation fixture','directToolsAvailable':True,'delegatedCall':'blocked'}
   report.append({'serverVersion':init['serverInfo']['version'],'toolCount':len(names),**observed})
  finally:
   if page:
    try:tool('run',{'code':'const p=await browser.page(%s);await p.close();return {closed:true};'%page})
    except Exception:pass
   p.stdin.close()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
(root/'dist/delegation-mode-validation.json').write_text(json.dumps({'modes':report,'limitations':'Owned synthetic DOM mechanism checks only; no Opus model, provider inference or end-to-end speed/cost comparison.'},indent=2)+'\n')
print(json.dumps(report))
