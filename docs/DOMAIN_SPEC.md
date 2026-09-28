# `loan_servicing` domain spec

Stage 1.1, 2026-09-28. The agent-facing policy is `../tau2-bench/data/tau2/domains/loan_servicing/policy.md`. This file maps each policy rule to the data and tools that make it checkable, and lists the edge cases that become tasks (Stage 2.1) and DB records (Stage 1.2).

It supersedes ROADMAP Sections 4.1 and 4.2 where they differ (Section 1). Internals referenced as "Flag N" are in `docs/TAU2_NOTES.md` Section 1.

## 1. Changes from ROADMAP 4.1 to 4.3

| Change | Why |
|---|---|
| **Case notes removed.** Hardship enrollments and transfers get their own structured records instead. | Free text in the DB breaks the hash check (Flag 1). |
| **`transfer_to_human_agents(reason, summary)` is a WRITE tool** that stores only `{transfer_id, reason}`. The `summary` argument is accepted but **not stored**, and no borrower id is stored either (whether the agent passes one would be arbitrary and would break the hash). `reason` is an enum. | Otherwise transfers are invisible to the DB check (Flag 2), and unnecessary transfers would go unpunished. |
| **Reference numbers**: new records get deterministic ids (next number after the highest existing one), and the policy tells the agent to read them out. | Gives language-neutral `COMMUNICATE` values (`PM-30112`) and deterministic replay (Flag 6). |
| **Id formats** follow the linter pattern `^[A-Z]{2}-\d{4,6}$`: `BF-` borrower, `LN-` loan, `PM-` payment, `BA-` bank account, `FE-` fee, `DR-` document request, `HP-` hardship enrollment, `TR-` transfer. | ROADMAP examples like `L-1042` would fail the linter. |
| **Late fee waiver** now needs status `current` or `past_due_30`, replacing the vague "must not remain past due after the waiver". Also a new ordering rule: waiver before payment. | Checkable from status alone; creates a clear multi-request task. |
| **Autopay "next cycle" notice** replaced by checkable rules: eligible statuses and an allowed day window. | The notice was only checkable by an LLM judge. |
| **New rules**: third-party verification details, one borrower per conversation, email-change security rule, `tax_summary` eligibility, `charged_off` and `paid_off` handling, "customer asks for a human" transfer. | Each closes a gap that would make a task ambiguous. |
| **Data model additions**: `past_due_amount` and `waived_date` on fees, an `id` on hardship entries, top-level `transfers` and `document_requests`, and `authorized_third_parties` as full names. | Needed to check the rules above. |
| **Fixed date**: today is 2026-03-16 (a Monday). | As planned (ROADMAP 4.1). |

## 2. Data model (for Stage 1.2)

All money is CAD, stored as numbers rounded to 2 decimals. All dates are `YYYY-MM-DD` strings.

- **Borrower** (`borrowers: dict[borrower_id, Borrower]`): `borrower_id`, `first_name`, `last_name`, `date_of_birth`, `postal_code` (such as `H2X 1Y4`), `email`, `phone`, `preferred_language` (`en` or `fr`), `authorized_third_parties` (list of full names), `bank_accounts` (list of `{method_id, bank_name, last4}`), `loan_ids`.
- **Loan** (`loans: dict[loan_id, Loan]`): `loan_id`, `borrower_ids` (primary first), `product` (`personal` or `auto`), `origination_date`, `original_principal`, `annual_rate`, `term_months`, `monthly_payment`, `principal_balance`, `accrued_interest` (as of today), `due_day`, `next_due_date`, `past_due_amount`, `status`, `autopay` (`{enabled, method_id, day}`), `fees` (list of `{fee_id, type: late_fee, amount, assessed_date, status: open|waived|paid, waived_date}`), `due_date_changes` (list of dates), `hardship_history` (list of `{hardship_id, plan, start_date, end_date}`).
- **Payment** (`payments: dict[payment_id, Payment]`): `payment_id`, `loan_id`, `amount`, `date`, `method_id`, `status` (`posted`, `scheduled`, `cancelled`, `returned`), `allocation` (`{fees, interest, principal}` for posted payments, otherwise null).
- **Document request** (`document_requests: dict`): `request_id`, `loan_id`, `borrower_id`, `doc_type`, `sent_to` (copied from the email on file).
- **Transfer** (`transfers: dict`): `transfer_id`, `reason`.

