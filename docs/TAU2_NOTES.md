# τ²-bench internals (verified from source)

Written in Stage 0.3 on 2026-09-28 by reading the fork `../tau2-bench` at commit `b7ea907` (v1.0.1). Paths are relative to the fork. This is the reference for all later stages; if the source changes, update this file.

## 1. Flags: what differs from ROADMAP.md

Read these first. Each one changes something we planned.

1. **Free text in the DB breaks the DB check.** The reward compares a SHA-256 hash of the whole DB (Section 6). Any free text a write tool stores (a case note `text`, a transfer `summary`) will differ between the agent's run and the reference replay, so the task fails even when the agent was right. **Write tools must store only structured values** (ids, enums, amounts, dates). The `Case note.text` field in ROADMAP 4.1 must become a `category` enum (or be left out of the DB).
2. **Transfers are invisible to the DB check.** In airline, `transfer_to_human_agents` is `ToolType.GENERIC`, so it does not mutate state and is not replayed. A "must transfer" task scored on `DB` alone would also pass an agent that does nothing. Our `transfer_to_human_agents` should be a WRITE tool that appends a structured transfer record (for example `{borrower_id or loan_id, reason: dispute|bankruptcy|fraud|complaint|out_of_scope|failed_verification}`), with no free text in the DB. Alternative: `ENV_ASSERTION`. Decide in Stage 1.1 and 1.3.
3. **Split files.** There is one split file per task file, `split_tasks.json`, which maps split names to task-id lists and must include `base`. Stage 2.1's prompt says `split_base.json` and `split_en_user.json`; that is wrong. Use `split_tasks.json` with keys `base`, `en_user`, `fr_user`. Select a split with `--task-split-name`.
4. **COMMUNICATE matching is looser than we assumed.** It is case-insensitive, and **commas are deleted from the agent's text** before the substring test (Section 7). A short number like `25` also matches inside `250` or `2025`. The linter must check that each `communicate_info` value cannot appear by accident in a normal answer (for example prefer 3-digit values or `BF-` codes, and check against amounts and dates the agent is likely to say).
5. **"No change" tasks need `actions: []`, not `null`.** If both `actions` and `env_assertions` are `null`, the DB check is skipped and returns 1.0. An empty list runs the check against the unchanged DB.
6. **Write tools must be deterministic.** During evaluation, every state-changing tool call in the trajectory is replayed, and by default the replay **raises** if the tool's output differs from what the agent saw (`strict=True`). So write tools cannot use random ids, the real clock, or anything non-deterministic. Airline uses a fixed list of new ids (`HATHAT`, `HATHAU`, `HATHAV`) and a fixed "now" (`_get_datetime` returns `2024-05-15T15:00:00`).
7. **The study repo cannot find the domain data by itself.** The data folder is `$TAU2_DATA_DIR` if set, otherwise `<source>/data`. When tau2 is installed as a package (as in the study repo), the fallback resolves to `.venv/Lib/data`, which does not exist. The study runner must set `TAU2_DATA_DIR=../tau2-bench/data`. The pinned fork commit in `pyproject.toml` must also be bumped once the domain exists.
8. **The user simulator's framing is always English.** The global guidelines (`data/tau2/user_simulator/simulation_guidelines.md`) and the labels around the scenario ("Reason for call:", "Known info:") are English in every condition. FR tasks only change the scenario text. This is a possible confound for Stage 3.3 to measure and the report to mention.
9. **`make check-all` rewrites files.** It runs `ruff check .` then `ruff format .` (not `--check`). Run it before committing.
10. **Infra errors.** Any termination other than `user_stop` or `agent_stop` scores 0.0 in the evaluator, but the run summary reports infrastructure errors separately and excludes them from its metrics. The study analysis must treat them as reruns, not failures (ROADMAP 4.1 exclusion rule).
11. **Cerebras tool calls** (from Stage 0.1): `to_litellm_messages` adds a non-standard top-level `name` to each tool call (`src/tau2/utils/llm_utils.py:182`), which Cerebras rejects. Fix or avoid before using Cerebras.

Everything else in ROADMAP Section 2 matches the source.

## 2. Domain layout

Code in `src/tau2/domains/<domain>/` (see `src/tau2/domains/README.md`):

