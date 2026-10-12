"""Tests for the Stage 5.1 analysis: the statistics on toy data, the loader on
a fake runner folder, and the report on a synthetic complete model."""

import json
import math

import numpy as np
import pandas as pd
import pytest
from generate_db import LAST_NAMES
from tau2.metrics.agent_metrics import pass_hat_k as tau2_pass_hat_k
from user_sim_eval import GREETING

from analysis import metrics
from analysis.load import (
    CONDITIONS,
    MODELS,
    QUEBEC_SURNAMES,
    load_cell,
    surname_group,
    task_table,
)
from analysis.report import TASKS, TRIALS, build

# ---------- metrics ----------


def test_pass_hat_k_matches_tau2():
    for s in range(5):
        for k in range(1, 5):
            assert metrics.pass_hat_k(4, s, k) == tau2_pass_hat_k(4, s, k)


def test_pass_hat_1_is_the_mean_success_rate():
    successes = np.array([4, 3, 0, 2], dtype=float)
    trials = np.full(4, 4.0)
    assert metrics.pass_hat_k_mean(successes, trials, 1) == pytest.approx(9 / 16)
    # pass^4 counts only the task solved in all 4 trials.
    assert metrics.pass_hat_k_mean(successes, trials, 4) == pytest.approx(1 / 4)


def test_pass_hat_k_skips_dropped_tasks():
    successes = np.array([4, np.nan])
    trials = np.array([4, np.nan])
    assert metrics.pass_hat_k_mean(successes, trials, 2) == 1.0


def test_incomplete_task_is_dropped_for_that_model_in_every_condition():
    successes = np.full((2, 2, 3), 4.0)
    trials = np.full((2, 2, 3), 4.0)
    trials[1, 0, 2] = 3  # task 2, model 1, C3: one conversation missing
    rates = metrics.drop_incomplete(successes, trials, 4)
    assert np.isnan(rates[1, 0]).all()
    assert not np.isnan(rates[1, 1]).any()  # the other model keeps the task
    assert not np.isnan(rates[0]).any()


def test_planned_trials_can_differ_per_model():
    # Amendment 2: model 0 has 4 planned trials, model 1 has 2.
    successes = np.full((2, 2, 3), 2.0)
    trials = np.full((2, 2, 3), 2.0)
    trials[:, 0] = 4
    trials[1, 1, 0] = 1  # task 2, model 1, C1: one of its 2 conversations missing
    rates = metrics.drop_incomplete(successes, trials, [4, 2])
    assert not np.isnan(rates[:, 0]).any()
    assert np.allclose(rates[0, 1], 1.0)  # 2 of 2 is complete for model 1
    assert np.isnan(rates[1, 1]).all()


def test_bootstrap_is_deterministic_and_paired():
    rng = np.random.default_rng(0)
    c1 = rng.integers(0, 5, size=48) / 4
    rates = np.stack([c1, c1 - 0.25], axis=1)[:, None, :]  # [task, model, cond]
    boot = metrics.bootstrap_means(rates, n_resamples=2000)
    assert np.array_equal(boot, metrics.bootstrap_means(rates, n_resamples=2000))
    # Every task drops by exactly 0.25, so a paired interval has no width.
    low, high = metrics.percentile_ci(boot[:, 0, 0] - boot[:, 0, 1])
    assert low == pytest.approx(0.25) and high == pytest.approx(0.25)
    # The interval for one condition covers its mean.
    low, high = metrics.percentile_ci(boot[:, 0, 0])
    assert low < c1.mean() < high


def test_bootstrap_draws_do_not_depend_on_the_other_models():
    rng = np.random.default_rng(1)
    one = rng.random((48, 1, 3))
    two = np.concatenate([one, rng.random((48, 1, 3))], axis=1)
    a = metrics.bootstrap_means(one, n_resamples=500)
    b = metrics.bootstrap_means(two, n_resamples=500)
    assert np.allclose(a[:, 0], b[:, 0])


def test_bootstrap_ignores_dropped_tasks():
    rates = np.ones((10, 1, 1))
    rates[3] = np.nan
    boot = metrics.bootstrap_means(rates, n_resamples=200)
    assert np.allclose(boot, 1.0)


def test_mcnemar_exact():
    assert metrics.mcnemar_exact([True, False], [True, False]) == (0, 0, 1.0)
    # b = 8, c = 2: p = 2 * P(X <= 2), X ~ Binomial(10, 0.5) = 112 / 1024.
    a = [True] * 8 + [False] * 2 + [True] * 5
    b = [False] * 8 + [True] * 2 + [True] * 5
    assert metrics.mcnemar_exact(a, b) == (8, 2, pytest.approx(112 / 1024))
    assert metrics.mcnemar_exact(b, a)[2] == pytest.approx(112 / 1024)
    # One discordant task: p = 1, never above 1.
    assert metrics.mcnemar_exact([True], [False])[2] == 1.0


