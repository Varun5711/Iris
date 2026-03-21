"""Unit tests for the LLM policy validator — critical safety checks."""
import pytest
from src.modules.policies.validator import (
    validate_copilot_response,
    check_for_direct_actuation,
    score_evidence_quality,
)


SAFE_RESPONSE = {
    "incident_summary": "Multi-vehicle accident on I-405",
    "signal_actions": [
        {
            "intersection_id": "int_01",
            "action": "Consider extending green phase by 20s (advisory only)",
            "expected_impact": "Reduce queue at diversion entry",
            "confidence": 0.8,
        }
    ],
    "diversion_plan": {
        "route_description": "Reroute via SR-99",
        "estimated_extra_minutes": 4.5,
        "traffic_redistribution_pct": 35.0,
        "confidence": 0.75,
        "evidence_refs": ["sensor:seg_001", "camera:cam_005"],
    },
    "alert_drafts": [{"channel": "vms", "message": "ACCIDENT AHEAD USE ALT ROUTE", "char_count": 30}],
    "narrative": "Sensors show severe congestion. Diversion recommended.",
    "overall_confidence": 0.75,
    "review_required": False,
    "blocked_reason": None,
    "evidence_refs": ["sensor:seg_001", "camera:cam_005"],
    "conversational_answer": None,
}


class TestActuationCheck:
    def test_safe_response_passes(self):
        assert check_for_direct_actuation(SAFE_RESPONSE) is False

    def test_direct_actuation_detected(self):
        bad = {**SAFE_RESPONSE, "signal_actions": [
            {"intersection_id": "int_01", "action": "Activate signal phase now", "confidence": 0.9,
             "expected_impact": ""}
        ]}
        assert check_for_direct_actuation(bad) is True

    def test_send_command_detected(self):
        bad = {**SAFE_RESPONSE, "narrative": "Send command to controller to change signal."}
        assert check_for_direct_actuation(bad) is True

    def test_change_signal_detected(self):
        bad = {**SAFE_RESPONSE, "incident_summary": "Change the signal timing immediately."}
        assert check_for_direct_actuation(bad) is True


class TestValidateCopilotResponse:
    def test_valid_response_unchanged(self):
        result = validate_copilot_response(SAFE_RESPONSE)
        assert result["review_required"] is False
        assert result["blocked_reason"] is None

    def test_low_confidence_triggers_review(self):
        low_conf = {**SAFE_RESPONSE, "overall_confidence": 0.4}
        result = validate_copilot_response(low_conf)
        assert result["review_required"] is True

    def test_missing_evidence_triggers_review(self):
        no_evidence = {**SAFE_RESPONSE, "evidence_refs": []}
        result = validate_copilot_response(no_evidence)
        assert result["review_required"] is True

    def test_direct_actuation_sets_blocked_reason(self):
        bad = {**SAFE_RESPONSE, "signal_actions": [
            {"intersection_id": "int_01", "action": "Activate signal phase immediately",
             "confidence": 0.9, "expected_impact": ""}
        ]}
        result = validate_copilot_response(bad)
        assert result["review_required"] is True
        assert result["blocked_reason"] is not None

    def test_confidence_below_threshold_flagged(self):
        for conf in [0.0, 0.3, 0.59]:
            r = validate_copilot_response({**SAFE_RESPONSE, "overall_confidence": conf})
            assert r["review_required"] is True, f"Expected review_required for confidence={conf}"


class TestEvidenceQuality:
    def test_empty_evidence_scores_zero(self):
        assert score_evidence_quality([]) == 0.0

    def test_single_source_scores_low(self):
        assert score_evidence_quality(["sensor:seg_001"]) <= 0.6

    def test_multi_source_scores_higher(self):
        score_single = score_evidence_quality(["sensor:seg_001"])
        score_multi  = score_evidence_quality(["sensor:seg_001", "camera:cam_005", "radio:unit7"])
        assert score_multi > score_single
