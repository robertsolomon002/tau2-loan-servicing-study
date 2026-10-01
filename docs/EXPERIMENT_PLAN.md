# Experiment plan (pre-registration, Stage 4.1)

**Written:** 2026-10-01, before any main run. **Status:** draft for Rob's approval; nothing in Stage 4.3 runs until Rob approves. Any later change is a dated amendment at the end of this file, never a silent edit.

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
- Prices were checked on 2026-09-30 in OpenRouter's models API, and for gpt-5.4-mini in OpenAI's pricing docs (2026-09-28).

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
- **The C1 language switch from Stage 3.3 is real across models.** Gemini Flash-Lite, Gemini 3.5 Flash-Lite, gpt-5.4-mini, Claude Sonnet 5.5 and both Nemotrons all answered English callers in French on tasks 1, 18 or 26, whose borrowers have `preferred_language: fr`.

### 4.2 Final model list

| Role (ROADMAP decision 9) | Model | Why |
|---|---|---|
| Free open model 1 | `openrouter/qwen/qwen3.8-27b:free` | 10/10, no tool errors, no rate-limit failures in this pilot |
| Free open model 2 | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 10/10, no tool errors, no rate-limit failures; about 3 times faster than Nemotron 3 Super (the backup if Ultra's free pool fails), and far larger than Qwen, which widens the range of model sizes for H3 |
| Near-free open model | `openrouter/deepseek/deepseek-v4-flash` | 10/10, no tool errors, about $0.002 per conversation, no rate limits; a dependable open model if the free pools fail |
| Cheap closed model | `openrouter/google/gemini-3.1-flash-lite` (paid, through OpenRouter) | 10/10 on the free tier. It is not OpenAI, so it is not a same-model pair with the user. It solved every task it ran in Pilot 1 and 15 of 16 in Pilot 2. The Google free tier allows about 13 conversations a day, too few for 576 |
| Frontier model | `openrouter/google/gemini-3.1-pro-preview` | 10/10, no tool errors, no rate limits, and about 25% cheaper than Claude Sonnet 5.5 |

**Dropped:**
- **Gemma 4 31B (free):** 0/10, rate-limited.
- **Gemini 3.5 Flash-Lite:** empty replies, tool errors and language mismatch.
- **Claude Haiku 4.5:** reliable, but about $0.07 per conversation, about 6 times Gemini Flash-Lite. A full 576-conversation run would cost about $43, which the budget can't cover.
- **gpt-5.4-mini as agent:** a same-model pair with the user simulator (Stage 3.4 discussion with Rob).
- **Claude Sonnet 5.5 as frontier:** it is the alternative to Gemini 3.1 Pro (Section 9), at about $5 more for the frontier cells.

**Notes:**
- Two Google models (Flash-Lite and Pro) make H3 partly a within-family size comparison, which helps its interpretation.
- Gemini 3.1 Pro is a "preview" model and could change or be withdrawn. Its C1 and C2 cells therefore run early (Section 8), and the model id and run dates are recorded.

## 5. Trials per cell

| Model | Conditions | Trials | Conversations |
|---|---|---|---|
| Qwen 3.8 27B (free) | C1, C2, C3 | 4 | 576 |
| Nemotron 3 Ultra (free) | C1, C2, C3 | 4 | 576 |
| DeepSeek V4 Flash | C1, C2, C3 | 4 | 576 |
| Gemini 3.1 Flash-Lite | C1, C2, C3 | 4 | 576 |
| Gemini 3.1 Pro | C1, C2, then C3 if the budget allows (Section 8) | 1 | 144 |
| **Total** | | | **2,448** |

## 6. Metrics and tests

All analysis code is written in Stage 5.1 and follows this section. "Success" means reward 1.0 (tau2's `is_successful`).

### 6.1 Primary metric

**pass^1 per model and condition:** the mean over the 48 tasks of each task's success rate across its trials.

Each pass^1 gets a **95% confidence interval from a paired bootstrap over tasks**:
- 10,000 resamples of the 48 tasks with replacement, seed 2026, percentile intervals;
- each resample keeps a task's results from every condition together.

Every pass^1 figure is shown next to the **do-nothing baseline**: an agent that never writes scores up to 27% (13/48), or 23% if it also never reads out an id (`docs/DOMAIN_SPEC.md`).

### 6.2 Secondary metrics

- **pass^k for k = 1 to 4** (the 4-trial models): tau2's formula, mean over tasks of C(successes, k) / C(trials, k).
- **pass^1 per task category** (11 categories), and for the 17 hard tasks versus the 31 others.
- **Language adherence.** The share of agent text turns in the customer's language, using `lingua` with the Stage 3.3 cleaning (ids, numbers, emails, postal codes, DB names and markdown removed; tau2's fixed English greeting and turns with fewer than two words skipped). Also the share of conversations with at least one agent turn in the other language.
- **Mean turns, tool calls and tool errors per conversation.**
- **Cost per conversation and per success.**
- **User-simulator language adherence** per condition. The Section 9 bar of at least 95% must hold; if it fails for a cell, that is reported.

### 6.3 Tests (per model)

Two comparisons per model: **C1 vs C2** (H1) and **C2 vs C3** (H2).

1. **Difference in pass^1** with a 95% paired-bootstrap interval (Section 6.1). This is the main result: an effect size with an interval.
2. **McNemar exact test** (two-sided binomial test on discordant tasks) on per-task majority success. A task counts as solved in a condition if it succeeded in at least 3 of 4 trials (the frontier model: its single trial). A sensitivity check uses at least 2 of 4.
3. **Multiplicity:** 2 comparisons × 5 models = 10 tests. Holm-adjusted p-values are reported next to the raw ones. Conclusions rest on the intervals, not on p < 0.05.

**H3:** the C1 − C2 gap of each smaller or open model minus the frontier model's gap, with a paired-bootstrap interval over tasks. For the 4-trial models, this uses only trial 1, so that both sides have one trial per task; all 4 trials are also reported.

**H4:** the Stage 5.2 failure taxonomy is applied to every failed conversation in C2 and C3, and to the failed C1 conversations as the comparison. Counts per type and condition are reported. H4 holds if "skipped or wrong verification" and "language mismatch" are the two types with the largest increase from C1 to the French conditions.

**Pre-specified exploratory analysis: the C1 language switch.**
- Compare language adherence in C1 between tasks whose borrower has `preferred_language: fr` (about 21 of 48) and the others. The exact list is fixed from the DB in Stage 5.1.
- Rob's alternative explanation is that a French name, not the DB field, triggers the switch. Test it on borrowers whose name is French but whose `preferred_language` is `en`, if there are enough of them.

### 6.4 What the study can detect

- **Size of a detectable difference.** With 48 paired tasks, a 95% interval on a pass^1 difference is roughly ±10 points, assuming a per-task standard deviation of the difference of about 0.35.
- **What this means for small effects.** Differences under about 10 points will not be distinguishable from zero, and the report must say so.
- **The frontier model.** With one trial per task, its intervals are wider.

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

### 8.1 Spend so far

| Item | $ |
|---|---|
| OpenRouter credit (bought, Stage 0) | 10.00 |
| OpenAI: Stages 0.1 to 3.3 | 0.71 |
| OpenAI: this pilot (user simulator and mini agent) | 0.33 |
| **Spent** | **11.04** |

The pilot used $2.94 of the OpenRouter credit, leaving $7.06 on it. Total pilot spend was $3.27 ($2.94 OpenRouter + $0.33 OpenAI), within its $5 cap.

The budget is $50 (hard cap $60). After a **$5 reserve**, **$33.96** is left for the main runs.

### 8.2 Projected cost per cell

**Per-conversation assumptions:**
- **User simulator:** $0.0032 (pilot mean $0.0027 × 1.2 for the harder full task set).
- **Agent:** the pilot cost × 1.2 for the harder tasks, and × 1.25 for OpenRouter's meter: DeepSeek $0.0029, Gemini Flash-Lite $0.0116, Gemini Pro $0.117. Free models are $0.

| Cell | Conversations | Agent $ | User $ | Cell $ |
|---|---|---|---|---|
| Qwen C1 / C2 / C3 | 192 each | 0 | 0.61 each | 1.84 |
| Nemotron Ultra C1 / C2 / C3 | 192 each | 0 | 0.61 each | 1.84 |
| DeepSeek C1 / C2 / C3 | 192 each | 0.56 each | 0.61 each | 3.51 |
| Gemini Flash-Lite C1 / C2 / C3 | 192 each | 2.23 each | 0.61 each | 8.52 |
| Gemini Pro C1 | 48 | 5.62 | 0.15 | 5.77 |
| Gemini Pro C2 | 48 | 5.62 | 0.15 | 5.77 |
| Gemini Pro C3 | 48 | 5.62 | 0.15 | 5.77 |
| **Total** | **2,448** | | | **33.02** |

**Margins:** projected total spend is $11.04 + $33.02 = **$44.06**. That leaves $0.94 of slack plus the $5 reserve.

**Where the money is spent:**
- About $25.20 of the agent cost goes through OpenRouter. The OpenRouter credit has $7.06 left, so it needs about **$20 more**, and the key's $10 limit must be raised to match.
- About $7.80 of user-simulator cost goes to OpenAI.

**Order:**
1. **Free cells (Qwen, Nemotron) start first** and run in the background for several days. 1,152 free conversations at about 9 requests each is about 10,400 requests, or about 10 days at OpenRouter's 1,000 free requests per day.
2. **Gemini Pro C1 and C2 run early,** because the model is a preview.
3. **Then DeepSeek and Gemini Flash-Lite.**
4. **Gemini Pro C3 runs last,** and only if the measured spend leaves at least its projected $5.77 plus the $5 reserve. If it doesn't, C3 for the frontier model is skipped and the report says so (H2 is then tested on the four other models only).

**Stop rules (Stage 4.2 runner):**
- Each cell stops at 1.5 × its projected cost.
- The whole run stops when total spend reaches $45. That keeps the $5 reserve under the $50 budget, and well under the $60 hard cap.

## 9. Decisions for Rob

1. **Approve this plan** (models, trials, metrics, rules, budget).
2. **Frontier model:** Gemini 3.1 Pro (recommended). The alternative is Claude Sonnet 5.5: about $0.155 per conversation (about $7.60 per cell, about $5.50 more over three cells). It also needs pauses for OpenRouter's 20-requests-per-minute limit on new accounts. Choosing it would mean dropping its C3 cell or one cheaper cell.
3. **Top up OpenRouter by about $20** with auto-reload off, and raise the API key's limit to match. Also check that the OpenAI balance covers about $8.

## Amendments

None yet.
