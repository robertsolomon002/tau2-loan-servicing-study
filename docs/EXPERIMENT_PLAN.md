# Experiment plan (pre-registration, Stage 4.1)

**Written:** 2026-10-01, before any main run. **Status: approved by Rob on 2026-10-01.** Any later change is a dated amendment at the end of this file, never a silent edit.

**Changes from the first draft (`004f15e`), agreed with Rob before approval:**
- Both Gemini models run directly on Google Cloud **Vertex AI** (project `tau-loan-study`), paid from Rob's Google Cloud free-trial credit, not through OpenRouter. A 3-conversation Vertex test of Gemini 3.1 Pro worked (Section 4.1), and Rob confirmed in the billing console that it came off the trial credit.
- With the trial credit, **Gemini 3.1 Pro gets the full design** (C1–C3 × 4 trials), the same as the other models.
- **No OpenRouter top-up.** OpenRouter now carries only DeepSeek (paid from the $7.06 left) and the free models.

**Versions:** study repo `630ed89` plus this commit; fork `66e179c` (pinned in `pyproject.toml`); 48 tasks in English (`en_user`) and Quebec French (`fr_user`).

**Supersedes:** where ROADMAP Sections 5 and 6 differ (they assume 40 tasks and older prices), this plan wins.

## 1. Question and hypotheses

Do customer-service agents follow a loan-servicing policy as well when the customer speaks Quebec French as when the customer speaks English?

The hypotheses are exploratory: the study has 48 tasks and can detect only large effects (Section 6.4).

- **H1.** For each model, pass^1 in C2 (English policy, French customer) is lower than in C1 (English policy, English customer).
- **H2.** For each model, pass^1 in C3 (French policy, French customer) is higher than in C2: a localized policy recovers part of the gap.
- **H3.** The C1 − C2 gap is larger for the smaller and open models than for the frontier model.
- **H4.** Among failures in the French conditions, the most common French-specific failure types are skipped or wrong identity verification and language mismatch. "French-specific" means more frequent in C2 and C3 than in C1, using the Stage 5.2 failure taxonomy.

## 2. Conditions

| Condition | tau2 domain | Policy | Task split | Customer |
|---|---|---|---|---|
| C1 EN/EN | `loan_servicing` | `policy.md` | `en_user` | English |
| C2 EN/FR | `loan_servicing` | `policy.md` | `fr_user` | Quebec French |
| C3 FR/FR | `loan_servicing_fr` | `policy_fr.md` | `fr_user` | Quebec French |

The tasks, the database, the tools and the scoring are identical across conditions. Each FR task has byte-identical evaluation criteria to its EN twin (checked by `scripts/lint_tasks.py`). Only the language of the policy and of the customer changes.

## 3. Fixed settings

