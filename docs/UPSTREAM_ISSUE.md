# Upstream issue draft (Stage 0.2)

To post at https://github.com/sierra-research/tau2-bench/issues/new

**Title:** Proposal: `loan_servicing` domain with English and French task variants

---

Hi! I'd like to contribute a new domain and wanted to check fit before opening a PR, as CONTRIBUTING.md suggests.

## Problem / goal

τ²-bench has no domain for **transactional** financial servicing. `banking_knowledge` tests retrieval over documents; this domain would test policy-constrained **actions** on a lender's database, in the same style as `airline` and `retail`. It would also add the first **non-English task variants**, so agents can be evaluated on whether they follow an English policy when the customer speaks another language (here, Quebec French).

## Proposed solution

A `loan_servicing` domain: the borrower-support desk of a fictional Canadian lender, with personal and auto loans in CAD. All names and data are synthetic.

- **Tools** (single control, agent only). Read: look up a borrower (by email, phone, or name plus date of birth), get borrower and loan details, list payments, calculate payoff, calculate. Write: make or cancel a payment, set autopay, change the due date, waive a late fee, enroll in a hardship plan, update contact info, send a document, transfer to a human. As in the existing domains, tools enforce data integrity only, not policy.
- **Policy** with testable rules: identity verification (name, date of birth and postal code must all match); co-borrowers vs listed third parties vs everyone else; confirmation before every write; payment amount and date limits; payoff quote windows; due date changes at most once per 12 months; late fee waivers (limits on amount and frequency); hardship eligibility (without the agent asking for medical details); and mandatory transfers (disputes, bankruptcy, fraud).
- **About 40 tasks**, roughly half requiring an action and half a refusal, a partial action, or a transfer. Rewards use `DB` or `DB` plus `COMMUNICATE`.
- **French variants.** Each task gets an FR variant with a Quebec French `user_scenario` and **identical evaluation criteria**, exposed as splits (for example `en_user` and `fr_user`). To keep scoring language-neutral, `communicate_info` only uses reference codes (like `BF-48213`) or whole numbers under 1000. French formatting of amounts and dates (`12 431,07 $`, `15 octobre`) would otherwise break substring matching.
- Optionally, a French translation of the policy (`policy_fr.md`), for evaluating a fully localized deployment.

## Impact

New files only, following the existing layout:
- `src/tau2/domains/loan_servicing/` (`data_model.py`, `tools.py`, `environment.py`, `utils.py`)
- `data/tau2/domains/loan_servicing/` (`policy.md`, `db.json`, `tasks.json`, split files)
- Tests under `tests/test_domains/test_loan_servicing/`
- One registration entry in `registry.py`

No new dependencies and no changes to core code.

## Timeline

About 3 to 4 weeks. The English domain and tasks come first, then the French variants.

## Questions

1. Would you accept this domain upstream?
2. For the French policy, which would you prefer: a second registered domain name (for example `loan_servicing_fr`) that reuses the same code and database with `policy_fr.md`, or some other mechanism?
3. Are split names like `en_user` and `fr_user` fine, or is there a convention you'd like for language variants?
4. Anything on scope, naming, or scoring you'd want changed before I start?

Thanks for τ²-bench!
