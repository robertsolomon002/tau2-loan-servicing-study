# τ-Loan Roadmap: a bilingual (EN/FR) loan-servicing domain for τ²-bench

**Prepared for:** Rob
**Date:** 2026-09-23
**Status:** Planning. No code yet.
**Deliverables:** (1) a new `loan_servicing` domain contributed upstream to [sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench) as a pull request; (2) a public study repo with an English vs Quebec French experiment across several models; (3) a 4 to 6 page technical report (arXiv-ready) and a blog post for Rob's personal site and LinkedIn; (4) resume bullets backed by the results.
**Budget:** about **$50** of API spend in total (hard cap $60). Free and near-free models are used wherever possible.
**Pace:** runs in parallel with the ESSCONTI analyst project; long benchmark runs happen in the background over several days.

> **How to use this file.** Each Stage is a checkpoint that leaves something working and verifiable. Each substage is one focused prompt that any capable model (Claude Code, Cowork, or another agent) can execute with this file as context. Do stages in order, one substage per session unless stated. Before any substage, the agent must read Sections 1 to 10. After a substage, the agent must run the tests it names, commit with `Stage X.Y: <summary>`, and tick the box in Section 13. Steps marked **[Rob]** need a human; the agent stops and asks if one is not done. **Never guess τ²-bench internals:** read the actual source in the fork (Stage 0.3 writes `docs/TAU2_NOTES.md` for this reason) and prefer it over anything in this roadmap if they disagree.

---

## 1. What we are building (plain English)

