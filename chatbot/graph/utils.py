import json
from pathlib import Path
from streamlit_app import ROOT

SCRIPTS: list[dict] = []
for p in (ROOT / "chatbot" / "scripts").glob("*.json"):
    SCRIPTS.extend(json.loads(p.read_text(encoding="utf-8")))

def match_script(message: str) -> dict | None:
    msg = message.lower()
    best, hits_best = None, 0
    for item in SCRIPTS:
        hits = sum(1 for pat in item.get("patterns", []) if pat.lower() in msg)
        if hits > hits_best:
            best, hits_best = item, hits
    return best if hits_best else None

import re
def extract_patient_nbr(msg: str) -> str | None:
    m = re.search(r"\bpatient\s*(?:id|nbr)?\s*[:=]?\s*(\d+)\b", msg, re.IGNORECASE)
    if m:
        return m.group(1)
    return None

def is_patient_lookup_request(msg: str) -> bool:
    return extract_patient_nbr(msg) is not None or "check patient" in msg.lower()
