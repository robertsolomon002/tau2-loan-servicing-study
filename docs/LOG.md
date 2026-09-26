# Log

One line per substage.

- 2026-09-26 · 0.1 (partial): cloned fork to `../tau2-bench`, branch `domain/loan_servicing/initial` at `b7ea907` (v1.0.1); `uv sync --extra dev` ok. Upstream bug: `import tau2` needs `websockets`, which is only in the `voice` extra (worked around with `uv pip install websockets` in the fork venv and an explicit dependency here). `make`/`gh` not installed on this machine, so Makefile commands were run directly. `make test` equivalent: 234 passed, 1 xfailed, 17 failed (all are live-API tests hardcoded to `gpt-3.5-turbo` that fail with no `OPENAI_API_KEY`). `ruff check` and `ruff format --check`: clean. Study repo scaffolded with tau2 pinned by git commit. **Pending:** airline smoke test with free models (needs Stage 0.2 keys).
- 2026-09-26 · 0.1 (partial): moved both repos into the workspace folder `C:/Users/rober/code/tau-loan` and rebuilt both venvs there.
