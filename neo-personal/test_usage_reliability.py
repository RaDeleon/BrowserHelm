import concurrent.futures
import io
import json
import pathlib
import sqlite3
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch
from gateway import Gateway
from metrics import Metrics
from experience import ExperienceMemory
from sqlite_support import ClosingConnection


class Reply(io.BytesIO):
    def __init__(self, value, session=None, status=200):
        super().__init__(json.dumps(value).encode())
        self.headers = {'Content-Type': 'application/json'}
        if session: self.headers['Mcp-Session-Id'] = session
        self.status = status


class ReliabilityTests(unittest.TestCase):
    def test_expired_action_is_not_replayed_and_concurrent_followups_renew_once(self):
        with tempfile.TemporaryDirectory() as root:
            g = Gateway('http://localhost:9010/mcp', root)
            g.session = 'expired'
            g.initialize_params = {'protocolVersion': '2025-03-26', 'clientInfo': {'name': 'test'}}
            calls = []
            def send(req, timeout):
                body = json.loads(req.data); calls.append(body)
                if body['method'] == 'initialize':
                    self.assertIsNone(req.get_header('Mcp-session-id'))
                    return Reply({'result': {'protocolVersion': '2025-06-18'}}, 'fresh')
                if body['method'] == 'notifications/initialized':
                    self.assertEqual(req.get_header('Mcp-protocol-version'), '2025-06-18')
                    return Reply({}, status=202)
                if req.get_header('Mcp-session-id') == 'expired':
                    raise urllib.error.HTTPError(req.full_url, 404, 'expired', {},
                        io.BytesIO(b'{"error":{"code":-32000,"message":"session expired"}}'))
                return Reply({'result': {}})
            with patch.object(g.opener, 'open', side_effect=send):
                original = {'id': 1, 'method': 'tools/call', 'params': {'name': 'run', 'arguments': {'code': 'mutate()'}}}
                self.assertIn('error', g.upstream_call(original))
                self.assertEqual(len(calls), 1)
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(lambda i: g.upstream_call({'id': i, 'method': 'tools/list'}), range(2,6)))
            self.assertEqual(sum(c['method']=='initialize' for c in calls), 1)
            self.assertEqual(sum(c['method']=='notifications/initialized' for c in calls), 1)
            self.assertEqual(sum(c['method']=='tools/call' for c in calls), 1)
            self.assertEqual(g.protocol, '2025-06-18')

    def test_failed_renewal_never_dispatches_waiting_action(self):
        with tempfile.TemporaryDirectory() as root:
            g = Gateway('http://localhost:9010/mcp', root)
            g.session_expired = True; g.initialize_params = {'protocolVersion':'2025-03-26'}
            with patch.object(g.opener,'open',return_value=Reply({'error':{'code':-1}})) as send:
                with self.assertRaises(RuntimeError):
                    g.upstream_call({'id':1,'method':'tools/call','params':{'name':'act'}})
                self.assertEqual(send.call_count,1)
            self.assertTrue(g.session_expired)

    def test_failed_initialization_notification_does_not_dispatch_action(self):
        with tempfile.TemporaryDirectory() as root:
            g=Gateway('http://localhost:9010/mcp',root)
            g.session_expired=True;g.initialize_params={'protocolVersion':'2025-03-26'}
            error=urllib.error.HTTPError(g.upstream,404,'expired',{},io.BytesIO(b'{"error":{"code":-32000}}'))
            with patch.object(g.opener,'open',side_effect=[Reply({'result':{'protocolVersion':'2025-03-26'}},'fresh'),error]) as send:
                with self.assertRaises(RuntimeError):
                    g.upstream_call({'id':1,'method':'tools/call','params':{'name':'act'}})
                self.assertEqual(send.call_count,2)
            self.assertTrue(g.session_expired)

    def test_timeout_never_renews_or_replays(self):
        with tempfile.TemporaryDirectory() as root:
            g=Gateway('http://localhost:9010/mcp',root);g.session='current'
            with patch.object(g.opener,'open',side_effect=TimeoutError) as send:
                with self.assertRaises(TimeoutError): g.upstream_call({'id':1,'method':'tools/call'})
                self.assertEqual(send.call_count,1)
            self.assertFalse(g.session_expired)

    def test_coverage_separates_validation_and_marks_untracked_calls(self):
        with tempfile.TemporaryDirectory() as root:
            m=Metrics(pathlib.Path(root)/'metrics.sqlite');m.start('claude-ai')
            def record(tool):
                m.record(dict(tool=tool,method='tools/call',started=time.time(),finished=time.time(),status='ok'))
            for tool in ['run','browserhelm_execute','browserhelm_visual_act','browserhelm_status']:record(tool)
            validation=Metrics(m.path);validation.start('BrowserHelm validation');validation.record(dict(tool='run',method='tools/call',started=time.time(),finished=time.time(),status='ok'))
            # Start labels belong to sessions, so use a distinct instance for non-test calls.
            other=Metrics(m.path);other.start('codex');other.record(dict(tool='run',method='tools/call',started=time.time(),finished=time.time(),status='error'))
            c=m.snapshot()['coverage']
            self.assertEqual(c['tool_calls'],6);self.assertEqual(c['tracked_calls'],0)
            self.assertEqual(c['validation_calls'],1);self.assertEqual(c['paths'],{'direct':2,'delegated':1,'vision':1,'local':1})
            self.assertEqual(c['failed_calls'],1);self.assertEqual(c['provider_records'],0)

    def test_validation_tool_results_do_not_seed_production_failures(self):
        with tempfile.TemporaryDirectory() as root:
            m=ExperienceMemory({'enabled':True,'validation':True},pathlib.Path(root)/'memory.sqlite')
            with patch.object(m,'credentials',return_value=('http://localhost',{})):
                m.capture_tool('run',{},dict(id='test',finished=time.time(),status='error',diagnostic={'category':'session_expired'}))
                with m.db() as db:
                    self.assertEqual(db.execute('select count(*) from tool_history').fetchone()[0],0)
                    self.assertEqual(db.execute('select count(*) from experiences').fetchone()[0],1)
                    self.assertTrue(json.loads(db.execute('select document from experiences').fetchone()[0])['test'])
                m.capture('https://example.com','goal','needle',{'status':'complete','verified':True,'provider':'typesafe'},[])
                self.assertTrue(m.local_documents()[0]['test'])
            m.close()

    def test_connection_context_commits_rolls_back_and_closes(self):
        with tempfile.TemporaryDirectory() as root:
            path=str(pathlib.Path(root)/'db')
            with sqlite3.connect(path,factory=ClosingConnection) as db: db.execute('create table items (value)')
            with self.assertRaises(sqlite3.ProgrammingError): db.execute('select 1')
            with self.assertRaises(ValueError):
                with sqlite3.connect(path,factory=ClosingConnection) as db:
                    db.execute('insert into items values (1)');raise ValueError()
            with sqlite3.connect(path,factory=ClosingConnection) as db:
                self.assertEqual(db.execute('select count(*) from items').fetchone()[0],0)
