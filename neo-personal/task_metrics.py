"""Explicit prompt-task boundaries and auditable API-equivalent costs.
No prompts, browser content, credentials or model reasoning are stored.
"""
import json
import math
import sqlite3
from sqlite_support import ClosingConnection
import time
import uuid

PRICING_SOURCE = 'https://platform.claude.com/docs/en/about-claude/pricing'
PRICING_DATE = '2026-10-11'
# USD per million tokens: normal input, output, cache read, 5m write, 1h write.
CLAUDE_PRICES = {
    'claude-opus-5.5': [4,20,.2,5,8],
    'claude-sonnet-5.5': [2,10,.1,2.5,4],
    'claude-haiku-5.5': [.1,.5,.01,.125,.2],
    'claude-opus-5': [5,25,.5,6.25,10],
    'claude-sonnet-5': [2,10,.2,2.5,4],
    'claude-opus-4.7': [5,25,.5,6.25,10],
    'claude-sonnet-4.6': [3,15,.3,3.75,6],
}
TOKEN_KEYS = ['input_tokens','output_tokens','cache_read_tokens','cache_write_5m_tokens','cache_write_1h_tokens']

def nonnegative(value, integer=False):
    if value is None: return None
    if type(value) not in ((int,) if integer else (int,float)) or not math.isfinite(value) or not 0 <= value <= 10**12:
        raise ValueError('Usage and prices must be finite nonnegative numbers')
    return value

def model_key(model):
    text = str(model).lower().strip().replace(' ', '-').replace('_','-')
    if not text.startswith('claude-'): text = 'claude-' + text
    aliases={'claude-opus-5-5':'claude-opus-5.5','claude-sonnet-5-5':'claude-sonnet-5.5','claude-haiku-5-5':'claude-haiku-5.5','claude-opus-4-7':'claude-opus-4.7','claude-sonnet-4-6':'claude-sonnet-4.6'}
    return aliases.get(text,text)

def claude_cost(model, usage):
    rates = CLAUDE_PRICES.get(model_key(model))
    if not rates: return None
    if any(usage.get(k) is None for k in TOKEN_KEYS): return None
    # Effort affects generated tokens, not the normal per-token list rate.
    return sum(nonnegative(usage[k], True)*r for k,r in zip(TOKEN_KEYS,rates))/1e6

