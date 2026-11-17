---
name: unloading-intel
description: Answer operational questions about a processed unloading-bay video (worker utilisation, conveyor belt utilisation, staffing, bottlenecks) by querying the local analytics store. Use when asked things like "when was the conveyor most underutilised", "how many workers were unloading during the busiest period", "show periods where three people were present but one was working", or "what are the biggest opportunities to improve unloading efficiency".
---

# Unloading intelligence

A video of an unloading operation has already been processed into a SQLite store (person tracks,
poses, zones, per-second activity, belt signals, insights). You answer questions about it by
running `scripts/query.py`. Never guess numbers and never reprocess video: query, then reason.

## How to answer

1. Run `python scripts/query.py overview` first. It returns the clip length, KPIs, zones, the
   precomputed insights and a `notes` list. Read the notes: if the data is flagged **synthetic**,
   say so at the top of your answer.
2. Pick the command that matches the question (table below) and run it. Combine commands when a
   question has two parts (e.g. find the busiest window with `belt --mode busy`, then inspect it
   with `window`).
3. Answer in this shape, written for an operations manager, not an engineer:
   - **The answer** in one or two sentences, with the number.
   - **Evidence**: the time ranges as `m:ss to m:ss`, each with its `video_link` so it can be watched.
   - **Why it matters / what to try**, only where the data supports it.
   - **Confidence**: one line on what could make this wrong (see `references/method.md`).
4. Quote times and figures exactly as returned. If the store cannot answer the question (e.g.
   parcel counts, anything outside the camera view), say what is missing and what would be needed.

## Commands

| Question | Command |
|---|---|
| What happened overall? Biggest opportunities? | `overview` (its `opportunities` list is already ranked), then `insights` for evidence |
| When was the conveyor most underutilised? | `belt --mode idle --window 30 --top 3` (ranked by `avg_belt_occupancy`) |
| Where was the bottleneck? | `insights --kind belt_stopped`, then `insights --kind belt_starved` |
| What does good look like? | `insights --kind full_flow` |
| Does an extra person help? | `insights --kind staffing_curve` |
| When was the busiest period, and how many were working? | `belt --mode busy --window 30 --top 1` (read `avg_handling`, `max_handling`) |
| Periods with N present but only M working | `periods --min-present 3 --max-handling 1 --min-seconds 5` |
| What happened between two times? | `window --from 60 --to 90` (seconds) |
| Who did what? (use with care, see notes) | `workers` |
| What did the manager decide on review? Which events were confirmed, rejected or need action? | `reviews --file <events file exported from the web app>` |
| Anything else | `sql "SELECT ..."` using `references/schema.md` |

All commands print JSON. Times are seconds from the start of the clip, with `start`/`end` as
`m:ss`. `video_link` opens the web app at that moment; `insight_link` opens a specific insight.

## Rules

- "Working" in a question maps to the `handling` state. `moving` is in transit; `waiting` is idle.
- Prefer crew-level statements ("two of three were handling") over naming individuals. Track ids
  are not reliable identities, and the customer's question is about the operation, not a person.
- Belt figures are estimates: hand-to-belt contacts are a proxy for items handled, and
  `belt_occupancy` is the share of the visible belt area covered. Neither is a parcel count.
- Name the bottleneck by line state. Belt standing still with freight on it: the whole line is down.
  Belt empty and running with people waiting: the constraint is upstream of the crew in view (often
  outside the camera). Belt loaded and moving with the crew busy: the line is at full flow.
- Do not build claims about pace on belt contacts alone; hands resting on the belt are counted.
- Review calls and notes belong to the operations manager. Quote notes as theirs, word for word. Treat
  "Not what happened" as evidence against the rule that raised the event, and say so when you report
  that rule's findings. If no events file has been exported yet, say how to get one (web app, Export data).
- For "biggest opportunities", keep the order of the `opportunities` list: it is ranked by the crew
  time spent waiting behind each cause. Give at most three, each with evidence. Say "crew time", not
  "worker-seconds".
- A period counts as a belt stop only where `belt_stopped_seconds` is above zero. A near-empty belt
  with people waiting is "belt empty", not a stop.

The store is opened read-only. Set `UNLOADING_DB` to point at a different store, and
`UNLOADING_APP_URL` if the web app is not on `http://localhost:5173`.
