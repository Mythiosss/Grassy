import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeCalendar } from "../../web/js/calendar.js";
import { normalizeEvents } from "../../web/js/engine.js";
import { plan, suggestDates, usualWeekday, sunAdvice } from "../../web/js/planner.js";
import { weekday } from "../../web/js/dates.js";

const fx = JSON.parse(readFileSync(new URL("../fixtures/parity.json", import.meta.url)));
const cals = JSON.parse(readFileSync(new URL("../../web/data/calendar.json", import.meta.url)));
const c = fx.cases.find((x) => x.name.endsWith("24/full"));
const { events } = normalizeEvents(c.events);
const cal = makeCalendar(cals[c.country]);

test("suggestDates are on the usual weekday and in the future", () => {
  const u = usualWeekday(events);
  const ds = suggestDates("2026-10-07", u, 3);
  assert.equal(ds.length, 3);
  ds.forEach((d) => { assert.equal(weekday(d), u); assert.ok(d > "2026-10-07"); });
});

test("plan returns sane numbers", () => {
  const ds = suggestDates("2026-10-07", usualWeekday(events), 3);
  const r = plan({ events, cal, place: { lat: -8.65, lon: 115.22, tz: 8 }, dates: ds, startHour: 7, duration: 120 });
  assert.equal(r.rows.length, 3);
  assert.ok(r.supplies >= Math.round(r.rows[r.best].point));
  assert.ok(r.rainScenario.point <= r.rows[r.best].point * 1.0001 || r.effects.rain >= 1);
  assert.ok(["low", "medium", "good"].includes(r.confidence));
  for (const row of r.rows) assert.ok(Number.isFinite(row.point) && row.low <= row.point && row.point <= row.high);
});

test("sun advice flags a start too close to sunset", () => {
  const a = sunAdvice("2026-10-07", { lat: -8.65, lon: 115.22, tz: 8 }, 17.5, 120);
  assert.equal(a.tooLate, true);
  assert.equal(sunAdvice("2026-10-07", { lat: -8.65, lon: 115.22, tz: 8 }, 7, 120).tooLate, false);
});
