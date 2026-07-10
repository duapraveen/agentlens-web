"""Tests for the versioned judge rubric/prompt."""

from agentlens.prompts.judge import (
    PROMPT_NAME,
    PROMPT_VERSION,
    RUBRIC_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


def test_prompt_identity() -> None:
    assert PROMPT_NAME == "judge"
    assert PROMPT_VERSION == "1.0"
    assert RUBRIC_VERSION == "1.0"


def test_rubric_names_dimensions_severities_stages() -> None:
    for dimension in (
        "task_completion",
        "factual_accuracy",
        "safety_compliance",
        "communication_quality",
    ):
        assert dimension in SYSTEM_PROMPT
    for severity in ("P0", "P1", "P2"):
        assert severity in SYSTEM_PROMPT
    for stage in ("transcription", "retrieval", "reasoning", "orchestration"):
        assert stage in SYSTEM_PROMPT


def test_user_prompt_renders_speaker_labels() -> None:
    transcript = [
        {"speaker": "agent", "text": "Hello, how can I help?"},
        {"speaker": "patient", "text": "I need a refill."},
    ]
    prompt = build_user_prompt(transcript)
    assert "Agent: Hello, how can I help?" in prompt
    assert "Patient: I need a refill." in prompt
