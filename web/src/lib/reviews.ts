import { useSyncExternalStore } from "react";
import type { Insight, Rule } from "./types";

/** The operator's call on each event, kept in this browser. It doubles as a label for checking the system. */
export type Outcome = "act" | "ok" | "wrong";
export const OUTCOMES: Outcome[] = ["act", "ok", "wrong"];
export const OUTCOME_LABEL: Record<Outcome, string> = { act: "Needs action", ok: "No action needed", wrong: "Not what happened" };

const STORE = "unloading-event-reviews";
const listeners = new Set<() => void>();
let cache: Record<string, Outcome> | null = null;

function read(): Record<string, Outcome> {
  if (cache) return cache;
  try { cache = JSON.parse(localStorage.getItem(STORE) ?? "{}"); } catch { cache = {}; }
  return cache!;
}

export function setReview(id: string, outcome: Outcome | null) {
  const next = { ...read() };
  if (outcome) next[id] = outcome; else delete next[id];
  cache = next;
  try { localStorage.setItem(STORE, JSON.stringify(next)); } catch { /* storage unavailable: reviews last until reload */ }
  listeners.forEach((l) => l());
}

export function useReviews() {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, read, read);
}

/** Events a person should look at: a moment in the video that a rule flagged as a problem. */
export function reviewQueue(insights: Insight[], rules: Rule[]): Insight[] {
  const clipWide = new Set(rules.filter((r) => r.scope === "clip").map((r) => r.kind));
  return insights.filter((i) => i.severity !== "info" && !clipWide.has(i.kind) && i.kind !== "staffing_curve" && i.kind !== "crew_mismatch");
}

/** The operator's own account of an event, typed or narrated. Kept in this browser, exported with the events. */
const NOTES = "unloading-event-notes";
const noteListeners = new Set<() => void>();
let noteCache: Record<string, string> | null = null;

function readNotes(): Record<string, string> {
  if (noteCache) return noteCache;
  try { noteCache = JSON.parse(localStorage.getItem(NOTES) ?? "{}"); } catch { noteCache = {}; }
  return noteCache!;
}

export function setNote(id: string, text: string) {
  const next = { ...readNotes() };
  if (text.trim()) next[id] = text; else delete next[id];
  noteCache = next;
  try { localStorage.setItem(NOTES, JSON.stringify(next)); } catch { /* storage unavailable: notes last until reload */ }
  noteListeners.forEach((l) => l());
}

export function useNotes() {
  return useSyncExternalStore((l) => { noteListeners.add(l); return () => noteListeners.delete(l); }, readNotes, readNotes);
}
