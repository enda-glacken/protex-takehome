import { useCallback, useEffect, useRef, useState } from "react";

/**
 * One clock for the whole app. Normally it follows the <video> element; if the video file is
 * missing (e.g. working from seeded demo data) it falls back to an internal clock so the
 * overlays, timeline and jump-to-moment still work.
 */
export function usePlayback(durationS: number) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasVideo, setHasVideo] = useState(true);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const clock = useRef(0);

  useEffect(() => {
    let raf = 0, last = performance.now();
    const tick = (now: number) => {
      const v = videoRef.current;
      if (hasVideo && v) {
        clock.current = v.currentTime;
      } else if (playing) {
        clock.current = Math.min(durationS, clock.current + (now - last) / 1000);
        if (clock.current >= durationS) setPlaying(false);
      }
      last = now;
      setTime((t) => (Math.abs(t - clock.current) > 0.05 ? clock.current : t));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [hasVideo, playing, durationS]);

  const seek = useCallback((t: number, play = false) => {
    const v = videoRef.current;
    clock.current = Math.max(0, Math.min(durationS, t));
    if (hasVideo && v) {
      v.currentTime = clock.current;
      if (play) void v.play();
    } else if (play) setPlaying(true);
    setTime(clock.current);
  }, [hasVideo, durationS]);

  const toggle = useCallback(() => {
    const v = videoRef.current;
    if (hasVideo && v) (v.paused ? void v.play() : v.pause());
    else setPlaying((p) => !p);
  }, [hasVideo]);

  return {
    videoRef, time, seek, toggle, hasVideo, playing,
    videoEvents: {
      onError: () => setHasVideo(false),
      onPlay: () => setPlaying(true),
      onPause: () => setPlaying(false),
    },
  };
}
