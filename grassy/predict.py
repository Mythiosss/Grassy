"""Predict turnout for planned events: TabPFN as the headline model, honest baselines beside it.

Models
------
tabpfn        TabPFNRegressor (Prior Labs tabular foundation model). `pip install tabpfn`.
effects       a small, transparent model that learns how much rain, a late start, a holiday, a
              holiday season or an off-day shifts YOUR group's turnout (Poisson regression with
              shrinkage). The phone app runs the same model offline.
mean_last5    average turnout of the last 5 events.
same_weekday  average turnout of the last 4 events on the same weekday.
gbr           scikit-learn gradient boosting on the full feature table (comparison only; its
              ranges are overconfident on tiny histories, see the README).
auto          tabpfn if installed; otherwise whichever of effects / mean_last5 / same_weekday would
              have predicted this group's own recent events best. The model used is always reported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calendar import EventCalendar
from .features import FEATURES, MIN_EVENTS, build_training, event_row
from .sun import Place

MODELS = ("tabpfn", "effects", "mean_last5", "same_weekday", "gbr")
SIMPLE_MODELS = ("mean_last5", "same_weekday", "effects")  # what auto chooses between offline
MIN_ABS_HALFWIDTH = 2.0  # people
MIN_REL_HALFWIDTH = 0.15  # of typical turnout: no prediction is perfectly certain
EFFECTS_LAMBDA = 2.0  # shrinkage: effects are pulled toward "no effect" unless the data insists
ERR_WINDOW = 30  # how many recent one-step errors are used for ranges and for auto-selection
EFFECTS_MIN = 5  # fewest past events the effects model is fitted on


def tabpfn_available() -> bool:
    try:
        import tabpfn  # noqa: F401
    except Exception:
        return False
    return True


@dataclass
class Prediction:
    date: pd.Timestamp
    point: float
    low: float
    high: float
    model: str
    n_events: int

    def as_row(self) -> dict:
        return {
            "date": self.date.date().isoformat(),
            "weekday": int(self.date.dayofweek),
            "people": round(self.point),
            "low": round(self.low),
            "high": round(self.high),
        }


# --------------------------------------------------------------------- simple averages
def _baseline_point(model: str, history: pd.DataFrame, when: pd.Timestamp) -> float:
    att = history["attendance"]
    if model == "same_weekday":
        same = history[history["date"].dt.dayofweek == when.dayofweek]["attendance"].iloc[-4:]
        if len(same):
            return float(same.mean())
    return float(att.iloc[-5:].mean())


# --------------------------------------------------------------------- effects model
def _usual_dow(hist: pd.DataFrame) -> int:
    counts = np.bincount(hist["date"].dt.dayofweek.to_numpy(), minlength=7)
    return int(np.argmax(counts))  # ties -> smallest weekday number


def _effect_row(when, start_hour: float, rain: float, s0: float, usual: int, cal: EventCalendar) -> list[float]:
    d = pd.Timestamp(when).normalize()
    return [
        1.0,
        float(rain),
        float(np.clip((start_hour - s0) / 2.0, -2.0, 2.0)),
        float(cal.holiday_near(d)),
        float(cal.in_season(d)),
        float(d.dayofweek != usual),
    ]


def _fit_effects(hist: pd.DataFrame, cal: EventCalendar, lam: float = EFFECTS_LAMBDA):
    """Poisson regression (log link) with a ridge penalty on every effect except the intercept."""
    s0 = float(np.median(hist["start_hour"]))
    usual = _usual_dow(hist)
    X = np.array(
        [_effect_row(r.date, r.start_hour, r.rain, s0, usual, cal) for r in hist.itertuples()], dtype=float
    )
    y = hist["attendance"].to_numpy(dtype=float)
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(max(float(y.mean()), 0.1))
    pen = np.eye(X.shape[1]) * lam
    pen[0, 0] = 0.0
    for _ in range(30):
        mu = np.exp(np.clip(X @ beta, -20, 20))
        grad = X.T @ (y - mu) - pen @ beta
        hess = X.T @ (X * mu[:, None]) + pen
        step = np.linalg.solve(hess, grad)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return beta, s0, usual


def _effects_point(beta, s0, usual, cal, when, start_hour, rain) -> float:
    row = np.array(_effect_row(when, start_hour, rain, s0, usual, cal))
    return float(np.exp(np.clip(row @ beta, -20, 20)))


def effect_summary(events: pd.DataFrame, country: str) -> dict | None:
    """Plain-language effects: how many times more (or fewer) people come, per factor."""
    if len(events) < EFFECTS_MIN:
        return None
    cal = EventCalendar(country)
    beta, _, _ = _fit_effects(events, cal)
    names = ["rain", "later_start_2h", "holiday", "season", "off_day"]
    return {n: float(np.exp(b)) for n, b in zip(names, beta[1:])}


# --------------------------------------------------------------------- error window, intervals, auto
def _one_step_errors(model: str, events: pd.DataFrame, cal: EventCalendar) -> list[float]:
    """|actual - predicted| for the most recent events, each predicted only from earlier ones."""
    n = len(events)
    errs = []
    for i in range(max(EFFECTS_MIN, n - ERR_WINDOW), n):
        hist, e = events.iloc[:i], events.iloc[i]
        if model == "effects":
            beta, s0, usual = _fit_effects(hist, cal)
            p = _effects_point(beta, s0, usual, cal, e["date"], e["start_hour"], e["rain"])
        else:
            p = _baseline_point(model, hist, e["date"])
        errs.append(abs(float(e["attendance"]) - p))
    return errs


def _halfwidth(errs: list[float], typical: float) -> float:
    hw = float(np.quantile(errs, 0.8)) if len(errs) >= 3 else 0.4 * typical
    return max(hw, MIN_ABS_HALFWIDTH, MIN_REL_HALFWIDTH * typical)


def best_simple_model(events: pd.DataFrame, country: str) -> str:
    """Which simple model would have predicted this group's recent events best (ties: simpler wins)."""
    cal = EventCalendar(country)
    if len(events) - EFFECTS_MIN < 3:
        return "mean_last5"
    scores = {m: float(np.mean(_one_step_errors(m, events, cal))) for m in SIMPLE_MODELS}
    best = SIMPLE_MODELS[0]
    for m in SIMPLE_MODELS[1:]:
        if scores[m] < scores[best] - 1e-12:
            best = m
    return best


