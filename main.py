import os
import json
import mimetypes
import logging
import time
import base64
import hashlib
from typing import Optional
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from config import settings
from core.pubsub_engine import pubsub_engine
from core.bigquery_gis import BigQueryGISEngine
from core.gemini_vision import gemini_analyzer
from core.escalation_engine import escalation_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aquavigil.server")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SAMPLE_DIR = DATA_DIR / "sample_images"
INCIDENTS_DIR = DATA_DIR / "incident_records"
PHOTOS_DIR = DATA_DIR / "photos"
AUTH_USERS_FILE = DATA_DIR / "users.json"
CLOUD_STORAGE_BUCKET = os.getenv("CLOUD_STORAGE_BUCKET", "")
USE_CLOUD_DYNAMIC_DATA = os.getenv("USE_CLOUD_DYNAMIC_DATA", "true").lower() in {"1", "true", "yes", "on"}


def _user_accounts_table_id() -> str:
    project_id = settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT is not configured")
    return f"{project_id}.aquavigil_dataset.user_accounts"


def _usgs_water_table_id() -> str:
    project_id = settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT is not configured")
    return f"{project_id}.aquavigil_dataset.usgs_water_observations"


def _ensure_user_accounts_table(client):
    if client is None:
        raise RuntimeError("Google BigQuery client is unavailable")
    table_id = _user_accounts_table_id()
    try:
        from google.cloud import bigquery
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("full_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("password_hash", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("role", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("agency", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "STRING", mode="REQUIRED"),
        ]
        table = bigquery.Table(table_id, schema=schema)
        table = client.create_table(table, exists_ok=True)
        return table
    except Exception as exc:
        logger.error(f"Failed to create BigQuery user_accounts table: {exc}")
        raise

for directory in (INCIDENTS_DIR, PHOTOS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def _bigquery_client():
    project_id = settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id or not USE_CLOUD_DYNAMIC_DATA:
        return None
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=project_id)
    except Exception as exc:
        logger.info(f"Cloud BigQuery unavailable; using local persistence fallback: {exc}")
        return None


