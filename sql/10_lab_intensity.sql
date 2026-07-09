SELECT CASE WHEN l.num_lab_procedures >= 50 THEN 'high' ELSE 'low' END AS lab_intensity,
       COUNT(*) AS encounters,
       AVG(CASE WHEN a.readmitted = '<30' THEN 1.0 ELSE 0.0 END) AS readmission_rate_30d
FROM fact_admission a
JOIN fact_lab l ON a.encounter_id = l.encounter_id
GROUP BY CASE WHEN l.num_lab_procedures >= 50 THEN 'high' ELSE 'low' END;
