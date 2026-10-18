"""Municipal Open Data ingestion workflow for AquaVigil.

This module downloads public municipal GIS data from open portals (for example,
NYC Open Data, London Open Data, or Data.gov), normalizes the features into a
consistent schema, and stores them in the project BigQuery GIS dataset.

It is intentionally designed to avoid synthetic fallback data: if a live source
is unavailable, the loader returns a clear error instead of generating a demo
municipal corridor.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, parse

logger = logging.getLogger("aquavigil.municipal_ingest")


DEFAULT_PORTALS = {
    "nyc_open_data": {
        "label": "NYC Open Data",
        "description": "Stormwater, sewer, and utility infrastructure feeds",
    },
    "london_datastore": {
        "label": "London Datastore / UK Open Data",
        "description": "Drainage and utility infrastructure layers",
    },
    "data_gov": {
        "label": "Data.gov",
        "description": "Public municipal service and sewer layers",
    },
}


def fetch_json(url: str) -> Dict[str, Any]:
    """Download JSON or GeoJSON from a URL."""
    req = request.Request(
        url,
        headers={
            "User-Agent": "AquaVigil-Municipal-Ingest/1.0",
            "Accept": "application/json, application/geo+json, */*",
        },
    )
    with request.urlopen(req, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _safe_get(d: Dict[str, Any], *path: str) -> Any:
    current: Any = d
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _feature_id(feature: Dict[str, Any], index: int) -> str:
    feature_id = feature.get("id")
    if feature_id:
        return str(feature_id)
    properties = feature.get("properties", {}) or {}
    for key in ("asset_id", "pipe_id", "sewer_id", "id", "OBJECTID", "name"):
        value = properties.get(key)
        if value is not None:
            return str(value)
    return f"municipal_feature_{index}"


def _feature_name(feature: Dict[str, Any], index: int) -> str:
    props = feature.get("properties", {}) or {}
    for key in ("name", "asset_name", "title", "label", "feature_name"):
        value = props.get(key)
        if value:
            return str(value)
    return f"Municipal feature {index}"


def _feature_status(feature: Dict[str, Any]) -> str:
    props = feature.get("properties", {}) or {}
    for key in ("status", "condition", "asset_status", "state"):
        value = props.get(key)
        if value is not None:
            return str(value)
    return "unknown"


def _feature_geometry(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    geometry = feature.get("geometry")
    if geometry is None:
        return None
    if isinstance(geometry, dict) and geometry.get("type"):
        return geometry
    return None


def _geometry_json(feature: Dict[str, Any]) -> str:
    geometry = _feature_geometry(feature)
    if geometry is None:
        raise ValueError("Feature is missing geometry")
    return json.dumps(geometry)


def normalize_feature_collection(payload: Dict[str, Any], source_name: str, asset_type: str, portal_name: str) -> List[Dict[str, Any]]:
    """Convert a GeoJSON FeatureCollection into a normalized row list."""
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("GeoJSON payload does not contain a feature collection")

    rows: List[Dict[str, Any]] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        geometry = _feature_geometry(feature)
        if geometry is None:
            logger.warning("Skipping feature without geometry: %s", _feature_id(feature, index))
            continue

        properties = feature.get("properties", {}) or {}
        rows.append({
            "asset_id": _feature_id(feature, index),
            "asset_name": _feature_name(feature, index),
            "asset_type": asset_type,
            "source_name": source_name,
            "source_portal": portal_name,
            "status": _feature_status(feature),
            "description": properties.get("description") or properties.get("notes") or "Open municipal infrastructure layer",
            "geometry_geojson": json.dumps(geometry),
        })
    return rows


def ensure_municipal_table(client: Any, project_id: str, dataset_id: str, table_name: str = "municipal_infrastructure") -> None:
    """Create the municipal infrastructure table if it does not already exist."""
    from google.cloud import bigquery

    schema = [
        bigquery.SchemaField("asset_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("asset_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("asset_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source_portal", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("geometry", "GEOGRAPHY", mode="REQUIRED"),
    ]

    table_ref = f"{project_id}.{dataset_id}.{table_name}"
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)
    logger.info("Ensured municipal table exists: %s", table_ref)


def sql_string(value: Any) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def ingest_geojson_url(
    url: str,
    source_name: str,
    asset_type: str,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    table_name: str = "municipal_infrastructure",
    portal_name: str = "municipal_open_data",
) -> Dict[str, Any]:
    """Download a GeoJSON layer and insert it into BigQuery."""
    if not project_id:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not dataset_id:
        dataset_id = os.getenv("BIGQUERY_DATASET", "aquavigil_dataset")

    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT is not configured")

    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install google-cloud-bigquery to use this ingestion workflow.") from exc

    payload = fetch_json(url)
    rows = normalize_feature_collection(payload, source_name=source_name, asset_type=asset_type, portal_name=portal_name)
    if not rows:
        raise ValueError("No valid municipal features were found in the provided GeoJSON feed")

    client = bigquery.Client(project=project_id)
    ensure_municipal_table(client, project_id, dataset_id, table_name)

    insert_sql = f"""
        INSERT INTO `{project_id}.{dataset_id}.{table_name}`
        (asset_id, asset_name, asset_type, source_name, source_portal, status, description, geometry)
        VALUES
    """
    arguments: List[str] = []
    for row in rows:
        geometry_json = row["geometry_geojson"].replace("'", "\\'")
        arguments.append(
            "(" +
            ", ".join([
                sql_string(row["asset_id"]),
                sql_string(row["asset_name"]),
                sql_string(row["asset_type"]),
                sql_string(row["source_name"]),
                sql_string(row["source_portal"]),
                sql_string(row.get("status", "unknown")),
                sql_string(row.get("description", "Open municipal infrastructure layer")),
                f"ST_GEOGFROMGEOJSON('{geometry_json}')",
            ]) +
            ")"
        )

    insert_sql += ",\n".join(arguments)
    client.query(insert_sql).result()

    return {
        "status": "SUCCESS",
        "project_id": project_id,
        "dataset_id": dataset_id,
        "table_name": table_name,
        "rows_inserted": len(rows),
        "source_name": source_name,
        "asset_type": asset_type,
    }


def get_portal_examples() -> Dict[str, str]:
    return {
        "OpenStreetMap": "https://www.openstreetmap.org",
        "NYC Open Data": "https://data.cityofnewyork.us/resource/5fzm-8x9j.geojson",
        "London Open Data": "https://data.london.gov.uk/",
        "Data.gov": "https://catalog.data.gov/dataset?res_format=GeoJSON",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest real municipal GeoJSON data into BigQuery GIS tables.")
    parser.add_argument("--url", required=True, help="Public GeoJSON or JSON URL for the municipal source.")
    parser.add_argument("--source-name", default="municipal_source", help="Friendly source name.")
    parser.add_argument("--asset-type", default="stormwater", help="Normalized asset type for AquaVigil.")
    parser.add_argument("--project-id", default=os.getenv("GOOGLE_CLOUD_PROJECT"), help="Google Cloud project ID.")
    parser.add_argument("--dataset-id", default=os.getenv("BIGQUERY_DATASET", "aquavigil_dataset"), help="BigQuery dataset ID.")
    parser.add_argument("--table-name", default="municipal_infrastructure", help="BigQuery table for municipal geometry.")
    parser.add_argument("--portal-name", default="municipal_open_data", help="Open data portal label.")
    args = parser.parse_args()

    try:
        result = ingest_geojson_url(
            url=args.url,
            source_name=args.source_name,
            asset_type=args.asset_type,
            project_id=args.project_id,
            dataset_id=args.dataset_id,
            table_name=args.table_name,
            portal_name=args.portal_name,
        )
        print(json.dumps(result, indent=2))
    except Exception as exc:  # pragma: no cover
        logger.exception("Municipal data ingestion failed")
        raise SystemExit(f"Municipal ingestion failure: {exc}") from exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    main()
