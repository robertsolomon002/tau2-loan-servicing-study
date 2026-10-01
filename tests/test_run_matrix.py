"""Offline tests of scripts/run_matrix.py: a fake LLM stands in for LiteLLM,
and real tau2 conversations run on the mock domain."""

import json
import random

import litellm
import pytest
import run_matrix
from litellm import ModelResponse

AGENT, USER = "test/agent", "test/user"
AGENT_TEXT = "Agent reply."


def settings_toml(**over) -> str:
    s = {
        "budget_factor": 1.5,
        "max_attempts": 2,
        "backoff_seconds": [0, 0],
        "idle_pause_seconds": 0,
        "cash_stop": 45.0,
        "cell_budget": None,
    }
    s.update(over)
    return f"""
budget_factor = {s["budget_factor"]}
max_attempts = {s["max_attempts"]}
backoff_seconds = {s["backoff_seconds"]}
idle_pause_seconds = {s["idle_pause_seconds"]}
[accounts.cash]
already_spent = 1.0
stop_at = {s["cash_stop"]}
[accounts.openrouter]
stop_at = 1.0
meter_factor = 1.25
[accounts.vertex]
stop_at = 1.0
[providers.openai]
rpm = 1000
[prices]
"{AGENT}" = [1.0, 1.0]
"{USER}" = [1.0, 1.0]
"""


def config_toml(trials=2, cell_budget=None) -> str:
    budget = f"cell_budget = {cell_budget}\n" if cell_budget is not None else ""
    return f"""
name = "t"
agent_llm = "{AGENT}"
user_llm = "{USER}"
trials = {trials}
agent_cost_per_conv = 0.001
user_cost_per_conv = 0.001
{budget}
[[cells]]
condition = "mock"
domain = "mock"
split = "base"
task_ids = ["create_task_1", "update_task_1"]
"""


