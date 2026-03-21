"""
OSMnx graph wrapper with caching.

This module is a thin facade over integrations/osm/loader.py that re-exports
get_graph() and initialize_graph() and adds two lightweight helpers for
nearest-node lookup and edge-attribute retrieval.
"""

from __future__ import annotations

import logging
from typing import Any

import osmnx as ox

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Re-exports from the OSM loader
# ---------------------------------------------------------------------------
# We import lazily to avoid a hard dependency on the loader at import time
# (makes unit-testing the helpers easier).

def _loader():
    """Lazily import the OSM loader module."""
    try:
        from src.integrations.osm import loader  # type: ignore[attr-defined]
        return loader
    except ImportError:
        logger.warning("src.integrations.osm.loader not available — graph operations will be limited")
        return None


def get_graph():
    """Return the cached OSM graph instance (may be None before initialisation)."""
    loader = _loader()
    if loader is None:
        return None
    # Use sync accessor — loader.get_graph() is async and would return a coroutine
    get_sync = getattr(loader, "get_graph_sync", None)
    if get_sync is not None:
        return get_sync()
    # Fallback: access module-level _graph directly
    return getattr(loader, "_graph", None)


async def initialize_graph():
    """Load (or reload) the OSM graph.  Delegates to the loader."""
    loader = _loader()
    if loader is None:
        logger.error("Cannot initialise graph: loader unavailable")
        return None
    return await loader.initialize_graph()


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

async def get_node_nearest(lat: float, lon: float, graph) -> int:
    """Return the OSM node ID nearest to the given coordinate.

    Args:
        lat:   Latitude in decimal degrees (WGS-84).
        lon:   Longitude in decimal degrees (WGS-84).
        graph: A networkx MultiDiGraph loaded via osmnx.

    Returns:
        Integer node ID, or 0 if the graph is unavailable or the lookup fails.
    """
    if graph is None or graph.number_of_nodes() == 0:
        logger.warning("get_node_nearest: graph is empty or None")
        return 0

    try:
        # ox.nearest_nodes(G, X=lon, Y=lat) — note the (X, Y) = (lon, lat) order.
        node_id = ox.nearest_nodes(graph, lon, lat)
        return int(node_id)
    except Exception:
        logger.exception("ox.nearest_nodes failed for (%.6f, %.6f)", lat, lon)
        return 0


def get_edge_data(graph, u: int, v: int) -> dict:
    """Return edge attributes for the directed edge u → v.

    Extracts: length (m), speed_kph, travel_time (s), name.

    Args:
        graph: networkx MultiDiGraph.
        u:     From-node OSM ID.
        v:     To-node OSM ID.

    Returns a dict with keys:
        length_m, speed_kph, travel_time_s, name
    Falls back to sensible defaults when an attribute is missing.
    """
    if graph is None:
        return _default_edge_data()

    try:
        raw = graph.get_edge_data(u, v)
        if raw is None:
            return _default_edge_data()

        # MultiDiGraph stores edges as {key: {attrs}}.
        attrs: dict[str, Any] = {}
        if isinstance(raw, dict):
            first = next(iter(raw.values()), {})
            attrs = first if isinstance(first, dict) else raw

        # Normalise field names — osmnx uses slightly different names depending
        # on graph type and whether speeds have been imputed.
        length_m = float(attrs.get("length", 200.0) or 200.0)

        # speed_kph is added by ox.add_edge_speeds(); fall back to maxspeed.
        speed_kph = (
            attrs.get("speed_kph")
            or attrs.get("maxspeed")
            or 50.0
        )
        try:
            speed_kph = float(str(speed_kph).split()[0])
        except (ValueError, TypeError):
            speed_kph = 50.0

        # travel_time is added by ox.add_edge_travel_times(); recompute if absent.
        travel_time_s = attrs.get("travel_time")
        if travel_time_s is None:
            travel_time_s = (length_m / (speed_kph / 3.6)) if speed_kph > 0 else 0.0
        travel_time_s = float(travel_time_s)

        name = attrs.get("name")
        if isinstance(name, list):
            name = name[0] if name else None
        if name:
            name = str(name).strip() or None

        return {
            "length_m": round(length_m, 2),
            "speed_kph": round(speed_kph, 1),
            "travel_time_s": round(travel_time_s, 2),
            "name": name,
        }
    except Exception:
        logger.exception("get_edge_data failed for edge (%d, %d)", u, v)
        return _default_edge_data()


def _default_edge_data() -> dict:
    return {
        "length_m": 200.0,
        "speed_kph": 50.0,
        "travel_time_s": 14.4,
        "name": None,
    }
