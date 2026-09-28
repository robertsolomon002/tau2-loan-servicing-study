"""Generate the deterministic `loan_servicing` database (Stage 1.2).

Writes `db.json` for the fork and `data/planted_cases.json` for this repo. The
output depends only on the constants below, so running it twice gives
byte-identical files.

Usage:
    python scripts/generate_db.py [--db PATH] [--planted PATH]

Money model (documented in docs/DOMAIN_SPEC.md):
- Monthly payment from standard amortization, rounded to cents.
- Each installment pays interest of balance * rate / 12, the rest principal.
- Accrued interest today is simple daily interest (rate / 365) on the
  principal since the last installment that was paid.
- Missed installments add to the past-due amount; 1 missed is past_due_30,
  2 is past_due_60, 3 or more is charged_off.
- A late fee paid later is added to the next installment and allocated to fees.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from tau2.domains.loan_servicing.data_model import LoanServicingDB

TODAY = date(2026, 3, 16)
SEED = 2026
NUM_BORROWERS = 60
NUM_LOANS = 90

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = (
    REPO.parent / "tau2-bench" / "data" / "tau2" / "domains" / "loan_servicing"
) / "db.json"
DEFAULT_PLANTED_PATH = REPO / "data" / "planted_cases.json"

FIRST_NAMES = [
    "Sophie",
    "Olivier",
    "Camille",
    "Mathieu",
    "Chloé",
    "Gabriel",
    "Léa",
    "Samuel",
    "Émilie",
    "Thomas",
    "Julie",
    "Alexandre",
    "Nadia",
    "Vincent",
    "Isabelle",
    "Maxime",
    "Amélie",
    "Nicolas",
    "Sarah",
    "David",
    "Karine",
    "Jonathan",
    "Hélène",
    "Kevin",
    "Marie",
    "Daniel",
    "Priya",
    "Omar",
    "Lina",
    "Ethan",
    "Grace",
    "Liam",
    "Mei",
    "Noah",
    "Aisha",
    "Lucas",
    "Zoé",
    "Hugo",
]
LAST_NAMES = [
    "Gagnon",
    "Roy",
    "Côté",
    "Bouchard",
    "Gauthier",
    "Morin",
    "Lavoie",
    "Fortin",
    "Gagné",
    "Ouellet",
    "Pelletier",
    "Bélanger",
    "Lévesque",
    "Bergeron",
    "Leblanc",
    "Paquette",
    "Girard",
    "Simard",
    "Boucher",
    "Caron",
    "Nguyen",
    "Patel",
    "Wilson",
    "Campbell",
    "Anderson",
    "MacDonald",
    "Singh",
    "Haddad",
    "Chen",
    "Kowalski",
    "Martin",
    "Thompson",
]
BANKS = ["Banque Fleuve", "Érable Bank", "Northgate Bank", "Caisse Horizon"]
# Postal-code first letters: Quebec (H Montréal, G Québec, J) and Ontario.
QC_LETTERS = ["H", "H", "G", "J"]
ON_LETTERS = ["K", "L", "M", "N"]
QC_AREA = ["514", "438", "450", "418", "819"]
ON_AREA = ["416", "613", "905", "647"]
POSTAL_LETTERS = "ABCEGHJKLMNPRSTVXY"


def money(x: float | Decimal) -> float:
    """Round to cents, half up."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def monthly_payment(principal: float, rate: float, term: int) -> float:
    i = rate / 12
    return money(principal * i / (1 - (1 + i) ** -term))


def add_months(d: date, n: int, day: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, day)


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


@dataclass
class FeeSpec:
    amount: float
    assessed: date
    status: str  # open, waived, paid
    waived: date | None = None


@dataclass
class LoanSpec:
    borrower_idx: list[int]
    product: str
    origination: date
    principal: float
    rate: float
    term: int
    due_day: int  # original due day; see day_changes
    missed: int = 0
    returned_last: bool = False
    paid_off_on: date | None = None
    day_changes: list[tuple[date, int]] = field(default_factory=list)
    fees: list[FeeSpec] = field(default_factory=list)
    hardship: list[tuple[str, date]] = field(default_factory=list)
    autopay_day_offset: int | None = None  # due_day minus offset; None = off
    autopay_account: int = 0
    scheduled: tuple[float, date] | None = None
    case: str | None = None


