import json
from datetime import date, datetime, timedelta
from pathlib import Path


OUTPUT_DIR = Path("data/synthea/generated")

PATIENTS = [
    ("pat-001", "Maya", "Patel", "female", "1986-04-12", "Hypertension", "Diabetes follow-up"),
    ("pat-002", "James", "Robinson", "male", "1972-11-03", "Type 2 diabetes mellitus", "Annual wellness visit"),
    ("pat-003", "Sofia", "Garcia", "female", "1994-08-21", "Asthma", "Urgent care visit"),
    ("pat-004", "Liam", "Nguyen", "male", "2011-02-18", "Seasonal allergic rhinitis", "Pediatric checkup"),
    ("pat-005", "Ava", "Williams", "female", "1958-06-30", "Chronic kidney disease stage 3", "Nephrology follow-up"),
    ("pat-006", "Noah", "Brown", "male", "1948-01-09", "Congestive heart failure", "Cardiology follow-up"),
    ("pat-007", "Emma", "Johnson", "female", "2002-09-14", "Iron deficiency anemia", "Primary care visit"),
    ("pat-008", "Ethan", "Miller", "male", "1981-12-27", "Hyperlipidemia", "Lab review"),
    ("pat-009", "Olivia", "Davis", "female", "1966-05-08", "Osteoarthritis", "Orthopedic consult"),
    ("pat-010", "Lucas", "Martinez", "male", "1990-03-24", "Major depressive disorder", "Behavioral health visit"),
    ("pat-011", "Mia", "Anderson", "female", "1978-07-19", "Migraine", "Neurology follow-up"),
    ("pat-012", "Benjamin", "Taylor", "male", "2016-10-02", "Acute otitis media", "Same-day pediatric visit"),
]

CONDITION_CODES = {
    "Hypertension": ("38341003", "Hypertension"),
    "Type 2 diabetes mellitus": ("44054006", "Diabetes mellitus type 2"),
    "Asthma": ("195967001", "Asthma"),
    "Seasonal allergic rhinitis": ("367498001", "Seasonal allergic rhinitis"),
    "Chronic kidney disease stage 3": ("433144002", "Chronic kidney disease stage 3"),
    "Congestive heart failure": ("42343007", "Congestive heart failure"),
    "Iron deficiency anemia": ("87522002", "Iron deficiency anemia"),
    "Hyperlipidemia": ("55822004", "Hyperlipidemia"),
    "Osteoarthritis": ("396275006", "Osteoarthritis"),
    "Major depressive disorder": ("370143000", "Major depressive disorder"),
    "Migraine": ("37796009", "Migraine"),
    "Acute otitis media": ("3110003", "Acute otitis media"),
}

OBSERVATIONS = [
    ("8302-2", "Body height", "cm", 150, 196),
    ("29463-7", "Body weight", "kg", 45, 108),
    ("8867-4", "Heart rate", "beats/min", 58, 102),
    ("8480-6", "Systolic blood pressure", "mmHg", 104, 158),
    ("8462-4", "Diastolic blood pressure", "mmHg", 62, 94),
    ("2339-0", "Glucose", "mg/dL", 78, 178),
    ("4548-4", "Hemoglobin A1c", "%", 4.9, 8.8),
    ("2093-3", "Total cholesterol", "mg/dL", 142, 268),
]


def _patient(patient_id, given, family, gender, birth_date):
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "active": True,
        "name": [{"use": "official", "family": family, "given": [given]}],
        "gender": gender,
        "birthDate": birth_date,
    }


def _encounter(patient_id, index, reason, start):
    encounter_id = f"enc-{patient_id}-{index}"
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "type": [{"text": reason}],
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": start.isoformat(), "end": (start + timedelta(minutes=42)).isoformat()},
        "reasonCode": [{"text": reason}],
    }


def _condition(patient_id, encounter_id, condition_name, recorded):
    code, display = CONDITION_CODES[condition_name]
    return {
        "resourceType": "Condition",
        "id": f"cond-{patient_id}",
        "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
        "verificationStatus": {"coding": [{"code": "confirmed", "display": "Confirmed"}]},
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": code, "display": display}], "text": display},
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "onsetDateTime": (recorded - timedelta(days=260)).isoformat(),
        "recordedDate": recorded.date().isoformat(),
    }


def _observation(patient_id, encounter_id, patient_index, observation_index, code, display, unit, low, high, effective):
    spread = high - low
    percentile = ((patient_index * 13) + (observation_index * 7)) % 100 / 100
    if code == "4548-4":
        percentile = [0.18, 0.34, 0.48, 0.63, 0.72, 0.86][patient_index % 6]
    if code == "8480-6":
        percentile = [0.22, 0.36, 0.51, 0.67, 0.81, 0.43][patient_index % 6]
    value = round(low + percentile * spread, 1)
    return {
        "resourceType": "Observation",
        "id": f"obs-{patient_id}-{code}",
        "status": "final",
        "category": [{"coding": [{"code": "vital-signs", "display": "Vital Signs"}]}],
        "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}], "text": display},
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "effectiveDateTime": effective.isoformat(),
        "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
    }


def _bundle(resources, patient_id):
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "id": f"bundle-{patient_id}",
        "entry": [{"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource} for resource in resources],
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale_file in OUTPUT_DIR.glob("*.json"):
        stale_file.unlink()

    base = datetime(2026, 3, 1, 9, 0, 0)
    for index, (patient_id, given, family, gender, birth_date, condition_name, reason) in enumerate(PATIENTS, start=1):
        start = base - timedelta(days=index * 11)
        patient = _patient(patient_id, given, family, gender, birth_date)
        encounter = _encounter(patient_id, 1, reason, start)
        condition = _condition(patient_id, encounter["id"], condition_name, start)
        observations = [
            _observation(patient_id, encounter["id"], index, obs_index, *spec, effective=start + timedelta(minutes=obs_index * 3))
            for obs_index, spec in enumerate(OBSERVATIONS, start=1)
        ]
        bundle = _bundle([patient, encounter, condition, *observations], patient_id)
        output_path = OUTPUT_DIR / f"{patient_id}.json"
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(bundle, file, indent=2)

    print(f"Generated {len(PATIENTS)} synthetic FHIR bundles in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
