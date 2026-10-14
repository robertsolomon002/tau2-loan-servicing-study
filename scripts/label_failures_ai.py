"""Blind AI labellers for the failure-review sample (Stage 5.2, Amendment).

Rob chose not to label the 40-conversation sample himself (docs/LOG.md,
2026-10-13). Two independent AI labellers label the same 40 blind instead:
a fresh Claude Code subagent and an OpenAI model. Both get exactly what Rob's
labeller (`scripts/label_failures.py`) would have shown: the digest with the
model name removed, the taxonomy, and the rule ids, plus the English policy.
Neither sees Claude's labels.

Usage (from the study repo):
    uv run python scripts/label_failures_ai.py prepare --out DIR
        # INSTRUCTIONS.md + item_01.md .. item_40.md for the subagent
    uv run python scripts/label_failures_ai.py gpt
        # OpenAI labeller -> data/failure_labels_gpt.json (resumes; $3 stop)
    uv run python scripts/label_failures_ai.py import-subagent FILE
        # {"item_01": {...}, ...} -> data/failure_labels_subagent.json
    uv run python scripts/label_failures_ai.py agreement
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.failures import (
    CAUSES,
    DIGESTS,
    GPT_LABELS,
    KAPPA_BAR,
    LABELS,
    REPO,
    SUBAGENT_LABELS,
    cohen_kappa,
    failed,
    fleiss_kappa,
    load_labels,
    review_sample,
    save_labels,
    validate,
)

POLICY = REPO.parent / "tau2-bench" / "data" / "tau2" / "domains" / "loan_servicing"
DOMAIN_SPEC = REPO / "docs" / "DOMAIN_SPEC.md"

# Checked 2026-10-13 at developers.openai.com/api/docs/pricing (standard tier).
GPT_MODEL = "gpt-6.1-sol"
PRICE_IN, PRICE_CACHED, PRICE_OUT = 2.00, 0.10, 10.00  # $ per million tokens
COST_CAP = 3.00

JUDGED = [c for c in CAUSES if c != "model_output"]

TASK = f"""You are labelling failed customer-service conversations from a benchmark.
An AI agent served customers of a fictional lender (Boreal Finance) under the
policy below. Each conversation failed: the final database state (and, for some
tasks, a reference number the agent had to read out) did not match the
expected outcome. The customer was played by another AI (the "user simulator")
following the instructions shown in each conversation's "User scenario".

For each conversation, give:
1. cause: the PRIMARY cause, the first thing that made the conversation fail.
   One of:
{chr(10).join(f"   - {c}: {CAUSES[c]}" for c in JUDGED)}
2. rule: the id of the policy rule involved (from the rule table below, e.g.
   F2 or T1), or "" if no rule is involved. Required for rule_misapplied.
3. turn: the message index [N] in the transcript where it went wrong.
4. explanation: one sentence.
5. sim_major: true if the customer simulator made a major error, i.e. did
   something its instructions forbid and that changed the outcome; else false.

Judge the agent's behaviour against the policy and the task; the agent model
is hidden on purpose. Transcripts may be in English or Quebec French.
"""


def instructions() -> str:
    spec = DOMAIN_SPEC.read_text(encoding="utf-8")
    rules = re.search(r"^## 4\..*?(?=^## 5\.)", spec, re.DOTALL | re.MULTILINE).group(0)
    policy = (POLICY / "policy.md").read_text(encoding="utf-8")
    return (
        f"{TASK}\n# Rule table (ids to use)\n\n{rules}\n"
        f"# Agent policy (English version)\n\n{policy}\n"
    )


def blind(key: str) -> str:
    """The digest as Rob's labeller shows it: no key line, no model name."""
    text = (DIGESTS / f"{key}.md").read_text(encoding="utf-8")
    return re.sub(r"^Model \S+, ", "", text.split("\n", 1)[1], count=1)


def items() -> dict[str, str]:
    return {f"item_{i:02d}": k for i, k in enumerate(review_sample(failed()), 1)}


def prepare(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "INSTRUCTIONS.md").write_text(instructions(), encoding="utf-8")
    for item, key in items().items():
        (out / f"{item}.md").write_text(blind(key), encoding="utf-8")
    print(f"{len(items())} items and INSTRUCTIONS.md in {out}")


