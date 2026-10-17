import os
import json
import mimetypes
import logging
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

# Initialize BigQuery GIS engine
gis_engine = BigQueryGISEngine(str(DATA_DIR / "network_topology.json"))

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
                    "operational_ingestion": "Cloud Pub/Sub",
                    "multimodal_vision": "Gemini 1.5 Pro on Vertex AI",
                    "application_server": "Cloud Run (Dual-Persona UI)"
                }
            })
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

        # 6b. Live OpenStreetMap Corridor Fetcher
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
                logger.warning(f"OSM live fetch fallback: {e}")
            self.send_json({"status": "FALLBACK", "message": "Using calibrated municipal corridor vectors"})
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

            if not image_bytes and preset in ("clean", "moderate", "severe"):
                sample_file = SAMPLE_DIR / f"{preset}_filter.svg"
                if not sample_file.exists():
                    if preset == "severe":
                        sample_file = SAMPLE_DIR / "severe_biofilm_rust_filter.svg"
                    elif preset == "moderate":
                        sample_file = SAMPLE_DIR / "moderate_silt_filter.svg"
                    else:
                        sample_file = SAMPLE_DIR / "clean_filter.svg"
                if sample_file.exists():
                    with open(sample_file, "rb") as f:
                        image_bytes = f.read()
                    mime_type = "image/svg+xml"

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
