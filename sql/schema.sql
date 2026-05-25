CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    full_name TEXT,
    gender TEXT,
    birth_date TEXT,
    active BOOLEAN
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    patient_id TEXT,
    status TEXT,
    code TEXT,
    display TEXT,
    effective_datetime TEXT,
    value_numeric REAL,
    value_text TEXT,
    unit TEXT
);

CREATE TABLE IF NOT EXISTS encounters (
    encounter_id TEXT PRIMARY KEY,
    patient_id TEXT,
    status TEXT,
    class_code TEXT,
    class_display TEXT,
    type_display TEXT,
    start_datetime TEXT,
    end_datetime TEXT,
    reason_display TEXT
);

CREATE TABLE IF NOT EXISTS conditions (
    condition_id TEXT PRIMARY KEY,
    patient_id TEXT,
    encounter_id TEXT,
    clinical_status TEXT,
    verification_status TEXT,
    code TEXT,
    display TEXT,
    onset_datetime TEXT,
    recorded_date TEXT
);

CREATE TABLE IF NOT EXISTS etl_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TEXT NOT NULL,
    source_mode TEXT,
    patients_extracted INTEGER,
    observations_extracted INTEGER,
    encounters_extracted INTEGER,
    conditions_extracted INTEGER,
    hl7_messages_extracted INTEGER,
    hl7_results_extracted INTEGER,
    patients_loaded INTEGER,
    observations_loaded INTEGER,
    encounters_loaded INTEGER,
    conditions_loaded INTEGER,
    hl7_messages_loaded INTEGER,
    hl7_results_loaded INTEGER
);

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
);

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
);

CREATE TABLE IF NOT EXISTS compliance_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp TEXT NOT NULL,
    actor TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    purpose TEXT,
    outcome TEXT
);

CREATE INDEX IF NOT EXISTS idx_observations_patient_id
ON observations(patient_id);

CREATE INDEX IF NOT EXISTS idx_observations_code
ON observations(code);

CREATE INDEX IF NOT EXISTS idx_encounters_patient_id
ON encounters(patient_id);

CREATE INDEX IF NOT EXISTS idx_conditions_patient_id
ON conditions(patient_id);

CREATE INDEX IF NOT EXISTS idx_conditions_code
ON conditions(code);

CREATE INDEX IF NOT EXISTS idx_compliance_events_timestamp
ON compliance_events(event_timestamp);

CREATE INDEX IF NOT EXISTS idx_hl7_messages_patient_id
ON hl7_messages(patient_id);

CREATE INDEX IF NOT EXISTS idx_hl7_results_patient_id
ON hl7_results(patient_id);

CREATE INDEX IF NOT EXISTS idx_hl7_results_code
ON hl7_results(observation_code);
