"""Fresh handshakes from saved migrated client commands; no paid inference."""
import json
import pathlib
import select
import subprocess
import tomllib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent/'neo-personal'))
from version import VERSION

home=pathlib.Path.home()
configs=[('Codex',home/'.codex/config.toml'),('Claude Desktop',home/'Library/Application Support/Claude/claude_desktop_config.json')]
report=[]
for client,path in configs:
    root=tomllib.loads(path.read_text()) if path.suffix=='.toml' else json.loads(path.read_text())
    servers=root['mcp_servers' if path.suffix=='.toml' else 'mcpServers']
    assert 'openragnar' not in servers
    entry=servers['browserhelm']
    assert entry['command']=='/Applications/BrowserHelm.app/Contents/MacOS/BrowserHelm'
    process=subprocess.Popen([entry['command']]+entry['args'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    def request(identifier,method,params):
        process.stdin.write(json.dumps({'jsonrpc':'2.0','id':identifier,'method':method,'params':params})+'\n');process.stdin.flush()
        ready,_,_=select.select([process.stdout],[],[],30)
        if not ready:raise RuntimeError(client+' handshake timed out')
        result=json.loads(process.stdout.readline())
        assert result.get('id')==identifier and 'error' not in result
        return result['result']
    try:
        init=request(1,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':client.lower().replace(' ','-'),'version':'browserhelm-migration-check'}})
        assert init['serverInfo']=={'name':'browserhelm','title':'BrowserHelm','version':VERSION}
        process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');process.stdin.flush()
        catalog=request(2,'tools/list',{})
        names={t['name'] for t in catalog['tools']}
        assert {'browserhelm_execute','browserhelm_status','browserhelm_visual_act','run','neo_read_output'}<=names
        assert not any(n.startswith('openragnar_') for n in names)
        for identifier,tool in [(3,'browserhelm_status'),(4,'openragnar_status')]:
            status=request(identifier,'tools/call',{'name':tool,'arguments':{}})
            assert not status.get('isError',False)
        report.append({'client':client,'server':init['serverInfo'],'toolCount':len(names),'legacyAliasAccepted':True,'savedCommandHandshakeVerified':True,'existingClientCatalogReloadVerified':False})
    finally:
        process.stdin.close()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
output=pathlib.Path(__file__).resolve().parent.parent/'dist/browserhelm-client-verification.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
