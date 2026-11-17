import { useSyncExternalStore } from "react";

/** Operator-chosen names for cameras, kept in this browser so they survive a reload. */
const STORE = "unloading-camera-labels";
const listeners = new Set<() => void>();
let cache: Record<string, string> | null = null;

function read(): Record<string, string> {
  if (cache) return cache;
  try { cache = JSON.parse(localStorage.getItem(STORE) ?? "{}"); } catch { cache = {}; }
  return cache!;
}

export function saveCameraLabel(camera: string, label: string) {
  const next = { ...read() };
  const clean = label.trim();
  if (clean && clean !== camera) next[camera] = clean; else delete next[camera];
  cache = next;
  try { localStorage.setItem(STORE, JSON.stringify(next)); } catch { /* storage unavailable: the name lasts until reload */ }
  listeners.forEach((l) => l());
}

/** Returns a function giving the label for a camera (its own name unless the operator renamed it). */
export function useCameraLabels() {
  const labels = useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, read, read);
  return (camera: string) => labels[camera] ?? camera;
}
