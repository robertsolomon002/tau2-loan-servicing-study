"""Stage 5.3 figures and the main LaTeX table, drawn from `results/summary.csv`.

Every plotted number is read from `summary.csv` (written by `analysis.report`)
and saved with its keys in `results/figures/figure_data.csv`; `verify` checks
each one against `summary.csv` again, so a figure cannot drift from the
results. Vector PDF for the report, PNG for the blog.

Colour: conditions use slots 1 to 3 of the dataviz reference palette (blue,
orange, aqua), checked all-pairs for colour-blind separation; aqua is below
3:1 contrast on white, so every condition also has its own marker and a
legend, and the LaTeX table is the table view.

Usage (from the study repo):
    uv run --no-sync python -m analysis.figures
"""

from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from analysis.load import CONDITIONS, MODEL_NAMES, MODELS, REPO

SUMMARY_CSV = REPO / "results" / "summary.csv"
OUT = REPO / "results" / "figures"

COLOR = {"C1": "#2a78d6", "C2": "#eb6834", "C3": "#1baf7a"}
MARKER = {"C1": "o", "C2": "s", "C3": "^"}
COND_LABEL = {
    "C1": "C1: EN policy, EN customer",
    "C2": "C2: EN policy, FR customer",
    "C3": "C3: FR policy, FR customer",
}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SHORT = {
    "qwen": "Qwen 3.8 27B\n(2 trials)",
    "nemotron": "Nemotron 3\nUltra",
    "deepseek": "DeepSeek V4\nFlash",
    "flash_lite": "Gemini 3.1\nFlash-Lite",
    "gemini_pro": "Gemini 3.1\nPro",
}
DO_NOTHING = 13 / 48

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": INK_2,
        "axes.labelcolor": INK,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "legend.frameon": False,
        "lines.linewidth": 2,
        "pdf.fonttype": 42,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    }
)
PCT = FuncFormatter(lambda v, _: f"{100 * v:.0f}%")


class Data:
    """Reads `summary.csv` and logs every value a figure uses."""

    def __init__(self, summary: pd.DataFrame):
        self.s = summary
        self.used: list[dict] = []
        self.models = [m for m in MODELS if m in set(summary["model"].dropna())]

    def get(
        self, section, metric, *, model="", condition="", comparison="", detail=None
    ):
        s = self.s
        mask = (s["section"] == section) & (s["metric"] == metric)
        for col, val in (("model", model), ("condition", condition),
                         ("comparison", comparison)):  # fmt: skip
            mask &= s[col].fillna("") == val
        if detail is not None:
            mask &= s["detail"].fillna("") == detail
        rows = s[mask]
        if len(rows) != 1:
            raise KeyError(f"{len(rows)} rows for {section}/{metric}/{model}/{condition}/{comparison}/{detail}")  # fmt: skip
        row = rows.iloc[0]
        self.used.append(row.to_dict())
        return row


def style_models(ax, models):
    ax.set_xticks(range(len(models)), [SHORT[m] for m in models])
    ax.grid(axis="x", visible=False)


def legend_conditions(ax, ncol=3):
    """Condition legend above `ax` (colour and marker; never colour alone)."""
    handles = [
        plt.Line2D([], [], color=COLOR[c], marker=MARKER[c], linestyle="none",
                   markersize=7, label=COND_LABEL[c])
        for c in CONDITIONS
    ]  # fmt: skip
    ax.legend(handles=handles, loc="lower center", ncol=ncol,
              bbox_to_anchor=(0.5, 1.02), borderaxespad=0)  # fmt: skip


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)


# ---------- figures ----------


def fig_pass1(d: Data):
    """(1) pass^1 by model and condition, with 95% paired-bootstrap intervals."""
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    offsets = dict(zip(CONDITIONS, (-0.22, 0, 0.22)))
    for i, m in enumerate(d.models):
        for c in CONDITIONS:
            r = d.get("confirmatory", "pass^1", model=m, condition=c)
            ax.errorbar(i + offsets[c], r["value"],
                        yerr=[[r["value"] - r["ci_low"]], [r["ci_high"] - r["value"]]],
                        color=COLOR[c], marker=MARKER[c], markersize=7, capsize=0,
                        elinewidth=1.5, markeredgecolor="white", markeredgewidth=1)  # fmt: skip
    style_models(ax, d.models)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(0.7, 1.005)
    ax.set_ylabel("pass^1 (mean task success)")
    ax.text(len(d.models) - 0.5, 0.71, f"Do-nothing baseline {100 * DO_NOTHING:.1f}% (off scale)",
            ha="right", va="bottom", color=INK_2, fontsize=8)  # fmt: skip
    legend_conditions(ax)
    save(fig, "fig1_pass1")


