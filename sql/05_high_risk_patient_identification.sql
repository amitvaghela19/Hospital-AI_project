-- High-risk heuristic: prior inpatient visits and long LOS
SELECT a.encounter_id, a.patient_nbr, a.time_in_hospital, a.number_inpatient, a.readmitted
FROM fact_admission a
WHERE a.number_inpatient >= 2 OR a.time_in_hospital >= 7
ORDER BY a.number_inpatient DESC, a.time_in_hospital DESC
LIMIT 200;
