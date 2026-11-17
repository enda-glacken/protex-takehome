"""Stage 3: timeline -> KPIs and insights an operations manager can act on.

Every insight carries: what happened, why it matters (so_what), what to do, the numbers behind it
(evidence) and a time range, so any claim can be checked against the video.

Insight kinds
    crew_mismatch    crew size moved opposite to the workload across the clip
    belt_stopped     freight standing still on the belt: the line is down for everyone
    belt_starved     belt (nearly) empty while workers are present  -> the constraint is upstream
    crew_underused   several workers present, few handling freight
    full_flow        belt well loaded and moving, most of the crew busy: the benchmark
    staffing_curve   working hands at each crew size: does an extra person find work?
    belt_gap         fallback when there is no belt occupancy: nobody's hands at the belt

Hand-to-belt contacts are stored and reported as a KPI but no insight is built on them: watching the
clip showed hands resting on the belt are counted, so they are not a reliable measure of pace.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import List, Tuple

from . import store


def mmss(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def runs(flags: List[bool], min_len: int, merge_gap: int = 0) -> List[Tuple[int, int]]:
    """Contiguous True runs as (start, end) inclusive, bridging gaps <= merge_gap."""
    out, start, last = [], None, None
    for t, f in enumerate(flags):
        if not f:
            continue
        if start is None:
            start = t
        elif t - last > merge_gap + 1:
            out.append((start, last))
            start = t
        last = t
    if start is not None:
        out.append((start, last))
    return [(a, b) for a, b in out if b - a + 1 >= min_len]


def _mode(values):
    return Counter(values).most_common(1)[0][0]


def _crew_time(ws: float) -> str:
    """Everyone's time added together, in words a manager uses."""
    return f"{ws:.0f} seconds of crew time" if ws < 90 else f"{ws / 60:.0f} minutes of crew time"


def _people(n: int) -> str:
    return "1 person" if n == 1 else f"{n} people"


