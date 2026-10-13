"""Tests for the Stage 5.2 failure-classification helpers."""

import pandas as pd
import pytest

from analysis import failures


def test_kappa_perfect_and_chance():
    assert failures.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    # Same marginals, no agreement beyond chance.
    assert failures.cohen_kappa(["a", "b"], ["b", "a"]) == pytest.approx(-1.0)


def test_kappa_known_value():
    a = ["x"] * 6 + ["y"] * 4
    b = ["x"] * 5 + ["y"] * 5
    # observed 0.9; expected 0.6 * 0.5 + 0.4 * 0.5 = 0.5
    assert failures.cohen_kappa(a, b) == pytest.approx(0.8)


def test_validate_flags_bad_labels():
    good = {"cause": "rule_misapplied", "rule": "F1", "explanation": "x"}
    labels = {
        "ok": good | {"sim_major": False},
        "bad_cause": good | {"cause": "oops", "sim_major": False},
        "no_rule": good | {"rule": "", "sim_major": False},
        "no_flag": good,
    }
    problems = failures.validate(labels)
    assert not any(p.startswith("ok:") for p in problems)
    assert {p.split(":")[0] for p in problems} == {"bad_cause", "no_rule", "no_flag"}


def test_review_sample_is_fixed_and_skips_model_failures():
    keys = [f"cell__ls_{i:03d}_en__t0" for i in range(60)]
    status = ["model_failure" if i < 5 else "done" for i in range(60)]
    fails = pd.DataFrame({"status": status}, index=keys)
    first = failures.review_sample(fails)
    assert first == failures.review_sample(fails)
    assert len(first) == failures.SAMPLE_SIZE
    assert not set(first) & set(keys[:5])


def test_transcript_and_write_calls():
    sim = {
        "messages": [
            {"role": "user", "content": "Pay 10"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "c1", "name": "make_payment", "arguments": {"amount": 10}}
                ],
            },
            {"role": "tool", "id": "c1", "content": "boom", "error": True},
        ]
    }
    lines = failures.transcript(sim)
    assert lines[0] == "[0] USER: Pay 10"
    assert lines[1].endswith("make_payment(amount=10) **WRITE**")
    assert lines[2] == "[2]   <- ERROR boom"
    assert failures.write_calls(sim) == ["[1] make_payment(amount=10): tool error"]


def test_committed_labels_are_valid():
    labels = failures.load_labels()
    assert labels, "data/failure_labels.json is missing"
    assert failures.validate(labels) == []


def test_fleiss_kappa():
    # Perfect agreement, and agreement no better than chance.
    assert failures.fleiss_kappa([("a", "a", "a"), ("b", "b", "b")]) == 1.0
    rows = [("a", "b"), ("b", "a")]
    assert failures.fleiss_kappa(rows) == -1.0
    # Two raters: Fleiss equals Scott's pi; check against a hand computation.
    rows = [("a", "a"), ("a", "a"), ("a", "b"), ("b", "b")]
    # p_bar = 3/4; p_e = (5/8)^2 + (3/8)^2 = 34/64; kappa = (48-34)/(64-34)
    assert abs(failures.fleiss_kappa(rows) - 14 / 30) < 1e-12
