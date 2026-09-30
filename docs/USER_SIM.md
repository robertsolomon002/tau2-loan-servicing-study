# User simulator choice (Stage 3.3)

Date: 2026-09-29. Fork 66e179c. Script: `scripts/user_sim_eval.py` (`plan`, `run`, `report`, `review`). Metrics: `results/user_sim_metrics.csv`. Labels: `data/user_sim_labels.json`. Review sample for Rob: `docs/USER_SIM_REVIEW.md`. Raw trajectories (git-ignored): `results/raw/stage3_3/`.

**Recommendation: `gpt-5.4-mini` as the one user simulator for every condition and agent model.** It made no simulator errors in 20 conversations and kept the task's language in 100% of user turns in both languages, including when the agent switched language. It would cost about $6 for the whole study. **Rob confirmed this choice on 2026-09-30 (Stage 3.4, ROADMAP decision 8).**

## Setup

- **Candidates:**
  - `gpt-5.4-nano`: cheap paid, the user in every pilot so far.
  - `gpt-5.4-mini`: cheap paid, stronger.
  - `gemini/gemini-3.1-flash-lite`: the best free option from Stage 0.1.
  - Prices were checked in OpenAI's docs on 2026-09-28: nano $0.20 / $1.25 and mini $0.75 / $4.50 per 1M input / output tokens. Gemini was used on the free tier.
  - OpenRouter free models and Cerebras were left out: they failed on rate limits or tool-call format in Pilot 2.
- **Fixed agent:** `gpt-5.4-mini`, default tau2 settings, temperature 0.
- **Tasks:** the same 10 in EN and FR, chosen to stress the simulator:
  - 3 (plain payment)
  - 7, 11, 14, 31 (pushing back)
  - 18, 22 (bundled or ordered requests)
  - 33, 42 (two verification attempts)
  - 48 (a relative date)
- **Conditions:** the EN tasks ran as C1. The FR tasks ran as C2 (English policy), because an English-policy agent may drift into English, which is the hardest test of whether the user keeps speaking French.
- **Size:** 3 candidates × 20 conversations × 1 trial = 60 conversations.
- **Cost:** projected $0.71 (cap $4.00); actual **$0.52** (agent $0.42, paid users $0.10).
- **Provider failures:** none. All 60 conversations completed and ended with a user stop, including on the Gemini free tier. The run used concurrency 1, and Gemini was allowed task retries with a 65 s pause, which it did not need.

## Language adherence

Every user and agent turn was classified as English or French with `lingua-language-detector`. Before detecting, the script removes stop tokens, ids, emails, postal codes, numbers and markdown, plus the DB's person and bank names; French names otherwise made "Émilie Bouchard, 2000-09-22, J2V 3E7" look French. Turns with fewer than two words left are "short" and not judged.

| Simulator | EN user turns on English | FR user turns on French | Followed the agent into the other language |
|---|---|---|---|
| gpt-5.4-nano | **91.4%** (below the 95% bar) | 100% | 2 conversations |
| gpt-5.4-mini | 100% | 100% | 0 |
| gemini-3.1-flash-lite | 100% | 100% | 0 |

Section 9 bar: at least 95% in each language. **nano fails it.** In EN tasks 18 and 22 the agent switched to French after verification (see finding 1), and nano followed it. mini and Gemini kept speaking English in the same situation.

## Simulator errors

Claude read all 60 transcripts and labeled only the simulated user's behaviour. The four types and their definitions are in `data/user_sim_labels.json`. A **major** error could change the outcome.

| Simulator | Conversations with an error (EN + FR) | With a major error | Errors by type |
|---|---|---|---|
| gpt-5.4-nano | **11 / 20** (6 + 5) | 6 | 8 contradiction, 2 language switch, 1 early reveal, 1 wrong end |
| gpt-5.4-mini | **0 / 20** | 0 | none |
| gemini-3.1-flash-lite | 3 / 20 (1 + 2) | 1 | 3 wrong end |

- **nano** is the least reliable:
  - It merged or skipped scripted push-backs.
  - It asked for a change the scenario rules out.
  - It said "oui" to a one-month deferral while asking for two.
  - It reused a postal code the agent leaked, although the scenario says it knows no other.
  - It announced its date of birth was a mistake without giving the right one.
  - Several of these would flip the score.
