"""Unit tests for the incident detector rules and scorer."""
import pytest
from src.modules.detector.rules import (
    score_sensor_event,
    score_camera_event,
    score_radio_event,
    score_manual_event,
    score_event,
)
from src.modules.detector.scorer import IncidentScorer


class TestSensorScoring:
    def test_gridlock_scores_high(self):
        event = {"speed_kmh": 5.0, "free_flow_kmh": 90.0, "occupancy_pct": 0.95}
        score = score_sensor_event(event)
        assert score >= 0.7, f"Expected >= 0.7 for gridlock, got {score}"

    def test_free_flow_scores_zero(self):
        event = {"speed_kmh": 88.0, "free_flow_kmh": 90.0, "occupancy_pct": 0.1}
        score = score_sensor_event(event)
        assert score == 0.0, f"Expected 0.0 for free flow, got {score}"

    def test_moderate_congestion_mid_range(self):
        event = {"speed_kmh": 35.0, "free_flow_kmh": 90.0, "occupancy_pct": 0.5}
        score = score_sensor_event(event)
        assert 0.0 < score < 1.0

    def test_score_clamped_to_unit_interval(self):
        event = {"speed_kmh": 0.1, "free_flow_kmh": 100.0, "occupancy_pct": 1.0}
        score = score_sensor_event(event)
        assert 0.0 <= score <= 1.0


class TestCameraScoring:
    def test_blocked_lane_with_high_confidence(self):
        event = {"lane_blocked": True, "incident_detected": True, "confidence": 0.95}
        score = score_camera_event(event)
        assert score > 0.5

    def test_no_blockage_scores_low(self):
        event = {"lane_blocked": False, "incident_detected": False, "confidence": 0.1}
        score = score_camera_event(event)
        assert score <= 0.2

    def test_score_in_unit_interval(self):
        event = {"lane_blocked": True, "incident_detected": True, "confidence": 1.0}
        assert 0.0 <= score_camera_event(event) <= 1.0


class TestRadioScoring:
    def test_strong_keyword_scores_high(self):
        event = {"transcript": "Major accident on I-405, multiple vehicles"}
        score = score_radio_event(event)
        assert score >= 0.3

    def test_empty_transcript_scores_zero(self):
        event = {"transcript": ""}
        score = score_radio_event(event)
        assert score == 0.0

    def test_irrelevant_transcript_scores_low(self):
        event = {"transcript": "Unit 4 requesting coffee break"}
        score = score_radio_event(event)
        assert score < 0.3


class TestManualScoring:
    def test_manual_always_high(self):
        score = score_manual_event({})
        assert score >= 0.8


class TestScoreEventDispatch:
    def test_dispatches_sensor(self):
        event = type("E", (), {
            "source": "sensor", "speed_kmh": 5.0, "free_flow_kmh": 90.0,
            "occupancy_pct": 0.9, "transcript": None, "lane_blocked": None,
            "incident_detected": None, "confidence": None,
        })()
        score = score_event(event)
        assert 0.0 <= score <= 1.0

    def test_dispatches_manual(self):
        event = type("E", (), {"source": "manual"})()
        assert score_event(event) >= 0.8

    def test_unknown_source_returns_zero(self):
        event = type("E", (), {"source": "unknown_source"})()
        assert score_event(event) == 0.0


class TestIncidentScorer:
    def test_score_accumulates(self):
        scorer = IncidentScorer(decay_seconds=300)
        scorer.add_signal("e1", 0.8)
        scorer.add_signal("e2", 0.6)
        assert scorer.current_score() > 0.0

    def test_deduplication(self):
        scorer = IncidentScorer(decay_seconds=300)
        scorer.add_signal("e1", 0.9)
        scorer.add_signal("e1", 0.9)  # same event_id
        # Score should not double-count
        s1 = scorer.current_score()
        scorer2 = IncidentScorer(decay_seconds=300)
        scorer2.add_signal("e1", 0.9)
        assert abs(s1 - scorer2.current_score()) < 0.01

    def test_clear_resets_score(self):
        scorer = IncidentScorer(decay_seconds=300)
        scorer.add_signal("e1", 0.9)
        scorer.clear()
        assert scorer.current_score() == 0.0
