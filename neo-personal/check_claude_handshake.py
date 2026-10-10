"""Exercise the packaged stdio executable with Claude Desktop's logged version."""
import json
import pathlib
import select
import subprocess
import time
root=pathlib.Path(__file__).resolve().parent.parent
executable=root/'dist/OpenRagnar.app/Contents/MacOS/OpenRagnar'
process=subprocess.Popen([str(executable),'--mcp'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
def call(method,params,number):
    process.stdin.write(json.dumps({'jsonrpc':'2.0','method':method,'params':params,'id':number})+'\n');process.stdin.flush()
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        ready,_,_=select.select([process.stdout],[],[],1)
        if not ready: continue
        line=process.stdout.readline()
        if not line: raise RuntimeError('MCP executable ended before handshake completed')
        message=json.loads(line)
        if message.get('id')==number:
            if 'error' in message: raise RuntimeError(message['error'])
            return message['result']
    raise RuntimeError('MCP handshake timed out; check Keychain prompt and Neo')
try:
    result=call('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'claude-desktop','version':'protocol-regression'}},0)
    process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');process.stdin.flush()
    catalog=call('tools/list',{},1)
    report={'requestedProtocol':'2025-11-25','negotiatedProtocol':result['protocolVersion'],'server':result['serverInfo'],'toolCount':len(catalog['tools']),'toolListingSucceeded':True}
    print(json.dumps(report,indent=2))
    (root/'dist/claude-handshake-verification.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
    process.stdin.close()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.terminate();process.wait(timeout=5)
    process.stdout.close();process.stderr.close()
