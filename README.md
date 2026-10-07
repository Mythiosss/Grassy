# Grassy

**Know roughly who'll show up, and when to hold it.** A phone app for people who organize outdoor groups: run clubs, beach clean-ups, hiking and gardening groups.

Give it your past events (date, how many came). It tells you:

- **Expected turnout** for the dates you're considering, with a likely range
- **The best date** of those, when the history says dates differ
- **How many to plan supplies for** (the top of the range)
- **The latest start time** so you finish before sunset, worked out from your location
- **Heads-up** for holidays and festival seasons near a date
- **An invite** in your group's language (English, Bahasa Indonesia, Español, Kiswahili), ready to send on WhatsApp

It's a **PWA**: open the link on your phone, "Add to Home Screen", and it works with no signal. Your data stays on the phone.

## Run it

Phone/desktop, no install: serve `web/` from any static host (GitHub Pages, Netlify, `python -m http.server -d web`). Only `localhost` or HTTPS can install a PWA.

With the optional Smart-mode server (also serves the app):

```
pip install -r requirements.txt
python -m grassy.server        # http://localhost:8000
```

Deploy on Render with `render.yaml`. In the app: Settings → Smart-mode server address.

## Smart mode (optional, open-source AI)

| What | Model | Role |
|---|---|---|
| Better predictions | [TabPFN](https://github.com/PriorLabs/TabPFN) (`pip install -r requirements-tabpfn.txt`) | Used instead of the offline model when installed |
| Friendlier invites | Gemma via any OpenAI-compatible endpoint (e.g. Ollama) | Rewords the invite; rejected if it adds a number not in the draft |
| Voice | ElevenLabs | `/api/voice` |

The app sends only dates and head-counts, nothing is stored, and if the server is unreachable it falls back to the offline model and says so.

## How the offline prediction works

Three simple methods; the app uses whichever would have predicted *your group's* recent events best:

1. average of the last 5 events
2. average of the last 4 on the same weekday
3. **learned effects**: a small Poisson regression with shrinkage that learns how much rain, a late start, a holiday, a festival season or an off-day moves *your* turnout (shown in plain words under "What your group's history says")

The likely range is the 80th percentile of the model's own past misses (one-step-ahead), never narrower than 2 people or 15% of typical turnout.

## What was measured (synthetic data!)

`python -m grassy.backtest`-style experiment on 4 **made-up** groups (90 events each, rain/holiday/start-time effects built in plus lots of randomness). Error is wMAPE (lower is better):

| Past events | last-5 avg | learned effects | gradient boosting |
|---|---|---|---|
| 6 | 45% | 44% | 52% |
| 12 | 45% | 44% | 49% |
| 24 | 45% | 43% | 55% |
| 40 | 45% | 42% | 47% |

Honest reading: single events are mostly unpredictable (about 42–45% error whatever the method). Learned effects help a little with more history, and mostly their value is *explaining* what moves turnout. Ranges cover only about 58–73% of real outcomes at 6–8 events (nominal 80%), around 75–79% from 12 events, so the app labels histories under 12 events "low confidence". See `docs/learning_curve.png`.

**TabPFN has not been benchmarked here** (it couldn't be installed in the build sandbox). Any claim that it beats these baselines is untested until you run it: `pip install tabpfn` then the backtest with `models=("effects","tabpfn")`.

## What's verified, what isn't

| Item | Status |
|---|---|
| Sun times, calendars, models: JS matches Python | tested (`node --test tests/js/*.test.mjs`, fixtures from `tools/export_web_data.py`) |
| CSV import (EN/ID/ES/SW headers, day-first dates), views escape user text, no "undefined"/"NaN" on screen | tested |
| Phone UI in headless Chromium (mobile viewport): plan, history, language switch, **offline reload** | run (`tests/e2e_browser.py`) |
| Smart-mode server end to end, CORS, fallback when unreachable | run (`tests/e2e_smart_mode.py`, `tests/test_core.py`) |
| TabPFN, Gemma, ElevenLabs calls | **not run** (no network access to them in the build sandbox) |
| Installing on a real phone / iOS Safari | **not run** |
| Translations | AI-written, **not reviewed by native speakers** |
| Holiday dates | approximate (2023–2027), **not official** |

## Layout

```
web/            the phone app (static; js/ has the engine, planner, views)
grassy/         Python: same engine (reference), Smart-mode server, backtest
tests/          Python unittest, Node tests, browser e2e, parity fixtures
tools/          export_web_data.py (fixtures), make_icons.py
docs/           backtest results, DEV post outline, field-notes template, deploy guide
```

Rename the project in `grassy/__init__.py`, `web/index.html`, `web/manifest.webmanifest` and the logo in `web/js/views.js`.

Licence: MIT.
