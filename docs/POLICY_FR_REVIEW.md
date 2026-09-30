# French policy: back-translation check (Stage 3.1)

`policy_fr.md` (fork, `data/tau2/domains/loan_servicing/`) is the Quebec French translation of `policy.md`, used by the domain `loan_servicing_fr` (condition C3). This file records how it was checked for meaning drift. Terms follow `docs/GLOSSARY_FR.md`.

## Method

1. Claude translated `policy.md` into Quebec French, keeping the heading structure, every rule, and every code token, number, date and amount.
2. **Independent back-translation.** A fresh Claude subagent saw only `policy_fr.md`, never the English original, and translated it back into English as literally as possible. It also listed every French sentence it found ambiguous or unidiomatic. The result is `docs/POLICY_FR_BACKTRANSLATION.md`.
3. The back-translation was compared rule by rule with `policy.md` (table below).
4. **Automated parity** (fork test `test_french_policy_keeps_every_code_and_number`): both policies have the same multiset of backtick code tokens, of numbers, dates and amounts, and of Markdown headings. They also have the same number of bullets (50) and bold markers (54). The FR policy has 1,881 words and the EN one 1,614.

## Rule-by-rule comparison

"Same" means the back-translation states the same rule with the same conditions and values. The differences are in wording only.

| Section | Rule | Verdict |
|---|---|---|
| Header | Date 2026-03-16 (Monday), date format, "within 12 months" = on or after 2025-03-16 | Same |
| Header | Montréal; Quebec and Ontario; the 9 capabilities | Same ("waive" becomes "cancel late fees", per the glossary) |
| Verification | Name + DOB + postal code must all match one record; finding is not verifying; unknown value = not verified; 2 failures = transfer `failed_verification` | Same |
| Who may act | Borrower or co-borrower: any action; third party: verified with own name + borrower's 3 values, general info only (status, next due date, monthly payment, past-due amount); nobody else; one borrower per conversation; co-borrower can't see the other's contact info or loans | Same |
| Confirmation | State details, explicit "yes", one action at a time, re-confirm on change | Same |
| Reference numbers | Give exactly as written | Same |
| Tools | One call at a time; no message in the same turn; tools don't check policy | Same |
| Accuracy | No invention; no legal, tax or financial advice; use `calculate` | Same |
| Language | Reply in the borrower's language (English or French); keep ids | Same |
| Denials | Deny and name the rule | Same |
| Domain basics | Borrower and loan fields; 6 loan statuses; 4 payment statuses | Same (the FR adds a gloss to `cancelled`) |
| Payments | $1.00 to payoff on the payment date; refuse the excess; date today to 2026-04-15; bank account on file only, no transfer for a new method; allocation fees > interest > principal, loan becomes `current` at $0.00; cancel only `scheduled`; dispute of a posted payment = `dispute`; none on `paid_off` / `charged_off` | Same |
| Payoff | Dates today to 2026-03-26; payoff = principal + interest to date + open fees; letter always for 2026-03-26 | Same |
| Due date | 4 conditions (`current`, no change in 12 months, next due date after 2026-03-21, day 1 to 28 and different); same-month rule; one change per call | Same |
| Waivers | Fee `open` and at most $50.00; no other waiver in 12 months; `current` or `past_due_30`; one per loan per call; waiver before payment | Same |
| Hardship | 4 conditions (stated loss of income or expense, originated on or before 2025-09-16, no plan in 12 months, status); `deferral_1` first, `deferral_2` only if one month isn't enough, `reduced_payment_3` only if they can pay part; deferral effect; `in_hardship`; no probing; no credit promises | Same |
| Autopay | `current` or `past_due_30`; method on file; day = due day or up to 5 days before; keep the other setting; disabling always allowed | Same |
| Documents | Email on file only; update email first; 3 types and their limits; no document after an email change in the same conversation | Same |
| Contact updates | Own email and phone only; apply as confirmed | Same |
| Transfers | 7 situations and their reasons; an explicit denial is not a transfer reason; call the tool, tell the borrower, give the reference | Same |

**Result: no meaning drift.** Every rule, condition, value and reason is preserved.

## Changes made after the back-translation

The subagent flagged 16 points. These were fixed in `policy_fr.md` (the plural "frais" row came from the rule-by-rule comparison, not the subagent):

| Flag | Before | After |
|---|---|---|
| Verb without an object | inscrire à un plan d'aide financière | inscrire **l'emprunteur** à un plan d'aide financière |
| "le" could refer to more than one thing | Pour le vérifier, l'appelant doit… | Pour vérifier l'identité d'un tiers autorisé, l'appelant doit… |
| Calque "faire une action" | faire toute action; Faites une seule action; faire ou annuler des paiements | effectuer… (3 places) |
| Plural "frais" could be read as a total | Les frais sont `open` et de $50.00 ou moins. | Les frais de retard visés sont `open` et s'élèvent à $50.00 ou moins. |
| "Aucuns autres frais" looks like an error | Aucuns autres frais de retard du même prêt n'ont été annulés… | Aucune autre annulation de frais de retard n'a été faite sur le même prêt… |
| "tout plan" = "any" or "the whole" | Pendant tout plan, le prêt est `in_hardship`. | Tant qu'un plan est en cours, le prêt est `in_hardship`. |

The rest were kept on purpose:
- **English-format amounts** (`$1.00`): Rob's decision; see `docs/GLOSSARY_FR.md`.
- **The same ambiguity exists in `policy.md`**, so the translation stays faithful rather than clarifying only one language. This covers: "the tools don't check this policy", `paid_off` "only information and documents", "one change per call" versus "per conversation", "added to the end of the loan", "disabling autopay is always allowed", "then the rule below applies", and table rows with no subject. Changing these would change the rules for C3 only. If any should change, change both policies together.
- **"prêt auto"** is kept, because Quebec lenders use it; "prêt automobile" is more formal.
- **"transmis au recouvrement"** is kept, because the English says "sent to collections", not "written off".
- **"montant de remboursement intégral"** is kept for consistency with "lettre de remboursement intégral". The alternative "solde de remboursement anticipé" is for Rob to consider in 3.4.
- **"tour"** (turn) mirrors the English "turn". The agent reads it as conversation jargon in either language.

`POLICY_FR_BACKTRANSLATION.md` was made before these six fixes, so it shows the earlier wording at those places.

## For Rob (Stage 3.4)

Read `policy_fr.md` as a Quebec lender's document. The open wording choices are "annuler des frais de retard" (versus "renoncer à"), "plan d'aide financière", "montant de remboursement intégral", and "agent" versus "conseiller".

**Rob's review (2026-09-30):** approved as is. All four open choices keep their current wording: "annuler des frais de retard", "plan d'aide financière", "montant de remboursement intégral" and "agent". `docs/GLOSSARY_FR.md` and the FR task texts in `docs/TASKS_FR_REVIEW.md` were approved without changes too.
