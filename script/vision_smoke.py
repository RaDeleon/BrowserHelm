"""Opt-in local model/browser smoke test. Only clicks a dedicated test fixture.

Run: python3 script/vision_smoke.py [--report path]
Requires BrowserOS Neo and a downloaded qwen3-vl:2b-instruct served by local Ollama.
Does not read saved settings/keys, use cloud models, or change existing tabs.
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

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'neo-personal'))
from browserhelm import BrowserHelmGateway
from vision import DEFAULT_VISION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=pathlib.Path)
    args = parser.parse_args()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'neo-personal/fixtures'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    with tempfile.TemporaryDirectory(prefix='browserhelm-vision-smoke-') as directory:
        gateway = BrowserHelmGateway({'vision': {**DEFAULT_VISION, 'enabled': True}}, directory)
        counter = 0
        def request(method, params):
            nonlocal counter
            counter += 1
            result = gateway.handle({'jsonrpc': '2.0', 'id': counter, 'method': method, 'params': params})
            if result.get('error') or result.get('result', {}).get('isError'):
                raise RuntimeError('Smoke request failed: ' + json.dumps(result))
            return result['result']
        try:
            initialized = request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'BrowserHelm vision check', 'version': '1.0'}})
            catalog = request('tools/list', {})
            assert any(tool['name'] == 'browserhelm_visual_act' for tool in catalog['tools'])
            request('tools/call', {'name': 'tabs', 'arguments': {'action': 'list'}})
            request('tools/call', {'name': 'name_session', 'arguments': {'name': 'Local vision test', 'category': 'testing-and-qa', 'summary': 'Controlled canvas targeting and text verification with a local model.'}})
            url = 'http://127.0.0.1:%s/vision-targets.html' % server.server_port
            page = gateway.run_browser('const p=await browser.open(%s);await p.waitForText("Waiting for a selection");return p.id;' % json.dumps(url))
            reports = []
            for action in ('point', 'click'):
                started = time.monotonic()
                result = request('tools/call', {'name': 'browserhelm_visual_act', 'arguments': {'page': page, 'instruction': 'The green tile containing the white triangle', 'action': action, 'successText': 'Vision test complete'}})
                assert all(block.get('type') != 'image' for block in result['content'])
                text = result['content'][0]['text']
                report = json.loads(text.removeprefix('[UNTRUSTED_NEO_OUTPUT]\n').removesuffix('\n[END_UNTRUSTED_NEO_OUTPUT]'))
                report['clientResponseBytes'] = len(json.dumps(result).encode())
                report['totalSeconds'] = round(time.monotonic() - started, 3)
                reports.append(report)
            bounds = gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(()=>{const r=document.querySelector("canvas").getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};})).value;' % page)
            checks = []
            for instruction, left in [('The blue tile containing the white circle', 60), ('The white square in the rightmost brown tile', 560)]:
                result = request('tools/call', {'name': 'browserhelm_visual_act', 'arguments': {'page': page, 'instruction': instruction}})
                assert all(block.get('type') != 'image' for block in result['content'])
                text = result['content'][0]['text']
                point = json.loads(text.removeprefix('[UNTRUSTED_NEO_OUTPUT]\n').removesuffix('\n[END_UNTRUSTED_NEO_OUTPUT]'))
                local_x = (point['x'] - bounds['x']) * 800 / bounds['width']
                local_y = (point['y'] - bounds['y']) * 360 / bounds['height']
                checks.append({'target': instruction, 'insideExpectedTile': left <= local_x <= left + 180 and 80 <= local_y <= 260,
                               'found': point['found'], 'status': point['status'], 'x': point['x'], 'y': point['y'],
                               'inferenceSeconds': point['latencySeconds'], 'usage': point['usage']})
            value = {'app': initialized['serverInfo'], 'reports': reports,
                     'additionalTargets': checks,
                     'passed': reports[0]['status'] == 'point' and reports[1]['verified'] is True and all(check['insideExpectedTile'] for check in checks),
                     'limits': 'Controlled three-tile fixture; repeated green point/click may benefit from cache. No Claude quota, general GUI accuracy or 10x comparison measured.'}
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(value, indent=2) + '\n')
            print(json.dumps(value, indent=2))
            if not value['passed']: raise SystemExit(1)
        finally:
            gateway.moves_pool.shutdown()
            gateway.artifacts.cleanup()
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