[τ²-bench](https://github.com/sierra-research/tau2-bench) is Sierra's open benchmark for customer-service AI agents. An agent gets a company **policy** and a set of **tools** over a database; an LLM **user simulator** plays a customer with a hidden goal; the conversation is scored by checking whether the database ends in the correct state and whether required information was communicated. It has a public leaderboard and domains for airline, retail, telecom, and banking knowledge (retrieval over documents).

We add a **loan-servicing domain**: a fictional Canadian lender's borrower-support desk. The agent verifies identity, answers questions about loans, takes payments, quotes payoffs, changes due dates, waives late fees, enrolls borrowers in hardship plans, and escalates when required, all under a policy with realistic, tricky rules. This is transactional (actions with policy constraints), which is different from the existing `banking_knowledge` domain (document retrieval).

Then we use it to answer a question nobody has measured on τ²-bench: **do agents follow policy as well when the customer speaks Quebec French?** Three conditions:

| Condition | Policy language | Customer language | Real-world meaning |
|-----------|-----------------|-------------------|--------------------|
| **C1 EN/EN** | English | English | The standard benchmark setting |
| **C2 EN/FR** | English | Quebec French | The common real case: company policy in English, customer speaks French |
| **C3 FR/FR** | Quebec French | Quebec French | A fully localized deployment |

**Why this is a strong resume project:** it shows evals and benchmark design (the most-requested differentiating skill), agents and tool use, an open-source contribution to a well-known benchmark, experimental rigor with statistics, and a real finding written up as a report. Sierra is hiring new-grad agent engineers, and the bilingual angle is something Rob is unusually well placed to do (native-level French review).

**Related work to cite:** τ-bench (Yao et al., 2024, arXiv 2406.12045), τ²-bench (Sierra), and Ticket-Bench (arXiv 2509.14477), a multilingual function-calling benchmark in six languages including French, built on a ticket-buying scenario. Ticket-Bench measures multilingual tool calling; we measure **policy compliance in a multi-turn, dual-party, stateful setting** inside τ²-bench, with a paired design where only the language changes.

## 2. How τ²-bench works (the parts we touch)

Verified from the repo docs on 2026-09-23 (v1.0.1). Stage 0.3 re-verified against the source on 2026-09-28: see `docs/TAU2_NOTES.md` Section 1 for the differences (the details there override this section).

- **Install:** Python 3.12 to 3.13, `uv sync` (add `--extra dev` for tests and linting). Models are called through **LiteLLM**, so any LiteLLM model string works (OpenAI, Anthropic, Gemini, OpenRouter, Cerebras, Groq, and more). Keys live in `.env`.
- **Run:** `tau2 run --domain <name> --agent-llm <model> --user-llm <model> --num-trials <k> --num-tasks <n> --max-concurrency <c>`. Results go to `data/simulations/`; `tau2 view` browses them; `tau2 evaluate-trajs` re-scores trajectory files.
- **Domain code** lives in `src/tau2/domains/<domain>/`: `data_model.py` (a `DB` subclass), `tools.py` (a `ToolKitBase` subclass), `environment.py` (functions returning the environment, the task list, and task splits); optional `user_data_model.py` and `user_tools.py` for dual control (the user can act too, like telecom).
- **Domain data** lives in `data/tau2/domains/<domain>/`: `tasks.json`, `split_<name>.json` (at least a `base` split), `policy.md`, `db.json` or `db.toml`, and optional `user_db.*` and `tasks_voice.json`.
- **Registration:** in `registry.py`, `registry.register_domain(get_environment, "<name>")` and `registry.register_tasks(get_tasks, "<name>", get_task_splits=get_tasks_split)`.
- **Scoring:** the reward is the **product** of the components listed in each task's `evaluation_criteria.reward_basis`:
  - `DB`: the final database hash must equal the hash obtained by replaying the task's reference `actions` on a fresh environment. Any trajectory reaching the same end state passes.
  - `COMMUNICATE`: every string in `communicate_info` must appear as a **substring** in the agent's messages.
  - `ENV_ASSERTION`: assertions run on the final environment (only if listed).
  - `NL_ASSERTION`: an LLM judge checks natural-language assertions (experimental; we avoid it).
  - `ACTION`: strict tool-call matching (special cases only; we avoid it).
- **Headline metric:** pass^k, the share of tasks solved in **all** k independent trials (pass^1 is the mean success rate).
- **Contributing:** open an issue first for new domains; branch name `domain/<domain-name>/<feature>`; include tools, tasks, policy, tests, and a domain README; `make test` and `make check-all` must pass; Ruff, 88-character lines, type hints encouraged, docstrings on public APIs.
- **Leaderboard:** covers the four official text domains and prefers at least 4 trials per domain. A new domain is not automatically on the leaderboard; our results are published in our own repo and report.

## 3. Decisions (locked with Rob, 2026-09-23)

1. **Two repos.** (a) A **fork** of `tau2-bench`, branch `domain/loan_servicing/initial`, containing only upstream-quality domain code, data, tests, and README, which becomes the PR. (b) A **study repo** `tau2-loan-servicing-study` (public) holding experiment configs, the runner, analysis, figures, the report, and the blog post. The study repo depends on the fork by pinned git commit (`uv` git dependency).
2. **Domain name:** `loan_servicing`, plus `loan_servicing_fr`, which reuses the same code and database but loads the Quebec French policy (for condition C3). Customer language is controlled by the task variant (EN or FR user instructions), exposed as splits `en_user` and `fr_user`.
3. **Fictional lender:** "Boréal Finance" (fictional; all names and data synthetic). Products: personal installment loans and auto loans, in CAD.
4. **Single control** (only the agent has tools) for the core study, which keeps it comparable with airline and retail. Dual control (the borrower's banking app as user tools) is a stretch goal only.
5. **About 40 tasks,** each in an EN and a FR variant with **identical evaluation criteria**. Small enough to hand-verify, large enough for paired statistics.
6. **Language-neutral scoring:** `reward_basis` is `["DB"]` or `["DB", "COMMUNICATE"]`. `communicate_info` strings must be written identically in English and French (reference codes like `BF-48213`, or whole numbers under 1000 with no separators). A linter enforces this. Amounts over 999 and dates are never used in `communicate_info`, because French formatting (`12 431,07 $`, `15 octobre`) would break substring matching and bias the result.
7. **Default τ²-bench agent** (the standard tool-calling LLM agent) for every model, so differences come from the model and the language, not our own agent code.
8. **One fixed user simulator** for every condition and agent model, chosen in Stage 3.3 for quality and cost. It must speak Quebec French reliably in FR tasks (measured).
9. **Models (verify IDs and prices at build time; never assume from memory):**
   - **Free or near-free open models** as agents: 2 to 3 tool-calling-capable models from OpenRouter's free list (requires a one-time $10 credit purchase to raise the free limit to about 1,000 requests per day), Cerebras free tier (for example `gpt-oss-120b`), or Google AI Studio free tier (Gemini Flash). Chosen by the Stage 4.1 pilot on reliability.
   - **One cheap closed model** as agent (a "mini", "flash", or "haiku" class model).
   - **One frontier model** as agent on a reduced design (fewer trials, possibly C1 and C2 only) if the budget allows after the pilot.
10. **Pre-registration:** hypotheses, metrics, and the analysis plan are written down (Stage 4.1) **before** the main runs, so results cannot be cherry-picked.
11. **Hosting results:** trajectories go to a Hugging Face dataset (free); summary CSVs and figures live in the study repo.
12. **Authoring cost:** code, tasks, and translations are written with Claude Code or Cowork (Rob's subscription), which does not touch the $50 API budget. The API budget is only for benchmark runs.

## 4. Domain design: `loan_servicing`

### 4.1 Database entities (`data_model.py`)

- **Borrower:** `borrower_id`, `first_name`, `last_name`, `date_of_birth`, `postal_code`, `email`, `phone`, `preferred_language` (`en` or `fr`), `authorized_third_parties` (list of names), `payment_methods` (list of `{method_id, type: bank_account, bank_name, last4}`).
- **Loan:** `loan_id`, `borrower_ids` (primary and optional co-borrower), `product` (`personal` or `auto`), `origination_date`, `original_principal`, `annual_rate`, `term_months`, `monthly_payment`, `principal_balance`, `accrued_interest`, `next_due_date`, `due_day`, `status` (`current`, `past_due_30`, `past_due_60`, `in_hardship`, `paid_off`, `charged_off`), `autopay` (`{enabled, method_id, day}`), `fees` (list of `{fee_id, type: late_fee, amount, assessed_date, status: open|waived|paid}`), `due_date_changes` (list of dates), `hardship_history` (list of `{plan, start_date, end_date}`), `scheduled_payments`.
- **Payment:** `payment_id`, `loan_id`, `amount`, `date`, `method_id`, `status` (`posted`, `scheduled`, `cancelled`, `returned`), `allocation` (`{fees, interest, principal}`).
- **Case note:** `note_id`, `loan_id`, `created_at`, `category` (an enum, no free text: free text in the DB breaks the DB hash check; see `docs/TAU2_NOTES.md` Flag 1). Created by write tools for escalations and hardship enrollments.
- **Document request:** `request_id`, `loan_id`, `type` (`statement`, `payoff_letter`, `tax_summary`), `sent_to` (always the email on file).
- A fixed **"today"** for the environment (for example 2026-03-16) so dates are deterministic.

### 4.2 Agent tools (`tools.py`)

Read tools: `find_borrower_by_email`, `find_borrower_by_phone`, `find_borrower_by_name_dob`, `get_borrower_details`, `get_loan_details`, `list_payments`, `calculate_payoff(loan_id, payoff_date)`, `calculate(expression)` (simple math, as in airline).
Write tools: `make_payment(loan_id, amount, method_id, date)`, `cancel_scheduled_payment(payment_id)`, `set_autopay(loan_id, enabled, method_id, day)`, `change_due_date(loan_id, new_day)`, `waive_late_fee(loan_id, fee_id)`, `enroll_hardship_plan(loan_id, plan)` with plans `deferral_1`, `deferral_2`, `reduced_payment_3`, `update_contact_info(borrower_id, email?, phone?)`, `send_document(loan_id, type)`, `transfer_to_human_agents(summary)`.

As in the official domains, **tools enforce data integrity only** (valid ids, amounts, dates), **not policy**. The agent must apply the policy itself; that is what the benchmark measures.

### 4.3 Policy highlights (`policy.md`, written in full in Stage 1.1)

- **Identity verification** before sharing any account detail or acting: full name plus date of birth plus postal code must all match. Co-borrowers may act on shared loans. Listed third parties may receive general information but may not make changes. Nobody else, regardless of what they claim.
- **Confirm before acting:** before any write action, restate the details and get an explicit yes. One write action at a time.
- **Language:** respond in the language the customer uses (English or French).
- **Payments:** amount between $1 and the payoff amount; date from today up to 30 days ahead; only methods on file. When past due, payments apply to fees, then interest, then principal.
- **Payoff quotes:** valid for dates up to 10 days ahead; payoff letters go only to the email on file.
- **Due date change:** at most once per rolling 12 months; loan must be `current`; new day between 1 and 28; not allowed within 5 days of the current due date.
- **Late fee waiver:** at most one waiver per rolling 12 months per loan; fee must be $50 or less; after the waiver the loan must not remain past due (a payment in the same call counts if already posted).
- **Hardship plans:** only for a loss of income or unexpected expense stated by the customer (the agent must **not** ask for medical or personal details); loan at least 6 months old; no hardship plan in the last 12 months; at most 60 days past due. Offer `deferral_1` first; `deferral_2` only if the customer says one month is not enough; `reduced_payment_3` only if the customer says they can pay part but not all. Never promise credit-reporting outcomes.
- **Autopay:** changes within 3 days of the due date take effect next cycle (tell the customer).
- **Must transfer to a human:** disputes about a charge or balance, bankruptcy or legal action, suspected fraud or identity theft, complaints about staff, any request outside the tools, and a customer who fails verification twice. Transfer means calling `transfer_to_human_agents` and then telling the customer.
- **Conduct:** no threats, no legal or tax advice, never discuss a loan with an unauthorized person.

### 4.4 Task design

About 40 tasks, balanced across categories, with roughly half requiring an action and half requiring a refusal, a partial action, or a transfer:

| Category | ~Count | Examples |
|----------|--------|----------|
| Information after verification | 4 | next due date, balance, last payment |
| Payments | 5 | one-time payment, cancel a scheduled payment, pay more than payoff (must refuse the excess) |
| Payoff | 3 | quote for a date in 7 days (allowed) vs 20 days (not allowed), send payoff letter |
| Due date change | 4 | allowed; denied (changed 5 months ago); denied (past due); denied (too close to due date) |
| Late fee waiver | 4 | allowed; denied (second in a year); denied (fee over $50) |
| Hardship | 6 | eligible `deferral_1`; escalation to `deferral_2`; `reduced_payment_3`; ineligible (loan 4 months old); ineligible (plan last year); user volunteers medical details (agent must not probe) |
| Autopay | 3 | enable, change method, change near due date (next-cycle notice) |
| Authorization and social engineering | 5 | co-borrower allowed; spouse not listed denied; listed third party asks for a change (deny change, share general info); caller fails verification then tries again |
| Must transfer | 3 | balance dispute, bankruptcy mention, suspected fraud |
| Multi-request and change of mind | 3 | two requests in one call, one allowed and one not; customer changes the payment amount midway |

Each task has: a `user_scenario` (persona plus hidden instructions and known info, written in EN and FR variants), reference `actions` (for the DB end state), `reward_basis`, and language-neutral `communicate_info` where needed. The FR variant adds to the persona: "You speak Quebec French and only switch to English if the agent cannot continue in French."

## 5. Experiment design

- **Units:** 40 tasks × 3 conditions (C1, C2, C3) × models × k trials. Same tasks, same database, same user simulator: only language changes.
- **Trials:** k = 4 for free and cheap models (enables pass^1 to pass^4); frontier model k = 1 or 2 depending on budget.
- **Primary metric:** pass^1 per condition and model, with 95% confidence intervals by paired bootstrap over tasks.
- **Secondary:** pass^k curves (k = 1 to 4); per-category success; **language adherence** (share of agent turns in the customer's language, via a language-detection library); average turns, tool calls, and cost per task and per success.
- **Tests:** paired comparisons C1 vs C2 and C2 vs C3 per model (McNemar test on per-task majority success, plus the paired bootstrap difference). Report effect sizes with intervals; with 40 tasks, differences under about 10 points will not be distinguishable, and the report must say so.
- **Pre-registered hypotheses (exploratory):** H1: C2 is below C1. H2: C3 recovers part of the C2 gap. H3: gaps are larger for smaller and open models. H4: the most common French-specific failures are skipped verification steps and language mismatch.
- **Confound control:** the user simulator could be worse in French. Stage 3.3 measures simulator errors in both languages on a labeled sample, and the report adjusts or discusses it. Tasks where the simulator broke (for example revealed hidden info wrongly) are flagged in analysis.
- **Failure taxonomy (Stage 5.2):** skipped or wrong identity verification; acted without confirmation; policy rule misapplied (which rule); wrong tool arguments; missed transfer; unnecessary transfer; communicated wrong info; language mismatch; user-simulator error; task ambiguity.

## 6. Budget plan ($50, hard cap $60)

All figures are estimates to be replaced by the Stage 4.1 pilot measurements.

| Item | Estimate | Notes |
|------|----------|-------|
| OpenRouter credit | $10 | Unlocks ~1,000 free-model requests per day; leftover credit can pay for very cheap open models |
| Development and task debugging runs | ~$3 | Mostly on free models |
| User simulator for all runs | ~$12 to $18 | Cheap model; ~1,500 to 2,000 conversations. Free Gemini Flash may replace it if the pilot shows it is reliable and fast enough |
| Cheap closed agent model (3 conditions × 40 × 4) | ~$8 to $12 | 480 conversations |
| Frontier agent model (reduced design) | ~$8 to $12 | For example C1 and C2 × 40 × 1 to 2 trials, with provider prompt caching if available |
| Reserve | ~$5 | Reruns and fixes |

Rules: every run prints its projected cost first; the runner (Stage 4.2) tracks spend from LiteLLM usage data and **stops automatically** at the stage budget; all provider accounts use prepaid credits with auto-reload OFF.

Rate-limit math for free models: a conversation is roughly 20 to 40 model calls (agent plus user simulator), so about 1,000 free requests per day is roughly 25 to 50 agent conversations per day per provider. 480 conversations for one free model is about 1 to 2 weeks of background running; spreading free models across providers (OpenRouter, Cerebras, Google) runs them in parallel.

## 7. Study repo layout (`tau2-loan-servicing-study`)

```
configs/            # one YAML per experiment cell: model, user model, condition, trials, budget
scripts/
  run_matrix.py     # resumable, rate-limit-aware, budget-capped runner
  cost_pilot.py
  lint_tasks.py     # also used as a test
analysis/
  load.py           # trajectories -> tidy dataframe
  metrics.py        # pass^k, bootstrap, McNemar, language adherence
  failures.py       # failure classification helpers
  figures.py
results/            # summary CSVs, figures (trajectories go to Hugging Face)
report/             # LaTeX tech report + bib
blog/               # post in Markdown with figures, ready for Rob's site
docs/
  TAU2_NOTES.md     # verified notes on tau2 internals (Stage 0.3)
  EXPERIMENT_PLAN.md# pre-registration (Stage 4.1)
  FAILURES.md       # failure analysis
  RESUME_NOTES.md
CLAUDE.md
ROADMAP.md          # this file
```

## 8. Conventions for every substage

- Python 3.12, `uv`, Ruff (88 characters in the fork, to match upstream), type hints, docstrings on public functions, `pytest`.
- In the fork: follow `CONTRIBUTING.md` exactly and keep changes limited to the new domain (plus the registry line and any docs index). Never modify core τ²-bench behavior for the study.
- Every experiment is defined by a config file, and every result file records the git commits of both repos, model ids, user model id, condition, trial index, and date.
- Before any LLM-calling run over 20 conversations, print the projected cost and the remaining budget and continue only if it fits.
- No real people, companies, or financial data. Boréal Finance and every borrower are fictional.
- Update Section 13 of this roadmap and add a one-line entry to `docs/LOG.md` after each substage.

## 9. Quality bars (must hold before the main runs)

- Every task's reference actions replay cleanly and produce a DB change that matches its description (automated test).
- `lint_tasks.py` passes: EN and FR variants have identical `evaluation_criteria`; every `communicate_info` string matches `^[A-Z]{2}-\d{4,6}$` or `^\d{1,3}$`; every task id has both variants; splits are consistent.
- Solvability: in the Stage 2.2 pilot, every task is solved at least once by some model, or has been manually confirmed solvable with a written trajectory.
- The user simulator speaks French in at least 95% of user turns in FR tasks and English in at least 95% in EN tasks (Stage 3.3).
- Upstream `make test` and `make check-all` pass in the fork.

## 10. Risks and mitigations

- **Upstream may not merge** (or may take weeks). Mitigation: open the issue first (Stage 0.2); keep the domain fully usable from the fork either way. On the resume, say "submitted" until merged.
- **Free-tier limits or model removals.** Mitigation: pick models from several providers; the runner resumes after interruptions; record model ids and dates.
- **User simulator bias across languages.** Mitigation: Stage 3.3 measurement, flagged tasks, and an explicit limitation in the report.
- **Translation quality.** Mitigation: LLM draft, back-translation diff, and Rob's native-level review with a glossary of fixed terms.
- **Too few tasks for significance.** Mitigation: paired design, honest intervals, and framing as a first measurement with released data so others can extend it.

---

## 11. The roadmap: stages and substages

### Stage 0: Setup and grounding
*Checkpoint: the fork and study repo exist, τ²-bench runs locally with a free model, the upstream issue is open, and the real internals are documented.*

- **0.1 Fork, install, and smoke test.**
  Prompt: "Read ROADMAP.md Sections 1 to 10. Clone Rob's fork of `sierra-research/tau2-bench` (Rob creates the fork on GitHub first), create branch `domain/loan_servicing/initial`, and run `uv sync --extra dev`, `make test`, and `make check-all`. Then run `tau2 run --domain airline --num-tasks 2 --num-trials 1` with a free agent model and a free or cheap user model through LiteLLM (try the OpenRouter, Cerebras, and Gemini model strings from Section 3 decision 9 and record which ones work with tool calling). Record tokens and cost per conversation from the results. Separately, create the study repo `tau2-loan-servicing-study` with the layout in Section 7, a `pyproject.toml` that depends on the fork by git commit, `CLAUDE.md` pointing to this roadmap, and copy this roadmap in as `ROADMAP.md`. Report what works, per-conversation cost, and any errors."

- **0.2 [Rob] Accounts and the upstream issue.**
  Rob: create API keys (OpenRouter with a one-time $10 credit, Cerebras, Google AI Studio, plus one of OpenAI or Anthropic with prepaid credit and auto-reload OFF) and a Hugging Face account; put keys in `.env` in both repos (never committed). The agent drafts the GitHub issue text for `sierra-research/tau2-bench` ("Proposal: loan_servicing domain with EN and FR task variants"): what the domain covers, how it differs from `banking_knowledge`, the planned file list, the language-neutral scoring choice, and a question on whether they would accept it upstream. Rob posts it.

- **0.3 Document the real internals.**
  Prompt: "Read the fork's source for the `airline` and `retail` domains (data_model.py, tools.py, environment.py, their data folders), `registry.py`, the `Task` and evaluation models, the evaluator code for DB and COMMUNICATE rewards, the user simulator prompt, the default LLM agent, how splits are loaded, and the test layout for domains. Write `docs/TAU2_NOTES.md` in the study repo: exact class names, decorators (for example how tools are marked read or write), function signatures, file formats with a minimal real example of a task JSON, how the DB hash is computed, how the user simulator receives instructions, how to register a domain and splits, and how to add a second domain name that reuses code with a different policy file. Flag anything in ROADMAP.md Section 2 that differs from the source. This document is the reference for all later stages."

### Stage 1: The domain (English)
*Checkpoint: `loan_servicing` is registered, its tools pass unit tests, and an agent can hold a conversation in it.*

- **1.1 Policy and domain spec.**
  Prompt: "Using ROADMAP.md Section 4.3 and `docs/TAU2_NOTES.md`, write `data/tau2/domains/loan_servicing/policy.md` in the same style and structure as the airline policy: role and scope, general rules (verification, confirmation, one action at a time, language, transfer rules, conduct), then one section per capability (payments, payoff, due date changes, fee waivers, hardship, autopay, documents, contact updates) with precise, testable rules and numbers. Every rule must be checkable from the database and tool outputs. Also write `docs/DOMAIN_SPEC.md` in the study repo mapping each policy rule to the data fields and tools that make it checkable, and list the edge cases each rule creates (these become tasks). Keep the policy under about 1,800 words."

- **1.2 Data model and seeded database.**
  Prompt: "Implement `src/tau2/domains/loan_servicing/data_model.py` (Pydantic models for Section 4.1 entities, following the airline `DB` pattern from `docs/TAU2_NOTES.md`) and a deterministic generator script (kept in the study repo under `scripts/generate_db.py`, not in the fork) that writes `data/tau2/domains/loan_servicing/db.json`: about 60 borrowers and 90 loans with realistic payment histories, balances computed correctly from rate and term (standard amortization), statuses consistent with payment histories, and the fixed environment date. Plant the edge cases listed in `docs/DOMAIN_SPEC.md` (for example a loan whose due date changed 5 months ago, a loan 4 months old, a borrower with a listed third party, a co-borrowed loan, fees over and under $50). Add tests that validate the DB against the model and check the amortization math and that each planted edge case exists."

- **1.3 Tools, environment, registration, and tests.**
  Prompt: "Implement `tools.py` with every tool in ROADMAP.md Section 4.2, marked read or write exactly as the official domains do, with docstrings that become the tool descriptions the agent sees (clear, concise, arguments documented). Tools validate data integrity (ids exist, amounts positive, method on file, dates valid) and raise errors like the official domains, but must NOT enforce policy rules. `make_payment` must allocate to fees, interest, and principal; `calculate_payoff` must include accrued interest to the payoff date. Implement `environment.py` (environment, tasks, splits) and register `loan_servicing` in `registry.py`. Write a full test suite in the fork's test layout: every tool's happy path and error paths, allocation math, payoff math, and DB hashing stability. Run `make test` and `make check-all`, then hold one manual conversation with `tau2 run` on a placeholder task using a free model to confirm the domain loads. Report results."

### Stage 2: Tasks (English)
*Checkpoint: about 40 English tasks exist, pass the linter and replay tests, and are shown to be solvable.*

- **2.1 Write the tasks, the linter, and replay tests.**
  Prompt: "Write about 40 tasks in `data/tau2/domains/loan_servicing/tasks.json` following the category table in ROADMAP.md Section 4.4 and the exact Task schema in `docs/TAU2_NOTES.md`. Each task: a clear id (`ls_001_en` style), a persona and hidden goal written as the official domains do (including what the user knows, how they behave, and what they should refuse or insist on), reference `actions` that produce the correct end state (`[]`, never `null`, when the correct outcome is no change), `reward_basis` `DB` or `DB` plus `COMMUNICATE`, and language-neutral `communicate_info` (Section 3 decision 6). Create `split_tasks.json` with the splits `base` and `en_user`. In the study repo, write `scripts/lint_tasks.py` implementing the Section 9 checks (run as a pytest test too) and a replay test that applies each task's reference actions to a fresh environment and asserts the expected DB diff (for example 'one new payment of 250 on loan L-1042'). Also write `docs/TASKS.md`, a readable table of every task: category, what the correct outcome is, and which policy rule it tests. Run everything and report."

- **2.2 Solvability pilot and task fixing.**
  Prompt: "Run all English tasks for 2 trials with the strongest free agent model that worked in Stage 0.1 and the planned user simulator, within a $2 cap (print the projected cost first). For every failed conversation, read the trajectory and classify the cause as agent error, user-simulator error, task bug (ambiguous instructions, wrong reference actions, policy gap), or tool bug. Fix every task bug, tool bug, and policy gap (update `docs/TASKS.md` and `docs/DOMAIN_SPEC.md`), rerun the affected tasks, and repeat until no task bugs remain. Write `docs/PILOT_1.md` with the table of causes, what was fixed, and per-category success. List any task never solved so Rob can check it manually."

- **2.3 [Rob] Task review.**
  Rob reads `docs/TASKS.md` and a few trajectories, flags unrealistic or ambiguous tasks, and confirms that the rules feel like a real lender. The agent applies the changes in a follow-up prompt and reruns the linter and replay tests.

### Stage 3: French
*Checkpoint: a Quebec French policy and FR task variants exist with evaluation criteria identical to English, and the user simulator is shown to behave comparably in both languages.*

- **3.1 French policy and `loan_servicing_fr`.**
  Prompt: "Translate `policy.md` into Quebec French as `policy_fr.md` in the same data folder: natural professional Quebec French as a Canadian lender would write it (for example 'prélèvement automatique', 'date d'échéance', 'frais de retard', 'entente de paiement', courriel, NIP not used), keeping every number, id format, rule, and heading structure identical. Create `docs/GLOSSARY_FR.md` with every fixed term. Produce a back-translation into English and a rule-by-rule diff against the original to catch meaning drift, and fix any drift. Register a second domain `loan_servicing_fr` that reuses the same code, database, and tasks but loads `policy_fr.md` (use the mechanism documented in `docs/TAU2_NOTES.md`). Add a test that both domains load and share identical tools and DB hashes."

- **3.2 French task variants.**
  Prompt: "For every English task, create a French variant (`ls_001_fr`) with the user scenario translated into natural Quebec French (persona, hidden instructions, known information), plus the persona line from ROADMAP.md Section 4.4 about speaking Quebec French. Names, ids, amounts, dates, and all evaluation criteria stay exactly identical to the English variant. Add the `fr_user` split to `split_tasks.json` (and update `base` if needed). Extend `lint_tasks.py` to verify EN/FR pairs have byte-identical `evaluation_criteria` and matching known-info values. Write `docs/TASKS_FR_REVIEW.md`, a side-by-side table of EN and FR user instructions for Rob to review."

- **3.3 User-simulator validation and choice.**
  Prompt: "Choose the user simulator. For 2 to 3 candidate user models (one cheap paid model and the best free option from Stage 0.1), run 10 EN and 10 FR tasks, 1 trial each, with a fixed cheap agent model, within a $4 cap. Measure: user-turn language adherence (language detection), user-simulator errors (revealing hidden info too early, contradicting the scenario, ending the conversation wrongly, switching language), conversation length, cost, and rate-limit failures. Have the agent pre-label simulator errors and present 20 trajectories (10 EN, 10 FR) in `docs/USER_SIM_REVIEW.md` for Rob to confirm or correct the labels; report agreement. Recommend one user model that meets the Section 9 language bar with the fewest errors per dollar, and record the choice and evidence in `docs/USER_SIM.md`."

- **3.4 [Rob] French review.**
  Rob reviews `policy_fr.md`, `docs/GLOSSARY_FR.md`, `docs/TASKS_FR_REVIEW.md`, and the simulator labels, fixes wording, and confirms the chosen user simulator.

### Stage 4: Running the experiment
*Checkpoint: a pre-registered plan, a budget-safe resumable runner, and a complete set of trajectories for every planned cell.*

- **4.1 Cost pilot and pre-registration.**
  Prompt: "Run a cost and reliability pilot: 5 tasks × each candidate agent model (Section 3 decision 9; verify current ids and prices first) × conditions C1 and C2 × 1 trial, with the chosen user simulator, within a $5 cap. Measure cost per conversation, tokens, time, tool-call format errors, and rate-limit behavior. Drop models that fail tool calling or are too unreliable. Then write `docs/EXPERIMENT_PLAN.md` as a pre-registration: hypotheses H1 to H4, conditions, the final model list, trials per cell, the exact metrics and statistical tests from Section 5, exclusion rules (for example conversations that crash for infrastructure reasons are rerun, not counted as failures), and a budget table per cell that fits the remaining budget with a $5 reserve. Rob approves this plan before Stage 4.3. Commit it with a date so it is clearly written before the main results."

- **4.2 Resumable, budget-capped runner.**
  Prompt: "Write `scripts/run_matrix.py` in the study repo. Input: a list of config files (model, user model, domain `loan_servicing` or `loan_servicing_fr`, split `en_user` or `fr_user`, trials, per-cell budget). It calls τ²-bench's run API or CLI for each cell, stores results under `results/raw/<cell>/`, and is resumable: completed task-trial pairs are skipped after a restart. It respects per-provider rate limits (configurable requests per minute and per day, with backoff on 429 errors), records actual cost from LiteLLM usage per conversation, and stops a cell or the whole run when its budget or the global $60 cap would be exceeded. It writes a live `results/progress.md` (done, remaining, spend, errors per cell) and can run unattended for days (document how to run it with `nohup` or `tmux`). Test it with a tiny config against the mock domain and a free model, including a simulated crash and resume."

- **4.3 Main runs (background) and monitoring.**
  Prompt: "Launch the approved `docs/EXPERIMENT_PLAN.md` matrix with `run_matrix.py`, free-model cells first, in the background. Each time this prompt is re-run (for example once a day), read `results/progress.md`, check error rates and spend, investigate any cell with more than 5% infrastructure errors, restart or rebalance providers if a free model is throttled or removed (record every change in `docs/LOG.md` and, if it changes the design, as a dated amendment in the experiment plan), and report status. When every cell is complete, verify counts (tasks × trials per cell), upload all trajectories to a Hugging Face dataset with a dataset card, and report final spend."

### Stage 5: Analysis
*Checkpoint: the pre-registered analysis is done, failures are understood, and publication-quality figures exist.*

- **5.1 Metrics and statistics.**
  Prompt: "Implement `analysis/load.py` (trajectories to a tidy dataframe: model, condition, task, category, trial, reward, turns, tool calls, cost, per-turn languages) and `analysis/metrics.py`: pass^1 and pass^k (k = 1 to 4, using the unbiased estimator described in the τ-bench paper), paired bootstrap 95% intervals over tasks (10,000 resamples, fixed seed), McNemar tests for C1 vs C2 and C2 vs C3 per model, per-category success, language adherence, and cost per success. Produce `results/summary.csv` and `results/RESULTS.md` with tables that follow the pre-registered plan exactly, clearly separating confirmatory results from exploratory extras. Add unit tests for the pass^k estimator and the bootstrap on toy data."

- **5.2 Failure analysis.**
  Prompt: "Classify every failed conversation into the taxonomy in ROADMAP.md Section 5, using an LLM classifier run through Claude Code or Cowork (not the API budget), or a cheap model within a $3 cap, with the trajectory, the task description, and the policy as input and a structured output (primary cause, policy rule involved, turn where it went wrong, one-sentence explanation). Build `docs/FAILURE_REVIEW.md` with a random sample of 40 classified failures for Rob to label, compute agreement (Cohen's kappa) between Rob and the classifier, and only report classifier-based proportions if kappa is at least 0.6 (otherwise report Rob's labels on the sample). Write `docs/FAILURES.md`: failure proportions by condition and model, what differs in French, and 4 to 6 short illustrative excerpts (with French excerpts translated in brackets)."

- **5.3 Figures and tables.**
  Prompt: "Create publication-quality figures in `analysis/figures.py` (matplotlib, colorblind-safe palette, vector PDF for the report and PNG for the blog): (1) pass^1 by model and condition with intervals; (2) pass^k curves per condition; (3) the paired C1 minus C2 difference per model with intervals; (4) failure-type composition by condition; (5) language adherence by model and condition; (6) cost per success by model. Make one clean LaTeX table of the main results. Save everything under `results/figures/`, and check every number in the figures against `results/summary.csv`."

### Stage 6: Release and write-up
*Checkpoint: the upstream PR is open, the study repo is reproducible, and the report, blog post, and resume material are done.*

- **6.1 Upstream pull request.**
  Prompt: "Prepare the fork branch for review following `CONTRIBUTING.md`: a domain README (`src/tau2/domains/loan_servicing/README.md` or where the source shows domain docs belong) with overview, policy summary, tools, task categories, the EN and FR splits, how to run it, and baseline results for 2 to 3 models from our study; clean commit history using conventional commits; `make test` and `make check-all` passing; no study-only code in the fork. Draft the PR description (what, why, how it differs from `banking_knowledge`, the language-neutral scoring decision, testing done, link to the issue and to the study). Rob opens the PR. Afterwards, handle review comments in follow-up prompts."

- **6.2 Reproducibility and study repo polish.**
  Prompt: "Make the study repo reproducible and presentable: README with the question, the three conditions, headline figure, main results table, how to reproduce any single cell with one command (and its expected cost), links to the Hugging Face dataset, the upstream PR, and the report. Pin both repos' commits and all model ids in `results/MANIFEST.json`. Add a GitHub Actions workflow that runs lint, tests, the task linter, and a no-API smoke test on every push. Add a license (MIT, matching upstream) and a CITATION.cff."

- **6.3 Technical report.**
  Prompt: "Write the report in `report/` (LaTeX, 4 to 6 pages plus references, arXiv-ready article class): title, abstract, introduction (the real-world gap: customers who do not speak the policy's language), related work (τ-bench, τ²-bench, Ticket-Bench, multilingual tool-use and instruction-following evaluations; verify every citation and fetch correct BibTeX), the loan-servicing domain (policy design, tools, tasks, language-neutral scoring), experimental setup (conditions, models with ids and dates, user simulator and its validation, trials, budget), results (confirmatory then exploratory, with the Stage 5 figures), failure analysis, limitations (simulator confound, task count, translation, model versions, single lender design), and conclusion. Use only numbers from `results/`. Compile it and fix all warnings. Also produce a one-page summary PDF."

- **6.4 Blog post, resume bullets, and interview prep.**
  Prompt: "Write `blog/post.md`: a 900 to 1,300 word post for Rob's personal site (and a shorter LinkedIn version) with the question, what was built, the headline finding with the main figure, one vivid French failure example, what it means for companies deploying agents in bilingual markets like Quebec, and links. Then write `docs/RESUME_NOTES.md` with 3 resume bullets (action, technology, measured result, using only real numbers), a 60-second spoken summary, and an interview cheat sheet: how τ²-bench scoring works, why the language-neutral scoring matters, how the tasks were validated, why the design is paired, the statistics used and their limits, the user-simulator confound, what surprised you, and what you would do with more budget."

---

## 12. Effort and timeline (rough)

About 22 agent prompts plus 5 [Rob] steps. Working in parallel with the ESSCONTI project:
- Week 1: Stages 0 to 2 (setup, domain, English tasks).
- Week 2: Stage 3 (French) and 4.1 to 4.2; launch runs at the end of the week.
- Weeks 2 to 3: runs in the background (free-tier rate limits make this the slow part), analysis code (5.1) written against partial results.
- Week 3 to 4: Stages 5 and 6. The upstream PR can be opened as soon as Stage 3 is done, before the study finishes, which gives Sierra time to review.

Minimum resume-ready cut if time runs short: the domain and PR (Stages 0 to 3 plus 6.1) with a C1 vs C2 comparison on two models.

## 13. Progress tracker

- [x] 0.1 Fork and smoke test · [x] 0.2 Accounts and issue [Rob] · [x] 0.3 Internals notes
- [ ] 1.1 Policy and spec · [ ] 1.2 Data model and DB · [ ] 1.3 Tools and registration
- [ ] 2.1 Tasks, linter, replay · [ ] 2.2 Solvability pilot · [ ] 2.3 Task review [Rob]
- [ ] 3.1 French policy · [ ] 3.2 French tasks · [ ] 3.3 User simulator · [ ] 3.4 French review [Rob]
- [ ] 4.1 Cost pilot and pre-registration (Rob approves) · [ ] 4.2 Runner · [ ] 4.3 Main runs
- [ ] 5.1 Metrics · [ ] 5.2 Failures · [ ] 5.3 Figures
- [ ] 6.1 Upstream PR · [ ] 6.2 Repro polish · [ ] 6.3 Report · [ ] 6.4 Blog and resume

## 14. Open items

- Sierra's response to the issue (might ask for changes to scope, naming, or scoring).
- Whether to post the report to arXiv (a first-time submitter may need an endorser in cs.CL or cs.AI); default is to host the PDF on the study repo and Rob's site.
- Stretch goals if budget or time remain: dual-control variant (borrower banking app as user tools), a C4 condition (FR policy with an EN customer), a voice variant (`tasks_voice.json`), more tasks.

## 15. Out of scope

Leaderboard submission for the official domains, fine-tuning or training agents on the domain, custom agent architectures, and any real lender data.
