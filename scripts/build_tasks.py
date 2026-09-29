"""Build the loan_servicing task set from scripts/task_specs.py (Stage 2.1).

Writes the fork's `tasks.json` and `split_tasks.json` (ASCII-escaped, see
docs/TAU2_NOTES.md Flag 12), `docs/TASKS.md`, and `docs/TASKS_FR_REVIEW.md`.
Each spec gives an English task (`ls_NNN_en`) and a Quebec French twin
(`ls_NNN_fr`, text from scripts/task_specs_fr.py, Stage 3.2) with identical
evaluation criteria; action ids are language-neutral so that the criteria are
byte-identical. Every task is replayed on a
fresh environment first; the build fails if a reference action errors, if the
DB changes differ from the spec's `expected` list, or if a communicate id does
not exist after the replay.

Usage:
    python scripts/build_tasks.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import study_env  # noqa: F401  (must come before tau2 imports)
from task_specs import END, NO_HUMAN, SPECS, Spec
from task_specs_fr import END_FR, FR, NO_HUMAN_FR, PERSONA_FR
from tau2.domains.loan_servicing.data_model import LoanServicingDB
from tau2.domains.loan_servicing.environment import get_environment

REPO = Path(__file__).resolve().parents[1]
DOMAIN_DATA = (
    REPO.parent / "tau2-bench" / "data" / "tau2" / "domains" / "loan_servicing"
)
DB_PATH = DOMAIN_DATA / "db.json"
TASKS_PATH = DOMAIN_DATA / "tasks.json"
SPLITS_PATH = DOMAIN_DATA / "split_tasks.json"
PLANTED_PATH = REPO / "data" / "planted_cases.json"
TASKS_DOC = REPO / "docs" / "TASKS.md"
FR_REVIEW_DOC = REPO / "docs" / "TASKS_FR_REVIEW.md"


def load_db() -> LoanServicingDB:
    return LoanServicingDB.model_validate(json.loads(DB_PATH.read_text("ascii")))


def task_id(num: int, lang: str = "en") -> str:
    return f"ls_{num:03d}_{lang}"


# ---------- DB diff summary (shared with tests/test_tasks.py) ----------


def _autopay(a: dict) -> str:
    return f"{a['method_id']} day {a['day']}" if a["enabled"] else "off"


def summarize_changes(before: dict, after: dict) -> list[str]:
    """Human-readable list of the DB changes that matter for a task."""
    out = []
    for pid, p in after["payments"].items():
        old = before["payments"].get(pid)
        if old is None:
            out.append(
                f"payment {pid} added: {p['loan_id']} {p['amount']:.2f} "
                f"{p['status']} {p['date']}"
            )
        elif old["status"] != p["status"]:
            out.append(f"payment {pid} status: {old['status']} -> {p['status']}")
    for lid, loan in after["loans"].items():
        old = before["loans"][lid]
        for f_old, f_new in zip(old["fees"], loan["fees"]):
            if f_old["status"] != f_new["status"]:
                out.append(
                    f"loan {lid} fee {f_new['fee_id']}: "
                    f"{f_old['status']} -> {f_new['status']}"
                )
        known = {h["hardship_id"] for h in old["hardship_history"]}
        for h in loan["hardship_history"]:
            if h["hardship_id"] not in known:
                out.append(f"loan {lid} hardship {h['hardship_id']} added: {h['plan']}")
        if old["status"] != loan["status"]:
            out.append(f"loan {lid} status: {old['status']} -> {loan['status']}")
        if old["due_day"] != loan["due_day"]:
            out.append(f"loan {lid} due_day: {old['due_day']} -> {loan['due_day']}")
        if old["autopay"] != loan["autopay"]:
            out.append(
                f"loan {lid} autopay: {_autopay(old['autopay'])} -> "
                f"{_autopay(loan['autopay'])}"
            )
    for bid, b in after["borrowers"].items():
        old = before["borrowers"][bid]
        for key in ("email", "phone"):
            if old[key] != b[key]:
                out.append(f"borrower {bid} {key}: {old[key]} -> {b[key]}")
    for rid, r in after["document_requests"].items():
        if rid not in before["document_requests"]:
            out.append(
                f"document {rid} added: {r['loan_id']} {r['doc_type']} to {r['sent_to']}"
            )
    for tid, t in after["transfers"].items():
        if tid not in before["transfers"]:
            out.append(f"transfer {tid} added: {t['reason']}")
    return out


# ---------- building ----------


def resolve_actions(spec: Spec, db: LoanServicingDB) -> list[tuple[str, dict]]:
    """Replace "PAYOFF:<loan>:<date>" amounts with the tool's payoff total."""
    env = get_environment(db=copy.deepcopy(db))
    resolved = []
    for name, args in spec.actions:
        args = dict(args)
        amount = args.get("amount")
        if isinstance(amount, str) and amount.startswith("PAYOFF:"):
            _, loan_id, when = amount.split(":")
            quote = env.tools.calculate_payoff(loan_id=loan_id, payoff_date=when)
            args["amount"] = quote.total
        resolved.append((name, args))
    return resolved