| File | Contents |
|---|---|
| `utils.py` | Paths only: `<X>_DATA_DIR = DATA_DIR / "tau2" / "domains" / "<domain>"`, plus `_DB_PATH`, `_POLICY_PATH`, `_TASK_SET_PATH` |
| `data_model.py` | Pydantic models and a `DB` subclass (for example `FlightDB(DB)`) |
| `tools.py` | A `ToolKitBase` subclass (for example `AirlineTools(ToolKitBase)`) |
| `environment.py` | `get_environment`, `get_tasks`, `get_tasks_split` |
| `user_data_model.py`, `user_tools.py` | Optional, dual control only (we don't use them) |

Data in `data/tau2/domains/<domain>/`: `policy.md`, `db.json` (or `.toml`), `tasks.json`, `split_tasks.json`, optional `tasks_voice.json`. For scale: the airline policy is about 1,300 words (retail about 1,160), with 50 tasks; retail has 114 tasks.

## 3. Data model

`src/tau2/environment/db.py`:

```python
class DB(BaseModelNoExtra):          # pydantic, model_config = ConfigDict(extra="forbid")
    @classmethod
    def load(cls, path: str) -> "DB"   # load_file(path) then model_validate
    def dump(self, path, exclude_defaults=False, **kwargs)
    def get_hash(self) -> str          # get_pydantic_hash(self)
    def get_statistics(self) -> dict   # override to report counts
```

Airline pattern: nested models with `Field(description=...)`, `Literal` types for enums, and a top-level `FlightDB(DB)` with `Dict[str, Model]` collections keyed by id (`flights`, `users`, `reservations`). Because of `extra="forbid"`, `db.json` must match the model exactly.

## 4. Tools

`src/tau2/environment/toolkit.py`:

```python
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

class LoanTools(ToolKitBase):
    db: LoanDB
    def __init__(self, db: LoanDB) -> None:
        super().__init__(db)

    @is_tool(ToolType.READ)
    def get_loan_details(self, loan_id: str) -> Loan:
        """
        Get the details of a loan.

        Args:
            loan_id: The loan ID, such as 'L-1042'.

        Returns:
            The loan details.

        Raises:
            ValueError: If the loan is not found.
        """
```

- `ToolType` values: `READ`, `WRITE`, `THINK`, `GENERIC`. `is_tool(tool_type, mutates_state=None)`: `mutates_state` defaults to `True` for `WRITE` and `False` otherwise. Only mutating tools are replayed during evaluation.
- Airline uses `READ` for lookups, `WRITE` for changes, and `GENERIC` for `calculate` and `transfer_to_human_agents`. `think` exists but is commented out.
- The **docstring is the tool description** the agent sees. It is parsed with `docstring_parser`: short description, long description, `Args:` (one line per parameter), `Returns:`, `Raises:`. Type hints become the JSON schema.
- Errors: tools `raise ValueError("...")`. `Environment.get_response` catches any exception and returns a `ToolMessage` with content `"Error: <message>"` and `error=True`. The run ends with `too_many_errors` after 10 errors (`DEFAULT_MAX_ERRORS`).
- Return values: a pydantic model is serialized with `model_dump`, then `json.dumps(..., default=str)`.
- Private helpers start with `_` (for example `_get_user`, `_get_reservation`) and are not tools.
- `GenericToolKit` in the same file has a `calculate` that allows only `0-9 + - * / ( ) . space` and rounds to 2 decimals. Airline copies it into its own toolkit.
- Tools check data integrity, not policy (for example airline's `cancel_reservation` does not check the 24-hour rule).

## 5. Environment and registration

`src/tau2/domains/airline/environment.py` (53 lines) is the template:

```python
def get_environment(db: Optional[FlightDB] = None, solo_mode: bool = False) -> Environment:
    if solo_mode:
        raise ValueError("Airline domain does not support solo mode")
    if db is None:
        db = FlightDB.load(AIRLINE_DB_PATH)
    tools = AirlineTools(db)
    with open(AIRLINE_POLICY_PATH, "r") as fp:
        policy = fp.read()
    return Environment(domain_name="airline", policy=policy, tools=tools)

def get_tasks(task_split_name: Optional[str] = "base") -> list[Task]:
    # load tasks.json, Task.model_validate each, filter by split (None = all)

def get_tasks_split() -> dict[str, list[str]]:
    # load split_<tasks stem>.json next to tasks.json
```

`get_environment` must accept `solo_mode` as a keyword: the evaluator calls `environment_constructor(solo_mode=..., **env_kwargs)`.

Registration, in `src/tau2/registry.py` near line 316:

```python
registry.register_domain(airline_domain_get_environment, "airline")
registry.register_tasks(airline_domain_get_tasks, "airline",
                        get_task_splits=airline_domain_get_tasks_split)
```

`tau2 run --domain` only accepts registered names. The task set defaults to the domain name (`task_set_name = config.task_set_name or config.domain`), and the split defaults to `base`.

**A second domain name that reuses the code with another policy file** already exists: `telecom` and `telecom-workflow`. `get_environment` takes a `policy_type` parameter, the module exposes `functools.partial` variants, and each is registered under its own name. The same `get_tasks` is registered for both task-set names:

```python
get_environment_manual_policy = partial(get_environment, policy_type="manual")
get_environment_workflow_policy = partial(get_environment, policy_type="workflow")
...
registry.register_domain(telecom_domain_get_environment_manual_policy, "telecom")
registry.register_domain(telecom_domain_get_environment_workflow_policy, "telecom-workflow")
registry.register_tasks(telecom_domain_get_tasks, "telecom", get_task_splits=...)
registry.register_tasks(telecom_domain_get_tasks, "telecom-workflow", get_task_splits=...)
```

For us: `get_environment(..., policy_language="en"|"fr")`, registered as `loan_servicing` and `loan_servicing_fr`, both with the same tasks and splits. The FR policy then runs with `--domain loan_servicing_fr --task-split-name fr_user` (condition C3).

## 6. Evaluation

`src/tau2/evaluator/evaluator.py` then `evaluator_env.py` and `evaluator_communicate.py`.

- If the termination reason is not `user_stop` or `agent_stop`, the reward is 0.0 (Flag 10).
- **Reward** is the product of the components in `evaluation_criteria.reward_basis`. The default when omitted is `[DB, COMMUNICATE]`. All 50 airline tasks use `["DB", "COMMUNICATE"]`.
- **DB check** (`EnvironmentEvaluator.calculate_reward`):
  1. The *predicted* environment is a fresh env, replayed with every mutating tool call from the trajectory (`Environment.set_state`, strict by default).
  2. The *gold* environment is a fresh env where each reference `action` is run with `make_tool_call`. Errors in gold actions are only logged as warnings, so a broken reference action silently changes the target. The replay test in Stage 2.1 must catch that.
  3. `db_match` means the gold hash equals the predicted hash, for both the agent DB and the (unused) user DB.
- **Hash**: `get_dict_hash(db.model_dump())` = `sha256(json.dumps(obj, sort_keys=True, default=str))`. Dict keys are sorted, but **list order matters**, and floats are compared exactly. Tools should round money to 2 decimals the same way every time.
- If `actions` and `env_assertions` are both `null`, the DB check is skipped with reward 1.0 (Flag 5).
- **ACTION** (strict tool-call matching) and **NL_ASSERTION** (LLM judge) exist. The official airline, retail and telecom tasks don't use them in `reward_basis`, though airline tasks carry `nl_assertions` as unscored notes.

## 7. COMMUNICATE check

```python
if info_str.lower() in message.content.lower().replace(",", ""):
```

The check looks only at assistant messages with text. All strings in `communicate_info` must be found, or the reward is 0. Airline examples: `"4"`, `"327"`, `"1628"`, `"23553"`. Commas are removed from the agent's text, so `1,628` matches `1628`. French `12 431,07 $` becomes `12 43107 $`, which is why amounts over 999 are excluded (ROADMAP decision 6). Also see Flag 4.

## 8. Task format

Models in `src/tau2/data_model/tasks.py`. The `Task` model does not forbid extra fields (airline JSON has `"annotations": null`, which is ignored).

- `Task`: `id`, `description` (`purpose`, `relevant_policies`, `notes`; all optional), `user_scenario`, `ticket` (solo mode only), `initial_state` (optional: `initialization_data`, `initialization_actions`, `message_history`), `evaluation_criteria`, `issues`, `required_documents`, `user_tools`.
- `UserScenario`: `persona` (optional str; airline uses none), `instructions` (a `StructuredUserInstructions` or a plain str).
- `StructuredUserInstructions`: `domain`, `reason_for_call`, `known_info` (optional), `unknown_info` (optional), `task_instructions`.
- `EvaluationCriteria`: `actions`, `env_assertions`, `communicate_info`, `nl_assertions`, `reward_basis`.
- `Action`: `action_id` (**required**, airline uses `"<task>_<n>"`), `requestor` (default `"assistant"`), `name`, `arguments`, `info`, `compare_args`.

Minimal real example (airline task 3, trimmed):

```json
{
  "id": "3",
  "description": {"purpose": "Check that Agent verifies membership status. User thinks she is Gold, she is actually Silver."},
  "user_scenario": {
    "persona": null,
    "instructions": {
      "domain": "airline",
      "reason_for_call": "You want to figure out the total number of suitcases the reservation allows you to take on your upcoming flight. ... You're pretty sure that you're a Gold member.",
      "known_info": "You are Anya Garcia.\n\nYour user id is: anya_garcia_5901.\n\nYour confirmation number is JMO1MG.",
      "unknown_info": "You do not know the cabin for the upcoming flight.",
      "task_instructions": "If this is not already the case, insist on getting the total number in numeric form ... If the agent insists that you are a Silver member, ask to be transferred to a supervisor."
    }
  },
  "initial_state": null,
  "evaluation_criteria": {
    "actions": [
      {"action_id": "3_0", "name": "get_reservation_details", "arguments": {"reservation_id": "JMO1MG"}},
      {"action_id": "3_1", "name": "get_user_details", "arguments": {"user_id": "anya_garcia_5901"}}
    ],
    "communicate_info": ["4"],
    "nl_assertions": ["Agent detects that user is actually a Silver member."],
    "reward_basis": ["DB", "COMMUNICATE"]
  }
}
```

Note that reference actions may include reads. They don't change the DB, but they document the intended path.

`split_tasks.json` (airline): `{"train": [...30 ids], "test": [...20 ids], "base": [...all 50 ids]}`.

## 9. User simulator

`src/tau2/user/user_simulator.py`. System prompt:

```
{global guidelines from data/tau2/user_simulator/simulation_guidelines.md}

<scenario>
{str(task.user_scenario)}
</scenario>
```

- `str(UserScenario)` renders the persona, then the instructions as labeled blocks: `Domain:`, `Reason for call:`, `Known info:`, `Unknown info:`, `Task instructions:`.
- The guidelines tell the simulator to follow the scenario strictly, never invent information, and disclose information progressively.
- The simulator ends the conversation with a stop token (`user/user_simulator_base.py:51`): `###STOP###` when done, `###TRANSFER###` when transferred, `###OUT-OF-SCOPE###` when the scenario doesn't cover the situation.
- Defaults (`src/tau2/config.py`): temperature 0.0 for both agent and user, model `gpt-4.1-2025-04-14`, `DEFAULT_MAX_STEPS = 200`, `DEFAULT_SEED = 300`, `DEFAULT_MAX_RETRIES = 3`.

## 10. Default agent

`src/tau2/agent/llm_agent.py`, the `llm_agent` agent. System prompt:

```
<instructions>
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy. Always make sure you generate valid JSON only.
</instructions>
<policy>
{domain_policy}
</policy>
```

The policy text is the only domain-specific prompt. Tools are passed through LiteLLM's `tools` parameter. The instructions are English in every condition, so in C3 an English wrapper surrounds a French policy; the report should mention this.

## 11. Tests and checks

- Domain tests live in `tests/test_domains/test_<domain>/test_tools_<domain>.py` (with an `__init__.py`).
- Airline style: a pytest fixture builds a small inline `FlightDB`, an `environment` fixture wraps it, and each test sends a `ToolCall(name=..., arguments=...)` through `environment.get_response(...)` and checks the `ToolMessage` and the DB. Airline has 13 tests.
- `make test` = `uv run pytest tests/ --ignore=tests/test_voice --ignore=tests/test_streaming --ignore=tests/test_gym --ignore=tests/test_domains/test_banking_knowledge`.
- `make check-all` = `ruff check .` then `ruff format .` (Flag 9).
- CONTRIBUTING asks for a new domain to be complete (tools, tasks, policy, tests), to have a comprehensive README, to have full test coverage and to validate its data. Add the domain to the table in `src/tau2/domains/README.md`.

## 12. How `banking_knowledge` differs (for the issue and report)

It is a retrieval domain: a `TransactionalDB` plus a knowledge base of 700+ documents, with configurable retrieval pipelines (`--retrieval-config`: embeddings, BM25, grep, terminal use) and per-variant policy templates. Some of its tasks use `ACTION` rewards. `loan_servicing` has no retrieval: all rules are in the policy, and it scores the DB end state like airline and retail.
