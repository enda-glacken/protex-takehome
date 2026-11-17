import { useEffect, useRef, useState } from "react";
import { frameAt, mmss } from "../lib/data";
import type { Frame, Insight, Rule } from "../lib/types";

const KINDS = ["belt_stopped", "crew_underused", "belt_starved"]; // one moment from each, in this order

interface Props {
  insights: Insight[];
  rules: Rule[];
  frames: Frame[];
  privacy: boolean;
  toReview: number;   // events still waiting for a call
  total: number;
  onSelect: (i: Insight) => void;
  onStart: () => void;
}

/** The three moments most worth watching, as stills from the video. */
export default function Flagged({ insights, rules, frames, privacy, toReview, total, onSelect, onStart }: Props) {
  const picks = KINDS.map((k) => insights.find((i) => i.kind === k)).filter((i): i is Insight => !!i);
  for (const i of insights) if (picks.length < 3 && !picks.includes(i)) picks.push(i);
  const name = (kind: string) => rules.find((r) => r.kind === kind)?.name ?? "";
  if (!picks.length) return null;
  return (
    <section className="flagged">
      <h2>Flagged for review</h2>
      <p className="side-note">The three moments most worth watching.</p>
      <div className="flag-row">
        {picks.slice(0, 3).map((i) => (
          <button type="button" className="flag" key={i.id} onClick={() => onSelect(i)}>
            <Still t={i.t_start_s + Math.min(10, (i.t_end_s - i.t_start_s) / 2)} frames={frames} privacy={privacy} />
            <span className="flag-text">
              <span className="flag-title">{i.title}</span>
              <span className="flag-meta">{name(i.kind)}, {mmss(i.t_start_s)} to {mmss(i.t_end_s)}</span>
            </span>
          </button>
        ))}
      </div>
      {total > 0 && (
        <button type="button" className={toReview ? "primary start-review" : "quiet start-review"} onClick={onStart}>
          {toReview === total ? `Start review (${total} events)` : toReview ? `Continue review (${toReview} left)` : `All ${total} reviewed. Go through them again`}
        </button>
      )}
    </section>
  );
}

/** One frame of the video at time t, with people blurred the same way as the main player. */
function Still({ t, frames, privacy }: { t: number; frames: Frame[]; privacy: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const v = video.current, c = canvas.current;
    if (!ready || !v || !c) return;
    const w = (c.width = 480), h = (c.height = 270);
    const g = c.getContext("2d")!;
    g.drawImage(v, 0, 0, w, h);
    if (privacy) {
      for (const [, , x1, y1, x2, y2] of frameAt(frames, t)?.[1] ?? []) {
        g.save();
        g.beginPath();
        g.rect((x1 - 0.012) * w, (y1 - 0.012) * h, (x2 - x1 + 0.024) * w, (y2 - y1 + 0.024) * h);
        g.clip();
        if (typeof (g as { filter?: string }).filter === "string") {
          g.filter = "blur(5px)";
          g.drawImage(v, 0, 0, w, h);
        } else {
          g.fillStyle = "#48555f";
          g.fillRect(0, 0, w, h);
        }
        g.restore();
      }
    }
  }, [ready, privacy, frames, t]);

  return (
    <span className="still">
      {!failed && (
        <video ref={video} src={`${import.meta.env.BASE_URL}video/unloading.mp4`} muted playsInline preload="metadata"
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;   // never seek past the end of a shorter clip
            v.currentTime = Math.min(t, Math.max(0, (v.duration || t) - 0.5));
          }}
          onSeeked={() => setReady(true)} onError={() => setFailed(true)} />
      )}
      <canvas ref={canvas} aria-hidden="true" />
      <span className="still-play" aria-hidden="true">▶</span>
      <span className="still-time">{mmss(t)}</span>
    </span>
  );
}
