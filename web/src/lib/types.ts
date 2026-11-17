// Shapes of the JSON files written by `pipeline/unloading/export.py`.

export type State = "handling" | "moving" | "waiting";

export interface Kpi { key: string; value: number; unit: string; label: string }

export interface Meta {
  video: {
    source: string; width: number; height: number; fps: number; duration_s: number;
    sample_fps: number; model: string; processed_at: string; synthetic: number;
  };
  site: { customer?: string; logo?: string; site?: string; camera?: string; belt_action?: string };
  kpis: Record<string, Kpi>;
}

export interface Second {
  t_s: number; present: number; handling: number; moving: number; waiting: number;
  belt_touches: number; belt_occupancy: number | null; belt_motion?: number | null;
}

export interface Insight {
  id: string; kind: string; severity: "high" | "medium" | "info";
  t_start_s: number; t_end_s: number;
  title: string; what: string; so_what: string; recommendation: string;
  evidence: Record<string, unknown>;
}

export interface Zone { id: string; name: string; kind: string; polygon: [number, number][] }

/** [label, state, x1, y1, x2, y2, keypoints[[x, y, conf] * 17]] in normalised coordinates */
export type Detection = [string, State, number, number, number, number, [number, number, number][]];
export type Frame = [number, Detection[]]; // [t_ms, detections]

export interface Opportunity {
  id: string; rank: number; title: string; worker_seconds: number; share_of_waiting: number;
  what: string; action: string; event_kinds: string[];
}

export interface AllocationWindow { kind: "release" | "need"; t_start_s: number; t_end_s: number; people: number }

export interface Rule { kind: string; name: string; scope: "event" | "clip"; definition: string; events: number; alert_after_s?: number }

export interface Dataset {
  meta: Meta; timeline: Second[]; insights: Insight[]; zones: Zone[]; frames: Frame[];
  opportunities: Opportunity[]; rules: Rule[]; allocation: AllocationWindow[];
}
