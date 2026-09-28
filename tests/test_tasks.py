"""Task set checks: the linter, and a replay of every task's reference actions.

The replay applies each task's reference actions to a fresh environment and
checks the DB changes against the spec (for example "payment PM-31887 added:
LN-20004 150.00 posted 2026-03-16"), so a broken reference action cannot
silently change a task's target (docs/TAU2_NOTES.md Section 6).
"""

import json

import pytest
from build_tasks import (
    TASKS_DOC,
    build,
    load_db,
    replay,
    summarize_changes,
    tasks_doc,
)
from lint_tasks import lint, load
from task_specs import END, SPECS
from tau2.data_model.tasks import Task

COMMITTED_TASKS, COMMITTED_SPLITS = load()
SPEC_BY_ID = {f"ls_{s.num:03d}_en": s for s in SPECS}


def test_lint_passes():
    assert lint(COMMITTED_TASKS, COMMITTED_SPLITS) == []


def test_committed_files_match_builder():
    tasks, splits = build()
    assert json.loads(json.dumps(tasks)) == COMMITTED_TASKS
    assert splits == COMMITTED_SPLITS
    assert TASKS_DOC.read_text(encoding="utf-8") == tasks_doc(tasks)


def test_tasks_validate_against_tau2_schema():
    for task in COMMITTED_TASKS:
        Task.model_validate(task)


@pytest.mark.parametrize("task", COMMITTED_TASKS, ids=lambda t: t["id"])
def test_replay_matches_expected_changes(task):
    db = load_db()
    actions = [
        (a["name"], a["arguments"]) for a in task["evaluation_criteria"]["actions"]
    ]
    after = replay(db, actions)
    changes = summarize_changes(db.model_dump(), after)
    assert sorted(changes) == sorted(SPEC_BY_ID[task["id"]].expected)
    for value in task["evaluation_criteria"]["communicate_info"]:
        assert f'"{value}"' in json.dumps(after)


def test_category_balance():
    no_change = [s for s in SPECS if not s.actions]
    assert 35 <= len(SPECS) <= 45
    # A good share of tasks must be refusals with no DB change (ROADMAP 4.4;
    # transfers and partial actions make up the rest of the "not a plain
    # action" half).
    assert 0.25 <= len(no_change) / len(SPECS) <= 0.6


def test_every_task_has_the_closing_rules():
    # Pilot 1 (Stage 2.2): without these, the simulated user ended the
    # conversation in the same message as a confirmation, or accepted
    # unrelated changes the agent offered.
    for task in COMMITTED_TASKS:
        assert task["user_scenario"]["instructions"]["task_instructions"].endswith(END)
