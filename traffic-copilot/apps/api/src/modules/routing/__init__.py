"""Traffic routing module."""
from src.modules.routing.diversion import compute_diversion_routes, estimate_redistribution
from src.modules.routing.graph import get_node_nearest, get_edge_data
__all__ = ["compute_diversion_routes", "estimate_redistribution", "get_node_nearest", "get_edge_data"]
