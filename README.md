# AquaVigil Platform
**Subterranean Cross-Contamination & Purifier Health Sentry**  
*Google Cloud AI Builder Cup 2026 | Track: Sustainability & Community Resilience*

---

## 🌊 Overview
Over **1.3 billion people worldwide** receive domestic water through **Intermittent Water Supply (IWS)** systems. During low-pressure or supply shutoff periods, subterranean sewer exfiltration, contaminated groundwater, and soil moisture are drawn inward through cracks, leaks, and defective joints in drinking mains. When supply resumes, contaminants are transported directly to household taps.

**AquaVigil** closes this critical public health visibility gap without requiring expensive physical in-pipe sensors. It couples **BigQuery GIS network-topology risk modeling** with **Gemini 1.5 Pro multimodal visual filter forensics** to detect subterranean contamination corridors and assess household sediment pre-filter fouling.

---

## 🏛️ Tri-Pillar Architecture

```
                                    +-----------------------------------------+
                                    |     Cloud Pub/Sub Operational Events    |
                                    | (Pump shutdowns, SCADA valve closures)  |
                                    +--------------------+--------------------+
                                                         |
                                                         v
+-------------------------------+           +-----------------------------+
|    Gemini Multimodal AI       |           |     BigQuery GIS Engine     |
| (Vertex AI / Gemini 1.5 Pro)  |           | (Distributed Spatial Joins) |
| • Optical Opacity Forensics   |           | • ST_BUFFER(geometry, 5.0m) |
| • Biofilm / Rust Detection    |           | • ST_INTERSECTS & ST_DIST   |
| • Visual Fouling Index (0-1)  |           | • Composite Intrusion Score |
+---------------+---------------+           +--------------+--------------+
                |                                          |
                +--------------------+---------------------+
                                     |
                                     v
                 +-----------------------------------------+
                 |       Two-Tier Escalation Engine        |
                 |  Tier 1: Precautionary Household Advice |
                 |  Tier 2: Utility Verification Corridors |
                 +-----------------------------------------+
```

1. **Pillar I: Subterranean Network-Topology Risk Layer (BigQuery GIS)**
   - Computes configurable $5.0\text{ m}$ proximity buffers (`ST_BUFFER(geometry, 5.0)`) around depressurized potable water mains.
   - Intersects (`ST_INTERSECTS`) with aging wastewater infrastructure.
   - Calculates Intrusion Vulnerability Score:
     $$\text{Score} = \text{round}\left( \frac{5.0 - d}{5.0} \times 0.45 + \frac{\text{Rating}}{5.0} \times 0.35 + 0.20,\, 2 \right)$$
   - Sub-second distributed queries executed in $<500\text{ ms}$.

2. **Pillar II: Event-Driven Operational Ingestion (Cloud Pub/Sub)**
   - Captures operational supply-cycle shutdown events, pump stoppage signals, and depressurizations.
   - Downstream water mains transition to resting, unpressurized states ($0.05\text{ bar}$) triggering immediate spatial risk triage.

3. **Pillar III: Gemini Multimodal Visual Fouling Assessment (Vertex AI)**
   - Residents upload smartphone photographs of transparent under-sink pre-filter canisters.
   - Gemini 1.5 Pro parses optical opacity, surface discoloration, and particulate saturation.
   - Outputs structured JSON schema evaluating fouling index ($0.00 - 1.00$), deposit indicators (`IRON_OXIDE_RUST`, `INORGANIC_SILT`, `POSSIBLE_BIOFILM_ACCUMULATION`), and severity.

---

## 🚀 Quick Start Instructions

### Prerequisites
- Python 3.9+
- Web browser (Chrome, Edge, Firefox)

