import type { Dataset, Frame, Insight, Meta, Rule, Second } from "./types";

const get = async <T,>(name: string): Promise<T> => {
  const r = await fetch(`${import.meta.env.BASE_URL}data/${name}`);
  if (!r.ok) throw new Error(`Could not load ${name}`);
  return r.json();
};

export async function loadDataset(): Promise<Dataset> {
  const [meta, timeline, insights, zones, frames, opportunities, rules, allocation] = await Promise.all([
    get<Dataset["meta"]>("meta.json"), get<Dataset["timeline"]>("timeline.json"),
    get<Dataset["insights"]>("insights.json"), get<Dataset["zones"]>("zones.json"),
    get<Dataset["frames"]>("frames.json"),
    get<Dataset["opportunities"]>("opportunities.json").catch(() => []),
    get<Dataset["rules"]>("rules.json").catch(() => []),
    get<Dataset["allocation"]>("allocation.json").catch(() => []),
  ]);
  return { meta, timeline, insights, zones, frames, opportunities, rules, allocation };
}

/** Latest sampled frame at or before t (seconds); null if the nearest one is stale. */
export function frameAt(frames: Frame[], t: number): Frame | null {
  const ms = t * 1000;
  let lo = 0, hi = frames.length - 1, best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (frames[mid][0] <= ms) { best = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return best >= 0 && ms - frames[best][0] < 400 ? frames[best] : null;
}

export const mmss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

export const duration = (s: number) => {
  const m = Math.floor(s / 60), r = Math.round(s % 60);
  return m ? `${m} min ${r} s` : `${r} s`;
};

export const STATE_LABEL = { handling: "Handling freight", moving: "Moving", waiting: "Waiting" } as const;
// Chart colours follow the design system: ink is work being done, grey is neutral,
// yellow is time worth looking at, red is belt downtime.
export const STATE_COLOR = { handling: "#0b0b0c", moving: "#8b8b90", waiting: "#f5c400" } as const;
// On the video the same states have to stand out against a busy picture: white, dashed white, yellow.
export const OVERLAY_COLOR = { handling: "#ffffff", moving: "#ffffff", waiting: "#f5c400" } as const;

/** Line states. Stopped is a status (always labelled); the other two are neutral. */
export const LINE_COLOR = { flowing: "#0b0b0c", stopped: "#c2332f", empty: "#d9d9dc" } as const;

/** Everyone's time added together: three people waiting for a minute is 3 minutes of crew time. */
export const workerMinutes = (ws: number) => `${Math.round(ws / 60)} min of crew time`;

/**
 * Belt stops as [start, end] seconds, inclusive. Same test as the pipeline (config/analytics.json):
 * freight on the belt not moving for 20 seconds or more, bridging gaps of up to 5 seconds, and the
 * belt more than 10% covered at some point in the pause.
 */
export function beltStops(timeline: Second[], motion = 5, minS = 20, mergeS = 5, emptyCover = 0.1): [number, number][] {
  const out: [number, number][] = [];
  let start = -1, last = -1;
  timeline.forEach((s, t) => {
    if (s.belt_motion == null || s.belt_motion >= motion) return;
    if (start < 0) start = t;
    else if (t - last > mergeS + 1) { out.push([start, last]); start = t; }
    last = t;
  });
  if (start >= 0) out.push([start, last]);
  // A pause on a belt that stayed empty throughout is "belt empty", not a stop: nothing moves in the picture either way.
  return out.filter(([a, b]) => b - a + 1 >= minS && timeline.slice(a, b + 1).some((s) => (s.belt_occupancy ?? 0) > emptyCover));
}

// ---- export: what is on screen, as files a planner or analyst can open in a spreadsheet ----
const cell = (v: unknown) => {
  const t = v == null ? "" : String(v);
  return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
};
const csv = (rows: unknown[][]) => rows.map((r) => r.map(cell).join(",")).join("\n") + "\n";

export function timelineCsv(timeline: Second[]): string {
  const stopped = new Set(beltStops(timeline).flatMap(([a, b]) => Array.from({ length: b - a + 1 }, (_, i) => a + i)));
  return csv([
    ["time", "second", "people_in_view", "handling_freight", "moving", "waiting", "belt_covered_pct", "belt_stopped"],
    ...timeline.map((s, t) => [mmss(s.t_s), s.t_s, s.present, s.handling, s.moving, s.waiting,
      s.belt_occupancy == null ? "" : Math.round(s.belt_occupancy * 100), stopped.has(t) ? 1 : 0]),
  ]);
}

export function eventsCsv(insights: Insight[], rules: Rule[], reviews: Record<string, string> = {}, notes: Record<string, string> = {}): string {
  const rule = (kind: string) => rules.find((r) => r.kind === kind)?.name ?? kind;
  return csv([
    ["from", "to", "seconds", "rule", "severity", "event", "your_call", "your_note", "what_happened", "why_it_matters", "suggested_action"],
    ...[...insights].sort((a, b) => a.t_start_s - b.t_start_s).map((i) => [mmss(i.t_start_s), mmss(i.t_end_s),
      i.t_end_s - i.t_start_s + 1, rule(i.kind), i.severity, i.title, reviews[i.id] ?? "", notes[i.id] ?? "", i.what, i.so_what, i.recommendation]),
  ]);
}

export function figuresCsv(meta: Meta): string {
  return csv([["figure", "value", "unit"], ...Object.values(meta.kpis).map((k) => [k.label, Number(k.value.toFixed(3)), k.unit])]);
}

export function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob(["\ufeff", text], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
