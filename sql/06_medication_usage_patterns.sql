SELECT insulin, COUNT(*) AS encounters,
       AVG(CASE WHEN readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d
FROM fact_admission a
JOIN fact_medication m ON a.encounter_id = m.encounter_id
GROUP BY insulin
ORDER BY encounters DESC;
