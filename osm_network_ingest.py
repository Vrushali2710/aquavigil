"""Download a street-level transport network for a city sector using OSM.

This script intentionally avoids country boundary polygons such as the
johan/world.geo.json sample, because AquaVigil requires infrastructure-scale
geometry (roads, utility corridors, sewer mains, service lines) rather than
national border polygons.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def download_osm_network(place: str, output_path: str, network_type: str = "drive") -> dict[str, Any]:
    """Download a street network for a city/sector and save it as GeoJSON."""
    try:
        import osmnx as ox
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "osmnx is required. Install it with: pip install osmnx geopandas"
        ) from exc

    graph = ox.graph_from_place(place, network_type=network_type)
    gdf = ox.graph_to_gdfs(graph, nodes=False, fill_edge_geometry=True)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_file, driver="GeoJSON")

    result = {
        "status": "SUCCESS",
        "place": place,
        "network_type": network_type,
        "output_path": str(out_file),
        "feature_count": len(gdf),
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a street-level OpenStreetMap network for AquaVigil GIS use.")
    parser.add_argument("--place", required=True, help="City/area name, e.g. 'Manhattan, New York, USA'")
    parser.add_argument("--output", default="osm_network.geojson", help="Output GeoJSON path")
    parser.add_argument("--network-type", default="drive", help="OSM network type (drive, walk, bike, all)")
    args = parser.parse_args()

    download_osm_network(place=args.place, output_path=args.output, network_type=args.network_type)


if __name__ == "__main__":
    main()
