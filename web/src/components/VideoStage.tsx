import { useEffect, useRef } from "react";
import { frameAt, OVERLAY_COLOR } from "../lib/data";
import type { Frame, Zone } from "../lib/types";

const BONES = [[5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16]];
const WRISTS = [9, 10];

export interface Layers { boxes: boolean; pose: boolean; zones: boolean; privacy: boolean }

interface Props {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  videoEvents: object;
  hasVideo: boolean;
  playing: boolean;
  onToggle: () => void;
  aspect: number;
  time: number;
  frames: Frame[];
  zones: Zone[];
  layers: Layers;
  draft: [number, number][] | null; // polygon being drawn in the zone editor
  onStageClick?: (p: [number, number]) => void;
}

export default function VideoStage(p: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = c.clientHeight;
    if (c.width !== w * dpr || c.height !== h * dpr) { c.width = w * dpr; c.height = h * dpr; }
    const g = c.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.lineJoin = "round";
    g.font = "500 12px Outfit, system-ui, sans-serif";

    const poly = (pts: [number, number][], close = true) => {
      g.beginPath();
      pts.forEach(([x, y], i) => (i ? g.lineTo(x * w, y * h) : g.moveTo(x * w, y * h)));
      if (close) g.closePath();
    };

    const frame = frameAt(p.frames, p.time);

    // Privacy: blur each person, not the whole picture, so the operation stays readable.
    const video = p.videoRef.current;
    if (p.layers.privacy && video && video.readyState >= 2) {
      for (const [, , x1, y1, x2, y2] of frame?.[1] ?? []) {
        const pad = 0.012;
        g.save();
        g.beginPath();
        g.rect((x1 - pad) * w, (y1 - pad) * h, (x2 - x1 + 2 * pad) * w, (y2 - y1 + 2 * pad) * h);
        g.clip();
        if (typeof (g as { filter?: string }).filter === "string") {
          g.filter = "blur(10px)";
          g.drawImage(video, 0, 0, w, h);
        } else {   // browsers without canvas filters: cover the person instead
          g.fillStyle = "#48555f";
          g.fillRect(0, 0, w, h);
        }
        g.restore();
      }
    }

    if (p.layers.zones) {
      for (const z of p.zones) {
        const belt = z.kind === "belt";
        poly(z.polygon);
        g.fillStyle = belt ? "rgba(245,196,0,0.16)" : "rgba(255,255,255,0.07)";
        g.fill();
        g.setLineDash(belt ? [] : [6, 5]);
        g.lineWidth = belt ? 2.5 : 1.5;
        g.strokeStyle = belt ? "#f5c400" : "rgba(255,255,255,0.8)";
        g.stroke();
        g.setLineDash([]);
        const [lx, ly] = z.polygon[0];
        chip(g, z.name, lx * w + 6, ly * h + 6, belt ? "#f5c400" : "rgba(11,11,12,0.85)", belt ? "#0b0b0c" : "#fff");
      }
    }

    for (const [, state, x1, y1, x2, y2, kp] of frame?.[1] ?? []) {
      const color = OVERLAY_COLOR[state];
      if (p.layers.pose && kp.length) {
        g.lineWidth = 2;
        g.strokeStyle = "rgba(255,255,255,0.9)";
        for (const [a, b] of BONES) {
          if (kp[a][2] < 0.3 || kp[b][2] < 0.3) continue;
          g.beginPath();
          g.moveTo(kp[a][0] * w, kp[a][1] * h);
          g.lineTo(kp[b][0] * w, kp[b][1] * h);
          g.stroke();
        }
        // Wrists are the signal the analytics uses, so they get the emphasis.
        for (const i of WRISTS) {
          if (kp[i][2] < 0.3) continue;
          g.beginPath();
          g.arc(kp[i][0] * w, kp[i][1] * h, 5, 0, Math.PI * 2);
          g.fillStyle = color;
          g.fill();
          g.lineWidth = 2;
          g.strokeStyle = "#0b0b0c";
          g.stroke();
        }
      }
      if (p.layers.boxes) {
        g.lineWidth = 2;
        g.strokeStyle = color;
        g.setLineDash(state === "moving" ? [6, 4] : []);   // moving and handling are both white; the dash tells them apart
        g.strokeRect(x1 * w, y1 * h, (x2 - x1) * w, (y2 - y1) * h);
        g.setLineDash([]);
        // State only: tracker ids are not stable identities, and the product is about the crew, not individuals.
        chip(g, state, x1 * w, y1 * h - 20, color, "#0b0b0c");
      }
    }

    if (p.draft?.length) {
      poly(p.draft, false);
      g.lineWidth = 2;
      g.strokeStyle = "#f5c400";
      g.stroke();
      for (const [x, y] of p.draft) {
        g.beginPath();
        g.arc(x * w, y * h, 4, 0, Math.PI * 2);
        g.fillStyle = "#f5c400";
        g.fill();
      }
    }
  });

  const click = (e: React.MouseEvent) => {
    if (!p.onStageClick) return;
    const r = e.currentTarget.getBoundingClientRect();
    p.onStageClick([(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]);
  };

  return (
    <div className="stage" style={{ aspectRatio: String(p.aspect) }}>
      {p.hasVideo ? (
        <video ref={p.videoRef} src={`${import.meta.env.BASE_URL}video/unloading.mp4`} controls={!p.onStageClick}
          muted playsInline preload="auto" {...p.videoEvents} />
      ) : (
        <div className="stage-empty">
          <p>No video file found, so only the tracked skeletons are shown.</p>
          <p>Run <code>./run.sh video path/to/file.mp4</code> to add the clip.</p>
          <button type="button" onClick={p.onToggle}>{p.playing ? "Pause" : "Play"}</button>
        </div>
      )}
      <canvas ref={canvasRef} className={p.onStageClick ? "drawing" : ""} onClick={click} />
    </div>
  );
}

function chip(g: CanvasRenderingContext2D, text: string, x: number, y: number, bg: string, fg: string) {
  const w = g.measureText(text).width + 10;
  g.fillStyle = bg;
  g.beginPath();
  g.roundRect(x, Math.max(0, y), w, 18, 3);
  g.fill();
  g.fillStyle = fg;
  g.textBaseline = "middle";
  g.fillText(text, x + 5, Math.max(0, y) + 9.5);
}
