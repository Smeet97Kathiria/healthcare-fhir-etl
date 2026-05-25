# Technical Overview: FHIROps Console

## Project Summary

FHIROps Console is a compact healthcare interoperability platform for local validation of FHIR and HL7 data workflows. It extracts FHIR resources, parses HL7 v2 messages, validates core fields, normalizes source payloads into relational tables, and exposes dashboard-ready analytics through a local API.

## FHIR Context

FHIR represents healthcare data as resources such as Patient, Observation, Encounter, Medication, and Condition. It commonly uses REST APIs and JSON, which aligns well with API-based ingestion patterns, schema validation, and downstream analytics modeling.

## Epic on FHIR Readiness

The project includes Epic on FHIR sandbox configuration placeholders for `EPIC_FHIR_BASE_URL`, `EPIC_CLIENT_ID`, `EPIC_REDIRECT_URI`, and SMART scopes. The current live pipeline uses a public FHIR endpoint, but the extraction path is designed so an OAuth-backed Epic sandbox client can be added while reusing the same Patient, Encounter, Condition, and Observation normalization logic.

## Pipeline Flow

1. Calls a FHIR REST endpoint.
2. Extracts Patient and Observation resources.
3. Saves the raw JSON payloads for traceability.
4. Parses nested FHIR fields into flat relational structures.
5. Validates required IDs and core fields using Pydantic.
6. Loads the curated data into SQLite tables.
7. Runs SQL analytics queries for reporting use cases.

## HL7 v2 Context

HL7 v2 is commonly pipe-delimited and event-driven, while FHIR is resource-based and API-oriented. In enterprise integration environments, HL7 v2 often supports real-time operational interfaces, while FHIR is commonly used for API-based exchange, patient access, and modern application integration.

## HL7 Processing

The project generates and parses synthetic ADT and ORU messages. Parsed data from MSH, PID, PV1, OBR, and OBX segments is loaded into curated `hl7_messages` and `hl7_results` tables for operational analytics.

## Technologies

- Python for extraction and transformation
- Requests for FHIR API calls
- Pydantic for validation
- Pandas for transformation
- SQLite for relational storage
- SQL for analytics queries
- Static HTML, CSS, and JavaScript for the dashboard

## FHIR vs HL7 v2

HL7 v2 is a messaging standard commonly used for real-time hospital interface messages. It is pipe-delimited and organized into segments such as MSH, PID, OBR, and OBX. FHIR represents healthcare data as resources, usually exchanged through REST APIs using JSON. From an implementation perspective, FHIR aligns with API ingestion, while HL7 v2 aligns with event-message parsing and transformation.

## Compliance Posture

The project defaults to synthetic data, keeps PHI ingestion disabled unless explicitly configured, records ETL audit metadata, logs dashboard access events, and exposes curated views instead of raw clinical payloads. Production use would require additional controls such as RBAC, TLS, encryption, secrets management, risk analysis, monitoring, and organizational compliance processes.
