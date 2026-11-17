#!/usr/bin/env python3
"""Compare hand labels (evals/activity_labels.csv) with the pipeline's timeline. Standard library only."""
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "unloading.db"
labels = list(csv.DictReader((ROOT / "evals" / "activity_labels.csv").open()))
# Rows you have not filled in yet are skipped.
labels = [r for r in labels if (r["present"] or "").strip() and (r["handling"] or "").strip()]
if not labels:
    sys.exit("No labels yet. Add rows to evals/activity_labels.csv (see evals/README.md).")
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
print(f"{'time':>6} {'present h/p':>12} {'handling h/p':>13}  note")
exact = {"present": 0, "handling": 0}
err = {"present": 0, "handling": 0}
for row in labels:
    t = int(row["t_s"])
    # Compare with the 3-second neighbourhood: a human label is not frame-exact.
    got = con.execute("SELECT ROUND(AVG(present)), ROUND(AVG(handling)) FROM timeline WHERE t_s BETWEEN ? AND ?",
                      (t - 1, t + 1)).fetchone()
    for k, g in zip(("present", "handling"), got):
        want = int(row[k])
        exact[k] += int(want == int(g or 0))
        err[k] += abs(want - int(g or 0))
    print(f"{t // 60}:{t % 60:02d}".rjust(6), f"{row['present']}/{int(got[0] or 0)}".rjust(12),
          f"{row['handling']}/{int(got[1] or 0)}".rjust(13), "", row.get("note", ""))
n = len(labels)
print(f"\n{n} labelled moments")
for k in ("present", "handling"):
    print(f"  {k:9} exact match {exact[k] / n:.0%}   mean absolute error {err[k] / n:.2f} workers")
