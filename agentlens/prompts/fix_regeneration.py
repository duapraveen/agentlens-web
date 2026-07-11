"""Prompt template for regenerating scenarios with a patched agent. Version 1.0.

Separate from corpus_generation (which stays at v1.0): here there is no
failure injection — the fix patch is presented as the agent's updated policy
and the call plays out under it (AC-5.2).
"""

from agentlens.corpus.scenarios import SCENARIO_DESCRIPTIONS, Scenario
from agentlens.prompts.corpus_generation import SYSTEM_PROMPT as _CORPUS_SYSTEM_PROMPT

PROMPT_NAME = "fix_regeneration"
PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = _CORPUS_SYSTEM_PROMPT


def build_user_prompt(scenario: str, patch: str) -> str:
    """User prompt for one regenerated transcript under the patched agent policy."""
    return "\n".join(
        [
            f"Scenario: {SCENARIO_DESCRIPTIONS[Scenario(scenario)]}",
            "The agent's instructions have been updated with the following policy, "
            "which it now follows:",
            patch,
            "Write one complete call transcript for this scenario with the updated agent.",
        ]
    )
