# τ-Loan study (bilingual loan-servicing domain for τ²-bench)

- The full plan is `ROADMAP.md`. Read its Sections 1 to 10 before any work, do exactly one substage at a time, and tick it in Section 13.
- Two repos, side by side inside the workspace folder `C:/Users/rober/code/tau-loan`: the fork of sierra-research/tau2-bench at `../tau2-bench` (branch `domain/loan_servicing/initial`, upstream-quality domain code only) and this study repo `tau2-loan-servicing-study` (runner, analysis, report).
- Fork gotcha: `import tau2` needs `websockets` (only in the `voice` extra). In the fork, run `uv pip install websockets` after `uv sync`, and use `uv run --no-sync` so it isn't removed. `make` is not installed, so run the Makefile's commands directly.
- Windows gotcha: set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before `tau2 run`, or it crashes printing to the console.
- The study repo imports the fork by pinned commit (`pyproject.toml` `rev`). After pushing domain code to the fork, bump `rev` and run `uv sync`. Regenerate the DB with `uv run python scripts/generate_db.py` (writes the fork's `db.json` and `data/planted_cases.json`); look up task ids in `planted_cases.json`.
- Never guess tau2-bench internals: read the fork's source and `docs/TAU2_NOTES.md` (written in Stage 0.3).
- Budget: about $50 of API spend total, hard cap $60. Print projected cost before any run over 20 conversations. Prefer free models. Verify model ids and prices in provider docs; never assume them.
- `communicate_info` must be language-neutral (codes like `BF-12345` or whole numbers under 1000). EN and FR task variants must have identical evaluation criteria.
- All data and names are fictional (lender: Boréal Finance). Never commit API keys.
- Commit messages: `Stage X.Y: <summary>` (conventional commits in the fork).
