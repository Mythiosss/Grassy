// Pure state -> HTML. No DOM access, so it can be tested in Node. Every piece of user text goes
// through esc().

import { t, LANGS, weekdayName, monthName } from "./i18n.js";
import { weekday, dayOf, monthOf, diffDays } from "./dates.js";
import { hhmm } from "./sun.js";
import { MIN_EVENTS } from "./engine.js";

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export const COUNTRIES = {
  ID: { name: "Indonesia", place: { lat: -8.65, lon: 115.22, tz: 8 } },
  KE: { name: "Kenya", place: { lat: -1.29, lon: 36.82, tz: 3 } },
  MX: { name: "México", place: { lat: 19.43, lon: -99.13, tz: -6 } },
  IN: { name: "India", place: { lat: 12.97, lon: 77.59, tz: 5.5 } },
};

const fmtDate = (lang, iso) => `${weekdayName(lang, weekday(iso)).slice(0, 3)} ${dayOf(iso)} ${monthName(lang, monthOf(iso))}`;
const hoursToTime = (h) => hhmm(h * 60);
const fxText = (lang, x) => {
  if (Math.abs(x - 1) < 0.05) return t(lang, "noEffect");
  return x > 1 ? t(lang, "more", { x: x.toFixed(1) }) : t(lang, "fewer", { x: x.toFixed(1) });
};

function tabs(lang, tab) {
  const item = (id, label) => `<button class="tab${tab === id ? " on" : ""}" data-action="tab" data-tab="${id}">${esc(label)}</button>`;
  return `<nav class="tabs">${item("plan", t(lang, "plan"))}${item("history", t(lang, "history"))}${item("settings", t(lang, "settings"))}</nav>`;
}

export function viewWelcome(lang, ui = {}) {
  const countryOpts = Object.entries(COUNTRIES)
    .map(([k, c]) => `<option value="${k}"${ui.country === k ? " selected" : ""}>${esc(c.name)}</option>`)
    .join("");
  return `<main class="screen">
  <h1 class="logo">Grassy</h1>
  <p class="lead">${esc(t(lang, "tagline"))}</p>
  <section class="card">
    <h2>${esc(t(lang, "newGroup"))}</h2>
    <label>${esc(t(lang, "groupName"))}<input id="gname" value="${esc(ui.name ?? "")}" autocomplete="off"></label>
    <label>${esc(t(lang, "country"))}<select id="gcountry">${countryOpts}</select></label>
    <label>${esc(t(lang, "pasteHistory"))}<textarea id="gpaste" rows="6" placeholder="${esc(t(lang, "pasteHint"))}">${esc(ui.paste ?? "")}</textarea></label>
    <button class="primary" data-action="create">${esc(t(lang, "load"))}</button>
    ${ui.message ? `<p class="msg" role="status">${esc(ui.message)}</p>` : ""}
  </section>
  <section class="card">
    <button data-action="sample">${esc(t(lang, "useSample"))}</button>
  </section>
  <p class="foot">${esc(t(lang, "offline"))}</p>
  ${langPicker(lang)}
</main>`;
}

