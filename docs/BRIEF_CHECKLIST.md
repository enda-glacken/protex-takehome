# Brief coverage

Every instruction in the take-home brief, where it is answered, and how far the answer goes.
A ticked box means it exists and runs on the full 28.5-minute video; the note says what it does not do.

## 1. Computer vision and data

| | Instruction | Where | State |
|---|---|---|---|
| [x] | Off-the-shelf CV models to detect and track people | `pipeline/unloading/detect.py` (YOLO pose + ByteTrack) | Run on the full video: 84,572 detections at 10 frames a second. |
| [x] | Pose estimation to understand worker activity | `analytics.py` (wrists, arm and body motion) | Checked against 10 hand-labelled moments: within one person 9 times in 10. |
| [x] | Detection, tracking and pose data stored locally, queryable without reprocessing | `store.py`, `data/processed/unloading.db` raw tables | Analytics re-run in seconds from the store; `evals/sensitivity.py` does it 11 times. |
| [x] | Drawing configurable zones on the video, especially belt and working areas | Web app "Edit zones", `config/zones.json` | Works. Saving a drawn zone back to config is manual (download, save, `./run.sh analytics`). |
| [x] | Explore how zones, pose and detections identify activity, hands at the belt, belt utilisation or capacity | README "What I chose to measure"; `DECISIONS.md` verification log | Hands at the belt explored and rejected as a pace measure (resting hands are counted). Belt cover and belt motion are used instead. |

## 2. Operational analytics and insights

| | Instruction | Where | State |
|---|---|---|---|
| [x] | Worker utilisation: actively unloading vs waiting or idle | Headline cards, timeline, breakdown | 36% handling, 52% waiting. Work away from the belt can read as waiting. |
| [x] | Belt utilisation: occupancy, throughput or available capacity | Belt downtime, freight on belt | Downtime and cover are measured. Throughput is not: there is no parcel count. |
| [x] | Resource allocation: when underutilised, when more would help | People handling by crew size; people to spare and short; "Across your lines" | Answered for one line. Where spare people should go needs other lines connected. |
| [x] | Bottlenecks: where and when unloading slows | Top actions; belt stop, belt empty and crew events | Three causes, sized by crew time lost. |
| [x] | What you chose to measure and why | README table, `DECISIONS.md` | Written. |
| [x] | Polished React application | `web/` | Runs on the real data. |
| [x] | Video playback with detection, pose and zone overlays | `VideoStage.tsx`, layer toggles | Blur and activity on by default; pose and zones one click away. |
| [x] | Clear metrics, trends and meaningful alerts | Headline cards, timeline, 5-minute blocks, Alerts tab | Trends are within one recording. Alerts are previews of what a live system would send; nothing is sent. |
| [x] | Click an insight or alert to jump to the moment | Top actions, flagged clips, timeline, events, alerts; `?t=` and `?insight=` links | Works. |
| [x] | Explain what happened and why it matters | Review panel beside the video | What happened, why it matters, what to try, plus the manager's own call and note. |
| [x] | Feels like an early customer-facing product, not a debugging interface | Plain wording, mock customer branding, people blurred | Not yet tested with someone who has not seen it. |

## 3. Claude skill

| | Instruction | Where | State |
|---|---|---|---|
| [x] | Reusable Claude skill acting as a harness over the processed data | `skill/unloading-intel/` | Works in Claude Code via `./run.sh skill-link`. |
| [x] | Claude can query the underlying data | `scripts/query.py` commands and read-only SQL | Read-only by construction. |
| [x] | "When was the conveyor most underutilised?" | `belt --mode idle` | Returns ranked windows with timestamps and links; ground truth from `./run.sh eval`. |
| [x] | "How many workers were actively unloading during the busiest period?" | `belt --mode busy` then `window` | Same. |
| [x] | "Periods where three people were present but only one appeared to be working" | `periods --min-present 3 --max-handling 1` | Same. |
| [x] | "Biggest opportunities to improve unloading efficiency?" | `overview`, `insights` | Same. |
| [x] | Answers reference supporting evidence and video timestamps | m:ss ranges and `video_link` in every result | Works. |
| [x] | Beyond the brief: the manager's review calls and notes | `reviews --file <events file exported from the app>` | Reads calls and notes back as labels. Nothing is retrained from them yet. |

## 4. Architecture and code quality

| | Instruction | Where | State |
|---|---|---|---|
| [x] | Video processing, storage, analytics, React app and skill reasonably modular | One module per stage; app and skill touch only the store or its export | The belt-stop rule is repeated once in the web app (see `DECISIONS.md` 24). |
| [x] | High-level architecture and technical decisions | README "Architecture" and "Decisions"; `DECISIONS.md` | Written. |
| [x] | How it extends to additional use cases | README "Extending it" and "Proposed pilot" | Written. The store holds one recording today. |

## Deliverables

| | Deliverable | State |
|---|---|---|
| [x] | Working React prototype using the supplied video | Runs on the full video |
| [x] | CV pipeline with locally persisted data | Full run stored in `data/processed/unloading.db` |
| [x] | At least three meaningful insights supported by video evidence | Belt downtime, crew limited by working positions, belt empty with crew waiting. All five belt stops were checked by eye. |
| [x] | Working Claude skill for querying and reasoning over the data | Works |
| [x] | README: setup, architecture, assumptions, limitations | Current |
| – | 5 to 10 minute Loom run-through | Not in the repo; sent with the submission |
