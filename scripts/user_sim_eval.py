"""User-simulator validation (Stage 3.3).

Runs the same 10 tasks in English (C1: EN policy, EN user) and Quebec French
(C2: EN policy, FR user) for each candidate user model, with one fixed agent,
then measures what the study needs from a simulator: the language of every
user turn, conversation length, cost, and provider failures. It also writes
one condensed transcript per conversation, which Claude reads to pre-label
simulator errors (data/user_sim_labels.json) for Rob to check.

C2 rather than C3 for the FR runs: an English-policy agent may drift into
English, which is the hardest test of whether the user keeps speaking French.

Usage:
    python scripts/user_sim_eval.py plan               # projected cost
    python scripts/user_sim_eval.py run [CANDIDATE...]  # resumable
    python scripts/user_sim_eval.py report             # metrics + transcripts
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import study_env
from lingua import Language, LanguageDetectorBuilder
from lint_tasks import db_names

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "results" / "raw" / "stage3_3"
METRICS_CSV = REPO / "results" / "user_sim_metrics.csv"
SIMULATIONS = study_env.FORK / "data" / "simulations"

# Chosen to stress the simulator: pushing back (7, 11, 14, 31), two
# verification attempts (33, 42), bundled or ordered requests (18, 22), a
# relative date (48), plus a plain payment (3).
TASK_NUMS = [3, 7, 11, 14, 18, 22, 31, 33, 42, 48]
AGENT = "gpt-5.4-mini"
CANDIDATES = {
    "nano": "gpt-5.4-nano",
    "mini": "gpt-5.4-mini",
    "gemini": "gemini/gemini-3.1-flash-lite",
}
LANGS = {"en": ("loan_servicing", "en_user"), "fr": ("loan_servicing", "fr_user")}

# Per-conversation costs measured in this project (docs/LOG.md, PILOT_2,
# Stage 3.2 smoke tests); prices checked 2026-09-28 in OpenAI's docs
# (nano $0.20/$1.25, mini $0.75/$4.50 per 1M tokens). Gemini is the free tier.
COST_PER_CONV = {"agent": 0.010, "nano": 0.0012, "mini": 0.0045, "gemini": 0.0}
CAP = 4.00
# tau2 opens every conversation with this fixed agent message
# (src/tau2/orchestrator/orchestrator.py:48); the model never generates it.
GREETING = "Hi! How can I help you today?"

DETECTOR = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH, Language.FRENCH
).build()
NOISE = re.compile(
    r"###[A-Z-]+###"  # stop tokens
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"  # emails
    r"|\b[A-Z]{2}-\d{4,6}\b"  # ids
    r"|\b[A-Z]\d[A-Z] ?\d[A-Z]\d\b"  # postal codes
    r"|[\d$€%.,:/-]+"  # numbers, dates, amounts
    r"|[*`_#>]"  # markdown
)


def cell_name(candidate: str, lang: str) -> str:
    return f"user_sim_{candidate}_{lang}"


def task_ids(lang: str) -> list[str]:
    return [f"ls_{n:03d}_{lang}" for n in TASK_NUMS]


# ---------- plan and run ----------


def plan(candidates: list[str]) -> float:
    n = len(TASK_NUMS) * len(LANGS)
    total = 0.0
    print(f"{n} conversations per candidate, agent {AGENT}, 1 trial")
    for c in candidates:
        cost = n * (COST_PER_CONV["agent"] + COST_PER_CONV[c])
        total += cost
        print(f"  {c:7s} {CANDIDATES[c]:30s} projected ${cost:.2f}")
    print(f"Total projected: ${total:.2f} (stage cap ${CAP:.2f})")
    return total


def run(candidates: list[str]) -> None:
    if plan(candidates) > CAP:
        sys.exit("Projected cost is over the stage cap; not running.")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    RAW.mkdir(parents=True, exist_ok=True)
    for c in candidates:
        # The Gemini free tier allows about 15 requests per minute: go slowly
        # and let tau2 retry a failed conversation after a pause.
        retries = ["--max-retries", "4", "--retry-delay", "65"] if c == "gemini" else []
        for lang, (domain, split) in LANGS.items():
            name = cell_name(c, lang)
            cmd = [
                "tau2", "run", "--domain", domain, "--task-split-name", split,
                "--agent-llm", AGENT, "--user-llm", CANDIDATES[c],
                "--task-ids", *task_ids(lang), "--num-trials", "1",
                "--max-concurrency", "1", "--save-to", name,
                "--log-level", "WARNING", *retries,
            ]  # fmt: skip
            print(f"Running {name} ...", flush=True)
            subprocess.run(cmd, env=env, check=False, cwd=study_env.FORK)
            src = SIMULATIONS / name / "results.json"
            if src.exists():
                shutil.copy(src, RAW / f"{name}.json")


# ---------- report ----------


def _names_pattern() -> re.Pattern:
    """Person and bank names from the DB: French names would skew detection."""
    names = sorted(db_names(), key=len, reverse=True)
    return re.compile("|".join(re.escape(n) for n in names))


NAMES = _names_pattern()


def classify(text: str) -> str:
    """'en', 'fr', or 'short' (fewer than two words left to judge)."""
    clean = NOISE.sub(" ", NAMES.sub(" ", text))
    if len(re.findall(r"[^\W\d_]{2,}", clean)) < 2:
        return "short"
    lang = DETECTOR.detect_language_of(clean)
    return {Language.ENGLISH: "en", Language.FRENCH: "fr"}.get(lang, "short")


def user_turns(sim: dict, role: str = "user") -> list[str]:
    """Text turns of one role, without tau2's fixed English greeting."""
    return [
        m["content"]
        for m in sim["messages"]
        if m["role"] == role
        and m.get("content")
        and not m.get("tool_calls")
        and m["content"] != GREETING
    ]


