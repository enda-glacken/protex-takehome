#!/usr/bin/env python3
"""Ground truth for the brief's four skill questions, computed straight from the store."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / "skill" / "unloading-intel" / "scripts" / "query.py"


def ask(*args):
    return json.loads(subprocess.run([sys.executable, str(Q), *args], capture_output=True, text=True, check=True).stdout)


def show(title, items, fields):
    print(f"\n{title}")
    for it in items:
        print("  " + f"{it['start']} to {it['end']}".ljust(16) + "  ".join(f"{f}={it.get(f)}" for f in fields))


show("1. Conveyor most underutilised (lowest occupancy, staffed windows)",
     ask("belt", "--mode", "idle", "--top", "3")["windows"], ["avg_belt_occupancy", "belt_stopped_seconds", "avg_present", "avg_waiting"])
show("2. Busiest period and workers handling in it",
     ask("belt", "--mode", "busy", "--top", "1")["windows"], ["avg_handling", "max_handling", "avg_present", "belt_contacts_per_min"])
show("3. Three or more present, at most one handling",
     ask("periods", "--min-present", "3", "--max-handling", "1", "--top", "5")["periods"], ["duration_s", "avg_present", "avg_handling"])
print("\n4. Biggest opportunities (ranked by crew time spent waiting)")
for o in ask("overview")["opportunities"]:
    print(f"  {o['rank']}. {o['title']}: {round(o['share_of_waiting'] * 100)}% of waiting, {round(o['worker_minutes'])} min of crew time")
