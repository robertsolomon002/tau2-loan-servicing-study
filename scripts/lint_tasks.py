"""Lint the loan_servicing task set (ROADMAP Section 9, plus scoring checks).

Checks:
- Task ids look like `ls_NNN_en` / `ls_NNN_fr` and are unique.
- Every task has evaluation criteria with `actions` as a list (never null, so
  the DB check always runs; docs/TAU2_NOTES.md Flag 5).
- `reward_basis` uses only DB and COMMUNICATE; COMMUNICATE is listed exactly
  when `communicate_info` is non-empty.
- Every `communicate_info` string matches `^[A-Z]{2}-\\d{4,6}$` or `^\\d{1,3}$`
  (language-neutral, ROADMAP decision 6), and does not appear anywhere in the
  user scenario (the agent must find it, not repeat it).
- Every reference action is a write tool of the domain, with known arguments.
- Once any French task exists: every task has both variants and each EN/FR
  pair has identical `evaluation_criteria`. The pair's user scenarios contain
  the same values (ids, ISO dates, emails, phone numbers, postal codes,
  amounts in either language's format, other numbers, and the DB's person and
  bank names), and only the FR task has a persona (the language line).
- Splits: `base` exists, `en_user` / `fr_user` list exactly the EN / FR tasks,
  every split id exists, and every task is in `base` or a language split.

Usage:
    python scripts/lint_tasks.py      # exits 1 and prints problems if any
"""

from __future__ import annotations

import inspect
import json
import re
import sys

import study_env  # sets TAU2_DATA_DIR; must come before tau2 imports
from tau2.domains.loan_servicing.tools import LoanServicingTools
from tau2.environment.toolkit import ToolType

DOMAIN_DATA = study_env.FORK / "data" / "tau2" / "domains" / "loan_servicing"
TASK_ID = re.compile(r"^ls_\d{3}_(en|fr)$")
COMMUNICATE = re.compile(r"^([A-Z]{2}-\d{4,6}|\d{1,3})$")

# Values that must survive translation unchanged, in the order they are
# removed from the text (emails and postal codes contain digits).
EXACT_VALUES = [
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),  # email
    re.compile(r"\b[A-Z]{2}-\d{4,6}\b"),  # id
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # ISO date
    re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),  # phone
    re.compile(r"\b[A-Z]\d[A-Z] \d[A-Z]\d\b"),  # postal code
]
# "$4,000.50" in English; "4 000,50 $" in French (\s also covers no-break
# spaces, which French typography uses as the thousands separator).
AMOUNT_EN = re.compile(r"\$(\d[\d,]*(?:\.\d+)?)")
AMOUNT_FR = re.compile(r"(\d{1,3}(?:\s\d{3})*(?:,\d+)?)\s?\$")


def scenario_values(text: str, names: set[str]) -> set[str]:
    """Language-independent values in a user scenario, normalized."""
    values = set()
    for pattern in EXACT_VALUES:
        values |= set(pattern.findall(text))
        text = pattern.sub(" ", text)
    for match in AMOUNT_EN.finditer(text):
        values.add(f"${float(match.group(1).replace(',', '')):.2f}")
    text = AMOUNT_EN.sub(" ", text)
    for match in AMOUNT_FR.finditer(text):
        number = re.sub(r"\s", "", match.group(1)).replace(",", ".")
        values.add(f"${float(number):.2f}")
    text = AMOUNT_FR.sub(" ", text)
    values |= {f"#{n}" for n in re.findall(r"\d+", text)}
    values |= {name for name in names if name in text}
    return values


def db_names() -> set[str]:
    """Person and bank names from the DB, which must not be translated."""
    db = json.loads((DOMAIN_DATA / "db.json").read_text("ascii"))
    names = set()
    for b in db["borrowers"].values():
        names |= {b["first_name"], b["last_name"], *b["authorized_third_parties"]}
        names |= {a["bank_name"] for a in b["bank_accounts"]}
    return names


def write_tools() -> dict[str, set[str]]:
    toolkit = LoanServicingTools(None)
    tools = {}
    for name in toolkit.tools:
        if toolkit.tool_type(name) == ToolType.WRITE:
            params = inspect.signature(getattr(toolkit, name)).parameters
            tools[name] = set(params)
    return tools


