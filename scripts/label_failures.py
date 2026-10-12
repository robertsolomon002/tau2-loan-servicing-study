"""Blind labelling of the failure-review sample (Stage 5.2, Rob).

Shows each of the 40 sampled failed conversations in the terminal: the task,
what the customer was told to do, the scoring checks, the agent's write calls
and the transcript. You pick the primary cause (and the policy rule, if any)
and say whether the customer simulator made a major error. Only after you
answer is Claude's label shown, so your label stays independent; you can add
a comment then. Every answer is saved immediately to
data/failure_labels_rob.json, so you can quit at any time and resume.

Usage (from the study repo):
    uv run python scripts/label_failures.py            # label, resuming
    uv run python scripts/label_failures.py --redo 5   # redo conversation 5
    uv run python scripts/label_failures.py --agreement
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.failures import (
    CAUSES,
    DIGESTS,
    KAPPA_BAR,
    LABELS,
    ROB_LABELS,
    agreement,
    failed,
    load_labels,
    review_sample,
)

# Rob chooses among the judgement causes; model-output failures are not sampled.
CHOICES = {str(i): c for i, c in enumerate(CAUSES, 1) if c != "model_output"}
CHOICES = {("0" if k == "10" else k): v for k, v in CHOICES.items()}
AGENT_CHARS = 700  # long agent messages are shortened; the customer's are not

os.system("")  # enables ANSI colours in the Windows console
BOLD, DIM, CYAN, GREEN, YELLOW, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[0m",
)


def ask(prompt: str, choices: set[str] | None = None) -> str:
    while True:
        answer = input(f"{YELLOW}{prompt}{RESET} ").strip()
        if choices is None or answer.lower() in choices:
            return answer if choices is None else answer.lower()
        print(f"  Please type one of: {', '.join(sorted(choices))}")


def save(answers: dict) -> None:
    ROB_LABELS.write_text(
        json.dumps(answers, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def show(key: str) -> str:
    """The digest, coloured: customer lines highlighted, tool results dimmed.
    The model is hidden, so the label judges the behaviour only."""
    text = (DIGESTS / f"{key}.md").read_text(encoding="utf-8")
    text = re.sub(r"^Model \S+, ", "", text.split("\n", 1)[1], count=1)
    out, style = [], ""
    for line in text.splitlines():
        if line.startswith("## "):
            style = ""
            out.append(f"{BOLD}{line}{RESET}")
            continue
        if re.match(r"\[\d+\] USER:", line):
            style = CYAN + BOLD
        elif re.match(r"\[\d+\] AGENT:", line):
            style = ""
            if len(line) > AGENT_CHARS:
                line = line[:AGENT_CHARS] + " [...]"
        elif re.match(r"\[\d+\]   (<-|->)", line):
            style = DIM
        out.append(f"{style}{line}{RESET}" if style else line)
    return "\n".join(out)


def label_one(n: int, total: int, key: str, claude: dict) -> dict:
    print("\n" * 2 + "=" * 100)
    print(f"{BOLD}[{n}/{total}]{RESET}")
    print("=" * 100)
    print(show(key))
    print("-" * 100)
    for k, cause in CHOICES.items():
        print(f"  {k}. {cause}: {CAUSES[cause]}")
    choice = ask("Primary cause [0-9], [s]kip, [q]uit?", set(CHOICES) | {"s", "q"})
    if choice in {"s", "q"}:
        return {"_action": choice}
    answer = {"cause": CHOICES[choice]}
    answer["rule"] = ask("Policy rule id (e.g. F2, T1; Enter for none):").upper()
    answer["sim_major"] = (
        ask("Did the customer simulator make a major error? [y/n]", {"y", "n"}) == "y"
    )
    print("-" * 100)
    print(f"{BOLD}Claude's label:{RESET}")
    lab = claude[key]
    print(
        f"{GREEN}  {lab['cause']} {lab['rule']} (message {lab['turn']}), "
        f"simulator major error: {lab['sim_major']}\n  {lab['explanation']}{RESET}"
    )
    answer["comment"] = ask("Any comment (optional, Enter to skip):")
    return answer


def print_agreement(sample: list[str], claude: dict, answers: dict) -> None:
    res = agreement(sample, claude, answers)
    if not res["labelled"]:
        print("No answers yet.")
        return
    n = res["labelled"]
    print(f"\n{BOLD}Agreement on {n} of {len(sample)} conversations{RESET}")
    print(f"  Same primary cause: {res['agree']}/{n} ({100 * res['agree'] / n:.0f}%)")
    print(f"  Cohen's kappa: {res['kappa']:.2f} (bar {KAPPA_BAR})")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--redo", type=int, help="relabel conversation number N")
    parser.add_argument("--agreement", action="store_true")
    args = parser.parse_args()

    if not DIGESTS.exists():
        sys.exit("Run `uv run python -m analysis.failures digests` first.")
    claude = load_labels(LABELS)
    answers = load_labels(ROB_LABELS)
    sample = review_sample(failed())
    if args.agreement:
        print_agreement(sample, claude, answers)
        return
    todo = (
        [sample[args.redo - 1]]
        if args.redo
        else [k for k in sample if k not in answers]
    )
    if not todo:
        print("All conversations are labelled.")
    for key in todo:
        result = label_one(sample.index(key) + 1, len(sample), key, claude)
        if result.get("_action") == "q":
            break
        if result.get("_action") == "s":
            continue
        answers[key] = result
        save(answers)
    print_agreement(sample, claude, answers)


if __name__ == "__main__":
    main()
