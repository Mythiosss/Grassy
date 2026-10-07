import test from "node:test";
import assert from "node:assert/strict";
import { parseCSV, toCSV } from "../../web/js/csv.js";
import { normalizeEvents } from "../../web/js/engine.js";

test("english header, comma", () => {
  const r = parseCSV("date,attendance,start,rain\n2026-09-05,20,07:00,0\n2026-09-12,14,07:30,yes\n");
  assert.equal(r.rows.length, 2);
  assert.equal(r.rows[1].rain, 1);
});

test("indonesian header, semicolon, day-first dates", () => {
  const r = parseCSV("Tanggal;Hadir;Jam\n05/09/2026;20;7.30\n13/09/2026;14;07:00\n");
  assert.equal(r.rows[0].date, "2026-09-05");
  assert.equal(r.ambiguousDates, 1);
  assert.equal(r.rows[1].date, "2026-09-13");
});

test("no header", () => {
  assert.equal(parseCSV("2026-09-05,20\n2026-09-12,14\n").rows.length, 2);
});

test("bad lines are counted, not fatal", () => {
  const r = parseCSV("date,attendance\n2026-09-05,20\nhello,3\n2026-09-12,abc\n");
  assert.equal(r.rows.length, 1);
  assert.equal(r.skipped, 2);
});

test("garbage gives an error", () => {
  assert.ok(parseCSV("foo,bar\n1,2\n").error);
  assert.ok(parseCSV("").error);
});

test("round trip", () => {
  const { events } = normalizeEvents([{ date: "2026-09-05", attendance: 20, start: "07:30", duration: 90, rain: 1 }]);
  const back = parseCSV(toCSV(events));
  assert.equal(back.rows[0].attendance, 20);
  assert.equal(back.rows[0].start, "07:30");
});
