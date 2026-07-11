"""Tests for fix regression regeneration (gateway mocked)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from agentlens.corpus.generator import TranscriptOutput, TranscriptTurn
from agentlens.fixes.regression import affected_calls, regenerate_for_fix
from agentlens.models import Call, Cluster, ClusterMember, EvalRecord, FixProposal
from agentlens.prompts.fix_regeneration import PROMPT_VERSION, build_user_prompt


def _seed_cluster_with_calls(session: Session, n_calls: int = 2) -> FixProposal:
    cluster = Cluster(
        label="missed cardiac escalation",
        description="d",
        routing_suggestion="prompt_fix",
        dominant_severity="P0",
        size=n_calls,
    )
    session.add(cluster)
    session.flush()
    for i in range(n_calls):
        call_id = f"call_orig_{i}"
        session.add(
            Call(
                id=call_id,
                scenario="symptom_triage",
                transcript=[{"speaker": "agent", "text": "hi"}],
                batch_id="b1",
            )
        )
        record = EvalRecord(
            call_id=call_id,
            dimension="safety_compliance",
            score=10,
            severity="P0",
            passed=False,
            failure_description="missed escalation",
            judge_reasoning="r",
            judge_model="claude-haiku-4-5",
            prompt_version="1.0",
            rubric_version="1.0",
            input_hash="h",
        )
        session.add(record)
        session.flush()
        session.add(ClusterMember(cluster_id=cluster.id, eval_record_id=record.id))
    fix = FixProposal(
        cluster_id=cluster.id,
        fix_type="prompt_fix",
        rationale="r",
        patch="Escalate chest pain to emergency services immediately.",
    )
    session.add(fix)
    session.commit()
    return fix


def test_regeneration_prompt_has_patch_and_no_injection_framing() -> None:
    prompt = build_user_prompt("symptom_triage", "Escalate chest pain immediately.")
    assert "Escalate chest pain immediately." in prompt
    assert "symptom" in prompt
    assert "weave" not in prompt.lower()
    assert PROMPT_VERSION == "1.0"


def _mock_client(turns_factory: Any) -> MagicMock:
    client = MagicMock()

    def parse(**kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            parsed_output=turns_factory(),
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=300, output_tokens=200),
        )

    client.messages.parse.side_effect = parse
    return client


def _transcript() -> TranscriptOutput:
    turns = [
        TranscriptTurn(speaker="agent" if i % 2 == 0 else "patient", text=f"turn {i}")
        for i in range(6)
    ]
    return TranscriptOutput(turns=turns)


def test_affected_calls_are_distinct_member_calls(db_session: Session) -> None:
    fix = _seed_cluster_with_calls(db_session, n_calls=2)
    calls = affected_calls(db_session, fix.cluster)
    assert [c.id for c in calls] == ["call_orig_0", "call_orig_1"]


def test_regenerate_stamps_batch_and_version(db_session: Session) -> None:
    fix = _seed_cluster_with_calls(db_session, n_calls=2)
    regenerated = regenerate_for_fix(db_session, fix, client=_mock_client(_transcript))

    assert len(regenerated) == 2
    for call in regenerated:
        assert call.batch_id == f"fixbatch_{fix.id}"
        assert call.agent_prompt_version == f"fix_{fix.id}"
        assert call.scenario == "symptom_triage"
        assert call.ground_truth is None
        assert not call.is_golden


def test_gateway_failure_skips_call_without_raising(db_session: Session) -> None:
    fix = _seed_cluster_with_calls(db_session, n_calls=2)
    client = MagicMock()
    client.messages.parse.side_effect = [
        SimpleNamespace(
            parsed_output=_transcript(),
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=300, output_tokens=200),
        ),
        RuntimeError("api down"),
    ]
    regenerated = regenerate_for_fix(db_session, fix, client=client)
    assert len(regenerated) == 1
