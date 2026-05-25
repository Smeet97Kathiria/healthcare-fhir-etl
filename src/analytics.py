import sqlite3
from typing import Dict

import pandas as pd

from src.config import settings


def run_query(query: str) -> pd.DataFrame:
    with sqlite3.connect(settings.sqlite_db_path) as conn:
        return pd.read_sql_query(query, conn)


def run_sample_analytics() -> Dict[str, pd.DataFrame]:
    queries = {
        "patient_count_by_gender": """
            SELECT gender, COUNT(*) AS patient_count
            FROM patients
            GROUP BY gender
            ORDER BY patient_count DESC;
        """,
        "top_observation_codes": """
            SELECT code, display, COUNT(*) AS observation_count
            FROM observations
            GROUP BY code, display
            ORDER BY observation_count DESC
            LIMIT 10;
        """,
        "missing_patient_references": """
            SELECT COUNT(*) AS observations_without_patient_reference
            FROM observations
            WHERE patient_id IS NULL OR patient_id = '';
        """,
    }

    return {name: run_query(query) for name, query in queries.items()}


def print_analytics() -> None:
    results = run_sample_analytics()
    for name, dataframe in results.items():
        print(f"\n--- {name} ---")
        print(dataframe.to_string(index=False))
