// Dates are plain "YYYY-MM-DD" strings everywhere. Arithmetic goes through ordinals
// (days since 0001-01-01, same as Python's date.toordinal) so time zones can never shift a date.

const ORD_1970 = 719163; // Python: date(1970, 1, 1).toordinal()

// Howard Hinnant's civil-date algorithms (public domain).
function daysFromCivil(y, m, d) {
  y -= m <= 2 ? 1 : 0;
  const era = Math.floor(y / 400);
  const yoe = y - era * 400;
  const doy = Math.floor((153 * ((m + 9) % 12) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

function civilFromDays(z) {
  z += 719468;
  const era = Math.floor(z / 146097);
  const doe = z - era * 146097;
  const yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524) - Math.floor(doe / 146096)) / 365);
  const doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
  const mp = Math.floor((5 * doy + 2) / 153);
  const d = doy - Math.floor((153 * mp + 2) / 5) + 1;
  const m = mp < 10 ? mp + 3 : mp - 9;
  return [yoe + era * 400 + (m <= 2 ? 1 : 0), m, d];
}

export function parseISO(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso));
  if (!m) throw new Error(`not a date: ${iso}`);
  const [y, mo, d] = [+m[1], +m[2], +m[3]];
  const back = civilFromDays(daysFromCivil(y, mo, d));
  if (back[0] !== y || back[1] !== mo || back[2] !== d) throw new Error(`not a real date: ${iso}`);
  return [y, mo, d];
}

export const toOrdinal = (iso) => daysFromCivil(...parseISO(iso)) + ORD_1970;

export function fromOrdinal(ordinal) {
  const [y, m, d] = civilFromDays(ordinal - ORD_1970);
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** Monday = 0 ... Sunday = 6, like Python's date.weekday(). */
export const weekday = (iso) => (toOrdinal(iso) - 1) % 7;
export const addDays = (iso, n) => fromOrdinal(toOrdinal(iso) + n);
export const diffDays = (a, b) => toOrdinal(a) - toOrdinal(b);
export const dayOf = (iso) => parseISO(iso)[2];
export const monthOf = (iso) => parseISO(iso)[1]; // 1..12

/** Today on THIS device, as YYYY-MM-DD. */
export function todayISO(now = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

/** Hours east of UTC on this device on a given date (handles daylight saving). */
export function deviceTzHours(iso) {
  const [y, m, d] = parseISO(iso);
  return -new Date(y, m - 1, d, 12).getTimezoneOffset() / 60;
}

/**
 * Read a date a person typed or pasted. Returns { iso, ambiguous } or null.
 * Accepts YYYY-MM-DD, YYYY/MM/DD, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY. When both numbers could be a
 * month we assume day-first (most of the world) and flag it so the screen can show what was read.
 */
export function parseDateFlexible(text) {
  const s = String(text ?? "").trim();
  let m = /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/.exec(s);
  let y, mo, d, ambiguous = false;
  if (m) {
    [y, mo, d] = [+m[1], +m[2], +m[3]];
  } else if ((m = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(s))) {
    let a = +m[1], b = +m[2];
    y = +m[3];
    if (a > 12) { d = a; mo = b; }
    else if (b > 12) { mo = a; d = b; }
    else { d = a; mo = b; ambiguous = a !== b; }
  } else {
    return null;
  }
  const iso = `${String(y).padStart(4, "0")}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  try { parseISO(iso); } catch { return null; }
  return { iso, ambiguous };
}
