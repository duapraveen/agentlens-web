"""Judge-human agreement stats (AC-4.2), computed live from reviews.

Agreement is the share of reviews where the human confirmed the judge's
finding (verdict == "agree"), as a 0-1 fraction. No caching: recompute on
read so the numbers update as reviews are submitted.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from agentlens.models import EvalRecord, Review


@dataclass(frozen=True)
class AgreementStats:
    """Judge-human agreement, overall and per dimension (fractions 0-1)."""

    n_reviews: int
    n_agree: int
    agreement: float
    per_dimension: dict[str, float] = field(default_factory=dict)
    per_dimension_counts: dict[str, int] = field(default_factory=dict)


def compute_agreement(
    session: Session,
    judge_model: str | None = None,
    prompt_version: str | None = None,
) -> AgreementStats:
    """Agreement stats over all reviews, optionally for one judge configuration."""
    query = session.query(Review).join(Review.eval_record)
    if judge_model is not None:
        query = query.filter(EvalRecord.judge_model == judge_model)
    if prompt_version is not None:
        query = query.filter(EvalRecord.prompt_version == prompt_version)
    reviews = query.all()

    by_dimension: dict[str, list[bool]] = {}
    for review in reviews:
        by_dimension.setdefault(review.eval_record.dimension, []).append(review.verdict == "agree")
    n_agree = sum(v for votes in by_dimension.values() for v in votes)
    return AgreementStats(
        n_reviews=len(reviews),
        n_agree=n_agree,
        agreement=n_agree / len(reviews) if reviews else 0.0,
        per_dimension={dim: sum(votes) / len(votes) for dim, votes in by_dimension.items()},
        per_dimension_counts={dim: len(votes) for dim, votes in by_dimension.items()},
    )
