"""Optional: let Gemma reword an invite, without letting it change any fact.

The phone app writes a plain invite from known facts. Smart mode may ask Gemma (any
OpenAI-compatible endpoint, e.g. Ollama) to make it friendlier. Because language models can
invent details, the reply is accepted only if every number in it already appears in the draft.
Otherwise the draft is returned unchanged.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

NUM = re.compile(r"\d+")


def numbers(text: str) -> set[str]:
    return set(NUM.findall(text))


def grounded(draft: str, candidate: str) -> bool:
    """True when the candidate adds no number that the draft did not have."""
    return bool(candidate.strip()) and numbers(candidate) <= numbers(draft)


def _cfg():
    base = os.getenv("GRASSY_BASE_URL") or os.getenv("GEMMA_BASE_URL")
    model = os.getenv("GRASSY_MODEL") or os.getenv("GEMMA_MODEL")
    key = os.getenv("GRASSY_API_KEY") or os.getenv("GEMMA_API_KEY") or "none"
    return (base, model, key) if base and model else None


def llm_available() -> bool:
    return _cfg() is not None


def polish(draft: str, lang: str = "en", timeout: float = 30.0) -> tuple[str, str]:
    """-> (text, source) where source is 'gemma' or 'draft'."""
    cfg = _cfg()
    if not cfg or not draft.strip():
        return draft, "draft"
    base, model, key = cfg
    prompt = (
        f"Rewrite this invitation for an outdoor group so it sounds warm and short, in the language with code '{lang}'. "
        "Keep every date, time and fact exactly as given. Do not add numbers, places or promises. "
        "Reply with the message only.\n\n" + draft
    )
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4}).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = json.load(resp)["choices"][0]["message"]["content"].strip()
    except Exception:
        return draft, "draft"
    return (text, "gemma") if grounded(draft, text) else (draft, "draft")
