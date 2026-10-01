"""Resumable, budget-capped runner for the main experiment (Stage 4.2).

Runs the cells of docs/EXPERIMENT_PLAN.md (model x condition x 48 tasks x
trials) with tau2's own per-task runner, one conversation at a time per model
and one thread per model. Every LLM call goes through a pacer that enforces
per-provider request limits (per minute and per rolling 24 hours, persisted
across restarts), backs off on 429/5xx/connection errors, and meters cost per
budget account. Each finished conversation is saved as its own file, so a
restart skips everything already done.

Usage:
    python scripts/run_matrix.py plan CONFIG...      # conversations and cost
    python scripts/run_matrix.py run CONFIG...       # run (resumable)
    python scripts/run_matrix.py status CONFIG...    # rewrite progress.md
    python scripts/run_matrix.py collect CONFIG...   # tau2 results.json per cell

Configs: configs/main/*.toml (one per model) and configs/runner.toml (shared
settings). Results: results/raw/main/<cell>/; live status: results/progress.md.
To stop a running process cleanly, create the file results/raw/main/STOP: each
model finishes its current conversation and exits. See docs/RUNNER.md.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import tomllib
import traceback
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import study_env  # noqa: F401  (sets TAU2_DATA_DIR before tau2 is imported)
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
# The study repo's .env holds the API keys and the Vertex project; load it
# before tau2 is imported (tau2's own load_dotenv does not override).
load_dotenv(REPO / ".env")

import litellm
from tau2 import TextRunConfig
from tau2.config import DEFAULT_SEED
from tau2.data_model.simulation import (
    Results,
    SimulationRun,
    TerminationReason,
)
from tau2.runner.batch import run_single_task
from tau2.runner.helpers import get_info, get_tasks
from tau2.utils import llm_utils
from tau2.utils.utils import get_now

RUNNER_TOML = REPO / "configs" / "runner.toml"
DEFAULT_OUT = REPO / "results" / "raw" / "main"
DEFAULT_PROGRESS = REPO / "results" / "progress.md"

# Plan Section 2: condition -> (tau2 domain, task split).
CONDITIONS = {
    "C1": ("loan_servicing", "en_user"),
    "C2": ("loan_servicing", "fr_user"),
    "C3": ("loan_servicing_fr", "fr_user"),
}

# Errors worth waiting out: the provider is busy or unreachable.
RETRYABLE = (
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
    litellm.BadGatewayError,
    litellm.APIConnectionError,
    litellm.Timeout,
)
# Errors that no amount of waiting fixes: stop the model's thread.
FATAL = (
    litellm.AuthenticationError,
    litellm.PermissionDeniedError,
    litellm.NotFoundError,
    litellm.BudgetExceededError,
)
FATAL_TEXT = re.compile(
    r"\b402\b|insufficient[ _](credits|funds|quota)|billing", re.IGNORECASE
)

STOP = threading.Event()
_tls = threading.local()


def log(msg: str) -> None:
    line = f"{datetime.now().astimezone():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    if RUN.log_path is not None:
        with RUN.lock, RUN.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


# ---------------------------------------------------------------------------
# Providers, accounts and pacing
# ---------------------------------------------------------------------------


def provider_of(model: str) -> str:
    if model.startswith("openrouter/"):
        return "openrouter_free" if model.endswith(":free") else "openrouter"
    if model.startswith("vertex_ai/"):
        return "vertex"
    if model.startswith("gemini/"):
        return "gemini_studio"
    return "openai"


def account_of(model: str) -> str | None:
    """Budget account a model's spend is charged to (None: free)."""
    provider = provider_of(model)
    if provider == "openrouter_free":
        return None
    if provider == "openrouter":
        return "openrouter"
    if provider == "vertex":
        return "vertex"
    return "cash"


