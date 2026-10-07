"""The headline experiment: how many past events are enough?

For each history size (6, 8, 12, 16, 24, 40 events) we take the most recent `size` events
before many different origins, predict the NEXT event (knowing only what an organizer would
know in advance: date, start time, rain expectation), and score it against what really
happened. Every model sees the same origins, so the curves are directly comparable.

Metrics
  wMAPE     sum|error| / sum(actual): scale-free, so a 14-person and a 50-person group average fairly.
  coverage  how often the real turnout fell inside the stated "likely range".
  short     how often more people came than the top of the range (a supply shortfall if you planned for it).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data import GROUPS, generate_group
from .features import normalize_events
from .predict import predict, resolve_model
from .sun import Place

DEFAULT_SIZES = (6, 8, 12, 16, 24, 40)


def learning_curve(
    events: pd.DataFrame,
    country: str,
    place: Place | None = None,
    models=("mean_last5", "same_weekday", "effects", "gbr"),
    sizes=DEFAULT_SIZES,
    n_origins: int = 12,
) -> pd.DataFrame:
    """Long table: model, size, wmape, mae, coverage, short, n for one group (events already normalized)."""
    models = [resolve_model(m) for m in models]
    max_size = max(sizes)
    if len(events) <= max_size + 1:
        raise ValueError(f"only {len(events)} events; need more than {max_size + 1} to test a window of {max_size}")
    origins = np.unique(np.linspace(max_size, len(events) - 1, n_origins).astype(int))

    rows = []
    for model in models:
        for size in sizes:
            abs_err = actual_sum = 0.0
            hit = short = n = 0
            for o in origins:
                train = events.iloc[o - size : o].reset_index(drop=True)
                e = events.iloc[o]
                target = {"date": e["date"], "start_hour": e["start_hour"], "duration": e["duration"], "rain": e["rain"]}
                p = predict(train, country, [target], model=model, place=place)[0]
                actual = float(e["attendance"])
                abs_err += abs(actual - p.point)
                actual_sum += actual
                hit += p.low <= actual <= p.high
                short += actual > p.high
                n += 1
            rows.append(
                {
                    "model": model,
                    "size": size,
                    "wmape": abs_err / max(actual_sum, 1e-9),
                    "mae": abs_err / n,
                    "coverage": hit / n,
                    "short": short / n,
                    "n": n,
                }
            )
    return pd.DataFrame(rows)


def run_all_groups(models=("mean_last5", "same_weekday", "effects", "gbr"), sizes=DEFAULT_SIZES, **kw) -> pd.DataFrame:
    frames = []
    for kind, cfg in GROUPS.items():
        events, _ = normalize_events(generate_group(kind, n_events=90))
        lc = learning_curve(events, cfg["country"], cfg["place"], models=models, sizes=sizes, **kw)
        lc.insert(0, "group", kind)
        frames.append(lc)
    return pd.concat(frames, ignore_index=True)


def plot_learning_curve(results: pd.DataFrame, path: str | Path, title: str | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    avg = results.groupby(["model", "size"], as_index=False)["wmape"].mean()
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=150)
    styles = {
        "tabpfn": ("#c2410c", "o", 2.6),
        "gbr": ("#9ca3af", "s", 1.4),
        "effects": ("#2563eb", "D", 2.4),
        "same_weekday": ("#059669", "^", 1.8),
        "mean_last5": ("#6b7280", "v", 1.8),
    }
    for model, g in avg.groupby("model"):
        color, marker, lw = styles.get(model, ("#444", "o", 1.5))
        ax.plot(g["size"], g["wmape"] * 100, label=model, color=color, marker=marker, lw=lw)
    ax.set_xscale("log")
    ax.minorticks_off()  # log axes add minor labels that collide with ours
    ax.set_xticks(sorted(avg["size"].unique()))
    ax.set_xticklabels([str(x) for x in sorted(avg["size"].unique())])
    ax.set_xlabel("Past events the group has on record")
    ax.set_ylabel("Turnout prediction error, wMAPE % (lower is better)")
    ax.set_title(title or "How many past events are enough? (4 synthetic groups)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
