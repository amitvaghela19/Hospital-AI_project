SELECT patient_nbr, COUNT(*) AS admissions,
       SUM(number_inpatient) AS inpatient_visits,
       AVG(CASE WHEN readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d
FROM fact_admission
GROUP BY patient_nbr
HAVING COUNT(*) >= 3
ORDER BY admissions DESC
LIMIT 200;
