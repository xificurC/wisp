#!/usr/bin/env python3
"""Aggregate Harbor job results for the wisp bench.

Usage: python3 aggregate.py JOBS_DIR [JOBS_DIR ...] [--csv OUT]

JOBS_DIR is a harbor -o output directory. Each trial subdirectory holds a
result.json; the trial's agent/ subdirectory holds the collected wisp
session, whose wisp.usage carries the per-turn cost LiteLLM reported.

Output: one markdown row per (jobs dir, model) and a per-task detail
table. Pass = reward 1.0 (Terminal-Bench scorers are binary).
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path


def trial_records(jobs_dir: Path):
    for result in sorted(jobs_dir.rglob("result.json")):
        try:
            data = json.loads(result.read_text())
        except ValueError:
            continue
        if "task_name" not in data:  # job-level summary file, skip
            continue
        rec = {
            "jobs_dir": jobs_dir.name,
            "task": data.get("task_name", "?").split("/")[-1],
            "trial": data.get("trial_name", result.parent.name),
            "model": ((data.get("agent_info") or {}).get("model_info") or {}).get("name") or "?",
            "reward": None,
            "exception": bool(data.get("exception_info")),
            "input": 0,
            "cached": 0,
            "output": 0,
            "cost": 0.0,
            "seconds": None,
        }
        rewards = ((data.get("verifier_result") or {}).get("rewards") or {})
        if "reward" in rewards:
            rec["reward"] = float(rewards["reward"])
        agent = data.get("agent_result") or {}
        rec["input"] = int(agent.get("n_input_tokens") or 0)
        rec["cached"] = int(agent.get("n_cache_tokens") or 0)
        rec["output"] = int(agent.get("n_output_tokens") or 0)
        try:
            start = datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(data["finished_at"].replace("Z", "+00:00"))
            rec["seconds"] = (end - start).total_seconds()
        except (KeyError, ValueError, AttributeError):
            pass
        usage = result.parent / "agent" / "wisp-sessions" / "wisp" / "wisp.usage"
        if usage.is_file():
            for line in usage.read_text().splitlines():
                try:
                    chunk = json.loads(line.removeprefix("data: "))
                except ValueError:
                    continue
                rec["cost"] += float(chunk.get("cost") or 0)
        yield rec


def summarize(records):
    groups = {}
    for rec in records:
        key = (rec["jobs_dir"], rec["model"])
        groups.setdefault(key, []).append(rec)
    for (jobs_dir, model), recs in sorted(groups.items()):
        n = len(recs)
        passed = sum(1 for r in recs if r["reward"] is not None and r["reward"] >= 0.999)
        errored = sum(1 for r in recs if r["exception"] or r["reward"] is None)
        scored = [r["reward"] for r in recs if r["reward"] is not None]
        yield {
            "jobs_dir": jobs_dir,
            "model": model,
            "trials": n,
            "passed": passed,
            "errored": errored,
            "pass_rate": passed / n if n else 0.0,
            "mean_reward": sum(scored) / len(scored) if scored else 0.0,
            "input": sum(r["input"] for r in recs),
            "cached": sum(r["cached"] for r in recs),
            "output": sum(r["output"] for r in recs),
            "cost": sum(r["cost"] for r in recs),
            "seconds": sum(r["seconds"] or 0 for r in recs),
            "_recs": recs,
        }


def fmt_summary(rows):
    head = (
        "| jobs | model | trials | pass | err | pass rate | mean reward "
        "| in tok | cache tok | out tok | cost $ | agent s |"
    )
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines = [head, sep]
    for row in rows:
        lines.append(
            f"| {row['jobs_dir']} | {row['model']} | {row['trials']} "
            f"| {row['passed']} | {row['errored']} | {row['pass_rate']:.0%} "
            f"| {row['mean_reward']:.3f} | {row['input']:,} "
            f"| {row['cached']:,} | {row['output']:,} "
            f"| {row['cost']:.4f} | {row['seconds']:.0f} |"
        )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_dir", nargs="+", type=Path)
    ap.add_argument("--csv", type=Path, help="write per-trial rows to this CSV")
    args = ap.parse_args()

    records = []
    for jobs_dir in args.jobs_dir:
        if not jobs_dir.is_dir():
            sys.exit(f"not a directory: {jobs_dir}")
        records.extend(trial_records(jobs_dir))
    if not records:
        sys.exit("no trial result.json found")

    rows = list(summarize(records))
    print(fmt_summary(rows))
    print()
    for row in rows:
        print(f"## {row['jobs_dir']} / {row['model']}")
        for rec in sorted(row["_recs"], key=lambda r: r["task"]):
            reward = "-" if rec["reward"] is None else f"{rec['reward']:.2f}"
            secs = "-" if rec["seconds"] is None else f"{rec['seconds']:.0f}"
            print(
                f"  {rec['task']:<40} reward={reward:<5} "
                f"in={rec['input']:<7,} out={rec['output']:<6,} "
                f"${rec['cost']:.4f} {secs}s"
                + (" EXCEPTION" if rec["exception"] else "")
            )
        print()

    if args.csv:
        fields = [k for k in records[0] if k != "jobs_dir"] or list(records[0])
        with args.csv.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        print(f"csv: {args.csv}")


if __name__ == "__main__":
    main()
