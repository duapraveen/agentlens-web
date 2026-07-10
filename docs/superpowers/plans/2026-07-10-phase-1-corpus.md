# Phase 1 — Synthetic Corpus & Golden Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US-7 (as re-scoped 2026-07-10) — 50–60 **short** labeled synthetic patient↔agent transcripts (≈1–2 minutes of spoken conversation each, ≈6–12 short turns) across 5 scenarios with ~30% injected failures drawn from 6 modes, plus a frozen, stratified golden set (≥50 calls — 50 of the 60) committed to `data/golden/` (append-only).

**Architecture:** A fixed taxonomy module (`corpus/scenarios.py`) maps each failure mode to pipeline stage, severity, dimension, and a prompt injection instruction. The generator makes one gateway call per transcript (`claude-sonnet-5`, Pydantic-validated turns) and persists `Call` + optional `GroundTruthLabel`. Batch jobs live in `agentlens/jobs/` with structlog JSON lines to stdout and `logs/jobs.log` (IDs only — never transcript text). Failure assignment is deterministic per seed: exactly `round(count × rate)` failures, scenarios and modes cycled evenly.

**Tech Stack:** Everything from Phase 0; no new dependencies.

**Tasks:** T101–T106 from `specs/001-agentlens-core/tasks.md`. T101–T105 run fully mocked (zero spend). T106 is the real generation run — **requires explicit user approval (~$0.50–1)**.

## Global Constraints

Same as Phase 0 (mypy --strict, ruff, gateway-only LLM access, redaction, no transcript text in logs, ORM only, `llm` marker gating, Conventional Commits with task IDs and the Co-Authored-By trailer). Additional for this phase:

- `data/golden/` is append-only from the moment T106 lands; the freeze job must never overwrite an existing file.
- Enum string values are stored in the DB — never rename members after T106.

---

### Task 1: Scenario & failure-mode taxonomy (T101)

**Files:**
- Create: `agentlens/corpus/__init__.py`, `agentlens/corpus/scenarios.py`
- Test: `tests/test_scenarios.py`

**Interfaces:**
- Produces `Scenario` (5 members), `FailureMode` (6), `PipelineStage` (4), `Severity` (P0/P1/P2), `Dimension` (4) — all `StrEnum`; `FailureModeInfo` dataclass (`stage`, `severity`, `dimension`, `injection_instruction`); `FAILURE_MODE_INFO: dict[FailureMode, FailureModeInfo]`; `SCENARIO_DESCRIPTIONS: dict[Scenario, str]`. Imported by T102–T105 and by phases 2–3.

- [ ] **Step 1: Write the failing tests** — `tests/test_scenarios.py` asserting: the exact 5 scenario values and 6 failure-mode values from spec AC-7.1/7.2; every mode has complete info (typed stage/severity/dimension, injection instruction > 20 chars); P0 set == {missed_escalation, unnecessary_phi_readback}; the exact 4 dimensions and 4 stages from AC-1.1.
- [ ] **Step 2: Run to verify failure** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `scenarios.py` — enums with values `appointment_scheduling / symptom_triage / insurance_eligibility / prescription_refill / referral_navigation`; `transcription_noise_identifier / hallucinated_availability / wrong_retrieval / missed_escalation / unnecessary_phi_readback / dead_end_loop`; stage/severity/dimension mapping: transcription_noise→(transcription,P1,factual_accuracy), hallucinated_availability→(reasoning,P1,factual_accuracy), wrong_retrieval→(retrieval,P1,factual_accuracy), missed_escalation→(reasoning,P0,safety_compliance), unnecessary_phi_readback→(orchestration,P0,safety_compliance), dead_end_loop→(orchestration,P1,task_completion); realistic injection instructions per mode; one-line scenario descriptions.
- [ ] **Step 4: Verify** — tests pass; ruff/mypy clean.
- [ ] **Step 5: Commit** `feat: scenario and failure-mode taxonomy (specs/001-agentlens-core/tasks.md#T101)`.

### Task 2: Versioned corpus generation prompt (T102)