def test_holm():
    assert metrics.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert metrics.holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])


# ---------- loader ----------


def test_task_table():
    tasks = task_table()
    assert len(tasks) == TASKS
    assert tasks["category"].nunique() == 11
    assert int(tasks["hard"].sum()) == 17
    assert set(tasks["preferred_language"]) == {"en", "fr"}


def test_quebec_surnames_come_from_the_generator_pool():
    assert QUEBEC_SURNAMES <= set(LAST_NAMES)
    assert surname_group("Gagnon") == "french"
    assert surname_group("Martin") == "ambiguous"
    assert surname_group("Patel") == "other"


def _write_sim(path, messages, reward=1.0, info=None):
    path.write_text(
        json.dumps(
            {
                "termination_reason": "user_stop",
                "reward_info": None if info else {"reward": reward},
                "messages": messages,
                "info": info,
            }
        ),
        encoding="utf-8",
    )


def test_load_cell_statuses_languages_and_costs(tmp_path):
    cell = tmp_path / "m_C1"
    (cell / "sims").mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"task_ids": ["ls_001_en", "ls_002_en"]}), encoding="utf-8"
    )
    messages = [
        {"role": "assistant", "content": GREETING},
        {"role": "user", "content": "Hi, I would like to make a payment on my loan today."},
        {"role": "assistant", "content": "Bonjour, je peux vous aider avec votre paiement aujourd'hui."},
        {
            "role": "assistant",
            "content": "Let me check that for you right now.",
            "tool_calls": [{"name": "get_loan_details", "arguments": {}}],
        },
        {"role": "tool", "content": "Error: loan not found", "error": True},
    ]  # fmt: skip
    _write_sim(cell / "sims" / "ls_001_en__t0.json", messages)
    _write_sim(
        cell / "sims" / "ls_001_en__t1.json",
        [],
        info={"runner_outcome": "model_failure"},
    )
    attempts = [
        {"task_id": "ls_001_en", "trial": 0, "outcome": "provider_error",
         "cost": {"cash": 0.001}, "time": "2026-10-01T22:00:00+00:00"},
        {"task_id": "ls_001_en", "trial": 0, "outcome": "done",
         "cost": {"cash": 0.002, "vertex": 0.01}, "time": "2026-10-01T22:01:00+00:00"},
        {"task_id": "ls_001_en", "trial": 1, "outcome": "model_failure",
         "cost": {"vertex": 0.003}, "time": "2026-10-01T22:02:00+00:00"},
    ] + [
        {"task_id": "ls_002_en", "trial": 0, "outcome": "provider_error",
         "cost": {}, "time": "2026-10-01T22:03:00+00:00"}
    ] * 6  # fmt: skip
    (cell / "attempts.jsonl").write_text(
        "\n".join(json.dumps(a) for a in attempts), encoding="utf-8"
    )

    rows = {
        (r["task_id"], r["trial"]): r
        for r in load_cell(tmp_path, "m", "C1", trials=2, max_attempts=6)
    }
    done = rows[("ls_001_en", 0)]
    assert done["status"] == "done" and done["success"] is True
    # The greeting and the tool-call message are not turns the customer sees.
    assert done["agent_langs"] == ("fr",) and done["user_langs"] == ("en",)
    assert done["agent_other_lang"] == 1 and done["agent_in_lang"] == 0
    assert (done["turns"], done["tool_calls"], done["tool_errors"]) == (3, 1, 1)
    assert done["user_cost"] == pytest.approx(0.003)
    assert done["agent_cost"] == pytest.approx(0.01)
    failure = rows[("ls_001_en", 1)]
    assert failure["status"] == "model_failure" and failure["success"] is False
    assert rows[("ls_002_en", 0)]["status"] == "missing"
    assert rows[("ls_002_en", 1)]["status"] == "pending"


def test_load_cell_stopped_model_marks_unfinished_as_missing(tmp_path):
    # Amendment 2: a stopped model's unfinished conversations are missing,
    # even after fewer than max_attempts attempts.
    cell = tmp_path / "qwen_C1"
    (cell / "sims").mkdir(parents=True)
    (cell / "cell.json").write_text(
        json.dumps({"task_ids": ["ls_001_en"]}), encoding="utf-8"
    )
    _write_sim(cell / "sims" / "ls_001_en__t0.json", [])
    (cell / "attempts.jsonl").write_text(
        json.dumps({"task_id": "ls_001_en", "trial": 1, "outcome": "provider_error",
                    "cost": {}, "time": "2026-10-05T21:00:00+00:00"}),
        encoding="utf-8",
    )  # fmt: skip
    rows = load_cell(tmp_path, "qwen", "C1", trials=2, max_attempts=6, stopped=True)
    assert [r["status"] for r in rows] == ["done", "missing"]


