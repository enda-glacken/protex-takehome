# Unloading Efficiency Intelligence

A prototype that turns one fixed-camera video of a conveyor unloading line into answers an operations
manager can act on: how much of the crew's time goes to handling freight, when the belt was stopped
or running empty, and whether an extra person actually adds people working.

Built for the Protex AI Forward Deployed Engineer take-home. The customer name and logo in the app
("Brackenway Express") are a fictional placeholder.

> **Status: working prototype.** The full 28.5-minute reference video has been processed at 10 frames a
> second. The app, the analytics, the evals and the Claude skill all run on that data, and the results
> below come from that run.

## The scene

One camera sees nearly the whole belt and the crew taking freight off it. Freight is fed onto the belt
from outside the frame, so the people unloading the truck are not visible.

## What the customer asked, and what I chose to measure

The customer has a fixed number of workers spread over several unloading operations and wants to know
how well they are used, where the bottlenecks are and how to improve.

| Question | Measure | Why this one |
|---|---|---|
| Where is the constraint? | **Line state**: belt standing still with freight on it (stopped), belt empty with people waiting (starved), or loaded and moving (full flow) | Each calls for a different move. Stopped: the whole line is down, so find the cause. Starved: the constraint is upstream, so adding people here does nothing. Full flow: the benchmark for crew size. |
| Is the crew the right size for the work? | Share of worker time handling freight; episodes where several are present and few are handling | Waiting worker-seconds are labour that could be on another line. |
| Does adding a person add work done? | Average number of people handling freight at each crew size | The actual allocation decision. One clip can only suggest it; it is a test to run. |

Hand-to-belt contacts are counted but no insight rests on them: watching the clip showed that hands
resting on the belt are counted too, so they are not a reliable measure of pace.

## Results on the reference clip

28.5 minutes from one camera, analysed at 10 frames a second.

| Finding | Evidence |
|---|---|
| **The belt stood still with freight on it for 17% of the clip.** 5 stops, 4 min 58 s in total. | 8:51 to 10:37, 12:27 to 12:48, 14:59 to 15:31, 18:47 to 20:19, 25:52 to 26:34. All five watched. One had a visible cause: a question over a label, and the belt was stopped to avoid a pile-up. |
| **About two people were working whatever the crew size.** On average 2.0 people were handling freight with 5, 6 and 7 present. | Consistent with two people scanning at the belt end, seen in the video. Extra people waited. |
| **People spent 52% of their time waiting** and 36% handling freight (1.7 of 4.7 in view, on average). | Waiting by cause: 64% while freight was moving past them, 20% while the belt stood still, 16% at an empty, running belt. |
| **Crew size ran opposite to the workload.** | From 4:00, 6.7 people in view with the belt 9% covered. From 26:00, 3.6 people with it 38% covered. |

**What I would tell the customer:** open a second pick-off position so more of the crew can reach freight (about
four people stood at the sort end and about 1.5 were handling at a time; cutting the crew to five would free only
about one person for under five minutes); find out who stops the belt and why, starting with the stop at 8:51; and
share scan data for the same half hour so throughput can be checked.

**How far to trust it.** I labelled 10 moments by hand, one every three minutes, before looking at the system's
answer (`./run.sh eval`, labels in `evals/activity_labels.csv`).

| | Exact match | Within one person | Average error | Direction of error |
|---|---|---|---|---|
| People present | 4 of 10 | 9 of 10 | 0.7 | System never counted more than I did; it misses people at the edges of the frame |
| People handling | 4 of 10 | 9 of 10 | 0.7 | System lower in 5, higher in 1 |

At those moments I counted 17 handling out of 54 present (31%); the system counted 12 out of 47 (26%). So the
system undercounts both people and work, but the conclusion holds on my labels as well as its own: roughly a third
of the crew was handling freight at any moment. My labels also show no more people working at larger crew sizes
(1.75 handling on average with 6 or 7 present, 1.67 with 4 or 5). Ten moments is a small sample; a real deployment
would need a few hundred, labelled by someone who knows the operation.

Known weak spots: work done away from the belt can be labelled waiting, and people partly in frame are dropped.
A stop on a belt with nothing on it cannot be seen.

