// Local events (holidays, festival seasons). The windows come from data/calendar.json, which is
// exported from grassy/calendar.py so Python and the phone app can never disagree.

import { toOrdinal } from "./dates.js";

/** windows: [[name, "YYYY-MM-DD", "YYYY-MM-DD"], ...] for ONE country. */
export function makeCalendar(windows = []) {
  const w = windows
    .map(([name, s, e]) => ({ name, s: toOrdinal(s), e: toOrdinal(e) }))
    .sort((a, b) => a.s - b.s);

  return {
    windows: w,

    /** Inside a long window (more than 5 days: Ramadan, a festival month). */
    inSeason(iso) {
      const d = toOrdinal(iso);
      return w.some((x) => x.s <= d && d <= x.e && x.e - x.s >= 5);
    },

    /** Within `within` days of a SHORT event (a holiday, not a whole season). */
    holidayNear(iso, within = 1, maxLen = 5) {
      const d = toOrdinal(iso);
      return w.some((x) => x.e - x.s <= maxLen && x.s - within <= d && d <= x.e + within);
    },

    /**
     * Closest event to a date: { name, gap } or null. gap is 0 inside the event, positive if it
     * starts later, negative if it ended earlier. Ties go to the shorter, more specific event.
     */
    eventNear(iso, within = 3) {
      const d = toOrdinal(iso);
      let best = null;
      let bestKey = null;
      for (const x of w) {
        const gap = d >= x.s && d <= x.e ? 0 : d < x.s ? x.s - d : -(d - x.e);
        if (Math.abs(gap) > within) continue;
        const key = [Math.abs(gap), x.e - x.s];
        if (!bestKey || key[0] < bestKey[0] || (key[0] === bestKey[0] && key[1] < bestKey[1])) {
          best = { name: x.name, gap };
          bestKey = key;
        }
      }
      return best;
    },
  };
}
