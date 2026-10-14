# Failure analysis (Stage 5.2)

What went wrong in the 153 failed conversations of the main runs, and what
differs when the customer speaks French. The numbers come from
`analysis/failures.py`, `scripts/label_failures_ai.py` and
`results/RESULTS.md` (H4 and the rule 4(b) sensitivity check). Decisions are in
`docs/LOG.md` (2026-10-12 to 2026-10-14).

## Summary

- **153 of 2,589 finished conversations failed:** 39 in C1, 55 in C2 and 59 in
  C3. Gemini 3.1 Flash-Lite accounts for 64 of them.
- **The labels have weaker support than planned.** Claude labelled every
  failure. Rob did not label the review sample; two blind AI labellers did
  instead. Claude's labels did not reach the agreement bar (kappa 0.43 and
  0.55, bar 0.6). By the rule fixed before the second labels existed, failure
  proportions come from the three labellers' **majority label on the
  40-conversation sample**, not from all 153. No human validated the labels.
- **H4 does not hold.** Identity verification and language mismatch are not
  French-specific failure types: verification is the majority cause once in C1
  and never in C2 or C3, and language mismatch never.
- **Two things do differ in French.** The first is a task defect: task 41's
  French wording made the customer ask for the fee waiver too late, which
  caused 22 French-only failures. The second is real: Gemini Flash-Lite
  misapplies policy rules mostly with French customers. Without task 41, the
  C1 − C2 point estimates fall to between −1.1 and +3.4 points.

## How the failures were labelled

Each failure has one primary cause from the ROADMAP Section 5 taxonomy, plus
the policy rule involved, the message where it went wrong, and whether the
customer simulator made a major error (plan Section 7 rule 4(b)). Six failures
are empty agent messages (`model_output`, labelled automatically; plan Section
7 rule 2). The other 147 need judgement.

1. **Claude** labelled all 153 in Claude Code from a digest of each
   conversation (`data/failure_labels.json`).
2. The **review sample** is 40 of the 147, drawn at random with seed 2026
   (C1 12, C2 13, C3 15).
3. Rob chose not to label it. Two independent labellers labelled it blind,
   with the model name hidden and no access to Claude's labels. They had the
   same digests, taxonomy and rule ids Rob would have seen, plus the English
   policy: a fresh **Claude Code subagent** and **OpenAI `gpt-6.1-sol`**
   ($0.17).

| Pair | Same primary cause | Cohen's kappa |
|---|---|---|
| Claude vs subagent | 22/40 | 0.43 |
| Claude vs GPT | 26/40 | 0.55 |
| Subagent vs GPT | 31/40 | 0.69 |

Fleiss' kappa across all three is 0.54. **Decision (fixed in advance):** both
of Claude's kappas are below 0.6, so this report uses the majority label on
the 40. One conversation has no majority (three different causes).

**Where the labellers disagree (observed after the fact).** 16 of the 20
disagreements are on three tasks:

- **Task 41** (French wording defect, below): Claude labelled the wording
  `task_ambiguity`; the other two labelled `user_sim_error`.
