import { useEffect, useRef, useState } from "react";
import CameraTabs from "./components/CameraTabs";
import EventList, { PatternList } from "./components/EventList";
import ExportData from "./components/ExportData";
import Flagged from "./components/Flagged";
import Lines, { CameraName, ConnectCamera } from "./components/Lines";
import { OverviewBelow, TopActions } from "./components/Overview";
import ReviewPanel from "./components/ReviewPanel";
import RulesPanel from "./components/RulesPanel";
import Timeline from "./components/Timeline";
import VideoStage, { type Layers } from "./components/VideoStage";
import ZonePanel from "./components/ZonePanel";
import { useCameraLabels } from "./lib/cameraLabels";
import { download, duration, eventsCsv, figuresCsv, loadDataset, mmss, timelineCsv } from "./lib/data";
import { OUTCOME_LABEL, reviewQueue, useNotes, useReviews } from "./lib/reviews";
import type { Dataset, Insight, Zone } from "./lib/types";
import { usePlayback } from "./lib/usePlayback";

type Tab = "events" | "patterns" | "rules";

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { loadDataset().then(setData, (e) => setError(String(e.message ?? e))); }, []);

  if (error) {
    return (
      <main className="blank">
        <h1>No processed data yet</h1>
        <p>Run <code>./run.sh demo</code> for seeded demo data, or <code>./run.sh pipeline</code> to process the video, then reload.</p>
        <p className="hint">{error}</p>
      </main>
    );
  }
  if (!data) return <main className="blank"><p>Loading the unloading analysis</p></main>;
  return <Dashboard data={data} />;
}

