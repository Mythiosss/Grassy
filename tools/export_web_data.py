"""Export data the phone app shares with the Python engine, plus parity fixtures.

    python tools/export_web_data.py

Writes:
  web/data/calendar.json   local event windows (single source of truth: grassy/calendar.py)
  web/data/sample.json     SYNTHETIC sample groups for the app's "try a sample" button
  tests/fixtures/parity.json   Python's answers, which the JavaScript engine must reproduce
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `python tools/export_web_data.py` finds the grassy package

import pandas as pd  # noqa: E402

from grassy.calendar import EVENTS  # noqa: E402
from grassy.data import GROUPS, generate_group
from grassy.features import normalize_events, parse_hhmm
from grassy.predict import SIMPLE_MODELS, best_simple_model, effect_summary, predict
from grassy.sun import sun_times


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", path.relative_to(ROOT), f"({path.stat().st_size} bytes)")


def calendar_json() -> dict:
    return {
        country: [[name, s.date().isoformat(), e.date().isoformat()] for name, s, e in windows]
        for country, windows in EVENTS.items()
    }


def raw_rows(df: pd.DataFrame, drop: tuple[str, ...] = ()) -> list[dict]:
    out = df.drop(columns=[c for c in ("truth_special",) + drop if c in df]).copy()
    out["date"] = out["date"].dt.date.astype(str)
    return out.to_dict("records")


def sample_json() -> list[dict]:
    out = []
    for key, cfg in GROUPS.items():
        df = generate_group(key, n_events=80).tail(24)
        p = cfg["place"]
        out.append(
            {
                "key": key,
                "label": cfg["label"],
                "country": cfg["country"],
                "lang": cfg["lang"],
                "place": {"lat": p.lat, "lon": p.lon, "tz": p.tz},
                "synthetic": True,
                "events": raw_rows(df),
            }
        )
    return out


def parity_fixtures() -> dict:
    cases = []
    for key in ("beach_cleanup_id", "run_club_ke", "garden_group_in"):
        cfg = GROUPS[key]
        full = generate_group(key, n_events=60)
        for n_events, variant in ((9, "full"), (24, "full"), (24, "no_start"), (40, "no_rain_no_duration")):
            hist = full.tail(n_events).reset_index(drop=True)
            drop = {"full": (), "no_start": ("start",), "no_rain_no_duration": ("rain", "duration")}[variant]
            raw = raw_rows(hist, drop)
            events, _ = normalize_events(pd.DataFrame(raw))
            last = events["date"].iloc[-1]
            targets = [
                {"date": (last + pd.Timedelta(days=d)).date().isoformat(), "start": s, "duration": dur, "rain": r}
                for d, s, dur, r in ((6, "07:00", 150, 0), (7, "09:30", 150, 0), (13, "07:00", 90, 1), (14, "06:30", 120, 0))
            ]
            tg = [
                {"date": t["date"], "start_hour": parse_hhmm(t["start"]), "duration": t["duration"], "rain": float(t["rain"])}
                for t in targets
            ]
            expected = {}
            for m in SIMPLE_MODELS:
                preds = predict(events, cfg["country"], tg, model=m)
                expected[m] = [{"point": p.point, "low": p.low, "high": p.high} for p in preds]
            cases.append(
                {
                    "name": f"{key}/{n_events}/{variant}",
                    "country": cfg["country"],
                    "events": raw,
                    "targets": targets,
                    "expected": expected,
                    "best_simple_model": best_simple_model(events, cfg["country"]),
                    "effect_summary": effect_summary(events, cfg["country"]),
                }
            )
    sun = []
    for iso, lat, lon, tz in (
        ("2026-10-07", -8.65, 115.22, 8),
        ("2026-06-21", 51.5, -0.12, 1),
        ("2026-12-21", 51.5, -0.12, 0),
        ("2026-03-20", -0.18, -78.47, -5),
        ("2026-01-15", -1.29, 36.82, 3),
        ("2026-07-04", 19.43, -99.13, -6),
        ("2026-12-21", 69.65, 18.96, 1),
        ("2026-06-21", 69.65, 18.96, 2),
        ("2027-02-28", 12.97, 77.59, 5.5),
    ):
        st = sun_times(date.fromisoformat(iso), type("P", (), {"lat": lat, "lon": lon, "tz": tz})())
        sun.append({"date": iso, "lat": lat, "lon": lon, "tz": tz, "sunrise": st.sunrise, "sunset": st.sunset, "daylight_min": st.daylight_min})
    return {"cases": cases, "sun": sun}


if __name__ == "__main__":
    _write(ROOT / "web/data/calendar.json", calendar_json())
    _write(ROOT / "web/data/sample.json", sample_json())
    _write(ROOT / "tests/fixtures/parity.json", parity_fixtures())
