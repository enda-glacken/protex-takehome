import { useState, type ReactNode } from "react";
import { mmss } from "../lib/data";
import { OUTCOME_LABEL, reviewQueue, useNotes, useReviews } from "../lib/reviews";
import type { Insight, Rule } from "../lib/types";

const PRIORITY = { high: "High", medium: "Medium", info: "" } as const;
type Show = "all" | "open" | "done";

interface Props {
  insights: Insight[];
  rules: Rule[];
  selectedId: string | null;
  filter: string[] | null; // rule kinds to show; null = all
  onFilter: (kinds: string[] | null) => void;
  onSelect: (i: Insight) => void;
}

/** The review queue: one line per event. Selecting one plays it and opens its explanation under the video. */
export default function EventList({ insights, rules, selectedId, filter, onFilter, onSelect }: Props) {
  const reviews = useReviews();
  const notes = useNotes();
  const [show, setShow] = useState<Show>("all");
  const queue = reviewQueue(insights, rules);
  const match = (i: Insight) => !filter || filter.includes(i.kind);
  const done = queue.filter((i) => reviews[i.id]).length;
  const rows = queue.filter(match).filter((i) => show === "all" || (show === "done") === !!reviews[i.id]);
  const stopEvents = insights.filter((i) => i.kind === "belt_stopped");
  const allStops = stopEvents[0]?.evidence.stops_in_clip as number | undefined;
  const names = (filter ?? []).map((k) => rules.find((r) => r.kind === k)?.name.toLowerCase() ?? k);

  if (!insights.length) return <p className="empty">No events yet. Run <code>./run.sh analytics</code> after processing the video.</p>;
  const row = (i: Insight, tag: string, status?: ReactNode) => (
    <li key={i.id}>
      <button type="button" className={`ev-row ${i.id === selectedId ? "selected" : ""}`} aria-current={i.id === selectedId} onClick={() => onSelect(i)}>
        <span className={`ev-tag ${status ? i.severity : ""}`}>{tag}</span>
        <span className="ev-time">{mmss(i.t_start_s)} to {mmss(i.t_end_s)}</span>
        <span className="ev-title">{i.title}</span>
        <span className="ev-status">{status}</span>
      </button>
    </li>
  );

  return (
    <>
      <div className="ev-head">
        <div>
          <h2>Events to review</h2>
          <p className="side-note">
            Highest priority first. Only the largest of each kind are listed
            {allStops != null && allStops > stopEvents.length && <>, including the {stopEvents.length} longest of {allStops} belt stops</>}.
            Select one to watch it; the review opens beside the video.
          </p>
        </div>
        <div className="seg" role="group" aria-label="Show events">
          {([["all", `All ${queue.length}`], ["open", `To review ${queue.length - done}`], ["done", `Reviewed ${done}`]] as [Show, string][]).map(([k, text]) => (
            <button type="button" key={k} aria-pressed={show === k} onClick={() => setShow(k)}>{text}</button>
          ))}
        </div>
      </div>
      <div className="ev-progress" role="img" aria-label={`${done} of ${queue.length} reviewed`}>
        <span className="ev-bar"><span style={{ width: `${queue.length ? (done / queue.length) * 100 : 0}%` }} /></span>
        <span>{done} of {queue.length} reviewed</span>
      </div>
      {filter && (
        <p className="ev-filter">
          Showing only: {names.join(", ")}. <button type="button" className="rename" onClick={() => onFilter(null)}>Show all events</button>
        </p>
      )}
      {rows.length ? (
        <ul className="ev-list">
          <li className="ev-cols" aria-hidden="true"><span>Priority</span><span>When</span><span>Event</span><span>Your call</span></li>
          {rows.map((i) => row(i, PRIORITY[i.severity], reviews[i.id]
            ? <><b className={`call-tag ${reviews[i.id]}`}>{OUTCOME_LABEL[reviews[i.id]]}</b>{notes[i.id] && <>, with your note</>}</>
            : <>To review{notes[i.id] && <>, note added</>}</>))}
        </ul>
      ) : <p className="empty">{show === "open" ? "Nothing left to review." : show === "done" ? "Nothing reviewed yet." : "No events of this kind."}</p>}
    </>
  );
}

/** Findings with nothing to review: patterns across the whole recording, and stretches when the line ran well. */
export function PatternList({ insights, rules, selectedId, onSelect }: Pick<Props, "insights" | "rules" | "selectedId" | "onSelect">) {
  const queue = reviewQueue(insights, rules);
  const rows = insights.filter((i) => !queue.includes(i));
  return (
    <>
      <h2>Patterns</h2>
      <p className="side-note">Patterns across the whole recording, and stretches when the line ran well. Nothing to review. Select one to see it explained beside the video.</p>
      {rows.length ? (
        <ul className="ev-list">
          {rows.map((i) => (
            <li key={i.id}>
              <button type="button" className={`ev-row ${i.id === selectedId ? "selected" : ""}`} aria-current={i.id === selectedId} onClick={() => onSelect(i)}>
                <span className="ev-tag">{i.severity === "info" ? "Benchmark" : "Pattern"}</span>
                <span className="ev-time">{mmss(i.t_start_s)} to {mmss(i.t_end_s)}</span>
                <span className="ev-title">{i.title}</span>
                <span className="ev-status" />
              </button>
            </li>
          ))}
        </ul>
      ) : <p className="empty">No patterns found in this recording.</p>}
    </>
  );
}
