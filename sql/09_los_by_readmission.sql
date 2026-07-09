SELECT readmitted, AVG(time_in_hospital) AS avg_los, COUNT(*) AS encounters
FROM fact_admission
GROUP BY readmitted;
