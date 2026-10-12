"""Names of local/generated artifacts, shared by commit and packaging checks."""
import fnmatch
import pathlib

LOCAL_DIRECTORIES = {
    'logs', 'debug-logs', 'debug-output', 'outputs', 'artifacts', 'test-results',
    'test-output', 'test-artifacts', 'playwright-report', 'blob-report', 'coverage',
    'htmlcov', 'screenshots', 'recordings', 'traces', '.audit', '.audit-output',
    '.local', 'local-data', 'data', 'node_modules', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', '.tox', '.tools', '.claude', '.codex', '.openviking',
    '.browserhelm', '.openragnar', 'agents-output',
}
LOCAL_PATTERNS = (
    '*.log', '*.log.*', '*.jsonl', '*.ndjson', '*.har', '*.trace', '*.crash', '*.ips',
    '*.core', '*.db', '*.db-*', '*.sqlite', '*.sqlite-*', '*.sqlite3', '*.sqlite3-*',
    '*.bak', '*.backup', '*.orig', '*.profraw', '*.profdata', '*.gcda', '*.gcno',
    '*.xcresult', '*.dSYM', '*.gitleaks.json', '.coverage', '.coverage.*',
    'screenshot*.png', 'screenshot*.jpg', 'Screenshot *.png',
)
PRIVATE_NAMES = {'settings.json', 'ovcli.conf', 'ov.conf'}
BENCHMARK_OUTPUT_NAMES = {
    'preflight.json', 'results.json', 'results.csv', 'progress.json',
    'comparison.json', 'usage.json', 'provenance.json', 'metrics.json',
}


def is_private_artifact(path):
    path = pathlib.PurePosixPath(str(path))
    if any(part in LOCAL_DIRECTORIES for part in path.parts):
        return True
    if any(fnmatch.fnmatchcase(part, pattern) for part in path.parts for pattern in LOCAL_PATTERNS):
        return True
    if path.parts and (path.parts[0] in ('design', 'tmp', 'temp') or
                       path.as_posix() == 'docs/backlog.md'):
        return True
    name = path.name
    if len(path.parts) == 1 and name in BENCHMARK_OUTPUT_NAMES | {'diagnostics.json'}:
        return True
    return (name in PRIVATE_NAMES or
            ((name == '.env' or name.startswith('.env.')) and name != '.env.example') or
            path.suffix in ('.pem', '.key', '.p12', '.pfx') or
            ('benchmarks' in path.parts and name in BENCHMARK_OUTPUT_NAMES))
