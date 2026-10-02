"""Write the Stage 5.1 results: `results/summary.csv` and `results/RESULTS.md`.

Follows `docs/EXPERIMENT_PLAN.md` Section 6 (metrics and tests) and Section 7
(exclusions). Only models whose three cells are complete are analyzed; the
others are listed with their progress. The same command, unchanged, gives the
final results once every cell is complete.

Usage (from the study repo):
    uv run --no-sync python -m analysis.report
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import metrics
from analysis.load import (
    CONDITIONS,
    CUSTOMER_LANG,
    FRONTIER,
    MODEL_NAMES,
    MODELS,
    RAW,
    REPO,
    complete_models,
    load,
    model_configs,
)

SUMMARY_CSV = REPO / "results" / "summary.csv"
RESULTS_MD = REPO / "results" / "RESULTS.md"
TRIALS = 4
TASKS = 48
# An agent that never writes scores up to 13/48; 11/48 if it also never reads
# out an id (docs/DOMAIN_SPEC.md, plan Section 6.1).
DO_NOTHING = (13 / TASKS, 11 / TASKS)
USER_LANG_BAR = 0.95  # ROADMAP Section 9
FINISHED = ["done", "model_failure"]


# ---------- arrays ----------


def success_arrays(
    df: pd.DataFrame, models: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    """Successes and finished trials, indexed [task, model, condition]."""
    shape = (TASKS, len(models), len(CONDITIONS))
    successes, trials = np.zeros(shape), np.zeros(shape)
    sub = df[df["model"].isin(models) & df["status"].isin(FINISHED)]
    counts = (
        sub.assign(success=sub["success"].astype(bool))
        .groupby(["task", "model", "condition"], observed=True)["success"]
        .agg(["sum", "count"])
    )
    for (task, model, condition), row in counts.iterrows():
        i, j, k = task - 1, models.index(model), CONDITIONS.index(condition)
        successes[i, j, k], trials[i, j, k] = row["sum"], row["count"]
    return successes, trials


# ---------- formatting ----------


def pct(x: float) -> str:
    return "–" if x is None or math.isnan(x) else f"{100 * x:.1f}%"


def pts(x: float) -> str:
    return "–" if math.isnan(x) else f"{100 * x:+.1f}"


def ci_pct(ci: tuple[float, float]) -> str:
    return f"[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}]"


def ci_pts(ci: tuple[float, float]) -> str:
    return f"[{100 * ci[0]:+.1f}, {100 * ci[1]:+.1f}]"


def pval(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def excludes_zero(ci: tuple[float, float]) -> str:
    return "yes" if ci[0] > 0 or ci[1] < 0 else "no"


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


# ---------- the analysis ----------


class Report:
    """Computes every Section 6 quantity for the complete models, recording
    each number once for summary.csv and formatting it for RESULTS.md."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.models = complete_models(df)
        self.rows: list[dict] = []
        self.successes, self.trials = success_arrays(df, self.models)
        self.rates = metrics.drop_incomplete(self.successes, self.trials, TRIALS)
        self.boot = metrics.bootstrap_means(self.rates)
        with np.errstate(invalid="ignore"):
            self.pass1 = np.nanmean(self.rates, axis=0)

    def record(self, section, metric, value, *, model="", condition="",
               comparison="", ci=(math.nan, math.nan), n=None, detail=""):  # fmt: skip
        self.rows.append(
            {
                "section": section,
                "model": model,
                "condition": condition,
                "comparison": comparison,
                "metric": metric,
                "value": value,
                "ci_low": ci[0],
                "ci_high": ci[1],
                "n": n,
                "detail": detail,
            }
        )

    def mi(self, model: str) -> int:
        return self.models.index(model)

    def ci(self, model: str, condition: str) -> tuple[float, float]:
        return metrics.percentile_ci(
            self.boot[:, self.mi(model), CONDITIONS.index(condition)]
        )

    def diff(self, model: str, a: str, b: str):
        """pass^1(a) − pass^1(b) and its paired-bootstrap interval."""
        j, ka, kb = self.mi(model), CONDITIONS.index(a), CONDITIONS.index(b)
        value = self.pass1[j, ka] - self.pass1[j, kb]
        return value, metrics.percentile_ci(self.boot[:, j, ka] - self.boot[:, j, kb])

    def finished(self, models: list[str] | None = None) -> pd.DataFrame:
        models = models or self.models
        df = self.df
        return df[df["model"].isin(models) & (df["status"] == "done")]

    # ----- data -----

    def data_section(self) -> str:
        rows = []
        df = self.df
        for (model, condition), g in df.groupby(["model", "condition"], observed=True):
            status = g["status"].value_counts()
            finished = int(status.get("done", 0) + status.get("model_failure", 0))
            failed_attempts = int(g["attempts"].sum()) - finished
            other_endings = g.loc[
                g["termination"].notna() & (g["termination"] != "user_stop"),
                "termination",
            ].value_counts()
            for name, n in status.items():
                self.record("data", f"conversations_{name}", int(n), model=model,
                            condition=condition)  # fmt: skip
            self.record("data", "failed_attempts", failed_attempts, model=model,
                        condition=condition)  # fmt: skip
            rows.append(
                [
                    f"{model}_{condition}",
                    f"{finished} / {len(g)}",
                    int(status.get("model_failure", 0)),
                    int(status.get("missing", 0)),
                    int(status.get("pending", 0)),
                    failed_attempts,
                    ", ".join(f"{k} {v}" for k, v in other_endings.items()) or "none",
                    "analyzed" if model in self.models else "running",
                ]
            )
        return table(
            ["Cell", "Finished", "Model failures", "Missing", "Pending",
             "Failed attempts (rerun)", "Endings other than user_stop", "Status"],
            rows,
        )  # fmt: skip

    # ----- confirmatory -----

    def pass1_section(self) -> str:
        rows = []
        for model in self.models:
            cells = []
            for condition in CONDITIONS:
                value, ci = (
                    self.pass1[self.mi(model), CONDITIONS.index(condition)],
                    self.ci(model, condition),
                )
                n = int(np.sum(~np.isnan(self.rates[:, self.mi(model), 0])))
                self.record("confirmatory", "pass^1", value, model=model,
                            condition=condition, ci=ci, n=n,
                            detail="n = tasks; paired bootstrap over tasks")  # fmt: skip
                cells.append(f"{pct(value)} {ci_pct(ci)}")
            rows.append([MODEL_NAMES[model], *cells])
        rows.append(
            ["*Do-nothing baseline*", *[f"*≤ {pct(DO_NOTHING[0])}*"] * len(CONDITIONS)]
        )
        return table(["Model", "C1 EN/EN", "C2 EN/FR", "C3 FR/FR"], rows)

    def hypothesis_tests(self) -> tuple[str, str]:
        """H1 (C1 vs C2) and H2 (C3 vs C2), with Holm over every test run."""
        tests = []
        for model in self.models:
            tests.append(("H1", model, "C1", "C2"))
            tests.append(("H2", model, "C3", "C2"))
        results = []
        for hyp, model, a, b in tests:
            j = self.mi(model)
            value, ci = self.diff(model, a, b)
            keep = ~np.isnan(self.rates[:, j, 0])
            sa = self.successes[keep, j, CONDITIONS.index(a)]
            sb = self.successes[keep, j, CONDITIONS.index(b)]
            b1, c1, p = metrics.mcnemar_exact(
                sa >= metrics.MAJORITY, sb >= metrics.MAJORITY
            )
            _, _, p2 = metrics.mcnemar_exact(
                sa >= metrics.MAJORITY_SENSITIVITY, sb >= metrics.MAJORITY_SENSITIVITY
            )
            results.append([hyp, model, a, b, value, ci, b1, c1, p, p2])
        adjusted = metrics.holm([r[8] for r in results])
        out = {"H1": [], "H2": []}
        for (hyp, model, a, b, value, ci, b1, c1, p, p2), p_holm in zip(
            results, adjusted, strict=True
        ):
            comp = f"{a}-{b}"
            self.record("confirmatory", "pass^1 difference", value, model=model,
                        comparison=comp, ci=ci, detail=hyp)  # fmt: skip
            self.record("confirmatory", "mcnemar_p", p, model=model, comparison=comp,
                        detail=f"{hyp}; majority >=3/4; b={b1} c={c1}")  # fmt: skip
            self.record("confirmatory", "mcnemar_p_holm", p_holm, model=model,
                        comparison=comp, detail=f"{hyp}; Holm over {len(results)} tests")  # fmt: skip
            self.record("confirmatory", "mcnemar_p_sensitivity", p2, model=model,
                        comparison=comp, detail=f"{hyp}; majority >=2/4")  # fmt: skip
            j = self.mi(model)
            out[hyp].append(
                [
                    MODEL_NAMES[model],
                    pct(self.pass1[j, CONDITIONS.index(a)]),
                    pct(self.pass1[j, CONDITIONS.index(b)]),
                    f"{pts(value)} {ci_pts(ci)}",
                    excludes_zero(ci),
                    f"{b1} / {c1}",
                    pval(p),
                    pval(p_holm),
                    pval(p2),
                ]
            )
        headers = {
            "H1": ["Model", "C1", "C2", "C1 − C2, points [95% CI]", "CI excludes 0",
                   "Tasks solved only in C1 / only in C2", "McNemar p",
                   "Holm p", "p (≥2/4)"],
            "H2": ["Model", "C3", "C2", "C3 − C2, points [95% CI]", "CI excludes 0",
                   "Tasks solved only in C3 / only in C2", "McNemar p",
                   "Holm p", "p (≥2/4)"],
        }  # fmt: skip
        return table(headers["H1"], out["H1"]), table(headers["H2"], out["H2"])

    def h3_section(self) -> str:
        if FRONTIER not in self.models:
            return "Pending: the frontier model's cells are not complete."
        f = self.mi(FRONTIER)
        c1, c2 = CONDITIONS.index("C1"), CONDITIONS.index("C2")
        frontier_gap = self.pass1[f, c1] - self.pass1[f, c2]
        boot_frontier = self.boot[:, f, c1] - self.boot[:, f, c2]
        rows = []
        for model in self.models:
            if model == FRONTIER:
                continue
            j = self.mi(model)
            gap = self.pass1[j, c1] - self.pass1[j, c2]
            value = gap - frontier_gap
            ci = metrics.percentile_ci(
                self.boot[:, j, c1] - self.boot[:, j, c2] - boot_frontier
            )
            self.record("confirmatory", "gap minus frontier gap", value, model=model,
                        comparison="(C1-C2) - frontier (C1-C2)", ci=ci, detail="H3")  # fmt: skip
            rows.append(
                [MODEL_NAMES[model], pts(gap), pts(frontier_gap),
                 f"{pts(value)} {ci_pts(ci)}", excludes_zero(ci)]
            )  # fmt: skip
        return table(
            ["Model", "Its C1 − C2 gap", f"{MODEL_NAMES[FRONTIER]} gap",
             "Difference, points [95% CI]", "CI excludes 0"],
            rows,
        )  # fmt: skip

    # ----- secondary -----

    def pass_k_section(self) -> str:
        rows = []
        for model in self.models:
            j = self.mi(model)
            for condition in CONDITIONS:
                k_ = CONDITIONS.index(condition)
                keep = ~np.isnan(self.rates[:, j, k_])
                values = []
                for k in range(1, TRIALS + 1):
                    v = metrics.pass_hat_k_mean(
                        self.successes[keep, j, k_], self.trials[keep, j, k_], k
                    )
                    self.record("secondary", f"pass^{k}", v, model=model,
                                condition=condition, n=int(keep.sum()))  # fmt: skip
                    values.append(pct(v))
                rows.append([MODEL_NAMES[model], condition, *values])
        return table(
            ["Model", "Condition", "pass^1", "pass^2", "pass^3", "pass^4"], rows
        )

    def grouped_pass1(self, column: str, label: str) -> str:
        """pass^1 per task group, one 'C1 / C2 / C3' cell per model."""
        tasks = self.df.drop_duplicates("task").set_index("task")[column]
        groups = list(dict.fromkeys(tasks.sort_index()))
        rows = []
        for group in groups:
            idx = np.array([t - 1 for t, g in tasks.items() if g == group])
            cells = []
            for model in self.models:
                j = self.mi(model)
                parts = []
                for condition in CONDITIONS:
                    with np.errstate(invalid="ignore"):
                        v = float(
                            np.nanmean(self.rates[idx, j, CONDITIONS.index(condition)])
                        )
                    self.record("secondary", f"pass^1 by {column}", v, model=model,
                                condition=condition, n=len(idx), detail=str(group))  # fmt: skip
                    parts.append(f"{100 * v:.0f}")
                cells.append(" / ".join(parts))
            name = {True: "hard", False: "other"}.get(group, group)
            rows.append([name, len(idx), *cells])
        return table(
            [
                label,
                "Tasks",
                *[f"{MODEL_NAMES[m]} (C1 / C2 / C3, %)" for m in self.models],
            ],
            rows,
        )

    def language_section(self) -> tuple[str, str]:
        """Agent language adherence, and the user simulator's (Section 9 bar)."""
        done = self.finished()
        agent_rows, user_rows = [], []
        for (model, condition), g in done.groupby(
            ["model", "condition"], observed=True
        ):
            lang = CUSTOMER_LANG[condition]
            share = g["agent_in_lang"].sum() / g["agent_judged"].sum()
            any_other = (g["agent_other_lang"] > 0).mean()
            user_share = g["user_in_lang"].sum() / g["user_judged"].sum()
            any_user_other = (g["user_other_lang"] > 0).mean()
            n_turns, n_user = int(g["agent_judged"].sum()), int(g["user_judged"].sum())
            self.record("secondary", "agent turns in customer language", share,
                        model=model, condition=condition, n=n_turns)  # fmt: skip
            self.record("secondary", "conversations with an agent turn in the other language",
                        any_other, model=model, condition=condition, n=len(g))  # fmt: skip
            self.record("secondary", "user turns in task language", user_share,
                        model=model, condition=condition, n=n_user)  # fmt: skip
            self.record("secondary", "conversations with a user turn in the other language",
                        any_user_other, model=model, condition=condition, n=len(g))  # fmt: skip
            agent_rows.append(
                [MODEL_NAMES[model], condition, lang.upper(), pct(share), n_turns,
                 pct(any_other), int((g["agent_other_lang"] > 0).sum())]
            )  # fmt: skip
            user_rows.append(
                [MODEL_NAMES[model], condition, lang.upper(), pct(user_share), n_user,
                 int((g["user_other_lang"] > 0).sum()),
                 "yes" if user_share >= USER_LANG_BAR else "**no**"]
            )  # fmt: skip
        return (
            table(
                ["Model", "Condition", "Customer language", "Agent turns in it",
                 "Judged agent turns", "Conversations with any agent turn in the other language",
                 "(count)"],
                agent_rows,
            ),
            table(
                ["Model", "Condition", "Task language", "User turns in it",
                 "Judged user turns", "Conversations with a user turn in the other language",
                 "Meets the 95% bar"],
                user_rows,
            ),
        )  # fmt: skip

    def conversation_section(self) -> str:
        rows = []
        for (model, condition), g in self.finished().groupby(
            ["model", "condition"], observed=True
        ):
            for col in ("turns", "tool_calls", "tool_errors"):
                self.record("secondary", f"mean {col}", g[col].mean(), model=model,
                            condition=condition, n=len(g))  # fmt: skip
            rows.append(
                [MODEL_NAMES[model], condition, f"{g['turns'].mean():.1f}",
                 f"{g['tool_calls'].mean():.2f}", f"{g['tool_errors'].mean():.3f}"]
            )  # fmt: skip
        return table(["Model", "Condition", "Turns", "Tool calls", "Tool errors"], rows)

    def cost_section(self) -> str:
        df = self.df[self.df["model"].isin(self.models)]
        rows = []
        for (model, condition), g in df.groupby(["model", "condition"], observed=True):
            fin = g[g["status"].isin(FINISHED)]
            wins = int(fin["success"].astype(bool).sum())
            agent, user = g["agent_cost"].sum(), g["user_cost"].sum()
            total = agent + user
            per_success = total / wins if wins else math.nan
            for metric, value in (
                ("agent cost per conversation", agent / len(fin)),
                ("user simulator cost per conversation", user / len(fin)),
                ("total cost", total),
                ("cost per success", per_success),
            ):
                self.record("secondary", metric, value, model=model,
                            condition=condition, n=len(fin),
                            detail="USD, LiteLLM estimate, all attempts")  # fmt: skip
            rows.append(
                [MODEL_NAMES[model], condition, f"${agent / len(fin):.4f}",
                 f"${user / len(fin):.4f}", f"${total:.2f}", f"${per_success:.4f}"]
            )  # fmt: skip
        return table(
            ["Model", "Condition", "Agent $ / conversation",
             "User simulator $ / conversation", "Cell total", "$ / success"],
            rows,
        )  # fmt: skip

    def sensitivity_section(self) -> str:
        """Plan Section 7 rule 4(a): drop conversations with any user turn in
        the wrong language. Rule 4(b) needs the Stage 5.2 labels."""
        df = self.df
        wrong = df["status"].eq("done") & (df["user_other_lang"].fillna(0) > 0)
        successes, trials = success_arrays(df[~wrong], self.models)
        with np.errstate(invalid="ignore", divide="ignore"):
            rates = np.where(
                np.isnan(self.rates) | (trials == 0), np.nan, successes / trials
            )
            pass1 = np.nanmean(rates, axis=0)
        boot = metrics.bootstrap_means(rates)
        rows = []
        for model in self.models:
            j = self.mi(model)
            dropped = [
                int((wrong & (df["model"] == model) & (df["condition"] == c)).sum())
                for c in CONDITIONS
            ]
            cells = []
            for a, b in (("C1", "C2"), ("C3", "C2")):
                ka, kb = CONDITIONS.index(a), CONDITIONS.index(b)
                value = pass1[j, ka] - pass1[j, kb]
                ci = metrics.percentile_ci(boot[:, j, ka] - boot[:, j, kb])
                self.record("sensitivity", "pass^1 difference", value, model=model,
                            comparison=f"{a}-{b}", ci=ci,
                            detail="rule 4(a): user turns in the wrong language dropped")  # fmt: skip
                cells.append(f"{pts(value)} {ci_pts(ci)}")
            for k_, condition in enumerate(CONDITIONS):
                self.record("sensitivity", "pass^1", pass1[j, k_], model=model,
                            condition=condition, n=dropped[k_],
                            detail="rule 4(a); n = conversations dropped")  # fmt: skip
            rows.append(
                [MODEL_NAMES[model], " / ".join(map(str, dropped)),
                 " / ".join(pct(pass1[j, k]) for k in range(3)), *cells]
            )  # fmt: skip
        return table(
            ["Model", "Dropped (C1 / C2 / C3)", "pass^1 (C1 / C2 / C3)",
             "C1 − C2 [95% CI]", "C3 − C2 [95% CI]"],
            rows,
        )  # fmt: skip

    # ----- exploratory -----

    def language_switch_section(self) -> tuple[str, str]:
        """Plan Section 6.3: in C1 (English callers), does the agent switch to
        French more for borrowers whose DB record prefers French, or for
        borrowers with a French surname (Rob's alternative)?"""
        c1 = self.finished()
        c1 = c1[c1["condition"] == "C1"]
        rows = []
        for model in [*self.models, "all"]:
            g_model = c1 if model == "all" else c1[c1["model"] == model]
            for pref in ("fr", "en"):
                g = g_model[g_model["preferred_language"] == pref]
                switched = (g["agent_other_lang"] > 0).mean()
                turns = g["agent_other_lang"].sum() / g["agent_judged"].sum()
                self.record("exploratory", "C1 conversations with a French agent turn",
                            switched, model=model, n=len(g),
                            detail=f"preferred_language={pref}")  # fmt: skip
                rows.append(
                    [MODEL_NAMES.get(model, "All analyzed models"), pref,
                     g["task"].nunique(), len(g), pct(switched),
                     int((g["agent_other_lang"] > 0).sum()), pct(turns)]
                )  # fmt: skip
        by_pref = table(
            ["Model", "Borrower's preferred_language", "Tasks", "Conversations",
             "With a French agent turn", "(count)", "Agent turns in French"],
            rows,
        )  # fmt: skip
        rows = []
        for (pref, surname), g in c1.groupby(["preferred_language", "surname_group"]):
            switched = (g["agent_other_lang"] > 0).mean()
            self.record("exploratory", "C1 conversations with a French agent turn",
                        switched, model="all", n=len(g),
                        detail=f"preferred_language={pref}; surname={surname}")  # fmt: skip
            rows.append(
                [pref, surname, g["task"].nunique(), len(g), pct(switched),
                 int((g["agent_other_lang"] > 0).sum())]
            )  # fmt: skip
        by_name = table(
            ["preferred_language", "Surname", "Tasks", "Conversations",
             "With a French agent turn", "(count)"],
            rows,
        )  # fmt: skip
        return by_pref, by_name


