import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { sunTimes } from "../../web/js/sun.js";
import { makeCalendar } from "../../web/js/calendar.js";
import { normalizeEvents, parseHHMM, predict, bestSimpleModel, effectSummary } from "../../web/js/engine.js";

const fx = JSON.parse(readFileSync(new URL("../fixtures/parity.json", import.meta.url)));
const cals = JSON.parse(readFileSync(new URL("../../web/data/calendar.json", import.meta.url)));

test("sun times match Python", () => {
  for (const s of fx.sun) {
    const r = sunTimes(s.date, { lat: s.lat, lon: s.lon, tz: s.tz });
    if (s.sunrise === null) { assert.equal(r.sunrise, null); continue; }
    assert.ok(Math.abs(r.sunrise - s.sunrise) < 0.01, `sunrise ${s.date}`);
    assert.ok(Math.abs(r.sunset - s.sunset) < 0.01, `sunset ${s.date}`);
    assert.ok(Math.abs(r.daylightMin - s.daylight_min) < 0.01);
  }
});

for (const c of fx.cases) {
  test(`predictions match Python: ${c.name}`, () => {
    const cal = makeCalendar(cals[c.country]);
    const { events } = normalizeEvents(c.events);
    const targets = c.targets.map((t) => ({ date: t.date, start_hour: parseHHMM(t.start), rain: t.rain }));
    for (const [model, exp] of Object.entries(c.expected)) {
      const got = predict(events, cal, targets, model);
      exp.forEach((e, i) => {
        for (const k of ["point", "low", "high"]) {
          assert.ok(Math.abs(got[i][k] - e[k]) < 1e-6, `${model} ${k} #${i}: ${got[i][k]} vs ${e[k]}`);
        }
      });
    }
    assert.equal(bestSimpleModel(events, cal), c.best_simple_model);
    const es = effectSummary(events, cal);
    for (const [k, v] of Object.entries(c.effect_summary)) assert.ok(Math.abs(es[k] - v) < 1e-6, k);
  });
}