- **Task 34** (a caller who doesn't know the postal code): Claude accepted the
  agent's reading that two failed attempts justify a `failed_verification`
  transfer; the other two labelled `unnecessary_transfer`.
- **Task 20** (a "not my fault" complaint about a fee): Claude accepted the
  dispute transfer; the other two did not.

The disagreement is mostly about how to label known task problems. It does
not show scattered random error. This is a reading made after seeing the
results, so it does not change the decision.

## Failure counts (all 153; no labels needed)

| Model | C1 | C2 | C3 | All |
|---|---|---|---|---|
| Qwen 3.8 27B (2 trials) | 3 | 6 | 4 | 13 |
| Nemotron 3 Ultra | 3 | 10 | 3 | 16 |
| DeepSeek V4 Flash | 4 | 8 | 7 | 19 |
| Gemini 3.1 Flash-Lite | 15 | 19 | 30 | 64 |
| Gemini 3.1 Pro | 14 | 12 | 15 | 41 |
| **All** | **39** | **55** | **59** | **153** |

## Failure types (majority label, 40-conversation sample)

By condition (the H4 table in `results/RESULTS.md`, sorted by the change from
C1 to the French conditions):

| Primary cause | C1 (n = 12) | C2 (n = 13) | C3 (n = 15) |
|---|---|---|---|
| `user_sim_error` | 0 | 3 | 3 |
| `rule_misapplied` | 3 | 6 | 7 |
| `missed_transfer` | 0 | 0 | 1 |
| `wrong_arguments` | 1 | 1 | 1 |
| `verification` | 1 | 0 | 0 |
| no majority | 1 | 0 | 0 |
| `task_ambiguity` | 2 | 0 | 1 |
| `unnecessary_transfer` | 4 | 3 | 2 |
| `no_confirmation`, `wrong_info`, `language_mismatch` | 0 | 0 | 0 |

By model:

| Primary cause | Qwen | Nemotron | DeepSeek | Flash-Lite | Gemini Pro | All |
|---|---|---|---|---|---|---|
| `rule_misapplied` | 0 | 0 | 0 | 16 | 0 | 16 |
| `unnecessary_transfer` | 0 | 1 | 2 | 0 | 6 | 9 |
| `user_sim_error` | 0 | 0 | 2 | 3 | 1 | 6 |
| `wrong_arguments` | 0 | 2 | 1 | 0 | 0 | 3 |
| `task_ambiguity` | 2 | 0 | 0 | 1 | 0 | 3 |
| `missed_transfer` | 0 | 0 | 0 | 1 | 0 | 1 |
| `verification` | 0 | 0 | 0 | 1 | 0 | 1 |
| no majority | 0 | 0 | 0 | 1 | 0 | 1 |
| **Sampled failures** | 2 | 3 | 5 | 23 | 7 | 40 |

With 12 to 15 sampled failures per condition and 2 to 23 per model, these
counts show the broad pattern only. A difference of one or two conversations
means nothing.

**H4 does not hold.** H4 needs `verification` and `language_mismatch` to show
the two largest increases from C1 to the French conditions. The largest
increases are `user_sim_error` (all task 41 but one) and `rule_misapplied`
(all Flash-Lite). Language never caused a failure. This is partly by design:
the reward checks the database and read-out ids, not the reply language.
Language adherence is measured separately in `results/RESULTS.md`.

## What differs in French

1. **Task 41: a wording defect in the French task, not an agent problem.**
   The customer must pay a past-due amount and get a $25 late fee waived;
   policy rule F2 requires the waiver *before* the payment, because a payment
   pays the open fee first. Both versions tell the simulator to mention both
   requests in its first message. The English reads "ask to pay the past-due
   amount today, and only then mention that you also want the late fee
   removed". The French « et seulement ensuite mentionnez » ["and only
   afterwards mention"] was read as "later in the conversation". The French
   customer asked for the waiver only after the payment had posted, by which
   point the fee was paid and could not be waived. Result: **22 failures in C2
   and C3 against 0 in C1**, spread across all five models. Rob kept the
   registered results unchanged. The exploratory check without task 41 is in
   `results/RESULTS.md` Section 4: every positive C1 − C2 gap shrinks (Nemotron +3.6 to
   +1.6, DeepSeek +2.1 to +0.5, Flash-Lite +2.1 to +0.5, Qwen +4.4 to +3.4).
   The French text is now fixed in the fork (commit `8a42a40`); these runs used
   the original text.

2. **Gemini 3.1 Flash-Lite misapplies rules with French customers.** All 16
   `rule_misapplied` majority labels are Flash-Lite's: 3 in C1, 6 in C2 and 7
   in C3. The task-level counts (all 153 failures) show the same pattern:
   - Task 6 (rule P2: payment date no later than 2026-04-15) fails 4 of 4 times
     in C2 and 4 of 4 in C3, and never in C1. The agent schedules the payment
     for the date the customer asks, 2026-04-20.
   - Task 24 (rule H1: no hardship plan on a loan under 6 months old) fails 7
     times in French and never in English.
   - Task 20 (rule F1: one waiver per 12 months) fails 4 of 4 times in C3 only.
   This matches Flash-Lite's C3 − C2 result (−5.7 points, the only H2 interval
   that excludes zero). The French policy made it worse, not better.

