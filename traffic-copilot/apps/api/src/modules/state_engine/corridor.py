"""
Corridor analysis: propagate incident impact along connected road segments.

Uses BFS from the incident origin node outward up to *radius_nodes* hops,
collecting every edge (u, v) encountered. For each edge we compute a
synthetic delay and congestion figure that degrades with distance from the
origin (traffic spill-back model).
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

import networkx as nx

from src.modules.state_engine.map_matcher import get_road_name
from src.modules.state_engine.queue_estimator import estimate_delay, classify_congestion

logger = logging.getLogger(__name__)

# Each hop away from the origin reduces congestion by this fraction.
_HOP_DECAY_FACTOR = 0.65

# Assumed free-flow speed when edge has no speed attribute.
_DEFAULT_FREE_FLOW_KMH = 50.0

# Assumed segment length when edge has no length attribute.
_DEFAULT_SEGMENT_LENGTH_M = 200.0


async def compute_affected_corridor(
    origin_node: int,
    graph,
    radius_nodes: int = 5,
    incident_id: str | None = None,
    session=None,
) -> list[dict]:
    """BFS from *origin_node* outward up to *radius_nodes* hops.

    For each traversed edge a congestion/delay estimate is computed.  The
    severity decays geometrically with hop distance so near-origin segments
    are most affected.

    Args:
        origin_node:  OSM node ID at the incident location.
        graph:        networkx MultiDiGraph loaded via osmnx.
        radius_nodes: Maximum number of hops from the origin to include.
        incident_id:  UUID string of the parent incident (for DB writes).
        session:      SQLAlchemy async session; if provided, writes affected
                      segments to the DB.

    Returns a list of dicts, each describing one affected segment:
        osm_way_id, osm_node_u, osm_node_v, road_name,
        delay_seconds, congestion_pct, congestion_level, hop_distance
    """
    if graph is None or graph.number_of_nodes() == 0:
        logger.warning("compute_affected_corridor: empty graph")
        return []

    if origin_node not in graph:
        logger.warning("compute_affected_corridor: origin_node %d not in graph", origin_node)
        return []

    affected: list[dict] = []
    visited_nodes: set[int] = {origin_node}
    visited_edges: set[tuple[int, int]] = set()

    # BFS queue: (node, hop_distance)
    queue: deque[tuple[int, int]] = deque([(origin_node, 0)])

    while queue:
        node, hop = queue.popleft()
        if hop >= radius_nodes:
            continue

        neighbors = list(graph.successors(node))
        for neighbor in neighbors:
            edge_key = (node, neighbor)
            if edge_key in visited_edges:
                continue
            visited_edges.add(edge_key)

            edge_attrs = _get_edge_attrs(graph, node, neighbor)
            road_name = await get_road_name(graph, node, neighbor)
            osm_way_id = _extract_osm_id(edge_attrs.get("osmid", 0))

            # Congestion decays with distance.
            base_congestion = 75.0  # origin is heavily congested
            congestion_pct = max(5.0, base_congestion * (_HOP_DECAY_FACTOR ** hop))

            free_flow = float(edge_attrs.get("speed_kph", _DEFAULT_FREE_FLOW_KMH) or _DEFAULT_FREE_FLOW_KMH)
            segment_length = float(edge_attrs.get("length", _DEFAULT_SEGMENT_LENGTH_M) or _DEFAULT_SEGMENT_LENGTH_M)

            observed_speed = free_flow * (1.0 - congestion_pct / 100.0)
            metrics = estimate_delay(observed_speed, free_flow, segment_length)

            segment = {
                "osm_way_id": osm_way_id,
                "osm_node_u": int(node),
                "osm_node_v": int(neighbor),
                "road_name": road_name,
                "delay_seconds": metrics["delay_seconds"],
                "congestion_pct": round(congestion_pct, 2),
                "congestion_level": classify_congestion(congestion_pct),
                "hop_distance": hop,
            }
            affected.append(segment)

            if neighbor not in visited_nodes:
                visited_nodes.add(neighbor)
                queue.append((neighbor, hop + 1))

    logger.info(
        "Corridor for origin=%d: %d affected segments across %d hops",
        origin_node, len(affected), radius_nodes,
    )

    if session is not None and incident_id is not None:
        await _write_segments_to_db(affected, incident_id, session)

    return affected


async def get_nearby_intersections(
    origin_node: int,
    graph,
    count: int = 5,
) -> list[dict]:
    """Return the N nearest intersection nodes from *origin_node*.

    An intersection is defined as any node with degree (in + out) > 2 in the
    road network.  We use BFS distance to rank candidates.

    Args:
        origin_node: Starting OSM node ID.
        graph:       networkx MultiDiGraph.
        count:       Maximum number of intersections to return.

    Returns list of dicts:
        node_id, lat, lon, road_names (list of distinct road names at node)
    """
    if graph is None or origin_node not in graph:
        return []

    intersections: list[dict] = []
    visited: set[int] = {origin_node}
    queue: deque[tuple[int, int]] = deque([(origin_node, 0)])

    while queue and len(intersections) < count:
        node, hop = queue.popleft()

        node_data = graph.nodes.get(node, {})
        degree = graph.degree(node)  # undirected total degree

        if degree > 2 and node != origin_node:
            road_names = _collect_road_names_at_node(graph, node)
            intersections.append({
                "node_id": int(node),
                "lat": float(node_data.get("y", 0.0)),
                "lon": float(node_data.get("x", 0.0)),
                "road_names": road_names,
            })

        for neighbor in graph.successors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, hop + 1))

    return intersections[:count]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_edge_attrs(graph, u: int, v: int) -> dict[str, Any]:
    """Return flattened edge attribute dict for the first key of edge u→v."""
    try:
        data = graph.get_edge_data(u, v)
        if data is None:
            return {}
        if isinstance(data, dict):
            # MultiDiGraph: {key: attrs}
            first = next(iter(data.values()), {})
            return first if isinstance(first, dict) else {}
        return {}
    except Exception:
        return {}


def _extract_osm_id(osmid: Any) -> int:
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


def _collect_road_names_at_node(graph, node: int) -> list[str]:
    """Collect distinct road names for all edges incident to *node*."""
    names: set[str] = set()
    for _, neighbor in graph.out_edges(node):
        attrs = _get_edge_attrs(graph, node, neighbor)
        name = attrs.get("name")
        if name:
            if isinstance(name, list):
                names.update(str(n) for n in name if n)
            else:
                names.add(str(name))
    for pred in graph.predecessors(node):
        attrs = _get_edge_attrs(graph, pred, node)
        name = attrs.get("name")
        if name:
            if isinstance(name, list):
                names.update(str(n) for n in name if n)
            else:
                names.add(str(name))
    return sorted(names)


async def _write_segments_to_db(
    segments: list[dict],
    incident_id: str,
    session,
) -> None:
    """Persist affected corridor segments to the database.

    Uses a simple upsert strategy: delete existing rows for this incident,
    then bulk-insert the new computed segments.
    """
    try:
        from sqlalchemy import text

        await session.execute(
            text("DELETE FROM affected_segments WHERE incident_id = :iid"),
            {"iid": incident_id},
        )
        for seg in segments:
            await session.execute(
                text(
                    """
                    INSERT INTO affected_segments
                        (incident_id, osm_way_id, osm_node_u, osm_node_v,
                         road_name, delay_seconds, congestion_pct, hop_distance)
                    VALUES
                        (:incident_id, :osm_way_id, :osm_node_u, :osm_node_v,
                         :road_name, :delay_seconds, :congestion_pct, :hop_distance)
                    """
                ),
                {
                    "incident_id": incident_id,
                    "osm_way_id": seg["osm_way_id"],
                    "osm_node_u": seg["osm_node_u"],
                    "osm_node_v": seg["osm_node_v"],
                    "road_name": seg.get("road_name"),
                    "delay_seconds": seg["delay_seconds"],
                    "congestion_pct": seg["congestion_pct"],
                    "hop_distance": seg["hop_distance"],
                },
            )
        await session.commit()
        logger.debug("Wrote %d corridor segments for incident %s", len(segments), incident_id)
    except Exception:
        logger.exception("Failed to write corridor segments to DB for incident %s", incident_id)
        try:
            await session.rollback()
        except Exception:
            pass
