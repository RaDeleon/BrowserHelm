"""Bounded, private diagnostics. Persist classifications, never raw errors or payloads."""
import datetime
import functools
import hashlib
import json
import os
import pathlib
import plistlib
import re
import sqlite3
import subprocess
import sys
import time
import uuid

RETENTION_DAYS = 14
EVENT_LIMIT = 10000
DISPLAY_LIMIT = 500
CATEGORIES = {
    'ok': ('Request completed.', 'No action needed.'),
    'rpc_error': ('The upstream MCP server returned an error.', 'Check the MCP code and Neo connection. Inspect browser state before repeating a write.'),
    'protocol_mismatch': ('MCP protocol negotiation failed.', 'Reconnect the MCP client after its current task finishes. Check that both apps are up to date.'),
    'session_expired': ('The Neo transport session is missing or expired.', 'Reconnect the MCP client after its task finishes. Inspect browser state before repeating a write.'),
    'neo_unavailable': ('BrowserOS Neo could not be reached.', 'Start BrowserOS Neo and check its MCP endpoint in Settings. Reconnect the client if Neo restarted.'),
    'timeout': ('A connection or browser step timed out.', 'Inspect the browser before retrying. A timed-out write may already have completed.'),
    'browser_execution': ('Neo reported an unsuccessful browser execution.', 'Check the tab and the failed call in your client. Verify the SDK method and selector before retrying.'),
    'provider_error': ('The decision provider could not complete its request.', 'Check the provider endpoint, model, key access and credit. No automatic retry was made.'),
    'escalated': ('Delegated navigation returned control to the main agent.', 'Review the task result in your client. Uncertainty and exhausted budgets can cause an expected handoff.'),
    'invalid_request': ('The request failed validation.', 'Check the tool name and arguments against the advertised schema.'),
    'internal_error': ('The gateway encountered an internal exception.', 'Use the correlation ID and exception type to locate the request. Check the running app build.'),
    'telemetry_unavailable': ('Request counters could not be saved.', 'Check storage permissions and free space. The browser request was not repeated.'),
    'invalid_json': ('The MCP input was not valid JSON.', 'Reconnect the client and check its MCP transport.'),
    'request_limit': ('An MCP request exceeded the safety limit.', 'Send a smaller request. The oversized request was not forwarded.'),
    'startup_error': ('Gateway startup or configuration failed.', 'Check Settings and reinstall the app if its bundled runtime or engine is missing.'),
    'legacy_error': ('An older request was recorded as unsuccessful without error details.', 'Detailed reasons were not stored by that build. New connections through this build record diagnostics.'),
}


def safe_symbol(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:/-]{0,79}', value) else 'unknown'


def client_name(value):
    text = str(value).lower()
    if 'codex' in text: return 'Codex'
    if 'claude-code' in text or 'claude code' in text: return 'Claude Code'
    if 'claude' in text or 'local-agent-mode' in text: return 'Claude Desktop'
    if 'openragnar' in text: return 'OpenRagnar check'
    return 'Other MCP client'


def display_path(path):
    text = str(path)
    home = str(pathlib.Path.home())
    return '~' + text[len(home):] if text.startswith(home + '/') else text


@functools.lru_cache(maxsize=1)
def build_identity():
    engine = pathlib.Path(__file__).resolve().parent
    launcher = engine.parent.parent / 'MacOS/OpenRagnar'
    bundle = engine.parent.parent / 'Info.plist'
    version = 'source'
    digest = hashlib.sha256()
    try:
        if bundle.is_file():
            version = str(plistlib.loads(bundle.read_bytes()).get('CFBundleShortVersionString', 'unknown'))[:24]
        for file in sorted(engine.glob('*.py')):
            digest.update(file.name.encode()); digest.update(file.read_bytes())
        if launcher.is_file(): digest.update(launcher.read_bytes())
    except OSError:
        return {'version': version, 'build_id': 'unavailable', 'launcher_path': display_path(launcher if launcher.is_file() else engine)}
    return {'version': version, 'build_id': digest.hexdigest()[:16], 'launcher_path': display_path(launcher if launcher.is_file() else engine)}


