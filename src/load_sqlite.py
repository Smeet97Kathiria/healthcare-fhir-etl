import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from src.config import settings


def _read_sql_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def initialize_database(conn: sqlite3.Connection) -> None:
    schema_sql = _read_sql_file("sql/schema.sql")
    conn.executescript(schema_sql)
    _migrate_audit_table(conn)
    conn.commit()


def _migrate_audit_table(conn: sqlite3.Connection) -> None:
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(etl_audit)").fetchall()}
    migrations = {
        "source_mode": "ALTER TABLE etl_audit ADD COLUMN source_mode TEXT",
        "encounters_extracted": "ALTER TABLE etl_audit ADD COLUMN encounters_extracted INTEGER",
        "conditions_extracted": "ALTER TABLE etl_audit ADD COLUMN conditions_extracted INTEGER",
        "hl7_messages_extracted": "ALTER TABLE etl_audit ADD COLUMN hl7_messages_extracted INTEGER",
        "hl7_results_extracted": "ALTER TABLE etl_audit ADD COLUMN hl7_results_extracted INTEGER",
        "encounters_loaded": "ALTER TABLE etl_audit ADD COLUMN encounters_loaded INTEGER",
        "conditions_loaded": "ALTER TABLE etl_audit ADD COLUMN conditions_loaded INTEGER",
        "hl7_messages_loaded": "ALTER TABLE etl_audit ADD COLUMN hl7_messages_loaded INTEGER",
        "hl7_results_loaded": "ALTER TABLE etl_audit ADD COLUMN hl7_results_loaded INTEGER",
    }
    for column, statement in migrations.items():
        if column not in existing_columns:
            conn.execute(statement)

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
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_compliance_events_timestamp
        ON compliance_events(event_timestamp)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hl7_messages (
            message_id TEXT PRIMARY KEY,
            message_type TEXT,
            trigger_event TEXT,
            sending_application TEXT,
            sending_facility TEXT,
            receiving_application TEXT,
            receiving_facility TEXT,
            message_timestamp TEXT,
            patient_id TEXT,
            patient_name TEXT,
            event_type TEXT,
            raw_message TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hl7_results (
            result_id TEXT PRIMARY KEY,
            message_id TEXT,
            patient_id TEXT,
            order_id TEXT,
            observation_id TEXT,
            observation_code TEXT,
            observation_name TEXT,
            value_type TEXT,
            observation_value TEXT,
            units TEXT,
            reference_range TEXT,
            abnormal_flag TEXT,
            result_status TEXT,
            observation_timestamp TEXT
        )
        """
    )


def load_dataframe(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str) -> int:
    if df.empty:
        return 0
    df.to_sql(table_name, conn, if_exists="append", index=False)
    return len(df)


def insert_audit_record(conn: sqlite3.Connection, stats: Dict[str, int]) -> None:
    conn.execute(
        """
        INSERT INTO etl_audit (
            run_timestamp,
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            stats.get("source_mode", "hapi_fhir"),
            stats.get("patients_extracted", 0),
            stats.get("observations_extracted", 0),
            stats.get("encounters_extracted", 0),
            stats.get("conditions_extracted", 0),
            stats.get("hl7_messages_extracted", 0),
            stats.get("hl7_results_extracted", 0),
            stats.get("patients_loaded", 0),
            stats.get("observations_loaded", 0),
            stats.get("encounters_loaded", 0),
            stats.get("conditions_loaded", 0),
            stats.get("hl7_messages_loaded", 0),
            stats.get("hl7_results_loaded", 0),
        ),
    )
    conn.commit()


def run_load(extract_stats: Dict[str, int]) -> Dict[str, int]:
    patients_path = os.path.join(settings.processed_dir, "patients.csv")
    observations_path = os.path.join(settings.processed_dir, "observations.csv")

    patients_df = pd.read_csv(patients_path) if os.path.exists(patients_path) else pd.DataFrame()
    observations_df = pd.read_csv(observations_path) if os.path.exists(observations_path) else pd.DataFrame()

    with sqlite3.connect(settings.sqlite_db_path) as conn:
        initialize_database(conn)
        conn.execute("DELETE FROM patients")
        conn.execute("DELETE FROM observations")
        conn.execute("DELETE FROM encounters")
        conn.execute("DELETE FROM conditions")
        conn.commit()

        patients_loaded = load_dataframe(conn, patients_df, "patients")
        observations_loaded = load_dataframe(conn, observations_df, "observations")

        load_stats = {
            "patients_loaded": patients_loaded,
            "observations_loaded": observations_loaded,
            "encounters_loaded": 0,
            "conditions_loaded": 0,
            "hl7_messages_loaded": 0,
            "hl7_results_loaded": 0,
        }
        insert_audit_record(conn, {**extract_stats, **load_stats})

    return load_stats
