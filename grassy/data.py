"""Synthetic outdoor-group event histories.

EVERYTHING produced here is synthetic: four invented groups in four countries whose turnout
follows plausible patterns (weekday, local holidays, rain, start time vs. heat, the odd
"a school joined us" spike). It exists so the predictor can be tested and benchmarked
without anyone's private data. Never present it as real.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .calendar import EventCalendar
from .sun import Place

GROUPS = {
    "beach_cleanup_id": {
        "label": "Beach clean-up crew in Bali (Indonesia)",
        "country": "ID",
        "place": Place(-8.65, 115.22, 8),
        "usual_dow": 6,  # Sunday
        "base": 28,
        "start_choices": [(6.5, 0.4), (7.0, 0.3), (8.0, 0.15), (9.5, 0.15)],
        "duration": 150,
        "heat_penalty": 0.35,
        "rain_prob": 0.30,
        "rain_mult": 0.55,
        "event_mult": {"Ramadan": 0.8, "Eid al-Fitr": 0.4, "Independence Day": 1.6, "Christmas": 0.6},
        "lang": "id",
    },
    "run_club_ke": {
        "label": "Saturday run club in Nairobi (Kenya)",
        "country": "KE",
        "place": Place(-1.29, 36.82, 3),
        "usual_dow": 5,  # Saturday
        "base": 45,
        "start_choices": [(6.0, 0.3), (6.5, 0.4), (7.5, 0.2), (9.0, 0.1)],
        "duration": 90,
        "heat_penalty": 0.10,
        "rain_prob": 0.20,
        "rain_mult": 0.75,
        "event_mult": {"Jamhuri Day": 1.15, "Christmas": 0.7, "New Year": 0.6, "Mashujaa Day": 1.1},
        "lang": "sw",
    },
    "hiking_club_mx": {
        "label": "Weekend hiking club in Mexico City (Mexico)",
        "country": "MX",
        "place": Place(19.43, -99.13, -6),
        "usual_dow": 6,
        "base": 18,
        "start_choices": [(7.0, 0.3), (8.0, 0.4), (9.0, 0.2), (10.0, 0.1)],
        "duration": 240,
        "heat_penalty": 0.15,
        "rain_prob": 0.25,
        "rain_mult": 0.5,
        "event_mult": {"Day of the Dead": 0.7, "Independence Day": 0.75, "Christmas": 0.5, "New Year": 0.6},
        "lang": "es",
    },
    "garden_group_in": {
        "label": "Community garden volunteers in Bengaluru (India)",
        "country": "IN",
        "place": Place(12.97, 77.59, 5.5),
        "usual_dow": 5,
        "base": 14,
        "start_choices": [(7.0, 0.3), (7.5, 0.4), (9.0, 0.2), (10.5, 0.1)],
        "duration": 120,
        "heat_penalty": 0.25,
        "rain_prob": 0.25,
        "rain_mult": 0.6,
        "event_mult": {"Diwali": 0.6, "Holi": 0.65, "Independence Day": 1.3, "Republic Day": 1.3},
        "lang": "en",
    },
}


def _hhmm(hour: float) -> str:
    return f"{int(hour):02d}:{int(round((hour % 1) * 60)):02d}"


def generate_group(kind: str, n_events: int = 80, end: str = "2026-10-06", seed: int = 7) -> pd.DataFrame:
    """DataFrame[date, attendance, start, duration, rain, truth_special] of past events.

    Events are roughly weekly with gaps and the odd shift to the other weekend day.
    `truth_special` marks injected "a school/company joined" spikes (never read by the predictor).
    """
    if kind not in GROUPS:
        raise ValueError(f"unknown group {kind!r}; choose from {sorted(GROUPS)}")
    cfg = GROUPS[kind]
    rng = np.random.default_rng([seed, sum(map(ord, kind))])
    cal = EventCalendar(cfg["country"])

    end_d = pd.Timestamp(end).date()
    last = end_d - timedelta(days=(end_d.weekday() - cfg["usual_dow"]) % 7)  # latest usual weekday <= end
    dates: list[date] = []
    week = 0
    while len(dates) < n_events and week < n_events * 3:
        d = last - timedelta(days=7 * week)
        week += 1
        if rng.random() < 0.15:  # skipped week
            continue
        if rng.random() < 0.10:  # held on the other weekend day instead
            d = d + timedelta(days=1 if cfg["usual_dow"] == 5 else -1)
        dates.append(d)
    dates = sorted(set(dates))

    starts, weights = zip(*cfg["start_choices"])
    rows = []
    for i, d in enumerate(dates):
        ts = pd.Timestamp(d)
        start = float(rng.choice(starts, p=np.array(weights) / sum(weights)))
        rain = int(rng.random() < cfg["rain_prob"])
        mean = cfg["base"] * (1 + 0.002 * i)  # slow growth
        if ts.dayofweek != cfg["usual_dow"]:
            mean *= 0.8
        for name, s, e in cal.windows:
            if s <= ts <= e and name in cfg["event_mult"]:
                mean *= cfg["event_mult"][name]
        mean *= 1 - cfg["heat_penalty"] * float(np.clip((start - 8.0) / 2.5, 0, 1))
        if rain:
            mean *= cfg["rain_mult"]
        special = rng.random() < 0.04
        if special:
            mean *= 2.5
        lam = mean * rng.gamma(8.0, 1 / 8.0)  # extra day-to-day variation
        rows.append(
            {
                "date": ts,
                "attendance": int(rng.poisson(lam)),
                "start": _hhmm(start),
                "duration": cfg["duration"],
                "rain": rain,
                "truth_special": special,
            }
        )
    return pd.DataFrame(rows)
