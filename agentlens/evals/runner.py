"""Idempotent per-call eval runner: deterministic checks + one call-level judge call.

Re-running never duplicates records (AC-1.4): eval records are unique per
(call, dimension, judge_model, prompt_version); check results per (call, check).
Every eval record carries judge model, prompt version, rubric version, and an
input hash (AC-1.3). Deterministic checks persist even when the judge call
fails, so a retry only repeats the judge (AC-1.2, constitution I.3).
"""

import hashlib
import json
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.corpus.scenarios import Dimension
from agentlens.evals.checks import run_checks
from agentlens.llm.gateway import complete_json
from agentlens.models import Call, DeterministicCheckResult, EvalRecord
from agentlens.prompts.judge import (
    PROMPT_NAME,
    PROMPT_VERSION,
    RUBRIC_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class DimensionJudgment(BaseModel):
    """Judge verdict for one dimension. Score is 0-100."""

    score: int = Field(ge=0, le=100)
    severity: Literal["P0", "P1", "P2", "none"]
    failure_description: str = ""
    reasoning: str
    pipeline_stage: Literal["transcription", "retrieval", "reasoning", "orchestration", "none"] = (
        "none"
    )


class JudgeOutput(BaseModel):
    """One call-level judgment covering all four rubric dimensions (OQ-3)."""

    task_completion: DimensionJudgment
    factual_accuracy: DimensionJudgment
    safety_compliance: DimensionJudgment
    communication_quality: DimensionJudgment

    def for_dimension(self, dimension: Dimension) -> DimensionJudgment:
        judgment: DimensionJudgment = getattr(self, dimension.value)
        return judgment


def transcript_hash(transcript: list[dict[str, Any]]) -> str:
    """Stable 16-hex-char content hash of a transcript (AC-1.3 input hash)."""
    canonical = json.dumps(transcript, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _persist_checks(session: Session, call: Call) -> None:
    existing = {
        c.check_name
        for c in session.query(DeterministicCheckResult).filter_by(call_id=call.id).all()
    }
    for outcome in run_checks(call.transcript):
        if outcome.check_name not in existing:
            session.add(
                DeterministicCheckResult(
                    call_id=call.id,
                    check_name=outcome.check_name,
                    triggered=outcome.triggered,
                    detail=outcome.detail,
                )
            )
    session.commit()


def evaluate_call(
    session: Session,
    call: Call,
    *,
    model: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> Literal["created", "skipped", "failed"]:
    """Evaluate one call: persist deterministic checks, then judge all four dimensions.

    Returns "skipped" when records already exist for this judge configuration,
    "failed" when the judge gateway call failed (checks are still persisted,
    and a later retry will re-attempt the judge), else "created".
    """
    judge_model = model or get_settings().judge_model
    existing = (
        session.query(EvalRecord)
        .filter_by(call_id=call.id, judge_model=judge_model, prompt_version=PROMPT_VERSION)
        .count()
    )
    if existing:
        return "skipped"

    _persist_checks(session, call)

    result = complete_json(
        session,
        purpose="judge",
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        system=SYSTEM_PROMPT,
        user_content=build_user_prompt(call.transcript),
        response_model=JudgeOutput,
        model=judge_model,
        client=client,
    )
    if not result.success or result.parsed is None:
        return "failed"

    input_hash = transcript_hash(call.transcript)
    for dimension in Dimension:
        judgment = result.parsed.for_dimension(dimension)
        session.add(
            EvalRecord(
                call_id=call.id,
                dimension=dimension.value,
                score=judgment.score,
                severity=judgment.severity,
                passed=judgment.severity == "none",
                failure_description=judgment.failure_description or None,
                judge_reasoning=judgment.reasoning,
                pipeline_stage=None
                if judgment.pipeline_stage == "none"
                else judgment.pipeline_stage,
                judge_model=judge_model,
                prompt_version=PROMPT_VERSION,
                rubric_version=RUBRIC_VERSION,
                input_hash=input_hash,
            )
        )
    session.commit()
    return "created"
