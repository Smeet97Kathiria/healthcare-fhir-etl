import json
import os
from typing import Any, Dict, List

import pandas as pd

from src.config import settings
from src.validate import ObservationRecord, PatientRecord, validate_records


def _load_raw(resource_name: str) -> List[Dict[str, Any]]:
    path = os.path.join(settings.raw_dir, f"{resource_name}.json")
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _patient_name(patient: Dict[str, Any]) -> str | None:
    names = patient.get("name", [])
    if not names:
        return None
    name = names[0]
    given = " ".join(name.get("given", []))
    family = name.get("family", "")
    full_name = f"{given} {family}".strip()
    return full_name or None


def transform_patients(raw_patients: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for patient in raw_patients:
        rows.append(
            {
                "patient_id": patient.get("id"),
                "full_name": _patient_name(patient),
                "gender": patient.get("gender"),
                "birth_date": patient.get("birthDate"),
                "active": patient.get("active"),
            }
        )

    valid_rows, errors = validate_records(rows, PatientRecord)
    df = pd.DataFrame(valid_rows)

    if not df.empty:
        # Add non-required columns back after validation model keeps core schema.
        full_df = pd.DataFrame(rows)
        df = full_df[full_df["patient_id"].isin(df["patient_id"])]

    if errors:
        print(f"Patient validation warnings: {len(errors)} invalid records skipped")

    return df


def _first_coding_display(observation: Dict[str, Any]) -> tuple[str | None, str | None]:
    coding = observation.get("code", {}).get("coding", [])
    if not coding:
        return None, observation.get("code", {}).get("text")
    first = coding[0]
    return first.get("code"), first.get("display") or observation.get("code", {}).get("text")


def _patient_reference(observation: Dict[str, Any]) -> str | None:
    subject = observation.get("subject", {}).get("reference")
    if not subject:
        return None
    # Common format: Patient/123
    return subject.split("/")[-1]


def transform_observations(raw_observations: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for observation in raw_observations:
        code, display = _first_coding_display(observation)
        value_quantity = observation.get("valueQuantity", {})
        rows.append(
            {
                "observation_id": observation.get("id"),
                "patient_id": _patient_reference(observation),
                "status": observation.get("status"),
                "code": code,
                "display": display,
                "effective_datetime": observation.get("effectiveDateTime"),
                "value_numeric": value_quantity.get("value"),
                "value_text": observation.get("valueString") or observation.get("valueCodeableConcept", {}).get("text"),
                "unit": value_quantity.get("unit"),
            }
        )

    valid_rows, errors = validate_records(rows, ObservationRecord)
    df = pd.DataFrame(valid_rows)

    if not df.empty:
        full_df = pd.DataFrame(rows)
        df = full_df[full_df["observation_id"].isin(df["observation_id"])]

    if errors:
        print(f"Observation validation warnings: {len(errors)} invalid records skipped")

    return df


def run_transform() -> Dict[str, int]:
    os.makedirs(settings.processed_dir, exist_ok=True)

    raw_patients = _load_raw("patients")
    raw_observations = _load_raw("observations")

    patients_df = transform_patients(raw_patients)
    observations_df = transform_observations(raw_observations)

    patients_df.to_csv(os.path.join(settings.processed_dir, "patients.csv"), index=False)
    observations_df.to_csv(os.path.join(settings.processed_dir, "observations.csv"), index=False)

    return {
        "patients_transformed": len(patients_df),
        "observations_transformed": len(observations_df),
    }