# ---------- report ----------


def _synthetic_df(model: str, seed: int = 0, trials: int = TRIALS) -> pd.DataFrame:
    """A complete model: 48 tasks x 3 conditions x `trials` trials."""
    rng = np.random.default_rng(seed)
    rows = []
    for condition in CONDITIONS:
        for task in range(1, TASKS + 1):
            for trial in range(trials):
                success = bool(rng.random() < 0.85)
                rows.append(
                    {
                        "model": model, "condition": condition,
                        "cell": f"{model}_{condition}", "task": task,
                        "task_id": f"ls_{task:03d}_en", "trial": trial,
                        "attempts": 1, "last_attempt": "2026-10-02T03:08:00+00:00",
                        "agent_cost": 0.01, "user_cost": 0.003, "status": "done",
                        "reward": float(success), "success": success,
                        "termination": "user_stop", "turns": 10, "tool_calls": 3,
                        "tool_errors": 0, "agent_judged": 5, "agent_in_lang": 5,
                        "agent_other_lang": 0, "user_judged": 5, "user_in_lang": 5,
                        "user_other_lang": 0,
                    }
                )  # fmt: skip
    df = pd.DataFrame(rows).join(task_table(), on="task")
    df["model"] = pd.Categorical(df["model"], categories=MODELS, ordered=True)
    return df


def test_report_numbers_match_a_direct_computation(tmp_path):
    df = _synthetic_df("gemini_pro")
    summary, md = build(df, tmp_path)
    rates = df.groupby(["condition", "task"])["success"].mean()
    pass1 = rates.groupby("condition").mean()
    got = summary[
        (summary["metric"] == "pass^1") & (summary["section"] == "confirmatory")
    ]
    for _, row in got.iterrows():
        assert row["value"] == pytest.approx(pass1[row["condition"]])
        assert row["ci_low"] <= row["value"] <= row["ci_high"]
    h1 = summary[
        (summary["section"] == "confirmatory")
        & (summary["metric"] == "pass^1 difference")
        & (summary["comparison"] == "C1-C2")
    ]
    assert h1.iloc[0]["value"] == pytest.approx(pass1["C1"] - pass1["C2"])
    assert "Preliminary: 1 of 5 models" in md
    assert not math.isnan(h1.iloc[0]["ci_low"])


def test_report_with_a_two_trial_model(tmp_path):
    """Amendment 2: Qwen with 2 trials and one missing conversation (task 20)."""
    qwen = _synthetic_df("qwen", seed=1, trials=2)
    missing = (qwen["task"] == 20) & (qwen["condition"] == "C2") & (qwen["trial"] == 0)
    qwen["success"] = qwen["success"].astype(object)  # as in load(): NaN if unfinished
    qwen.loc[missing, ["status", "success", "reward"]] = ["missing", np.nan, np.nan]
    df = pd.concat([_synthetic_df("gemini_pro"), qwen], ignore_index=True)
    df["model"] = pd.Categorical(df["model"], categories=MODELS, ordered=True)
    summary, md = build(df, tmp_path)

    def get(metric, **kw):
        rows = summary[(summary["metric"] == metric) & (summary["model"] == "qwen")]
        for k, v in kw.items():
            rows = rows[rows[k] == v]
        return rows

    # Task 20 is dropped in every condition; pass^1 is over the other 47.
    kept = qwen[qwen["task"] != 20]
    pass1 = (
        kept.groupby(["condition", "task"])["success"]
        .mean()
        .groupby("condition")
        .mean()
    )
    got = get("pass^1", section="confirmatory")
    assert set(got["n"]) == {47}
    for _, row in got.iterrows():
        assert row["value"] == pytest.approx(pass1[row["condition"]])
    # pass^k only up to k = 2; McNemar majorities 2/2 and 1/2.
    assert len(get("pass^2")) == 3 and get("pass^3").empty
    assert get("mcnemar_p")["detail"].str.contains(">=2/2").all()
    assert get("mcnemar_p_sensitivity")["detail"].str.contains(">=1/2").all()
    gemini = summary[
        (summary["metric"] == "mcnemar_p") & (summary["model"] == "gemini_pro")
    ]
    assert gemini["detail"].str.contains(">=3/4").all()
    by_hard = get("pass^1 by hard", condition="C1")
    assert by_hard["n"].sum() == 47
    assert "Qwen 3.8 27B (free) has 2 trials and 47 tasks" in md
    assert "only k = 1 and 2" in md
