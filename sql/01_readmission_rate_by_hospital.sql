-- Readmission rate by hospital proxy (medical_specialty as care unit proxy when hospital id absent)
SELECT medical_specialty,
       COUNT(*) AS encounters,
       AVG(CASE WHEN readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d
FROM fact_admission
GROUP BY medical_specialty
ORDER BY encounters DESC;