def followed_agent_switch(sim: dict, lang: str) -> bool:
    """The user answered in another language right after the agent did."""
    previous = None
    for m in sim["messages"]:
        if not m.get("content") or m.get("tool_calls") or m["role"] == "tool":
            continue
        current = classify(m["content"])
        if (
            m["role"] == "user"
            and previous not in (None, lang, "short")
            and current == previous
        ):
            return True
        if m["role"] == "assistant":
            previous = current
    return False


def pct(values: list[str], lang: str) -> float | None:
    judged = [v for v in values if v != "short"]
    return (
        round(100 * sum(v == lang for v in judged) / len(judged), 1) if judged else None
    )


def cost(sim: dict, role: str) -> float:
    return sum((m.get("cost") or 0.0) for m in sim["messages"] if m["role"] == role)


def transcript(sim: dict) -> str:
    """A condensed transcript: messages, and tool calls with short results."""
    lines = []
    for m in sim["messages"]:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                args = ", ".join(f"{k}={v}" for k, v in tc["arguments"].items())
                lines.append(f"  [tool] {tc['name']}({args})")
        elif role == "tool":
            lines.append(f"  [result] {str(m.get('content'))[:160]}")
        elif m.get("content"):
            tag = "AGENT" if role == "assistant" else "USER"
            lang = f" ({classify(m['content'])})" if role == "user" else ""
            lines.append(f"{tag}{lang}: {m['content']}")
    return "\n".join(lines)


def report() -> list[dict]:
    rows = []
    (RAW / "transcripts").mkdir(parents=True, exist_ok=True)
    for c, user_model in CANDIDATES.items():
        for lang in LANGS:
            path = RAW / f"{cell_name(c, lang)}.json"
            if not path.exists():
                continue
            sims = json.loads(path.read_text(encoding="utf-8"))["simulations"]
            done = [
                s for s in sims if s["termination_reason"] != "infrastructure_error"
            ]
            turns = [classify(t) for s in done for t in user_turns(s)]
            agent = [classify(t) for s in done for t in user_turns(s, "assistant")]
            rewards = [(s.get("reward_info") or {}).get("reward") or 0.0 for s in done]
            rows.append(
                {
                    "candidate": c,
                    "user_model": user_model,
                    "lang": lang,
                    "planned": len(TASK_NUMS),
                    "completed": len(done),
                    "infra_errors": len(sims) - len(done),
                    "user_turns": len(turns),
                    "short_turns": turns.count("short"),
                    "on_language_pct": pct(turns, lang),
                    "convs_user_followed_agent_switch": sum(
                        followed_agent_switch(s, lang) for s in done
                    ),
                    "agent_on_language_pct": pct(agent, lang),
                    "convs_agent_switched": sum(
                        any(
                            classify(t) not in (lang, "short")
                            for t in user_turns(s, "assistant")
                        )
                        for s in done
                    ),
                    "avg_user_turns": round(len(turns) / len(done), 1)
                    if done
                    else None,
                    "avg_messages": round(
                        sum(len(s["messages"]) for s in done) / len(done), 1
                    )
                    if done
                    else None,
                    "agent_reward": round(sum(rewards) / len(done), 2)
                    if done
                    else None,
                    "user_cost": round(sum(cost(s, "user") for s in sims), 4),
                    "agent_cost": round(sum(cost(s, "assistant") for s in sims), 4),
                    "endings": ", ".join(
                        sorted({s["termination_reason"] for s in sims})
                    ),
                }
            )
            for s in sims:
                out = RAW / "transcripts" / f"{c}_{s['task_id']}.md"
                header = (
                    f"# {c} {s['task_id']} | ending {s['termination_reason']} | "
                    f"reward {(s.get('reward_info') or {}).get('reward')}\n\n"
                )
                out.write_text(header + transcript(s) + "\n", encoding="utf-8")
    if rows:
        with METRICS_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        for r in rows:
            print(r)
    return rows


