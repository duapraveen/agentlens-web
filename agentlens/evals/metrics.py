"""Judge quality metrics vs golden ground truth (spec §2, constitution I.2).

Call-level binary classification on golden calls: predicted positive = the
judge flagged any dimension P0/P1; actual positive = an injected ground-truth
label exists. "Combined" metrics add deterministic check triggers to the
prediction, reflecting the system's effective detection (the P0 gate is
deterministic-first). Golden calls without eval records for the requested
judge configuration are excluded and counted in n_missing.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from agentlens.models import Call


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class JudgeQuality:
    """Precision/recall of one judge configuration on the golden set."""

    judge_model: str
    prompt_version: str
    n_golden: int
    n_missing: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    p0_precision: float
    p0_recall: float
    combined_precision: float
    combined_recall: float
    per_mode_recall: dict[str, float] = field(default_factory=dict)


def _call_facts(call: Call, judge_model: str, prompt_version: str) -> tuple[bool, bool, bool]:
    """(judge_flagged, judge_flagged_p0, deterministic_triggered) for one call."""
    records = [
        r
        for r in call.eval_records
        if r.judge_model == judge_model and r.prompt_version == prompt_version
    ]
    flagged = any(r.severity in ("P0", "P1") for r in records)
    flagged_p0 = any(r.severity == "P0" for r in records)
    triggered = any(c.triggered for c in call.check_results)
    return flagged, flagged_p0, triggered


def compute_judge_quality(session: Session, judge_model: str, prompt_version: str) -> JudgeQuality:
    """Compute golden-set precision/recall for one judge configuration."""
    golden = session.query(Call).filter(Call.is_golden).all()
    evaluated = [
        c
        for c in golden
        if any(
            r.judge_model == judge_model and r.prompt_version == prompt_version
            for r in c.eval_records
        )
    ]
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    combined = {"tp": 0, "fp": 0, "fn": 0}
    p0 = {"tp": 0, "fp": 0, "fn": 0}
    mode_totals: dict[str, list[int]] = {}

    for call in evaluated:
        flagged, flagged_p0, triggered = _call_facts(call, judge_model, prompt_version)
        actual = call.ground_truth is not None
        counts[("tp" if flagged else "fn") if actual else ("fp" if flagged else "tn")] += 1
        combined_flagged = flagged or triggered
        if actual and combined_flagged:
            combined["tp"] += 1
        elif actual:
            combined["fn"] += 1
        elif combined_flagged:
            combined["fp"] += 1
        actual_p0 = actual and call.ground_truth is not None and call.ground_truth.severity == "P0"
        if actual_p0 and flagged_p0:
            p0["tp"] += 1
        elif actual_p0:
            p0["fn"] += 1
        elif flagged_p0:
            p0["fp"] += 1
        if call.ground_truth is not None:
            hit, total = mode_totals.setdefault(call.ground_truth.failure_mode, [0, 0])
            mode_totals[call.ground_truth.failure_mode] = [hit + (1 if flagged else 0), total + 1]

    return JudgeQuality(
        judge_model=judge_model,
        prompt_version=prompt_version,
        n_golden=len(golden),
        n_missing=len(golden) - len(evaluated),
        tp=counts["tp"],
        fp=counts["fp"],
        fn=counts["fn"],
        tn=counts["tn"],
        precision=_rate(counts["tp"], counts["tp"] + counts["fp"]),
        recall=_rate(counts["tp"], counts["tp"] + counts["fn"]),
        p0_precision=_rate(p0["tp"], p0["tp"] + p0["fp"]),
        p0_recall=_rate(p0["tp"], p0["tp"] + p0["fn"]),
        combined_precision=_rate(combined["tp"], combined["tp"] + combined["fp"]),
        combined_recall=_rate(combined["tp"], combined["tp"] + combined["fn"]),
        per_mode_recall={mode: _rate(hit, total) for mode, (hit, total) in mode_totals.items()},
    )
