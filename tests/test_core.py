import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pandas as pd

from grassy.calendar import EventCalendar
from grassy.data import GROUPS, generate_group
from grassy.features import MIN_EVENTS, build_training, normalize_events
from grassy.invite import grounded, polish
from grassy.predict import best_simple_model, effect_summary, predict
from grassy.sun import Place, sun_times

ROOT = Path(__file__).resolve().parent.parent


def events(kind="beach_cleanup_id", n=30):
    ev, _ = normalize_events(generate_group(kind, n_events=n))
    return ev, GROUPS[kind]


class Sun(unittest.TestCase):
    def test_equator_about_twelve_hours(self):
        s = sun_times(date(2026, 3, 20), Place(0.0, 0.0, 0))
        self.assertAlmostEqual(s.daylight_min / 60, 12.1, delta=0.2)

    def test_london_solstices(self):
        p = Place(51.5, -0.12, 0)
        self.assertGreater(sun_times(date(2026, 6, 21), p).daylight_min / 60, 16.3)
        self.assertLess(sun_times(date(2026, 12, 21), p).daylight_min / 60, 8.2)


class Data(unittest.TestCase):
    def test_deterministic(self):
        a, b = generate_group("run_club_ke", n_events=20), generate_group("run_club_ke", n_events=20)
        self.assertTrue(a.equals(b))

    def test_normalize_defaults_and_dedupe(self):
        df = pd.DataFrame({"date": ["2026-01-03", "2026-01-03", "2026-01-10"], "attendance": [5, 7, "x"]})
        ev, meta = normalize_events(df)
        self.assertEqual(len(ev), 1)  # duplicate collapsed, bad count dropped
        self.assertEqual(ev["attendance"].iloc[0], 7)
        self.assertFalse(meta["has_start"])
        self.assertEqual(ev["start_hour"].iloc[0], 7.0)


class Features(unittest.TestCase):
    def test_no_leakage(self):
        ev, cfg = events()
        X, y = build_training(ev, cfg["country"], cfg["place"])
        # last_att for row i must be the attendance of event i (the previous event of target i+1)
        self.assertTrue(np.allclose(X["last_att"].to_numpy(), ev["attendance"].to_numpy()[:-1]))
        self.assertEqual(len(X), len(ev) - 1)


class Predict(unittest.TestCase):
    def setUp(self):
        self.ev, self.cfg = events()
        self.target = [{"date": "2026-10-10", "start_hour": 7.0, "duration": 120, "rain": 0}]

    def test_models_produce_ordered_ranges(self):
        for m in ("mean_last5", "same_weekday", "effects", "gbr"):
            p = predict(self.ev, self.cfg["country"], self.target, model=m, place=self.cfg["place"])[0]
            self.assertLessEqual(p.low, p.point)
            self.assertLessEqual(p.point, p.high)
            self.assertGreaterEqual(p.low, 0)

    def test_too_few_events(self):
        with self.assertRaises(ValueError):
            predict(self.ev.iloc[: MIN_EVENTS - 1], "ID", self.target, model="mean_last5")

    def test_rain_effect_has_sensible_sign(self):
        es = effect_summary(self.ev, self.cfg["country"])
        self.assertLess(es["rain"], 1.0)  # the synthetic groups lose people when it rains

    def test_auto_picks_a_simple_model(self):
        self.assertIn(best_simple_model(self.ev, self.cfg["country"]), ("mean_last5", "same_weekday", "effects"))

    def test_javascript_parity_fixture_is_current(self):
        fx = json.loads((ROOT / "tests" / "fixtures" / "parity.json").read_text())
        c = fx["cases"][0]
        ev, _ = normalize_events(pd.DataFrame(c["events"]))
        from grassy.features import parse_hhmm

        tg = [{"date": t["date"], "start_hour": parse_hhmm(t["start"]), "duration": t["duration"], "rain": t["rain"]} for t in c["targets"]]
        got = predict(ev, c["country"], tg, model="effects")
        for g, e in zip(got, c["expected"]["effects"]):
            self.assertAlmostEqual(g.point, e["point"], places=9)


class Calendar(unittest.TestCase):
    def test_season_and_holiday(self):
        cal = EventCalendar("ID")
        self.assertTrue(cal.in_season(pd.Timestamp("2026-03-01")) or cal.in_season(pd.Timestamp("2026-02-25")))


class Invite(unittest.TestCase):
    def test_guard(self):
        draft = "Sat 10 Oct, 07:30. Bring water."
        self.assertTrue(grounded(draft, "See you Sat 10 Oct at 07:30!"))
        self.assertFalse(grounded(draft, "See you Sat 10 Oct at 08:30 with 50 people"))
        self.assertFalse(grounded(draft, "  "))

    def test_without_llm_returns_draft(self):
        self.assertEqual(polish("Hello 5", "en"), ("Hello 5", "draft"))


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from grassy.server import Handler

        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, body=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_health_config_and_static(self):
        self.assertEqual(self.call("/health")[0], 200)
        cfg = json.loads(self.call("/api/config")[1])
        self.assertEqual(set(cfg), {"tabpfn", "gemma", "voice"})
        status, body = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Grassy", body)

    def test_predict_end_to_end(self):
        raw = generate_group("garden_group_in", n_events=24)
        rows = [{"date": r.date.date().isoformat(), "attendance": int(r.attendance), "start": r.start, "duration": int(r.duration), "rain": int(r.rain)} for r in raw.itertuples()]
        status, body = self.call("/api/predict", {"country": "IN", "events": rows, "targets": [{"date": "2026-10-10", "start": "07:00", "duration": 120, "rain": 0}, {"date": "2026-10-10", "rain": 1}]})
        self.assertEqual(status, 200, body)
        j = json.loads(body)
        self.assertEqual(len(j["predictions"]), 2)
        for p in j["predictions"]:
            self.assertLessEqual(p["low"], p["point"] + 1e-9)
            self.assertLessEqual(p["point"], p["high"] + 1e-9)

    def test_bad_requests(self):
        self.assertEqual(self.call("/api/predict", {"events": [], "targets": []})[0], 400)
        self.assertEqual(self.call("/api/predict", {"events": [{"date": "2026-01-01", "attendance": 3}] * 3, "targets": [{"date": "2026-10-10"}]})[0], 400)
        self.assertEqual(self.call("/api/predict", {"events": "no", "targets": 1})[0], 400)
        self.assertEqual(self.call("/api/nope", {})[0], 404)
        self.assertEqual(self.call("/api/voice", {"text": "hi"})[0], 503)  # not configured here


if __name__ == "__main__":
    unittest.main()