def replay(db: LoanServicingDB, actions: list[tuple[str, dict]]) -> dict:
    """Run the actions on a fresh environment; raise on any tool error."""
    env = get_environment(db=copy.deepcopy(db))
    for name, args in actions:
        env.make_tool_call(name, requestor="assistant", **args)
    return env.tools.db.model_dump()


def identity_lines(
    db: LoanServicingDB, borrower_id: str, lang: str = "en"
) -> list[str]:
    b = db.borrowers[borrower_id]
    if lang == "fr":
        return [
            f"Vous êtes {b.first_name} {b.last_name}.",
            f"Votre date de naissance est le {b.date_of_birth}.",
            f"Votre code postal est {b.postal_code}.",
        ]
    return [
        f"You are {b.first_name} {b.last_name}.",
        f"Your date of birth is {b.date_of_birth}.",
        f"Your postal code is {b.postal_code}.",
    ]


def scenario(
    spec: Spec, db: LoanServicingDB, borrower_id: str, lang: str
) -> tuple[str | None, dict]:
    """The persona and structured user instructions for one language."""
    text = spec if lang == "en" else FR[spec.num]
    identity = identity_lines(db, borrower_id, lang) if spec.identity else []
    instructions = {
        "domain": "loan_servicing",
        "reason_for_call": text.reason,
        "known_info": "\n".join(identity + text.known),
        "unknown_info": text.unknown,
        "task_instructions": text.instructions,
    }
    return (PERSONA_FR if lang == "fr" else None), instructions


def build_task(spec: Spec, db: LoanServicingDB, planted: dict) -> list[dict]:
    """Build the EN task and its FR twin (same evaluation criteria)."""
    case = planted[spec.case]
    borrower_id = case["borrower_ids"][spec.borrower]
    actions = resolve_actions(spec, db)

    before = db.model_dump()
    after = replay(db, actions)
    changes = summarize_changes(before, after)
    if sorted(changes) != sorted(spec.expected):
        raise ValueError(
            f"Task {spec.num}: DB changes differ from the spec.\n"
            f"  expected: {spec.expected}\n  actual:   {changes}"
        )
    all_ids = json.dumps(after)
    for value in spec.communicate:
        if f'"{value}"' not in all_ids:
            raise ValueError(f"Task {spec.num}: {value} not in the DB after replay")

    if spec.num not in FR:
        raise ValueError(f"Task {spec.num}: no French text in task_specs_fr.py")
    criteria = {
        "actions": [
            {"action_id": f"ls_{spec.num:03d}_{n}", "name": name, "arguments": args}
            for n, (name, args) in enumerate(actions)
        ],
        "communicate_info": list(spec.communicate),
        "nl_assertions": None,
        "reward_basis": ["DB", "COMMUNICATE"] if spec.communicate else ["DB"],
    }
    borrower = db.borrowers[borrower_id]
    tasks = []
    for lang, language in (("en", "English"), ("fr", "Quebec French")):
        persona, instructions = scenario(spec, db, borrower_id, lang)
        for _, args in actions:
            loan_id = args.get("loan_id")
            text = instructions["reason_for_call"] + instructions["known_info"]
            if loan_id and len(borrower.loan_ids) > 1 and loan_id not in text:
                raise ValueError(
                    f"Task {spec.num} ({lang}): borrower has several loans; "
                    f"say {loan_id}"
                )
        tasks.append(
            {
                "id": task_id(spec.num, lang),
                "description": {
                    "purpose": spec.purpose,
                    "relevant_policies": ", ".join(spec.rules),
                    "notes": f"Category: {spec.category}. Planted case: {spec.case}. "
                    f"Difficulty: {'hard' if spec.hard else 'standard'}. "
                    f"User language: {language}. "
                    f"Expected outcome: {spec.outcome}",
                },
                "user_scenario": {"persona": persona, "instructions": instructions},
                "initial_state": None,
                "evaluation_criteria": copy.deepcopy(criteria),
            }
        )
    return tasks


def build() -> tuple[list[dict], dict[str, list[str]]]:
    db = load_db()
    planted = json.loads(PLANTED_PATH.read_text("ascii"))
    nums = [s.num for s in SPECS]
    if nums != list(range(1, len(SPECS) + 1)):
        raise ValueError(f"Task numbers must be 1..N in order: {nums}")
    extra = sorted(set(FR) - set(nums))
    if extra:
        raise ValueError(f"French text for unknown tasks: {extra}")
    pairs = [build_task(spec, db, planted) for spec in SPECS]
    tasks = [en for en, _ in pairs] + [fr for _, fr in pairs]
    en = [t["id"] for t in tasks if t["id"].endswith("_en")]
    fr = [t["id"] for t in tasks if t["id"].endswith("_fr")]
    # `base` stays the English set; the language splits select the user side.
    splits = {"base": en, "en_user": en, "fr_user": fr}
    return tasks, splits


