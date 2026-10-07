import test from "node:test";
import assert from "node:assert/strict";
import { LANGS, keysOf, t, weekdayName } from "../../web/js/i18n.js";

test("every language has every English key", () => {
  const en = keysOf("en");
  for (const l of Object.keys(LANGS)) {
    const missing = en.filter((k) => !keysOf(l).includes(k));
    assert.deepEqual(missing, [], `${l} missing ${missing}`);
  }
});

test("placeholders match English in every language", () => {
  const ph = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join();
  for (const l of Object.keys(LANGS)) {
    for (const k of keysOf("en")) assert.equal(ph(t(l, k, {})), ph(t("en", k, {})), `${l}.${k}`);
  }
});

test("t fills variables and falls back", () => {
  assert.equal(t("en", "needMore", { n: 6, have: 3 }), "Need at least 6 past events. You have 3.");
  assert.equal(t("xx", "plan"), "Plan");
  assert.equal(weekdayName("id", 5), "Sabtu");
});
