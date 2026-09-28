"""Tests for scripts/generate_db.py: determinism and the planted edge cases.

The planted cases are listed in docs/DOMAIN_SPEC.md Section 5. Each test names
the policy rule the case exists for.
"""

import json
from datetime import date

import pytest
from generate_db import DEFAULT_DB_PATH, DEFAULT_PLANTED_PATH, TODAY, generate

ONE_YEAR_AGO = "2025-03-16"  # "within the last 12 months" means on or after this
SIX_MONTHS_AGO = "2025-09-16"


@pytest.fixture(scope="module")
def generated():
    return generate()


@pytest.fixture(scope="module")
def db(generated):
    return generated[0]


@pytest.fixture(scope="module")
def planted(generated):
    return generated[1]


def loan(db, planted, case):
    return db["loans"][planted[case]["loan_id"]]


def open_fees(loan_record):
    return [f["amount"] for f in loan_record["fees"] if f["status"] == "open"]


def test_generation_is_deterministic(generated):
    assert generate() == generated


def test_committed_files_match_generator(db, planted):
    assert json.loads(DEFAULT_DB_PATH.read_text(encoding="ascii")) == db
    assert json.loads(DEFAULT_PLANTED_PATH.read_text(encoding="ascii")) == planted


def test_sizes(db):
    assert len(db["borrowers"]) == 60
    assert len(db["loans"]) == 90
    assert all(b["loan_ids"] for b in db["borrowers"].values())


# D1: due date changes
def test_due_change_recent(db, planted):
    x = loan(db, planted, "due_change_recent")
    assert x["status"] == "current"
    assert [c for c in x["due_date_changes"] if c >= ONE_YEAR_AGO]
    assert date.fromisoformat(x["next_due_date"]) > date(2026, 3, 21)


def test_due_change_old(db, planted):
    x = loan(db, planted, "due_change_old")
    assert x["status"] == "current"
    assert x["due_date_changes"] and max(x["due_date_changes"]) < ONE_YEAR_AGO


def test_due_soon_and_later(db, planted):
    assert loan(db, planted, "due_soon")["next_due_date"] == "2026-03-20"
    assert loan(db, planted, "due_later")["next_due_date"] == "2026-04-02"


def test_due_exactly_five_days_away(db, planted):
    # Boundary for "more than 5 days after today": 2026-03-21 is not allowed.
    assert loan(db, planted, "co_borrowed")["next_due_date"] == "2026-03-21"


# H1: hardship eligibility
def test_loan_age_around_six_months(db, planted):
    assert loan(db, planted, "young_loan")["origination_date"] > SIX_MONTHS_AGO
    assert loan(db, planted, "six_month_loan")["origination_date"] <= SIX_MONTHS_AGO


def test_hardship_history(db, planted):
    recent = loan(db, planted, "hardship_recent")
    old = loan(db, planted, "hardship_old")
    assert recent["hardship_history"][0]["start_date"] >= ONE_YEAR_AGO
    assert old["hardship_history"][0]["start_date"] < ONE_YEAR_AGO
    assert recent["status"] == old["status"] == "current"


# F1: late fee waivers
def test_fee_amounts(db, planted):
    assert open_fees(loan(db, planted, "fee_35_open")) == [35.0]
    assert loan(db, planted, "fee_35_open")["status"] == "current"
    fee_50 = loan(db, planted, "fee_50_open_past_due_30")
    assert open_fees(fee_50) == [50.0] and fee_50["status"] == "past_due_30"
    assert open_fees(loan(db, planted, "fee_65_open")) == [65.0]


def test_fee_waived_within_last_year(db, planted):
    x = loan(db, planted, "fee_waived_recently")
    waived = [f for f in x["fees"] if f["status"] == "waived"]
    assert waived and waived[0]["waived_date"] >= ONE_YEAR_AGO
    assert open_fees(x) and max(open_fees(x)) <= 50


def test_fee_paid_through_payment(db, planted):
    x = loan(db, planted, "fee_paid_history")
    assert [f["status"] for f in x["fees"]] == ["paid"]
    payments = [p for p in db["payments"].values() if p["loan_id"] == x["loan_id"]]
    assert any(p["allocation"] and p["allocation"]["fees"] > 0 for p in payments)


# Loan statuses
@pytest.mark.parametrize(
    "case,status",
    [
        ("past_due_30", "past_due_30"),
        ("past_due_60", "past_due_60"),
        ("in_hardship", "in_hardship"),
        ("paid_off", "paid_off"),
        ("charged_off", "charged_off"),
    ],
)
def test_statuses(db, planted, case, status):
    assert loan(db, planted, case)["status"] == status


def test_every_status_exists(db):
    statuses = {x["status"] for x in db["loans"].values()}
    assert statuses == {
        "current",
        "past_due_30",
        "past_due_60",
        "in_hardship",
        "paid_off",
        "charged_off",
    }


# A1 to A4: authorization
def test_third_party(db, planted):
    borrower = db["borrowers"][planted["third_party"]["borrower_ids"][0]]
    assert borrower["authorized_third_parties"] == ["Marc Tremblay"]


def test_co_borrowed_loan(db, planted):
    x = loan(db, planted, "co_borrowed")
    assert len(x["borrower_ids"]) == 2
    for borrower_id in x["borrower_ids"]:
        assert len(db["borrowers"][borrower_id]["loan_ids"]) >= 2


def test_same_name_borrowers(db, planted):
    a = db["borrowers"][planted["same_name_1"]["borrower_ids"][0]]
    b = db["borrowers"][planted["same_name_2"]["borrower_ids"][0]]
    assert (a["first_name"], a["last_name"]) == (b["first_name"], b["last_name"])
    assert a["date_of_birth"] != b["date_of_birth"]
    assert a["postal_code"] != b["postal_code"]


# U1 and P3: autopay and payment methods
def test_autopay_cases(db, planted):
    on = loan(db, planted, "autopay_on")
    assert on["autopay"]["enabled"]
    assert len(db["borrowers"][on["borrower_ids"][0]]["bank_accounts"]) == 2
    off = loan(db, planted, "autopay_off_low_due_day")
    assert not off["autopay"]["enabled"] and off["due_day"] <= 5


# P5: payment statuses
def test_payment_statuses(db, planted):
    def statuses(case):
        loan_id = planted[case]["loan_id"]
        return {p["status"] for p in db["payments"].values() if p["loan_id"] == loan_id}

    assert "scheduled" in statuses("scheduled_payment")
    assert "returned" in statuses("returned_payment")
    assert statuses("due_soon") == {"posted"}


# C1: tax summary eligibility
def test_originated_2026(db, planted):
    assert loan(db, planted, "originated_2026")["origination_date"] >= "2026-01-01"


# COMMUNICATE: small numbers exist
def test_small_numbers_for_communicate(db):
    past_due = [x["past_due_amount"] for x in db["loans"].values()]
    assert any(0 < a < 1000 for a in past_due)
    assert sum(x["monthly_payment"] < 1000 for x in db["loans"].values()) > 45


def test_no_due_date_today(db):
    for x in db["loans"].values():
        assert x["next_due_date"] != TODAY.isoformat()