PLAN_MONTHS = {"deferral_1": 1, "deferral_2": 2, "reduced_payment_3": 3}


def plan_window(plan: str, start: date) -> tuple[date, date]:
    end = add_months(start, PLAN_MONTHS[plan], 1) - timedelta(days=1)
    return start, end


def due_dates(spec: LoanSpec) -> list[date]:
    """All installment due dates from the first one to a little past maturity.

    `spec.due_day` is the original due day. A change on `change_date` moves the
    next due date after it to the new day in the same month (the policy rule).
    """
    changes = sorted(spec.day_changes)
    day = spec.due_day
    d = add_months(spec.origination, 1, day)
    dates: list[date] = []
    while len(dates) < spec.term + 6:
        for change_date, new_day in changes:
            prev = dates[-1] if dates else spec.origination
            if prev <= change_date < d:
                d, day = date(d.year, d.month, new_day), new_day
        dates.append(d)
        d = add_months(d, 1, day)
    return dates


def final_due_day(spec: LoanSpec) -> int:
    return max(spec.day_changes)[1] if spec.day_changes else spec.due_day


class Builder:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.borrowers: list[dict] = []
        self.loans: list[dict] = []
        self.payments: list[dict] = []
        self.fee_counter = 50001
        self.hardship_counter = 70001
        self.account_counter = 40001
        self.planted: dict[str, dict] = {}
        self.used_phones: set[str] = set()

    # ---------- borrowers ----------
    def postal_code(self, quebec: bool) -> str:
        r = self.rng
        first = r.choice(QC_LETTERS if quebec else ON_LETTERS)
        return (
            f"{first}{r.randint(0, 9)}{r.choice(POSTAL_LETTERS)} "
            f"{r.randint(0, 9)}{r.choice(POSTAL_LETTERS)}{r.randint(0, 9)}"
        )

    def phone(self, quebec: bool) -> str:
        # 555-0100 to 555-0199 are reserved for fictional use.
        while True:
            area = self.rng.choice(QC_AREA if quebec else ON_AREA)
            p = f"{area}-555-01{self.rng.randint(0, 99):02d}"
            if p not in self.used_phones:
                self.used_phones.add(p)
                return p

    def add_borrower(
        self,
        first: str | None = None,
        last: str | None = None,
        dob: str | None = None,
        quebec: bool | None = None,
        accounts: int = 1,
        third_parties: list[str] | None = None,
    ) -> int:
        r = self.rng
        idx = len(self.borrowers)
        quebec = r.random() < 0.7 if quebec is None else quebec
        first = first or r.choice(FIRST_NAMES)
        last = last or r.choice(LAST_NAMES)
        dob = (
            dob
            or date(
                r.randint(1955, 2002), r.randint(1, 12), r.randint(1, 28)
            ).isoformat()
        )
        ascii_name = (
            f"{first}.{last}".lower()
            .translate(str.maketrans("éèêëàâôîïçÉ", "eeeeaaoiice"))
            .replace(" ", "")
        )
        bank_accounts = []
        for _ in range(accounts):
            bank_accounts.append(
                {
                    "method_id": f"BA-{self.account_counter}",
                    "bank_name": r.choice(BANKS),
                    "last4": f"{r.randint(0, 9999):04d}",
                }
            )
            self.account_counter += 1
        self.borrowers.append(
            {
                "borrower_id": f"BF-{10001 + idx}",
                "first_name": first,
                "last_name": last,
                "date_of_birth": dob,
                "postal_code": self.postal_code(quebec),
                "email": f"{ascii_name}{10 + idx}@example.com",
                "phone": self.phone(quebec),
                "preferred_language": ("fr" if quebec and r.random() < 0.75 else "en"),
                "authorized_third_parties": third_parties or [],
                "bank_accounts": bank_accounts,
                "loan_ids": [],
            }
        )
        return idx

    # ---------- loans ----------
    def random_loan(self, borrower_idx: list[int]) -> LoanSpec:
        r = self.rng
        product = "auto" if r.random() < 0.45 else "personal"
        if product == "auto":
            principal = r.randrange(12000, 45001, 500)
            rate = r.choice([0.0499, 0.0599, 0.0699, 0.0799, 0.0899, 0.0999])
            term = r.choice([36, 48, 60, 72, 84])
        else:
            principal = r.randrange(3000, 25001, 250)
            rate = r.choice([0.0799, 0.0899, 0.0999, 0.1199, 0.1399, 0.1599])
            term = r.choice([12, 24, 36, 48, 60])
        months_ago = r.randint(3, min(term - 2, 48))
        origination = add_months(TODAY, -months_ago, r.randint(1, 28))
        due_day = r.choice([d for d in range(1, 29) if d != TODAY.day])
        spec = LoanSpec(
            borrower_idx, product, origination, principal, rate, term, due_day
        )
        roll = r.random()
        if roll < 0.08:
            spec.missed = 1
        elif roll < 0.12:
            spec.missed = 2
        if spec.missed == 0 and r.random() < 0.45:
            spec.autopay_day_offset = r.choice([0, 0, 1, 2, 3])
        return spec

    def build_loan(self, spec: LoanSpec) -> None:
        loan_idx = len(self.loans)
        loan_id = f"LN-{20001 + loan_idx}"
        borrower = self.borrowers[spec.borrower_idx[0]]
        method_id = borrower["bank_accounts"][spec.autopay_account]["method_id"]
        m = monthly_payment(spec.principal, spec.rate, spec.term)
        i = spec.rate / 12

        windows = [(p, *plan_window(p, s)) for p, s in spec.hardship]

        def plan_at(d: date) -> str | None:
            for plan, start, end in windows:
                if start <= d <= end:
                    return plan
            return None

        all_dues = due_dates(spec)
        past = [d for d in all_dues if d < TODAY]
        future = [d for d in all_dues if d > TODAY]
        if spec.paid_off_on:
            past = [d for d in past if d < spec.paid_off_on]
        missed_dues = past[-spec.missed :] if spec.missed else []

        fees = sorted(spec.fees, key=lambda f: f.assessed)
        paid_fees = [f for f in fees if f.status == "paid"]
        balance = spec.principal
        last_paid = spec.origination
        loan_payments = []
        for d in past:
            plan = plan_at(d)
            if plan in ("deferral_1", "deferral_2"):
                continue
            if d in missed_dues:
                if spec.returned_last and d == missed_dues[-1]:
                    loan_payments.append(
                        {
                            "amount": m,
                            "date": d,
                            "status": "returned",
                            "allocation": None,
                        }
                    )
                continue
            amount = money(m / 2) if plan == "reduced_payment_3" else m
            interest = money(balance * i)
            principal_part = money(amount - interest)
            if principal_part >= balance:
                principal_part = money(balance)
                amount = money(interest + principal_part)
            fee_part = 0.0
            while paid_fees and paid_fees[0].assessed < d:
                fee_part = money(fee_part + paid_fees.pop(0).amount)
            balance = money(balance - principal_part)
            last_paid = d
            loan_payments.append(
                {
                    "amount": money(amount + fee_part),
                    "date": d,
                    "status": "posted",
                    "allocation": {
                        "fees": fee_part,
                        "interest": interest,
                        "principal": principal_part,
                    },
                }
            )
            if balance <= 0:
                break

        closed = False
        if spec.paid_off_on and balance > 0:
            days = (spec.paid_off_on - last_paid).days
            interest = money(balance * spec.rate / 365 * days)
            loan_payments.append(
                {
                    "amount": money(balance + interest),
                    "date": spec.paid_off_on,
                    "status": "posted",
                    "allocation": {
                        "fees": 0.0,
                        "interest": interest,
                        "principal": balance,
                    },
                }
            )
            balance = 0.0
        if balance <= 0:
            closed = True

        # Late fees: one open fee per missed installment, plus explicit ones.
        fee_records = list(fees)
        for d in missed_dues:
            assessed = d + timedelta(days=10)
            if assessed <= TODAY:
                amount = float(min(65, max(25, round(0.05 * m))))
                fee_records.append(FeeSpec(amount, assessed, "open"))
        fee_records.sort(key=lambda f: f.assessed)
        fee_dicts = []
        for f in fee_records:
            fee_dicts.append(
                {
                    "fee_id": f"FE-{self.fee_counter}",
                    "type": "late_fee",
                    "amount": money(f.amount),
                    "assessed_date": f.assessed.isoformat(),
                    "status": f.status,
                    "waived_date": iso(f.waived),
                }
            )
            self.fee_counter += 1

        hardship_dicts = []
        for plan, start, end in windows:
            hardship_dicts.append(
                {
                    "hardship_id": f"HP-{self.hardship_counter}",
                    "plan": plan,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                }
            )
            self.hardship_counter += 1

        missed = len(missed_dues)
        active_plan = plan_at(TODAY)
        if closed:
            status = "paid_off"
        elif missed >= 3:
            status = "charged_off"
        elif active_plan:
            status = "in_hardship"
        else:
            status = {0: "current", 1: "past_due_30", 2: "past_due_60"}[missed]

        if status in ("paid_off", "charged_off"):
            next_due = None
        else:
            next_due = next(
                d for d in future if plan_at(d) not in ("deferral_1", "deferral_2")
            )
        due_day = final_due_day(spec)
        if closed:
            accrued = 0.0
        else:
            accrued = money(balance * spec.rate / 365 * (TODAY - last_paid).days)

        autopay = {"enabled": False, "method_id": None, "day": None}
        if spec.autopay_day_offset is not None and status not in (
            "paid_off",
            "charged_off",
        ):
            autopay = {
                "enabled": True,
                "method_id": method_id,
                "day": max(1, due_day - spec.autopay_day_offset),
            }

        if spec.scheduled:
            amount, when = spec.scheduled
            loan_payments.append(
                {
                    "amount": amount,
                    "date": when,
                    "status": "scheduled",
                    "allocation": None,
                }
            )

        for p in loan_payments:
            p["loan_id"] = loan_id
            p["method_id"] = method_id
            self.payments.append(p)

        self.loans.append(
            {
                "loan_id": loan_id,
                "borrower_ids": [
                    self.borrowers[b]["borrower_id"] for b in spec.borrower_idx
                ],
                "product": spec.product,
                "origination_date": spec.origination.isoformat(),
                "original_principal": money(spec.principal),
                "annual_rate": spec.rate,
                "term_months": spec.term,
                "monthly_payment": m,
                "principal_balance": money(balance),
                "accrued_interest": accrued,
                "due_day": due_day,
                "next_due_date": iso(next_due),
                "past_due_amount": money(m * missed) if status != "paid_off" else 0.0,
                "status": status,
                "autopay": autopay,
                "fees": fee_dicts,
                "due_date_changes": [
                    c.isoformat() for c, _ in sorted(spec.day_changes)
                ],
                "hardship_history": hardship_dicts,
            }
        )
        for b in spec.borrower_idx:
            self.borrowers[b]["loan_ids"].append(loan_id)
        if spec.case:
            self.planted[spec.case] = {
                "loan_id": loan_id,
                "borrower_ids": [
                    self.borrowers[b]["borrower_id"] for b in spec.borrower_idx
                ],
            }

    # ---------- planted cases (docs/DOMAIN_SPEC.md Section 5) ----------
    def planted_specs(self) -> list[LoanSpec]:
        b = self.add_borrower
        specs: list[LoanSpec] = []

        def loan(case: str, owner: list[int], **kw) -> LoanSpec:
            # Defaults vary per loan so planted loans don't look like clones.
            r = self.rng
            base = {
                "product": "personal",
                "origination": add_months(TODAY, -r.randint(14, 30), r.randint(1, 28)),
                "principal": float(r.randrange(5000, 15001, 250)),
                "rate": r.choice([0.0899, 0.0999, 0.1199, 0.1399]),
                "term": r.choice([36, 48, 60]),
                "due_day": 8,
            }
            base.update(kw)
            spec = LoanSpec(owner, **base, case=case)
            specs.append(spec)
            return spec

        # 1. Due date changes: about 5 months ago, and just over 12 months ago.
        loan(
            "due_change_recent",
            [b(quebec=True)],
            due_day=5,
            day_changes=[(date(2025, 10, 14), 22)],
        )
        loan(
            "due_change_old",
            [b(quebec=False)],
            due_day=12,
            origination=date(2023, 11, 20),
            day_changes=[(date(2025, 3, 1), 3)],
        )
        # 2. Next due date within 5 days, and one well after.
        loan("due_soon", [b()], due_day=20, origination=date(2024, 9, 25))
        loan("due_later", [b()], due_day=2, origination=date(2024, 8, 12))
        # 3. Loan age around the 6-month hardship threshold.
        loan(
            "young_loan",
            [b()],
            origination=date(2025, 11, 2),
            due_day=2,
            principal=6000.0,
            term=36,
        )
        loan(
            "six_month_loan",
            [b()],
            origination=date(2025, 9, 10),
            due_day=10,
            principal=7500.0,
            term=36,
        )
        # 4. Hardship history inside and outside the last 12 months.
        loan(
            "hardship_recent",
            [b()],
            origination=date(2023, 5, 15),
            due_day=15,
            hardship=[("deferral_1", date(2025, 6, 1))],
        )
        loan(
            "hardship_old",
            [b()],
            origination=date(2023, 2, 6),
            due_day=6,
            product="auto",
            principal=24000.0,
            rate=0.0699,
            term=60,
            hardship=[("deferral_1", date(2024, 12, 1))],
        )
        # 5. Open fees of 35, 50 and 65, and a recent waiver plus a new fee.
        loan(
            "fee_35_open",
            [b()],
            due_day=11,
            fees=[FeeSpec(35.0, date(2026, 2, 21), "open")],
        )
        loan(
            "fee_50_open_past_due_30",
            [b()],
            missed=1,
            due_day=4,
            product="auto",
            principal=52000.0,
            rate=0.0599,
            term=60,
            origination=date(2024, 1, 15),
        )
        loan(
            "fee_65_open",
            [b()],
            due_day=9,
            product="auto",
            principal=40000.0,
            rate=0.0899,
            term=36,
            origination=date(2024, 6, 3),
            fees=[FeeSpec(65.0, date(2026, 2, 19), "open")],
        )
        loan(
            "fee_waived_recently",
            [b()],
            due_day=13,
            fees=[
                FeeSpec(35.0, date(2025, 11, 10), "waived", date(2025, 11, 20)),
                FeeSpec(30.0, date(2026, 2, 23), "open"),
            ],
        )
        loan(
            "fee_paid_history",
            [b()],
            due_day=18,
            fees=[FeeSpec(40.0, date(2025, 8, 28), "paid")],
        )
        # 6. Every status.
        loan("past_due_30", [b()], missed=1, due_day=5)
        loan("past_due_60", [b()], missed=2, due_day=7)
        loan(
            "in_hardship",
            [b()],
            origination=date(2023, 9, 19),
            due_day=19,
            hardship=[("deferral_2", date(2026, 3, 1))],
        )
        loan(
            "paid_off",
            [b()],
            origination=date(2022, 5, 10),
            due_day=10,
            principal=5000.0,
            term=24,
            paid_off_on=date(2024, 4, 10),
        )
        loan("charged_off", [b()], missed=4, due_day=6, origination=date(2024, 2, 1))
        # 7. Third party, and a co-borrowed loan whose borrowers have other loans.
        tp = b(quebec=True, third_parties=["Marc Tremblay"])
        loan("third_party", [tp], due_day=24)
        p1, p2 = b(quebec=True, accounts=2), b(quebec=True)
        loan(
            "co_borrowed",
            [p1, p2],
            product="auto",
            principal=30000.0,
            rate=0.0599,
            term=72,
            origination=date(2024, 3, 21),
            due_day=21,
            autopay_day_offset=2,
            autopay_account=1,
        )
        loan("co_borrower_1_other", [p1], due_day=14)
        loan(
            "co_borrower_2_other",
            [p2],
            due_day=27,
            principal=4000.0,
            term=24,
            origination=date(2025, 1, 27),
        )
        # 8. Same name, different date of birth and postal code.
        s1 = b(first="Sophie", last="Gagnon", dob="1984-07-12", quebec=True)
        s2 = b(first="Sophie", last="Gagnon", dob="1991-02-03", quebec=False)
        loan("same_name_1", [s1], due_day=12)
        loan(
            "same_name_2",
            [s2],
            due_day=25,
            product="auto",
            principal=21000.0,
            rate=0.0799,
            term=60,
            origination=date(2023, 10, 25),
        )
        # 9. Two bank accounts, autopay on and off, due day at most 5.
        two = b(accounts=2)
        loan("autopay_on", [two], due_day=15, autopay_day_offset=3)
        loan("autopay_off_low_due_day", [b()], due_day=3)
        # 10. Scheduled, returned, and posted-only payments.
        loan(
            "scheduled_payment", [b()], due_day=26, scheduled=(500.0, date(2026, 3, 25))
        )
        loan("returned_payment", [b()], missed=1, returned_last=True, due_day=1)
        # 11. Too new for a tax summary.
        loan(
            "originated_2026",
            [b()],
            origination=date(2026, 1, 12),
            due_day=12,
            principal=8000.0,
            term=48,
        )
        return specs

    def build(self) -> dict:
        specs = self.planted_specs()
        while len(self.borrowers) < NUM_BORROWERS:
            self.add_borrower(accounts=self.rng.choice([1, 1, 1, 2]))
        for spec in specs:
            self.build_loan(spec)
        # Random loans: every borrower without a loan gets one, then extras.
        empty = [i for i, x in enumerate(self.borrowers) if not x["loan_ids"]]
        owners = empty + [
            self.rng.randrange(len(self.borrowers))
            for _ in range(NUM_LOANS - len(specs) - len(empty))
        ]
        for owner in owners:
            self.build_loan(self.random_loan([owner]))

        self.payments.sort(key=lambda p: (p["date"], p["loan_id"]))
        payments = {}
        for n, p in enumerate(self.payments):
            pid = f"PM-{30001 + n}"
            payments[pid] = {
                "payment_id": pid,
                "loan_id": p["loan_id"],
                "amount": p["amount"],
                "date": p["date"].isoformat(),
                "method_id": p["method_id"],
                "status": p["status"],
                "allocation": p["allocation"],
            }
        return {
            "borrowers": {x["borrower_id"]: x for x in self.borrowers},
            "loans": {x["loan_id"]: x for x in self.loans},
            "payments": payments,
            "document_requests": {},
            "transfers": {},
        }


def generate() -> tuple[dict, dict]:
    builder = Builder()
    db = builder.build()
    LoanServicingDB.model_validate(db)
    return db, builder.planted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--planted", type=Path, default=DEFAULT_PLANTED_PATH)
    args = parser.parse_args()
    db, planted = generate()
    # ASCII escapes keep the file readable by tau2's load_file on any platform.
    args.db.parent.mkdir(parents=True, exist_ok=True)
    args.db.write_text(json.dumps(db, indent=2) + "\n", encoding="ascii")
    args.planted.parent.mkdir(parents=True, exist_ok=True)
    args.planted.write_text(json.dumps(planted, indent=2) + "\n", encoding="ascii")
    stats = LoanServicingDB.model_validate(db).get_statistics()
    print(f"Wrote {args.db} and {args.planted}: {stats}")


if __name__ == "__main__":
    main()
