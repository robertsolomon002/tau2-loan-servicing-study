# Pilot 1: solvability of the English tasks (Stage 2.2)

Date: 2026-09-28. Fork task set at commit a04f799, plus the closing-instruction fix below.

**Setup**
- Agents (both free): `openrouter/qwen/qwen3.8-27b:free` and `gemini/gemini-3.1-flash-lite`.
- User simulator: `gpt-5.4-nano`.
- Default tau2 settings (temperature 0).
- Cost: 183 simulations in total (87 evaluated, the rest infrastructure errors from rate limits); the user simulator cost $0.072, and both agents were free.

## Round 1 (Qwen, original task instructions)

28 of the 32 evaluated conversations passed. The 48 infrastructure errors came from OpenRouter's limit of 20 requests per minute on free models, reached by running 2 conversations at a time combined with tau2's immediate retries. They are not counted.

| Task | Cause | Class | Fix |
|---|---|---|---|
| ls_013_en | The user confirmed and sent `###STOP###` in the same message, so the agent never acted | User simulator, caused by task wording | Closing instruction rewritten |
| ls_027_en | Same as ls_013_en | User simulator, caused by task wording | Same |
| ls_025_en | The hardship request was correctly refused; the agent then offered a due date change (allowed by the policy) and the user accepted | Task bug (user not told to refuse unrelated offers) | Same |
| ls_029_en | Before any verification, the agent changed an **unrelated** borrower's email (`BF-10001`) to an invented address, then served the real caller | Agent error | None needed (the task worked as designed) |

**Fix.** Every task's instructions now end with the `END` rule in `scripts/task_specs.py`:
- the user does not agree to changes the task does not describe;
- the user waits for the agent to report the outcome before ending;
- the user never ends the conversation in the same message as a confirmation.

A test enforces this rule on all tasks.

## Round 2 (fixed tasks)

- **55 of 55 evaluated conversations passed:** Gemini 40/40 (every task), Qwen 15/15.
- **Every task was solved at least once.** No task bugs or tool bugs remain.
- The 6 tasks that round 2 missed at first because of rate limits were rerun one task per invocation with 60 to 70 second pauses; there were no errors after that.

## Findings for later stages

1. **Possible ceiling effect (decision for Rob in Stage 2.3).** Small free models solve nearly every English task. A ceiling in C1 would compress any French gap.
   - The likely reason: the users are cooperative, state their loan ids, give details when asked, and accept refusals quickly.
   - Options:
     - (a) keep the tasks and rely on pass^4 and the French conditions to separate models;
     - (b) harden some tasks: users who push back on refusals, give details out of order, or bundle several requests;
     - (c) add about 10 harder tasks.
   - Recommendation: (b), plus a few of (c), decided in the Stage 2.3 review.
2. **Rate limits need pacing in the runner (Stage 4.2).**
   - OpenRouter allows 20 free requests per minute, and the shared Qwen pool often returns 429.
   - Gemini Flash-Lite allows about 10 requests per minute.
   - tau2 retries 3 times without backoff, so the runner needs per-provider pacing and must rerun infrastructure errors.
3. **Cost.** About $0.001 per conversation for the `gpt-5.4-nano` user, far below the budget estimate. LiteLLM reports Gemini's paid price even on the free tier, so the runner must record cost per provider tier.

Raw results: `tau2-bench/data/simulations/pilot*` (git-ignored; to be moved to `results/raw/stage2_pilot`).
