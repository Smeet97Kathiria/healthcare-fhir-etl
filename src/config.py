import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    fhir_base_url: str = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")
    patient_limit: int = int(os.getenv("PATIENT_LIMIT", "25"))
    observation_limit: int = int(os.getenv("OBSERVATION_LIMIT", "100"))
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "healthcare_fhir.db")
    data_classification: str = os.getenv("DATA_CLASSIFICATION", "synthetic")
    allow_phi: bool = os.getenv("ALLOW_PHI", "false").lower() == "true"
    app_actor: str = os.getenv("APP_ACTOR", "local-operator")
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"


settings = Settings()