def lint(tasks: list[dict], splits: dict[str, list[str]]) -> list[str]:
    problems: list[str] = []
    tools = write_tools()
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        problems.append("duplicate task ids")

    by_id = {}
    for t in tasks:
        tid = t["id"]
        by_id[tid] = t
        if not TASK_ID.match(tid):
            problems.append(f"{tid}: id does not match ls_NNN_en / ls_NNN_fr")
        crit = t.get("evaluation_criteria")
        if crit is None or crit.get("actions") is None:
            problems.append(f"{tid}: actions must be a list, not null")
            continue
        basis = set(crit.get("reward_basis") or [])
        if not basis <= {"DB", "COMMUNICATE"} or "DB" not in basis:
            problems.append(f"{tid}: reward_basis must be DB or DB + COMMUNICATE")
        info = crit.get("communicate_info") or []
        if bool(info) != ("COMMUNICATE" in basis):
            problems.append(f"{tid}: COMMUNICATE must be listed iff communicate_info")
        scenario = json.dumps(t["user_scenario"])
        for value in info:
            if not COMMUNICATE.match(value):
                problems.append(f"{tid}: communicate_info '{value}' is not neutral")
            if value in scenario:
                problems.append(f"{tid}: '{value}' appears in the user scenario")
        for action in crit["actions"]:
            name = action["name"]
            if name not in tools:
                problems.append(f"{tid}: action {name} is not a write tool")
            elif not set(action["arguments"]) <= tools[name]:
                problems.append(f"{tid}: unknown arguments for {name}")
        if t["user_scenario"]["instructions"]["domain"] != "loan_servicing":
            problems.append(f"{tid}: instructions.domain must be loan_servicing")

    en = sorted(i for i in ids if i.endswith("_en"))
    fr = sorted(i for i in ids if i.endswith("_fr"))
    if fr:
        stems_en = {i[:-3] for i in en}
        stems_fr = {i[:-3] for i in fr}
        for stem in sorted(stems_en ^ stems_fr):
            problems.append(f"{stem}: missing its EN or FR variant")
        names = db_names()
        for stem in sorted(stems_en & stems_fr):
            task_en, task_fr = by_id[f"{stem}_en"], by_id[f"{stem}_fr"]
            a = task_en["evaluation_criteria"]
            b = task_fr["evaluation_criteria"]
            if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
                problems.append(f"{stem}: EN and FR evaluation_criteria differ")
            values_en, values_fr = (
                scenario_values(
                    json.dumps(t["user_scenario"]["instructions"], ensure_ascii=False),
                    names,
                )
                for t in (task_en, task_fr)
            )
            if values_en != values_fr:
                problems.append(
                    f"{stem}: scenario values differ: EN only "
                    f"{sorted(values_en - values_fr)}, FR only "
                    f"{sorted(values_fr - values_en)}"
                )
            if task_en["user_scenario"]["persona"] is not None:
                problems.append(f"{stem}_en: EN tasks have no persona")
            if not task_fr["user_scenario"]["persona"]:
                problems.append(f"{stem}_fr: FR tasks need the language persona")

    if "base" not in splits:
        problems.append("splits: 'base' is missing")
    if sorted(splits.get("en_user", [])) != en:
        problems.append("splits: en_user must list exactly the EN tasks")
    if fr and sorted(splits.get("fr_user", [])) != fr:
        problems.append("splits: fr_user must list exactly the FR tasks")
    for name, members in splits.items():
        for tid in members:
            if tid not in by_id:
                problems.append(f"splits: {name} lists unknown task {tid}")
    covered = set().union(*splits.values()) if splits else set()
    for tid in ids:
        if tid not in covered:
            problems.append(f"{tid}: not in any split")
    return problems


def load() -> tuple[list[dict], dict[str, list[str]]]:
    tasks = json.loads((DOMAIN_DATA / "tasks.json").read_text("ascii"))
    splits = json.loads((DOMAIN_DATA / "split_tasks.json").read_text("ascii"))
    return tasks, splits


def main() -> int:
    problems = lint(*load())
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