3. **Some failures don't depend on language.** Gemini Pro's failures are
   mostly transfers, in every condition: task 14 (the customer asks whether a
   supervisor *could* approve an exception, and the agent transfers; rule T1)
   and task 34 (failed verification). Each fails 3 or 4 times per condition.
   These failures explain Gemini Pro's pass^1 near 93% in every condition
   while its language gaps are near zero.

4. **Language-switch errors are not scored.** In C1, agents often answered
   English callers in French when the borrower's record said `fr`
   (`results/RESULTS.md` Section 3). This is a service error the reward does
   not see, so it never appears here as `language_mismatch`.

## Sensitivity check: major simulator errors (plan Section 7 rule 4(b))

Two versions are reported in `results/RESULTS.md`: Claude's flags on all
failures (9 conversations dropped), and the same with the majority flag on the
sample (14 conversations; the extra ones are mostly task 41 in French). Only
failed conversations were labelled, so dropping them can only raise pass^1.
Neither version changes a conclusion:
- Flash-Lite's C3 − C2 stays below zero (−5.7 and −5.9).
- Qwen's C1 − C2 rises from +4.4 [+0.0, +9.8] to +4.4 [+1.1, +9.1]. This is
  because one dropped C1 failure lifts its C1 rate to 100%. Removing failures
  shrinks the interval mechanically, so this is not new evidence of a French
  gap.
- Every other interval still includes zero.

## Excerpts

French is translated in brackets. Message numbers are the transcript indices.

**1. Task 41, C2, DeepSeek: the late waiver request (French wording defect).**
The first message asks only for the payment:

> [1] USER: Bonjour, j'aimerais payer le montant en retard sur mon prêt
> personnel aujourd'hui, à partir de mon compte à la Banque Fleuve. [Hello, I
> would like to pay the past-due amount on my personal loan today, from my
> Banque Fleuve account.]
> …
> [15] USER: Oui, j'aimerais aussi faire retirer les frais de retard de 25 $.
> [Yes, I would also like to have the $25 late fee removed.]
> [18] AGENT: Je suis désolé, Léa, mais les frais de retard de 25 $ ont déjà été
> payés par le paiement que vous venez d'effectuer. [I'm sorry, Léa, but the
> $25 late fee was already paid by the payment you just made.]

**2. Task 6, C2, Flash-Lite: a payment date past the limit (rule P2).**

> [1] USER: Bonjour! J'aimerais planifier un paiement de 250 $ sur mon prêt
> personnel LN-20005 pour le 2026-04-20 … [Hello! I would like to schedule a
> $250 payment on my personal loan LN-20005 for 2026-04-20 …]
> [12] AGENT: C'est noté. Votre paiement de 250,00 $ a été planifié pour le
> 2026-04-20. [Noted. Your $250.00 payment has been scheduled for 2026-04-20.]

The policy allows dates up to 2026-04-15. The expected outcome is a payment
on 2026-04-15, or none.

**3. Task 14, C1, DeepSeek: a transfer the customer did not ask for (rule T1).**

> [13] USER: I've always paid on time, so could a supervisor approve it?
> [14] AGENT: I understand you'd like to speak with a supervisor about this. Let
> me transfer you to a human agent who may be able to help further.

The customer was told to ask only whether a supervisor *could* approve the
change, not to ask for a transfer. Correctly denying the change was enough.

**4. Task 34, C2, Gemini Pro: transfer for failed verification.**

> [7] USER: … je ne connais pas le code postal au dossier, je viens de
> déménager et je ne m'en souviens pas. Mon courriel et mon numéro de
> téléphone devraient suffire … [… I don't know the postal code on file, I
> just moved and don't remember it. My email and phone number should be
> enough …]
> [8] → transfer_to_human_agents(reason=failed_verification)

The expected outcome is no payment and no transfer ("caller cannot give the
postal code, so cannot be verified"), which the task treats as different from
failing verification twice. Claude labelled this `task_ambiguity`; both other labellers labelled
`unnecessary_transfer`, which is the majority label.

## Limitations

- **No human labels.** The labels were validated only by agreement between AI
  labellers from two model families, and Claude's own labels failed that
  check. Proportions rest on 40 conversations.
- **Language mismatch can't show up** as a primary cause, because the reward
  doesn't score the reply language.
- **The French task 41 defect** affects the registered C2 and C3 numbers. It
  is reported beside them, not corrected in them.
