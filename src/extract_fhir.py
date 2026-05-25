import json
import os
from typing import Any, Dict, List

import requests

from src.config import settings


def _request_fhir_resource(resource_type: str, count: int) -> Dict[str, Any]:
    """Fetch a FHIR Bundle for a resource type from the configured FHIR server."""
    url = f"{settings.fhir_base_url.rstrip('/')}/{resource_type}"
    params = {"_count": count}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _bundle_entries(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = bundle.get("entry", [])
    return [entry.get("resource", {}) for entry in entries if entry.get("resource")]


def extract_patients() -> List[Dict[str, Any]]:
    bundle = _request_fhir_resource("Patient", settings.patient_limit)
    return _bundle_entries(bundle)


def extract_observations() -> List[Dict[str, Any]]:
    bundle = _request_fhir_resource("Observation", settings.observation_limit)
    return _bundle_entries(bundle)


def save_raw_json(resource_name: str, records: List[Dict[str, Any]]) -> str:
    os.makedirs(settings.raw_dir, exist_ok=True)
    path = os.path.join(settings.raw_dir, f"{resource_name}.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)
    return path


def run_extract() -> Dict[str, int]:
    patients = extract_patients()
    observations = extract_observations()

    save_raw_json("patients", patients)
    save_raw_json("observations", observations)

    return {
        "patients_extracted": len(patients),
        "observations_extracted": len(observations),
    }
