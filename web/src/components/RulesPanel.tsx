import { beltStops, mmss } from "../lib/data";
import type { Insight, Opportunity, Rule, Second, Zone } from "../lib/types";

const CHANNELS = ["Email", "Slack", "Teams", "SMS"];
// What the person receiving the alert can do with it.
const WHY: Record<string, string> = {
  belt_stopped: "A stopped belt idles the whole crew at once. Told within seconds, a supervisor can clear it before it becomes minutes.",
  belt_starved: "The crew is ready and nothing is arriving. Chase the feeding end, or lend people to a line that is short.",
  crew_underused: "More people are at this line than the work needs right now. Move someone to a line that is short.",
};
const list = (xs: string[]) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

interface Props {
  rules: Rule[];
  zones: Zone[];
  insights: Insight[];
  opportunities: Opportunity[];
  timeline: Second[];
  site: string;
  onOpenEvents: (kinds: string[]) => void;
  onEditZones: () => void;
}

/** Alerts: what the operations manager would be told while it is happening, and what that is worth. */
export default function RulesPanel({ rules, zones, insights, opportunities, timeline, site, onOpenEvents, onEditZones }: Props) {
  const alerts = rules.filter((r) => r.alert_after_s != null);
  const stops = beltStops(timeline);
  return (
    <>
      <h2>Alerts</h2>
      <ul className="alerts">
        {alerts.map((r) => {
          const after = r.alert_after_s ?? 0;
          const mine = insights.filter((i) => i.kind === r.kind).sort((a, b) => a.t_start_s - b.t_start_s);
          const all = r.kind === "belt_stopped" && stops.length > 0;   // every stop is known from the timeline
          const times = all ? stops.map(([a]) => a + after) : mine.map((i) => i.t_start_s + after);
          const people = mine[0]?.evidence.present as number | undefined;
          const cost = opportunities.find((o) => o.event_kinds.includes(r.kind));
          return (
            <li key={r.kind} className="alert-card">
              <h3>{r.name}</h3>
              <dl>
                <dt>Tells you when</dt><dd>{r.definition}</dd>
                <dt>Why it helps</dt><dd>{WHY[r.kind] ?? "Someone can act while it is still happening."}</dd>
                <dt>In this recording</dt>
                <dd>
                  {times.length === 0 ? "It would not have gone off."
                    : times.length > 3 ? `It would have alerted ${times.length} times, first at ${mmss(times[0])}.`
                      : `It would have alerted at ${list(times.map(mmss))}${all ? "" : " (the longest cases)"}.`}
                  {cost && <> {cost.what}</>}
                </dd>
              </dl>
              {mine[0] && (
                <p className="alert-msg">
                  <span>Example alert</span>
                  {site}: {r.name.toLowerCase()} for {after} seconds{people ? `, ${people} people in view` : ""}. Watch the clip.
                </p>
              )}
              <p className="alert-channels"><b>Send to</b>{CHANNELS.map((c) => <span key={c}>{c}</span>)}</p>
              <button type="button" className="rename" disabled={!mine.length} onClick={() => onOpenEvents([r.kind])}>See these events</button>
            </li>
          );
        })}
      </ul>

      <div className="alert-setup">
        <p><b>What this camera watches.</b> {list(zones.map((z) => z.name))}. Alerts depend on the belt zone being drawn in the right place.</p>
        <button type="button" className="quiet" onClick={onEditZones}>Edit zones on the video</button>
      </div>
      <details className="rule-defs">
        <summary>How each event and pattern is worked out</summary>
        <dl>
          {rules.map((r) => (<div key={r.kind}><dt>{r.name}</dt><dd>{r.definition}</dd></div>))}
        </dl>
      </details>
    </>
  );
}
