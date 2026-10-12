"""Metrics and tests of the pre-registered analysis (plan Section 6, Stage 5.1).

Everything here is a pure function of arrays, so the unit tests can check it on
toy data. The arrays are indexed [task, model, condition]; a NaN marks a task
dropped for that model (plan Section 7, rule 1: a missing conversation drops
the task for that model in every condition).
"""

from __future__ import annotations

import math

import numpy as np

N_RESAMPLES = 10_000
SEED = 2026
# Plan Section 6.3: a task is solved in a condition if it succeeded in at least
# 3 of its 4 trials; the sensitivity check uses at least 2 of 4. Amendment 2
# (Qwen, 2 trials): 2 of 2, and 1 of 2 for the sensitivity check.
# Trials -> (majority, sensitivity majority).
MAJORITY = {4: (3, 2), 2: (2, 1)}


def pass_hat_k(num_trials: int, success_count: int, k: int) -> float:
    """tau2's pass^k for one task (`tau2.metrics.agent_metrics.pass_hat_k`):
    the chance that k trials drawn without replacement all succeed."""
    if num_trials < k:
        raise ValueError(f"{num_trials} trials is fewer than k = {k}")
    return math.comb(success_count, k) / math.comb(num_trials, k)


def pass_hat_k_mean(successes: np.ndarray, trials: np.ndarray, k: int) -> float:
    """Mean pass^k over tasks (1-d arrays; NaN tasks are skipped)."""
    keep = ~(np.isnan(successes) | np.isnan(trials))
    values = [
        pass_hat_k(int(n), int(s), k)
        for s, n in zip(successes[keep], trials[keep], strict=True)
    ]
    return float(np.mean(values)) if values else math.nan


def drop_incomplete(successes: np.ndarray, trials: np.ndarray, planned):
    """Per-task success rates [task, model, condition]; a task with any
    conversation missing for a model is NaN in every condition of that model.
    `planned` is the planned trials: one number, or one per model."""
    with np.errstate(invalid="ignore", divide="ignore"):
        rates = successes / trials
    incomplete = (trials < np.reshape(planned, (1, -1, 1))).any(axis=2, keepdims=True)
    return np.where(incomplete, np.nan, rates)


def bootstrap_means(
    rates: np.ndarray, n_resamples: int = N_RESAMPLES, seed: int = SEED
) -> np.ndarray:
    """Paired bootstrap over tasks (plan Section 6.1).

    Each resample draws the tasks with replacement once and keeps every model
    and condition of a drawn task together, so differences between conditions
    and between models are paired. Returns the mean over the drawn tasks,
    shape (n_resamples, *rates.shape[1:]). With a fixed seed and task count the
    draws do not depend on which models are present, so adding models later
    leaves the earlier models' intervals unchanged.
    """
    n_tasks = rates.shape[0]
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n_tasks, size=(n_resamples, n_tasks))
    out = np.empty((n_resamples, *rates.shape[1:]))
    # In chunks, to keep memory small.
    for start in range(0, n_resamples, 1000):
        chunk = rates[draws[start : start + 1000]]
        with np.errstate(invalid="ignore"):
            out[start : start + 1000] = np.nanmean(chunk, axis=1)
    return out


def percentile_ci(samples: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    tail = 100 * (1 - level) / 2
    low, high = np.nanpercentile(samples, [tail, 100 - tail])
    return float(low), float(high)


def mcnemar_exact(solved_a: np.ndarray, solved_b: np.ndarray) -> tuple[int, int, float]:
    """Exact McNemar test: a two-sided binomial test on the discordant tasks.

    Returns (b, c, p): b tasks solved only under A, c solved only under B.
    """
    a = np.asarray(solved_a, dtype=bool)
    b_ = np.asarray(solved_b, dtype=bool)
    b = int(np.sum(a & ~b_))
    c = int(np.sum(~a & b_))
    n = b + c
    if n == 0:
        return b, c, 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return b, c, min(1.0, 2 * tail)


def holm(p_values: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted
