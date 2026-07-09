SELECT diag_1 AS diagnosis,
       COUNT(*) AS encounters,
       AVG(CASE WHEN readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d
FROM fact_admission
GROUP BY diag_1
HAVING COUNT(*) >= 50
ORDER BY readmission_rate_30d DESC
LIMIT 50;
