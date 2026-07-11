"""Regenerate a fix's affected scenarios with the patched agent (AC-5.2)."""

from uuid import uuid4

import anthropic
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.corpus.generator import TranscriptOutput
from agentlens.llm.gateway import complete_json
from agentlens.models import Call, Cluster, ClusterMember, EvalRecord, FixProposal
from agentlens.prompts.fix_regeneration import (
    PROMPT_NAME,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


def affected_calls(session: Session, cluster: Cluster) -> list[Call]:
    """Distinct calls behind the cluster's member eval records, ordered by id."""
    return (
        session.query(Call)
        .join(EvalRecord, EvalRecord.call_id == Call.id)
        .join(ClusterMember, ClusterMember.eval_record_id == EvalRecord.id)
        .filter(ClusterMember.cluster_id == cluster.id)
        .distinct()
        .order_by(Call.id)
        .all()
    )


def regenerate_for_fix(
    session: Session,
    fix: FixProposal,
    *,
    model: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> list[Call]:
    """One regenerated call per affected call, under the fix's patched agent policy.

    Regenerated calls carry batch_id "fixbatch_<fix.id>" and
    agent_prompt_version "fix_<fix.id>", and no ground-truth label. Gateway
    failures skip that call (already recorded in llm_call_log).
    """
    regenerated: list[Call] = []
    for original in affected_calls(session, fix.cluster):
        result = complete_json(
            session,
            purpose="fix_regeneration",
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
            system=SYSTEM_PROMPT,
            user_content=build_user_prompt(original.scenario, fix.patch),
            response_model=TranscriptOutput,
            model=model or get_settings().generator_model,
            client=client,
        )
        if not result.success or result.parsed is None:
            continue
        call = Call(
            id=f"call_{uuid4().hex[:12]}",
            scenario=original.scenario,
            transcript=[turn.model_dump() for turn in result.parsed.turns],
            batch_id=f"fixbatch_{fix.id}",
            agent_prompt_version=f"fix_{fix.id}",
        )
        session.add(call)
        session.commit()
        regenerated.append(call)
    return regenerated