def fig_passk(d: Data):
    """(2) pass^k curves per condition, one panel per model."""
    fig, axes = plt.subplots(1, len(d.models), figsize=(9, 2.8), sharey=True)
    for ax, m in zip(axes, d.models):
        for c in CONDITIONS:
            ks, vals = [], []
            for k in range(1, 5):
                try:
                    r = d.get("secondary", f"pass^{k}", model=m, condition=c)
                except KeyError:
                    break  # Qwen has 2 trials: k <= 2 only
                ks.append(k)
                vals.append(r["value"])
            ax.plot(ks, vals, color=COLOR[c], marker=MARKER[c], markersize=6,
                    markeredgecolor="white", markeredgewidth=0.8)  # fmt: skip
        ax.set_title(SHORT[m].replace("\n", " "), fontsize=9)
        ax.set_xticks(range(1, 5))
        ax.set_xlim(0.7, 4.3)
        ax.set_xlabel("k")
    axes[0].yaxis.set_major_formatter(PCT)
    axes[0].set_ylabel("pass^k")
    handles = [
        plt.Line2D(
            [], [], color=COLOR[c], marker=MARKER[c], markersize=6, label=COND_LABEL[c]
        )
        for c in CONDITIONS
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.98))
    fig.tight_layout()
    save(fig, "fig2_passk")


def fig_diff(d: Data):
    """(3) Paired differences per model: C1 − C2 (H1) and C3 − C2 (H2)."""
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
    panels = (("C1-C2", "H1: C1 − C2\n(> 0: French customers did worse)"),
              ("C3-C2", "H2: C3 − C2\n(> 0: French policy did better)"))  # fmt: skip
    ys = np.arange(len(d.models))[::-1]
    for ax, (comp, title) in zip(axes, panels):
        for y, m in zip(ys, d.models):
            r = d.get("confirmatory", "pass^1 difference", model=m, comparison=comp)
            v, lo, hi = 100 * r["value"], 100 * r["ci_low"], 100 * r["ci_high"]
            excl = lo > 0 or hi < 0
            ax.plot([lo, hi], [y, y], color=INK if excl else INK_2, linewidth=2,
                    solid_capstyle="round")  # fmt: skip
            ax.plot(v, y, "o", color=INK if excl else "white", markersize=7,
                    markeredgecolor=INK, markeredgewidth=1.5)  # fmt: skip
            label = f"{v:+.1f} [{lo:+.1f}, {hi:+.1f}]".replace("-", "−")
            ax.text(12, y, label, va="center", fontsize=7.5, color=INK_2)  # fmt: skip
        ax.axvline(0, color=INK_2, linewidth=1)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("Difference in pass^1 (points)")
        ax.set_xlim(-14, 24)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(ys, [SHORT[m].replace("\n", " ") for m in d.models])
    fig.text(0.5, -0.06, "Filled dot: 95% interval excludes zero. Paired bootstrap over tasks.",
             ha="center", color=INK_2, fontsize=8)  # fmt: skip
    save(fig, "fig3_differences")


def fig_failures(d: Data):
    """(4) Failure-type composition by condition: majority labels of the three
    labellers on the 40-conversation sample (docs/FAILURES.md)."""
    rows = d.s[(d.s["metric"] == "failure type count")]
    causes = rows["detail"].str.split("; ").str[1].unique().tolist()
    counts = {c: {cause: d.get("confirmatory", "failure type count", condition=c,
                               detail=f"H4; {cause}; majority label on the review sample")
                  for cause in causes} for c in CONDITIONS}  # fmt: skip
    total = {
        cause: sum(counts[c][cause]["value"] for c in CONDITIONS) for cause in causes
    }
    causes = [c for c in sorted(causes, key=lambda x: total[x]) if total[c] > 0]
    fig, axes = plt.subplots(1, 3, figsize=(8.5, 3.0), sharey=True, sharex=True)
    for ax, c in zip(axes, CONDITIONS):
        vals = [counts[c][cause]["value"] for cause in causes]
        n = int(counts[c][causes[0]]["n"])
        ax.barh(range(len(causes)), vals, color=COLOR[c], height=0.7)
        for y, v in enumerate(vals):
            if v:
                ax.text(v + 0.15, y, f"{v:.0f}", va="center", fontsize=8, color=INK)
        ax.set_title(f"{c} (n = {n})", fontsize=9)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Failed conversations")
    axes[0].set_yticks(range(len(causes)), [c.replace("_", " ") for c in causes])
    fig.text(0.5, -0.08, "Majority label of three AI labellers on a random sample of 40 "
             "of the 147 judged failures; not validated by a human.",
             ha="center", color=INK_2, fontsize=8)  # fmt: skip
    save(fig, "fig4_failure_types")


