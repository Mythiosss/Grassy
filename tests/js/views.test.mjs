import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeCalendar } from "../../web/js/calendar.js";
import { normalizeEvents } from "../../web/js/engine.js";
import { plan, suggestDates, usualWeekday } from "../../web/js/planner.js";
import { buildInvite, whatsappUrl } from "../../web/js/invite.js";
import { viewApp, viewWelcome, esc } from "../../web/js/views.js";
import { LANGS } from "../../web/js/i18n.js";

const sample = JSON.parse(readFileSync(new URL("../../web/data/sample.json", import.meta.url)));
const cals = JSON.parse(readFileSync(new URL("../../web/data/calendar.json", import.meta.url)));
const BAD = /undefined|NaN|\[object|\{[a-z]+\}/;

for (const s of sample) {
  for (const lang of Object.keys(LANGS)) {
    test(`views render cleanly: ${s.key} / ${lang}`, () => {
      const { events } = normalizeEvents(s.events);
      const cal = makeCalendar(cals[s.country]);
      const dates = suggestDates("2026-10-07", usualWeekday(events), 3);
      const result = plan({ events, cal, place: s.place, dates, startHour: 7, duration: 120 });
      const top = result.rows[result.best];
      const invite = buildInvite({ lang, group: s.label, date: top.date, startHour: 7, rain: true });
      const ui = { tab: "plan", dates, picked: dates, startHour: 7, duration: 120, rain: false, result, invite, waUrl: whatsappUrl(invite) };
      const group = { name: s.label, events, synthetic: true };
      for (const tab of ["plan", "history", "settings"]) {
        const html = viewApp(lang, { smartUrl: "" }, group, { ...ui, tab }, "2026-10-07");
        assert.doesNotMatch(html, BAD, `${tab}`);
      }
      assert.doesNotMatch(viewWelcome(lang, { message: "x" }), BAD);
      assert.doesNotMatch(invite, BAD);
    });
  }
}

test("user text is escaped", () => {
  const evil = '<img src=x onerror=alert(1)>"';
  assert.equal(esc(evil).includes("<"), false);
  const html = viewApp("en", { smartUrl: "" }, { name: evil, events: [] }, { tab: "plan", dates: [], picked: [] }, "2026-10-07");
  assert.ok(!html.includes("<img"));
});
