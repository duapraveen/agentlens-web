"""Tests for LLM cluster labeling (gateway mocked)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from agentlens.clustering.labeling import ClusterLabel, label_cluster
from agentlens.prompts.cluster_labeling import PROMPT_VERSION, build_user_prompt


def test_prompt_includes_descriptions_and_routing_options() -> None:
    prompt = build_user_prompt(["desc one", "desc two"])
    assert "desc one" in prompt and "desc two" in prompt
    for routing in ("prompt_fix", "retrieval_data_fix", "ops_process", "model_config"):
        assert routing in prompt
    assert PROMPT_VERSION == "1.0"


def test_prompt_samples_at_most_ten() -> None:
    prompt = build_user_prompt([f"description number {i}" for i in range(30)])
    assert "description number 9" in prompt
    assert "description number 15" not in prompt


def _mock_client(parsed: Any) -> MagicMock:
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(
        parsed_output=parsed,
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=300, output_tokens=80),
    )
    return client


def test_label_cluster_returns_parsed_label(db_session: Session) -> None:
    expected = ClusterLabel(
        label="hallucinated availability",
        description="Agent invents open slots.",
        routing="prompt_fix",
    )
    result = label_cluster(db_session, ["Agent invented a slot."], client=_mock_client(expected))
    assert result.success and result.parsed == expected
