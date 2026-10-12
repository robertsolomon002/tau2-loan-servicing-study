"""Main-run conversations to a tidy dataframe (Stage 5.1).

One row per planned conversation (model × condition × task × trial), read from
the runner's output in `results/raw/main/` (`docs/RUNNER.md`):
- `<cell>/sims/<task_id>__t<trial>.json`: the finished conversation;
- `<cell>/attempts.jsonl`: every attempt, with its metered cost.

Each conversation's `status` follows plan Section 7:
- `done`: finished; its reward counts.
- `model_failure`: the agent model's own output broke the conversation; it
  counts as a failure (reward 0).
- `missing`: no attempt finished after `max_attempts`; the paired analysis
  drops the task for that model in every condition.
- `pending`: not run yet (the free models are still running).

Plan Amendment 2: OpenRouter withdrew the free Qwen endpoint after Qwen's
second trial, so Qwen is planned with 2 trials (`STOPPED_TRIALS`), and its
unfinished conversations in them are `missing`, not `pending`.

Language columns use the Stage 3.3 detector and cleaning
(`scripts/user_sim_eval.py`): ids, numbers, emails, postal codes, DB names and
markdown are removed, tau2's fixed English greeting and turns with fewer than
two words left are skipped ("short").
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pandas as pd
import study_env
from task_specs import SPECS
from user_sim_eval import GREETING, classify

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "results" / "raw" / "main"
CONFIGS = REPO / "configs" / "main"
RUNNER_TOML = REPO / "configs" / "runner.toml"
PLANTED = REPO / "data" / "planted_cases.json"
DB_PATH = study_env.FORK / "data" / "tau2" / "domains" / "loan_servicing" / "db.json"

CONDITIONS = ["C1", "C2", "C3"]
CUSTOMER_LANG = {"C1": "en", "C2": "fr", "C3": "fr"}
# Plan Section 4.2, from the smallest to the frontier model.
MODELS = ["qwen", "nemotron", "deepseek", "flash_lite", "gemini_pro"]
MODEL_NAMES = {
    "qwen": "Qwen 3.8 27B (free)",
    "nemotron": "Nemotron 3 Ultra (free)",
    "deepseek": "DeepSeek V4 Flash",
    "flash_lite": "Gemini 3.1 Flash-Lite",
    "gemini_pro": "Gemini 3.1 Pro",
}
FRONTIER = "gemini_pro"
# Plan Amendment 2: models stopped early, with the trials they are analyzed on.
STOPPED_TRIALS = {"qwen": 2}

# For the exploratory C1 language-switch analysis (plan Section 6.3): Rob's
# alternative explanation is a French name rather than `preferred_language`.
# The DB generator draws names independently of the language; these are the
# French-Canadian surnames of its pool (`scripts/generate_db.py` LAST_NAMES).
# "Martin" is common in both languages and counts as neither. The list was
# fixed on 2026-10-02, before any result was looked at by name.
QUEBEC_SURNAMES = frozenset(
    {
        "Gagnon", "Roy", "Côté", "Bouchard", "Gauthier", "Morin", "Lavoie",
        "Fortin", "Gagné", "Ouellet", "Pelletier", "Bélanger", "Lévesque",
        "Bergeron", "Leblanc", "Paquette", "Girard", "Simard", "Boucher", "Caron",
    }
)  # fmt: skip
AMBIGUOUS_SURNAMES = frozenset({"Martin"})


def surname_group(last_name: str) -> str:
    if last_name in QUEBEC_SURNAMES:
        return "french"
    if last_name in AMBIGUOUS_SURNAMES:
        return "ambiguous"
    return "other"


def task_table() -> pd.DataFrame:
    """One row per task: category, hard flag, and the loan borrower's record."""
    db = json.loads(DB_PATH.read_text("ascii"))
    planted = json.loads(PLANTED.read_text(encoding="utf-8"))
    rows = []
    for spec in SPECS:
        borrower_id = planted[spec.case]["borrower_ids"][spec.borrower]
        borrower = db["borrowers"][borrower_id]
        rows.append(
            {
                "task": spec.num,
                "category": spec.category,
                "hard": spec.hard,
                "borrower_id": borrower_id,
                "preferred_language": borrower["preferred_language"],
                "surname": borrower["last_name"],
                "surname_group": surname_group(borrower["last_name"]),
            }
        )
    return pd.DataFrame(rows).set_index("task")


def text_turns(sim: dict, role: str) -> list[str]:
    """What one side said to the other: text messages without tool calls.

    An assistant message with tool calls goes to the environment, not to the
    customer, so its text is not a turn the customer sees.
    """
    return [
        m["content"]
        for m in sim.get("messages") or []
        if m["role"] == role
        and m.get("content")
        and not m.get("tool_calls")
        and m["content"] != GREETING
    ]