def response(model, content):
    return ModelResponse(
        model=model,
        choices=[
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        usage={"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
    )


class FakeLLM:
    """The agent always answers AGENT_TEXT; the user says hello, then stops
    once the agent has spoken. `agent`/`user` may be overridden per test."""

    def __init__(self, agent=None, user=None):
        self.agent, self.user = agent, user
        self.calls = []

    def __call__(self, *args, model, messages, **kwargs):
        self.calls.append(model)
        if model == AGENT:
            if self.agent:
                return self.agent(model)
            return response(model, AGENT_TEXT)
        if self.user:
            return self.user(model)
        spoke = any(AGENT_TEXT in str(m.get("content")) for m in messages)
        return response(model, "###STOP###" if spoke else "Hello, I need help.")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(run_matrix, "RUN", run_matrix.RunState())
    run_matrix.STOP.clear()
    fake = FakeLLM()
    monkeypatch.setattr(run_matrix, "_original_completion", fake)
    pings = []
    monkeypatch.setattr(
        run_matrix, "health_send", lambda sig="", body="": pings.append((sig, body))
    )

    class Env:
        out = tmp_path / "out"
        llm = fake
        pings_sent = pings

        def run(self, *extra, settings=None, config=None):
            monkeypatch.setattr(run_matrix, "RUN", run_matrix.RunState())
            run_matrix.STOP.clear()
            (tmp_path / "runner.toml").write_text(settings or settings_toml())
            (tmp_path / "t.toml").write_text(config or config_toml())
            run_matrix.main(
                [
                    "run",
                    str(tmp_path / "t.toml"),
                    "--out",
                    str(self.out),
                    "--settings",
                    str(tmp_path / "runner.toml"),
                    *extra,
                ]
            )
            return run_matrix.RUN

        def attempts(self):
            path = self.out / "t_mock" / "attempts.jsonl"
            return [json.loads(x) for x in path.read_text().splitlines()]

        def sims(self):
            return sorted(p.name for p in (self.out / "t_mock" / "sims").glob("*.json"))

    return Env()


def test_run_stop_and_resume(env):
    env.run("--max-conversations", "3")
    assert len(env.sims()) == 3
    state = env.run()
    assert env.sims() == [
        "create_task_1__t0.json",
        "create_task_1__t1.json",
        "update_task_1__t0.json",
        "update_task_1__t1.json",
    ]
    # Each conversation ran exactly once, in trial order.
    attempts = env.attempts()
    assert [a["outcome"] for a in attempts] == ["done"] * 4
    assert [a["trial"] for a in attempts] == [0, 0, 1, 1]
    progress = (env.out / "progress.md").read_text(encoding="utf-8")
    assert "| t_mock | 4 / 4 |" in progress
    # Spend: 1 agent + 2 user calls per conversation at $0.0011 each.
    assert attempts[0]["cost"]["cash"] == pytest.approx(0.0033)
    assert state.account_total("cash") == pytest.approx(1.0 + 4 * 0.0033)
    sim = json.loads((env.out / "t_mock" / "sims" / env.sims()[0]).read_text())
    assert sim["termination_reason"] == "user_stop"


def test_seeds_match_tau2(env):
    env.run("--max-conversations", "0")
    cell = json.loads((env.out / "t_mock" / "cell.json").read_text())
    random.seed(300)  # tau2's DEFAULT_SEED, as in runner.batch.prepare_batch
    assert cell["seeds"] == [random.randint(0, 1000000) for _ in range(2)]


def test_changed_settings_refused(env):
    env.run("--max-conversations", "1")
    with pytest.raises(SystemExit, match="settings changed"):
        env.run(config=config_toml(trials=3))


def test_rate_limit_backs_off_then_succeeds(env):
    left = {"n": 2}

    def flaky(model):
        if left["n"]:
            left["n"] -= 1
            raise litellm.RateLimitError("busy", llm_provider="openai", model=model)
        return response(model, AGENT_TEXT)

    env.llm.agent = flaky
    env.run(config=config_toml(trials=1))
    attempts = env.attempts()
    assert [a["outcome"] for a in attempts] == ["done", "done"]
    assert attempts[0]["requests"]["openai"] == 5  # 3 calls + 2 retries


def test_provider_errors_rerun_then_missing(env):
    def down(model):
        raise litellm.ServiceUnavailableError(
            "down", llm_provider="openai", model=model
        )

    env.llm.agent = down
    state = env.run(config=config_toml(trials=1))
    outcomes = [a["outcome"] for a in env.attempts()]
    assert outcomes == ["provider_error"] * 4  # 2 tasks x max_attempts 2
    assert env.sims() == []
    assert {u.status for u in state.units["t_mock"].values()} == {"missing"}
    assert state.lane_status["t"] == "complete"


def test_empty_agent_reply_is_a_model_failure(env):
    env.llm.agent = lambda model: response(model, "")
    state = env.run(config=config_toml(trials=1))
    assert [a["outcome"] for a in env.attempts()] == ["model_failure"] * 2
    sim = json.loads((env.out / "t_mock" / "sims" / env.sims()[0]).read_text())
    assert sim["termination_reason"] == "infrastructure_error"
    assert sim["info"]["runner_outcome"] == "model_failure"
    assert sim["info"]["failed_model"] == AGENT
    assert {u.status for u in state.units["t_mock"].values()} == {"model_failure"}


def test_empty_user_reply_is_rerun(env):
    env.llm.user = lambda model: response(model, "")
    state = env.run(config=config_toml(trials=1))
    assert {a["outcome"] for a in env.attempts()} == {"user_failure"}
    assert {u.status for u in state.units["t_mock"].values()} == {"missing"}


def test_cell_budget_stops_the_cell(env):
    # Projected $0.002 per conversation; actual $0.0033. Budget 0.005 allows
    # the first conversation, then 0.0033 + 0.002 > 0.005 blocks the second.
    state = env.run(config=config_toml(trials=1, cell_budget=0.005))
    assert len(env.sims()) == 1
    assert "cell budget" in state.cells[0].stopped
    progress = (env.out / "progress.md").read_text(encoding="utf-8")
    assert "stopped: cell budget" in progress


def test_account_cap_stops_everything(env):
    state = env.run(settings=settings_toml(cash_stop=1.001))
    assert env.sims() == []
    assert "cash account cap" in state.cells[0].stopped


def test_fatal_error_stops_the_model(env):
    def no_key(model):
        raise litellm.AuthenticationError("bad key", llm_provider="openai", model=model)

    env.llm.agent = no_key
    state = env.run(config=config_toml(trials=1))
    assert len(env.attempts()) == 1
    assert state.lane_status["t"].startswith("stopped: AuthenticationError")


def test_insufficient_quota_is_fatal_without_backoff(env):
    def broke(model):
        raise litellm.RateLimitError(
            "You exceeded your current quota (insufficient_quota)",
            llm_provider="openai",
            model=model,
        )

    env.llm.agent = broke
    state = env.run(config=config_toml(trials=1))
    assert env.attempts()[0]["requests"]["openai"] == 2  # 1 user + 1 agent, no retry
    assert state.lane_status["t"].startswith("stopped")


def test_limiter_per_minute_and_per_day():
    now = {"t": 1000.0}
    slept = []

    def sleep(s):
        slept.append(s)
        now["t"] += s

    lim = run_matrix.Limiter("x", rpm=2, rpd=3, clock=lambda: now["t"], sleep=sleep)
    lim.acquire()
    lim.acquire()
    lim.acquire()  # third in the same minute waits ~60 s
    assert now["t"] == pytest.approx(1060.0)
    lim.acquire()  # fourth in 24 h waits for the first to leave the window
    assert now["t"] == pytest.approx(1000.0 + 86_400)
    lim.cool_down(100)
    t0 = now["t"]
    lim.acquire()
    assert now["t"] >= t0 + 100


def test_provider_and_account_mapping():
    pm, am = run_matrix.provider_of, run_matrix.account_of
    assert pm("openrouter/qwen/qwen3.8-27b:free") == "openrouter_free"
    assert am("openrouter/qwen/qwen3.8-27b:free") is None
    assert am("openrouter/deepseek/deepseek-v4-flash") == "openrouter"
    assert am("vertex_ai/gemini-3.1-pro-preview") == "vertex"
    assert am("gpt-5.4-mini") == "cash"


def test_main_configs_match_the_plan():
    """configs/main/*.toml reproduce the plan's 2,880 conversations."""
    settings = run_matrix.load_settings()
    run_matrix.RUN.configure(
        settings, run_matrix.DEFAULT_OUT, run_matrix.DEFAULT_PROGRESS
    )
    paths = sorted((run_matrix.REPO / "configs" / "main").glob("*.toml"))
    cells = run_matrix.load_cells(paths, settings["budget_factor"])
    assert len(cells) == 15
    assert sum(len(c.tasks) * c.trials for c in cells) == 2880
    assert {c.user_llm for c in cells} == {"gpt-5.4-mini"}
    assert not {c.agent_llm for c in cells} & {c.user_llm for c in cells}


def test_stop_file_stops_after_the_current_conversation(env):
    def agent_then_stop(model):
        (env.out / "STOP").touch()
        return response(model, AGENT_TEXT)

    env.llm.agent = agent_then_stop
    state = env.run(config=config_toml(trials=1))
    assert len(env.sims()) == 1  # the conversation in progress finished
    assert state.lane_status["t"] == "stopped (STOP requested)"


def fails(env):
    return [body for sig, body in env.pings_sent if sig == "fail"]


def test_health_heartbeat_and_finished_once(env):
    env.run()
    assert env.pings_sent[0][0] == ""  # heartbeat as soon as the run starts
    assert len(fails(env)) == 1 and "FINISHED" in fails(env)[0]
    env.run()  # a restart with nothing left does not repeat the email
    assert len(fails(env)) == 1


def test_health_alert_on_fatal_error(env):
    def no_key(model):
        raise litellm.AuthenticationError("bad key", llm_provider="openai", model=model)

    env.llm.agent = no_key
    env.run(config=config_toml(trials=1))
    assert any("model t stopped: AuthenticationError" in b for b in fails(env))
    assert not any("FINISHED" in b for b in fails(env))
    assert any(
        sig == "log" and body.startswith("runner exited") and "bad key" in body
        for sig, body in env.pings_sent
    )


def test_health_alert_on_budget_stop(env):
    env.run(config=config_toml(trials=1, cell_budget=0.005))
    assert any("t_mock stopped: cell budget" in b for b in fails(env))


def test_health_stall_alert(env, monkeypatch):
    env.run("--max-conversations", "0")
    state = run_matrix.RUN
    state.last_activity = run_matrix.time.time() - 4 * 3600
    done = run_matrix.threading.Event()
    done.set()  # one pass of the loop only
    run_matrix.heartbeat_loop(done)
    assert any("no LLM activity for 4.0 hours" in b for b in fails(env))
    # A thread waiting on a request limit is not a stall.
    env.pings_sent.clear()
    state.alerts_sent.clear()
    state.waiting = 1
    run_matrix.heartbeat_loop(done)
    assert fails(env) == [] and env.pings_sent[0][0] == ""