- **Agent:** tau2's default `llm_agent`, unchanged, with temperature 0 (the tau2 default).
- **User simulator:** `gpt-5.4-mini` (OpenAI), temperature 0, for every model and condition. It was chosen in Stage 3.3 and confirmed by Rob in Stage 3.4; see `docs/USER_SIM.md`. **No agent model is an OpenAI model**, so the customer and the agent are never the same model.
- **tau2 defaults:** max steps 200, max errors 10, seed 300 (trials use tau2's per-trial seeds).
- **Concurrency:** 1 per model, so rate limits stay predictable.
- **Results:** every result file records both repos' commits, the model ids, the condition, the trial and the date (ROADMAP Section 8).

## 4. Models

### 4.1 Pilot results (2026-09-30 to 2026-10-01)

**Setup:**
- 5 tasks (1, 18, 26, 36, 46) × C1 and C2 × 1 trial, per candidate.
- User simulator gpt-5.4-mini.
- Script: `scripts/cost_pilot.py`; metrics: `results/cost_pilot_metrics.csv`.
- Prices were checked on 2026-09-30 in OpenRouter's models API, and for gpt-5.4-mini in OpenAI's pricing docs (2026-09-28). Google's own list prices for Gemini 3.1 Pro ($2.00 / $12.00 per 1M input / output tokens, $0.20 cached input) and Flash-Lite ($0.25 / $1.50) match OpenRouter's; LiteLLM carries the same prices for the `vertex_ai/` ids.

| Candidate (LiteLLM id) | Tier | Completed / 10 | Rate-limited first tries | Solved | Tool errors / calls | Agent in C1 language | Agent $ per conv* | Min per conv |
|---|---|---|---|---|---|---|---|---|
| `openrouter/qwen/qwen3.8-27b:free` | free, open | 10 | 0 | 10 | 0 / 38 | 100% | 0 | 0.7 |
| `openrouter/google/gemma-4-31b-it:free` | free, open | **0** | 10 | – | – | – | 0 | – |
| `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | free, open | 10 | 0 | 10 | 0 / 48 | 75% | 0 | 3.2 |
| `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | free, open | 10 | 0 | 10 | 0 / 37 | 82% | 0 | 1.0 |
| `gemini/gemini-3.1-flash-lite` (Google free tier) | cheap, closed | 10 | 0 | 10 | 2 / 34 | 53% | 0.0077 (list price) | 0.5 |
| `openrouter/deepseek/deepseek-v4-flash` | near-free, open | 10 | 0 | 10 | 0 / 42 | 100% | 0.0019 | 0.6 |
| `gpt-5.4-mini` | cheap, closed | 10 | 0 | 10 | 5 / 40 | 77% | 0.0059 | 0.1 |
| `openrouter/anthropic/claude-haiku-4.5` | cheap, closed | 10 | 5 | 10 | 0 / 35 | 100% | 0.0474 | 0.2 |
| `openrouter/google/gemini-3.5-flash-lite` | cheap, closed | **9** | 3 | 7 | 3 / 27 | 33% | 0.0047 | 0.1 |
| `openrouter/anthropic/claude-sonnet-5.5` | frontier | 10 | 3 | 10 | 0 / 37 | 67% | 0.1032 | 0.2 |
| `openrouter/google/gemini-3.1-pro-preview` | frontier | 10 | 0 | 10 | 0 / 37 | 100% | 0.0777 | 0.5 |

\*LiteLLM's estimate per completed conversation. OpenRouter's own meter showed **$2.94** where LiteLLM summed $2.35, so OpenRouter costs below are multiplied by **1.25**.

**What the pilot showed:**
- **The Nemotron and Qwen free pools all worked in this pilot.** Both Nemotrons and Qwen completed 10/10.
- **Every completed conversation except two (both Gemini 3.5 Flash-Lite) was solved.** The 5 pilot tasks are mostly easy, so this pilot measures cost and reliability, not ability. Stage 2.3 already showed that the full task set separates models.
- **Free pools are unreliable from day to day.** Gemma was rate-limited upstream on all 10 tries, even with 4 retries 65 s apart. Qwen, which failed in Pilot 2, worked this time.
- **OpenRouter limits new accounts to 20 requests per minute on Anthropic models.** Haiku and Sonnet needed retries with pauses.
- **Gemini 3.5 Flash-Lite returned empty messages.** On task 46 (C1) it did so four times in a row; tau2 records that as an "infrastructure error", but it is a model failure (Section 7).
- **Vertex AI test (2026-10-01):** `vertex_ai/gemini-3.1-pro-preview` on tasks 18, 26 and 46 (C1): 3/3 solved, 31–48 s each, agent $0.091–0.102 per conversation (LiteLLM), against about $0.101 for the same tasks through OpenRouter. Gemini's automatic caching saved about 13%. The charge (about $0.29) came off the trial credit. Raw results: `results/raw/stage4_1/vertex_test_pro.json`.
- **The C1 language switch from Stage 3.3 is real across models.** Gemini Flash-Lite, Gemini 3.5 Flash-Lite, gpt-5.4-mini, Claude Sonnet 5.5 and both Nemotrons all answered English callers in French on tasks 1, 18 or 26, whose borrowers have `preferred_language: fr`.

### 4.2 Final model list

| Role (ROADMAP decision 9) | Model | Why |
|---|---|---|
| Free open model 1 | `openrouter/qwen/qwen3.8-27b:free` | 10/10, no tool errors, no rate-limit failures in this pilot |
| Free open model 2 | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 10/10, no tool errors, no rate-limit failures; about 3 times faster than Nemotron 3 Super (the backup if Ultra's free pool fails), and far larger than Qwen, which widens the range of model sizes for H3 |
| Near-free open model | `openrouter/deepseek/deepseek-v4-flash` | 10/10, no tool errors, about $0.002 per conversation, no rate limits; a dependable open model if the free pools fail |
| Cheap closed model | `vertex_ai/gemini-3.1-flash-lite` (Vertex AI, trial credit) | 10/10 on the free tier. It is not OpenAI, so it is not a same-model pair with the user. It solved every task it ran in Pilot 1 and 15 of 16 in Pilot 2. The Google AI Studio free tier allows about 13 conversations a day, too few for 576, so it runs on Vertex |
| Frontier model | `vertex_ai/gemini-3.1-pro-preview` (Vertex AI, trial credit) | 10/10 through OpenRouter and 3/3 through Vertex, no tool errors, no rate limits, about 25% cheaper than Claude Sonnet 5.5. Chosen by Rob |

**Dropped:**
- **Gemma 4 31B (free):** 0/10, rate-limited.
- **Gemini 3.5 Flash-Lite:** empty replies, tool errors and language mismatch.
- **Claude Haiku 4.5:** reliable, but about $0.07 per conversation, about 6 times Gemini Flash-Lite. A full 576-conversation run would cost about $43, which the budget can't cover.
- **gpt-5.4-mini as agent:** a same-model pair with the user simulator (Stage 3.4 discussion with Rob).
- **Claude Sonnet 5.5 as frontier:** Rob chose Gemini 3.1 Pro, which the trial credit pays for; Sonnet would be cash through OpenRouter.

**Notes:**
- Two Google models (Flash-Lite and Pro) make H3 partly a within-family size comparison, which helps its interpretation.
- Gemini 3.1 Pro is a "preview" model and could change or be withdrawn. Its cells therefore run early (Section 8), and the model id and run dates are recorded.
- `vertex_ai/gemini-3.1-flash-lite` has not been called through Vertex yet (only through the AI Studio free tier). The Stage 4.2 runner test includes one Vertex Flash-Lite conversation before its cells start.
- Trial accounts can have lower Vertex quotas. The runner backs off on 429 errors like any other provider (Section 7).

## 5. Trials per cell

| Model | Conditions | Trials | Conversations |
|---|---|---|---|
| Qwen 3.8 27B (free) | C1, C2, C3 | 4 | 576 |
| Nemotron 3 Ultra (free) | C1, C2, C3 | 4 | 576 |
| DeepSeek V4 Flash | C1, C2, C3 | 4 | 576 |
| Gemini 3.1 Flash-Lite | C1, C2, C3 | 4 | 576 |
| Gemini 3.1 Pro | C1, C2, C3 | 4 | 576 |
| **Total** | | | **2,880** |

## 6. Metrics and tests

All analysis code is written in Stage 5.1 and follows this section. "Success" means reward 1.0 (tau2's `is_successful`).

### 6.1 Primary metric

**pass^1 per model and condition:** the mean over the 48 tasks of each task's success rate across its trials.

Each pass^1 gets a **95% confidence interval from a paired bootstrap over tasks**:
- 10,000 resamples of the 48 tasks with replacement, seed 2026, percentile intervals;
- each resample keeps a task's results from every condition together.

Every pass^1 figure is shown next to the **do-nothing baseline**: an agent that never writes scores up to 27% (13/48), or 23% if it also never reads out an id (`docs/DOMAIN_SPEC.md`).

### 6.2 Secondary metrics

- **pass^k for k = 1 to 4** (every model): tau2's formula, mean over tasks of C(successes, k) / C(trials, k).
- **pass^1 per task category** (11 categories), and for the 17 hard tasks versus the 31 others.
- **Language adherence.** The share of agent text turns in the customer's language, using `lingua` with the Stage 3.3 cleaning (ids, numbers, emails, postal codes, DB names and markdown removed; tau2's fixed English greeting and turns with fewer than two words skipped). Also the share of conversations with at least one agent turn in the other language.
- **Mean turns, tool calls and tool errors per conversation.**
- **Cost per conversation and per success.**
- **User-simulator language adherence** per condition. The Section 9 bar of at least 95% must hold; if it fails for a cell, that is reported.

### 6.3 Tests (per model)

Two comparisons per model: **C1 vs C2** (H1) and **C2 vs C3** (H2).

1. **Difference in pass^1** with a 95% paired-bootstrap interval (Section 6.1). This is the main result: an effect size with an interval.
2. **McNemar exact test** (two-sided binomial test on discordant tasks) on per-task majority success. A task counts as solved in a condition if it succeeded in at least 3 of 4 trials. A sensitivity check uses at least 2 of 4.
3. **Multiplicity:** 2 comparisons × 5 models = 10 tests. Holm-adjusted p-values are reported next to the raw ones. Conclusions rest on the intervals, not on p < 0.05.

**H3:** the C1 − C2 gap of each smaller or open model minus the frontier model's gap, with a paired-bootstrap interval over tasks, using all 4 trials on both sides.

**H4:** the Stage 5.2 failure taxonomy is applied to every failed conversation in C2 and C3, and to the failed C1 conversations as the comparison. Counts per type and condition are reported. H4 holds if "skipped or wrong verification" and "language mismatch" are the two types with the largest increase from C1 to the French conditions.

**Pre-specified exploratory analysis: the C1 language switch.**
- Compare language adherence in C1 between tasks whose borrower has `preferred_language: fr` (about 21 of 48) and the others. The exact list is fixed from the DB in Stage 5.1.
- Rob's alternative explanation is that a French name, not the DB field, triggers the switch. Test it on borrowers whose name is French but whose `preferred_language` is `en`, if there are enough of them.

### 6.4 What the study can detect

- **Size of a detectable difference.** With 48 paired tasks, a 95% interval on a pass^1 difference is roughly ±10 points, assuming a per-task standard deviation of the difference of about 0.35.
- **What this means for small effects.** Differences under about 10 points will not be distinguishable from zero, and the report must say so.

## 7. Exclusion and rerun rules

1. **Provider failures are rerun, not counted.** This covers rate limits (429), server errors (5xx), timeouts and connection errors.
   - tau2 retries each conversation itself (`--max-retries 4 --retry-delay 65` on free and rate-limited providers).
   - A conversation that still ends as `infrastructure_error` with a provider error is rerun later, up to 5 more times.
   - If it never completes, it is reported as missing, and the paired tests drop that task for that model in every condition.
2. **Model output failures count as failures (reward 0), not reruns.** This covers an empty assistant message, a reply with neither text nor tool call, or a tool call the provider rejects because of the model's output. tau2 labels these `infrastructure_error`, and the error message tells them apart.
3. **Agent-side endings count as failures:** `max_steps`, `too_many_errors`, `agent_error` and `context_window_exceeded`.
4. **User-simulator errors are kept in the main analysis.** A sensitivity analysis excludes conversations where:
   - (a) any user turn is in the wrong language, or
   - (b) Stage 5.2 labels a major simulator error, for example an early `###TRANSFER###`.
5. **No other exclusions.** No conversation is dropped or rerun because of its result.

## 8. Run order and budget

Money comes from three places: **cash** (the $50 budget, hard cap $60), the **OpenRouter credit** already bought (part of the cash spent), and **Google Cloud trial credit** (outside the cash budget; $300, used only for the two Gemini models).

### 8.1 Spend so far

| Item | Cash $ |
|---|---|
| OpenRouter credit (bought, Stage 0) | 10.00 |
| OpenAI: Stages 0.1 to 3.3 | 0.71 |
| OpenAI: the 4.1 pilot (user simulator and mini agent) | 0.33 |
| OpenAI: the Vertex test (user simulator) | 0.01 |
| **Spent** | **11.05** |

- The pilot used $2.94 of the OpenRouter credit, leaving **$7.06** on it. Total pilot spend was $3.27, within its $5 cap.
- The Vertex test used about **$0.29 of trial credit**.

### 8.2 Projected cost per cell

**Per-conversation assumptions:**
- **User simulator (OpenAI, cash):** $0.0032 (pilot mean $0.0027 × 1.2 for the harder full task set).
- **Agent:** the pilot cost × 1.2 for the harder tasks. DeepSeek also × 1.25 for OpenRouter's meter: $0.0029. Gemini on Vertex is billed at Google's list price, with no OpenRouter factor: Flash-Lite $0.0092, Pro $0.093 (the Vertex test measured $0.091–0.102 on three longer-than-average tasks). Free models are $0.

| Cell (each of C1 / C2 / C3) | Conversations | Agent $ (paid from) | User $ (cash) |
|---|---|---|---|
| Qwen | 192 | 0 (free) | 0.61 |
| Nemotron Ultra | 192 | 0 (free) | 0.61 |
| DeepSeek | 192 | 0.56 (OpenRouter credit) | 0.61 |
| Gemini Flash-Lite | 192 | 1.77 (trial credit) | 0.61 |
| Gemini Pro | 192 | 17.90 (trial credit) | 0.61 |
| **Total, 15 cells** | **2,880** | | **9.22** |

| Source | Projected main-run cost | Total with spend so far | Limit |
|---|---|---|---|
| **Cash** (OpenAI) | $9.22 | **$20.27** | $50 budget, $60 hard cap |
| OpenRouter credit (already paid) | $1.67 (DeepSeek) | $4.61 of $10 | key limit $10 |
| **Google trial credit** | $59.03 (Flash-Lite $5.32, Pro $53.71) | **$59.32** | $300 |

**What has to be in each account before Stage 4.3:**
- **OpenAI:** at least $12 of prepaid balance, auto-recharge off.
- **OpenRouter:** nothing to add; $7.06 covers DeepSeek with margin.
- **Google trial:** nothing to add. The budget alert should sit above the projected $59, for example at $100.

**Order:**
1. **Free cells (Qwen, Nemotron) start first** and run in the background for several days. 1,152 free conversations at about 9 requests each is about 10,400 requests, or about 10 days at OpenRouter's 1,000 free requests per day.
2. **Gemini Pro runs early** (all three conditions), because the model is a preview.
3. **Then DeepSeek and Gemini Flash-Lite.**

**Stop rules (Stage 4.2 runner):**
- Each cell stops at 1.5 × its projected cost.
- Cash: the whole run stops when total cash spend reaches $45. That keeps a $5 reserve under the $50 budget, and well under the $60 hard cap.
- Trial credit: the Gemini cells stop when Vertex spend reaches $90 (1.5 × the projection). If the trial credit ever stops covering Vertex, the Gemini cells pause and the change is recorded as an amendment.

## 9. Decisions (resolved 2026-10-01)

1. **Plan:** approved by Rob.
2. **Frontier model:** Gemini 3.1 Pro, through Vertex AI, with the full 4-trial design.
3. **Money:** no OpenRouter top-up. Gemini runs on the Google trial credit (Rob confirmed in the billing console that the Vertex test was charged to it). The only cash still to add is the OpenAI balance (at least $12) before Stage 4.3.

## Amendments

### Amendment 1 (2026-10-01, Stage 4.2, before any main run): how reruns work

The runner (`scripts/run_matrix.py`, `docs/RUNNER.md`) applies Section 7's rules with different mechanics than rule 1 describes. The rules themselves are unchanged.
- **Retries happen per LLM call, not per conversation.** tau2's `--max-retries 4 --retry-delay 65` restarts a whole conversation. Instead, a 429, 5xx, timeout or connection error makes the runner wait and retry that one call (20 s, then 1, 2, 5, 10, 15 and 30 min). If it still fails, the conversation is rerun later. A conversation gets **at most 6 attempts in all**, then it is reported as missing (rule 1).
- **A user-simulator crash is rerun.** This means an empty user reply, or an error in a user-simulator call. It isn't the agent's failure, so it is treated like a provider failure (rule 1). Rule 4 is about simulator *behaviour* in finished conversations and is unchanged.
- **Which model failed** is taken from the LLM call that failed, or whose reply tau2 rejected. Agent-side output errors count as failures (rules 2 and 3).
- **The budget is metered per call**, so failed attempts count toward the caps. The caps are those of Section 8.
