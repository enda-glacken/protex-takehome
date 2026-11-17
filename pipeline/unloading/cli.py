"""Command line entry point:  python -m unloading.cli <stage>

    detect    video -> raw detections (slow, needs the video)
    seed      synthetic raw data instead of detect (for building the app before the video is processed)
    analyze   raw detections + zones -> activity, timeline, KPIs, insights (seconds)
    export    store -> JSON for the web app
    refresh   analyze + export
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import store

ROOT = store.ROOT


def main() -> None:
    p = argparse.ArgumentParser(prog="unloading", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=store.DEFAULT_DB)
    p.add_argument("--zones", type=Path, default=ROOT / "config" / "zones.json")
    p.add_argument("--config", type=Path, default=ROOT / "config" / "analytics.json")
    p.add_argument("--site", type=Path, default=ROOT / "config" / "site.json")
    p.add_argument("--web-data", type=Path, default=ROOT / "web" / "public" / "data")
    sub = p.add_subparsers(dest="stage", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--video", type=Path, default=ROOT / "data" / "raw" / "unloading.mp4")
    d.add_argument("--model", default="yolo11s-pose.pt")
    d.add_argument("--sample-fps", type=float, default=10.0)
    d.add_argument("--device", default="auto", help="auto | cpu | mps | 0")
    d.add_argument("--imgsz", type=int, default=960)
    d.add_argument("--conf", type=float, default=0.25)
    d.add_argument("--tracker", default="bytetrack.yaml")
    d.add_argument("--max-seconds", type=float, default=None, help="process only the first N seconds (quick test)")
    d.add_argument("--source", default="https://www.youtube.com/watch?v=-gXqiZHu2UY")
    for name in ("seed", "analyze", "export", "refresh"):
        sub.add_parser(name)
    a = p.parse_args()

    def analyze():
        from . import analytics, insights
        s = analytics.run(a.db, a.zones, a.config)
        n = insights.run(a.db, a.config, a.site)
        print(f"Analysed {s['seconds']}s: {s['tracks']} tracks, {s['belt_events']} belt contacts, "
              f"belt occupancy {'on' if s['belt_index'] else 'off'}, {n} insights")

    def export():
        from . import export as ex
        ex.run(a.db, a.web_data, a.site, a.config)

    if a.stage == "detect":
        from . import detect
        detect.run(a.video, a.db, a.model, a.sample_fps, a.device, a.conf, a.imgsz, a.tracker, a.max_seconds, a.source)
    elif a.stage == "seed":
        from . import synth
        synth.run(a.db, a.zones)
    elif a.stage == "analyze":
        analyze()
    elif a.stage == "export":
        export()
    elif a.stage == "refresh":
        analyze()
        export()


if __name__ == "__main__":
    main()
