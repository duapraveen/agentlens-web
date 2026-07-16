# Review Queue: Per-Score Review

Date: 2026-07-15
Status: Approved
Spec: 001-agentlens-core
Amends: [2026-07-10-ui-design.md](2026-07-10-ui-design.md) §5 Review Queue, [2026-07-13-streamlit-to-web-migration-design.md](2026-07-13-streamlit-to-web-migration-design.md)

---

## Problem

The Review Queue currently surfaces one flagged (failing) `EvalRecord` at a time, with a single Agree/Disagree verdict for that one record. The reviewer never sees the call's other three dimension scores while reviewing, and cannot challenge a judge verdict on a dimension that *passed* — only on the one dimension that happened to fail and get queued.

## Change

The Review Queue now operates at the **call** level instead of the **record** level:

- When a call has an unreviewed failing finding, the reviewer sees **all four dimension scores for that call**, rendered as foldouts identical in structure to the Call Detail page (dimension · score · severity badge · pass/fail · stage, expanding to judge reasoning, finding, deterministic checks, and provenance).
- **Every foldout carries its own verdict controls** (Agree / Disagree + optional note), not just the one that failed — a reviewer can also record disagreement with a dimension the judge scored as passing. Submitting a verdict on one dimension does not require or block submitting verdicts on the others.
- The queue advances to the next call once every *failing* dimension for the current call has a review (matching today's semantics of "the queue is driven by unreviewed failures" — passing-dimension reviews are optional additions, not a gate on advancement).

## Non-Goals

- No change to `AgreementStats`/calibration math — it already aggregates over all `Review` rows regardless of which dimension or pass/fail state they're attached to, so reviewing a passing dimension already contributes correctly with no backend changes to `feedback/calibration.py`.
- No change to the `Review` model or `submit_review()` — both already operate per `eval_record_id` with resubmission-updates-in-place semantics, which is exactly what per-score, resubmittable verdicts need.
- No bulk/batch submit UI — each foldout submits independently, matching the plan's YAGNI stance.

## Design

**Backend:**
- `agentlens/feedback/queue.py`: add `next_call_id_for_review(session) -> str | None`, returning the `call_id` of the first entry in the existing `review_queue()` ordering (unreviewed-first, then P0 > P1 > P2, then id) that has no review yet. `None` when the queue is empty.
- `agentlens/api/schemas.py`: replace `FindingOut` with `ReviewOut` (verdict, note) + `ScoredRecordOut` (all `EvalRecordOut` fields plus a nested `review: ReviewOut | None`) + `CallReviewOut` (call_id, scenario, transcript, checks, `records: list[ScoredRecordOut]`). `ReviewQueueOut.current` becomes `CallReviewOut | None`.
- `agentlens/api/routers/review_queue.py`: `_current_queue()` calls `next_call_id_for_review()`, then reuses `dashboard/data.py::call_detail()` (unchanged) to bundle that call's records/checks/transcript. The `POST /api/review-queue/{eval_record_id}` endpoint is unchanged — it already takes an arbitrary `eval_record_id`, so submitting a verdict on any of the four displayed records (not just the originally-flagged one) works with zero endpoint changes.

**Frontend (`ReviewQueue.tsx`):**
- Render `current.records` as `<details>` foldouts, matching `CallDetail.tsx`'s structure and severity left-edge/dot treatment (Task-18-era UI polish) for visual consistency between the two pages.
- Each foldout gets its own local verdict/note state and its own `useMutation` call to `POST /api/review-queue/{eval_record_id}`, mirroring the existing single-record submit flow but multiplied per record.
- The page-level "queue clear" empty state and the agreement-stats panel are unchanged.

## Acceptance Criteria

- AC-1: Visiting the Review Queue while a call has an unreviewed failing dimension shows all of that call's dimension scores as expandable foldouts, not just the failing one.
- AC-2: Every foldout has its own Agree/Disagree + note controls; submitting one does not affect or require the others.
- AC-3: A reviewer can submit a verdict on a *passing* dimension's foldout, and it is recorded via the existing `submit_review()`/`Review` model with no schema change.
- AC-4: The queue advances to the next call only once every failing dimension of the current call has a submitted review.
- AC-5: Existing `AgreementStats` continue to reflect all submitted reviews, including ones on passing dimensions, with no calibration-math changes required.
