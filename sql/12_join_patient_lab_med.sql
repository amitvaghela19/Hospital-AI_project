SELECT p.age, p.gender, a.time_in_hospital, l.num_lab_procedures, l.A1Cresult, m.insulin, a.readmitted
FROM fact_admission a
JOIN dim_patient p ON a.patient_nbr = p.patient_nbr
JOIN fact_lab l ON a.encounter_id = l.encounter_id
JOIN fact_medication m ON a.encounter_id = m.encounter_id
LIMIT 100;
