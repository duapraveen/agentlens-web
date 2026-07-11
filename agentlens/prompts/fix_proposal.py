"""Prompt template for cluster fix proposals. Version 1.0."""

PROMPT_NAME = "fix_proposal"
PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = (
    "You draft fixes for recurring failure patterns in healthcare voice-agent calls. "
    "Given a named failure cluster and sample failure descriptions, return JSON with: "
    "fix_type (which kind of fix), rationale (one or two sentences on why this fix "
    "addresses the root cause), and patch (the concrete change — for prompt_fix, the "
    "exact instruction text to add to the agent's prompt; for other types, the concrete "
    "change to make). The patch must be directly applicable, not a vague suggestion."
)

_MAX_SAMPLES = 10

_FIX_TYPE_GUIDE = """Fix types:
- prompt_fix: change the agent's instructions/prompt (e.g. it invents details, \
skips escalation, over-discloses)
- retrieval_data_fix: correct the lookup data or retrieval pipeline (wrong hours, \
wrong provider record)
- ops_process: add a human/operational process (e.g. review queue, staffing)
- model_config: change the underlying model or transcription configuration \
(e.g. persistent mishearing of identifiers)"""


def build_user_prompt(
    label: str,
    description: str,
    routing_suggestion: str,
    descriptions: list[str],
) -> str:
    """User prompt drafting one fix from cluster context and ≤10 member descriptions."""
    sampled = descriptions[:_MAX_SAMPLES]
    numbered = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(sampled))
    return (
        f"Failure cluster: {label}\n"
        f"Summary: {description}\n"
        f"Suggested routing: {routing_suggestion}\n\n"
        f"Sample failure descriptions ({len(sampled)}):\n{numbered}\n\n"
        f"{_FIX_TYPE_GUIDE}\n\nDraft the fix."
    )