def conversation_stats(sim: dict, customer_lang: str) -> dict:
    """Language, length and tool counts of one finished conversation."""
    messages = sim.get("messages") or []
    agent_langs = [classify(t) for t in text_turns(sim, "assistant")]
    user_langs = [classify(t) for t in text_turns(sim, "user")]
    stats = {
        "agent_langs": tuple(agent_langs),
        "user_langs": tuple(user_langs),
        # Agent and user messages, without tau2's fixed opening greeting.
        "turns": sum(
            m["role"] in ("assistant", "user") and m.get("content") != GREETING
            for m in messages
        ),
        "tool_calls": sum(
            len(m.get("tool_calls") or []) for m in messages if m["role"] == "assistant"
        ),
        "tool_errors": sum(
            m["role"] == "tool" and bool(m.get("error")) for m in messages
        ),
    }
    for side, langs in (("agent", agent_langs), ("user", user_langs)):
        judged = [x for x in langs if x != "short"]
        stats[f"{side}_judged"] = len(judged)
        stats[f"{side}_in_lang"] = sum(x == customer_lang for x in judged)
        stats[f"{side}_other_lang"] = sum(x != customer_lang for x in judged)
    return stats


def read_attempts(cell_path: Path) -> dict[tuple[str, int], list[dict]]:
    path = cell_path / "attempts.jsonl"
    attempts: dict[tuple[str, int], list[dict]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                attempts.setdefault((rec["task_id"], rec["trial"]), []).append(rec)
    return attempts


def load_cell(
    raw: Path,
    model: str,
    condition: str,
    trials: int,
    max_attempts: int,
    stopped: bool = False,
) -> list[dict]:
    """Rows for every planned conversation of one cell. In a stopped model's
    cell, a conversation that never finished is missing (Amendment 2)."""
    cell = f"{model}_{condition}"
    cell_path = raw / cell
    lang = "en" if condition == "C1" else "fr"
    info_path = cell_path / "cell.json"
    if info_path.exists():
        task_ids = json.loads(info_path.read_text(encoding="utf-8"))["task_ids"]
    else:
        task_ids = [f"ls_{s.num:03d}_{lang}" for s in SPECS]
    attempts = read_attempts(cell_path)
    rows = []
    for task_id in task_ids:
        for trial in range(trials):
            recs = attempts.get((task_id, trial), [])
            # Spend of every attempt, finished or not. The cash account is the
            # OpenAI user simulator; the others pay for the agent.
            costs = [r["cost"] for r in recs]
            row = {
                "model": model,
                "condition": condition,
                "cell": cell,
                "task": int(task_id[3:6]),
                "task_id": task_id,
                "trial": trial,
                "attempts": len(recs),
                "last_attempt": recs[-1]["time"] if recs else None,
                "agent_cost": sum(
                    v for c in costs for k, v in c.items() if k != "cash"
                ),
                "user_cost": sum(c.get("cash", 0.0) for c in costs),
            }
            sim_file = cell_path / "sims" / f"{task_id}__t{trial}.json"
            if sim_file.exists():
                sim = json.loads(sim_file.read_text(encoding="utf-8"))
                failed = (sim.get("info") or {}).get(
                    "runner_outcome"
                ) == "model_failure"
                reward = 0.0 if failed else (sim.get("reward_info") or {})["reward"]
                row |= {
                    "status": "model_failure" if failed else "done",
                    "reward": reward,
                    # tau2's is_successful: a reward of 1 within 1e-6.
                    "success": abs(reward - 1.0) <= 1e-6,
                    "termination": sim.get("termination_reason"),
                }
                if not failed:
                    row |= conversation_stats(sim, CUSTOMER_LANG[condition])
            else:
                failed_attempts = sum(
                    r["outcome"] not in ("done", "model_failure") for r in recs
                )
                row["status"] = (
                    "missing"
                    if stopped or failed_attempts >= max_attempts
                    else "pending"
                )
            rows.append(row)
    return rows


def model_configs(configs: Path = CONFIGS) -> dict[str, dict]:
    out = {}
    for path in sorted(configs.glob("*.toml")):
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        out[cfg["name"]] = cfg
    return out


def load(
    raw: Path = RAW, configs: Path = CONFIGS, runner_toml: Path = RUNNER_TOML
) -> pd.DataFrame:
    """Every planned conversation of the main runs, with task metadata."""
    max_attempts = tomllib.loads(runner_toml.read_text(encoding="utf-8"))[
        "max_attempts"
    ]
    rows = []
    for model, cfg in model_configs(configs).items():
        trials = STOPPED_TRIALS.get(model, cfg["trials"])
        for condition in cfg["conditions"]:
            rows += load_cell(
                raw, model, condition, trials, max_attempts, model in STOPPED_TRIALS
            )
    df = pd.DataFrame(rows)
    df = df.join(task_table(), on="task")
    df["model"] = pd.Categorical(df["model"], categories=MODELS, ordered=True)
    return df.sort_values(["model", "condition", "task", "trial"]).reset_index(
        drop=True
    )


def complete_models(df: pd.DataFrame) -> list[str]:
    """Models with no pending conversation in any condition."""
    pending = df.groupby("model", observed=True)["status"].apply(
        lambda s: (s == "pending").any()
    )
    return [m for m in MODELS if m in pending.index and not pending[m]]
