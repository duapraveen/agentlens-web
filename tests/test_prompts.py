"""Tests for the versioned corpus generation prompt."""

from agentlens.corpus.scenarios import FailureMode, Scenario
from agentlens.prompts.corpus_generation import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


def test_prompt_identity() -> None:
    assert PROMPT_NAME == "corpus_generation"
    assert PROMPT_VERSION == "1.0"


def test_system_prompt_specifies_short_call() -> None:
    assert "6 to 12" in SYSTEM_PROMPT
    assert "two minutes" in SYSTEM_PROMPT


def test_clean_prompt_mentions_scenario_without_injection() -> None:
    prompt = build_user_prompt(Scenario.APPOINTMENT_SCHEDULING, None)
    assert "appointment" in prompt.lower()
    assert "defect" not in prompt.lower()


def test_injected_prompt_contains_instruction_unlabeled() -> None:
    prompt = build_user_prompt(Scenario.SYMPTOM_TRIAGE, FailureMode.MISSED_ESCALATION)
    assert "red-flag" in prompt
    assert "do NOT label" in prompt
