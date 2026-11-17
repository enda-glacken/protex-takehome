import { useEffect, useRef, useState } from "react";
import { useCameraLabels } from "../lib/cameraLabels";

export const CAMERAS = ["IP Camera 1", "IP Camera 2", "IP Camera 3", "IP Camera 4"];

interface Props { connected: string; selected: string; onSelect: (camera: string) => void }

/** Which camera this page is showing. Only one camera has footage in this prototype. */
export default function CameraTabs({ connected, selected, onSelect }: Props) {
  const label = useCameraLabels();
  const [adding, setAdding] = useState(false);
  const actions = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!adding) return;
    const away = (e: PointerEvent) => { if (!actions.current?.contains(e.target as Node)) setAdding(false); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [adding]);

  return (
    <nav className="cam-tabs" aria-label="Cameras">
      {CAMERAS.map((c) => (
        <button type="button" key={c} className={c === selected ? "on" : ""} aria-current={c === selected ? "page" : undefined}
          onClick={() => onSelect(c)}>
          <i className={c === connected ? "dot live" : "dot"} aria-hidden="true" />
          <span>{label(c)}</span>
          {c !== connected && <em>not connected</em>}
        </button>
      ))}
      <span className="cam-actions" ref={actions}>
        <button type="button" className="add" aria-expanded={adding} onClick={() => setAdding((a) => !a)}>
          <span aria-hidden="true">+</span> Add camera
        </button>
        {adding && <span className="add-note" role="status">Adding cameras isn't available in this prototype. In a deployment this starts the camera setup.</span>}
      </span>
    </nav>
  );
}
