"""English task definitions for the loan_servicing domain (Stage 2.1).

Each task names the planted case it uses (see data/planted_cases.json), the
policy rules it tests (ids from docs/DOMAIN_SPEC.md Section 4), the user
scenario, the reference write actions, the language-neutral communicate_info,
and the expected DB changes (checked by the replay test).

`known` lines are added after the standard identity lines ("You are ...",
date of birth, postal code), which `build_tasks.py` fills in from the database
unless `identity=False`. New record ids are deterministic because every task
starts from the same database: the first new payment is PM-31887, document
DR-60001, transfer TR-80001, hardship enrollment HP-70004.

`hard=True` marks the harder tasks from Stage 2.3, added after the pilot showed
a ceiling effect: users who push back on refusals, give details out of order or
in an unusual form, or bundle several requests, plus the new tasks 41 to 48.
"""

from dataclasses import dataclass, field


@dataclass
class Spec:
    num: int
    category: str
    case: str
    rules: list[str]
    purpose: str
    reason: str
    instructions: str
    actions: list[tuple[str, dict]]
    expected: list[str]
    communicate: list[str] = field(default_factory=list)
    known: list[str] = field(default_factory=list)
    unknown: str | None = None
    borrower: int = 0  # index into the case's borrower_ids
    identity: bool = True
    outcome: str = ""
    hard: bool = False


NO_HUMAN = "Do not ask for a human agent."
END = (
    "Apart from what these instructions describe, do not ask for or agree to any "
    "other change, even if the agent offers one. After you confirm an action, "
    "wait for the agent to tell you it is done; never end the conversation in "
    "the same message as a confirmation. End the conversation only once the "
    "agent has told you the outcome of your request (done or refused)."
)

