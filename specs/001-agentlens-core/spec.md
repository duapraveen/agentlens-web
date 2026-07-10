# Spec 001 — AgentLens Core: Conversation Quality & Learning-Loop Platform

Status: Draft for approval · Owner: Praveen Dua · Constitution: v1.0.0
Scope: 2-3 day prototype, architected for production continuation by a team.

---

## 1. Problem & Intent

AI voice agents handling patient conversations fail in ways that are today
found manually: humans review calls, spot issues, file tickets, and hope fixes
work. This does not scale with call volume.

**Intent:** close the loop automatically — every conversation is evaluated,
failures are detected and clustered into recurring patterns, human reviewers
calibrate the automated judge, and proposed fixes are validated by regression
evals before being trusted.

Primary user: AI/platform engineers and operations reviewers at a healthcare
voice-AI company. (Demo context: healthcare care-navigation agents like triage, appointment booking, etc...)

## 2. Success Metrics (prototype)

- Judge quality is **measured, not assumed**: precision and recall ≥ 0.80 on
  P0/P1 failure detection against injected ground truth in the golden set.
- ≥ 90% of injected failure instances land in a correctly-labeled cluster.
- Judge↔human agreement rate visible and recomputed live as reviews arrive.
- One full closed-loop demo: cluster → proposed fix → regression re-run →
  before/after pass-rate delta shown.
- Cost per evaluated call computed and displayed (target: < $0.05 with cheap
  model on bulk pass).

## 3. User Stories & Acceptance Criteria

### US-1: Ingest and evaluate conversations
As a platform engineer, I want every conversation automatically scored on a
fixed rubric so quality issues surface without manual review.

- AC-1.1: Given a corpus of transcripts, running the eval job produces one
  eval record per call per dimension: `task_completion`, `factual_accuracy`,
  `safety_compliance`, `communication_quality`; each score 0-100 with severity
  (P0/P1/P2), failure description, judge reasoning, and attributed pipeline
  stage (`transcription | retrieval | reasoning | orchestration`).
- AC-1.2: Deterministic safety checks (rule-based escalation and PHI patterns)
  run on every call independent of the LLM judge; a deterministic P0 hit is
  recorded even if the judge scores the call clean (Constitution I.3).
- AC-1.3: Every eval record stores model version, prompt version, rubric
  version, and input hash (Constitution I.5).
- AC-1.4: Eval job is idempotent — re-running does not duplicate records.

### US-2: Detect recurring failure patterns
As an engineering lead, I want similar failures clustered and labeled so we fix
patterns, not individual calls.

- AC-2.1: Failure descriptions are embedded and clustered; each cluster gets an
  auto-generated human-readable label and a member count.
- AC-2.2: Each cluster carries a routing suggestion: `prompt_fix |
  retrieval_data_fix | ops_process | model_config`.
- AC-2.3: Cluster view links to member calls; ≥90% of a given injected failure
  mode lands in one dominant cluster on the golden set.

### US-3: Investigate a single call
As an engineer debugging a failure, I want a per-call trace showing what
happened and why the judge flagged it.

- AC-3.1: Call detail view shows transcript, all dimension scores, judge
  reasoning, deterministic-check results, attributed pipeline stage, and (in
  dev mode) injected ground truth.
- AC-3.2: From a call I can navigate to its cluster and vice versa.

### US-4: Calibrate the judge with human feedback
As an operations reviewer, I want to confirm or reject the judge's findings so
the automated system earns trust.

- AC-4.1: Reviewer queue presents flagged calls; reviewer records
  agree/disagree + optional note per finding.
- AC-4.2: Judge↔human agreement rate is computed per dimension and displayed;
  updates as reviews are submitted.
- AC-4.3: A rubric/prompt revision can be re-run on the golden set and its
  agreement + precision/recall compared against the prior judge version
  side-by-side (Constitution IV.3).

### US-5: Close the loop — propose and validate fixes
As an AI engineer, I want the system to draft a fix for a failure cluster and
prove it works before I trust it.

- AC-5.1: For a selected cluster, the system generates a proposed fix (e.g., a
  prompt patch for the simulated agent) with rationale.
- AC-5.2: Applying the fix regenerates the affected scenarios with the patched
  agent and re-runs evals on them.
- AC-5.3: A before/after report shows pass-rate delta per dimension and flags
  regressions on unrelated dimensions.
- AC-5.4: P0 clusters cannot be auto-closed; the report requires human
  acknowledgment (Constitution V.4).

### US-6: Monitor quality over time
As a product/eng leader, I want a dashboard of agent quality trends.

- AC-6.1: Overview shows pass rate per dimension over time, severity counts,
  top clusters, judge accuracy stats, and cumulative eval cost.
- AC-6.2: All numbers drill down to underlying calls within two clicks.

### US-7: Synthetic corpus with ground truth (enabler)
As the team, we need realistic labeled data to measure everything above.

- AC-7.1: Generator produces 50-60 short patient↔agent transcripts (≈1-2
  minutes of spoken conversation each) across scenarios: appointment
  scheduling, symptom triage, insurance/eligibility, prescription refill,
  referral navigation.
- AC-7.2: ~30% of calls carry injected failures drawn from: transcription
  noise on identifiers, hallucinated availability, wrong retrieval (provider/
  hours), missed escalation of red-flag symptoms, unnecessary PHI readback,
  dead-end loops / task non-completion.
- AC-7.3: Every injected failure is tagged with ground truth (mode, pipeline
  stage, severity) stored separately from eval outputs.
- AC-7.4: A frozen labeled subset (≥50 calls) is checked in as
  `data/golden/` (Constitution IV.2).

## 4. Non-Goals (prototype)

- No real audio/ASR — transcripts only. (Extension path: model ASR errors from
  a real STT stage)
- No real PHI, no HIPAA infrastructure — synthetic data behind a designed
  redaction boundary.
- No streaming ingestion — batch jobs. Production path documented, not built.
- No authentication/multi-tenancy in the UI.
- No automatic deployment of fixes to a live agent — proposals + validation
  only, human approves.

## 5. System Shape (constraint, not design)

Monorepo Python package `agentlens/` with modules: `corpus` (generation),
`evals` (judge + deterministic checks), `clustering`, `feedback` (reviews +
calibration), `fixes` (propose + regression), `dashboard` (Streamlit),
`llm` (gateway), `privacy` (redaction), `jobs` (batch entrypoints).
Detailed design belongs in `plan.md`, not here.

## 6. Open Questions (resolve in plan phase)

- OQ-1: Cheap-model bulk judging with expensive-model escalation on borderline
  scores — worth it in prototype, or note as production path?
- OQ-2: Clustering algo: KMeans with silhouette-tuned k vs HDBSCAN (variable
  cluster count). Decide by golden-set behavior.
- OQ-3: Judge granularity: one call-level judgment vs per-turn judgments
  aggregated. Per-turn is more accurate for stage attribution but ~5x cost.
- OQ-4: Streamlit multipage vs single page with tabs.

## 7. Review & Acceptance

Spec is approved when: constitution conflicts = none, all ACs testable, golden
set defined before US-1 implementation begins. Plan (`plan.md`) and task
breakdown (`tasks.md`) are generated from this spec after approval.
