"""Tests for transcript generation (gateway mocked; one real-API test marked llm)."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from agentlens.corpus.generator import TranscriptOutput, TranscriptTurn, generate_call
from agentlens.corpus.scenarios import FailureMode, Scenario
from agentlens.llm.gateway import GatewayResult
from agentlens.models import Call, GroundTruthLabel


def _turns(n: int) -> list[TranscriptTurn]:
    return [
        TranscriptTurn(speaker="agent" if i % 2 == 0 else "patient", text=f"turn {i}")
        for i in range(n)
    ]


def _ok_result() -> GatewayResult[TranscriptOutput]:
    return GatewayResult(
        parsed=TranscriptOutput(turns=_turns(8)), success=True, error=None, cost_cents=0.5
    )


def _failed_result() -> GatewayResult[TranscriptOutput]:
    return GatewayResult(parsed=None, success=False, error="boom", cost_cents=0.0)


def test_generate_clean_call(db_session: Session) -> None:
    with patch("agentlens.corpus.generator.complete_json", return_value=_ok_result()):
        call = generate_call(db_session, Scenario.SYMPTOM_TRIAGE, None, batch_id="b1")
    assert call is not None
    assert call.id.startswith("call_")
    loaded = db_session.get(Call, call.id)
    assert loaded is not None
    assert loaded.scenario == "symptom_triage"
    assert len(loaded.transcript) == 8
    assert loaded.ground_truth is None


def test_generate_failure_call_writes_ground_truth(db_session: Session) -> None:
    with patch("agentlens.corpus.generator.complete_json", return_value=_ok_result()):
        call = generate_call(
            db_session, Scenario.SYMPTOM_TRIAGE, FailureMode.MISSED_ESCALATION, batch_id="b1"
        )
    assert call is not None
    label = db_session.query(GroundTruthLabel).one()
    assert label.call_id == call.id
    assert label.failure_mode == "missed_escalation"
    assert label.pipeline_stage == "reasoning"
    assert label.severity == "P0"


def test_gateway_failure_returns_none_and_writes_nothing(db_session: Session) -> None:
    with patch("agentlens.corpus.generator.complete_json", return_value=_failed_result()):
        call = generate_call(db_session, Scenario.PRESCRIPTION_REFILL, None, batch_id="b1")
    assert call is None
    assert db_session.query(Call).count() == 0


def test_transcript_output_rejects_out_of_range_lengths() -> None:
    with pytest.raises(ValueError):
        TranscriptOutput(turns=_turns(2))
    with pytest.raises(ValueError):
        TranscriptOutput(turns=_turns(20))


@pytest.mark.llm
def test_real_generation_smoke(db_session: Session) -> None:
    """Costs money. Run only with explicit user approval: uv run pytest -m llm."""
    call = generate_call(
        db_session, Scenario.APPOINTMENT_SCHEDULING, FailureMode.DEAD_END_LOOP, batch_id="smoke"
    )
    assert call is not None
    assert 6 <= len(call.transcript) <= 16