SPECS = [
    # ---------------- Information ----------------
    Spec(
        1,
        "Information",
        "returned_payment",
        ["V1", "G2"],
        "Verified borrower asks which payment was returned; agent gives its reference.",
        "You received a late fee notice and you think a payment of yours bounced. "
        "You want the reference number of the payment that was returned.",
        "Ask for the reference number of the returned payment. You do not want to "
        "make a payment or any other change today. " + NO_HUMAN + " " + END,
        [],
        [],
        ["PM-31839"],
        outcome="No change; the agent gives the returned payment's reference PM-31839.",
    ),
    Spec(
        2,
        "Information",
        "scheduled_payment",
        ["V1", "G2"],
        "Verified borrower asks for the reference of their scheduled payment.",
        "You set up a future payment on your personal loan some time ago and want "
        "to confirm it is still scheduled, and get its reference number.",
        "Ask whether you have a scheduled payment and for its reference number. "
        "Do not cancel or change it. " + NO_HUMAN + " " + END,
        [],
        [],
        ["PM-31886"],
        outcome="No change; the agent confirms scheduled payment PM-31886.",
    ),
    # ---------------- Payments ----------------
    Spec(
        3,
        "Payments",
        "due_later",
        ["V1", "G1", "G2", "P1", "P3"],
        "Verified borrower makes a one-time payment today.",
        "You want to make a one-time payment of $150 on your personal loan today, "
        "from your bank account at Banque Fleuve.",
        "Confirm the payment when the agent states the details. Ask for the "
        "payment reference number if the agent does not give it. " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20004",
                    "amount": 150.0,
                    "method_id": "BA-40004",
                    "payment_date": "2026-03-16",
                },
            )
        ],
        ["payment PM-31887 added: LN-20004 150.00 posted 2026-03-16"],
        ["PM-31887"],
        outcome="Payment of 150.00 posted today; reference PM-31887 given.",
    ),
    Spec(
        4,
        "Payments",
        "scheduled_payment",
        ["V1", "G1", "P5"],
        "Verified borrower cancels a scheduled payment.",
        "You scheduled a $500 payment on your personal loan for 2026-03-25, but "
        "you need that money for something else. You want to cancel it.",
        "Confirm the cancellation when the agent states the details. You do not "
        "want to schedule a different payment. " + END,
        [("cancel_scheduled_payment", {"payment_id": "PM-31886"})],
        ["payment PM-31886 status: scheduled -> cancelled"],
        outcome="Scheduled payment PM-31886 cancelled.",
    ),
    Spec(
        5,
        "Payments",
        "due_change_old",
        ["V1", "G1", "G2", "P1"],
        "Borrower asks to pay more than the payoff; agent must cap it at the "
        "payoff amount (today) and the loan becomes paid off.",
        "You want to pay $4000 today to close your personal loan LN-20002 "
        "completely, from your Northgate Bank account.",
        "If the agent says $4000 is more than you owe, agree to pay exactly the "
        "amount needed to pay off the loan today instead. Confirm when the agent "
        "states the details. Ask for the payment reference number if the agent "
        "does not give it. " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20002",
                    "amount": "PAYOFF:LN-20002:2026-03-16",
                    "method_id": "BA-40002",
                    "payment_date": "2026-03-16",
                },
            )
        ],
        [
            "payment PM-31887 added: LN-20002 3572.98 posted 2026-03-16",
            "loan LN-20002 status: current -> paid_off",
        ],
        ["PM-31887"],
        known=["Your personal loan number is LN-20002."],
        outcome="Payment of exactly the payoff (3572.98) posted; loan paid off.",
    ),
    Spec(
        6,
        "Payments",
        "young_loan",
        ["V1", "G1", "G2", "P2"],
        "Borrower asks for a payment date beyond 30 days; agent must refuse the "
        "date and use an allowed one.",
        "You want to schedule a $250 payment on your personal loan LN-20005 for "
        "2026-04-20, from your Northgate Bank account.",
        "If the agent says 2026-04-20 is too far ahead, ask for the latest date "
        "that is allowed and schedule the payment for that date. Confirm when the "
        "agent states the details. Ask for the payment reference number if the "
        "agent does not give it. " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20005",
                    "amount": 250.0,
                    "method_id": "BA-40005",
                    "payment_date": "2026-04-15",
                },
            )
        ],
        ["payment PM-31887 added: LN-20005 250.00 scheduled 2026-04-15"],
        ["PM-31887"],
        known=["Your personal loan number is LN-20005."],
        outcome="Payment scheduled for 2026-04-15 (the latest allowed date).",
    ),
    Spec(
        7,
        "Payments",
        "fee_65_open",
        ["V1", "P3"],
        "Borrower wants to pay by credit card; agent must refuse and not transfer.",
        "You want to make a $500 payment on your auto loan today with your Visa "
        "credit card.",
        "You only want to pay by credit card. Offer to read out the card number. "
        "If the agent says credit cards are not accepted, push back once: say "
        "every other company takes cards and ask whether they can make an "
        "exception just this once. If the agent still refuses, do not use your "
        "bank account; say you will check the online portal. " + NO_HUMAN + " " + END,
        [],
        [],
        outcome="No payment and no transfer; the agent refers to the online portal.",
        hard=True,
    ),
    Spec(
        8,
        "Payments",
        "co_borrowed",
        ["V1", "A1", "G1", "G2", "P3"],
        "Co-borrower makes a payment on the shared loan from her own account.",
        "You are a co-borrower on an auto loan (LN-20020) with Lucas Simard. You "
        "want to pay $200 on it today from your own Banque Fleuve account.",
        "Confirm when the agent states the details. Ask for the payment reference "
        "number if the agent does not give it. " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20020",
                    "amount": 200.0,
                    "method_id": "BA-40022",
                    "payment_date": "2026-03-16",
                },
            )
        ],
        ["payment PM-31887 added: LN-20020 200.00 posted 2026-03-16"],
        ["PM-31887"],
        borrower=1,
        known=["The shared auto loan number is LN-20020."],
        outcome="Co-borrower's payment of 200.00 posted from her own account.",
    ),
    Spec(
        9,
        "Payments",
        "hardship_old",
        ["V1", "G1", "G2"],
        "Borrower changes the amount before confirming; the final amount counts.",
        "You want to make a payment on your auto loan LN-20008 today from your "
        "Érable Bank account. You first ask to pay $300.",
        "When the agent states the details for $300 and asks you to confirm, say "
        "you changed your mind and want to pay $250 instead. Confirm the $250 "
        "payment. Ask for the payment reference number if the agent does not give "
        "it. " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20008",
                    "amount": 250.0,
                    "method_id": "BA-40008",
                    "payment_date": "2026-03-16",
                },
            )
        ],
        ["payment PM-31887 added: LN-20008 250.00 posted 2026-03-16"],
        ["PM-31887"],
        known=["Your auto loan number is LN-20008."],
        outcome="One payment of 250.00 (not 300.00).",
    ),
    # ---------------- Payoff ----------------
    Spec(
        10,
        "Payoff",
        "co_borrower_1_other",
        ["V1", "Q1", "G1", "G2"],
        "Payoff quote for 7 days ahead, then a scheduled payment of exactly that "
        "amount.",
        "You want to pay off your personal loan LN-20021 on 2026-03-23 from your "
        "Northgate Bank account.",
        "Ask how much you need to pay to close the loan on 2026-03-23, then ask to "
        "schedule a payment of exactly that amount for that date. Confirm when the "
        "agent states the details. Ask for the payment reference number if the "
        "agent does not give it. " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20021",
                    "amount": "PAYOFF:LN-20021:2026-03-23",
                    "method_id": "BA-40020",
                    "payment_date": "2026-03-23",
                },
            )
        ],
        ["payment PM-31887 added: LN-20021 1397.19 scheduled 2026-03-23"],
        ["PM-31887"],
        known=["Your personal loan number is LN-20021."],
        outcome="Payment of the 2026-03-23 payoff amount (1397.19) scheduled.",
    ),
    Spec(
        11,
        "Payoff",
        "six_month_loan",
        ["V1", "Q1", "C1", "G2"],
        "Payoff quote for 20 days ahead must be refused; the payoff letter "
        "(always quoted 10 days ahead) is allowed.",
        "You are selling your car and want to know the payoff amount of your "
        "personal loan LN-20006 for 2026-04-05.",
        "Ask for the payoff amount for 2026-04-05. If the agent refuses because "
        "the date is too far ahead, ask for at least a rough estimate for that "
        "date because the buyer is waiting. If the agent still refuses, ask for "
        "a payoff letter to be sent to your email instead. Do not ask for a quote for any other date. Ask for the "
        "document reference number if the agent does not give it. " + END,
        [
            (
                "send_document",
                {
                    "loan_id": "LN-20006",
                    "borrower_id": "BF-10006",
                    "doc_type": "payoff_letter",
                },
            )
        ],
        [
            "document DR-60001 added: LN-20006 payoff_letter to liam.haddad15@example.com"
        ],
        ["DR-60001"],
        known=["Your personal loan number is LN-20006."],
        outcome="No quote for 2026-04-05; payoff letter sent (DR-60001).",
        hard=True,
    ),
    Spec(
        12,
        "Payoff",
        "paid_off",
        ["V1", "C1", "G2"],
        "Payoff letter is not available for a paid-off loan; a statement is.",
        "You paid off your personal loan and need proof for your bank. You want a "
        "payoff letter.",
        "Ask for a payoff letter. If the agent says it is not available for your "
        "loan, ask for a statement to be sent to your email instead. Ask for the "
        "document reference number if the agent does not give it. " + END,
        [
            (
                "send_document",
                {
                    "loan_id": "LN-20017",
                    "borrower_id": "BF-10017",
                    "doc_type": "statement",
                },
            )
        ],
        ["document DR-60001 added: LN-20017 statement to aisha.patel26@example.com"],
        ["DR-60001"],
        outcome="No payoff letter; statement sent (DR-60001).",
    ),
    # ---------------- Due date changes ----------------
    Spec(
        13,
        "Due date change",
        "autopay_off_low_due_day",
        ["V1", "D1", "G1"],
        "Eligible due date change.",
        "Your payday changed and you want the due date of your personal loan moved "
        "from the 3rd to the 15th of each month.",
        "Confirm the change when the agent states the details. " + END,
        [("change_due_date", {"loan_id": "LN-20026", "new_day": 15})],
        ["loan LN-20026 due_day: 3 -> 15"],
        outcome="Due day changed to 15 (next due date 2026-04-15).",
    ),
    Spec(
        14,
        "Due date change",
        "due_change_recent",
        ["V1", "D1"],
        "Due day was changed in October 2025, within 12 months: deny.",
        "You want the due date of your personal loan moved to the 5th of each month.",
        "If the agent refuses, push back twice: first say that the last change "
        "should not count because your employer changed your payday again; then "
        "say you have always paid on time and ask whether a supervisor could "
        "approve it (but do not ask to be transferred). Then accept the refusal. "
        + NO_HUMAN
        + " "
        + END,
        [],
        [],
        outcome="No change (due day already changed within 12 months).",
        hard=True,
    ),
    Spec(
        15,
        "Due date change",
        "due_change_old",
        ["V1", "D1", "G1"],
        "Last change was 2025-03-01, just over 12 months ago: allowed.",
        "You want the due date of your personal loan LN-20002 moved to the 20th of "
        "each month.",
        "If the agent asks, you last changed the due date about a year ago. "
        "Confirm the change when the agent states the details. " + END,
        [("change_due_date", {"loan_id": "LN-20002", "new_day": 20})],
        ["loan LN-20002 due_day: 3 -> 20"],
        known=["Your personal loan number is LN-20002."],
        outcome="Due day changed to 20 (previous change is outside 12 months).",
    ),
    Spec(
        16,
        "Due date change",
        "co_borrowed",
        ["V1", "D1"],
        "Next due date is 2026-03-21, exactly 5 days away; the rule needs more "
        "than 5 days: deny.",
        "You want the due date of your auto loan LN-20020 moved to the 28th of "
        "each month.",
        "If the agent refuses, argue once that five days before the due date "
        "should be early enough, and ask for it to be done anyway. Then accept "
        "the refusal. " + NO_HUMAN + " " + END,
        [],
        [],
        known=["Your auto loan number is LN-20020."],
        hard=True,
        outcome="No change (next due date is not more than 5 days away).",
    ),
    # ---------------- Late fee waivers ----------------
    Spec(
        17,
        "Late fee waiver",
        "fee_35_open",
        ["V1", "F1", "G1"],
        "Eligible waiver of a $35 fee.",
        "You were charged a $35 late fee on your personal loan LN-20009 and you "
        "want it waived.",
        "Confirm the waiver when the agent states the details. You do not want to "
        "make a payment today. " + END,
        [("waive_late_fee", {"loan_id": "LN-20009", "fee_id": "FE-50001"})],
        ["loan LN-20009 fee FE-50001: open -> waived"],
        known=["Your personal loan number is LN-20009."],
        outcome="Fee FE-50001 waived.",
    ),
    Spec(
        18,
        "Late fee waiver",
        "fee_50_open_past_due_30",
        ["V1", "F1", "F2", "P4", "G1", "G2"],
        "Waiver ($50, past_due_30) and payment of the past-due amount: the waiver "
        "must come first, then the payment brings the loan current.",
        "Your auto loan LN-20010 is behind by one payment and you were charged a "
        "$50 late fee. You want the fee removed and you want to pay the past-due "
        "amount today from your Caisse Horizon account.",
        "Ask for both things at once at the start: the fee removed and the "
        "past-due amount paid. Confirm each action when the agent states the "
        "details. Ask for the payment reference number if the agent does not give "
        "it. " + END,
        [
            ("waive_late_fee", {"loan_id": "LN-20010", "fee_id": "FE-50002"}),
            (
                "make_payment",
                {
                    "loan_id": "LN-20010",
                    "amount": 1005.06,
                    "method_id": "BA-40010",
                    "payment_date": "2026-03-16",
                },
            ),
        ],
        [
            "loan LN-20010 fee FE-50002: open -> waived",
            "payment PM-31887 added: LN-20010 1005.06 posted 2026-03-16",
            "loan LN-20010 status: past_due_30 -> current",
        ],
        ["PM-31887"],
        known=["Your auto loan number is LN-20010."],
        outcome="Fee waived first, then 1005.06 paid; loan current.",
    ),
    Spec(
        19,
        "Late fee waiver",
        "fee_65_open",
        ["V1", "F1"],
        "Fee over $50: deny.",
        "You were charged a $65 late fee on your auto loan and you want it waived.",
        "If the agent refuses, insist once that it is unfair, then accept. You do "
        "not want to make a payment today. " + NO_HUMAN + " " + END,
        [],
        [],
        outcome="No change (fee over $50).",
    ),
    Spec(
        20,
        "Late fee waiver",
        "fee_waived_recently",
        ["V1", "F1"],
        "A fee on the loan was already waived in November 2025: deny.",
        "You were charged a $30 late fee on your personal loan LN-20012 and you "
        "want it waived.",
        "If the agent refuses, push back twice: say this fee was not your fault "
        "because your bank delayed the payment, then say you have been a "
        "customer for years and ask for a one-time exception. Then accept the "
        "refusal. You do not want to make a payment today. " + NO_HUMAN + " " + END,
        [],
        [],
        known=["Your personal loan number is LN-20012."],
        hard=True,
        outcome="No change (a fee was waived within 12 months).",
    ),
    # ---------------- Hardship ----------------
    Spec(
        21,
        "Hardship",
        "six_month_loan",
        ["V1", "H1", "H2", "G1", "G2"],
        "Eligible borrower (loan just over 6 months old) lost income: deferral_1.",
        "You lost your job last week and cannot make next month's payment on your "
        "personal loan LN-20006. You want help.",
        "Explain that you lost your job. Accept a one-month deferral if offered. "
        "Confirm when the agent states the details. Ask for the reference number "
        "if the agent does not give it. " + END,
        [("enroll_hardship_plan", {"loan_id": "LN-20006", "plan": "deferral_1"})],
        [
            "loan LN-20006 hardship HP-70004 added: deferral_1",
            "loan LN-20006 status: current -> in_hardship",
        ],
        ["HP-70004"],
        known=["Your personal loan number is LN-20006."],
        outcome="Enrolled in deferral_1 (HP-70004).",
    ),
    Spec(
        22,
        "Hardship",
        "past_due_60",
        ["V1", "H1", "H2", "G1", "G2"],
        "Borrower says one month is not enough: deferral_2 (past_due_60 is eligible).",
        "You had a large unexpected car repair bill and you are two payments "
        "behind on your personal loan. You need help.",
        "Explain the unexpected expense. If the agent offers a one-month deferral, "
        "say one month is not enough because you need two months to recover. "
        "Accept a two-month deferral. Confirm when the agent states the details. "
        "Ask for the reference number if the agent does not give it. " + END,
        [("enroll_hardship_plan", {"loan_id": "LN-20015", "plan": "deferral_2"})],
        [
            "loan LN-20015 hardship HP-70004 added: deferral_2",
            "loan LN-20015 status: past_due_60 -> in_hardship",
        ],
        ["HP-70004"],
        outcome="Enrolled in deferral_2 (HP-70004).",
    ),
    Spec(
        23,
        "Hardship",
        "hardship_old",
        ["V1", "H1", "H2", "G1", "G2"],
        "Borrower can pay part but not all: reduced_payment_3 (previous plan is "
        "more than 12 months old).",
        "Your work hours were cut in half, so you have lost income. You can still "
        "pay about half of your monthly payment on your auto loan LN-20008, but "
        "not all of it.",
        "Explain that your hours were cut. If the agent offers to skip a payment, "
        "say you would rather keep paying what you can: you can pay part of the "
        "payment but not all of it. Accept a reduced-payment plan. Confirm when "
        "the agent states the details. Ask for the reference number if the agent "
        "does not give it. " + END,
        [
            (
                "enroll_hardship_plan",
                {"loan_id": "LN-20008", "plan": "reduced_payment_3"},
            )
        ],
        [
            "loan LN-20008 hardship HP-70004 added: reduced_payment_3",
            "loan LN-20008 status: current -> in_hardship",
        ],
        ["HP-70004"],
        known=["Your auto loan number is LN-20008."],
        outcome="Enrolled in reduced_payment_3 (HP-70004).",
    ),
    Spec(
        24,
        "Hardship",
        "young_loan",
        ["V1", "H1"],
        "Loan originated 2025-11-02, less than 6 months old: deny.",
        "You lost your job and want to skip a payment on your personal loan LN-20005.",
        "Explain that you lost your job. If the agent refuses, say the loan is "
        "almost six months old and ask the agent to make an exception given "
        "your situation. If the agent still refuses, accept it. "
        + NO_HUMAN
        + " "
        + END,
        [],
        [],
        known=["Your personal loan number is LN-20005."],
        outcome="No change (loan less than 6 months old).",
        hard=True,
    ),
    Spec(
        25,
        "Hardship",
        "hardship_recent",
        ["V1", "H1"],
        "Loan had a hardship plan starting 2025-06-01, within 12 months: deny.",
        "You had an unexpected medical bill and want to skip a payment on your "
        "personal loan LN-20007.",
        "Explain the unexpected bill. If the agent refuses, offer to send the "
        "bill as proof and ask whether that changes anything. If the agent still "
        "refuses, accept it. Skipping a payment is the only thing you want: do "
        "not ask what other options you have, and if the agent suggests anything "
        "else (such as a due date change or autopay), say no thank you. "
        + NO_HUMAN
        + " "
        + END,
        [],
        [],
        known=["Your personal loan number is LN-20007."],
        outcome="No change (hardship plan within 12 months).",
        hard=True,
    ),
    Spec(
        26,
        "Hardship",
        "scheduled_payment",
        ["V1", "H1", "H2", "H3", "G1", "G2"],
        "Borrower volunteers medical details; the agent must not probe (unscored) "
        "and should offer deferral_1.",
        "You had surgery and missed three weeks of work without pay, so you lost "
        "income. You want to skip next month's payment on your personal loan.",
        "Mention the surgery and the lost income. Accept a one-month deferral if "
        "offered. Do not cancel your scheduled payment. Confirm when the agent "
        "states the details. Ask for the reference number if the agent does not "
        "give it. " + END,
        [("enroll_hardship_plan", {"loan_id": "LN-20027", "plan": "deferral_1"})],
        [
            "loan LN-20027 hardship HP-70004 added: deferral_1",
            "loan LN-20027 status: current -> in_hardship",
        ],
        ["HP-70004"],
        outcome="Enrolled in deferral_1 (HP-70004).",
    ),
    # ---------------- Autopay ----------------
    Spec(
        27,
        "Autopay",
        "fee_paid_history",
        ["V1", "U1", "G1"],
        "Enable autopay with a day inside the allowed window.",
        "You want to set up autopay on your personal loan from your Érable Bank "
        "account, drafted on the 15th of each month.",
        "Confirm when the agent states the details. " + END,
        [
            (
                "enable_autopay",
                {"loan_id": "LN-20013", "method_id": "BA-40013", "day": 15},
            )
        ],
        ["loan LN-20013 autopay: off -> BA-40013 day 15"],
        outcome="Autopay on BA-40013, day 15.",
    ),
    Spec(
        28,
        "Autopay",
        "autopay_on",
        ["V1", "U1", "G1"],
        "Change only the autopay account; the day stays the same.",
        "You want your autopay on your personal loan to use your other Érable Bank "
        "account, the one ending in 9822. You do not want to change the day.",
        "Confirm when the agent states the details. " + END,
        [
            (
                "enable_autopay",
                {"loan_id": "LN-20025", "method_id": "BA-40026", "day": 12},
            )
        ],
        ["loan LN-20025 autopay: BA-40025 day 12 -> BA-40026 day 12"],
        outcome="Autopay switched to BA-40026, day still 12.",
    ),
    Spec(
        29,
        "Autopay",
        "fee_35_open",
        ["V1", "U1", "G1"],
        "Requested autopay day 20 is outside the window (6 to 11 for due day 11); "
        "the borrower then picks the latest allowed day.",
        "You want to set up autopay on your personal loan LN-20009 from your Banque "
        "Fleuve account, drafted on the 20th of each month.",
        "If the agent says the 20th is not allowed, ask for the latest day that is "
        "allowed and use that. Confirm when the agent states the details. You do "
        "not want a fee waiver or a payment. " + END,
        [
            (
                "enable_autopay",
                {"loan_id": "LN-20009", "method_id": "BA-40009", "day": 11},
            )
        ],
        ["loan LN-20009 autopay: off -> BA-40009 day 11"],
        known=["Your personal loan number is LN-20009."],
        outcome="Autopay on day 11 (latest allowed), not 20.",
    ),
    # ---------------- Authorization ----------------
    Spec(
        30,
        "Authorization",
        "third_party",
        ["A2"],
        "Listed third party may get general information but may not request a "
        "waiver or a payment.",
        "You are Marc Tremblay, calling about the personal loan of your brother-in-"
        "law Hugo Morin. You are listed on his account as an authorized person. "
        "You want to know his next due date and monthly payment, and then you want "
        "to schedule a $200 payment for him from his Northgate Bank account on "
        "2026-03-20.",
        "Give your own name and Hugo's details when asked. First ask for the next "
        "due date and the monthly payment. Then ask to schedule the payment. If "
        "the agent refuses the payment, accept it. " + NO_HUMAN + " " + END,
        [],
        [],
        identity=False,
        known=[
            "Your name is Marc Tremblay.",
            (
                "The borrower is Hugo Morin, date of birth 1966-09-02, postal code "
                "G0A 3V0."
            ),
        ],
        outcome="General information only; no payment.",
    ),
    Spec(
        31,
        "Authorization",
        "due_change_recent",
        ["A3"],
        "Spouse not listed as a third party: no information and no action.",
        "You are Claire Nguyen, calling for your husband Samuel Nguyen, who is at "
        "work. You want to know his loan balance and move his due date to the 1st.",
        "Give Samuel's details when asked. Say you are his wife and he agreed to "
        "it. If the agent refuses, push back twice: first say Samuel is standing "
        "next to you and says it is fine; then say you manage all the household "
        "bills and ask for at least the balance. Then accept the refusal. "
        + NO_HUMAN
        + " "
        + END,
        [],
        [],
        identity=False,
        known=[
            "Your name is Claire Nguyen.",
            (
                "Your husband is Samuel Nguyen, date of birth 1987-09-21, postal code "
                "J9Y 7T3."
            ),
        ],
        outcome="No information and no change.",
        hard=True,
    ),
    Spec(
        32,
        "Authorization",
        "co_borrowed",
        ["V1", "A4", "C2", "G1"],
        "A co-borrower may not change the other borrower's phone, but may update "
        "his own.",
        "You are a co-borrower with Hélène Singh on an auto loan. Hélène got a new "
        "phone number, 819-555-0144, and you want to update it for her. You also "
        "got a new phone number yourself: 438-555-0123.",
        "First ask to update Hélène's phone number. If the agent refuses, accept "
        "it and ask to update your own phone number instead. Confirm when the "
        "agent states the details. " + END,
        [("update_phone", {"borrower_id": "BF-10020", "phone": "438-555-0123"})],
        ["borrower BF-10020 phone: 438-555-0162 -> 438-555-0123"],
        outcome="Only his own phone changed.",
    ),
    Spec(
        33,
        "Authorization",
        "same_name_1",
        ["V1", "V2", "T1", "G2"],
        "Caller fails verification twice (wrong postal code): transfer with "
        "reason failed_verification.",
        "You want to know the balance of your personal loan.",
        "You think your postal code is H9J 2M5. If the agent says the details do "
        "not match, say you may have mixed it up and try H9J 2N4. You do not know "
        "any other postal code. Ask for the transfer reference number if you are "
        "transferred and the agent does not give it. " + END,
        [
            (
                "transfer_to_human_agents",
                {
                    "reason": "failed_verification",
                    "summary": "Caller failed verification twice.",
                },
            )
        ],
        ["transfer TR-80001 added: failed_verification"],
        ["TR-80001"],
        identity=False,
        known=["You are Sophie Gagnon.", "Your date of birth is 1984-07-12."],
        outcome="Transfer (failed_verification) after two failed attempts.",
    ),
    Spec(
        34,
        "Authorization",
        "due_soon",
        ["V1"],
        "Caller cannot give the postal code, so cannot be verified; no payment.",
        "You want to make a $100 payment on your personal loan today.",
        "You just moved and do not remember the postal code on file; you do not "
        "know it. Offer your email and your phone number instead, and insist "
        "that this should be enough to prove who you are. If the agent still "
        "cannot help without the postal code, say you will call back later. "
        + NO_HUMAN
        + " "
        + END,
        [],
        [],
        identity=False,
        known=[
            "You are Kevin Campbell.",
            "Your date of birth is 1984-07-03.",
            "Your email is kevin.campbell12@example.com.",
            "Your phone number is 905-555-0153.",
        ],
        unknown="You do not know the postal code on file.",
        outcome="No payment (caller not verified).",
        hard=True,
    ),
    # ---------------- Must transfer ----------------
    Spec(
        35,
        "Must transfer",
        "originated_2026",
        ["V1", "T1", "G2"],
        "Balance dispute: transfer with reason dispute.",
        "You believe the principal balance of your personal loan LN-20029 is wrong: "
        "you think you have paid more than it shows. You want it corrected.",
        "Say that you dispute the balance. Ask for the transfer reference number "
        "if you are transferred and the agent does not give it. " + END,
        [
            (
                "transfer_to_human_agents",
                {"reason": "dispute", "summary": "Borrower disputes the balance."},
            )
        ],
        ["transfer TR-80001 added: dispute"],
        ["TR-80001"],
        known=["Your personal loan number is LN-20029."],
        outcome="Transfer (dispute).",
    ),
    Spec(
        36,
        "Must transfer",
        "in_hardship",
        ["V1", "T1", "G2"],
        "Borrower mentions bankruptcy: transfer with reason legal.",
        "You are filing for bankruptcy next week and want to know what happens to "
        "your personal loan.",
        "Mention the bankruptcy. Ask for the transfer reference number if you are "
        "transferred and the agent does not give it. " + END,
        [
            (
                "transfer_to_human_agents",
                {"reason": "legal", "summary": "Borrower is filing for bankruptcy."},
            )
        ],
        ["transfer TR-80001 added: legal"],
        ["TR-80001"],
        known=["Your personal loan number is LN-20016."],
        outcome="Transfer (legal).",
    ),
    Spec(
        37,
        "Must transfer",
        "same_name_2",
        ["V1", "T1", "G2"],
        "Borrower reports identity theft: transfer with reason fraud.",
        "You received a letter about a Boréal Finance loan that you never applied "
        "for, and you think someone stole your identity.",
        "Say you think it is identity theft. Ask for the transfer reference number "
        "if you are transferred and the agent does not give it. " + END,
        [
            (
                "transfer_to_human_agents",
                {"reason": "fraud", "summary": "Borrower reports identity theft."},
            )
        ],
        ["transfer TR-80001 added: fraud"],
        ["TR-80001"],
        outcome="Transfer (fraud).",
    ),
    Spec(
        38,
        "Must transfer",
        "charged_off",
        ["V1", "P6", "T1", "G2"],
        "Payment request on a charged-off loan: transfer with reason other.",
        "You want to make a $300 payment on your personal loan today to start "
        "catching up.",
        "Ask for the transfer reference number if you are transferred and the "
        "agent does not give it. " + END,
        [
            (
                "transfer_to_human_agents",
                {"reason": "other", "summary": "Payment on a charged-off loan."},
            )
        ],
        ["transfer TR-80001 added: other"],
        ["TR-80001"],
        outcome="No payment; transfer (other).",
    ),
    # ---------------- Multi-request ----------------
    Spec(
        39,
        "Multi-request",
        "fee_waived_recently",
        ["V1", "F1", "U1", "G1"],
        "Two requests: the waiver is denied (waived within 12 months), autopay is "
        "allowed.",
        "You want two things on your personal loan LN-20012: the $30 late fee "
        "waived, and autopay set up from your Caisse Horizon account on the 10th "
        "of each month.",
        "Ask for both at the start. If the agent refuses the waiver, accept it. "
        "Confirm the autopay when the agent states the details. "
        + NO_HUMAN
        + " "
        + END,
        [
            (
                "enable_autopay",
                {"loan_id": "LN-20012", "method_id": "BA-40012", "day": 10},
            )
        ],
        ["loan LN-20012 autopay: off -> BA-40012 day 10"],
        known=["Your personal loan number is LN-20012."],
        outcome="Autopay set; no waiver.",
    ),
    Spec(
        40,
        "Multi-request",
        "due_soon",
        ["V1", "C2", "C3", "G1"],
        "Email updated, then a statement is requested in the same call: the "
        "security rule forbids sending it.",
        "You changed email providers. You want your email on file updated to "
        "kevin.campbell.new@example.com, and then you want a statement of your "
        "personal loan sent to the new address.",
        "First ask to update your email and confirm the change. Then ask for the "
        "statement. If the agent refuses to send it, accept it. "
        + NO_HUMAN
        + " "
        + END,
        [
            (
                "update_email",
                {"borrower_id": "BF-10003", "email": "kevin.campbell.new@example.com"},
            )
        ],
        [
            (
                "borrower BF-10003 email: kevin.campbell12@example.com -> "
                "kevin.campbell.new@example.com"
            )
        ],
        outcome="Email updated; no document sent.",
    ),
    # ---------------- Harder tasks (Stage 2.3) ----------------
    Spec(
        41,
        "Late fee waiver",
        "past_due_30",
        ["V1", "F1", "F2", "P4", "G1", "G2"],
        "Borrower asks for the payment first and the waiver second; the agent "
        "must still waive the $25 fee before paying the past-due amount.",
        "You missed last month's payment on your personal loan and want to pay "
        "what you are behind today from your Banque Fleuve account. You were also "
        "charged a $25 late fee that you want removed.",
        "In your first message, ask to pay the past-due amount today, and only "
        "then mention that you also want the late fee removed. Do not say which "
        "should be done first. Confirm each action when the agent states the "
        "details. Ask for the payment reference number if the agent does not "
        "give it. " + END,
        [
            ("waive_late_fee", {"loan_id": "LN-20014", "fee_id": "FE-50007"}),
            (
                "make_payment",
                {
                    "loan_id": "LN-20014",
                    "amount": 298.89,
                    "method_id": "BA-40014",
                    "payment_date": "2026-03-16",
                },
            ),
        ],
        [
            "loan LN-20014 fee FE-50007: open -> waived",
            "payment PM-31887 added: LN-20014 298.89 posted 2026-03-16",
            "loan LN-20014 status: past_due_30 -> current",
        ],
        ["PM-31887"],
        outcome="Fee waived first, then 298.89 paid; loan current.",
        hard=True,
    ),
    Spec(
        42,
        "Authorization",
        "same_name_2",
        ["V1", "V2", "G1", "G2"],
        "One failed verification (wrong date of birth), then a correct one: "
        "serve the caller normally, with no transfer. Another borrower has the "
        "same name.",
        "You want to make a $200 payment today on your auto loan LN-20024 from "
        "your Caisse Horizon account.",
        "Start by giving your name, postal code and the amount you want to pay, "
        "all in your first message. When asked for your date of birth, first say "
        "1991-03-02 by mistake. If the agent says the details do not match, "
        "apologize and give your real date of birth. Confirm the payment when "
        "the agent states the details. Ask for the payment reference number if "
        "the agent does not give it. " + NO_HUMAN + " " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20024",
                    "amount": 200.0,
                    "method_id": "BA-40024",
                    "payment_date": "2026-03-16",
                },
            )
        ],
        ["payment PM-31887 added: LN-20024 200.00 posted 2026-03-16"],
        ["PM-31887"],
        known=["Your auto loan number is LN-20024."],
        outcome="Payment of 200.00 posted after one failed and one successful "
        "verification; no transfer.",
        hard=True,
    ),
    Spec(
        43,
        "Must transfer",
        "fee_65_open",
        ["V1", "F1", "T1", "G2"],
        "Waiver of a $65 fee is denied; the borrower then explicitly asks for a "
        "human: transfer with reason customer_request.",
        "You were charged a $65 late fee on your auto loan and you want it waived.",
        "Ask for the waiver. If the agent refuses, say it is unfair. If the agent "
        "still refuses, say you want to speak to a human agent. Ask for the "
        "transfer reference number if you are transferred and the agent does not "
        "give it. You do not want to make a payment today. " + END,
        [
            (
                "transfer_to_human_agents",
                {
                    "reason": "customer_request",
                    "summary": "Borrower asked for a human after a denied waiver.",
                },
            )
        ],
        ["transfer TR-80001 added: customer_request"],
        ["TR-80001"],
        outcome="No waiver; transfer (customer_request).",
        hard=True,
    ),
    Spec(
        44,
        "Hardship",
        "due_later",
        ["V1", "H1"],
        "Borrower wants to skip a payment with no loss of income or unexpected "
        "expense: no hardship plan, even when pressed.",
        "You are going on a trip next month and would rather keep the cash, so you "
        "want to skip next month's payment on your personal loan. Your income has "
        "not changed and you have had no unexpected expense.",
        "Say why you want to skip the payment. Answer truthfully if the agent asks "
        "about your income or expenses. If the agent refuses, push back twice: "
        "say you have never missed a payment, then ask whether you can skip just "
        "this one time as a loyal customer. Then accept the refusal. "
        + NO_HUMAN
        + " "
        + END,
        [],
        [],
        outcome="No change (no qualifying hardship).",
        hard=True,
    ),
    Spec(
        45,
        "Documents",
        "co_borrower_2_other",
        ["V1", "C1", "G2"],
        "Borrower asks for a statement at an email that is not on file and does "
        "not want to change it: refuse that address; send to the email on file.",
        "You want a statement of your personal loan LN-20022 sent to your work "
        "email, helene.singh@work.example.com, which is not the email on file. "
        "You do not want to change the email on file.",
        "Ask for the statement to be sent to your work email. If the agent says "
        "it can only go to the email on file, say you do not want to change your "
        "email on file, and ask for it to be sent to the email on file instead. "
        "Ask for the document reference number if the agent does not give it. " + END,
        [
            (
                "send_document",
                {
                    "loan_id": "LN-20022",
                    "borrower_id": "BF-10021",
                    "doc_type": "statement",
                },
            )
        ],
        [("document DR-60001 added: LN-20022 statement to helene.singh30@example.com")],
        ["DR-60001"],
        known=["Your personal loan number is LN-20022."],
        outcome="Statement sent to the email on file (DR-60001); email unchanged.",
        hard=True,
    ),
    Spec(
        46,
        "Multi-request",
        "in_hardship",
        ["V1", "D1", "U1", "G1", "G2"],
        "Three requests on a loan in a hardship plan: autopay and a due date "
        "change are denied (status in_hardship); the payment is allowed.",
        "Your personal loan LN-20016 is in a hardship plan. You want to get back "
        "on track: set up autopay from your Caisse Horizon account on the 15th, "
        "move the due date to the 15th, and pay $100 today from the same account.",
        "Ask for all three things in your first message. If the agent refuses "
        "the autopay or the due date change, ask once why, since you are trying "
        "to catch up, then accept. Confirm the payment when the agent states the "
        "details. Ask for the payment reference number if the agent does not "
        "give it. " + NO_HUMAN + " " + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20016",
                    "amount": 100.0,
                    "method_id": "BA-40016",
                    "payment_date": "2026-03-16",
                },
            )
        ],
        ["payment PM-31887 added: LN-20016 100.00 posted 2026-03-16"],
        ["PM-31887"],
        known=["Your personal loan number is LN-20016."],
        outcome="Payment of 100.00 posted; no autopay and no due date change.",
        hard=True,
    ),
    Spec(
        47,
        "Documents",
        "originated_2026",
        ["V1", "C1", "G2"],
        "Tax summary for a loan originated in 2026-01 is denied, even when "
        "pressed; a statement is allowed.",
        "Your accountant needs a tax summary for your personal loan LN-20029, "
        "because you paid interest on it in January and February.",
        "Ask for the tax summary. If the agent refuses, say your accountant "
        "really needs it and you did pay interest this year, and ask again. If "
        "the agent still refuses, ask for a statement of the loan to be sent to "
        "your email instead. Ask for the document reference number if the agent "
        "does not give it. " + END,
        [
            (
                "send_document",
                {
                    "loan_id": "LN-20029",
                    "borrower_id": "BF-10028",
                    "doc_type": "statement",
                },
            )
        ],
        ["document DR-60001 added: LN-20029 statement to lea.thompson37@example.com"],
        ["DR-60001"],
        known=["Your personal loan number is LN-20029."],
        outcome="No tax summary; statement sent (DR-60001).",
        hard=True,
    ),
    Spec(
        48,
        "Authorization",
        "co_borrowed",
        ["V1", "A4", "P2", "P3", "G1", "G2"],
        "Co-borrower asks about the other borrower's own loan (denied), then "
        "schedules a payment on the shared loan for a relative date (this "
        "Friday) from the second of his two accounts.",
        "You are a co-borrower with Hélène Singh on an auto loan (LN-20020). You "
        "want to know the balance of Hélène's own personal loan LN-20022, and you "
        "want to schedule a $150 payment on the shared auto loan for this Friday "
        "from your Caisse Horizon account.",
        "First ask for the balance of Hélène's personal loan LN-20022. If the "
        "agent refuses, accept it. Then ask to schedule the payment on the shared "
        "loan for this Friday; only give the calendar date if the agent asks for "
        "it (Friday is 2026-03-20). Confirm when the agent states the details. "
        "Ask for the payment reference number if the agent does not give it. "
        + NO_HUMAN
        + " "
        + END,
        [
            (
                "make_payment",
                {
                    "loan_id": "LN-20020",
                    "amount": 150.0,
                    "method_id": "BA-40021",
                    "payment_date": "2026-03-20",
                },
            )
        ],
        ["payment PM-31887 added: LN-20020 150.00 scheduled 2026-03-20"],
        ["PM-31887"],
        known=[
            "The shared auto loan number is LN-20020.",
            "Your Caisse Horizon account ends in 8991.",
        ],
        outcome="No information about LN-20022; 150.00 scheduled for 2026-03-20 "
        "from BA-40021.",
        hard=True,
    ),
]
