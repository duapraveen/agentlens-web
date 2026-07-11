"""LLM fix proposal for one cluster (AC-5.1). Goes through the gateway."""

from typing import Literal

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.llm.gateway import GatewayResult, complete_json
from agentlens.models import Cluster
from agentlens.prompts.fix_proposal import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class ProposedFix(BaseModel):
    """LLM output: fix type, rationale, and a directly applicable patch."""

    fix_type: Literal["prompt_fix", "retrieval_data_fix", "ops_process", "model_config"]
    rationale: str
    patch: str


def propose_fix(
    session: Session,
    cluster: Cluster,
    *,
    model: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> GatewayResult[ProposedFix]:
    """Draft one fix for a cluster from its label, summary, and member descriptions."""
    descriptions = [
        m.eval_record.failure_description or "" for m in cluster.members if m.eval_record
    ]
    return complete_json(
        session,
        purpose="fix_proposal",
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        system=SYSTEM_PROMPT,
        user_content=build_user_prompt(
            label=cluster.label,
            description=cluster.description,
            routing_suggestion=cluster.routing_suggestion,
            descriptions=descriptions,
        ),
        response_model=ProposedFix,
        model=model or get_settings().judge_model,
        max_tokens=1024,
        client=client,
    )
