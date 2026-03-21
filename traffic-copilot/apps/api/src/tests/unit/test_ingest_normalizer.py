"""Unit tests for the ingest normalizer."""
import pytest
from datetime import datetime
from src.modules.ingest.normalizer import normalize_event


class TestNormalizeSensor:
    def test_valid_sensor_event(self):
        raw = {
            "segment_id": "seg_001",
            "speed_kmh": 12.0,
            "free_flow_kmh": 90.0,
            "occupancy_pct": 0.88,
            "lat": 34.05,
            "lon": -118.24,
            "corridor_id": "i405_nb",
        }
        event = normalize_event("sensor", raw)
        assert event.source == "sensor"
        assert event.speed_kmh == 12.0
        assert event.lat == pytest.approx(34.05)
        assert event.event_id is not None
        assert isinstance(event.event_time, datetime)

    def test_missing_speed_raises(self):
        with pytest.raises((ValueError, KeyError, AttributeError)):
            normalize_event("sensor", {"segment_id": "seg_001"})


class TestNormalizeCamera:
    def test_valid_camera_event(self):
        raw = {
            "camera_id": "cam_005",
            "lane_blocked": True,
            "vehicle_count": 42,
            "incident_detected": True,
            "confidence": 0.91,
            "lat": 34.05,
            "lon": -118.24,
        }
        event = normalize_event("camera", raw)
        assert event.source == "camera"
        assert event.lane_blocked is True
        assert event.confidence == pytest.approx(0.91)


class TestNormalizeRadio:
    def test_valid_radio_event(self):
        raw = {
            "transcript": "Unit 7 on scene, two vehicles blocking lane",
            "unit_id": "unit_7",
        }
        event = normalize_event("radio", raw)
        assert event.source == "radio"
        assert "Unit 7" in event.transcript


class TestNormalizeManual:
    def test_valid_manual_event(self):
        raw = {
            "severity": "high",
            "description": "Multi-vehicle accident",
            "reporter_id": "officer_42",
            "lat": 34.05,
            "lon": -118.24,
            "corridor_id": "i405_nb",
        }
        event = normalize_event("manual", raw)
        assert event.source == "manual"
        assert event.severity == "high"
        assert event.reporter_id == "officer_42"

    def test_unknown_source_raises(self):
        with pytest.raises((ValueError, KeyError)):
            normalize_event("unknown_source", {})