**What watching every detected stop changed.** The first version reported 8 belt stops (21% of the clip). I watched
all eight. Five were real. Three, all in the first five minutes, were an empty belt that was running while the crew
waited for the next cart: on an empty belt nothing moves in the picture whether it runs or not. The rule now needs
freight on the belt at some point in the pause, and those three periods are reported as what they were, belt empty
with the crew waiting. The figures above are from the corrected rule.

**Do the findings survive different thresholds?** `python evals/sensitivity.py` re-runs the analysis 11 times on
the stored detections, moving one threshold at a time (no video reprocessing; about 35 seconds in total).

| What was moved | Belt stops | Belt downtime | Crew waiting | People handling with 5 / 6 / 7 present |
|---|---|---|---|---|
| Nothing (as shipped) | 5 | 17% | 52% | 2.0 / 2.0 / 2.0 |
| Belt-stop motion test, stricter to looser | 5 | 17% to 18% | 52% | unchanged |
| Belt-stop minimum length, 15 s to 30 s | 7 to 4 | 19% to 16% | 52% | unchanged |
| Arm-speed thresholds for handling, 20% lower to 20% higher | 5 | 17% | 46% to 57% | 2.4 / 2.4 / 2.5 to 1.8 / 1.7 / 1.7 |
| Hands-at-belt share and body-speed thresholds, each moved 20% | 5 | 17% | 49% to 54% | 1.9 to 2.2 |

What holds in every variant: the number of people handling freight with 6 or 7 present stays within 0.1 of the
number with 5, and the top action is the same. What moves: the number of belt stops depends on how long a pause
must last to count (4 to 7), and the waiting share moves by about five points either way with the handling
thresholds. So "about half the crew's time is waiting" and "the belt is down for about a sixth of the time" are
the right level of precision, not 52% and 17%.

## Quick start

Requires Python 3.9+ and Node 20+. `ffmpeg` is optional (used to make a fast-seeking copy for the app).

```bash
./run.sh setup                          # .venv with the CV dependencies, npm install for the web app
./run.sh video raw/videoplayback.mp4    # point the project at your copy of the reference video
./run.sh pipeline                       # detect -> analytics -> export   (./run.sh quick = first 20s)
./run.sh web                            # http://localhost:5173
```

No video yet? `./run.sh demo && ./run.sh web` runs the whole app on synthetic data (clearly bannered).

After drawing zones in the app (Edit zones, then Download zones.json) save the file to
`config/zones.json` and run `./run.sh analytics`. That takes seconds: it never touches the video.

`./run.sh test` runs the unit tests and a synthetic end-to-end check. `./run.sh eval` scores the
activity labels against hand labels and prints ground truth for the skill questions (see `evals/`).

### The Claude skill

```bash
./run.sh skill-link   # exposes skill/unloading-intel to Claude Code in this repo
```

Then ask Claude Code, for example, "when was the conveyor most underutilised?". After reviewing events in the app, export them
(Export data, "Events, with your calls and notes") and ask "what did the manager decide?"; the skill reads the
file with `reviews --file`. For claude.ai,
`./run.sh skill-package` builds `dist/unloading-intel.zip` with the current store bundled.

## Architecture

```
 video.mp4
    │
    ▼
┌──────────┐   raw tables: detections (box, track id, 17 keypoints), frame_grid (thumbnail per second)
│ detect   │   YOLO pose + ByteTrack. Slow, run once.
└────┬─────┘
     ▼
┌──────────────────────────── SQLite: data/processed/unloading.db ────────────────────────────┐
     ▼                                              ▲                            ▲
┌──────────┐ + config/zones.json             ┌───────────┐                ┌──────────────┐
│ analytics│ + config/analytics.json         │ insights  │ + site.json    │ Claude skill │
│          │ worker_seconds, timeline,       │ kpis,     │                │ query.py     │
└──────────┘ belt_events, workers            │ insights  │                │ (read-only)  │
                                             └─────┬─────┘                └──────────────┘
                                                   ▼
                                             ┌───────────┐  static JSON   ┌──────────────┐
                                             │ export    │ ─────────────▶ │ React app    │
                                             └───────────┘                └──────────────┘
```

| Module | Path | Depends on |
|---|---|---|
| CV processing | `pipeline/unloading/detect.py` | ultralytics, OpenCV |
| Storage | `pipeline/unloading/store.py` | sqlite3 |
| Analytics and insights | `pipeline/unloading/analytics.py`, `insights.py` | standard library |
| Web app | `web/` | React, Vite. No chart library, no backend |
| Claude skill | `skill/unloading-intel/` | standard library |
| Tests and evals | `tests/`, `evals/` | standard library |

