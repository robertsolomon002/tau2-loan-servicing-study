# Main-run progress

Updated 2026-10-08 23:13 (written by `scripts/run_matrix.py`; results in `results/raw/main/`).

## Spend

| Account | Before the runs | Metered here | Total | Stop at |
|---|---|---|---|---|
| cash | $11.06 | $8.16 | **$19.22** | $45.00 |
| openrouter | $0.00 | $0.82 | **$0.82** | $6.50 |
| vertex | $0.30 | $43.78 | **$44.08** | $90.00 |

## Cells

| Cell | Done / planned | Model failures | Missing | Pending | Pass^1 so far | Failed attempts* | Spend / budget | Status |
|---|---|---|---|---|---|---|---|---|
| qwen_C1 | 95 / 192 | 0 | 0 | 97 | 0.97 | 1 / 96 (1%) | $0.294 / $0.92 | stopped: NotFoundError: litellm.NotFoundError: NotFoundError: OpenrouterException - {"error":{"message":"This model is unavailable for free. The paid version is available now - use this slug instead:  |
| qwen_C2 | 95 / 192 | 3 | 0 | 97 | 0.94 | 1 / 96 (1%) | $0.291 / $0.92 | stopped: NotFoundError: litellm.NotFoundError: NotFoundError: OpenrouterException - {"error":{"message":"This model is unavailable for free. The paid version is available now - use this slug instead:  |
| qwen_C3 | 95 / 192 | 1 | 0 | 97 | 0.96 | 1 / 96 (1%) | $0.300 / $0.92 | stopped: NotFoundError: litellm.NotFoundError: NotFoundError: OpenrouterException - {"error":{"message":"This model is unavailable for free. The paid version is available now - use this slug instead:  |
| nemotron_C1 | 192 / 192 | 1 | 0 | 0 | 0.98 | 0 / 192 (0%) | $0.647 / $0.92 | complete |
| nemotron_C2 | 192 / 192 | 1 | 0 | 0 | 0.95 | 0 / 192 (0%) | $0.654 / $0.92 | complete |
| nemotron_C3 | 192 / 192 | 0 | 0 | 0 | 0.98 | 0 / 192 (0%) | $0.654 / $0.92 | complete |
| deepseek_C1 | 192 / 192 | 0 | 0 | 0 | 0.98 | 0 / 192 (0%) | $0.861 / $1.75 | complete |
| deepseek_C2 | 192 / 192 | 0 | 0 | 0 | 0.96 | 0 / 192 (0%) | $0.908 / $1.75 | complete |
| deepseek_C3 | 192 / 192 | 0 | 0 | 0 | 0.96 | 0 / 192 (0%) | $0.939 / $1.75 | complete |
| flash_lite_C1 | 192 / 192 | 0 | 0 | 0 | 0.92 | 0 / 192 (0%) | $1.226 / $3.57 | complete |
| flash_lite_C2 | 192 / 192 | 0 | 0 | 0 | 0.90 | 0 / 192 (0%) | $1.271 / $3.57 | complete |
| flash_lite_C3 | 192 / 192 | 0 | 0 | 0 | 0.84 | 0 / 192 (0%) | $1.050 / $3.57 | complete |
| gemini_pro_C1 | 192 / 192 | 0 | 0 | 0 | 0.93 | 0 / 192 (0%) | $15.805 / $27.71 | complete |
| gemini_pro_C2 | 192 / 192 | 0 | 0 | 0 | 0.94 | 0 / 192 (0%) | $15.628 / $27.71 | complete |
| gemini_pro_C3 | 192 / 192 | 0 | 0 | 0 | 0.92 | 0 / 192 (0%) | $12.242 / $27.71 | complete |

**Overall:** 2589 / 2880 conversations finished.

\*Attempts that ended with a provider error, a user-simulator crash or a runner error. Those conversations are rerun, up to 6 attempts, then counted as missing.

## Models

| Model | Status |
|---|---|
| qwen | stopped: NotFoundError: litellm.NotFoundError: NotFoundError: OpenrouterException - {"error":{"message":"This model is unavailable for free. The paid version is available now - use this slug instead:  |
| nemotron | complete |
| deepseek | complete |
| flash_lite | complete |
| gemini_pro | complete |

## Request limits (rolling 24 hours)

| Provider | Requests | Per-day limit |
|---|---|---|
| openrouter_free | 944 | 950 |
| gemini_studio | 0 | 450 |

## Alerts

None.
