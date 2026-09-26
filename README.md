# τ-Loan: a bilingual loan-servicing study for τ²-bench

Do customer-service agents follow policy as well when the customer speaks Quebec French?
This repo holds the experiment configs, runner, analysis, and write-up. The
`loan_servicing` domain itself lives in a fork of
[sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench)
([robertsolomon002/tau2-bench](https://github.com/robertsolomon002/tau2-bench), branch
`domain/loan_servicing/initial`), pinned in `pyproject.toml`.

All names and data (including the lender, Boréal Finance) are fictional.

Status: setup (see `ROADMAP.md` Section 13).

## Setup

```sh
uv sync
cp .env.example .env   # then fill in the keys you use
```