## 3. Tools (for Stage 1.3)

Tools check data integrity only (ids exist, amounts are positive, the method belongs to a borrower on the loan, dates are valid, the enums are valid, a payment being cancelled is `scheduled`). They never check policy. **No tool has optional parameters**: some providers reject `anyOf [type, null]` schemas (found in Stage 1.3; the official domains have none either), so autopay and contact updates are split into separate tools. That makes 19 tools in total.

| Tool | Type | Effect / returns |
|---|---|---|
| `find_borrower_by_email(email)` | READ | borrower_id |
| `find_borrower_by_phone(phone)` | READ | borrower_id |
| `find_borrower_by_name_dob(first_name, last_name, date_of_birth)` | READ | borrower_id |
| `get_borrower_details(borrower_id)` | READ | Borrower |
| `get_loan_details(loan_id)` | READ | Loan |
| `list_payments(loan_id, limit=12)` | READ | payments on the loan, most recent first (limit keeps tool output short) |
| `calculate_payoff(loan_id, payoff_date)` | READ | principal + accrued interest to that date (simple daily interest, rate / 365) + open fees |
| `calculate(expression)` | GENERIC | as in airline |
| `make_payment(loan_id, amount, method_id, payment_date)` | WRITE | new `PM-` id; posted if dated today (allocation, past-due amount and status updated), otherwise scheduled. Rejects an amount above the payoff on that date (integrity: no negative balance), so the P1 "refuse the excess" rule is partly tool-enforced. Fees are paid oldest first, each only if fully covered. |
| `cancel_scheduled_payment(payment_id)` | WRITE | status becomes `cancelled` |
| `enable_autopay(loan_id, method_id, day)` | WRITE | replaces the autopay settings (also used to change the method or day) |
| `disable_autopay(loan_id)` | WRITE | turns autopay off |
| `change_due_date(loan_id, new_day)` | WRITE | sets `due_day`, moves `next_due_date` within its month, appends today to `due_date_changes` |
| `waive_late_fee(loan_id, fee_id)` | WRITE | fee becomes `waived`, `waived_date` = today |
| `enroll_hardship_plan(loan_id, plan)` | WRITE | new `HP-` entry; status `in_hardship`; deferrals clear the past-due amount and push the next due date by 1 or 2 months |
| `update_email(borrower_id, email)` | WRITE | sets the email, trimmed and lowercased so harmless formatting differences do not break the hash |
| `update_phone(borrower_id, phone)` | WRITE | sets the phone, normalized to `NNN-NNN-NNNN` |
| `send_document(loan_id, borrower_id, doc_type)` | WRITE | new `DR-` id; `sent_to` = that borrower's email on file |
| `transfer_to_human_agents(reason, summary)` | WRITE | new `TR-` id; stores only the id and reason |

## 4. Rules, how each is checked, and the edge cases it creates

How a rule is checked:
- **DB**: a violation changes the final DB. A wrongly taken action adds or changes records, and a wrongly refused one leaves them missing.
- **COMM**: checked through a reference number or a small number the agent must say.
- **Unscored**: conduct the benchmark can't observe. It stays in the policy for realism, and no task depends on it.