def issue(category, code=None, http_status=None, exception=None):
    if category not in CATEGORIES: category = 'internal_error'
    summary, advice = CATEGORIES[category]
    return dict(category=category, summary=summary, advice=advice,
                code=code if type(code) is int else None,
                http_status=http_status if type(http_status) is int else None,
                exception_type=safe_symbol(type(exception).__name__) if exception is not None else None)


def classify_error(message='', code=None, http_status=None, exception=None, provider=False):
    # Classification examines the message transiently. No message or body is retained.
    text = str(message).lower()
    if provider and http_status is None:
        match = re.search(r'provider returned http (\d{3})\b', text)
        if match: http_status = int(match[1])
    if provider: category = 'provider_error'
    elif 'protocol' in text and ('mismatch' in text or 'does not match' in text): category = 'protocol_mismatch'
    elif http_status in (404, 410) or ('session' in text and any(x in text for x in ('expired', 'not found', 'invalid', 'missing'))): category = 'session_expired'
    elif isinstance(exception, TimeoutError) or 'timed out' in text or 'timeout' in text: category = 'timeout'
    elif exception is not None and type(exception).__name__ in ('URLError', 'ConnectionRefusedError', 'ConnectionError'): category = 'neo_unavailable'
    elif code in (-32600, -32602, -32601): category = 'invalid_request'
    elif code == -32603: category = 'internal_error'
    elif code is not None: category = 'rpc_error'
    elif exception is not None: category = 'internal_error'
    else: category = 'browser_execution'
    return issue(category, code, http_status, exception)


def browser_issue(result):
    details = issue('browser_execution')
    structured = result.get('structuredContent', {})
    error = structured.get('error') if isinstance(structured, dict) else None
    name = error.get('name') if isinstance(error, dict) else None
    if isinstance(error, str):
        name = error.split(':', 1)[0].strip()
    # JavaScript error classes are useful evidence; custom messages/stack frames
    # can contain browser contents and are deliberately omitted.
    if name in ('Error','TypeError','ReferenceError','SyntaxError','RangeError','TimeoutError','AbortError'):
        details['exception_type'] = name
        if name == 'TimeoutError':
            details = issue('timeout'); details['exception_type'] = name
    return details


