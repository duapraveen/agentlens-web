"""Tests for the scenario/failure taxonomy (AC-7.1, AC-7.2, constitution V.4)."""

from agentlens.corpus.scenarios import (
    FAILURE_MODE_INFO,
    SCENARIO_DESCRIPTIONS,
    Dimension,
    FailureMode,
    PipelineStage,
    Scenario,
    Severity,
)


def test_five_scenarios_from_spec() -> None:
    assert {s.value for s in Scenario} == {
        "appointment_scheduling",
        "symptom_triage",
        "insurance_eligibility",
        "prescription_refill",
        "referral_navigation",
    }
    assert set(SCENARIO_DESCRIPTIONS) == set(Scenario)


def test_six_failure_modes_from_spec() -> None:
    assert {f.value for f in FailureMode} == {
        "transcription_noise_identifier",
        "hallucinated_availability",
        "wrong_retrieval",
        "missed_escalation",
        "unnecessary_phi_readback",
        "dead_end_loop",
    }


def test_every_failure_mode_has_complete_info() -> None:
    assert set(FAILURE_MODE_INFO) == set(FailureMode)
    for info in FAILURE_MODE_INFO.values():
        assert isinstance(info.stage, PipelineStage)
        assert isinstance(info.severity, Severity)
        assert isinstance(info.dimension, Dimension)
        assert len(info.injection_instruction) > 20


def test_p0_safety_modes() -> None:
    p0 = {mode for mode, info in FAILURE_MODE_INFO.items() if info.severity is Severity.P0}
    assert p0 == {FailureMode.MISSED_ESCALATION, FailureMode.UNNECESSARY_PHI_READBACK}


def test_four_dimensions_and_stages() -> None:
    assert {d.value for d in Dimension} == {
        "task_completion",
        "factual_accuracy",
        "safety_compliance",
        "communication_quality",
    }
    assert {p.value for p in PipelineStage} == {
        "transcription",
        "retrieval",
        "reasoning",
        "orchestration",
    }
