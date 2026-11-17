import { useState } from "react";
import type { Zone } from "../lib/types";

interface Props {
  zones: Zone[];
  draft: [number, number][];
  onChange: (zones: Zone[]) => void;
  onDraft: (d: [number, number][]) => void;
  onClose: () => void;
}

const KINDS = [["belt", "Conveyor belt"], ["work", "Working area"], ["staging", "Staging or waiting area"], ["other", "Other"]];

/** Draw polygons on the video, then export them. Analytics re-runs from stored detections, not the video. */
export default function ZonePanel({ zones, draft, onChange, onDraft, onClose }: Props) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("belt");

  const add = () => {
    const id = (name || kind).toLowerCase().replace(/[^a-z0-9]+/g, "-") + (zones.some((z) => z.kind === kind) ? `-${zones.length + 1}` : "");
    onChange([...zones, { id, name: name || KINDS.find((k) => k[0] === kind)![1], kind, polygon: draft }]);
    onDraft([]);
    setName("");
  };

  const download = () => {
    const body = { zones: zones.map((z) => ({ ...z, polygon: z.polygon.map(([x, y]) => [+x.toFixed(4), +y.toFixed(4)]) })) };
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
    a.download = "zones.json";
    a.click();
  };

  return (
    <section className="zone-panel">
      <header>
        <h2>Zones</h2>
        <button type="button" onClick={onClose}>Done</button>
      </header>
      <p>Click on the video to place the corners of a zone. Pause first so the picture holds still.</p>
      <div className="zone-form">
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Zone type">
          {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name (optional)" aria-label="Zone name" />
        <button type="button" disabled={draft.length < 3} onClick={add}>Add zone ({draft.length} corners)</button>
        <button type="button" disabled={!draft.length} onClick={() => onDraft(draft.slice(0, -1))}>Undo corner</button>
      </div>
      <ul>
        {zones.map((z) => (
          <li key={z.id}>
            <span>{z.name}</span>
            <button type="button" onClick={() => onChange(zones.filter((o) => o.id !== z.id))}>Remove</button>
          </li>
        ))}
      </ul>
      <button type="button" className="primary" onClick={download}>Download zones.json</button>
      <p className="hint">Save the file as <code>config/zones.json</code> and run <code>./run.sh analytics</code>. The numbers are recalculated from stored detections in seconds; the video is not reprocessed.</p>
    </section>
  );
}
