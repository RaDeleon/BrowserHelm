"""Private, cross-process gateway counters. Never persist tool arguments or results.
Token equivalents use text UTF-8 bytes / 3, not a tokenizer or billed LLM usage.
Neo's cockpit values are its own estimates, not a Claude-alone benchmark.
"""
import hashlib
import json
import math
import os
import pathlib
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()) if value is not None else 0


def text_size(response):
    # Ignore base64 image/audio payloads. Image billing cannot be inferred from bytes.
    if not isinstance(response, dict):
        return 0
    result = response.get('result', {})
    if not isinstance(result, dict):
        return size(response)
    if 'content' not in result:
        return size(response)
    texts = [b.get('text', '') for b in result.get('content', []) if b.get('type') == 'text']
    structured = result.get('structuredContent')
    return sum(len(t.encode()) for t in texts) + (size(structured) if structured is not None else 0)


def usage_tokens(usage):
    def valid(key):
        v = usage.get(key)
        return v if type(v) is int and 0 <= v <= 10**12 else None
    total = valid('total_tokens')
    if total is not None:
        return total
    a = valid('input_tokens')
    b = valid('output_tokens')
    if a is None:
        a = valid('prompt_tokens')
    if b is None:
        b = valid('completion_tokens')
    return a + b if a is not None and b is not None else None