function Dashboard({ data }: { data: Dataset }) {
  const { meta, timeline, insights, frames, opportunities, rules, allocation } = data;
  const pb = usePlayback(meta.video.duration_s);
  const [tab, setTab] = useState<Tab>("events");
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<string[] | null>(null);
  // People are blurred and labelled by activity by default; skeletons and zones are one click away.
  const [layers, setLayers] = useState<Layers>({ boxes: true, pose: false, zones: false, privacy: true });
  const [zones, setZones] = useState<Zone[]>(data.zones);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<[number, number][]>([]);

  // Deep links: ?t=83 jumps to a moment, ?insight=belt-stopped-1 opens an event. The Claude skill emits these.
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const linked = insights.find((i) => i.id === q.get("insight"));
    if (linked) { setTab(reviewQueue(insights, rules).includes(linked) ? "events" : "patterns"); setSelected(linked.id); pb.seek(linked.t_start_s); }
    else if (q.get("t")) { setTab("events"); pb.seek(Number(q.get("t"))); }
    const wanted = q.get("tab");
    if (wanted === "events" || wanted === "patterns" || wanted === "rules") setTab(wanted);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const select = (i: Insight) => {
    setSelected(i.id);
    pb.seek(Math.max(0, i.t_start_s - 1), true);
  };
  const openEvents = (kinds: string[]) => {
    setFilter(kinds);
    // Open on an event to review when there is one; otherwise on the pattern behind the action.
    const first = queue.find((i) => kinds.includes(i.kind)) ?? insights.find((i) => kinds.includes(i.kind));
    setTab(first && !queue.includes(first) ? "patterns" : "events");
    if (first) { setSelected(first.id); pb.seek(Math.max(0, first.t_start_s - 1)); }
    watch.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const k = (key: string) => meta.kpis[key]?.value ?? 0;
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const toggle = (key: keyof Layers) => setLayers((l) => ({ ...l, [key]: !l[key] }));
  const stopped = meta.kpis.belt_stopped_share?.value ?? 0;
  // The bottleneck in one sentence, when the data shows work levelling off as the crew grows.
  const capped = insights.find((i) => i.kind === "staffing_curve" && i.title.startsWith("About"));

  const watch = useRef<HTMLElement>(null);
  const toVideo = () => watch.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  const camera = meta.site.camera ?? "IP Camera 2";
  const [cam, setCam] = useState(camera);
  const label = useCameraLabels();
  const reviews = useReviews();
  const notes = useNotes();
  const queue = reviewQueue(insights, rules);
  const toReview = queue.filter((i) => !reviews[i.id]).length;
  const current = insights.find((i) => i.id === selected) ?? null;
  const tabFor = (i: Insight): Tab => (queue.includes(i) ? "events" : "patterns");
  const slug = label(camera).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "camera";
  const exports = [
    { label: "Headline figures", note: `${Object.keys(meta.kpis).length} rows`, run: () => download(`${slug}-figures.csv`, figuresCsv(meta)) },
    { label: "Events, with your calls and notes", note: `${insights.length} rows`,
      run: () => download(`${slug}-events.csv`, eventsCsv(insights, rules, Object.fromEntries(Object.entries(reviews).map(([id, o]) => [id, OUTCOME_LABEL[o]])), notes)) },
    { label: "Timeline, second by second", note: `${timeline.length.toLocaleString("en")} rows`, run: () => download(`${slug}-timeline.csv`, timelineCsv(timeline)) },
  ];

  // When this line had people to spare, and when it was short (detail is in "Across your lines").
  const spare = allocation.filter((w) => w.kind === "release"), short = allocation.filter((w) => w.kind === "need");
  const span = (ws: typeof allocation) => ws.reduce((a, w) => a + w.t_end_s - w.t_start_s + 1, 0);
  const headcount = (ws: typeof allocation) => {
    const n = Math.max(1, Math.round(ws.reduce((a, w) => a + w.people, 0) / ws.length));
    return n === 1 ? "1 person" : `${n} people`;
  };

  // Headline numbers for the connected line; shown at the top and inside its card in "Across your lines".
  // Five figures, one per card; the sentences that used to carry them are gone.
  const handlingAvg = k("crew_utilisation") * k("avg_crew");
  const whether = capped?.title.match(/whether (.+) were present/)?.[1];
  const summary = (
    <div className="line-summary">
      <div className="tiles">
        <div className="tile">
          <span className="tile-label">Belt downtime</span>
          <strong>{pct(stopped)}</strong>
          <span className="tile-sub">{Math.round(k("belt_stops"))} stops, {duration(k("belt_stopped_seconds"))} in total</span>
        </div>
        <div className="tile">
          <span className="tile-label">Crew waiting</span>
          <strong>{pct(k("waiting_share"))}</strong>
          <span className="tile-sub">of crew time; may include work away from the belt</span>
        </div>
        <div className="tile">
          <span className="tile-label">People handling freight</span>
          <strong>{Math.round(handlingAvg)} of {Math.round(k("avg_crew"))}</strong>
          <span className="tile-sub">{whether ? `on average, about the same whether ${whether} were present` : "on average"}</span>
        </div>
        {spare.length > 0 && (
          <div className="tile half">
            <span className="tile-label">People to spare</span>
            <strong>{headcount(spare)}</strong>
            <span className="tile-sub">for {duration(span(spare))}</span>
          </div>
        )}
        {short.length > 0 && (
          <div className="tile half">
            <span className="tile-label">Short of people</span>
            <strong>{headcount(short)}</strong>
            <span className="tile-sub">for {duration(span(short))}</span>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <main className="app">
      {meta.video.synthetic === 1 && (
        <p className="banner">Demo data. These figures are generated to exercise the app, not measured from the video.</p>
      )}
      <header className="top">
        {meta.site.logo && <img src={`${import.meta.env.BASE_URL}${meta.site.logo}`} alt={meta.site.customer ?? "Customer"} />}
      </header>
      <CameraTabs connected={camera} selected={cam} onSelect={setCam} />

      {cam !== camera ? (
        <section className="panel not-connected">
          <h1>{label(cam)} is not connected</h1>
          <p>There is no footage from this camera in this prototype. Once it is connected, this page shows its
            downtime, waiting time, events and clips, and it joins the comparison across your lines.</p>
          <ConnectCamera />
          <p><button type="button" className="quiet" onClick={() => setCam(camera)}>Back to {label(camera)}</button></p>
        </section>
      ) : (
        <>
          <div className="page-title">
            <CameraName camera={camera} page />
            <span className="page-actions">
              <span className="pill on">Connected</span>
              <ExportData name={label(camera)} files={exports} />
            </span>
          </div>
          {!editing && (
            <div className="hero-row">
              <section className="panel hero-card">
                <h2>How this line ran</h2>
                {summary}
                <button type="button" className="rename hero-link"
                  onClick={() => document.querySelector(".lines")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
                  Compare across your lines
                </button>
              </section>
              <TopActions opportunities={opportunities} insights={insights} onOpenEvents={openEvents} />
            </div>
          )}

          <div className="columns">
            <section className="watch" ref={watch}>
              <VideoStage videoRef={pb.videoRef} videoEvents={pb.videoEvents} hasVideo={pb.hasVideo} playing={pb.playing}
                onToggle={pb.toggle} aspect={meta.video.width / meta.video.height} time={pb.time} frames={frames}
                zones={zones} layers={editing ? { ...layers, zones: true } : layers} draft={editing ? draft : null}
                onStageClick={editing ? (p) => setDraft((d) => [...d, p]) : undefined} />
              <div className="controls">
                <span className="clock">{mmss(pb.time)}</span>
                <label><input type="checkbox" checked={layers.privacy} onChange={() => toggle("privacy")} />Blur people</label>
                <label><input type="checkbox" checked={layers.boxes} onChange={() => toggle("boxes")} />Activity</label>
                <label><input type="checkbox" checked={layers.pose} onChange={() => toggle("pose")} />Pose</label>
                <label><input type="checkbox" checked={editing || layers.zones} disabled={editing} onChange={() => toggle("zones")} />Zones</label>
                <button type="button" onClick={() => setEditing((e) => !e)}>{editing ? "Close zone editor" : "Edit zones"}</button>
              </div>
            </section>

            <aside className="side">
              {editing ? (
                <ZonePanel zones={zones} draft={draft} onChange={setZones} onDraft={setDraft}
                  onClose={() => { setEditing(false); setDraft([]); }} />
              ) : current ? (
                <ReviewPanel queue={queue} rules={rules} selected={current}
                  onSelect={(i) => { setTab(tabFor(i)); select(i); }} onClose={() => setSelected(null)} />
              ) : (
                <Flagged insights={insights} rules={rules} frames={frames} privacy={layers.privacy}
                  toReview={toReview} total={queue.length}
                  onSelect={(i) => { setTab("events"); setFilter(null); select(i); }}
                  onStart={() => { setTab("events"); setFilter(null); select(queue.find((i) => !reviews[i.id]) ?? queue[0]); }} />
              )}
            </aside>
          </div>

          <Timeline timeline={timeline} insights={insights} time={pb.time} selectedId={selected}
            onSeek={(t) => pb.seek(t)} onSelect={(i) => { setTab(tabFor(i)); select(i); }} />

          {!editing && (
            <section className="panel wide">
              <nav className="tabs" aria-label="Sections">
                <button type="button" className={tab === "events" ? "on" : ""} onClick={() => setTab("events")}>Events {toReview > 0 && <span>{toReview} to review</span>}</button>
                <button type="button" className={tab === "patterns" ? "on" : ""} onClick={() => setTab("patterns")}>Patterns</button>
                <button type="button" className={tab === "rules" ? "on" : ""} onClick={() => setTab("rules")}>Alerts</button>
              </nav>
              {tab === "events" && (
                <EventList insights={insights} rules={rules} selectedId={selected} filter={filter} onFilter={setFilter}
                  onSelect={(i) => { select(i); toVideo(); }} />
              )}
              {tab === "patterns" && (
                <PatternList insights={insights} rules={rules} selectedId={selected} onSelect={(i) => { select(i); toVideo(); }} />
              )}
              {tab === "rules" && (
                <RulesPanel rules={rules} zones={zones} insights={insights} opportunities={opportunities} timeline={timeline} site={label(camera)}
                  onOpenEvents={openEvents} onEditZones={() => { setEditing(true); toVideo(); }} />
              )}
            </section>
          )}

          {!editing && <Lines meta={meta} allocation={allocation} onSeek={(t) => { pb.seek(t, true); toVideo(); }} />}

          {/* Always shown: the breakdown belongs to the line, not to a tab. */}
          {!editing && <OverviewBelow meta={meta} insights={insights} timeline={timeline} onSeek={(t) => { pb.seek(t); toVideo(); }} />}
        </>
      )}
    </main>
  );
}
