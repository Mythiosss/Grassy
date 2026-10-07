// DOM glue: loads data, keeps state, renders views, handles taps. All real logic is in the
// other modules so it can be tested without a browser.

import { load, save, newId } from "./store.js";
import { t } from "./i18n.js";
import { todayISO } from "./dates.js";
import { makeCalendar } from "./calendar.js";
import { normalizeEvents, parseHHMM, predict } from "./engine.js";
import { parseCSV, toCSV } from "./csv.js";
import { plan, suggestDates, usualWeekday } from "./planner.js";
import { buildInvite, whatsappUrl } from "./invite.js";
import { viewApp, viewWelcome, COUNTRIES } from "./views.js";

const root = document.getElementById("app");
const state = load();
let calendars = {};
let samples = [];
const ui = { tab: "plan", dates: [], picked: [], startHour: 7, duration: 120, rain: false, result: null, invite: "", waUrl: "#", message: "", smartNote: "", notSaved: false };

const lang = () => state.lang ?? (["id", "es", "sw"].find((l) => (navigator.language ?? "").startsWith(l)) ?? "en");
const current = () => state.groups.find((g) => g.id === state.current) ?? null;
const persist = () => { ui.notSaved = !save(state); };

function hydrate(g) {
  const { events } = normalizeEvents(g.rows);
  return { ...g, events };
}

function resetPlan(g) {
  const events = hydrate(g).events;
  const today = todayISO();
  ui.dates = events.length ? suggestDates(today, usualWeekday(events), 3) : [];
  ui.picked = [...ui.dates];
  ui.result = null;
  ui.smartNote = "";
  const starts = events.map((e) => e.start_hour).sort((a, b) => a - b);
  ui.startHour = starts.length ? starts[Math.floor(starts.length / 2)] : 7;
  const durs = events.map((e) => e.duration).sort((a, b) => a - b);
  ui.duration = durs.length ? durs[Math.floor(durs.length / 2)] : 120;
}

function render() {
  ui.smartUrl = state.smartUrl;
  const l = lang();
  document.documentElement.lang = l;
  const g = current();
  root.innerHTML = g ? viewApp(l, state, hydrate(g), ui, todayISO()) : viewWelcome(l, ui);
}

