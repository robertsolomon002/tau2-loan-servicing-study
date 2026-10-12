"""Build the Hugging Face dataset folder from the main-run results (Stage 4.3).

Copies every cell of `results/raw/main/` (cell.json, attempts.jsonl and one
tau2 SimulationRun JSON per conversation under sims/) to `trajectories/`, adds
the runner log, the dataset card (`deploy/hf_dataset_card.md` as README.md),
and a flat `index.csv` with one row per finished conversation for the
dataset viewer.

The outcome per conversation comes from the runner's attempts.jsonl (plan
Section 7): `done`, or `model_failure` (empty model reply; tau2 labels it
infrastructure_error and stores no reward_info), which is scored 0.

Usage:
    python scripts/build_hf_dataset.py OUT_DIR [--results results/raw/main]
    hf upload <user>/tau2-loan-servicing-trajectories OUT_DIR . --repo-type dataset --private
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "deploy" / "hf_dataset_card.md"


def final_outcomes(cell: Path) -> dict[tuple[str, int], str]:
    outcomes = {}
    for line in (cell / "attempts.jsonl").read_text(encoding="utf-8").splitlines():
        attempt = json.loads(line)
        if attempt["outcome"] in ("done", "model_failure"):
            outcomes[(attempt["task_id"], attempt["trial"])] = attempt["outcome"]
    return outcomes


def build(results: Path, out: Path) -> list[dict]:
    if out.exists():
        shutil.rmtree(out)
    (out / "trajectories").mkdir(parents=True)
    rows = []
    for cell in sorted(p for p in results.iterdir() if p.is_dir()):
        meta = json.loads((cell / "cell.json").read_text(encoding="utf-8"))
        outcomes = final_outcomes(cell)
        shutil.copytree(cell, out / "trajectories" / cell.name)
        for path in sorted((cell / "sims").glob("*.json")):
            sim = json.loads(path.read_text(encoding="utf-8"))
            task_id, trial = path.stem.split("__t")
            rows.append(
                {
                    "cell": cell.name,
                    "model": cell.name.rsplit("_", 1)[0],
                    "condition": meta["condition"],
                    "domain": meta["domain"],
                    "agent_llm": meta["agent_llm"],
                    "user_llm": meta["user_llm"],
                    "task_id": task_id,
                    "task_number": int(task_id.split("_")[1]),
                    "user_language": task_id.split("_")[2],
                    "trial": int(trial),
                    "seed": sim["seed"],
                    "outcome": outcomes[(task_id, int(trial))],
                    "reward": sim["reward_info"]["reward"]
                    if sim["reward_info"]
                    else 0.0,
                    "termination_reason": sim["termination_reason"],
                    "num_messages": len(sim["messages"]),
                    "agent_cost": sim["agent_cost"],
                    "user_cost": sim["user_cost"],
                    "file": f"trajectories/{cell.name}/sims/{path.name}",
                }
            )
    with open(out / "index.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    shutil.copy(results / "runner.log", out / "runner.log")
    shutil.copy(CARD, out / "README.md")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--results", type=Path, default=ROOT / "results" / "raw" / "main"
    )
    args = parser.parse_args()
    rows = build(args.results, args.out)
    print(f"{len(rows)} conversations written to {args.out}")


if __name__ == "__main__":
    main()