def fig_language(d: Data):
    """(5) Agent language adherence by model and condition."""
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    offsets = dict(zip(CONDITIONS, (-0.22, 0, 0.22)))
    for i, m in enumerate(d.models):
        for c in CONDITIONS:
            r = d.get(
                "secondary", "agent turns in customer language", model=m, condition=c
            )
            ax.plot(i + offsets[c], r["value"], marker=MARKER[c], color=COLOR[c],
                    markersize=7, linestyle="none", markeredgecolor="white",
                    markeredgewidth=1)  # fmt: skip
            if r["value"] < 0.995:
                ax.text(i + offsets[c] + 0.08, r["value"], f"{100 * r['value']:.1f}%",
                        va="center", fontsize=8, color=INK)  # fmt: skip
    style_models(ax, d.models)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Agent turns in the\ncustomer's language")
    legend_conditions(ax)
    save(fig, "fig5_language")


def fig_cost(d: Data):
    """(6) Cost per successful conversation (agent + user simulator, list price)."""
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    offsets = dict(zip(CONDITIONS, (-0.22, 0, 0.22)))
    for i, m in enumerate(d.models):
        for c in CONDITIONS:
            r = d.get("secondary", "cost per success", model=m, condition=c)
            ax.plot(i + offsets[c], r["value"], marker=MARKER[c], color=COLOR[c],
                    markersize=7, linestyle="none", markeredgecolor="white",
                    markeredgewidth=1)  # fmt: skip
    style_models(ax, d.models)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    ax.set_ylabel("USD per success (log scale)")
    fig.text(0.5, -0.1, "Agent plus user simulator, LiteLLM list prices, all attempts. "
             "Qwen and Nemotron ran on free endpoints (agent cost $0).",
             ha="center", color=INK_2, fontsize=8)  # fmt: skip
    legend_conditions(ax)
    save(fig, "fig6_cost")


def latex_table(d: Data):
    """The main results table: pass^1 per condition and the H1/H2 differences."""

    def p(v):
        return f"{100 * v:.1f}"

    lines = [
        r"\begin{tabular}{lrrrll}",
        r"\toprule",
        r"Model & C1 & C2 & C3 & C1 $-$ C2 [95\% CI] & C3 $-$ C2 [95\% CI] \\",
        r"\midrule",
    ]
    for m in d.models:
        cells = [p(d.get("confirmatory", "pass^1", model=m, condition=c)["value"])
                 for c in CONDITIONS]  # fmt: skip
        for comp in ("C1-C2", "C3-C2"):
            r = d.get("confirmatory", "pass^1 difference", model=m, comparison=comp)
            cells.append(
                f"${100 * r['value']:+.1f}$ [${100 * r['ci_low']:+.1f}$, "
                f"${100 * r['ci_high']:+.1f}$]"
            )
        n = int(d.get("confirmatory", "pass^1", model=m, condition="C1")["n"])
        name = MODEL_NAMES[m] + (f" ({n} tasks, 2 trials)" if m == "qwen" else "")
        lines.append(f"{name} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "main_results.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- check ----------


def verify(used: pd.DataFrame, summary: pd.DataFrame) -> int:
    """Every plotted value must equal its row in summary.csv."""
    keys = ["section", "model", "condition", "comparison", "metric", "detail"]
    cols = ["value", "ci_low", "ci_high", "n"]
    a = used[keys + cols].fillna({k: "" for k in keys})
    b = summary[keys + cols].fillna({k: "" for k in keys})
    merged = a.merge(b, on=keys, how="left", suffixes=("", "_summary"))
    for col in cols:
        x, y = merged[col], merged[f"{col}_summary"]
        bad = ~(np.isclose(x, y, rtol=0, atol=1e-12) | (x.isna() & y.isna()))
        if bad.any():
            raise AssertionError(
                f"{int(bad.sum())} plotted {col} values differ from summary.csv"
            )
    return len(merged)


def build(summary: pd.DataFrame) -> pd.DataFrame:
    d = Data(summary)
    for fig in (fig_pass1, fig_passk, fig_diff, fig_failures, fig_language, fig_cost):
        fig(d)
    latex_table(d)
    used = pd.DataFrame(d.used).drop_duplicates()
    used.to_csv(OUT / "figure_data.csv", index=False)
    return used


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    summary = pd.read_csv(SUMMARY_CSV)
    build(summary)
    n = verify(pd.read_csv(OUT / "figure_data.csv"), pd.read_csv(SUMMARY_CSV))
    print(f"Wrote 6 figures (PDF, PNG) and main_results.tex to {OUT}; "
          f"{n} plotted values match summary.csv")  # fmt: skip


if __name__ == "__main__":
    main()
