"""Generate one synthetic call via the LLM gateway and persist it with ground truth."""

from typing import Literal
from uuid import uuid4

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.corpus.scenarios import FAILURE_MODE_INFO, FailureMode, Scenario
from agentlens.llm.gateway import complete_json
from agentlens.models import Call, GroundTruthLabel
from agentlens.prompts.corpus_generation import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class TranscriptTurn(BaseModel):
    """One spoken turn."""

    speaker: Literal["patient", "agent"]
    text: str


class TranscriptOutput(BaseModel):
    """LLM output schema for a generated call.

    Prompted length is 6-12 turns (~1-2 minutes spoken); 16 is the hard
    tolerance ceiling before the output counts as a validation failure.
    """

    turns: list[TranscriptTurn] = Field(min_length=6, max_length=16)


def generate_call(
    session: Session,
    scenario: Scenario,
    failure_mode: FailureMode | None,
    batch_id: str,
    *,
    model: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> Call | None:
    """Generate and commit one Call (plus GroundTruthLabel when a failure is injected).

    Returns None when the gateway call failed; the failure is already recorded
    in llm_call_log by the gateway. The gateway is invoked before any objects
    are staged on the session (the gateway commits).
    """
    result = complete_json(
        session,
        purpose="corpus_generation",
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        system=SYSTEM_PROMPT,
        user_content=build_user_prompt(scenario, failure_mode),
        response_model=TranscriptOutput,
        model=model or get_settings().generator_model,
        client=client,
    )
    if not result.success or result.parsed is None:
        return None

    call = Call(
        id=f"call_{uuid4().hex[:12]}",
        scenario=scenario.value,
        transcript=[turn.model_dump() for turn in result.parsed.turns],
        batch_id=batch_id,
    )
    session.add(call)
    if failure_mode is not None:
        info = FAILURE_MODE_INFO[failure_mode]
        session.add(
            GroundTruthLabel(
                call_id=call.id,
                failure_mode=failure_mode.value,
                pipeline_stage=info.stage.value,
                severity=info.severity.value,
            )
        )
    session.commit()
    return call
