# Tasks — Spec 001: AgentLens Core

Task breakdown generated from `plan.md`. Reference the task ID in every commit:
`feat: ... (specs/001-agentlens-core/tasks.md#T104)`.

Status legend: ☐ not started · ◐ in progress · ☑ done

## Phase 0 — Foundation

| Status | ID | Task | AC / Rule |
|---|---|---|---|
| ☑ | T001 | Project scaffold (uv, ruff, mypy --strict, pytest `llm` marker, .env.example, git init, ADR-001) | Constitution II, III |
| ☑ | T002 | Typed settings (pydantic-settings) | Constitution III.5 |
| ☑ | T003 | DB engine + core models (`Call`, `GroundTruthLabel`, `LLMCallLog`, `JobRun`) | AC-7.3; Constitution II (ORM only, Postgres-portable) |
| ☑ | T004 | Privacy redaction module | Constitution V.2 |
| ☑ | T005 | LLM gateway (structured JSON, cost cents, prompt-version tagging, failure recording) | Constitution II (single gateway) |

## Phase 1 — Synthetic Corpus & Golden Set (US-7)

| Status | ID | Task | AC |
|---|---|---|---|
| ☑ | T101 | Scenario & failure-mode taxonomy | AC-7.1, AC-7.2 |
| ☑ | T102 | Versioned corpus generation prompt | AC-7.1 |
| ☑ | T103 | Transcript generator (Call + GroundTruthLabel) | AC-7.2, AC-7.3 |
| ☑ | T104 | Corpus generation job (`--count/--failure-rate/--seed`) | AC-7.1, AC-7.2 |
| ☑ | T105 | Golden-set freeze job (stratified, append-only) | AC-7.4 |
| ☑ | T106 | Run generation + commit golden set (user-approved spend) | AC-7.1–7.4 |

## Phase 2 — Evals (US-1)

| Status | ID | Task | AC |
|---|---|---|---|
| ☑ | T201 | Eval schema (`EvalRecord`, `DeterministicCheckResult`, idempotency constraint) | AC-1.1, AC-1.3, AC-1.4 |
| ☑ | T202 | Deterministic safety checks (escalation, PHI) | AC-1.2; Constitution I.3 |
| ☑ | T203 | Judge rubric + prompt v1.0 (call-level, 4 dimensions) | AC-1.1 |
| ☑ | T204 | Eval runner (idempotent, provenance-stamped) | AC-1.3, AC-1.4 |
| ☑ | T205 | Eval job (`--scope`, cost estimate) | AC-1.1 |
| ☑ | T206 | Judge quality metrics vs golden (P/R baseline for regression gate) | Spec §2; Constitution IV.3 |
| ☐ | T207 | **Deferred:** fix `phi_readback` false positives — drop bare PHONE matches (3 FPs on clinic callback numbers); re-run checks + metrics (free, no LLM) | Constitution I.3 |

## Phase 3 — Clustering (US-2)

| Status | ID | Task | AC |
|---|---|---|---|
| ☑ | T301 | Embeddings backend decision + ADR-002 + embed module (escalated: TF-IDF → sentence-transformers per ADR-002 amendment) | AC-2.1 |
| ☑ | T302 | Clustering algorithm + tables + recluster job (resolves OQ-2: KMeans; HDBSCAN rejected empirically) | AC-2.1 |
| ☑ | T303 | LLM cluster labeling + routing suggestion | AC-2.1, AC-2.2 |
| ☑ | T304 | Cluster purity check (≥90% dominant-cluster) — result 5/6 modes at 1.00; hallucinated_availability 0.67, deviation pending user acceptance (see plan.md Phase 3 exit result) | AC-2.3 |

## Phase 4 — Feedback & Calibration (US-4)

| Status | ID | Task | AC |
|---|---|---|---|
| ☐ | T401 | Review model + review queue backend | AC-4.1 |
| ☐ | T402 | Judge↔human agreement stats (per dimension, live) | AC-4.2 |
| ☐ | T403 | Judge version comparison on golden set (regression gate) | AC-4.3 |

## Phase 5 — Fix Loop (US-5)

| Status | ID | Task | AC |
|---|---|---|---|
| ☐ | T501 | Fix schema (`FixProposal`, `RegressionRun`) | AC-5.1 |
| ☐ | T502 | Fix proposal generation | AC-5.1 |
| ☐ | T503 | Regenerate affected scenarios + re-run evals | AC-5.2 |
| ☐ | T504 | Before/after report + P0 human-ack guard | AC-5.3, AC-5.4 |

## Phase 6 — Dashboard (US-3, US-6)

Build order per approved UI design; each task leaves the app working with no dead links.

| Status | ID | Task | AC |
|---|---|---|---|
| ☐ | T601 | App shell (roles, nav, status block) + ADR-003 (streamlit) | UI design §App Shell |
| ☐ | T602 | Jobs page | UI design §1 |
| ☐ | T603 | Conversations page | UI design §2 |
| ☐ | T604 | Call Detail page | AC-3.1, AC-3.2 |
| ☐ | T605 | Clusters page | AC-2.3 (links); UI design §4 |
| ☐ | T606 | Review Queue page | AC-4.1 |
| ☐ | T607 | Overview page | AC-6.1, AC-6.2 |
| ☐ | T608 | Fix Workbench page | AC-5.1–5.4 (UI) |

## Phase 7 — Validation & Wrap-up

| Status | ID | Task | AC |
|---|---|---|---|
| ☐ | T701 | Success-metrics verification script/run | Spec §2 |
| ☐ | T702 | README + docs current | — |

## AC Traceability

| Spec AC | Covered by |
|---|---|
| AC-1.1–1.4 | T201–T206 |
| AC-2.1–2.3 | T301–T304, T605 |
| AC-3.1–3.2 | T604 |
| AC-4.1–4.3 | T401–T403, T606 |
| AC-5.1–5.4 | T501–T504, T608 |
| AC-6.1–6.2 | T607 |
| AC-7.1–7.4 | T101–T106 |
