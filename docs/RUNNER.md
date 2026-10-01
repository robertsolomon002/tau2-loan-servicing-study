# Running the main experiment (`scripts/run_matrix.py`)

The runner executes the cells of `docs/EXPERIMENT_PLAN.md`: 5 agent models × C1–C3 × 48 tasks × 4 trials = 2,880 conversations. It can run unattended for days, and it is safe to stop and restart at any time.

## Commands

All commands run from the study repo folder.

```
uv run --no-sync python scripts/run_matrix.py plan configs/main/*.toml     # what's left and its projected cost (no API calls)
uv run --no-sync python scripts/run_matrix.py run configs/main/*.toml      # run or resume
uv run --no-sync python scripts/run_matrix.py status configs/main/*.toml   # rewrite results/progress.md
uv run --no-sync python scripts/run_matrix.py collect configs/main/*.toml  # one tau2 results.json per cell
```

To run only some models, pass only their configs, for example `configs/main/qwen.toml configs/main/nemotron.toml`.

## Running it on the Google Cloud VM (the plan for Stage 4.3)

The runs take about 11 days, because the free models share OpenRouter's 1,000 requests a day. So they run on a small VM in the `tau-loan-study` project instead of Rob's PC.

**The VM (set up 2026-10-01):**
- `tau-loan-runner`, zone `us-central1-a`, Debian 12.
- Machine type `e2-micro` with a 30 GB standard disk. Both are inside Google's Always Free tier, which the docs say applies during the free trial. The external IP may cost a little trial credit.
- 2 GB swap (the machine has 1 GB of memory), uv, git and tmux.
- The repos are cloned to `~/tau-loan/`, with the fork at `66e179c`. Python 3.12 (`.python-version`).
- `.env` holds only the OpenRouter and OpenAI keys and the Vertex project and location, with mode 600.
- Vertex calls use the VM's service account (`821932985217-compute@developer.gserviceaccount.com`, scope `cloud-platform`), not a personal login. That account needs the role **Vertex AI User** (`roles/aiplatform.user`) in `tau-loan-study` before the Gemini models can run there.

**Commands, from Rob's PC** (add `--project tau-loan-study --zone us-central1-a` to each):

```
gcloud compute ssh tau-loan-runner                                  # log in
# on the VM: start the runs in tmux, so they survive logging out
cd ~/tau-loan/tau2-loan-servicing-study && git pull
tmux new -d -s runs 'PYTHONUTF8=1 .venv/bin/python scripts/run_matrix.py run configs/main/*.toml'
tmux attach -t runs                                                 # watch it (detach: Ctrl+B then D)
cat results/progress.md                                             # status
touch results/raw/main/STOP                                         # clean stop

gcloud compute scp --recurse tau-loan-runner:tau-loan/tau2-loan-servicing-study/results/raw/main results/raw/   # copy results back
gcloud compute instances stop tau-loan-runner                       # stop the VM when the study is done
```

The VM test on 2026-10-01: 151 tests pass; `plan` matches the PC; the mock live run solved 4/4, and it rode out a real 429 from the free Qwen pool with the 20-second backoff.

## Running it unattended on Windows

`tmux` doesn't exist on Windows. Start the runner as a hidden background process from PowerShell instead; it keeps running after the terminal closes:

```powershell
cd C:\Users\rober\code\tau-loan\tau2-loan-servicing-study
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
Start-Process -WindowStyle Hidden -FilePath ".venv\Scripts\python.exe" `
  -ArgumentList "scripts/run_matrix.py","run","configs/main/qwen.toml","configs/main/nemotron.toml","configs/main/deepseek.toml","configs/main/flash_lite.toml","configs/main/gemini_pro.toml" `
  -RedirectStandardOutput "results/raw/main/stdout.txt" -RedirectStandardError "results/raw/main/stderr.txt"
```

From Git Bash, `nohup .venv/Scripts/python.exe scripts/run_matrix.py run configs/main/*.toml > results/raw/main/stdout.txt 2>&1 &` does the same.

**Keep the computer awake.** Windows suspends background processes when the PC sleeps. While the runs last, set *Settings → System → Power → Screen and sleep → "When plugged in, put my device to sleep after"* to **Never**, and keep the laptop plugged in. A sleep or reboot only pauses the study: restart the runner and it resumes.

## Checking on it

- **`results/progress.md`** is rewritten after every conversation. It shows spend per account against its cap, each cell's progress, pass^1 so far, failed attempts, each model's status, the free-model request count for the last 24 hours, and alerts (for example a cell with more than 5% failed attempts).
- **`results/raw/main/runner.log`** has one line per conversation, plus every retry, wait and stop.

## Stopping and resuming

