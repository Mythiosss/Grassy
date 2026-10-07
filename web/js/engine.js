// The prediction engine, running on the phone. A faithful port of the simple models in
// grassy/predict.py (tests/js/parity.test.mjs checks both give the same numbers).

import { toOrdinal, weekday } from "./dates.js";

export const MIN_EVENTS = 6;
export const SIMPLE_MODELS = ["mean_last5", "same_weekday", "effects"];
const MIN_ABS_HALFWIDTH = 2.0;
const MIN_REL_HALFWIDTH = 0.15;
const EFFECTS_LAMBDA = 2.0;
const ERR_WINDOW = 30;
const EFFECTS_MIN = 5;
const DEFAULT_START = 7.0;
const DEFAULT_DURATION = 120;

// ------------------------------------------------------------------ small numeric helpers
const mean = (a) => a.reduce((s, x) => s + x, 0) / a.length;

export function median(a) {
  const s = [...a].sort((x, y) => x - y);
  const n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

/** Same as numpy.quantile(a, q) with the default "linear" method. */
export function quantile(a, q) {
  const s = [...a].sort((x, y) => x - y);
  const pos = (s.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}

/** Solve A x = b by Gaussian elimination with partial pivoting (A is small and square). */
function solve(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    const piv = M[c][c];
    if (Math.abs(piv) < 1e-14) throw new Error("singular");
    for (let r = c + 1; r < n; r++) {
      const f = M[r][c] / piv;
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  const x = new Array(n).fill(0);
  for (let r = n - 1; r >= 0; r--) {
    let s = M[r][n];
    for (let k = r + 1; k < n; k++) s -= M[r][k] * x[k];
    x[r] = s / M[r][r];
  }
  return x;
}

// ------------------------------------------------------------------ cleaning
export function parseHHMM(value) {
  if (value === null || value === undefined || value === "") return NaN;
  const text = String(value).trim().replace(".", ":");
  const mt = /^(\d+)(?::(\d+))?$/.exec(text);
  if (!mt) return NaN;
  return +mt[1] + (mt[2] ? +mt[2] / 60 : 0);
}

/**
 * Raw rows -> [{date, attendance, start_hour, duration, rain}] sorted by date, one per date
 * (the last one wins). Missing start / duration become the group's median (or a default).
 */
export function normalizeEvents(rows) {
  const has = (k) => rows.some((r) => k in r);
  const meta = { has_start: has("start"), has_duration: has("duration"), has_rain: has("rain") };
  const startRaw = rows.map((r) => (meta.has_start ? parseHHMM(r.start) : NaN));
  const durRaw = rows.map((r) => {
    if (!meta.has_duration) return NaN;
    const v = r.duration === "" || r.duration === null ? NaN : Number(r.duration);
    return v;
  });
  const startMed = startRaw.some((x) => !Number.isNaN(x)) ? median(startRaw.filter((x) => !Number.isNaN(x))) : DEFAULT_START;
  const durMed = durRaw.some((x) => !Number.isNaN(x)) ? median(durRaw.filter((x) => !Number.isNaN(x))) : DEFAULT_DURATION;

  const byDate = new Map();
  rows.forEach((r, i) => {
    const att = r.attendance === "" || r.attendance === null ? NaN : Number(r.attendance);
    if (Number.isNaN(att)) return;
    const rainNum = meta.has_rain && r.rain !== "" && r.rain !== null ? Number(r.rain) : 0;
    byDate.set(r.date, {
      date: r.date,
      attendance: att,
      start_hour: Number.isNaN(startRaw[i]) ? startMed : startRaw[i],
      duration: Number.isNaN(durRaw[i]) ? durMed : durRaw[i],
      rain: rainNum > 0 ? 1 : 0,
    });
  });
  const events = [...byDate.values()].sort((a, b) => toOrdinal(a.date) - toOrdinal(b.date));
  return { events, meta };
}

// ------------------------------------------------------------------ simple averages
function baselinePoint(model, history, when) {
  if (model === "same_weekday") {
    const wd = weekday(when);
    const same = history.filter((e) => weekday(e.date) === wd).slice(-4);
    if (same.length) return mean(same.map((e) => e.attendance));
  }
  return mean(history.slice(-5).map((e) => e.attendance));
}

// ------------------------------------------------------------------ effects model
function usualDow(hist) {
  const counts = new Array(7).fill(0);
  hist.forEach((e) => counts[weekday(e.date)]++);
  let best = 0;
  for (let i = 1; i < 7; i++) if (counts[i] > counts[best]) best = i;
  return best;
}

const clip = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

function effectRow(cal, when, startHour, rain, s0, usual) {
  return [
    1,
    rain ? 1 : 0,
    clip((startHour - s0) / 2, -2, 2),
    cal.holidayNear(when) ? 1 : 0,
    cal.inSeason(when) ? 1 : 0,
    weekday(when) !== usual ? 1 : 0,
  ];
}

function fitEffects(hist, cal, lam = EFFECTS_LAMBDA) {
  const s0 = median(hist.map((e) => e.start_hour));
  const usual = usualDow(hist);
  const X = hist.map((e) => effectRow(cal, e.date, e.start_hour, e.rain, s0, usual));
  const y = hist.map((e) => e.attendance);
  const k = X[0].length;
  const beta = new Array(k).fill(0);
  beta[0] = Math.log(Math.max(mean(y), 0.1));
  for (let it = 0; it < 30; it++) {
    const mu = X.map((row) => Math.exp(clip(row.reduce((s, v, j) => s + v * beta[j], 0), -20, 20)));
    const grad = new Array(k).fill(0);
    const hess = Array.from({ length: k }, () => new Array(k).fill(0));
    X.forEach((row, i) => {
      for (let a = 0; a < k; a++) {
        grad[a] += row[a] * (y[i] - mu[i]);
        for (let b = 0; b < k; b++) hess[a][b] += row[a] * row[b] * mu[i];
      }
    });
    for (let a = 1; a < k; a++) {
      grad[a] -= lam * beta[a];
      hess[a][a] += lam;
    }
    const step = solve(hess, grad);
    for (let a = 0; a < k; a++) beta[a] += step[a];
    if (Math.max(...step.map(Math.abs)) < 1e-10) break;
  }
  return { beta, s0, usual };
}

function effectsPoint(fit, cal, when, startHour, rain) {
  const row = effectRow(cal, when, startHour, rain, fit.s0, fit.usual);
  return Math.exp(clip(row.reduce((s, v, j) => s + v * fit.beta[j], 0), -20, 20));
}

/** How many times more (or fewer) people come per factor, or null when there is too little data. */
export function effectSummary(events, cal) {
  if (events.length < EFFECTS_MIN) return null;
  const { beta } = fitEffects(events, cal);
  const names = ["rain", "later_start_2h", "holiday", "season", "off_day"];
  return Object.fromEntries(names.map((n, i) => [n, Math.exp(beta[i + 1])]));
}

// ------------------------------------------------------------------ ranges and auto-choice
function oneStepErrors(model, events, cal) {
  const n = events.length;
  const errs = [];
  for (let i = Math.max(EFFECTS_MIN, n - ERR_WINDOW); i < n; i++) {
    const hist = events.slice(0, i);
    const e = events[i];
    const p =
      model === "effects"
        ? effectsPoint(fitEffects(hist, cal), cal, e.date, e.start_hour, e.rain)
        : baselinePoint(model, hist, e.date);
    errs.push(Math.abs(e.attendance - p));
  }
  return errs;
}

function halfwidth(errs, typical) {
  const hw = errs.length >= 3 ? quantile(errs, 0.8) : 0.4 * typical;
  return Math.max(hw, MIN_ABS_HALFWIDTH, MIN_REL_HALFWIDTH * typical);
}

/** The simple model that would have predicted this group's recent events best (ties: simpler). */
export function bestSimpleModel(events, cal) {
  if (events.length - EFFECTS_MIN < 3) return "mean_last5";
  const score = Object.fromEntries(SIMPLE_MODELS.map((m) => [m, mean(oneStepErrors(m, events, cal))]));
  let best = SIMPLE_MODELS[0];
  for (const m of SIMPLE_MODELS.slice(1)) if (score[m] < score[best] - 1e-12) best = m;
  return best;
}

/**
 * Predict each target { date, start_hour, rain }. model: "auto" or one of SIMPLE_MODELS.
 * Returns [{ date, point, low, high, model, n }].
 */
export function predict(events, cal, targets, model = "auto") {
  if (events.length < MIN_EVENTS) throw new Error(`need at least ${MIN_EVENTS} past events, got ${events.length}`);
  const m = model === "auto" ? bestSimpleModel(events, cal) : model;
  if (!SIMPLE_MODELS.includes(m)) throw new Error(`unknown model ${m}`);
  const typical = mean(events.map((e) => e.attendance));
  const hw = halfwidth(oneStepErrors(m, events, cal), typical);
  const fit = m === "effects" ? fitEffects(events, cal) : null;
  return targets.map((t) => {
    const p = fit ? effectsPoint(fit, cal, t.date, t.start_hour, t.rain) : baselinePoint(m, events, t.date);
    return { date: t.date, point: p, low: Math.max(0, p - hw), high: p + hw, model: m, n: events.length };
  });
}