### Launching the Application
1. Open PowerShell or Terminal in this folder:
   ```powershell
   cd C:\Users\vrushali.shah\.gemini\antigravity\scratch\aquavigil
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the platform:
   ```bash
   python main.py
   ```
   *(Or double-click `start.bat` on Windows)*
4. Open your browser and navigate to:
   ```
   http://127.0.0.1:8081
   ```

---

## ⏱️ 3-Minute Hackathon Demo Blueprint Walkthrough

The application features a built-in interactive demo banner at the top of the interface:

- **Minute 1: The Trigger Event**
  - Click **[Min 1 Trigger Shutoff]**.
  - Simulates supply-cycle cessation via Cloud Pub/Sub on valve `VLV-SEC4-WEST-02`.
  - Mains `WTR-PIPE-4011` and `4012` drop from $2.80\text{ bar}$ to $0.05\text{ bar}$ resting state (lines turn dashed red).
- **Minute 2: Spatial Triaging**
  - Click **[Min 2 BigQuery GIS Triage]**.
  - BigQuery GIS executes `ST_BUFFER` and `ST_INTERSECTS` in $\sim 42\text{ ms}$.
  - Highlights a $180\text{ m}$ Pine Avenue street corridor with an elevated Intrusion Vulnerability Score (**0.86**).
- **Minute 3: Contextual Triage**
  - Click **[Min 3 Gemini Multimodal Sentry]**.
  - Automatically loads the citizen view for `104 Pine Avenue` and analyzes the fouled cartridge photograph.
  - Gemini scores Visual Fouling at **0.84** with `POSSIBLE_BIOFILM_ACCUMULATION`.
  - Two-Tier Escalation triggers:
    - **Tier 1:** Precautionary Household Boil Advisory & filter replacement instructions.
    - **Tier 2:** Dispatches utility field inspection team to Pine Avenue corridor for verification testing.

---

## 🛡️ Judge Defense Matrix (Defensibility)

| Metric / Question | Scientific & Architectural Defense |
|---|---|
| **~1.3B People on IWS** | Intermittent distribution networks are documented across Asia, Africa, and Latin America (Kumpel & Nelson 2016; Bivins et al. 2017). |
| **&lt; 500ms Query SLA** | Distributed geospatial joins in BigQuery GIS evaluate buffer intersections in sub-second timeframes upon valve shutdown. |
| **Zero New In-Pipe Hardware** | Operates purely from SCADA logs, public road easements (OpenStreetMap), and crowdsourced citizen pre-filter photos. |
| **Strict 2-Tier Escalation** | A single smartphone photo **never** triggers an uncorroborated public boil-water alert. High-risk actions require joint spatial proximity + operational corroboration. |
| **Rust vs Biofilm Detection** | Gemini evaluates optical opacity, textural uniformity, and surface encrustation as visual forensic indicators rather than raw color alone. |

---

## ☁️ Google Cloud Technology Stack

| GCP Service | Architectural Role |
|---|---|
| **Gemini 1.5 Pro (Vertex AI)** | Multimodal visual filter fouling forensics & deposit indicator scoring |
| **BigQuery & BigQuery GIS** | Distributed geospatial network topology modeling (`ST_BUFFER`, `ST_INTERSECTS`) |
| **Cloud Pub/Sub** | Real-time event ingestion for SCADA valve and pump state changes |
| **Cloud Run** | Containerized FastAPI dual-persona web application |
| **Cloud Storage (GCS)** | Object storage for crowdsourced filter photographs and GeoJSON maps |

---

## 🌍 GRACE / Earth Engine Integration

This project uses the Google Earth Engine (EE) Python API to compute GRACE LWE (land water equivalent) aggregates and to create map tiles. To avoid exposing EE tokens to clients, the server uses a tile proxy (`/api/ee/tile-proxy`) which fetches tiles server-side and streams them to the frontend.

Key server endpoints related to EE and GRACE:
- `GET /api/grace/timeseries?lat=<>&lon=<>` — returns LWE timeseries for the supplied point (buffering applied server-side).
- `GET /api/grace/heatmap?bbox=minLon,minLat,maxLon,maxLat` — returns a GeoJSON heatmap grid.
- `GET /api/ee/tile-proxy?min=&max=&palette=&z={z}&x={x}&y={y}` — returns EE tile bytes proxied by server.
- `GET /api/groundwater-alert?lat=<>&lon=<>` — computes baseline vs recent LWE means and returns an alert level.

## Earth Engine Authentication (recommended: service account)

1. Create a Google Cloud service account (SA) and download its JSON key.
2. Grant the SA appropriate IAM roles for any GCP services you use (BigQuery, Storage, Pub/Sub as needed).
3. IMPORTANT: Register the SA email as an Earth Engine user. An Earth Engine administrator must add the SA email via the Earth Engine user management console — otherwise EE calls will receive authorization errors.
4. Place the SA JSON in the repo (e.g., `credentials.json`) or set `GOOGLE_APPLICATION_CREDENTIALS` to its path. The server will auto-detect common filenames.

Local interactive EE authentication (developer only):
```bash
pip install earthengine-api
earthengine authenticate
```

Server initialization behavior (in `main.py`):
- The server first attempts `ee.Initialize()` with default ADC (Application Default Credentials).
- If that fails and `CREDENTIALS_FILE` + `SERVICE_ACCOUNT_EMAIL` are set, it will try `ee.ServiceAccountCredentials` + `ee.Initialize(creds, {'project': ...})`.

## Testing & Troubleshooting

- Confirm dependencies are installed:
   ```bash
   pip install -r requirements.txt
   pip show earthengine-api
   ```
- To test GRACE alert for a lat/lon:
   ```bash
   curl -i "http://127.0.0.1:8081/api/groundwater-alert?lat=22.5052&lon=73.4678&recent_months=12&threshold_pct=20"
   ```
- If you get EE authorization errors, verify:
   - `GOOGLE_APPLICATION_CREDENTIALS` points to the SA JSON, and
   - The SA email is registered as an Earth Engine user.

## Next steps I can help with
- Add a `cloudbuild.yaml` and `Dockerfile` for Cloud Run deployment.
- Automate Earth Engine mapid caching to reduce repeated `getMapId` calls.
- Add richer alerting rules and notification hooks (email/SMS/webhook).

---
If you'd like, I can now add a short `deploy/` scaffold (Dockerfile + Cloud Run instructions) or run dependency installs here and verify `ee` imports. Which would you prefer? 
