# FHIROps Console

FHIROps Console is a local healthcare interoperability project that extracts FHIR resources, parses HL7 v2 messages, validates and normalizes clinical payloads, loads curated tables into SQLite, and serves dashboard-ready analytics through a lightweight API.

It provides a focused implementation of healthcare interoperability patterns through a local ETL pipeline, curated healthcare tables, HL7 v2 parsing, compliance-aware audit logging, and an interactive dashboard.

## Capabilities

- FHIR REST API integration
- HL7 v2 ADT/ORU message parsing
- Patient and Observation resource extraction
- JSON normalization into relational tables
- SQL-based healthcare analytics
- Data validation and quality checks
- Reproducible local ETL pipeline
- Dashboard-ready output tables

## Architecture

```text
FHIR REST API / Synthetic FHIR / Synthetic HL7 v2
    ↓
Python Extractors and Parsers
    ↓
Raw JSON / HL7 Payloads
    ↓
Validation + Transformation
    ↓
SQLite Relational Tables
    ↓
Dashboard API and UI
```

## Healthcare Resources

| FHIR Resource | Purpose |
|---|---|
| Patient | Demographic and patient master data |
| Observation | Clinical measurements such as labs, vitals, or other observations |
| Encounter | Visit and utilization context |
| Condition | Diagnosis and problem-list context |
| HL7 ADT | Admission/registration event messages |
| HL7 ORU | Observation/result event messages |

## Tech Stack

- Python
- Requests
- Pandas
- Pydantic
- SQLite
- SQL
- FHIR R4-style JSON resources

## Project Structure

