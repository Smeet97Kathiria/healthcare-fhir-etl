from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"


@dataclass(frozen=True)
class DashboardSettings:
    fhir_base_url: str = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")
    patient_limit: int = int(os.getenv("PATIENT_LIMIT", "25"))
    observation_limit: int = int(os.getenv("OBSERVATION_LIMIT", "100"))
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "healthcare_fhir.db")
    data_classification: str = os.getenv("DATA_CLASSIFICATION", "synthetic")
    allow_phi: bool = os.getenv("ALLOW_PHI", "false").lower() == "true"
    app_actor: str = os.getenv("APP_ACTOR", "system-operator")
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


settings = DashboardSettings()
DB_PATH = ROOT_DIR / settings.sqlite_db_path


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _database_exists() -> bool:
    return DB_PATH.exists()


def _fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if not _database_exists():
        return []
    with _connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def _fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = _fetch_all(query, params)
    return rows[0] if rows else {}


def _ensure_compliance_table() -> None:
    if not _database_exists():
        return
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compliance_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_timestamp TEXT NOT NULL,
                actor TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                purpose TEXT,
                outcome TEXT
            )
            """
        )
        conn.commit()


def _record_compliance_event(
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    purpose: str = "operations",
    outcome: str = "success",
) -> None:
    if not _database_exists():
        return
    _ensure_compliance_table()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO compliance_events (
                event_timestamp, actor, action, resource_type, resource_id, purpose, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                settings.app_actor,
                action,
                resource_type,
                resource_id,
                purpose,
                outcome,
            ),
        )
        conn.commit()


def _compliance_posture() -> dict[str, Any]:
    _ensure_compliance_table()
    recent_events = _fetch_all(
        """
        SELECT event_timestamp, actor, action, resource_type, resource_id, purpose, outcome
        FROM compliance_events
        ORDER BY event_id DESC
        LIMIT 8
        """
    )
    is_phi_mode = settings.data_classification.lower() in {"phi", "ephi", "production_phi"}
    phi_blocked = is_phi_mode and not settings.allow_phi
    status = "Non-PHI mode" if not is_phi_mode else ("PHI enabled" if settings.allow_phi else "PHI blocked")

    return {
        "status": status,
        "data_classification": settings.data_classification,
        "phi_allowed": settings.allow_phi,
        "phi_blocked": phi_blocked,
        "actor": settings.app_actor,
        "recent_events": recent_events,
        "controls": [
            {
                "name": "Non-PHI data default",
                "status": "pass" if settings.data_classification == "synthetic" else "review",
                "detail": "Default mode uses generated records and avoids real PHI.",
            },
            {
                "name": "PHI ingestion guard",
                "status": "pass" if not settings.allow_phi else "review",
                "detail": "Real PHI requires explicit ALLOW_PHI=true and production safeguards.",
            },
            {
                "name": "ETL audit trail",
                "status": "pass" if bool(_fetch_one("SELECT COUNT(*) AS count FROM etl_audit").get("count", 0)) else "review",
                "detail": "Each load stores source mode plus extracted and loaded counts.",
            },
            {
                "name": "Access event logging",
                "status": "pass",
                "detail": "Patient drill-down and dashboard actions are written to compliance_events.",
            },
            {
                "name": "Minimum necessary views",
                "status": "pass",
                "detail": "Dashboard uses curated tables instead of exposing full raw FHIR bundles.",
            },
            {
                "name": "Production gaps",
                "status": "review",
                "detail": "A real PHI deployment still needs RBAC, TLS, encryption/key management, BAA, risk analysis, and incident response.",
            },
        ],
    }


def _summary() -> dict[str, Any]:
    if not _database_exists():
        return {
            "database_ready": False,
            "patients": 0,
            "encounters": 0,
            "conditions": 0,
            "observations": 0,
            "hl7_messages": 0,
            "hl7_results": 0,
            "observation_codes": 0,
            "missing_patient_references": 0,
            "coded_observation_rate": 0,
            "valued_observation_rate": 0,
            "last_run": None,
            "compliance_status": "Not ready",
        }

    total_observations = _fetch_one("SELECT COUNT(*) AS count FROM observations").get("count", 0)

    return {
        "database_ready": True,
        "patients": _fetch_one("SELECT COUNT(*) AS count FROM patients").get("count", 0),
        "encounters": _fetch_one("SELECT COUNT(*) AS count FROM encounters").get("count", 0),
        "conditions": _fetch_one("SELECT COUNT(*) AS count FROM conditions").get("count", 0),
        "observations": total_observations,
        "hl7_messages": _fetch_one("SELECT COUNT(*) AS count FROM hl7_messages").get("count", 0),
        "hl7_results": _fetch_one("SELECT COUNT(*) AS count FROM hl7_results").get("count", 0),
        "observation_codes": _fetch_one("SELECT COUNT(DISTINCT code) AS count FROM observations WHERE code IS NOT NULL").get("count", 0),
        "missing_patient_references": _fetch_one(
            "SELECT COUNT(*) AS count FROM observations WHERE patient_id IS NULL OR patient_id = ''"
        ).get("count", 0),
        "coded_observation_rate": _percent(
            _fetch_one("SELECT COUNT(*) AS count FROM observations WHERE code IS NOT NULL AND code != ''").get("count", 0),
            total_observations,
        ),
        "valued_observation_rate": _percent(
            _fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM observations
                WHERE value_numeric IS NOT NULL
                   OR (value_text IS NOT NULL AND value_text != '')
                """
            ).get("count", 0),
            total_observations,
        ),
        "last_run": _fetch_one(
            """
            SELECT run_timestamp,
                   source_mode,
                   patients_extracted,
                   observations_extracted,
                   encounters_extracted,
                   conditions_extracted,
                   hl7_messages_extracted,
                   hl7_results_extracted,
                   patients_loaded,
                   observations_loaded,
                   encounters_loaded,
                   conditions_loaded,
                   hl7_messages_loaded,
                   hl7_results_loaded
            FROM etl_audit
            ORDER BY audit_id DESC
            LIMIT 1
            """
        )
        or None,
        "compliance_status": _compliance_posture()["status"],
    }


