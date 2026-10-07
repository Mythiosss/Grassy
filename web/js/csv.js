// Reading and writing the group's history as CSV (what people paste from a spreadsheet or chat).

import { parseDateFlexible } from "./dates.js";

const HINTS = {
  date: ["date", "tanggal", "tgl", "fecha", "tarehe", "day", "when"],
  attendance: ["attendance", "turnout", "people", "attended", "count", "total", "hadir", "peserta", "jumlah", "asistentes", "asistencia", "personas", "waliohudhuria", "idadi", "n"],
  start: ["start", "time", "mulai", "jam", "inicio", "hora", "kuanza", "saa"],
  duration: ["duration", "minutes", "mins", "durasi", "menit", "duracion", "muda"],
  rain: ["rain", "hujan", "lluvia", "mvua", "weather"],
};

export function detectDelimiter(line) {
  const counts = { ",": 0, ";": 0, "\t": 0 };
  let inQ = false;
  for (const ch of line) {
    if (ch === '"') inQ = !inQ;
    else if (!inQ && ch in counts) counts[ch]++;
  }
  const best = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  return best[1] > 0 ? best[0] : ",";
}

function splitLine(line, delim) {
  const out = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQ && line[i + 1] === '"') { cur += '"'; i++; } else inQ = !inQ;
    } else if (ch === delim && !inQ) { out.push(cur); cur = ""; } else cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

const norm = (s) => s.toLowerCase().replace(/[^a-záéíóúñ]/g, "");

function mapHeaders(cells) {
  const map = {};
  cells.forEach((c, i) => {
    const key = norm(c);
    for (const [field, words] of Object.entries(HINTS)) {
      if (!(field in map) && words.some((w) => key === w || (key.length > 3 && key.startsWith(w)))) map[field] = i;
    }
  });
  return map;
}

const RAIN_YES = ["1", "yes", "y", "true", "rain", "rainy", "hujan", "si", "sí", "ndiyo", "mvua"];

export function parseRain(v) {
  const s = String(v ?? "").trim().toLowerCase();
  if (!s) return 0;
  if (!Number.isNaN(Number(s))) return Number(s) > 0 ? 1 : 0;
  return RAIN_YES.includes(s) ? 1 : 0;
}

/**
 * -> { rows, skipped, ambiguousDates, error }.
 * rows: [{date, attendance, start?, duration?, rain?}]. skipped: lines that could not be read.
 */
export function parseCSV(text) {
  const lines = String(text ?? "").replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return { rows: [], skipped: 0, ambiguousDates: 0, error: "empty" };
  const delim = detectDelimiter(lines[0]);
  const head = splitLine(lines[0], delim);
  let map = mapHeaders(head);
  let body = lines.slice(1);
  if (!("date" in map) || !("attendance" in map)) {
    // No usable header: maybe the first line is data. Assume date, attendance[, start, duration, rain].
    if (parseDateFlexible(head[0])) {
      map = { date: 0, attendance: 1, start: 2, duration: 3, rain: 4 };
      body = lines;
    } else return { rows: [], skipped: 0, ambiguousDates: 0, error: "columns" };
  }
  const rows = [];
  let skipped = 0;
  let ambiguousDates = 0;
  for (const line of body) {
    const cells = splitLine(line, delim);
    const d = parseDateFlexible(cells[map.date]);
    const raw = (cells[map.attendance] ?? "").replace(/[^\d.]/g, "");
    const att = raw === "" ? NaN : Number(raw);
    if (!d || Number.isNaN(att) || att < 0) { skipped++; continue; }
    if (d.ambiguous) ambiguousDates++;
    const row = { date: d.iso, attendance: att };
    if ("start" in map && cells[map.start]) row.start = cells[map.start];
    if ("duration" in map && cells[map.duration]) row.duration = cells[map.duration];
    if ("rain" in map) row.rain = parseRain(cells[map.rain]);
    rows.push(row);
  }
  return { rows, skipped, ambiguousDates, error: rows.length ? null : "none" };
}

export function toCSV(events) {
  const hh = (h) => `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.round((h % 1) * 60)).padStart(2, "0")}`;
  const lines = ["date,attendance,start,duration,rain"];
  for (const e of events) lines.push([e.date, e.attendance, hh(e.start_hour), e.duration, e.rain].join(","));
  return lines.join("\n") + "\n";
}
