# How the numbers are produced, and what can make them wrong

- **Detection and tracking**: off-the-shelf YOLO pose model with ByteTrack, sampled at about 10 frames
  a second. People who are occluded (inside the trailer, behind freight) are not counted while hidden.
- **Track ids are not identities**: when someone leaves view and returns they usually get a new id.
  Crew-level counts per second are robust to this; per-person totals are not.
- **Activity states** (one per worker per second, smoothed over 3 s):
  - `handling`: a wrist is inside the belt zone for a meaningful part of the second and the arm is
    moving (a hand resting on the belt does not count), or the arms are moving quickly relative to the
    torso while the body stays in place.
  - `moving`: the body is travelling.
  - `waiting`: neither.
  A single 2D camera cannot tell a hand above the belt from a hand on it, so "hands at the belt" depends
  on camera angle and on how the belt zone was drawn.
- **Belt contacts**: a debounced count of wrists entering the belt zone. A proxy for items handled at
  the belt (taken off or placed on, depending on the site; see `overview`). It over-counts adjustments
  and under-counts two-handed lifts. It is not a parcel count.
- **Belt occupancy**: share of the belt zone whose colour differs from the empty belt, with people
  masked out, sampled once a second. Freight close to the belt's own colour is under-counted, and it
  measures area covered, not number of items.
- **Belt stopped**: when the freight on the belt does not change from one second to the next for 20
  seconds or more, the belt is taken to be standing still. It needs freight on the belt to tell: a
  pause on a belt that stays under 10% covered throughout is treated as belt empty, not as a stop, so a
  stop on an empty belt is invisible. All five stops in the reference clip were checked against the video.
- **Starved vs full flow**: an empty, running belt with workers waiting means the constraint is upstream
  of the crew in view. A well loaded, moving belt with a busy crew is the line at full flow. Thresholds
  are in `config/analytics.json` (`belt_empty_occupancy`, `belt_full_occupancy`, `belt_stopped_motion`).
- **False people**: tracks with low average detector confidence are dropped (`min_track_conf`); a stack
  of parcels was being detected as a person.
- **What the camera cannot see**: whoever feeds the belt may be outside the frame. Their number and
  activity are unknown; only the freight arriving on the belt is visible.
- **Thresholds** live in `config/analytics.json`; zones in `config/zones.json`. Changing either changes
  the derived tables, not the raw detections.
- **One clip, one camera**: findings describe this clip. Extrapolating to a shift is a hypothesis.
