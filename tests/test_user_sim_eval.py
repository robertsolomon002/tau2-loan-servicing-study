"""Checks for the Stage 3.3 simulator evaluation: language detection and labels."""

import pytest
from user_sim_eval import (
    CANDIDATES,
    LANGS,
    classify,
    error_summary,
    load_labels,
    task_ids,
)

TYPES = {"early_reveal", "contradiction", "wrong_end", "language_switch"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # French names alone must not count as a French turn.
        ("Émilie Bouchard, 2000-09-22, J2V 3E7", "short"),
        (
            (
                "My name is Amélie Singh, my date of birth is 1955-01-04, and my "
                "postal code is G1E 8P5."
            ),
            "en",
        ),
        ("Oui, je confirme le paiement de 150 $ à la Banque Fleuve.", "fr"),
        ("Thanks, that is all. ###STOP###", "en"),
        ("OK", "short"),
    ],
)
def test_classify(text, expected):
    assert classify(text) == expected


def test_labels_cover_every_conversation_with_valid_values():
    labels = load_labels()
    expected = {
        f"{c}/{t}" for c in CANDIDATES for lang in LANGS for t in task_ids(lang)
    }
    assert set(labels) == expected
    for errors in labels.values():
        for e in errors:
            assert e["type"] in TYPES
            assert e["severity"] in {"major", "minor"}
            assert e["note"]


def test_error_summary_counts_match_labels():
    labels = load_labels()
    total = sum(r["convs_with_error"] for r in error_summary())
    assert total == sum(bool(v) for v in labels.values())
