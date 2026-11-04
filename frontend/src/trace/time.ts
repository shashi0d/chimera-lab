/** "+1:05" from the run's start, for a trace row. */
export function offset(at: string, start: string | null): string {
  if (!start) return "";
  const s = Math.max(0, Math.round((Date.parse(at) - Date.parse(start)) / 1000));
  return `+${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** "1:52" left until an ISO time (never negative). */
export function remaining(until: string, now: number): string {
  const s = Math.max(0, Math.ceil((Date.parse(until) - now) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** "00:00 UTC" from an ISO time, as the cap message words it. */
export function utcClock(iso: string | null | undefined): string | null {
  if (!iso || Number.isNaN(Date.parse(iso))) return null;
  const d = new Date(iso);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
}
