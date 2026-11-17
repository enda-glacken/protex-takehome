import { useState } from "react";
import { useCameraLabels } from "../lib/cameraLabels";
import { beltStops, duration, LINE_COLOR, mmss, STATE_COLOR, workerMinutes } from "../lib/data";
import type { Insight, Meta, Opportunity, Second } from "../lib/types";

const kpi = (meta: Meta, key: string) => meta.kpis[key]?.value ?? 0;
const pct = (v: number) => `${Math.round(v * 100)}%`;

interface SideProps {
  meta: Meta;
  opportunities: Opportunity[];
  insights: Insight[];
  onOpenEvents: (kinds: string[]) => void;
}

/** The three actions, largest first, for the top of the page. Each links to its events. */
export function TopActions({ opportunities, insights, onOpenEvents }: Omit<SideProps, "meta">) {
  const count = (kinds: string[]) => insights.filter((i) => kinds.includes(i.kind)).length;
  return (
    <section className="panel top-actions">
      <h2>Top actions</h2>
      <p className="side-note">Crew time adds everyone's minutes together.</p>
      <ol className="opps compact">
        {opportunities.slice(0, 3).map((o) => (
          <li key={o.id}>
            <h3>{o.title}</h3>
            <p className="opp-size"><b>{workerMinutes(o.worker_seconds)}</b> waiting, {pct(o.share_of_waiting)} of all waiting</p>
            <p className="opp-action">{o.action}</p>
            {count(o.event_kinds) > 0 && (
              <button type="button" className="rename" onClick={() => onOpenEvents(o.event_kinds)}>See the evidence</button>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

interface Segment { label: string; value: number; color: string }

/** One 100% bar. The legend carries every value, so nothing depends on colour or on hovering. */
function ShareBar({ title, note, segments, format }: { title: string; note: string; segments: Segment[]; format: (v: number) => string }) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  return (
    <figure className="sharebar">
      <figcaption><strong>{title}</strong> <span>{note}</span></figcaption>
      <div className="bar" role="img" aria-label={`${title}: ${segments.map((s) => `${s.label} ${Math.round((s.value / total) * 100)}%`).join(", ")}`}>
        {segments.filter((s) => s.value > 0).map((s) => (
          <span key={s.label} style={{ width: `${(s.value / total) * 100}%`, background: s.color }} title={`${s.label}: ${format(s.value)}`} />
        ))}
      </div>
      <ul className="bar-legend">
        {segments.map((s) => (
          <li key={s.label}><i style={{ background: s.color }} /><b>{Math.round((s.value / total) * 100)}%</b> {s.label} <span>{format(s.value)}</span></li>
        ))}
      </ul>
    </figure>
  );
}

interface BelowProps { meta: Meta; insights: Insight[]; timeline: Second[]; onSeek: (t: number) => void }

/** Under the video: the breakdowns behind the three numbers. */
export function OverviewBelow({ meta, insights, timeline, onSeek }: BelowProps) {
  const name = useCameraLabels()(meta.site.camera ?? "IP Camera 2");
  const k = (key: string) => kpi(meta, key);
  const staffed = k("staffed_seconds");
  const stoppedS = k("belt_stopped_seconds");
  const emptyS = Math.round(k("belt_empty_share") * staffed);
  const present = k("waiting_worker_seconds") / (k("waiting_share") || 1);
  const handling = k("crew_utilisation") * present;
  const waiting = k("waiting_worker_seconds");
  const curve = insights.find((i) => i.kind === "staffing_curve")?.evidence.by_crew_size as
    Record<string, { seconds: number; avg_handling: number }> | undefined;
  const maxCrew = curve ? Math.max(...Object.keys(curve).map(Number)) : 0;

  // Belt downtime in 5-minute blocks, from the same stops the headline counts.
  const BLOCK = 300;
  const down = new Set(beltStops(timeline).flatMap(([a, b]) => Array.from({ length: b - a + 1 }, (_, i) => a + i)));
  const blocks = Array.from({ length: Math.ceil(timeline.length / BLOCK) }, (_, b) => {
    const end = Math.min(timeline.length, b * BLOCK + BLOCK);
    let stopped = 0;
    for (let t = b * BLOCK; t < end; t++) if (down.has(t)) stopped++;
    return { start: b * BLOCK, end, stopped, part: end - b * BLOCK < BLOCK };
  });
  const worst = Math.max(1, ...blocks.map((b) => b.stopped));
  const worstBlock = blocks.find((b) => b.stopped === worst && b.stopped > 0);
  const partBlock = blocks.find((b) => b.part);
  const level = meta.kpis.crew_level?.value;
  const flat = curve != null && level != null && maxCrew > level;
  const half = (v: number) => { const r = Math.round(v * 2) / 2; return Number.isInteger(r) ? String(r) : r.toFixed(1); };

  return (
    <div className="below">
      <h2 className="below-title">Breakdown for {name}</h2>
      <section className="panel">
        <h2>Where the time went</h2>
        <ShareBar title="The line" note="what the belt was doing" format={duration}
          segments={[
            { label: "freight moving", value: staffed - stoppedS - emptyS, color: LINE_COLOR.flowing },
            { label: "belt downtime (stopped with freight on it)", value: stoppedS, color: LINE_COLOR.stopped },
            { label: "running empty", value: emptyS, color: LINE_COLOR.empty },
          ]} />
        <ShareBar title="The crew" note="what people in view were doing" format={workerMinutes}
          segments={[
            { label: "handling freight", value: handling, color: STATE_COLOR.handling },
            { label: "moving", value: present - handling - waiting, color: STATE_COLOR.moving },
            { label: "waiting", value: waiting, color: STATE_COLOR.waiting },
          ]} />
        <ShareBar title="Why people were waiting" note="each waiting minute counted once" format={workerMinutes}
          segments={[
            { label: "freight was moving past them", value: k("waiting_ws_freight_available"), color: LINE_COLOR.flowing },
            { label: "the belt was down", value: k("waiting_ws_belt_stopped"), color: LINE_COLOR.stopped },
            { label: "the belt was empty", value: k("waiting_ws_belt_empty"), color: LINE_COLOR.empty },
          ]} />
      </section>

      <div className="col">
        <section className="panel">
          <h2>{worstBlock ? <>Belt downtime was worst between {mmss(worstBlock.start)} and {mmss(worstBlock.end)}</> : <>No belt downtime in this recording</>}</h2>
          <p className="panel-note">Seconds of belt downtime in each 5 minutes. Select a bar to jump there.</p>
          <div className="blocks" role="img" aria-label={blocks.map((b) => `${mmss(b.start)}: ${b.stopped} seconds`).join("; ")}>
            {blocks.map((b) => (
              <button type="button" key={b.start} className={b === worstBlock ? "block worst" : "block"} onClick={() => onSeek(b.start)} title={`From ${mmss(b.start)}: ${b.stopped} s stopped`}>
                <span className="block-v">{b.stopped} s</span>
                <span className="block-bar" style={{ height: `${Math.max(2, (b.stopped / worst) * 96)}px` }} />
                <span className="block-t">{mmss(b.start)}{b.part ? "*" : ""}</span>
              </button>
            ))}
          </div>
          {partBlock && <p className="panel-note small">* The last block is only {duration(partBlock.end - partBlock.start)} long.</p>}
        </section>

        {curve && (
          <section className="panel">
            <h2>{flat ? <>Beyond {level} people, no more were handling freight</> : <>More people present meant more people handling freight</>}</h2>
            <p className="panel-note">Average number of people handling freight at each crew size, with belt downtime left out.</p>
            <div className="crew-rows" role="img"
              aria-label={Object.entries(curve).map(([n, v]) => `${n} present, ${v.avg_handling.toFixed(1)} handling`).join("; ")}>
              {Object.entries(curve).map(([n, v]) => (
                <div className="crew-row" key={n}>
                  <span className="crew-n">With {n} people</span>
                  <span className="crew-track" style={{ width: `${(Number(n) / maxCrew) * 100}%` }} title={`${n} present for ${duration(v.seconds)}`}>
                    <span style={{ width: `${(v.avg_handling / Number(n)) * 100}%` }} />
                  </span>
                  <span className="crew-v"><b>about {half(v.avg_handling)}</b> handling</span>
                  <span className="crew-seen">seen for {duration(v.seconds)}</span>
                </div>
              ))}
            </div>
            <p className="legend-line"><i style={{ background: STATE_COLOR.handling }} />handling freight <i className="track" />people present</p>
          </section>
        )}
      </div>

      <section className="panel limits">
        <h2>Get more insights by adding more data</h2>
        <ul>
          <li><b>Parcels cleared per hour.</b> <More text="Add your scan data" does="Importing scan data" starts="the data import" /> for the same period. It would also check the figures on this page.</li>
          <li><b>The unloading end.</b> <More text="Add a camera" does="Adding cameras" starts="the camera setup" /> where freight is fed onto the belt. The people unloading are outside this view, so they are not counted.</li>
          <li>
            <b>Where spare people could go.</b>{" "}
            <button type="button" className="more-link" onClick={() => document.querySelector(".lines")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Connect your other lines</button>
            {" "}to see which one was short when this one had people to spare.
          </li>
          <li><b>A normal week.</b> <More text="Add more shifts" does="Adding recordings" starts="the upload of more footage" />. This is {duration(meta.video.duration_s)} from one line on one morning.</li>
        </ul>
      </section>
    </div>
  );
}

/** A next step the prototype cannot carry out yet: a real link that says so when selected. */
function More({ text, does, starts }: { text: string; does: string; starts: string }) {
  const [asked, setAsked] = useState(false);
  return (
    <>
      <button type="button" className="more-link" aria-expanded={asked} onClick={() => setAsked((a) => !a)}>{text}</button>
      {asked && <span className="more-note" role="status"> ({does} isn't available in this prototype. In a deployment this starts {starts}.)</span>}
    </>
  );
}