| Id | Rule | Data / tools | How checked | Edge cases (task seeds) |
|---|---|---|---|---|
| V1 | Name, date of birth and postal code must all match before any info or action | borrower fields; find tools | DB (an action by an unverified caller) | correct name and DOB but wrong postal code, then asks to pay → no payment; knows the email but not the DOB |
| V2 | Two failed verifications → transfer `failed_verification` | `transfers` | DB | fails twice → TR record; fails once, then succeeds → normal service, no transfer |
| A1 | Borrowers on a loan (co-borrowers too) may act | `loan.borrower_ids` | DB | co-borrower makes a payment on the shared loan → allowed |
| A2 | Third party: verified by own name plus borrower's 3 values; general info only; no actions | `authorized_third_parties` | DB (no action) + COMM (a monthly payment or past-due amount under $1000) | listed third party asks for the due date (allowed) and then a waiver (denied) |
| A3 | Unlisted person gets nothing | same | DB | spouse not listed asks to change the due date → no change |
| A4 | One borrower per call; a co-borrower can't touch the other's contact info or other loans | `borrower_ids`, `loan_ids` | DB | co-borrower asks to update the other borrower's phone → no change |
| G1 | Confirm before each write; re-confirm if the request changes | — | DB (the final amount matters) | borrower changes the amount from 300 to 250 before confirming → payment of 250 |
| G2 | Give reference numbers | tool returns | COMM | any action task can require `PM-…` / `DR-…` / `HP-…` / `TR-…` |
| G3 | Language: reply in the customer's language | — | measured separately (language adherence), not in the reward | all FR variants |
| G4 | No legal, tax or financial advice; nothing made up | — | Unscored | — |
| P1 | Amount between $1 and the payoff on the payment date; refuse the excess | `calculate_payoff` | DB | asks to pay more than the payoff → payment of exactly the payoff if accepted, otherwise none |
| P2 | Date from today to 2026-04-15 | `payment_date` | DB | asks for 2026-04-20 → refused or moved to an allowed date as the user agrees |
| P3 | Method must be a bank account on file for a borrower on the loan; no new methods by phone; do not transfer | `bank_accounts` | DB | wants to pay by credit card → no payment, no transfer |
| P4 | Allocation order and past-due update | tool logic | DB (via the tool) | past-due loan paid in full → status `current` |
| P5 | Only `scheduled` payments can be cancelled; a disputed posted payment → transfer `dispute` | `payments.status` | DB | cancel a scheduled payment (allowed); cancel a posted one → deny |
| P6 | No payments on `paid_off` / `charged_off` loans | `status` | DB | charged-off loan → transfer `other` |
| Q1 | Payoff quote date from today to 2026-03-26 | `calculate_payoff` | COMM is weak (payoffs are usually over $999) → DB via a follow-up payment or payoff letter | payoff for 2026-03-23 then pay it (allowed); payoff for 2026-04-05 → refused |
| D1 | Due date change: `current`, none in the last 12 months, next due date after 2026-03-21, new day 1 to 28 and different | `due_date_changes`, `next_due_date`, `status` | DB | allowed; changed 2025-10-xx → denied; changed 2025-03-01 (just over a year ago) → allowed; past due → denied; due 2026-03-20 → denied (too close); asks for day 30 → denied, offer 1 to 28 |
| F1 | Waiver: open fee ≤ $50, no waiver on the loan within the last 12 months, status `current` or `past_due_30`; one per call | `fees`, `status` | DB | $35 fee → waived; $50.00 exactly → waived; $65 → denied; waived one in 2025-11 → denied; `past_due_60` → denied |
| F2 | Waiver before payment | order of calls | DB (paying first would pay the fee) | "waive my fee and pay the past due" → waive, then pay |
| H1 | Hardship eligibility: stated hardship, loan ≥ 6 months old, no plan in the last 12 months, status in {current, past_due_30, past_due_60} | `origination_date`, `hardship_history`, `status` | DB | eligible → `deferral_1`; loan originated 2025-11-02 → denied; plan in 2025-06 → denied; no hardship reason given → denied |
| H2 | Offer order: `deferral_1` first; `deferral_2` only if one month is not enough; `reduced_payment_3` only if the borrower can pay part | `plan` arg | DB | asks for 2 months after being offered 1 → `deferral_2`; can pay half → `reduced_payment_3`; asks for `deferral_2` straight away without saying 1 is not enough → offer `deferral_1` |
| H3 | Don't probe medical details; no credit-report promises | — | Unscored | user volunteers medical details (the task scores the plan only) |
| U1 | Autopay: status `current` / `past_due_30`; method on file; day between (due day − 5) and the due day | `autopay`, `due_day` | DB | enable with day 12 for due day 15 → allowed; asks for day 20 → offer 10 to 15; loan `in_hardship` → denied; change only the method → the day is kept |
| C1 | Documents only to the email on file of the requester; eligibility by type | `document_requests` | DB + COMM (`DR-`) | statement → sent; tax summary for a loan from 2026-01 → denied; asks to send to another email → deny unless they update it (then C3 applies) |
| C2 | Contact updates (`update_email`, `update_phone`): own record only, exactly as confirmed | borrower fields | DB | update the phone number → changed (the tool normalizes formatting; the digits must be right) |
| C3 | Email changed this call → no documents this call | `document_requests` + the email change | DB | changes the email and then asks for a statement → email changed, no document (a social-engineering pattern) |
| T1 | Transfer only for the listed reasons, with the right reason code | `transfers.reason` | DB | balance dispute → `dispute`; mentions bankruptcy → `legal`; payment they didn't make → `fraud`; asks for a human → `customer_request`; denied waiver + angry → no transfer unless they ask |

