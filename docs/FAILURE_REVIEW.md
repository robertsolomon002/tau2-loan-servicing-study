# Failure review (Stage 5.2, for Rob)

**Status:** Claude has labelled all 153 failed conversations (`data/failure_labels.json`). Rob's blind labels on the 40-conversation sample are pending.

## What this is

Each failed conversation of the main runs gets one label from the ROADMAP Section 5 taxonomy. Claude classified them in Claude Code (no API spend) from a digest of each conversation (`uv run python -m analysis.failures digests`): the task, what the customer was told to do, the scoring checks, the agent's write calls and the transcript. A failure is a finished conversation with reward below 1, or a model-output failure, which counts as 0 (plan Section 7 rule 2).

Before Claude's proportions can be reported, Rob labels a random sample of 40 failures and we compute Cohen's kappa on the primary cause (ROADMAP 5.2). If kappa is at least 0.6, `docs/FAILURES.md` reports Claude's labels on all 153. Otherwise it reports Rob's labels on the 40.

## The sample

- **Drawn from:** the 147 failures that need judgement, at random with seed 2026 (`analysis.failures.review_sample`). The 6 model-output failures (an empty agent message, labelled automatically) are left out.
- **By condition:** C1 12, C2 13, C3 15.
- **Keys:** `uv run python -m analysis.failures sample` prints the 40 keys.

## How to label (Rob)

```
uv run python scripts/label_failures.py            # label, resuming where you left off
uv run python scripts/label_failures.py --redo 5   # redo conversation 5
uv run python scripts/label_failures.py --agreement
```

1. For each conversation you see the task, the customer's instructions, the scoring checks and the transcript. The agent model is hidden.
2. You pick the **primary cause**: the first thing that made the conversation fail.
3. You give the policy rule id, if one is involved. The ids are listed in `docs/DOMAIN_SPEC.md` Section 4, for example F2 (waiver before payment) or T1 (transfer reasons).
4. You say whether the customer simulator made a **major error**: something its instructions forbid that changed the outcome.
5. Only then is Claude's label shown, and you can add a comment.

Every answer is saved at once to `data/failure_labels_rob.json`. To keep the labels independent, please don't open `data/failure_labels.json` until you have finished.

| # | Cause | Meaning |
|---|---|---|
| 1 | `verification` | skipped or wrong identity verification or authorization |
| 2 | `no_confirmation` | acted without the customer's explicit confirmation |
| 3 | `rule_misapplied` | a policy rule misapplied (name the rule) |
| 4 | `wrong_arguments` | right action, wrong tool arguments |
| 5 | `missed_transfer` | should have transferred and did not |
| 6 | `unnecessary_transfer` | transferred when it should not have |
| 7 | `wrong_info` | communicated wrong or missing information (for example no reference number) |
| 8 | `language_mismatch` | replied in the wrong language, and that caused the failure |
| 9 | `user_sim_error` | the user simulator broke the scenario |
| 0 | `task_ambiguity` | the task or the policy allows the agent's reading |

## Agreement

*To be filled in after Rob labels the sample.*
