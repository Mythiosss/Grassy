"""Optional Smart-mode server (standard library only, so it runs anywhere Python does).

    python -m grassy.server            # http://localhost:8000, serves the phone app too

POST /api/predict {country, events:[{date,attendance,start?,duration?,rain?}], targets:[{date,start?,duration?,rain?}]}
POST /api/invite  {draft, lang}
POST /api/voice   {text}
GET  /api/config, GET /health

Nothing is stored or logged beyond the standard request line. TabPFN is used when installed;
otherwise the best simple model is used (and reported).
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

from . import APP_NAME, __version__
from .features import MIN_EVENTS, normalize_events, parse_hhmm
from .invite import llm_available, polish
from .predict import predict, resolve_model, tabpfn_available
from .voice import synthesize, voice_available

WEB = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 256 * 1024
MAX_EVENTS = 2000
MAX_TARGETS = 60
COUNTRIES = {"ID", "KE", "MX", "IN"}


class BadRequest(Exception):
    pass


def handle_predict(payload: dict) -> dict:
    country = payload.get("country", "ID")
    if country not in COUNTRIES:
        country = "ID"  # unknown country: no local holiday notes, same model
    rows, targets = payload.get("events"), payload.get("targets")
    if not isinstance(rows, list) or not isinstance(targets, list):
        raise BadRequest("events and targets must be lists")
    if len(rows) > MAX_EVENTS or not 0 < len(targets) <= MAX_TARGETS:
        raise BadRequest("too many events or targets")
    try:
        df = pd.DataFrame(rows)
        if "date" not in df or "attendance" not in df:
            raise BadRequest("each event needs date and attendance")
        events, _ = normalize_events(df)
        if len(events) < MIN_EVENTS:
            raise BadRequest(f"need at least {MIN_EVENTS} past events")
        tg = []
        default_start = float(events["start_hour"].median())
        default_dur = float(events["duration"].median())
        for t in targets:
            start = parse_hhmm(t.get("start")) if t.get("start") else float("nan")
            tg.append(
                {
                    "date": pd.Timestamp(t["date"]).normalize(),
                    "start_hour": default_start if pd.isna(start) else start,
                    "duration": float(t.get("duration") or default_dur),
                    "rain": 1.0 if float(t.get("rain") or 0) > 0 else 0.0,
                }
            )
    except BadRequest:
        raise
    except Exception as e:  # malformed dates, numbers...
        raise BadRequest(f"could not read the request: {e}")
    model = resolve_model("auto", events, country)
    try:
        preds = predict(events, country, tg, model="auto")
    except Exception:
        if model != "tabpfn":
            raise
        preds = predict(events, country, tg, model="effects")  # TabPFN failed (e.g. no weights): stay useful
        model = "effects"
    return {
        "model": model,
        "predictions": [
            {"date": p.date.date().isoformat(), "point": p.point, "low": p.low, "high": p.high} for p in preds
        ],
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):  # request line only, never bodies
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            return self._json({"ok": True, "app": APP_NAME, "version": __version__})
        if self.path == "/api/config":
            return self._json({"tabpfn": tabpfn_available(), "gemma": llm_available(), "voice": voice_available()})
        if self.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                raise BadRequest("body missing or too large")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise BadRequest("expected a JSON object")
            if self.path == "/api/predict":
                return self._json(handle_predict(payload))
            if self.path == "/api/invite":
                text, source = polish(str(payload.get("draft", ""))[:2000], str(payload.get("lang", "en"))[:5])
                return self._json({"text": text, "source": source})
            if self.path == "/api/voice":
                audio = synthesize(str(payload.get("text", ""))[:1500])
                if audio is None:
                    return self._json({"error": "voice not configured"}, 503)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio)))
                self.end_headers()
                self.wfile.write(audio)
                return
            return self._json({"error": "not found"}, 404)
        except (BadRequest, json.JSONDecodeError) as e:
            return self._json({"error": str(e)}, 400)
        except Exception:
            return self._json({"error": "server error"}, 500)


def main(argv=None):
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"{APP_NAME} on http://localhost:{port}  (tabpfn={tabpfn_available()}, gemma={llm_available()}, voice={voice_available()})")
    server.serve_forever()


if __name__ == "__main__":
    main()
