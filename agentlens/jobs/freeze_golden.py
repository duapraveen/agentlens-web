"""Batch job: freeze a stratified golden set to data/golden/ (AC-7.4, append-only).

Usage: python -m agentlens.jobs.freeze_golden [--count 50]
"""

import argparse
import json
import time
from collections import defaultdict
from collections.abc import Sequence

from agentlens.config import get_settings
from agentlens.db import open_session
from agentlens.jobs._logging import configure_job_logging
from agentlens.models import Call, JobRun, utcnow


def select_golden(calls: Sequence[Call], count: int) -> list[Call]:
    """Stratified round-robin over (scenario, failure_mode-or-clean) groups.

    Deterministic: groups sorted by key, calls sorted by id within each group.
    Returns min(count, len(calls)) calls.
    """
    groups: dict[str, list[Call]] = defaultdict(list)
    for call in calls:
        mode = call.ground_truth.failure_mode if call.ground_truth else "clean"
        groups[f"{call.scenario}:{mode}"].append(call)
    pools = [sorted(groups[key], key=lambda c: c.id) for key in sorted(groups)]
    selected: list[Call] = []
    i = 0
    while len(selected) < count and any(pools):
        pool = pools[i % len(pools)]
        if pool:
            selected.append(pool.pop(0))
        i += 1
    return selected


def _export_record(call: Call) -> dict[str, object]:
    label = call.ground_truth
    return {
        "call": {
            "id": call.id,
            "scenario": call.scenario,
            "transcript": call.transcript,
            "batch_id": call.batch_id,
            "agent_prompt_version": call.agent_prompt_version,
        },
        "ground_truth": None
        if label is None
        else {
            "failure_mode": label.failure_mode,
            "pipeline_stage": label.pipeline_stage,
            "severity": label.severity,
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Run the golden freeze job; returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)

    settings = get_settings()
    log = configure_job_logging(settings.jobs_log_path)
    settings.golden_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    with open_session() as session:
        run = JobRun(job_name="freeze_golden", status="running")
        session.add(run)
        session.commit()

        candidates = session.query(Call).filter(~Call.is_golden).all()
        selected = select_golden(candidates, args.count)
        frozen = 0
        for call in selected:
            path = settings.golden_dir / f"{call.id}.json"
            if path.exists():  # append-only: never overwrite an existing entry
                log.warning("golden_file_exists_skipping", call_id=call.id)
                continue
            path.write_text(json.dumps(_export_record(call), indent=2))
            call.is_golden = True
            frozen += 1
            log.info("golden_frozen", call_id=call.id, scenario=call.scenario)

        run.status = "completed"
        run.finished_at = utcnow()
        run.summary = {
            "requested": args.count,
            "frozen": frozen,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        session.commit()
        log.info("job_finished", job="freeze_golden", **run.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
