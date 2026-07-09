SELECT p.gender, COUNT(*) AS encounters,
       AVG(CASE WHEN a.readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d
FROM fact_admission a
JOIN dim_patient p ON a.patient_nbr = p.patient_nbr
GROUP BY p.gender;
