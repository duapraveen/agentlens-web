"""Side-by-side judge version comparison with the regression gate (AC-4.3).

Constitution IV.3: a candidate judge whose golden-set precision or recall
drops more than 2 points (0.02, fractions 0-1) vs the baseline blocks merge.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from agentlens.evals.metrics import JudgeQuality, compute_judge_quality
from agentlens.feedback.calibration import AgreementStats, compute_agreement

_REGRESSION_THRESHOLD = 0.02


@dataclass(frozen=True)
class JudgeComparison:
    """Two judge configurations on the golden set; deltas are candidate - baseline."""

    baseline: JudgeQuality
    candidate: JudgeQuality
    baseline_agreement: AgreementStats
    candidate_agreement: AgreementStats
    precision_delta: float
    recall_delta: float
    regression_flagged: bool


def compare_judge_versions(
    session: Session,
    judge_model: str,
    baseline_version: str,
    candidate_version: str,
) -> JudgeComparison:
    """Compare candidate vs baseline prompt version for one judge model."""
    baseline = compute_judge_quality(session, judge_model, baseline_version)
    candidate = compute_judge_quality(session, judge_model, candidate_version)
    precision_delta = candidate.precision - baseline.precision
    recall_delta = candidate.recall - baseline.recall
    return JudgeComparison(
        baseline=baseline,
        candidate=candidate,
        baseline_agreement=compute_agreement(session, judge_model, baseline_version),
        candidate_agreement=compute_agreement(session, judge_model, candidate_version),
        precision_delta=precision_delta,
        recall_delta=recall_delta,
        regression_flagged=(
            precision_delta < -_REGRESSION_THRESHOLD or recall_delta < -_REGRESSION_THRESHOLD
        ),
    )
