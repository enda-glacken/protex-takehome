#!/usr/bin/env python3
"""Read-only query harness over the unloading analytics store (SQLite). Standard library only.

Every answer is JSON and every time range carries seconds, m:ss and a deep link into the web app,
so claims can be checked against the video.

    python query.py overview
    python query.py insights [--kind belt_stopped|belt_starved|crew_mismatch|crew_underused|full_flow|staffing_curve]
    python query.py periods --min-present 3 --max-handling 1 [--min-seconds 5]
    python query.py belt --mode idle|busy [--window 30] [--top 3]
    python query.py window --from 60 --to 90
    python query.py workers
    python query.py reviews --file belt-1-events.csv   (the manager's calls and notes, exported from the web app)
    python query.py sql "SELECT ... "          (read-only escape hatch; see references/schema.md)
"""
import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
APP_URL = os.environ.get("UNLOADING_APP_URL", "http://localhost:5173")


def find_db(explicit):
    candidates = [explicit, os.environ.get("UNLOADING_DB"),
                  SKILL_DIR / "data" / "unloading.db",                           # bundled with a packaged skill
                  SKILL_DIR.parents[1] / "data" / "processed" / "unloading.db",  # running inside the repo
                  Path.cwd() / "data" / "processed" / "unloading.db"]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    sys.exit(json.dumps({"error": "No unloading.db found. Pass --db, set UNLOADING_DB, or run `./run.sh pipeline`."}))


def mmss(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def span(a, b):
    return {"start_s": a, "end_s": b, "start": mmss(a), "end": mmss(b), "duration_s": b - a + 1,
            "video_link": f"{APP_URL}/?t={a}"}


def rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args)]


def runs(seconds, min_len, merge_gap=1):
    """Group a sorted list of matching seconds into (start, end) runs."""
    out = []
    for t in seconds:
        if out and t - out[-1][1] <= merge_gap + 1:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [(a, b) for a, b in out if b - a + 1 >= min_len]


def belt_stops(con):
    """Reported belt stops as (start_s, end_s). Read from the store, so the rule that decides what
    counts as a stop lives in one place (the pipeline) and is not repeated here."""
    r = con.execute("SELECT evidence FROM insights WHERE kind = 'belt_stopped' LIMIT 1").fetchone()
    if not r:
        return []

    def sec(s):
        t = 0
        for part in s.split(":"):
            t = t * 60 + int(part)
        return t
    return [(sec(x), sec(y)) for x, y in json.loads(r[0]).get("all_stops", [])]


def stats(con, a, b):
    r = rows(con, """SELECT COUNT(*) seconds, AVG(present) avg_present, MAX(present) max_present,
                     AVG(handling) avg_handling, MAX(handling) max_handling, AVG(waiting) avg_waiting,
                     SUM(waiting) waiting_worker_seconds, SUM(belt_touches) belt_contacts,
                     AVG(belt_occupancy) avg_belt_occupancy
                     FROM timeline WHERE t_s BETWEEN ? AND ?""", (a, b))[0]
    r = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}
    r["belt_contacts_per_min"] = round((r["belt_contacts"] or 0) * 60 / max(r["seconds"], 1), 1)
    r["belt_stopped_seconds"] = sum(max(0, min(b, y) - max(a, x) + 1) for x, y in belt_stops(con))
    return r


def notes(con):
    v = rows(con, "SELECT * FROM video")[0]
    n = ["'handling' = hands over the belt zone, or arms working while standing in place; it is an indicator, "
         "not ground truth.",
         "Belt contacts are hand-to-belt events: a proxy for items handled at the belt, not a parcel count. "
         "belt_occupancy is the estimated share (0..1) of the visible belt covered by freight.",
         "belt_stopped_seconds counts the seconds of a period that fall inside a reported belt stop (20 s or "
         "more, with freight on the belt). Shorter pauses and an empty, running belt are not stops.",
         "Worker labels (W1, W2...) are tracker ids; one person can receive several ids if they leave view. "
         "Prefer crew-level counts over per-person claims."]
    if v["synthetic"]:
        n.insert(0, "WARNING: this store holds SYNTHETIC demo data, not results from the real video. Say so.")
    return n


