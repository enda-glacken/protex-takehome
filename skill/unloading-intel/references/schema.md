# Store schema (SQLite)

Coordinates are normalised 0..1. Times: `t_ms` milliseconds, `t_s` whole seconds from clip start.

## Raw layer (from the CV stage)
- `video(source, width, height, fps, duration_s, frame_count, sample_fps, model, tracker, processed_at, synthetic)` one row.
- `detections(frame_idx, t_ms, track_id, x1, y1, x2, y2, conf, keypoints)` one row per person per sampled
  frame. `keypoints` is JSON `[[x, y, conf] * 17]` in COCO order (9 = left wrist, 10 = right wrist).
- `frame_grid(frame_idx, t_ms, cols, rows, px)` one colour thumbnail per second (BLOB), used for belt occupancy.

## Derived layer (rebuilt by analytics; depends on zones and thresholds)
- `zones(id, name, kind, polygon)` kind is `belt | work | staging | other`.
- `worker_seconds(t_s, track_id, zone, state, hands_on_belt, wrist_speed, body_speed)` state is
  `handling | moving | waiting`; `hands_on_belt` is the share of that second with a wrist in a belt zone.
- `timeline(t_s, present, handling, moving, waiting, belt_touches, belt_occupancy, belt_motion)` one row
  per second. This is the table most questions need. `belt_occupancy` is the share (0..1) of the visible
  belt covered by freight. `belt_motion` is how much that freight changed since the previous second:
  below about 5 means it is standing still (belt stopped); NULL means too little freight to tell.
- `belt_events(id, t_ms, track_id, zone)` one row per hand-to-belt contact.
- `workers(track_id, label, first_s, last_s, present_s, handling_s, moving_s, waiting_s, utilisation, belt_touches)`.
- `insights(id, kind, severity, t_start_s, t_end_s, title, what, so_what, recommendation, evidence)`.
- `kpis(key, value, unit, label)`.
- `allocation(kind, t_start_s, t_end_s, people)` windows when this line had more people than it could use
  (`release`) or was short with a loaded belt (`need`). `kpis.crew_level` is the crew size it is measured against.
- `opportunities(id, rank, title, worker_seconds, share_of_waiting, what, action, event_kinds)` waiting time
  split by cause (belt stopped, belt empty, freight available), largest first. The causes do not overlap.

## Example queries
```sql
-- seconds where three or more were present and at most one was handling
SELECT t_s, present, handling FROM timeline WHERE present >= 3 AND handling <= 1;
-- line state per second: starved (belt empty, people waiting) vs backed up (belt loaded)
SELECT t_s, present, waiting, belt_occupancy,
  CASE WHEN belt_motion < 5 THEN 'stopped' WHEN belt_occupancy <= 0.10 THEN 'starved'
       WHEN belt_occupancy >= 0.45 THEN 'full flow' ELSE 'flowing' END state
FROM timeline WHERE present > 0;
-- belt contacts per minute, by crew size
SELECT present, COUNT(*) seconds, ROUND(SUM(belt_touches) * 60.0 / COUNT(*), 1) contacts_per_min
FROM timeline WHERE present > 0 GROUP BY present;
-- where each worker spent their waiting time
SELECT w.label, ws.zone, COUNT(*) seconds FROM worker_seconds ws JOIN workers w USING (track_id)
WHERE ws.state = 'waiting' GROUP BY w.label, ws.zone ORDER BY seconds DESC;
```
