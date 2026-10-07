"""Optional voice replies through ElevenLabs text-to-speech.

Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID. Returns MP3 bytes, or None when voice is not
configured or the request fails, so the rest of the app never depends on it.
"""

from __future__ import annotations

import json
import os
import urllib.request

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MODEL_ID = "eleven_multilingual_v2"  # covers Indonesian, Spanish and Swahili among others


def voice_available() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"))


def synthesize(text: str, timeout: float = 60.0) -> bytes | None:
    if not voice_available() or not text.strip():
        return None
    url = API.format(voice_id=os.environ["ELEVENLABS_VOICE_ID"])
    body = json.dumps({"text": text, "model_id": MODEL_ID}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None
