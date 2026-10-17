import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Settings:
    APP_NAME: str = "AquaVigil Platform"
    APP_VERSION: str = "1.0.0"
    TRACK: str = "Sustainability & Community Resilience"
    PORT: int = int(os.getenv("PORT", "8080"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # Defaults
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "aquavigil-cloud-run")
    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "aquavigil_dataset")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    SERVICE_ACCOUNT_EMAIL: str = ""
    CREDENTIALS_FILE: str = ""

    # Simulation settings
    PROXIMITY_BUFFER_METERS: float = 5.0
    SECTOR_FOCUS: str = "SECTOR_04_SOUTH"

    def __init__(self):
        self._load_from_credentials_file()

    def _load_from_credentials_file(self):
        """
        Auto-detect Google Cloud Service Account JSON file.
        Checks GOOGLE_APPLICATION_CREDENTIALS, or common file names in the project folder.
        """
        candidate_files = [
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
            str(BASE_DIR / "credentials.json"),
            str(BASE_DIR / "gcp_credentials.json"),
            str(BASE_DIR / "service_account.json"),
            str(BASE_DIR / "key.json")
        ]

        for file_path in candidate_files:
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Verify it is a valid Google Service Account JSON
                    if data.get("type") == "service_account":
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = file_path
                        self.CREDENTIALS_FILE = file_path
                        if data.get("project_id"):
                            self.GOOGLE_CLOUD_PROJECT = data["project_id"]
                            os.environ["GOOGLE_CLOUD_PROJECT"] = data["project_id"]
                        if data.get("client_email"):
                            self.SERVICE_ACCOUNT_EMAIL = data["client_email"]
                        print(f"✓ Loaded Google Cloud credentials from: {file_path}")
                        print(f"  Account: {self.SERVICE_ACCOUNT_EMAIL}")
                        print(f"  Project: {self.GOOGLE_CLOUD_PROJECT}")
                        break
                except Exception as e:
                    print(f"Warning: could not parse credentials file {file_path}: {e}")

settings = Settings()
