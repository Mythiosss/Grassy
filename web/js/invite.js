// The invite message, written from facts we know. No AI needed offline; Smart mode may reword it.

import { weekday, dayOf, monthOf } from "./dates.js";
import { t, weekdayName, monthName } from "./i18n.js";
import { hhmm } from "./sun.js";

export function buildInvite({ lang, group, date, startHour, rain = false, sunOk = true }) {
  const lines = [
    t(lang, "invHeader", { group }),
    t(lang, "invLine", {
      day: weekdayName(lang, weekday(date)),
      d: dayOf(date),
      mon: monthName(lang, monthOf(date)),
      time: hhmm(startHour * 60),
    }),
    t(lang, "invBring"),
  ];
  if (sunOk) lines.push(t(lang, "invDark"));
  if (rain) lines.push(t(lang, "invRain"));
  return lines.join("\n");
}

export const whatsappUrl = (text) => `https://wa.me/?text=${encodeURIComponent(text)}`;
