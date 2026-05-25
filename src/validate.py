from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field, ValidationError


class PatientRecord(BaseModel):
    patient_id: str = Field(min_length=1)
    gender: str | None = None
    birth_date: str | None = None


class ObservationRecord(BaseModel):
    observation_id: str = Field(min_length=1)
    patient_id: str | None = None
    code: str | None = None
    display: str | None = None
    effective_datetime: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None


def validate_records(records: List[Dict[str, Any]], model: type[BaseModel]) -> Tuple[List[Dict[str, Any]], List[str]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[str] = []

    for index, record in enumerate(records):
        try:
            valid_records.append(model(**record).model_dump())
        except ValidationError as exc:
            errors.append(f"Record {index}: {exc}")

    return valid_records, errors
