"""Tests for the LLM gateway (mocked anthropic client; one real-API test marked llm)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentlens.llm.gateway import GatewayResult, complete_json, cost_cents
from agentlens.models import LLMCallLog


class Answer(BaseModel):
    value: int


def _mock_client(
    *, parsed: Any = None, stop_reason: str = "end_turn", raises: Exception | None = None
) -> MagicMock:
    client = MagicMock()
    if raises is not None:
        client.messages.parse.side_effect = raises
    else:
        client.messages.parse.return_value = SimpleNamespace(
            parsed_output=parsed,
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=2000),
        )
    return client


def _call(session: Session, client: MagicMock) -> GatewayResult[Answer]:
    return complete_json(
        session,
        purpose="test",
        prompt_name="test_prompt",
        prompt_version="1.0",
        system="You are a test.",
        user_content="What is 2+2? My SSN is 123-45-6789.",
        response_model=Answer,
        model="claude-haiku-4-5",
        client=client,
    )


def test_cost_cents_known_models() -> None:
    # haiku: 100 cents/MTok in, 500 cents/MTok out
    assert cost_cents("claude-haiku-4-5", 1_000_000, 1_000_000) == pytest.approx(600.0)
    assert cost_cents("claude-sonnet-5", 1_000_000, 0) == pytest.approx(300.0)


def test_cost_cents_unknown_model_raises() -> None:
    with pytest.raises(ValueError, match="no pricing"):
        cost_cents("claude-unknown-9", 1, 1)


def test_success_parses_logs_and_costs(db_session: Session) -> None:
    client = _mock_client(parsed=Answer(value=4))
    result = _call(db_session, client)
    assert result.success and result.parsed == Answer(value=4)
    assert result.cost_cents == pytest.approx(0.1 + 1.0)  # 1000 in + 2000 out on haiku
    log = db_session.query(LLMCallLog).one()
    assert log.success is True
    assert log.cost_cents == pytest.approx(result.cost_cents)
    assert log.purpose == "test"


def test_outbound_content_is_redacted(db_session: Session) -> None:
    client = _mock_client(parsed=Answer(value=4))
    _call(db_session, client)
    sent = client.messages.parse.call_args.kwargs["messages"][0]["content"]
    assert "123-45-6789" not in sent
    assert "[REDACTED:SSN]" in sent


def test_unparseable_output_is_recorded_failure(db_session: Session) -> None:
    client = _mock_client(parsed=None)
    result = _call(db_session, client)
    assert not result.success and result.parsed is None
    log = db_session.query(LLMCallLog).one()
    assert log.success is False
    assert log.error is not None


def test_api_error_is_recorded_failure(db_session: Session) -> None:
    client = _mock_client(raises=RuntimeError("boom"))
    result = _call(db_session, client)
    assert not result.success
    assert "boom" in (result.error or "")
    assert db_session.query(LLMCallLog).one().success is False


def test_refusal_is_recorded_failure(db_session: Session) -> None:
    client = _mock_client(parsed=None, stop_reason="refusal")
    result = _call(db_session, client)
    assert not result.success
    assert "refusal" in (result.error or "")


@pytest.mark.llm
def test_real_api_smoke(db_session: Session) -> None:
    """Costs money. Run only with explicit user approval: uv run pytest -m llm."""
    result = complete_json(
        db_session,
        purpose="smoke",
        prompt_name="smoke",
        prompt_version="1.0",
        system="Answer with the requested JSON only.",
        user_content="Return value=4.",
        response_model=Answer,
        model="claude-haiku-4-5",
    )
    assert result.success and result.parsed is not None and result.parsed.value == 4