LABELS = REPO / "data" / "user_sim_labels.json"
REVIEW_DOC = REPO / "docs" / "USER_SIM_REVIEW.md"
# Clean conversations of the recommended simulator on the hardest tasks, added
# to the review so Rob also checks for missed errors (not only flagged ones).
REVIEW_CLEAN = [f"mini/ls_{n:03d}_{lang}" for lang in LANGS for n in (31, 33, 42)]


def load_labels() -> dict[str, list[dict]]:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    return {k: v for k, v in labels.items() if not k.startswith("_")}


def error_summary() -> list[dict]:
    """Simulator errors per candidate and language, from the labels."""
    labels = load_labels()
    rows = []
    for c in CANDIDATES:
        for lang in LANGS:
            keys = [f"{c}/{t}" for t in task_ids(lang)]
            errors = [e for k in keys for e in labels[k]]
            rows.append(
                {
                    "candidate": c,
                    "lang": lang,
                    "convs_with_error": sum(bool(labels[k]) for k in keys),
                    "convs_with_major": sum(
                        any(e["severity"] == "major" for e in labels[k]) for k in keys
                    ),
                    **{
                        t: sum(e["type"] == t for e in errors)
                        for t in (
                            "early_reveal",
                            "contradiction",
                            "wrong_end",
                            "language_switch",
                        )
                    },
                }
            )
    return rows


def review() -> None:
    """Write docs/USER_SIM_REVIEW.md: 10 EN and 10 FR conversations to check."""
    labels = load_labels()
    flagged = [k for k, v in labels.items() if v]
    keys = flagged + [k for k in REVIEW_CLEAN if k not in flagged]
    keys.sort(key=lambda k: (k.endswith("_fr"), k))
    counts = {lang: sum(k.endswith(f"_{lang}") for k in keys) for lang in LANGS}
    lines = [
        "# User-simulator label review (Stage 3.3, for Rob in 3.4)",
        "",
        (
            "Generated by `scripts/user_sim_eval.py review`; do not edit by hand. "
            f"{counts['en']} EN and {counts['fr']} FR conversations: every one "
            "Claude flagged with a simulator error, plus clean conversations of "
            "the recommended simulator (gpt-5.4-mini) on the three hardest tasks, "
            "to check for missed errors. Only the simulated user is judged, not "
            "the agent. Error types and severities are defined in "
            "`data/user_sim_labels.json`; the user's instructions for each task "
            "are in `docs/TASKS_FR_REVIEW.md`."
        ),
        "",
        (
            "For each conversation, write `agree`, or the label you would give, "
            "after **Rob:**. Claude then computes the agreement."
        ),
        "",
    ]
    for n, key in enumerate(keys, 1):
        c, tid = key.split("/")
        text = (RAW / "transcripts" / f"{c}_{tid}.md").read_text(encoding="utf-8")
        body = text.split("\n", 2)[2]
        header = text.split("\n", 1)[0].lstrip("# ")
        label = "; ".join(
            f"**{e['type']}** ({e['severity']}): {e['note']}" for e in labels[key]
        )
        lines += [
            f"## {n}. {header}",
            "",
            f"**Claude:** {label or 'no simulator error'}",
            "",
            "**Rob:**",
            "",
            "<details><summary>Transcript</summary>",
            "",
            "```text",
            body.strip(),
            "```",
            "",
            "</details>",
            "",
        ]
    REVIEW_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(keys)} conversations to {REVIEW_DOC} ({counts})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "run", "report", "review"])
    parser.add_argument("candidates", nargs="*", default=list(CANDIDATES))
    args = parser.parse_args()
    unknown = set(args.candidates) - set(CANDIDATES)
    if unknown:
        sys.exit(f"Unknown candidates: {sorted(unknown)}")
    if args.command == "plan":
        plan(args.candidates)
    elif args.command == "run":
        run(args.candidates)
    elif args.command == "report":
        report()
        for row in error_summary():
            print(row)
    else:
        review()


if __name__ == "__main__":
    main()
