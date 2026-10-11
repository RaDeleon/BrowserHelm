"""Live packaged stdio MCP smoke + one public Jev-assisted navigation trial."""
import json
import argparse
import pathlib
import select
import subprocess
import time
root=pathlib.Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app',type=pathlib.Path,default=pathlib.Path('/Applications/OpenRagnar.app'),help='Installed app by default; choose an explicit test bundle to override.')
args=parser.parse_args()
app=args.app.expanduser().resolve()/'Contents/MacOS/OpenRagnar'
if not app.is_file(): parser.error('App missing. Install OpenRagnar or pass --app dist/OpenRagnar.app.')
process=subprocess.Popen([str(app),'--mcp'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)

def call(method,params,number):
    process.stdin.write(json.dumps({'jsonrpc':'2.0','id':number,'method':method,'params':params})+'\n'); process.stdin.flush()
    deadline=time.monotonic()+140
    while time.monotonic()<deadline:
        readable,_,_=select.select([process.stdout],[],[],1)
        if not readable: continue
        line=process.stdout.readline()
        if not line: raise RuntimeError('MCP process ended')
        value=json.loads(line)
        if value.get('id')==number:
            if 'error' in value: raise RuntimeError(value['error'])
            return value['result']
    raise RuntimeError('Response deadline exceeded')

try:
    init=call('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'OpenRagnar live provider validation','version':'0.4.0'}},1)
    process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');process.stdin.flush()
    catalog=call('tools/list',{},2)
    print(json.dumps({'server':init['serverInfo'],'catalogBytes':len(json.dumps(catalog).encode()),'tools':[t['name'] for t in catalog['tools']]}),flush=True)
    result=call('tools/call',{'name':'openragnar_navigate','arguments':{'startUrl':'https://docs.typesafe.ai/models','goal':'Find the API reference describing choice-answer probabilities','successText':'floats that sum to 1','maxSteps':3}},3)
    print(json.dumps(result),flush=True)
    report={'app':str(args.app),'server':init['serverInfo'],'catalogBytes':len(json.dumps(catalog).encode()),'toolCount':len(catalog['tools']),'navigation':result,'limitations':'One public-site task. Provider usage returned when available; no Claude quota benchmark.'}
    (root/'neo-personal/openragnar-live-results.json').write_text(json.dumps(report,indent=2)+'\n')
    if result.get('isError'):
        raise SystemExit('Provider/browser test failed; inspect the saved report before retrying.')
    payload=None
    for block in result.get('content',[]):
        if block.get('type')=='text' and '[UNTRUSTED_NEO_OUTPUT]' in block.get('text',''):
            raw=block['text'].split('[UNTRUSTED_NEO_OUTPUT]',1)[1].split('[END_UNTRUSTED_NEO_OUTPUT]',1)[0].strip()
            payload=json.loads(raw)
            break
    if not payload or payload.get('status')!='complete' or payload.get('verified') is not True:
        raise SystemExit('Provider/browser test did not verify completion; inspect the saved report before retrying.')
finally:
    process.stdin.close()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.terminate();process.wait(timeout=5)