class TaskLedger:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, label TEXT, started REAL, finished REAL,
              status TEXT, boundary_source TEXT, model TEXT, effort TEXT,
              verification TEXT, metadata TEXT);
            CREATE TABLE IF NOT EXISTS task_sessions (
              task_id TEXT, session_id TEXT, PRIMARY KEY(task_id,session_id));
            CREATE TABLE IF NOT EXISTS provider_usage (
              id TEXT PRIMARY KEY, request_id TEXT, task_id TEXT, kind TEXT,
              provider TEXT, model TEXT, status TEXT, usage TEXT, latency REAL);
            CREATE INDEX IF NOT EXISTS provider_usage_task ON provider_usage(task_id);
            ''')
            db.execute('DELETE FROM provider_usage WHERE request_id NOT IN (SELECT id FROM requests)')
            db.execute("DELETE FROM tasks WHERE started<?", (time.time()-90*86400,))
            db.execute('DELETE FROM task_sessions WHERE task_id NOT IN (SELECT id FROM tasks)')
    def db(self):
        db=sqlite3.connect(self.path, timeout=2, factory=ClosingConnection); db.row_factory=sqlite3.Row
        return db
    def active(self, session_id):
        with self.db() as db:
            row=db.execute("SELECT t.id FROM tasks t JOIN task_sessions s ON s.task_id=t.id WHERE s.session_id=? AND t.status='running'",(session_id,)).fetchone()
            return row['id'] if row else None
    def command(self, data, session_id=None, source='manual'):
        action=data.get('action')
        if action=='start':
            label=data.get('label','')
            if not isinstance(label,str) or not 1<=len(label.strip())<=120: raise ValueError('Use a short task label, without private content')
            sid=session_id or data.get('session_id')
            if not sid: raise ValueError('Choose the MCP session for this task')
            started=nonnegative(data.get('started',time.time()))
            if started>time.time()+5: raise ValueError('Task start cannot be in the future')
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                if not db.execute('SELECT 1 FROM sessions WHERE id=?',(sid,)).fetchone(): raise ValueError('Unknown MCP session')
                if db.execute("SELECT 1 FROM task_sessions s JOIN tasks t ON t.id=s.task_id WHERE s.session_id=? AND t.status='running'",(sid,)).fetchone(): raise ValueError('Finish the current task before starting another prompt')
                tid=uuid.uuid4().hex
                model=str(data.get('model',''))[:80]; effort=str(data.get('effort',''))[:24]
                meta={'usage':{},'usage_source':'unknown','pricing_date':PRICING_DATE,'pricing_source':PRICING_SOURCE,'rates':CLAUDE_PRICES.get(model_key(model)), 'memory_cost':None}
                db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)',(tid,label.strip(),started,None,'running',source,model,effort,'unverified',json.dumps(meta)))
                db.execute('INSERT INTO task_sessions VALUES(?,?)',(tid,sid))
            return {'task_id':tid,'status':'running','boundary_source':source}
        tid=data.get('task_id') or (self.active(session_id) if session_id else None)
        if not tid: raise ValueError('Specify an existing task ID')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if not row: raise ValueError('Unknown task')
            if session_id and not db.execute('SELECT 1 FROM task_sessions WHERE task_id=? AND session_id=?',(tid,session_id)).fetchone():
                raise ValueError('Attach this session before updating the task')
            if action=='attach':
                sid=data.get('session_id')
                if row['status']!='running': raise ValueError('Only running tasks can attach another session')
                if not db.execute('SELECT 1 FROM sessions WHERE id=?',(sid,)).fetchone(): raise ValueError('Unknown session')
                if db.execute("SELECT 1 FROM task_sessions s JOIN tasks t ON t.id=s.task_id WHERE s.session_id=? AND t.status='running' AND t.id!=?",(sid,tid)).fetchone(): raise ValueError('Session is already tracking another task')
                db.execute('INSERT OR IGNORE INTO task_sessions VALUES(?,?)',(tid,sid))
            elif action=='finish':
                if row['status']!='running': raise ValueError('Task already finished')
                status=data.get('status','complete')
                if status not in ('complete','failed','cancelled','awaiting_approval'): raise ValueError('Invalid task outcome')
                verification=data.get('verification','unverified')
                if verification not in ('unverified','agent_reported','independent'): raise ValueError('Invalid verification source')
                if source=='agent_marker' and verification=='independent': raise ValueError('Agent completion cannot assert independent verification')
                finished=nonnegative(data.get('finished',time.time()))
                if finished<row['started'] or finished>time.time()+5: raise ValueError('Invalid finish time')
                db.execute('UPDATE tasks SET finished=?,status=?,verification=? WHERE id=?',(finished,status,verification,tid))
            elif action=='usage':
                meta=json.loads(row['metadata'])
                usage=data.get('usage',{})
                if not isinstance(usage,dict): raise ValueError('Usage must be an object')
                if any(k not in TOKEN_KEYS for k in usage): raise ValueError('Unknown token category')
                meta['usage']={k:nonnegative(usage.get(k),True) for k in TOKEN_KEYS}
                usage_source=data.get('usage_source','manual')
                if usage_source not in ('manual','client_reported','estimated'): raise ValueError('Invalid usage source')
                meta['usage_source']=usage_source
                meta['main_agent_turns']=nonnegative(data.get('main_agent_turns'),True)
                meta['memory_cost']=nonnegative(data.get('memory_cost'))
                meta['provider_rates']={k:nonnegative(data.get(k)) for k in ('decision_input_rate','decision_output_rate','vision_input_rate','vision_output_rate')}
                db.execute('UPDATE tasks SET metadata=? WHERE id=?',(json.dumps(meta),tid))
            else: raise ValueError('Use start, attach, finish or usage')
        return {'task_id':tid,'action':action}
    def record_providers(self, db, row):
        for event in row.get('provider_events',[]):
            raw=event.get('usage',{}); usage={}
            if isinstance(raw,dict):
                for key in ('input_tokens','output_tokens','prompt_tokens','completion_tokens','total_tokens','cost'):
                    value=raw.get(key)
                    if type(value) in ((int,float) if key=='cost' else (int,)) and math.isfinite(value) and 0<=value<=10**12: usage[key]=value
            db.execute('INSERT INTO provider_usage VALUES(?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,row['id'],row.get('task_id'),event['kind'],event['provider'],event['model'],event['status'],json.dumps(usage),event.get('latency',0)))
    def snapshot(self):
        with self.db() as db:
            tasks=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY started DESC LIMIT 100')]
            for task in tasks:
                meta=json.loads(task.pop('metadata'));task['usage']=meta['usage'];task['usage_source']=meta['usage_source']
                task['main_agent_turns']=meta.get('main_agent_turns')
                task['provider_rates']=meta.get('provider_rates',{});task['pricing_rates']=meta.get('rates')
                task['pricing_date']=meta['pricing_date'];task['pricing_source']=meta['pricing_source']
                rates=meta.get('rates')
                task['claude_cost']=(sum(meta['usage'][k]*r for k,r in zip(TOKEN_KEYS,rates))/1e6 if rates and all(meta['usage'].get(k) is not None for k in TOKEN_KEYS) else None)
                if model_key(task['model'])=='claude-haiku-5.5': task['claude_cost']=None # context-tier pricing needs per-call context sizes
                task['elapsed_seconds']=max(0,(task['finished'] or time.time())-task['started'])
                all_rows=[dict(r) for r in db.execute("SELECT * FROM requests WHERE task_id=? AND method='tools/call'",(task['id'],))]
                rows=[r for r in all_rows if r['tool'] not in ('browserhelm_task', 'openragnar_task')]
                controls=[r for r in all_rows if r['tool'] in ('browserhelm_task', 'openragnar_task')]
                task['tracking_calls']=len(controls);task['tracking_seconds']=sum(max(0,r['finished']-r['started']) for r in controls)
                task['tool_calls']=len(rows);task['failures']=sum(r['status']=='error' for r in rows)
                task['browser_calls']=sum(r['upstream_calls'] or 0 for r in rows)
                task['tool_seconds']=sum(max(0,r['finished']-r['started']) for r in rows)
                task['text_token_equivalents']=round(sum(r['input_bytes']+r['client_text'] for r in all_rows)/3)
                task['session_ids']=[r[0] for r in db.execute('SELECT session_id FROM task_sessions WHERE task_id=?',(task['id'],))]
                providers=[dict(r) for r in db.execute('SELECT * FROM provider_usage WHERE task_id=?',(task['id'],))]
                for r in rows:
                    missing=max(0,(r['provider_calls'] or 0)-sum(e['request_id']==r['id'] for e in providers))
                    for _ in range(missing): providers.append({'kind':'vision' if r['tool'] in ('browserhelm_visual_act', 'openragnar_visual_act') else 'decision','provider':'unknown','model':'unknown','status':'unknown','usage':'{}','request_id':r['id']})
                for kind in ('decision','vision'):
                    events=[e for e in providers if e['kind']==kind];known=0.; unknown=0; tokens=0; token_unknown=0; bases=set()
                    for event in events:
                        usage=json.loads(event['usage']);a=usage.get('input_tokens',usage.get('prompt_tokens'));b=usage.get('output_tokens',usage.get('completion_tokens'))
                        total=usage.get('total_tokens',a+b if type(a) is int and type(b) is int else None)
                        if type(total) is int and total>=0: tokens+=total
                        else: token_unknown+=1
                        cost=usage.get('cost');reported=type(cost) in (int,float) and math.isfinite(cost) and cost>=0
                        basis='provider_reported' if reported else 'unknown'
                        if not reported:
                            rates=meta.get('provider_rates',{});ir=rates.get(kind+'_input_rate');orr=rates.get(kind+'_output_rate')
                            if event['provider'] in ('ollama','lmstudio'): cost=0.; basis='local_api_zero'
                            elif event['status']=='ok' and a is not None and b is not None and ir is not None and orr is not None: cost=(a*ir+b*orr)/1e6; basis='rate_estimate'
                            else: cost=None
                        bases.add(basis)
                        if cost is None: unknown+=1
                        else:known+=cost
                    task[kind]={'calls':len(events),'tokens':tokens if not token_unknown else None,'known_tokens':tokens,'unknown_usage_calls':token_unknown,'cost':known if not unknown else None,'known_cost':known,'unknown_cost_calls':unknown,'cost_basis':','.join(sorted(bases)) if bases else 'no_provider_calls'}
                task['memory_cost']=meta.get('memory_cost')
                parts=[task['claude_cost'],task['decision']['cost'],task['vision']['cost'],task['memory_cost']]
                task['known_cost']=(task['claude_cost'] or 0)+task['decision']['known_cost']+task['vision']['known_cost']+(task['memory_cost'] or 0)
                task['total_cost']=sum(parts) if all(v is not None for v in parts) else None
        return tasks
