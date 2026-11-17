import { useState } from "react";
import { saveCameraLabel, useCameraLabels } from "../lib/cameraLabels";
import { duration, mmss } from "../lib/data";
import type { AllocationWindow, Meta } from "../lib/types";
import { CAMERAS } from "./CameraTabs";

const people = (n: number) => (Math.max(1, Math.round(n)) === 1 ? "1 person" : `${Math.max(1, Math.round(n))} people`);

/** Camera name the operator can rename; saved in this browser. `page` renders it as the page title. */
export function CameraName({ camera, page = false }: { camera: string; page?: boolean }) {
  const label = useCameraLabels()(camera);
  const [draft, setDraft] = useState<string | null>(null);
  const save = () => { if (draft != null) saveCameraLabel(camera, draft); setDraft(null); };
  if (draft == null) {
    return (
      <span className="cam-name">
        {page ? <h1>{label}</h1> : <h3>{label}</h3>}
        <button type="button" className="pencil" onClick={() => setDraft(label)} aria-label={`Rename ${label}`} title="Rename">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M11.3 1.9l2.8 2.8L5.3 13.5l-3.5.7.7-3.5z M9.6 3.6l2.8 2.8" /></svg>
        </button>
      </span>
    );
  }
  return (
    <form className="cam-name editing" onSubmit={(e) => { e.preventDefault(); save(); }}>
      <input autoFocus value={draft} maxLength={40} aria-label="Camera name" onChange={(e) => setDraft(e.target.value)}
        onFocus={(e) => e.currentTarget.select()}
        onKeyDown={(e) => { if (e.key === "Escape") setDraft(null); }} />
      <button type="submit" className="rename strong">Save</button>
      <button type="button" className="rename" onClick={() => setDraft(null)}>Cancel</button>
    </form>
  );
}

/** "Connect camera" for a camera with no footage. Honest about being a placeholder. */
export function ConnectCamera() {
  const [asked, setAsked] = useState(false);
  return (
    <>
      <button type="button" className="connect" onClick={() => setAsked((a) => !a)}>Connect camera</button>
      {asked && <p className="connect-note">Connecting cameras isn't available in this prototype. In a deployment this starts the camera setup.</p>}
    </>
  );
}

interface Props {
  meta: Meta;
  allocation: AllocationWindow[];
  onSeek: (t: number) => void;
}

/**
 * The customer has a fixed pool of people across several lines. The chart shows when the connected
 * line had a person to spare and leaves a matching, empty slot on every line that is not connected.
 * Other lines are never given invented data.
 */
export default function Lines({ meta, allocation, onSeek }: Props) {
  const label = useCameraLabels();
  const [adding, setAdding] = useState<string | null>(null);
  const camera = meta.site.camera ?? "IP Camera 2";
  const others = CAMERAS.filter((c) => c !== camera);
  const length = meta.video.duration_s;
  const release = allocation.filter((w) => w.kind === "release");
  const need = allocation.filter((w) => w.kind === "need");
  const total = (ws: AllocationWindow[]) => ws.reduce((a, w) => a + w.t_end_s - w.t_start_s + 1, 0);
  const each = (ws: AllocationWindow[]) => people(ws.reduce((a, w) => a + w.people, 0) / ws.length);
  const span = (w: AllocationWindow) => `${mmss(w.t_start_s)} to ${mmss(w.t_end_s)}`;
  const place = (w: AllocationWindow) => ({
    left: `${(w.t_start_s / length) * 100}%`,
    width: `max(10px, ${((w.t_end_s - w.t_start_s + 1) / length) * 100}%)`,
  });
  const ticks = Array.from({ length: Math.floor(length / 300) + 1 }, (_, i) => i * 300);

  return (
    <section className="panel lines">
      <h2>Across your lines</h2>
      {release.length ? (
        <>
          <p className="moves-lede">
            {label(camera)} had about <b>{each(release)} to spare for {duration(total(release))}</b>. Connect another line to see whether it needed them then.
          </p>
          <ul className="moves-legend">
            <li><i className="key spare" />Person to spare</li>
            {need.length > 0 && <li><i className="key short" />Short of a person</li>}
            <li><i className="key slot" />Needed here? Not known yet</li>
          </ul>
          <div className="moves-chart" style={{ gridTemplateRows: "repeat(2, 44px) 22px" }}>
            {/* one band per spare window, running down into the other lines' row */}
            <div className="moves-bands" style={{ gridRow: "1 / span 2" }} aria-hidden="true">
              {release.map((w) => <span key={w.t_start_s} style={place(w)} />)}
            </div>
            <div className="moves-name" style={{ gridRow: 1 }}><b>{label(camera)}</b></div>
            <div className="moves-strip" style={{ gridRow: 1 }}>
              {release.map((w) => (
                <button type="button" key={`r${w.t_start_s}`} className="blk spare" style={place(w)} onClick={() => onSeek(w.t_start_s)}
                  title={`${people(w.people)} to spare, ${span(w)}. Select to watch.`}>
                  {(w.t_end_s - w.t_start_s + 1) / length >= 0.07 && <span>{Math.max(1, Math.round(w.people))} free</span>}
                </button>
              ))}
              {need.map((w) => (
                <button type="button" key={`n${w.t_start_s}`} className="blk short" style={place(w)} onClick={() => onSeek(w.t_start_s)}
                  title={`Short by ${people(w.people)}, ${span(w)}. Select to watch.`} />
              ))}
            </div>
            <div className="moves-name off" style={{ gridRow: 2 }}><b>Your other lines</b><span>not connected</span></div>
            <div className="moves-strip off" style={{ gridRow: 2 }}>
              {release.map((w) => (
                <span key={w.t_start_s} className="blk slot" style={place(w)}
                  title={`Not known: connect another line to see whether it was short of people from ${span(w)}.`}><span>?</span></span>
              ))}
            </div>
            <div className="moves-axis" style={{ gridRow: 3 }} aria-hidden="true">
              {ticks.map((t) => <span key={t} style={{ left: `${(t / length) * 100}%` }}>{mmss(t)}</span>)}
            </div>
          </div>
          <p className="moves-add">
            <span>Connect a line:</span>
            {others.map((c) => (
              <button type="button" key={c} className="more-link" aria-expanded={adding === c} onClick={() => setAdding(adding === c ? null : c)}>{label(c)}</button>
            ))}
          </p>
          {adding && (
            <p className="connect-note" role="status">
              Adding {label(adding)} isn't available in this prototype. In a deployment this starts the camera setup.
            </p>
          )}
        </>
      ) : <p className="panel-note">No window where this line had more people than it could use.</p>}
    </section>
  );
}