# ---------- RESULTS.md ----------


def run_info(raw: Path, models: list[str]) -> dict:
    for model in models:
        path = raw / f"{model}_C1" / "cell.json"
        if path.exists():
            info = json.loads(path.read_text(encoding="utf-8"))
            return {k: (info.get(k) or "")[:7] for k in ("study_commit", "fork_commit")}
    return {"study_commit": "", "fork_commit": ""}


def build(df: pd.DataFrame, raw: Path) -> tuple[pd.DataFrame, str]:
    rep = Report(df)
    if not rep.models:
        raise SystemExit("No model has all three cells complete yet.")
    configs = model_configs()
    pending = [m for m in MODELS if m in configs and m not in rep.models]
    finished_n = int(df["status"].isin(FINISHED).sum())
    as_of = df["last_attempt"].dropna().max()
    info = run_info(raw, rep.models)
    final = not pending

    data = rep.data_section()
    pass1 = rep.pass1_section()
    h1, h2 = rep.hypothesis_tests()
    h3 = rep.h3_section()
    pass_k = rep.pass_k_section()
    by_category = rep.grouped_pass1("category", "Category")
    by_hard = rep.grouped_pass1("hard", "Hard task (Stage 2.3)")
    agent_lang, user_lang = rep.language_section()
    conv = rep.conversation_section()
    cost = rep.cost_section()
    sens = rep.sensitivity_section()
    switch_pref, switch_name = rep.language_switch_section()
    n_tests = 2 * len(rep.models)

    status_line = (
        "**Final:** every cell is complete."
        if final
        else (
            f"**Preliminary: {len(rep.models)} of {len(configs)} models.** "
            f"{', '.join(MODEL_NAMES[m] for m in rep.models)} are complete and "
            f"analyzed. Still running: "
            + ", ".join(
                f"{MODEL_NAMES[m]} ({int(df[(df['model'] == m) & df['status'].isin(FINISHED)].shape[0])} / 576)"
                for m in pending
            )
            + ". Their cells will be added by rerunning the same command; the "
            "numbers for the models above will not change (same data, same "
            "bootstrap draws), except the Holm-adjusted p-values, which can only "
            f"go up when the family grows from {n_tests} to "
            f"{2 * len(configs)} tests."
        )
    )

    md = f"""# Results (Stage 5.1)

Generated by `analysis/report.py` on {datetime.now(UTC).date().isoformat()}; do not edit by
hand. Every number is also in `results/summary.csv`. The analysis follows the
pre-registration, `docs/EXPERIMENT_PLAN.md` Sections 6 and 7.

{status_line}

- Data: {finished_n} of {len(df)} planned conversations finished, the last on
  {as_of[:16].replace("T", " ")} UTC. Runs used study commit `{info["study_commit"]}`
  and fork commit `{info["fork_commit"]}`; user simulator `gpt-5.4-mini`.
- pass^1 is the mean over the 48 tasks of each task's success rate over its 4
  trials. Intervals are 95% paired-bootstrap percentile intervals over tasks
  (10,000 resamples, seed 2026).
- **Do-nothing baseline:** an agent that never writes scores up to
  {pct(DO_NOTHING[0])} (13/48), or {pct(DO_NOTHING[1])} if it also never reads
  out an id.
- **What 48 tasks can detect:** a difference under about 10 points cannot be
  told apart from zero (plan Section 6.4). Conclusions rest on the intervals,
  not on p < 0.05.

## Data

{data}

## 1. Confirmatory (pre-registered)

### pass^1 by model and condition, with 95% intervals

{pass1}

### H1: is C2 (English policy, French customer) below C1 (English throughout)?

Positive differences mean French customers did worse. McNemar: exact test on
tasks solved in at least 3 of 4 trials; the last column uses at least 2 of 4.
Holm adjusts over the {n_tests} H1 and H2 tests run so far.

{h1}

### H2: is C3 (French policy, French customer) above C2?

Positive differences mean the French policy did better.

{h2}

### H3: is the C1 − C2 gap larger for the smaller and open models than for the frontier model?

Positive values mean a larger French gap than {MODEL_NAMES[FRONTIER]}'s.

{h3}

### H4: French-specific failure types

Pending: needs the Stage 5.2 failure classification.

## 2. Secondary

### pass^k (k = 1 to 4)

pass^k is the chance that k trials of a task all succeed, averaged over tasks
(tau2's formula). It shows consistency, not just average success.

{pass_k}

### pass^1 by task category

{by_category}

### pass^1 for the 17 hard tasks and the 31 others

{by_hard}

### Agent language adherence

Share of the agent's judged text turns written in the customer's language
(lingua with the Stage 3.3 cleaning; turns with fewer than two words left are
not judged).

{agent_lang}

### User-simulator language adherence

ROADMAP Section 9 requires at least 95% of user turns in the task's language.

{user_lang}

### Conversation length and tool use (means per conversation)

{conv}

### Cost

USD as metered by the runner from LiteLLM, including failed attempts. The
user simulator is paid in cash; DeepSeek from the OpenRouter credit (whose
meter reads about 25% above LiteLLM's estimate); the Gemini models from the
Google Cloud trial credit.

{cost}

### Sensitivity analysis (plan Section 7, rule 4)

(a) Conversations with any user turn in the wrong language dropped:

{sens}

(b) Conversations with a major user-simulator error dropped: pending (needs the
Stage 5.2 labels).

## 3. Exploratory (pre-specified)

### C1 language switch: English callers, French-preferring borrowers

Does the agent answer an English caller in French when the borrower's record
says `preferred_language: fr`?

{switch_pref}

### Rob's alternative: the borrower's French surname

Same C1 conversations, all analyzed models together, split by the record's
language and the surname (French-Canadian surnames of the DB generator;
"Martin" counts as ambiguous). If the surname drives the switch, the
`en` + `french` row should show it.

{switch_name}
"""
    return pd.DataFrame(rep.rows), md


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=RAW)
    args = parser.parse_args(argv)
    df = load(args.raw)
    summary, md = build(df, args.raw)
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.6g")
    RESULTS_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {SUMMARY_CSV.relative_to(REPO)} ({len(summary)} rows) and "
          f"{RESULTS_MD.relative_to(REPO)}")  # fmt: skip


if __name__ == "__main__":
    main()
