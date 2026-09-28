"""Build the loan_servicing task set from scripts/task_specs.py (Stage 2.1).

Writes the fork's `tasks.json` and `split_tasks.json` (ASCII-escaped, see
docs/TAU2_NOTES.md Flag 12) and `docs/TASKS.md`. Every task is replayed on a
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
from task_specs import SPECS, Spec
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


def identity_lines(db: LoanServicingDB, borrower_id: str) -> list[str]:
    b = db.borrowers[borrower_id]
    return [
        f"You are {b.first_name} {b.last_name}.",
        f"Your date of birth is {b.date_of_birth}.",
        f"Your postal code is {b.postal_code}.",
    ]


def build_task(spec: Spec, db: LoanServicingDB, planted: dict) -> dict:
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

    known = (identity_lines(db, borrower_id) if spec.identity else []) + spec.known
    borrower = db.borrowers[borrower_id]
    for _, args in actions:
        loan_id = args.get("loan_id")
        if loan_id and len(borrower.loan_ids) > 1:
            text = spec.reason + " ".join(known)
            if loan_id not in text:
                raise ValueError(
                    f"Task {spec.num}: borrower has several loans; say {loan_id}"
                )

    tid = task_id(spec.num)
    return {
        "id": tid,
        "description": {
            "purpose": spec.purpose,
            "relevant_policies": ", ".join(spec.rules),
            "notes": f"Category: {spec.category}. Planted case: {spec.case}. "
            f"Expected outcome: {spec.outcome}",
        },
        "user_scenario": {
            "persona": None,
            "instructions": {
                "domain": "loan_servicing",
                "reason_for_call": spec.reason,
                "known_info": "\n".join(known),
                "unknown_info": spec.unknown,
                "task_instructions": spec.instructions,
            },
        },
        "initial_state": None,
        "evaluation_criteria": {
            "actions": [
                {"action_id": f"{tid}_{n}", "name": name, "arguments": args}
                for n, (name, args) in enumerate(actions)
            ],
            "communicate_info": list(spec.communicate),
            "nl_assertions": None,
            "reward_basis": ["DB", "COMMUNICATE"] if spec.communicate else ["DB"],
        },
    }


def build() -> tuple[list[dict], dict[str, list[str]]]:
    db = load_db()
    planted = json.loads(PLANTED_PATH.read_text("ascii"))
    nums = [s.num for s in SPECS]
    if nums != list(range(1, len(SPECS) + 1)):
        raise ValueError(f"Task numbers must be 1..N in order: {nums}")
    tasks = [build_task(spec, db, planted) for spec in SPECS]
    en = [t["id"] for t in tasks if t["id"].endswith("_en")]
    splits = {"base": en, "en_user": en}
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
            "must say."
        ),
        "",
        "| Task | Category | Correct outcome | Rules | Checked |",
        "|---|---|---|---|---|",
    ]
    for t in tasks:
        s = specs[t["id"]]
        crit = t["evaluation_criteria"]
        checked = " + ".join(crit["reward_basis"])
        if crit["communicate_info"]:
            checked += " (" + ", ".join(crit["communicate_info"]) + ")"
        lines.append(
            f"| `{t['id']}` | {s.category} | {s.outcome} | {', '.join(s.rules)} "
            f"| {checked} |"
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
        f"{len(SPECS) - no_change} expect an action or a transfer.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    tasks, splits = build()
    TASKS_PATH.write_text(json.dumps(tasks, indent=2) + "\n", encoding="ascii")
    SPLITS_PATH.write_text(json.dumps(splits, indent=2) + "\n", encoding="ascii")
    TASKS_DOC.write_text(tasks_doc(tasks), encoding="utf-8")
    print(f"Wrote {len(tasks)} tasks to {TASKS_PATH} and {TASKS_DOC}")


if __name__ == "__main__":
    main()
