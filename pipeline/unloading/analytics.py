"""Stage 2: raw detections + zones -> per-second worker activity, belt signals, crew timeline.

Pure Python + SQLite, no video and no ML. Re-run it whenever zones or thresholds change.

Activity model (deliberately simple and explainable, one label per worker per second):
    handling  a wrist is over the belt zone AND the arm is moving (a hand resting on the belt does
              not count), or the arms are moving quickly while the body stays put
    moving    the body is travelling (walking to/from the freight)
    waiting   present, but neither of the above
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from . import store
from .zones import Zone, load_zones, zone_for

L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST = 5, 6, 9, 10
STATES = ("handling", "moving", "waiting")


def _dist(a, b, aspect):
    return math.hypot((a[0] - b[0]) * aspect, a[1] - b[1])


def _samples(con, cfg, zones: List[Zone], aspect: float):
    """Per-detection features, grouped by track."""
    belts = [z for z in zones if z.kind == "belt"]
    places = [z for z in zones if z.kind != "belt"]
    kmin = cfg["keypoint_min_conf"]
    by_track: Dict[int, list] = defaultdict(list)
    for r in con.execute("SELECT * FROM detections ORDER BY track_id, t_ms"):
        kp = json.loads(r["keypoints"] or "[]")
        h = max(r["y2"] - r["y1"], 1e-3)
        feet = ((r["x1"] + r["x2"]) / 2, r["y2"])
        ok = lambda i: len(kp) > i and kp[i][2] >= kmin
        sh = [kp[i][:2] for i in (L_SHOULDER, R_SHOULDER) if ok(i)]
        torso = (sum(p[0] for p in sh) / len(sh), sum(p[1] for p in sh) / len(sh)) if sh else \
                ((r["x1"] + r["x2"]) / 2, r["y1"] + 0.2 * h)
        wrists = {i: tuple(kp[i][:2]) for i in (L_WRIST, R_WRIST) if ok(i)}
        # A wrist counts as at the belt if it is inside the zone or within a small reach margin of it.
        m = cfg.get("belt_reach_margin", 0.0)
        near = lambda w: [w, (w[0] - m, w[1]), (w[0] + m, w[1]), (w[0], w[1] - m), (w[0], w[1] + m)]
        on_belt = next((z.id for z in belts for w in wrists.values() if any(z.contains(q) for q in near(w))), None)
        place = zone_for(feet, places)
        by_track[r["track_id"]].append({
            "t_ms": r["t_ms"], "h": h, "feet": feet, "on_belt": on_belt, "conf": r["conf"],
            "zone": place.id if place else None,
            "rel": {i: (w[0] - torso[0], w[1] - torso[1]) for i, w in wrists.items()},
        })
    # Keep tracks that last long enough and that the detector was confident about. Low-confidence
    # tracks are mostly not people (a stack of parcels was repeatedly detected as a person).
    min_ms, min_conf = cfg["min_track_seconds"] * 1000, cfg.get("min_track_conf", 0.0)
    return {t: s for t, s in by_track.items()
            if s[-1]["t_ms"] - s[0]["t_ms"] >= min_ms and sum(x["conf"] for x in s) / len(s) >= min_conf}


def _classify(hands: float, wrist_speed: float, body_speed: float, cfg) -> str:
    # Hands at the belt only count as handling if the arm is also moving: people rest a hand on the
    # belt edge while they wait, and that must not read as work.
    if hands >= cfg["handling_hands_on_belt_share"] and wrist_speed >= cfg.get("handling_min_wrist_speed_at_belt", 0.0):
        return "handling"
    if body_speed >= cfg["moving_body_speed"]:
        return "moving"
    if wrist_speed >= cfg["handling_wrist_speed"]:
        return "handling"
    return "waiting"


def _smooth(states: Dict[int, str], window: int) -> Dict[int, str]:
    """Majority vote over a centred window, so one noisy second doesn't flip a label."""
    half = window // 2
    out = {}
    for t in states:
        votes = Counter(states[u] for u in range(t - half, t + half + 1) if u in states)
        top = max(votes.values())
        out[t] = states[t] if votes[states[t]] == top else votes.most_common(1)[0][0]
    return out


