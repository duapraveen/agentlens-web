"""Single entry point for all LLM calls.

Responsibilities (constitution II): redact outbound text, validate structured
JSON output with Pydantic, account cost in USD cents, tag prompt versions,
and record every call — including unparseable output — as an LLMCallLog row.
Transport retries use the anthropic SDK's built-in budget (max_retries=2);
parse/validation failures are recorded, never retried.

No other module may import the anthropic SDK.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agentlens.config import get_settings
from agentlens.models import LLMCallLog
from agentlens.privacy.redact import redact

T = TypeVar("T", bound=BaseModel)

# Sticker prices cached from Anthropic docs 2026-07-10, USD cents per million
# tokens (input, output). Sonnet 5 has intro pricing (200/1000) through
# 2026-08-31; we use sticker prices and accept slight over-reporting.
_PRICING_CENTS_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (100.0, 500.0),
    "claude-sonnet-5": (300.0, 1500.0),
}


def cost_cents(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost of one LLM call in USD cents. Raises ValueError for unpriced models."""
    if model not in _PRICING_CENTS_PER_MTOK:
        raise ValueError(f"no pricing for model {model!r}; add it to _PRICING_CENTS_PER_MTOK")
    in_rate, out_rate = _PRICING_CENTS_PER_MTOK[model]
    return input_tokens * in_rate / 1_000_000 + output_tokens * out_rate / 1_000_000


@dataclass(frozen=True)
class GatewayResult(Generic[T]):
    """Outcome of one gateway call. cost_cents is USD cents (0.0 if the call never ran)."""

    parsed: T | None
    success: bool
    error: str | None
    cost_cents: float


def _default_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


def complete_json(
    session: Session,
    *,
    purpose: str,
    prompt_name: str,
    prompt_version: str,
    system: str,
    user_content: str,
    response_model: type[T],
    model: str,
    max_tokens: int = 8192,
    client: anthropic.Anthropic | None = None,
) -> GatewayResult[T]:
    """Run one structured-JSON LLM call and log it (commits one LLMCallLog row).

    user_content is redacted unconditionally before leaving the process.
    Returns a failed GatewayResult (never raises) on API errors, refusals,
    or output that does not validate against response_model. Callers must
    invoke the gateway before staging their own uncommitted objects (the
    gateway commits the session).
    """
    client = client or _default_client()
    parsed: T | None = None
    error: str | None = None
    in_tokens = out_tokens = 0
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": redact(user_content)}],
            output_format=response_model,
        )
        in_tokens = response.usage.input_tokens
        out_tokens = response.usage.output_tokens
        if response.stop_reason == "refusal":
            error = "model returned stop_reason=refusal"
        elif response.parsed_output is None:
            error = "output did not validate against response model"
        else:
            parsed = response.parsed_output
    except Exception as exc:  # gateway boundary: every failure becomes a recorded result
        error = f"{type(exc).__name__}: {exc}"

    cents = cost_cents(model, in_tokens, out_tokens)
    session.add(
        LLMCallLog(
            purpose=purpose,
            model=model,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_cents=cents,
            success=error is None,
            error=error,
        )
    )
    session.commit()
    return GatewayResult(parsed=parsed, success=error is None, error=error, cost_cents=cents)
