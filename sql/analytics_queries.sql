-- Patient count by gender
SELECT gender, COUNT(*) AS patient_count
FROM patients
GROUP BY gender
ORDER BY patient_count DESC;

-- Top clinical observation codes
SELECT code, display, COUNT(*) AS observation_count
FROM observations
GROUP BY code, display
ORDER BY observation_count DESC
LIMIT 10;

-- Most recent observation per patient
SELECT o.*
FROM observations o
JOIN (
    SELECT patient_id, MAX(effective_datetime) AS latest_effective_datetime
    FROM observations
    WHERE patient_id IS NOT NULL
    GROUP BY patient_id
) latest
ON o.patient_id = latest.patient_id
AND o.effective_datetime = latest.latest_effective_datetime;

-- Data quality check: observations missing patient references
SELECT COUNT(*) AS observations_without_patient_reference
FROM observations
WHERE patient_id IS NULL OR patient_id = '';