def _belt_signals(con, zones: List[Zone], cfg):
    """Per second: (occupancy, motion) for the belt zone, from the one-a-second colour thumbnails.

    occupancy  share of the visible belt covered by freight. The belt surface is one uniform colour,
               so the most common colour inside the belt zone across the clip is "empty belt" and any
               cell that differs from it is covered. Cells hidden by a person are left out. Freight
               close to the belt's own colour is under-counted.
    motion     mean colour change, since the previous second, of the cells that hold freight. On a
               running belt freight moves and this is large; when it is near zero the freight is
               standing still, i.e. the belt has stopped. None when there is too little freight to tell.
    """
    belts = [z for z in zones if z.kind == "belt"]
    grids = con.execute("SELECT frame_idx, t_ms, cols, rows, px FROM frame_grid ORDER BY t_ms").fetchall()
    if not belts or not grids:
        return {}, {}
    cols, rows = grids[0]["cols"], grids[0]["rows"]
    cells = [(c, r) for r in range(rows) for c in range(cols)
             if any(z.contains(((c + 0.5) / cols, (r + 0.5) / rows)) for z in belts)]
    if not cells:
        return {}, {}
    # Empty-belt reference: modal colour (16-level bins) over a sample of the clip.
    bins: Counter = Counter()
    for g in grids[::max(1, len(grids) // 80)]:
        px = g["px"]
        for c, r in cells:
            i = (r * cols + c) * 3
            bins[(px[i] >> 4, px[i + 1] >> 4, px[i + 2] >> 4)] += 1
    ref = [v * 16 + 8 for v in bins.most_common(1)[0][0]]
    thr2 = cfg["belt_colour_threshold"] ** 2
    min_cells = cfg.get("belt_motion_min_cells", 12)

    boxes = defaultdict(list)
    for d in con.execute("SELECT frame_idx, x1, y1, x2, y2 FROM detections"):
        boxes[d["frame_idx"]].append((d["x1"], d["y1"], d["x2"], d["y2"]))
    occupancy, motion, prev, prev_t = {}, {}, None, None
    for g in grids:
        px, bxs, cur = g["px"], boxes.get(g["frame_idx"], []), {}
        for c, r in cells:
            x, y = (c + 0.5) / cols, (r + 0.5) / rows
            if any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in bxs):
                continue  # a person is covering this cell
            i = (r * cols + c) * 3
            col = (px[i], px[i + 1], px[i + 2])
            cur[(c, r)] = (col, (col[0] - ref[0]) ** 2 + (col[1] - ref[1]) ** 2 + (col[2] - ref[2]) ** 2 > thr2)
        t = g["t_ms"] // 1000
        if cur:
            occupancy[t] = round(sum(1 for v in cur.values() if v[1]) / len(cur), 3)
        if prev is not None and t - prev_t <= 2:
            both = [k for k in cur if k in prev and (cur[k][1] or prev[k][1])]
            if len(both) >= min_cells:
                motion[t] = round(sum(abs(cur[k][0][j] - prev[k][0][j]) for k in both for j in range(3))
                                  / (3 * len(both)), 2)
        prev, prev_t = cur, t
    return occupancy, motion


def run(db_path: Path, zones_path: Path, config_path: Path) -> dict:
    cfg = json.loads(Path(config_path).read_text())
    zones = load_zones(zones_path)
    con = store.connect(db_path)
    video = con.execute("SELECT * FROM video").fetchone()
    if video is None:
        raise SystemExit("No raw data in the store. Run the detect stage (or `seed`) first.")
    aspect = video["width"] / video["height"]
    duration = int(math.ceil(video["duration_s"]))

    store.reset_derived(con)
    con.executemany("INSERT INTO zones VALUES (?,?,?,?)",
                    [(z.id, z.name, z.kind, json.dumps(z.polygon)) for z in zones])

    tracks = _samples(con, cfg, zones, aspect)
    touches_by_s: Counter = Counter()
    worker_rows, labels, seen, samples_in = [], {}, [], {}
    for n, (tid, samples) in enumerate(sorted(tracks.items(), key=lambda kv: kv[1][0]["t_ms"]), start=1):
        labels[tid] = f"W{n}"
        feats: Dict[int, dict] = {}
        prev, last_contact_end, in_contact, n_touch = None, -10**9, False, 0
        for s in samples:
            t = s["t_ms"] // 1000
            f = feats.setdefault(t, {"n": 0, "belt": 0, "body": 0.0, "wrist": 0.0, "dt": 0.0, "zones": Counter()})
            f["n"] += 1
            f["belt"] += 1 if s["on_belt"] else 0
            f["zones"][s["zone"]] += 1
            if prev is not None and 0 < s["t_ms"] - prev["t_ms"] <= 1000:
                h = (s["h"] + prev["h"]) / 2
                f["dt"] += (s["t_ms"] - prev["t_ms"]) / 1000
                f["body"] += _dist(s["feet"], prev["feet"], aspect) / h
                arm = [_dist(s["rel"][i], prev["rel"][i], aspect) / h for i in s["rel"] if i in prev["rel"]]
                f["wrist"] += max(arm) if arm else 0.0
            # Hand-to-belt contact events: rising edge, debounced.
            if s["on_belt"] and not in_contact:
                if s["t_ms"] - last_contact_end >= cfg["touch_debounce_ms"]:
                    con.execute("INSERT INTO belt_events (t_ms, track_id, zone) VALUES (?,?,?)",
                                (s["t_ms"], tid, s["on_belt"]))
                    touches_by_s[t] += 1
                    n_touch += 1
                in_contact = True
            elif not s["on_belt"] and in_contact:
                in_contact, last_contact_end = False, s["t_ms"]
            prev = s

        raw_state, per_s = {}, {}
        for t, f in feats.items():
            dt = f["dt"] or 1.0
            per_s[t] = (f["belt"] / f["n"], f["wrist"] / dt, f["body"] / dt, f["zones"].most_common(1)[0][0])
            raw_state[t] = _classify(per_s[t][0], per_s[t][1], per_s[t][2], cfg)
        state = _smooth(raw_state, cfg["smooth_window_s"])
        for t in per_s:
            seen.append((t, tid, state[t]))
            samples_in[(t, tid)] = feats[t]["n"]
        con.executemany("INSERT INTO worker_seconds VALUES (?,?,?,?,?,?,?)",
                        [(t, tid, per_s[t][3], state[t], round(per_s[t][0], 3), round(per_s[t][1], 3),
                          round(per_s[t][2], 3)) for t in sorted(per_s)])
        c = Counter(state.values())
        worker_rows.append((tid, labels[tid], min(per_s), max(per_s), len(per_s), c["handling"], c["moving"],
                            c["waiting"], round(c["handling"] / len(per_s), 3), n_touch))
    con.executemany("INSERT INTO workers VALUES (?,?,?,?,?,?,?,?,?,?)", worker_rows)

    belt, belt_motion = _belt_signals(con, zones, cfg)
    # Crew counts per second. Trackers hand out a new id when someone is briefly lost, so counting
    # distinct ids double-counts people. Instead each track is weighted by the share of that second's
    # sampled frames it appears in, and the weighted totals are rounded so the states still add up.
    frames_in = Counter(r["s"] for r in con.execute("SELECT DISTINCT frame_idx, t_ms / 1000 AS s FROM detections"))
    weights = {t: Counter() for t in range(duration)}
    for t, tid, state in seen:
        if t in weights:
            weights[t][state] += min(1.0, samples_in[(t, tid)] / max(frames_in[t], 1))
    rows = []
    for t, w in sorted(weights.items()):
        present = int(sum(w.values()) + 0.5)
        counts = {s: int(w[s]) for s in STATES}
        for s in sorted(STATES, key=lambda s: w[s] - int(w[s]), reverse=True):  # largest remainder
            if sum(counts.values()) >= present:
                break
            counts[s] += 1
        rows.append((t, present, counts["handling"], counts["moving"], counts["waiting"],
                     touches_by_s.get(t, 0), belt.get(t), belt_motion.get(t)))
    con.executemany("INSERT INTO timeline VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    summary = {"tracks": len(tracks), "seconds": duration, "belt_events": sum(touches_by_s.values()),
               "belt_index": bool(belt)}
    con.close()
    return summary
