"""Turn a list of past events into a small tabular dataset (one row per event).

A group might only have 10-40 past events. So the feature set is small and every feature for
an event uses only information that was known BEFORE it happened: its date and start time,
the sun, the calendar, the rain forecast the organizer enters, and the group's own recent
turnout. Tests check that nothing about the event's own attendance leaks in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .calendar import EventCalendar
from .sun import Place, sun_times

FEATURES = [
    "dow",
    "start_hour",
    "start_after_sunrise_min",
    "end_before_sunset_min",
    "daylight_h",
    "rain",
    "in_event",
    "in_season",
    "days_to_event",
    "days_since_event",
    "gap_days",
    "last_att",
    "ma3",
]

MIN_EVENTS = 6  # the first event has no history; 5 training rows is the least that fits anything
DEFAULT_START = 7.0
DEFAULT_DURATION = 120.0


def parse_hhmm(value) -> float:
    """'07:30' -> 7.5. Accepts '7', '7:30', '07.30'. NaN if it can't be read."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return float("nan")
    text = str(value).strip().replace(".", ":")
    try:
        h, _, m = text.partition(":")
        return int(h) + (int(m) / 60 if m else 0.0)
    except ValueError:
        return float("nan")


def normalize_events(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean raw events into [date, attendance, start_hour, duration, rain] plus what was provided."""
    ev = pd.DataFrame(
        {"date": pd.to_datetime(df["date"]).dt.normalize(), "attendance": pd.to_numeric(df["attendance"], errors="coerce")}
    )
    meta = {"has_start": "start" in df, "has_duration": "duration" in df, "has_rain": "rain" in df}
    start = df["start"].map(parse_hhmm) if meta["has_start"] else pd.Series(np.nan, index=df.index)
    ev["start_hour"] = start.fillna(start.median() if start.notna().any() else DEFAULT_START)
    dur = pd.to_numeric(df["duration"], errors="coerce") if meta["has_duration"] else pd.Series(np.nan, index=df.index)
    ev["duration"] = dur.fillna(dur.median() if dur.notna().any() else DEFAULT_DURATION)
    rain = pd.to_numeric(df["rain"], errors="coerce") if meta["has_rain"] else pd.Series(0, index=df.index)
    ev["rain"] = (rain.fillna(0) > 0).astype(float)
    ev = ev.dropna(subset=["attendance"]).drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    return ev, meta


def event_row(history: pd.DataFrame, when, start_hour: float, duration: float, rain: float, cal: EventCalendar, place: Place | None) -> dict:
    """Features for an event on `when`. `history` must contain only events strictly before it."""
    when = pd.Timestamp(when).normalize()
    att = history["attendance"].to_numpy()
    sr, ss, daylight = 360.0, 1080.0, 12.0  # neutral defaults when no location is set
    if place is not None:
        st = sun_times(when.date(), place)
        daylight = st.daylight_min / 60
        if st.sunrise is not None:
            sr, ss = st.sunrise, st.sunset
    row = {
        "dow": when.dayofweek,
        "start_hour": start_hour,
        "start_after_sunrise_min": start_hour * 60 - sr,
        "end_before_sunset_min": ss - (start_hour * 60 + duration),
        "daylight_h": daylight,
        "rain": rain,
        "gap_days": (when - history["date"].iloc[-1]).days if len(history) else np.nan,
        "last_att": att[-1] if len(att) else np.nan,
        "ma3": att[-3:].mean() if len(att) else np.nan,
    }
    row.update(cal.features(when))
    return row


def build_training(events: pd.DataFrame, country: str, place: Place | None = None):
    """(X, y): one row per event, from the second event on (the first has no history)."""
    cal = EventCalendar(country)
    rows = []
    for i in range(1, len(events)):
        e = events.iloc[i]
        rows.append(event_row(events.iloc[:i], e["date"], e["start_hour"], e["duration"], e["rain"], cal, place))
    return pd.DataFrame(rows)[FEATURES], events["attendance"].iloc[1:].to_numpy(dtype=float)
