// Turns predictions into advice an organizer can act on. Pure functions; no DOM, no network.

import { addDays, weekday, diffDays } from "./dates.js";
import { sunTimes } from "./sun.js";
import { predict, effectSummary, bestSimpleModel } from "./engine.js";

const SUNSET_MARGIN_MIN = 30;

/** The next `count` dates (after `from`) on the group's usual weekday, plus the day after it. */
export function suggestDates(from, usual, count = 3) {
  const out = [];
  let d = addDays(from, 1);
  for (let i = 0; i < 60 && out.length < count; i++, d = addDays(d, 1)) {
    if (weekday(d) === usual) out.push(d);
  }
  return out;
}

export function usualWeekday(events) {
  const counts = new Array(7).fill(0);
  events.forEach((e) => counts[weekday(e.date)]++);
  return counts.indexOf(Math.max(...counts));
}

export function confidence(n) {
  return n < 12 ? "low" : n < 24 ? "medium" : "good";
}

/** Latest start (hours) so the event ends SUNSET_MARGIN_MIN before dark; null if no sun data. */
export function sunAdvice(iso, place, startHour, durationMin) {
  const s = sunTimes(iso, place);
  if (s.sunrise === null) return null;
  const latest = (s.sunset - SUNSET_MARGIN_MIN - durationMin) / 60;
  const earliest = s.sunrise / 60;
  return {
    sunrise: s.sunrise,
    sunset: s.sunset,
    latestStart: latest,
    earliestStart: earliest,
    tooLate: startHour > latest,
    tooEarly: startHour < earliest,
  };
}

/**
 * Plan for candidate dates.
 * opts: { events, cal, place, dates, startHour, duration, rain, predictor }
 * predictor(events, cal, targets, model) -> predictions (defaults to the offline engine; the app
 * can pass a Smart-mode wrapper that falls back to it).
 */
export function plan({ events, cal, place, dates, startHour, duration, rain = 0, predictor = predict, model = "auto" }) {
  const chosen = model === "auto" ? bestSimpleModel(events, cal) : model;
  const targets = dates.map((date) => ({ date, start_hour: startHour, rain }));
  const preds = predictor(events, cal, targets, chosen);
  const rows = preds.map((p, i) => ({
    ...p,
    sun: place ? sunAdvice(dates[i], place, startHour, duration) : null,
    event: cal.eventNear(dates[i]),
  }));
  let best = 0;
  rows.forEach((r, i) => {
    if (r.point > rows[best].point + 1e-9) best = i;
  });
  const top = rows[best];
  const rainy = predictor(events, cal, [{ date: top.date, start_hour: startHour, rain: 1 }], chosen)[0];
  return {
    rows,
    best,
    supplies: Math.ceil(top.high),
    rainScenario: rainy,
    confidence: confidence(events.length),
    model: top.model,
    effects: effectSummary(events, cal),
  };
}

/** Days from `today` to a date (for "in 5 days"). */
export const daysUntil = (today, iso) => diffDays(iso, today);
