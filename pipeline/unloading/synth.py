"""Synthetic raw data so the analytics, web app and skill can be built and tested before
(or while) the real video is processed. NOT real results: the video row is flagged synthetic=1
and the web app shows a banner.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

from . import store
from .detect import GRID_COLS, GRID_ROWS
from .zones import load_zones

W, H, FPS, DURATION = 1280, 720, 10, 150
ASPECT = W / H


def _in(t, spans):
    return any(a <= t < b for a, b in spans)


def _script(worker: int, t: float):
    """(state, feet_x, feet_y) for a worker at time t, or None if not in view."""
    if worker == 1:
        return ("waiting" if 70 <= t < 95 else "handling", 0.30, 0.58)
    if worker == 2:
        if t < 5:
            return None
        if 70 <= t < 95:
            return ("waiting", 0.70, 0.58)
        c = t % 40
        if c < 20:
            return ("handling", 0.70, 0.58)
        if c < 25:
            return ("moving", 0.70 + 0.10 * math.sin((c - 20) * 2.2), 0.58)
        return ("waiting", 0.72, 0.58)
    if worker == 3:
        if not 30 <= t < 125:
            return None
        if _in(t, [(55, 68), (100, 110)]):
            return ("handling", 0.28, 0.75)
        if _in(t, [(52, 55), (68, 71), (97, 100), (110, 113)]):
            return ("moving", 0.15 + 0.13 * ((t % 3) / 3), 0.80)
        return ("waiting", 0.15, 0.85)


def _skeleton(fx, fy, h, wrist, rng):
    j = lambda: rng.gauss(0, 0.0015)
    sx = 0.11 * h / ASPECT
    top = fy - h
    pts = [(fx, top + 0.07 * h), (fx - sx * .3, top + .05 * h), (fx + sx * .3, top + .05 * h),
           (fx - sx * .6, top + .07 * h), (fx + sx * .6, top + .07 * h),
           (fx - sx, top + .20 * h), (fx + sx, top + .20 * h),
           (fx - sx * 1.2, top + .36 * h), (fx + sx * 1.2, top + .36 * h),
           (fx - sx * 1.2, top + .50 * h), (fx + sx * 1.2, top + .50 * h),
           (fx - sx * .7, top + .53 * h), (fx + sx * .7, top + .53 * h),
           (fx - sx * .7, top + .76 * h), (fx + sx * .7, top + .76 * h),
           (fx - sx * .7, fy - .02 * h), (fx + sx * .7, fy - .02 * h)]
    if wrist:
        side = 10 if wrist[0] > fx else 9
        pts[side] = wrist
        sh = pts[side - 4]
        pts[side - 2] = ((sh[0] + wrist[0]) / 2, (sh[1] + wrist[1]) / 2 + 0.03 * h)
    return [[round(x + j(), 4), round(y + j(), 4), 0.9] for x, y in pts]


def run(db_path: Path, zones_path: Path) -> None:
    rng = random.Random(7)
    belt = next(z for z in load_zones(zones_path) if z.kind == "belt")
    reach = {1: (0.39, 0.46), 2: (0.61, 0.46), 3: (0.36, 0.62)}
    con = store.connect(db_path)
    store.init_raw(con, reset=True)
    con.execute("INSERT INTO video VALUES (1,?,?,?,?,?,?,?,?,?,?,?,1)",
                ("synthetic demo data", "", W, H, float(FPS), float(DURATION), DURATION * FPS, float(FPS),
                 "synthetic", "synthetic", datetime.now(timezone.utc).isoformat(timespec="seconds")))
    cells = [(c, r) for r in range(GRID_ROWS) for c in range(GRID_COLS)
             if belt.contains(((c + .5) / GRID_COLS, (r + .5) / GRID_ROWS))]
    for f in range(DURATION * FPS):
        t = f / FPS
        handling = 0
        for w in (1, 2, 3):
            s = _script(w, t)
            if s is None:
                continue
            state, fx, fy = s
            h, wrist = 0.32, None
            if state == "handling":
                handling += 1
                phase = (t + w * 0.7) % 2.5
                if phase < 1.25:  # reaching onto the belt
                    wrist = (reach[w][0] + 0.01 * math.sin(t * 5), reach[w][1])
                else:             # arms back towards the freight
                    away = -0.05 if reach[w][0] > fx else 0.05
                    wrist = (fx + away, fy - 0.55 * h + 0.09 * math.sin(t * 6))
            bw = 0.36 * h / ASPECT
            con.execute("INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?)",
                        (f, int(t * 1000), w, fx - bw, fy - h, fx + bw, fy, 0.9,
                         json.dumps(_skeleton(fx, fy, h, wrist, rng))))
        if f % FPS == 0:  # one thumbnail a second: grey floor and belt, tan "freight" on a share of belt cells
            grid = bytearray([70, 70, 72] * (GRID_COLS * GRID_ROWS))
            load = (0.02 if handling == 0 else 0.12 * handling) + (0.35 if 40 <= t < 52 else 0)
            for c, r in cells:
                i = (r * GRID_COLS + c) * 3
                grid[i:i + 3] = bytes([110, 150, 185]) if rng.random() < load else bytes([98, 100, 102])
            con.execute("INSERT INTO frame_grid VALUES (?,?,?,?,?)",
                        (f, int(t * 1000), GRID_COLS, GRID_ROWS, bytes(grid)))
    con.commit()
    con.close()
    print(f"Seeded SYNTHETIC demo data ({DURATION}s, 3 workers) -> {db_path}")
