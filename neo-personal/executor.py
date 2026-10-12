"""Bounded browser delegation. Models choose observed links, never executable code."""
import hashlib
import json
import re
import time
from gateway import encode
from metrics import usage_tokens

ACTIONS = ['inspect', 'extract', 'navigate', 'scroll', 'locate']
FIELD = {'type': 'object', 'properties': {'name': {'type': 'string', 'minLength': 1, 'maxLength': 60},
         'selector': {'type': 'string', 'minLength': 1, 'maxLength': 200},
         'read': {'type': 'string', 'enum': ['text', 'style', 'href']},
         'contains': {'type': 'string', 'minLength': 1, 'maxLength': 200,
                      'description': 'Text reads only: return an excerpt around this literal phrase (case insensitive). Absence is reported.'}},
         'required': ['name', 'selector'], 'additionalProperties': False}
STEP_VARIANTS = {
    'inspect': {'includeStyles': {'type': 'boolean', 'default': False,
                                'description': 'Include heading/body computed styles only when needed.'}},
    'extract': {'fields': {'type': 'array', 'items': FIELD, 'minItems': 1, 'maxItems': 12}},
    'navigate': {'text': {'type': 'string', 'minLength': 4, 'maxLength': 200,
                         'description': 'Required literal phrase expected on the destination page, not a navigation instruction.'},
                 'maxHops': {'type': 'integer', 'minimum': 1, 'maximum': 3, 'default': 2}},
    'scroll': {'pixels': {'type': 'integer', 'minimum': -2000, 'maximum': 2000}},
    'locate': {'instruction': {'type': 'string', 'minLength': 1, 'maxLength': 500}}}
STEP_REQUIRED = {'inspect': [], 'extract': ['fields'], 'navigate': ['text'],
                 'scroll': ['pixels'], 'locate': ['instruction']}
STEP = {'oneOf': [{'type': 'object', 'properties': {'action': {'type': 'string', 'enum': [action]}, **properties},
                   'required': ['action', *STEP_REQUIRED[action]], 'additionalProperties': False}
                  for action, properties in STEP_VARIANTS.items()]}
EXEC_HELP = """browserhelm_execute runs a bounded read-only plan. Supply exactly one of page or public HTTPS startUrl.
Each step has action-specific parameters: inspect optionally includeStyles; extract requires fields;
navigate requires text (a literal phrase expected on the destination) and optionally maxHops=1–3;
scroll requires nonzero pixels; locate alone accepts instruction and proposes a point, never clicks.
Example inspection: {"page":153,"goal":"Read heading","allowedActions":["inspect","extract"],"steps":[{"action":"inspect"},{"action":"extract","fields":[{"name":"heading","selector":"h1"}]}],"completion":{"selectorsPresent":["h1"]}}
Example navigation: {"startUrl":"https://example.com/","goal":"Find API documentation","allowedActions":["navigate","extract"],"steps":[{"action":"navigate","text":"API reference","maxHops":2},{"action":"extract","fields":[{"name":"api","selector":"body","contains":"API reference"}]}],"completion":{"textPresent":["API reference"]}}
inspect defaults to headings/links; use includeStyles:true or extract read:style for typography.
Text fields return at most 1200 characters with truncated, totalChars and offset; contains focuses an excerpt.
Missing selectors or phrases have null values. Completion verifies only supplied text/selector checks,
not the entire user goal or optional fields. Read partial results on escalation before recovery.
No forms, clicks, downloads, arbitrary JavaScript or automatic retries. Direct tools handle unsupported work.
"""
EXEC_TOOL = {'name': 'browserhelm_execute', 'description':
    'Delegate a bounded read-only browser plan in one call. Runs inspection, guarded selector extraction, '
    'inspect has no instruction; navigate requires literal destination text; locate alone uses instruction. '
    'same-origin public link navigation using the configured decision provider, viewport scrolling and '
    'optional vision point proposals. Supply explicit steps, allowedActions and completion text/selector '
    'checks. Missing elements are reported; required missing checks escalate. No forms, clicks, downloads '
    'or arbitrary JavaScript. Returns findings, check evidence, usage and partial progress; stop on '
    'uncertainty/errors and inspect state before retrying. Cloud decisions receive goal/link labels; '
    'explicit locate steps send screenshots to the selected vision provider. Verification covers only '
    'the supplied checks. Prefer this over repeated main-agent browser calls for supported tasks.',
    'inputSchema': {'type': 'object', 'properties': {
        'goal': {'type': 'string', 'minLength': 1, 'maxLength': 500},
        'startUrl': {'type': 'string'}, 'page': {'type': 'integer', 'minimum': 1},
        'allowedActions': {'type': 'array', 'items': {'type': 'string', 'enum': ACTIONS}, 'minItems': 1, 'uniqueItems': True},
        'steps': {'type': 'array', 'items': STEP, 'minItems': 1, 'maxItems': 8},
        'completion': {'type': 'object', 'properties': {
            'textPresent': {'type': 'array', 'items': {'type': 'string', 'minLength': 4, 'maxLength': 200}, 'maxItems': 8},
            'selectorsPresent': {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'maxLength': 200}, 'maxItems': 8}}, 'additionalProperties': False},
        'maxSeconds': {'type': 'integer', 'minimum': 5, 'maximum': 90, 'default': 45},
        'maxBrowserCalls': {'type': 'integer', 'minimum': 2, 'maximum': 40, 'default': 20}},
        'required': ['goal', 'allowedActions', 'steps', 'completion'], 'additionalProperties': False}}

