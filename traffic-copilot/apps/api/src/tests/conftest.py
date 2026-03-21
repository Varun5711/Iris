"""Shared pytest fixtures for TrafficCopilot tests."""
import pytest


@pytest.fixture
def sample_sensor_payload():
    return {
        "segment_id": "test_seg_001",
        "speed_kmh": 10.0,
        "free_flow_kmh": 90.0,
        "occupancy_pct": 0.92,
        "lat": 34.0522,
        "lon": -118.2437,
        "corridor_id": "test_corridor",
    }


@pytest.fixture
def sample_camera_payload():
    return {
        "camera_id": "test_cam_001",
        "lane_blocked": True,
        "vehicle_count": 55,
        "incident_detected": True,
        "confidence": 0.88,
        "lat": 34.0522,
        "lon": -118.2437,
    }


@pytest.fixture
def sample_manual_payload():
    return {
        "severity": "high",
        "description": "Test incident: multi-vehicle accident",
        "reporter_id": "test_officer",
        "lat": 34.0522,
        "lon": -118.2437,
        "corridor_id": "test_corridor",
    }


@pytest.fixture
def safe_copilot_response():
    return {
        "incident_summary": "Test incident on test corridor",
        "signal_actions": [
            {
                "intersection_id": "int_test_01",
                "action": "Consider extending green phase by 15s (advisory only)",
                "expected_impact": "Reduce queue buildup",
                "confidence": 0.8,
            }
        ],
        "diversion_plan": {
            "route_description": "Reroute via alternative road",
            "estimated_extra_minutes": 3.0,
            "traffic_redistribution_pct": 25.0,
            "confidence": 0.7,
            "evidence_refs": ["sensor:test_seg_001"],
        },
        "alert_drafts": [
            {"channel": "vms", "message": "INCIDENT AHEAD USE ALT ROUTE", "char_count": 29}
        ],
        "narrative": "Test incident narrative.",
        "overall_confidence": 0.75,
        "review_required": False,
        "blocked_reason": None,
        "evidence_refs": ["sensor:test_seg_001"],
        "conversational_answer": None,
    }
