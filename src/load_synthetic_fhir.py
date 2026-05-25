import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

from src.config import settings
from src.load_sqlite import initialize_database, insert_audit_record, load_dataframe


SYNTHETIC_DIR = Path("data/synthea")


def _load_json_files(directory: Path = SYNTHETIC_DIR) -> List[Dict[str, Any]]:
    if not directory.exists():
        return []

    payloads = []
    for path in sorted(directory.glob("**/*.json")):
        with open(path, "r", encoding="utf-8") as file:
            payloads.append(json.load(file))
    return payloads


def _bundle_resources(payloads: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resources: List[Dict[str, Any]] = []
    for payload in payloads:
        if payload.get("resourceType") == "Bundle":
            resources.extend(entry.get("resource", {}) for entry in payload.get("entry", []) if entry.get("resource"))
        elif payload.get("resourceType"):
            resources.append(payload)
    return resources


def _reference_id(reference: str | None) -> str | None:
    if not reference:
        return None
    return reference.split(":")[-1].split("/")[-1]


def _patient_name(patient: Dict[str, Any]) -> str | None:
    names = patient.get("name", [])
    if not names:
        return None
    name = names[0]
    given = " ".join(name.get("given", []))
    family = name.get("family", "")
    full_name = f"{given} {family}".strip()
    return full_name or None


def _coding(resource: Dict[str, Any], field: str = "code") -> tuple[str | None, str | None]:
    codeable = resource.get(field, {})
    coding = codeable.get("coding", [])
    if coding:
        first = coding[0]
        return first.get("code"), first.get("display") or codeable.get("text")
    return None, codeable.get("text")


def _concept_text(resource: Dict[str, Any], field: str) -> str | None:
    codeable = resource.get(field, {})
    coding = codeable.get("coding", [])
    if coding:
        return coding[0].get("display") or codeable.get("text")
    return codeable.get("text")


def _transform_patients(resources: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for patient in [resource for resource in resources if resource.get("resourceType") == "Patient"]:
        rows.append(
            {
                "patient_id": patient.get("id"),
                "full_name": _patient_name(patient),
                "gender": patient.get("gender"),
                "birth_date": patient.get("birthDate"),
                "active": patient.get("active", True),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["patient_id"]) if rows else pd.DataFrame()


def _transform_observations(resources: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for observation in [resource for resource in resources if resource.get("resourceType") == "Observation"]:
        code, display = _coding(observation)
        value_quantity = observation.get("valueQuantity", {})
        rows.append(
            {
                "observation_id": observation.get("id"),
                "patient_id": _reference_id(observation.get("subject", {}).get("reference")),
                "status": observation.get("status"),
                "code": code,
                "display": display,
                "effective_datetime": observation.get("effectiveDateTime") or observation.get("issued"),
                "value_numeric": value_quantity.get("value"),
                "value_text": observation.get("valueString") or observation.get("valueCodeableConcept", {}).get("text"),
                "unit": value_quantity.get("unit") or value_quantity.get("code"),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["observation_id"]) if rows else pd.DataFrame()


def _transform_encounters(resources: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for encounter in [resource for resource in resources if resource.get("resourceType") == "Encounter"]:
        class_info = encounter.get("class", {})
        encounter_type = encounter.get("type", [{}])[0] if encounter.get("type") else {}
        reason = encounter.get("reasonCode", [{}])[0] if encounter.get("reasonCode") else {}
        rows.append(
            {
                "encounter_id": encounter.get("id"),
                "patient_id": _reference_id(encounter.get("subject", {}).get("reference")),
                "status": encounter.get("status"),
                "class_code": class_info.get("code"),
                "class_display": class_info.get("display"),
                "type_display": _concept_text({"type": encounter_type}, "type"),
                "start_datetime": encounter.get("period", {}).get("start"),
                "end_datetime": encounter.get("period", {}).get("end"),
                "reason_display": _concept_text({"reason": reason}, "reason"),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["encounter_id"]) if rows else pd.DataFrame()


def _transform_conditions(resources: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for condition in [resource for resource in resources if resource.get("resourceType") == "Condition"]:
        code, display = _coding(condition)
        rows.append(
            {
                "condition_id": condition.get("id"),
                "patient_id": _reference_id(condition.get("subject", {}).get("reference")),
                "encounter_id": _reference_id(condition.get("encounter", {}).get("reference")),
                "clinical_status": _concept_text(condition, "clinicalStatus"),
                "verification_status": _concept_text(condition, "verificationStatus"),
                "code": code,
                "display": display,
                "onset_datetime": condition.get("onsetDateTime"),
                "recorded_date": condition.get("recordedDate"),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["condition_id"]) if rows else pd.DataFrame()


def run_synthetic_load(directory: Path = SYNTHETIC_DIR) -> Dict[str, int]:
    payloads = _load_json_files(directory)
    if not payloads:
        raise FileNotFoundError(f"No FHIR JSON files found in {directory}")

    resources = _bundle_resources(payloads)
    os.makedirs(settings.processed_dir, exist_ok=True)

    patients_df = _transform_patients(resources)
    observations_df = _transform_observations(resources)
    encounters_df = _transform_encounters(resources)
    conditions_df = _transform_conditions(resources)

    patients_df.to_csv(os.path.join(settings.processed_dir, "patients.csv"), index=False)
    observations_df.to_csv(os.path.join(settings.processed_dir, "observations.csv"), index=False)
    encounters_df.to_csv(os.path.join(settings.processed_dir, "encounters.csv"), index=False)
    conditions_df.to_csv(os.path.join(settings.processed_dir, "conditions.csv"), index=False)

    with sqlite3.connect(settings.sqlite_db_path) as conn:
        initialize_database(conn)
        for table in ("patients", "observations", "encounters", "conditions"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

        stats = {
            "source_mode": "synthetic_fhir",
            "patients_extracted": len(patients_df),
            "observations_extracted": len(observations_df),
            "encounters_extracted": len(encounters_df),
            "conditions_extracted": len(conditions_df),
            "patients_loaded": load_dataframe(conn, patients_df, "patients"),
            "observations_loaded": load_dataframe(conn, observations_df, "observations"),
            "encounters_loaded": load_dataframe(conn, encounters_df, "encounters"),
            "conditions_loaded": load_dataframe(conn, conditions_df, "conditions"),
        }
        insert_audit_record(conn, stats)

    return stats