def tasks_doc(tasks: list[dict]) -> str:
    specs = {task_id(s.num): s for s in SPECS}
    lines = [
        "# loan_servicing tasks",
        "",
        (
            "Generated by `scripts/build_tasks.py` from `scripts/task_specs.py`; do not "
            "edit by hand. Rule ids refer to `docs/DOMAIN_SPEC.md` Section 4. "
            '"Checked" lists the reward basis and any reference numbers the agent '
            'must say. "Hard" marks the harder tasks from Stage 2.3 (users who push '
            "back, give details out of order, or bundle requests). Each task also "
            "has a Quebec French twin (`ls_NNN_fr`, split `fr_user`) with identical "
            "evaluation criteria; see `docs/TASKS_FR_REVIEW.md`."
        ),
        "",
        "| Task | Category | Hard | Correct outcome | Rules | Checked |",
        "|---|---|---|---|---|---|",
    ]
    for t in tasks:
        if t["id"] not in specs:
            continue
        s = specs[t["id"]]
        crit = t["evaluation_criteria"]
        checked = " + ".join(crit["reward_basis"])
        if crit["communicate_info"]:
            checked += " (" + ", ".join(crit["communicate_info"]) + ")"
        lines.append(
            f"| `{t['id']}` | {s.category} | {'yes' if s.hard else ''} | "
            f"{s.outcome} | {', '.join(s.rules)} | {checked} |"
        )
    counts: dict[str, int] = {}
    for s in SPECS:
        counts[s.category] = counts.get(s.category, 0) + 1
    no_change = sum(1 for s in SPECS if not s.actions)
    lines += [
        "",
        f"{len(SPECS)} tasks: "
        + ", ".join(f"{k} {v}" for k, v in counts.items())
        + f". {no_change} expect no DB change (refusals); "
        f"{len(SPECS) - no_change} expect an action or a transfer. "
        f"{sum(1 for s in SPECS if s.hard)} are marked hard.",
        "",
    ]
    return "\n".join(lines)


def _cell(text: str | None) -> str:
    if text is None:
        return ""
    return text.replace("|", "\\|").replace("\n", "<br>")


def _strip_closing(text: str, lang: str) -> str:
    """Drop the shared closing lines, shown once at the top of the review."""
    end, no_human = (END, NO_HUMAN) if lang == "en" else (END_FR, NO_HUMAN_FR)
    marks = []
    if text.endswith(end):
        text = text[: -len(end)].rstrip()
        marks.append("END")
    if text.endswith(no_human):
        text = text[: -len(no_human)].rstrip()
        marks.insert(0, "NO_HUMAN")
    return text + "".join(f" [{m}]" for m in marks)


def fr_review_doc(tasks: list[dict]) -> str:
    """Side-by-side EN and FR user scenarios, for Rob's review (Stage 3.4)."""
    by_id = {t["id"]: t for t in tasks}
    lines = [
        "# French task review (Stage 3.2)",
        "",
        (
            "Generated by `scripts/build_tasks.py` from `scripts/task_specs.py` and "
            "`scripts/task_specs_fr.py`; do not edit by hand. Each FR task has the "
            "same evaluation criteria as its EN twin, and `scripts/lint_tasks.py` "
            "checks that both scenarios contain the same names, ids, dates, emails, "
            "phone numbers, postal codes, amounts and other numbers. Fix wording in "
            "`task_specs_fr.py`, then rebuild."
        ),
        "",
        "Shared lines, shown once here and marked in the tables:",
        "",
        "| | English | French |",
        "|---|---|---|",
        f"| Persona | (none) | {_cell(PERSONA_FR)} |",
        f"| [NO_HUMAN] | {_cell(NO_HUMAN)} | {_cell(NO_HUMAN_FR)} |",
        f"| [END] | {_cell(END)} | {_cell(END_FR)} |",
        "",
    ]
    fields = [
        ("Reason for call", "reason_for_call"),
        ("Known info", "known_info"),
        ("Unknown info", "unknown_info"),
        ("Task instructions", "task_instructions"),
    ]
    for spec in SPECS:
        en = by_id[task_id(spec.num, "en")]["user_scenario"]["instructions"]
        fr = by_id[task_id(spec.num, "fr")]["user_scenario"]["instructions"]
        lines += [
            f"## {spec.num}. {spec.category}{' (hard)' if spec.hard else ''}",
            "",
            f"Correct outcome: {spec.outcome}",
            "",
            "| | English | French |",
            "|---|---|---|",
        ]
        for label, key in fields:
            a, b = en[key], fr[key]
            if a is None and b is None:
                continue
            if key == "task_instructions":
                a, b = _strip_closing(a, "en"), _strip_closing(b, "fr")
            lines.append(f"| {label} | {_cell(a)} | {_cell(b)} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    tasks, splits = build()
    TASKS_PATH.write_text(json.dumps(tasks, indent=2) + "\n", encoding="ascii")
    SPLITS_PATH.write_text(json.dumps(splits, indent=2) + "\n", encoding="ascii")
    TASKS_DOC.write_text(tasks_doc(tasks), encoding="utf-8")
    FR_REVIEW_DOC.write_text(fr_review_doc(tasks), encoding="utf-8")
    print(f"Wrote {len(tasks)} tasks to {TASKS_PATH} and {TASKS_DOC}")


if __name__ == "__main__":
    main()
