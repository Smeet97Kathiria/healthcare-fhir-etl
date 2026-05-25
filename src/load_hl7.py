import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.config import settings
from src.load_sqlite import initialize_database, insert_audit_record, load_dataframe


HL7_DIR = Path("data/hl7/messages")


def _segments(message: str) -> List[List[str]]:
    normalized = message.replace("\n", "\r")
    return [segment.split("|") for segment in normalized.split("\r") if segment.strip()]


def _field(segment: List[str], index: int) -> str:
    return segment[index] if len(segment) > index else ""


def _component(value: str, index: int) -> str:
    parts = value.split("^")
    return parts[index] if len(parts) > index else ""


def _patient_name(pid: List[str]) -> str:
    name = _field(pid, 5)
    family = _component(name, 0)
    given = _component(name, 1)
    return f"{given} {family}".strip()


def _parse_message(message: str) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    segments = _segments(message)
    segment_map: Dict[str, List[List[str]]] = {}
    for segment in segments:
        segment_map.setdefault(segment[0], []).append(segment)

    msh = segment_map.get("MSH", [[]])[0]
    pid = segment_map.get("PID", [[]])[0]
    pv1 = segment_map.get("PV1", [[]])[0] if segment_map.get("PV1") else []
    obr = segment_map.get("OBR", [[]])[0] if segment_map.get("OBR") else []

    message_type = _field(msh, 8)
    message_parts = message_type.split("^")
    message_id = _field(msh, 9)
    patient_id = _component(_field(pid, 3), 0)
    patient_name = _patient_name(pid)

    message_row = {
        "message_id": message_id,
        "message_type": message_parts[0] if message_parts else "",
        "trigger_event": message_parts[1] if len(message_parts) > 1 else "",
        "sending_application": _field(msh, 2),
        "sending_facility": _field(msh, 3),
        "receiving_application": _field(msh, 4),
        "receiving_facility": _field(msh, 5),
        "message_timestamp": _field(msh, 6),
        "patient_id": patient_id,
        "patient_name": patient_name,
        "event_type": _field(pv1, 18) if pv1 else _component(_field(obr, 4), 1),
        "raw_message": message,
    }

    result_rows = []
    order_id = _field(obr, 2) or _field(obr, 3)
    for obx in segment_map.get("OBX", []):
        observation_id = _field(obx, 3)
        code = _component(observation_id, 0)
        name = _component(observation_id, 1)
        result_rows.append(
            {
                "result_id": f"{message_id}-{_field(obx, 1)}",
                "message_id": message_id,
                "patient_id": patient_id,
                "order_id": order_id,
                "observation_id": _field(obx, 1),
                "observation_code": code,
                "observation_name": name,
                "value_type": _field(obx, 2),
                "observation_value": _field(obx, 5),
                "units": _field(obx, 6),
                "reference_range": _field(obx, 7),
                "abnormal_flag": _field(obx, 8),
                "result_status": _field(obx, 11),
                "observation_timestamp": _field(obx, 14),
            }
        )

    return message_row, result_rows


def run_hl7_load(directory: Path = HL7_DIR) -> Dict[str, int]:
    paths = sorted(directory.glob("*.hl7"))
    if not paths:
        raise FileNotFoundError(f"No HL7 files found in {directory}")

    message_rows = []
    result_rows = []
    for path in paths:
        message = path.read_text(encoding="utf-8")
        message_row, parsed_results = _parse_message(message)
        message_rows.append(message_row)
        result_rows.extend(parsed_results)

    messages_df = pd.DataFrame(message_rows)
    results_df = pd.DataFrame(result_rows)

    with sqlite3.connect(settings.sqlite_db_path) as conn:
        initialize_database(conn)
        conn.execute("DELETE FROM hl7_messages")
        conn.execute("DELETE FROM hl7_results")
        conn.commit()

        stats = {
            "source_mode": "synthetic_hl7",
            "hl7_messages_extracted": len(messages_df),
            "hl7_results_extracted": len(results_df),
            "hl7_messages_loaded": load_dataframe(conn, messages_df, "hl7_messages"),
            "hl7_results_loaded": load_dataframe(conn, results_df, "hl7_results"),
        }
        insert_audit_record(conn, stats)

    return stats