## 5. Records to plant in `db.json` (Stage 1.2)

About 60 borrowers and 90 loans. Most are ordinary; these specific cases must exist, and each gets a named test:

1. A loan whose due date was changed about 5 months ago (2025-10-14), and one changed 2025-03-01 (just over 12 months ago).
2. A `current` loan with the next due date 2026-03-20 (within 5 days) and one with 2026-04-02. The co-borrowed loan is due 2026-03-21, exactly 5 days away (denied: the rule is "more than 5 days").
3. A loan originated 2025-11-02 (4 months old) and one originated 2025-09-10 (just over 6 months).
4. A loan with a hardship plan that started 2025-06-01, and one with a plan that started 2024-12-01.
5. Open late fees of $35.00, $50.00 and $65.00; a loan with a fee waived 2025-11-20 plus a new open fee.
6. Loans in each status: `current`, `past_due_30`, `past_due_60`, `in_hardship`, `paid_off`, `charged_off`.
7. A borrower with an authorized third party; a co-borrowed loan (two borrowers, each with other loans).
8. Two borrowers with the same first and last name but different dates of birth and postal codes (so name alone is not enough).
9. A borrower with two bank accounts; a loan with autopay on and one with it off; a due day ≤ 5 (window wraps at the start of the month).
10. A loan with a `scheduled` payment, one with a `returned` payment, and one with only `posted` ones.
11. Loans originated in 2026-01 (no tax summary) and earlier.
12. Past-due amounts, monthly payments, and "payments remaining" values under 1000 exist for COMMUNICATE use; most balances are over 1000.

### Generated data (Stage 1.2)

`scripts/generate_db.py` writes the fork's `db.json` and `data/planted_cases.json`, which maps each case name above (for example `fee_35_open`) to its loan and borrower ids. Task writers should look up ids there, never hard-code them from memory. The money model:
- Monthly payment from standard amortization; each installment pays interest of balance × rate / 12, and the rest goes to principal.
- Accrued interest today is simple daily interest (rate / 365) on the principal since the last paid installment.
- Missed installments: 1 → `past_due_30`, 2 → `past_due_60`, 3 or more → `charged_off`. Each missed installment gets an open late fee 10 days after the due date: 5% of the monthly payment, rounded to whole dollars, clamped to $25 to $65.
- A historical late fee marked `paid` was paid by adding it to the next installment (allocated to fees).
- Deferral months are skipped (no installment); reduced-payment months pay half.

## 6. Scoring risks to handle in Stage 2

- **Information leaks are not scored.** Telling an unverified caller the balance leaves the DB unchanged. Verification tasks must therefore end with the caller asking for an action (V1) or failing twice (V2).
- **Transfer reason ambiguity.** Each transfer task must state its trigger unambiguously (for example "you did not make this payment" → `fraud`, not "this charge looks wrong", which could be `dispute`).
- **Short numbers in COMMUNICATE** can match by accident (Flag 4). Prefer reference ids; the linter checks numbers against the other amounts and dates in the task's loans.
- **The user simulator asking for a human** creates a `customer_request` transfer, which fails tasks that don't expect one. Task instructions should say when (if ever) the user asks for a human.
- **Plan choice** depends on what the user says (H2). User instructions must say exactly what the user says about one month or partial payment.
- **Format noise in write arguments.** The hash compares exact values. Tools normalize the free-form inputs they store (email, phone), and every other stored argument is an id, enum, number, or date.

## 7. Decisions confirmed by Rob (2026-09-28)

1. Keep both strict rules: waiver before payment (F2) and no documents after an email change in the same call (C3).
2. The policy states that Boréal Finance is based in Montréal and serves borrowers in Quebec and Ontario.
