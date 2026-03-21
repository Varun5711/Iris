#!/usr/bin/env python3
"""Download OSMnx road network graph for configured city and save to cache."""
import asyncio
import sys
sys.path.insert(0, "/app")

from src.core.config import settings
from src.integrations.osm.loader import initialize_graph, load_or_download_graph
from src.core.logging import get_logger, configure_logging

async def main():
    configure_logging()
    logger = get_logger(__name__)
    logger.info("importing_osm_graph", place=settings.osm_place_name, cache=settings.osm_graph_cache)
    G = await load_or_download_graph(settings.osm_place_name, settings.osm_graph_cache)
    logger.info("graph_imported", nodes=len(G.nodes), edges=len(G.edges))

if __name__ == "__main__":
    asyncio.run(main())