def cmd_overview(con, a):
    return {"video": rows(con, "SELECT source, duration_s, width, height, sample_fps, model, processed_at, synthetic FROM video")[0],
            "kpis": rows(con, "SELECT key, value, unit, label FROM kpis"),
            "zones": rows(con, "SELECT id, name, kind FROM zones"),
            "opportunities": [{**o, "event_kinds": json.loads(o["event_kinds"]), "worker_minutes": round(o["worker_seconds"] / 60, 1)}
                              for o in rows(con, "SELECT * FROM opportunities ORDER BY rank")],
            "insights": [{**span(i["t_start_s"], i["t_end_s"]), "id": i["id"], "severity": i["severity"], "title": i["title"]}
                         for i in rows(con, "SELECT * FROM insights ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t_start_s")]}


def cmd_insights(con, a):
    sql, args = "SELECT * FROM insights", ()
    if a.kind:
        sql, args = sql + " WHERE kind = ?", (a.kind,)
    out = []
    for i in rows(con, sql + " ORDER BY t_start_s", args):
        out.append({**i, "evidence": json.loads(i["evidence"]), "when": span(i["t_start_s"], i["t_end_s"]),
                    "insight_link": f"{APP_URL}/?insight={i['id']}"})
    return {"insights": out}


def cmd_periods(con, a):
    """Periods matching a crew condition, e.g. three present but only one working."""
    secs = [r["t_s"] for r in rows(con, """SELECT t_s FROM timeline WHERE present >= ? AND present <= ?
            AND handling >= ? AND handling <= ? AND waiting >= ? ORDER BY t_s""",
            (a.min_present, a.max_present, a.min_handling, a.max_handling, a.min_waiting))]
    found = [{**span(s, e), **stats(con, s, e)} for s, e in runs(secs, a.min_seconds)]
    found.sort(key=lambda p: -p["duration_s"])
    return {"condition": {k: getattr(a, k) for k in ("min_present", "max_present", "min_handling", "max_handling", "min_waiting", "min_seconds")},
            "total_matching_seconds": len(secs), "periods": found[:a.top]}


def cmd_belt(con, a):
    """Sliding windows ranked by belt use (belt_occupancy when available, then hand-to-belt contacts). Staffed windows only."""
    T = rows(con, "SELECT * FROM timeline ORDER BY t_s")
    w = min(a.window, len(T))
    scored = []
    for s in range(0, len(T) - w + 1):
        seg = T[s:s + w]
        if sum(1 for r in seg if r["present"] > 0) < w * 0.8:
            continue  # ignore windows where the bay was mostly empty
        act = [r["belt_occupancy"] for r in seg if r["belt_occupancy"] is not None]
        scored.append((round(sum(act) / len(act), 3) if act else 0, sum(r["belt_touches"] for r in seg), s))
    scored.sort(reverse=(a.mode == "busy"))
    picked = []
    for _, _, s in scored:  # top non-overlapping windows
        if all(abs(s - p) >= w for p in picked):
            picked.append(s)
        if len(picked) == a.top:
            break
    overall = stats(con, 0, len(T) - 1)
    return {"mode": a.mode, "window_s": w, "clip_average": overall,
            "windows": [{**span(s, s + w - 1), **stats(con, s, s + w - 1)} for s in picked]}


def cmd_window(con, a):
    lo, hi = a.start, a.end
    return {"when": span(lo, hi), "stats": stats(con, lo, hi),
            "per_worker": rows(con, """SELECT w.label, COUNT(*) seconds_present,
                SUM(ws.state='handling') handling_s, SUM(ws.state='moving') moving_s, SUM(ws.state='waiting') waiting_s,
                GROUP_CONCAT(DISTINCT ws.zone) zones
                FROM worker_seconds ws JOIN workers w USING (track_id)
                WHERE ws.t_s BETWEEN ? AND ? GROUP BY w.label ORDER BY handling_s DESC""", (lo, hi)),
            "insights_overlapping": rows(con, "SELECT id, title FROM insights WHERE t_start_s <= ? AND t_end_s >= ?", (hi, lo))}