def _percent(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0
    return round((numerator / denominator) * 100, 1)


def _analytics() -> dict[str, Any]:
    return {
        "patient_count_by_gender": _fetch_all(
            """
            SELECT COALESCE(gender, 'unknown') AS gender, COUNT(*) AS patient_count
            FROM patients
            GROUP BY COALESCE(gender, 'unknown')
            ORDER BY patient_count DESC
            """
        ),
        "top_observation_codes": _fetch_all(
            """
            SELECT COALESCE(code, 'unknown') AS code,
                   COALESCE(display, 'Unlabeled observation') AS display,
                   COUNT(*) AS observation_count
            FROM observations
            GROUP BY COALESCE(code, 'unknown'), COALESCE(display, 'Unlabeled observation')
            ORDER BY observation_count DESC
            LIMIT 10
            """
        ),
        "top_conditions": _fetch_all(
            """
            SELECT COALESCE(code, 'unknown') AS code,
                   COALESCE(display, 'Unlabeled condition') AS display,
                   COUNT(*) AS condition_count
            FROM conditions
            GROUP BY COALESCE(code, 'unknown'), COALESCE(display, 'Unlabeled condition')
            ORDER BY condition_count DESC, display
            LIMIT 10
            """
        ),
        "encounter_classes": _fetch_all(
            """
            SELECT COALESCE(class_display, class_code, 'unknown') AS encounter_class,
                   COUNT(*) AS encounter_count
            FROM encounters
            GROUP BY COALESCE(class_display, class_code, 'unknown')
            ORDER BY encounter_count DESC
            """
        ),
        "hl7_message_types": _fetch_all(
            """
            SELECT message_type || '^' || trigger_event AS message_type,
                   COUNT(*) AS message_count
            FROM hl7_messages
            GROUP BY message_type, trigger_event
            ORDER BY message_count DESC
            """
        ),
        "hl7_abnormal_results": _fetch_all(
            """
            SELECT COALESCE(observation_code, 'unknown') AS code,
                   COALESCE(observation_name, 'Unlabeled result') AS display,
                   COUNT(*) AS abnormal_count
            FROM hl7_results
            WHERE abnormal_flag IS NOT NULL AND abnormal_flag != ''
            GROUP BY COALESCE(observation_code, 'unknown'), COALESCE(observation_name, 'Unlabeled result')
            ORDER BY abnormal_count DESC, display
            LIMIT 8
            """
        ),
        "latest_hl7_messages": _fetch_all(
            """
            SELECT message_id, message_type, trigger_event, sending_application, patient_id, patient_name, event_type, message_timestamp
            FROM hl7_messages
            ORDER BY message_timestamp DESC
            LIMIT 8
            """
        ),
        "recent_observations": _fetch_all(
            """
            SELECT observation_id, patient_id, status, display, effective_datetime, value_numeric, value_text, unit
            FROM observations
            ORDER BY effective_datetime DESC
            LIMIT 10
            """
        ),
        "patient_age_bands": _fetch_all(
            """
            SELECT
                CASE
                    WHEN birth_date IS NULL OR birth_date = '' THEN 'Unknown'
                    WHEN CAST((julianday('now') - julianday(birth_date)) / 365.25 AS INTEGER) < 18 THEN '0-17'
                    WHEN CAST((julianday('now') - julianday(birth_date)) / 365.25 AS INTEGER) BETWEEN 18 AND 34 THEN '18-34'
                    WHEN CAST((julianday('now') - julianday(birth_date)) / 365.25 AS INTEGER) BETWEEN 35 AND 49 THEN '35-49'
                    WHEN CAST((julianday('now') - julianday(birth_date)) / 365.25 AS INTEGER) BETWEEN 50 AND 64 THEN '50-64'
                    ELSE '65+'
                END AS age_band,
                COUNT(*) AS patient_count
            FROM patients
            GROUP BY age_band
            ORDER BY
                CASE age_band
                    WHEN '0-17' THEN 1
                    WHEN '18-34' THEN 2
                    WHEN '35-49' THEN 3
                    WHEN '50-64' THEN 4
                    WHEN '65+' THEN 5
                    ELSE 6
                END
            """
        ),
        "observation_completeness": _fetch_all(
            """
            SELECT 'Patient reference present' AS check_name,
                   SUM(CASE WHEN patient_id IS NOT NULL AND patient_id != '' THEN 1 ELSE 0 END) AS passed_count,
                   COUNT(*) AS total_count
            FROM observations
            UNION ALL
            SELECT 'Clinical code present' AS check_name,
                   SUM(CASE WHEN code IS NOT NULL AND code != '' THEN 1 ELSE 0 END) AS passed_count,
                   COUNT(*) AS total_count
            FROM observations
            UNION ALL
            SELECT 'Observation value present' AS check_name,
                   SUM(CASE WHEN value_numeric IS NOT NULL OR (value_text IS NOT NULL AND value_text != '') THEN 1 ELSE 0 END) AS passed_count,
                   COUNT(*) AS total_count
            FROM observations
            UNION ALL
            SELECT 'Effective date present' AS check_name,
                   SUM(CASE WHEN effective_datetime IS NOT NULL AND effective_datetime != '' THEN 1 ELSE 0 END) AS passed_count,
                   COUNT(*) AS total_count
            FROM observations
            UNION ALL
            SELECT 'Encounter link present' AS check_name,
                   SUM(CASE WHEN encounter_id IS NOT NULL AND encounter_id != '' THEN 1 ELSE 0 END) AS passed_count,
                   COUNT(*) AS total_count
            FROM conditions
            """
        ),
        "patient_observation_coverage": _fetch_all(
            """
            SELECT
                CASE
                    WHEN observation_count = 0 THEN '0 observations'
                    WHEN observation_count BETWEEN 1 AND 2 THEN '1-2 observations'
                    WHEN observation_count BETWEEN 3 AND 5 THEN '3-5 observations'
                    ELSE '6+ observations'
                END AS coverage_band,
                COUNT(*) AS patient_count
            FROM (
                SELECT p.patient_id, COUNT(o.observation_id) AS observation_count
                FROM patients p
                LEFT JOIN observations o ON p.patient_id = o.patient_id
                GROUP BY p.patient_id
            )
            GROUP BY coverage_band
            ORDER BY
                CASE coverage_band
                    WHEN '0 observations' THEN 1
                    WHEN '1-2 observations' THEN 2
                    WHEN '3-5 observations' THEN 3
                    ELSE 4
                END
            """
        ),
        "care_gaps": _fetch_all(
            """
            SELECT p.patient_id,
                   p.full_name,
                   p.gender,
                   p.birth_date,
                   COUNT(DISTINCT e.encounter_id) AS encounter_count,
                   COUNT(DISTINCT c.condition_id) AS condition_count,
                   COUNT(DISTINCT o.observation_id) AS observation_count,
                   MAX(o.effective_datetime) AS latest_observation,
                   SUM(CASE WHEN o.code = '8480-6' AND o.value_numeric >= 140 THEN 1 ELSE 0 END) AS high_systolic_events,
                   SUM(CASE WHEN o.code = '4548-4' AND o.value_numeric >= 7 THEN 1 ELSE 0 END) AS high_a1c_events
            FROM patients p
            LEFT JOIN encounters e ON p.patient_id = e.patient_id
            LEFT JOIN conditions c ON p.patient_id = c.patient_id
            LEFT JOIN observations o ON p.patient_id = o.patient_id
            GROUP BY p.patient_id, p.full_name, p.gender, p.birth_date
            ORDER BY high_a1c_events DESC, high_systolic_events DESC, condition_count DESC, latest_observation DESC
            LIMIT 8
            """
        ),
    }


def _patients(limit: int, search: str) -> list[dict[str, Any]]:
    pattern = f"%{search.lower()}%"
    return _fetch_all(
        """
        SELECT patient_id, full_name, gender, birth_date, active
        FROM patients
        WHERE ? = ''
           OR LOWER(COALESCE(full_name, '')) LIKE ?
           OR LOWER(patient_id) LIKE ?
           OR LOWER(COALESCE(gender, '')) LIKE ?
        ORDER BY full_name IS NULL, full_name, patient_id
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )


def _observations(limit: int, search: str) -> list[dict[str, Any]]:
    pattern = f"%{search.lower()}%"
    return _fetch_all(
        """
        SELECT observation_id, patient_id, status, code, display, effective_datetime, value_numeric, value_text, unit
        FROM observations
        WHERE ? = ''
           OR LOWER(COALESCE(display, '')) LIKE ?
           OR LOWER(COALESCE(code, '')) LIKE ?
           OR LOWER(COALESCE(patient_id, '')) LIKE ?
        ORDER BY effective_datetime DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )


def _encounters(limit: int, search: str) -> list[dict[str, Any]]:
    pattern = f"%{search.lower()}%"
    return _fetch_all(
        """
        SELECT encounter_id, patient_id, status, class_display, type_display, start_datetime, end_datetime, reason_display
        FROM encounters
        WHERE ? = ''
           OR LOWER(COALESCE(type_display, '')) LIKE ?
           OR LOWER(COALESCE(reason_display, '')) LIKE ?
           OR LOWER(COALESCE(patient_id, '')) LIKE ?
        ORDER BY start_datetime DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )


def _conditions(limit: int, search: str) -> list[dict[str, Any]]:
    pattern = f"%{search.lower()}%"
    return _fetch_all(
        """
        SELECT condition_id, patient_id, encounter_id, clinical_status, verification_status, code, display, onset_datetime, recorded_date
        FROM conditions
        WHERE ? = ''
           OR LOWER(COALESCE(display, '')) LIKE ?
           OR LOWER(COALESCE(code, '')) LIKE ?
           OR LOWER(COALESCE(patient_id, '')) LIKE ?
        ORDER BY recorded_date DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )


def _hl7_messages(limit: int, search: str) -> list[dict[str, Any]]:
    pattern = f"%{search.lower()}%"
    return _fetch_all(
        """
        SELECT message_id, message_type, trigger_event, sending_application, sending_facility,
               patient_id, patient_name, event_type, message_timestamp
        FROM hl7_messages
        WHERE ? = ''
           OR LOWER(COALESCE(message_id, '')) LIKE ?
           OR LOWER(COALESCE(patient_id, '')) LIKE ?
           OR LOWER(COALESCE(patient_name, '')) LIKE ?
           OR LOWER(COALESCE(message_type, '') || '^' || COALESCE(trigger_event, '')) LIKE ?
        ORDER BY message_timestamp DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, pattern, limit),
    )


def _hl7_results(limit: int, search: str) -> list[dict[str, Any]]:
    pattern = f"%{search.lower()}%"
    return _fetch_all(
        """
        SELECT result_id, message_id, patient_id, observation_code, observation_name,
               observation_value, units, reference_range, abnormal_flag, result_status, observation_timestamp
        FROM hl7_results
        WHERE ? = ''
           OR LOWER(COALESCE(patient_id, '')) LIKE ?
           OR LOWER(COALESCE(observation_code, '')) LIKE ?
           OR LOWER(COALESCE(observation_name, '')) LIKE ?
           OR LOWER(COALESCE(abnormal_flag, '')) LIKE ?
        ORDER BY observation_timestamp DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, pattern, limit),
    )


