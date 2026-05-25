# Epic on FHIR Readiness

FHIROps Console currently runs against public and synthetic data sources. The FHIR ingestion layer is structured so it can be adapted to an Epic on FHIR sandbox or another SMART on FHIR-capable EHR endpoint.

This is not a production Epic integration. It documents the integration path and keeps the codebase ready for sandbox client registration.

## Current State

- Live FHIR extraction uses `FHIR_BASE_URL`, which defaults to the public HAPI FHIR R4 server.
- Curated tables already support Patient, Encounter, Condition, and Observation data.
- Dashboard APIs read from the curated SQLite model rather than directly from raw FHIR JSON.
- Compliance posture defaults to synthetic data and `ALLOW_PHI=false`.

## Epic Sandbox Configuration

The following environment variables are included for Epic on FHIR sandbox readiness:

```text
FHIR_AUTH_MODE=none
EPIC_FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_CLIENT_ID=
EPIC_REDIRECT_URI=http://localhost:8000/oauth/callback
EPIC_SCOPES=launch/patient patient/Patient.read patient/Observation.read patient/Encounter.read patient/Condition.read offline_access
```

`EPIC_CLIENT_ID` should be populated only after registering an app in the Epic on FHIR developer portal. Client secrets or private keys should never be committed to the repository.

## SMART on FHIR Path

To move from public FHIR extraction to Epic sandbox access:

1. Register an app in Epic on FHIR.
2. Configure one or more redirect URIs.
3. Store the generated client ID in environment configuration.
4. Request the required SMART scopes for Patient, Observation, Encounter, and Condition reads.
5. Implement the OAuth authorization-code flow.
6. Attach the access token to FHIR API requests.
7. Reuse the existing transform and load steps to normalize resources into curated tables.

Epic's public developer materials describe client registration, redirect URI configuration, SMART testing, and OAuth behavior. In Epic's sandbox, scopes are required for testing and determine which resources the application can access.

## Production Controls

A production Epic/EHR integration would also require:

- secure secret storage
- TLS-only callback URLs
- token refresh handling
- role-based access control
- audit logging and monitoring
- PHI data classification
- BAA and organizational compliance review
- incident response and access review procedures

The current implementation keeps those controls explicit instead of treating a local sandbox workflow as production-ready.
