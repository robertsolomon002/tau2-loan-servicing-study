"""Failure classification helpers (Stage 5.2).

Every failed conversation of the main runs (reward below 1, or a model-output
failure counted as 0 under plan Section 7 rule 2) gets one label from the
ROADMAP Section 5 taxonomy:
- a primary cause (`CAUSES`),
- the policy rule involved (DOMAIN_SPEC Section 4 ids, or "" if none),
- the message index in the transcript where it went wrong,
- a one-sentence explanation,
- whether a major user-simulator error occurred (plan Section 7 rule 4(b)).

Claude labels the conversations in Claude Code (no API spend) from the digests
written by `digests`: the task, the reference actions, the scoring checks, the
agent's write calls and a condensed transcript. Labels live in
`data/failure_labels.json`. Rob labels a random sample of 40 blind
(`scripts/label_failures.py`, `data/failure_labels_rob.json`), and Cohen's
kappa on the primary cause decides whether the classifier's proportions are
reported (ROADMAP 5.2: kappa at least 0.6).

Model-output failures (an empty agent message, which tau2 rejects) need no
judgement: they are labelled `model_output` automatically and are not in
Rob's sample.

Usage (from the study repo):
    uv run python -m analysis.failures digests   # write the digests
    uv run python -m analysis.failures status    # labelled / unlabelled
    uv run python -m analysis.failures sample    # the 40 keys for Rob
    uv run python -m analysis.failures kappa     # agreement with Rob
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import pandas as pd
from task_specs import SPECS

from analysis.load import RAW, REPO, load

DIGESTS = REPO / "results" / "raw" / "failures"
LABELS = REPO / "data" / "failure_labels.json"
ROB_LABELS = REPO / "data" / "failure_labels_rob.json"
SAMPLE_SIZE = 40
SEED = 2026
KAPPA_BAR = 0.6

# ROADMAP Section 5 taxonomy, plus `model_output` for plan Section 7 rule 2.
CAUSES = {
    "verification": "skipped or wrong identity verification or authorization",
    "no_confirmation": "acted without the customer's explicit confirmation",
    "rule_misapplied": "a policy rule misapplied (name the rule)",
    "wrong_arguments": "right action, wrong tool arguments",
    "missed_transfer": "should have transferred and did not",
    "unnecessary_transfer": "transferred when it should not have",
    "wrong_info": "communicated wrong or missing information (e.g. no reference)",
    "language_mismatch": "replied in the wrong language and that caused the failure",
    "user_sim_error": "the user simulator broke the scenario",
    "task_ambiguity": "the task or policy allows the agent's reading",
    "model_output": "the agent model returned an empty message (automatic)",
}
WRITE_TOOLS = {
    "make_payment",
    "cancel_scheduled_payment",
    "enable_autopay",
    "disable_autopay",
    "change_due_date",
    "waive_late_fee",
    "enroll_hardship_plan",
    "update_email",
    "update_phone",
    "send_document",
    "transfer_to_human_agents",
}
SPEC_BY_NUM = {s.num: s for s in SPECS}
RESULT_CHARS = 300


def key(row) -> str:
    return f"{row.cell}__{row.task_id}__t{row.trial}"


def failed(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Finished conversations that did not succeed, model failures included."""
    df = load() if df is None else df
    finished = df[df["status"].isin(["done", "model_failure"])]
    out = finished[~finished["success"].astype(bool)].copy()
    out["key"] = [key(r) for r in out.itertuples()]
    return out.set_index("key")


def _args(arguments: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in arguments.items())


def transcript(sim: dict) -> list[str]:
    """Numbered transcript: [i] is the index in tau2's `messages` list."""
    lines = []
    for i, m in enumerate(sim.get("messages") or []):
        role = m["role"]
        if role == "assistant":
            if m.get("content"):
                lines.append(f"[{i}] AGENT: {m['content']}")
            for tc in m.get("tool_calls") or []:
                mark = " **WRITE**" if tc["name"] in WRITE_TOOLS else ""
                lines.append(f"[{i}]   -> {tc['name']}({_args(tc['arguments'])}){mark}")
        elif role == "tool":
            err = " ERROR" if m.get("error") else ""
            text = str(m.get("content"))
            if len(text) > RESULT_CHARS:
                text = text[:RESULT_CHARS] + " ..."
            lines.append(f"[{i}]   <-{err} {text}")
        elif m.get("content"):
            lines.append(f"[{i}] USER: {m['content']}")
    return lines


def write_calls(sim: dict) -> list[str]:
    """The agent's write calls, each with whether the tool accepted it."""
    results = {m.get("id"): m for m in sim.get("messages") or [] if m["role"] == "tool"}
    out = []
    for i, m in enumerate(sim.get("messages") or []):
        for tc in m.get("tool_calls") or []:
            if tc["name"] in WRITE_TOOLS:
                res = results.get(tc.get("id")) or {}
                status = "tool error" if res.get("error") else "ok"
                out.append(f"[{i}] {tc['name']}({_args(tc['arguments'])}): {status}")
    return out


def scoring(sim: dict) -> list[str]:
    info = sim.get("reward_info") or {}
    lines = [f"reward {info.get('reward')}, breakdown {info.get('reward_breakdown')}"]
    db = info.get("db_check") or {}
    lines.append(f"DB match: {db.get('db_match')}")
    for ac in info.get("action_checks") or []:
        a = ac["action"]
        mark = "matched" if ac["action_match"] else "NOT matched"
        lines.append(f"reference {a['name']}({_args(a['arguments'])}): {mark}")
    for cc in info.get("communicate_checks") or []:
        lines.append(f"communicate {cc['info']}: {'met' if cc['met'] else 'NOT met'}")
    return lines


