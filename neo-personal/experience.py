"""Scoped OpenViking browser experiences; no model-generated reflection or page dumps."""
import hashlib
import hmac
import json
import os
import pathlib
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import uuid

ROOT = 'viking://~/memories/experiences/openragnar'
MAX_HINT_BYTES = 1600
LESSONS = {
    'stale_link': 'The selected link or page changed. Re-observe instead of replaying the old action.',
    'step_budget': 'The route did not reach the text postcondition within its step budget. Consider another observed route.',
    'no_links': 'No eligible link remained. Return control to the main agent.',
    'uncertain': 'The provider was uncertain. Do not treat the attempted route as a proven success.',
    'provider_error': 'The decision provider failed. Check its connection; do not repeat browser writes.',
    'execution_error': 'A browser step failed. Inspect current state before another attempt.',
    'cancelled': 'Execution stopped at its cancellation or time budget. Completion was not verified.',
}


def same_task(document, start, goal, needle, age=90*86400):
    """Match intent as well as host/postcondition; never transfer a route to another goal."""
    if not isinstance(document, dict) or document.get('schema') not in (1, 2) or document.get('source') != 'openragnar':
        return False
    if document.get('kind', 'navigation') != 'navigation' or document.get('test') or 'validation' in str(document.get('provider', '')).lower():
        return False
    created = document.get('created')
    return (type(created) in (int, float) and 0 <= time.time()-created <= age and
            document.get('host') == urllib.parse.urlsplit(start).netloc and
            document.get('start') == safe_url(start) and
            str(document.get('goal', '')).strip().casefold() == clean(goal).strip().casefold() and
            document.get('successText') == clean(needle, 200))


def route_data(document, host, key='route'):
    rows = document.get(key, [])
    if not isinstance(rows, list): return []
    route = []
    for row in rows[:6]:
        if not isinstance(row, dict): continue
        try:
            source, target = safe_url(row.get('from', '')), safe_url(row.get('to', ''))
            if not source or not target or urllib.parse.urlsplit(source).netloc != host or urllib.parse.urlsplit(target).netloc != host: continue
            route.append({'from': source, 'to': target, 'label': clean(row.get('label', ''), 80)})
        except ValueError: continue
    return route


def clean(value, limit=500):
    text = str(value)[:limit]
    text = re.sub(r'(?i)(?:bearer\s+|sk-|api[_-]?key[=: ]+)\S+', '[redacted]', text)
    text = re.sub(r'(?i)\b(?:password|secret|token)\s*[=:]\s*\S+', '[redacted]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[email]', text)
    return text


def safe_url(value):
    p = urllib.parse.urlsplit(str(value))
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query:
        return ''
    return urllib.parse.urlunsplit((p.scheme, p.netloc, clean(p.path, 1000), '', ''))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirected service.