class Limiter:
    """Requests per rolling minute and per rolling 24 hours for one provider,
    plus a shared cool-down after a 429. The 24-hour window is persisted."""

    def __init__(self, name, rpm=None, rpd=None, *, clock=time.time, sleep=None):
        self.name, self.rpm, self.rpd = name, rpm, rpd
        self.clock = clock
        self.sleep = sleep or (lambda s: STOP.wait(s))
        self.minute: deque[float] = deque()
        self.day: deque[float] = deque()
        self.cooldown_until = 0.0
        self.lock = threading.Lock()

    def wait_time(self, now: float) -> float:
        while self.minute and now - self.minute[0] >= 60:
            self.minute.popleft()
        while self.day and now - self.day[0] >= 86_400:
            self.day.popleft()
        waits = [self.cooldown_until - now]
        if self.rpm and len(self.minute) >= self.rpm:
            waits.append(60 - (now - self.minute[0]))
        if self.rpd and len(self.day) >= self.rpd:
            waits.append(86_400 - (now - self.day[0]))
        return max(waits)

    def acquire(self) -> None:
        announced = False
        while True:
            with self.lock:
                now = self.clock()
                wait = self.wait_time(now)
                if wait <= 0:
                    self.minute.append(now)
                    if self.rpd:
                        self.day.append(now)
                    return
            if wait > 120 and not announced:
                log(f"[{self.name}] request limit reached; waiting {wait / 60:.0f} min")
                announced = True
            if STOP.is_set():
                raise KeyboardInterrupt("stop requested")
            self.sleep(min(wait, 30))

    def cool_down(self, seconds: float) -> None:
        with self.lock:
            self.cooldown_until = max(self.cooldown_until, self.clock() + seconds)


@dataclass
class Meter:
    """Cost and requests of one conversation attempt, by account."""

    cost: dict[str, float] = field(default_factory=dict)
    requests: dict[str, int] = field(default_factory=dict)

    def add_request(self, provider: str) -> None:
        self.requests[provider] = self.requests.get(provider, 0) + 1

    def add_cost(self, account: str | None, cost: float) -> None:
        if account is not None:
            self.cost[account] = self.cost.get(account, 0.0) + cost


def response_cost(model: str, response) -> float:
    """LiteLLM's cost; if it reports 0 for a priced model, list price."""
    try:
        cost = litellm.completion_cost(completion_response=response) or 0.0
    except Exception:  # noqa: BLE001  (unknown model: fall back to list price)
        cost = 0.0
    price = RUN.prices.get(model)
    if cost == 0.0 and price:
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        cost = (tokens_in * price[0] + tokens_out * price[1]) / 1e6
    return cost


_original_completion = llm_utils.completion


def paced_completion(*args, **kwargs):
    """Stands in for litellm.completion inside tau2's generate()."""
    model = kwargs.get("model") or args[0]
    provider = provider_of(model)
    limiter = RUN.limiters[provider]
    meter: Meter | None = getattr(_tls, "meter", None)
    kwargs["num_retries"] = 0  # the backoff below replaces LiteLLM's retries
    for attempt in range(len(RUN.backoff) + 1):
        limiter.acquire()
        if limiter.rpd:
            RUN.save_rate_state()
        _tls.last_model = model
        if meter is not None:
            meter.add_request(provider)
        try:
            response = _original_completion(*args, **kwargs)
        except RETRYABLE as e:
            if (
                attempt == len(RUN.backoff)
                or STOP.is_set()
                or FATAL_TEXT.search(str(e))  # e.g. OpenAI's insufficient_quota
            ):
                e.tau_loan_model = model
                raise
            delay = RUN.backoff[attempt]
            limiter.cool_down(delay)
            log(
                f"[{provider}] {type(e).__name__} on {model}; retry "
                f"{attempt + 1}/{len(RUN.backoff)} in {delay}s: {str(e)[:160]}"
            )
            continue
        except Exception as e:
            e.tau_loan_model = model
            raise
        if meter is not None:
            meter.add_cost(account_of(model), response_cost(model, response))
        return response
    raise AssertionError("unreachable")


llm_utils.completion = paced_completion


# ---------------------------------------------------------------------------
# Configs and cells
# ---------------------------------------------------------------------------


