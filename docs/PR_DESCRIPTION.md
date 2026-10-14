# Upstream pull request draft (Stage 6.1)

**From:** `robertsolomon002:domain/loan_servicing/add-domain` (8 commits on
upstream `main` at `dd8757d`)
**To:** `sierra-research/tau2-bench:main`
**Title:** `feat: add loan_servicing domain with English and French variants`

The branch is a clean copy of `domain/loan_servicing/initial`, with three small
fix commits folded into the commits they fix. The original branch is kept
unchanged because the study repo pins its commits.

---

## Summary

Adds `loan_servicing`, a transactional customer-service domain for consumer
loans at a fictional lender (Boréal Finance, Montréal; all data synthetic), with
an English and a Quebec French version of every task and of the policy.
Proposed in #579.

The domain tests policy-constrained **actions** on a lender's database, in the
style of `airline` and `retail`. It differs from `banking_knowledge`, which
tests retrieval over a large document set: here the full policy (about 1,600
words) is in the prompt, and the challenge is applying dated eligibility rules,
verification and authorization correctly, then making the right writes.

The French variants let the same tasks measure how much an agent loses when the
customer, or the policy, is not in English. Each EN/FR task pair has
byte-identical `evaluation_criteria`; only the user scenario is translated.

## Changes Made

- `src/tau2/domains/loan_servicing/`: `data_model.py` (`LoanServicingDB`),
  `tools.py` (19 tools: 7 read, 1 generic, 11 write), `environment.py`,
  `utils.py`, and a domain `README.md`.
- `data/tau2/domains/loan_servicing/`: `policy.md`, `policy_fr.md`, `db.json`
  (60 borrowers, 90 loans, 1,886 payments, generated with a fixed seed, with
  planted edge cases), `tasks.json` (48 tasks × EN and FR = 96),
  `split_tasks.json`.
- `src/tau2/registry.py`: registers `loan_servicing` (English policy) and
  `loan_servicing_fr` (French policy) as domains and task sets. They share
  code, tools, database, tasks and splits, following the `telecom` /
  `telecom-workflow` pattern.
- `tests/test_domains/test_loan_servicing/`: 71 tests.
- `README.md` and `src/tau2/domains/README.md`: the domain is listed.
- No new dependencies and no changes to core code.

### Design decisions worth reviewing

- **Splits:** `base` holds only the 48 English tasks, so a default run stays
  comparable to other domains. `en_user` equals `base`, and `fr_user` holds
  the 48 French twins. Running `fr_user` on `loan_servicing` gives an English
  policy with French customers; running it on `loan_servicing_fr` gives a
  fully French deployment.
- **Language-neutral scoring:** `communicate_info` holds only reference codes
  (`PM-31887`) or whole numbers under 1,000. French formatting of amounts and
  dates (`12 431,07 $`) would otherwise break the substring check in one
  language only.
- **DB-hash-safe writes:** no tool has optional parameters (an OpenRouter
  provider rejected them), and write tools store only structured values, never
  free text, so the database hash is exact. Reference ids are deterministic,
  so replay and `COMMUNICATE` checks are stable.
- **Transfers are writes:** `transfer_to_human_agents` stores
  `{transfer_id, reason}`, so a missed, unneeded or wrongly coded transfer
  changes the database and is scored. The free-text summary is not hashed.
- **Fixed date:** the policy fixes the current date (2026-03-16), so every date
  rule has one correct answer.
- **Solo mode:** not supported; `get_environment(solo_mode=True)` raises
  `ValueError`.
- **Encoding:** `environment.py` reads the policy as UTF-8, and `db.json` and `tasks.json` are
  ASCII-escaped, so the domain loads on Windows without `PYTHONUTF8`.

## Testing

- `make test` (run as its pytest command, with API keys unset): 305 passed,
  17 failed, 1 xfailed. The 17 failures are the live-LLM tests
  (`test_agent`, `test_llm_utils`, `test_orchestrator`, `test_run`,
  `test_user`), which fail the same way on unmodified `main` without a key
  (234 passed, 17 failed). The branch adds 71 passing tests.
- `make check-all`: `ruff check .` passes and `ruff format --check .` reports
  every file formatted.
- `tau2 check-data` passes.
- **New tests:** database validation (ids, links, amortization, balances
  against posted payments, status and past-due consistency, due dates, autopay
  windows); success and error paths of every tool; allocation and payoff math;
  payoff closing a loan; hash stability and replay via `set_state`; the
  transfer summary not being hashed; order effects (waiver before or after a
  payment); and checks that both domains load under their own names with the
  same tools, database hash, tasks and splits, and the same codes, numbers and
  headings in both policies.
- **Task validation** (in the study repo, so no study code enters this repo):
  every task's reference actions are replayed against a fresh environment and
  must produce the expected database change; a linter checks the schema,
  language-neutral `communicate_info`, and EN/FR parity of every scenario
  value. Every task was solved at least once in solvability pilots.
- **Live runs:** 2,589 conversations with 5 agent models across the three
  conditions (user simulator `gpt-5.4-mini`, 4 trials). pass^1 ranges from
  84% to 99% by model and condition, against a do-nothing baseline of 27%. The
  domain README has a baseline table for three models.

## Documentation

- Domain README: `src/tau2/domains/loan_servicing/README.md` (overview,
  policy, tools, task categories, splits and conditions, how to run, baseline
  results).
- Proposal: #579.
- Study using this domain, with results, trajectories and analysis:
  https://github.com/robertsolomon002/tau2-loan-servicing-study

## Checklist

- [x] Tests pass (`make test`; the 17 live-LLM tests need an API key and fail
  without one on `main` too)
- [x] Code follows style guidelines (`make check-all`)
- [x] Documentation updated
- [x] Breaking changes noted (none)
