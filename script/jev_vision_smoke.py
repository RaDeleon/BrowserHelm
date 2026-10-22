"""Opt-in paid vision-provider smoke check on an owned Neo canvas fixture.

Reads only the selected provider key through the installed app's native helper.
Default: Jev. Use --provider openrouter to compare DeepSeek on the same cases.
Never saves settings, changes existing tabs, or touches production experience memory.
One click is permitted only in this fixture. All failures are retained in the report.
"""
import argparse
import functools
import http.server
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'neo-personal'))
from browserhelm import BrowserHelmGateway
from vision import TYPESAFE_ENDPOINT, OPENROUTER_ENDPOINT, JEV_VISION_MODEL, VisionProvider, visual_act


def inside_shape(case, x, y):
    """Independent fixture geometry, including boundaries; no model evidence."""
    if case in ('triangle', 'click'):
        half_width = (y-120)*50/90
        return 120 <= y <= 210 and 400-half_width <= x <= 400+half_width
    if case == 'circle': return (x-150)**2 + (y-170)**2 <= 45**2
    if case == 'square': return 620 <= x <= 680 and 140 <= y <= 200
    raise ValueError('No white-shape oracle for this case.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=pathlib.Path, default=pathlib.Path('/Applications/BrowserHelm.app'))
    parser.add_argument('--report', type=pathlib.Path, required=True)
    parser.add_argument('--provider', choices=['typesafe', 'openrouter'], default='typesafe')
    parser.add_argument('--model', choices=['deepseek/deepseek-v4.1-flash', 'qwen/qwen3.8-flash', 'bytedance/ui-tars-1.5-7b'],
                        default='deepseek/deepseek-v4.1-flash', help='Model for the OpenRouter provider.')
    parser.add_argument('--shape-targets', action='store_true', help='Use precise white-shape descriptions instead of whole-tile descriptions.')
    parser.add_argument('--cases', nargs='+', choices=['triangle','circle','square','absent','ambiguous','click'],
                        help='Optional diagnostic subset; default runs all six cases.')
    parser.add_argument('--diagnostics', action='store_true', help='Retain synthetic-fixture output text and usage for failed-response diagnosis.')
    args = parser.parse_args()
    # Capture private IPC; never echo the key or the helper's stdout/stderr.
    helper = args.app / 'Contents/MacOS/BrowserHelm'
    result = subprocess.run([str(helper), '--provider-key', args.provider], capture_output=True, timeout=30)
    if result.returncode or not result.stdout:
        raise SystemExit('Selected provider key unavailable through the installed app. Save it in BrowserHelm Settings first.')
    key = result.stdout.decode('utf-8')
    config = {'enabled': True, 'provider': 'typesafe', 'endpoint': TYPESAFE_ENDPOINT,
              'model': JEV_VISION_MODEL, 'minConfidence': 0.9}
    if args.provider == 'openrouter':
        config = {'enabled': True, 'provider': 'openrouter', 'endpoint': OPENROUTER_ENDPOINT,
                  'model': args.model}
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'neo-personal/fixtures'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    rows = []
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='browserhelm-jev-smoke-') as directory:
            gateway = BrowserHelmGateway({'vision': config}, directory)
            gateway.vision_api_key = key
            try:
                initialized = gateway.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                    'protocolVersion':'2025-11-25','capabilities':{},
                    'clientInfo':{'name':'BrowserHelm vision comparison','version':'1.0'}}})
                if initialized.get('error'): raise ValueError('Neo MCP initialization failed.')
                gateway.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'tabs','arguments':{'action':'list'}}})
                gateway.handle({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'name_session','arguments':{
                    'name':'Vision comparison','category':'testing-and-qa',
                    'summary':'Controlled image grounding, refusal and fixture click verification.'}}})
                url = 'http://127.0.0.1:%s/vision-targets.html' % server.server_port
                page = gateway.run_browser('const p=await browser.open(%s);await p.waitForText("Waiting for a selection");return p.id;' % json.dumps(url))
                bounds = gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(()=>{const r=document.querySelector("canvas").getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};})).value;' % page)
                cases = [('triangle', 'The green tile containing the white triangle', 310),
                         ('circle', 'The blue tile containing the white circle', 60),
                         ('square', 'The rightmost brown tile containing the white square', 560),
                         ('absent', 'The purple tile containing a white star', None),
                         ('ambiguous', 'A colored tile containing a white shape', None),
                         ('click', 'The green tile containing the white triangle', 310)]
                if args.shape_targets:
                    labels = {'triangle': 'The white triangle', 'circle': 'The white circle',
                              'square': 'The white square', 'click': 'The white triangle'}
                    cases = [(name, labels.get(name, instruction), left) for name, instruction, left in cases]
                if args.cases:
                    cases = [case for case in cases if case[0] in args.cases]
                for index, (name, instruction, left) in enumerate(cases):
                    before = time.monotonic()
                    row = {'case': name, 'target': instruction}
                    diagnostic = {}
                    original_request = VisionProvider.request
                    def capture_request(provider, path, *values, **options):
                        raw = original_request(provider, path, *values, **options)
                        if path == '/chat/completions':
                            choices = raw.get('choices', [])
                            first = choices[0] if choices else {}
                            message = first.get('message', {})
                            diagnostic.update(output=str(message.get('content', ''))[:4096],
                                              finishReason=first.get('finish_reason'), usage=raw.get('usage', {}))
                        return raw
                    try:
                        with patch.object(VisionProvider, 'request', capture_request if args.diagnostics else original_request):
                            report = visual_act(gateway, {'page':page,'instruction':instruction,
                            'action':'click' if name == 'click' else 'point',
                            **({'successText':'Vision test complete'} if name == 'click' else {})}, 10+index)
                        row['result'] = report
                        if left is None:
                            row['passed'] = report.get('found') is False and not report.get('clicked')
                        else:
                            x = (report['x'] - bounds['x'])*800/bounds['width']
                            y = (report['y'] - bounds['y'])*360/bounds['height']
                            row['insideExpectedTile'] = left <= x <= left+180 and 80 <= y <= 260
                            row['passed'] = bool(report.get('found') and row['insideExpectedTile'] and
                                                 (name != 'click' or report.get('verified')))
                            if args.shape_targets:
                                row['insideExpectedShape'] = bool(report.get('found') and inside_shape(name, x, y))
                                row['passed'] = row['passed'] and row['insideExpectedShape']
                    except (ValueError, RuntimeError, KeyError, TypeError) as error:
                        row.update(passed=False, error=str(error))
                    if args.diagnostics:
                        row['providerDiagnostic'] = diagnostic
                    row['elapsedSeconds'] = round(time.monotonic()-before, 3)
                    rows.append(row)
                    print(json.dumps({'case':name, 'passed':row['passed'], 'status':row.get('result',{}).get('status'),
                                      'error':row.get('error')}), file=sys.stderr, flush=True)
                # Independent rendered-text observation after the fixture click.
                outcome = gateway.run_browser('const p=await browser.page(%s);return (await p.evaluate(()=>document.querySelector("#outcome").textContent)).value;' % page)
                passed = all(row['passed'] for row in rows) and (not any(c['case']=='click' for c in rows) or outcome == 'Vision test complete')
            finally:
                gateway.moves_pool.shutdown(); gateway.artifacts.cleanup()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    usages = [row.get('result', {}).get('usage', {}) for row in rows]
    known_inputs = sum(u.get('input_tokens', u.get('prompt_tokens', 0)) for u in usages
                       if type(u.get('input_tokens', u.get('prompt_tokens'))) is int)
    reported_costs = [u['cost'] for u in usages if type(u.get('cost')) in (int, float)]
    value = {'provider':args.provider,'model':config['model'],'shapeTargets':args.shape_targets,'caseSubset':args.cases,'diagnostics':args.diagnostics,'minConfidence':config.get('minConfidence'),'passed':passed,'cases':rows,
             'independentOutcome':outcome,'oracleBounds':bounds,'oracleVersion':'fixture-shape-v2','elapsedSeconds':round(time.monotonic()-started,3),
             'knownInputTokens':known_inputs,'unknownUsageCases':sum('input_tokens' not in u and 'prompt_tokens' not in u for u in usages),
             'estimatedKnownInputCostUSD':known_inputs*0.042/1_000_000 if args.provider == 'typesafe' else None,
             'reportedKnownCostUSD':sum(reported_costs) if reported_costs else None,
             'unknownReportedCostCases':len(usages)-len(reported_costs),
             'costBasis':('Published $0.042/M input rate, free output; estimate, not measured bill.'
                          if args.provider == 'typesafe' else 'OpenRouter response usage.cost; missing costs remain unknown.'),
             'limits':'One fixture, six attempts. Provider adapters use their own acceptance rules; not a model-only ranking. No main-agent or total-task savings comparison.'}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value,indent=2))
    if not passed: raise SystemExit(1)


if __name__ == '__main__': main()
