import { useEffect, useMemo, useRef, useState } from "react";
import { beltStops, duration, mmss } from "../lib/data";
import type { Insight, Second } from "../lib/types";

// Four labelled rows, one idea each: people, freight, belt stops, events.
const TOP = 10, PEOPLE = 104, FREIGHT = 30, STOPS = 12, EVENTS = 14, GAP = 18, AXIS = 26, RIGHT = 12;

interface Props {
  timeline: Second[];
  insights: Insight[];
  time: number;
  selectedId: string | null;
  onSeek: (t: number) => void;
  onSelect: (i: Insight) => void;
}

export default function Timeline({ timeline, insights, time, selectedId, onSeek, onSelect }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrap.current!;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = timeline.length;
  const left = width < 640 ? 96 : 132; // room for the row labels
  const plotW = Math.max(40, width - left - RIGHT);
  const x = (t: number) => left + (t / n) * plotW;
  const hasBelt = timeline.some((s) => s.belt_occupancy != null);

  // Long clips are averaged into 30-second steps: the shape matters here, not each second.
  const step = n > 600 ? 30 : n > 180 ? 10 : 1;
  const steps = useMemo(() => Array.from({ length: Math.ceil(n / step) }, (_, b) => {
    const seg = timeline.slice(b * step, b * step + step);
    const avg = (f: (s: Second) => number) => seg.reduce((a, s) => a + f(s), 0) / seg.length;
    return { t: b * step, end: Math.min(n, b * step + step), present: avg((s) => s.present), handling: avg((s) => s.handling), freight: avg((s) => s.belt_occupancy ?? 0) };
  }), [timeline, n, step]);
  const stops = useMemo(() => beltStops(timeline), [timeline]);

  const peopleMax = Math.max(2, Math.ceil(Math.max(...steps.map((s) => s.present)) / 2) * 2);
  const freightMax = Math.max(0.1, ...steps.map((s) => s.freight));
  const peopleTop = TOP, peopleBase = peopleTop + PEOPLE;
  const freightTop = peopleBase + GAP, freightBase = freightTop + FREIGHT;
  const stopsTop = freightBase + GAP;
  const eventsTop = stopsTop + STOPS + GAP;
  const bottom = eventsTop + EVENTS;
  const height = bottom + AXIS;
  const yPeople = (v: number) => peopleBase - (v / peopleMax) * PEOPLE;

  const area = (value: (s: (typeof steps)[number]) => number, y: (v: number) => number, base: number) => {
    let d = `M${x(0)},${base}`;
    for (const s of steps) d += `L${x(s.t)},${y(value(s))}L${x(s.end)},${y(value(s))}`;
    return `${d}L${x(n)},${base}Z`;
  };
  const inView = area((s) => s.present, yPeople, peopleBase);
  const handling = area((s) => s.handling, yPeople, peopleBase);
  const freight = hasBelt ? area((s) => s.freight, (v) => freightBase - (v / freightMax) * FREIGHT, freightBase) : "";

  const events = insights.filter((i) => i.kind !== "staffing_curve"); // clip-wide findings have no moment to mark
  const yTicks = Array.from({ length: peopleMax / 2 + 1 }, (_, i) => i * 2).filter((v) => peopleMax <= 4 || v % 4 === 0);
  const tickStep = n > 600 ? 120 : n > 240 ? 60 : n > 90 ? 30 : 10;
  const ticks = Array.from({ length: Math.floor(n / tickStep) + 1 }, (_, i) => i * tickStep);
  const secondAt = (clientX: number) => {
    const r = wrap.current!.getBoundingClientRect();
    return Math.max(0, Math.min(n - 1, Math.floor(((clientX - r.left - left) / plotW) * n)));
  };
  const h = hover != null ? steps[Math.min(steps.length - 1, Math.floor(hover / step))] : null;
  const hoverStop = hover != null ? stops.find(([a, b]) => hover >= a && hover <= b) : undefined;
  const rowLabel = (text: string, y: number) => <text className="row-label" x={0} y={y + 4}>{text}</text>;

  return (
    <section className="timeline">
      <div className="legend">
        <h2>Timeline</h2>
        <span className="legend-item"><i className="sw-handling" />Handling freight</span>
        <span className="legend-item"><i className="sw-inview" />In view, not handling</span>
        <span className="legend-hint">Click anywhere to jump the video to that moment</span>
      </div>
      <div className="plot" ref={wrap}>
      <svg width={width} height={height} role="img"
        aria-label="Timeline with four rows: people in view and handling freight, freight on the belt, belt stops, and events"
        onPointerMove={(e) => setHover(secondAt(e.clientX))} onPointerLeave={() => setHover(null)}
        onClick={(e) => onSeek(secondAt(e.clientX))}>
        {/* people */}
        {rowLabel("People", peopleTop + PEOPLE / 2)}
        {yTicks.map((v) => (
          <g key={v}>
            <line className="grid" x1={left} x2={width - RIGHT} y1={yPeople(v)} y2={yPeople(v)} />
            <text className="tick" x={left - 8} y={yPeople(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        <path d={inView} className="area-inview" />
        <path d={handling} className="area-handling" />

        {/* freight on the belt: its own row and scale, never a second axis on the people chart */}
        {rowLabel("Freight on belt", freightTop + FREIGHT / 2)}
        <line className="grid" x1={left} x2={width - RIGHT} y1={freightBase} y2={freightBase} />
        {freight ? <path d={freight} className="area-freight" /> : <text className="tick" x={left} y={freightBase - 8}>No belt reading</text>}

        {/* belt stops */}
        {rowLabel("Belt downtime", stopsTop + STOPS / 2)}
        <rect className="track" x={left} y={stopsTop} width={plotW} height={STOPS} rx={3} />
        {stops.map(([a, b]) => (
          <rect key={a} className="stop" x={x(a)} y={stopsTop} width={Math.max(3, x(b + 1) - x(a))} height={STOPS} rx={3}>
            <title>Belt stopped, {mmss(a)} to {mmss(b)} ({duration(b - a + 1)})</title>
          </rect>
        ))}

        {/* events: one marker each, where the event starts */}
        {rowLabel("Events", eventsTop + EVENTS / 2)}
        <line className="grid" x1={left} x2={width - RIGHT} y1={eventsTop + EVENTS / 2} y2={eventsTop + EVENTS / 2} />
        {events.map((i) => (
          <g key={i.id} className={`event ${i.id === selectedId ? "selected" : ""}`}
            onClick={(e) => { e.stopPropagation(); onSelect(i); }}>
            <title>{i.title}, {mmss(i.t_start_s)} to {mmss(i.t_end_s)}</title>
            <circle className="hit" cx={x(i.t_start_s)} cy={eventsTop + EVENTS / 2} r={12} />
            <circle className="mark" cx={x(i.t_start_s)} cy={eventsTop + EVENTS / 2} r={i.id === selectedId ? 7 : 5.5} />
          </g>
        ))}

        {ticks.map((t) => (
          <text key={t} className="tick" x={x(t)} y={height - 6} textAnchor={t === 0 ? "start" : t >= n - 1 ? "end" : "middle"}>{mmss(t)}</text>
        ))}
        {hover != null && <line className="crosshair" x1={x(hover + 0.5)} x2={x(hover + 0.5)} y1={peopleTop} y2={bottom} />}
        <g className="playhead" transform={`translate(${x(Math.min(time, n))},0)`}>
          <line y1={0} y2={bottom} />
          <path d="M-5,0h10v6l-5,5l-5,-5z" />
        </g>
      </svg>
      {h && hover != null && (
        <div className="tooltip" style={{ left: Math.max(left, Math.min(x(hover) + 12, width - 232)) }}>
          <strong>{mmss(hover)}</strong>
          <div><i className="sw-handling" /><b>{h.handling.toFixed(1)}</b> handling freight</div>
          <div><i className="sw-inview" /><b>{h.present.toFixed(1)}</b> in view</div>
          {step > 1 && <div className="tooltip-note">Average, {mmss(h.t)} to {mmss(h.end)}</div>}
          <div className="tooltip-foot">
            {hoverStop ? <><b>Belt stopped</b> {mmss(hoverStop[0])} to {mmss(hoverStop[1])}</>
              : hasBelt ? <>Belt running, <b>{Math.round((timeline[hover].belt_occupancy ?? 0) * 100)}%</b> covered by freight</>
                : <>No belt reading</>}
          </div>
        </div>
      )}
      </div>
    </section>
  );
}
