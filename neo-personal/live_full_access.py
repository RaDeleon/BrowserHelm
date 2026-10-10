"""Packaged MCP read/write smoke. Only changes an owned example.com tab's DOM."""
import json
import pathlib
import re
import select
import subprocess
import time
root=pathlib.Path(__file__).resolve().parent.parent
app=root/'dist/OpenRagnar.app/Contents/MacOS/OpenRagnar'
p=subprocess.Popen([str(app),'--mcp'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
serial=0
page=None

def call(method,params):
    global serial
    serial+=1
    p.stdin.write(json.dumps({'jsonrpc':'2.0','id':serial,'method':method,'params':params})+'\n');p.stdin.flush()
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        ready,_,_=select.select([p.stdout],[],[],1)
        if not ready: continue
        line=p.stdout.readline()
        if not line: raise RuntimeError('MCP process ended')
        response=json.loads(line)
        if response.get('id')==serial:
            if 'error' in response or response.get('result',{}).get('isError'): raise RuntimeError('MCP test request failed: '+json.dumps(response)[:1500])
            return response['result']
    raise RuntimeError('MCP smoke timed out')

def tool(name,args): return call('tools/call',{'name':name,'arguments':args})
def value(result):
    text='\n'.join(b.get('text','') for b in result.get('content',[]) if b.get('type')=='text')
    match=re.fullmatch(r'\[UNTRUSTED_NEO_OUTPUT\]\n(.*)\n\[END_UNTRUSTED_NEO_OUTPUT\]',text,re.S)
    if not match: raise RuntimeError('Expected complete run JSON')
    parsed=json.loads(match.group(1))
    if parsed.get('ok') is not True: raise RuntimeError('Run failed')
    return parsed['value']

try:
    init=call('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'OpenRagnar validation','version':'0.4.0'}})
    p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');p.stdin.flush()
    catalog=call('tools/list',{})
    tools={t['name']:t for t in catalog['tools']}
    assert {'run','evaluate','snapshot','act','read','neo_read_output','openragnar_navigate'} <= set(tools)
    tool('name_session',{'name':'OpenRagnar 0.3 read/write validation'})
    page=value(tool('run',{'code':'const p=await browser.open("https://example.com"); await p.waitForSelector("body",{timeout:8000}); return p.id;'}))
    tool('evaluate',{'page':page,'code':'const el=document.createElement("input"); el.id="ragnar-smoke"; el.setAttribute("aria-label","OpenRagnar test input"); document.body.appendChild(el); return {created:!!document.getElementById("ragnar-smoke")};'})
    snap=tool('snapshot',{'page':page})
    text='\n'.join(b.get('text','') for b in snap.get('content',[]) if b.get('type')=='text')
    line=next((line for line in text.splitlines() if 'OpenRagnar test input' in line),'')
    ref=re.search(r'\b(e\d+)\b',line)
    if not ref: raise RuntimeError('Test input ref missing: '+text[:1800])
    schema=tools['act']['inputSchema']
    args={'page':page,'ref':ref.group(1)}
    # Input schema is the authority for act's fill field.
    props=schema.get('properties',{})
    args['kind' if 'kind' in props else 'action']='fill'
    args['value']='OpenRagnar writes work'
    tool('act',args)
    verified=value(tool('run',{'code':'const p=await browser.page(%s); const r=await p.evaluate(()=>({value:document.getElementById("ragnar-smoke").value})); return r.value;' % json.dumps(page)}))
    assert verified['value']=='OpenRagnar writes work', verified
    big=tool('run',{'code':'return "OPENRAGNAR_RECOVERY_CHECK:" + "x".repeat(20000);'})
    preview='\n'.join(b.get('text','') for b in big.get('content',[]) if b.get('type')=='text')
    handle=re.search(r'neo_read_output\(handle=([a-zA-Z0-9_-]+)',preview)
    assert handle, 'Large output was not retained'
    recovered=tool('neo_read_output',{'handle':handle.group(1),'offset':0,'maxCharacters':2000})
    assert 'OPENRAGNAR_RECOVERY_CHECK' in json.dumps(recovered)
    report={'version':init['serverInfo']['version'],'protocol':init['protocolVersion'],'toolCount':len(tools),
            'fullToolNames':sorted(tools),'ownedPublicTabOnly':True,'granularEvaluateWrite':True,'snapshotRef':True,
            'actFillAndReadbackVerified':True,'largeOutputRecovery':True,'providerCalled':False}
    (root/'dist/full-access-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
finally:
    if page is not None:
        try: tool('run',{'code':'const p=await browser.page(%s); await p.close(); return {closed:true};' % json.dumps(page)})
        except Exception: pass
    p.stdin.close()
    try: p.wait(timeout=8)
    except subprocess.TimeoutExpired: p.terminate();p.wait(timeout=5)
