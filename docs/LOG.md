# Log

One line per substage.

- 2026-09-26 · 0.1 (partial): cloned fork to `../tau2-bench`, branch `domain/loan_servicing/initial` at `b7ea907` (v1.0.1); `uv sync --extra dev` ok. Upstream bug: `import tau2` needs `websockets`, which is only in the `voice` extra (worked around with `uv pip install websockets` in the fork venv and an explicit dependency here). `make`/`gh` not installed on this machine, so Makefile commands were run directly. `make test` equivalent: 234 passed, 1 xfailed, 17 failed (all are live-API tests hardcoded to `gpt-3.5-turbo` that fail with no `OPENAI_API_KEY`). `ruff check` and `ruff format --check`: clean. Study repo scaffolded with tau2 pinned by git commit. **Pending:** airline smoke test with free models (needs Stage 0.2 keys).
- 2026-09-26 · 0.1 (partial): moved both repos into the workspace folder `C:/Users/rober/code/tau-loan` and rebuilt both venvs there.
- 2026-09-28 · 0.1 (done): airline smoke test, `--num-tasks 2 --num-trials 1 --max-concurrency 1`, fork at `b7ea907`. Prices checked 2026-09-28 in provider docs (OpenAI gpt-5.4-nano $0.20/$1.25 per 1M in/out, gpt-5.4-mini $0.75/$4.50; Gemini Flash and Flash-Lite free tier "free of charge"). All 4 keys verified. Raw results in `results/raw/stage0_smoke/` (git-ignored). Total spend about $0.03 (OpenAI only; OpenRouter $0, 72 of 1,000 free daily requests used).

  | Agent (LiteLLM string) | Result | Agent calls / input tokens per conv | Cost per conv |
  |---|---|---|---|
  | `openrouter/qwen/qwen3.8-27b:free` | 2/2 solved | 6-11 / 34k-74k | $0 agent + ~$0.001 user |
  | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | 1/2 solved | 26-32 / 230k-290k | $0 agent + ~$0.003-0.007 user |
  | `gpt-5.4-mini` (paid, direct) | 1/2 solved | 6-9 / 23k-45k | ~$0.007-0.010 agent + ~$0.001 user (prompt caching applied) |
  | `gemini/gemini-3.1-flash-lite` (free, direct) | 1/1 solved, 1 infra error | 5 / 26k | $0 (LiteLLM reports paid price, about $0.008; ignore on free tier) |
  | `openrouter/google/gemma-4-31b-it:free` | 0/2, both infra errors | - | upstream 429: shared free pool busy at Google AI Studio |
  | `cerebras/gpt-oss-120b` | 0/2, both infra errors | - | tool-calling format rejected (see below) |

  User simulator for all rows: `gpt-5.4-nano` (paid, about $0.001-0.007 per conversation). Findings:
  - **Gemini free tier is rate-limited per model:** `gemini-3.8-flash` allows 5 requests/min (conversations failed as infra errors), a burst probe gave about 10/min for `gemini-3.1-flash-lite`, 5 for `gemini-3.5-flash-lite`, 0 for `gemini-2.5-flash-lite`. Too slow as user simulator or agent at concurrency above 1 without retry pacing; revisit in 3.3 and 4.1 (the paid Gemini tier is an option).
  - **Cerebras incompatibility:** Cerebras rejects `messages.N.assistant.tool_calls.0.name` because tau2 adds a non-standard top-level `name` to each tool call in `to_litellm_messages` (`src/tau2/utils/llm_utils.py:182`). Needs a small fix or a route through OpenRouter before Cerebras models can be used. Cerebras free trial is also tight: 5 requests/min, 1M tokens/day, $5 credits that expire after 30 days.
  - **Token use varies a lot by model:** Nemotron used about 8x the calls and tokens of Qwen and gpt-5.4-mini on the same tasks. Budget estimates in Stage 4.1 must be per model.
  - **Paid agent is cheaper than feared:** gpt-5.4-mini costs about $0.01 per airline conversation thanks to automatic prompt caching; 480 conversations would be about $5.
  - **Windows gotcha:** `tau2 run` crashes printing its header on the cp1252 console (`UnicodeEncodeError`). Set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before running.
- 2026-09-28 · 0.3 (done): read the fork's source at `b7ea907` and wrote `docs/TAU2_NOTES.md`. Main findings: free text written to the DB breaks the hash-based DB check, so write tools must store only structured values; `transfer_to_human_agents` is non-mutating in airline, so transfer tasks need a structured transfer record or an env assertion; splits live in one `split_tasks.json`; COMMUNICATE strips commas and is case-insensitive substring matching; "no change" tasks need `actions: []`; write tools must be deterministic for strict replay; the study repo must set `TAU2_DATA_DIR`. Fixed the affected ROADMAP lines (Section 2 note, 4.1 case note, 2.1 and 3.2 split files) and updated `docs/UPSTREAM_ISSUE.md` (telecom-style `loan_servicing_fr`, `split_tasks.json`, base-split question).
- 2026-09-28 · 0.2 (done): keys for OpenRouter, Cerebras, Gemini and OpenAI in both `.env` files; Hugging Face account created; upstream issue posted as https://github.com/sierra-research/tau2-bench/issues/579.
