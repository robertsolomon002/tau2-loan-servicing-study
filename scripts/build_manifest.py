"""Write results/MANIFEST.json: what produced the results (Stage 6.2).

Reads each main cell's cell.json and attempts.jsonl from results/raw/main (the
local copy of the VM results, git-ignored) and pins both repos' commits, every
model id, the seeds, and the run dates. Run it again only if the raw results
change.

Usage:
    uv run python scripts/build_manifest.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "main"
OUT = ROOT / "results" / "MANIFEST.json"

# Plan Amendment 2: Qwen's free model was withdrawn mid-run, so its cells were
# analyzed with 2 trials (analysis/load.py STOPPED_TRIALS).
TRIALS_ANALYZED = {"qwen": 2}


def lock_version(package: str) -> str:
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    match = re.search(rf'name = "{package}"\nversion = "([^"]+)"', lock)
    return match.group(1) if match else "unknown"


def cell_entry(cell_dir: Path) -> dict:
    cell = json.loads((cell_dir / "cell.json").read_text(encoding="utf-8"))
    attempts = [
        json.loads(line)
        for line in (cell_dir / "attempts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    finished = [a for a in attempts if a["outcome"] in ("done", "model_failure")]
    lane = cell["cell"].rsplit("_", 1)[0]
    return {
        "cell": cell["cell"],
        "condition": cell["condition"],
        "domain": cell["domain"],
        "split": cell["split"],
        "agent_llm": cell["agent_llm"],
        "user_llm": cell["user_llm"],
        "trials_planned": cell["trials"],
        "trials_analyzed": TRIALS_ANALYZED.get(lane, cell["trials"]),
        "seeds": cell["seeds"],
        "tasks": len(cell["task_ids"]),
        "conversations_finished": len(finished),
        "first_attempt_utc": min(a["time"] for a in attempts),
        "last_attempt_utc": max(a["time"] for a in attempts),
        "study_commit": cell["study_commit"],
        "fork_commit": cell["fork_commit"],
    }


def main() -> None:
    if not RAW.is_dir():
        sys.exit(f"{RAW} not found: copy the raw results first (docs/RUNNER.md).")
    cells = [cell_entry(d) for d in sorted(RAW.iterdir()) if (d / "cell.json").exists()]
    study = {c["study_commit"] for c in cells}
    fork = {c["fork_commit"] for c in cells}
    if len(study) != 1 or len(fork) != 1:
        sys.exit(f"Cells ran on different commits: study {study}, fork {fork}")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pinned = pyproject["tool"]["uv"]["sources"]["tau2"]
    manifest = {
        "study": "tau2-loan-servicing-study (English vs Quebec French policy compliance)",
        "runs": {
            "study_repo": "https://github.com/robertsolomon002/tau2-loan-servicing-study",
            "study_commit": study.pop(),
            "fork_repo": pinned["git"],
            "fork_commit": fork.pop(),
            "conversations_planned": 2592,
            "conversations_finished": sum(c["conversations_finished"] for c in cells),
            "first_attempt_utc": min(c["first_attempt_utc"] for c in cells),
            "last_attempt_utc": max(c["last_attempt_utc"] for c in cells),
            "runner": "scripts/run_matrix.py with configs/main/*.toml and configs/runner.toml",
        },
        "fork_pinned_now": {
            "commit": pinned["rev"],
            "note": (
                "pyproject.toml now pins the fork one commit after the runs, "
                "which rewords the French user text of task ls_041 (docs/LOG.md, "
                "Stage 5.2). To rerun exactly what was measured, use fork_commit "
                "under runs."
            ),
        },
        "tau2_settings": {
            "agent": "llm_agent (tau2 default), temperature 0",
            "user": "user_simulator, temperature 0",
            "max_steps": 200,
            "max_errors": 10,
            "seed": 300,
        },
        "models": {
            "agents": sorted({c["agent_llm"] for c in cells}),
            "user_simulator": sorted({c["user_llm"] for c in cells}),
            "failure_labellers": [
                "Claude Code (Claude Opus 5.5), main session and a blind subagent",
                "gpt-6.1-sol (scripts/label_failures_ai.py)",
            ],
            "notes": [
                (
                    "openrouter/qwen/qwen3.8-27b:free was withdrawn by OpenRouter "
                    "on 2026-10-05; the same weights are now the paid slug "
                    "openrouter/qwen/qwen3.8-27b (plan Amendment 2)."
                ),
                (
                    "vertex_ai/gemini-3.1-pro-preview is a preview model and may "
                    "change or be withdrawn."
                ),
            ],
        },
        "packages": {
            p: lock_version(p) for p in ("tau2", "litellm", "lingua-language-detector")
        },
        "trajectories": "https://huggingface.co/datasets/robsol/tau2-loan-servicing-trajectories",
        "cells": cells,
    }
    OUT.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(cells)} cells -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
