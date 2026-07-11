# Note: making fix regression counterfactual (deferred design options)

Status: **deferred by user decision 2026-07-10 — do not implement without approval.**
Context: Phase 5's regression re-run regenerates affected scenarios fresh under the
patched agent policy (no failure injection), so before/after are two unrelated
stories; it validates loop mechanics and unrelated-dimension side effects, not
causal fix efficacy. Options discussed to fix that, all variants of "hold the
patient side constant, vary only the agent":

## Option 1 — Prefix replay (counterfactual continuation) · cheap, recommended first step
Cut the original failing transcript at the pivot turn (locatable from the judge's
failure_description + deterministic check detail), have the model continue **as the
agent only** given the prefix + patched policy, then judge the hybrid transcript.
Same patient, same pressure, only the agent policy varies at the decision point that
failed. Deterministic checks give a free judge-independent verdict for P0 modes.
Cost shape unchanged (~1 generation + 1 judge call per affected call).

## Option 2 — Frozen patient-script replay · middle ground, probably skip
Replay patient turns verbatim, regenerate each agent turn under the patch. Fully
counterfactual but incoherent after first divergence (patient script stops making
sense); cutting at first divergence collapses this into option 1.

## Option 3 — Two-role simulation with a real agent prompt · principled long-term fix
Make the agent an actual system prompt (what `agent_prompt_version` pretends to track)
and the patient a persona-driven simulator; the failure injection becomes patient-side
pressure ("mentions chest pain in passing", "mumbles member ID"). Unpatched vs patched
runs face identical pressure → genuinely causal A/B. Upgrades the platform (fixes patch
a real artifact; scenarios re-runnable against any agent version). Cost ~one call per
turn (≈6-12× per conversation; a 12-call regression ≈ $1.50-2.50 with haiku patient).
Corpus-architecture change — needs its own spec section/ADR. Natural slot: before or
alongside Phase 7.
