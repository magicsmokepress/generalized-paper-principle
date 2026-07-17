"""Character operations for LLM agents — deterministic + a visualize-and-mark path.

The deterministic functions (count_letter, char_at, reverse_word) are exact and
should be the guarantee. `visual_spell` is the model-in-the-loop "render → look →
mark → count" method for when you want the model to *do* it with its eyes rather
than trust its token-sense; it is high-probability, not certain — back it with
the deterministic check.
"""
from __future__ import annotations

import base64
import io
import os
import re


# ── Deterministic (guaranteed correct) ────────────────────────────────────
def count_letter(word: str, letter: str) -> int:
    return word.lower().count(letter.lower())


def char_at(word: str, n: int, from_end: bool = False) -> str | None:
    """1-indexed character; from_end=True counts from the last character."""
    if not (1 <= n <= len(word)):
        return None
    return word[-n] if from_end else word[n - 1]


def reverse_word(word: str) -> str:
    return word[::-1]


# ── Visualize → mark → count (model-in-the-loop) ───────────────────────────
# Requires an OpenAI-compatible vision endpoint. Configure via env:
#   VLM_URL   (default http://localhost:1234/v1)
#   VLM_MODEL (default the server's default; set explicitly for most servers)
# and Pillow (`pip install Pillow`).
VLM_URL = os.environ.get("VLM_URL", "http://localhost:1234/v1")
VLM_MODEL = os.environ.get("VLM_MODEL", "")
_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_MARK_RE = re.compile(r"([A-Za-z])\s*[-–—:]\s*(yes|no)\b", re.I)
_ANSWER_RE = re.compile(r"ANSWER:\s*(\d+)", re.I)


def _render(word: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for p in _FONTS:
        if os.path.exists(p):
            font = ImageFont.truetype(p, 110)
            break
    if font is None:
        font = ImageFont.load_default()
    img = Image.new("RGB", (max(300, 68 * len(word) + 60), 200), "white")
    ImageDraw.Draw(img).text((30, 45), word, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def visual_spell(word: str, letter: str, timeout: float = 90.0) -> dict:
    """Render `word` in a clean font, have a VLM read it letter-by-letter marking
    each, count the marks. Returns {ok, read_back, read_matches, count, working}.
    Fail-open: returns ok=False if Pillow/vision/parse is unavailable — fall back
    to count_letter and/or the deterministic backstop."""
    try:
        png = _render(word)
    except Exception as e:
        return {"ok": False, "error": f"render failed ({e}); is Pillow installed?"}
    b64 = base64.b64encode(png).decode()
    prompt = ("Read the word in this image ONE LETTER AT A TIME, left to right. "
              f"For each letter output a line: <n>. <letter> - <yes if it is '{letter}', else no>. "
              "Cover EVERY letter. Then output: ANSWER: <how many were yes>")
    try:
        import httpx
        r = httpx.post(VLM_URL.rstrip("/") + "/chat/completions",
                       json={"model": VLM_MODEL, "max_tokens": 500, "temperature": 0,
                             "messages": [{"role": "user", "content": [
                                 {"type": "text", "text": prompt},
                                 {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]},
                       timeout=timeout)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"] or ""
    except Exception as e:
        return {"ok": False, "error": f"vision call failed ({e})"}
    letters, yes = [], []
    for line in text.splitlines():
        m = _MARK_RE.search(line)
        if m:
            letters.append(m.group(1))
            if m.group(2).lower() == "yes":
                yes.append(m.group(1))
    am = _ANSWER_RE.search(text)
    count = len(yes) if letters else (int(am.group(1)) if am else None)
    read = "".join(letters)
    return {"ok": count is not None, "read_back": read,
            "read_matches": read.lower() == word.lower(), "count": count,
            "working": text.strip()}


if __name__ == "__main__":
    assert count_letter("Accessories", "c") == 2
    assert count_letter("Mississippi", "s") == 4
    assert count_letter("parallel", "l") == 3
    assert char_at("kompressor", 4, from_end=True) == "s"
    assert char_at("python", 2) == "y"
    assert reverse_word("semaphore") == "erohpames"
    print("char_ops deterministic self-check ok "
          "(visual_spell needs a VLM endpoint + Pillow; see env vars)")