@dataclass
class Cell:
    name: str  # e.g. qwen_C1
    lane: str  # config name, e.g. qwen
    condition: str
    domain: str
    split: str
    agent_llm: str
    user_llm: str
    trials: int
    task_ids: list[str] | None
    agent_cost: float  # projected $ per conversation, before meter factor
    user_cost: float
    budget: float = 0.0
    tasks: list = field(default_factory=list)
    seeds: list[int] = field(default_factory=list)
    stopped: str | None = None

    @property
    def config(self) -> TextRunConfig:
        return TextRunConfig(
            domain=self.domain,
            task_split_name=self.split,
            task_ids=self.task_ids,
            agent="llm_agent",
            llm_agent=self.agent_llm,
            user="user_simulator",
            llm_user=self.user_llm,
            num_trials=self.trials,
            max_concurrency=1,
            save_to=None,
        )

    def per_conv_total(self) -> float:
        return sum(self.projected().values())

    def projected(self) -> dict[str, float]:
        """Projected metered $ per conversation, by account."""
        out: dict[str, float] = {}
        for model, cost in (
            (self.agent_llm, self.agent_cost),
            (self.user_llm, self.user_cost),
        ):
            acct = account_of(model)
            if acct is not None:
                out[acct] = out.get(acct, 0.0) + cost * RUN.factor(acct)
        return out


def load_settings(path: Path = RUNNER_TOML) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_cells(config_paths: list[Path], budget_factor: float) -> list[Cell]:
    cells: list[Cell] = []
    for path in config_paths:
        cfg = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        specs = cfg.get("cells") or [{"condition": c} for c in cfg["conditions"]]
        for spec in specs:
            cond = spec["condition"]
            domain, split = CONDITIONS.get(cond, (None, None))
            cell = Cell(
                name=f"{cfg['name']}_{cond}",
                lane=cfg["name"],
                condition=cond,
                domain=spec.get("domain", domain),
                split=spec.get("split", split),
                agent_llm=cfg["agent_llm"],
                user_llm=cfg["user_llm"],
                trials=cfg["trials"],
                task_ids=spec.get("task_ids"),
                agent_cost=cfg["agent_cost_per_conv"],
                user_cost=cfg["user_cost_per_conv"],
            )
            if cell.domain is None:
                sys.exit(f"{path}: condition {cond} needs a domain and split")
            cell.tasks = get_tasks(
                cell.domain, task_split_name=cell.split, task_ids=cell.task_ids
            )
            # tau2's own trial seeds (runner.batch.prepare_batch), so a cell is
            # the same as `tau2 run --num-trials N` with the default seed.
            rng = random.Random(DEFAULT_SEED)
            cell.seeds = [rng.randint(0, 1000000) for _ in range(cell.trials)]
            n = len(cell.tasks) * cell.trials
            cell.budget = spec.get(
                "cell_budget",
                cfg.get("cell_budget", budget_factor * n * cell.per_conv_total()),
            )
            cells.append(cell)
    names = [c.name for c in cells]
    if len(names) != len(set(names)):
        sys.exit(f"Duplicate cell names: {names}")
    return cells


# ---------------------------------------------------------------------------
# Run state (shared by all model threads)
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    status: str = "pending"  # pending | done | model_failure | missing
    attempts: int = 0  # attempts that did not finish (provider/user errors)
    reward: float | None = None


class RunState:
    def __init__(self):
        self.lock = threading.RLock()
        self.out: Path = DEFAULT_OUT
        self.progress_path: Path = DEFAULT_PROGRESS
        self.log_path: Path | None = None
        self.settings: dict = {}
        self.prices: dict[str, tuple[float, float]] = {}
        self.backoff: list[int] = []
        self.limiters: dict[str, Limiter] = {}
        self.cells: list[Cell] = []
        self.units: dict[str, dict[tuple[str, int], Unit]] = {}
        self.cell_spend: dict[str, float] = {}  # metered $, all accounts
        self.cell_attempts: dict[str, dict[str, int]] = {}
        self.account_spend: dict[str, float] = {}  # raw LiteLLM $, this run dir
        self.lane_status: dict[str, str] = {}
        self.max_conversations: int | None = None
        self.conversations_run = 0

    def configure(self, settings: dict, out: Path, progress: Path) -> None:
        self.settings = settings
        self.out, self.progress_path = out, progress
        self.prices = {k: tuple(v) for k, v in settings.get("prices", {}).items()}
        self.backoff = list(settings["backoff_seconds"])
        self.limiters = {
            name: Limiter(name, p.get("rpm"), p.get("rpd"))
            for name, p in settings["providers"].items()
        }
        for name in (
            "openrouter_free",
            "openrouter",
            "openai",
            "vertex",
            "gemini_studio",
        ):
            self.limiters.setdefault(name, Limiter(name))
        self.load_rate_state()

    def factor(self, account: str) -> float:
        return self.settings["accounts"][account].get("meter_factor", 1.0)

    def account_total(self, account: str) -> float:
        acct = self.settings["accounts"][account]
        return acct.get("already_spent", 0.0) + self.account_spend.get(
            account, 0.0
        ) * self.factor(account)

    # --- rate state -------------------------------------------------------

    @property
    def rate_path(self) -> Path:
        return self.out / "rate_state.json"

    def load_rate_state(self) -> None:
        if self.rate_path.exists():
            data = json.loads(self.rate_path.read_text(encoding="utf-8"))
            for name, stamps in data.items():
                if name in self.limiters:
                    self.limiters[name].day = deque(sorted(stamps))

    def save_rate_state(self) -> None:
        data = {n: list(lim.day) for n, lim in self.limiters.items() if lim.rpd}
        if data:
            with self.lock:
                atomic_write(self.rate_path, json.dumps(data))


