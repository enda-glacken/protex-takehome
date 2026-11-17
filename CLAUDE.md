# Unloading Efficiency Intelligence (Protex AI FDE take-home)

Prototype that turns one video of a truck-unloading operation into operational intelligence for an
operations manager. The brief is `Protex AI_ FDE Take-Home Exercise_ Unloading Efficiency Intelligence.docx`;
brief coverage is `docs/BRIEF_CHECKLIST.md`, decisions and trade-offs are in `docs/DECISIONS.md`, and the
visual rules are in `docs/DESIGN_SYSTEM.md`. Read the brief and `DECISIONS.md` before starting work, and
log any new decision or trade-off in `DECISIONS.md` as you make it.

## The scene
One fixed camera sees almost the whole conveyor and the crew taking freight OFF it (top-left). Freight is
fed on from outside the frame (bottom-right), so the unloaders and the truck are not visible. The clip is
28.5 minutes, 1080p, 20 fps.

## Layout
- `pipeline/unloading/` Python package, one module per stage:
  `detect.py` (video -> raw detections, the only slow stage) -> `analytics.py` (zones + activity states +
  timeline) -> `insights.py` (KPIs + insights) -> `export.py` (JSON for the web app). `synth.py` seeds fake raw
  data. `store.py` owns the SQLite schema. `cli.py` is the entry point.
- `config/zones.json` zone polygons (normalised 0..1). `config/analytics.json` every threshold.
  `config/site.json` customer and site context (mock customer; also sets belt wording).
- `data/processed/unloading.db` the store. Raw tables are written once; derived tables are rebuilt.
- `web/` Vite + React + TypeScript app. No backend: it reads `web/public/data/*.json`.
- `skill/unloading-intel/` Claude skill: `SKILL.md` + `scripts/query.py` (read-only, stdlib only).
- `tests/` unit tests and a synthetic end-to-end check. `evals/` hand-label agreement and skill ground truth.

## Commands
`./run.sh demo` (synthetic data), `./run.sh quick` (first 20s of real video), `./run.sh pipeline` (full run),
`./run.sh analytics` (after zone/threshold changes), `./run.sh web`, `./run.sh test`, `./run.sh eval`,
`./run.sh skill-link`. See `./run.sh help`. Run `./run.sh test` after any change to the pipeline.

## Rules for this repo
- Keep the stage boundaries. Zones and thresholds are applied in analytics, never in detect, so that
  changing them does not need the video again.
- Analytics, insights, export and the skill stay on the Python standard library (Python 3.9 compatible).
- All coordinates are normalised 0..1. Times are seconds (`t_s`) or milliseconds (`t_ms`) from clip start.
- The audience for the UI and for insight text is an operations manager. Plain language, the number, the
  time range, why it matters, what to try. No debugging vocabulary in the UI.
- Never present synthetic data as real results. Hedge claims the model cannot verify ("appeared to").
- State colours are fixed (see `docs/DESIGN_SYSTEM.md`): handling #0b0b0c, moving #8b8b90, waiting #f5c400,
  belt downtime #c2332f. One y-axis per chart.
- If the schema changes, update `skill/unloading-intel/references/schema.md` and `web/src/lib/types.ts`.
- Nothing is reported per person: tracker ids are not stable identities.
- Prefer tuning thresholds and insight wording over new features.
