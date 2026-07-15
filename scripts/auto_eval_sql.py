import sys
import random
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chatbot.graph.api import route_chat

def generate_questions():
    ages = ["[70-80)", "[60-70)", "[80-90)"]
    genders = ["Male", "Female"]
    risks = ["High", "Low", "Medium"]
    meds = ["2", "3", "5"]
    los = ["> 3", "> 5", "< 2"]
    
    questions = []
    
    # Generate 10 distinct questions
    for i in range(10):
        c_age = random.choice(ages)
        c_gender = random.choice(genders)
        c_risk = random.choice(risks)
        c_meds = random.choice(meds)
        c_los = random.choice(los)
        
        template = random.choice([
            f"Find all patients who are {c_risk} risk, {c_gender}, age {c_age}, on {c_meds} meds, and stayed {c_los} days.",
            f"How many encounters are {c_gender}, {c_risk} risk, taking {c_meds} medications with length of stay {c_los}?",
            f"Count {c_gender} patients in age group {c_age} with {c_risk} risk.",
            f"What is the average length of stay for {c_risk} risk {c_gender} patients on {c_meds} meds?",
            f"male, {c_risk} risk, {c_meds} meds, {c_age}"
        ])
        questions.append(template)
        
    return questions

from unittest.mock import patch

def main():
    questions = generate_questions()
    failures = []
    
    with patch("streamlit_app.rbac.can_sql", return_value=True):
        print(f"Starting evaluation of {len(questions)} queries...")
        for i, q in enumerate(questions):
            print(f"[{i+1}/{len(questions)}] Query: {q}")
            try:
                ans, route, stages, rag_mode = route_chat(q, "analyst")
                
                if route not in ("sqlite_mcp", "semantic_metric_mcp"):
                    fail_msg = f"Failed routing. Expected sqlite_mcp, got {route}. Answer: {ans}"
                    failures.append({"query": q, "error": fail_msg})
                    print(f"  [FAIL] {fail_msg}")
                    continue
                    
                if "error" in ans.lower() or "no rows" in ans.lower() or "no column" in ans.lower():
                    fail_msg = f"SQL execution error or empty result: {ans}"
                    failures.append({"query": q, "error": fail_msg})
                    print(f"  [FAIL] {fail_msg}")
                    continue
                    
                print("  [PASS] Passed")
                
            except Exception as e:
                fail_msg = f"Exception: {e}"
                failures.append({"query": q, "error": fail_msg})
                print(f"  [FAIL] {fail_msg}")
            
    print(f"\nEvaluation complete. Passed: {len(questions)-len(failures)}/{len(questions)}")
    
    if failures:
        out_path = ROOT / "scripts" / "eval_failures.json"
        with open(out_path, "w") as f:
            json.dump(failures, f, indent=2)
        print(f"Failures saved to {out_path}")
        sys.exit(1)
    else:
        print("100% Success!")
        sys.exit(0)

if __name__ == "__main__":
    main()