RUN = RunState()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def shown(path: Path) -> str:
    """A path relative to the repo when it is inside it."""
    return (path.relative_to(REPO) if path.is_relative_to(REPO) else path).as_posix()


def cell_dir(cell: Cell) -> Path:
    return RUN.out / cell.name


def sim_path(cell: Cell, task_id: str, trial: int) -> Path:
    return cell_dir(cell) / "sims" / f"{task_id}__t{trial}.json"


def git_commit(path: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip
    except Exception:  # noqa: BLE001  (no git: record nothing)
        return None


def fork_rev() -> str | None:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'rev\s*=\s*"([0-9a-f]+)"', text)
    return m.group(1) if m else None


def write_cell_info(cell: Cell) -> None:
    """Record the cell's settings once; refuse to continue a cell whose models
    or tasks changed since it started."""
    path = cell_dir(cell) / "cell.json"
    info = {
        "cell": cell.name,
        "condition": cell.condition,
        "domain": cell.domain,
        "split": cell.split,
        "agent_llm": cell.agent_llm,
        "user_llm": cell.user_llm,
        "trials": cell.trials,
        "seeds": cell.seeds,
        "task_ids": [t.id for t in cell.tasks],
    }
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        changed = [k for k in info if old.get(k) != info[k]]
        if changed:
            sys.exit(f"{cell.name}: settings changed since the cell started: {changed}")
        return
    info |= {
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        "study_commit": git_commit(REPO),
        "fork_commit": fork_rev(),
    }
    atomic_write(path, json.dumps(info, indent=2))


def load_state(cells: list[Cell]) -> None:
    """Rebuild every unit's status and the spend from the files on disk."""
    max_attempts = RUN.settings["max_attempts"]
    RUN.cells = cells
    for cell in cells:
        units = {(t.id, k): Unit() for k in range(cell.trials) for t in cell.tasks}
        attempts_file = cell_dir(cell) / "attempts.jsonl"
        counts: dict[str, int] = {}
        spend = 0.0
        if attempts_file.exists():
            for line in attempts_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                counts[rec["outcome"]] = counts.get(rec["outcome"], 0) + 1
                for acct, cost in rec["cost"].items():
                    RUN.account_spend[acct] = RUN.account_spend.get(acct, 0.0) + cost
                    spend += cost * RUN.factor(acct)
                unit = units.get((rec["task_id"], rec["trial"]))
                if unit is not None and rec["outcome"] not in ("done", "model_failure"):
                    unit.attempts += 1
        for (task_id, trial), unit in units.items():
            path = sim_path(cell, task_id, trial)
            if path.exists():
                sim = json.loads(path.read_text(encoding="utf-8"))
                outcome = (sim.get("info") or {}).get("runner_outcome")
                unit.status = "model_failure" if outcome == "model_failure" else "done"
                unit.reward = (sim.get("reward_info") or {}).get("reward")
            elif unit.attempts >= max_attempts:
                unit.status = "missing"
        RUN.units[cell.name] = units
        RUN.cell_spend[cell.name] = spend
        RUN.cell_attempts[cell.name] = counts