def cmd_workers(con, a):
    return {"workers": [{**w, "seen": span(w["first_s"], w["last_s"])} for w in rows(con, "SELECT * FROM workers ORDER BY first_s")]}


def cmd_reviews(con, a):
    """The operations manager's calls and notes on each event, from the events file the web app exports."""
    path = Path(a.file).expanduser()
    if not path.is_file():
        sys.exit(json.dumps({"error": f"No file at {path}. In the web app choose Export data, then "
                                      "'Events, with your calls and notes', and pass that file."}))
    with open(path, newline="", encoding="utf-8-sig") as f:
        recs = list(csv.DictReader(f))
    secs = lambda m: int(m.split(":")[0]) * 60 + int(m.split(":")[1])
    events = [{"event": r["event"], "rule": r["rule"], "call": r.get("your_call") or None,
               "note": r.get("your_note") or None, "when": span(secs(r["from"]), secs(r["to"]))} for r in recs]
    called = [e for e in events if e["call"]]
    rejected = [e for e in called if e["call"] == "Not what happened"]
    by_rule = {}
    for e in called:
        r = by_rule.setdefault(e["rule"], {"reviewed": 0, "confirmed": 0, "not_what_happened": 0})
        r["reviewed"] += 1
        r["not_what_happened" if e in rejected else "confirmed"] += 1
    return {"file": str(path), "events_in_file": len(events), "reviewed": len(called),
            "without_a_call": len(events) - len(called),
            "calls": {c: sum(1 for e in called if e["call"] == c) for c in sorted({e["call"] for e in called})},
            "confirmed_share": round((len(called) - len(rejected)) / len(called), 2) if called else None,
            "needs_action": [e for e in called if e["call"] == "Needs action"],
            "not_what_happened": rejected,
            "manager_notes": [e for e in events if e["note"]],
            "by_rule": by_rule,
            "reading": "Calls and notes are the operations manager's own. 'Not what happened' counts against the rule "
                       "that raised the event. Patterns and benchmarks never get a call, so they stay without one."}


def cmd_sql(con, a):
    q = a.query.strip().rstrip(";")
    if not q.lower().startswith(("select", "with")) or ";" in q:
        sys.exit(json.dumps({"error": "Only a single SELECT statement is allowed."}))
    res = rows(con, q)
    return {"row_count": len(res), "rows": res[:a.limit], "truncated": len(res) > a.limit}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("overview")
    sub.add_parser("workers")
    s = sub.add_parser("insights"); s.add_argument("--kind")
    s = sub.add_parser("periods")
    s.add_argument("--min-present", type=int, default=1); s.add_argument("--max-present", type=int, default=99)
    s.add_argument("--min-handling", type=int, default=0); s.add_argument("--max-handling", type=int, default=99)
    s.add_argument("--min-waiting", type=int, default=0); s.add_argument("--min-seconds", type=int, default=5)
    s.add_argument("--top", type=int, default=10)
    s = sub.add_parser("belt")
    s.add_argument("--mode", choices=["idle", "busy"], default="idle")
    s.add_argument("--window", type=int, default=30); s.add_argument("--top", type=int, default=3)
    s = sub.add_parser("window")
    s.add_argument("--from", dest="start", type=int, required=True); s.add_argument("--to", dest="end", type=int, required=True)
    s = sub.add_parser("reviews"); s.add_argument("--file", required=True)
    s = sub.add_parser("sql"); s.add_argument("query"); s.add_argument("--limit", type=int, default=200)
    a = p.parse_args()

    con = sqlite3.connect(f"file:{find_db(a.db)}?mode=ro", uri=True)  # read-only: the skill can never alter the data
    con.row_factory = sqlite3.Row
    try:
        result = globals()[f"cmd_{a.cmd}"](con, a)
    except sqlite3.Error as e:
        sys.exit(json.dumps({"error": str(e)}))
    result["notes"] = notes(con)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
