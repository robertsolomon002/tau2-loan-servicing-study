# Pilot 2: solvability of the harder tasks (Stage 2.3)

Date: 2026-09-28 to 2026-09-29. Task set: 48 English tasks, from the uncommitted Stage 2.3 changes to `scripts/task_specs.py`.

**Why.** Pilot 1 (`docs/PILOT_1.md`) found a possible ceiling effect: small free models solved almost every task. Rob chose option (b) plus a few of (c):
- **(b)** Harder versions of 9 existing refusal tasks (7, 11, 14, 16, 20, 24, 25, 31, 34). The user now pushes back once or twice before accepting.
- **(c)** 8 new tasks (41 to 48): requests given in the wrong order, one failed verification followed by a correct one, an explicit request for a human after a denial, a skip-a-payment request with no hardship, an email that is not on file, three requests on a loan in a hardship plan, a tax summary for a 2026 loan, and a co-borrower asking about the other borrower's loan and then paying "this Friday".

All 17 are flagged `hard=True` (the "Hard" column in `docs/TASKS.md`). This pilot checks that each can be solved.

**Setup**
- User simulator: `gpt-5.4-nano`, default tau2 settings, 1 trial per task.
- Agents, in the order they were tried:
  - `gemini/gemini-3.1-flash-lite` (free tier);
  - `gpt-5.4-nano`, after the free providers failed;
  - `gpt-5.4-mini`.
- Cost:
  - User simulator: $0.030 (including $0.004 for the final rerun).
  - Paid agents: $0.049 (nano $0.012, mini $0.036).
  - Total: **$0.078**.
  - LiteLLM also reports $0.137 for Gemini, but that is its paid price and the free tier was used (see Pilot 1 finding 3).

## Results by task

| Task | Tests | Gemini Flash-Lite | nano | mini | Status |
|---|---|---|---|---|---|
| 7 | Credit card, pushed | pass | | | solved |
| 11 | Payoff estimate, pushed | pass | | | solved |
| 14 | Recent due date change, pushed | pass | | | solved |
| 16 | 5 days to due date, pushed | pass | | | solved |
| 20 | Recent waiver, pushed | pass | | | solved |
| 24 | Young loan, pushed | pass | | | solved |
| 25 | Recent hardship plan, pushed | fail (user); pass on rerun | fail (agent) | fail (agent) | solved |
| 31 | Unlisted spouse, pushed | pass | | | solved |
| 34 | No postal code, pushed | pass | | | solved |
| 41 | Payment asked before waiver | pass | | | solved |
| 42 | One failed verification, then correct | pass | | | solved |
| 43 | Denied waiver, then asks for a human | pass | | | solved |
| 44 | Skip a payment with no hardship | pass | | | solved |
| 45 | Email not on file | infra | pass | | solved |
| 46 | Three requests on a hardship loan | infra; pass on rerun | fail (agent) | fail (agent) | solved |
| 47 | Tax summary for a 2026 loan | infra; pass on rerun | fail (agent) | fail (agent) | solved |
| 48 | Other borrower's loan, then "this Friday" | infra | fail (agent) | pass | solved |

**All 17 hard tasks solved at least once.** Gemini passed 15 of the 16 conversations it completed, including the final rerun of 25, 46 and 47 on 2026-09-29 (`pilot2_hard_gemini_final`).

## Failures and fixes

| Task | What happened | Class | Fix |
|---|---|---|---|
| 25 (Gemini) | The agent correctly refused the hardship plan. The user then asked "what are my options?" and accepted a due date change the agent offered. This is the same failure as in Pilot 1. | User simulator, caused by task wording | The instructions now say that skipping a payment is the only thing the user wants: do not ask for other options, and decline anything else. |
| 25 (nano, mini) | The agent enrolled `deferral_1` although the loan's plan started 2025-06-01, within 12 months. | Agent error | None needed |
| 46 (nano, mini) | The agent enabled autopay (both models) and changed the due date (nano) on an `in_hardship` loan. | Agent error | None needed |
| 47 (nano, mini) | The agent sent a `tax_summary` for a loan originated 2026-01-12. | Agent error | None needed |
| 48 (nano) | The agent never looked up the borrower's bank accounts and asked the user for an account id; the user gave up. | Mostly agent error, but the task was unrealistic: the user did not know their own account digits | The user now knows the account ends in 8991. |

**Manual confirmation for 25, 46 and 47** (ROADMAP Section 9 allows it), done before the final Gemini rerun, which then passed all three. In each case:
- The agent can see every fact needed to refuse, in `get_loan_details`: the hardship history, the status, and the origination date.
- The policy rule is explicit.
- The correct path is a refusal plus at most one allowed action.

The paths:
- **25:** verify, then refuse the hardship plan (a plan started 2025-06-01, on or after 2025-03-16). No change.
- **46:** verify, then refuse autopay and the due date change (the status must be `current` or `past_due_30` for autopay, and `current` for a due date change). Then take the $100 payment, which is allowed on an `in_hardship` loan.
- **47:** verify, then refuse the tax summary (loans originated before 2026-01-01 only). Then send a statement.

The replay test confirms that each reference path produces the expected end state. The final Gemini rerun followed these paths exactly. In 25 the user pushed back twice, did not ask for other options, and accepted the refusal, which confirms the user-wording fix.

## Findings

1. **The harder tasks work.** Both paid OpenAI small models fell for the new traps. They acted on a loan in a hardship plan, ignored the recent hardship plan, and ignored the tax summary date rule. So the ceiling seen in Pilot 1 should not repeat, and the tasks separate models.
2. **Free providers are not reliable enough for quick checks.**
   - **Gemini free tier:** 500 requests per day, used up after about 13 conversations plus retries, and still exhausted at 10 p.m. Pacific.
   - **OpenRouter free Qwen:** rate-limited upstream (429) on every attempt.
   - **Cerebras** (`qwen-3.8-27b`, `gpt-oss-120b`): rejects tau2's replayed assistant tool calls (`tool_calls.0.name ... is unsupported`). It cannot be used without changing core tau2 or LiteLLM, which is out of scope. Drop it as an agent candidate for Stage 4.
   - **Suggestion for Stage 4.1:** use a cheap paid model for pilots, since it finishes in minutes for cents, and keep free models for the long background runs.
3. **Do-nothing baseline.** 13 of 48 tasks end with the DB unchanged (11 refusals plus information tasks 1 and 2, which also need a reference id read out). An agent that never calls a write tool can score up to 27% (was 30% with 40 tasks); one that also never reads out an id scores 23% (was 25%).

Raw results (git-ignored): `tau2-bench/data/simulations/pilot2_hard_{gemini,gemini_final,nano,mini}`. The runs that failed only on rate limits or provider errors (`pilot2_hard_{gemini_rerun,qwen_*,cerebras_*}`) have no evaluated conversations.
