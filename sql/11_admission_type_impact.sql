SELECT admission_type_id, COUNT(*) AS encounters,
       AVG(CASE WHEN readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d,
       AVG(time_in_hospital) AS avg_los
FROM fact_admission
GROUP BY admission_type_id
ORDER BY encounters DESC;