# ---------------------------------------------------------------------------
# One conversation
# ---------------------------------------------------------------------------


def classify_error(e: BaseException, cell: Cell) -> str:
    """Plan Section 7: provider failures and user-simulator crashes are rerun;
    the agent model's own bad output counts as a failure."""
    if isinstance(e, FATAL) or FATAL_TEXT.search(str(e)):
        return "fatal"
    if isinstance(e, RETRYABLE):
        return "provider_error"
    # The model whose call failed, or whose reply tau2 rejected right after it
    # (an empty message, unparsable tool arguments, a context overflow).
    model = getattr(e, "tau_loan_model", None) or getattr(_tls, "last_model", None)
    if "UserMessage must have" in str(e):
        return "user_failure"
    if isinstance(e, (ValueError, AssertionError, litellm.BadRequestError)):
        return "model_failure" if model == cell.agent_llm else "user_failure"
    return "runner_error"


class FatalError(Exception):
    pass


def run_one(cell: Cell, task, trial: int) -> str:
    seed = cell.seeds[trial]
    meter = Meter()
    _tls.meter, _tls.last_model = meter, None
    started = get_now()
    t0 = time.time()
    sim: SimulationRun | None = None
    error: BaseException | None = None
    try:
        sim = run_single_task(cell.config, task, seed=seed)
        sim.trial = trial
        outcome = "done"
    except KeyboardInterrupt:
        raise
    except Exception as e:  # noqa: BLE001  (every failure is classified)
        error = e
        outcome = classify_error(e, cell)
    finally:
        _tls.meter = None
    if outcome == "model_failure":
        now = get_now()
        sim = SimulationRun(
            id=str(uuid.uuid4()),
            task_id=task.id,
            timestamp=now,
            start_time=started,
            end_time=now,
            duration=time.time() - t0,
            termination_reason=TerminationReason.INFRASTRUCTURE_ERROR,
            messages=[],
            trial=trial,
            seed=seed,
            info={
                "runner_outcome": "model_failure",
                "error": str(error),
                "error_type": type(error).__name__,
                "failed_model": getattr(error, "tau_loan_model", None)
                or getattr(_tls, "last_model", None),
            },
        )
    record = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "task_id": task.id,
        "trial": trial,
        "seed": seed,
        "outcome": outcome,
        "seconds": round(time.time() - t0, 1),
        "cost": {k: round(v, 6) for k, v in meter.cost.items()},
        "requests": meter.requests,
    }
    if sim is not None and sim.reward_info is not None:
        record["reward"] = sim.reward_info.reward
        record["termination"] = str(sim.termination_reason.value)
    if error is not None:
        record["error_type"] = type(error).__name__
        record["error"] = str(error)[:500]
        if outcome == "runner_error":
            record["traceback"] = "".join(traceback.format_exception(error))[-3000:]
    with RUN.lock:
        # The attempt is logged before the conversation file, so its spend is
        # never lost; a crash in between only means the conversation reruns.
        with (cell_dir(cell) / "attempts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        if sim is not None:
            atomic_write(sim_path(cell, task.id, trial), sim.model_dump_json(indent=2))
        update_state(cell, task.id, trial, record)
    if outcome == "fatal":
        raise FatalError(f"{type(error).__name__}: {error}")
    return outcome


def update_state(cell: Cell, task_id: str, trial: int, record: dict) -> None:
    unit = RUN.units[cell.name][(task_id, trial)]
    outcome = record["outcome"]
    counts = RUN.cell_attempts[cell.name]
    counts[outcome] = counts.get(outcome, 0) + 1
    for acct, cost in record["cost"].items():
        RUN.account_spend[acct] = RUN.account_spend.get(acct, 0.0) + cost
        RUN.cell_spend[cell.name] += cost * RUN.factor(acct)
    if outcome in ("done", "model_failure"):
        unit.status = outcome
        unit.reward = record.get("reward")
    else:
        unit.attempts += 1
        if unit.attempts >= RUN.settings["max_attempts"]:
            unit.status = "missing"


def budget_block(cell: Cell) -> str | None:
    """Why the next conversation of this cell must not start, if it must not."""
    projected = cell.projected()
    if RUN.cell_spend[cell.name] + sum(projected.values()) > cell.budget:
        return f"cell budget ${cell.budget:.2f} reached"
    for acct, cost in projected.items():
        cap = RUN.settings["accounts"][acct]["stop_at"]
        if RUN.account_total(acct) + cost > cap:
            return f"{acct} account cap ${cap:.2f} reached"
    return None


# ---------------------------------------------------------------------------
# Model threads
# ---------------------------------------------------------------------------


def stop_requested() -> bool:
    if (RUN.out / "STOP").exists():
        STOP.set()
    return STOP.is_set()


def lane_loop(lane: str, cells: list[Cell]) -> None:
    """Run one model's cells: trial by trial, then condition, then task, so a
    run that stops early still has every condition at the same trials."""
    try:
        while True:
            pending = progressed = False
            for trial in range(max(c.trials for c in cells)):
                for cell in cells:
                    if cell.stopped or trial >= cell.trials:
                        continue
                    for task in cell.tasks:
                        unit = RUN.units[cell.name][(task.id, trial)]
                        if unit.status != "pending":
                            continue
                        if stop_requested():
                            RUN.lane_status[lane] = "stopped (STOP requested)"
                            return
                        with RUN.lock:
                            if RUN.max_conversations is not None and (
                                RUN.conversations_run >= RUN.max_conversations
                            ):
                                RUN.lane_status[lane] = "paused (--max-conversations)"
                                return
                            block = budget_block(cell)
                            if not block:
                                RUN.conversations_run += 1
                        if block:
                            cell.stopped = block
                            log(f"[{cell.name}] stopped: {block}")
                            write_progress()
                            break
                        pending = True
                        RUN.lane_status[lane] = (
                            f"running {cell.name} {task.id} t{trial}"
                        )
                        outcome = run_one(cell, task, trial)
                        progressed = progressed or outcome in ("done", "model_failure")
                        log(
                            f"[{cell.name}] {task.id} t{trial}: {outcome}"
                            + (
                                f" reward={unit.reward}"
                                if unit.reward is not None
                                else ""
                            )
                            + f" (cell ${RUN.cell_spend[cell.name]:.3f})"
                        )
                        write_progress()
            if not pending:
                stopped = [c.name for c in cells if c.stopped]
                RUN.lane_status[lane] = (
                    f"finished; budget-stopped: {', '.join(stopped)}"
                    if stopped
                    else "complete"
                )
                return
            if not progressed:
                pause = RUN.settings["idle_pause_seconds"]
                RUN.lane_status[lane] = f"waiting {pause // 60} min (provider errors)"
                write_progress()
                log(f"[{lane}] a whole pass failed; pausing {pause // 60} min")
                if STOP.wait(pause):
                    return
    except FatalError as e:
        RUN.lane_status[lane] = f"stopped: {e}"[:200]
        log(f"[{lane}] FATAL, model stopped: {e}")
    except KeyboardInterrupt:
        RUN.lane_status[lane] = "stopped (STOP requested)"
    except Exception as e:  # noqa: BLE001  (a runner bug: keep other models going)
        RUN.lane_status[lane] = f"crashed: {type(e).__name__}: {e}"[:200]
        log(f"[{lane}] CRASH: {traceback.format_exc()}")
    finally:
        write_progress()


# ---------------------------------------------------------------------------
# Progress report
# ---------------------------------------------------------------------------


def write_progress() -> None:
    with RUN.lock:
        atomic_write(RUN.progress_path, progress_markdown())


def progress_markdown() -> str:
    lines = [
        "# Main-run progress",
        "",
        (
            f"Updated {datetime.now().astimezone():%Y-%m-%d %H:%M} (written by "
            f"`scripts/run_matrix.py`; results in "
            f"`{shown(RUN.out)}/`)."
        ),
        "",
        "## Spend",
        "",
        "| Account | Before the runs | Metered here | Total | Stop at |",
        "|---|---|---|---|---|",
    ]
    for acct, cfg in RUN.settings["accounts"].items():
        before = cfg.get("already_spent", 0.0)
        total = RUN.account_total(acct)
        lines.append(
            f"| {acct} | ${before:.2f} | ${total - before:.2f} | **${total:.2f}** "
            f"| ${cfg['stop_at']:.2f} |"
        )
    lines += [
        "",
        "## Cells",
        "",
        (
            "| Cell | Done / planned | Model failures | Missing | Pending "
            "| Pass^1 so far | Failed attempts* | Spend / budget | Status |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    alerts = []
    totals = {"planned": 0, "final": 0}
    for cell in RUN.cells:
        units = RUN.units[cell.name].values()
        n = len(units)
        done = sum(u.status == "done" for u in units)
        model_fail = sum(u.status == "model_failure" for u in units)
        missing = sum(u.status == "missing" for u in units)
        pending = sum(u.status == "pending" for u in units)
        scored = [
            u.reward or 0.0 for u in units if u.status in ("done", "model_failure")
        ]
        pass1 = f"{sum(scored) / len(scored):.2f}" if scored else "–"
        counts = RUN.cell_attempts[cell.name]
        attempts = sum(counts.values())
        failed = sum(v for k, v in counts.items() if k not in ("done", "model_failure"))
        rate = failed / attempts if attempts else 0.0
        if attempts >= 10 and rate > 0.05:
            alerts.append(
                f"{cell.name}: {rate:.0%} of attempts failed for provider or runner reasons (over 5%)."
            )
        if done + model_fail >= 10 and model_fail / (done + model_fail) > 0.05:
            alerts.append(
                f"{cell.name}: {model_fail} model-output failures; check they are the model's fault."
            )
        if counts.get("runner_error"):
            alerts.append(
                f"{cell.name}: {counts['runner_error']} runner errors (see attempts.jsonl tracebacks)."
            )
        lane_status = RUN.lane_status.get(cell.lane, "not running")
        if cell.stopped:
            status = f"stopped: {cell.stopped}"
        elif pending == 0:
            status = "complete"
        elif lane_status.startswith(f"running {cell.name} "):
            status = "running"
        elif lane_status.startswith("running"):
            status = "queued"
        else:
            status = lane_status
        lines.append(
            f"| {cell.name} | {done + model_fail} / {n} | {model_fail} | {missing} | {pending} "
            f"| {pass1} | {failed} / {attempts} ({rate:.0%}) "
            f"| ${RUN.cell_spend[cell.name]:.3f} / ${cell.budget:.2f} | {status} |"
        )
        totals["planned"] += n
        totals["final"] += done + model_fail
    lines += [
        "",
        f"**Overall:** {totals['final']} / {totals['planned']} conversations finished.",
        "",
        (
            "\\*Attempts that ended with a provider error, a user-simulator crash "
            "or a runner error. Those conversations are rerun, up to "
            f"{RUN.settings['max_attempts']} attempts, then counted as missing."
        ),
        "",
        "## Models",
        "",
        "| Model | Status |",
        "|---|---|",
    ]
    for lane in dict.fromkeys(c.lane for c in RUN.cells):
        lines.append(f"| {lane} | {RUN.lane_status.get(lane, 'not running')} |")
    lines += [
        "",
        "## Request limits (rolling 24 hours)",
        "",
        "| Provider | Requests | Per-day limit |",
        "|---|---|---|",
    ]
    now = time.time()
    for name, lim in RUN.limiters.items():
        if lim.rpd:
            used = sum(1 for t in lim.day if now - t < 86_400)
            lines.append(f"| {name} | {used} | {lim.rpd} |")
    lines += ["", "## Alerts", ""]
    lines += [f"- {a}" for a in alerts] or ["None."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def plan(cells: list[Cell]) -> None:
    """Remaining conversations and their projected cost, by account."""
    by_acct: dict[str, float] = {}
    total_left = 0
    print(
        f"{'cell':26s} {'left':>5s} {'planned':>7s} {'$/conv':>8s} {'$ left':>8s} {'budget':>7s}"
    )
    for cell in cells:
        units = RUN.units[cell.name].values()
        left = sum(u.status == "pending" for u in units)
        total_left += left
        per = cell.per_conv_total()
        for acct, cost in cell.projected().items():
            by_acct[acct] = by_acct.get(acct, 0.0) + cost * left
        print(
            f"{cell.name:26s} {left:5d} {len(units):7d} {per:8.4f} "
            f"{per * left:8.2f} {cell.budget:7.2f}"
        )
    print(f"\n{total_left} conversations left.")
    for acct, cost in sorted(by_acct.items()):
        cap = RUN.settings["accounts"][acct]["stop_at"]
        now = RUN.account_total(acct)
        flag = "  OVER THE CAP" if now + cost > cap else ""
        print(
            f"  {acct:11s} spent ${now:6.2f} + projected ${cost:6.2f} "
            f"= ${now + cost:6.2f} (stop at ${cap:.2f}){flag}"
        )


def check_prices(cells: list[Cell]) -> None:
    """Refuse to run a paid model whose cost LiteLLM cannot compute and that
    has no list price in configs/runner.toml: its spend would read $0."""
    for model in {m for c in cells for m in (c.agent_llm, c.user_llm)}:
        if account_of(model) is None:
            continue
        known = (
            model in litellm.model_cost or model.split("/", 1)[-1] in litellm.model_cost
        )
        if not known and model not in RUN.prices:
            sys.exit(f"No price for paid model {model}: add it under [prices].")


def acquire_lock(out: Path):
    """One runner per results folder; the OS frees the lock if it dies."""
    out.mkdir(parents=True, exist_ok=True)
    f = open(out / "runner.lock", "a+")  # noqa: SIM115  (held open until exit)
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"Another run_matrix.py is already running on {out}.")
    return f


def run(cells: list[Cell]) -> None:
    check_prices(cells)
    lock = acquire_lock(RUN.out)  # noqa: F841 (held until exit)
    stop_file = RUN.out / "STOP"
    if stop_file.exists():
        stop_file.unlink()
        log("Removed an old STOP file.")
    RUN.log_path = RUN.out / "runner.log"
    for cell in cells:
        write_cell_info(cell)
    plan(cells)
    lanes: dict[str, list[Cell]] = {}
    for cell in cells:
        lanes.setdefault(cell.lane, []).append(cell)
    log(f"Starting {len(lanes)} model thread(s): {', '.join(lanes)}")
    threads = [
        threading.Thread(
            target=lane_loop, args=(lane, lane_cells), name=lane, daemon=True
        )
        for lane, lane_cells in lanes.items()
    ]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=1)
    except KeyboardInterrupt:
        log("Ctrl+C: stopping after the current conversations (Ctrl+C again to kill).")
        STOP.set()
        for t in threads:
            t.join()
    write_progress()
    log(
        "Runner finished: " + "; ".join(f"{k}: {v}" for k, v in RUN.lane_status.items())
    )


def collect(cells: list[Cell]) -> None:
    """Write each cell's finished conversations as a tau2 results.json."""
    for cell in cells:
        sims = []
        for (task_id, trial), unit in sorted(RUN.units[cell.name].items()):
            if unit.status in ("done", "model_failure"):
                path = sim_path(cell, task_id, trial)
                sims.append(
                    SimulationRun.model_validate_json(path.read_text(encoding="utf-8"))
                )
        results = Results(
            info=get_info(cell.config), tasks=cell.tasks, simulations=sims
        )
        out = cell_dir(cell) / "results.json"
        atomic_write(out, results.model_dump_json(indent=2))
        print(f"{cell.name}: {len(sims)} conversations -> {shown(out)}")


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["plan", "run", "status", "collect"])
    parser.add_argument("configs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--progress", type=Path, default=None)
    parser.add_argument("--settings", type=Path, default=RUNNER_TOML)
    parser.add_argument(
        "--max-conversations", type=int, default=None,
        help="stop after starting this many conversations (for tests)",
    )  # fmt: skip
    args = parser.parse_args(argv)
    out = args.out.resolve()
    progress = (
        args.progress
        or (DEFAULT_PROGRESS if out == DEFAULT_OUT else out / "progress.md")
    ).resolve()
    settings = load_settings(args.settings)
    RUN.configure(settings, out, progress)
    RUN.max_conversations = args.max_conversations
    cells = load_cells(args.configs, settings["budget_factor"])
    load_state(cells)
    if args.command == "plan":
        plan(cells)
    elif args.command == "run":
        run(cells)
    elif args.command == "status":
        write_progress()
        print(RUN.progress_path.read_text(encoding="utf-8"))
    else:
        collect(cells)


if __name__ == "__main__":
    main()