**Files:**
- Create: `agentlens/prompts/__init__.py`, `agentlens/prompts/corpus_generation.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Produces `PROMPT_NAME = "corpus_generation"`, `PROMPT_VERSION = "1.0"`, `SYSTEM_PROMPT: str`, `build_user_prompt(scenario, failure_mode | None) -> str`.

- [ ] **Step 1: Failing tests** — clean prompt mentions the scenario description and contains no injection language; injected prompt contains the mode's injection instruction and tells the model not to label the defect.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — system prompt: realistic spoken healthcare call, fictional details only, **short call of about one to two minutes of spoken time: 6–12 strictly alternating brief turns**, starting with the agent, JSON per requested schema. User prompt: scenario description + either "handled correctly" or the injection instruction framed as an unlabeled production defect.
- [ ] **Step 4: Verify** — tests/ruff/mypy clean.
- [ ] **Step 5: Commit** `feat: versioned corpus generation prompt (specs/001-agentlens-core/tasks.md#T102)`.

### Task 3: Transcript generator (T103)

**Files:**
- Create: `agentlens/corpus/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Produces `TranscriptTurn` (`speaker: Literal["patient","agent"]`, `text: str`), `TranscriptOutput` (`turns`, min 6 / max 16 — tolerance above the prompted 6–12), and `generate_call(session, scenario, failure_mode, batch_id, *, model=None, client=None) -> Call | None` — one gateway call; on success commits `Call` (+ `GroundTruthLabel` when a failure was injected) and returns it; on gateway failure returns `None` (failure already recorded in `llm_call_log`). Gateway is invoked **before** staging objects (gateway commits).

- [ ] **Step 1: Failing tests** — mocked `complete_json`: clean call persists Call with 8 turns and no label; failure call persists label with correct mode/stage/severity; gateway failure → None and nothing persisted; `TranscriptOutput` rejects < 6 and > 16 turns; plus an `llm`-marked real-generation smoke test (not run).
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** with `call_{uuid4().hex[:12]}` IDs, `transcript=[turn.model_dump() for ...]`.
- [ ] **Step 4: Verify** fast suite; ruff/mypy clean. Do **not** run `-m llm`.
- [ ] **Step 5: Commit** `feat: transcript generator (specs/001-agentlens-core/tasks.md#T103)`.

### Task 4: Corpus generation job (T104)

**Files:**
- Create: `agentlens/jobs/__init__.py`, `agentlens/jobs/_logging.py`, `agentlens/jobs/generate_corpus.py`
- Test: `tests/test_generate_corpus_job.py`

**Interfaces:**
- Produces `configure_job_logging(log_path) -> BoundLogger` (JSON lines to stdout + appended to log file); `plan_assignments(count, failure_rate, seed) -> list[tuple[Scenario, FailureMode | None]]` (pure, deterministic, exactly `round(count×rate)` failures, scenarios/modes cycled evenly); `main(argv) -> int` with `--count 60 --failure-rate 0.3 --seed N` (defaults), runnable via `python -m agentlens.jobs.generate_corpus`. Writes a `JobRun` row with summary `{batch_id, requested, generated, failed, duration_ms}`.

- [ ] **Step 1: Failing tests** — `plan_assignments` deterministic per seed, exact failure count, full scenario/mode coverage; `main` with stubbed `generate_call` (uuid-based fake IDs): JobRun completed with correct summary; all-failure path counts correctly; log file written under `AGENTLENS_JOBS_LOG_PATH`. Env-driven via monkeypatched `AGENTLENS_DATABASE_URL` (file-backed tmp SQLite).
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — argparse; seeded `random.Random`; shuffled cycled scenarios; `rng.sample` for failure indices; modes via `cycle(sorted(FailureMode))`; per-call structlog events (`call_generated` with call_id/scenario/failure_mode only); JobRun bookkeeping.
- [ ] **Step 4: Verify** full fast suite; ruff/mypy clean.
- [ ] **Step 5: Commit** `feat: corpus generation batch job (specs/001-agentlens-core/tasks.md#T104)`.

### Task 5: Golden-set freeze job (T105)

**Files:**
- Create: `agentlens/jobs/freeze_golden.py`
- Test: `tests/test_freeze_golden_job.py`

**Interfaces:**
- Produces `select_golden(calls, count) -> list[Call]` (pure, stratified round-robin over `(scenario, failure_mode-or-clean)` groups, deterministic ordering) and `main(argv) -> int` with `--count 50` (default): marks selections `is_golden=True`, exports `{call_id}.json` (`{"call": {...}, "ground_truth": {...}|null}`) to `settings.golden_dir`, **never overwrites existing files**, records a `JobRun`.

- [ ] **Step 1: Failing tests** — stratification covers all populated groups; caps at corpus size; `main` marks 50 golden, exports 50 files with the right shape, completes JobRun; re-run leaves existing files byte-identical (append-only).
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Verify** full fast suite; ruff/mypy clean.
- [ ] **Step 5: Commit** `feat: golden-set freeze job (specs/001-agentlens-core/tasks.md#T105)`.

### Task 6: Corpus run + golden commit (T106) — REQUIRES USER APPROVAL

- [ ] **Step 1: Get explicit approval** for spend: `uv run pytest -m llm` (~$0.02) + `python -m agentlens.jobs.generate_corpus --count 60 --failure-rate 0.3 --seed 42` (~$0.50–1, a few minutes).
- [ ] **Step 2: Run the llm smoke tests**, then the generation job; verify counts in DB (60 requested, failures = 18, all 5 scenarios, all 6 modes).
- [ ] **Step 3: Freeze** — `python -m agentlens.jobs.freeze_golden --count 50`; verify 50 files in `data/golden/` and stratification.
- [ ] **Step 4: Commit** `eval: freeze golden set v1 (specs/001-agentlens-core/tasks.md#T106)` including `data/golden/`.

## Phase 1 Exit Gate

- AC-7.1: 50–60 short calls (≈1–2 min each) across the 5 spec scenarios ✓ (verified by DB query)
- AC-7.2: ~30% carry injected failures across the 6 spec modes ✓
- AC-7.3: ground truth (mode, stage, severity) in `ground_truth_labels`, separate from eval outputs, and in the golden JSON export ✓
- AC-7.4: ≥50-call frozen labeled subset (50 of 60) committed to `data/golden/`, append-only ✓
- Fast suite, ruff, mypy clean; `tasks.md` statuses updated.
