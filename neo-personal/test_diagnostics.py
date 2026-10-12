import concurrent.futures
import io
import json
import pathlib
import sqlite3
import tempfile
import time
import unittest
import urllib.error
from contextlib import redirect_stderr
from unittest.mock import patch
from types import SimpleNamespace

from diagnostics import Diagnostics, diagnostic_snapshot, claude_errors, classify_error, issue, runtime_processes, browser_issue
from gateway import Gateway
from metrics import Metrics
from browserhelm import BrowserHelmGateway


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.g = BrowserHelmGateway({}, self.root/'outputs')
        self.g.enable_metrics(self.root/'metrics.sqlite')
        self.g.enable_diagnostics(self.root/'diagnostics.sqlite')
        self.g.metrics.start('claude-desktop')
        self.request = {'jsonrpc':'2.0','id':7,'method':'tools/call','params':{'name':'run','arguments':{'code':'SECRET-PAGE-CONTENT'}}}

    def tearDown(self):
        self.g.moves_pool.shutdown(); self.g.artifacts.cleanup(); self.temp.cleanup()

    def snapshot(self):
        return diagnostic_snapshot(self.root/'diagnostics.sqlite', self.root/'metrics.sqlite', self.root/'missing.log', include_processes=False)

    def test_error_detail_correlates_without_storing_sensitive_message(self):
        response = {'jsonrpc':'2.0','id':7,'error':{'code':-32603,'message':'SECRET-KEY and user@example.com at https://example.com/?token=secret'}}
        with patch.object(Gateway,'upstream_call',return_value=response), redirect_stderr(io.StringIO()) as logs:
            actual = self.g.handle(self.request)
        data = self.snapshot()
        event = data['events'][0]
        row = self.g.metrics.snapshot()['requests'][0]
        self.assertEqual(event['request_id'],row['id'])
        self.assertEqual(actual['error']['data']['browserhelmRequestId'], row['id'])
        self.assertEqual(event['code'],-32603)
        self.assertEqual(data['error_count'],1)  # No duplicate legacy-counter event.
        persisted = (self.root/'diagnostics.sqlite').read_bytes() + logs.getvalue().encode() + json.dumps(data).encode()
        for secret in (b'SECRET-KEY', b'SECRET-PAGE-CONTENT', b'user@example.com', b'token=secret'):
            self.assertNotIn(secret, persisted)

    def test_structured_failure_survives_compaction_and_updates_status(self):
        response = {'jsonrpc':'2.0','id':7,'result':{'content':[{'type':'text','text':'x'*20000}], 'structuredContent':{'ok':False,'error':'SECRET-BROWSER-ERROR'},'isError':False}}
        with patch.object(Gateway,'upstream_call',return_value=response), redirect_stderr(io.StringIO()):
            result = self.g.handle(self.request)
        self.assertNotIn('structuredContent',result['result'])
        self.assertEqual(self.g.metrics.snapshot()['requests'][0]['status'],'error')
        self.assertEqual(self.snapshot()['events'][0]['category'],'browser_execution')

    def test_diagnostics_survive_missing_metrics(self):
        self.g.metrics = None
        with patch.object(Gateway,'upstream_call',side_effect=TimeoutError('SECRET-TIMEOUT')), redirect_stderr(io.StringIO()):
            self.g.handle(self.request)
        event = self.snapshot()['events'][0]
        self.assertEqual(event['category'],'timeout')
        self.assertEqual(event['upstream_calls'],1)

    def test_logging_failure_never_repeats_a_write(self):
        response = {'jsonrpc':'2.0','id':7,'result':{'content':[]}}
        with patch.object(Gateway,'upstream_call',return_value=response) as upstream, patch.object(self.g.diagnostics,'record',side_effect=OSError), redirect_stderr(io.StringIO()):
            result = self.g.handle(self.request)
        self.assertEqual(upstream.call_count,1)
        self.assertNotIn('error',result)
        self.assertEqual(self.g.metrics.snapshot()['requests'][0]['status'],'ok')

    def test_unexpected_worker_exception_gets_a_response_and_event(self):
        with patch.object(self.g,'_handle',side_effect=RuntimeError('SECRET-EXCEPTION')), redirect_stderr(io.StringIO()):
            response = self.g.handle(self.request)
        self.assertEqual(response['id'],7)
        self.assertEqual(response['error']['code'],-32603)
        self.assertEqual(self.snapshot()['events'][0]['exception_type'],'RuntimeError')

    def test_http_null_id_is_correlated_without_retry(self):
        body = io.BytesIO(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32603,'message':'Session not found'}}).encode())
        error = urllib.error.HTTPError('http://localhost/mcp',404,'missing',{},body)
        with patch.object(self.g.opener,'open',side_effect=error) as upstream, redirect_stderr(io.StringIO()):
            response = self.g.handle(self.request)
        self.assertEqual(response['id'],7)
        self.assertEqual(upstream.call_count,1)
        self.assertEqual(self.snapshot()['events'][0]['category'],'session_expired')
        self.assertEqual(self.snapshot()['events'][0]['http_status'],404)

    def test_bad_params_and_invalid_response_are_recorded(self):
        with redirect_stderr(io.StringIO()):
            invalid = self.g.handle({**self.request,'params':'SECRET-BAD-PARAMS'})
            with patch.object(self.g,'_handle',return_value=None): missing = self.g.handle(self.request)
        self.assertEqual(invalid['error']['code'],-32602)
        self.assertEqual(missing['error']['code'],-32603)
        self.assertEqual(self.snapshot()['error_count'],2)

    def test_connection_identity_and_readonly_snapshot_do_not_create_sessions(self):
        self.g.diagnostics.identify('local-agent-mode-browserhelm','2025-11-25')
        data = self.snapshot()
        self.assertEqual(data['connections'][0]['client'],'Claude Desktop')
        self.assertTrue(data['connections'][0]['active'])
        self.assertEqual(data['connections'][0]['protocol'],'2025-11-25')
        self.snapshot()
        self.assertEqual(len(self.snapshot()['connections']),1)
        self.g.diagnostics.close()
        self.assertFalse(self.snapshot()['connections'][0]['active'])
        self.assertEqual((self.root/'diagnostics.sqlite').stat().st_mode & 0o777,0o600)

    def test_bounded_concurrent_records_and_retention(self):
        recorder = self.g.diagnostics
        with redirect_stderr(io.StringIO()), patch('diagnostics.EVENT_LIMIT',20):
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda _:recorder.record(issue('ok')),range(42)))
        self.assertEqual(self.snapshot()['stored_event_count'],20)
        with recorder.db() as db: db.execute('UPDATE events SET created=?',(time.time()-15*86400,))
        with redirect_stderr(io.StringIO()): recorder.record(issue('ok'))
        self.assertEqual(self.snapshot()['stored_event_count'],1)

    def test_claude_log_projection_discards_raw_content(self):
        stamp = time.strftime('%Y-%m-%dT%H:%M:%S',time.gmtime())+'.123Z'
        path = self.root/'claude.log'
        path.write_text(stamp+' [browserhelm] [info] Message from server: id=9 error(code=-32603) SECRET-KEY\n'+stamp+' [browserhelm] [info] token=SECRET-KEY\n')
        events = claude_errors(path)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['code'],-32603)
        self.assertNotIn('SECRET-KEY',json.dumps(events))
        self.assertIsNone(events[0]['request_id'])

    def test_legacy_counter_failure_stays_unknown_and_no_db_is_created_on_read(self):
        path = self.root/'absent.sqlite'
        value = diagnostic_snapshot(path,log_path=self.root/'missing',include_processes=False)
        self.assertEqual(value['events'],[]);self.assertFalse(path.exists())
        row = dict(method='tools/call',tool='run',started=time.time(),finished=time.time(),status='error',input_bytes=1,upstream_input_bytes=1,upstream_bytes=0,client_bytes=0,upstream_text=0,client_text=0,upstream_calls=1,provider_tokens=0,provider_calls=0,provider_unknown=0,media_count=0)
        self.g.metrics.record(row)
        self.assertEqual(self.snapshot()['events'][0]['category'],'legacy_error')

    def test_process_projection_omits_unrelated_commands_and_marks_path_mismatch(self):
        launcher = self.root/'BrowserHelm.app/Contents/MacOS/BrowserHelm'
        launcher.parent.mkdir(parents=True);launcher.touch()
        fake = SimpleNamespace(stdout=f'  42 {launcher} --mcp\n  43 /bin/other --key SECRET-KEY\n')
        processes = runtime_processes([], '/Applications/BrowserHelm.app/Contents/MacOS/BrowserHelm',lambda *a,**kw:fake)
        self.assertEqual(len(processes),1);self.assertFalse(processes[0]['matches_configured'])
        self.assertFalse(processes[0]['tracked']);self.assertIsNone(processes[0]['build_id'])
        self.assertNotIn('SECRET-KEY',json.dumps(processes))

    def test_classification_never_keeps_raw_exception(self):
        self.assertEqual(classify_error('MCP-Protocol-Version does not match')['category'],'protocol_mismatch')
        self.assertEqual(classify_error('SECRET',exception=ValueError('secret'),provider=True)['category'],'provider_error')
        self.assertNotIn('secret',json.dumps(classify_error(exception=RuntimeError('secret'))))
        self.assertEqual(classify_error('Provider returned HTTP 429. SECRET',provider=True)['http_status'],429)

    def test_startup_failure_is_safe_and_diagnostics_still_readable(self):
        from browserhelm import main
        settings = self.root/'bad.json'
        settings.write_text('{SECRET-INVALID-JSON')
        argv = ['browserhelm','--settings',str(settings),'--output-dir',str(self.root/'outputs')]
        with patch('sys.argv',argv), redirect_stderr(io.StringIO()) as logs:
            with self.assertRaises(SystemExit): main()
        self.assertNotIn('SECRET-INVALID-JSON',logs.getvalue())
        self.assertEqual(self.snapshot()['events'][0]['category'],'startup_error')
        with patch('sys.argv',argv+['--diagnostics']), patch('sys.stdout',new=io.StringIO()) as output:
            main()
        self.assertTrue(json.loads(output.getvalue())['events'])

    def test_js_error_class_is_safe_and_upstream_error_data_preserved(self):
        details = browser_issue({'structuredContent':{'ok':False,'error':{'name':'TypeError','message':'SECRET-PAGE'}}})
        self.assertEqual(details['exception_type'],'TypeError')
        self.assertNotIn('SECRET-PAGE',json.dumps(details))
        self.assertIsNone(browser_issue({'structuredContent':{'error':{'name':'SECRET'}}})['exception_type'])
        response = {'jsonrpc':'2.0','id':7,'error':{'code':-32602,'message':'invalid','data':{'existing':'original guidance'}}}
        with patch.object(Gateway,'upstream_call',return_value=response), redirect_stderr(io.StringIO()):
            actual = self.g.handle(self.request)
        self.assertEqual(actual['error']['data']['existing'],'original guidance')
        self.assertEqual(actual['error']['data']['browserhelm']['category'],'invalid_request')


if __name__ == '__main__': unittest.main()