### Decisions

The full log, with alternatives and trade-offs, is in `docs/DECISIONS.md`. The main ones:

- **Raw and derived data are separate layers in one SQLite file.** Detection is the expensive step,
  so it stores only what the model saw. Zones and thresholds are applied afterwards, which means a
  zone can be redrawn and the numbers recomputed in seconds, and a new use case is a new analytics
  module over the same detections.
- **An explainable rule-based activity model.** A worker-second is `handling`, `moving` or `waiting`
  from three signals: wrist at the belt zone, arm motion relative to the torso, body displacement.
  Every label can be explained to a customer and every threshold is in one config file.
- **Belt occupancy from belt colour.** The belt is a uniform colour and almost fully visible, so the
  share of belt cells that are not belt-coloured is a direct estimate of how loaded it is. Background
  subtraction was rejected because a stopped, jammed belt would be learned as background and read as empty.
- **Crew-level over per-person metrics.** Tracker ids break under occlusion, so per-second crew
  counts are far more reliable than per-person totals. It is also the right framing: the question is
  about the operation, not about monitoring individuals. The app can blur the video.
- **Static JSON to the front end.** Enough for a single-clip prototype. The step to a live product is
  a thin API over the same tables.
- **The skill is a harness, not a prompt.** `query.py` returns JSON with timestamps and deep links
  into the app (`?t=83`, `?insight=belt-starved-1`), opens the store read-only, and `SKILL.md` tells
  Claude how to turn that into an answer with evidence and stated confidence.

## Assumptions

- A wrist over the belt zone is a reasonable proxy for handling an item at the belt.
- People in view are part of this line's crew.
- Belt colour and lighting are stable across the clip.
- The crew in view takes freight off the belt; freight is fed on from outside the frame.
- The 28.5 minutes are continuous and no one in view belongs to a different operation.

## Limitations

- **The unloading end is out of frame.** The system reports on the crew it can see and on the freight
  arriving; it cannot say how many people are feeding the belt or how full the trailer is.
- **No parcel detection, so no true throughput.** Occupancy is area covered, not an item count, and
  under-counts freight close to the belt's own colour. The customer's scan data is the right source.
- **Belt stops need freight on the belt to be seen.** A stop on an empty belt is invisible, and an empty running
  belt was at first mistaken for a stop (see Results). All five stops now reported have been watched.
- **Work away from the belt may read as waiting**, for example someone sorting into a cart.
- **2D only.** A hand above the belt and a hand on it look the same.
- **Track ids are unstable** (38 ids for about 5 people in a 90-second sample), so nothing is reported per person.
- **Thresholds are tuned by eye on one clip.** Agreement has been checked on only 10 hand-labelled moments (see Results).
- **One line, one half hour.** Extrapolating to a shift, or to the cross-line allocation question, is a
  hypothesis to test, not a finding.


## Proposed pilot

One half hour of one line raises three questions it cannot settle. A two-week pilot would:

- **Connect three cameras:** this line, one more line, and the unloading end that feeds the belt. Take the
  customer's scan data for the same period.
- **Test a second pick-off position.** Run alternate days with and without it. Measure people handling at once
  (camera) and parcels per person-hour (scan data). This is the test of the top action.
- **Find out why the belt stops.** Supervisors record the reason for each stop in the review panel. Measure
  downtime per shift by cause.
- **Measure real redeployment.** Count the minutes when one line has a person to spare while another is short.
- **Check accuracy first.** A supervisor labels a few hundred moments before any figure is used for a decision.

Success criteria are for the customer to set before it starts: for example, the lift in parcels per person-hour
that would justify a second position, and the share of belt downtime that must have a named cause and owner.

## Extending it

- **More cameras or lines:** add a `video_id` column to the raw tables. A per-line state over time is
  the building block for the cross-line view the customer ultimately wants.
- **New use cases:** dwell time in a zone, congestion at the belt end, ergonomic risk from pose are
  each a new function over the existing `detections` or `worker_seconds` tables.
- **Live operation:** run `detect` on a stream, append to the raw tables, recompute the derived tables
  on a rolling window, and turn insights into alerts for the shift supervisor.
- **Per-site setup:** zones, thresholds and site context are three config files.
