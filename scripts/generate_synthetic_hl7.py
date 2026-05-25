from datetime import datetime, timedelta
from pathlib import Path


OUTPUT_DIR = Path("data/hl7/messages")

PATIENTS = [
    ("pat-001", "Patel", "Maya", "19860412", "F", "Diabetes follow-up"),
    ("pat-002", "Robinson", "James", "19721103", "M", "Annual wellness visit"),
    ("pat-003", "Garcia", "Sofia", "19940821", "F", "Urgent care visit"),
    ("pat-004", "Nguyen", "Liam", "20110218", "M", "Pediatric checkup"),
    ("pat-005", "Williams", "Ava", "19580630", "F", "Nephrology follow-up"),
    ("pat-006", "Brown", "Noah", "19480109", "M", "Cardiology follow-up"),
]

RESULTS = [
    ("8480-6", "Systolic blood pressure", "NM", "142", "mmHg", "90-120", "H"),
    ("8462-4", "Diastolic blood pressure", "NM", "82", "mmHg", "60-80", "H"),
    ("4548-4", "Hemoglobin A1c", "NM", "7.4", "%", "4.0-5.6", "H"),
    ("2339-0", "Glucose", "NM", "126", "mg/dL", "70-99", "H"),
]


def _timestamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _adt_message(index: int, patient_id: str, family: str, given: str, birth_date: str, gender: str, reason: str, timestamp: datetime) -> str:
    message_id = f"ADT{index:04d}"
    return "\r".join(
        [
            f"MSH|^~\\&|SYNTH_EHR|FHIR_OPS|INTERFACE|WAREHOUSE|{_timestamp(timestamp)}||ADT^A01|{message_id}|P|2.5.1",
            f"EVN|A01|{_timestamp(timestamp)}",
            f"PID|1||{patient_id}^^^FHIR_OPS^MR||{family}^{given}||{birth_date}|{gender}",
            f"PV1|1|O|AMB^FHIR^01||||1234^Care^Alex|||||||||||{reason}",
        ]
    )


def _oru_message(index: int, patient_id: str, family: str, given: str, birth_date: str, gender: str, timestamp: datetime) -> str:
    message_id = f"ORU{index:04d}"
    order_id = f"ORD{index:04d}"
    lines = [
        f"MSH|^~\\&|SYNTH_LAB|FHIR_OPS|INTERFACE|WAREHOUSE|{_timestamp(timestamp)}||ORU^R01|{message_id}|P|2.5.1",
        f"PID|1||{patient_id}^^^FHIR_OPS^MR||{family}^{given}||{birth_date}|{gender}",
        f"OBR|1|{order_id}|{order_id}|24323-8^Basic metabolic and vitals panel^LN|||{_timestamp(timestamp)}",
    ]
    for result_index, (code, name, value_type, value, unit, reference_range, flag) in enumerate(RESULTS, start=1):
        adjusted_value = value
        if value_type == "NM":
            adjusted_value = str(round(float(value) + (index % 3) * 2.1, 1))
        lines.append(
            f"OBX|{result_index}|{value_type}|{code}^{name}^LN||{adjusted_value}|{unit}|{reference_range}|{flag}|||F|||{_timestamp(timestamp + timedelta(minutes=result_index))}"
        )
    return "\r".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale_file in OUTPUT_DIR.glob("*.hl7"):
        stale_file.unlink()

    base = datetime(2026, 3, 15, 8, 30, 0)
    for index, patient in enumerate(PATIENTS, start=1):
        patient_id, family, given, birth_date, gender, reason = patient
        timestamp = base + timedelta(hours=index)
        (OUTPUT_DIR / f"{index:02d}_{patient_id}_adt.hl7").write_text(
            _adt_message(index, patient_id, family, given, birth_date, gender, reason, timestamp),
            encoding="utf-8",
        )
        (OUTPUT_DIR / f"{index:02d}_{patient_id}_oru.hl7").write_text(
            _oru_message(index, patient_id, family, given, birth_date, gender, timestamp + timedelta(minutes=20)),
            encoding="utf-8",
        )

    print(f"Generated {len(PATIENTS) * 2} synthetic HL7 v2 messages in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