def run(db_path: Path, config_path: Path, site_path: Path) -> int:
    cfg = json.loads(Path(config_path).read_text())["insights"]
    site = json.loads(Path(site_path).read_text()) if Path(site_path).is_file() else {}
    taken_off = site.get("belt_action", "taken off") == "taken off"
    # What a hand-to-belt contact means for the workers in view.
    contact, contacts = ("pick from the belt", "picks from the belt") if taken_off else \
                        ("placement on the belt", "placements on the belt")
    upstream = "the unloading end feeding the belt" if taken_off else "the freight supply to this crew"

    con = store.connect(db_path)
    T = [dict(r) for r in con.execute("SELECT * FROM timeline ORDER BY t_s")]
    hands = {r["t_s"] for r in con.execute("SELECT DISTINCT t_s FROM worker_seconds WHERE hands_on_belt > 0")}
    con.execute("DELETE FROM insights")
    con.execute("DELETE FROM kpis")
    staffed = [r for r in T if r["present"] > 0]
    if not staffed:
        con.commit()
        return 0
    has_belt = any(r["belt_occupancy"] is not None for r in T)
    occ = lambda r: r["belt_occupancy"] if r["belt_occupancy"] is not None else 0.0
    # Belt stopped = freight on it, but the freight is not moving.
    still = lambda r: r.get("belt_motion") is not None and r["belt_motion"] < cfg.get("belt_stopped_motion", 5.0)
    # A pause only counts as a stop if the belt had freight on it at some point in the pause. On an empty
    # belt nothing moves in the picture whether the belt runs or not, so that is "belt empty", not "stopped".
    # (Found by watching all eight first detections: three were an empty, running belt.)
    stops = [(a, b) for a, b in runs([still(r) for r in T], cfg.get("belt_stop_min_s", 20), 5)
             if max(occ(r) for r in T[a:b + 1]) > cfg["belt_empty_occupancy"]]
    stopped = {t for a, b in stops for t in range(a, b + 1)}

    # ---- KPIs ------------------------------------------------------------------------------
    present_ws = sum(r["present"] for r in T)
    handling_ws = sum(r["handling"] for r in T)
    waiting_ws = sum(r["waiting"] for r in T)
    touches = sum(r["belt_touches"] for r in T)
    rate = touches * 60 / len(staffed)
    kpis = [
        ("crew_utilisation", handling_ws / present_ws, "share", "Share of worker time spent handling freight"),
        ("waiting_share", waiting_ws / present_ws, "share", "Share of worker time spent waiting"),
        ("waiting_worker_seconds", waiting_ws, "worker-seconds", "Total worker time spent waiting"),
        ("belt_idle_share", sum(1 for r in staffed if r["t_s"] not in hands) / len(staffed), "share",
         "Share of staffed time with no hands at the belt"),
        ("belt_contacts", touches, "count", f"Hand-to-belt contacts (estimated {contacts})"),
        ("belt_contacts_per_min", rate, "per minute", f"Estimated {contacts} per staffed minute"),
        ("avg_crew", present_ws / len(staffed), "workers", "Average workers in view while staffed"),
        ("peak_crew", max(r["present"] for r in T), "workers", "Most workers in view at once"),
        ("staffed_seconds", len(staffed), "seconds", "Seconds with at least one worker in view"),
    ]
    if has_belt:
        kpis += [
            ("avg_belt_occupancy", sum(occ(r) for r in staffed) / len(staffed), "share",
             "Average share of the visible belt covered by freight"),
            ("belt_empty_share", sum(1 for r in staffed if occ(r) <= cfg["belt_empty_occupancy"]
                                     and r["t_s"] not in stopped) / len(staffed),
             "share", "Share of staffed time with the belt (nearly) empty and running"),
            ("belt_stopped_seconds", len(stopped), "seconds", "Time the belt stood still with freight on it"),
            ("belt_stopped_share", len(stopped) / len(T), "share", "Share of the clip the belt stood still with freight on it"),
            ("belt_stops", len(stops), "count", "Number of belt stops"),
        ]
    # Why were people waiting? Every waiting worker-second is attributed to exactly one line state.
    empty = lambda r: has_belt and r["t_s"] not in stopped and occ(r) <= cfg["belt_empty_occupancy"]
    wait_stop = sum(r["waiting"] for r in T if r["t_s"] in stopped)
    wait_empty = sum(r["waiting"] for r in T if empty(r))
    wait_flow = waiting_ws - wait_stop - wait_empty
    kpis += [
        ("waiting_ws_belt_stopped", wait_stop, "worker-seconds", "Waiting while the belt stood still"),
        ("waiting_ws_belt_empty", wait_empty, "worker-seconds", "Waiting at an empty, running belt"),
        ("waiting_ws_freight_available", wait_flow, "worker-seconds", "Waiting while freight was moving on the belt"),
        ("line_flowing_share", sum(1 for r in staffed if r["t_s"] not in stopped and not empty(r)) / len(staffed),
         "share", "Share of staffed time with freight moving on the belt"),
    ]
    con.executemany("INSERT INTO kpis VALUES (?,?,?,?)", [(k, round(v, 4), u, l) for k, v, u, l in kpis])

    out = []

    # ---- 1. Crew underused: several present, few handling ----------------------------------
    flags = [r["present"] >= cfg["idle_crew_min_present"] and r["waiting"] >= 1
             and r["handling"] <= r["present"] * cfg["idle_crew_max_handling_share"] for r in T]
    eps = []
    for a, b in runs(flags, cfg["min_episode_s"], cfg["merge_gap_s"]):
        seg = T[a:b + 1]
        eps.append((sum(r["waiting"] for r in seg), a, b, _mode(r["present"] for r in seg),
                    _mode(r["handling"] for r in seg), sum(occ(r) for r in seg) / len(seg)))
    for i, (wait_ws, a, b, p, h, o) in enumerate(sorted(eps, reverse=True)[:2], start=1):
        dur = b - a + 1
        if not has_belt:
            cause = "Watch the clip to see what they were waiting for."
        elif sum(1 for r in seg if r["t_s"] in stopped) > len(seg) / 2:
            cause = "The belt was standing still for most of this period, so nobody could work."
        elif o <= cfg["belt_empty_occupancy"] * 2:
            cause = f"The belt was close to empty ({o:.0%} covered), so they were waiting on {upstream}."
        else:
            cause = (f"The belt was {o:.0%} covered at the time, so freight was available. Check what held "
                     f"them up: full cages, no space to put freight down, or unclear who takes what.")
        out.append({
            "id": f"crew-underused-{i}", "kind": "crew_underused",
            "severity": "high" if wait_ws >= 240 else "medium", "t_start_s": a, "t_end_s": b,
            "title": f"{p} workers present, {h or 'none'} handling freight for {dur}s",
            "what": f"From {mmss(a)} to {mmss(b)}, {_people(p)} were in view but {f'only {h}' if h else 'nobody'} "
                    f"appeared to be handling freight. Together they waited for {_crew_time(wait_ws)}.",
            "so_what": "This is paid labour with nothing in front of it. If the pattern repeats across a shift, "
                       "this crew is larger than the work reaching it.",
            "recommendation": f"{cause} If it repeats, move one person to where the constraint is.",
            "evidence": {"duration_s": dur, "present": p, "handling": h, "waiting_worker_seconds": wait_ws,
                         "avg_belt_occupancy": round(o, 3) if has_belt else None},
        })

    if has_belt:
        # ---- 2a. Belt starved: the constraint is upstream of this crew ----------------------
        flags = [r["present"] >= 1 and occ(r) <= cfg["belt_empty_occupancy"] and r["t_s"] not in stopped for r in T]
        eps = sorted(((b - a + 1, a, b) for a, b in runs(flags, cfg["belt_gap_min_s"], 2)), reverse=True)
        for i, (dur, a, b) in enumerate(eps[:2], start=1):
            seg = T[a:b + 1]
            p, wait_ws = _mode(r["present"] for r in seg), sum(r["waiting"] for r in seg)
            out.append({
                "id": f"belt-starved-{i}", "kind": "belt_starved", "severity": "high" if dur >= 45 else "medium",
                "t_start_s": a, "t_end_s": b,
                "title": f"Belt ran empty for {dur}s with {p} waiting at it",
                "what": f"Between {mmss(a)} and {mmss(b)} almost nothing was on the belt while {_people(p)} "
                        f"stood at it ({_crew_time(wait_ws)} spent waiting).",
                "so_what": f"The crew in view was not the bottleneck here: {upstream} was. Adding people at "
                           "this end would not have moved more freight.",
                "recommendation": f"Look at {upstream} for this period (it is outside this camera's view). If it "
                                  "is short-handed, moving one person there from this crew is the cheapest fix.",
                "evidence": {"duration_s": dur, "present": p, "waiting_worker_seconds": wait_ws,
                             "avg_belt_occupancy": round(sum(occ(r) for r in seg) / len(seg), 3)},
            })
        # ---- 2b. Belt stopped: freight standing still, the whole line is down -----------------
        total = len(stopped)
        for i, (a, b) in enumerate(sorted(stops, key=lambda ab: ab[0] - ab[1])[:3], start=1):
            seg = T[a:b + 1]
            dur, p = b - a + 1, _mode(r["present"] for r in seg)
            wait_ws = sum(r["waiting"] for r in seg)
            out.append({
                "id": f"belt-stopped-{i}", "kind": "belt_stopped", "severity": "high" if i == 1 else "medium",
                "t_start_s": a, "t_end_s": b,
                "title": f"Belt stood still for {dur}s with freight on it",
                "what": f"From {mmss(a)} to {mmss(b)} the freight on the belt did not move, with {_people(p)} in view "
                        f"({_crew_time(wait_ws)} spent waiting). Across the clip the belt stood still {len(stops)} "
                        f"times, {total // 60} min {total % 60} s in total ({total / len(T):.0%} of the time).",
                "so_what": "A stopped belt idles everyone on the line at once, at both ends. It is the most "
                           "expensive kind of wait, and it does not show up as anyone doing anything wrong.",
                "recommendation": "Find out who stops the belt and why: an awkward item, a full cart, or the feeding "
                                  "end pausing. If stops cluster around oversized items, a set-down area off the belt "
                                  "would let it keep running.",
                "evidence": {"duration_s": dur, "present": p, "waiting_worker_seconds": wait_ws,
                             "stops_in_clip": len(stops), "total_stopped_s": total,
                             "all_stops": [[mmss(x), mmss(y)] for x, y in stops]},
            })
        # ---- 2c. Full flow: loaded, moving belt and a busy crew. The benchmark. ----------------
        flags = [occ(r) >= cfg["belt_full_occupancy"] and r["t_s"] not in stopped for r in T]
        eps = sorted(((b - a + 1, a, b) for a, b in runs(flags, cfg["belt_gap_min_s"], 2)), reverse=True)
        for i, (dur, a, b) in enumerate(eps[:2], start=1):
            seg = T[a:b + 1]
            p, o = _mode(r["present"] for r in seg), sum(occ(r) for r in seg) / len(seg)
            h = sum(r["handling"] for r in seg) / len(seg)
            out.append({
                "id": f"full-flow-{i}", "kind": "full_flow", "severity": "info",
                "t_start_s": a, "t_end_s": b,
                "title": f"Line at full flow for {dur}s: {h:.1f} of {p} handling",
                "what": f"From {mmss(a)} to {mmss(b)} the belt was about {o:.0%} covered and moving, with "
                        f"{_people(p)} in view and {h:.1f} handling on average.",
                "so_what": "This is the line working as intended: freight arriving steadily and most of the crew "
                           "busy. It shows what crew size the line needs when the freight is there.",
                "recommendation": "Use this as the benchmark. Compare crew size and how freight arrived here with "
                                  "the periods of waiting.",
                "evidence": {"duration_s": dur, "present": p, "avg_handling": round(h, 2),
                             "avg_belt_occupancy": round(o, 3)},
            })
    else:
        # ---- 2e. Fallback without belt occupancy: nobody's hands at the belt ------------------
        flags = [r["present"] >= 1 and r["t_s"] not in hands for r in T]
        gaps = sorted(((b - a + 1, a, b) for a, b in runs(flags, cfg["belt_gap_min_s"], 1)), reverse=True)
        for i, (dur, a, b) in enumerate(gaps[:3], start=1):
            p = _mode(r["present"] for r in T[a:b + 1])
            out.append({
                "id": f"belt-gap-{i}", "kind": "belt_gap", "severity": "high" if dur >= 20 else "medium",
                "t_start_s": a, "t_end_s": b,
                "title": f"Nobody worked the belt for {dur}s with {p} present",
                "what": f"Between {mmss(a)} and {mmss(b)} no worker's hands were at the conveyor, "
                        f"although {_people(p)} {'was' if p == 1 else 'were'} present.",
                "so_what": "The conveyor is the fixed-capacity asset. Without belt occupancy we cannot tell whether "
                           "it was empty (starved) or loaded and unattended, which point to different fixes.",
                "recommendation": "Check the clip, and draw a belt zone so occupancy can separate the two cases.",
                "evidence": {"duration_s": dur, "present": p},
            })

    # ---- 2d. Crew vs workload over the clip: were people there when the freight was? ----------
    block = cfg.get("trend_block_s", 120)
    blocks = []
    for s in range(0, len(T) - block + 1, block):
        seg = [r for r in T[s:s + block] if r["present"] > 0]
        if has_belt and len(seg) >= block * 0.8:
            blocks.append({"start_s": s, "present": sum(r["present"] for r in seg) / len(seg),
                           "handling": sum(r["handling"] for r in seg) / len(seg),
                           "occupancy": sum(occ(r) for r in seg) / len(seg)})
    if len(blocks) >= 6:
        n = len(blocks)
        mp, mo = sum(b["present"] for b in blocks) / n, sum(b["occupancy"] for b in blocks) / n
        sp = (sum((b["present"] - mp) ** 2 for b in blocks) / n) ** 0.5
        so = (sum((b["occupancy"] - mo) ** 2 for b in blocks) / n) ** 0.5
        if sp > 0 and so > 0:
            corr = sum((b["present"] - mp) * (b["occupancy"] - mo) for b in blocks) / (n * sp * so)
            gap = lambda b: (b["present"] - mp) / sp - (b["occupancy"] - mo) / so   # people relative to freight
            over, under = max(blocks, key=gap), min(blocks, key=gap)
            if corr <= -0.3:
                a, b = over["start_s"], under["start_s"]
                out.append({
                    "id": "crew-mismatch", "kind": "crew_mismatch", "severity": "high",
                    "t_start_s": a, "t_end_s": a + block - 1,
                    "title": "Crew size ran opposite to the workload",
                    "what": f"In the {block // 60} minutes from {mmss(a)} about {over['present']:.1f} people were in view "
                            f"and the belt was {over['occupancy']:.0%} covered. In the {block // 60} minutes from {mmss(b)} "
                            f"there were {under['present']:.1f} and it was {under['occupancy']:.0%} covered. Across the "
                            f"clip, the more people were present, the emptier the belt tended to be.",
                    "so_what": "People were at this line when the freight was not, and fewer were there when it "
                               "arrived. The same headcount, timed to the freight, would mean less waiting early "
                               "and less backlog later.",
                    "recommendation": "Find out where people went and what triggered it. If staffing follows a fixed "
                                      "routine rather than the belt, trial a simple rule: join this line when the belt "
                                      "is more than a third covered, leave when it runs empty.",
                    "evidence": {"correlation_present_vs_occupancy": round(corr, 2), "block_s": block,
                                 "blocks": [{k: round(v, 2) for k, v in b.items()} for b in blocks]},
                })

    # ---- 3. Staffing curve: does an extra person find work? ---------------------------------
    by_crew = {}
    for n in sorted({r["present"] for r in staffed}):
        seg = [r for r in staffed if r["present"] == n and r["t_s"] not in stopped]
        if len(seg) >= cfg.get("staffing_min_seconds", 60):
            by_crew[n] = {"seconds": len(seg), "avg_handling": round(sum(r["handling"] for r in seg) / len(seg), 2),
                          "handling_share": round(sum(r["handling"] for r in seg) / (n * len(seg)), 3)}
    sizes = sorted(by_crew)
    if len(sizes) >= 2:
        usual = max(sizes, key=lambda n: by_crew[n]["seconds"])       # the most common crew size
        hi = sizes[-1]
        if hi > usual:
            h_usual, h_hi = by_crew[usual]["avg_handling"], by_crew[hi]["avg_handling"]
            added = h_hi - h_usual
            flat = added < 0.5 * (hi - usual)   # each extra person added less than half a working pair of hands
            span = max(runs([r["present"] == hi for r in T], 1), key=lambda ab: ab[1] - ab[0])
            out.append({
                "id": "staffing-curve", "kind": "staffing_curve", "severity": "high" if flat else "info",
                "t_start_s": span[0], "t_end_s": span[1],
                "title": (f"About {h_usual:.0f} people working whether {usual} or {hi} were present" if flat else
                          f"Going from {usual} to {hi} people added {added:.1f} working hands"),
                "what": "Average number handling freight at each crew size (belt stops excluded): "
                        + ", ".join(f"{n} present: {by_crew[n]['avg_handling']:.1f}" for n in sizes) + ".",
                "so_what": ("Extra people did not find work to do. That points to a pace set by something fixed, "
                            "such as the number of scan points or the rate freight arrives, rather than headcount."
                            if flat else "Extra people found work, so the line was short of hands at the smaller size."),
                "recommendation": (f"Add a scan or pick-off point so more people can work in parallel; that is the "
                                   f"larger lever. Running with {usual} frees little by comparison. Crew size and "
                                   f"workload are confounded in one clip, so treat this as a test to run." if flat else
                                   "Adding a person here is likely to pay back; test where it stops scaling."),
                "evidence": {"usual_crew": usual, "by_crew_size": by_crew},
            })

    # ---- Allocation: when could this line give people up, and when could it have used one? ---
    # "Level" is the crew size at which the number of people actually working stops rising.
    con.execute("DELETE FROM allocation")
    release = []
    if by_crew and has_belt:
        best = max(v["avg_handling"] for v in by_crew.values())
        level = min(n for n, v in by_crew.items() if v["avg_handling"] >= 0.9 * best)
        release = runs([r["present"] > level for r in T], cfg.get("release_min_s", 30), 10)
        need = runs([r["present"] < level and occ(r) >= cfg["belt_full_occupancy"] and r["t_s"] not in stopped
                     for r in T], cfg.get("need_min_s", 20), 10)
        avg = lambda a, b, f: round(sum(f(r) for r in T[a:b + 1]) / (b - a + 1), 2)
        con.executemany("INSERT INTO allocation VALUES (?,?,?,?)",
                        [("release", a, b, avg(a, b, lambda r: max(0, r["present"] - level))) for a, b in release] +
                        [("need", a, b, avg(a, b, lambda r: max(0, level - r["present"]))) for a, b in need])
        con.executemany("INSERT INTO kpis VALUES (?,?,?,?)", [
            ("crew_level", level, "workers", "Crew size at which the number of people working stops rising"),
            ("spare_worker_seconds", sum(max(0, r["present"] - level) for r in T), "worker-seconds",
             "Worker time above the crew size the line could use"),
        ])

    # ---- Opportunities: waiting time by cause, largest first, each with its evidence --------
    con.execute("DELETE FROM opportunities")
    wm = lambda ws: f"{ws / 60:.0f} minutes of crew time"
    ops = []
    if wait_stop:
        longest = max(stops, key=lambda ab: ab[1] - ab[0])
        ops.append(("keep-belt-running", "Keep the belt running", wait_stop,
                    f"The belt stood still {len(stops)} times, {len(stopped) // 60} min {len(stopped) % 60} s in total. "
                    f"People waited for {wm(wait_stop)} during those stops.",
                    f"Find out who stops the belt and why. Start with the longest stop, at {mmss(longest[0])}.",
                    ["belt_stopped"]))
    if wait_flow:
        title, detail, spot = "Match the crew to the work", "", ""
        action = "Check what the waiting people were waiting for, then trial a smaller crew."
        # Where the crew stood while freight was flowing: the working area holding most of them.
        flow_s = {r["t_s"] for r in T if r["t_s"] not in stopped and not empty(r)}
        by_zone = {}
        for r in con.execute("SELECT w.t_s, z.name, w.state FROM worker_seconds w JOIN zones z ON z.id = w.zone "
                             "WHERE z.kind = 'work'"):
            if r["t_s"] in flow_s:
                z = by_zone.setdefault(r["name"], [0, 0])
                z[0] += 1
                z[1] += r["state"] == "handling"
        if by_zone and flow_s:
            name, (n, h) = max(by_zone.items(), key=lambda kv: kv[1][0])
            if n / len(flow_s) >= 1.5:
                spot = (f" Most of the crew stood at the {name[0].lower() + name[1:]}: about {n / len(flow_s):.0f} people "
                        f"there while freight was flowing, {h / len(flow_s):.1f} of them handling at a time.")
        if by_crew:
            top = max(v["avg_handling"] for v in by_crew.values())
            level = min(n for n, v in by_crew.items() if v["avg_handling"] >= 0.9 * top)
            if max(by_crew) > level:
                # More people did not mean more people working: the limit is places to work, not headcount.
                title = "Open a second working position"
                detail = (f" About {by_crew[level]['avg_handling']:.0f} people were handling whether {level} or "
                          f"{max(by_crew)} were present.")
                action = "Trial a second pick-off position further up the belt, so more of the crew can reach freight."
                if release:
                    spare_s = sum(b - a + 1 for a, b in release)
                    spare_n = max(1, round(sum(max(0, r["present"] - level) for a, b in release for r in T[a:b + 1]) / spare_s))
                    action += (f" Cutting the crew to {level} would free only about {_people(spare_n)} for "
                               f"{spare_s // 60} min {spare_s % 60} s in this recording.")
            else:
                action = f"Trial this line with {level} people when freight is flowing and redeploy the others."
        ops.append(("match-crew-to-work", title, wait_flow,
                    f"People waited for {wm(wait_flow)} while freight was moving on the belt.{detail}{spot}", action,
                    ["staffing_curve", "crew_underused", "crew_mismatch"]))
    if wait_empty:
        ops.append(("keep-freight-arriving", "Keep freight arriving", wait_empty,
                    f"People waited for {wm(wait_empty)} at an empty, running belt.",
                    f"Look at {upstream}, which is outside this camera's view, for the same periods.",
                    ["belt_starved"]))
    ops.sort(key=lambda o: -o[2])
    con.executemany("INSERT INTO opportunities VALUES (?,?,?,?,?,?,?,?)", [
        (o[0], i, o[1], o[2], round(o[2] / waiting_ws, 4) if waiting_ws else 0, o[3], o[4], json.dumps(o[5]))
        for i, o in enumerate(ops, start=1)])

    con.executemany("INSERT INTO insights VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (i["id"], i["kind"], i["severity"], i["t_start_s"], i["t_end_s"], i["title"], i["what"], i["so_what"],
         i["recommendation"], json.dumps(i["evidence"])) for i in out])
    con.commit()
    con.close()
    return len(out)