function langPicker(lang) {
  return `<label class="lang">${esc(t(lang, "language"))}
    <select id="lang">${Object.entries(LANGS).map(([k, v]) => `<option value="${k}"${k === lang ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`;
}

export function viewPlan(lang, group, ui, today) {
  const n = group.events.length;
  const header = `<header class="gh"><h1>${esc(group.name)}</h1>${group.synthetic ? `<span class="pill">${esc(t(lang, "sample"))}</span>` : ""}</header>`;
  if (n < MIN_EVENTS) {
    return `${header}<p class="msg">${esc(t(lang, "needMore", { n: MIN_EVENTS, have: n }))}</p>`;
  }
  const chips = ui.dates
    .map(
      (d) => `<label class="chip"><input type="checkbox" data-date="${esc(d)}"${ui.picked.includes(d) ? " checked" : ""}>${esc(fmtDate(lang, d))}</label>`,
    )
    .join("");
  const form = `<section class="card">
    <h2>${esc(t(lang, "whichDates"))}</h2>
    <div class="chips">${chips}</div>
    <div class="row">
      <label>${esc(t(lang, "startTime"))}<input id="start" type="time" value="${esc(hoursToTime(ui.startHour))}"></label>
      <label>${esc(t(lang, "durationMin"))}<input id="dur" type="number" min="15" step="15" value="${esc(ui.duration)}"></label>
    </div>
    <label class="check"><input id="rain" type="checkbox"${ui.rain ? " checked" : ""}> ${esc(t(lang, "rainExpected"))}</label>
    <button class="primary" data-action="plan">${esc(t(lang, "planIt"))}</button>
  </section>`;
  return `${header}${form}${ui.result ? viewResult(lang, group, ui, today) : ""}`;
}

function viewResult(lang, group, ui, today) {
  const r = ui.result;
  const top = r.rows[r.best];
  const spread = Math.max(...r.rows.map((x) => x.point)) - Math.min(...r.rows.map((x) => x.point));
  const showBest = spread >= 0.5; // equal predictions: no date is 'best'
  const rows = r.rows
    .map((row, i) => {
      const ev = row.event
        ? `<div class="sub">${esc(
            row.event.gap === 0
              ? t(lang, "nearDuring", { name: row.event.name })
              : t(lang, "near", {
                  name: row.event.name,
                  when: row.event.gap > 0 ? t(lang, "inDays", { n: row.event.gap }) : t(lang, "daysAgo", { n: -row.event.gap }),
                }),
          )}</div>`
        : "";
      const sun = row.sun?.tooLate ? `<div class="sub warn">${esc(t(lang, "tooLate"))}</div>` : row.sun?.tooEarly ? `<div class="sub warn">${esc(t(lang, "tooEarly", { s: hhmm(row.sun.sunrise) }))}</div>` : "";
      return `<li class="res${showBest && i === r.best ? " best" : ""}">
        <div class="d">${esc(fmtDate(lang, row.date))}${showBest && i === r.best ? ` <span class="pill ok">${esc(t(lang, "best"))}</span>` : ""}</div>
        <div class="n">${Math.round(row.point)}</div>
        <div class="sub">${esc(t(lang, "range", { low: Math.round(row.low), high: Math.round(row.high) }))}</div>${ev}${sun}</li>`;
    })
    .join("");
  const adv = top.sun
    ? `<p>${esc(t(lang, "startBy", { t: hoursToTime(top.sun.latestStart), m: 30, s: hhmm(top.sun.sunset) }))}</p>`
    : "";
  const fx = r.effects
    ? `<details class="card"><summary>${esc(t(lang, "learned"))}</summary><ul class="fx">
        <li><span>${esc(t(lang, "fx_rain"))}</span><b>${esc(fxText(lang, r.effects.rain))}</b></li>
        <li><span>${esc(t(lang, "fx_later"))}</span><b>${esc(fxText(lang, r.effects.later_start_2h))}</b></li>
        <li><span>${esc(t(lang, "fx_holiday"))}</span><b>${esc(fxText(lang, r.effects.holiday))}</b></li>
        <li><span>${esc(t(lang, "fx_season"))}</span><b>${esc(fxText(lang, r.effects.season))}</b></li>
        <li><span>${esc(t(lang, "fx_off"))}</span><b>${esc(fxText(lang, r.effects.off_day))}</b></li></ul></details>`
    : "";
  const smart = ui.smartNote ? `<p class="sub">${esc(ui.smartNote)}</p>` : "";
  return `<section class="card result">
    <h2>${esc(t(lang, "expected"))}</h2>
    <ul class="results">${rows}</ul>
    <p><b>${esc(t(lang, "bring", { n: r.supplies }))}</b></p>
    <p>${esc(t(lang, "ifRain", { n: Math.round(r.rainScenario.point) }))}</p>
    ${adv}
    <p class="sub">${esc(t(lang, `conf_${r.confidence}`, { n: r.rows[0].n }))}</p>
    <p class="sub">${esc(t(lang, "model"))}: ${esc(t(lang, `m_${r.model}`))}</p>${smart}
  </section>
  ${fx}
  <section class="card">
    <h2>${esc(t(lang, "invite"))}</h2>
    <textarea id="invite" rows="5">${esc(ui.invite ?? "")}</textarea>
    <div class="row">${ui.smartUrl ? `<button data-action="polish">${esc(t(lang, "polish"))}</button>` : ""}<button data-action="copy">${esc(t(lang, "copy"))}</button>
    <a class="btn primary" data-action="wa" href="${esc(ui.waUrl ?? "#")}" target="_blank" rel="noopener">${esc(t(lang, "shareWa"))}</a></div>
  </section>`;
}

export function viewHistory(lang, group, ui = {}) {
  const items = [...group.events]
    .reverse()
    .map(
      (e) => `<li><span>${esc(fmtDate(lang, e.date))} ${esc(e.date.slice(0, 4))}</span><b>${esc(e.attendance)}</b>${e.rain ? '<span class="pill">☂</span>' : ""}
        <button class="x" data-action="remove" data-date="${esc(e.date)}" aria-label="${esc(t(lang, "remove"))}">×</button></li>`,
    )
    .join("");
  return `<section class="card"><h2>${esc(t(lang, "addEvent"))}</h2>
    <div class="row"><label>${esc(t(lang, "date"))}<input id="ed" type="date"></label>
    <label>${esc(t(lang, "howMany"))}<input id="ea" type="number" min="0" inputmode="numeric"></label></div>
    <button class="primary" data-action="addEvent">${esc(t(lang, "add"))}</button>
    ${ui.message ? `<p class="msg" role="status">${esc(ui.message)}</p>` : ""}</section>
  <section class="card"><ul class="hist">${items}</ul>
    <button data-action="export">${esc(t(lang, "export"))}</button></section>`;
}

export function viewSettings(lang, state, group, ui = {}) {
  return `<section class="card">${langPicker(lang)}</section>
  <section class="card"><h2>${esc(t(lang, "smart"))}</h2>
    <label>${esc(t(lang, "smartUrl"))}<input id="smart" inputmode="url" placeholder="https://" value="${esc(state.smartUrl ?? "")}"></label>
    <p class="sub">${esc(t(lang, "smartHelp"))}</p>
    <button data-action="saveSmart">${esc(t(lang, "load"))}</button></section>
  <section class="card"><button class="danger" data-action="deleteGroup">${esc(t(lang, "deleteGroup"))}</button>
    <button data-action="newGroup">${esc(t(lang, "newGroup"))}</button></section>
  <p class="foot">${esc(t(lang, "offline"))}</p>`;
}

export function viewApp(lang, state, group, ui, today) {
  const body =
    ui.tab === "history" ? viewHistory(lang, group, ui) : ui.tab === "settings" ? viewSettings(lang, state, group, ui) : viewPlan(lang, group, ui, today);
  const warn = ui.notSaved ? `<p class="msg warn">${esc(t(lang, "notSaved"))}</p>` : "";
  return `<main class="screen">${warn}${body}</main>${tabs(lang, ui.tab)}`;
}

export { diffDays };
