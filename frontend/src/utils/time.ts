/**
 * Time display helper (RUI-02).
 *
 * The backend stores timestamps in UTC and returns ISO strings WITHOUT a timezone
 * suffix (e.g. "2026-08-30T08:12:26"). A bare `new Date(iso)` would parse them as
 * LOCAL time, causing an 8-hour offset for UTC+8 users. This helper appends a `Z`
 * (UTC marker) before parsing, so the value is converted to the viewer's local
 * timezone correctly.
 *
 * SUGGESTION-1 defense: values that already carry an explicit timezone indicator
 * (`Z` or `+HH:MM` / `-HH:MM`) are parsed as-is, so tz-aware data is not corrupted.
 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const text = String(iso);
  const hasZone = /(Z|[+-]\d{2}:\d{2})$/i.test(text);
  const normalized = hasZone ? text : text.replace(' ', 'T') + 'Z';
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text;
  return date.toLocaleString();
}
