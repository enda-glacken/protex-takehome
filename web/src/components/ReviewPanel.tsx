import { useEffect, useRef, useState } from "react";
import { mmss } from "../lib/data";
import { OUTCOME_LABEL, OUTCOMES, setNote, setReview, useNotes, useReviews } from "../lib/reviews";
import type { Insight, Rule } from "../lib/types";

interface Props {
  queue: Insight[];            // events to review, highest priority first
  rules: Rule[];
  selected: Insight;
  onSelect: (i: Insight) => void;
  onClose: () => void;
}

// The browser's speech-to-text (Chrome, Edge, Safari). Typed notes work everywhere.
interface Recogniser {
  continuous: boolean; interimResults: boolean; lang: string;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void;
}
const recogniser = (): (new () => Recogniser) | undefined => {
  const w = window as unknown as { SpeechRecognition?: new () => Recogniser; webkitSpeechRecognition?: new () => Recogniser };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
};

/**
 * Sits beside the video. Explains the selected event, takes the operator's own account of it
 * (typed or narrated) and their call, then moves to the next one, so a review never leaves the video.
 */
export default function ReviewPanel({ queue, rules, selected, onSelect, onClose }: Props) {
  const reviews = useReviews();
  const notes = useNotes();
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState("");
  const rec = useRef<Recogniser | null>(null);

  // Narration belongs to one event: stop listening when the event changes or the panel closes.
  useEffect(() => { setMicError(""); return () => { rec.current?.stop(); rec.current = null; }; }, [selected.id]);

  const idx = queue.findIndex((i) => i.id === selected.id);
  const rule = rules.find((r) => r.kind === selected.kind);
  const outcome = reviews[selected.id];
  const note = notes[selected.id] ?? "";

  const choose = (o: (typeof OUTCOMES)[number]) => {
    if (outcome === o) { setReview(selected.id, null); return; }
    setReview(selected.id, o);
    if (outcome) return;   // changing an earlier call: stay on this event
    const rest = [...queue.slice(idx + 1), ...queue.slice(0, idx)];
    const next = rest.find((i) => !reviews[i.id]);
    if (next) onSelect(next);
  };

  const narrate = () => {
    if (listening) { rec.current?.stop(); return; }
    const Ctor = recogniser();
    if (!Ctor) return;
    const id = selected.id, before = note.trim() ? `${note.trim()} ` : "";
    const r = new Ctor();
    r.continuous = true;
    r.interimResults = true;
    r.lang = navigator.language || "en-GB";
    r.onresult = (e) => {
      let said = "";
      for (let k = 0; k < e.results.length; k++) said += e.results[k][0].transcript;
      setNote(id, before + said.trim());
    };
    r.onerror = (e) => setMicError(e.error === "not-allowed" || e.error === "service-not-allowed"
      ? "Microphone access was refused. You can type instead."
      : e.error === "no-speech" ? "" : `Narration stopped (${e.error}). You can type instead.`);
    r.onend = () => { setListening(false); rec.current = null; };
    try { r.start(); rec.current = r; setListening(true); setMicError(""); }
    catch { setMicError("Narration could not start. You can type instead."); }
  };

  return (
    <section className="review" aria-label="Event review">
      <div className="review-head">
        <span className="review-step">
          {idx >= 0 ? <>Reviewing {idx + 1} of {queue.length}</> : selected.severity === "info" ? <>Benchmark</> : <>Pattern across the recording</>}
        </span>
        <span className="review-nav">
          {idx >= 0 && queue.length > 1 && (
            <>
              <button type="button" onClick={() => onSelect(queue[(idx - 1 + queue.length) % queue.length])}>Previous</button>
              <button type="button" onClick={() => onSelect(queue[(idx + 1) % queue.length])}>Next</button>
            </>
          )}
          <button type="button" onClick={onClose}>Close</button>
        </span>
      </div>
      <h2>{selected.title}</h2>
      <p className="review-meta">
        {rule?.name ? `${rule.name}, ` : ""}{mmss(selected.t_start_s)} to {mmss(selected.t_end_s)}
        <button type="button" className="rename" onClick={() => onSelect(selected)}>Replay</button>
      </p>
      <div className="review-body">
        <h4>What happened</h4><p>{selected.what}</p>
        <h4>Why it matters</h4><p>{selected.so_what}</p>
        <h4>What to try</h4><p>{selected.recommendation}</p>
      </div>
      <div className="review-foot">
        <div className="note-head">
          <label htmlFor="review-note">What did you see? <span>optional</span></label>
          {recogniser() && (
            <button type="button" className={`mic ${listening ? "on" : ""}`} aria-pressed={listening} onClick={narrate}>
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.8a2 2 0 0 1 2 2v3.6a2 2 0 0 1-4 0V3.8a2 2 0 0 1 2-2z M3.8 7.4a4.2 4.2 0 0 0 8.4 0 M8 11.6v2.6" /></svg>
              {listening ? "Stop" : "Narrate"}
            </button>
          )}
        </div>
        <textarea id="review-note" rows={2} value={note} placeholder={listening ? "Listening. Say what happened and why." : "Say or type what happened and why."}
          onChange={(e) => setNote(selected.id, e.target.value)} />
        {micError && <p className="mic-error" role="status">{micError}</p>}
        {idx >= 0 ? (
          <>
            <p className="review-ask">Mark as reviewed</p>
            <div className="calls">
              {OUTCOMES.map((o) => (
                <button type="button" key={o} className={`call ${o}`} aria-pressed={outcome === o} onClick={() => choose(o)}>{OUTCOME_LABEL[o]}</button>
              ))}
            </div>
          </>
        ) : <p className="review-ask quiet-ask">Nothing to mark: this is for reference.</p>}
      </div>
    </section>
  );
}
