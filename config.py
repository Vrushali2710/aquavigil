import os

class Settings:
    APP_NAME: str = "AquaVigil Platform"
    APP_VERSION: str = "1.0.0"
    TRACK: str = "Sustainability & Community Resilience"
    PORT: int = 8080
    HOST: str = "127.0.0.1"
    
    # Google Cloud settings
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "aquavigil-cloud-run")
    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "aquavigil_dataset")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    
    # Simulation settings
    PROXIMITY_BUFFER_METERS: float = 5.0
    SECTOR_FOCUS: str = "SECTOR_04_SOUTH"

settings = Settings()