```text
healthcare-fhir-etl/
├── README.md
├── requirements.txt
├── .env.example
├── run_pipeline.py
├── src/
│   ├── config.py
│   ├── extract_fhir.py
│   ├── transform.py
│   ├── load_sqlite.py
│   ├── load_synthetic_fhir.py
│   ├── load_hl7.py
│   ├── validate.py
│   └── analytics.py
├── scripts/
│   ├── generate_synthetic_fhir.py
│   └── generate_synthetic_hl7.py
├── sql/
│   ├── schema.sql
│   └── analytics_queries.sql
├── web/
│   ├── index.html
│   ├── knowledge.html
│   ├── app.js
│   └── styles.css
├── data/
│   ├── raw/
│   ├── hl7/
│   ├── synthea/
│   └── processed/
├── docs/
│   └── technical_overview.md
├── run_synthetic_pipeline.py
├── run_hl7_pipeline.py
└── web_app.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the Live FHIR Pipeline

```bash
python run_pipeline.py
```

By default, the project uses the public HAPI FHIR test server:

```text
https://hapi.fhir.org/baseR4
```

You can override it with an environment variable:

```bash
export FHIR_BASE_URL="https://hapi.fhir.org/baseR4"
python run_pipeline.py
```

## Outputs

After running the pipeline, you will get:

```text
healthcare_fhir.db
```

with these tables:

| Table | Description |
|---|---|
| patients | Curated patient demographic records |
| encounters | Curated care encounter records |
| conditions | Curated diagnosis/problem records |
| observations | Curated clinical observation records |
| hl7_messages | Parsed HL7 v2 message metadata |
| hl7_results | Parsed HL7 v2 OBX result rows |
| etl_audit | ETL run metadata and data quality statistics |

The pipeline also generates processed CSV files in:

```text
data/processed/
```

## Run the Dashboard UI

The project includes a local healthcare dashboard that exposes a JSON API over the SQLite output and serves a browser UI.

```bash
python web_app.py
```

Open:

```text
http://127.0.0.1:8000
```

The dashboard can:

- Trigger the live FHIR extract-transform-load workflow
- Load local synthetic FHIR bundles for deterministic sample data
- Load local synthetic HL7 v2 ADT/ORU messages
- Show Patient and Observation counts
- Show Encounter and Condition counts
- Display patient count by gender
- Display top clinical observation codes
- Display top condition codes
- Display encounter class distribution
- Display patient age-band distribution
- Display patient-to-observation coverage
- Score observation completeness across patient references, codes, values, and effective dates
- Browse curated patient and observation records
- Surface basic data quality checks such as missing patient references

Dashboard API endpoints:

| Endpoint | Purpose |
|---|---|
| GET `/api/config` | Shows the configured FHIR endpoint and record limits |
| GET `/api/summary` | Returns ETL counts, database status, and latest audit run |
| GET `/api/analytics` | Returns dashboard-ready aggregate data |
| GET `/api/patients` | Returns curated patient rows |
| GET `/api/encounters` | Returns curated encounter rows |
| GET `/api/conditions` | Returns curated condition rows |
| GET `/api/observations` | Returns curated observation rows |
| GET `/api/hl7-messages` | Returns parsed HL7 v2 message rows |
| GET `/api/hl7-results` | Returns parsed HL7 v2 OBX result rows |
| POST `/api/run-pipeline` | Runs the FHIR extraction, transformation, and SQLite load |
| POST `/api/load-synthetic` | Generates and loads local synthetic FHIR bundles |
| POST `/api/load-hl7` | Generates and loads local synthetic HL7 v2 messages |

## Load Synthetic FHIR Data

The public HAPI FHIR test server is useful for validating live API extraction, but shared test-server data can be sparse or inconsistent. For repeatable local analytics, the project also supports synthetic FHIR bundles in:

```text
data/synthea/
```

Generate and load the included Synthea-compatible bundles:

```bash
python scripts/generate_synthetic_fhir.py
python run_synthetic_pipeline.py
```

This loads curated tables for:

| Table | FHIR Resource |
|---|---|
| patients | Patient |
| encounters | Encounter |
| conditions | Condition |
| observations | Observation |

You can replace the generated files with downloaded Synthea FHIR JSON bundles and run the same synthetic pipeline.

## Load Synthetic HL7 v2 Data

The project also includes legacy HL7 v2 interface processing. It generates ADT registration messages and ORU result messages, then parses MSH, PID, PV1, OBR, and OBX segments into curated SQLite tables.

```bash
python run_hl7_pipeline.py
```

This loads:

| Table | Source |
|---|---|
| hl7_messages | ADT/ORU message metadata and patient/event context |
| hl7_results | ORU OBX result values, units, flags, and timestamps |

This supports both:

- FHIR REST/JSON resource ingestion
- HL7 v2 event/message parsing

## FHIR API Access

By default, this project uses the public HAPI FHIR R4 test server:

```text
https://hapi.fhir.org/baseR4
```

That public endpoint usually does not require API credentials, but data availability and performance can vary because it is a shared test server.

For more realistic API access, create a developer sandbox account with one of these:

- SMART Health IT sandbox: https://launch.smarthealthit.org/
- HAPI FHIR public test server: https://hapi.fhir.org/
- Inferno test suites and reference tooling: https://inferno.healthit.gov/
- Epic on FHIR developer sandbox: https://fhir.epic.com/
- Oracle Health/Cerner developer program: https://code.cerner.com/

For technical review purposes, classify this as a local interoperability validation project using public and synthetic healthcare data, not a production hospital integration.

## Compliance Posture

This project is designed to avoid PHI by default. It does not claim production HIPAA compliance, because that requires organizational controls, contracts, infrastructure, policies, and security operations beyond a local repository.

Implemented safeguards:

- Synthetic data mode by default through `DATA_CLASSIFICATION=synthetic`
- PHI ingestion guard through `ALLOW_PHI=false`
- ETL audit trail with extracted and loaded counts
- Dashboard access event logging in `compliance_events`
- Curated minimum-necessary tables instead of exposing full raw bundles in the UI
- Clear production-readiness gaps for RBAC, TLS, encryption/key management, BAA, risk analysis, and incident response

Relevant regulatory context:

- HHS HIPAA Security Rule: https://www.hhs.gov/hipaa/for-professionals/security/
- HHS HIPAA Privacy Rule: https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/
- ONC Cures Act Final Rule: https://www.healthit.gov/regulations/cures-act-final-rule

## Example Analytics

The project includes SQL queries for:

- Patient count by gender
- Observation count by clinical code
- Condition count by SNOMED CT code
- Encounter count by class
- HL7 message count by message type
- HL7 abnormal result count by OBX code
- Most recent observation per patient
- Data quality checks for missing patient references
- Patient age-band distribution
- Observation completeness and coding coverage
- Patient observation coverage
