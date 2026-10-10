"""Scoped OpenViking browser experiences; no model-generated reflection or page dumps."""
import hashlib
import json
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
            ''')
        self.path.chmod(0o600)

    @property
    def enabled(self):
        try:
            return json.loads(self.settings_path.read_text()).get('memory',{}).get('enabled') is True
        except (OSError, ValueError):
            return self.initial_enabled

    def db(self):
        return sqlite3.connect(str(self.path), timeout=1)

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
        headers = {'Content-Type': 'application/json', 'User-Agent': 'openragnar/0.4.0'}
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

    def recall(self, start, goal, needle):
        if not self.enabled: return []
        documents = []
        deadline = time.monotonic()+3
        try:
            destination = self.destination()
            with self.db() as db: identity = dict(db.execute('SELECT key,value FROM memory_state').fetchall())
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
        except Exception:
            self.state('connection', 'Unavailable; using local experience cache')
        # Newly saved records can be used while semantic indexing is pending.
        with self.db() as db:
            rows = db.execute('SELECT document FROM experiences WHERE destination=? ORDER BY created DESC LIMIT 100', (self.destination(),)).fetchall()
        documents.extend(json.loads(r[0]) for r in rows)
        hints, seen = [], set()
        host = urllib.parse.urlsplit(start).netloc
        for d in documents:
            if not isinstance(d,dict) or d.get('schema') != 1 or d.get('source') != 'openragnar' or d.get('test'):
                continue
            if d.get('host') != host or d.get('successText') != clean(needle,200) or d.get('id') in seen:
                continue
            created = d.get('created',0)
            if type(created) not in (int,float) or not 0 <= time.time()-created <= 90*86400: continue
            routes = d.get('route', [])
            if not isinstance(routes,list): continue
            route = []
            for r in routes[:6]:
                if not isinstance(r,dict): continue
                try:
                    source,target = safe_url(r.get('from','')),safe_url(r.get('to',''))
                    if not source or not target or urllib.parse.urlsplit(source).netloc != host or urllib.parse.urlsplit(target).netloc != host: continue
                    route.append({'from':source,'to':target,'label':clean(r.get('label',''),80)})
                except ValueError: continue
            hint = {'outcome': 'successText found' if d.get('verified') is True else 'postcondition not verified',
                    'route': route, 'browserCalls': d.get('browserCalls',0) if type(d.get('browserCalls')) is int else 0}
            if not route: continue
            seen.add(d.get('id')); candidate = hints+[hint]
            if len(json.dumps(candidate).encode()) > MAX_HINT_BYTES: continue
            hints = candidate
            if len(hints) == 2: break
        self.state('last_recalled', len(hints))
        if hints:
            with self.db() as db:
                old = db.execute("SELECT value FROM memory_state WHERE key='tasks_with_recall'").fetchone()
                db.execute('INSERT OR REPLACE INTO memory_state VALUES (?,?)',('tasks_with_recall',str(int(old[0]) + 1 if old else 1)))
        return hints

    def capture(self, start, goal, needle, report, route, test=False):
        if not self.enabled or report.get('status') == 'proposal': return 'not saved'
        identifier = str(uuid.uuid4())
        document = {'schema':1, 'source':'openragnar', 'id':identifier, 'created':time.time(),
            'test':test, 'host':urllib.parse.urlsplit(start).netloc, 'start':safe_url(start),
            'goal':clean(goal), 'successText':clean(needle,200), 'verified':report.get('verified') is True,
            'verification':'literal successText presence only', 'status':report.get('status'),
            'provider':clean(report.get('provider',''),60), 'browserCalls':report.get('browserCalls',0),
            'model':clean((report.get('decisions') or [{}])[-1].get('model',''),100),
            'route':[{'from':safe_url(r['from']), 'to':safe_url(r['to']), 'label':clean(r['label'],80)} for r in route[:6]]}
        try:
            destination = self.destination()
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM experiences WHERE synced IS NOT NULL AND created < ?', (time.time()-90*86400,))
                if db.execute('SELECT COUNT(*) FROM experiences WHERE synced IS NULL').fetchone()[0] >= 500:
                    return 'queue full; outcome not stored'
                db.execute('INSERT INTO experiences (id,document,created,destination) VALUES (?,?,?,?)',
                    (identifier,json.dumps(document),document['created'],destination))
            return 'queued'
        except Exception:
            return 'memory storage unavailable; browser outcome unchanged'

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
        try: endpoint=self.credentials()[0]
        except Exception: endpoint='Existing OpenViking connection unavailable'
        return {'enabled':self.enabled, 'endpoint':endpoint, 'collection':self.root,
            'connection':state.get('connection','Not checked'), 'saved':count-pending, 'pending':pending,
            'tasks_with_recall':int(state.get('tasks_with_recall',0)), 'last_recalled':int(state.get('last_recalled',0)),
            'recent':[{'id':json.loads(r[0])['id'], 'goal':json.loads(r[0])['goal'],
                'verified':json.loads(r[0])['verified'], 'created':json.loads(r[0])['created'], 'synced':r[1] is not None} for r in recent]}
