---
license: cc-by-4.0
language:
- en
- fr
pretty_name: τ-Loan main-run trajectories
tags:
- agents
- tool-use
- tau2-bench
- multilingual
- customer-service
size_categories:
- 1K<n<10K
configs:
- config_name: index
  data_files: index.csv
---

# τ-Loan main-run trajectories

Every conversation from the main runs of the τ-Loan study: a bilingual (English and Quebec French) loan-servicing domain for [τ²-bench](https://github.com/sierra-research/tau2-bench). The study asks whether tool-using LLM agents get worse when the customer speaks French, and whether a French policy helps.

- Study repo (code, pre-registered plan, analysis): https://github.com/robertsolomon002/tau2-loan-servicing-study
- Domain code: https://github.com/robertsolomon002/tau2-bench, branch `domain/loan_servicing/initial`

All borrowers, loans, and the lender (Boréal Finance) are fictional.

## Design

| Condition | Domain | Policy | Customer |
|---|---|---|---|
| C1 | `loan_servicing` | English | English (`ls_NNN_en`) |
| C2 | `loan_servicing` | English | Quebec French (`ls_NNN_fr`) |
| C3 | `loan_servicing_fr` | Quebec French | Quebec French (`ls_NNN_fr`) |

There are 48 tasks per condition. Each French task has the same evaluation criteria as its English twin. Scoring follows τ²-bench: final database state plus required ids read out to the customer (reward 0 or 1). The user simulator is `gpt-5.4-mini` for every run.

| Model (`model` column) | Agent LiteLLM id | Trials | Conversations |
|---|---|---|---|
| `deepseek` | `openrouter/deepseek/deepseek-v4-flash` | 4 | 576 |
| `flash_lite` | `vertex_ai/gemini-3.1-flash-lite` | 4 | 576 |
| `gemini_pro` | `vertex_ai/gemini-3.1-pro-preview` | 4 | 576 |
| `nemotron` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 4 | 576 |
| `qwen` | `openrouter/qwen/qwen3.8-27b:free` | 2 | 285 |

That makes 2,589 conversations in total. Qwen stopped after two trials because OpenRouter withdrew its free endpoint on 2026-10-05. Three Qwen conversations were never completed: C1 `ls_034_en` trial 1, C2 `ls_020_fr` trial 1, and C3 `ls_048_fr` trial 2 (`trial` 0, 0 and 1 in the files). See Amendment 2 in the study's `docs/EXPERIMENT_PLAN.md`. Runs took place 2026-10-01 to 2026-10-08.

## Files

- `index.csv`: one row per conversation with the columns `cell`, `model`, `condition`, `domain`, `agent_llm`, `user_llm`, `task_id`, `task_number`, `user_language`, `trial` (0-based), `seed`, `outcome`, `reward`, `termination_reason`, `num_messages`, `agent_cost`, `user_cost` (USD, as LiteLLM computes it), and `file`.
- `trajectories/<model>_<condition>/sims/<task_id>__t<trial>.json`: τ²-bench `SimulationRun` with the full message history, tool calls, and reward breakdown.
- `trajectories/<cell>/cell.json`: cell settings (domain, split, model ids, seeds, study and fork commits).
- `trajectories/<cell>/attempts.jsonl`: every attempt the runner made, including provider errors that were retried.
- `runner.log`: the runner's log for the whole run.

**Outcomes.** `done` means the conversation finished and was scored. `model_failure` (6 conversations: 2 Nemotron, 4 Qwen) means the agent model returned an empty reply. τ²-bench labels these `infrastructure_error` and stores no `reward_info`. The pre-registered plan counts them as failures, so `reward` is 0 in `index.csv`.

