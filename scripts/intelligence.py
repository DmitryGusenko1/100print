#!/usr/bin/env python3
"""Read project intelligence or apply an application-role-only migration."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect
from app.intelligence import migrate, snapshot, metrics, review, seed_strategy
p=argparse.ArgumentParser()
p.add_argument('command',choices=['migrate','snapshot','metrics','review','seed'])
a=p.parse_args()
with connect() as conn, conn.cursor() as cur:
    result={'migrate':migrate,'snapshot':snapshot,'metrics':metrics,'review':review,'seed':seed_strategy}[a.command](cur)
print(json.dumps(result or {'ok':True},default=str,ensure_ascii=False))
