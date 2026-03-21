"""Unit tests for the BPR queue estimation model."""
import pytest
from src.modules.state_engine.queue_estimator import estimate_delay, classify_congestion


class TestEstimateDelay:
    def test_free_flow_no_delay(self):
        result = estimate_delay(speed_kmh=90.0, free_flow_kmh=90.0)
        assert result["congestion_pct"] == pytest.approx(0.0, abs=1e-3)
        assert result["delay_seconds"] == pytest.approx(0.0, abs=1e-3)

    def test_gridlock_high_congestion(self):
        result = estimate_delay(speed_kmh=2.0, free_flow_kmh=90.0)
        assert result["congestion_pct"] > 90.0

    def test_delay_increases_with_congestion(self):
        mild   = estimate_delay(50.0, 90.0)
        severe = estimate_delay(10.0, 90.0)
        assert severe["delay_seconds"] > mild["delay_seconds"]

    def test_zero_speed_handled(self):
        result = estimate_delay(speed_kmh=0.0, free_flow_kmh=90.0)
        assert result["congestion_pct"] <= 100.0
        assert result["delay_seconds"] >= 0.0

    def test_returns_required_keys(self):
        result = estimate_delay(40.0, 90.0)
        assert "congestion_pct" in result
        assert "delay_seconds" in result
        assert "queue_length_m" in result


class TestClassifyCongestion:
    def test_gridlock_label(self):
        assert classify_congestion(95.0) == "gridlock"

    def test_free_flow_label(self):
        assert classify_congestion(5.0) == "free_flow"

    def test_moderate_label(self):
        label = classify_congestion(50.0)
        assert label in ("moderate", "heavy")

    def test_all_outputs_are_strings(self):
        for pct in [0, 15, 40, 60, 80, 95, 100]:
            assert isinstance(classify_congestion(float(pct)), str)
