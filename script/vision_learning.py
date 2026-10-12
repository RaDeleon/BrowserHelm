"""Opt-in live repeated visual tasks with a private temporary learning database.

Uses real Ollama inference and BrowserOS Neo on its own local canvas fixture.
--remote syncs one validation-tagged outcome to the existing OpenViking collection.
No provider keys, saved app settings, screenshots or coordinates are uploaded.
"""
import argparse
import functools
import http.server
import json
import pathlib
import sys
import tempfile
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'neo-personal'))
from experience import ExperienceMemory
from browserhelm import BrowserHelmGateway
from vision import DEFAULT_VISION
from version import VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=pathlib.Path)
    parser.add_argument('--remote', action='store_true')
    args = parser.parse_args()
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    handler = functools.partial(QuietHandler, directory=str(ROOT / 'neo-personal/fixtures'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    with tempfile.TemporaryDirectory(prefix='browserhelm-visual-learning-') as tmp:
        root = pathlib.Path(tmp)
        gateway = BrowserHelmGateway({'vision': {**DEFAULT_VISION, 'enabled': True}}, root/'outputs')
        memory = ExperienceMemory({'enabled': True, 'validation': True}, root/'experiences.sqlite')
        gateway.memory = memory
        counter = 0
        def request(method, params):
            nonlocal counter
            counter += 1
            response = gateway.handle({'jsonrpc': '2.0', 'id': counter, 'method': method, 'params': params})
            if response.get('error') or response.get('result', {}).get('isError'):
                raise RuntimeError('Visual validation request failed: '+json.dumps(response))
            return response['result']
        def visual(instruction, needle, action='click'):
            started = time.monotonic()
            result = request('tools/call', {'name': 'browserhelm_visual_act', 'arguments': {
                'page': page, 'instruction': instruction, 'action': action, 'successText': needle}})
            assert all(block.get('type') != 'image' for block in result['content'])
            text = result['content'][0]['text']
            report = json.loads(text.replace('[UNTRUSTED_NEO_OUTPUT]\n', '', 1).rsplit('\n[END_UNTRUSTED_NEO_OUTPUT]', 1)[0])
            report.update(totalSeconds=round(time.monotonic()-started, 3), clientResponseBytes=len(json.dumps(result).encode()))
            return report
        def reset():
            # Keep the test's pre-action outcome area empty. Mutable status text
            # can alternate compositor antialiasing and correctly miss the exact-
            # scene cache; those earlier trials are retained in run observations.
            gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(async()=>{document.querySelector("#outcome").textContent="";await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));return true;})).value;' % page)
        try:
            initialized = request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                'clientInfo': {'name': 'BrowserHelm visual learning validation', 'version': VERSION}})
            request('tools/list', {})
            request('tools/call', {'name': 'name_session', 'arguments': {'name': 'Vision learning', 'category': 'testing-and-qa',
                'summary': 'Three canvas targets, repeated verified runs, moved controls and memory persistence.'}})
            url = 'http://127.0.0.1:%s/vision-targets.html' % server.server_port
            page = gateway.run_browser('const p=await browser.open(%s);await p.waitForText("Waiting for a selection");return p.id;' % json.dumps(url))
            tasks = [('triangle', 'The green tile containing the white triangle', 'Vision test complete'),
                     ('circle', 'The blue tile containing the white circle', 'Circle selected'),
                     ('square', 'The white square in the rightmost brown tile', 'Square selected')]
            runs = []
            for label, instruction, needle in tasks:
                attempts = []
                for attempt in range(3):
                    reset()
                    if attempt == 2:
                        # Reopen the database, not just an in-process cache.
                        memory = ExperienceMemory({'enabled': True, 'validation': True}, memory.path, memory.config_path)
                        gateway.memory = memory
                    report = visual(instruction, needle)
                    attempts.append(report)
                runs.append({'target': label, 'attempts': attempts,
                    'passed': all(row.get('verified') for row in attempts) and
                    [row.get('groundingSource') for row in attempts] == ['model', 'model', 'verified_local_memory']})
            # Move the triangle in canvas pixels without changing the DOM target/layout.
            reset()
            gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(async()=>{window.drawTiles(560);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));return true;})).value;' % page)
            moved = visual(tasks[0][1], tasks[0][2])
            already = visual(tasks[0][1], tasks[0][2])
            gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(()=>{window.drawTiles(310);window.failVerification=true;return true;})).value;' % page)
            reset()
            failed = visual(tasks[0][1], tasks[0][2])
            gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(()=>{window.failVerification=false;return true;})).value;' % page)
            recovery = []
            for _ in range(3):
                reset(); recovery.append(visual(tasks[0][1], tasks[0][2]))
            remote = {'tested': False}
            if args.remote:
                # Upload only one marked test outcome; never seed production local reuse.
                with memory.db() as db:
                    record = db.execute('SELECT id,document FROM experiences ORDER BY created DESC LIMIT 1').fetchone()
                    db.execute('DELETE FROM experiences WHERE id<>?', (record[0],))
                memory.test(); sync = memory.sync(limit=1)
                raw = memory.request('/api/v1/content/read?'+urllib.parse.urlencode({'uri': memory.root+'/'+record[0]+'.md'}))
                if isinstance(raw, dict): raw = raw.get('content', '')
                remote = {'tested': True, 'uploaded': sync['uploaded'], 'readbackMatches': json.loads(raw)==json.loads(record[1]),
                          'markedValidation': json.loads(raw)['test'] is True}
            value = {'app': initialized['serverInfo'], 'tasks': runs, 'movedTarget': moved, 'alreadySatisfied': already,
                'injectedFailure': failed, 'recovery': recovery,
                'memoryCounters': {k: memory.snapshot()[k] for k in ('visual_attempts', 'visual_verified', 'visual_calls_avoided', 'visual_reuse_verified')},
                'openViking': remote, 'passed': all(row['passed'] for row in runs) and moved.get('verified') is True and
                    moved.get('groundingSource')=='model' and already.get('status')=='already_satisfied' and
                    failed.get('clicked') is True and failed.get('verified') is False and
                    failed.get('groundingSource')=='verified_local_memory' and
                    [row.get('groundingSource') for row in recovery]==['model','model','verified_local_memory'] and
                    all(row.get('verified') for row in recovery) and
                    (not args.remote or remote['readbackMatches'] and remote['markedValidation']),
                'limits': 'Controlled three-target canvas, same screen reuse only, not a general accuracy/speed or Claude quota benchmark. Model weights are unchanged.'}
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(value, indent=2)+'\n')
            print(json.dumps(value, indent=2))
            if not value['passed']: raise SystemExit(1)
        finally:
            memory.close(); gateway.moves_pool.shutdown(); gateway.artifacts.cleanup()
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