# One current-page read batches consecutive inspections and extracts. Never dereference a missing element.
READ_JS = r'''({jobs,checks,needle}) => {
const visible=e=>!!e&&e.getClientRects().length>0;
const body=document.body?.innerText||'';
const select=s=>{try{return {element:document.querySelector(s)}}catch{return {invalid:true}}};
const style=e=>{if(!e)return null;const s=getComputedStyle(e);return {
 fontFamily:s.fontFamily,fontSize:s.fontSize,fontWeight:s.fontWeight,color:s.color,
 backgroundColor:s.backgroundColor,padding:s.padding,letterSpacing:s.letterSpacing};};
const links=Array.from(document.querySelectorAll('a[href]')).filter(a=>visible(a)&&!a.hasAttribute('download'))
 .map(a=>({url:a.href,label:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,120)}))
 .filter(a=>a.label&&a.url.length<=2000).slice(0,60);
const findings=jobs.map(j=>{
 if(j.action==='inspect')return {action:'inspect',headings:Array.from(document.querySelectorAll('h1,h2,h3'))
  .filter(visible).slice(0,12).map(e=>({tag:e.tagName,text:String(e.innerText||e.textContent||'').slice(0,160),
   ...(j.includeStyles?{style:style(e)}:{})})),
  ...(j.includeStyles?{bodyStyle:style(document.body)}:{}),links:links.slice(0,20)};
 return {action:'extract',fields:j.fields.map(f=>{const q=select(f.selector),e=q.element;
  const out={name:f.name,selector:f.selector,status:q.invalid?'invalid_selector':!visible(e)?'missing':'present',value:null};
  if(!visible(e))return out;
  if(f.read==='style'){out.value=style(e);return out;}
  if(f.read==='href'){out.value=e.getAttribute('href');return out;}
  const text=String(e.innerText||e.textContent||''),at=f.contains?text.toLowerCase().indexOf(f.contains.toLowerCase()):0;
  out.totalChars=text.length;out.truncated=text.length>1200;
  if(at<0){out.status='missing_text';out.matched=false;out.offset=null;return out;}
  const offset=Math.min(Math.max(0,at-400),Math.max(0,text.length-1200));
  out.offset=offset;out.value=text.slice(offset,offset+1200);
  if(f.contains)out.matched=true;
  return out;})};
});
const evidence=[...(checks.textPresent||[]).map(text=>({kind:'text',expected:text,
 present:body.toLowerCase().includes(text.toLowerCase())})),
 ...(checks.selectorsPresent||[]).map(selector=>{const q=select(selector);
 return {kind:'selector',expected:selector,present:visible(q.element),invalid:q.invalid===true};})];
const at=needle?body.toLowerCase().indexOf(needle.toLowerCase()):-1;
return {url:location.href,title:document.title.slice(0,160),links,findings,checks:evidence,
 found:at>=0,excerpt:at>=0?body.slice(Math.max(0,at-80),at+needle.length+120):''};
}'''


