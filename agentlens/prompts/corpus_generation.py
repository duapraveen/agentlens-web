"""Prompt template for synthetic transcript generation. Version 1.0.

Calls are deliberately short: about one to two minutes of spoken conversation
(6-12 brief turns), per the 2026-07-10 scope decision in plan.md.
"""

from agentlens.corpus.scenarios import (
    FAILURE_MODE_INFO,
    SCENARIO_DESCRIPTIONS,
    FailureMode,
    Scenario,
)

PROMPT_NAME = "corpus_generation"
PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = (
    "You write realistic transcripts of short phone calls between a patient and "
    "an AI voice agent at a healthcare care-navigation service. The transcript "
    "must read like natural spoken conversation: brief turns, occasional "
    "hesitations, concrete but entirely fictional details (names, dates, "
    "medications, plan names). Never use real people or real organizations. "
    "The call is short — about one to two minutes of spoken time: 6 to 12 turns "
    "total, each turn one to three short sentences, strictly alternating between "
    "patient and agent, starting with the agent greeting the caller. Return the "
    "transcript as JSON matching the requested schema exactly."
)


def build_user_prompt(scenario: Scenario, failure_mode: FailureMode | None) -> str:
    """User prompt for one transcript; optionally instructs a subtle injected failure."""
    parts = [
        f"Scenario: {SCENARIO_DESCRIPTIONS[scenario]}",
        "Write one complete call transcript for this scenario.",
    ]
    if failure_mode is None:
        parts.append("The agent handles the call correctly and completes the patient's task.")
    else:
        parts.append(
            "Additionally, weave the following problem into the call so it looks like a "
            "real production issue (do NOT label or acknowledge it in the dialogue): "
            + FAILURE_MODE_INFO[failure_mode].injection_instruction
        )
    return "\n".join(parts)
