"""Before/after regression report and fix lifecycle (AC-5.3, AC-5.4).

Pass rates are 0-1 fractions per dimension. Closing a fix on a P0 cluster
requires a human actor — automation can never close a P0 (constitution V.4).
"""

from collections import Counter
from typing import Literal

from sqlalchemy.orm import Session

from agentlens.fixes.regression import affected_calls
from agentlens.models import Call, FixProposal, RegressionRun
from agentlens.prompts.judge import PROMPT_VERSION


def pass_rates(calls: list[Call], judge_model: str, prompt_version: str) -> dict[str, float]:
    """Per-dimension pass fraction over the calls' eval records for one judge config."""
    outcomes: dict[str, list[bool]] = {}
    for call in calls:
        for record in call.eval_records:
            if record.judge_model == judge_model and record.prompt_version == prompt_version:
                outcomes.setdefault(record.dimension, []).append(record.passed)
    return {dim: sum(passed) / len(passed) for dim, passed in outcomes.items()}


def _target_dimension(fix: FixProposal) -> str:
    dimensions = Counter(m.eval_record.dimension for m in fix.cluster.members if m.eval_record)
    return dimensions.most_common(1)[0][0]


def build_regression_run(
    session: Session, fix: FixProposal, regenerated: list[Call]
) -> RegressionRun:
    """Persist the before/after report for one fix and mark it validated.

    Before = the fix's cluster-affected calls; after = the regenerated batch.
    regressed_dimensions: non-target dimensions whose after-rate < before-rate.
    """
    judge_model = fix.cluster.members[0].eval_record.judge_model
    before = pass_rates(affected_calls(session, fix.cluster), judge_model, PROMPT_VERSION)
    after = pass_rates(regenerated, judge_model, PROMPT_VERSION)
    target = _target_dimension(fix)
    regressed = sorted(
        dim for dim in set(before) & set(after) if dim != target and after[dim] < before[dim]
    )
    run = RegressionRun(
        fix_proposal_id=fix.id,
        batch_id=f"fixbatch_{fix.id}",
        n_before=len(affected_calls(session, fix.cluster)),
        n_after=len(regenerated),
        before_pass_rates=before,
        after_pass_rates=after,
        target_dimension=target,
        regressed_dimensions=regressed,
    )
    session.add(run)
    fix.status = "validated"
    session.flush()
    return run


def close_fix(session: Session, fix: FixProposal, actor: Literal["human", "auto"]) -> None:
    """Close a fix. P0 clusters require a human actor (constitution V.4)."""
    if actor == "auto" and fix.cluster.dominant_severity == "P0":
        raise PermissionError(
            f"fix {fix.id} targets a P0 cluster; automation cannot close it (constitution V.4)"
        )
    fix.status = "closed"
    session.flush()
