"""Pydantic response/request models.

Every *_Out model sets from_attributes=True so FastAPI can validate the
dataclass or ORM instances returned by dashboard/data.py and the
business-logic modules directly (no hand-copied field mapping needed for
flat shapes); composed shapes (e.g. CallDetailOut) are still built field by
field in the router because their source objects nest differently than the
response shape.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StatusSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    last_eval_at: datetime | None
    n_calls: int
    n_golden: int


class ConversationRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    call_id: str
    scenario: str
    failed_dimensions: set[str]
    has_p0: bool
    avg_score: float
    est_cost_cents: float
    created_at: datetime
    is_golden: bool


class ClusterLabelOut(BaseModel):
    id: int
    label: str


class ConversationsListOut(BaseModel):
    rows: list[ConversationRowOut]
    total: int
    clusters: list[ClusterLabelOut]


class ClusterCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cluster_id: int
    label: str
    description: str
    routing: str
    severity: str
    size: int
    is_p0: bool


class ClustersListOut(BaseModel):
    cards: list[ClusterCardOut]
    n_failures: int
    last_clustered_at: datetime | None


class DimensionQualityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pass_rate: float
    delta: float | None


class FailureTrendPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: str
    overall_rate: float
    p0_rate: float
    p1_rate: float
    p2_rate: float
    total_records: int


class OverviewOut(BaseModel):
    quality: dict[str, DimensionQualityOut]
    severities: dict[str, int]
    precision: float | None
    recall: float | None
    agreement: float | None
    n_reviews: int
    top_clusters: list[ClusterCardOut]
    total_eval_cents: float
    avg_per_call_cents: float
    failure_trend: list[FailureTrendPointOut]


class EvalRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dimension: str
    score: int
    severity: str
    passed: bool
    failure_description: str | None
    judge_reasoning: str
    pipeline_stage: str | None
    judge_model: str
    prompt_version: str
    rubric_version: str
    input_hash: str


class CheckResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    check_name: str
    triggered: bool
    detail: str | None


class ClusterRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str


class GroundTruthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    failure_mode: str
    pipeline_stage: str
    severity: str


class CallDetailOut(BaseModel):
    call_id: str
    scenario: str
    transcript: list[dict[str, Any]]
    records: list[EvalRecordOut]
    checks: list[CheckResultOut]
    cluster: ClusterRefOut | None
    ground_truth: GroundTruthOut | None
    is_golden: bool


class AgreementStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    n_reviews: int
    n_agree: int
    agreement: float
    per_dimension: dict[str, float]
    per_dimension_counts: dict[str, int]


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    verdict: str
    note: str | None


class ScoredRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dimension: str
    score: int
    severity: str
    passed: bool
    failure_description: str | None
    judge_reasoning: str
    pipeline_stage: str | None
    judge_model: str
    prompt_version: str
    rubric_version: str
    input_hash: str
    review: ReviewOut | None


class CallReviewOut(BaseModel):
    call_id: str
    scenario: str
    transcript: list[dict[str, Any]]
    records: list[ScoredRecordOut]
    checks: list[CheckResultOut]


class ReviewQueueOut(BaseModel):
    stats: AgreementStatsOut
    pending_count: int
    current: CallReviewOut | None


class SubmitReviewIn(BaseModel):
    verdict: str
    note: str | None = None


class FixProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cluster_id: int
    fix_type: str
    rationale: str
    patch: str
    status: str


class RegressionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fix_proposal_id: int
    batch_id: str
    n_before: int
    n_after: int
    before_pass_rates: dict[str, float]
    after_pass_rates: dict[str, float]
    target_dimension: str
    regressed_dimensions: list[str]


class FixWorkbenchOut(BaseModel):
    cluster: ClusterCardOut
    fix: FixProposalOut | None
    regression: RegressionRunOut | None


class JobSummaryOut(BaseModel):
    finished_at: datetime | None
    summary: dict[str, Any]


class JobsStatusOut(BaseModel):
    corpus: JobSummaryOut
    evals: JobSummaryOut
    cluster: JobSummaryOut
    log_lines: list[str]


class EvalEstimateOut(BaseModel):
    n_calls: int
    estimate_cents: float


class GenerateCorpusIn(BaseModel):
    count: int
    failure_rate: float


class RunEvalsIn(BaseModel):
    scope: str
    model: str
