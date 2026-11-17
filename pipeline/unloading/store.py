"""SQLite store. One file, two layers:

RAW layer (written once by the CV stage; expensive to produce)
    video        one row of metadata about the processed clip
    detections   one row per person per sampled frame: box, track id, 17 COCO keypoints
    frame_grid   one small colour thumbnail per second (for belt occupancy in any zone drawn later)

DERIVED layer (rebuilt in seconds by the analytics stage; never needs the video)
    zones, worker_seconds, timeline, belt_events, workers, insights, kpis

Zones are applied in the derived layer, so redrawing a zone never re-runs inference.
All coordinates are normalised to 0..1 of frame width/height.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "processed" / "unloading.db"

RAW_SCHEMA = """
CREATE TABLE IF NOT EXISTS video (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    source TEXT, path TEXT,
    width INTEGER, height INTEGER,
    fps REAL, duration_s REAL, frame_count INTEGER,
    sample_fps REAL,            -- rate the CV stage actually sampled at
    model TEXT, tracker TEXT,
    processed_at TEXT,
    synthetic INTEGER DEFAULT 0 -- 1 = generated demo data, not a real video
);
CREATE TABLE IF NOT EXISTS detections (
    frame_idx INTEGER NOT NULL,
    t_ms INTEGER NOT NULL,
    track_id INTEGER NOT NULL,
    x1 REAL, y1 REAL, x2 REAL, y2 REAL,
    conf REAL,
    keypoints TEXT,             -- JSON [[x, y, conf] * 17], COCO order
    PRIMARY KEY (frame_idx, track_id)
);
CREATE INDEX IF NOT EXISTS idx_det_t ON detections (t_ms);
CREATE INDEX IF NOT EXISTS idx_det_track ON detections (track_id, t_ms);
CREATE TABLE IF NOT EXISTS frame_grid (
    frame_idx INTEGER PRIMARY KEY,
    t_ms INTEGER NOT NULL,
    cols INTEGER, rows INTEGER,
    px BLOB                     -- rows*cols*3 bytes: mean B, G, R of each cell
);
"""

DERIVED_TABLES = ["zones", "worker_seconds", "timeline", "belt_events", "workers", "insights", "kpis", "opportunities", "allocation"]

DERIVED_SCHEMA = """
CREATE TABLE zones (
    id TEXT PRIMARY KEY, name TEXT, kind TEXT,   -- kind: belt | work | staging | other
    polygon TEXT                                 -- JSON [[x, y], ...] normalised
);
CREATE TABLE worker_seconds (
    t_s INTEGER NOT NULL, track_id INTEGER NOT NULL,
    zone TEXT,                  -- zone id the worker's feet are in (NULL = outside all zones)
    state TEXT NOT NULL,        -- handling | moving | waiting
    hands_on_belt REAL,         -- share of samples this second with a wrist inside a belt zone
    wrist_speed REAL,           -- arm motion relative to torso, body-heights per second
    body_speed REAL,            -- feet displacement, body-heights per second
    PRIMARY KEY (t_s, track_id)
);
CREATE TABLE timeline (
    t_s INTEGER PRIMARY KEY,
    present INTEGER, handling INTEGER, moving INTEGER, waiting INTEGER,
    belt_touches INTEGER,       -- hand-to-belt contact events that started this second
    belt_occupancy REAL,        -- 0..1 share of the visible belt covered by freight (NULL if no frame_grid)
    belt_motion REAL            -- how much the freight on the belt changed since the previous second
                                -- (colour units; near 0 = freight standing still; NULL = too little freight to tell)
);
CREATE TABLE belt_events (
    id INTEGER PRIMARY KEY, t_ms INTEGER, track_id INTEGER, zone TEXT
);
CREATE TABLE workers (
    track_id INTEGER PRIMARY KEY, label TEXT,
    first_s INTEGER, last_s INTEGER,
    present_s INTEGER, handling_s INTEGER, moving_s INTEGER, waiting_s INTEGER,
    utilisation REAL,           -- handling_s / present_s
    belt_touches INTEGER
);
CREATE TABLE insights (
    id TEXT PRIMARY KEY, kind TEXT, severity TEXT,   -- severity: high | medium | info
    t_start_s INTEGER, t_end_s INTEGER,
    title TEXT, what TEXT, so_what TEXT, recommendation TEXT,
    evidence TEXT               -- JSON: the numbers behind the claim
);
CREATE TABLE kpis (
    key TEXT PRIMARY KEY, value REAL, unit TEXT, label TEXT
);
CREATE TABLE opportunities (
    id TEXT PRIMARY KEY, rank INTEGER, title TEXT,
    worker_seconds INTEGER,     -- waiting time attributed to this cause (the causes do not overlap)
    share_of_waiting REAL,
    what TEXT, action TEXT,
    event_kinds TEXT            -- JSON list of insight kinds that are the evidence
);
CREATE TABLE allocation (
    kind TEXT,                  -- release: more people than the line could use | need: short of people with a loaded belt
    t_start_s INTEGER, t_end_s INTEGER,
    people REAL                 -- average number spare (release) or short (need) over the window
);
"""


def connect(db_path: Path | str = DEFAULT_DB, read_only: bool = False) -> sqlite3.Connection:
    db_path = Path(db_path)
    if read_only:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_raw(con: sqlite3.Connection, reset: bool = False) -> None:
    if reset:
        for t in ("video", "detections", "frame_grid"):
            con.execute(f"DROP TABLE IF EXISTS {t}")
    con.executescript(RAW_SCHEMA)
    con.commit()


def reset_derived(con: sqlite3.Connection) -> None:
    for t in DERIVED_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.executescript(DERIVED_SCHEMA)
    con.commit()
