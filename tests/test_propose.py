"""Tests for LLM fix proposal (gateway mocked)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from agentlens.fixes.propose import ProposedFix, propose_fix
from agentlens.models import Cluster
from agentlens.prompts.fix_proposal import PROMPT_VERSION, build_user_prompt


def _cluster(session: Session) -> Cluster:
    cluster = Cluster(
        label="missed cardiac escalation",
        description="Agent books routine appointments for red-flag chest pain.",
        routing_suggestion="prompt_fix",
        dominant_severity="P0",
        size=3,
    )
    session.add(cluster)
    session.flush()
    return cluster


def test_prompt_includes_cluster_context_and_fix_types() -> None:
    prompt = build_user_prompt(
        label="missed cardiac escalation",
        description="Agent books routine appointments for red-flag chest pain.",
        routing_suggestion="prompt_fix",
        descriptions=["desc one", "desc two"],
    )
    assert "missed cardiac escalation" in prompt
    assert "red-flag chest pain" in prompt
    assert "desc one" in prompt and "desc two" in prompt
    for fix_type in ("prompt_fix", "retrieval_data_fix", "ops_process", "model_config"):
        assert fix_type in prompt
    assert PROMPT_VERSION == "1.0"


def test_prompt_samples_at_most_ten() -> None:
    prompt = build_user_prompt(
        label="l",
        description="d",
        routing_suggestion="prompt_fix",
        descriptions=[f"member description {i}" for i in range(30)],
    )
    assert "member description 9" in prompt
    assert "member description 15" not in prompt


def _mock_client(parsed: Any) -> MagicMock:
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(
        parsed_output=parsed,
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=400, output_tokens=150),
    )
    return client


def test_propose_fix_returns_parsed_fix(db_session: Session) -> None:
    cluster = _cluster(db_session)
    expected = ProposedFix(
        fix_type="prompt_fix",
        rationale="Escalation rules are not prioritized in the agent prompt.",
        patch="If the caller mentions chest pain, escalate to emergency services immediately.",
    )
    result = propose_fix(db_session, cluster, client=_mock_client(expected))
    assert result.success and result.parsed == expected