async function smartPredictions(g, events) {
  if (!state.smartUrl) return null;
  const base = state.smartUrl.replace(/\/+$/, "");
  const targets = ui.picked.flatMap((d) => [0, 1].map((rain) => ({ date: d, start: `${String(Math.floor(ui.startHour)).padStart(2, "0")}:${String(Math.round((ui.startHour % 1) * 60)).padStart(2, "0")}`, duration: ui.duration, rain })));
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    const res = await fetch(`${base}/api/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country: g.country, events: g.rows, targets }),
      signal: ctl.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    const j = await res.json();
    if (!Array.isArray(j.predictions) || j.predictions.length !== targets.length) return null;
    const map = new Map(j.predictions.map((p, i) => [`${targets[i].date}|${targets[i].rain}`, p]));
    return { model: j.model, map };
  } catch {
    return null;
  }
}

async function doPlan() {
  const g = current();
  const l = lang();
  const h = hydrate(g);
  if (!ui.picked.length) return;
  ui.smartNote = "";
  const smart = await smartPredictions(g, h.events);
  let predictor = predict;
  if (smart) {
    predictor = (events, cal, targets) =>
      targets.map((tg) => {
        const p = smart.map.get(`${tg.date}|${tg.rain ? 1 : 0}`);
        return { date: tg.date, point: p.point, low: p.low, high: p.high, model: smart.model, n: events.length };
      });
    ui.smartNote = t(l, "smartOn", { m: smart.model });
  } else if (state.smartUrl) ui.smartNote = t(l, "smartOff");
  const dates = [...ui.picked].sort();
  ui.result = plan({ events: h.events, cal: makeCalendar(calendars[g.country] ?? []), place: g.place, dates, startHour: ui.startHour, duration: ui.duration, rain: ui.rain ? 1 : 0, predictor });
  const top = ui.result.rows[ui.result.best];
  ui.invite = buildInvite({ lang: l, group: g.name, date: top.date, startHour: ui.startHour, rain: ui.rain, sunOk: !top.sun?.tooLate });
  ui.waUrl = whatsappUrl(ui.invite);
  render();
}

function addGroup({ name, country, rows, place, synthetic = false }) {
  const g = { id: newId(), name, country, place, rows, synthetic };
  state.groups.push(g);
  state.current = g.id;
  ui.tab = "plan";
  ui.message = "";
  resetPlan(g);
  persist();
  render();
}

function readInputs() {
  const s = document.getElementById("start");
  if (s?.value) { const h = parseHHMM(s.value); if (!Number.isNaN(h)) ui.startHour = h; }
  const d = document.getElementById("dur");
  if (d && Number(d.value) > 0) ui.duration = Number(d.value);
  const r = document.getElementById("rain");
  if (r) ui.rain = r.checked;
  const boxes = [...document.querySelectorAll("input[data-date]")];
  if (boxes.length) ui.picked = boxes.filter((c) => c.checked).map((c) => c.dataset.date); // other tabs have none: keep the choice
}

const actions = {
  tab(el) { readInputs(); ui.tab = el.dataset.tab; ui.message = ""; render(); },
  create() {
    const l = lang();
    const name = document.getElementById("gname").value.trim() || "Grassy";
    const country = document.getElementById("gcountry").value;
    const text = document.getElementById("gpaste").value;
    ui.name = name; ui.country = country; ui.paste = text;
    const r = parseCSV(text);
    if (r.error) { ui.message = t(l, r.error === "columns" ? "badColumns" : "nothing"); return render(); }
    const { events } = normalizeEvents(r.rows);
    if (events.length < 6) { ui.message = t(l, "needMore", { n: 6, have: events.length }); return render(); }
    ui.name = ui.paste = undefined;
    addGroup({ name, country, rows: r.rows, place: COUNTRIES[country].place });
  },
  sample() {
    const s = samples[Math.floor(Math.random() * samples.length)];
    addGroup({ name: s.label, country: s.country, rows: s.events, place: s.place, synthetic: true });
  },
  plan() { readInputs(); doPlan(); },
  async polish() {
    const base = state.smartUrl.replace(/\/+$/, "");
    try {
      const res = await fetch(`${base}/api/invite`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft: document.getElementById("invite").value, lang: lang() }) });
      const j = await res.json();
      if (res.ok && j.text) { ui.invite = j.text; ui.waUrl = whatsappUrl(j.text); render(); }
    } catch { /* offline: keep the plain invite */ }
  },
  copy() {
    const text = document.getElementById("invite").value;
    navigator.clipboard?.writeText(text).catch(() => {});
    const b = document.querySelector('[data-action="copy"]');
    if (b) b.textContent = t(lang(), "copied");
  },
  addEvent() {
    const g = current();
    const date = document.getElementById("ed").value;
    const att = document.getElementById("ea").value;
    if (!date || att === "" || Number(att) < 0) return;
    g.rows = g.rows.filter((r) => r.date !== date).concat([{ date, attendance: Number(att) }]);
    resetPlan(g); persist(); render();
  },
  remove(el) {
    const g = current();
    g.rows = g.rows.filter((r) => r.date !== el.dataset.date);
    resetPlan(g); persist(); render();
  },
  export() {
    const g = current();
    const blob = new Blob([toCSV(hydrate(g).events)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${g.name.replace(/[^\w-]+/g, "_")}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  },
  saveSmart() { state.smartUrl = document.getElementById("smart").value.trim(); persist(); render(); },
  deleteGroup() {
    if (!confirm(t(lang(), "confirmDelete"))) return;
    state.groups = state.groups.filter((g) => g.id !== state.current);
    state.current = state.groups[0]?.id ?? null;
    persist(); render();
  },
  newGroup() { state.current = null; render(); },
};

root.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action]");
  if (!el || el.dataset.action === "wa") return; // WhatsApp is a normal link
  e.preventDefault();
  actions[el.dataset.action]?.(el);
});
root.addEventListener("change", (e) => {
  if (e.target.id === "lang") {
    state.lang = e.target.value; persist();
    if (ui.result) { const top = ui.result.rows[ui.result.best]; ui.invite = buildInvite({ lang: lang(), group: current().name, date: top.date, startHour: ui.startHour, rain: ui.rain, sunOk: !top.sun?.tooLate }); ui.waUrl = whatsappUrl(ui.invite); }
    render();
  }
});
root.addEventListener("input", (e) => {
  if (e.target.id === "invite") ui.waUrl = whatsappUrl(e.target.value);
  const wa = root.querySelector('[data-action="wa"]');
  if (wa && e.target.id === "invite") wa.href = ui.waUrl;
});

async function boot() {
  try {
    [calendars, samples] = await Promise.all([fetch("data/calendar.json").then((r) => r.json()), fetch("data/sample.json").then((r) => r.json())]);
  } catch { /* offline first load without cache: the app still works with no holiday notes */ }
  if (current()) resetPlan(current());
  render();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
}
boot();
