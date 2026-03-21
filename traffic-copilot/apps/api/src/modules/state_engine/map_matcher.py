"""
Map-matching: snap a raw GPS lat/lon to the nearest OSM road segment.

Uses osmnx.nearest_edges() which returns the (u, v, key) tuple for the
closest MultiDiGraph edge to the given point.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import osmnx as ox

logger = logging.getLogger(__name__)

# Approximate metres per degree of latitude (good enough for distances < 1 km).
_METRES_PER_LAT_DEGREE = 111_320.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


async def snap_to_segment(lat: float, lon: float, graph) -> dict:
    """Snap a GPS coordinate to the nearest OSM road edge.

    Args:
        lat:   Latitude in decimal degrees (WGS-84).
        lon:   Longitude in decimal degrees (WGS-84).
        graph: A networkx MultiDiGraph loaded via osmnx.

    Returns a dict with:
        osm_way_id    – OSM way identifier stored in edge data (int or 0).
        osm_node_u    – From-node of the nearest edge.
        osm_node_v    – To-node of the nearest edge.
        snapped_lat   – Latitude of the midpoint of the matched edge.
        snapped_lon   – Longitude of the midpoint of the matched edge.
        distance_m    – Distance from input point to the edge midpoint.
        road_name     – Human-readable road name or None.
    """
    if graph is None or graph.number_of_edges() == 0:
        logger.warning("snap_to_segment: empty graph — returning fallback")
        return _fallback_snap(lat, lon)

    try:
        # nearest_edges returns (u, v, key) for the closest edge.
        u, v, _key = ox.nearest_edges(graph, lon, lat)  # note: osmnx takes (X=lon, Y=lat)
    except Exception:
        logger.exception("ox.nearest_edges failed for (%.6f, %.6f)", lat, lon)
        return _fallback_snap(lat, lon)

    edge_data = _get_edge_dict(graph, u, v)

    # Compute snapped position as the midpoint of u and v node coordinates.
    try:
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        snapped_lat = (u_data["y"] + v_data["y"]) / 2.0
        snapped_lon = (u_data["x"] + v_data["x"]) / 2.0
        distance_m = _haversine_m(lat, lon, snapped_lat, snapped_lon)
    except (KeyError, TypeError):
        snapped_lat, snapped_lon, distance_m = lat, lon, 0.0

    # Extract OSM way ID from the edge — it may be a list (multiple ways share edge).
    osm_way_id = _extract_osm_id(edge_data.get("osmid", 0))
    road_name = await get_road_name(graph, u, v)

    return {
        "osm_way_id": osm_way_id,
        "osm_node_u": int(u),
        "osm_node_v": int(v),
        "snapped_lat": snapped_lat,
        "snapped_lon": snapped_lon,
        "distance_m": round(distance_m, 2),
        "road_name": road_name,
    }


async def get_road_name(graph, u: int, v: int) -> str | None:
    """Extract human-readable road name from an OSM edge (u→v).

    Checks the 'name' attribute on the edge; returns None if absent or blank.
    When the value is a list (OSM sometimes returns multiple names), returns
    the first non-empty entry.
    """
    edge_data = _get_edge_dict(graph, u, v)
    raw = edge_data.get("name")
    if raw is None:
        return None
    if isinstance(raw, list):
        for item in raw:
            if item and str(item).strip():
                return str(item).strip()
        return None
    name = str(raw).strip()
    return name if name else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_edge_dict(graph, u: int, v: int) -> dict[str, Any]:
    """Return a flat attribute dict for edge u→v (first key if multi-edge)."""
    if graph is None:
        return {}
    try:
        edge_data = graph.get_edge_data(u, v)
        if edge_data is None:
            return {}
        # MultiDiGraph stores edges as {key: {attrs}}, pick key 0.
        if isinstance(edge_data, dict):
            inner = next(iter(edge_data.values()), {})
            if isinstance(inner, dict):
                return inner
            return edge_data  # flat dict (DiGraph)
        return {}
    except Exception:
        return {}


def _extract_osm_id(osmid: Any) -> int:
    """Return a single integer OSM way ID from whatever osmnx gives us."""
    if osmid is None:
        return 0
    if isinstance(osmid, (int, float)):
        return int(osmid)
    if isinstance(osmid, list):
        for item in osmid:
            try:
                return int(item)
            except (TypeError, ValueError):
                continue
        return 0
    try:
        return int(osmid)
    except (TypeError, ValueError):
        return 0


def _fallback_snap(lat: float, lon: float) -> dict:
    """Return a minimal fallback result when the graph is unavailable."""
    return {
        "osm_way_id": 0,
        "osm_node_u": 0,
        "osm_node_v": 0,
        "snapped_lat": lat,
        "snapped_lon": lon,
        "distance_m": 0.0,
        "road_name": None,
    }
