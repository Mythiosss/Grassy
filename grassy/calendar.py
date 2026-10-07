"""Local-calendar features.

Demand in small shops moves with local events (Ramadan, Diwali, Dia de Muertos...).
Dates below are approximate public-calendar dates for 2023-2027. They are a starting
point: contributors are very welcome to add countries and fix dates (see CONTRIBUTING.md).

If the optional `holidays` package is installed, official public holidays for any
supported country code are added on top of the built-in table.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

CAP = 14  # "days to/since event" is capped so far-away events look the same

_YEARS = range(2023, 2028)


def _fixed(name: str, month: int, day: int, length: int = 1):
    """An event that falls on the same date every year."""
    out = []
    for y in _YEARS:
        start = pd.Timestamp(y, month, day)
        out.append((name, start, start + pd.Timedelta(days=length - 1)))
    return out


def _w(name: str, start: tuple, end: tuple):
    return (name, pd.Timestamp(*start), pd.Timestamp(*end))


EVENTS: dict[str, list[tuple[str, pd.Timestamp, pd.Timestamp]]] = {
    "ID": [
        _w("Ramadan", (2024, 3, 11), (2024, 4, 9)),
        _w("Ramadan", (2025, 3, 1), (2025, 3, 29)),
        _w("Ramadan", (2026, 2, 18), (2026, 3, 19)),
        _w("Eid al-Fitr", (2024, 4, 10), (2024, 4, 11)),
        _w("Eid al-Fitr", (2025, 3, 31), (2025, 4, 1)),
        _w("Eid al-Fitr", (2026, 3, 20), (2026, 3, 21)),
        _w("Eid al-Adha", (2024, 6, 17), (2024, 6, 17)),
        _w("Eid al-Adha", (2025, 6, 7), (2025, 6, 7)),
        _w("Eid al-Adha", (2026, 5, 27), (2026, 5, 27)),
        *_fixed("Independence Day", 8, 17),
        *_fixed("Christmas", 12, 25),
        *_fixed("New Year", 1, 1),
    ],
    "MX": [
        *_fixed("Independence Day", 9, 16),
        *_fixed("Day of the Dead", 11, 1, 2),
        *_fixed("Guadalupe Day", 12, 12),
        *_fixed("Christmas", 12, 25),
        *_fixed("New Year", 1, 1),
    ],
    "IN": [
        _w("Holi", (2024, 3, 25), (2024, 3, 25)),
        _w("Holi", (2025, 3, 14), (2025, 3, 14)),
        _w("Holi", (2026, 3, 4), (2026, 3, 4)),
        _w("Diwali", (2024, 10, 31), (2024, 11, 2)),
        _w("Diwali", (2025, 10, 20), (2025, 10, 22)),
        _w("Diwali", (2026, 11, 8), (2026, 11, 10)),
        *_fixed("Independence Day", 8, 15),
        *_fixed("Republic Day", 1, 26),
    ],
    "KE": [
        *_fixed("Madaraka Day", 6, 1),
        *_fixed("Mashujaa Day", 10, 20),
        *_fixed("Jamhuri Day", 12, 12),
        *_fixed("Christmas", 12, 25),
        *_fixed("New Year", 1, 1),
    ],
}

SUPPORTED_COUNTRIES = sorted(EVENTS)


def _optional_public_holidays(country: str):
    """Official public holidays via the optional `holidays` package (if installed)."""
    try:
        import holidays  # type: ignore
    except ImportError:
        return []
    try:
        cal = holidays.country_holidays(country, years=list(_YEARS))
    except Exception:  # unknown country code
        return []
    return [(str(name), pd.Timestamp(d), pd.Timestamp(d)) for d, name in sorted(cal.items())]


class EventCalendar:
    """Answers: is this day inside an event, and how close is the nearest one?"""

    def __init__(self, country: str = "ID"):
        self.country = country.upper()
        windows = list(EVENTS.get(self.country, []))
        known = {(n, s) for n, s, _ in windows}
        for n, s, e in _optional_public_holidays(self.country):
            if (n, s) not in known:
                windows.append((n, s, e))
        self.windows = sorted(windows, key=lambda w: w[1])

    def features(self, d) -> dict:
        d = pd.Timestamp(d).normalize()
        in_event = in_season = 0
        to_next = since_last = CAP
        # "inside an event" and "distance to the next/last one" are independent signals:
        # the days just before Eid still count down while Ramadan is in progress.
        for _, s, e in self.windows:
            if s <= d <= e:
                in_event = 1
                in_season = 1 if (e - s).days >= 5 else in_season
            if s > d:
                to_next = min(to_next, (s - d).days)
            if e < d:
                since_last = min(since_last, (d - e).days)
        return {
            "in_event": in_event,
            "in_season": in_season,
            "days_to_event": min(to_next, CAP),
            "days_since_event": min(since_last, CAP),
        }

    def next_event(self, d, within: int = 7):
        """(name, days_away) of the next event starting within `within` days, else None."""
        d = pd.Timestamp(d).normalize()
        best = None
        for name, s, _ in self.windows:
            gap = (s - d).days
            if 0 < gap <= within and (best is None or gap < best[1]):
                best = (name, gap)
        return best

    def event_near(self, d, within: int = 3):
        """(name, signed_days) of the closest event to `d`, or None.

        signed_days is 0 if `d` is inside the event, positive if the event starts that many
        days later, negative if it ended that many days earlier. Ties go to the shorter,
        more specific event (Eid beats the month of Ramadan around it).
        """
        d = pd.Timestamp(d).normalize()
        best, best_key = None, None
        for name, s, e in self.windows:
            if s <= d <= e:
                gap = 0
            elif d < s:
                gap = (s - d).days
            else:
                gap = -((d - e).days)
            if abs(gap) <= within:
                key = (abs(gap), (e - s).days)
                if best_key is None or key < best_key:
                    best, best_key = (name, gap), key
        return best

    def in_season(self, d) -> bool:
        """True inside a long event window (more than 5 days: Ramadan, a festival month)."""
        return bool(self.features(d)["in_season"])

    def holiday_near(self, d, within: int = 1, max_len: int = 5) -> bool:
        """True if `d` is within `within` days of a SHORT event (a holiday, not a whole season)."""
        d = pd.Timestamp(d).normalize()
        for _, s, e in self.windows:
            if (e - s).days <= max_len and s - pd.Timedelta(days=within) <= d <= e + pd.Timedelta(days=within):
                return True
        return False

