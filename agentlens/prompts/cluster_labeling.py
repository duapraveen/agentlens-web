"""Prompt template for cluster labeling. Version 1.0."""

PROMPT_NAME = "cluster_labeling"
PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = (
    "You name recurring failure patterns found in healthcare voice-agent calls. "
    "Given several one-sentence failure descriptions that were grouped together, "
    "return JSON with: label (3-6 word name for the pattern), description (one or "
    "two sentences summarizing it), and routing (which kind of fix addresses it)."
)

_MAX_SAMPLES = 10

_ROUTING_GUIDE = """Routing options:
- prompt_fix: the agent's instructions/prompt should change (e.g. it invents details, \
skips escalation, over-discloses)
- retrieval_data_fix: the lookup data or retrieval pipeline is wrong (wrong hours, \
wrong provider record)
- ops_process: a human/operational process is needed (e.g. review queue, staffing)
- model_config: the underlying model or transcription configuration should change \
(e.g. persistent mishearing of identifiers)"""


def build_user_prompt(descriptions: list[str]) -> str:
    """User prompt naming one cluster from up to 10 sampled member descriptions."""
    sampled = descriptions[:_MAX_SAMPLES]
    numbered = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(sampled))
    return (
        f"These {len(sampled)} failure descriptions were clustered together:\n\n"
        f"{numbered}\n\n{_ROUTING_GUIDE}\n\nName this pattern."
    )
