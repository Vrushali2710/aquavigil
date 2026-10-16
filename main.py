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

        # 6. SCADA Operational Status
        if path == "/api/scada/status":
            self.send_json(pubsub_engine.get_operational_status())
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

            # Parse multipart/form-data or application/x-www-form-urlencoded
            if "multipart/form-data" in content_type:
                try:
                    boundary = content_type.split("boundary=")[1].strip().encode()
                    parts = raw_body.split(b"--" + boundary)
                    for part in parts:
                        if b'name="preset"' in part:
                            # extract preset string
                            header_body = part.split(b"\r\n\r\n", 1)
                            if len(header_body) > 1:
                                preset = header_body[1].rstrip(b"\r\n").decode("utf-8", errors="ignore").strip()
                        elif b'name="file"' in part:
                            header_body = part.split(b"\r\n\r\n", 1)
                            if len(header_body) > 1:
                                image_bytes = header_body[1].rstrip(b"\r\n")
                                if b"Content-Type: " in header_body[0]:
                                    ct_line = [l for l in header_body[0].split(b"\r\n") if l.startswith(b"Content-Type: ")]
                                    if ct_line:
                                        mime_type = ct_line[0].split(b": ")[1].decode("utf-8").strip()
                except Exception as e:
                    logger.warning(f"Error parsing multipart: {e}")

            elif "application/x-www-form-urlencoded" in content_type:
                form_data = parse_qs(raw_body.decode("utf-8", errors="ignore"))
                preset = form_data.get("preset", ["severe"])[0]

            elif "application/json" in content_type:
                try:
                    jdata = json.loads(raw_body.decode("utf-8"))
                    preset = jdata.get("preset", "severe")
                except:
                    pass

            if not image_bytes and preset:
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
    server_address = (settings.HOST, settings.PORT)
    httpd = ThreadingHTTPServer(server_address, AquaVigilHandler)
    print("=" * 65)
    print(f"🚀 AquaVigil Platform running at: http://{settings.HOST}:{settings.PORT}")
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
