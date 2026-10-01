"""Cost and reliability pilot for the agent models (Stage 4.1).

Runs 5 tasks in C1 (EN policy, EN user) and C2 (EN policy, FR user), 1 trial,
for every candidate agent model, with the fixed user simulator gpt-5.4-mini
(Stage 3.4). Measures cost per conversation, tokens, time, tool-call errors,
provider failures (rate limits), and the agent's language adherence, so that
docs/EXPERIMENT_PLAN.md can fix the final model list and budget.

Usage:
    python scripts/cost_pilot.py plan [CANDIDATE...]    # projected cost
    python scripts/cost_pilot.py run [CANDIDATE...]     # resumable, capped
    python scripts/cost_pilot.py retry [CANDIDATE...]   # rerun infra errors
    python scripts/cost_pilot.py report                 # metrics CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import study_env
from user_sim_eval import classify, user_turns

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "results" / "raw" / "stage4_1"
METRICS_CSV = REPO / "results" / "cost_pilot_metrics.csv"
SIMULATIONS = study_env.FORK / "data" / "simulations"

# Information with a read-out id (1), two writes in order (18), a hardship
# plan (26), a transfer (36), and a hard multi-request that small models fail
# (46). Only 18 was also in the Stage 3.3 sample.
TASK_NUMS = [1, 18, 26, 36, 46]
USER = "gpt-5.4-mini"
CONDITIONS = {
    "C1": ("loan_servicing", "en_user", "en"),
    "C2": ("loan_servicing", "fr_user", "fr"),
}

# name: (LiteLLM model id, tier, input $/1M, output $/1M).
# Prices checked 2026-09-30 in OpenRouter's models API
# (https://openrouter.ai/api/v1/models); gpt-5.4-mini in OpenAI's pricing docs
# on 2026-09-28 (same as OpenRouter's listing). Gemini direct is the free tier.
CANDIDATES: dict[str, tuple[str, str, float, float]] = {
    "gemini-flash-lite": ("gemini/gemini-3.1-flash-lite", "free", 0.0, 0.0),
    "qwen": ("openrouter/qwen/qwen3.8-27b:free", "free", 0.0, 0.0),
    "gemma": ("openrouter/google/gemma-4-31b-it:free", "free", 0.0, 0.0),
    "nemotron-super": (
        "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "free",
        0.0,
        0.0,
    ),
    "nemotron-ultra": (
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
        "free",
        0.0,
        0.0,
    ),
    "deepseek-flash": ("openrouter/deepseek/deepseek-v4-flash", "open", 0.079, 0.157),
    "mini": ("gpt-5.4-mini", "cheap", 0.75, 4.50),
    "haiku": ("openrouter/anthropic/claude-haiku-4.5", "cheap", 1.00, 5.00),
    "gemini-3.5-flash-lite": (
        "openrouter/google/gemini-3.5-flash-lite",
        "cheap",
        0.30,
        2.50,
    ),
    "sonnet": ("openrouter/anthropic/claude-sonnet-5.5", "frontier", 2.00, 10.00),
    "gemini-pro": ("openrouter/google/gemini-3.1-pro-preview", "frontier", 2.00, 12.00),
}

# Worst case per conversation, from Stage 3.3 (mini agent: at most 56k input
# and 566 output tokens), with output raised to 3k for models that think.
WORST_IN, WORST_OUT = 56_000, 3_000
USER_PER_CONV = 0.0045  # mini as user, Stage 3.3 (upper end)
CAP = 5.00


def cell_name(candidate: str, condition: str) -> str:
    return f"pilot41_{candidate}_{condition}"


def task_ids(lang: str) -> list[str]:
    return [f"ls_{n:03d}_{lang}" for n in TASK_NUMS]


def per_conv_worst(candidate: str) -> float:
    _, _, p_in, p_out = CANDIDATES[candidate]
    return (WORST_IN * p_in + WORST_OUT * p_out) / 1e6 + USER_PER_CONV


def upper_bound(sim: dict, candidate: str) -> float:
    """Agent cost from tokens at list price, ignoring any cache discount."""
    _, _, p_in, p_out = CANDIDATES[candidate]
    usage = [
        m["usage"]
        for m in sim["messages"]
        if m["role"] == "assistant" and m.get("usage")
    ]
    tokens_in = sum(u.get("prompt_tokens") or 0 for u in usage)
    tokens_out = sum(u.get("completion_tokens") or 0 for u in usage)
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


def attempts(candidate: str, condition: str) -> list[list[dict]]:
    """Every saved attempt of one cell: the first run, then the retries."""
    base = cell_name(candidate, condition)
    paths = [RAW / f"{base}.json"] + sorted(RAW.glob(f"{base}_retry*.json"))
    return [
        json.loads(p.read_text(encoding="utf-8"))["simulations"]
        for p in paths
        if p.exists()
    ]


def is_infra(sim: dict) -> bool:
    return sim["termination_reason"] == "infrastructure_error"


def load(candidate: str, condition: str) -> list[dict]:
    """One conversation per task: the last attempt that did not crash for
    infrastructure reasons, or the last crash if every attempt crashed."""
    final: dict[str, dict] = {}
    for sims in attempts(candidate, condition):
        for s in sims:
            if s["task_id"] not in final or not is_infra(s):
                final[s["task_id"]] = s
    return list(final.values())


def spent() -> float:
    """Spend so far in this pilot, over every attempt: the larger of LiteLLM's
    cost and the uncached upper bound for the agent, plus the user simulator."""
    total = 0.0
    for c in CANDIDATES:
        for cond in CONDITIONS:
            for sims in attempts(c, cond):
                for s in sims:
                    total += max(s.get("agent_cost") or 0.0, upper_bound(s, c))
                    total += s.get("user_cost") or 0.0
    return total


def plan(candidates: list[str]) -> float:
    n = len(TASK_NUMS) * len(CONDITIONS)
    total = 0.0
    print(f"{n} conversations per candidate, user {USER}, 1 trial, worst case")
    for c in candidates:
        cost = n * per_conv_worst(c)
        total += cost
        print(f"  {c:22s} {CANDIDATES[c][0]:52s} ${cost:.2f}")
    print(f"Total projected (worst case): ${total:.2f}; stage cap ${CAP:.2f}")
    print(f"Spent so far in this pilot: ${spent():.2f}")
    return total


def run_cell(candidate: str, condition: str, name: str, ids: list[str]) -> None:
    """Run tau2 on some tasks of one cell and copy the results to RAW."""
    model, tier, _, _ = CANDIDATES[candidate]
    domain, split, _ = CONDITIONS[condition]
    # Free tiers, and OpenRouter's new-account limit of 20 requests per minute
    # on Anthropic models, need pauses: tau2 retries a failed conversation.
    retries = (
        ["--max-retries", "4", "--retry-delay", "65"]
        if tier == "free" or "anthropic" in model
        else []
    )
    cmd = [
        "tau2", "run", "--domain", domain, "--task-split-name", split,
        "--agent-llm", model, "--user-llm", USER,
        "--task-ids", *ids, "--num-trials", "1",
        "--max-concurrency", "1", "--save-to", name, "--auto-resume",
        "--log-level", "WARNING", *retries,
    ]  # fmt: skip
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    print(f"Running {name} ...", flush=True)
    subprocess.run(cmd, env=env, check=False, cwd=study_env.FORK)
    src = SIMULATIONS / name / "results.json"
    if src.exists():
        shutil.copy(src, RAW / f"{name}.json")


def run(candidates: list[str]) -> None:
    if plan(candidates) > CAP:
        sys.exit("Projected cost is over the stage cap; not running.")
    RAW.mkdir(parents=True, exist_ok=True)
    for c in candidates:
        for cond, (_, _, lang) in CONDITIONS.items():
            if spent() > CAP:
                sys.exit(f"Stage cap ${CAP:.2f} reached; stopping.")
            run_cell(c, cond, cell_name(c, cond), task_ids(lang))
    print(f"Spent so far in this pilot: ${spent():.2f}")


def retry(candidates: list[str]) -> None:
    """Rerun the conversations that crashed for infrastructure reasons (the
    exclusion rule: rerun, not counted as failures)."""
    for c in candidates:
        for cond in CONDITIONS:
            ids = sorted(s["task_id"] for s in load(c, cond) if is_infra(s))
            if not ids:
                continue
            n = len(ids) * per_conv_worst(c)
            if spent() + n > CAP:
                sys.exit(f"Retrying {c} {cond} could pass the ${CAP:.2f} cap.")
            k = len(attempts(c, cond))
            run_cell(c, cond, f"{cell_name(c, cond)}_retry{k}", ids)
    print(f"Spent so far in this pilot: ${spent():.2f}")


def metrics(candidate: str, condition: str, sims: list[dict]) -> dict:
    lang = CONDITIONS[condition][2]
    done = [s for s in sims if s["termination_reason"] != "infrastructure_error"]
    n = len(done) or 1
    tool_msgs = [[m for m in s["messages"] if m["role"] == "tool"] for s in done]
    agent_turns = [classify(t) for s in done for t in user_turns(s, "assistant")]
    judged = [t for t in agent_turns if t != "short"]
    usage = [
        m["usage"]
        for s in done
        for m in s["messages"]
        if m["role"] == "assistant" and m.get("usage")
    ]
    every = [s for a in attempts(candidate, condition) for s in a]
    litellm_cost = sum(s.get("agent_cost") or 0.0 for s in every)
    return {
        "candidate": candidate,
        "model": CANDIDATES[candidate][0],
        "tier": CANDIDATES[candidate][1],
        "condition": condition,
        "planned": len(TASK_NUMS),
        "completed": len(done),
        "infra_errors_final": len(sims) - len(done),
        "infra_errors_all_attempts": sum(is_infra(s) for s in every),
        "endings": ", ".join(sorted({s["termination_reason"] for s in sims})),
        "reward": round(
            sum((s.get("reward_info") or {}).get("reward") or 0.0 for s in done) / n,
            2,
        ),
        "tool_calls": sum(len(t) for t in tool_msgs),
        "tool_errors": sum(m.get("error") is True for t in tool_msgs for m in t),
        "agent_on_language_pct": round(
            100 * sum(t == lang for t in judged) / len(judged), 1
        )
        if judged
        else None,
        "avg_agent_in_tokens": round(
            sum(u.get("prompt_tokens") or 0 for u in usage) / n
        ),
        "avg_agent_out_tokens": round(
            sum(u.get("completion_tokens") or 0 for u in usage) / n
        ),
        "agent_cost_litellm": round(litellm_cost, 4),
        "agent_cost_upper": round(sum(upper_bound(s, candidate) for s in every), 4),
        "agent_cost_per_conv": round(
            sum(s.get("agent_cost") or 0.0 for s in done) / n, 5
        ),
        "user_cost": round(sum(s.get("user_cost") or 0.0 for s in every), 4),
        "avg_minutes": round(sum(s.get("duration") or 0.0 for s in done) / n / 60, 1),
    }


def report() -> list[dict]:
    rows = [
        metrics(c, cond, sims)
        for c in CANDIDATES
        for cond in CONDITIONS
        if (sims := load(c, cond))
    ]
    if rows:
        with METRICS_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        for r in rows:
            print(r)
    print(f"Spent in this pilot: ${spent():.2f}")
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "run", "retry", "report"])
    parser.add_argument("candidates", nargs="*", default=list(CANDIDATES))
    args = parser.parse_args()
    unknown = set(args.candidates) - set(CANDIDATES)
    if unknown:
        sys.exit(f"Unknown candidates: {sorted(unknown)}")
    if args.command == "plan":
        plan(args.candidates)
    elif args.command == "run":
        run(args.candidates)
    elif args.command == "retry":
        retry(args.candidates)
    else:
        report()


if __name__ == "__main__":
    main()
