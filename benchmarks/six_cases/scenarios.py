"""Six controlled workloads and independent answer checks. No real account writes."""
import html

CASES = [
 {'id':'01_styles','name':'Guarded typography inspection','fixture':True,'task':
  'Inspect this page. Return the h1 computed font size in pixels, numeric weight and RGB color, the first nav link font size in pixels, and whether [data-missing] exists. Do not dereference missing elements. Final JSON keys: heading_font_px, heading_weight, heading_color, nav_font_px, missing_status.'},
 {'id':'02_navigation','name':'Public multi-step navigation','fixture':False,'task':
  'Starting at https://docs.typesafe.ai/models, find the API reference and extract the first h1 and the explanation of the probabilities response field. Verify current-page evidence. Final JSON keys: url, heading, probabilities_explanation.'},
 {'id':'03_comparison','name':'Long-page constrained comparison','fixture':True,'task':
  'Read the entire plan comparison or use a complete scoped query. Choose the cheapest plan with EU hosting, zero retention days and p95 latency at most 100 ms, within $35/month. Do not guess from a truncated result. Explain why it meets every constraint. Final JSON keys: chosen_plan, monthly_usd, reason.'},
 {'id':'04_vision','name':'Canvas visual target','fixture':True,'task':
  'Using visual evidence, click the blue circle beneath APPLY exactly once, then verify confirmation and the click count. This is a disposable test canvas. Do not inspect canvas drawing code, pixel data or scripts to derive coordinates; use screenshot interpretation or a vision tool. Final JSON keys: confirmation, click_count.'},
 {'id':'05_recovery','name':'Unknown-outcome recovery','fixture':True,'task':
  'Submit the disposable fixture request with Confirm exactly once, then verify the request ID, confirmation and submit count. A transport failure may occur after dispatch: inspect the actual state before retrying, and never submit twice. Final JSON keys: request_id, confirmation, submit_count.'},
 {'id':'06_learning','name':'Fresh-session learned navigation','fixture':False,'task':
  'Starting at https://docs.typesafe.ai/models, find the API reference and extract its h1 and probabilities field explanation. Verify current-page evidence. Final JSON keys: url, heading, probabilities_explanation. If using openragnar_execute, use this exact repeatable contract: goal="Find the API reference and read its first heading"; startUrl="https://docs.typesafe.ai/models"; allowedActions=["navigate","extract"]; steps=[{"action":"navigate","text":"floats that sum to 1","maxHops":2},{"action":"extract","fields":[{"name":"heading","selector":"h1"}]}]; completion={"textPresent":["floats that sum to 1"],"selectorsPresent":["h1"]}; maxSeconds=45. Retain complex interpretation with the main model.'}
]

BASE = '<!doctype html><meta charset="utf-8"><style>body{font:16px Arial;margin:24px;color:rgb(30,40,50)}h1{font-size:24px;font-weight:600;color:rgb(30,40,50)}nav a{font-size:16px}td,th{padding:8px;border:1px solid #999}table{border-collapse:collapse}button{font:20px Arial;padding:16px}</style>'

def page(case, run):
 if case=='01_styles':return BASE+'<h1>Benchmark typography</h1><nav><a href="#details">Details</a></nav><p>Read styles and handle an absent selector safely.</p>'
 if case=='03_comparison':
  rows=[('Legacy-'+str(n),10+n%20,'US',7,150+n) for n in range(120)]
  rows[5]=('Atlas',24,'EU',30,120);rows[77]=('Nimbus',30,'EU',0,80);rows[112]=('Spark',20,'EU',0,180)
  return BASE+'<h1>Plan comparison (synthetic)</h1><p>Choose using all five columns. Dollar amounts are monthly.</p><table><thead><tr><th>Plan</th><th>USD/month</th><th>Hosting</th><th>Retention days</th><th>p95 ms</th></tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
 if case=='05_recovery':return BASE+'''<h1>Disposable request</h1><p>Request ID: BENCH-1042</p><button id="confirm">Confirm</button><p id="status">Not submitted</p><p id="count">Submit count: 0</p><script>document.querySelector('#confirm').onclick=async()=>{const s=await(await fetch(location.pathname+'/commit',{method:'POST',body:'confirm'})).json();document.querySelector('#status').textContent='Request completed';document.querySelector('#count').textContent='Submit count: '+s.count;};</script>'''
 if case=='04_vision':return '''<!doctype html><meta charset="utf-8"><style>html,body{margin:0;font:20px Arial;background:white}canvas{display:block;width:100vw;height:85vh}#status,#count{margin:8px}</style><canvas></canvas><p id="status">Awaiting visual target</p><p id="count">Click count: 0</p><script>
const c=document.querySelector('canvas');c.width=innerWidth;c.height=Math.floor(innerHeight*.85);const ctx=c.getContext('2d');const w=c.width,h=c.height;
ctx.fillStyle='white';ctx.fillRect(0,0,w,h);ctx.fillStyle='black';ctx.font='bold 30px Arial';ctx.fillText('APPLY',w*.68,h*.32);ctx.fillText('CANCEL',w*.25,h*.32);
for(const [x,y,color,shape] of [[.72,.48,'#1565ff','circle'],[.3,.48,'#f32640','circle'],[.72,.75,'#148f44','square'],[.3,.75,'#1565ff','square']]){ctx.fillStyle=color;ctx.beginPath();if(shape==='circle'){ctx.arc(w*x,h*y,35,0,Math.PI*2);ctx.fill();}else ctx.fillRect(w*x-35,h*y-35,70,70);}
c.onclick=async e=>{const r=c.getBoundingClientRect(),x=(e.clientX-r.left)*c.width/r.width,y=(e.clientY-r.top)*c.height/r.height;const target=Math.hypot(x-w*.72,y-h*.48)<=35?'blue_circle':'wrong_target';const s=await(await fetch(location.pathname+'/commit',{method:'POST',body:target})).json();document.querySelector('#status').textContent=target==='blue_circle'?'Vision target confirmed':'Wrong target';document.querySelector('#count').textContent='Click count: '+s.count;};</script>'''
 raise ValueError('Unknown fixture')

def verify(case, answer, state):
 if not isinstance(answer,dict):return {'verified':False,'reason':'No JSON answer'}
 if case=='01_styles':
  try:ok=float(answer.get('heading_font_px',0))==24 and int(answer.get('heading_weight',0))==600 and answer.get('heading_color','').replace(' ','')=='rgb(30,40,50)' and float(answer.get('nav_font_px',0))==16 and answer.get('missing_status') in ('missing','absent','not_found','not present',False)
  except (ValueError,TypeError):ok=False
 elif case=='03_comparison':ok=answer.get('chosen_plan')=='Nimbus' and answer.get('monthly_usd')==30 and bool(answer.get('reason'))
 elif case in ('02_navigation','06_learning'):
  ok=answer.get('url','').rstrip('/')=='https://docs.typesafe.ai/api' and answer.get('heading')=='API reference' and 'sum to 1' in answer.get('probabilities_explanation','').lower() and state.get('publicVerified') is True
 elif case=='04_vision':ok=state.get('count')==1 and state.get('target')=='blue_circle' and answer.get('click_count')==1 and answer.get('confirmation')=='Vision target confirmed'
 elif case=='05_recovery':ok=state.get('count')==1 and state.get('target')=='confirm' and answer.get('submit_count')==1 and answer.get('request_id')=='BENCH-1042' and answer.get('confirmation')=='Request completed'
 else:ok=False
 return {'verified':bool(ok),'reason':'Independent checks passed' if ok else 'Answer or actual browser/fixture state did not meet the oracle','state':state}