def validate(args):
    if not isinstance(args, dict) or set(args) - set(EXEC_TOOL['inputSchema']['properties']):
        raise ValueError('Invalid executor arguments')
    goal = args.get('goal')
    if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 500:
        raise ValueError('Provide a goal of 1–500 characters')
    if ('page' in args) == ('startUrl' in args):
        raise ValueError('Provide exactly one of page or startUrl')
    if 'page' in args and (type(args['page']) is not int or args['page'] < 1):
        raise ValueError('Invalid page ID')
    actions, steps, checks = args.get('allowedActions'), args.get('steps'), args.get('completion')
    if not isinstance(actions, list) or not actions or any(type(a) is not str or a not in ACTIONS for a in actions) or len(set(actions)) != len(actions):
        raise ValueError('Provide explicit supported allowedActions')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        raise ValueError('Provide 1–8 bounded steps')
    if not isinstance(checks, dict) or set(checks) - {'textPresent', 'selectorsPresent'}:
        raise ValueError('Invalid completion checks')
    count = 0
    for key, values in checks.items():
        minimum = 4 if key == 'textPresent' else 1
        if not isinstance(values, list) or len(values) > 8 or any(not isinstance(v, str) or not minimum <= len(v.strip()) <= 200 for v in values):
            raise ValueError('Invalid completion check values')
        count += len(values)
    if not count:
        raise ValueError('At least one explicit text or selector completion check is required')
    for step in steps:
        if not isinstance(step, dict) or step.get('action') not in actions:
            raise ValueError('Every step must use an explicitly allowed action')
        action = step['action']
        keys = {'action', *STEP_VARIANTS[action]}
        if set(step) - keys:
            raise ValueError('Unexpected parameters for '+action+'. Allowed: '+', '.join(sorted(keys))+
                             '. Only locate accepts instruction; navigate requires text expected on the destination page.')
        if action == 'inspect' and type(step.get('includeStyles', False)) is not bool:
            raise ValueError('includeStyles must be a boolean')
        if action == 'extract':
            fields = step.get('fields')
            if not isinstance(fields, list) or not 1 <= len(fields) <= 12:
                raise ValueError('Provide 1–12 extraction fields')
            names = []
            for f in fields:
                if (not isinstance(f, dict) or set(f) - set(FIELD['properties']) or
                    not isinstance(f.get('name'), str) or not 1 <= len(f['name'].strip()) <= 60 or
                    not isinstance(f.get('selector'), str) or not 1 <= len(f['selector'].strip()) <= 200 or
                    f.get('read','text') not in ('text','style','href')):
                    raise ValueError('Invalid extraction field')
                if 'contains' in f and (f.get('read', 'text') != 'text' or
                    not isinstance(f['contains'], str) or not 1 <= len(f['contains'].strip()) <= 200):
                    raise ValueError('contains requires a literal phrase of 1–200 characters on a text field')
                names.append(f['name'])
            if len(set(names)) != len(names): raise ValueError('Extraction names must be unique')
        if action == 'navigate' and (not isinstance(step.get('text'),str) or not 4 <= len(step['text'].strip()) <= 200 or
                                     type(step.get('maxHops',2)) is not int or not 1 <= step.get('maxHops',2) <= 3):
            raise ValueError('Navigation requires text: a literal phrase expected on the destination page, and optional maxHops of 1–3')
        if action == 'scroll' and (type(step.get('pixels')) is not int or not -2000 <= step['pixels'] <= 2000 or step['pixels'] == 0):
            raise ValueError('Scroll requires nonzero pixels between -2000 and 2000')
        if action == 'locate' and (not isinstance(step.get('instruction'),str) or not 1 <= len(step['instruction'].strip()) <= 500):
            raise ValueError('Provide a visual target instruction')
    for key, default, low, high in [('maxSeconds',45,5,90),('maxBrowserCalls',20,2,40)]:
        if type(args.get(key,default)) is not int or not low <= args.get(key,default) <= high:
            raise ValueError('Invalid '+key)
    return args


def read_page(gateway, page, jobs, checks, needle=''):
    payload = {'jobs': jobs, 'checks': checks, 'needle': needle}
    raw = gateway.upstream_call({'jsonrpc':'2.0','id':'exec-read-'+hashlib.sha256(encode(payload)).hexdigest()[:12],
        'method':'tools/call','params':{'name':'evaluate','arguments':{'page':page,
        'code':'return (%s)(%s);' % (READ_JS, json.dumps(payload)), 'maxChars':60000, 'timeout':10000}}})
    result = raw.get('result', {}) if isinstance(raw,dict) else {}
    state = result.get('structuredContent', {}).get('value')
    if state is None and not result.get('isError'):
        for block in result.get('content', []):
            if block.get('type') != 'text': continue
            match = re.fullmatch(r'\[UNTRUSTED_PAGE_CONTENT nonce=([a-f0-9]+) origin=[^\]\n]+\][^\n]*\n(.*)\n\[END_UNTRUSTED_PAGE_CONTENT nonce=\1\]', block.get('text',''), re.S)
            if match:
                try: state = json.loads(match.group(2))
                except ValueError: pass
                break
    if (not isinstance(raw, dict) or raw.get('error') or result.get('isError') or not isinstance(state,dict) or
        not isinstance(state.get('url'),str) or not isinstance(state.get('links'),list) or
        not isinstance(state.get('checks'),list) or not isinstance(state.get('findings'),list)):
        raise ValueError('Executor observation failed or was truncated; inspect state before retrying')
    return state


