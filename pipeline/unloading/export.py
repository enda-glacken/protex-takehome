"""Stage 4: store -> static JSON for the web app. The app has no backend; it reads these files."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from . import store


def rules(cfg: dict, counts: Counter) -> list:
    """The detection rules in plain language, with the thresholds currently in config/analytics.json."""
    i = cfg["insights"]
    pct = lambda v: f"{v:.0%}"
    return [dict(r, events=counts.get(r["kind"], 0)) for r in [
        {"kind": "belt_stopped", "name": "Belt standing still", "scope": "event", "alert_after_s": i["belt_stop_min_s"],
         "definition": f"Freight on the belt has not moved for {i['belt_stop_min_s']} seconds or more."},
        {"kind": "belt_starved", "name": "Belt empty, crew waiting", "scope": "event", "alert_after_s": i["belt_gap_min_s"],
         "definition": f"The belt is running but under {pct(i['belt_empty_occupancy'])} covered, with someone present, "
                       f"for {i['belt_gap_min_s']} seconds or more."},
        {"kind": "crew_underused", "name": "Crew larger than the work", "scope": "event", "alert_after_s": i["min_episode_s"],
         "definition": f"{i['idle_crew_min_present']} or more people present and no more than "
                       f"{pct(i['idle_crew_max_handling_share'])} of them handling freight, for {i['min_episode_s']} seconds or more."},
        {"kind": "full_flow", "name": "Line at full flow", "scope": "event",
         "definition": f"The belt is at least {pct(i['belt_full_occupancy'])} covered and moving for "
                       f"{i['belt_gap_min_s']} seconds or more. A benchmark, not a problem."},
        {"kind": "staffing_curve", "name": "People working by crew size", "scope": "clip",
         "definition": f"Average number of people handling freight at each crew size seen for {i['staffing_min_seconds']} seconds or more."},
        {"kind": "crew_mismatch", "name": "Crew size against workload", "scope": "clip",
         "definition": f"Crew size compared with belt load over {i['trend_block_s'] // 60}-minute blocks."},
    ]]


def run(db_path: Path, out_dir: Path, site_path: Path, config_path: Path) -> None:
    con = store.connect(db_path, read_only=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = lambda sql: [dict(r) for r in con.execute(sql)]

    def dump(name, obj):
        (out_dir / name).write_text(json.dumps(obj, separators=(",", ":")))

    video = rows("SELECT * FROM video")[0]
    site = json.loads(Path(site_path).read_text()) if Path(site_path).is_file() else {}
    site = {k: v for k, v in site.items() if not k.startswith("_")}
    dump("meta.json", {"video": video, "site": site, "kpis": {k["key"]: k for k in rows("SELECT * FROM kpis")}})
    dump("timeline.json", rows("SELECT * FROM timeline ORDER BY t_s"))
    dump("workers.json", rows("SELECT * FROM workers ORDER BY first_s"))
    dump("zones.json", [{**z, "polygon": json.loads(z["polygon"])} for z in rows("SELECT * FROM zones")])
    order = {"high": 0, "medium": 1, "info": 2}
    insights = [{**i, "evidence": json.loads(i["evidence"])} for i in rows("SELECT * FROM insights")]
    # Most important first: severity, then the kind of finding, then time.
    kinds = ["belt_stopped", "staffing_curve", "crew_mismatch", "belt_starved", "crew_underused", "belt_gap", "full_flow"]
    rank = lambda i: (order.get(i["severity"], 9), kinds.index(i["kind"]) if i["kind"] in kinds else 99, i["t_start_s"])
    dump("insights.json", sorted(insights, key=rank))

    dump("allocation.json", rows("SELECT * FROM allocation ORDER BY t_start_s"))
    dump("opportunities.json", [{**o, "event_kinds": json.loads(o["event_kinds"])}
                                for o in rows("SELECT * FROM opportunities ORDER BY rank")])
    dump("rules.json", rules(json.loads(Path(config_path).read_text()), Counter(i["kind"] for i in insights)))

    # Per-frame overlay data: [t_ms, [[track_id, state, x1, y1, x2, y2, [x, y, conf]*17], ...]]
    state = {(r["t_s"], r["track_id"]): r["state"] for r in con.execute("SELECT t_s, track_id, state FROM worker_seconds")}
    labels = {r["track_id"]: r["label"] for r in con.execute("SELECT track_id, label FROM workers")}
    frames = defaultdict(list)
    for d in con.execute("SELECT * FROM detections ORDER BY t_ms"):
        if d["track_id"] not in labels:
            continue  # short-lived track dropped by analytics
        kp = [[round(x, 3), round(y, 3), round(c, 1)] for x, y, c in json.loads(d["keypoints"] or "[]")]
        frames[d["t_ms"]].append([labels[d["track_id"]], state.get((d["t_ms"] // 1000, d["track_id"]), "waiting"),
                                  round(d["x1"], 3), round(d["y1"], 3), round(d["x2"], 3), round(d["y2"], 3), kp])
    dump("frames.json", [[t, dets] for t, dets in sorted(frames.items())])
    con.close()
    print(f"Exported web data -> {out_dir}")
