"""Character operations for LLM agents.

Design for universality — TWO separable concerns:

  1. PERCEPTION: turning pixels into letters. Only needed when the word is NOT
     already clean text (it came from a camera/screenshot/photo). This is a
     PLUGGABLE backend — a `reader(png_bytes) -> str`. Bring whatever you have:
     an OpenAI-compatible vision model, Tesseract, a Coral/Edge-TPU OCR model,
     a cloud OCR API. Perception is the imperfect layer.
  2. COUNTING / INDEXING / REVERSING: deterministic, exact, no model. This is
     the guarantee, and it runs on whatever text perception produced.

If the word is already text, skip perception entirely — `count_letter` etc. are
exact and need nothing. Perception is required ONLY for image-sourced words.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Callable

# A perception backend: PNG bytes -> recognized text.
Reader = Callable[[bytes], str]


# ── COUNTING (deterministic, guaranteed correct, no model) ─────────────────
def count_letter(word: str, letter: str) -> int:
    return word.lower().count(letter.lower())


def char_at(word: str, n: int, from_end: bool = False) -> str | None:
    """1-indexed character; from_end=True counts from the last character."""
    if not (1 <= n <= len(word)):
        return None
    return word[-n] if from_end else word[n - 1]


def reverse_word(word: str) -> str:
    return word[::-1]


# ── PERCEPTION (pluggable; needed only for image-sourced words) ────────────
def vlm_reader(url: str | None = None, model: str | None = None,
               timeout: float = 60.0) -> Reader:
    """Built-in reader backed by an OpenAI-compatible VISION endpoint. Configure
    via args or env VLM_URL / VLM_MODEL. Prompts the model to TRANSCRIBE (not
    count) — transcription is easier and more reliable for a VLM than counting,
    and the deterministic layer does the counting."""
    url = (url or os.environ.get("VLM_URL", "http://localhost:1234/v1")).rstrip("/")
    model = model or os.environ.get("VLM_MODEL", "")

    def _read(png: bytes) -> str:
        import httpx
        b64 = base64.b64encode(png).decode()
        r = httpx.post(url + "/chat/completions",
                       json={"model": model, "max_tokens": 120, "temperature": 0,
                             "messages": [{"role": "user", "content": [
                                 {"type": "text", "text": "Transcribe the exact text in this "
                                  "image. Output ONLY the characters, nothing else."},
                                 {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]},
                       timeout=timeout)
        r.raise_for_status()
        return (r.json()["choices"][0]["message"]["content"] or "").strip()
    return _read


def tesseract_reader() -> Reader:
    """Reader backed by Tesseract (needs `pytesseract` + the tesseract binary).
    A local, model-free OCR option — no GPU, no service."""
    def _read(png: bytes) -> str:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(io.BytesIO(png))).strip()
    return _read


# For a Coral / Edge-TPU or cloud-OCR backend, write a `reader(png)->str` that
# runs your edgetpu-compiled recognizer (or cloud call) and returns the text,
# then pass it as `reader=...`. Coral suits local, low-power OCR of clean,
# fronto-parallel text feeding the deterministic counter; it is weaker than a
# modern VLM on stylized/angled real-world text.


def _render(word: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
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


def text_from_image(png: bytes, reader: Reader | None = None) -> str:
    """Perceive the letters in an image via a pluggable reader (default: env VLM)."""
    return (reader or vlm_reader())(png)


def count_letter_in_image(png: bytes, letter: str, reader: Reader | None = None) -> int:
    """Real-image case: OCR the image, then count deterministically. The count is
    exact GIVEN the perception; the perception (reader) is the uncertain layer."""
    return count_letter(text_from_image(png, reader), letter)


def visual_spell(word: str, letter: str | None = None, reader: Reader | None = None) -> dict:
    """Round-trip a KNOWN word: render it in a clean font YOU control, read it
    back with the perception backend, and count deterministically. The read-back
    vs the word is a self-consistency check on the reader. (For a word already
    in text form you do not need this — use count_letter directly.)
    Returns {ok, read_back, read_matches, count?, error?}. Fail-open."""
    try:
        png = _render(word)
    except Exception as e:
        return {"ok": False, "error": f"render failed ({e}); is Pillow installed?"}
    try:
        read = text_from_image(png, reader)
    except Exception as e:
        return {"ok": False, "error": f"perception failed ({e})"}
    out = {"ok": True, "read_back": read, "read_matches": read.lower() == word.lower()}
    if letter:
        out["count"] = count_letter(read, letter)   # deterministic count on the perceived text
    return out


if __name__ == "__main__":
    # Deterministic layer — the guarantee, no model, no vision.
    assert count_letter("Accessories", "c") == 2
    assert count_letter("Mississippi", "s") == 4
    assert count_letter("parallel", "l") == 3
    assert char_at("kompressor", 4, from_end=True) == "s"
    assert char_at("python", 2) == "y"
    assert reverse_word("semaphore") == "erohpames"
    # Perception is pluggable — a fake reader proves counting runs on ITS output.
    fake = lambda png: "Accessories"
    assert visual_spell("Accessories", "c", reader=fake)["count"] == 2
    assert count_letter_in_image(b"", "s", reader=lambda p: "Mississippi") == 4
    print("char_ops self-check ok (deterministic counting; perception is a pluggable reader)")
