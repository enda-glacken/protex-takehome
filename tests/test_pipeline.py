"""Unit tests for the pure-logic pieces, plus an end-to-end smoke test on synthetic data.
Run: ./run.sh test      (standard library only; no video, no ML dependencies)
"""
import json
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from unloading import analytics, insights, synth  # noqa: E402
from unloading.zones import Zone, point_in_polygon, zone_for  # noqa: E402

CONFIG, ZONES, SITE = ROOT / "config" / "analytics.json", ROOT / "tests" / "zones_synthetic.json", ROOT / "config" / "site.json"


class Geometry(unittest.TestCase):
    square = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]

    def test_point_in_polygon(self):
        self.assertTrue(point_in_polygon((0.5, 0.5), self.square))
        self.assertFalse(point_in_polygon((0.1, 0.5), self.square))
        self.assertFalse(point_in_polygon((0.5, 0.9), self.square))

    def test_zone_for_respects_kind(self):
        zones = [Zone("belt", "Belt", "belt", self.square)]
        self.assertIsNone(zone_for((0.5, 0.5), zones, kinds=["work"]))
        self.assertEqual(zone_for((0.5, 0.5), zones).id, "belt")


class Episodes(unittest.TestCase):
    def test_runs_min_length_and_merge(self):
        flags = [bool(int(c)) for c in "0111001110000010"]
        self.assertEqual(insights.runs(flags, min_len=3), [(1, 3), (6, 8)])
        self.assertEqual(insights.runs(flags, min_len=3, merge_gap=2), [(1, 8)])
        self.assertEqual(insights.runs([False] * 5, min_len=1), [])

    def test_classification_priority(self):
        cfg = json.loads(CONFIG.read_text())
        self.assertEqual(analytics._classify(0.5, 0.5, 0.0, cfg), "handling")   # working at the belt
        self.assertEqual(analytics._classify(1.0, 0.05, 0.0, cfg), "waiting")   # hand resting on the belt
        self.assertEqual(analytics._classify(0.0, 5.0, 5.0, cfg), "moving")     # walking beats arm swing
        self.assertEqual(analytics._classify(0.0, 5.0, 0.0, cfg), "handling")   # arms working in place
        self.assertEqual(analytics._classify(0.0, 0.0, 0.0, cfg), "waiting")


class SyntheticEndToEnd(unittest.TestCase):
    """The synthetic script has known ground truth: everyone waits from 70s to 95s on an empty belt."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "t.db"
        synth.run(cls.db, ZONES)
        analytics.run(cls.db, ZONES, CONFIG)
        insights.run(cls.db, CONFIG, SITE)
        cls.con = sqlite3.connect(cls.db)
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    def test_timeline_is_consistent(self):
        rows = self.con.execute("SELECT * FROM timeline").fetchall()
        self.assertEqual(len(rows), 150)
        for r in rows:
            self.assertEqual(r["present"], r["handling"] + r["moving"] + r["waiting"])

    def test_idle_stretch_is_found(self):
        mid = self.con.execute("SELECT AVG(handling) h, AVG(waiting) w FROM timeline WHERE t_s BETWEEN 73 AND 92").fetchone()
        self.assertLess(mid["h"], 0.2)
        self.assertGreater(mid["w"], 2.5)
        starved = self.con.execute("SELECT t_start_s, t_end_s FROM insights WHERE kind = 'belt_starved'").fetchall()
        self.assertTrue(any(s["t_start_s"] <= 75 and s["t_end_s"] >= 90 for s in starved))

    def test_kpis_in_range(self):
        k = {r["key"]: r["value"] for r in self.con.execute("SELECT key, value FROM kpis")}
        self.assertTrue(0.3 < k["crew_utilisation"] < 0.8)
        self.assertTrue(0 <= k["belt_empty_share"] <= 1)

    def test_skill_query_returns_timestamped_evidence(self):
        out = subprocess.run([sys.executable, str(ROOT / "skill/unloading-intel/scripts/query.py"), "--db", str(self.db),
                              "periods", "--min-present", "3", "--max-handling", "1"], capture_output=True, text=True, check=True)
        res = json.loads(out.stdout)
        self.assertTrue(any(p["start_s"] <= 75 and p["end_s"] >= 90 and "video_link" in p for p in res["periods"]))
        self.assertTrue(any("SYNTHETIC" in n for n in res["notes"]))

    def test_skill_refuses_writes(self):
        out = subprocess.run([sys.executable, str(ROOT / "skill/unloading-intel/scripts/query.py"), "--db", str(self.db),
                              "sql", "DELETE FROM timeline"], capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()
