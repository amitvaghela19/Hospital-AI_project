from __future__ import annotations

import re
import sqlite3

from mcp.common import PATHS

_WRITE_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|grant|revoke|merge|upsert)\b",
    re.IGNORECASE,
)

_READ_ONLY_MSG = (
    "Only read-only SELECT queries are permitted for chat_security reasons. "
    "Viewer, Clinician, and Analyst modes cannot modify patient or encounter data."
)


def _ensure_marts_loaded(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mart_clinical_risk'")
    if not cur.fetchone():
        import pandas as pd
        csv_path = PATHS["warehouse"].parent.parent / "exports" / "mart_clinical_risk.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df.to_sql("mart_clinical_risk", conn, if_exists="replace", index=False)


def run_query(sql: str, limit: int = 100) -> str:
    db = PATHS["warehouse"]
    if not db.exists():
        return "SQLite warehouse not found. Run Phase 1 first."
    sql_stripped = sql.strip().rstrip(";")
    norm = sql_stripped.lower()
    if not norm.startswith("select"):
        return _READ_ONLY_MSG
    if _WRITE_FORBIDDEN.search(sql_stripped):
        return _READ_ONLY_MSG
    if re.search(r"\binto\s+(outfile|dumpfile|table)\b", norm):
        return "Export or write-via-SELECT operations are not allowed."
    if "limit" not in norm:
        sql_stripped = f"{sql_stripped} LIMIT {limit}"
    with sqlite3.connect(db) as conn:
        _ensure_marts_loaded(conn)
        cur = conn.execute(sql_stripped)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
    if not rows:
        return "No rows returned."
    lines = ["\t".join(cols)]
    for row in rows[:limit]:
        lines.append("\t".join(str(v) for v in row))
    return "\n".join(lines)


def list_tables() -> list[str]:
    db = PATHS["warehouse"]
    if not db.exists():
        return []
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r[0] for r in cur.fetchall()]
