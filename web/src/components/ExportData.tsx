import { useEffect, useRef, useState } from "react";

export interface ExportFile { label: string; note: string; run: () => void }

/** Downloads what the page shows for one camera, as CSV files. A quiet, secondary control. */
export default function ExportData({ name, files }: { name: string; files: ExportFile[] }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [open]);

  return (
    <span className="export" ref={box}>
      <button type="button" className="ghost-btn" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8 M4.8 7L8 10.2 11.2 7 M3 13h10" /></svg>
        Export data
      </button>
      {open && (
        <span className="add-note export-menu">
          <b>Export {name} data</b>
          {files.map((f) => (
            <button type="button" key={f.label} onClick={() => { f.run(); setOpen(false); }}>
              <span>{f.label}</span><em>{f.note}</em>
            </button>
          ))}
        </span>
      )}
    </span>
  );
}
