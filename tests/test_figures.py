"""Stage 5.3: the figures are drawn from summary.csv and every plotted value
matches it."""

import pandas as pd
import pytest

from analysis import figures


def test_figures_match_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(figures, "OUT", tmp_path)
    summary = pd.read_csv(figures.SUMMARY_CSV)
    used = figures.build(summary)
    assert figures.verify(used, summary) == len(used) > 100
    names = {p.name for p in tmp_path.iterdir()}
    for i, stem in enumerate(
        ["pass1", "passk", "differences", "failure_types", "language", "cost"], 1
    ):
        assert {f"fig{i}_{stem}.pdf", f"fig{i}_{stem}.png"} <= names
    assert "main_results.tex" in names


def test_verify_catches_a_changed_value():
    summary = pd.read_csv(figures.SUMMARY_CSV)
    used = summary[summary["metric"] == "pass^1"].copy()
    used.iloc[0, used.columns.get_loc("value")] += 0.01
    with pytest.raises(AssertionError):
        figures.verify(used, summary)