SCHEMA = {
    "type": "object",
    "properties": {
        "cause": {"type": "string", "enum": JUDGED},
        "rule": {"type": "string"},
        "turn": {"type": "integer"},
        "explanation": {"type": "string"},
        "sim_major": {"type": "boolean"},
    },
    "required": ["cause", "rule", "turn", "explanation", "sim_major"],
    "additionalProperties": False,
}


def run_gpt() -> None:
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(REPO / ".env")
    client = OpenAI()
    system = instructions()
    labels = load_labels(GPT_LABELS)
    meta_path = GPT_LABELS.with_suffix(".cost.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"usd": 0.0}
    for item, key in items().items():
        if key in labels:
            continue
        if meta["usd"] >= COST_CAP:
            sys.exit(f"Cost cap ${COST_CAP} reached; stopping.")
        resp = client.responses.create(
            model=GPT_MODEL,
            instructions=system,
            input=f"Label this conversation ({item}).\n\n{blind(key)}",
            text={
                "format": {
                    "type": "json_schema",
                    "name": "failure_label",
                    "schema": SCHEMA,
                    "strict": True,
                }
            },
        )
        u = resp.usage
        cached = u.input_tokens_details.cached_tokens or 0
        usd = (
            (u.input_tokens - cached) * PRICE_IN
            + cached * PRICE_CACHED
            + u.output_tokens * PRICE_OUT
        ) / 1e6
        meta["usd"] = round(meta["usd"] + usd, 6)
        lab = json.loads(resp.output_text)
        lab["rule"] = lab["rule"].strip().upper()
        labels[key] = lab
        save_labels(labels, GPT_LABELS)
        meta_path.write_text(json.dumps(meta) + "\n")
        print(
            f"{item} {labels[key]['cause']:<22} ${usd:.4f} (total ${meta['usd']:.3f})"
        )
    print(f"Done: {len(labels)} labels, ${meta['usd']:.3f}")


def import_subagent(path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = items()
    labels = {}
    for item, lab in raw.items():
        lab["rule"] = (lab.get("rule") or "").strip().upper()
        labels[mapping[item]] = lab
    problems = validate(labels)
    if problems or len(labels) != len(mapping):
        sys.exit(f"{len(labels)} labels; problems: {problems}")
    save_labels(labels, SUBAGENT_LABELS)
    print(f"{len(labels)} labels -> {SUBAGENT_LABELS}")


def agreement() -> None:
    sample = review_sample(failed())
    raters = {
        "claude": load_labels(LABELS),
        "subagent": load_labels(SUBAGENT_LABELS),
        "gpt": load_labels(GPT_LABELS),
    }
    missing = {r: sum(k not in lab for k in sample) for r, lab in raters.items()}
    if any(missing.values()):
        sys.exit(f"Missing labels: {missing}")
    causes = {r: [lab[k]["cause"] for k in sample] for r, lab in raters.items()}
    print(f"Primary cause, {len(sample)} conversations")
    names = list(raters)
    pair = {}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            same = sum(x == y for x, y in zip(causes[a], causes[b]))
            pair[a, b] = cohen_kappa(causes[a], causes[b])
            print(f"  {a} vs {b}: {same}/{len(sample)} same, kappa {pair[a, b]:.2f}")
    print(
        f"  Fleiss' kappa (all three): {fleiss_kappa(list(zip(*causes.values()))):.2f}"
    )
    ok = pair["claude", "subagent"] >= KAPPA_BAR and pair["claude", "gpt"] >= KAPPA_BAR
    print(
        "Decision: "
        + (
            "report Claude's labels on all failures."
            if ok
            else "report the majority label on the 40."
        )
    )
    print("\nDisagreements:")
    for n, k in enumerate(sample, 1):
        row = [causes[r][n - 1] for r in names]
        if len(set(row)) > 1:
            print(
                f"  item_{n:02d} {k}: "
                + ", ".join(f"{r}={c}" for r, c in zip(names, row))
            )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare").add_argument("--out", type=Path, required=True)
    sub.add_parser("gpt")
    sub.add_parser("import-subagent").add_argument("file", type=Path)
    sub.add_parser("agreement")
    args = parser.parse_args()
    if args.cmd == "prepare":
        prepare(args.out)
    elif args.cmd == "gpt":
        run_gpt()
    elif args.cmd == "import-subagent":
        import_subagent(args.file)
    else:
        agreement()


if __name__ == "__main__":
    main()
