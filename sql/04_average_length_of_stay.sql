SELECT AVG(time_in_hospital) AS avg_los,
       MIN(time_in_hospital) AS min_los,
       MAX(time_in_hospital) AS max_los
FROM fact_admission;