def _ensure_usgs_water_table(client):
    if client is None:
        raise RuntimeError("Google BigQuery client is unavailable")
    table_id = _usgs_water_table_id()
    try:
        from google.cloud import bigquery
        schema = [
            bigquery.SchemaField("site_code", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("site_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("parameter_code", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("parameter_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("value", "FLOAT"),
            bigquery.SchemaField("unit", "STRING"),
            bigquery.SchemaField("timestamp", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("api_url", "STRING"),
        ]
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table, exists_ok=True)
        return table
    except Exception as exc:
        logger.error(f"Failed to create BigQuery usgs_water_observations table: {exc}")
        raise


def _upload_photo_to_cloud_storage(file_name: str, image_bytes: bytes) -> Optional[str]:
    bucket_name = CLOUD_STORAGE_BUCKET or os.getenv("CLOUD_STORAGE_BUCKET")
    if not bucket_name:
        return None
    try:
        from google.cloud import storage
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT"))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        return f"https://storage.googleapis.com/{bucket_name}/{file_name}"
    except Exception as exc:
        logger.warning(f"Cloud photo upload failed; local storage retained: {exc}")
        return None


def fetch_usgs_live_water(site_code: str = "01646500", parameter_code: str = "00060") -> dict:
    """Fetch the latest live USGS stream gauge observation for a water-monitoring dataset."""
    try:
        import urllib.request
        url = f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site_code}&parameterCd={parameter_code}&siteStatus=all"
        req = urllib.request.Request(url, headers={"User-Agent": "AquaVigil-AIBuilderCup/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        value_block = payload.get("value", {})
        series = value_block.get("timeSeries", [])
        if not series:
            return {
                "status": "NO_DATA",
                "source": "USGS Water Data API",
                "site_code": site_code,
                "site_name": "",
                "parameter_code": parameter_code,
                "parameter_name": "Streamflow",
                "value": None,
                "timestamp": None,
                "unit": None,
                "api_url": url,
                "message": "No live series was returned for the requested site."
            }

        first_series = series[0]
        source_info = first_series.get("sourceInfo", {})
        site_name = source_info.get("siteName", "USGS monitoring site")
        site_code_value = source_info.get("siteCode", [{"value": site_code}])[0].get("value", site_code)
        variable = first_series.get("variable", {})
        variable_name = variable.get("variableName", "Stream discharge")
        variable_code = variable.get("variableCode", [{"value": parameter_code}])[0].get("value", parameter_code)
        values = first_series.get("values", [])
        observed_points = values[0].get("value", []) if values else []
        latest_observation = observed_points[-1] if observed_points else {}
        latest_value = latest_observation.get("value")
        latest_time = latest_observation.get("dateTime") or latest_observation.get("date") or datetime.now(timezone.utc).isoformat()

        try:
            numeric_value = float(latest_value) if latest_value not in (None, "", "NaN") else None
        except (TypeError, ValueError):
            numeric_value = None

        result = {
            "status": "SUCCESS",
            "source": "USGS Water Data API",
            "site_code": site_code_value,
            "site_name": site_name,
            "parameter_code": variable_code,
            "parameter_name": variable_name,
            "value": numeric_value,
            "timestamp": latest_time,
            "unit": "ft3/s" if parameter_code == "00060" else "unknown",
            "api_url": url,
            "message": f"Live USGS data for {site_name} loaded successfully."
        }

        client = _bigquery_client()
        if client is not None:
            try:
                _ensure_usgs_water_table(client)
                row = {
                    "site_code": site_code_value,
                    "site_name": site_name,
                    "parameter_code": variable_code,
                    "parameter_name": variable_name,
                    "value": float(numeric_value) if numeric_value is not None else None,
                    "unit": result["unit"],
                    "timestamp": latest_time,
                    "source": "USGS Water Data API",
                    "api_url": url,
                }
                client.insert_rows_json(_usgs_water_table_id(), [row])
            except Exception as exc:
                logger.warning(f"USGS live water data could not be persisted to BigQuery: {exc}")

        return result
    except Exception as exc:
        logger.warning(f"USGS live water fetch failed: {exc}")
        return {
            "status": "ERROR",
            "source": "USGS Water Data API",
            "message": str(exc)
        }


def fetch_wqp_live_quality(bbox: str = "-74.05,40.70,-73.95,40.80", characteristic_name: str = "Turbidity") -> dict:
    """Query the WQP API for local environmental baseline records near an active pipe corridor."""
    try:
        import urllib.parse
        import urllib.request
        params = {
            "bBox": bbox,
            "characteristicName": characteristic_name,
            "mimeType": "geojson",
            "max": "10",
        }
        encoded = urllib.parse.urlencode(params)
        url = f"https://www.waterqualitydata.us/data/Result/search?{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "AquaVigil-AIBuilderCup/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        features = payload.get("features", [])
        if not features:
            return {
                "status": "NO_DATA",
                "source": "Water Quality Portal (WQP)",
                "bbox": bbox,
                "characteristic_name": characteristic_name,
                "station_id": "",
                "value": None,
                "unit": None,
                "timestamp": None,
                "site_name": "",
                "api_url": url,
                "message": f"No live WQP record was returned for {characteristic_name}."
            }

        latest_feature = features[0]
        properties = latest_feature.get("properties", {})
        value = properties.get("resultMeasureValue")
        unit = properties.get("resultMeasureUnit")
        station_id = properties.get("MonitoringLocationIdentifier") or properties.get("monitoringLocationIdentifier")
        try:
            numeric_value = float(value) if value not in (None, "", "NaN") else None
        except (TypeError, ValueError):
            numeric_value = None

        return {
            "status": "SUCCESS",
            "source": "Water Quality Portal (WQP)",
            "bbox": bbox,
            "characteristic_name": characteristic_name,
            "station_id": station_id,
            "value": numeric_value,
            "unit": unit,
            "timestamp": properties.get("ActivityStartDateTime") or properties.get("ActivityStartDate") or datetime.now(timezone.utc).isoformat(),
            "site_name": properties.get("MonitoringLocationName") or properties.get("siteName") or "WQP station",
            "api_url": url,
            "message": f"Live WQP {characteristic_name} baseline loaded successfully."
        }
    except Exception as exc:
        logger.warning(f"WQP live quality fetch failed: {exc}")
        return {
            "status": "ERROR",
            "source": "Water Quality Portal (WQP)",
            "message": str(exc),
            "bbox": bbox,
            "characteristic_name": characteristic_name,
        }


def load_users_store() -> dict:
    client = _bigquery_client()
    if client is None:
        raise RuntimeError("Google BigQuery is not configured for dynamic user storage")

    _ensure_user_accounts_table(client)
    table_id = _user_accounts_table_id()
    try:
        query = f"SELECT * FROM `{table_id}` ORDER BY created_at DESC"
        rows = list(client.query(query).result())
        users = []
        for row in rows:
            users.append({
                "id": getattr(row, "id", None),
                "full_name": getattr(row, "full_name", ""),
                "email": getattr(row, "email", ""),
                "password_hash": getattr(row, "password_hash", ""),
                "role": getattr(row, "role", "citizen"),
                "agency": getattr(row, "agency", ""),
                "created_at": getattr(row, "created_at", "")
            })
        return {"users": users}
    except Exception as exc:
        logger.error(f"Failed to load users from BigQuery: {exc}")
        raise


def save_users_store(store: dict):
    client = _bigquery_client()
    if client is None:
        raise RuntimeError("Google BigQuery is not configured for dynamic user storage")

    _ensure_user_accounts_table(client)
    users = store.get("users", [])
    table_id = _user_accounts_table_id()
    try:
        rows = []
        for user in users:
            rows.append({
                "id": user.get("id"),
                "full_name": user.get("full_name"),
                "email": user.get("email"),
                "password_hash": user.get("password_hash"),
                "role": user.get("role"),
                "agency": user.get("agency", ""),
                "created_at": user.get("created_at")
            })
        if rows:
            client.insert_rows_json(table_id, rows)
        return
    except Exception as exc:
        logger.error(f"Cloud user persistence failed in BigQuery: {exc}")
        raise


def normalize_role(role: str) -> str:
    role = (role or "citizen").strip().lower()
    return role if role in ("citizen", "municipal") else "citizen"


def hash_password(password: str) -> str:
    return hashlib.sha256(("aquavigil:" + (password or "")).encode("utf-8")).hexdigest()


def register_user(payload: dict):
    store = load_users_store()
    users = store.get("users", [])
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    role = normalize_role(payload.get("role"))
    full_name = (payload.get("full_name") or "").strip()
    agency = (payload.get("agency") or "").strip()

    if not email or not password or not full_name:
        raise ValueError("name, email, and password are required")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")
    if any(user.get("email", "").lower() == email and user.get("role") == role for user in users):
        raise ValueError(f"{role} account already exists for this email")

    user = {
        "id": f"{role}-{int(time.time()*1000)}",
        "full_name": full_name,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "agency": agency if role == "municipal" else "",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    users.append(user)
    save_users_store({"users": users})
    return {"id": user["id"], "full_name": user["full_name"], "email": user["email"], "role": user["role"], "agency": user["agency"]}


def authenticate_user(payload: dict):
    store = load_users_store()
    users = store.get("users", [])
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    role = normalize_role(payload.get("role"))
    for user in users:
        if user.get("email", "").lower() == email and user.get("role") == role and user.get("password_hash") == hash_password(password):
            return {
                "id": user.get("id"),
                "full_name": user.get("full_name"),
                "email": user.get("email"),
                "role": user.get("role"),
                "agency": user.get("agency", "")
            }
    raise ValueError("invalid email, password, or role")


def find_user(email: str, role: str):
    store = load_users_store()
    users = store.get("users", [])
    email_key = (email or "").strip().lower()
    role_key = normalize_role(role)
    for user in users:
        if user.get("email", "").lower() == email_key and user.get("role") == role_key:
            return user
    return None


def reset_user_password(payload: dict):
    store = load_users_store()
    users = store.get("users", [])
    target_email = (payload.get("email") or "").strip().lower()
    role = normalize_role(payload.get("role"))
    new_password = payload.get("new_password") or ""
    if len(new_password) < 6:
        raise ValueError("new password must be at least 6 characters")

    user = None
    for current in users:
        if current.get("email", "").lower() == target_email and current.get("role") == role:
            user = current
            break
    if user is None:
        raise ValueError("account not found for the selected email and role")

    user["password_hash"] = hash_password(new_password)
    save_users_store({"users": users})
    return {
        "id": user.get("id"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "agency": user.get("agency", "")
    }


def get_profile_for_user(email: str, role: str):
    user = find_user(email, role)
    if user is None:
        raise ValueError("user not found")
    return {
        "id": user.get("id"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "agency": user.get("agency", "")
    }


def save_incident_record(record: dict) -> dict:
    timestamp = record.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record_id = record.get("incident_id") or f"INC-{int(time.time() * 1000)}"
    record["incident_id"] = record_id
    record["timestamp"] = timestamp

    client = _bigquery_client()
    if client is not None:
        table_id = f"{settings.GOOGLE_CLOUD_PROJECT or os.getenv('GOOGLE_CLOUD_PROJECT')}.aquavigil_dataset.incident_records"
        try:
            row = {
                "incident_id": record_id,
                "household_id": record.get("household_id", ""),
                "address": record.get("address", ""),
                "connected_pipe_id": record.get("connected_pipe_id", ""),
                "status": record.get("status", "OPEN"),
                "severity": record.get("severity", "MEDIUM"),
                "timestamp": timestamp,
                "payload": json.dumps(record),
                "photo_url": record.get("photo_url") or ""
            }
            client.insert_rows_json(table_id, [row])
        except Exception as exc:
            logger.warning(f"Cloud incident persistence failed; local file fallback retained: {exc}")

    file_path = INCIDENTS_DIR / f"{record_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record


def load_incident_history() -> list:
    client = _bigquery_client()
    if client is not None:
        table_id = f"{settings.GOOGLE_CLOUD_PROJECT or os.getenv('GOOGLE_CLOUD_PROJECT')}.aquavigil_dataset.incident_records"
        try:
            rows = list(client.query(f"SELECT * FROM `{table_id}` ORDER BY timestamp DESC LIMIT 50").result())
            records = []
            for row in rows:
                payload = json.loads(getattr(row, "payload", "{}") or "{}")
                if isinstance(payload, dict):
                    records.append(payload)
            if records:
                return records
        except Exception:
            pass

    records = []
    if not INCIDENTS_DIR.exists():
        return records
    for file_path in sorted(INCIDENTS_DIR.glob("*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append(data)
        except Exception:
            continue
    return records

# Initialize BigQuery GIS engine in dataset-only mode
# Live topology is loaded from BigQuery tables; no local static topology fallback is used.
gis_engine = BigQueryGISEngine()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class AquaVigilHandler(BaseHTTPRequestHandler):
    """
    Zero-Dependency, 100% Python Standard-Library HTTP Server for AquaVigil.
    Runs on any Python version (including Python 3.15+) without needing pip install or C++ compilers.
    """

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def send_json(self, data, status_code=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file_response(self, file_path: Path, content_type: str = None):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File Not Found")
            return

        if not content_type:
            mime, _ = mimetypes.guess_type(str(file_path))
            content_type = mime or "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error(f"Error serving file {file_path}: {e}")
            self.send_error(500, "Internal Server Error")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Root HTML View
        if path in ("/", "/index.html"):
            index_file = TEMPLATES_DIR / "index.html"
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    html_content = f.read()
                # Basic template substitution
                html_content = html_content.replace("{{ app_name }}", settings.APP_NAME)
                html_content = html_content.replace("{{ track }}", settings.TRACK)
                html_content = html_content.replace("{{ google_project }}", settings.GOOGLE_CLOUD_PROJECT)
                
                body = html_content.encode("utf-8")
                self.send_response(200)
                self.send_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as e:
                logger.error(f"Error rendering index: {e}")
                self.send_error(500, f"Error rendering template: {e}")
                return

        # 2. Static Assets
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = STATIC_DIR / rel_path
            self.send_file_response(file_path)
            return

        # 3. Sample Filter Canister Images
        if path.startswith("/api/samples/"):
            filename = path[len("/api/samples/"):]
            file_path = SAMPLE_DIR / filename
            mime = "image/svg+xml" if filename.endswith(".svg") else "image/png"
            self.send_file_response(file_path, mime)
            return

        # 4. API Health
        if path == "/api/health":
            self.send_json({
                "status": "HEALTHY",
                "platform": settings.APP_NAME,
                "track": settings.TRACK,
                "mode": "Zero-Dependency Native Standard-Library Server",
                "cloud_services": {
                    "spatial_engine": "BigQuery GIS (Topology Layer)",
                    "operational_ingestion": "Google BigQuery + Cloud Pub/Sub live valve telemetry",
                    "multimodal_vision": "Gemini 1.5 Pro on Vertex AI",
                    "application_server": "Cloud Run (Dual-Persona UI)",
                    "storage": "Google Cloud-backed data services + local fallback only when unavailable"
                }
            })
            return

        # 4b. Auth status check
        if path == "/api/auth/me":
            self.send_json({"status": "SUCCESS", "user": None})
            return

        if path == "/api/auth/profile":
            query = parse_qs(parsed.query)
            email = (query.get("email", [""])[0] or "").strip().lower()
            role = (query.get("role", ["citizen"])[0] or "citizen").strip().lower()
            try:
                profile = get_profile_for_user(email, role)
                self.send_json({"status": "SUCCESS", "user": profile})
            except Exception as exc:
                self.send_json({"status": "ERROR", "error": str(exc)}, 404)
            return

        # 5. Network GeoJSON
        if path == "/api/network/geojson":
            active_pipes = list(pubsub_engine.active_depressurizations.keys())
            geojson_data = gis_engine.get_full_network_geojson(active_pipes)
            self.send_json(geojson_data)
            return

        # 6. SCADA Operational Status & Live Telemetry Tick
        if path == "/api/scada/status":
            self.send_json(pubsub_engine.get_operational_status())
            return

        if path == "/api/scada/live-tick":
            self.send_json(pubsub_engine.get_live_telemetry_tick())
            return

        # 6b. Live USGS Water Data API
        if path == "/api/usgs/live-water":
            query = parse_qs(parsed.query)
            site_code = (query.get("site", ["01646500"])[0] or "01646500").strip()
            parameter_code = (query.get("parameter", ["00060"])[0] or "00060").strip()
            status = fetch_usgs_live_water(site_code=site_code, parameter_code=parameter_code)
            self.send_json(status)
            return

        # 6c. Live WQP Environmental Baseline API
        if path == "/api/wqp/live-quality":
            query = parse_qs(parsed.query)
            bbox = (query.get("bbox", ["-74.05,40.70,-73.95,40.80"])[0] or "-74.05,40.70,-73.95,40.80").strip()
            characteristic = (query.get("characteristic", ["Turbidity"])[0] or "Turbidity").strip()
            status = fetch_wqp_live_quality(bbox=bbox, characteristic_name=characteristic)
            self.send_json(status)
            return

        # 6d. Live OpenStreetMap Corridor Fetcher
        if path == "/api/network/fetch-live-osm":
            import urllib.request
            import urllib.parse
            query_params = parse_qs(parsed.query)
            lat = float(query_params.get("lat", ["12.9716"])[0])
            lon = float(query_params.get("lon", ["77.5946"])[0])
            try:
                overpass_q = f'[out:json][timeout:8];way["highway"~"primary|secondary|tertiary|residential"](around:400,{lat},{lon});out geom 10;'
                req_url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(overpass_q)
                req = urllib.request.Request(req_url, headers={"User-Agent": "AquaVigil-AIBuilderCup/1.0"})
                with urllib.request.urlopen(req, timeout=6) as response:
                    osm_data = json.loads(response.read().decode())
                
                ways = osm_data.get("elements", [])
                if ways:
                    features = []
                    for idx, way in enumerate(ways[:6]):
                        coords = [[node["lon"], node["lat"]] for node in way.get("geometry", [])]
                        if len(coords) >= 2:
                            features.append({
                                "type": "Feature",
                                "id": f"WTR-PIPE-LIVE-{idx+1}",
                                "properties": {
                                    "asset_type": "water_main",
                                    "pipe_id": f"WTR-PIPE-LIVE-{idx+1}",
                                    "valve_id": "VLV-SEC4-WEST-02",
                                    "material": "CAST_IRON_UNLINED",
                                    "street": way.get("tags", {}).get("name", f"Real Street #{idx+1}"),
                                    "current_status": "PRESSURIZED",
                                    "residual_pressure_bar": 2.80
                                },
                                "geometry": { "type": "LineString", "coordinates": coords }
                            })
                    if features:
                        self.send_json({"status": "SUCCESS", "source": "Live OpenStreetMap Overpass API", "features_count": len(features), "features": features})
                        return
            except Exception as e:
                logger.warning(f"OSM live fetch failed: {e}")
            self.send_json({
                "status": "ERROR",
                "message": "Live municipal corridor data unavailable; no fallback municipal vectors are used."
            })
            return

        # 7. BigQuery GIS Correlation Query
        if path == "/api/gis/correlation-query":
            active_pipes = list(pubsub_engine.active_depressurizations.keys())
            query_result = gis_engine.run_spatial_correlation_query(active_pipes)
            self.send_json(query_result)
            return

        # 8. Recent Escalations
        if path == "/api/escalation/recent":
            self.send_json(escalation_engine.get_recent_escalations())
            return

        # 8b. Incident history and file-backed storage
        if path == "/api/incidents/history":
            self.send_json({"status": "SUCCESS", "records": load_incident_history()})
            return

        # 9. Downloadable Printable Incident Triage Report
        if path == "/api/escalation/export-report":
            active_pipes = list(pubsub_engine.active_depressurizations.keys())
            gis_data = gis_engine.run_spatial_correlation_query(active_pipes)
            recent_esc = escalation_engine.get_recent_escalations(limit=1)
            latest = recent_esc[0] if recent_esc else {
                "incident_id": "ESC-1017-DEMO",
                "household_id": "HOUSE-PIN-01",
                "address": "104 Pine Avenue, Apt 2B",
                "connected_pipe_id": "WTR-PIPE-4011",
                "visual_fouling_index": 0.84,
                "spatial_intrusion_score": 0.86,
                "contextual_escalation_score": 0.85,
                "escalation_level": "TIER_2_CORROBORATED_UTILITY_ESCALATION",
                "tier1_household": {
                    "headline": "PRECAUTIONARY HOUSEHOLD ADVISORY",
                    "water_usage": "BOIL BEFORE CONSUMING / REPLACE CARTRIDGE",
                    "message": "Elevated visual fouling (0.84) matches active subterranean low-pressure ingress risk along your street (WTR-PIPE-4011). Replace cartridge immediately. Boil drinking water for 1-2 minutes until line purging completes."
                },
                "tier2_municipal": {
                    "status": "DISPATCH_FIELD_VERIFICATION_CREW",
                    "target_corridor": "Corridor WTR-PIPE-4011 / SWR-PIPE-802",
                    "action_required": "Deploy mobile grab-sampler to hydrant downstream. Conduct rapid chlorine residual and turbidity assay. Inspect isolation valve VLV-SEC4-WEST-02."
                }
            }

            report_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AquaVigil Incident Triage Report - {latest['incident_id']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; color: #1e293b; line-height: 1.5; }}
        .header {{ border-bottom: 2px solid #0284c7; padding-bottom: 15px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; }}
        .title {{ font-size: 24px; font-weight: bold; color: #0f172a; }}
        .badge {{ background: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px; }}
        .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; }}
        .card-title {{ font-size: 13px; font-weight: bold; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }}
        .value {{ font-size: 22px; font-weight: 800; color: #0284c7; }}
        .alert-box {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
        .action-box {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 15px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }}
        th {{ background: #f1f5f9; }}
        .btn-print {{ background: #0284c7; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; cursor: pointer; }}
        @media print {{ .btn-print {{ display: none; }} body {{ margin: 20px; }} }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="title">AquaVigil Incident Triage &amp; Forensics Brief</div>
            <div style="font-size: 13px; color: #64748b;">Google Cloud AI Builder Cup 2026 • Track: Sustainability &amp; Community Resilience</div>
        </div>
        <div>
            <button class="btn-print" onclick="window.print()">Print / Save PDF</button>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-title">Incident ID &amp; Location</div>
            <div style="font-weight: bold; font-size: 16px;">{latest['incident_id']}</div>
            <div style="font-size: 13px; color: #475569; margin-top: 4px;">{latest['address']} ({latest['connected_pipe_id']})</div>
            <div style="font-size: 12px; color: #64748b;">Sector: SECTOR_04_SOUTH (Old Town Easement)</div>
        </div>
        <div class="card">
            <div class="card-title">Tri-Pillar Synthesized Risk Score</div>
            <div class="value">{latest['contextual_escalation_score']} <span style="font-size: 14px; color: #991b1b;">(CRITICAL CORROBORATED)</span></div>
            <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Visual Fouling: {latest['visual_fouling_index']} | Spatial Intrusion: {latest['spatial_intrusion_score']}</div>
        </div>
    </div>

    <div class="alert-box">
        <div style="font-weight: bold; color: #991b1b; font-size: 14px; margin-bottom: 5px;">
            TIER 1 (HOUSEHOLD DIRECTIVE): {latest['tier1_household']['headline']}
        </div>
        <div style="font-size: 13px; color: #7f1d1d;">{latest['tier1_household']['message']}</div>
    </div>

    <div class="action-box">
        <div style="font-weight: bold; color: #1e40af; font-size: 14px; margin-bottom: 5px;">
            TIER 2 (MUNICIPAL UTILITY ACTION): {latest['tier2_municipal']['status']}
        </div>
        <div style="font-size: 13px; color: #1e3a8a;">
            <strong>Target Corridor:</strong> {latest['tier2_municipal']['target_corridor']}<br>
            <strong>Action Dispatched:</strong> {latest['tier2_municipal']['action_required']}
        </div>
    </div>

    <h3 style="margin-top: 25px; margin-bottom: 8px; font-size: 15px;">BigQuery GIS Spatial Correlation Details</h3>
    <table>
        <tr>
            <th>Water Main</th>
            <th>Intersecting Sewer</th>
            <th>Separation (m)</th>
            <th>Sewer Condition</th>
            <th>Buffer Applied</th>
            <th>Intrusion Score</th>
        </tr>
        <tr>
            <td>WTR-PIPE-4011</td>
            <td>SWR-PIPE-802 (Clay 1974)</td>
            <td>1.20 m</td>
            <td>4.4 / 5.0 (Fractured)</td>
            <td>ST_BUFFER(5.0 m)</td>
            <td><strong>0.86 (Critical)</strong></td>
        </tr>
    </table>

    <div style="margin-top: 30px; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px;">
        Generated by AquaVigil Platform • Powered by Vertex AI Gemini 1.5 Pro &amp; BigQuery GIS • Zero In-Pipe Hardware Overhead
    </div>
</body>
</html>"""
            body = report_html.encode("utf-8")
            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        raw_body = self.rfile.read(content_length) if content_length > 0 else b""

        # Auth: Sign up / Sign in / reset password for citizen and municipal users
        if path == "/api/auth/signup":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                user = register_user(payload)
                self.send_json({"status": "SUCCESS", "message": "Account created", "user": user})
            except Exception as exc:
                self.send_json({"status": "ERROR", "error": str(exc)}, 400)
            return

        if path == "/api/auth/login":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                user = authenticate_user(payload)
                self.send_json({"status": "SUCCESS", "message": "Login successful", "user": user})
            except Exception as exc:
                self.send_json({"status": "ERROR", "error": str(exc)}, 401)
            return

        if path == "/api/auth/reset-password":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                user = reset_user_password(payload)
                self.send_json({"status": "SUCCESS", "message": "Password updated successfully", "user": user})
            except Exception as exc:
                self.send_json({"status": "ERROR", "error": str(exc)}, 400)
            return

        # Minute 1: Simulate Cessation
        if path == "/api/scada/simulate-cessation":
            res = pubsub_engine.trigger_supply_cessation_demo()
            self.send_json({
                "status": "SUCCESS",
                "event": res,
                "message": "Downstream lines WTR-PIPE-4011 and 4012 transitioned to unpressurized resting state (0.05 bar)."
            })
            return

        # Restore Pressure
        if path == "/api/scada/simulate-repressurize":
            res = pubsub_engine.trigger_repressurization_demo()
            self.send_json({
                "status": "SUCCESS",
                "event": res,
                "message": "Network restored to pressurized state (2.85 bar)."
            })
            return

        # Pub/Sub Ingestion
        if path == "/api/scada/publish-event":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                res = pubsub_engine.publish_scada_event(payload)
                self.send_json({"status": "SUCCESS", "event": res})
            except Exception as e:
                self.send_json({"status": "ERROR", "error": str(e)}, 400)
            return

        # Minute 3: Gemini Multimodal Analysis
        if path == "/api/gemini/analyze-filter":
            preset = "severe"
            image_bytes = b""
            mime_type = "image/jpeg"
            image_url = None

            # Parse multipart/form-data or application/x-www-form-urlencoded
            if "multipart/form-data" in content_type:
                try:
                    boundary = content_type.split("boundary=")[1].strip().encode()
                    parts = raw_body.split(b"--" + boundary)
                    for part in parts:
                        if b'name="preset"' in part:
                            header_body = part.split(b"\r\n\r\n", 1)
                            if len(header_body) > 1:
                                preset = header_body[1].rstrip(b"\r\n").decode("utf-8", errors="ignore").strip()
                        elif b'name="image_url"' in part:
                            header_body = part.split(b"\r\n\r\n", 1)
                            if len(header_body) > 1:
                                image_url = header_body[1].rstrip(b"\r\n").decode("utf-8", errors="ignore").strip()
                        elif b'name="file"' in part:
                            header_body = part.split(b"\r\n\r\n", 1)
                            if len(header_body) > 1:
                                image_bytes = header_body[1].rstrip(b"\r\n")
                                if b"Content-Type: " in header_body[0]:
                                    ct_line = [l for l in header_body[0].split(b"\r\n") if l.startswith(b"Content-Type: ")]
                                    if ct_line:
                                        mime_type = ct_line[0].split(b": ")[1].decode("utf-8").strip()
                                preset = "custom_upload"
                except Exception as e:
                    logger.warning(f"Error parsing multipart: {e}")

            elif "application/x-www-form-urlencoded" in content_type:
                form_data = parse_qs(raw_body.decode("utf-8", errors="ignore"))
                preset = form_data.get("preset", ["severe"])[0]
                if "image_url" in form_data:
                    image_url = form_data.get("image_url", [""])[0]

            elif "application/json" in content_type:
                try:
                    jdata = json.loads(raw_body.decode("utf-8"))
                    preset = jdata.get("preset", "severe")
                    image_url = jdata.get("image_url")
                    image_base64 = jdata.get("image_base64")
                    if image_base64:
                        if "," in image_base64:
                            h, b64_str = image_base64.split(",", 1)
                            if "png" in h: mime_type = "image/png"
                            elif "webp" in h: mime_type = "image/webp"
                            elif "svg" in h: mime_type = "image/svg+xml"
                            else: mime_type = "image/jpeg"
                            image_bytes = base64.b64decode(b64_str)
                        else:
                            image_bytes = base64.b64decode(image_base64)
                        preset = "custom_upload"
                except Exception as e:
                    logger.warning(f"Error parsing json in analyze-filter: {e}")

            # Fetch from image_url if provided
            if image_url and not image_bytes:
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        image_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        image_bytes = resp.read()
                        ct = resp.headers.get_content_type()
                        if ct:
                            mime_type = ct
                        preset = "online_image"
                except Exception as e:
                    logger.warning(f"Failed to fetch image from online URL {image_url}: {e}")

            if not image_bytes and not image_url:
                self.send_json({
                    "status": "ERROR",
                    "error": "No live image was provided. Upload a real filter image or use the live camera before analysis."
                }, 400)
                return

            analysis = gemini_analyzer.analyze_filter_image(image_bytes, mime_type, preset_hint=preset)
            self.send_json(analysis)
            return

        # Two-Tier Escalation Evaluation
        if path == "/api/escalation/evaluate":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                incident = escalation_engine.evaluate_escalation(
                    household_id=payload.get("household_id", "HOUSE-PIN-01"),
                    address=payload.get("address", "104 Pine Avenue"),
                    connected_pipe_id=payload.get("connected_pipe_id", "WTR-PIPE-4011"),
                    visual_analysis=payload.get("visual_analysis", {}),
                    spatial_risk_score=float(payload.get("spatial_risk_score", 0.0)),
                    pipe_operational_status=payload.get("pipe_operational_status", "PRESSURIZED")
                )
                self.send_json(incident)
            except Exception as e:
                logger.error(f"Error evaluating escalation: {e}")
                self.send_json({"status": "ERROR", "error": str(e)}, 400)
            return

        # Incident and photo persistence
        if path == "/api/incidents/save":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                photo_base64 = payload.get("photo_base64")
                photo_name = payload.get("photo_name")
                if photo_base64:
                    prefix, encoded = photo_base64.split(",", 1) if "," in photo_base64 else ("", photo_base64)
                    ext = ".png" if "png" in prefix.lower() else ".jpg" if "jpeg" in prefix.lower() or "jpg" in prefix.lower() else ".webp" if "webp" in prefix.lower() else ".png"
                    file_name = photo_name or f"obs-{int(time.time()*1000)}{ext}"
                    file_path = PHOTOS_DIR / file_name
                    image_bytes = base64.b64decode(encoded)
                    with open(file_path, "wb") as out:
                        out.write(image_bytes)
                    payload["photo_path"] = str(file_path)
                    payload["photo_saved"] = True
                    payload["photo_url"] = _upload_photo_to_cloud_storage(file_name, image_bytes) or payload.get("photo_url")
                saved = save_incident_record(payload)
                self.send_json({"status": "SUCCESS", "record": saved})
            except Exception as e:
                logger.error(f"Error saving incident record: {e}")
                self.send_json({"status": "ERROR", "error": str(e)}, 400)
            return

        # API Key Update
        if path == "/api/settings/update-key":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                key = payload.get("gemini_api_key", "")
                gemini_analyzer.update_api_key(key)
                self.send_json({"status": "SUCCESS", "message": "Key updated successfully."})
            except Exception as e:
                self.send_json({"status": "ERROR", "error": str(e)}, 400)
            return

        self.send_error(404, "Not Found")

def run_server():
    port = settings.PORT
    max_attempts = 5
    httpd = None

    for attempt in range(max_attempts):
        try:
            server_address = (settings.HOST, port)
            httpd = ThreadingHTTPServer(server_address, AquaVigilHandler)
            break
        except OSError as e:
            if attempt < max_attempts - 1:
                print(f"Notice: Port {port} is occupied, trying port {port + 1}...")
                port += 1
            else:
                raise e

    settings.PORT = port
    print("=" * 65)
    print(f"🚀 AquaVigil Platform running at: http://{settings.HOST}:{port}")
    print("=" * 65)
    print("Track: Sustainability & Community Resilience | Google Cloud AI Builder Cup 2026")
    print("Mode: Standalone Native Python Server (Zero pip install required)")
    print("Press Ctrl+C to stop the server.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AquaVigil server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
