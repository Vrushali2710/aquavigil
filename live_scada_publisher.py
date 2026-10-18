"""Continuously publish live SCADA valve events to Google Cloud Pub/Sub.

This is the active operational stream for AquaVigil pillar II.
It publishes lightweight JSON telemetry events every 10 seconds to the
`scada.valve.telemetry` topic in the configured Google Cloud project.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


def _fetch_wqp_live_baseline(bbox: str = "-74.05,40.70,-73.95,40.80", characteristic_name: str = "Turbidity") -> Dict[str, Any]:
    """Fetch an ambient WQP baseline value near an affected water corridor."""
    params = {
        "bBox": bbox,
        "characteristicName": characteristic_name,
        "mimeType": "geojson",
        "max": "10",
    }
    url = f"https://www.waterqualitydata.us/data/Result/search?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "AquaVigil-AIBuilderCup/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {
            "status": "NO_DATA",
            "source": "Water Quality Portal (WQP)",
            "characteristic_name": characteristic_name,
            "value": None,
            "unit": "unknown",
            "station_id": None,
        }

    features = payload.get("features", [])
    if not features:
        return {
            "status": "NO_DATA",
            "source": "Water Quality Portal (WQP)",
            "characteristic_name": characteristic_name,
            "value": None,
            "unit": "unknown",
            "station_id": None,
        }

    first_feature = features[0]
    props = first_feature.get("properties", {})
    value = props.get("resultMeasureValue")
    unit = props.get("resultMeasureUnit")
    station_id = props.get("MonitoringLocationIdentifier") or props.get("monitoringLocationIdentifier")
    try:
        numeric_value = float(value) if value not in (None, "", "NaN") else None
    except (TypeError, ValueError):
        numeric_value = None

    return {
        "status": "SUCCESS",
        "source": "Water Quality Portal (WQP)",
        "characteristic_name": characteristic_name,
        "value": numeric_value,
        "unit": unit,
        "station_id": station_id,
        "timestamp": props.get("ActivityStartDateTime") or props.get("ActivityStartDate") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _fetch_usgs_live_observation(site_code: str = "01646500", parameter_codes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Fetch the latest real USGS observation for a known monitoring site."""
    candidates = parameter_codes or ["00060", "00065", "00095", "63680"]

    for parameter_code in candidates:
        url = (
            f"https://waterservices.usgs.gov/nwis/iv/?"
            f"format=json&sites={site_code}&parameterCd={parameter_code}&siteStatus=all"
        )
        request = urllib.request.Request(url, headers={"User-Agent": "AquaVigil-AIBuilderCup/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            continue

        series = payload.get("value", {}).get("timeSeries", [])
        if not series:
            continue

        first_series = series[0]
        source_info = first_series.get("sourceInfo", {})
        site_name = source_info.get("siteName", "USGS monitoring site")
        site_code_value = source_info.get("siteCode", [{"value": site_code}])[0].get("value", site_code)

        variable = first_series.get("variable", {})
        variable_code = variable.get("variableCode", [{"value": parameter_code}])[0].get("value", parameter_code)
        variable_name = variable.get("variableName", "Water observation")

        values = first_series.get("values", [])
        observed_points = values[0].get("value", []) if values else []
        latest_observation = observed_points[-1] if observed_points else {}
        latest_value = latest_observation.get("value")
        latest_time = latest_observation.get("dateTime") or latest_observation.get("date")

        try:
            numeric_value = float(latest_value) if latest_value not in (None, "", "NaN") else None
        except (TypeError, ValueError):
            numeric_value = None

        unit_code = variable.get("unit", {}).get("unitCode", "unknown")

        return {
            "site_code": site_code_value,
            "site_name": site_name,
            "parameter_code": variable_code,
            "parameter_name": variable_name,
            "value": numeric_value,
            "unit": unit_code,
            "timestamp": latest_time,
            "source": "USGS Water Data API",
            "status": "SUCCESS",
        }

    return {
        "site_code": site_code,
        "site_name": "No live USGS reading available",
        "parameter_code": "",
        "parameter_name": "No live USGS reading available",
        "value": None,
        "unit": "unknown",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "USGS Water Data API",
        "status": "NO_DATA",
    }


def _build_payload(index: int, usgs_data: Optional[Dict[str, Any]] = None, wqp_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    usgs_snapshot = usgs_data or _fetch_usgs_live_observation()
    wqp_snapshot = wqp_data or _fetch_wqp_live_baseline()
    payload = {
        "event_id": f"evt_valve_down_{int(time.time())}_{index:04d}",
        "valve_id": "VLV-SEC4-WEST-02",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_type": "SUPPLY_CYCLE_SHUTDOWN",
        "telemetry": {
            "actuator_state": "CLOSED",
            "residual_pressure_bar": 0.05,
            "pipe_material": "CAST_IRON_UNLINED",
            "installation_decade": "1980s",
            "usgs_site_code": usgs_snapshot.get("site_code"),
            "usgs_parameter_code": usgs_snapshot.get("parameter_code"),
            "usgs_parameter_name": usgs_snapshot.get("parameter_name"),
            "usgs_value": usgs_snapshot.get("value"),
            "usgs_unit": usgs_snapshot.get("unit"),
            "usgs_timestamp": usgs_snapshot.get("timestamp"),
            "usgs_source": usgs_snapshot.get("source"),
            "wqp_baseline_turbidity_ntu": wqp_snapshot.get("value"),
            "wqp_station_id": wqp_snapshot.get("station_id"),
            "wqp_characteristic_name": wqp_snapshot.get("characteristic_name"),
            "wqp_unit": wqp_snapshot.get("unit"),
            "wqp_timestamp": wqp_snapshot.get("timestamp"),
            "wqp_source": wqp_snapshot.get("source"),
        },
        "impacted_sub_network": {
            "sector_id": "SECTOR_04_SOUTH",
            "downstream_line_ids": ["WTR-PIPE-4011", "WTR-PIPE-4012"],
        },
    }
    return payload


def _ensure_topic_exists(publisher, project_id: str, topic_id: str) -> str:
    topic_path = publisher.topic_path(project_id, topic_id)
    try:
        publisher.get_topic(request={"topic": topic_path})
        print(f"Pub/Sub topic already exists: {topic_path}")
        return topic_path
    except Exception:
        try:
            publisher.create_topic(request={"name": topic_path})
            print(f"Created Pub/Sub topic: {topic_path}")
            return topic_path
        except Exception as exc:
            raise RuntimeError(
                f"Unable to create or access Pub/Sub topic '{topic_path}'. "
                f"Check GOOGLE_CLOUD_PROJECT, credentials, and Pub/Sub permissions. Details: {exc}"
            ) from exc


def main() -> None:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "project-468c1498-16f8-4b24-98a")
    topic_id = os.getenv("PUBSUB_TOPIC_ID", "scada.valve.telemetry")
    publish_interval_seconds = int(os.getenv("PUBSUB_INTERVAL_SECONDS", "10"))

    try:
        from google.cloud import pubsub_v1
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-pubsub is required. Install it with: pip install google-cloud-pubsub"
        ) from exc

    publisher = pubsub_v1.PublisherClient()
    topic_path = _ensure_topic_exists(publisher, project_id, topic_id)

    print(f"Publishing live valve telemetry to: {topic_path}")
    print(f"Project: {project_id} | Topic: {topic_id} | Interval: {publish_interval_seconds}s")

    counter = 0
    while True:
        try:
            usgs_data = _fetch_usgs_live_observation()
            wqp_data = _fetch_wqp_live_baseline()
            payload = _build_payload(counter, usgs_data, wqp_data)
            data = json.dumps(payload).encode("utf-8")
            future = publisher.publish(topic_path, data)
            future.result(timeout=30)
            print(
                f"Published event_id={payload['event_id']} | valve_id={payload['valve_id']} | "
                f"usgs={usgs_data.get('parameter_name')}:{usgs_data.get('value')} {usgs_data.get('unit')} | "
                f"wqp={wqp_data.get('characteristic_name')}:{wqp_data.get('value')} {wqp_data.get('unit')} | "
                f"ts={payload['timestamp']}"
            )
            counter += 1
            time.sleep(publish_interval_seconds)
        except Exception as exc:
            print(f"Pub/Sub publish failed: {exc}")
            time.sleep(15)


if __name__ == "__main__":
    main()