def execute(gateway, arguments, request_id):
    from browserhelm import public_url, NAV_READY_JS
    from vision import visual_act
    args = validate(arguments)
    start = origin = None
    if 'startUrl' in args: start, origin = public_url(args['startUrl'])
    if not gateway.nav_lock.acquire(blocking=False):
        raise ValueError('Another delegated action is running in this connection')
    begin = time.monotonic()
    row = getattr(gateway.context, 'row', None)
    report = {'status':'escalate','verified':False,'mainAgentToolCalls':1,'steps':[],
              'checks':[],'decisions':[],'provider':gateway.settings.get('provider','none'),
              'memory':{'providerCallsAvoided':0,'reusedSteps':0}, 'verificationScope':'Explicit current-page text and visible-selector checks only'}
    deadline = begin + args.get('maxSeconds',45)
    gateway.context.execution_deadline = deadline
    gateway.context.execution_request_id = request_id
    gateway.context.execution_call_limit = args.get('maxBrowserCalls',20)
    gateway.context.execution_calls = 0
    page = args.get('page')
    state = None
    routes = []
    attempt = None
    memory = gateway.memory if gateway.memory and gateway.memory.enabled else None
    # Include the full contract to avoid transferring success between different plans/checks.
    contract = hashlib.sha256(encode({k:v for k,v in args.items() if k not in ('page','startUrl','maxSeconds','maxBrowserCalls')})).hexdigest()
    memory_goal = 'executor:'+contract
    provider = None
    def stopped():
        if request_id in gateway.cancelled:
            raise ValueError('Executor cancelled; inspect partial progress before continuing')
        if time.monotonic() >= deadline:
            raise ValueError('Executor elapsed-time budget reached')
    def observe(jobs=None, needle=''):
        stopped()
        return read_page(gateway,page,jobs or [],args['completion'],needle)
    try:
        stopped()
        if memory: memory.start()
        if start:
            page = gateway.run_browser('const p=await browser.open(%s);return p.id;' % json.dumps(start))
        if type(page) is not int or page < 1:
            raise ValueError('Neo returned an invalid owned page ID')
        report['pageId'] = page
        i = 0
        while i < len(args['steps']):
            stopped()
            step = args['steps'][i]; action = step['action']
            if action in ('inspect','extract'):
                end = i+1
                while end < len(args['steps']) and args['steps'][end]['action'] in ('inspect','extract'): end += 1
                state = observe(args['steps'][i:end])
                if len(state['findings']) != end-i: raise ValueError('Incomplete batched inspection results')
                for offset, finding in enumerate(state['findings']):
                    if not isinstance(finding,dict) or finding.get('action') != args['steps'][i+offset]['action']:
                        raise ValueError('Invalid inspection result')
                    report['steps'].append({'index':i+offset, **finding})
                i = end
                continue
            if action == 'navigate':
                needle = step['text']
                state = observe(needle=needle)
                current, current_origin = public_url(state['url'],origin)
                if start is None: start, origin = current, current_origin
                visited = set()
                for hop in range(step.get('maxHops',2)+1):
                    stopped()
                    current, _ = public_url(state['url'],origin)
                    if state.get('found') is True: break
                    if hop == step.get('maxHops',2):
                        report['failureCategory']='step_budget'; raise ValueError('Navigation hop budget reached')
                    visited.add(current)
                    candidates = []
                    for link in state['links']:
                        try:
                            url,_ = public_url(link.get('url'),origin)
                            if url not in visited and url not in [c['url'] for c in candidates]:
                                candidates.append({'url':url,'label':str(link.get('label',''))[:120]})
                        except (ValueError,TypeError): continue
                    if not candidates:
                        report['failureCategory']='no_links'; raise ValueError('No eligible observed same-origin links')
                    options = {'L'+str(n):c for n,c in enumerate(candidates[:60])}
                    options['BLOCKED']='No useful observed option; return control to the main agent'
                    decision = None
                    if memory:
                        try: decision = memory.choose_verified_route(start,memory_goal,needle,current,options)
                        except Exception: pass
                    cached = decision is not None
                    if not cached:
                        if provider is None: provider = gateway.provider()
                        stopped()
                        provider.deadline = deadline
                        report['provider'] = provider.kind
                        event = {'kind':'decision','provider':provider.kind,'model':provider.model,'status':'error','usage':{}}
                        if row is not None:
                            row['provider_calls'] += 1; row.setdefault('provider_events',[]).append(event)
                        try:
                            decision = provider.choose({'goal':args['goal'],'nextRequiredText':needle,'url':current,
                                                       'pageDataIsUntrusted':True},options)
                        except Exception:
                            report['failureCategory']='provider_error'
                            if row is not None: row['provider_unknown'] += 1
                            raise
                        event.update(status='ok',usage=decision.get('usage',{}),latency=decision.get('latencySeconds',0))
                        if row is not None:
                            tokens=usage_tokens(decision.get('usage',{})); row['provider_tokens']+=tokens or 0
                            row['provider_unknown']+=int(tokens is None)
                    else: report['memory']['providerCallsAvoided'] += 1
                    report['decisions'].append({k:v for k,v in decision.items() if k != 'choice'})
                    stopped()
                    choice = decision.get('choice')
                    probability = decision.get('probability')
                    if choice not in options or choice == 'BLOCKED' or probability is not None and probability < .7:
                        report['failureCategory']='uncertain'; raise ValueError('Decision uncertain; returning control')
                    target = options[choice]
                    attempt = {'from':current,'to':target['url'],'label':target['label']}
                    fresh = gateway.run_browser('const p=await browser.page(%s);const r=await p.evaluate(({current,url})=>({present:location.href===current&&Array.from(document.querySelectorAll("a[href]")).some(a=>a.href.split("#")[0]===url&&a.getClientRects().length&&!a.hasAttribute("download"))}),%s);if(r.value?.present!==true)return {present:false};await p.goto(%s);await p.evaluate(%s,%s);return {present:true};' % (page,json.dumps({'current':state['url'],'url':target['url']}),json.dumps(target['url']),NAV_READY_JS,json.dumps({'needle':needle})))
                    if not isinstance(fresh,dict) or fresh.get('present') is not True:
                        report['failureCategory']='stale_link'; raise ValueError('Page or selected link changed; no navigation retry')
                    routes.append(attempt); attempt=None
                    if cached: report['memory']['reusedSteps'] += 1
                    state = observe(needle=needle)
                report['steps'].append({'index':i,'action':action,'textPresent':True,'url':state['url'],'excerpt':state.get('excerpt','')})
            elif action == 'scroll':
                gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(d=>{window.scrollBy(0,d);return {x:scrollX,y:scrollY}},%s)).value;' % (page,step['pixels']))
                report['steps'].append({'index':i,'action':action,'requestedPixels':step['pixels']})
                state = None
            elif action == 'locate':
                value = visual_act(gateway,{'page':page,'instruction':step['instruction'],'action':'point'},request_id,lock_held=True)
                report['steps'].append({'index':i,'action':action,'result':value})
                if value.get('status') != 'point': raise ValueError('Visual target unavailable or stale; returning control')
                state = None
            i += 1
        if state is None: state = observe()
        stopped()
        report.update(url=state['url'],checks=state['checks'])
        expected = sum(len(v) for v in args['completion'].values())
        if len(state['checks']) != expected or not all(isinstance(c,dict) and c.get('present') is True for c in state['checks']):
            report['failureCategory']='verification_failed'; report['reason']='Required completion checks are missing on the current page'
        else:
            report.update(status='complete',verified=True,reason='All supplied current-page checks passed')
        return report
    except Exception as error:
        report.setdefault('failureCategory','execution_error')
        report['reason'] = str(error) if isinstance(error,ValueError) else 'Execution failed (%s); inspect state before retrying' % type(error).__name__
        if attempt: report['attempts']=[attempt]
        if state: report.update(url=state['url'],checks=state['checks'])
        return report
    finally:
        report['browserCalls']=getattr(gateway.context,'execution_calls',0)
        report['elapsedSeconds']=round(time.monotonic()-begin,3)
        if memory and start and (routes or attempt):
            # Capture each navigation requirement under the whole plan identity. No remote recall on the hot path.
            for needle in {s['text'] for s in args['steps'] if s['action']=='navigate'}:
                try:
                    report['memory']['outcome']=memory.capture(start,memory_goal,needle,report,routes)
                except Exception: report['memory']['outcome']='Memory unavailable; browser outcome unchanged'
            try: memory.record_route_use(report['memory']['providerCallsAvoided'],report['memory']['reusedSteps'],report['verified'])
            except Exception: pass
        report['elapsedSeconds']=round(time.monotonic()-begin,3)
        for name in ('execution_deadline','execution_call_limit','execution_calls','execution_request_id'):
            if hasattr(gateway.context,name): delattr(gateway.context,name)
        gateway.nav_lock.release()
        gateway.cancelled.discard(request_id)
