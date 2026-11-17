"""Stage 1: video -> raw detections. The only stage that needs the video and the GPU/CPU time.

Off-the-shelf Ultralytics YOLO pose model + ByteTrack. For every sampled frame we store each
person's box, track id and 17 COCO keypoints. Once a second we also keep a tiny colour thumbnail of
the frame, which the analytics stage turns into belt occupancy for whatever belt zone is drawn.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import store

GRID_COLS, GRID_ROWS = 96, 54


def pick_device(requested: str) -> str:
    if requested != "auto":
        return requested
    import torch
    if torch.cuda.is_available():
        return "0"
    # Ultralytics warns about a pose-keypoint bug on Apple MPS, so default to CPU on Macs.
    return "cpu"


def run(video_path: Path, db_path: Path, model_name: str = "yolo11s-pose.pt", sample_fps: float = 10.0,
        device: str = "auto", conf: float = 0.25, imgsz: int = 960, tracker: str = "bytetrack.yaml",
        max_seconds: float | None = None, source: str = "") -> None:
    import cv2
    from ultralytics import YOLO

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    stride = max(1, round(fps / sample_fps))
    device = pick_device(device)

    con = store.connect(db_path)
    store.init_raw(con, reset=True)
    con.execute(
        "INSERT INTO video (id, source, path, width, height, fps, duration_s, frame_count, sample_fps,"
        " model, tracker, processed_at, synthetic) VALUES (1,?,?,?,?,?,?,?,?,?,?,?,0)",
        (source, str(video_path), width, height, fps, n_frames / fps, n_frames, fps / stride,
         model_name, tracker, datetime.now(timezone.utc).isoformat(timespec="seconds")))

    model = YOLO(model_name)
    print(f"{video_path.name}: {width}x{height} @ {fps:.1f}fps, {n_frames / fps:.0f}s. "
          f"Sampling every {stride} frames (~{fps / stride:.1f}fps) on device={device}")

    results = model.track(source=str(video_path), stream=True, vid_stride=stride, persist=True,
                          tracker=tracker, conf=conf, imgsz=imgsz, classes=[0], device=device, verbose=False)
    t0, n_det, last_grid_s = time.time(), 0, -1
    for i, r in enumerate(results):
        frame_idx = i * stride
        t_ms = int(round(frame_idx / fps * 1000))
        if max_seconds and t_ms > max_seconds * 1000:
            break

        # One thumbnail per second: mean colour of each grid cell (BGR).
        if t_ms // 1000 != last_grid_s:
            last_grid_s = t_ms // 1000
            thumb = cv2.resize(r.orig_img, (GRID_COLS, GRID_ROWS), interpolation=cv2.INTER_AREA)
            con.execute("INSERT INTO frame_grid VALUES (?,?,?,?,?)",
                        (frame_idx, t_ms, GRID_COLS, GRID_ROWS, thumb.tobytes()))

        if r.boxes is not None and r.boxes.id is not None:
            ids = r.boxes.id.int().tolist()
            boxes = r.boxes.xyxyn.tolist()
            confs = r.boxes.conf.tolist()
            kxy = r.keypoints.xyn.tolist() if r.keypoints is not None else []
            kcf = r.keypoints.conf.tolist() if r.keypoints is not None and r.keypoints.conf is not None else []
            for j, tid in enumerate(ids):
                kp = []
                if j < len(kxy):
                    kp = [[round(x, 4), round(y, 4), round(kcf[j][k], 2) if kcf else 1.0]
                          for k, (x, y) in enumerate(kxy[j])]
                x1, y1, x2, y2 = boxes[j]
                con.execute("INSERT OR REPLACE INTO detections VALUES (?,?,?,?,?,?,?,?,?)",
                            (frame_idx, t_ms, tid, x1, y1, x2, y2, confs[j], json.dumps(kp)))
                n_det += 1
        if i % 100 == 0:
            con.commit()
            print(f"  {t_ms / 1000:6.1f}s  detections so far: {n_det}  ({time.time() - t0:.0f}s elapsed)")
    con.commit()
    con.close()
    print(f"Done: {n_det} detections -> {db_path}")
