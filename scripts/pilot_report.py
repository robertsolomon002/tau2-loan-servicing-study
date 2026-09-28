"""Summarize a tau2 run of the loan_servicing tasks (Stage 2.2 pilot).

Usage:
    python scripts/pilot_report.py RESULTS_JSON [--show TASK_ID ...]

Prints one row per simulation (reward, DB and COMMUNICATE results, termination
reason, write tools called vs reference, cost), per-category success, the list
of tasks never solved, and optionally full transcripts of chosen tasks.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import study_env  # noqa: F401  (sets TAU2_DATA_DIR; must come before tau2 imports)
from task_specs import SPECS

from tau2.domains.loan_servicing.tools import LoanServicingTools
from tau2.environment.toolkit import ToolType

WRITE_TOOLS = {
    name
    for name in LoanServicingTools(None).tools
    if LoanServicingTools(None).tool_type(name) == ToolType.WRITE
}
CATEGORY = {f"ls_{s.num:03d}_en": s.category for s in SPECS}


def write_calls(sim: dict) -> list[str]:
    calls = []
    for m in sim["messages"]:
        if m["role"] == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                if tc["name"] in WRITE_TOOLS:
                    args = ",".join(str(v) for v in tc["arguments"].values())
                    calls.append(f"{tc['name']}({args})")
    return calls


def transcript(sim: dict) -> str:
    lines = []
    for m in sim["messages"]:
        role = m["role"]
        if m.get("tool_calls"):
            for tc in m["tool_calls"]:
                lines.append(f"[{role} TOOL] {tc['name']}({json.dumps(tc['arguments'])})")
        elif role == "tool":
            lines.append(f"    -> {(m.get('content') or '')[:220]}")
        else:
            lines.append(f"[{role}] {(m.get('content') or '').strip()}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    parser.add_argument("--show", nargs="*", default=[])
    args = parser.parse_args()
    data = json.load(open(args.results, encoding="utf-8"))
    tasks = {t["id"]: t for t in data["tasks"]}

    rows = []
    by_task: dict[str, list[float]] = defaultdict(list)
    infra = 0
    cost = 0.0
    for sim in sorted(data["simulations"], key=lambda s: (s["task_id"], s["trial"])):
        tid = sim["task_id"]
        info = sim.get("reward_info") or {}
        term = sim["termination_reason"]
        cost += (sim.get("agent_cost") or 0) + (sim.get("user_cost") or 0)
        if term == "infrastructure_error":
            infra += 1
            rows.append(f"{tid} t{sim['trial']} INFRA")
            continue
        reward = info.get("reward", 0.0)
        by_task[tid].append(reward)
        db = (info.get("db_check") or {}).get("db_match")
        comm = [c["met"] for c in (info.get("communicate_checks") or [])]
        ref = [a["name"] for a in tasks[tid]["evaluation_criteria"]["actions"]]
        rows.append(
            f"{tid} t{sim['trial']} r={reward:.0f} db={db} comm={comm} {term} "
            f"calls={write_calls(sim)} ref={ref}"
        )
    print("\n".join(rows))

    print("\nPer category (pass rate over evaluated simulations):")
    cat: dict[str, list[float]] = defaultdict(list)
    for tid, rewards in by_task.items():
        cat[CATEGORY.get(tid, "?")].extend(rewards)
    for name, rewards in cat.items():
        print(f"  {name:18s} {sum(rewards):.0f}/{len(rewards)}")
    evaluated = [r for rs in by_task.values() for r in rs]
    print(
        f"\nOverall: {sum(evaluated):.0f}/{len(evaluated)} "
        f"(pass^1 {sum(evaluated) / max(1, len(evaluated)):.2f}); "
        f"infra errors {infra}; reported cost ${cost:.3f}"
    )
    never = sorted(t for t, rs in by_task.items() if rs and max(rs) == 0)
    print(f"Never solved ({len(never)}): {', '.join(never)}")
    missing = sorted(set(tasks) - set(by_task))
    if missing:
        print(f"No evaluated simulation ({len(missing)}): {', '.join(missing)}")

    for tid in args.show:
        for sim in data["simulations"]:
            if sim["task_id"] == tid:
                print(f"\n===== {tid} trial {sim['trial']} =====")
                print(transcript(sim))
                print("reward_info:", json.dumps(sim.get("reward_info"))[:600])


if __name__ == "__main__":
    main()