- **Clean stop:** create an empty file `results/raw/main/STOP`. Each model finishes the conversation it's on, then exits. The next `run` deletes the file.
- **Hard stop** (Task Manager, a crash, a reboot): also safe. At most the conversations in progress are lost; they're rerun on restart. Their partial spend isn't recorded, which is a few cents at most.
- **Resume:** run the same `run` command again. Finished conversations are skipped, and the 24-hour request counts are restored from `rate_state.json`.
- Only one runner can use a results folder at a time; a second one refuses to start.

## What it does

- **One thread per model, one conversation at a time per model** (plan Section 3). Each model works through its cells trial by trial, then by condition, then by task. If a run stops early, every condition then has the same trials done.
- **Same conversations as `tau2 run`.** It calls tau2's own `run_single_task` with tau2's per-trial seeds (seed 300), so each cell matches `tau2 run --num-trials 4`.
- **Request pacing.** Every LLM call goes through a per-provider limiter (`configs/runner.toml` → `[providers]`):
  - per-minute limits for every provider;
  - a rolling 24-hour limit for the free OpenRouter pool (950 requests, under OpenRouter's 1,000 a day, shared by Qwen and Nemotron).
  - When the daily limit is reached, the free models wait (possibly for hours) and continue on their own; paid models keep running meanwhile.
- **Retries.** A 429, 5xx, timeout or connection error makes the call wait and retry (20 s, then 1, 2, 5, 10, 15 and 30 min). The other models on that provider wait too. If the last retry fails, the conversation is rerun later, up to 6 attempts in all, and then reported as missing.
- **Outcomes** (plan Section 7). Each attempt is logged in `<cell>/attempts.jsonl` as one of:
  - `done`: tau2 finished and scored the conversation (including `max_steps` and similar endings).
  - `model_failure`: the agent model's own output broke the conversation, for example an empty reply, unparsable tool arguments or a context overflow. It counts as a failure (reward 0), and a placeholder is saved with `info.runner_outcome = "model_failure"`.
  - `provider_error` or `user_failure` (the user simulator crashed): rerun later.
  - `runner_error`: anything unexpected. It's rerun, its traceback is logged, and progress.md raises an alert.
  - `fatal`: a bad key, a billing error or an exhausted quota. That model stops at once instead of retrying.
- **Budget.** Before each conversation, the runner checks:
  - the cell's spend plus one projected conversation against the cell budget (1.5 × the projected cell cost);
  - each account against its cap: cash $45, OpenRouter credit $6.50, Vertex trial credit $90.
  - Spend comes from metering every LLM call with LiteLLM's cost, so failed attempts count too. OpenRouter is multiplied by 1.25 for its meter; a paid model that LiteLLM can't price falls back to the list price in `runner.toml`. When a cell hits its budget it stops; when an account hits its cap, every cell charged to it stops.
- **Guards.**
  - Each cell records its models, tasks and seeds in `<cell>/cell.json`, and the runner refuses to continue a cell whose settings changed.
  - It also refuses to run a paid model it can't price.

## Files

```
results/raw/main/                 (git-ignored; uploaded to Hugging Face in Stage 4.3)
  <model>_<condition>/
    cell.json                     settings, seeds, task ids, both repos' commits
    attempts.jsonl                one line per attempt: outcome, cost by account, requests
    sims/<task>__t<trial>.json    the tau2 SimulationRun of each finished conversation
    results.json                  written by `collect`, in tau2's Results format
  rate_state.json                 rolling 24-hour request times per provider
  runner.log
results/progress.md               live status
```

## Stage 4.2 test (2026-10-01)

- **Offline:** `tests/test_run_matrix.py` runs real tau2 conversations on the mock domain with a fake LLM (15 tests). It covers stopping and resuming, seeds equal to tau2's, the settings guard, backoff then success, rerun then missing, empty agent reply as a model failure, empty user reply as a rerun, cell budget and account caps, fatal errors, `insufficient_quota`, the STOP file, the limiter, and the main configs (15 cells, 2,880 conversations).
- **Live, mock domain:** free Qwen agent and gpt-5.4-mini user, 2 tasks × 2 trials. The process was hard-killed (`Stop-Process -Force`) after 2 conversations, then restarted. It skipped the 2 finished ones and ran only trial 1, with tau2's trial seeds. 4/4 solved, $0.005.
- **Live, Vertex:** `vertex_ai/gemini-3.1-flash-lite` on `ls_018_en` (C1). Solved in 15 s; agent $0.0068 (projection $0.0092), user $0.0034.
- The test results are in `results/raw/runner_test/`. Its 14 free requests aren't in the main folder's 24-hour count; the 50-request margin under 1,000 covers them.
