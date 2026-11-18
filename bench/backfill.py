#!/usr/bin/env python3
"""Backfill Harbor cost/token fields for jobs run before the adapter fix.

Usage: bench/.venv/bin/python bench/backfill.py JOBS_DIR [JOBS_DIR ...]

For every trial result.json under JOBS_DIR, convert the collected wisp
transcript (agent/wisp-sessions/*/wisp.jsonl) into ATIF
(agent/trajectory.json), then write the same token and cost totals into
result.json that populate_context_post_run() now writes on a fresh run.
Finally recompute the job-level result.json token and cost totals.

Safe to re-run: every output is derived from the wisp transcript.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harbor.utils.trajectory_utils import compute_model_usage, format_trajectory_json

from wisp_harbor import Wisp, find_transcript


class _Converter(Wisp):
    """Bypass BaseInstalledAgent.__init__; only the fields it reads."""

    def __init__(self, model_name: str | None) -> None:
        self.model_name = model_name
        self.logger = type(
            "Logger",
            (),
            {
                "debug": staticmethod(lambda *a, **k: None),
                "exception": staticmethod(lambda *a, **k: None),
            },
        )()


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _model_name(result: dict) -> str | None:
    info = result.get("agent_info") or {}
    model = info.get("model_info") or {}
    return model.get("name") or model.get("model_name")


def backfill_trial(trial_dir: Path) -> bool:
    result_path = trial_dir / "result.json"
    result = _read(result_path)
    if result is None or "task_name" not in result:
        return False
    transcript = find_transcript(trial_dir / "agent")
    if transcript is None:
        return False

    converter = _Converter(_model_name(result))
    trajectory = converter.convert_trajectory(trial_dir / "agent")
    if trajectory is None:
        return False

    (trial_dir / "agent" / "trajectory.json").write_text(
        format_trajectory_json(trajectory.to_json_dict()), encoding="utf-8"
    )

    metrics = trajectory.final_metrics
    if metrics is None:
        return False
    usage = compute_model_usage(trajectory) or None
    agent_result = result.get("agent_result") or {}
    agent_result.update(
        {
            "n_input_tokens": metrics.total_prompt_tokens or 0,
            "n_cache_tokens": metrics.total_cached_tokens or 0,
            "n_output_tokens": metrics.total_completion_tokens or 0,
            "cost_usd": metrics.total_cost_usd,
            "model_usage": (
                {name: entry.model_dump() for name, entry in usage.items()}
                if usage
                else None
            ),
            "metadata": None,
        }
    )
    result["agent_result"] = agent_result
    result_path.write_text(
        json.dumps(result, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return True


def backfill_job(job_dir: Path) -> None:
    trials = [
        path
        for path in sorted(job_dir.rglob("result.json"))
        if "task_name" in (_read(path) or {})
    ]
    changed = sum(backfill_trial(trial.parent) for trial in trials)

    job_path = job_dir / "result.json"
    if "stats" not in (_read(job_path) or {}):
        job_path = next(
            (
                path
                for path in sorted(job_dir.rglob("result.json"))
                if "stats" in (_read(path) or {})
            ),
            job_path,
        )
    job = _read(job_path)
    if job is None or "stats" not in job:
        return
    job_dir = job_path.parent
    inputs = caches = outputs = 0
    cost = 0.0
    priced = False
    for trial in trials:
        agent = (_read(trial) or {}).get("agent_result") or {}
        inputs += int(agent.get("n_input_tokens") or 0)
        caches += int(agent.get("n_cache_tokens") or 0)
        outputs += int(agent.get("n_output_tokens") or 0)
        if agent.get("cost_usd") is not None:
            cost += float(agent["cost_usd"])
            priced = True
    job["stats"]["n_input_tokens"] = inputs
    job["stats"]["n_cache_tokens"] = caches
    job["stats"]["n_output_tokens"] = outputs
    job["stats"]["cost_usd"] = cost if priced else None
    job_path.write_text(
        json.dumps(job, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{job_dir}: {changed}/{len(trials)} trials backfilled")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for arg in sys.argv[1:]:
        backfill_job(Path(arg))