class Metrics:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        self.sid = uuid.uuid4().hex
        with self.db() as db:
            # Readers in the dashboard must not block concurrent MCP writers.
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, client TEXT, label TEXT, started REAL, updated REAL,
              pid INTEGER, closed INTEGER DEFAULT 0, upstream_hash TEXT, compact INTEGER);
            CREATE TABLE IF NOT EXISTS requests (
              id TEXT PRIMARY KEY, session_id TEXT, method TEXT, tool TEXT, started REAL,
              finished REAL, status TEXT, input_bytes INTEGER, upstream_input_bytes INTEGER, upstream_bytes INTEGER,
              client_bytes INTEGER, upstream_text INTEGER, client_text INTEGER,
              upstream_calls INTEGER, provider_tokens INTEGER, provider_calls INTEGER,
              provider_unknown INTEGER, media_count INTEGER, moves INTEGER, moves_status TEXT);
            CREATE INDEX IF NOT EXISTS requests_session ON requests(session_id, started);
            CREATE TABLE IF NOT EXISTS benchmarks (
              session_id TEXT PRIMARY KEY, claude_tokens INTEGER, neo_tokens INTEGER,
              gateway_tokens INTEGER, updated REAL);
            ''')
            columns={row[1] for row in db.execute('PRAGMA table_info(requests)')}
            for column, kind in [('upstream_input_bytes','INTEGER DEFAULT 0'),('moves','INTEGER'),('moves_status','TEXT')]:
                if column not in columns:
                    db.execute('ALTER TABLE requests ADD COLUMN '+column+' '+kind)
            # Counters describe retained history; keep 90 days, never unbounded content logs.
            db.execute('DELETE FROM requests WHERE started < ?', (time.time()-90*86400,))
            db.execute('DELETE FROM sessions WHERE updated < ?', (time.time()-90*86400,))
            db.execute('DELETE FROM benchmarks WHERE session_id NOT IN (SELECT id FROM sessions)')
        os.chmod(self.path, 0o600)

    def db(self):
        db = sqlite3.connect(str(self.path), timeout=1.0)
        db.row_factory = sqlite3.Row
        return db

    def start(self, client, compact=False):
        with self.db() as db:
            now = time.time()
            db.execute('INSERT OR REPLACE INTO sessions(id,client,label,started,updated,pid,compact) VALUES(?,?,?,?,?,?,?)',
                       (self.sid, str(client)[:80], '', now, now, os.getpid(), int(compact)))

    def record(self, row, upstream_session=None, label=None):
        with self.db() as db:
            if not db.execute('SELECT 1 FROM sessions WHERE id=?', (self.sid,)).fetchone():
                self.start('Unknown MCP client')
            columns = ['id','session_id','method','tool','started','finished','status','input_bytes',
                       'upstream_input_bytes','upstream_bytes','client_bytes','upstream_text','client_text','upstream_calls',
                       'provider_tokens','provider_calls','provider_unknown','media_count']
            rid = row.get('id') or uuid.uuid4().hex
            data = {**row, 'id': rid, 'session_id':self.sid}
            db.execute('INSERT INTO requests('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                       [data[c] for c in columns])
            db.execute('UPDATE sessions SET updated=?, upstream_hash=COALESCE(?,upstream_hash), label=COALESCE(?,label) WHERE id=?',
                       (row['finished'], digest(upstream_session) if upstream_session else None,
                        str(label)[:120] if label else None, self.sid))
        return rid

    def moves(self, request_id, moves):
        with self.db() as db:
            db.execute("UPDATE requests SET moves=?,moves_status='time-correlated Neo dispatches' WHERE id=?",(moves,request_id))

    def close(self):
        with self.db() as db:
            db.execute('UPDATE sessions SET closed=1, updated=? WHERE id=?',(time.time(),self.sid))

    def benchmark(self, session_id, claude=None, neo=None, gateway=None):
        values = [claude, neo, gateway]
        if any(v is not None and (type(v) is not int or not 0 <= v <= 10**12) for v in values):
            raise ValueError('Benchmark values must be nonnegative integer token totals')
        with self.db() as db:
            if not db.execute('SELECT 1 FROM sessions WHERE id=?',(session_id,)).fetchone():
                raise ValueError('Unknown session')
            db.execute('INSERT OR REPLACE INTO benchmarks VALUES(?,?,?,?,?)',(session_id,claude,neo,gateway,time.time()))

    def snapshot(self):
        with self.db() as db:
            totals = dict(db.execute('''SELECT COUNT(*) requests,
              COALESCE(SUM(CASE WHEN method='tools/call' THEN 1 ELSE 0 END),0) tool_requests,
              COALESCE(SUM(input_bytes),0) input_bytes, COALESCE(SUM(upstream_input_bytes),0) upstream_input_bytes, COALESCE(SUM(upstream_bytes),0) upstream_bytes,
              COALESCE(SUM(client_bytes),0) client_bytes, COALESCE(SUM(upstream_text),0) upstream_text,
              COALESCE(SUM(client_text),0) client_text, COALESCE(SUM(upstream_calls),0) upstream_calls,
              COALESCE(SUM(provider_tokens),0) provider_tokens, COALESCE(SUM(provider_calls),0) provider_calls,
              COALESCE(SUM(provider_unknown),0) provider_unknown, COALESCE(SUM(media_count),0) media_count
              FROM requests''').fetchone())
            # Savings apply only to forwarded replies. Local artifact/help/provider replies are overhead.
            # Include them in both paths, so repeated artifact reads reduce net savings.
            totals['net_text_saved'] = totals['upstream_input_bytes'] + totals['upstream_text'] - totals['input_bytes'] - totals['client_text']
            sessions = [dict(r) for r in db.execute('''SELECT s.*,
              COUNT(r.id) requests, COALESCE(SUM(CASE WHEN r.method='tools/call' THEN 1 ELSE 0 END),0) tool_requests,
              COALESCE(SUM(r.input_bytes+r.client_text),0) text_bytes,
              COALESCE(SUM(r.upstream_input_bytes+r.upstream_text-r.input_bytes-r.client_text),0) saved_text,
              COALESCE(SUM(r.upstream_calls),0) upstream_calls,
              COALESCE(SUM(r.provider_tokens),0) provider_tokens,
              COALESCE(SUM(r.provider_unknown),0) provider_unknown
              FROM sessions s LEFT JOIN requests r ON r.session_id=s.id
              GROUP BY s.id ORDER BY s.started DESC LIMIT 100''')]
            requests = [dict(r) for r in db.execute('SELECT * FROM requests ORDER BY started DESC LIMIT 1000')]
            benchmarks = [dict(r) for r in db.execute('SELECT * FROM benchmarks')]
        for session in sessions:
            try:
                os.kill(session.pop('pid'),0)
                session['active'] = not bool(session['closed'])
            except (OSError, KeyError):
                session['active'] = False
        return {'totals':totals,'sessions':sessions,'requests':requests,'benchmarks':benchmarks,
                'retentionDays':90,'requestLimit':1000,'sessionLimit':100,'updatedAt':time.time()}


class NeoReader:
    def __init__(self, upstream):
        p = urllib.parse.urlsplit(upstream)
        if p.scheme != 'http' or p.hostname not in ('localhost','127.0.0.1','::1') or p.username or p.password:
            raise ValueError('Neo metrics require a loopback HTTP endpoint')
        self.base = urllib.parse.urlunsplit((p.scheme,p.netloc,'','',''))
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, path):
        with self.opener.open(self.base+path,timeout=3) as response:
            raw=response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:
                raise ValueError('Neo metrics response too large')
            return json.loads(raw)

    def snapshot(self, gateway_hashes):
        stats = self.get('/api/v1/cockpit/stats')
        history = self.get('/api/v1/sessions?limit=100')
        # Project safe scalar counters only. Do not copy URLs, argsJson, page text or transport IDs.
        items = []
        for raw in history.get('items',[]):
            h=digest(raw.get('sessionId',''))
            via=h in gateway_hashes or 'openragnar' in str(raw.get('slug','')).lower()
            tokens=raw.get('tokenUsage',{}) or {}
            items.append({'id':h,'client':str(raw.get('label','Neo client'))[:80],
                          'label':str(raw.get('name','Browser session'))[:120], 'viaGateway':via,
                          'started':raw.get('startedAt',0)/1000,'moves':raw.get('dispatchCount',0),
                          'tokens':tokens.get('totalTokenEstimate'), 'status':raw.get('status','unknown'),
                          'errors':raw.get('errorCount',0)})
        return {'available':True,'stats':stats,'sessions':items,'hasMore':bool(history.get('nextCursor'))}

    def request_moves(self, session_id, started, finished, tool):
        # Use actual Neo dispatch rows in this request's interval, including nested run steps.
        # Time correlation is approximate; overlapping requests are excluded by the caller.
        data=self.get('/api/v1/sessions/'+urllib.parse.quote(session_id,safe=''))
        all_rows=data.get('dispatches',[])
        rows=[r for r in all_rows if math.floor(started*1000) <= r.get('createdAt',0) <= math.floor(finished*1000)]
        roots=[r for r in rows if r.get('toolName')==tool and not r.get('parentDispatchId')]
        if len(roots)!=1:
            return None  # Millisecond timestamps cannot distinguish adjacent same-tool calls.
        root=roots[0]
        if any(r.get('parentDispatchId') for r in all_rows):
            # Prefer Neo's real parent/child links when the installed version supplies them.
            selected=[root]
            keys={str(root.get('dispatchKey','')),str(root.get('dispatchId',''))} - {''}
            while True:
                children=[r for r in all_rows if r not in selected and str(r.get('parentDispatchId','')) in keys]
                if not children:
                    break
                selected.extend(children)
                for child in children:
                    keys.update(str(child.get(k,'')) for k in ('dispatchKey','dispatchId'))
                keys.discard('')
            return len(selected)
        # Older Neo versions only expose millisecond times; never call this exact attribution.
        return len(rows)


def connectors(snapshot):
    home=pathlib.Path.home()
    definitions=[('Claude Desktop',home/'Library/Application Support/Claude/claude_desktop_config.json'),
                 ('Claude Code',home/'.claude.json'),('Codex',home/'.codex/config.toml')]
    result=[]
    for name,path in definitions:
        configured=False
        others=[]
        try:
            if path.suffix=='.toml':
                import tomllib
                data=tomllib.loads(path.read_text())
                entries=data.get('mcp_servers',{})
            else:
                entries=json.loads(path.read_text()).get('mcpServers',{})
            others=sorted(str(k)[:80] for k in entries if k != 'openragnar')
            entry=entries.get('openragnar',{})
            command=str(entry.get('command',''))
            configured=command.endswith('/OpenRagnar.app/Contents/MacOS/OpenRagnar') and '--mcp' in entry.get('args',[])
        except (OSError, ValueError, ImportError, TypeError, AttributeError):
            pass
        patterns={'Claude Desktop':['claude-desktop','claude desktop','claude-ai'], 'Claude Code':['claude-code','claude code'], 'Codex':['codex']}
        active=sum(1 for s in snapshot['sessions'] if s['active'] and any(p in s['client'].lower() for p in patterns[name]))
        result.append({'name':name,'configured':configured,'activeSessions':active,'path':str(path),'otherConnectors':others})
    return result


def dashboard(path, upstream):
    metrics=Metrics(path)
    result=metrics.snapshot()
    result['connectors']=connectors(result)
    try:
        result['neo']=NeoReader(upstream).snapshot({s['upstream_hash'] for s in result['sessions'] if s['upstream_hash']})
    except Exception as error:
        result['neo']={'available':False,'error':'Neo statistics unavailable ('+type(error).__name__+')'}
    return result
