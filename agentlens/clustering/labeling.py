"""LLM labeling of one failure cluster (AC-2.1, AC-2.2). Goes through the gateway."""

from typing import Literal

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.llm.gateway import GatewayResult, complete_json
from agentlens.prompts.cluster_labeling import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class ClusterLabel(BaseModel):
    """LLM output: human-readable pattern name, summary, and routing suggestion."""

    label: str
    description: str
    routing: Literal["prompt_fix", "retrieval_data_fix", "ops_process", "model_config"]


def label_cluster(
    session: Session,
    descriptions: list[str],
    *,
    model: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> GatewayResult[ClusterLabel]:
    """Label one cluster from its member failure descriptions (≤10 sampled)."""
    return complete_json(
        session,
        purpose="cluster_labeling",
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        system=SYSTEM_PROMPT,
        user_content=build_user_prompt(descriptions),
        response_model=ClusterLabel,
        model=model or get_settings().judge_model,
        max_tokens=1024,
        client=client,
    )
