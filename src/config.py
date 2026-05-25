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
    fhir_auth_mode: str = os.getenv("FHIR_AUTH_MODE", "none")
    epic_fhir_base_url: str = os.getenv(
        "EPIC_FHIR_BASE_URL",
        "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
    )
    epic_client_id: str = os.getenv("EPIC_CLIENT_ID", "")
    epic_redirect_uri: str = os.getenv("EPIC_REDIRECT_URI", "http://localhost:8000/oauth/callback")
    epic_scopes: str = os.getenv(
        "EPIC_SCOPES",
        "launch/patient patient/Patient.read patient/Observation.read patient/Encounter.read patient/Condition.read offline_access",
    )
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"


settings = Settings()
