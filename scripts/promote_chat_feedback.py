#!/usr/bin/env python3
"""CLI: promote thumbs-up chat feedback into learned_answers.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.services import feedback_svc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    out = feedback_svc.promote_feedback(limit=args.limit)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