def model_failure_error(row) -> str:
    path = RAW / row.cell / "attempts.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if (
            rec["task_id"] == row.task_id
            and rec["trial"] == row.trial
            and rec["outcome"] == "model_failure"
        ):
            return rec.get("error", "")
    return ""


def digest(row) -> str:
    """Everything the classifier needs for one failed conversation."""
    spec = SPEC_BY_NUM[row.task]
    sim_path = RAW / row.cell / "sims" / f"{row.task_id}__t{row.trial}.json"
    sim = json.loads(sim_path.read_text(encoding="utf-8"))
    ref = [f"{name}({_args(a)})" for name, a in spec.actions] or ["none (no change)"]
    parts = [
        f"# {row.Index}",
        (
            f"Model {row.model}, condition {row.condition}, task {row.task} "
            f"({spec.category}{', hard' if spec.hard else ''}), trial {row.trial}, "
            f"status {row.status}"
        ),
        f"Rules tested: {', '.join(spec.rules)}",
        f"Purpose: {spec.purpose}",
        f"Expected outcome: {spec.outcome}",
        "Reference actions: " + "; ".join(ref),
        f"Must communicate: {', '.join(spec.communicate) or 'nothing'}",
        "",
        "## User scenario (English spec; FR tasks are its translation)",
        f"Reason: {spec.reason}",
        f"Instructions: {spec.instructions}",
        f"Known extra info: {' | '.join(spec.known) or '-'}",
        "",
        "## Scoring",
        *scoring(sim),
        "",
        "## Agent write calls",
        *(write_calls(sim) or ["none"]),
    ]
    if row.status == "model_failure":
        parts += ["", "## Model failure", model_failure_error(row)]
    parts += ["", "## Transcript", *transcript(sim)]
    return "\n".join(parts) + "\n"


def write_digests(fails: pd.DataFrame) -> None:
    DIGESTS.mkdir(parents=True, exist_ok=True)
    for row in fails.itertuples():
        (DIGESTS / f"{row.Index}.md").write_text(digest(row), encoding="utf-8")
    index = fails[["model", "condition", "task", "trial", "status"]]
    index.to_csv(DIGESTS / "index.csv")
    print(f"{len(fails)} digests in {DIGESTS}")


def load_labels(path: Path = LABELS) -> dict[str, dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_labels(labels: dict[str, dict], path: Path = LABELS) -> None:
    text = json.dumps(dict(sorted(labels.items())), ensure_ascii=False, indent=1)
    path.write_text(text + "\n", encoding="utf-8")


def auto_label(fails: pd.DataFrame, labels: dict[str, dict]) -> dict[str, dict]:
    """Label the model-output failures, which need no judgement."""
    for k, row in fails[fails["status"] == "model_failure"].iterrows():
        labels.setdefault(
            k,
            {
                "cause": "model_output",
                "rule": "",
                "turn": None,
                "explanation": "The agent model returned an empty message, which "
                "tau2 rejects; counted as a failure (plan Section 7 rule 2).",
                "sim_major": False,
            },
        )
    return labels


def validate(labels: dict[str, dict]) -> list[str]:
    problems = []
    for k, lab in labels.items():
        if lab.get("cause") not in CAUSES:
            problems.append(f"{k}: unknown cause {lab.get('cause')!r}")
        if lab.get("cause") == "rule_misapplied" and not lab.get("rule"):
            problems.append(f"{k}: rule_misapplied needs a rule")
        if not isinstance(lab.get("sim_major"), bool):
            problems.append(f"{k}: sim_major must be true or false")
        if not lab.get("explanation"):
            problems.append(f"{k}: no explanation")
    return problems


def review_sample(fails: pd.DataFrame) -> list[str]:
    """40 failures for Rob, drawn at random (fixed seed) from those that need
    judgement (model-output failures excluded)."""
    keys = sorted(fails.index[fails["status"] == "done"])
    return sorted(random.Random(SEED).sample(keys, SAMPLE_SIZE))


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / n**2
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def agreement(sample: list[str], ours: dict, rob: dict) -> dict:
    done = [k for k in sample if k in rob]
    a = [ours[k]["cause"] for k in done]
    b = [rob[k]["cause"] for k in done]
    return {
        "labelled": len(done),
        "agree": sum(x == y for x, y in zip(a, b)),
        "kappa": cohen_kappa(a, b) if done else float("nan"),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["digests", "status", "sample", "kappa"])
    args = parser.parse_args(argv)
    fails = failed()
    labels = auto_label(fails, load_labels())
    if args.command == "digests":
        write_digests(fails)
        save_labels(labels)
    elif args.command == "status":
        todo = [k for k in fails.index if k not in labels]
        print(f"{len(fails)} failures, {len(labels)} labelled, {len(todo)} to do")
        for p in validate(labels):
            print("PROBLEM", p)
        print(Counter(lab["cause"] for lab in labels.values()).most_common())
    elif args.command == "sample":
        print("\n".join(review_sample(fails)))
    else:
        print(agreement(review_sample(fails), labels, load_labels(ROB_LABELS)))


if __name__ == "__main__":
    main()