class ExperienceMemory:
    def __init__(self, settings, path, config_path=None):
        self.initial_enabled = settings.get('enabled', False) is True
        self.validation = settings.get('validation', False) is True
        self.path = pathlib.Path(path)
        self.settings_path = self.path.parent/'settings.json'
        self.config_path = pathlib.Path(config_path or pathlib.Path.home()/'.openviking/ovcli.conf')
        self.stop = threading.Event()
        self.worker = None
        self.root = ROOT  # Deliberately fixed to this app's collection.
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS experiences (
              id TEXT PRIMARY KEY, document TEXT NOT NULL, created REAL NOT NULL,
              synced REAL, retry_at REAL DEFAULT 0, lease REAL DEFAULT 0,
              destination TEXT NOT NULL DEFAULT '');
              CREATE TABLE IF NOT EXISTS memory_state (key TEXT PRIMARY KEY, value TEXT);
              CREATE TABLE IF NOT EXISTS tool_history (
                id TEXT PRIMARY KEY, destination TEXT, tool TEXT, signature TEXT,
                created REAL, status TEXT, category TEXT);
              CREATE INDEX IF NOT EXISTS tool_history_match ON tool_history(destination,signature,created);
                CREATE TABLE IF NOT EXISTS visual_history (
                  id TEXT PRIMARY KEY, destination TEXT, task TEXT, scene TEXT,
                  created REAL, status TEXT, point TEXT, source TEXT);
                CREATE INDEX IF NOT EXISTS visual_history_match ON visual_history(destination,task,scene,created);
            ''')
            db.execute('INSERT OR IGNORE INTO memory_state VALUES (?,?)', ('request_hmac_key', os.urandom(32).hex()))
        self.path.chmod(0o600)

    @property
    def enabled(self):
        try:
            return json.loads(self.settings_path.read_text()).get('memory',{}).get('enabled') is True
        except (OSError, ValueError):
            return self.initial_enabled

    def db(self):
        return sqlite3.connect(str(self.path), timeout=.1)

    def state(self, key, value):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO memory_state VALUES (?,?)', (key, str(value)))

    def credentials(self):
        c = json.loads(self.config_path.read_text())
        url = c.get('url', '').rstrip('/')
        p = urllib.parse.urlsplit(url)
        if p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
            raise ValueError('Invalid OpenViking endpoint')
        if p.scheme != 'https' and not (p.scheme == 'http' and p.hostname in ('localhost','127.0.0.1','::1')):
            raise ValueError('OpenViking requires HTTPS or a local endpoint')
        headers = {'Content-Type': 'application/json', 'User-Agent': 'browserhelm/0.5.0'}
        if c.get('api_key'):
            headers['Authorization'] = 'Bearer ' + c['api_key']
        # Match the installed plugin: identity headers only in trusted mode.
        if c.get('auth_mode') == 'trusted' or (not c.get('auth_mode') and (c.get('account') or c.get('user'))):
            if c.get('account'): headers['X-OpenViking-Account'] = c['account']
            if c.get('user'): headers['X-OpenViking-User'] = c['user']
        return url, headers

    def request(self, path, body=None, timeout=2):
        url, headers = self.credentials()
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url+path, data=data, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=max(.1, timeout)) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000: raise ValueError('Memory response exceeds budget')
        value = json.loads(raw)
        if value.get('status') == 'error': raise ValueError('Memory request failed')
        return value.get('result', value)

    def test(self):
        info = self.request('/health')
        if info.get('healthy') is not True: raise ValueError('Memory service unavailable')
        self.state('connection', 'Connected')
        self.state('checked_at', time.time())
        self.state('user_id', info.get('user_id',''))
        self.state('identity_destination', self.destination())
        return {'connected': True, 'version': info.get('version'), 'collection': self.root}

    def destination(self):
        url, headers = self.credentials()
        return hashlib.sha256(json.dumps([url,headers,self.root],sort_keys=True).encode()).hexdigest()

    def start(self):
        if not self.enabled or self.worker: return
        def work():
            try: self.test()
            except Exception: pass
            while not self.stop.is_set():
                try: self.sync(limit=2)
                except Exception: pass  # Private pending records survive any service failure.
                self.stop.wait(30)
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def close(self):
        self.stop.set()
        if self.worker: self.worker.join(timeout=3)

    def local_documents(self):
        with self.db() as db:
            rows = db.execute('SELECT document FROM experiences WHERE destination=? AND document NOT LIKE ? AND document NOT LIKE ? ORDER BY created DESC LIMIT 200',
                              (self.destination(), '%"kind": "tool_outcome"%', '%"kind": "visual_outcome"%')).fetchall()
        documents = []
        for row in rows:
            try: documents.append(json.loads(row[0]))
            except (ValueError, TypeError): continue
        return documents

    def increment(self, values):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            for key, amount in values.items():
                if not amount: continue
                old = db.execute('SELECT value FROM memory_state WHERE key=?', (key,)).fetchone()
                db.execute('INSERT OR REPLACE INTO memory_state VALUES (?,?)', (key, str((int(old[0]) if old else 0)+amount)))

    def choose_verified_route(self, start, goal, needle, current, options):
        """Skip a provider choice only after two locally observed successes, never from remote hints alone."""
        if not self.enabled: return None
        documents = [d for d in self.local_documents() if same_task(d, start, goal, needle, 30*86400)]
        task_key = self.signature('navigation_task', [start, goal, needle])
        documents = [d for d in documents if d.get('taskKey') == task_key or
                     (not d.get('taskKey') and goal == clean(goal) and needle == clean(needle, 200))]
        candidates = []
        host = urllib.parse.urlsplit(start).netloc
        for choice, option in options.items():
            if not isinstance(option, dict): continue
            edge = (current, option.get('url'))
            evidence, failure_at = {}, 0
            for document in documents:
                edges = [(r['from'], r['to']) for r in route_data(document, host)]
                attempts = [(r['from'], r['to']) for r in route_data(document, host, 'attempts')]
                if document.get('verified') is True and document.get('status') == 'complete' and edge in edges:
                    evidence[document.get('id')] = document['created']
                elif document.get('verified') is not True and edge in edges+attempts:
                    failure_at = max(failure_at, document['created'])
            support = sum(created > failure_at for identifier, created in evidence.items() if identifier)
            if support >= 2: candidates.append((choice, support))
        # Conflicting successful paths go back to the provider rather than choosing arbitrarily.
        if len(candidates) != 1: return None
        return {'choice': candidates[0][0], 'probability': None, 'evidence': 'two or more local text-verified runs; live link recheck required',
                'usage': {}, 'model': 'local-verified-route', 'latencySeconds': 0, 'localRouteReuse': True}

    def record_route_use(self, avoided, followed, completed):
        if not self.enabled: return
        self.increment({'provider_calls_avoided': avoided, 'reused_steps': followed,
                        'tasks_with_reuse': int(avoided > 0), 'reused_tasks_verified': int(avoided > 0 and completed)})

    def signature(self, tool, arguments):
        with self.db() as db:
            key = bytes.fromhex(db.execute("SELECT value FROM memory_state WHERE key='request_hmac_key'").fetchone()[0])
        payload = json.dumps([tool, arguments], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def visual_evidence(self, task, scene):
        """Only this installation's observations count; remote memories cannot authorize coordinates."""
        if not self.enabled: return {'support': 0, 'failures': 0, 'point': None}
        with self.db() as db:
            rows = db.execute("SELECT status,point,source FROM visual_history WHERE destination=? AND task=? AND scene=? AND created>? AND (source='model' OR status<>'text_verified') ORDER BY created DESC,rowid DESC LIMIT 25",
                              (self.destination(), task, scene, time.time()-7*86400)).fetchall()
        support, failures, point = 0, 0, None
        for status, raw, source in rows:
            if status != 'text_verified':
                if not support: failures += 1
                else: break
                continue
            if failures: break
            if source == 'model':
                support += 1
                if point is None: point = json.loads(raw)
        return {'support': support, 'failures': failures, 'point': point if support >= 2 else None}

    def capture_visual(self, task, scene, point, report):
        if not self.enabled: return 'not saved'
        identifier, now = str(uuid.uuid4()), time.time()
        source = report['groundingSource']
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM visual_history WHERE created<?', (now-7*86400,))
            db.execute('INSERT INTO visual_history VALUES (?,?,?,?,?,?,?,?)',
                       (identifier, self.destination(), task, scene, now, report['status'], json.dumps(point), source))
            db.execute('DELETE FROM visual_history WHERE id IN (SELECT id FROM visual_history ORDER BY created DESC LIMIT -1 OFFSET 2000)')
        reused = source == 'verified_local_memory'
        self.increment({'visual_attempts': 1, 'visual_verified': int(report['verified']),
                        'visual_calls_avoided': int(reused), 'visual_reuse_verified': int(reused and report['verified'])})
        # Upload lessons/outcomes only. Screenshots, URL, instruction, postcondition,
        # coordinates and scene fingerprint remain private to this installation.
        document = {'schema': 3, 'source': 'openragnar', 'kind': 'visual_outcome', 'id': identifier, 'created': now,
                    'goal': 'Visual target '+report['status'], 'verified': report['verified'], 'status': report['status'],
                    'verification': 'successText absent before click; presence afterward only if verified=true',
                    'groundingSource': source, 'taskKey': task, 'test': self.validation,
                    'lesson': 'Use only the identical fresh screen and matching task; revoke reuse after failed verification.',
                    'model': clean(point.get('model', ''), 100)}
        return self.enqueue(document)

    def prior_tool_failure(self, tool, arguments):
        if not self.enabled: return None
        with self.db() as db:
            rows = db.execute('SELECT status,category FROM tool_history WHERE destination=? AND signature=? AND created>? ORDER BY created DESC,rowid DESC LIMIT 20',
                              (self.destination(), self.signature(tool, arguments), time.time()-14*86400)).fetchall()
        failed = []
        for status, category in rows:
            if status != 'error': break  # A later accepted request retires the old warning.
            failed.append(category)
        if not failed: return None
        from diagnostics import issue
        detail = issue(failed[0])
        return {'priorMatchingFailures': len(failed), 'category': detail['category'], 'advice': detail['advice'],
                'scope': 'identical tool arguments; MCP request outcome only'}

    def capture_tool(self, tool, arguments, row, hint_shown=False):
        if not self.enabled or tool.startswith(('openragnar_', 'browserhelm_')): return
        from diagnostics import issue
        category = issue((row.get('diagnostic') or {}).get('category', 'ok'))['category']
        identifier = row['id']
        previous = self.prior_tool_failure(tool, arguments)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM tool_history WHERE created<?', (time.time()-14*86400,))
            db.execute('INSERT OR IGNORE INTO tool_history VALUES (?,?,?,?,?,?,?)',
                       (identifier, self.destination(), clean(tool, 80), self.signature(tool, arguments), row['finished'], row['status'], category))
            db.execute('DELETE FROM tool_history WHERE id IN (SELECT id FROM tool_history ORDER BY created DESC LIMIT -1 OFFSET 10000)')
        if hint_shown: self.increment({'repeat_failure_hints': 1})
        # Sync reusable failure/recovery evidence, not every successful low-level request.
        if row['status'] == 'error' or previous:
            document = {'schema': 2, 'source': 'openragnar', 'kind': 'tool_outcome', 'id': identifier, 'created': row['finished'],
                        'test': False, 'goal': clean(tool, 80)+' request '+('failed' if row['status']=='error' else 'accepted after failure'),
                        'verified': False, 'verification': 'MCP outcome only; task completion unknown', 'tool': clean(tool, 80),
                        'status': row['status'], 'category': category, 'lesson': issue(category)['advice']}
            self.enqueue(document)

    def enqueue(self, document):
        try:
            destination = self.destination()
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM experiences WHERE synced IS NOT NULL AND created < ?', (time.time()-90*86400,))
                if db.execute('SELECT COUNT(*) FROM experiences WHERE synced IS NULL').fetchone()[0] >= 500:
                    return 'queue full; outcome not stored'
                db.execute('INSERT OR IGNORE INTO experiences (id,document,created,destination) VALUES (?,?,?,?)',
                           (document['id'], json.dumps(document), document['created'], destination))
                db.execute('DELETE FROM experiences WHERE id IN (SELECT id FROM experiences WHERE synced IS NOT NULL ORDER BY created DESC LIMIT -1 OFFSET 3000)')
            return 'queued'
        except Exception:
            return 'memory storage unavailable; browser outcome unchanged'

    def recall(self, start, goal, needle):
        if not self.enabled: return []
        documents = self.local_documents()
        deadline = time.monotonic()+3
        try:
            if any(same_task(d, start, goal, needle) and (route_data(d, urllib.parse.urlsplit(start).netloc) or d.get('failureCategory') in LESSONS) for d in documents):
                self.state('recall_source', 'Local cache')
                return self.hints(documents, start, goal, needle)
            destination = self.destination()
            with self.db() as db: identity = dict(db.execute('SELECT key,value FROM memory_state').fetchall())
            if identity.get('recall_failed_destination') == destination and time.time()-float(identity.get('recall_failed_at',0)) < 30:
                self.state('recall_source', 'Local fallback; service retry deferred')
                return self.hints(documents, start, goal, needle)
            if identity.get('identity_destination') != destination:
                self.test()
                with self.db() as db: identity = dict(db.execute('SELECT key,value FROM memory_state').fetchall())
            canonical = 'viking://user/'+identity.get('user_id','')+'/memories/experiences/openragnar/'
            found = self.request('/api/v1/search/find', {'query': clean(goal)+' '+start+' '+clean(needle,200),
                'target_uri': self.root, 'limit': 5, 'level': [2]}, timeout=1.5)
            hits = found.get('memories', []) if isinstance(found, dict) else []
            for hit in hits[:3]:
                uri = hit.get('uri', '')
                # Server may expand ~/ to its authenticated user URI.
                valid = (uri.startswith(self.root+'/') or uri.startswith(canonical)) and re.fullmatch(r'[a-f0-9-]+\.md',uri.rsplit('/',1)[-1])
                if not valid or time.monotonic() >= deadline: continue
                result = self.request('/api/v1/content/read?'+urllib.parse.urlencode({'uri':uri,'limit':80}),
                    timeout=min(1,deadline-time.monotonic()))
                raw = result if isinstance(result,str) else result.get('content','')
                if len(raw) <= 12000: documents.append(json.loads(raw))
            self.state('connection', 'Connected')
            self.state('recall_source', 'OpenViking')
        except Exception:
            self.state('connection', 'Unavailable; using local experience cache')
            self.state('recall_failed_at', time.time())
            self.state('recall_failed_destination', self.destination())
        # Newly saved records can be used while semantic indexing is pending.
        return self.hints(documents, start, goal, needle)

    def hints(self, documents, start, goal, needle):
        hints, seen = [], set()
        host = urllib.parse.urlsplit(start).netloc
        for d in documents:
            if not same_task(d, start, goal, needle) or d.get('id') in seen: continue
            route = route_data(d, host)
            failure = d.get('failureCategory')
            hint = {'outcome': 'successText found' if d.get('verified') is True else 'postcondition not verified',
                    'route': route, 'browserCalls': d.get('browserCalls',0) if type(d.get('browserCalls')) is int else 0}
            if failure in LESSONS:
                hint.update(lesson=LESSONS[failure], attempted=route_data(d, host, 'attempts'))
            if not route and failure not in LESSONS: continue
            seen.add(d.get('id')); candidate = hints+[hint]
            if len(json.dumps(candidate).encode()) > MAX_HINT_BYTES: continue
            hints = candidate
            if len(hints) == 2: break
        self.state('last_recalled', len(hints))
        if hints: self.increment({'tasks_with_recall': 1})
        return hints

    def capture(self, start, goal, needle, report, route, test=False):
        if not self.enabled or report.get('status') == 'proposal': return 'not saved'
        identifier = str(uuid.uuid4())
        document = {'schema':2, 'source':'openragnar', 'kind':'navigation', 'id':identifier, 'created':time.time(),
              'test':test or 'validation' in str(report.get('provider','')).lower(), 'host':urllib.parse.urlsplit(start).netloc, 'start':safe_url(start),
            'goal':clean(goal), 'successText':clean(needle,200), 'verified':report.get('verified') is True,
            'verification':clean(report.get('verificationScope','literal successText presence only'),200), 'status':report.get('status'),
            'provider':clean(report.get('provider',''),60), 'browserCalls':report.get('browserCalls',0),
            'model':clean((report.get('decisions') or [{}])[-1].get('model',''),100),
              'elapsedSeconds':report.get('elapsedSeconds'),
              'taskKey':self.signature('navigation_task', [start, goal, needle]),
              'providerCallsAvoided':report.get('memory',{}).get('providerCallsAvoided',0),
              'failureCategory':report.get('failureCategory') if report.get('failureCategory') in LESSONS else None,
              'route':route_data({'route':route}, urllib.parse.urlsplit(start).netloc),
              'attempts':route_data(report, urllib.parse.urlsplit(start).netloc, 'attempts')}
        return self.enqueue(document)

    def sync(self, limit=2):
        if not self.enabled: return {'uploaded':0, 'disabled':True}
        destination = self.destination()
        uploaded = 0
        for _ in range(min(limit,5)):
            if not self.enabled or self.stop.is_set(): break
            now=time.time()
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT id,document FROM experiences WHERE synced IS NULL AND retry_at <= ? AND lease < ? AND destination=? ORDER BY created LIMIT 1', (now,now,destination)).fetchone()
                if not row: break
                db.execute('UPDATE experiences SET lease=? WHERE id=?',(now+30,row[0]))
            try:
                result=self.request('/api/v1/content/write', {'uri':self.root+'/'+row[0]+'.md', 'content':row[1],
                    'mode':'replace', 'wait':False, 'processing_mode':'vectors_only'})
                with self.db() as db:
                    db.execute('UPDATE experiences SET synced=?,lease=0 WHERE id=?',(time.time(),row[0]))
                uploaded+=1
                self.state('connection','Connected; indexing may still be pending')
            except Exception:
                with self.db() as db:
                    db.execute('UPDATE experiences SET retry_at=?,lease=0 WHERE id=?',(time.time()+60,row[0]))
                self.state('connection','Unavailable; outcomes queued locally')
                break
        return {'uploaded':uploaded, **self.snapshot()}

    def snapshot(self):
        with self.db() as db:
            state=dict(db.execute('SELECT key,value FROM memory_state').fetchall())
            count,pending=db.execute('SELECT COUNT(*),COALESCE(SUM(synced IS NULL),0) FROM experiences').fetchone()
            recent=db.execute('SELECT document,synced FROM experiences ORDER BY created DESC LIMIT 10').fetchall()
            requests,failures=db.execute("SELECT COUNT(*),COALESCE(SUM(status='error'),0) FROM tool_history").fetchone()
        try: endpoint=self.credentials()[0]
        except Exception: endpoint='Existing OpenViking connection unavailable'
        return {'enabled':self.enabled, 'endpoint':endpoint, 'collection':self.root,
            'connection':state.get('connection','Not checked'), 'saved':count-pending, 'pending':pending,
            'tasks_with_recall':int(state.get('tasks_with_recall',0)), 'last_recalled':int(state.get('last_recalled',0)),
              'tasks_with_reuse':int(state.get('tasks_with_reuse',0)), 'reused_steps':int(state.get('reused_steps',0)),
              'reused_tasks_verified':int(state.get('reused_tasks_verified',0)), 'provider_calls_avoided':int(state.get('provider_calls_avoided',0)),
              'repeat_failure_hints':int(state.get('repeat_failure_hints',0)), 'tool_requests_seen':requests, 'tool_failures':failures,
              'visual_attempts':int(state.get('visual_attempts',0)), 'visual_verified':int(state.get('visual_verified',0)),
              'visual_calls_avoided':int(state.get('visual_calls_avoided',0)), 'visual_reuse_verified':int(state.get('visual_reuse_verified',0)),
              'recall_source':state.get('recall_source','Not used'),
            'recent':[{'id':json.loads(r[0])['id'], 'goal':json.loads(r[0])['goal'],
                  'kind':json.loads(r[0]).get('kind','navigation'), 'failure_category':json.loads(r[0]).get('failureCategory') or json.loads(r[0]).get('category'),
                  'status':json.loads(r[0]).get('status','unknown'), 'test':json.loads(r[0]).get('test',False),
                'verified':json.loads(r[0])['verified'], 'created':json.loads(r[0])['created'], 'synced':r[1] is not None} for r in recent]}
