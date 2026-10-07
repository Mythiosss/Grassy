// Sunrise, sunset and daylight length from latitude and longitude. Pure maths, no internet.
// NOAA solar calculator (about a minute of accuracy away from the poles). A line-for-line port of
// grassy/sun.py; tests/js/parity.test.mjs checks both agree.

import { toOrdinal } from "./dates.js";

const rad = (x) => (x * Math.PI) / 180;
const deg = (x) => (x * 180) / Math.PI;

/** place = { lat, lon, tz } with tz in hours east of UTC. Times are minutes after local midnight. */
export function sunTimes(iso, place) {
  const jd = toOrdinal(iso) + 1721424.5 + 0.5 - place.tz / 24; // Julian day at local noon
  const t = (jd - 2451545.0) / 36525.0;

  const meanLong = (((280.46646 + t * (36000.76983 + t * 0.0003032)) % 360) + 360) % 360;
  const meanAnom = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
  const m = rad(meanAnom);
  const eqCentre =
    Math.sin(m) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
    Math.sin(2 * m) * (0.019993 - 0.000101 * t) +
    Math.sin(3 * m) * 0.000289;
  const trueLong = meanLong + eqCentre;
  const omega = 125.04 - 1934.136 * t;
  const appLong = trueLong - 0.00569 - 0.00478 * Math.sin(rad(omega));
  const meanObliq = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60;
  const obliq = meanObliq + 0.00256 * Math.cos(rad(omega));
  const decl = Math.asin(Math.sin(rad(obliq)) * Math.sin(rad(appLong)));

  const y = Math.tan(rad(obliq / 2)) ** 2;
  const l0 = rad(meanLong);
  const eqTime =
    4 *
    deg(
      y * Math.sin(2 * l0) -
        2 * ecc * Math.sin(m) +
        4 * ecc * y * Math.sin(m) * Math.cos(2 * l0) -
        0.5 * y * y * Math.sin(4 * l0) -
        1.25 * ecc * ecc * Math.sin(2 * m),
    );

  const lat = rad(place.lat);
  const cosHa = Math.cos(rad(90.833)) / (Math.cos(lat) * Math.cos(decl)) - Math.tan(lat) * Math.tan(decl);
  if (cosHa > 1) return { sunrise: null, sunset: null, daylightMin: 0 }; // sun never rises
  if (cosHa < -1) return { sunrise: null, sunset: null, daylightMin: 1440 }; // sun never sets
  const ha = deg(Math.acos(cosHa));

  const solarNoon = 720 - 4 * place.lon - eqTime + place.tz * 60;
  return { sunrise: solarNoon - 4 * ha, sunset: solarNoon + 4 * ha, daylightMin: 8 * ha };
}

/** 372.4 minutes after midnight -> "06:12". */
export function hhmm(minutes) {
  const total = ((Math.round(minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}
