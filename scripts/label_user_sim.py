"""Interactive labelling of the user-simulator review sample (Stage 3.4, Rob).

Shows each of the 20 review conversations in the terminal: the customer's
instructions, the transcript, and Claude's label. You answer agree or
disagree (and give your own label if you disagree). Every answer is saved
immediately to data/user_sim_labels_rob.json, so you can quit at any time and
pick up where you left off. At the end it prints the agreement with Claude.

Usage (from the study repo):
    uv run python scripts/label_user_sim.py            # label, resuming
    uv run python scripts/label_user_sim.py --redo 5   # redo conversation 5
    uv run python scripts/label_user_sim.py --agreement
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

from lint_tasks import load
from task_specs import END, NO_HUMAN
from task_specs_fr import END_FR, NO_HUMAN_FR
from user_sim_eval import RAW, REPO, load_labels, review_keys

ROB_LABELS = REPO / "data" / "user_sim_labels_rob.json"
TYPES = {
    "1": ("early_reveal", "gives info before it is asked for, or before its trigger"),
    "2": ("contradiction", "says or does something the scenario rules out"),
    "3": ("wrong_end", "ends too early, too late, or with the wrong token"),
    "4": ("language_switch", "leaves the task's language"),
}
AGENT_CHARS = 500  # agent messages are shortened; the customer's are shown in full

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


def load_rob() -> dict:
    if ROB_LABELS.exists():
        return json.loads(ROB_LABELS.read_text(encoding="utf-8"))
    return {}


def save_rob(answers: dict) -> None:
    ROB_LABELS.write_text(
        json.dumps(answers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def instructions(task_id: str, tasks: dict) -> str:
    ins = tasks[task_id]["user_scenario"]["instructions"]
    steps = ins["task_instructions"]
    for tail in (END, END_FR, NO_HUMAN, NO_HUMAN_FR):
        steps = steps.replace(tail, "").strip()
    parts = [
        ("Reason", ins["reason_for_call"]),
        ("Knows", ins["known_info"]),
        ("Doesn't know", ins["unknown_info"]),
        ("Steps", steps),
    ]
    return "\n".join(
        textwrap.fill(f"{label}: {text}", 100, subsequent_indent="    ")
        for label, text in parts
        if text
    )


def transcript(key: str) -> str:
    c, tid = key.split("/")
    text = (RAW / "transcripts" / f"{c}_{tid}.md").read_text(encoding="utf-8")
    out = []
    for line in text.split("\n", 2)[2].splitlines():
        if line.startswith("AGENT:"):
            short = line if len(line) <= AGENT_CHARS else line[:AGENT_CHARS] + " [...]"
            out.append(f"{DIM}{short}{RESET}")
        elif line.startswith("USER"):
            out.append(f"{CYAN}{BOLD}{line}{RESET}")
        elif line.strip().startswith("[tool]"):
            out.append(f"{DIM}{line}{RESET}")
        elif line.strip().startswith("[result]"):
            continue
        else:
            out.append(f"{DIM}{line}{RESET}")
    return "\n".join(out)


def claude_label(errors: list[dict]) -> str:
    if not errors:
        return "no simulator error"
    return "\n".join(f"  - {e['type']} ({e['severity']}): {e['note']}" for e in errors)


def own_label() -> list[dict]:
    """Ask Rob for his own label: zero or more errors."""
    if ask("Is there any simulator error? [y/n]", {"y", "n"}) == "n":
        return []
    errors = []
    while True:
        for k, (name, desc) in TYPES.items():
            print(f"  {k}. {name}: {desc}")
        kind = TYPES[ask("Type [1-4]:", set(TYPES))][0]
        severity = {"m": "major", "n": "minor"}[
            ask("Severity: [m]ajor (could change the outcome) or mi[n]or?", {"m", "n"})
        ]
        note = ask("Short note (optional, Enter to skip):")
        errors.append({"type": kind, "severity": severity, "note": note})
        if ask("Another error in this conversation? [y/n]", {"y", "n"}) == "n":
            return errors


def label_one(n: int, total: int, key: str, tasks: dict, claude: list[dict]) -> dict:
    # The customer model is not shown, so the label judges the behaviour only.
    tid = key.split("/")[1]
    print("\n" * 2 + "=" * 100)
    print(f"{BOLD}[{n}/{total}] {tid}{RESET}")
    print("=" * 100)
    print(f"{BOLD}What the customer was told to do:{RESET}")
    print(instructions(tid, tasks))
    print("-" * 100)
    print(transcript(key))
    print("-" * 100)
    print(f"{BOLD}Claude's label (judging only the customer):{RESET}")
    print(f"{GREEN}{claude_label(claude)}{RESET}")
    print("-" * 100)
    verdict = ask("[a]gree, [d]isagree, [s]kip for now, [q]uit?", {"a", "d", "s", "q"})
    if verdict in {"s", "q"}:
        return {"_action": verdict}
    answer = {"verdict": "agree" if verdict == "a" else "disagree"}
    answer["errors"] = claude if verdict == "a" else own_label()
    answer["comment"] = ask("Any comment (optional, Enter to skip):")
    return answer


def has_error(errors: list[dict]) -> bool:
    return bool(errors)


def agreement(answers: dict, claude: dict) -> None:
    done = [k for k in review_keys() if k in answers]
    if not done:
        print("No answers yet.")
        return
    same = sum(answers[k]["verdict"] == "agree" for k in done)
    a = [has_error(claude[k]) for k in done]
    b = [has_error(answers[k]["errors"]) for k in done]
    n = len(done)
    p_o = sum(x == y for x, y in zip(a, b)) / n
    p_a, p_b = sum(a) / n, sum(b) / n
    p_e = p_a * p_b + (1 - p_a) * (1 - p_b)
    kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0
    print(f"\n{BOLD}Agreement on {n} of {len(review_keys())} conversations{RESET}")
    print(f"  Full agreement with Claude's label: {same}/{n} ({100 * same / n:.0f}%)")
    print(f"  Error vs no error: {100 * p_o:.0f}% agreement, Cohen's kappa {kappa:.2f}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--redo", type=int, help="relabel conversation number N")
    parser.add_argument("--agreement", action="store_true")
    args = parser.parse_args()

    claude = load_labels()
    answers = load_rob()
    keys = review_keys()
    if args.agreement:
        agreement(answers, claude)
        return
    tasks = {t["id"]: t for t in load()[0]}
    todo = [keys[args.redo - 1]] if args.redo else [k for k in keys if k not in answers]
    if not todo:
        print("All conversations are labelled.")
    for key in todo:
        result = label_one(keys.index(key) + 1, len(keys), key, tasks, claude[key])
        if result.get("_action") == "q":
            break
        if result.get("_action") == "s":
            continue
        answers[key] = result
        save_rob(answers)
        print(f"{GREEN}Saved.{RESET}")
    remaining = len([k for k in keys if k not in answers])
    print(f"\n{remaining} conversation(s) left to label.")
    agreement(answers, claude)


if __name__ == "__main__":
    main()
