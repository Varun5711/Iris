"""
OSMnx graph loader with pickle cache for TrafficCopilot.

The graph is a directed multigraph of the road network for the configured
place.  Edge weights include ``speed_kph`` and ``travel_time`` (seconds) added
by OSMnx so they can be used directly for routing.

Lifecycle
---------
    from src.integrations.osm.loader import initialize_graph, get_graph

    await initialize_graph(
        place_name=settings.osm_place_name,
        cache_path=settings.osm_graph_cache,
    )

    # Later, anywhere in the codebase:
    G = await get_graph()
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import networkx as nx
import osmnx as ox

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global graph singleton
# ---------------------------------------------------------------------------

_graph: nx.MultiDiGraph | None = None


# ---------------------------------------------------------------------------
# Load / download
# ---------------------------------------------------------------------------


async def load_or_download_graph(
    place_name: str,
    cache_path: str,
) -> nx.MultiDiGraph:
    """
    Load a road-network graph from a pickle cache, or download it from OSM.

    If the pickle file at *cache_path* exists it is loaded directly (fast,
    no network required).  Otherwise the graph is downloaded from OpenStreetMap
    via OSMnx, enriched with speed and travel-time edge attributes, and saved
    to *cache_path* for subsequent runs.

    Parameters
    ----------
    place_name:
        Nominatim place name, e.g. ``"Manhattan, New York, USA"``.
    cache_path:
        Filesystem path to the ``.gpickle`` cache file.

    Returns
    -------
    nx.MultiDiGraph
        Directed multigraph with ``speed_kph`` and ``travel_time`` on edges.
    """
    path = Path(cache_path)

    if path.exists():
        logger.info("Loading OSM graph from cache: %s", path)
        with open(path, "rb") as fh:
            graph: nx.MultiDiGraph = pickle.load(fh)
        logger.info(
            "Graph loaded from cache: %d nodes, %d edges",
            graph.number_of_nodes(),
            graph.number_of_edges(),
        )
        return graph

    logger.info(
        "Cache not found — downloading OSM graph for place: %s", place_name
    )
    graph = ox.graph_from_place(place_name, network_type="drive")
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)

    logger.info(
        "Downloaded OSM graph: %d nodes, %d edges — caching to %s",
        graph.number_of_nodes(),
        graph.number_of_edges(),
        path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(graph, fh, protocol=pickle.HIGHEST_PROTOCOL)

    return graph


async def get_graph() -> nx.MultiDiGraph:
    """
    Return the loaded graph singleton.

    Raises
    ------
    RuntimeError
        If ``initialize_graph`` has not been called yet.
    """
    if _graph is None:
        raise RuntimeError(
            "OSM graph is not loaded. "
            "Call initialize_graph(place_name, cache_path) first."
        )
    return _graph


async def initialize_graph(place_name: str, cache_path: str) -> None:
    """
    Load (or download) the road-network graph and store it as the singleton.

    This is the entry-point for application startup.  Subsequent calls to
    :func:`get_graph` will return the cached singleton without re-loading.

    Parameters
    ----------
    place_name:
        Nominatim place name passed to OSMnx.
    cache_path:
        Path to the pickle cache file.
    """
    global _graph
    _graph = await load_or_download_graph(place_name, cache_path)
    logger.info("OSM graph initialised and ready.")