- **Gemini** follows scenarios well, but ends early. Once it sent `###TRANSFER###` before any transfer happened (major), and twice it asked a question and ended in the same message.
- **mini** followed every scripted beat in both languages: push-backs in order, the wrong-then-right date of birth, the relative date "ce vendredi", and clean endings. Its French is natural Quebec register (« pis », « faque »).

**Agreement with Rob (Stage 3.4, 2026-09-30).** Rob labelled the 20 conversations in `docs/USER_SIM_REVIEW.md` with `scripts/label_user_sim.py`. His answers are in `data/user_sim_labels_rob.json`. The sample was:
- all 14 conversations that Claude flagged, 7 EN and 7 FR;
- 6 clean mini conversations on the hardest tasks (31, 33, 42 in EN and FR), to check for missed errors.

| Measure | Result |
|---|---|
| Full agreement with Claude's label (types and severities) | 20 / 20 |
| Error versus no error | 20 / 20 (100%), Cohen's kappa 1.00 |
| Errors Claude missed in the 6 clean mini conversations | 0 |

Caveats:
- **One rater.** Rob is the only human rater.
- **Not fully independent.** Rob discussed 3 of the 20 with Claude before answering, and Claude explained its label each time (conversations 1, 3 and 9). The other 17 were labelled alone, and they also agree 17 / 17.
- **Display problems, fixed on 2026-09-30.** During labelling, the script showed only the first line of a multi-line user message as the user's. It also hid the shared closing rules (`[NO_HUMAN]`, `[END]`). The first problem hid the request behind the label on conversation 9 until Rob asked about it. Both are now fixed.

Taken together, the labels are a sanity check rather than a strong reliability estimate. They still support the ranking mini < Gemini < nano on simulator errors.

Rob's comment on conversation 8 (nano, EN task 22, where the agent and then nano switched to French): the switch may come from the borrower's French name. The agent switched right after verification, which is when it reads `preferred_language: fr` (finding 1 below). That points to the DB field, but the name is present from the first turn, so the two causes aren't separated. Stage 5.2 can check whether agents also switch with French-named borrowers whose `preferred_language` is `en`.

## Cost per error-free conversation

| Simulator | User cost per conversation | For a 1,728-conversation study* | Simulator errors per conversation |
|---|---|---|---|
| gpt-5.4-nano | $0.0014 | about $2.40 | 0.60 |
| gpt-5.4-mini | $0.0035 | about $6.00 | 0.00 |
| gemini-3.1-flash-lite (free) | $0 | $0, but 500 requests per day | 0.15 |

\*48 tasks × 3 conditions × 4 trials × 3 agent models; Stage 4.1 sets the real design. ROADMAP Section 6 budgeted $12 to $18 for the user simulator, so mini fits with room to spare.

nano saves about $3.60 but fails the language bar and makes an error in half the conversations. Most of its errors are the kind that make a result mean "the user broke" rather than "the agent failed". Gemini is free, but its early endings can turn an agent success into a failure. Its free tier also caps a day at about 100 conversations (500 requests at about 5 user turns each). It stays the backup if OpenAI becomes unavailable.

**Caveat for Stage 4.1:** if `gpt-5.4-mini` is also the cheap closed agent, user and agent are the same model. Same-model pairs may understand each other unusually well. Either pick the cheap agent from another provider, or report this as a limitation.

## Findings for the study (not about the simulator)

1. **The agent switched to the borrower's DB `preferred_language` instead of the caller's language.** In EN tasks 18 and 22, the borrowers have `preferred_language: fr`. After verification, the agent answered an English-speaking caller in French with all three simulators. That breaks the policy's Language rule ("Reply in the language the borrower uses"), and it happened in **C1**. The DB field acts as a realistic distractor. It belongs in the failure taxonomy (language mismatch) and the language-adherence metric, and it should be measured in every condition.
2. **tau2 opens every conversation in English.** The orchestrator's fixed first message is "Hi! How can I help you today?" (`orchestrator.py:48`), even in C3. French users ignored it and answered in French every time. The report should state it as a limitation; changing it would need a core change or a per-task `initial_state`, which C2 and C3 would then share.
3. **Agent errors seen along the way:** skipping the explicit confirmation before a write, quoting a payoff outside the 10-day window, verifying an unlisted spouse by the borrower's details, **revealing the postal code on file** to an unverified caller, and wrapping replies in JSON (`{"message": ...}`). None of this is scored except through the DB end state, so Stage 5.2 should look for it.