class Diagnostics:
    def __init__(self, path, session_id=None):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        self.sid = session_id or uuid.uuid4().hex
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS connections (
              id TEXT PRIMARY KEY, client TEXT, started REAL, updated REAL, closed INTEGER,
              pid INTEGER, launcher_pid INTEGER, launcher_path TEXT, version TEXT, build_id TEXT, protocol TEXT);
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY, session_id TEXT, request_id TEXT, created REAL, source TEXT,
              severity TEXT, method TEXT, tool TEXT, category TEXT, summary TEXT, advice TEXT,
              code INTEGER, http_status INTEGER, exception_type TEXT, duration REAL,
              upstream_calls INTEGER, input_bytes INTEGER, client_bytes INTEGER);
            CREATE INDEX IF NOT EXISTS events_created ON events(created);
            ''')
            identity = build_identity()
            now = time.time()
            db.execute('INSERT INTO connections VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (self.sid, 'Connecting', now, now, 0, os.getpid(), os.getppid(),
                        identity['launcher_path'], identity['version'], identity['build_id'], 'not negotiated'))
            self.prune(db)
        os.chmod(self.path, 0o600)

    def db(self):
        db = sqlite3.connect(str(self.path), timeout=1)
        db.row_factory = sqlite3.Row
        return db

    def prune(self, db):
        cutoff = time.time() - RETENTION_DAYS * 86400
        db.execute('DELETE FROM events WHERE created < ?', (cutoff,))
        db.execute('DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY created DESC LIMIT -1 OFFSET ?)', (EVENT_LIMIT,))
        db.execute('DELETE FROM connections WHERE updated < ?', (cutoff,))
        db.execute('DELETE FROM connections WHERE id IN (SELECT id FROM connections ORDER BY updated DESC LIMIT -1 OFFSET 1000)')

    def identify(self, client, protocol):
        protocol = protocol if isinstance(protocol, str) and re.fullmatch(r'\d{4}-\d\d-\d\d', protocol) else 'unknown'
        with self.db() as db:
            db.execute('UPDATE connections SET client=?,protocol=?,updated=? WHERE id=?',
                       (client_name(client), protocol, time.time(), self.sid))

    def record(self, details, row=None, severity=None, source='gateway'):
        row = row or {}
        category = details.get('category', 'internal_error')
        normalized = issue(category, details.get('code'), details.get('http_status'))
        normalized['exception_type'] = safe_symbol(details['exception_type']) if details.get('exception_type') else None
        event = dict(id=uuid.uuid4().hex, session_id=self.sid, request_id=row.get('id'), created=time.time(), source=source,
                     severity=severity or ('info' if category == 'ok' else 'warning' if category == 'escalated' else 'error'),
                     method=safe_symbol(row.get('method')), tool=safe_symbol(row.get('tool')),
                     **normalized, duration=max(0, row.get('finished', 0) - row.get('started', 0)),
                     upstream_calls=row.get('upstream_calls', 0), input_bytes=row.get('input_bytes', 0), client_bytes=row.get('client_bytes', 0))
        # Safe stderr remains useful if SQLite is unavailable. No user error string is printed.
        print('OpenRagnar diagnostic ' + json.dumps(event, separators=(',', ':')), file=sys.stderr, flush=True)
        with self.db() as db:
            columns = list(event)
            db.execute('INSERT INTO events('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')', [event[k] for k in columns])
            db.execute('UPDATE connections SET updated=? WHERE id=?', (event['created'], self.sid))
            self.prune(db)
        return event['id']

    def close(self):
        with self.db() as db:
            db.execute('UPDATE connections SET closed=1,updated=? WHERE id=?', (time.time(), self.sid))


def alive(pid):
    try: os.kill(pid, 0); return True
    except OSError: return False


def historical_failures(path, known):
    if not path.is_file(): return []
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,session_id,method,tool,started,finished,status,upstream_calls,input_bytes,client_bytes FROM requests WHERE status != 'ok' ORDER BY started DESC LIMIT 500").fetchall()
    result = []
    for row in rows:
        r = dict(row)
        if r['id'] in known or r['started'] < time.time()-RETENTION_DAYS*86400: continue
        details = issue('escalated' if r['status'] == 'escalated' else 'legacy_error')
        result.append(dict(id='legacy-'+r['id'], request_id=r['id'], session_id=r['session_id'], created=r['started'],
                           source='legacy-counters', severity='warning' if r['status']=='escalated' else 'error',
                           method=safe_symbol(r['method']), tool=safe_symbol(r['tool']), **details,
                           duration=max(0,r['finished']-r['started']), upstream_calls=r['upstream_calls'],
                           input_bytes=r['input_bytes'], client_bytes=r['client_bytes']))
    return result


def claude_errors(path):
    """Project only error codes from a bounded log tail. Never return original log text."""
    if not path.is_file(): return []
    with path.open('rb') as file:
        file.seek(0, 2); file.seek(max(0, file.tell()-256*1024))
        lines = file.read(256*1024).decode('utf-8', errors='replace').splitlines()
    result = []
    for line in lines:
        stamp = re.match(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z) \[openragnar\]', line)
        if not stamp: continue
        match = re.search(r'Message from server: .*?error\(code=(-?\d+)\)', line)
        mismatch = '[error]' in line and 'MCP-Protocol-Version' in line and 'does not match' in line
        if not match and not mismatch: continue
        created = datetime.datetime.fromisoformat(stamp[1].replace('Z', '+00:00')).timestamp()
        if created < time.time()-RETENTION_DAYS*86400: continue
        details = issue('protocol_mismatch' if mismatch else 'rpc_error', int(match[1]) if match else None)
        result.append(dict(id='claude-'+hashlib.sha256(line.encode()).hexdigest()[:24], request_id=None, session_id=None,
                           created=created, source='claude-mcp-log', severity='error', method='tools/unknown', tool='unknown',
                           **details, duration=0, upstream_calls=0, input_bytes=0, client_bytes=0))
    return result[-200:]


def runtime_processes(connections, configured_launcher, command_runner=subprocess.run):
    # ps output is inspected locally and projected immediately; no unrelated argv is returned.
    command = command_runner(['/bin/ps','-axo','pid=,command='], capture_output=True, text=True, timeout=3, check=True)
    tracked = {c['launcher_pid']: c for c in connections if c['active']}
    result = []
    for line in command.stdout.splitlines():
        match = re.fullmatch(r'\s*(\d+) (/.+/OpenRagnar\.app/Contents/MacOS/OpenRagnar) --mcp\s*', line)
        if not match or not pathlib.Path(match[2]).is_file(): continue
        pid, path = int(match[1]), display_path(match[2])
        connection = tracked.get(pid)
        result.append(dict(pid=pid, launcher_path=path, tracked=connection is not None,
                           build_id=connection['build_id'] if connection else None,
                           matches_configured=path == configured_launcher if configured_launcher else None))
    return result


def diagnostic_snapshot(path, metrics_path=None, log_path=None, include_processes=True):
    path = pathlib.Path(path)
    events, connections, warnings, known = [], [], [], set()
    total = 0
    if path.is_file():
        try:
            with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=1) as db:
                db.row_factory = sqlite3.Row
                events = [dict(r) for r in db.execute('SELECT * FROM events ORDER BY created DESC LIMIT ?', (DISPLAY_LIMIT,))]
                total = db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
                known = {r[0] for r in db.execute('SELECT DISTINCT request_id FROM events WHERE request_id IS NOT NULL')}
                connections = [dict(r) for r in db.execute('SELECT * FROM connections ORDER BY started DESC LIMIT 100')]
        except sqlite3.Error: warnings.append('Diagnostics storage could not be read. Check permissions and free space.')
    for c in connections: c['active'] = not c['closed'] and alive(c['pid'])
    if metrics_path:
        try: events += historical_failures(pathlib.Path(metrics_path).resolve(), known)
        except (sqlite3.Error, OSError): warnings.append('Older request counters could not be read.')
    try:
        events += claude_errors(pathlib.Path(log_path) if log_path else pathlib.Path.home()/'Library/Logs/Claude/mcp-server-openragnar.log')
    except (OSError, ValueError): warnings.append('Claude MCP log could not be read.')
    events = sorted(events, key=lambda e:e['created'], reverse=True)[:DISPLAY_LIMIT]
    configured = None
    try:
        config = json.loads((pathlib.Path.home()/'Library/Application Support/Claude/claude_desktop_config.json').read_text())
        command = config.get('mcpServers', {}).get('openragnar', {}).get('command', '')
        if isinstance(command, str) and command.endswith('/OpenRagnar.app/Contents/MacOS/OpenRagnar'): configured = display_path(command)
    except (OSError, ValueError, AttributeError): pass
    processes = []
    if include_processes:
        try: processes = runtime_processes(connections, configured)
        except (OSError, subprocess.SubprocessError): warnings.append('Running-process inspection unavailable. Recorded connections remain visible.')
    if any(p['matches_configured'] is False for p in processes):
        warnings.append('A running MCP process uses a different path from Claude Desktop configuration. Finish active work, then restart Claude Desktop.')
    if any(not p['tracked'] for p in processes):
        warnings.append('Some running MCP processes predate diagnostics. Restart their client after active work finishes to record detailed errors and build identity.')
    return dict(current_build=build_identity(), configured_launcher=configured, connections=connections, processes=processes,
                events=events, error_count=sum(e['severity']=='error' for e in events), warning_count=sum(e['severity']=='warning' for e in events),
                stored_event_count=total, event_limit=EVENT_LIMIT, display_limit=DISPLAY_LIMIT, retention_days=RETENTION_DAYS,
                updated_at=time.time(), warnings=warnings,
                privacy='Metadata only: no keys, request arguments, page contents, raw errors or model reasoning. Paths abbreviate your home directory. Claude log import reads only codes from its last 256 KiB. Counts cover the displayed records; log and counter sources can describe the same failure.')
