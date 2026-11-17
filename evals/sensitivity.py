"""How far do the headline findings move when the thresholds move?

Re-runs the analysis (not the video) on a temporary copy of the stored detections, once per
variant, and prints a table. Nothing in the real database or the web data is changed.

    python evals/sensitivity.py [--db data/processed/unloading.db]
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from unloading import analytics, insights, store  # noqa: E402

# name, {config key: value}. Keys under "insights." go in the insights block.
VARIANTS = [
    ("Baseline (as shipped)", {}),
    ("Belt stop: stricter motion test (4)", {"insights.belt_stopped_motion": 4.0}),
    ("Belt stop: looser motion test (6)", {"insights.belt_stopped_motion": 6.0}),
    ("Belt stop: 15 s minimum", {"insights.belt_stop_min_s": 15}),
    ("Belt stop: 30 s minimum", {"insights.belt_stop_min_s": 30}),
    ("Handling: arm-speed thresholds 20% lower", {"handling_min_wrist_speed_at_belt": 0.16, "handling_wrist_speed": 0.72}),
    ("Handling: arm-speed thresholds 20% higher", {"handling_min_wrist_speed_at_belt": 0.24, "handling_wrist_speed": 1.08}),
    ("Handling: hands at belt 20% of the second", {"handling_hands_on_belt_share": 0.20}),
    ("Handling: hands at belt 30% of the second", {"handling_hands_on_belt_share": 0.30}),
    ("Moving: body-speed threshold 20% lower", {"moving_body_speed": 0.36}),
    ("Moving: body-speed threshold 20% higher", {"moving_body_speed": 0.54}),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=store.DEFAULT_DB)
    a = ap.parse_args()
    base = json.loads((ROOT / "config" / "analytics.json").read_text())
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "copy.db"
        shutil.copy(a.db, db)
        for name, change in VARIANTS:
            cfg = json.loads(json.dumps(base))
            for key, value in change.items():
                if key.startswith("insights."):
                    cfg["insights"][key.split(".", 1)[1]] = value
                else:
                    cfg[key] = value
            path = Path(tmp) / "analytics.json"
            path.write_text(json.dumps(cfg))
            analytics.run(db, ROOT / "config" / "zones.json", path)
            insights.run(db, path, ROOT / "config" / "site.json")
            con = store.connect(db)
            k = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM kpis")}
            curve = con.execute("SELECT evidence FROM insights WHERE kind = 'staffing_curve'").fetchone()
            by = json.loads(curve["evidence"])["by_crew_size"] if curve else {}
            top = con.execute("SELECT title, share_of_waiting FROM opportunities ORDER BY rank LIMIT 1").fetchone()
            con.close()
            rows.append((name, int(k.get("belt_stops", 0)), k.get("belt_stopped_share", 0), k.get("waiting_share", 0),
                         k.get("crew_utilisation", 0),
                         " / ".join(f"{by[n]['avg_handling']:.1f}" if n in by else "n/a" for n in ("5", "6", "7")),
                         f"{top['title']} ({int(top['share_of_waiting'] * 100 + 0.5)}%)" if top else "n/a"))
    print("| Variant | Belt stops | Belt downtime | Crew waiting | Crew handling | People handling with 5 / 6 / 7 present | Top action (share of waiting) |")
    print("|---|---|---|---|---|---|---|")
    for name, stops, down, wait, hand, curve, top in rows:
        print(f"| {name} | {stops} | {down:.0%} | {wait:.0%} | {hand:.0%} | {curve} | {top} |")


if __name__ == "__main__":
    main()
