# OpenRagnar gateway engine

Dependency-free Python 3.9+ implementation. The app bundles Python 3.12 and launches `launch.py` with isolated import handling. Start with the [project README](../README.md) and [setup guide](../README-OpenRagnar.md).

- `gateway.py`: MCP negotiation, JSON/SSE, compaction and private artifacts.
- `decision.py`: typed Jev choices and strict JSON-schema compatible providers.
- `openragnar.py`: delegation, local verification, metrics and native-app CLI.
- `experience.py`: OpenViking hints and a durable idempotent upload outbox.
- `metrics.py`: counters, local connector entries and Neo history/statistics.

Run tests from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s neo-personal -p 'test_*.py'
```

`install.py` retains legacy rollback helpers used by regression tests. Its direct CLI is disabled and it is not packaged. Use a separate `openragnar` connector through the native app or documented configuration.

Live scripts are opt-in. `live_openragnar.py` can contact a paid provider; `live_full_access.py` writes in an owned public test tab; `live_memory.py` saves an explicitly named validation route. See [benchmark instructions](../docs/benchmarks.md).
