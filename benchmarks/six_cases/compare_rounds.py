"""Compare separately retained one-pass pilots without changing either baseline."""
import argparse,hashlib,json,pathlib
from scenarios import CASES

ROOT=pathlib.Path(__file__).resolve().parents[2]

def index(rows):
    result={}
    for r in rows:
        key=(r['case'],r['mode'])
        if key in result:raise ValueError('One sample per case/mode required; do not collapse repeats')
        result[key]=r
    return result

def totals(rows):
    result={}
    for mode in ('neo','off','on'):
        group=[r for r in rows if r['mode']==mode]
        result[mode]={'attempts':len(group),'verified':sum(r['verified'] for r in group),
                      'summedElapsedSeconds':round(sum(r['elapsedSeconds'] for r in group),3),
                      'mainAgentTurns':None if any(r.get('mainAgentTurns') is None for r in group) else sum(r['mainAgentTurns'] for r in group),
                      'toolCalls':sum(r['mainAgentToolCalls'] for r in group),
                      'taskMarkerCalls':sum(sum('browserhelm_task' in t for t in r['toolNames']) for r in group),
                      'toolErrors':sum(r['transportErrors'] for r in group),
                      'knownApiEquivalentUSD':sum(r.get('apiEquivalentUSD') or 0 for r in group),
                      'unknownCostAttempts':sum(r.get('apiEquivalentUSD') is None for r in group),
                      'providerCalls':sum(len(r.get('providerUsage',[])) for r in group),
                      'totalTaskCostUSD':None}
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=pathlib.Path,required=True)
    ap.add_argument('--bundles',type=pathlib.Path,nargs='+',required=True);ap.add_argument('--output',type=pathlib.Path,required=True)
    args=ap.parse_args();baseline=json.loads(args.baseline.read_text());old=index(baseline['runs'])
    bundles=[json.loads(p.read_text()) for p in args.bundles];rows=[r for b in bundles for r in b['runs']];new=index(rows)
    expected={(c['id'],m) for c in CASES for m in ('neo','off','on')}
    missing=sorted(expected-set(new));versions=sorted({b['engineVersion'] for b in bundles})
    model_mismatch=[{'case':r['case'],'mode':r['mode'],'actual':r.get('actualModel')} for r in rows if r.get('actualModel')!='claude-opus-5-5']
    summary={'engineVersions':versions,'model':'claude-opus-5-5','effort':'high','runs':rows,'byMode':totals(rows),
             'baselineByMode':totals(baseline['runs']),'missingArms':missing,'modelMismatches':model_mismatch,
             'knownApiEquivalentUSD':sum(r.get('apiEquivalentUSD') or 0 for r in rows),
             'totalTaskCostUSD':None,'subscriptionAllowanceImpact':None,
             'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.baseline,*args.bundles]}}
    lines=['# Six-case optimization retest — BrowserHelm '+', '.join(versions),'',
           f"**{sum(r['verified'] for r in rows)}/{len(rows)} independently verified attempts.** One attempt per case/mode; no additional repeats.",'',
           'Same Opus 5.5 High model, Claude Code 2.1.296, Neo backend and task-specific tool exposure as the original pilot. Isolated fixtures/settings, local Ollama Qwen3-VL 2B for delegated vision, Jev for inferred navigation. Production memory and provider choices are preserved. The runner captures actual versions. Task markers default off in the optimized app.','',
           '| Case | Neo now | Ragnar off now | Ragnar on now | Ragnar on before |',
           '| --- | ---: | ---: | ---: | ---: |']
    for c in CASES:
        vals=[]
        for m in ('neo','off','on'):
            r=new.get((c['id'],m));vals.append(f"{r['elapsedSeconds']:.2f}s ({'pass' if r['verified'] else 'fail'})" if r else 'Pending')
        b=old.get((c['id'],'on'));vals.append(f"{b['elapsedSeconds']:.2f}s" if b else 'Unknown')
        lines.append('| '+c['name']+' | '+' | '.join(vals)+' |')
    lines+=['','## Observed totals','','Summed times describe these six different tasks; they are not a latency distribution for a repeated workload. All attempts, including failures and recovery, remain included.','',
            '| Mode | Verified | Sum of task times | Turns | Tool calls | Marker calls | Tool errors | Main-agent API-equivalent |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for mode,s in summary['byMode'].items():
        lines.append(f"| {mode} | {s['verified']}/{s['attempts']} | {s['summedElapsedSeconds']:.2f}s | {s['mainAgentTurns']} | {s['toolCalls']} | {s['taskMarkerCalls']} | {s['toolErrors']} | ${s['knownApiEquivalentUSD']:.6f}"+(' + unknown' if s['unknownCostAttempts'] else '')+' |')
    lines+=['',f"Known main-agent list-price API-equivalent: **${summary['knownApiEquivalentUSD']:.6f}**. This is client-reported usage priced by Claude, not a Max subscription charge or measured allowance reduction. Provider-reported usage is retained separately. Missing provider/memory/compute costs are unknown; complete task cost and cost per successful task are not established.",'',
            '## Per-arm change from original pilot','','| Case / mode | Time before → now | Turns before → now | Tool errors before → now |','| --- | ---: | ---: | ---: |']
    for c in CASES:
        for mode in ('neo','off','on'):
            a=old.get((c['id'],mode));b=new.get((c['id'],mode))
            if a and b:lines.append(f"| {c['id']} / {mode} | {a['elapsedSeconds']:.2f} → {b['elapsedSeconds']:.2f}s | {a['mainAgentTurns']} → {b['mainAgentTurns']} | {a['transportErrors']} → {b['transportErrors']} |")
    failures=[r for r in rows if not r['verified']]
    lines+=['','## Mechanism findings','',
            'Agent marker calls fell from 12 to 0 in each Ragnar mode. The delegated public-navigation arm had zero argument/help errors (four previously); its planner turns fell from 11 to 5. All three recovery arms deliberately injected one tool error and independently recorded exactly one submission. There were no unintended tool errors in this pass.', '',
            'The public navigation-on task did not invoke Jev; its trace used the executor for reads and then direct tools/output recovery. The stable-plan arm invoked Jev once: 1,223 input and 197 output tokens, 0.132s latency. Local vision reported 1,180 prompt and 27 completion tokens, 1.887s latency. Provider fees are not reported.', '',
            'Ragnar off and on had almost identical summed time (53.05s vs 53.27s); off had lower main-agent API-equivalent cost ($0.399326 vs $0.431377). The result supports keeping delegation optional, not making it a universal default winner.', '',
            '## Failures and limits','']
    lines += [f"- {r['case']} / {r['mode']}: {r['reason']}" for r in failures] or ['No failed independent task checks in this pass.']
    lines+=['', 'The unverified direct-Neo navigation answer matched the expected URL, heading and explanation, but the independent checker returned publicVerified:false. The recorded browser evaluation reported location.href at /api while its content wrapper still labeled the origin /models. The checker prefiltered tab-list URLs, so stale SPA metadata is a plausible harness false negative. The raw attempt remains unverified; this is not evidence of a Ragnar accuracy advantage. Future verification now reads current location/DOM on owned tabs before testing the destination; no paid task was rerun or raw result rewritten. The replacement verifier passed an owned synthetic DOM/location check with zero model calls; evidence is `dist/benchmarks/pilot-0.4.12/future-verifier-validation.json`.']
    if missing:lines.append('Pending arms: '+repr(missing))
    lines+=['','This is a second one-pass pilot, not enough samples for stable median/tail latency, reliability rankings or broad speed claims. Browser/model caching, run order and provider/network variability remain confounds. Fresh Claude process/MCP startup and final independent verification are inside elapsed time; fixture preparation is outside it. The first acquisition case does not measure learned-repeat improvement. Cloud vision and remote OpenViking recall are outside this retest. No guaranteed improvement, subscription savings or 10× result follows from mechanism checks alone.','',
            'Raw JSONL, prompts, traces and provider SQLite records are retained in ignored `dist/benchmarks/pilot-0.4.12/`. The original pilot files were not overwritten. Stop for usage review before further paid tasks.']
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text('\n'.join(lines)+'\n')
    output=ROOT/'dist/benchmarks/pilot-0.4.12/comparison.json';output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'report':str(args.output),'comparison':str(output),'attempts':len(rows),'verified':sum(r['verified'] for r in rows),'knownApiEquivalentUSD':summary['knownApiEquivalentUSD'],'missingArms':missing}))

if __name__=='__main__':main()