def _patient_detail(patient_id: str) -> dict[str, Any]:
    _record_compliance_event("patient_detail_view", "Patient", patient_id, "care-operations")
    patient = _fetch_one(
        """
        SELECT patient_id, full_name, gender, birth_date, active
        FROM patients
        WHERE patient_id = ?
        """,
        (patient_id,),
    )
    if not patient:
        return {}

    return {
        "patient": patient,
        "conditions": _fetch_all(
            """
            SELECT condition_id, code, display, clinical_status, recorded_date
            FROM conditions
            WHERE patient_id = ?
            ORDER BY recorded_date DESC
            LIMIT 6
            """,
            (patient_id,),
        ),
        "encounters": _fetch_all(
            """
            SELECT encounter_id, class_display, type_display, start_datetime, reason_display, status
            FROM encounters
            WHERE patient_id = ?
            ORDER BY start_datetime DESC
            LIMIT 6
            """,
            (patient_id,),
        ),
        "observations": _fetch_all(
            """
            SELECT observation_id, code, display, effective_datetime, value_numeric, value_text, unit
            FROM observations
            WHERE patient_id = ?
            ORDER BY effective_datetime DESC
            LIMIT 8
            """,
            (patient_id,),
        ),
        "signals": _fetch_one(
            """
            SELECT COUNT(DISTINCT c.condition_id) AS condition_count,
                   COUNT(DISTINCT e.encounter_id) AS encounter_count,
                   COUNT(DISTINCT o.observation_id) AS observation_count,
                   SUM(CASE WHEN o.code = '8480-6' AND o.value_numeric >= 140 THEN 1 ELSE 0 END) AS high_systolic_events,
                   SUM(CASE WHEN o.code = '4548-4' AND o.value_numeric >= 7 THEN 1 ELSE 0 END) AS high_a1c_events
            FROM patients p
            LEFT JOIN conditions c ON p.patient_id = c.patient_id
            LEFT JOIN encounters e ON p.patient_id = e.patient_id
            LEFT JOIN observations o ON p.patient_id = o.patient_id
            WHERE p.patient_id = ?
            GROUP BY p.patient_id
            """,
            (patient_id,),
        ),
        "hl7_results": _fetch_all(
            """
            SELECT observation_code, observation_name, observation_value, units, abnormal_flag, observation_timestamp
            FROM hl7_results
            WHERE patient_id = ?
            ORDER BY observation_timestamp DESC
            LIMIT 6
            """,
            (patient_id,),
        ),
    }