def resolve_model(name: str, events: pd.DataFrame | None = None, country: str = "ID") -> str:
    if name == "auto":
        if tabpfn_available():
            return "tabpfn"
        return best_simple_model(events, country) if events is not None else "mean_last5"
    if name not in MODELS:
        raise ValueError(f"unknown model {name!r}; choose from {MODELS + ('auto',)}")
    return name


# --------------------------------------------------------------------- ML models
def _make_ml(name: str):
    if name == "tabpfn":
        from tabpfn import TabPFNRegressor  # lazy: optional dependency

        return TabPFNRegressor()  # defaults; it conditions on the rows in fit(), no training loop
    from sklearn.ensemble import GradientBoostingRegressor

    return GradientBoostingRegressor(n_estimators=120, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0)


def _tabpfn_interval(reg, row: pd.DataFrame):
    """Native 10-90% interval from TabPFN's predictive distribution, or None if unsupported."""
    try:
        res = reg.predict(row, output_type="quantiles", quantiles=[0.1, 0.9])
        flat = (
            np.concatenate([np.asarray(r, dtype=float).ravel() for r in res])
            if isinstance(res, (list, tuple))
            else np.asarray(res, dtype=float).ravel()
        )
        if flat.size == 2 and np.isfinite(flat).all():
            return float(flat[0]), float(flat[1])
    except Exception:
        pass
    return None


def _ml_halfwidth(name: str, X: pd.DataFrame, y: np.ndarray) -> float:
    typical = float(np.mean(y))
    k = min(6, len(y) // 3)
    if k < 2:
        return max(0.4 * typical, MIN_ABS_HALFWIDTH)
    reg = _make_ml(name)
    reg.fit(X.iloc[:-k], y[:-k])
    pred = np.asarray(reg.predict(X.iloc[-k:]), dtype=float)
    return _halfwidth(list(np.abs(y[-k:] - pred)), typical)


# --------------------------------------------------------------------- public API
def predict(
    events: pd.DataFrame,
    country: str,
    targets: list[dict],
    model: str = "auto",
    place: Place | None = None,
    intervals: bool = True,
) -> list[Prediction]:
    """Predict turnout for each planned event in `targets`.

    `events` is the normalized history (see features.normalize_events). Each target is a dict
    with `date`, `start_hour`, `duration` and `rain` (0/1, the organizer's expectation).
    """
    if len(events) < MIN_EVENTS:
        raise ValueError(f"need at least {MIN_EVENTS} past events, got {len(events)}")
    model = resolve_model(model, events, country)
    n = len(events)
    typical = float(events["attendance"].mean())
    cal = EventCalendar(country)

    if model in SIMPLE_MODELS:
        hw = _halfwidth(_one_step_errors(model, events, cal), typical) if intervals else 0.0
        fit = _fit_effects(events, cal) if model == "effects" else None
        out = []
        for t in targets:
            when = pd.Timestamp(t["date"]).normalize()
            if fit is not None:
                p = _effects_point(*fit[:3], cal, when, t["start_hour"], t["rain"])
            else:
                p = _baseline_point(model, events, when)
            out.append(Prediction(when, p, max(0.0, p - hw), p + hw, model, n))
        return out

    X, y = build_training(events, country, place)
    reg = _make_ml(model)
    reg.fit(X, y)
    hw = None
    out = []
    for t in targets:
        when = pd.Timestamp(t["date"]).normalize()
        row = pd.DataFrame(
            [event_row(events, when, t["start_hour"], t["duration"], t["rain"], cal, place)]
        )[FEATURES]
        p = max(0.0, float(np.asarray(reg.predict(row), dtype=float)[0]))
        lo = hi = p
        if intervals:
            native = _tabpfn_interval(reg, row) if model == "tabpfn" else None
            if native is not None:
                lo, hi = max(0.0, native[0]), max(p, native[1])
            else:
                if hw is None:
                    hw = _ml_halfwidth(model, X, y)
                lo, hi = max(0.0, p - hw), p + hw
        out.append(Prediction(when, p, lo, hi, model, n))
    return out
