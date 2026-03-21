"""
NetworkX k-shortest-path diversion route computation.

Finds up to k alternative paths between an origin and destination node
while excluding a set of blocked edges (e.g. the incident location).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import networkx as nx
from shapely.geometry import LineString, mapping

logger = logging.getLogger(__name__)

# Weight attribute used for shortest-path computation.
_WEIGHT_ATTR = "travel_time"

# Fallback travel speed when edge weight is missing.
_FALLBACK_SPEED_MS = 50.0 / 3.6  # 50 km/h in m/s

# Maximum candidate paths to explore before returning k results.
_MAX_CANDIDATES = 50


async def compute_diversion_routes(
    origin_node: int,
    destination_node: int,
    graph,
    blocked_edges: list[tuple[int, int]],
    k: int = 3,
) -> list[dict]:
    """Compute up to k shortest diversion paths avoiding blocked_edges.

    Uses a temporary copy of the graph with blocked edges removed so that
    networkx.shortest_simple_paths() (Yen's algorithm internally) only
    considers valid road segments.

    Args:
        origin_node:      Starting OSM node ID.
        destination_node: Target OSM node ID.
        graph:            networkx MultiDiGraph loaded via osmnx.
        blocked_edges:    List of (u, v) tuples that must not be used.
        k:                Maximum number of alternative routes to return.

    Returns a list of route dicts (up to k), each containing:
        path_nodes       – Ordered list of OSM node IDs.
        route_geojson    – GeoJSON LineString of the route coordinates.
        distance_m       – Total route length in metres.
        estimated_minutes – Estimated travel time in minutes.
        road_names       – Distinct road names along the route (ordered).
    """
    if graph is None or graph.number_of_nodes() == 0:
        logger.warning("compute_diversion_routes: graph unavailable")
        return []

    if origin_node not in graph or destination_node not in graph:
        logger.warning(
            "compute_diversion_routes: node %d or %d not in graph",
            origin_node, destination_node,
        )
        return []

    if origin_node == destination_node:
        return []

    # Build a working copy with blocked edges removed.
    work_graph = _build_graph_without_edges(graph, blocked_edges)

    # Ensure the weight attribute exists on all edges.
    _ensure_weight_attr(work_graph)

    routes: list[dict] = []
    try:
        path_generator = nx.shortest_simple_paths(
            work_graph,
            origin_node,
            destination_node,
            weight=_WEIGHT_ATTR,
        )
        for i, path in enumerate(path_generator):
            if len(routes) >= k or i >= _MAX_CANDIDATES:
                break
            route = _build_route_dict(path, work_graph)
            routes.append(route)
    except nx.NetworkXNoPath:
        logger.info(
            "No path from %d to %d after blocking %d edges",
            origin_node, destination_node, len(blocked_edges),
        )
    except nx.NodeNotFound as exc:
        logger.warning("compute_diversion_routes NodeNotFound: %s", exc)
    except Exception:
        logger.exception("Unexpected error in compute_diversion_routes")

    logger.info(
        "compute_diversion_routes: found %d/%d routes (blocked=%d edges)",
        len(routes), k, len(blocked_edges),
    )
    return routes


def estimate_redistribution(
    primary_volume: float,
    diversion_capacity: float,
    diversion_count: int,
) -> float:
    """Estimate the percentage of traffic that will shift to diversion routes.

    Uses a simple capacity-constrained model:
      - If the diversion network has enough capacity, all diverted traffic
        can be absorbed.
      - Otherwise the fraction is capped at available capacity / demand.

    Args:
        primary_volume:    Vehicles per hour currently using the primary route.
        diversion_capacity: Total capacity available on diversion routes (veh/h).
        diversion_count:   Number of viable diversion routes found.

    Returns a float between 0 and 100 representing the estimated percentage of
    primary route traffic that will use alternative routes.
    """
    if primary_volume <= 0:
        return 0.0
    if diversion_count <= 0 or diversion_capacity <= 0:
        return 0.0

    # Base redistribution: how much capacity do we have vs demand?
    capacity_ratio = min(1.0, diversion_capacity / primary_volume)

    # Each additional diversion route increases uptake slightly (up to a cap).
    route_bonus = min(0.15 * (diversion_count - 1), 0.30)

    redistribution = min(1.0, capacity_ratio + route_bonus) * 100.0
    return round(redistribution, 1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_graph_without_edges(
    graph,
    blocked_edges: list[tuple[int, int]],
) -> nx.DiGraph:
    """Return a DiGraph copy of *graph* with all *blocked_edges* removed.

    OSMnx graphs are MultiDiGraph; nx.shortest_simple_paths requires a
    plain DiGraph.  Parallel edges are collapsed by keeping the one with
    the smallest travel_time weight.
    """
    # Convert MultiDiGraph → DiGraph, keeping min-weight parallel edge.
    dg = nx.DiGraph()
    dg.add_nodes_from(graph.nodes(data=True))
    for u, v, data in graph.edges(data=True):
        if (u, v) in [(bu, bv) for bu, bv in blocked_edges]:
            continue
        weight = data.get(_WEIGHT_ATTR, float("inf"))
        if dg.has_edge(u, v):
            if weight < dg[u][v].get(_WEIGHT_ATTR, float("inf")):
                dg[u][v].update(data)
        else:
            dg.add_edge(u, v, **data)
    return dg


def _ensure_weight_attr(graph: nx.DiGraph) -> None:
    """Add a *travel_time* weight to any edge that is missing one.

    Computes travel_time = length / speed where speed defaults to 50 km/h.
    """
    for u, v, data in graph.edges(data=True):
        if _WEIGHT_ATTR not in data or not data[_WEIGHT_ATTR]:
            length = float(data.get("length", 200.0) or 200.0)
            speed_kph = data.get("speed_kph") or 50.0
            try:
                speed_ms = float(str(speed_kph).split()[0]) / 3.6
            except (ValueError, TypeError):
                speed_ms = _FALLBACK_SPEED_MS
            data[_WEIGHT_ATTR] = length / speed_ms if speed_ms > 0 else length / _FALLBACK_SPEED_MS


def _build_route_dict(path: list[int], graph: nx.DiGraph) -> dict:
    """Build a route result dict from an ordered list of node IDs."""
    coords: list[tuple[float, float]] = []
    total_distance_m = 0.0
    total_travel_time_s = 0.0
    road_names: list[str] = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        attrs = _get_edge_attrs(graph, u, v)

        length = float(attrs.get("length", 200.0) or 200.0)
        travel_time = float(attrs.get(_WEIGHT_ATTR, length / _FALLBACK_SPEED_MS) or 0.0)

        total_distance_m += length
        total_travel_time_s += travel_time

        name = attrs.get("name")
        if isinstance(name, list):
            name = name[0] if name else None
        if name and str(name).strip() and str(name).strip() not in road_names:
            road_names.append(str(name).strip())

        # Add the from-node coordinate.
        u_data = graph.nodes.get(u, {})
        if u_data:
            coords.append((float(u_data.get("x", 0.0)), float(u_data.get("y", 0.0))))

    # Add the last node's coordinate.
    if path:
        last_data = graph.nodes.get(path[-1], {})
        if last_data:
            coords.append((float(last_data.get("x", 0.0)), float(last_data.get("y", 0.0))))

    # Build GeoJSON LineString.
    if len(coords) >= 2:
        line = LineString(coords)
        route_geojson = json.loads(json.dumps(mapping(line)))
    else:
        route_geojson = {"type": "LineString", "coordinates": coords}

    return {
        "path_nodes": [int(n) for n in path],
        "route_geojson": route_geojson,
        "distance_m": round(total_distance_m, 1),
        "estimated_minutes": round(total_travel_time_s / 60.0, 1),
        "road_names": road_names,
    }


def _get_edge_attrs(graph: nx.DiGraph, u: int, v: int) -> dict[str, Any]:
    """Return edge attribute dict for edge u→v."""
    try:
        data = graph.get_edge_data(u, v)
        if data is None:
            return {}
        # DiGraph: data is a plain dict; MultiDiGraph: data is keyed by int
        if isinstance(data, dict):
            # If values are dicts, it's a MultiDiGraph — take first
            first = next(iter(data.values()), None)
            if isinstance(first, dict):
                return first
            return data
        return {}
    except Exception:
        return {}
