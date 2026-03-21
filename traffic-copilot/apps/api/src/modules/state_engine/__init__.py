"""Traffic state estimation pipeline."""
from src.modules.state_engine.deduper import is_duplicate
from src.modules.state_engine.map_matcher import snap_to_segment
from src.modules.state_engine.queue_estimator import estimate_delay, classify_congestion
from src.modules.state_engine.corridor import compute_affected_corridor, get_nearby_intersections
__all__ = ["is_duplicate", "snap_to_segment", "estimate_delay", "classify_congestion", "compute_affected_corridor", "get_nearby_intersections"]
