# French glossary (Stage 3.1)

These are the fixed terms for everything in French in this study: `policy_fr.md` (fork, `data/tau2/domains/loan_servicing/`), the FR task variants (Stage 3.2), and any French in the report. Use them exactly, so the agent's policy and the user's scenario name things the same way. Rob approved this list without changes in Stage 3.4 (2026-09-30).

## Conventions

- **Never translated:** code tokens in backticks (tool names, statuses, plan ids, document types, transfer reasons, field names such as `authorized_third_parties`). The tools only accept the English values, so the French policy glosses them in brackets instead, for example `` `returned` (refusé par la banque) ``.
- **Ids and reference numbers:** unchanged (`BF-10001`, `LN-20001`, `BA-40001`, `PM-30112`).
- **Dates:** ISO `AAAA-MM-JJ` (the policy's own format), for example `2026-03-16 (lundi)`.
- **Amounts:** English format, `$50.00` (Rob's decision, 2026-09-29). This keeps the policy identical in form to the English one and to the tool outputs (`50.0`), so number formatting is not a confound between C2 and C3. Natural Quebec French would be `50,00 $`. The FR user scenarios (Stage 3.2) do use the Quebec form (`150 $`, `4 000 $`), as a customer would say it. C2 and C3 share those users, so this is not a confound between them. `communicate_info` never contains amounts over 999.
- **User scenarios (Stage 3.2):** `scripts/task_specs_fr.py`. The FR persona line is « Vous parlez français québécois et ne passez à l'anglais que si l'agent ne peut pas continuer en français. » In speech, customers use everyday words: « sauter un versement », « lettre de remboursement », « montant en retard ». The agent has to map these to the policy's terms, as it would with a real customer.
- **Register:** the agent is addressed as *vous*; the borrower is *l'emprunteur* (generic masculine, as in Quebec lender documents).
- **Typography:** guillemets « » for quoted words, a space before the colon, and no space before `; ! ?` (Quebec usage).

## Terms

| English | French | Notes |
|---|---|---|
| Borrower Support Policy | Politique de service aux emprunteurs | Title |
| borrower support agent | agent du service aux emprunteurs | |
| human agent | agent humain | "Transférer l'appel à un agent humain" |
| borrower | emprunteur | |
| co-borrower | coemprunteur | No hyphen (OQLF) |
| primary borrower | emprunteur principal | |
| authorized third party | tiers autorisé | |
| caller | appelant | |
| borrower record | dossier d'emprunteur | |
| on file | au dossier | "compte bancaire au dossier", "courriel au dossier" |
| verify / verification | vérifier / vérification (d'identité) | |
| full name | nom complet | |
| date of birth | date de naissance | |
| postal code | code postal | |
| email | courriel | Never "e-mail" or "mail" |
| phone | téléphone / numéro de téléphone | |
| contact information | coordonnées | |
| preferred language | langue préférée | |
| general information | renseignements généraux | "renseignement", not "information", for facts about an account |
| loan | prêt | |
| personal loan / auto loan | prêt personnel / prêt auto | Product values stay `personal` / `auto` |
| origination date / originated | date d'octroi / octroyé | |
| annual interest rate | taux d'intérêt annuel | |
| term | durée | |
| monthly payment | versement mensuel | "versement" for the scheduled instalment, "paiement" for a payment made |
| payment | paiement | |
| missed payment | versement manqué | |
| principal / principal balance | capital / solde du capital | |
| accrued interest | intérêts courus | |
| due day | jour d'échéance | |
| (next) due date | (prochaine) date d'échéance | |
| past-due amount | montant en souffrance | |
| past due (status) | en souffrance | |
| status | statut | |
| posted | appliqué | Gloss of `posted` |
| scheduled | planifié | Gloss of `scheduled` |
| cancelled | annulé | Gloss of `cancelled` |
| returned (payment) | refusé par la banque | Gloss of `returned` |
| sent to collections | transmis au recouvrement | Gloss of `charged_off` |
| payment method | mode de paiement | |
| bank account | compte bancaire | |
| online portal | portail en ligne | |
| payoff amount / quote a payoff | montant de remboursement intégral / indiquer le montant de remboursement intégral | |
| payoff letter | lettre de remboursement intégral | Gloss of `payoff_letter` |
| late fee | frais de retard | Always plural in French; "open" fee = frais non réglés (`open`) |
| waive a late fee / waiver | annuler des frais de retard / annulation de frais | Not "renonciation", which is unnatural on the phone |
| hardship plan | plan d'aide financière | Status `in_hardship` = "visé par un plan d'aide financière en cours" |
| lost income / unexpected expense | perte de revenu / dépense imprévue | |
| skip a payment (deferral) | sauter un versement (report) | `deferral_1`, `deferral_2` |
| pay half the monthly payment | payer la moitié du versement mensuel | `reduced_payment_3` |
| credit report | dossier de crédit | |
| autopay | prélèvement automatique | |
| enable / disable autopay | activer / désactiver le prélèvement automatique | |
| statement | relevé de compte | Gloss of `statement` |
| tax summary | relevé fiscal | Gloss of `tax_summary` |
| reference number | numéro de référence | |
| transfer (the call) | transférer (l'appel) | |
| reason (for transfer) | motif | |
| dispute | contester | `dispute` |
| bankruptcy / lawyer / legal action | faillite / avocat / poursuite judiciaire | `legal` |
| fraud / identity theft | fraude / vol d'identité | `fraud` |
| complaint about staff | se plaindre du personnel | `complaint` |
| write tool | outil d'écriture | |
| within the last 12 months | au cours des 12 derniers mois | |
| inclusive | inclusivement | |