def _run_pipeline() -> dict[str, Any]:
    if settings.data_classification.lower() in {"phi", "ephi", "production_phi"} and not settings.allow_phi:
        _record_compliance_event("run_pipeline_blocked", "FHIR", None, "ingestion", "blocked")
        raise PermissionError("PHI mode is blocked unless ALLOW_PHI=true and production safeguards are configured.")

    from src.extract_fhir import run_extract
    from src.load_sqlite import run_load
    from src.transform import run_transform

    extract_stats = run_extract()
    transform_stats = run_transform()
    load_stats = run_load(extract_stats)
    _record_compliance_event("run_fhir_etl", "FHIR", None, "ingestion")
    return {
        "extract": extract_stats,
        "transform": transform_stats,
        "load": load_stats,
        "summary": _summary(),
    }


def _run_synthetic_pipeline() -> dict[str, Any]:
    from scripts.generate_synthetic_fhir import main as generate_synthetic_fhir
    from src.load_synthetic_fhir import run_synthetic_load

    generate_synthetic_fhir()
    load_stats = run_synthetic_load()
    _record_compliance_event("load_synthetic_fhir", "Bundle", None, "synthetic-load")
    return {
        "load": load_stats,
        "summary": _summary(),
    }


def _run_hl7_pipeline() -> dict[str, Any]:
    from scripts.generate_synthetic_hl7 import main as generate_hl7
    from src.load_hl7 import run_hl7_load

    generate_hl7()
    load_stats = run_hl7_load()
    _record_compliance_event("load_synthetic_hl7", "HL7v2", None, "synthetic-load")
    return {
        "load": load_stats,
        "summary": _summary(),
    }


class HealthcareDashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path, parse_qs(parsed.query))
            return

        self._serve_static(parsed.path)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        relative_path = "index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/")
        target = (WEB_DIR / relative_path).resolve()

        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.exists() or not target.is_file():
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/run-pipeline":
            try:
                self._send_json(_run_pipeline())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path == "/api/load-synthetic":
            try:
                self._send_json(_run_synthetic_pipeline())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path == "/api/load-hl7":
            try:
                self._send_json(_run_hl7_pipeline())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path == "/api/audit-event":
            length = int(self.headers.get("Content-Length", "0") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}") if length else {}
            _record_compliance_event(
                payload.get("action", "dashboard_event"),
                payload.get("resource_type"),
                payload.get("resource_id"),
                payload.get("purpose", "operations"),
                payload.get("outcome", "success"),
            )
            self._send_json({"status": "recorded"})
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def _handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        limit = min(int(query.get("limit", ["50"])[0]), 200)
        search = query.get("search", [""])[0].strip().lower()

        routes = {
            "/api/config": lambda: {
                "fhir_base_url": settings.fhir_base_url,
                "patient_limit": settings.patient_limit,
                "observation_limit": settings.observation_limit,
                "sqlite_db_path": settings.sqlite_db_path,
                "data_classification": settings.data_classification,
                "fhir_auth_mode": settings.fhir_auth_mode,
                "epic_sandbox": {
                    "base_url": settings.epic_fhir_base_url,
                    "client_configured": bool(settings.epic_client_id),
                    "redirect_uri": settings.epic_redirect_uri,
                    "scopes": settings.epic_scopes.split(),
                    "status": "ready_for_client_registration" if not settings.epic_client_id else "client_configured",
                },
            },
            "/api/summary": _summary,
            "/api/analytics": _analytics,
            "/api/compliance": _compliance_posture,
            "/api/patients": lambda: _patients(limit, search),
            "/api/observations": lambda: _observations(limit, search),
            "/api/encounters": lambda: _encounters(limit, search),
            "/api/conditions": lambda: _conditions(limit, search),
            "/api/hl7-messages": lambda: _hl7_messages(limit, search),
            "/api/hl7-results": lambda: _hl7_results(limit, search),
            "/api/patient-detail": lambda: _patient_detail(query.get("patient_id", [""])[0]),
        }

        handler = routes.get(path)
        if handler is None:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(handler())

    def _serve_static(self, path: str) -> None:
        relative_path = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_DIR / relative_path).resolve()

        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.exists() or not target.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    server = ReusableThreadingHTTPServer((host, port), HealthcareDashboardHandler)
    print(f"Healthcare FHIR dashboard running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
